"""New CPU-only contracts: no requested memory, exclusivity or 85% admission."""
from __future__ import annotations
import hashlib,json,re
from datetime import datetime
from pathlib import PurePosixPath
from ..queue_v1 import queue_contract as fmt
from .slurm_format import fields

RUN=fmt.RUN;PROJECT=fmt.PROJECT;PY=fmt.PYTHON
MEMORY_POLICY='SLURM_DEFAULT_UNSPECIFIED'
REQUEST_SCHEMA='CPU_AUTO_MEMORY_QUEUED_REQUEST_V1'
PROOF_SCHEMA='FRESH_CPU_AUTO_MEMORY_EXECUTION_ADMISSION_V1'
NODES={'analysis':[2,*range(8,20)],'conformer':list(range(11,20)),'qm':list(range(11,20))}
MODES={'FIXTURE_ONLY','BOUNDED_METADATA_PREPARATION','BOUNDED_PERFORMANCE_BATCH',
       'FULL_SOURCE_INVENTORY_PRIOR_CRC','FULL_SOURCE_AFTER_PROFILE'}
FORBIDDEN={'memory_gib','memory_basis','resource_policy','exclusive_user','memory_fraction',
           'declared_memory_fraction','memory_exemption'}


def need(ok,code):
    if not ok:raise ValueError(code)


def same(a,b):return fmt._same(a,b)
def pin(value,small=True):return fmt._pin(value,small=small)
def literal(value):return fmt._literal_path(str(value))

def pin_bytes(value,read_small):
    value=pin(value);raw=read_small(value['path'])
    need(type(raw) is bytes and len(raw)==value['bytes'] and
         hashlib.sha256(raw).hexdigest()==value['sha256'],'ACTUAL_SMALL_PIN_CHANGED')
    return raw


def validate_authority(reference,*,read_small):
    a=json.loads(pin_bytes(reference,read_small))
    need(a.get('schema')=='USER_AUTHORIZED_CPU_AUTO_MEMORY_DECISION_V1' and
         a.get('status')=='USER_AUTHORIZED','NEW_USER_RESOURCE_AUTHORITY_REQUIRED')
    need(a.get('memory_policy')==MEMORY_POLICY and a.get('partition')=='cpu' and
         a.get('cpus_per_task')==16 and a.get('allowed_nodes')==NODES and
         a.get('max_wall_seconds')==172800 and a.get('quota_reserve_bytes')==200000000000,
         'EXACT_NEW_CPU_NODE_AND_RESOURCE_AUTHORITY_REQUIRED')
    for key in ('memory_directives_allowed','exclusive_requested','declared_memory_fraction_admission'):
        need(a.get(key) is False,'NO_REQUESTED_MEMORY_EXCLUSIVITY_OR_PERCENT_ADMISSION:'+key)
    for key in ('record_actual_memory','no_forced_signals','old_scientific_gates_unchanged'):
        need(a.get(key) is True,'NEW_AUTHORITY_INVARIANT_REQUIRED:'+key)
    need(type(a.get('user_statements')) is list and len(a['user_statements'])>=2 and
         all(type(v) is str and v.strip() for v in a['user_statements']),'ACTUAL_USER_STATEMENTS_REQUIRED')
    return a


