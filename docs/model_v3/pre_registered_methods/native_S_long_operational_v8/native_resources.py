"""Native-only automatic Slurm-memory admission; frozen GPU/process rules retained."""
from __future__ import annotations
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import socket
from long_common import *

POLICY=N/'model_GPU_auto_memory_policy_v1_source'
POLICY_PIN='cbb3d620f90768272abb2e135a11e928a861a896e9c51c80b5bea82ec6eca245'
SOFTWARE=32<<30
NODE_QUERY=['scontrol','show','node',NODE]
QUEUE_QUERY=['squeue','-h','-w',NODE,'-o','%i|%u|%t|%m|%C']


def shared():
    spec=importlib.util.spec_from_file_location('Native_B_shared_GPU_auto_memory_policy',POLICY/'policy.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.verify_package(POLICY_PIN)
    return module


def clean_environment():
    return {key:value for key,value in os.environ.items() if not key.startswith('SBATCH_')}


def unavailable(row):
    if row['returncode']==0:return False
    return row.get('exception') in ('FileNotFoundError','TimeoutExpired') or any(
        x in row['stderr'].lower() for x in ('connection refused','unable to contact slurm',
        'persist_conn_open','slurm_persist_conn_open','accounting storage','problem talking to the database'))


def validate_sbatch(argv):
    require(type(argv) is list and argv and argv[0]=='sbatch','Actual sbatch argv required')
    require(not any(x=='--mem' or x.startswith(('--mem=','--mem-per-','--mem-bind','--exclusive',
        '--overcommit','--oversubscribe')) for x in argv if type(x) is str),
        'Automatic default memory: no fixed/zero memory or exclusive/overcommit override')
    for option in ('--partition=all','--nodelist='+NODE,'--cpus-per-task=16','--time=02:00:00'):
        require(argv.count(option)==1,'Original exact Slurm non-memory resources required')


def validate_allocation(job,environment,hostname,uid,cgroup):
    require(str(job)==environment.get('SLURM_JOB_ID') and environment.get('SLURM_CPUS_PER_TASK')=='16'
        and hostname==NODE and uid==1278 and environment.get('CUDA_VISIBLE_DEVICES')==GPU,
        'Actual GPU allocation/environment differs')
    require(not any(key.startswith('SBATCH_') for key in environment),'Inherited SBATCH override is forbidden')
    require(re.search(r'(?:job[_/-])'+re.escape(str(job))+r'(?:[/\n]|$)',cgroup), 'Actual Slurm job cgroup missing')
    return dict(job_id=str(job),uid=uid,hostname=hostname,cgroup=cgroup,CPU_request=16,
        software_memory_budget_bytes=SOFTWARE,software_RSS_limit_bytes=RSS,
        Slurm_memory_mode='automatic_default',fixed_memory_request_claimed=False,
        actual_Slurm_memory_environment={name:environment.get(name) for name in (
            'SLURM_MEM_PER_NODE','SLURM_MEM_PER_CPU','SLURM_MEM_PER_GPU')},
        proof='actual_Slurm_environment_plus_kernel_job_cgroup',
        allocated_memory_source='actual_environment_recorded_verbatim_not_software_budget_or_fabricated_AllocTRES')


def process_allocation(job):
    result=validate_allocation(job,os.environ,socket.gethostname(),os.getuid(),Path('/proc/self/cgroup').read_text())
    result['boot_id']=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    return result


def selected_gpu(gpus,apps):
    from common import normalized_uuid
    selected=[line.split(',') for line in gpus.splitlines() if line and normalized_uuid(line.split(',')[0])==GPU]
    require(len(selected)==1 and '5090' in selected[0][1] and selected[0][2].strip()=='590.44.01',
        'Exact physical5090/driver590.44.01 required')
    require(not any(normalized_uuid(line.split(',')[0])==GPU for line in apps.splitlines() if line.strip()),
        'Selected UUID has a foreign GPU compute process')
    return [x.strip() for x in selected[0]]


def registration_id(phase,slot):
    require(Path(phase)==N/'native_S_B20k_v3' and type(slot) is int and 1<=slot<=108,'Original finite Native slot required')
    return Path(phase).name+f'_slot_{slot:03d}_auto_v1'


def new_registration(phase,slot,adoption_ref,adoption):
    api=shared();record=api.make_registration(registration_id=registration_id(phase,slot),node=NODE,gpu_uuid=GPU,
        software_budget_bytes=SOFTWARE,rss_limit_bytes=RSS,Root_source=binding(HERE/'long_operations.py'),
        source_pins=binding(HERE/'source_pins.json'),job_id_field='actual_sbatch_job_id',
        proof_refs=(adoption_ref,adoption['method_publication'],adoption['user_auto_memory_approval']))
    registry=adoption['registry']
    with api.registry_lock(registry):
        value=read(registry);require(record['registration_id'] not in value.get('GPU_software_memory',{}),
            'Existing resource registration requires Root reconciliation; no automatic retry')
        original={key:value for key,value in value.items() if key!='GPU_software_memory'}
        api.put_registration(value,record)
        require({key:item for key,item in value.items() if key!='GPU_software_memory'}==original,
            'Resource registration must not change storage/reservation fields')
        replace_feed(registry,value)
    return record


def submitted_registration(api,value,record,submission):
    updated=dict(record,status='SUBMITTED',job_id=read_ref(submission)['actual_sbatch_job_id'],actual_submission=submission)
    api.put_registration(value,updated)
    return updated


def assess_raw(node_raw,queue_raw,meminfo_raw,*,registry,record_id,job=None):
    return shared().assess(node_raw,queue_raw,meminfo_raw,node=NODE,software_budget_bytes=SOFTWARE,
        rss_limit_bytes=RSS,registry_path=registry,current_job_id=job,current_reservation_id=record_id)


def observe(*,worker=False,root_frame=None,registry=None,record_id=None):
    rows=[]
    def run(argv,*,local=False,check=True):
        command=argv
        if not worker and local:
            command=['ssh','-n','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes',
                '-o','UserKnownHostsFile='+str(OLD/'compute21_known_hosts_v1'),NODE,shlex.join(map(str,argv))]
        row=actual(command,check=check);rows.append(row);return row
    if worker:
        require(root_frame is not None,'Actual bound Root submission frame required')
        registry=root_frame['registry'];record_id=root_frame['GPU_software_memory_registration']['registration_id']
    require(registry is not None and record_id is not None,'Explicit original registry and one Native resource registration required')
    node=run(NODE_QUERY,check=not worker);queue=run(QUEUE_QUERY,check=not worker)
    fallback=worker and (node['returncode']!=0 or queue['returncode']!=0)
    if fallback:
        require(all(x['returncode']==0 or unavailable(x) for x in (node,queue)), 'Unexpected scheduler failure cannot use fallback')
        old=root_frame['resource_observations']
        parent=[row for row in old['raw'] if row['argv'] in (NODE_QUERY,QUEUE_QUERY)]
        require(len(parent)==2,'Missing exact fresh Root controller observations')
        for row in parent:fresh(row)
        node=next(row for row in parent if row['argv']==NODE_QUERY)
        queue=next(row for row in parent if row['argv']==QUEUE_QUERY)
        require(node['returncode']==queue['returncode']==0,'Sealed Root scheduler call failed')
    values=dict(re.findall(r'(CPUAlloc|CPUTot|RealMemory|AllocMem)=(\d+)',node['stdout']))
    require(set(values)=={'CPUAlloc','CPUTot','RealMemory','AllocMem'}
        and not any(x in node['stdout'] for x in ('DOWN','DRAIN','UNKNOWN','NOT_RESPONDING')), 'Unknown/unavailable Slurm node')
    require(worker and not fallback or int(values['CPUTot'])-int(values['CPUAlloc'])>=16, '16 actual CPUs unavailable')
    host=run(['hostname','-s'],local=True)['stdout'].strip();require(host==NODE,'Wrong actual node')
    meminfo=run(['cat','/proc/meminfo'],local=True)['stdout']
    memory=assess_raw(node['stdout'],queue['stdout'],meminfo,registry=registry,record_id=record_id,
        job=os.environ['SLURM_JOB_ID'] if worker else None)
    gpus=run(['nvidia-smi','--query-gpu=uuid,name,driver_version,memory.total,memory.free',
        '--format=csv,noheader,nounits'],local=True)['stdout']
    apps=run(['nvidia-smi','--query-compute-apps=gpu_uuid,pid,process_name,used_gpu_memory',
        '--format=csv,noheader,nounits'],local=True)['stdout']
    gpu=selected_gpu(gpus,apps)
    run(['flock','-n',str(LOCK),'/bin/true'],local=True)
    return dict(raw=rows,memory=memory,gpu_row=gpu,foreign_compute_processes=[],
        Slurm_memory_mode='automatic_default',software_memory_budget_bytes=SOFTWARE,software_RSS_limit_bytes=RSS,
        registry_path=str(registry),registration_id=record_id,shared_policy=binding(POLICY/'source_pins.json'),
        scheduler_scope='sealed_fresh_Root_preallocation_frame_not_worker_live' if fallback else 'actual_live_controller',
        GPU_scope='actual_worker_NVML' if worker else 'actual_node_NVML_via_login_SSH',lock_probe_only=True)
