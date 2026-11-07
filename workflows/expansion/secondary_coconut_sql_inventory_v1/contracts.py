"""Independent Alpha readonly main, complete argv and actual producer authority."""
import csv,hashlib,io,json,os,re,socket,stat,sys,time
from pathlib import Path

ROOT=Path('/gfshome/alpha/codex_data_v1_20261026');UID=1264;ENDPOINT='218.192.171.238:22'
KEY='coconut_sql_format_schema_probe_v1';MODULE='secondary_coconut_sql_inventory_v1.probe'
NODES={'compute-0-1','compute-0-3','compute-0-4','compute-0-5','compute-0-6','sonmi1'}
SMALL=2*1024**2;SQL_BYTES=37876914074

def need(ok,code):
    if not ok:raise ValueError(code)

def literal(path):
    path=Path(path);need(path.is_absolute() and '..' not in path.parts and ROOT in path.parents and
        not any(p.is_symlink() for p in (path,*path.parents)),'OWNED_LITERAL_ALPHA_PATH_REQUIRED');return path

def read_small(path):
    path=literal(path)
    with path.open('rb') as stream:
        a=os.fstat(stream.fileno());need(stat.S_ISREG(a.st_mode) and a.st_uid==UID and a.st_size<=SMALL,'SMALL_ALPHA_METADATA_REQUIRED')
        raw=stream.read(SMALL+1);b=os.fstat(stream.fileno())
    need(len(raw)==a.st_size and frame(a)==frame(b),'SMALL_ALPHA_METADATA_CHANGED');return raw

def pin(path):
    raw=read_small(path);return {'path':str(path),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}

def load(path):return json.loads(read_small(path))
def verify_pin(ref):need(pin(ref['path'])==ref,'ACTUAL_SMALL_ALPHA_PIN_CHANGED');return Path(ref['path'])
def verify(ref):return load(verify_pin(ref))
def frame(st):return {k:getattr(st,'st_'+v) for k,v in (('device','dev'),('inode','ino'),('size','size'),('mtime_ns','mtime_ns'),('uid','uid'))}

