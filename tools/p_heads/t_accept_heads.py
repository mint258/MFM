"""The registered64 real TRAIN samples, frozen encoder, at most2000 head updates."""
import argparse,collections,json,pathlib,torch,os,fcntl,csv,subprocess,time
from h_resources import REPO,guard,watchdog,save
from phychem_mfm.phase1.p_recipe_data import PRecipeDataset,dataset_configuration
from phychem_mfm.phase1.v2_s_training import s_model
from phychem_mfm.phase1.v31_training import V31PDModel
from phychem_mfm.phase1.v31_loader import encode_samples

def main():
    p=argparse.ArgumentParser();p.add_argument('--arm',choices=['T1','T2'],required=True);a=p.parse_args()
    watchdog();torch.set_num_threads(1);torch.manual_seed(0)
    import pyarrow as pa
    pa.set_cpu_count(1);pa.set_io_thread_count(1)
    gpu=os.environ['CUDA_VISIBLE_DEVICES'].split(',')[0]
    lock_path=pathlib.Path('/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage46_shared_gpu_launch/.own_gpu_uuid_locks')/(gpu+'.lock')
    gpu_lock=lock_path.open('a');fcntl.flock(gpu_lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    row=next(csv.reader(subprocess.check_output(['nvidia-smi','--id='+gpu,'--query-gpu=memory.used,memory.total','--format=csv,noheader,nounits'],text=True).splitlines()))
    if float(row[0])/float(row[1])>.30:raise RuntimeError('GPU occupancy exceeds30%')
    torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
    base=json.loads((REPO/'configs/p_recipe/fixed_20261115/provisional_B_20261116/round2/B3.json').read_text())
    data=PRecipeDataset(**dataset_configuration(base))
    structural,_=s_model('C1-0','three');structural.encoder.backbone.activation_checkpointing=False
    pd=V31PDModel(structural.encoder,data.view,forms=base['head_form'],pooling='registry',p_recipe=base['p_recipe'])
    cp=torch.load(pathlib.Path(base['output'])/'samples_3000000.pt',map_location='cpu',weights_only=True)
    torch.nn.ModuleDict(dict(structural=structural,pd=pd)).load_state_dict(cp['model'],strict=True)
    if a.arm=='T1':
        from phychem_mfm.model.p_heads import AtomAttentionDecoder
        pd.heads.atom_decoder=AtomAttentionDecoder()
        fields=[f.name for f in pd.registry.fields if f.group=='P' and
            (f.level=='pair' or f.level=='atom' and f.representation=='scalar')]
    else:
        from phychem_mfm.model.p_constraint_heads import install_physical_heads
        config=json.loads((REPO/'configs/p_heads/T/T2_seed0.json').read_text())
        install_physical_heads(pd.heads,config['p_recipe']['physical_constraint_heads'])
        fields=list(config['p_recipe']['physical_constraint_heads'])
    for parameter in pd.parameters():parameter.requires_grad_(False)
    if a.arm=='T1':
        for parameter in pd.heads.atom_decoder.parameters():parameter.requires_grad_(True)
    for name in fields:
        for parameter in pd.heads.field_heads[pd.heads.keys[pd.selections[name][0]]].parameters():parameter.requires_grad_(True)
    pd.configure_step_overhead(base['step_overhead']);pd.cuda().train();pd.encoder.eval()
    samples=[data.read(int(mi),int(data.choices(int(mi))[0])) for mi in data.indices[:64]]
    if len(samples)!=64:raise ValueError('Need64 actual TRAIN samples')
    batches=[]
    for start in (0,32):
        chunk=samples[start:start+32]
        with torch.no_grad():batch,h=encode_samples(chunk,pd.encoder,device='cuda')
        batches.append((chunk,batch,h.detach()))
    optimizer=torch.optim.AdamW([v for v in pd.parameters() if v.requires_grad],lr=.003,weight_decay=0.)
    initial={};current={};passed={};updates=0;started=time.monotonic()
    for step in range(2001):
        optimizer.zero_grad(set_to_none=True);values=collections.defaultdict(list)
        for chunk,batch,h in batches:
            prediction=pd.predict(chunk,groups=('P',),fields=fields,clean_features=h,clean_batch=batch)
            loss=pd.loss(prediction,chunk,groups=('P',),fields=fields)
            for name,value in loss.fields.items():
                if loss.counts[name]>0:values[name].append(float(value.detach()))
            if step<2000:loss.total.div(2).backward()
        current={n:sum(v)/len(v) for n,v in values.items()}
        if not initial:initial=current.copy()
        for name,value in current.items():
            if value<initial[name]*.01 or initial[name]==0 and value==0:passed.setdefault(name,step)
        if len(passed)==len(initial) or step==2000 or time.monotonic()-started>=14400:break
        optimizer.step();updates+=1
        if step%100==0:print(json.dumps(dict(arm=a.arm,updates=updates,passed=len(passed),heads=len(initial))),flush=True);guard()
    report=dict(arm=a.arm,samples=64,encoder_frozen=True,updates=updates,learning_rate=.003,
        unobserved_fields=sorted(set(fields)-set(initial)),
        optimizer='AdamW weight_decay0, fixed; no search',
        heads={n:dict(initial=initial[n],final=current[n],ratio=current[n]/initial[n] if initial[n] else 0.,passed_at_update=passed.get(n),passed=n in passed) for n in initial})
    save(REPO/'results/p_heads/T'/(a.arm+'_acceptance.json'),report)
    config_path=REPO/'configs/p_heads/T'/(a.arm+'_seed0.json')
    config=json.loads(config_path.read_text())
    if a.arm=='T1':config['p_recipe']['atom_decoder_fields']=sorted(passed)
    else:
        config['p_recipe']['physical_constraint_heads']={name:spec for name,spec in config['p_recipe']['physical_constraint_heads'].items() if name in passed}
    save(config_path,config)
    print(json.dumps(report),flush=True);data.close()
if __name__=='__main__':main()
