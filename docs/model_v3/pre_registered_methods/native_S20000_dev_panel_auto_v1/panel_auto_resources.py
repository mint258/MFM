"""Source-bound automatic memory overlay for the unchanged Native full panel."""
from __future__ import annotations
from copy import deepcopy
from datetime import datetime,timezone
import hashlib,importlib.util,json,os,re,socket,time
from pathlib import Path
from native_admission import B,N,REGISTRY,LIMIT,binding,read_ref,load,need,bare

HERE=Path(__file__).absolute().parent
OLD=N/'gpu_runtime_retry_v4/submit_composed_eq_gpu_runtime_retry_v4.py'
OLD_SHA='d3cba6a8610e6bd55fa21873be5c770efbe30be73b7b16d4f1cbdfa6ccb1c193'
POLICY=N/'model_GPU_auto_memory_policy_v1_source'
POLICY_PIN='cbb3d620f90768272abb2e135a11e928a861a896e9c51c80b5bea82ec6eca245'
NODE='compute-0-21';GPU='GPU-c35f2434-9137-9723-1af5-dc69b6295243'
BUDGET=32<<30;RSS=28<<30
PREFIX='docs/model_v3/pre_registered_methods/native_S20000_dev_panel_auto_v1/'


def original():
    need(binding(OLD)['sha256']==OLD_SHA,'Original resource raw validators changed')
    return load(OLD,'native20k_original_resource_primitives')


def policy():
    module=load(POLICY/'policy.py','native20k_shared_auto_memory_policy')
    module.verify_package(POLICY_PIN)
    return module


def verify_sources():
    item=binding(HERE/'source_pins.json');pins=read_ref(item)
    need(pins['schema']=='native_S20000_panel_auto_sources_v1','Exact20k source family required')
    for row in pins['files']:
        need(binding(HERE/row['relative_path'])=={'path':str(HERE/row['relative_path']),
            'bytes':row['bytes'],'sha256':row['sha256']},'20k operational source drift')
    for row in read_ref(pins['dependencies'])['files']:
        need(binding(row['path'])==bare(row),'Bound unchanged dependency changed')
    policy()
    return item


def verify_publication(item):
    need(binding(item['path'])==item,'Actual new publication rawref changed')
    value=read_ref(item)
    need(value['schema']=='model_v3_exact_tree_publication_actual_v1'
        and value['repository_full_name']=='mint258/MFM' and value['branch']=='model-v3'
        and value['public_branch_readback_verified'] is True and value['public_Git_API_tree_readback_verified'] is True,
        'Actual new20k exact-tree publication required')
    table={x['path']:x for x in value['files']};need(len(table)==len(value['files']),'Duplicate public path')
    pins=read_ref(verify_sources())
    for name in [row['relative_path'] for row in pins['files']]+['source_pins.json']:
        raw=(HERE/name).read_bytes();row=table[PREFIX+name]
        need(row['type']=='blob' and row['sha']==hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest(),
            'Exact published20k method source required: '+name)
    policy().verify_publication(item)
    return value


def Recorder():
    return original().Recorder()


def quota_reserve(raw):
    return original().quota_reserve(raw)


def recorded_assessment(snapshot,node,queue,mem,registration_id):
    api=policy();seed=api.read(POLICY/'legacy_bindings.json');table=snapshot.get(api.REGISTRY_KEY,{})
    need(snapshot['schema']=='native_S_Root_registered_reservations_v1'
        and snapshot['uid']==1278 and snapshot['authority']=='ROOT_ACTUAL' and type(table) is dict,
        'Actual source-bound registry snapshot required')
    need(all(key==row['registration_id'] for key,row in table.items()),'Recorded registry keys/IDs differ')
    records=list(seed['registrations'])+list(table.values())
    for row in records:api.validate_registration(row)
    # Pure SAME frozen arithmetic, only for historical raw-frame reproducibility.
    # Startup below uses public assess() and a fresh live locked registry instead.
    return api._assess(node,queue,mem,node=NODE,software_budget_bytes=BUDGET,rss_limit_bytes=RSS,
        registrations=records,current_reservation_id=registration_id)