def write_new(path,obj):
    raw=(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode();need(len(raw)<=SMALL,'SMALL_PROBE_OUTPUT_REQUIRED')
    path=literal(path)
    with path.open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
    return pin(path)

def fields(raw):
    matches=list(re.finditer(r'(?<!\S)([A-Za-z][A-Za-z0-9_./+:-]*)=',raw));out={}
    need(matches and not raw[:matches[0].start()].strip(),'ACTUAL_SCONTROL_FIELDS_REQUIRED')
    for i,m in enumerate(matches):
        need(m[1] not in out,'DUPLICATE_SCONTROL_FIELD');out[m[1]]=raw[m.end():matches[i+1].start() if i+1<len(matches) else len(raw)].strip()
    return out

def wall(value):
    m=re.fullmatch(r'(?:(\d+)-)?(\d+):([0-5]\d):([0-5]\d)',value);need(m is not None,'FINITE_SLURM_CLOCK_REQUIRED')
    return int(m[1] or 0)*86400+int(m[2])*3600+int(m[3])*60+int(m[4])

def startup(plan_path,proof_path,main_source):
    plan=load(plan_path);review=verify(plan['root_review_reference']);proof=load(proof_path)
    primary=ROOT/'code/secondary_coconut_sql_inventory_v1/probe.py'
    argv=[plan['python'],'-B','-m',MODULE,'--plan',str(plan_path),'--startup-proof',str(proof_path)]
    need(Path(main_source).absolute()==primary==Path(sys.modules['__main__'].__file__).absolute() and
        Path(sys.executable).absolute()==Path(plan['python']).absolute() and sys.argv==[str(primary),*argv[4:]],
        'REAL_PRIMARY_AND_COMPLETE_OPTIONS_REQUIRED_NO_WRAPPER_MAIN')
    need(plan.get('schema')=='SECONDARY_COCONUT_SQL_FORMAT_PROBE_PLAN_V1' and plan.get('producer_key')==plan.get('scope_key')==KEY and
        plan.get('stage')=='SQL_FORMAT_SCHEMA_PROBE' and plan.get('endpoint')==ENDPOINT and plan.get('uid')==UID and
        plan.get('run_root')==str(ROOT) and plan.get('node') in NODES and plan.get('cpus')==16 and plan.get('pilot') is False and
        plan.get('memory_policy')=='SLURM_DEFAULT_UNSPECIFIED' and plan.get('wall_seconds')==600 and
        0<plan.get('output_cap_bytes',0)<=64*1024**2 and plan['execution_argv']==argv and
        plan['startup_proof_path']==str(proof_path),'EXACT_BOUNDED_SQL_FORMAT_PLAN_REQUIRED')
    need(review.get('schema')=='EXACT_SECONDARY_BOUNDED_READONLY_ROOT_REVIEW_V1' and
        review.get('status')=='APPROVED_FOR_EXACT_STAGE' and review.get('reviewer')=='root','EXACT_READONLY_ROOT_REVIEW_REQUIRED')
    for key in ('scope_key','scope_parameters','stage','endpoint','uid','run_root','node','cpus','memory_policy','pilot',
                'wall_seconds','output_cap_bytes','execution_argv','data_references','parent_evidence_references'):
        need(plan[key]==review[key],'EXACT_ROOT_PROBE_FIELD_DIFFERS:'+key)
    need(plan['source_references']==review['approved_source_references'],'REVIEWED_SMALL_SOURCE_SET_REQUIRED')
    need(proof.get('schema')=='SECONDARY_COCONUT_SQL_READONLY_STARTUP_V1' and proof.get('endpoint')==ENDPOINT and
        proof.get('uid')==os.getuid()==UID and proof['node']==plan['node']==socket.gethostname().split('.')[0] and
        proof['boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'ACTUAL_ALPHA_UID_NODE_BOOT_REQUIRED')
    env=os.environ
    need(env.get('SLURM_JOB_ID')==str(proof['job_id']) and env.get('SLURM_JOB_PARTITION')=='cpu' and env.get('SLURM_CPUS_PER_TASK')=='16' and
        env.get('CUDA_VISIBLE_DEVICES')=='' and all(env.get(k)=='1' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')),
        'ACTUAL_CPU16_NO_GPU_AND_ONE_LIBRARY_THREAD_REQUIRED')
    need(0<=time.time()-proof['observed_unix_seconds']<=120 and proof['plan_reference']==pin(plan_path) and
        proof['root_review_reference']==plan['root_review_reference'],'FRESH_INDEPENDENT_EXACT_PLAN_PROOF_REQUIRED')
    request=proof['request']
    need(request=={'kind':'analysis','pilot':False,'cpus':16,'memory_policy':'SLURM_DEFAULT_UNSPECIFIED',
        'wall_seconds':600,'execution_argv':argv} and proof['memory_limits_requested'] is False and
        proof['exclusive_requested'] is False and proof.get('bounded_readonly_scope_only') is True,'NO_MEMORY_EXCLUSIVE_OR_SCIENCE_SCOPE')
    declared={r['path']:r for r in proof['source_target_verification']}
    for ref in [*plan['source_references'],*plan['parent_evidence_references'],plan['root_review_reference'],pin(plan_path)]:
        need(declared.get(ref['path'])==ref,'PROOF_SOURCE_PIN_NOT_BOUND');verify_pin(ref)
    for path in (primary,primary.parent/'contracts.py',primary.parent/'__init__.py'):
        need(pin(path) in plan['source_references'],'ALL_ACTUAL_PROBE_SOURCES_MUST_BE_REVIEWED')
    need(Path(__file__).absolute()==primary.parent/'contracts.py','ACTUAL_IMPORTED_CONTRACT_SOURCE_PATH_REQUIRED')
    origin=proof['controller_evidence']
    need(origin['endpoint']==ENDPOINT and origin['uid']==UID and origin['hostname']=='sonmi' and
        origin['proof_is_not_created_by_scientific_worker'] is True and origin['actual_script_reference']==proof['script_reference'],
        'INDEPENDENT_ALPHA_LOGIN_SIGNER_REQUIRED')
    script=verify_text(proof['script_reference'])
    for line in script.splitlines():
        if line.strip().startswith('#SBATCH'):
            need(not any(s in line for s in ('--mem','--gres','--gpu','--exclusive')),'NO_REQUESTED_MEMORY_GPU_OR_EXCLUSIVITY')
    job=fields(proof['job_metadata'])
    need(job.get('JobId')==str(proof['job_id']) and job.get('UserId')=='alpha(1264)' and job.get('JobState')=='RUNNING' and
        job.get('NodeList')==plan['node'] and job.get('Partition')=='cpu' and job.get('NumCPUs')=='16' and job.get('NumTasks')=='1' and
        job.get('Requeue')=='0' and job.get('Command')==proof['script_reference']['path'] and wall(job.get('TimeLimit',''))==600,
        'ACTUAL_OWN_RUNNING_SCRIPT_CPU_WALL_REQUIRED')
    gate=proof['actual_gate_process'];proc=Path('/proc/self');raw=(proc/'stat').read_text();tail=raw[raw.rfind(')')+2:].split()
    need(gate['pid']==os.getpid() and gate['uid']==UID and gate['start_ticks']==int(tail[19]) and gate['pgid']==os.getpgrp() and
        gate['sid']==os.getsid(0) and gate['cgroup_sha256']==hashlib.sha256((proc/'cgroup').read_bytes()).hexdigest(),
        'EXEC_MUST_PRESERVE_ACTUAL_ATTESTED_GATE_PROCESS_IDENTITY')
    storage=proof['storage_observation'];verify(proof['storage_observation_reference'])
    need(proof['account_free_bytes']==storage['effective_free_bytes'] and
        proof['account_free_bytes']-plan['output_cap_bytes']>=200000000000 and 0<=time.time()-storage['observed_unix_seconds']<=120 and
        storage['whole_output_caps_reserved_bytes']>=plan['output_cap_bytes'],'FRESH_STORAGE_ALL_CAPS_AND200GB_REQUIRED')
    authority=verify(plan['resource_authority_reference'])
    need(authority.get('schema')=='USER_AUTHORIZED_SECONDARY_DATA_CLUSTER_V1' and authority.get('status')=='USER_AUTHORIZED' and
        authority.get('endpoint')==ENDPOINT and authority.get('observed_uid')==UID and authority.get('memory_policy')=='SLURM_DEFAULT_UNSPECIFIED',
        'ACTUAL_ALPHA_USER_AUTHORITY_REQUIRED')
    return plan,proof

def verify_text(ref):
    need(pin(ref['path'])==ref,'ACTUAL_SCRIPT_PIN_CHANGED');return read_small(ref['path']).decode()

def producer(plan):
    receipt_ref=plan['sql_producer_receipt_reference'];cost_ref=plan['sql_producer_cost_reference']
    need(receipt_ref in plan['parent_evidence_references'] and cost_ref in plan['parent_evidence_references'],'ACTUAL_SQL_PARENTS_REQUIRED')
    receipt,cost=verify(receipt_ref),verify(cost_ref)
    need(receipt['schema']=='SECONDARY_COCONUT_ACQUISITION_RECEIPT_V1' and receipt['job_id']=='1884765' and receipt['endpoint']==ENDPOINT and
        receipt['uid']==UID and receipt['stage']=='PLAIN_SQL_FULL_DOWNLOAD' and
        receipt['status']=='ACTUAL_PLAIN_SQL_DOWNLOAD_COMPLETE_NOT_LOGICAL_COVERAGE' and receipt['payload_download_complete'] is True and
        receipt['error'] is None and receipt['inactive_coverage_proven'] is False,'ACTUAL_COMPLETE_PLAIN_SQL_PRODUCER_REQUIRED')
    payload=receipt['payload_reference']
    need(plan['data_references']==[payload] and set(payload)=={'path','bytes','sha256'} and type(payload['bytes']) is int and
        payload['bytes']==SQL_BYTES and re.fullmatch('[0-9a-f]{64}',payload['sha256']) and
        ROOT/'artifacts/source_acquisition' in literal(payload['path']).parents,'EXACT_COMPLETE_SQL_LOCATOR_REQUIRED')
    parent=cost['actual_parent']
    need(cost['schema']=='SECONDARY_COCONUT_ACTUAL_PARENT_COST_V1' and cost['status']=='SECONDARY_ACTUAL_TERMINAL_PARENT_ACCOUNTED' and
        cost['endpoint']==ENDPOINT and cost['uid']==UID and cost['receipt']==receipt_ref and parent['JobIDRaw']=='1884765' and
        parent['State']=='COMPLETED' and parent['ExitCode']=='0:0' and parent['UID']==str(UID) and parent['NodeList']==receipt['node'] and
        parent['Partition']=='cpu' and parent['AllocCPUS']=='16' and cost['allocated_core_seconds']==int(parent['ElapsedRaw'])*16,
        'ACTUAL_SQL_TERMINAL_C0_COST_REQUIRED_NOT_CSV_SUCCESS_FLAG')
    evidence=verify(cost['accounting_evidence']);need(evidence['query_returncode']==0,'ACTUAL_SQL_ACCOUNT_QUERY_REQUIRED')
    raw_ref=cost['raw_sacct_reference'];need(raw_ref==evidence['raw_sacct_reference'],'SQL_RAW_ACCOUNT_PIN_DIFFERS')
    rows=list(csv.DictReader(io.StringIO(verify_text(raw_ref)),delimiter='|'));actual=[r for r in rows if r.get('JobIDRaw')=='1884765']
    need(len(actual)==1 and all(actual[0][k]==parent[k] for k in ('State','ExitCode','UID','ElapsedRaw','AllocCPUS','NodeList','Partition')),
        'ACTUAL_SQL_PARENT_RAW_ACCOUNTING_DIFFERS')
    transfer=verify(receipt['transfer']);need(transfer['payload_download_complete'] is True and transfer['payload_reference']==payload,
        'ACTUAL_PRODUCER_FULL_GET_AND_SHA_REQUIRED')
    marker=verify(receipt['structural_profile']);need(marker['schema']=='SECONDARY_PLAIN_SQL_PAYLOAD_MARKER_PROFILE_V1' and
        0<marker['read_prefix_bytes']<=65536 and marker['prefix_plaintext_persisted'] is False and
        marker['logical_database_rows_or_active_inactive_coverage_established'] is False,'ACTUAL_PRODUCER_PREFIX_PROFILE_REQUIRED')
    return payload,{'receipt':receipt_ref,'cost':cost_ref,'actual_parent':parent,'producer_prefix_profile':receipt['structural_profile'],
        'producer_full_payload_SHA256':payload['sha256'],'source_CRC':'NOT_APPLICABLE_PLAIN_SQL_NOT_AN_ARCHIVE'}
