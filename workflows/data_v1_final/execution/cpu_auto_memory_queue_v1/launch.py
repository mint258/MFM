"""Wait for a new-authority CPU proof; never infer Slurm default memory size."""
import argparse,os,socket,subprocess,time
from pathlib import Path
from .shared import ROOT,load,pin,read_small,write_new,now
from .contract import need,validate_request,validate_bound_request,validate_fresh_startup_proof


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--request',type=Path,required=True);a=p.parse_args()
    req=load(a.request);validate_request(req,read_small=read_small);validate_bound_request(req,read_small=read_small)
    jid=os.environ.get('SLURM_JOB_ID','');node=socket.gethostname().split('.')[0]
    need(jid.isdecimal() and os.getuid()==1278 and node==req['node'] and
         os.environ.get('SLURM_JOB_PARTITION')=='cpu' and os.environ.get('SLURM_CPUS_PER_TASK')=='16'
         and os.environ.get('CUDA_VISIBLE_DEVICES')=='','ACTUAL_OWN_CPU16_ALLOCATION_REQUIRED')
    boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    write_new(ROOT/'control/queue_started'/(req['job_name']+'.json'),{'job_id':jid,'node':node,'uid':1278,
        'boot_id':boot,'request_reference':pin(a.request),'observed_at':now(),'scientific_work_started':False,
        'actual_memory_environment':{key:os.environ.get(key) for key in ('SLURM_MEM_PER_NODE','SLURM_MEM_PER_CPU')},
        'memory_policy':req['memory_policy'],'memory_admission_evaluated':False})
    path=Path(req['startup_proof_path']);marker=path.with_suffix('.ready.json');deadline=time.monotonic()+120
    while not marker.exists():
        need(time.monotonic()<deadline,'NO_NEW_FRESH_ROOT_ADMISSION_NO_STAGE');time.sleep(1)
    ready=load(marker);need(ready['job_id']==jid and ready['proof_reference']==pin(path),'EXACT_NEW_READY_PROOF')
    proof=load(path);need(proof['job_id']==jid and proof['request_reference']==pin(a.request),'ACTUAL_NEW_JOB_AND_REQUEST_PROOF')
    validate_fresh_startup_proof(proof,req,now_unix=time.time(),uid=1278,boot_id=boot,max_age_seconds=120)
    result=subprocess.run(req['execution_argv'],stdin=subprocess.DEVNULL)
    write_new(ROOT/'control/queue_finished'/(req['job_name']+'.json'),{'job_id':jid,
        'request_reference':pin(a.request),'startup_proof_reference':pin(path),'child_returncode':result.returncode,
        'observed_at':now(),'memory_policy':req['memory_policy'],'forced_signals_sent':False,'automatic_resubmission':False})
    return result.returncode


if __name__=='__main__':raise SystemExit(main())
