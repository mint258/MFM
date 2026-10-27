"""Actual CPU parent identity handshake, then exec into producer with same PID."""
import argparse,os,socket,time
from pathlib import Path
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.probe import observation
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.registry import process_identity
from . import contract as C
Q=C.Q

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--request',type=Path,required=True);a=p.parse_args()
    r=Q.load(a.request);C.validate(r);jid=os.environ.get('SLURM_JOB_ID','')
    C.need(jid.isdecimal() and os.getuid()==1278 and socket.gethostname().split('.')[0]==r['node']
        and os.environ.get('SLURM_JOB_PARTITION')=='cpu' and os.environ.get('SLURM_CPUS_PER_TASK')==str(r['cpus'])
        and os.environ.get('CUDA_VISIBLE_DEVICES')=='','ACTUAL_PACKED_ALLOCATION_BEFORE_ANY_DATA')
    identity=process_identity(os.getpid());obs=observation();root=Path(r['startup_proof_path']).parent
    Q.write_new(root/'started.json',{'schema':'CPU_PACKED_DAY_ACTUAL_PARENT_READY_V1','job_id':jid,'request_reference':Q.pin(a.request),
        'parent_identity':identity,'memory_observation':obs,'actual_cpus':r['cpus'],'actual_memory_environment':{
            k:v for k,v in os.environ.items() if k.startswith('SLURM_MEM')},'scientific_DATA_opened':False,'native_or_science_started':False})
    marker=root/'proof.ready.json';deadline=time.monotonic()+120
    while not marker.exists():C.need(time.monotonic()<deadline,'NO_FRESH_PACKED_PROOF_NO_SCIENCE');time.sleep(1)
    m=Q.load(marker);proof=Q.load(r['startup_proof_path'])
    C.need(m['job_id']==jid and m['proof_reference']==Q.pin(r['startup_proof_path']) and proof['request_reference']==Q.pin(a.request)
        and proof['parent_identity']==identity and 0<=time.time()-proof['memory_observation']['observed_unix_seconds']<=120,
        'SAME_ACTUAL_PARENT_FRESH_ROOT_METADATA_ADMISSION')
    os.execv(r['execution_argv'][0],r['execution_argv'])
if __name__=='__main__':main()
