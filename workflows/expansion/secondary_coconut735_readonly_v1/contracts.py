"""Exact independent Alpha735 scope, actual C0 parents and deferred fixed index."""
import csv,hashlib,io,os,socket,sys,time
from pathlib import Path
from secondary_cpu_queue_v1 import common as q
from secondary_coconut_strict5_day_v1 import contracts as OLD
ROOT=q.ROOT;UID=1264;KEY='coconut735_closed_identity_diagnosis_alpha_v1';MODULE='secondary_coconut735_readonly_v1.run'
HERE=ROOT/'code/secondary_coconut735_readonly_v1';STAGE='COCONUT735_EXISTING_IDENTITY_EVIDENCE_DIAGNOSIS'
SCHEMA='COCONUT735_READONLY_DIAGNOSTIC_PLAN_V1';PROOF='COCONUT735_READONLY_DIAGNOSTIC_STARTUP_V1';CAP=2<<30;WALL=3600
FILES=('__init__.py','contracts.py','run.py','test_v1.py','adapters.py','controller.py','metadata.py','README.md')
need=q.need;pin=q.ref;load=q.load;literal=q.literal;write_new=q.write_new
def triple(v):
    from secondary_coconut_strict5_day_v1.io import triple as original
    return original(v)
def unique(refs):
    values={}
    for x in refs:
        r=triple(x);need(r['path'] not in values or values[r['path']]==r,'NO_CONFLICTING_SAME_PATH_REFERENCE');values[r['path']]=r
    return list(values.values())
def parameters(p):
    return {'purpose':'EXACT_EXISTING735_READONLY_DIAGNOSIS_NOT_STRICT5_PRODUCTION','parent_job_id':'1885088','unknown_physical_rows':735,
      'locator_reference':p['unknown_locator_reference'],'fixed_index_authority_reference':p['fixed_index_authority_reference'],
      'norm_recomputed':False,'new_authoritative_full_keys':False,'graph_repair':False,'network_calls':0,'QM_UFF_calls':0,
      'original_K_project_replay_only':True,'maximum_original_variants_per_row':3,'all_original_values_errors_and_unknowns_retained':True,
      'SQL_executed_or_imported':False,'nonidentity_SQL_values_decoded':False,'opaque_original_SQL_candidate_capture':True,
      'maximum_opaque_SQL_candidate_rows':4096,'maximum_opaque_SQL_row_bytes':16<<20,'maximum_opaque_SQL_capture_bytes':64<<20,
      'source_norm_full_rescan_or_reproduction':False,'workers':16,'maximum_pending_batches':32,'batch_rows':16,
      'wall_seconds':WALL,'output_cap_bytes':CAP,'environment':OLD.ENV,'mode':'diagnostic735','strict5_candidate_READY_or_pool_release':False}
def parents(p):
    chain=p['strict_parent'];need(set(chain)=={'receipt','plan','proof','coverage','accounting'},'EXACT_1885088_PARENT_CHAIN')
    r=q.load_ref(chain['receipt']);old=q.load_ref(chain['plan']);proof=q.load_ref(chain['proof']);coverage=q.load_ref(chain['coverage'])
    account=q.load_ref(chain['accounting']);raw=account['raw_sacct_reference']
    from secondary_coconut_identity_norm_full_v1.contracts import account as original_account
    original_account(chain['accounting'],'1885088',r['node'],[chain['accounting'],raw])
    need(r['schema']=='COCONUT_STRICT5_DAY_RECEIPT_V1' and r['job_id']=='1885088' and r['uid']==UID and r['endpoint']==q.ENDPOINT
      and r['complete_physical_source'] is True and r['READY_candidate'] is False and r['global_decontamination_or_pool_release'] is False
      and r['status']=='PHYSICAL_PROJECTED_UNKNOWN_OR_RESOURCE_HOLD_NOT_READY' and r['counters']['unresolved_without_identity_or_composition']==735
      and r['startup_proof_reference']==chain['proof'] and r['plan_reference']==chain['plan'] and r['coverage_reference']==chain['coverage']
      and proof['plan_reference']==chain['plan'] and proof['job_id']=='1885088' and proof['uid']==UID and proof['node']==r['node'],
      'ACTUAL_C0_1885088_UNKNOWN735_NOT_READY_NO_PARENT_PROMOTION')
    need(coverage['physical_rows']==2939137 and coverage['unresolved_without_identity_or_composition']==735 and coverage['all_splits'] is True
      and coverage['observed_physical_rows_by_table']==OLD.COUNTS and coverage['original_consumer_all_identity_rows_readback']==2938431
      and old['data_references']==coverage['raw_artifacts'] and proof['scope_key']==OLD.KEY,'EXACT_OLD_PHYSICAL_AND_STRICT_ROW_DISTINCT_COUNTS')
    need(triple(r['outputs']['unknown_locators'])==p['unknown_locator_reference'] and r['outputs']['unknown_locators']['rows']==735,'ONLY_ACTUAL735_PRODUCER_LOCATORS')
    norm,normplan,parts,properties,native=OLD.norm_parent(old)
    need(p['frozen_identity_source_references']==old['frozen_identity_source_references'] and p['decontamination_source_reference']==old['decontamination_source_reference'],'DIRECT_UNCHANGED_OLD_KERNEL_SOURCE_CONTEXT')
    authority=q.load_ref(p['fixed_index_authority_reference']);index_root=Path(chain['receipt']['path']).parent
    need(authority['schema']=='ROOT_FIXED_CLOSED_COCONUT735_INDEX_METADATA_LOCATOR_AUTHORITY_V1'
      and authority['status']=='APPROVED_SAME_PARENT_FIRST_WHOLE_SHA_READONLY_NOT_SCIENCE_ACCEPTANCE' and authority['reviewer']=='root'
      and authority['uid']==UID and authority['endpoint']==q.ENDPOINT and authority['producer_job_id']=='1885088'
      and authority['fixed_output_root']==str(index_root) and authority['fixed_index_path']==str(index_root/'identity_links.sqlite')
      and authority['actual_closed_parent_accounting_reference']==chain['accounting'] and authority['producer_SHA_not_claimed'] is True
      and authority['scientific_body_opened_or_hashed'] is False and authority['new_diagnostic_CPU_must_validate_current_stable_FD_whole_SHA_no_sidecars_before_read'] is True
      and authority['only_original735_exact_index_lookup_no_candidate_or_READY'] is True,'REAL_ROOT_FIXED_INDEX_FIRST_CPU_HASH_AUTHORITY')
    frame=authority['actual_lstat'];need(type(frame['bytes']) is int and frame['bytes']>0 and frame['uid']==UID and frame['nlink']==1,'REAL_POSITIVE_INDEX_LSTAT_NOT_FUTURE_HASH')
    aplan=q.load_ref(native['plan']);ddl_ref=aplan['schema_observations_reference'];ddl=q.load_ref(ddl_ref)
    tables={v['table_identifiers'][-1]:v for v in ddl['tables']};need('structures' in tables,'ACTUAL_CLOSED_DDL_STRUCTURES_NOT_GUESSED_SCHEMA')
    indexes=[triple(x) for x in native['physical_output_references'] if x['path'].endswith('/identity_inventory.sqlite')]
    structures=[triple(x) for x in native['physical_output_references'] if x['path'].endswith('/structures.raw_identity.parquet')]
    need(len(indexes)==len(structures)==1,'ONE_PRODUCER_HASHED_A_INDEX_AND_STRUCTURES_LOCATOR')
    data=unique([p['unknown_locator_reference'],*(x['reference'] for x in parts),properties,indexes[0],structures[0],native['input_reference']])
    if 'data_references' in p:need(p['data_references']==data,'EXACT_CLOSED_DATA_REFERENCE_SET_NO_DEFERRED_FAKE_SHA')
    return {'receipt':r,'old_plan':old,'norm_receipt':norm,'parts':parts,'properties':properties,'A_receipt':native,
      'A_index':indexes[0],'structures':structures[0],'SQL':triple(native['input_reference']),'DDL':ddl,'DDL_reference':ddl_ref,
      'A_plan_reference':native['plan'],'index_authority':authority,'raw_accounting_reference':raw},data

