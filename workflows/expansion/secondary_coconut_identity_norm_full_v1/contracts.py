"""Independent full-scope proof; reuse the actual1884785 profile's exact kernel."""
import csv,hashlib,io,os,socket,sys,time
from pathlib import Path
from secondary_cpu_queue_v1 import common as q

ROOT=q.ROOT;UID=1264;KEY='coconut_identity_norm_full_alpha_v1';MODULE='secondary_coconut_identity_norm_full_v1.run'
STAGE='IDENTITY_KEY_NORMALIZATION_FULL';COUNTS={'molecules':1140133,'entries':1799004};TOTAL=2939137
ENV={'python':'3.11.14','numpy':'2.2.6','RDKit':'2025.09.5','pyarrow':'17.0.0'}
PROFILE={
 '__init__.py':(84,'efd575f612865eb944b512c5910fe669eb5c08762d3117962c3b7384d7414376'),
 'contracts.py':(13615,'bc569267b5854959231f290f02848bb40ed0908d82b46ab4b18ce15917f1a827'),
 'runtime.py':(4377,'29d3ec8464e8bde5d66a718d6a8bb37ae78feaad8dfca063115f863af011848f'),
 'run.py':(20852,'62397760fc59718e965eb44c02b5e4bf7be81d2ca54ab3428aff551f8c2fe9a2')}
need=q.need;pin=q.ref;load=q.load;literal=q.literal

def parameters():
    return {'mode':'full','input_tables':['molecules','entries'],'expected_physical_rows_by_table':dict(COUNTS),
      'expected_physical_rows':TOTAL,'record_selection':'ALL_PARQUET_PHYSICAL_ROWS_ORIGINAL_ORDER','workers':16,'maximum_pending':32,
      'actual_profile_job_id':'1884785','environment':dict(ENV),'same_profile_function_objects':True,'same_three_profile_fixtures':True,
      'present_SMILES_variants_separately':True,'stored_full_keys_strict':False,'status_invalid_or_identity_filter':False,
      'raw_identity_rows_retained':True,'X_rules_or_features_called':False,'maximum_input_JSON_bytes_per_record':2*1024**2,
      'maximum_result_JSON_bytes_per_record':8*1024**2,'maximum_source_rowgroup_uncompressed_bytes':256*1024**2,
      'journal_part_maximum_rows':65536,'journal_part_maximum_bytes':256*1024**2,'Parquet_buffer_maximum_rows':16,
      'full_source_normalization_authorized':True,'global_identity_acceptance_or_pool_release':False,
      'algorithm_current_RSS_reference_bytes':48*1024**3,'runtime_MemAvailable_min_fraction':.15,'cost_overrun_action':'REPORT_AND_CONTINUE'}

def frame(s):return {'device':s.st_dev,'inode':s.st_ino,'size':s.st_size,'mtime_ns':s.st_mtime_ns,'uid':s.st_uid}

