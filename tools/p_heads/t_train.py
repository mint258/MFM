"""Isolated T training; reuse the frozen B3 engine and its existing evaluation."""
import argparse,fcntl,json,os,pathlib,sys,threading,time,gc
import torch
from h_resources import guard,watchdog,save,CONTROL,REPO

def main():
    p=argparse.ArgumentParser();p.add_argument('--configuration',required=True);a=p.parse_args()
    c=json.loads(pathlib.Path(a.configuration).read_text());watchdog()
    if c['samples']!=3000000 or c['seed'] not in (0,1): raise ValueError('Only registered 3M seeds')
    if c['batch_size']!=32 or c['microbatch_size']!=32: raise ValueError('Frozen B32 required')
    import subprocess,csv
    gpu=os.environ['CUDA_VISIBLE_DEVICES'].split(',')[0]
    locks=pathlib.Path('/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage46_shared_gpu_launch/.own_gpu_uuid_locks')
    lock=(locks/(gpu+'.lock')).open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    row=next(csv.reader(subprocess.check_output(['nvidia-smi','--id='+gpu,'--query-gpu=memory.used,memory.total','--format=csv,noheader,nounits'],text=True).splitlines()))
    if float(row[0])/float(row[1])>.30: raise RuntimeError('Actual GPU occupancy exceeds30%')

    torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
    import phychem_mfm.phase1.p_recipe_training as training
    # Only log destinations change. Imports and the entire B3 engine are reused.
    runtime=CONTROL/'runtime';training.REPO=runtime
    sys.path.insert(0,str(REPO/'tools/p_recipe'))
    import native_run,evaluate
    native_run.REPO=runtime
    telemetry=dict(c,training_budget=c['samples'],gpu_uuid=gpu)
    stop=threading.Event()
    def monitor():
        while not stop.wait(30):
            try: native_run.record_gpu_telemetry(telemetry)
            except Exception as e: print('Telemetry unavailable:',str(e),flush=True)
    thread=threading.Thread(target=monitor,daemon=True);thread.start()
    try:
        summary=training.train(c)
        if summary.get('status')=='HANDOFF_SAVED':return
        # Training finishes once; no call to the original train.py main.
        gc.collect();torch.cuda.empty_cache();guard(force=True)
        evaluation={**c,'checkpoint':str(pathlib.Path(c['output'])/'samples_3000000.pt'),
            'features':str(pathlib.Path(c['output'])/'features_3000000'),
            'output':str(pathlib.Path(c['output'])/'readout'),'persist_features':False,
            'store':'/share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/selected_train_store_4520421/native_store/training_store.json',
            'reference_manifest':'/lfshome/zixiao/model_v31_20261105/P_RECIPE_20261113/reference_C1_0/predictions.json'}
        destination=pathlib.Path(evaluation['output'])
        if not (destination/'scores.json').exists():
            evaluate.run(evaluation)
            scores=evaluate.score(destination/'predictions.json',evaluation['reference_manifest'],CONTROL/'scores.csv')
            save(REPO/'results/p_heads/T'/(c['run']+'_scores.json'),scores)
        summary.update(status='COMPLETE')
        save(pathlib.Path(c['output'])/'summary.json',summary)
    finally:stop.set();thread.join(timeout=12)
if __name__=='__main__': main()
