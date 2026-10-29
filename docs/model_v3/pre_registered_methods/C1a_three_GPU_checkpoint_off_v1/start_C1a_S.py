"""Original supervisor launch after the shared automatic-memory worker guard."""
from __future__ import annotations
import hashlib, importlib.util, json, os, socket, subprocess, sys
from pathlib import Path
B=Path('/share/home/zixiao/descriptor_analysis');N=B/'runs/model_v3_20261026'
HERE=N/'C1a_three_GPU_checkpoint_off_v1_source'

def need(ok,message):
    if not ok:raise ValueError(message)

def main():
    need(os.getuid()==os.geteuid()==1278 and os.environ.get('SLURM_CPUS_PER_TASK')=='16'
        and os.environ.get('SLURM_JOB_ID','').isdigit(),'Actual owned16CPU Slurm worker required')
    node=os.environ['MODEL_V3_EXPECTED_NODE'];gpu=os.environ['MODEL_V3_GPU_UUID'];job=os.environ['SLURM_JOB_ID']
    need(socket.gethostname().split('.')[0]==node and os.environ['CUDA_VISIBLE_DEVICES']==gpu,'Admitted actual node/UUID required')
    deps=json.loads((HERE/'dependencies.json').read_bytes());ref=deps['shared_policy']
    need(hashlib.sha256(Path(ref['path']).read_bytes()).hexdigest()==ref['sha256'],'Resource-policy source binding differs')
    spec=importlib.util.spec_from_file_location('C1a_original_shared_GPU_auto_policy',ref['path'])
    policy=importlib.util.module_from_spec(spec);spec.loader.exec_module(policy)
    policy.verify_package(deps['shared_policy_pins']['sha256'])
    registry=N/'native_S_profile_registered_reservations_v6.json';key=os.environ['MODEL_V3_AUTO_REGISTRATION_ID']
    with policy.registry_lock(registry):
        record=policy.read(registry)['GPU_software_memory'][key];policy.validate_registration(record)
        need(record['status']=='SUBMITTED' and record['job_id']==job and record['node']==node and record['gpu_uuid']==gpu
            and record['software_budget_bytes']==64<<30 and record['rss_limit_bytes']==56<<30,'Actual Root registration/parent/GPU/budget required')
    raw=[]
    def observe(argv):
        done=subprocess.run(argv,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=30)
        need(done.returncode==0 and len(done.stdout)+len(done.stderr)<=2<<20,'Fresh actual resource observation failed')
        raw.append(dict(argv=argv,returncode=done.returncode,stdout=done.stdout,stderr=done.stderr));return done.stdout
    control=observe(['scontrol','show','node',node]);queue=observe(['squeue','-h','-w',node,'-o','%i|%u|%t|%m|%C'])
    mem=Path('/proc/meminfo').read_text()
    memory=policy.assess(control,queue,mem,node=node,software_budget_bytes=64<<30,rss_limit_bytes=56<<30,
        registry_path=registry,current_job_id=job,current_reservation_id=key)
    job_control=observe(['scontrol','show','job','-o',job])
    output=Path(os.environ['MODEL_V3_OUT']);supervisor=Path(os.environ['MODEL_V3_RECORD']);startup=Path(os.environ['MODEL_V3_STARTUP_JSON'])
    need(output.absolute()==output.resolve() and output.is_relative_to(N) and not output.exists()
        and supervisor.parent==output.parent and not supervisor.exists() and not supervisor.is_relative_to(output)
        and startup.is_relative_to(N) and startup.resolve()==startup and not startup.exists(),'Fresh disjoint output/control records required')
    startup.parent.mkdir(parents=True,exist_ok=True)
    with startup.open('x') as stream:json.dump(dict(schema='model_v3_C1a_GPU_auto_memory_startup_v1',job_id=job,
        memory=memory,raw_observations=raw,actual_meminfo=mem,actual_job_control=job_control,
        Slurm_memory_environment={k:v for k,v in os.environ.items() if k.startswith('SLURM_MEM_')},
        Slurm_memory_mode='automatic_default',fixed_memory_requested_bytes=None,finite_physical_guarantee_claimed=False),stream,indent=2);stream.write('\n')
    W=Path(os.environ['MODEL_V3_SOURCE_ROOT']);py=str(Path(sys.executable).absolute())
    child=[py,'-u','-B',str(HERE/'benchmark_C1a_S.py'),'--source-root',str(W),'--expected-gpu',os.environ['MODEL_V3_EXPECTED_GPU'],
        '--gpu-uuid',gpu,'--expected-node',node,'--code-sha',os.environ['MODEL_V3_CODE_SHA'],'--output',str(output)]
    command=[py,'-u','-B',str(W/'tools/model_v3/run_supervised.py'),'--output-root',str(output),'--record',str(supervisor),
        '--gpu-uuid',gpu,'--wall-seconds','6900','--rss-limit-bytes','60129542144','--output-budget-bytes','2147483648',
        '--private-scratch-root','/tmp/mv3n_'+job,'--private-storage-budget-bytes','2147483648','--',*child]
    os.execv(py,command)

if __name__=='__main__':main()
