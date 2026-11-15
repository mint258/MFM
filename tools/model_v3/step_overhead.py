"""Taskbook-controlled capacity, single-step equivalence and timing runs."""
import argparse
import csv
import heapq
import json
import os
from pathlib import Path
import socket
import subprocess
import threading
import time
import xml.etree.ElementTree as ET

import numpy as np
import torch

BASE = Path('/share/home/zixiao/descriptor_analysis')
REPO = Path(__file__).resolve().parents[2]
CONFIG = BASE/'MFM_p_recipe/configs/p_recipe/calibration_20261114/training/G1_B32_lr3e4.json'
G1 = Path('/lfshome/zixiao/model_v31_20261105/P_RECIPE_20261113/calibration_20261114/calibration_20261114_G1_B32_lr3e4_sbatch_cuda_recovery_continued/samples_3000000.pt')


def configuration():
    c = json.loads(CONFIG.read_text())
    for name in ('resume', 'required_gpu_uuid', 'handoff_request', 'handoff_ack', 'resume_from_output'):
        c.pop(name, None)
    c['workers'] = min(14, max(1, int(os.environ.get('SLURM_CPUS_PER_TASK', '16'))-2))
    return c


def model_for(c, options, device='cuda'):
    from phychem_mfm.phase1.v2_s_training import s_model
    from phychem_mfm.phase1.v31_training import V31PDModel
    from phychem_mfm.phase1.p_recipe import UncertaintyWeights
    from phychem_mfm.phase1.p_recipe_data import PRecipeDataset, dataset_configuration
    torch.set_num_threads(1)
    torch.manual_seed(0)
    data = PRecipeDataset(**dataset_configuration(c))
    structural, _ = s_model('C1-0', 'three')
    structural.encoder.backbone.activation_checkpointing = False
    pd = V31PDModel(structural.encoder, data.view, forms=c['head_form'], pooling='registry', p_recipe=c['p_recipe'])
    pd.configure_step_overhead(options)
    fields = tuple(f.name for f in pd.registry.enabled(('P',)))
    heads = {pd.selections[n][0] for n in fields}
    families = {f.name:f.family for f in pd.head_registry.fields if f.name in heads}
    modules = dict(structural=structural, pd=pd)
    recipe = c['p_recipe']
    if recipe.get('uncertainty_weighting', False):
        modules['uncertainty'] = UncertaintyWeights(sorted(set(families.values())) if recipe.get('family_equal') else list(families))
    return torch.nn.ModuleDict(modules).to(device).train(), data, fields, families


def calculate(model, samples, c, fields, families):
    from phychem_mfm.phase1.v31_loader import encode_samples
    from phychem_mfm.phase1.p_recipe_training import family_losses
    from phychem_mfm.phase1.p_recipe import normalized_field_weights, collapse_penalty
    pd = model['pd']
    clean, h = encode_samples(samples, pd.encoder, device='cuda')
    predictions = pd.predict(samples, groups=('P',), fields=fields, clean_features=h, clean_batch=clean)
    loss = pd.loss(predictions, samples, groups=('P',), fields=fields)
    recipe = c['p_recipe']
    family = family_losses(loss, families)
    active = {n:families[n] for n in loss.fields if loss.counts[n]>0}
    if recipe.get('uncertainty_weighting'):
        total = model['uncertainty'](family if recipe.get('family_equal') else {n:loss.fields[n] for n in active})
    elif pd.grouped_fields and active:
        values = torch.stack([loss.fields[n] for n in active])
        if recipe.get('family_equal'):
            groups = set(active.values())
            weights = values.new_tensor([1/(len(groups)*list(active.values()).count(g)) for g in active.values()])
            total = (values*weights).sum()
        else:
            total = values.mean()
    else:
        weights = normalized_field_weights(active, family_equal=recipe.get('family_equal', False), device='cuda')
        total = sum((loss.fields[n]*w for n,w in weights.items()), loss.total.new_zeros(()))
    if recipe.get('anti_collapse'):
        total = total+.1*collapse_penalty(h, recipe.get('gamma', .1597693323500406))
    return total, loss


def draw(data, rng, count):
    choices = []
    for _ in range(count):
        molecule = int(rng.choice(data.indices))
        choices.append((molecule, int(rng.choice(data.choices(molecule)))))
    return choices