def capture_root(spec,output):
    old=original();api=policy();recorder=old.Recorder();started=time.monotonic()
    node=recorder.capture(['scontrol','show','node',NODE]);queue=recorder.capture(['squeue','-h','-w',NODE,'-o','%i|%u|%t|%m|%C'])
    state=re.search(r'\bState=(\S+)',node);values=dict(re.findall(r'\b(CPUAlloc|CPUTot|RealMemory|AllocMem)=(\d+)',node))
    need(state and not any(word in state[1] for word in ('DOWN','DRAIN','UNKNOWN','FAIL','MAINT','REBOOT','POWER'))
        and set(values)=={'CPUAlloc','CPUTot','RealMemory','AllocMem'}
        and int(values['CPUTot'])-int(values['CPUAlloc'])>=16,'Original live node/16CPU gate required')
    ssh=['ssh','-n','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes',
         '-o','UserKnownHostsFile='+str(B/'runs/model_v3_20261025/compute21_known_hosts_v1'),NODE]
    mem=recorder.capture(ssh+['head -n 5 /proc/meminfo'])
    rid=spec['storage']['reservation_id']
    assessment=api.assess(node,queue,mem,node=NODE,software_budget_bytes=BUDGET,rss_limit_bytes=RSS,
        registry_path=REGISTRY,current_reservation_id=rid)
    with api.registry_lock(REGISTRY):snapshot=api.read(REGISTRY)
    need(recorded_assessment(snapshot,node,queue,mem,rid)==assessment,'Registry changed during raw assessment snapshot')
    gpu=recorder.capture(ssh+['nvidia-smi --query-gpu=uuid,name,memory.total,memory.free --format=csv,noheader,nounits'])
    apps=recorder.capture(ssh+['nvidia-smi --query-compute-apps=gpu_uuid,pid,process_name,used_gpu_memory --format=csv,noheader,nounits'])
    selected=old.gpu_idle(gpu,apps,spec['gpu_uuid'])
    need(float(selected['memory_total_MiB'])>0,'Positive known physical GPU capacity required')
    lock=B/'docs/phase1/evidence/stage46_shared_gpu_launch/.own_gpu_uuid_locks'/(spec['gpu_uuid']+'.lock')
    recorder.capture(ssh+['flock -n '+str(lock)+' true'])
    duration=time.monotonic()-started;need(duration<=30,'Original30s resource capture bound exceeded')
    quota=old.quota_reserve(recorder.capture(['quota','-v','-u','zixiao']))
    observations={}
    wanted=old.resource_observation_argv()
    for role,argv in wanted.items():
        rows=[old.enrich_observation(row) for row in recorder.rows if row['argv']==argv]
        need(len(rows)==1,'Exactly one original raw observation for '+role);old.checked_observation(rows[0],argv)
        observations[role]=rows[0]
    body=dict(schema='native_S_panel_auto_Root_resource_frame_v1',origin='ROOT_PRE_SUBMISSION_NOT_WORKER_LIVE',
        node=NODE,gpu_uuid=spec['gpu_uuid'],observations=observations,all_raw_observations=recorder.rows,
        registry_snapshot=snapshot,assessment=assessment,selected_GPU=selected,quota=quota,
        resource_capture_seconds=duration,source_pins=verify_sources(),method_publication=spec['method_publication'],
        Slurm_memory_mode='automatic_default',software_memory_budget_bytes=BUDGET,RSS_limit_bytes=RSS)
    frame={**body,'body_sha256':old.canonical_digest(body)}
    verify_root_resources(frame,{'gpu_uuid':spec['gpu_uuid']},spec=spec)
    return frame