def validate_scope_spec(spec,authority,*,read_small):
    need(spec.get('schema')=='ROOT_REVIEWED_CPU_AUTO_MEMORY_STAGE_SPEC_V1','NEW_STAGE_SPEC_SCHEMA_REQUIRED')
    need(spec.get('kind') in NODES and type(spec.get('pilot')) is bool,'EXACT_ROLE_AND_HONEST_PILOT_REQUIRED')
    need(not FORBIDDEN.intersection(spec),'OLD_RESOURCE_FIELDS_CANNOT_ENTER_NEW_SPEC')
    need(('cpus' not in spec or type(spec['cpus']) is int and spec['cpus']==16) and
         ('memory_policy' not in spec or spec['memory_policy']==MEMORY_POLICY),'EXACT_NEW_SPEC_CPU_AND_MEMORY_POLICY')
    need(type(spec.get('scope_key')) is str and re.fullmatch(r'[a-z][a-z0-9_]{0,127}',spec['scope_key'])
         and type(spec.get('scope_parameters')) is dict,'EXACT_SCOPE_KEY_AND_PARAMETERS_REQUIRED')
    need(type(spec.get('wall_seconds')) is int and 0<spec['wall_seconds']<=172800,'FINITE_MAX48H_WALL_REQUIRED')
    need(type(spec.get('estimated_peak_output_bytes')) is int and spec['estimated_peak_output_bytes']>0,'WHOLE_OUTPUT_CAP_REQUIRED')
    scope=spec.get('scope',{});mode=scope.get('mode')
    need(mode in MODES and 'parent_profile' in scope,'EXPLICIT_SCOPE_MODE_AND_PARENT_REQUIRED')
    if mode=='FIXTURE_ONLY':need(spec['pilot'] is True,'FIXTURE_REQUIRES_TRUE_PILOT')
    elif mode!='BOUNDED_PERFORMANCE_BATCH':need(spec['pilot'] is False,'FULL_OR_PREPARATION_REQUIRES_FALSE_PILOT')
    review=json.loads(pin_bytes(scope.get('review'),read_small))
    need(review.get('schema')=='EXACT_CPU_AUTO_MEMORY_SCOPE_ROOT_REVIEW_V1' and
         review.get('status')=='APPROVED_FOR_EXACT_STAGE' and review.get('reviewer')=='root' and
         review.get('resource_authority_reference')==authority,'EXACT_NEW_AUTHORITY_ROOT_SCOPE_REVIEW_REQUIRED')
    for key in ('kind','scope_key','scope_parameters','pilot','wall_seconds',
                'estimated_peak_output_bytes','execution_argv','source_status_stage'):
        need(same(spec.get(key),review.get(key)),'ROOT_EXACT_SCOPE_FIELD_DIFFERS:'+key)
    need(review.get('scope_mode')==mode,'ROOT_SCOPE_MODE_DIFFERS')
    cap=spec.get('stage_output_cap_bytes',spec['estimated_peak_output_bytes'])
    need(type(cap) is int and 0<cap<=spec['estimated_peak_output_bytes'] and
         review.get('stage_output_cap_bytes')==cap,'STAGE_CAP_WITHIN_WHOLE_CAP_REQUIRED')
    parents=review.get('parent_evidence_references')
    need(type(parents) is list and (parents or mode=='FIXTURE_ONLY'),'ACTUAL_PARENT_EVIDENCE_REQUIRED')
    normalized=[pin(value) for value in parents]
    need(len({p['path'] for p in normalized})==len(parents),'UNIQUE_PARENT_PINS_REQUIRED')
    for value in normalized:pin_bytes(value,read_small)
    profile=scope['parent_profile']
    if profile is not None:need(pin(profile) in normalized,'EXACT_PARENT_PROFILE_REQUIRED')
    if mode=='BOUNDED_PERFORMANCE_BATCH':need(review.get('bounded_batch_limits_reviewed') is True,'BOUNDED_PERFORMANCE_LIMITS_REQUIRED')
    if mode=='FULL_SOURCE_AFTER_PROFILE':
        need(profile is not None and review.get('profile_reviewed') is True and
             review.get('approved_profile_reference')==profile,'FULL_STAGE_REQUIRES_REVIEWED_PROFILE')
    if mode=='FULL_SOURCE_INVENTORY_PRIOR_CRC':
        need(cap<=10*1024**3 and review.get('inventory_only') is True and
             review.get('candidate_release_authorized') is False and review.get('crc_full_eof_actual_passed') is True and
             review.get('crc_receipt_reference') in normalized,'PRIOR_CRC_INVENTORY_ONLY_10GIB_CAP_REQUIRED')
    return {'parents':normalized,'review':review,'mode':mode}


def validate_script(request,text):
    d=fmt._directives(text)
    expected={'job-name':request['job_name'],'partition':'cpu','nodelist':request['node'],
              'nodes':'1','ntasks':'1','cpus-per-task':'16'}
    need(all(d.get(k)==v for k,v in expected.items()),'SCRIPT_EXACT_CPU_RESOURCES_REQUIRED')
    need(set(d)<=set(expected)|{'time','output','chdir'} and
         not any(k.startswith('mem') or k.startswith('gpu') or k in {'exclusive','gres'} for k in d),
         'NO_MEMORY_GPU_OR_EXCLUSIVE_DIRECTIVES_ALLOWED')
    need(fmt._wall(d.get('time',''))==request['wall_seconds'] and d.get('chdir',PROJECT)==PROJECT,
         'SCRIPT_WALL_OR_WORKDIR_DIFFERS')
    return d


