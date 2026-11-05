"""One actual32 PID waits for independent login proof then execs exact producer."""
import argparse,os,socket,time
from pathlib import Path
from secondary_cpu_queue_v1 import common as Q
from . import contracts as C

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',required=True);a=p.parse_args();plan=C.validate(Q.load(a.plan));C.parent_review(plan)
    Q.need(os.getuid()==1264 and socket.gethostname().split('.')[0]==plan['node'] and os.environ.get('SLURM_JOB_PARTITION')=='cpu'
      and os.environ.get('SLURM_CPUS_PER_TASK')=='32' and os.environ.get('SLURM_JOB_ID','').isdecimal() and os.environ.get('CUDA_VISIBLE_DEVICES')=='','ACTUAL_REAL_ALPHA32_GATE')
    directory=Path(plan['startup_proof_path']).parent;ready=directory/'proof.ready.json';identity=Q.self_identity()
    Q.write_new(directory/'started.json',{'schema':'ALPHA_DAY32_ACTUAL_PARENT_WAITING_V1','job_id':os.environ['SLURM_JOB_ID'],
      'plan_reference':Q.ref(a.plan),'actual_parent_identity':identity,'scientific_DATA_or_chemistry_started':False})
    until=time.monotonic()+120
    while not ready.exists():Q.need(time.monotonic()<until,'WAIT120_NO_FRESH32_PROOF_NO_SCIENCE');time.sleep(.25)
    marker=Q.load(ready);proof=Q.load(plan['startup_proof_path']);Q.need(marker['proof_reference']==Q.ref(plan['startup_proof_path'])
      and marker['job_id']==proof['job_id']==os.environ['SLURM_JOB_ID'] and proof['plan_reference']==Q.ref(a.plan)
      and proof['parent_identity']['pid']==identity['pid'] and proof['parent_identity']['start_ticks']==identity['start_ticks']
      and 0<=time.time()-proof['observed_unix_seconds']<=120,'SAME_PID_INDEPENDENT_REAL32_PROOF')
    os.chdir(Q.ROOT/'code');os.execv(plan['execution_argv'][0],plan['execution_argv'])
if __name__=='__main__':main()
