"""Source-only recovery proposal: immutable inputs, strict admission, no submission."""
from __future__ import annotations
import copy,csv,gzip,hashlib,io,json,math,os,re,socket,sys,time
from datetime import datetime
from pathlib import Path
PARENT=Path(__file__).parent.parent
sys.path.insert(0,str(PARENT))
import common as IO
MISSING={'principal_01112964':7,'principal_00509656':10}
OLD_SHA={
 'run_pilot.py':'f7733b23602d9883159bbedc2ea712fb3054e9e7963950c6fd6c10c1f582868f',
 'common.py':'ffa4fc9b6ce97be5b62af926c35337168b687f1f80a0fdd3564957dfe169b83b',
 'science.py':'2476767636d97b2a334dcf1f8b8e789e137a268acc6404ade61b7162690d211f',
 'selection.py':'41f21f5586c06f3c6fd7cfa9712623adc8091da996c72f6d71170dd4b716e2cb',
 'statistics_tools.py':'22422b92fde096a64c019683cf265514b99351b002fa8bc450f6eeaf932808ed',
 'live_memory_policy_32g_v1.py':'f91594e9fc111fbc732c505b4a329b0bb5d3d073d2d571e729feb5cc24a5ad7e',
 'run_pilot_live_memory_32g_v1.py':'c99c477f3a7fb304c01ce283ab18a284eb9ca30498a25708cb92994e4f298b88',
 'formal_v1/full_common.py':'7c4aac1f010898efaa6229216c3d0de34b208d8008bd319b4175b2dacb2619c7',
 'pilot_closure_v1/close_pilot.py':'e7c8992c06c305a53c3d706e0335b6a94db752d9053594c7bc0571f3e642907f',
}

def require(ok,message):
    if not ok:raise ValueError(message)

