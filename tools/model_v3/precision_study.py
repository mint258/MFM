"""Fixed single-step deviations and the prescribed precision speed grid."""
import argparse
import csv
import json
import os
from pathlib import Path
import socket
import subprocess
import threading
import time

import numpy as np
import torch

from phychem_mfm.model.precision import MODES, configure_precision

REPO = Path(__file__).resolve().parents[2]
G1 = '/lfshome/zixiao/model_v31_20261105/P_RECIPE_20261113/calibration_20261114/calibration_20261114_G1_B32_lr3e4_sbatch_cuda_recovery_continued/samples_3000000.pt'


def configuration(path=None):
    path = path or REPO/'configs/p_recipe/calibration_20261114/training/G1_B32_lr3e4.json'
    c = json.loads(Path(path).read_text())
    for key in tuple(c):
        if key.startswith('resume') or key.startswith('handoff') or key in ('required_gpu_uuid','attempt','recovery_reason','protocol_exception'):
            c.pop(key)
    return c


def build(c):
    from phychem_mfm.phase1.p_recipe_data import PRecipeDataset, dataset_configuration
    from phychem_mfm.phase1.v31_training import V31PDModel
    from phychem_mfm.phase1.v2_s_training import s_model
    torch.set_num_threads(1)
    torch.manual_seed(0)
    data = PRecipeDataset(**dataset_configuration(c))
    structural, _ = s_model('C1-0','three')
    structural.encoder.backbone.activation_checkpointing = c['activation_checkpointing']
    pd = V31PDModel(structural.encoder,data.view,forms=c['head_form'],pooling='registry',p_recipe=c['p_recipe'])
    model = torch.nn.ModuleDict(dict(structural=structural,pd=pd)).cuda().train()
    fields = tuple(f.name for f in pd.registry.enabled(('P',)))
    heads = {pd.selections[n][0] for n in fields}
    families = {f.name:f.family for f in pd.head_registry.fields if f.name in heads}
    return model,data,fields,families


def calculate(model,samples,fields,families):
    from phychem_mfm.phase1.v31_loader import encode_samples
    from phychem_mfm.phase1.p_recipe import normalized_field_weights
    pd = model['pd']
    clean,h = encode_samples(samples,pd.encoder,device='cuda')
    prediction = pd.predict(samples,groups=('P',),fields=fields,clean_features=h,clean_batch=clean)
    loss = pd.loss(prediction,samples,groups=('P',),fields=fields)
    active = {n:families[n] for n in loss.fields if loss.counts[n]>0}
    weights = normalized_field_weights(active,device='cuda')
    total = sum((loss.fields[n]*w for n,w in weights.items()),loss.total.new_zeros(()))
    return total,loss