def write_new(path,value):
    import json
    raw=(json.dumps(value,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n').encode();need(len(raw)<=2*1024**2,'SMALL_METADATA_REQUIRED')
    with Path(path).open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())

def account(ref,job,node,parents):
    value=q.load_ref(ref);p=value['actual_parent'];raw_ref=value['raw_sacct_reference']
    need(ref in parents and raw_ref in parents and value['query_returncode']==0 and value['endpoint']==q.ENDPOINT and value['uid']==UID and
      p['JobIDRaw']==job and p['State']=='COMPLETED' and p['ExitCode']=='0:0' and p['UID']==str(UID) and p['AllocCPUS']=='16' and
      p['NodeList']==node and p['Partition']=='cpu','ACTUAL_C0_PARENT_ACCOUNT_REQUIRED')
    rows=list(csv.DictReader(io.StringIO(q.read_small(q.verify(raw_ref)).decode()),delimiter='|'));matching=[r for r in rows if r.get('JobIDRaw')==job]
    need(len(matching)==1 and all(matching[0][k]==p[k] for k in ('State','ExitCode','UID','ElapsedRaw','AllocCPUS','NodeList','Partition')) and
      value['allocated_core_seconds_observed']==16*int(p['ElapsedRaw']),'ACTUAL_RAW_SACCT_AND_ALLOCATION_COST_REQUIRED')
    return value

def startup(plan_path,proof_path,primary):
    plan=load(plan_path);proof=load(proof_path);review=q.load_ref(plan['root_review_reference']);wall=plan['wall_seconds'];cap=32*1024**3
    source=ROOT/'code/secondary_coconut_identity_norm_full_v1/run.py';argv=[plan['python'],'-B','-m',MODULE,'--plan',str(plan_path),'--startup-proof',str(proof_path)]
    need(plan.get('schema')=='SECONDARY_COCONUT_IDENTITY_NORM_FULL_PLAN_V1' and plan.get('producer_key')==plan.get('scope_key')==KEY and
      plan.get('stage')==STAGE and plan.get('mode')=='full' and plan.get('pilot') is False and plan.get('scope_parameters')==parameters() and
      plan.get('endpoint')==q.ENDPOINT and plan.get('uid')==UID and plan.get('run_root')==str(ROOT) and plan.get('node') in q.NODES and plan.get('cpus')==16 and
      plan.get('memory_policy')=='SLURM_DEFAULT_UNSPECIFIED' and type(wall) is int and 0<wall<=172800 and wall%60==0 and plan.get('output_cap_bytes')==cap,
      'EXACT_INDEPENDENT_FULL_PHYSICAL_SCOPE_REQUIRED')
    need(Path(primary).absolute()==source==Path(sys.modules['__main__'].__file__).absolute() and Path(sys.executable).absolute()==Path(plan['python']).absolute() and
      sys.argv==[str(source),*argv[4:]] and plan['execution_argv']==argv and plan['startup_proof_path']==str(proof_path),'ACTUAL_FULL_PRIMARY_AND_ALL_ARGV')
    need(review.get('schema')=='EXACT_SECONDARY_BOUNDED_READONLY_ROOT_REVIEW_V1' and review.get('status')=='APPROVED_FOR_EXACT_STAGE' and review.get('reviewer')=='root',
      'EXACT_ROOT_FULL_STAGE_REVIEW')
    for key in ('scope_key','scope_parameters','stage','endpoint','uid','run_root','node','cpus','memory_policy','pilot','wall_seconds','output_cap_bytes',
      'execution_argv','data_references','parent_evidence_references'):need(plan[key]==review[key],'ROOT_FULL_FIELD_DIFFERS:'+key)
    need(plan['source_references']==review['approved_source_references'] and review.get('actual_profile_cost_and_quality_reviewed') is True and
      review.get('all_physical_rows_including_no_key_authorized') is True,'EXACT_APPROVED_FULL_SOURCES_AND_QUALITY_REVIEW')
    need(proof.get('schema')=='SECONDARY_COCONUT_IDENTITY_NORM_FULL_STARTUP_V1' and proof.get('endpoint')==q.ENDPOINT and proof.get('uid')==os.getuid()==UID and
      proof['node']==plan['node']==socket.gethostname().split('.')[0] and proof['boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip() and
      0<=time.time()-proof['observed_unix_seconds']<=120 and proof['plan_reference']==pin(plan_path) and proof['root_review_reference']==plan['root_review_reference'],
      'ACTUAL_FRESH_ALPHA_FULL_PROOF')
    need(proof['request']=={'kind':'analysis','pilot':False,'cpus':16,'memory_policy':'SLURM_DEFAULT_UNSPECIFIED','wall_seconds':wall,'execution_argv':argv} and
      proof['memory_limits_requested'] is False and proof['exclusive_requested'] is False and proof.get('bounded_readonly_scope_only') is True and
      proof.get('bounded_source_acquisition_scope_only',False) is False,'FULL_DEFAULT_MEMORY_READONLY_NOT_ACQUISITION_REQUEST')
    env=os.environ;need(env.get('SLURM_JOB_ID')==str(proof['job_id']) and env.get('SLURM_JOB_PARTITION')=='cpu' and env.get('SLURM_CPUS_PER_TASK')=='16' and
      env.get('CUDA_VISIBLE_DEVICES')=='' and all(env.get(k)=='1' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')),'REAL_CPU16_LIBRARY_THREADS')
    declared={r['path']:{k:r[k] for k in ('path','bytes','sha256')} for r in proof['source_target_verification']}
    for ref in [*plan['source_references'],*plan['parent_evidence_references'],plan['root_review_reference'],pin(plan_path)]:
        need(declared.get(ref['path'])==ref,'ACTUAL_FULL_SOURCE_NOT_BOUND');q.verify(ref)
    for path in [*source.parent.glob('*.py'),Path(q.__file__),Path(q.__file__).parent/'__init__.py']:need(pin(path) in plan['source_references'],'ACTUAL_NEW_FULL_AND_BASE_CODE_REQUIRED')
    signer=proof['controller_evidence'];need(signer['endpoint']==q.ENDPOINT and signer['uid']==UID and signer['hostname']=='sonmi' and signer['proof_is_not_created_by_scientific_worker'] is True and
      signer['actual_script_reference']==proof['script_reference'],'REAL_LOGIN_CONTROLLER_SIGNER')
    for line in q.read_small(q.verify(proof['script_reference'])).decode().splitlines():
        if line.strip().startswith('#SBATCH'):need(not any(x in line for x in ('--mem','--exclusive','--gres','--gpu')),'NO_MEMORY_EXCLUSIVE_GPU')
    job=q.fields(proof['job_metadata']);need(job.get('JobId')==str(proof['job_id']) and job.get('UserId')=='alpha(1264)' and job.get('JobState')=='RUNNING' and
      job.get('NodeList')==plan['node'] and job.get('Partition')=='cpu' and job.get('NumCPUs')=='16' and job.get('NumTasks')=='1' and job.get('Requeue')=='0' and
      job.get('Command')==proof['script_reference']['path'] and q.duration(job.get('TimeLimit',''))==wall,'ACTUAL_FULL_JOB_SCRIPT_WALL')
    gate=proof['actual_gate_process'];tail=Path('/proc/self/stat').read_text().rsplit(')',1)[1].split();need(gate['pid']==os.getpid() and gate['uid']==UID and
      gate['start_ticks']==int(tail[19]) and gate['pgid']==os.getpgrp() and gate['sid']==os.getsid(0) and gate['cgroup_sha256']==hashlib.sha256(Path('/proc/self/cgroup').read_bytes()).hexdigest(),
      'SAME_ACTUAL_EXEC_GATE_IDENTITY')
    storage=proof['storage_observation'];q.load_ref(proof['storage_observation_reference']);need(proof['account_free_bytes']==storage['effective_free_bytes'] and
      proof['account_free_bytes']-cap>=200000000000 and storage['whole_output_caps_reserved_bytes']>=cap and 0<=time.time()-storage['observed_unix_seconds']<=120,'FRESH_ALL_CAPS200GB_STORAGE')
    for key in ('resource_authority_reference','cost_decision_reference'):need(plan[key] in plan['source_references'],'ACTUAL_APPROVED_AUTHORITY')
    authority=q.load_ref(plan['resource_authority_reference']);need(authority.get('schema')=='USER_AUTHORIZED_SECONDARY_DATA_CLUSTER_V1' and authority.get('status')=='USER_AUTHORIZED' and
      authority.get('endpoint')==q.ENDPOINT and authority.get('observed_uid')==UID and authority.get('memory_policy')=='SLURM_DEFAULT_UNSPECIFIED','REAL_ALPHA_AUTHORITY')
    cost=q.load_ref(plan['cost_decision_reference']);need(cost.get('schema')=='USER_AUTHORIZED_ALLOCATION_OVERRUN_REPORT_CONTINUE_V1' and cost.get('status')=='USER_AUTHORIZED' and
      cost.get('on_overrun')=='REPORT_AND_CONTINUE' and cost.get('scientific_quality_thresholds_unchanged') is True,'REAL_COST_CONTINUE_QUALITY_UNCHANGED')
    parents=plan['parent_evidence_references']
    for key in ('accepted_profile_receipt_reference','accepted_profile_accounting_reference','profile_plan_reference','profile_startup_proof_reference',
      'a_full_receipt_reference','a_full_accounting_reference','a_full_plan_reference','a_full_startup_proof_reference'):
        need(plan[key] in parents,'EXACT_HISTORICAL_PARENT_REQUIRED:'+key)
    prior=q.load_ref(plan['accepted_profile_receipt_reference']);old_plan=q.load_ref(plan['profile_plan_reference']);old_proof=q.load_ref(plan['profile_startup_proof_reference'])
    need(prior['schema']=='SECONDARY_COCONUT_IDENTITY_NORM_PROFILE_RECEIPT_V1' and prior['status']=='SAMPLED_FROZEN_IDENTITY_KEY_OBSERVATIONS_COMPLETE' and prior['mode']=='profile' and
      prior['job_id']=='1884785' and prior['uid']==UID and prior['endpoint']==q.ENDPOINT and prior['node']=='compute-0-1' and
      prior['plan']==plan['profile_plan_reference'] and prior['startup_proof']==plan['profile_startup_proof_reference'] and
      prior['observed_rows_by_table']=={'molecules':10000,'entries':10000} and prior['observed_rows']==20000 and
      len(prior['actual_nonempty_workers'])==16 and sum(prior['actual_nonempty_workers'].values())==20000 and all(x>0 for x in prior['actual_nonempty_workers'].values()) and
      prior['fixtures']=={'tests_run':3,'failures':0,'errors':0,'skips':0,'before_A_body_IO':True} and prior['actual_environment']['actual_versions']==ENV,'ACTUAL_CLOSED_PROFILE1884785_REQUIRED')
    need(old_plan['schema']=='SECONDARY_COCONUT_IDENTITY_NORM_PROFILE_PLAN_V1' and old_plan['producer_key']==old_plan['scope_key']=='coconut_identity_norm_profile_alpha_v1' and
      old_plan['mode']=='profile' and old_plan['pilot'] is True and old_plan['endpoint']==q.ENDPOINT and old_plan['uid']==UID and old_plan['node']==prior['node'] and
      old_proof['schema']=='SECONDARY_COCONUT_IDENTITY_NORM_PROFILE_STARTUP_V1' and old_proof['uid']==UID and old_proof['endpoint']==q.ENDPOINT and
      str(old_proof['job_id'])=='1884785' and old_proof['node']==prior['node'] and old_proof['plan_reference']==plan['profile_plan_reference'] and
      old_proof['root_review_reference']==old_plan['root_review_reference'],'HISTORICAL_PROFILE_PLAN_PROOF_BINDING_NOT_FRESH_PROOF_REUSE')
    account(plan['accepted_profile_accounting_reference'],'1884785',prior['node'],parents)
    historical={r['path']:{k:r[k] for k in ('path','bytes','sha256')} for r in old_proof['source_target_verification']}
    for name,(size,sha) in PROFILE.items():
        ref=pin(ROOT/'code/secondary_coconut_identity_norm_profile_v1'/name)
        need(ref['bytes']==size and ref['sha256']==sha and ref in plan['source_references'] and ref in old_plan['source_references'] and historical.get(ref['path'])==ref,'EXACT_REGISTERED_PROFILE_FOUR_KERNEL_SOURCES')
    for key in ('frozen_identity_source_references','a_full_receipt_reference','a_full_accounting_reference','a_full_plan_reference','a_full_startup_proof_reference'):
        need(plan[key]==old_plan[key],'UNCHANGED_FROZEN_HELPER_AND_A_AUTHORITY_CHAIN:'+key)
    for ref in plan['frozen_identity_source_references'].values():need(ref in plan['source_references'] and ref in old_plan['source_references'],'EXACT_FROZEN_HELPER_PINS')
    a=q.load_ref(plan['a_full_receipt_reference']);a_plan=q.load_ref(plan['a_full_plan_reference']);a_proof=q.load_ref(plan['a_full_startup_proof_reference'])
    need(a['schema']=='SECONDARY_COCONUT_SQL_IDENTITY_INVENTORY_RECEIPT_V1' and a['status']=='FULL_SQL_PHYSICAL_IDENTITY_FIELD_INVENTORY_COMPLETE' and a['mode']=='full' and
      a['job_id']=='1884772' and a['uid']==UID and a['endpoint']==q.ENDPOINT and a['all_statuses_classes_invalid_and_NULL_rows_retained'] is True and
      a['plan']==plan['a_full_plan_reference'] and a['startup_proof']==plan['a_full_startup_proof_reference'] and a['input_before']==a['input_after'] and
      a['inventory']['current_full_SQL_SHA_reverified'] is True and a['inventory']['full_EOF_and_all_tables_proven'] is True,'ACTUAL_FULL_A1884772_SCOPE')
    need(a_plan['mode']=='full' and a_plan['pilot'] is False and a_plan['data_references']==[a['input_reference']] and
      a_proof['plan_reference']==plan['a_full_plan_reference'] and str(a_proof['job_id'])==a['job_id'] and a_proof['uid']==UID and a_proof['node']==a['node'],'ACTUAL_A_PLAN_PROOF_CHAIN')
    account(plan['a_full_accounting_reference'],a['job_id'],a['node'],parents)
    need(plan['data_references']==old_plan['data_references']==[x['reference'] for x in prior['source_SHA_footer_phases']] and
      [x['table'] for x in prior['source_SHA_footer_phases']]==list(COUNTS) and {x['table']:x['footer_rows'] for x in prior['source_SHA_footer_phases']}==COUNTS,'SAME_COMPLETE_A_TWO_PARQUET_LOCATORS')
    for table in COUNTS:need(a['inventory']['physical_COPY_rows_by_table'][table]==a['inventory']['reconciliation']['projected_rows_by_table'][table]==COUNTS[table],'ALL_ACTUAL_PHYSICAL_ROWS_REQUIRED')
    for ref in a['kernel_source_references']:need(ref in plan['source_references'] and ref in a_plan['source_references'],'EXACT_ORIGINAL_A_KERNEL_SOURCES')
    return plan,proof,prior,a