def capacity(c, output, options):
    execution = dict(grouped_fields=True, head_checkpointing=False, distance_tiling=options.get('distance_tiling',False))
    model, data, fields, families = model_for(c, execution)
    rng = np.random.default_rng(0)
    heavy = []
    for ordinal in range(1000):
        choices = draw(data, rng, 32)
        lengths = [len(data.record('M', m)[1]) for m,_ in choices]
        score = 32*max(lengths)**2+sum(n*n for n in lengths)
        heapq.heappush(heavy, (score, ordinal, choices, lengths))
        if len(heavy)>8:
            heapq.heappop(heavy)
    optimizer = torch.optim.AdamW(model.parameters(), lr=c['lr'], betas=tuple(c['betas']), weight_decay=c['weight_decay'])
    (output/'heavy_batches.json').write_text(json.dumps(sorted(heavy,reverse=True),indent=2)+'\n')
    records = []
    failed = None
    for score, ordinal, choices, lengths in sorted(heavy, reverse=True):
        torch.cuda.reset_peak_memory_stats()
        try:
            samples = [data.read(m, conf) for m,conf in choices]
            optimizer.zero_grad(set_to_none=True)
            total, _ = calculate(model, samples, c, fields, families)
            total.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 281.7)
            optimizer.step()
            torch.cuda.synchronize()
            row = dict(ordinal=ordinal,score=score,choices=choices,atom_counts=lengths,peak_bytes=torch.cuda.max_memory_allocated())
            records.append(row)
            print(json.dumps(row), flush=True)
        except torch.cuda.OutOfMemoryError as error:
            failed = dict(ordinal=ordinal, error=str(error),peak_bytes=torch.cuda.max_memory_allocated())
            break
    peak = max((r['peak_bytes'] for r in records), default=0)
    decision = dict(grouped_fields=True, head_checkpointing=False,
        distance_tiling=bool(execution['distance_tiling'] or failed or peak>20*1024**3), prepared_input=True)
    result = dict(mode='capacity',node=socket.gethostname(),gpu=torch.cuda.get_device_name(0),
        uuid=os.environ['CUDA_VISIBLE_DEVICES'],batches=records,failure=failed,peak_bytes=peak,options=decision,
        execution=execution,heavy_selection='Eight largest padded-plus-native squared atom-count costs in the seed-0 first1000 batches')
    (output/'capacity.json').write_text(json.dumps(result, indent=2)+'\n')
    data.close()


def benchmark(c, output, options):
    from phychem_mfm.phase1.p_recipe_training import train
    c.update(run='step_overhead_'+output.name,output=str(output/'training'),step_overhead=options,benchmark_updates=1100)
    stop = threading.Event()
    telemetry = []
    def capture():
        while not stop.is_set():
            row = subprocess.check_output(['nvidia-smi','-i',os.environ['CUDA_VISIBLE_DEVICES'],
                '--query-gpu=power.draw,memory.used,utilization.gpu','--format=csv,noheader,nounits'], text=True).strip()
            telemetry.append([time.time(),*map(float,row.split(','))])
            stop.wait(1)
    monitor = threading.Thread(target=capture,daemon=True)
    monitor.start()
    try:
        result = train(c)
    finally:
        stop.set()
        monitor.join(timeout=5)
        with (output/'gpu.csv').open('w',newline='') as stream:
            writer=csv.writer(stream)
            writer.writerow(['unix_seconds','power_W','used_MiB','GPU_percent'])
            writer.writerows(telemetry)
    measured = [row for row in telemetry if result['measure_wall_start']<=row[0]<=result['measure_wall_end']]
    result.update(gpu=torch.cuda.get_device_name(0),uuid=os.environ['CUDA_VISIBLE_DEVICES'],node=socket.gethostname(),
        power_W=float(np.mean([r[1] for r in measured])),options=options)
    (output/'benchmark.json').write_text(json.dumps(result,indent=2)+'\n')


def equal_tensors(left, right):
    if isinstance(left, torch.Tensor):
        if not isinstance(right, torch.Tensor) or left.dtype!=right.dtype or left.shape!=right.shape:
            return False
        same = left==right
        if left.is_floating_point():
            same = same | (left.isnan() & right.isnan())
        return bool(same.all())
    if isinstance(left, dict):
        return left.keys()==right.keys() and all(equal_tensors(left[n], right[n]) for n in left)
    if isinstance(left, (tuple, list)):
        return len(left)==len(right) and all(equal_tensors(a,b) for a,b in zip(left,right))
    return left==right


