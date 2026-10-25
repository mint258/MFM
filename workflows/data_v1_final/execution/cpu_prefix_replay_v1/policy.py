"""Exact small-scope policies and metadata pins. No scheduler or scientific imports."""
from __future__ import annotations
import hashlib,json,os,pathlib,re
ROOT=pathlib.Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025')
REPO=ROOT/'repository'
POLICY=REPO/'configs/data_v1/cpu_prefix_replay_scopes_v1.json'
DECISION=REPO/'configs/data_v1/cpu_prefix_replay_decision_v1.json'
CPU_NODES={f'compute-0-{n}' for n in (2,*range(8,20))}
BASIS='CPU_BOUNDED_TEST_LIVE_MEMORY_V1'
MAX_SMALL=2*1024**2
GUARD_CAP=32*1024**2

def require(ok,message):
    if not ok:raise ValueError(message)

def read_small(path):
    p=pathlib.Path(path)
    require(p.is_absolute() and '..' not in p.parts and p.is_file() and not p.is_symlink(),'LITERAL_SMALL_REGULAR_FILE_REQUIRED')
    with p.open('rb') as f:
        before=os.fstat(f.fileno());require(before.st_size<=MAX_SMALL,'SMALL_METADATA_2MIB_LIMIT')
        b=f.read(MAX_SMALL+1);after=os.fstat(f.fileno())
    require(len(b)==before.st_size<=MAX_SMALL and (before.st_ino,before.st_mtime_ns,before.st_size)==(after.st_ino,after.st_mtime_ns,after.st_size),'SMALL_FILE_CHANGED')
    return b

def ref(path):
    p=pathlib.Path(path);b=read_small(p)
    return {'path':str(p),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}

def load(path):return json.loads(read_small(path))

def verify(pin):
    require(ref(pin['path'])=={k:pin[k] for k in ('path','bytes','sha256')},'SMALL_SOURCE_PIN_CHANGED:'+pin['path'])
    return pathlib.Path(pin['path'])

def scope(request,verify_sources=True):
    require(request['kind']=='analysis' and request['pilot'] is True,'ONLY_BOUNDED_ANALYTICAL_PILOTS_ALLOWED')
    require(request['resource_policy']==BASIS and request['node'] in CPU_NODES,'CPU_SCOPE_OR_MEMORY_BASIS_INVALID')
    require(request['cpus']==16,'EXACT_BOUNDED_16_CPU_POOL_REQUIRED')
    require(request['decision_reference']==ref(DECISION) and request['scope_policy_reference']==ref(POLICY),'ACTUAL_DECISION_AND_SCOPE_POLICY_REQUIRED')
    p=load(POLICY);s=p['scopes'][request['scope_key']]
    require(request['scope_parameters']==s['parameters'],'FINITE_SCIENTIFIC_SCOPE_DIFFERS')
    require(request['memory_gib']==s['memory_gib'] and 0<request['wall_seconds']<=s['wall_seconds'],'SMALL_SCOPE_MEMORY_OR_WALL_DIFFERS')
    require(s['output_cap_bytes']+GUARD_CAP<=request['estimated_peak_output_bytes']<=s['output_cap_bytes']+2*GUARD_CAP,'WHOLE_RUN_OUTPUT_WITH_MONITOR_BUDGET_DIFFERS')
    require(request['root_review']['status']=='APPROVED' and request['root_review']['reviewer']=='root','EXPLICIT_ROOT_REVIEW_REQUIRED')
    require(request['base_request_reference']==s['base_request_reference'],'REVIEWED_ORIGINAL_TEST_REQUEST_REQUIRED')
    require(request.get('formal_generation_authorized') is False,'NO_FORMAL_GENERATION_AUTHORITY')
    refs=request['source_references'];by_path={r['path']:r for r in refs}
    require(len(by_path)==len(refs),'DUPLICATE_SOURCE_REFERENCE')
    for pth in (POLICY,DECISION,*[REPO/'workflows/data_v1_final/execution/cpu_prefix_replay_v1'/n for n in ('policy.py','runtime.py','probe_memory.py','launch.py','submit_cpu_pilot_v1.py')]):
        require(by_path.get(str(pth))==ref(pth),'CENTRAL_RUNTIME_OR_POLICY_NOT_PINNED:'+str(pth))
    for pin in [s['base_request_reference'],*s.get('authority_references',[])]:
        require(by_path.get(pin['path'])==pin,'BOUNDED_SOURCE_AUTHORITY_NOT_PINNED')
        if verify_sources:verify(pin)
    if verify_sources:
        for pin in [request['script_reference'],*refs]:verify(pin)
    return s

def job_name(request):
    text=read_small(verify(request['script_reference'])).decode()
    require(text.startswith('#!/bin/bash\n') and '\r' not in text,'LF_SBATCH_REQUIRED')
    d={}
    for line in text.splitlines():
        m=re.fullmatch(r'#SBATCH --([\w-]+)=(\S+)',line)
        if m:d[m[1]]=m[2]
    name=d['job-name'];require(re.fullmatch(r'dv1_[A-Za-z0-9_]+',name) is not None,'DV1_NAME_REQUIRED')
    require(d['partition']=='cpu' and d['nodelist']==request['node'],'REAL_CPU_PARTITION_AND_NODE_REQUIRED')
    require(d['nodes']=='1' and d['ntasks']=='1' and int(d['cpus-per-task'])==16,'ONE_16_CPU_ALLOCATION_REQUIRED')
    require(d['mem']==str(request['memory_gib'])+'G','EXACT_SCOPE_MEMORY_DIRECTIVE_REQUIRED')
    parts=list(map(int,d['time'].split(':')));require(len(parts)==3 and parts[0]*3600+parts[1]*60+parts[2]==request['wall_seconds'],'WALL_DIRECTIVE_DIFFERS')
    require(not any(k in d for k in ('gres','gpus','gpus-per-node')),'GPU_REQUEST_FORBIDDEN')
    expected=str(ROOT/'control/submissions'/(name+'.intent.json'))
    require('--intent '+expected+' -- ' in text,'REVIEWED_LAUNCHER_INTENT_AND_COMMAND_REQUIRED')
    require('workflows.data_v1_final.execution.cpu_prefix_replay_v1.launch' in text,'MONITORED_LAUNCHER_REQUIRED')
    return name
