"""Wait for fresh Root admission on the actual allocated CPU node, then execute."""
import argparse,json,os,pathlib,socket,subprocess,time
from .shared import ROOT,load,need,pin,read_small,write_new,now
from .queue_contract import validate_request,validate_fresh_startup_proof

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--request',type=pathlib.Path,required=True);a=p.parse_args()
    req=load(a.request);validate_request(req,read_small=read_small,script_text=read_small(req['script_reference']['path']).decode())
    jid=os.environ.get('SLURM_JOB_ID','');node=socket.gethostname().split('.')[0]
    need(jid.isdecimal() and os.getuid()==1278 and node==req['node'],'ACTUAL_QUEUED_JOB_IDENTITY')
    need(os.environ.get('SLURM_JOB_PARTITION')=='cpu' and int(os.environ.get('SLURM_CPUS_PER_TASK','0'))==16,'ACTUAL_CPU16')
    need(int(os.environ.get('SLURM_MEM_PER_NODE','0'))==65536 and os.environ.get('CUDA_VISIBLE_DEVICES')=='','ACTUAL64G_CPU_ONLY')
    boot=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    notice=ROOT/'control/queue_started'/(req['job_name']+'.json')
    write_new(notice,{'job_id':jid,'node':node,'boot_id':boot,'uid':1278,'request_reference':pin(a.request),
        'observed_at':now(),'observed_unix_seconds':time.time(),'scientific_work_started':False})
    proofpath=pathlib.Path(req['startup_proof_path']);ready=proofpath.with_suffix('.ready.json');deadline=time.monotonic()+120
    while not ready.exists():
        need(time.monotonic()<deadline,'ROOT_FRESH_ADMISSION_NOT_AVAILABLE_NO_SCIENCE');time.sleep(1)
    marker=load(ready);need(marker['proof_reference']==pin(proofpath) and marker['job_id']==jid,'EXACT_READY_PROOF')
    proof=load(proofpath);need(proof['request_reference']==pin(a.request) and proof['job_id']==jid,'EXACT_CURRENT_JOB_REQUEST')
    validate_fresh_startup_proof(proof,req,now_unix=time.time(),uid=1278,boot_id=boot,max_age_seconds=120)
    result=subprocess.run(req['execution_argv'],stdin=subprocess.DEVNULL)
    write_new(ROOT/'control/queue_finished'/(req['job_name']+'.json'),{'job_id':jid,'node':node,
        'request_reference':pin(a.request),'startup_proof_reference':pin(proofpath),
        'execution_argv':req['execution_argv'],'child_returncode':result.returncode,
        'observed_at':now(),'forced_signals_sent':False,'automatic_resubmission':False})
    return result.returncode
if __name__=='__main__':raise SystemExit(main())
