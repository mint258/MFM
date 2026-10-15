"""Read actual GPU hardware, Slurm allocation, environment and the node host key."""
import concurrent.futures as cf,hashlib,json,os,socket,subprocess,time
from pathlib import Path
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/sprime_s_convergence_20261013')

def call(argv):
    p=subprocess.run(argv,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=30)
    return {'argv':argv,'rc':p.returncode,'stdout':p.stdout,'stderr':p.stderr}

def main():
    assert os.environ.get('SLURM_JOB_ID') and int(os.environ['SLURM_CPUS_PER_TASK'])>=16
    import torch
    torch.set_num_threads(16)
    commands=[['nvidia-smi','--query-gpu=index,uuid,name,memory.total,memory.used,utilization.gpu','--format=csv'],['nvidia-smi','--query-compute-apps=gpu_uuid,pid,used_memory','--format=csv'],['ssh-keygen','-lf','/etc/ssh/ssh_host_ed25519_key.pub']]
    with cf.ThreadPoolExecutor(max_workers=16) as pool: observations=list(pool.map(call,commands))
    result={'job_id':os.environ['SLURM_JOB_ID'],'hostname':socket.gethostname(),'uid':os.getuid(),'timestamp':time.time(),'logical_interpreter':os.path.abspath(os.sys.executable),'torch':str(torch.__version__),'cuda':torch.version.cuda,'observations':observations}
    # This is a hardware inventory. The representative model path is checked separately.
    result['cuda_device_count']=torch.cuda.device_count()
    (ROOT/'reports'/('gpu_inventory_'+os.environ['SLURM_JOB_ID']+'.json')).write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result),flush=True)

if __name__=='__main__':main()
