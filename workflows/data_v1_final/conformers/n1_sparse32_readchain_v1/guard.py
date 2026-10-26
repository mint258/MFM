"""Independent Main/Alpha analysis guards; zero optimizer and ledger authority."""
from __future__ import annotations
import copy,csv,hashlib,io,os,pathlib,socket,sys,time
from . import common as U
MAIN_KEY='n1_sparse32_readchain_export_v1';ALPHA_KEY='n1_sparse32_readchain_alpha_v1'
ALPHA_STAGE='READ_ORIGINAL_LMDB_VALUES_FIELD_GRAPH_CONTROL32'
PARAMETERS={'molecules':32,'original_PM7_pointers_per_molecule':1,'source_prepare_job_id':'4521417','source_pilot_job_id':'4521418',
 'source_value_encoding':'EXACT_ORIGINAL_PICKLE_BYTES_NO_REPICKLE','original_LMDB_key_encoding':'ASCII_INT_MINWIDTH9_NO_REINDEX',
 'raw_value_software_cap_bytes':8<<20,'raw_value_cap_in_original_loader':None,'maximum_raw_bytes':256<<20,
 'map_size_formula':'round_up(2*actual_group_raw_bytes+16MiB,page_size)','maximum_one_map_bytes':528<<20,'maximum_total_map_bytes':1<<30,
 'whole_selected_input_cap_bytes':2<<30,'whole_output_cap_bytes':2<<30,'field_signature_depth':32,'field_signature_nodes':100000,
 'field_signature_leaf_logical_bytes':64<<20,'field_signature_record_logical_bytes':128<<20,'field_signature_JSON_bytes':1<<20,
 'execution_pointer_edit_allowlist':['source_path'],'original_task_bytes_changed':False,'frozen_module_globals_monkeypatched':False,
 'new_UFF_calls':0,'new_QM_calls':0,'once_ledger_opened':False,'canonical32_attempts_consumed':False,
 'dataset_membership':False,'common':False,'production_population_release':False,'unsupported_field_types':'UNKNOWN_NEVER_EQUIVALENT'}