def validate_request(request,*,read_small,script_text=None):
    need(request.get('schema')==REQUEST_SCHEMA and request.get('memory_policy')==MEMORY_POLICY,
         'NEW_UNSPECIFIED_MEMORY_REQUEST_REQUIRED')
    need(not FORBIDDEN.intersection(request) and request.get('exclusive_requested') is False,
         'NO_OLD_MEMORY_OR_EXCLUSIVE_RESOURCE_FIELDS')
    kind=request.get('kind');need(kind in NODES,'EXACT_COMPUTE_ROLE_REQUIRED')
    need(request.get('node') in {'compute-0-'+str(n) for n in NODES[kind]} and
         request.get('partition')=='cpu' and type(request.get('cpus')) is int and request['cpus']==16,
         'AUTHORIZED_CPU_NODE_AND_EXACT16_REQUIRED')
    need(type(request.get('wall_seconds')) is int and 0<request['wall_seconds']<=172800,'MAX48H_WALL_REQUIRED')
    need(type(request.get('estimated_peak_output_bytes')) is int and request['estimated_peak_output_bytes']>0,
         'FINITE_WHOLE_OUTPUT_CAP_REQUIRED')
    need(type(request.get('pilot')) is bool and request.get('workdir')==PROJECT,'PILOT_AND_WORKDIR_REQUIRED')
    name=request.get('job_name');need(type(name) is str and re.fullmatch(r'dv1_q_[A-Za-z0-9_]+',name),'SAFE_NEW_JOB_NAME_REQUIRED')
    need(request.get('startup_proof_path')==RUN+'/control/queue_startup/'+name+'.json'
         and request.get('startup_wait_seconds')==120,'EXACT_NEW_STARTUP_PATH_AND_WAIT_REQUIRED')
    argv=request.get('execution_argv');need(type(argv) is list and len(argv)>=2 and argv[0]==PY and
         all(type(v) is str and not any(c in v for c in ('\0','\n','\r')) for v in argv),'EXACT_LITERAL_PYTHON_ARGV_REQUIRED')
    deps=request.get('dependencies',[]);need(type(deps) is list and len(set(deps))==len(deps) and
         all(type(v) is str and v.isdecimal() for v in deps),'EXACT_AFTEROK_JOB_IDS_REQUIRED')
    review=request.get('root_review',{});need(review.get('status')=='APPROVED' and review.get('reviewer')=='root','ROOT_REVIEW_REQUIRED')
    refs=request.get('source_references');need(type(refs) is list and refs,'SMALL_SOURCES_REQUIRED')
    refs=[pin(v) for v in refs];need(len({v['path'] for v in refs})==len(refs),'UNIQUE_SOURCE_PINS_REQUIRED')
    authority=pin(request.get('queue_authority_reference'));need(authority in refs,'RESOURCE_AUTHORITY_MUST_BE_PINNED')
    validate_authority(authority,read_small=read_small)
    bodies=[pin(v,small=False) for v in request.get('data_references',[])]
    need(len({v['path'] for v in bodies})==len(bodies) and
         not {v['path'] for v in bodies}&{v['path'] for v in refs},'UNIQUE_DISJOINT_DATA_LOCATORS_REQUIRED')
    script=pin(request.get('script_reference'));seen={}
    for value in [*refs,script]:
        if value['path'] in seen:need(seen[value['path']]==value,'CONFLICTING_SOURCE_PIN');continue
        raw=pin_bytes(value,read_small);seen[value['path']]=value
        if value==script:actual_text=raw.decode('utf-8')
    if script_text is not None:need(script_text==actual_text,'SCRIPT_TEXT_NOT_PINNED_BYTES')
    validate_script(request,actual_text)
    return {'status':'NEW_CPU_REQUEST_VALIDATED_NOT_STARTED','memory_policy':MEMORY_POLICY,
            'memory_admission_evaluated':False,'data_bodies_read_or_stat':False}


