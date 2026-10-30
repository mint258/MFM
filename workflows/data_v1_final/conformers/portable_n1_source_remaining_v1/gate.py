"""Finite actual-node ready/proof handshake. Root alone submits/releases/signs proof."""
from __future__ import annotations
import argparse,os,pathlib,socket,sys,time
from . import contract as C,runtime as R


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=pathlib.Path,required=True);a=p.parse_args()
    plan=C.load_path(a.plan);C.review(plan);spec=C.endpoint(plan['endpoint'])
    C.need(os.getuid()==spec['uid'] and socket.gethostname().split('.')[0]==plan['node']
        and os.environ.get('SLURM_JOB_PARTITION')=='cpu' and os.environ.get('SLURM_CPUS_PER_TASK')==str(plan['cpus'])
        and os.environ.get('SLURM_JOB_ID','').isdigit(),'ACTUAL_GATE_ENDPOINT_CPU_JOB')
    control=C.literal(plan['control_directory']);control.mkdir(parents=True,exist_ok=True)
    fields=pathlib.Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()
    C.save(control/'ready.json',{'schema':'ACTUAL_PORTABLE_REMAINING_GATE_READY_V4','endpoint':spec,
        'job_id':os.environ['SLURM_JOB_ID'],'node':plan['node'],'cpus':plan['cpus'],'plan_reference':C.ref(a.plan),
        'parent_identity':{'pid':os.getpid(),'uid':os.getuid(),'start_ticks':R.ticks(os.getpid()),'boot_id':R.boot(),
            'pgid':int(fields[2]),'sid':int(fields[3]),'cgroup_sha256':C.sha(pathlib.Path('/proc/self/cgroup').read_bytes())},
        'observed_unix_seconds':time.time(),'execution_not_admitted':True})
    proof=pathlib.Path(plan['startup_proof_path']);end=time.monotonic()+120
    while not proof.exists() and time.monotonic()<end:time.sleep(.25)
    C.need(proof.exists(),'FINITE_ROOT_STARTUP_PROOF_WAIT_EXPIRED_NO_SCIENCE')
    argv=plan['execution_argv'];C.need(pathlib.Path(argv[0])==pathlib.Path(sys.executable),'EXACT_LOGICAL_PYTHON')
    os.execv(argv[0],argv)


if __name__=='__main__':main()