def verify_input(c, output):
    from concurrent.futures import ProcessPoolExecutor
    import multiprocessing
    from phychem_mfm.phase1.p_recipe_input import init_prepared_reader, reader_metadata, ordered_prepared_batches, unpack_targets
    from phychem_mfm.phase1.v31_loader import collate_samples
    from phychem_mfm.phase1.v3_training import SampleClock
    model, data, fields, _ = model_for(c, dict(grouped_fields=True), device='cpu')
    pd = model['pd']
    from phychem_mfm.phase1.p_recipe_data import dataset_configuration
    reader = dataset_configuration(c)
    rng = np.random.default_rng(0)
    new_rng = np.random.default_rng(0)
    clock = SampleClock(c['samples'])
    records, violations = [], []
    tensor_batches = 0
    with ProcessPoolExecutor(c['workers'],mp_context=multiprocessing.get_context('spawn'),
            initializer=init_prepared_reader,initargs=(reader,c['mean_labels'],reader_metadata(pd,fields),None)) as pool:
        batches = ordered_prepared_batches(pool, clock, new_rng, 32, 32000)
        for ordinal, (prepared, state) in enumerate(batches):
            choices = draw(data, rng, 32)
            actual = [(int(s['molecule_index']),int(s['conformer_index'])) for s in prepared]
            sequence_equal = choices==actual and rng.bit_generator.state==state
            tensors_equal = True
            if ordinal<20:
                old = [data.read(m,conf) for m,conf in choices]
                tensors_equal = equal_tensors(collate_samples(old).to_dict(),prepared.prepared['clean_batch'].to_dict())
                for n,shape in prepared.prepared['shapes'].items():
                    tensors_equal &= tuple(np.concatenate([s['targets'][n].raw for s in old]).shape)==shape
                packed_targets, _, target_names = unpack_targets(prepared.prepared['loss_targets'])
                for name, target in packed_targets.items():
                    names = target_names[name]
                    values = np.concatenate([np.concatenate([s['targets'][n].values for s in old]) for n in names],-1)
                    valid = np.concatenate([np.concatenate([s['targets'][n].valid for s in old]) for n in names],-1).all(-1)
                    tensors_equal &= equal_tensors(torch.as_tensor(values,dtype=torch.float32),target.values)
                    tensors_equal &= equal_tensors(torch.as_tensor(valid),target.valid)
                for route, indices in prepared.prepared['route_indices'].items():
                    route_fields = [n for n in fields if pd.routes[pd.selections[n][0]]==route]
                    expected = list(range(32)) if route==21 else [i for i,s in enumerate(old) if any(s['targets'][n].valid.any() for n in route_fields)]
                    tensors_equal &= indices==expected
                    if not indices:
                        continue
                    source = [old[i] for i in indices]
                    if len(indices)!=32:
                        for n in route_fields:
                            offsets = np.r_[0,np.cumsum([len(s['targets'][n].raw) for s in old])]
                            expected_rows = torch.as_tensor(np.concatenate([np.arange(offsets[i],offsets[i+1]) for i in indices]))
                            tensors_equal &= equal_tensors(expected_rows,prepared.prepared['scatter_rows'][n])
                    reference = collate_samples(source if route==21 else [{**s,'pos':s['pos_perturbed']} for s in source])
                    if route==22:
                        tensors_equal &= equal_tensors(reference.to_dict(),prepared.prepared['perturbed_batch'].to_dict())
                    for n in route_fields:
                        head = pd.selections[n][0]
                        if pd.by_name[n].level!='pair':
                            continue
                        masks = [s['targets'][n].valid.any(-1) for s in source]
                        pairs = torch.cat([torch.as_tensor(s['targets'][n].pair_index[mask].T.copy(),dtype=torch.long)+reference.ptr[i]
                            for i,(s,mask) in enumerate(zip(source,masks))],1)
                        rows = torch.as_tensor(np.flatnonzero(np.concatenate(masks)))
                        tensors_equal &= equal_tensors(pairs,prepared.prepared['pairs'][head])
                        tensors_equal &= equal_tensors(rows,prepared.prepared['pair_rows'][head][0])
                        tensors_equal &= len(np.concatenate(masks))==prepared.prepared['pair_rows'][head][1]
                tensor_batches += 1
            records.append(dict(batch=ordinal,choices=actual,sequence_equal=sequence_equal,
                                tensors_equal=bool(tensors_equal) if ordinal<20 else None))
            if not sequence_equal or not tensors_equal:
                violations.append(ordinal)
            clock.advance(32)
            new_rng.bit_generator.state = state
            if (ordinal+1)%100==0:
                print('INPUT_BATCHES',ordinal+1,'VIOLATIONS',len(violations),flush=True)
    result = dict(status='PASS' if not violations and len(records)==1000 and tensor_batches==20 else 'FAIL',
        batches=len(records),tensor_batches=tensor_batches,violations=violations,records=records,
        final_clock=clock.state_dict(),final_rng=new_rng.bit_generator.state)
    (output/'input_equivalence.json').write_text(json.dumps(result,indent=2)+'\n')
    data.close()