def validate_bound_request(request,*,read_small):
    ref=request['root_review']['stage_spec_reference'];spec=json.loads(pin_bytes(ref,read_small))
    result=validate_scope_spec(spec,request['queue_authority_reference'],read_small=read_small)
    controls={'schema','kind','pilot','cpus','memory_policy','wall_seconds','estimated_peak_output_bytes',
              'execution_argv','source_references','data_references','deferred_authority_references'}
    for key,value in spec.items():
        if key not in controls:need(same(request.get(key),value),'PRODUCER_DOMAIN_FIELD_NOT_PRESERVED:'+key)
    for key in ('kind','pilot','wall_seconds','estimated_peak_output_bytes'):
        need(same(request.get(key),spec[key]),'BOUND_RESOURCE_FIELD_DIFFERS:'+key)
    for key in ('data_references','deferred_authority_references'):
        need(same(request.get(key,[]),spec.get(key,[])),'EXACT_BOUND_INPUT_LOCATORS_DIFFER:'+key)
    expected=[s.replace('__ROOT_STARTUP_PROOF__',request['startup_proof_path']) for s in spec['execution_argv']]
    need(request['execution_argv']==expected,'EXACT_BOUND_PRODUCER_ARGV_REQUIRED')
    need(all(p in request['source_references'] for p in [ref,spec['scope']['review'],*spec['source_references'],*result['parents']]),
         'BOUND_SPEC_REVIEW_AND_PARENT_PINS_REQUIRED')
    return result


def job_identity(request,raw,*,job_id,held=False):
    job=fields(raw) if isinstance(raw,str) else raw
    need(job.get('JobId')==str(job_id) and fmt._uid(job)==1278,'EXACT_OWN_JOB_ID_REQUIRED')
    need(job.get('JobName')==request['job_name'] and job.get('Partition')=='cpu' and
         job.get('NumCPUs')=='16' and job.get('NumTasks','1')=='1' and
         job.get('Requeue')=='0' and job.get('Command')==request['script_reference']['path'] and
         job.get('WorkDir')==PROJECT and fmt._wall(job.get('TimeLimit',''))==request['wall_seconds'],
         'ACTUAL_CPU_JOB_SCRIPT_OR_WALL_DIFFERS')
    if held:
        need(job.get('JobState')=='PENDING' and job.get('Reason')=='JobHeldUser' and job.get('Priority')=='0'
             and job.get('ReqNodeList')==request['node'] and job.get('NumNodes') in {'1','1-1'},'EXACT_OWN_HELD_JOB_REQUIRED')
    else:
        need(job.get('JobState')=='RUNNING' and fmt._nodes(job.get('NodeList'))=={request['node']}
             and job.get('NumNodes')=='1','ACTUAL_RUNNING_SINGLE_NODE_REQUIRED')
    return job


def free_cpu_observation(request,raw):
    node=fields(raw) if isinstance(raw,str) else raw
    need(node.get('NodeName')==request['node'] and 'cpu' in node.get('Partitions','').split(','),'ACTUAL_CPU_PARTITION_NODE_REQUIRED')
    total=int(node['CPUTot']);allocated=int(node['CPUAlloc'])
    need(0<=allocated<=total and total-allocated>=16,'WAIT_ACTUAL16_FREE_CPU_REQUIRED')
    return {'node':request['node'],'total_cpus':total,'allocated_cpus':allocated,'free_cpus':total-allocated,
            'memory_admission_evaluated':False,'raw':raw}


def validate_fresh_startup_proof(proof,request,*,now_unix,uid,boot_id,max_age_seconds=120):
    need(proof.get('schema')==PROOF_SCHEMA and proof.get('memory_policy')==MEMORY_POLICY and
         proof.get('memory_admission_evaluated') is False and proof.get('memory_limits_requested') is False,'OLD_MEMORY_PROOF_CANNOT_MASQUERADE_AS_NEW')
    need(same(proof.get('request'),request) and proof.get('uid')==uid==1278 and
         proof.get('boot_id')==boot_id,'ACTUAL_REQUEST_UID_BOOT_REQUIRED')
    need(0<max_age_seconds<=120,'NO_STARTUP_FRESHNESS_EXTENSION')
    obs=proof.get('memory_observation',{})
    need(obs.get('uid')==uid and obs.get('boot_id')==boot_id and obs.get('node')==request['node'],
         'ACTUAL_TARGET_OBSERVATION_IDENTITY_REQUIRED')
    epoch=obs.get('observed_unix_seconds')
    need(type(epoch) in (int,float) and 0<=now_unix-epoch<=max_age_seconds,'TARGET_PROOF_STALE_OR_FUTURE')
    job_identity(request,proof.get('job_metadata'),job_id=proof.get('job_id'))
    need(proof.get('source_references')==request['source_references'] and
         proof.get('script_reference')==request['script_reference'] and
         proof.get('queue_authority_reference')==request['queue_authority_reference'],'ACTUAL_SOURCE_SCRIPT_AUTHORITY_PROOF_BINDING')
    need(type(proof.get('existing_jobs_all_users')) is list,'ALL_USER_DECLARATIONS_MUST_BE_RECORDED')
    free=proof.get('account_free_bytes');need(type(free) is int and
         free-request['estimated_peak_output_bytes']>=200000000000,'WHOLE_OUTPUT_PLUS_200GB_QUOTA_REQUIRED')
    need(proof.get('execution_admission_granted') is True,'NEW_EXECUTION_ADMISSION_REQUIRED')
    return {'status':'FRESH_CPU_STARTUP_VERIFIED_MEMORY_ONLY_RECORDED','memory_policy':MEMORY_POLICY,
            'memory_admission_evaluated':False,'age_seconds':now_unix-epoch}