def verify_root_resources(frame,inputs,*,spec,now=None):
    old=original();body={key:value for key,value in frame.items() if key!='body_sha256'}
    need(old.canonical_digest(body)==frame['body_sha256'] and frame['schema']=='native_S_panel_auto_Root_resource_frame_v1'
        and frame['origin']=='ROOT_PRE_SUBMISSION_NOT_WORKER_LIVE' and frame['node']==NODE
        and frame['gpu_uuid']==inputs['gpu_uuid']==spec['gpu_uuid']==GPU
        and frame['source_pins']==verify_sources() and frame['method_publication']==spec['method_publication']
        and frame['Slurm_memory_mode']=='automatic_default' and frame['software_memory_budget_bytes']==BUDGET
        and frame['RSS_limit_bytes']==RSS and 0<=frame['resource_capture_seconds']<=30,
        'Exact source-bound automatic Root frame required')
    verify_publication(frame['method_publication'])
    wanted=old.resource_observation_argv();rows=frame['observations'];need(set(rows)==set(wanted),'Exact raw roles required')
    for role,argv in wanted.items():old.checked_observation(rows[role],argv)
    actual=recorded_assessment(frame['registry_snapshot'],rows['node']['stdout'],rows['queue']['stdout'],
        rows['memory']['stdout'],spec['storage']['reservation_id'])
    need(actual==frame['assessment'] and old.gpu_idle(rows['GPU']['stdout'],rows['applications']['stdout'],GPU)==frame['selected_GPU']
        and old.quota_reserve(rows['quota']['stdout'])==frame['quota'],'Raw Root resource arithmetic/binding differs')
    lock=B/'docs/phase1/evidence/stage46_shared_gpu_launch/.own_gpu_uuid_locks'/(GPU+'.lock')
    lock_argv=['ssh','-n','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes',
        '-o','UserKnownHostsFile='+str(B/'runs/model_v3_20261025/compute21_known_hosts_v1'),NODE,'flock -n '+str(lock)+' true']
    probes=[old.enrich_observation(row) for row in frame['all_raw_observations'] if row['argv']==lock_argv]
    need(len(probes)==1,'Exact original public UUID-lock Root probe required')
    old.checked_observation(probes[0],lock_argv)
    current=datetime.now(timezone.utc) if now is None else now
    ages={role:(current-datetime.fromisoformat(row['finished_utc'])).total_seconds() for role,row in rows.items()}
    need(all(0<=age<=120 for age in ages.values()) and
        0<=(current-datetime.fromisoformat(probes[0]['finished_utc'])).total_seconds()<=120,
        'Original120s Root frame freshness exhausted')
    return ages


def actual_allocation_identity(spec):
    need(os.getuid()==os.geteuid()==1278 and socket.gethostname().split('.')[0]==NODE
        and os.environ.get('SLURMD_NODENAME')==NODE and os.environ.get('SLURM_CPUS_PER_TASK')=='16'
        and os.environ.get('CUDA_VISIBLE_DEVICES')==spec['gpu_uuid']==GPU,'Actual original node/CPU16/UID/GPU required')
    job=os.environ.get('SLURM_JOB_ID','');group=Path('/proc/self/cgroup').read_text()
    need(job.isdigit() and re.search(r'/job_'+re.escape(job)+r'(?:/|$)',group),'Actual job kernel cgroup required')
    need(not any(key.startswith('SBATCH_') for key in os.environ),'Inherited SBATCH override forbidden')
    tail=Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()
    return dict(job_id=job,node=NODE,uid=os.getuid(),pid=os.getpid(),start_ticks=int(tail[19]),
        boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),pgid=os.getpgid(0),sid=os.getsid(0),
        cgroup=group,cgroup_sha256=hashlib.sha256(group.encode()).hexdigest(),cpus_per_task=16,
        actual_Slurm_memory_environment={key:os.environ.get(key) for key in ('SLURM_MEM_PER_NODE','SLURM_MEM_PER_CPU','SLURM_MEM_PER_GPU')},
        software_memory_budget_bytes=BUDGET,RSS_limit_bytes=RSS,actual_memory_reserved_bytes_claimed=None)


def worker_resource_evidence(recorder,inputs,root_frame,allocation,*,spec):
    ages=verify_root_resources(root_frame,inputs,spec=spec)
    node=recorder.capture(['scontrol','show','node',NODE]);queue=recorder.capture(['squeue','-h','-w',NODE,'-o','%i|%u|%t|%m|%C'])
    mem=recorder.capture(['head','-n','5','/proc/meminfo'])
    assessment=policy().assess(node,queue,mem,node=NODE,software_budget_bytes=BUDGET,rss_limit_bytes=RSS,
        registry_path=REGISTRY,current_job_id=allocation['job_id'],current_reservation_id=spec['storage']['reservation_id'])
    gpu=recorder.capture(['nvidia-smi','--query-gpu=uuid,name,memory.total,memory.free','--format=csv,noheader,nounits'])
    apps=recorder.capture(['nvidia-smi','--query-compute-apps=gpu_uuid,pid,process_name,used_gpu_memory','--format=csv,noheader,nounits'])
    current_GPU=original().gpu_idle(gpu,apps,inputs['gpu_uuid'])
    need(float(current_GPU['memory_total_MiB'])>0,'Positive known actual worker GPU capacity required')
    return dict(origin='ACTUAL_WORKER_LIVE_SCHEDULER_AND_MEMAVAILABLE',Root_frame_ages=ages,assessment=assessment,current_GPU=current_GPU,
        actual_allocation=allocation,Slurm_memory_mode='automatic_default',fixed_memory_allocation_claimed=False)