def startup(plan_path,proof_path,primary):
    plan=load(plan_path);proof=load(proof_path);review=q.load_ref(plan['root_review_reference']);wall=plan['wall_seconds'];cap=plan['output_cap_bytes']
    source=HERE/'run.py';argv=[plan['python'],'-B','-m',MODULE,'--plan',str(plan_path),'--startup-proof',str(proof_path)]
    need(plan.get('schema')==SCHEMA and plan.get('producer_key')==plan.get('scope_key')==KEY and
      plan.get('stage')==STAGE and plan.get('mode')=='diagnostic735' and plan.get('pilot') is False and plan.get('scope_parameters')==parameters(plan) and
      plan.get('endpoint')==q.ENDPOINT and plan.get('uid')==UID and plan.get('run_root')==str(ROOT) and plan.get('node') in q.NODES and plan.get('cpus')==16 and
      plan.get('memory_policy')=='SLURM_DEFAULT_UNSPECIFIED' and type(wall) is int and wall==WALL and wall%60==0 and plan.get('output_cap_bytes')==cap,
      'EXACT_INDEPENDENT_FULL_PHYSICAL_SCOPE_REQUIRED')
    need(Path(primary).absolute()==source==Path(sys.modules['__main__'].__file__).absolute() and Path(sys.executable).absolute()==Path(plan['python']).absolute() and
      sys.argv==[str(source),*argv[4:]] and plan['execution_argv']==argv and plan['startup_proof_path']==str(proof_path),'ACTUAL_FULL_PRIMARY_AND_ALL_ARGV')
    need(review.get('schema')=='EXACT_SECONDARY_BOUNDED_READONLY_ROOT_REVIEW_V1' and review.get('status')=='APPROVED_FOR_EXACT_STAGE' and review.get('reviewer')=='root',
      'EXACT_ROOT_FULL_STAGE_REVIEW')
    for key in ('scope_key','scope_parameters','stage','endpoint','uid','run_root','node','cpus','memory_policy','pilot','wall_seconds','output_cap_bytes',
      'execution_argv','data_references','parent_evidence_references'):need(plan[key]==review[key],'ROOT_FULL_FIELD_DIFFERS:'+key)
    need(plan['source_references']==review['approved_source_references'] and review.get('actual_closed735_parent_and_fixed_index_reviewed') is True and
      review.get('fixed_root_first_CPU_SHA_readonly_index_authorized') is True,'EXACT_APPROVED_FULL_SOURCES_AND_QUALITY_REVIEW')
    need(proof.get('schema')==PROOF and proof.get('endpoint')==q.ENDPOINT and proof.get('uid')==os.getuid()==UID and
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
    need(type(cap)is int and cap==CAP,'EXACT_2G_DIAGNOSTIC_OUTPUT_CAP')
    parents(plan)
    return plan,proof
# ORIGINAL_RESOURCE_STARTUP_NARROW_SCOPE_INVERSE_END