def profile(output, options):
    spy = Path('/lfshome/zixiao/model_v3_perf_20261112/sampler_tools_v1/bin/py-spy')
    destination = output/'run'
    command = [os.sys.executable,'-B','-u',str(Path(__file__)),'benchmark','--output',str(destination),
               '--options',json.dumps(options)]
    sampler = None
    with (output/'training.log').open('w') as log:
        with subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1) as child:
            for line in child.stdout:
                log.write(line)
                log.flush()
                if 'MEASUREMENT_START' in line:
                    sampler = subprocess.Popen([str(spy),'record','--native','-d','30','--pid',str(child.pid),
                        '-o',str(output/'flame.svg')],stdout=log,stderr=subprocess.STDOUT)
            if child.wait()!=0:
                raise RuntimeError('Profile training failed')
        if sampler is None or sampler.wait()!=0:
            raise RuntimeError('Native profile capture failed')


def flame_categories(path):
    frames = []
    for group in ET.parse(path).getroot().iter():
        if not group.tag.endswith('}g'):
            continue
        title = next((child.text for child in group if child.tag.endswith('}title')), None)
        rect = next((child for child in group if child.tag.endswith('}rect')), None)
        if title is not None and rect is not None:
            start = int(rect.get('{http://github.com/jonhoo/inferno}x'))
            width = int(rect.get('{http://github.com/jonhoo/inferno}w'))
            frames.append((title,start,start+width))
    total = max(end-start for _,start,end in frames)
    categories = dict(backward=('run_backward','Engine::evaluate_function','Engine::thread_main'),
        encoder=('encode_atoms (','encode_graph ('), heads=('V3HeadBank.forward (','grouped_head_predictions ('),
        loss=('V31PDModel.loss (','compute_v3_loss (','grouped_regression_loss ('),
        CPU_input=('collate_samples (','MFM4Dataset.record (','decode_mfm4 ('),
        IPC=('multiprocessing/connection.py','multiprocessing/reduction.py','concurrent/futures/process.py'),
        optimizer_and_clip=('adamw','clip_grad_norm_'))
    result = {}
    for name,patterns in categories.items():
        intervals = sorted((start,end) for label,start,end in frames if any(p in label for p in patterns))
        merged = []
        for start,end in intervals:
            if merged and start<=merged[-1][1]:
                merged[-1][1] = max(merged[-1][1],end)
            else:
                merged.append([start,end])
        result[name] = 100*sum(end-start for start,end in merged)/total
    return dict(total_samples=total,inclusive_percent=result,
                note='Union of sampled stack intervals per operation; nested categories may overlap.')


def timing_suite(output, options):
    versions = [dict(grouped_fields=True),dict(grouped_fields=True,head_checkpointing=False,distance_tiling=True),
                dict(grouped_fields=True,head_checkpointing=False,distance_tiling=True,prepared_input=True)]
    if options.get('idle',False):
        plan = [(version,1,'old' if version==0 else 'new',execution) for version,execution in enumerate([{},*versions])]
    else:
        plan = [(version,repeat,name,execution) for version,execution_options in enumerate(versions,1)
                for repeat in (1,2) for name,execution in [('old',{}),('new',execution_options)]]
    records = []
    for version,repeat,name,execution in plan:
                label=f'v{version}_r{repeat}_{name}'
                destination=output/label
                with (output/(label+'.log')).open('w') as log:
                    subprocess.run([os.sys.executable,'-B','-u',str(Path(__file__)),'benchmark','--output',str(destination),
                        '--options',json.dumps(execution)],stdout=log,stderr=subprocess.STDOUT,check=True)
                result=json.loads((destination/'benchmark.json').read_text())
                records.append(dict(version=version,repeat=repeat,role=name,**result))
                (output/'timing_runs.json').write_text(json.dumps(records,indent=2)+'\n')
                print(label,result['samples_per_second'],result['power_W'],flush=True)
    for name,execution in [('old',{}),('new',versions[-1])]:
        destination=output/('profile_'+name)
        destination.mkdir()
        profile(destination,execution)
    (output/'flame_comparison.json').write_text(json.dumps({name:flame_categories(output/('profile_'+name)/'flame.svg')
        for name in ('old','new')},indent=2)+'\n')


