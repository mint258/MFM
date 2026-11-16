"""The taskbook's one 200-update old/new acceptance, from one frozen checkpoint."""
import argparse,csv,json,os,signal,subprocess,sys,time
from pathlib import Path
REPO=Path('/share/home/zixiao/descriptor_analysis/MFM_model_v3_cpu_perf_20261112')
REFERENCE=REPO.parent/'MFM_model_v3_cpu_reference_20261112'
DEPS=REPO.parent/'docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps'
CHECKPOINT=Path('/lfshome/zixiao/model_v31_20261105/P_C1_0_seed0_micro32_continuation_20261110/samples_4000000.pt')


class AcceptedBoundary(Exception): pass


def child(role,output):
    import torch
    from phychem_mfm.phase1.v31_experiments import train_v31
    from phychem_mfm.phase1.v2_disk import save_checkpoint,save_metadata_json
    checkpoint=torch.load(CHECKPOINT,map_location='cpu',weights_only=True)
    configuration=dict(checkpoint['configuration']);del checkpoint
    configuration.update(output=str(output),resume=str(CHECKPOINT),run_until_samples=None,
        workers=min(14,max(1,int(os.environ.get('SLURM_CPUS_PER_TASK','16'))-2)))
    os.environ.pop('MFM_CPU_MEASURE_STEPS',None);os.environ.pop('MFM_CPU_PROFILE_DIR',None)
    trace=[];original=csv.DictWriter.writerow
    def record(writer,row):
        result=original(writer,row)
        if type(row.get('updates')) is int:
            frame=sys._getframe(1)
            while frame is not None and ('model' not in frame.f_locals or 'clock' not in frame.f_locals):
                frame=frame.f_back
            if frame is None: raise RuntimeError('Cannot identify actual update frame')
            state=frame.f_locals
            trace.append([[int(s['molecule_index']),int(s['conformer_index'])] for s in state['samples']])
            if len(trace)==200:
                save_checkpoint({name:p.detach().cpu().clone() for name,p in state['model'].named_parameters()},output/'parameters_200.pt')
                save_metadata_json(dict(role=role,steps=200,choices=trace,clock=state['clock'].state_dict(),
                    deterministic_algorithms=torch.are_deterministic_algorithms_enabled(),
                    tf32=torch.backends.cuda.matmul.allow_tf32),output/'trace_200.json')
                raise AcceptedBoundary()
        return result
    csv.DictWriter.writerow=record
    try:
        train_v31(configuration)
        raise RuntimeError('Training ended before the acceptance boundary')
    except AcceptedBoundary:
        print('EXACTLY_200_UPDATES_CAPTURED',role,flush=True)
    finally:
        csv.DictWriter.writerow=original