def numerical(c,output,checkpoint):
    model,data,fields,families = build(c)
    params = list(model.parameters())
    initial = {key:value.detach().cpu().clone() if isinstance(value,torch.Tensor) else value
               for key,value in model.state_dict().items()}
    rng = np.random.default_rng(0)
    choices = []
    for _ in range(20):
        batch = []
        for _ in range(32):
            molecule = int(rng.choice(data.indices))
            batch.append((molecule,int(rng.choice(data.choices(molecule)))))
        choices.append(batch)
    batches = [[data.read(m,conf) for m,conf in batch] for batch in choices]
    (output/'choices.json').write_text(json.dumps(choices)+'\n')
    rows = []
    def step(samples):
        model.zero_grad(set_to_none=True)
        torch.manual_seed(0)
        total,loss = calculate(model,samples,fields,families)
        total.backward()
        values = {name:float(value.detach()) for name,value in loss.fields.items() if loss.counts[name]>0}
        values['TOTAL'] = float(total.detach())
        gradient = torch.cat([p.grad.detach().flatten() if p.grad is not None else torch.zeros_like(p).flatten() for p in params]).cpu()
        if not all(np.isfinite(v) for v in values.values()) or not bool(torch.isfinite(gradient).all()):
            raise FloatingPointError('NaN/Inf in losses or complete parameter gradient')
        return values,gradient
    for weights in ('seed0','G1_3M'):
        state = initial if weights=='seed0' else torch.load(checkpoint,map_location='cpu',weights_only=True)['model']
        model.load_state_dict(state)
        configure_precision(model,'fp32')
        reference = [step(batch) for batch in batches]
        for mode in ('fp32_repeat','tf32_islands','bf16_islands'):
            configure_precision(model,'fp32' if mode=='fp32_repeat' else mode)
            for ordinal,(batch,(base_losses,base_gradient)) in enumerate(zip(batches,reference)):
                losses,gradient = step(batch)
                baseline = base_gradient.double()
                relative = float((gradient.double()-baseline).norm()/baseline.norm().clamp_min(torch.finfo(torch.float64).tiny))
                for name,value in losses.items():
                    old = base_losses[name]
                    rows.append(dict(weights=weights,mode=mode,batch=ordinal,field=name,fp32_loss=old,
                        candidate_loss=value,loss_relative_difference=abs(value-old)/max(abs(old),np.finfo(float).tiny),
                        gradient_relative_L2=relative,gradient_elements=gradient.numel()))
                print(json.dumps(dict(weights=weights,mode=mode,batch=ordinal,gradient_relative_L2=relative)),flush=True)
            with (output/'deviations.csv').open('w',newline='') as stream:
                writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
        del reference
    data.close()
    result=dict(status='COMPLETE',node=socket.gethostname(),gpu=torch.cuda.get_device_name(0),
        uuid=os.environ['CUDA_VISIBLE_DEVICES'],batches=20,initializations=['seed0','G1_3M'],
        gradient_elements=sum(p.numel() for p in params),numeric_acceptance='Report only; NaN/Inf fails')
    (output/'numerical.json').write_text(json.dumps(result,indent=2)+'\n')


def benchmark(c,output,mode,batch):
    from phychem_mfm.phase1.p_recipe_training import train
    c.update(precision=mode,batch_size=batch,microbatch_size=batch,activation_checkpointing=batch==128,
        benchmark_updates=1100,run='precision_speed_'+output.name,output=str(output/'training'))
    c['workers'] = min(14,max(1,int(os.environ.get('SLURM_CPUS_PER_TASK','16'))-2))
    stop = threading.Event()
    telemetry = []
    def capture():
        while not stop.is_set():
            raw = subprocess.check_output(['nvidia-smi','-i',os.environ['CUDA_VISIBLE_DEVICES'],
                '--query-gpu=power.draw,memory.used,utilization.gpu','--format=csv,noheader,nounits'],text=True).strip()
            telemetry.append([time.time(),*map(float,raw.split(','))])
            stop.wait(1)
    monitor = threading.Thread(target=capture,daemon=True);monitor.start()
    try:
        result = train(c)
    finally:
        stop.set();monitor.join(timeout=5)
        with (output/'gpu.csv').open('w',newline='') as stream:
            writer=csv.writer(stream);writer.writerow(['unix_seconds','power_W','memory_MiB','GPU_percent']);writer.writerows(telemetry)
    measured=[row for row in telemetry if result['measure_wall_start']<=row[0]<=result['measure_wall_end']]
    if not measured:raise RuntimeError('No measured GPU telemetry')
    result.update(gpu=torch.cuda.get_device_name(0),uuid=os.environ['CUDA_VISIBLE_DEVICES'],node=socket.gethostname(),
        power_W=float(np.mean([r[1] for r in measured])),activation_checkpointing=c['activation_checkpointing'],workers=c['workers'])
    (output/'benchmark.json').write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':
    if socket.gethostname().split('.')[0]=='compute-0-21':
        raise RuntimeError('User excludes compute-0-21 from this study')
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=('numerical','benchmark'))
    parser.add_argument('--configuration')
    parser.add_argument('--checkpoint',default=G1)
    parser.add_argument('--output',required=True)
    parser.add_argument('--precision',choices=MODES,default='fp32')
    parser.add_argument('--batch-size',type=int,choices=(32,128),default=32)
    args=parser.parse_args()
    output=Path(args.output);output.mkdir(parents=True,exist_ok=False)
    c=configuration(args.configuration)
    if args.action=='numerical':numerical(c,output,args.checkpoint)
    else:benchmark(c,output,args.precision,args.batch_size)
