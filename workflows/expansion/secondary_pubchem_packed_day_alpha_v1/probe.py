"""Actual32 waiting PID metadata only; no DATA, chemistry or proof creation."""
import argparse,os,socket,time
from pathlib import Path
from secondary_cpu_queue_v1 import common as Q
from secondary_cpu_queue_v1.probe import process
from . import contracts as C

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',required=True);p.add_argument('--job-id',required=True);p.add_argument('--pid',type=int,required=True);a=p.parse_args()
    plan=Q.load(a.plan);C.validate(plan);Q.need(os.getuid()==1264 and socket.gethostname().split('.')[0]==plan['node'],'ACTUAL_ALPHA_TARGET32_NODE')
    record=process(a.pid);env=record['selected_environment'];gate=[plan['python'],'-B','-m','secondary_pubchem_packed_day_alpha_v1.gate','--plan',a.plan]
    Q.need(record['argv']==gate and env.get('SLURM_CPUS_PER_TASK')=='32' and env.get('SLURM_JOB_ID')==a.job_id
      and env.get('SLURM_JOB_PARTITION')=='cpu' and env.get('CUDA_VISIBLE_DEVICES')=='','TRUE32_GATE_FULL_ARGV_AND_ENV')
    if ('/job_'+a.job_id+'/') not in record['cgroup'] and ('/job_'+a.job_id+'\n') not in record['cgroup']:
        listing=Q.query(['scontrol','listpids',a.job_id],emit=False);rows=[x.split() for x in listing['stdout'].splitlines()]
        Q.need(sum(len(r)>=2 and r[0]==str(a.pid) and r[1]==a.job_id for r in rows)==1,'EXACT_ACTUAL_PID_SLURM_MEMBERSHIP')
        record['actual_slurm_listpids_query']=listing
    print(Q.canonical({'schema':'ACTUAL_ALPHA_DAY32_TARGET_PID_METADATA_V1','job_id':a.job_id,'uid':1264,'node':plan['node'],
      'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'observed_unix_seconds':time.time(),'plan_reference':Q.ref(a.plan),
      'parent_identity':record,'storage':Q.storage_observation(quiet=True),'scientific_DATA_or_chemistry_read':False}).decode(),flush=True)
if __name__=='__main__':main()
