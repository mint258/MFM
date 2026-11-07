"""Finite metadata wait, then exec the exact producer; never create a proof."""
import argparse,os,time
from pathlib import Path
from .common import ROOT,UID,need,load,load_ref,ref,event,source_review


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--request',type=Path,required=True)
    args=parser.parse_args();request=load(args.request)
    need(os.getuid()==UID and os.environ.get('SLURM_JOB_ID','').isdecimal() and
         os.environ.get('SLURM_CPUS_PER_TASK')=='16' and os.environ.get('SLURM_JOB_PARTITION')=='cpu',
         'ACTUAL_OWN_ALPHA_CPU_GATE_REQUIRED')
    source_review(request['controller_review_reference']['path'])
    proof_path=Path(request['adapter']['startup_proof_path']);ready_path=Path(request['ready_path'])
    started=time.monotonic();last=float('-inf')
    while time.monotonic()-started<=120:
        if ready_path.exists():
            ready=load(ready_path)
            need(ready['job_id']==os.environ['SLURM_JOB_ID'] and ready['queue_request_reference']==ref(args.request) and
                 ready['proof_reference']==ref(proof_path),'ACTUAL_READY_PROOF_OR_REQUEST_CHANGED')
            proof=load_ref(ready['proof_reference'])
            need(proof['job_id']==ready['job_id'] and proof['schema']==request['adapter']['proof_schema'],
                 'INDEPENDENT_PRODUCER_STARTUP_PROOF_REQUIRED')
            os.chdir(request['adapter']['producer_working_directory'])
            argv=request['adapter']['producer_argv']
            os.execv(argv[0],argv)
        if time.monotonic()-last>=10:event('PENDING_ROOT_LOGIN_STARTUP_PROOF',job_id=os.environ['SLURM_JOB_ID']);last=time.monotonic()
        time.sleep(.25)
    raise ValueError('ROOT_STARTUP_PROOF_GATE_TIMEOUT120_NO_PRODUCER_STARTED_NO_RETRY')


if __name__=='__main__':main()