def numerical(c, output, options):
    from phychem_mfm.phase1.p_recipe_input import prepare_samples, reader_metadata
    model, data, fields, families = model_for(c, {})
    metadata = reader_metadata(model['pd'], fields)
    rng = np.random.default_rng(0)
    batches = [draw(data,rng,32) for _ in range(20)]
    details, comparisons = [], []
    for weights in ('random_seed0','G1_3M'):
        if weights=='G1_3M':
            checkpoint=torch.load(G1,map_location='cpu',weights_only=True)
            model.load_state_dict(checkpoint['model'])
            del checkpoint
        for ordinal, choices in enumerate(batches):
            samples = [data.read(m,conf) for m,conf in choices]
            prepared = prepare_samples(samples, metadata)
            cpu_rng, cuda_rng = torch.get_rng_state(), torch.cuda.get_rng_state()
            runs = []
            none_sets = []
            for variant in ('old1','old2','new'):
                torch.set_rng_state(cpu_rng)
                torch.cuda.set_rng_state(cuda_rng)
                model['pd'].configure_step_overhead(options if variant=='new' else {})
                model.zero_grad(set_to_none=True)
                total, loss = calculate(model, prepared if variant=='new' else samples, c, fields, families)
                total.backward()
                torch.cuda.synchronize()
                field_losses = {name:float(value.detach()) for name,value in loss.fields.items()}
                gradients = torch.cat([parameter.grad.detach().flatten() if parameter.grad is not None
                    else parameter.new_zeros(parameter.numel()) for parameter in model.parameters()]).cpu().double()
                none_sets.append({name for name,p in model.named_parameters() if p.grad is None})
                runs.append((field_losses,gradients))
                for name,value in field_losses.items():
                    details.append(dict(weights=weights,batch=ordinal,variant=variant,field=name,loss=value))
            (old,g1),(old2,g2),(new,g3)=runs
            denominator=float(g1.norm())
            eps_grad=float((g1-g2).norm())/max(denominator,1e-30)
            difference=float((g1-g3).norm())/max(denominator,1e-30)
            eps_loss=max(abs(old[n]-old2[n])/max(abs(old[n]),1e-30) for n in old)
            comparisons.append(dict(weights=weights,batch=ordinal,epsilon_loss=eps_loss,epsilon_grad=eps_grad,
                grad_relative=difference,unused_parameters_equal=none_sets[0]==none_sets[1]==none_sets[2],
                losses=[dict(field=n,old=old[n],new=new[n],absolute_difference=abs(old[n]-new[n])) for n in old]))
            print('NUMERICAL',weights,ordinal,'grad_relative',difference,flush=True)
    eps_loss=max(row['epsilon_loss'] for row in comparisons) or 1e-6
    eps_grad=max(row['epsilon_grad'] for row in comparisons) or 1e-6
    violations=[]
    for row in comparisons:
        row['grad_pass']=row['grad_relative']<=max(10*eps_grad,1e-5)
        for loss in row['losses']:
            loss['tolerance']=max(1e-7,10*eps_loss*abs(loss['old']),1e-5*abs(loss['old']))
            loss['pass']=loss['absolute_difference']<=loss['tolerance']
        row['pass']=row['grad_pass'] and row['unused_parameters_equal'] and all(loss['pass'] for loss in row['losses'])
        if not row['pass']:
            violations.append([row['weights'],row['batch']])
    result=dict(status='PASS' if not violations else 'FAIL',epsilon_loss=eps_loss,epsilon_grad=eps_grad,
        violations=violations,comparisons=comparisons,options=options,gpu=torch.cuda.get_device_name(0),
        uuid=os.environ['CUDA_VISIBLE_DEVICES'],torch=torch.__version__,cuda=torch.version.cuda)
    (output/'numerical.json').write_text(json.dumps(result,indent=2)+'\n')
    with (output/'field_losses.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=['weights','batch','variant','field','loss'])
        writer.writeheader()
        writer.writerows(details)
    data.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=['capacity','benchmark','input','numerical','timing_suite'])
    parser.add_argument('--output',required=True)
    parser.add_argument('--options',default='{}')
    args=parser.parse_args()
    output=Path(args.output)
    output.mkdir(parents=True,exist_ok=False)
    c=configuration()
    (output/'configuration.json').write_text(json.dumps(c,indent=2)+'\n')
    if args.mode=='capacity':capacity(c,output,json.loads(args.options))
    elif args.mode=='benchmark':benchmark(c,output,json.loads(args.options))
    elif args.mode=='input':verify_input(c,output)
    elif args.mode=='numerical':numerical(c,output,json.loads(args.options))
    else:timing_suite(output,json.loads(args.options))


if __name__=='__main__':
    main()
