"""Bounded GPU-context health and last committed checkpoint integrity check."""
import argparse,csv,fcntl,json,os,subprocess,sys,time
from pathlib import Path
from prepare import ROOT,PROJECT,save,sha

def child(uuid):
    os.environ['CUDA_VISIBLE_DEVICES']=uuid
    import torch
    torch.set_num_threads(8);torch.set_num_interop_threads(1)
    torch.manual_seed(0);torch.cuda.manual_seed_all(0)
    assert torch.cuda.device_count()==1
    started=time.monotonic()
    a=torch.randn(2048,2048,device='cuda');b=torch.randn(2048,2048,device='cuda')
    for _ in range(12):
        c=a@b;assert bool(torch.isfinite(c).all());torch.cuda.synchronize()
    print(json.dumps({'status':'CUDA_FRESH_CONTEXT_MATMUL_FINITE_AND_SYNCHRONIZED_PASS','uuid':uuid,
        'torch_version':torch.__version__,'cuda_version':torch.version.cuda,'model':torch.cuda.get_device_name(0),
        'peak_allocated_bytes':torch.cuda.max_memory_allocated(),'elapsed_seconds':time.monotonic()-started}),flush=True)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--child');args=ap.parse_args()
    if args.child:child(args.child);return
    assert os.getuid()==1278 and os.environ.get('SLURM_JOB_ID') and int(os.environ['SLURM_CPUS_PER_TASK'])>=16
    assert __import__('socket').gethostname().split('.')[0]=='compute-0-21'
    folder=ROOT/'cuda_recovery_v1';folder.mkdir(exist_ok=True)
    query=lambda argv:subprocess.run(argv,capture_output=True,text=True,check=True,timeout=20).stdout
    gpu_raw=query(['nvidia-smi','--query-gpu=uuid,name,memory.total,memory.free,utilization.gpu,temperature.gpu','--format=csv,noheader,nounits'])
    apps=query(['nvidia-smi','--query-compute-apps=gpu_uuid,pid,used_memory','--format=csv,noheader,nounits'])
    occupied={r.split(',')[0].strip() for r in apps.splitlines() if r.strip()}
    rows=list(csv.reader(gpu_raw.splitlines()));locks=[];children=[]
    try:
        for row in rows:
            uuid=row[0].strip();assert uuid not in occupied and int(row[3])>=.95*int(row[2])
            lock=(PROJECT/'docs/phase1/evidence/stage46_shared_gpu_launch/.own_gpu_uuid_locks'/(uuid+'.lock')).open('a')
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);locks.append(lock)
            children.append((uuid,subprocess.Popen([sys.executable,'-B',__file__,'--child',uuid],stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)))
        proofs=[]
        for uuid,process in children:
            try:out,err=process.communicate(timeout=90)
            except subprocess.TimeoutExpired:
                process.terminate()
                try:out,err=process.communicate(timeout=5)
                except subprocess.TimeoutExpired:process.kill();out,err=process.communicate(timeout=5)
                raise RuntimeError('Owned bounded health child timed out '+uuid)
            assert process.returncode==0,{'uuid':uuid,'rc':process.returncode,'stderr':err}
            proof=json.loads(out);assert proof['uuid']==uuid and proof['status'].endswith('_PASS');proofs.append(proof)
        os.environ['CUDA_VISIBLE_DEVICES']=''
        import torch
        torch.set_num_threads(16);torch.set_num_interop_threads(1)
        ref=json.loads((ROOT/'s_training/B1_seed1/latest_checkpoint.json').read_text())
        assert ref['consumed_records']==4194304 and ref['optimizer_updates']==10292 and sha(ref['path'])==ref['sha256']
        state=torch.load(ref['path'],map_location='cpu',weights_only=True)
        assert state['consumed_records']==4194304 and state['optimizer_updates']==10292
        assert not state['scientific_stop'] and state['completed_epochs']==[]
        assert state['config_sha256']==sha(ROOT/'formal_s/B1_seed1_v2.json')
        assert state['coverage'].numel()==11104772 and int(state['coverage'].sum())==4194304
        assert int(state['coverage'].max())==1 and int(state['coverage'].min())==0
        def finite(value):
            if isinstance(value,torch.Tensor):assert value.device.type=='cpu' and bool(torch.isfinite(value).all())
            elif isinstance(value,dict):
                for item in value.values():finite(item)
            elif isinstance(value,(list,tuple)):
                for item in value:finite(item)
        finite(state['model']);finite(state['optimizer'])
        result={'status':'BOTH_GPU_CONTEXTS_AND_LAST_COMMITTED_CHECKPOINT_INTEGRITY_PASS','job_id':os.environ['SLURM_JOB_ID'],
            'timestamp':time.time(),'gpu_metadata':gpu_raw,'initial_compute_processes':apps,'gpu_proofs':proofs,
            'checkpoint_reference':ref,'checkpoint_config_sha256':state['config_sha256'],
            'visited_records_once':4194304,'model_tensors':len(state['model']),'optimizer_parameter_states':len(state['optimizer']['state']),
            'cpu_and_cuda_rng_fields_present':all(k in state for k in ['cpu_rng','cuda_rng']),
            'original_LMDB_written':False,'gpu_reset_or_other_users_signalled':False,'check_source_sha256':sha(__file__)}
        assert result['cpu_and_cuda_rng_fields_present']
        save(folder/'health_and_checkpoint_receipt.json',result);print(json.dumps(result),flush=True)
    finally:
        for _,process in children:
            if process.poll() is None:process.terminate();process.wait(timeout=5)
        for lock in locks:lock.close()

if __name__=='__main__':main()
