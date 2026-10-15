"""Bounded CUDA kernel compatibility, distinct from a representative model check."""
import csv,fcntl,json,os,socket,subprocess,time,tempfile,shutil
from pathlib import Path
from prepare import ROOT,save

def query(args):
    p=subprocess.run(args,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=15)
    if p.returncode:raise RuntimeError(p.stderr)
    return p.stdout

def main():
    assert os.environ.get('SLURM_JOB_ID') and socket.gethostname()=='compute-0-21'
    assert int(os.environ['SLURM_CPUS_PER_TASK'])>=16
    applications=query(['nvidia-smi','--query-compute-apps=gpu_uuid,pid,used_memory','--format=csv,noheader,nounits'])
    foreign={line.split(',')[0].strip() for line in applications.splitlines() if line.strip()}
    gpu_rows=list(csv.reader(query(['nvidia-smi','--query-gpu=uuid,name,memory.total,memory.free','--format=csv,noheader,nounits']).splitlines()))
    idle=[r for r in gpu_rows if r[0].strip() not in foreign]
    if not idle:raise RuntimeError('No currently idle GPU; defer owned probe')
    selected=idle[0];uuid=selected[0].strip()
    lockdir=Path('/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage46_shared_gpu_launch/.own_gpu_uuid_locks')
    lockdir.mkdir(exist_ok=True)
    lock=(lockdir/(uuid+'.lock')).open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    os.environ['CUDA_VISIBLE_DEVICES']=uuid
    scratch=Path(tempfile.mkdtemp(prefix='sconv_cuda_'+os.environ['SLURM_JOB_ID']+'_',dir='/tmp'))
    os.chmod(scratch,0o700);os.environ['CUDA_CACHE_PATH']=str(scratch/'cuda_cache')
    result={'job_id':os.environ['SLURM_JOB_ID'],'node':socket.gethostname(),'gpu_uuid':uuid,'gpu_model':selected[1].strip(),'total_memory_mib':int(selected[2]),'start_free_memory_mib':int(selected[3]),'logical_interpreter':os.path.abspath(os.sys.executable),'protection':'USER_ACCEPTED_SHARED_GPU_RISK','model_path_verified':False}
    try:
        import torch
        torch.set_num_threads(16);torch.manual_seed(123)
        result.update(torch=str(torch.__version__),cuda_runtime=torch.version.cuda)
        assert torch.cuda.device_count()==1
        x=torch.randn(8,6,32,64,device='cuda',requires_grad=True)
        out=torch.nn.functional.scaled_dot_product_attention(x,x,x)
        out.square().mean().backward();torch.cuda.synchronize()
        assert bool(torch.isfinite(out).all()) and bool(torch.isfinite(x.grad).all())
        result.update(status='CUDA_KERNEL_PASS',peak_allocated_bytes=torch.cuda.max_memory_allocated())
    except Exception as exc:
        result.update(status='CUDA_KERNEL_FAILED',error=repr(exc));raise
    finally:
        save(ROOT/'reports'/('cuda_probe_'+os.environ['SLURM_JOB_ID']+'.json'),result)
        shutil.rmtree(scratch);lock.close()
    print(json.dumps(result),flush=True)

if __name__=='__main__':main()