REGISTRY_DIR=RUN+'/control/cpu_auto_memory_registries'

def registry_path(path):
    value = fmt._literal_path(str(path))
    p = PurePosixPath(value)
    need(str(p.parent) == REGISTRY_DIR and re.fullmatch(r"[a-z0-9_]+\.json", p.name),
         "NEW_CANONICAL_AUTO_MEMORY_REGISTRY_REQUIRED")
    return value


def row_keys(row, request):
    jid = row.get("job_id")
    need(type(jid) is str and jid.isdecimal(), "REGISTERED_DECIMAL_JOB_ID_REQUIRED")
    ref = fmt._pin(row.get("request_reference"), small=True)
    proof = fmt._literal_path(request.get("startup_proof_path"))
    name = request.get("job_name")
    need(type(name) is str and re.fullmatch(r"dv1_q_[A-Za-z0-9_]+", name), "REGISTERED_JOB_NAME_REQUIRED")
    need(ref["path"] == RUN + "/control/requests/" + name + ".json"
         and proof == RUN + "/control/queue_startup/" + name + ".json",
         "REGISTERED_REQUEST_OR_PROOF_NAMESPACE_DIFFERS")
    return {"job_id": jid, "request_path": ref["path"], "proof_path": proof, "job_name": name}


def validate_disjoint(registries, *, load_request):
    """registries is [(literal registry path, object)]; old V1 rows are included."""
    seen = {key: {} for key in ("job_id", "request_path", "proof_path", "job_name")}
    paths = set()
    for path, registry in registries:
        path = fmt._literal_path(str(path))
        need(path not in paths, "DUPLICATE_REGISTRY_PATH"); paths.add(path)
        need(registry.get("schema") in {"REGISTERED_QUEUED_CPU_JOBS_V1",
             "REGISTERED_QUEUED_CPU_JOBS_V2", "REGISTERED_QUEUED_CPU_JOBS_V3", "REGISTERED_CPU_AUTO_MEMORY_JOBS_V1"} and type(registry.get("jobs")) is list
             and bool(registry["jobs"]), "EXACT_NONEMPTY_REGISTERED_JOB_SET")
        for row in registry["jobs"]:
            request = load_request(row["request_reference"])
            for key, value in row_keys(row, request).items():
                need(value not in seen[key], "REGISTRY_OVERLAP:" + key)
                seen[key][value] = path
    return seen



def validate_observer_identity(saved, current, *, expected_argv, registry_reference, source_reference):
    for key in ("pid", "uid", "boot_id", "start_ticks", "pgid", "sid", "argv_sha256", "argv",
                "cgroup_sha256", "cgroup"):
        need(saved.get(key) == current.get(key), "LIVE_OBSERVER_IDENTITY_CHANGED:" + key)
    need(saved.get("uid") == 1278 and saved.get("argv") == expected_argv
         and saved.get("pgid") == saved.get("pid") == saved.get("sid"),
         "EXACT_OWN_OBSERVER_ARGV_REQUIRED")
    need(saved.get("registry_reference") == registry_reference
         and saved.get("source_reference") == source_reference,
         "OBSERVER_SOURCE_OR_REGISTRY_BINDING_CHANGED")
    return True