def canonical(value):
    return json.dumps(value,sort_keys=True,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode()

def task_sha(task):return hashlib.sha256(canonical(task)).hexdigest()

def expected_seed(task):
    prefix='sprime-ETKDGv3-v1-retry1:' if task['meta']['cohort']=='retry_once' else 'sprime-ETKDGv3-v1:'
    raw=hashlib.sha256((prefix+task['meta']['molecule_id']).encode()).digest()
    return max(int.from_bytes(raw[:4],'big')&0x7fffffff,1)

def scientific_sha(packet):
    value=copy.deepcopy(packet)
    require(set(value['summary'])>= {'elapsed_seconds'},'ORIGINAL_PACKET_TIMING_FIELD_REQUIRED')
    del value['summary']['elapsed_seconds']
    return hashlib.sha256(canonical(value)).hexdigest()

def small_load(pin):
    require(pin['bytes']<=2*1024**2,'SMALL_METADATA_LIMIT')
    return json.loads(IO.require_pin(pin).read_text())

def named(refs,name):
    rows=[r for r in refs if Path(r['path']).name==name]
    require(len(rows)==1,'UNIQUE_ORIGINAL_OUTPUT_REFERENCE_REQUIRED:'+name)
    return rows[0]

def load_plan(path,approved=False):
    value=json.loads(Path(path).read_text())
    require(value['schema']=='SPRIME_MISSING_RECOVERY_PLAN_V1','NEW_RECOVERY_PLAN_REQUIRED')
    require(value['original_job_id']=='4520364' and value['expected_original_molecules']==336,'ORIGINAL336_IDENTITY_REQUIRED')
    require(value['expected_missing_molecules']==MISSING and value['replay_control_count']==14,'EXACT_TWO_MISSING_AND14_CONTROLS_REQUIRED')
    require(value['workers']==16 and value['cpus']==16 and value['memory_gib']==64,'STRICT16CPU64G_RECOVERY_ONLY')
    require(value['new_logical_retry_count']==0 and value['scientific_recipe_changed'] is False,'NO_NEW_SEED_OR_LOGICAL_RETRY')
    require(value['formal_generation_authorized'] is False,'RECOVERY_IS_NOT_FORMAL_AUTHORITY')
    require(value['max_output_bytes']==8*1024**3 and value['closure_max_output_bytes']==1024**3 and
            value['quota_reserve_bytes']==200000000000,'FROZEN_FINITE_OUTPUT_AND_QUOTA_BUDGETS_REQUIRED')
    if approved:
        require(value.get('status')=='ROOT_APPROVED_RECOVERY_EXECUTION','RECOVERY_PLAN_NOT_AUTHORIZED')
        require(type(value.get('wall_seconds')) is int and 0<value['wall_seconds']<=48*3600,'REVIEWED_MAX48H_WALL_REQUIRED')
        require(type(value.get('additional_allocated_core_seconds_cap')) is int and
                value['additional_allocated_core_seconds_cap']>=value['wall_seconds']*16,'EXPLICIT_ALLOCATION_CEILING_REQUIRED')
        require(value.get('runtime_forecast')=='RIGHT_CENSORED_NO_DEFENSIBLE_POINT_ESTIMATE','NO_INVENTED_RUNTIME_FORECAST')
    return value

def controls_from_closed(closed):
    rows=[r for r in closed if r['summary']['status']=='SUCCESS' and r['detail']['new_real_accepted_count']>0]
    rows=sorted(rows,key=lambda r:r['molecule_id'])
    require(len(rows)>=14,'FOURTEEN_NONEMPTY_GENERATED_GEOMETRY_CONTROLS_REQUIRED')
    return [r['molecule_id'] for r in rows[:14]]

def bind_inputs(value):
    audit=small_load(value['partial_audit_report'])
    require(audit['schema']=='PARTIAL_SPRIME_PILOT_READONLY_AUDIT_V1' and
            audit['status']=='PARTIAL_PILOT_NOT_ACCEPTED_FOR_FORMAL','REAL_READONLY_PARTIAL_AUDIT_REQUIRED')
    require(audit['original_job_id']=='4520364' and audit['original_parent_state']=='TIMEOUT' and
            audit['complete_reusable_molecules']==334 and audit['missing_molecules']==2 and
            audit['invalid_molecules']==0 and audit['unexpected_entries']==0,'EXACT334_PLUS_TWO_AUDITED_INPUTS_REQUIRED')
    missing=small_load(named(audit['outputs'],'missing_tasks.json'))
    require({r['molecule_id']:r['expected_original_N'] for r in missing}==MISSING,'ACTUAL_MISSING_IDS_OR_N_CHANGED')
    closed=small_load(named(audit['outputs'],'complete_packages.json'))
    mids=[r['molecule_id'] for r in closed]
    require(len(mids)==334 and len(set(mids))==334 and not set(mids)&set(MISSING),'334_UNIQUE_REUSABLE_PACKAGES_REQUIRED')
    require(value['replay_control_ids']==controls_from_closed(closed),'FROZEN_DETERMINISTIC_CONTROL_SELECTION_DIFFERS')
    prepared=small_load(audit['prepared_reference'])
    require(prepared['molecules']==336 and prepared['config']==audit['original_pilot_config_reference'],'ORIGINAL_PREPARED_BINDING_REQUIRED')
    require(value['recipe_config']==audit['original_pilot_config_reference'],'RECIPE_CONFIG_CHANGED')
    pin=named(prepared['outputs'],'tasks.jsonl')
    require(pin==audit['tasks_reference'] and pin==value['tasks_reference'],'ORIGINAL_TASK_BODY_PIN_CHANGED')
    IO.require_pin(pin) # whole tasks body is opened only after an actual CPU admission
    raw_tasks=Path(pin['path']).read_bytes()
    require(len(raw_tasks)==pin['bytes'] and hashlib.sha256(raw_tasks).hexdigest()==pin['sha256'],'ORIGINAL_TASK_BYTES_CHANGED')
    expected_names={Path(row['reference']['path']).name for row in closed}
    folder=Path(audit['pilot_output_directory'])/'reproduction'
    require({entry.name for entry in folder.iterdir()}==expected_names,'ORIGINAL334_SOURCE_DIRECTORY_CHANGED')
    for row in closed:
        st=Path(row['reference']['path']).stat()
        now={'device':st.st_dev,'inode':st.st_ino,'bytes':st.st_size,'mtime_ns':st.st_mtime_ns,'uid':st.st_uid}
        require(now==row['file_identity'],'ORIGINAL334_SOURCE_IDENTITY_CHANGED')
    tasks={}
    for raw in raw_tasks.splitlines():
        task=json.loads(raw);mid=task['meta']['molecule_id']
        require(mid not in tasks,'DUPLICATE_ORIGINAL_TASK')
        tasks[mid]=task
    require(set(tasks)==set(mids)|set(MISSING),'ORIGINAL336_TASK_SET_CHANGED')
    for mid,n in MISSING.items():
        require(tasks[mid]['meta']['cohort']=='retry_once' and tasks[mid]['meta']['expected_conformers']==n,'ORIGINAL_MISSING_TASK_CHANGED')
    return audit,closed,tasks

def require_sources(pins):
    for name,sha in OLD_SHA.items():
        actual=IO.reference(PARENT/name)
        require(actual['sha256']==sha and actual in pins,'FROZEN_SCIENTIFIC_SOURCE_NOT_PINNED:'+name)
    for path in Path(__file__).parent.glob('*.py'):
        require(IO.reference(path) in pins,'ACTUAL_RECOVERY_SOURCE_NOT_PINNED:'+path.name)
    for pin in pins:IO.require_pin(pin)

def generation_admit(plan_path,value,intent_path,approval_path):
    """Strict original64G/all-user declaration admission, no small-test policy."""
    runtime=IO.runtime_guard(16)
    require(runtime['allocated_cpus']==16 and os.getuid()==1278,'EXACT16CPU_REAL_OWNER_REQUIRED')
    require(os.environ.get('SLURM_JOB_PARTITION')=='cpu' and os.environ.get('CUDA_VISIBLE_DEVICES')=='','CPU_ONLY_ALLOCATION_REQUIRED')
    require(int(os.environ.get('SLURM_MEM_PER_NODE','0'))>=64*1024,'ACTUAL64G_ALLOCATION_REQUIRED')
    for env in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
        require(os.environ.get(env)=='1','ONE_THREAD_PER_WORKER_REQUIRED')
    proof=json.loads(Path(intent_path).read_text());request=proof['request']
    require(request.get('kind')=='conformer' and request.get('pilot') is True,'NEW_GENERATION_PILOT_REQUEST_REQUIRED')
    require(request.get('resource_policy') is None and not request.get('memory_basis'),'NO_CPU_ANALYSIS_OR_OLD_LIVE_MEMORY_AUTHORITY')
    require(request['memory_gib']==64 and request['cpus']==16 and request['wall_seconds']==value['wall_seconds'],'EXACT_NEW_REVIEWED_RESOURCES_REQUIRED')
    require(proof['uid']==1278 and request['node']==runtime['hostname'],'ROOT_OWNER_AND_NODE_REQUIRED')
    require(request.get('root_review',{}).get('status')=='APPROVED','NEW_ROOT_REVIEW_REQUIRED')
    require(IO.reference(plan_path) in request['source_references'] and IO.reference(approval_path) in request['source_references'],'NEW_PLAN_AND_APPROVAL_PINS_REQUIRED')
    approval=json.loads(Path(approval_path).read_text())
    require(approval.get('schema')=='SPRIME_MISSING_RECOVERY_USER_AND_ROOT_DECISION_V1' and
            approval.get('status')=='APPROVED_FOR_THIS_RECOVERY_ONLY','NEW_INDEPENDENT_RECOVERY_DECISION_REQUIRED')
    require(approval.get('plan_reference')==IO.reference(plan_path) and
            approval.get('cost_ceiling_not_forecast')==value['additional_allocated_core_seconds_cap'],'EXACT_NEW_PLAN_AND_COST_SCOPE_REQUIRED')
    require(isinstance(approval.get('user_budget_and_resource_reply'),str) and
            bool(approval['user_budget_and_resource_reply'].strip()),'NEW_BUDGET_RESOURCE_DECISION_TEXT_REQUIRED')
    require(approval.get('original_336_approval_reused') is False,'ORIGINAL_SINGLE_PILOT_APPROVAL_CANNOT_AUTHORIZE_RECOVERY')
    for job in proof['existing_jobs_all_users']:
        raw=job['metadata']
        matches=re.findall(r'(?:^|\s)MinMemory(?:Node|CPU)=([^\s]+)',raw)
        require(len(matches)==1 and not re.fullmatch(r'0[KMGTP]?',matches[0]),'UNBOUNDED_OTHER_JOB_DECLARATION_BLOCKS_RECOVERY')
    require(value['recipe_config'] in request['source_references'],'ORIGINAL_RECIPE_CONFIG_PIN_REQUIRED')
    IO.require_pin(value['recipe_config'])
    IO.require_preflight(intent_path,plan_path,value)
    require_sources(request['source_references'])
    return runtime,proof

def packet_reader():
    import importlib.util
    path=PARENT/'pilot_closure_v1/close_pilot.py'
    require(IO.digest(path)=='e7c8992c06c305a53c3d706e0335b6a94db752d9053594c7bc0571f3e642907f','OLD_PACKAGE_VALIDATOR_CHANGED')
    spec=importlib.util.spec_from_file_location('_recovery_old_package_validator',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

def read_packet(ref,task,validator):
    path=Path(ref['path']);before=path.stat()
    summary,detail,rows=validator.read_package((ref,task,1024**3))
    with gzip.open(path,'rb') as stream:raw=stream.read(1024**3+1)
    require(len(raw)<=1024**3,'PACKET_UNCOMPRESSED_CAP')
    packet=json.loads(raw);after=path.stat()
    require((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)==
            (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns),'PACKAGE_CHANGED_DURING_READ')
    return packet,detail

def terminal_parents(text):
    reader=csv.DictReader(io.StringIO(text),delimiter='|')
    require(reader.fieldnames and {'State','ExitCode','ElapsedRaw','AllocCPUS'}<=set(reader.fieldnames),'RAW_PARENT_ACCOUNTING_HEADER_REQUIRED')
    key='JobIDRaw' if 'JobIDRaw' in reader.fieldnames else 'JobID';rows={}
    for row in reader:
        jid=row.get(key,'')
        if not jid.isdecimal():continue
        require(jid not in rows and row['State'].split()[0] in
                {'COMPLETED','FAILED','TIMEOUT','CANCELLED','OUT_OF_MEMORY','NODE_FAIL'},'UNIQUE_TERMINAL_PARENT_ROWS_REQUIRED')
        seconds,cpus=int(row['ElapsedRaw']),int(row['AllocCPUS'])
        require(seconds>=0 and cpus>=0,'NONNEGATIVE_ACTUAL_ACCOUNTING_REQUIRED')
        rows[jid]={'job_id':jid,'state':row['State'].split()[0],'exit_code':row['ExitCode'],
                   'elapsed_raw_seconds':seconds,'alloc_cpus':cpus,'allocated_core_seconds':seconds*cpus}
    return rows