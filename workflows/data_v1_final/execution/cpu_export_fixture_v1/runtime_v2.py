"""CPU runtime v2: identical resource envelope with node-local monotonic heartbeats."""
from __future__ import annotations
import datetime,json,os,pathlib,re,socket,time
from . import policy
CACHE={}

def _stat_start(pid):
    text=pathlib.Path(f'/proc/{pid}/stat').read_text();return int(text[text.rfind(')')+2:].split()[19])

def _proof(intent,pinned_path=None,cap=None,wall_limit=7200,verify_sources=True):
    path=pathlib.Path(intent);proof=policy.load(path);r=proof['request']
    policy.scope(r,verify_sources=verify_sources);name=policy.job_name(r)
    policy.require(policy.ref(pathlib.Path(__file__)) in r['source_references'],'ACTUAL_LOCAL_HEARTBEAT_RUNTIME_NOT_PINNED')
    policy.require(path==policy.ROOT/'control/submissions'/(name+'.intent.json'),'EXACT_OWN_INTENT_PATH_REQUIRED')
    policy.require(proof['uid']==os.getuid()==1278,'REAL_OWNER_REQUIRED')
    node=socket.gethostname().split('.')[0]
    policy.require(node==r['node'] and node in policy.CPU_NODES,'REAL_CPU_HOSTNAME_MUST_MATCH_REQUEST')
    policy.require(os.environ.get('SLURM_JOB_ID','').isdecimal() and os.environ.get('SLURM_JOB_PARTITION')=='cpu','ACTUAL_SLURM_CPU_PARTITION_REQUIRED')
    policy.require(int(os.environ.get('SLURM_CPUS_PER_TASK','0'))>=16 and int(os.environ.get('SLURM_MEM_PER_NODE','0'))>=r['memory_gib']*1024,'ACTUAL_CPU_AND_MEMORY_ALLOCATION_REQUIRED')
    policy.require(os.environ.get('CUDA_VISIBLE_DEVICES')=='' and all(os.environ.get(n)=='1' for n in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')),'CPU_ONLY_SINGLE_THREAD_WORKER_ENV_REQUIRED')
    policy.require(r['wall_seconds']<=wall_limit,'REVIEWED_WALL_EXCEEDED')
    if pinned_path is not None:policy.require(policy.ref(pathlib.Path(pinned_path)) in r['source_references'],'ACTUAL_RUNTIME_OR_CONFIG_NOT_PINNED')
    s=policy.load(policy.POLICY)['scopes'][r['scope_key']]
    if cap is not None:policy.require(cap<=s['output_cap_bytes'],'SCIENTIFIC_OUTPUT_EXCEEDS_FINITE_SCOPE')
    age=time.time()-datetime.datetime.fromisoformat(proof['observed_at']).timestamp()
    policy.require(0<=age<=3600,'ROOT_PREFLIGHT_STALE')
    policy.require(proof['memory_basis']==policy.BASIS and proof['actual_memory_admission_passed'] is True,'MEASURED_SMALL_TEST_ADMISSION_REQUIRED')
    policy.require(proof['account_free_bytes']-r['estimated_peak_output_bytes']>=200_000_000_000,'QUOTA_RESERVE_BELOW_200GB')
    policy.require(proof['node_memory_limit_bytes']>0 and proof['reserved_positive_other_bytes']>=0,'MEMORY_ENVELOPE_REQUIRED')
    return proof

def root_guard(path,pinned_path,cap,wall_limit=3600):
    proof=_proof(path,pinned_path,cap,wall_limit)
    policy.require(os.environ.get('DATA_V1_CPU_INTENT')==str(pathlib.Path(path)),'MONITORED_LAUNCH_INTENT_ENV_REQUIRED')
    checkpoint()
    return proof

def local_guard_directory(name,jid):
    policy.require(str(jid).isdigit(),'ACTUAL_JOB_ID_REQUIRED_FOR_LOCAL_GUARD')
    return pathlib.Path('/tmp')/('dv1_cpu_guard_1278_'+str(jid)+'_'+name)

def heartbeat_is_fresh(h,now_monotonic):
    return 0<=now_monotonic-h['observed_monotonic_seconds']<=5

def checkpoint():
    """Use node-local metadata and boot-monotonic age; no shared-FS heartbeat I/O."""
    intent=os.environ.get('DATA_V1_CPU_INTENT');folder=os.environ.get('DATA_V1_CPU_GUARD_DIR');local=os.environ.get('DATA_V1_CPU_LOCAL_GUARD_DIR')
    policy.require(bool(intent and folder and local),'LOCAL_CPU_MEMORY_MONITOR_ENV_REQUIRED')
    key=(os.getpid(),intent,folder,local)
    if key not in CACHE:
        p=_proof(intent,verify_sources=False);name=policy.job_name(p['request'])
        expected=policy.ROOT/'artifacts/cpu_analysis_guards'/name
        jid=str(os.environ['SLURM_JOB_ID'])
        policy.require(pathlib.Path(folder)==expected and pathlib.Path(local)==local_guard_directory(name,jid),'OWN_GLOBAL_AND_LOCAL_GUARD_DIRECTORIES_REQUIRED')
        policy.require(pathlib.Path(local).stat().st_uid==1278 and not pathlib.Path(local).is_symlink(),'OWN_LOCAL_GUARD_DIRECTORY_REQUIRED')
        CACHE[key]=(jid,policy.ref(pathlib.Path(intent)),p['request']['node'],p['memory_observation']['boot_id'])
    jid,iref,node,boot=CACHE[key];directory=pathlib.Path(local)
    stop=directory/'STOP.json'
    if stop.exists():
        data=policy.load(stop)
        policy.require(data['job_id']==jid and data['intent_reference']==iref,'OWN_STOP_IDENTITY_DIFFERS')
        raise RuntimeError('CPU_MEMORY_GUARD_STOP_BEFORE_NEXT_WORK:'+str(data.get('reason')))
    h=policy.load(directory/'heartbeat.json')
    policy.require(h['job_id']==jid and h['intent_reference']==iref and h['node']==node and h['uid']==1278 and h['boot_id']==boot,'LOCAL_MONITOR_IDENTITY_DIFFERS')
    policy.require(heartbeat_is_fresh(h,time.monotonic()),'CPU_MEMORY_HEARTBEAT_STALE')
    policy.require(h['state']=='ALLOW' and _stat_start(h['monitor_pid'])==h['monitor_start_ticks'],'LIVE_MEMORY_MONITOR_NOT_HEALTHY')

def memory_denial(sample,limit_bytes,reserved_other_bytes,requested_bytes,own_rss_bytes):
    """Conservative reservation: measured used plus all known other reservations."""
    if not (0<sample['available_bytes']<=sample['total_bytes'] and sample['used_bytes']==sample['total_bytes']-sample['available_bytes']):return 'INVALID_MEMORY_SAMPLE'
    limit=min(limit_bytes,sample['total_bytes'])
    if sample['used_bytes']+reserved_other_bytes+requested_bytes>limit*.85:return 'NODE_USED_PLUS_KNOWN_RESERVATIONS_AND_FULL_REQUEST_OVER85PCT'
    if own_rss_bytes>=requested_bytes*.75:return 'OWN_PROCESS_TREE_RSS_OVER75PCT_REQUEST'
    return None

def own_tree_rss(root_pid):
    """Read process metadata only; count descendant RSS conservatively, no commands/env."""
    rows={}
    for p in pathlib.Path('/proc').iterdir():
        if not p.name.isdigit():continue
        try:
            if p.stat().st_uid!=os.getuid():continue
            text=(p/'stat').read_text();v=text[text.rfind(')')+2:].split()
            rows[int(p.name)]=(int(v[1]),int(v[21])*os.sysconf('SC_PAGE_SIZE'))
        except (FileNotFoundError,ProcessLookupError,PermissionError):continue
    accepted={root_pid};changed=True
    while changed:
        more={pid for pid,(ppid,_) in rows.items() if ppid in accepted}-accepted
        changed=bool(more);accepted.update(more)
    return sum(rows[p][1] for p in accepted if p in rows),len(accepted)