def compare(root):
    import math,torch
    old=json.loads((root/'old/trace_200.json').read_text())
    new=json.loads((root/'new/trace_200.json').read_text())
    sequence_equal=old['choices']==new['choices']
    with (root/'old/losses.csv').open() as file:a=list(csv.DictReader(file))
    with (root/'new/losses.csv').open() as file:b=list(csv.DictReader(file))
    assert len(a)==len(b)==200
    violations=[];worst={}
    for index,(before,after) in enumerate(zip(a,b),1):
        assert before['samples']==after['samples'] and before['updates']==after['updates']
        for name in ('total','S','D','P','preclip_norm'):
            if not before[name] or not after[name]:
                assert before[name]==after[name]
                continue
            x,y=float(before[name]),float(after[name]);difference=abs(y-x);tolerance=max(1e-6,1e-5*abs(x))
            ratio=difference/tolerance
            if name not in worst or ratio>worst[name]['tolerance_ratio']:
                worst[name]=dict(step=index,old=x,new=y,absolute_difference=difference,tolerance_ratio=ratio)
            if not math.isfinite(y) or difference>tolerance:
                violations.append(dict(step=index,field=name,old=x,new=y,absolute_difference=difference,tolerance=tolerance))
    p=torch.load(root/'old/parameters_200.pt',weights_only=True,map_location='cpu')
    q=torch.load(root/'new/parameters_200.pt',weights_only=True,map_location='cpu')
    assert p.keys()==q.keys()
    numerator=denominator=0.
    for name in p:
        x,y=p[name].double(),q[name].double()
        numerator+=float((x-y).square().sum());denominator+=float(x.square().sum())
    parameter_relative_l2=math.sqrt(numerator)/max(math.sqrt(denominator),1e-30)
    state_equal=old['clock']==new['clock']
    settings_equal=(old['deterministic_algorithms']==new['deterministic_algorithms'] and old['tf32']==new['tf32']==False)
    verdict=dict(status='PASS' if sequence_equal and state_equal and settings_equal and not violations and parameter_relative_l2<=1e-5 else 'FAIL',
        steps=200,choices_equal=sequence_equal,clock_equal=old['clock']==new['clock'],
        old_deterministic_algorithms=old['deterministic_algorithms'],new_deterministic_algorithms=new['deterministic_algorithms'],
        old_tf32=old['tf32'],new_tf32=new['tf32'],parameter_relative_l2=parameter_relative_l2,
        violation_count=len(violations),first_violations=violations[:10],worst=worst)
    (root/'acceptance.json').write_text(json.dumps(verdict,indent=2)+'\n')
    print(json.dumps(verdict),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--role',choices=('old','new'));parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if args.role:
        child(args.role,args.output);return
    sys.path.insert(0,str(REPO/'tools/model_v3'))
    from cpu_bottleneck_step1 import capacity,idle_gpu,SCRATCH,query
    import fcntl
    capacity()
    captured=list(SCRATCH.glob('equivalence_*/*/trace_200.json'))
    if captured:
        raise RuntimeError('A 200-update acceptance capture already exists; inspect it instead of replaying')
    gpu=idle_gpu()
    root=SCRATCH/('equivalence_'+os.environ['SLURM_JOB_ID']);root.mkdir(parents=True,exist_ok=False)
    lock=REPO.parent/'docs/phase1/evidence/stage46_shared_gpu_launch/.own_gpu_uuid_locks'/(gpu+'.lock')
    with lock.open('a') as handle:
        fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
        for role,source,flag in (('old',REFERENCE,'0'),('new',REPO,'1')):
            capacity()
            if idle_gpu()!=gpu:raise RuntimeError('Acceptance GPU is no longer idle')
            environment=dict(os.environ,CUDA_VISIBLE_DEVICES=gpu,PYTHONPATH=str(source/'current')+':'+str(DEPS),
                             MFM_CPU_HEAD_NO_RECOMPUTE=flag,PYTHONHASHSEED='0')
            with (root/(role+'.log')).open('x') as log:
                process=subprocess.Popen([sys.executable,'-B','-u',str(Path(__file__).absolute()),'--role',role,
                    '--output',str(root/role)],env=environment,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
                try:
                    while process.poll() is None:
                        capacity()
                        rows=query('nvidia-smi','--query-compute-apps=gpu_uuid,pid','--format=csv,noheader')
                        if any(parts[0].strip()==gpu and int(parts[1])!=process.pid
                               for line in rows.splitlines() if len(parts:=line.split(','))==2):
                            raise RuntimeError('External GPU process appeared during acceptance')
                        time.sleep(1)
                    if process.returncode:raise RuntimeError(f'{role} child failed; preserve outputs and inspect, never replay automatically')
                finally:
                    if process.poll() is None:
                        os.killpg(process.pid,signal.SIGTERM)
                        try:process.wait(timeout=30)
                        except subprocess.TimeoutExpired:
                            os.killpg(process.pid,signal.SIGKILL);process.wait()
        compare(root)


if __name__=='__main__': main()
