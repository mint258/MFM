"""New independent Alpha normalization-profile protocol; A full C0 is mandatory."""
import csv,hashlib,io,os,re,socket,sys,time
from pathlib import Path
from secondary_cpu_queue_v1 import common as q

ROOT=q.ROOT;UID=1264;KEY='coconut_identity_norm_profile_alpha_v1';MODULE='secondary_coconut_identity_norm_profile_v1.run'
STAGE='IDENTITY_KEY_NORMALIZATION_PROFILE';need=q.need;pin=q.ref;load=q.load;literal=q.literal
FROZEN={'projection':('workflows/expansion/identity_v2/projection_v2.py',8616,'7da54ccb4488950fb567c17cfa161bc339d8a377f2e2fb27362434ce88516d28'),
 'common':('workflows/expansion/common.py',4312,'8c988f617776ad05354deae1cf69933e7ff95210f7a2609f903e4826172ccbad')}

def parameters(version):
    need(isinstance(version,str) and re.fullmatch(r'3\.[0-9]+\.[0-9]+',version),'EXPLICIT_ACTUAL_SAMPLER_PYTHON_VERSION_REQUIRED')
    return {'mode':'profile','sample_tables':['molecules','entries'],'maximum_sample_rows_per_table':10000,'seed':20261026,
      'ordinal_sampler':'PY_RANDOM_SAMPLE_SORTED_TABLE_SHA256_SEED_V1','sampler_python_version':version,'workers':16,'maximum_pending':32,
      'RDKit_version':'2025.09.5','present_SMILES_variants_separately':True,'stored_full_keys_strict':False,
      'status_invalid_or_identity_filter':False,'raw_identity_rows_retained':True,'X_rules_or_features_called':False,
      'maximum_input_JSON_bytes_per_record':2*1024**2,'maximum_result_JSON_bytes_per_record':8*1024**2,
      'maximum_source_rowgroup_uncompressed_bytes':256*1024**2,'full_source_normalization_authorized':False,
      'algorithm_current_RSS_reference_bytes':48*1024**3,'runtime_MemAvailable_min_fraction':.15,'cost_overrun_action':'REPORT_AND_CONTINUE'}

def frame(s):return {'device':s.st_dev,'inode':s.st_ino,'size':s.st_size,'mtime_ns':s.st_mtime_ns,'uid':s.st_uid}