def set_threads():os.environ.update({k:'1' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','BLIS_NUM_THREADS')})
def request_ref(proof_path,path):
    proof=U.load(U.pin(proof_path,True));wanted=str(pathlib.Path(path).absolute())
    hits=[r for key in ('source_references','data_references') for r in proof['request'].get(key,[]) if r['path']==wanted]
    U.need(hits and all(r==hits[0] for r in hits),'LITERAL_SMALL_PLAN_MUST_BE_IN_REAL_REQUEST');return hits[0]
def approved(proof,references):
    refs=[r for key in ('source_references','data_references') for r in proof['request'].get(key,[])]
    for r in references:U.need(r in refs,'EXACT_UPSTREAM_REFERENCE_NOT_AUTHORIZED:'+r['path'])

def main_startup(plan_path,proof_path):
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.runtime import require_startup
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.contract import PY
    from workflows.data_v1_final.conformers.n1_pprime2_pilot_v4 import io as V
    here=pathlib.Path(__file__).absolute().parent;plan_ref=request_ref(proof_path,plan_path);plan=U.load(plan_ref)
    U.need(plan['schema']=='MAIN_N1_SPARSE32_READCHAIN_EXPORT_PLAN_V1' and plan['scope_key']==MAIN_KEY and plan['scope_parameters']==PARAMETERS,'EXACT_MAIN_RAW_ONLY32_PLAN')
    U.need(plan['output_cap_bytes']==U.CAP and plan['selected_input_cap_bytes']==U.CAP and 120<plan['wall_seconds']<=3600,'FINITE_MAIN2GIB_ONE_HOUR_SCOPE')
    required=[plan_ref,*[plan[k] for k in ('prepared_reference','pilot_receipt_reference','science_cost_review_reference','accounting_reference','catalog_reference','recipe_reference','quota_provider_review_reference')],
      *plan['science_sources'].values(),*[U.pin(p,True) for p in here.iterdir() if p.suffix in ('.py','.md')]]
    required.extend(U.pin(p,True) for p in (V.__file__,V.C.__file__,V.Q.__file__,pathlib.Path(V.__file__).parent/'__init__.py'))
    argv=[PY,'-B','-m','workflows.data_v1_final.conformers.n1_sparse32_readchain_v1.main_export','--plan',str(pathlib.Path(plan_path).absolute()),'--root-preflight',str(pathlib.Path(proof_path).absolute())]
    proof=require_startup(proof_path,expected_scope_key=MAIN_KEY,expected_scope_parameters=PARAMETERS,expected_execution_argv=argv,
        expected_source=here/'main_export.py',expected_kind='analysis',required_references=required)
    U.need(proof['request']['pilot'] is False and proof['request']['node']=='compute-0-13'
      and proof['request']['estimated_peak_output_bytes']>=U.CAP and proof['request']['wall_seconds']==plan['wall_seconds'],'REAL_NODE13_NONPILOT_ANALYSIS_CAP')
    prepared=U.load(plan['prepared_reference']);pilot=U.load(plan['pilot_receipt_reference']);review=U.load(plan['science_cost_review_reference'])
    U.need(prepared['schema']=='N1_PPRIME2_PILOT_PREPARED32_V4' and prepared['job_id']=='4521417' and prepared['status']=='ACTUAL_INPUT32_READY_NOT_GENERATED'
      and prepared['selected_count']==32 and len(prepared['tasks'])==len(prepared['baseline_packets'])==32,'REAL_FROZEN_V4_INPUT32')
    U.need(pilot['schema']=='N1_PPRIME2_PILOT32_RECEIPT_V4' and pilot['status']=='ACTUAL32_PACKETS_CLOSED_REQUIRES_SCIENTIFIC_AND_COST_ROOT_REVIEW'
      and pilot['job_id']=='4521418' and pilot['prepared']==plan['prepared_reference']
      and pilot['completed_durable_readback_packets']==32 and not pilot['unknown_started_task_keys'],'REAL_CANONICAL32_SOURCE_PILOT_HEADER')
    U.need(review['schema']=='ROOT_ACTUAL_N1_V4_PILOT32_SCIENCE_COST_REVIEW_V1' and review['reviewer']=='root'
      and review['prepared_reference']==plan['prepared_reference'] and review['pilot_receipt_reference']==plan['pilot_receipt_reference']
      and review['terminal_all_known_accounting_reference']==plan['accounting_reference'],'ACTUAL_ROOT32_CANONICAL_SOURCE_REVIEW')
    account=U.load(plan['accounting_reference']);approved(proof,[account['raw_sacct_reference'],prepared['source_population_authority'],*prepared['tasks'],*prepared['baseline_packets']])
    V.terminal_c0(plan['accounting_reference'],'4521417');V.terminal_c0(plan['accounting_reference'],'4521418')
    authority=U.load(prepared['source_population_authority']);U.need(len(authority['selected_molecule_ids'])==32,'EXACT_SOURCE32_ROSTER_AUTHORITY')
    catalog=U.load(plan['catalog_reference']);U.need(plan['catalog_reference']==prepared['catalog'],'ORIGINAL_CATALOG_REFERENCE')
    expected={'common':catalog['references']['io'],'legacy':catalog['references']['graph_stereo_rmsd'],'prepare':catalog['references']['legacy_prepare_import']}
    U.need(plan['science_sources']==expected and plan['recipe_reference']==catalog['references']['recipe'],'EXACT_THREE_ORIGINAL_READER_SOURCES_AND_RECIPE')
    from workflows.data_v1_final.conformers.n1_pprime2_pilot_v4 import quota_provider as Q
    quota_refs=Q.references(plan['quota_provider_review_reference']);approved(proof,quota_refs)
    for r in quota_refs:U.require(r,True)
    alpha=pathlib.Path(plan['alpha_input_root']);U.need(U.ALPHA/'inputs/n1_sparse32_readchain_v1' in alpha.parents,'EXACT_NEW_EXPECTED_ALPHA_INPUT_CHILD')
    set_threads();plan=dict(plan,actual_proof_path=str(proof_path));return plan,proof,prepared,authority,Q.Client(plan['quota_provider_review_reference'],proof['request'])

def alpha_startup(plan_path,proof_path):
    from secondary_cpu_queue_v1 import common as Q
    plan=U.load(U.pin(plan_path,True));proof=U.load(U.pin(proof_path,True));source=U.ALPHA/'code/n1_sparse32_readchain_v1/alpha_read.py'
    U.need(plan['schema']=='SECONDARY_N1_SPARSE32_READCHAIN_PLAN_V1' and proof['schema']=='SECONDARY_N1_SPARSE32_READCHAIN_STARTUP_V1','NEW_INDEPENDENT_ALPHA_READCHAIN_PROOF')
    for key,value in (('scope_key',ALPHA_KEY),('stage',ALPHA_STAGE),('endpoint','218.192.171.238:22'),('uid',1264)):
        U.need(plan[key]==proof[key]==value,'EXACT_ALPHA_READCHAIN_IDENTITY:'+key)
    U.need(plan['producer_key']==ALPHA_KEY and plan['run_root']==str(U.ALPHA),'EXACT_ALPHA_PRODUCER_ROOT')
    U.need(plan['scope_parameters']==PARAMETERS and plan['kind']=='analysis' and plan['pilot'] is False and plan['cpus']==16
      and plan['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED' and 120<plan['wall_seconds']<=3600 and plan['output_cap_bytes']==U.CAP,'ALPHA_ANALYSIS16_NO_MEMORY_ONE_HOUR2GIB')
    argv=[plan['python'],'-B','-m','n1_sparse32_readchain_v1.alpha_read','--plan',str(pathlib.Path(plan_path).absolute()),'--startup-proof',str(pathlib.Path(proof_path).absolute())]
    U.need(plan['execution_argv']==argv and proof['request']=={'kind':'analysis','pilot':False,'cpus':16,'memory_policy':'SLURM_DEFAULT_UNSPECIFIED','wall_seconds':plan['wall_seconds'],'execution_argv':argv},'ACTUAL_ALPHA_REQUEST_ARGV')
    U.need(pathlib.Path(sys.modules['__main__'].__file__).absolute()==source and pathlib.Path(sys.executable).absolute()==pathlib.Path(plan['python'])
      and sys.argv[1:]==argv[4:],'ACTUAL_ALPHA_PRIMARY_AND_ALL_OPTIONS')
    node=socket.gethostname().split('.')[0]
    U.need(os.getuid()==proof['uid']==1264 and node==plan['node']==proof['node'] and node in Q.NODES and os.environ.get('SLURM_JOB_ID')==str(proof['job_id'])
      and proof['boot_id']==pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip() and 0<=time.time()-proof['observed_unix_seconds']<=120,'ACTUAL_NEW_ALPHA_UID_BOOT_NODE_JOB_FRESH')
    U.need(proof['memory_limits_requested'] is False and proof['exclusive_requested'] is False and os.environ.get('SLURM_JOB_PARTITION')=='cpu'
      and os.environ.get('SLURM_CPUS_PER_TASK')=='16' and os.environ.get('CUDA_VISIBLE_DEVICES')=='','ALPHA_REAL_CPU16_DEFAULT_MEMORY_NO_GPU')
    job=Q.fields(proof['job_metadata'])
    U.need(job.get('JobId')==str(proof['job_id']) and job.get('UserId')=='alpha(1264)' and job.get('JobState')=='RUNNING'
      and job.get('NodeList')==node and job.get('Partition')=='cpu' and job.get('NumCPUs')=='16' and job.get('NumTasks')=='1'
      and job.get('Requeue')=='0' and job.get('Command')==proof['script_reference']['path'] and Q.duration(job.get('TimeLimit',''))==plan['wall_seconds'],'ACTUAL_ALPHA_SLURM_SCRIPT_ALLOCATION')
    for line in U.require(proof['script_reference'],True).read_text().splitlines():
        if line.strip().startswith('#SBATCH'):U.need(not any(x in line for x in ('--mem','--exclusive','--gres','--gpu')),'NO_MEMORY_EXCLUSIVE_GPU_DIRECTIVES')
    gate=proof['actual_gate_process'];tail=pathlib.Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()
    U.need(gate['pid']==os.getpid() and gate['uid']==1264 and gate['start_ticks']==int(tail[19]) and gate['pgid']==os.getpgrp() and gate['sid']==os.getsid(0)
      and gate['cgroup_sha256']==hashlib.sha256(pathlib.Path('/proc/self/cgroup').read_bytes()).hexdigest(),'SAME_ATTESTED_ALPHA_EXEC_GATE')
    U.need(proof['plan_reference']==U.pin(plan_path,True) and proof['root_review_reference']==plan['root_review_reference'],'ACTUAL_ALPHA_PLAN_ROOT_REVIEW')
    review=U.load(plan['root_review_reference']);U.need(review['schema']=='EXACT_SECONDARY_BOUNDED_READONLY_ROOT_REVIEW_V1'
      and review['status']=='APPROVED_FOR_EXACT_STAGE' and review['reviewer']=='root','ROOT_EXACT_ALPHA_READONLY_REVIEW')
    for key in ('scope_key','scope_parameters','stage','endpoint','uid','run_root','node','cpus','memory_policy','pilot','wall_seconds','output_cap_bytes','execution_argv','data_references','parent_evidence_references'):
        U.need(plan[key]==review[key],'ALPHA_ROOT_REVIEW_DIFFERS:'+key)
    U.need(plan['source_references']==review['approved_source_references'],'ACTUAL_APPROVED_ALPHA_READCHAIN_SOURCES')
    U.need(not ({r['path'] for r in plan['data_references']}&{r['path'] for r in plan['source_references']}),'BODY_INPUTS_NOT_PRE_FIXTURE_SOURCE_HASHES')
    declared={r['path']:{k:r[k] for k in ('path','bytes','sha256')} for r in proof['source_target_verification']}
    for r in [*plan['source_references'],*plan['parent_evidence_references'],plan['root_review_reference'],U.pin(plan_path,True)]:
        U.need(declared.get(r['path'])==r,'ACTUAL_SOURCE_TARGET_PIN');U.require(r,True)
    for p in source.parent.iterdir():
        if p.suffix in ('.py','.md'):U.need(U.pin(p,True) in plan['source_references'],'EVERY_ALPHA_NEW_SOURCE')
    for r in [*plan['science_sources'].values(),plan['recipe_reference'],plan['original_recipe_reference'],plan['input_manifest_reference'],
        U.pin(Q.__file__,True),U.pin(pathlib.Path(Q.__file__).parent/'__init__.py',True)]:
        U.need(r in plan['source_references'],'EXPLICIT_ALPHA_READER_SOURCE_OR_METADATA')
    manifest=U.load(plan['input_manifest_reference']);U.need(manifest['schema']=='MAIN_N1_SPARSE32_EXACT_READCHAIN_EXPORT_V1'
      and manifest['status']=='ALL32_RAW_KV_EXPORTED_AND_REOPEN_VERIFIED_NO_GENERATION' and manifest['endpoint']=='202.38.247.57:22' and manifest['uid']==1278
      and manifest['node']=='compute-0-13' and manifest['scope_key']==MAIN_KEY and manifest['scope_parameters']==PARAMETERS
      and manifest['job_id'] not in ('4521417','4521418') and manifest['logical_record_count']==manifest['unique_molecule_count']==manifest['unique_KV_count']==32,
      'REAL_NEW_MAIN_RAW32_EXPORT_MANIFEST_NOT_ORIGINAL_CANONICAL_GENERATION')
    for key in ('main_export_accounting_reference','main_export_raw_sacct_reference'):
        U.need(plan[key] in plan['parent_evidence_references'],'EXACT_MAIN_EXPORT_C0_PARENT_COPY:'+key)
    account=U.load(plan['main_export_accounting_reference']);raw_origin=account['raw_sacct_reference']
    U.need(plan['main_export_accounting_reference']['bytes']==plan['main_export_accounting_origin_reference']['bytes']
      and plan['main_export_accounting_reference']['sha256']==plan['main_export_accounting_origin_reference']['sha256']
      and raw_origin['bytes']==plan['main_export_raw_sacct_reference']['bytes'] and raw_origin['sha256']==plan['main_export_raw_sacct_reference']['sha256'],
      'ORIGINAL_MAIN_ACCOUNTING_BYTES_UNCHANGED_ALPHA_COPIES')
    raw=U.require(plan['main_export_raw_sacct_reference'],True).read_text();rows=list(csv.DictReader(io.StringIO(raw),delimiter='|'))
    selected=[r for r in rows if r.get('JobIDRaw',r.get('JobID'))==manifest['job_id']]
    U.need(account['schema']=='DATA_V1_PARENT_ACCOUNTING_CLOSURE_V1' and account['status']=='ACTUAL_PARENT_ACCOUNTING_CLOSED'
      and account['query_returncode']==0 and len(selected)==1 and selected[0]['State']=='COMPLETED' and selected[0]['ExitCode']=='0:0'
      and selected[0]['UID']=='1278' and selected[0]['AllocCPUS']=='16' and selected[0]['NodeList']=='compute-0-13','ACTUAL_MAIN_EXPORT_C0_NOT_ALPHA_UID_OR_PROOF')
    U.need(plan['origin_manifest_reference']['bytes']==plan['input_manifest_reference']['bytes']
      and plan['origin_manifest_reference']['sha256']==plan['input_manifest_reference']['sha256'],'UNCHANGED_MAIN_MANIFEST_COPY_NOT_MAIN_FILE_IDENTITY')
    U.need(plan['data_references']==manifest['alpha_data_references'] and len(manifest['records'])==32
      and sum(r['bytes'] for r in plan['data_references'])<=U.CAP,'EXACT_INSTALLED_EXPECTED_BODY_LOCATORS_NO_FUTURE_VERIFICATION')
    U.need(plan['science_sources']==manifest['alpha_science_sources'] and plan['recipe_reference']==manifest['alpha_recipe_reference'],'EXPLICIT_READER_SOURCE_RELOCATION')
    U.need(plan['original_recipe_reference']==manifest['alpha_original_recipe_reference']
      and all(manifest['origin_recipe_reference'][k]==plan['original_recipe_reference'][k] for k in ('bytes','sha256')),'EXACT_ORIGINAL_RECIPE_BYTES_COPY')
    for row in manifest['science_source_copies']:
        U.need(row['origin_reference']['bytes']==row['alpha_target_locator']['bytes'] and row['origin_reference']['sha256']==row['alpha_target_locator']['sha256']
          and plan['science_sources'][row['name']]==row['alpha_target_locator'],'ORIGINAL_SCIENCE_SOURCE_BYTES_EQUAL_EXPLICIT_TARGET')
    original=U.load(plan['original_recipe_reference']);actual=U.load(plan['recipe_reference']);expected=copy.deepcopy(original)
    expected['science_source_pins']=[dict(original['science_source_pins'][0],path=plan['science_sources']['legacy']['path']),dict(original['science_source_pins'][1],path=plan['science_sources']['prepare']['path'])]
    expected['external_output_root']=str(U.ALPHA/'artifacts/n1_sparse32_readchain_v1')
    U.need(actual==expected,'ONLY_TWO_READER_SOURCE_LOCATORS_AND_OUTPUT_ROOT_IN_A_NEW_RECIPE')
    U.need(proof['account_free_bytes']-U.CAP>=200000000000,'FRESH_ALPHA_QUOTA200GB_PLUS_CAP')
    signer=proof['controller_evidence'];U.need(signer['endpoint']=='218.192.171.238:22' and signer['uid']==1264 and signer['hostname']=='sonmi'
      and signer['proof_is_not_created_by_scientific_worker'] is True and signer['actual_script_reference']==proof['script_reference'],'ACTUAL_ALPHA_LOGIN_CONTROLLER_NOT_MAIN_PROOF')
    storage=proof['storage_observation'];U.require(proof['storage_observation_reference'],True)
    U.need(storage['effective_free_bytes']==proof['account_free_bytes'] and storage['whole_output_caps_reserved_bytes']>=U.CAP
      and 0<=time.time()-storage['observed_unix_seconds']<=120,'FRESH_ALL_PENDING_CAPS_STORAGE')
    U.need(plan['transfer_verification_reference'] is None,'FUTURE_BODY_HASH_RECEIPT_NOT_PRECLAIMED')
    set_threads();return dict(plan,actual_proof_path=str(proof_path)),proof,manifest