def write_new(path,value):
    import json
    raw=(json.dumps(value,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n').encode();need(len(raw)<=2*1024**2,'SMALL_METADATA_REQUIRED')
    with Path(path).open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())

def startup(plan_path,proof_path,primary):
    plan=load(plan_path);proof=load(proof_path);review=q.load_ref(plan['root_review_reference']);wall=plan['wall_seconds'];cap=2*1024**3
    source=ROOT/'code/secondary_coconut_identity_norm_profile_v1/run.py'
    argv=[plan['python'],'-B','-m',MODULE,'--plan',str(plan_path),'--startup-proof',str(proof_path)]
    need(plan.get('schema')=='SECONDARY_COCONUT_IDENTITY_NORM_PROFILE_PLAN_V1' and plan.get('producer_key')==plan.get('scope_key')==KEY and
      plan.get('stage')==STAGE and plan.get('mode')=='profile' and plan.get('pilot') is True and plan.get('scope_parameters')==parameters(plan['sampler_python_version']) and
      plan['sampler_python_version']==sys.version.split()[0] and plan.get('endpoint')==q.ENDPOINT and plan.get('uid')==UID and plan.get('run_root')==str(ROOT) and
      plan.get('node') in q.NODES and plan.get('cpus')==16 and plan.get('memory_policy')=='SLURM_DEFAULT_UNSPECIFIED' and
      type(wall) is int and 0<wall<=14400 and wall%60==0 and plan.get('output_cap_bytes')==cap,'EXACT_NEW_PROFILE_ONLY_PLAN')
    need(Path(primary).absolute()==source==Path(sys.modules['__main__'].__file__).absolute() and Path(sys.executable).absolute()==Path(plan['python']).absolute()
      and sys.argv==[str(source),*argv[4:]] and plan['execution_argv']==argv and plan['startup_proof_path']==str(proof_path),'ACTUAL_MAIN_AND_ALL_ARGV')
    need(review.get('schema')=='EXACT_SECONDARY_BOUNDED_READONLY_ROOT_REVIEW_V1' and review.get('status')=='APPROVED_FOR_EXACT_STAGE' and
      review.get('reviewer')=='root','EXACT_ROOT_PROFILE_REVIEW')
    for key in ('scope_key','scope_parameters','stage','endpoint','uid','run_root','node','cpus','memory_policy','pilot','wall_seconds',
      'output_cap_bytes','execution_argv','data_references','parent_evidence_references'):need(plan[key]==review[key],'ROOT_PROFILE_FIELD_DIFFERS:'+key)
    need(plan['source_references']==review['approved_source_references'],'EXACT_APPROVED_CODE_SOURCES')
    need(proof.get('schema')=='SECONDARY_COCONUT_IDENTITY_NORM_PROFILE_STARTUP_V1' and proof.get('endpoint')==q.ENDPOINT and proof.get('uid')==os.getuid()==UID
      and proof['node']==plan['node']==socket.gethostname().split('.')[0] and proof['boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip()
      and 0<=time.time()-proof['observed_unix_seconds']<=120 and proof['plan_reference']==pin(plan_path) and proof['root_review_reference']==plan['root_review_reference'],
      'ACTUAL_FRESH_INDEPENDENT_ALPHA_PROFILE_PROOF')
    need(proof['request']=={'kind':'analysis','pilot':True,'cpus':16,'memory_policy':'SLURM_DEFAULT_UNSPECIFIED','wall_seconds':wall,'execution_argv':argv}
      and proof['memory_limits_requested'] is False and proof['exclusive_requested'] is False
      and proof.get('bounded_readonly_scope_only') is True and proof.get('bounded_source_acquisition_scope_only',False) is False,
      'PROFILE_DEFAULT_MEMORY_READONLY_NOT_ACQUISITION_REQUEST')
    env=os.environ;need(env.get('SLURM_JOB_ID')==str(proof['job_id']) and env.get('SLURM_JOB_PARTITION')=='cpu' and env.get('SLURM_CPUS_PER_TASK')=='16'
      and env.get('CUDA_VISIBLE_DEVICES')=='' and all(env.get(x)=='1' for x in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')),'REAL_CPU16_THREADS')
    declared={r['path']:{k:r[k] for k in ('path','bytes','sha256')} for r in proof['source_target_verification']}
    for ref in [*plan['source_references'],*plan['parent_evidence_references'],plan['root_review_reference'],pin(plan_path)]:
        need(declared.get(ref['path'])==ref,'ACTUAL_APPROVED_PROFILE_TARGET_MISSING');q.verify(ref)
    for path in [*source.parent.glob('*.py'),Path(q.__file__),Path(q.__file__).parent/'__init__.py']:
        need(pin(path) in plan['source_references'],'EXACT_IMPORTED_PROFILE_AND_BASE_CODE_REQUIRED')
    signer=proof['controller_evidence'];need(signer['endpoint']==q.ENDPOINT and signer['uid']==UID and signer['hostname']=='sonmi'
      and signer['proof_is_not_created_by_scientific_worker'] is True and signer['actual_script_reference']==proof['script_reference'],'REAL_LOGIN_CONTROLLER')
    for line in q.read_small(q.verify(proof['script_reference'])).decode().splitlines():
        if line.strip().startswith('#SBATCH'):need(not any(x in line for x in ('--mem','--exclusive','--gres','--gpu')),'NO_MEMORY_EXCLUSIVE_GPU')
    job=q.fields(proof['job_metadata']);need(job.get('JobId')==str(proof['job_id']) and job.get('UserId')=='alpha(1264)' and job.get('JobState')=='RUNNING'
      and job.get('NodeList')==plan['node'] and job.get('Partition')=='cpu' and job.get('NumCPUs')=='16' and job.get('NumTasks')=='1' and job.get('Requeue')=='0'
      and job.get('Command')==proof['script_reference']['path'] and q.duration(job.get('TimeLimit',''))==wall,'REAL_OWN_SCRIPT_JOB_WALL')
    gate=proof['actual_gate_process'];tail=Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()
    need(gate['pid']==os.getpid() and gate['uid']==UID and gate['start_ticks']==int(tail[19]) and gate['pgid']==os.getpgrp() and gate['sid']==os.getsid(0)
      and gate['cgroup_sha256']==hashlib.sha256(Path('/proc/self/cgroup').read_bytes()).hexdigest(),'SAME_ATTESTED_EXEC_GATE_PROCESS')
    storage=proof['storage_observation'];q.load_ref(proof['storage_observation_reference']);need(proof['account_free_bytes']==storage['effective_free_bytes'] and
      proof['account_free_bytes']-cap>=200000000000 and storage['whole_output_caps_reserved_bytes']>=cap and 0<=time.time()-storage['observed_unix_seconds']<=120,'FRESH_ALL_CAPS200GB_STORAGE')
    for key in ('resource_authority_reference','cost_decision_reference'):
        need(plan[key] in plan['source_references'],'EXACT_ACTUAL_AUTHORITY_SOURCE')
    authority=q.load_ref(plan['resource_authority_reference']);need(authority.get('schema')=='USER_AUTHORIZED_SECONDARY_DATA_CLUSTER_V1' and authority.get('status')=='USER_AUTHORIZED'
      and authority.get('endpoint')==q.ENDPOINT and authority.get('observed_uid')==UID and authority.get('memory_policy')=='SLURM_DEFAULT_UNSPECIFIED','REAL_ALPHA_AUTHORITY')
    cost=q.load_ref(plan['cost_decision_reference']);need(cost.get('schema')=='USER_AUTHORIZED_ALLOCATION_OVERRUN_REPORT_CONTINUE_V1' and cost.get('status')=='USER_AUTHORIZED'
      and cost.get('on_overrun')=='REPORT_AND_CONTINUE' and cost.get('scientific_quality_thresholds_unchanged') is True,'REAL_COST_CONTINUE_AUTHORITY')
    for key in ('a_full_receipt_reference','a_full_accounting_reference','a_full_plan_reference','a_full_startup_proof_reference'):
        need(plan[key] in plan['parent_evidence_references'],'ACTUAL_A_FULL_PARENT_REQUIRED:'+key)
    a=q.load_ref(plan['a_full_receipt_reference']);need(a['schema']=='SECONDARY_COCONUT_SQL_IDENTITY_INVENTORY_RECEIPT_V1' and a['mode']=='full'
      and a['status']=='FULL_SQL_PHYSICAL_IDENTITY_FIELD_INVENTORY_COMPLETE' and a['endpoint']==q.ENDPOINT and a['uid']==UID and
      a['input_reference']['bytes']==37876914074 and a['input_reference']['sha256']=='bb61f8e074f876beaaf251b9abe5b4334aebbda28717120ac482db39d58ced29' and
      a['all_statuses_classes_invalid_and_NULL_rows_retained'] is True and a['plan']==plan['a_full_plan_reference'] and a['startup_proof']==plan['a_full_startup_proof_reference'],
      'ACTUAL_COMPLETE_A_FULL_NOT_A_PREFIX_PROFILE')
    a_plan=q.load_ref(plan['a_full_plan_reference']);a_proof=q.load_ref(plan['a_full_startup_proof_reference'])
    need(a_plan.get('schema')=='SECONDARY_COCONUT_SQL_IDENTITY_INVENTORY_PLAN_V1' and a_plan.get('mode')=='full' and
      a_plan.get('producer_key')==a_plan.get('scope_key')=='coconut_sql_identity_inventory_alpha_v1' and
      a_plan.get('stage')=='SQL_IDENTITY_PROJECTION_FULL' and a_plan.get('pilot') is False and
      a_plan.get('endpoint')==q.ENDPOINT and a_plan.get('uid')==UID and a_plan.get('cpus')==16 and
      a_plan.get('node')==a['node'] and a['node'] in q.NODES and a_plan.get('data_references')==[a['input_reference']],
      'ACTUAL_A_PLAN_FULL_PHASE_UID_NODE_AND_INPUT_BINDING')
    need(a_proof.get('schema')=='SECONDARY_COCONUT_SQL_IDENTITY_INVENTORY_STARTUP_V1' and
      a_proof.get('endpoint')==q.ENDPOINT and a_proof.get('uid')==UID and str(a_proof.get('job_id'))==a['job_id'] and
      a_proof.get('node')==a['node'] and a_proof.get('plan_reference')==plan['a_full_plan_reference'] and
      a_proof.get('root_review_reference')==a_plan['root_review_reference'] and
      a_proof.get('request',{}).get('kind')=='analysis' and a_proof['request'].get('pilot') is False and
      a_proof['request'].get('cpus')==16,'HISTORICAL_A_FULL_PROOF_JOB_UID_NODE_PLAN_BINDING')
    # Historical completed A proof is byte-bound, never subjected to B's fresh120s clock.
    details=a['inventory'];need(details['current_full_SQL_SHA_reverified'] is True and details['full_EOF_and_all_tables_proven'] is True and len(details['DDL_tables_seen'])==15 and
      details['source_bytes_consumed_at_record_boundary']==details['source_bytes_read_including_read_ahead']==37876914074 and
      details['reconciliation']['no_status_or_invalid_class_filtered'] is True and a['input_before']==a['input_after'],'A_FULL_EOF_CONSERVATION_AND_STATUS_SCOPE')
    account=q.load_ref(plan['a_full_accounting_reference']);parent=account['actual_parent'];need(account['query_returncode']==0 and account['uid']==UID and account['endpoint']==q.ENDPOINT
      and parent['JobIDRaw']==a['job_id'] and parent['State']=='COMPLETED' and parent['ExitCode']=='0:0' and parent['UID']==str(UID) and parent['AllocCPUS']=='16'
      and parent['NodeList']==a['node'] and parent['Partition']=='cpu','ACTUAL_A_FULL_C0_COST')
    need(account['raw_sacct_reference'] in plan['parent_evidence_references'],'RAW_A_FULL_PARENT_ACCOUNTING_PIN')
    raw=list(csv.DictReader(io.StringIO(q.read_small(q.verify(account['raw_sacct_reference'])).decode()),delimiter='|'));parents=[x for x in raw if x.get('JobIDRaw')==a['job_id']]
    need(len(parents)==1 and all(parents[0][k]==parent[k] for k in ('State','ExitCode','UID','ElapsedRaw','AllocCPUS','NodeList','Partition')) and
      account['allocated_core_seconds_observed']==int(parent['ElapsedRaw'])*16 and review.get('actual_A_full_cost_and_identity_projection_reviewed') is True,'REAL_A_FULL_RAW_ACCOUNT_AND_ROOT_REVIEW')
    wanted={t:next((r for r in a['physical_output_references'] if Path(r['path']).name==t+'.raw_identity.parquet'),None) for t in ('molecules','entries')}
    need(all(wanted.values()) and plan['data_references']==[wanted[t] for t in ('molecules','entries')],'ONLY_ACTUAL_A_TWO_RAW_IDENTITY_INPUTS')
    for table in wanted:need(details['physical_COPY_rows_by_table'][table]==details['reconciliation']['projected_rows_by_table'][table]>0,'ACTUAL_A_TABLE_COUNTS_REQUIRED')
    a_kernel=[pin(ROOT/'code/secondary_coconut_sql_identity_v1'/name) for name in ('__init__.py','contracts.py','copy_text.py','run.py')]
    need(len(a['kernel_source_references'])==4 and {q.canonical(ref) for ref in a['kernel_source_references']}==
      {q.canonical(ref) for ref in a_kernel},'EXACT_FOUR_ACTUAL_A_KERNEL_SOURCE_FILES')
    for ref in a_kernel:
        need(ref in plan['source_references'] and ref in a_plan['source_references'],'EXACT_A_KERNEL_MUST_BE_APPROVED_BY_B_AND_HISTORICAL_A_PLAN')
    for name,(_,size,sha) in FROZEN.items():
        ref=plan['frozen_identity_source_references'][name];need(ref in plan['source_references'] and ref['bytes']==size and ref['sha256']==sha,'UNCHANGED_FROZEN_IDENTITY_SOURCE:'+name)
    return plan,proof,a
