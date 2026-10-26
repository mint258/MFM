"""Only exact Alpha full normalization and Native72 invariants v2 protocols."""
import csv,io
from pathlib import Path
from secondary_cpu_queue_v1 import common as q
from secondary_cpu_queue_v1.common import ROOT,ENDPOINT,UID,POLICY,NODES,need,ref,load,load_ref,verify,normalized,literal,read_small

NORM_FULL_KEY='coconut_identity_norm_full_alpha_v1'
NATIVE_KEY='pprime_native72_invariants_readonly_alpha_v2'
PROTOCOLS={
 NORM_FULL_KEY:{'plan':'SECONDARY_COCONUT_IDENTITY_NORM_FULL_PLAN_V1','proof':'SECONDARY_COCONUT_IDENTITY_NORM_FULL_STARTUP_V1',
   'stage':'IDENTITY_KEY_NORMALIZATION_FULL','module':'secondary_coconut_identity_norm_full_v1.run'},
 NATIVE_KEY:{'plan':'SECONDARY_NATIVE72_INVARIANTS_READONLY_PLAN_V2','proof':'SECONDARY_NATIVE72_INVARIANTS_READONLY_STARTUP_V2',
   'stage':'PPRIME_NATIVE72_EXISTING_REPORT_INVARIANTS','module':'native72_invariants_alpha_v2.run'}}
HERE=ROOT/'code/secondary_cpu_readonly_queue_v7'
OLD=ROOT/'code/frame_native_precision_alpha_v2'
REVIEW_FIELDS=('scope_key','scope_parameters','stage','endpoint','uid','run_root','node','cpus','memory_policy',
    'pilot','wall_seconds','output_cap_bytes','execution_argv','data_references','parent_evidence_references')

NATIVE_PARAMETERS={'original_main_job_id':'4521124','source_diagnosis_job_id':'1884773',
    'retained_cases':72,'original_covariance_failures':15,'fixed_noisy_xtb_pair_groups':3,
    'input_bodies':2,'original_fixture_methods':4,'derived_fixture_methods':4,
    'all8_tests_must_pass_before_body_reads':True,'new_QM_calls':0,'new_UFF_calls':0,
    'raw_SQLite_reads':0,'original_inputs_read':0,'pilot':False,'production_membership':False,
    'original_failures_retained':True,'original_tolerances_changed':False,
    'coordinates_recomputed_from_raw':False,'coordinate_evidence':'RECORDED_INPUT_ORBITS_AND_OLD_OUTPUT_FRAME_METADATA',
    'arithmetic':'EXACT_FRACTION_OF_RECORDED_BINARY64_AND_NATIVE_DECIMAL_CENTERS',
    'maximum_atoms':80,'maximum_vector_fields':4,'maximum_report_bytes':8388608,
    'maximum_summary_bytes':262144,'whole_output_cap_bytes':33554432,
    'algorithm_rss_soft_cap_bytes':8589934592,'minimum_mem_available_bytes':4294967296,
    'wall_seconds':600,'dispatch_reserve_seconds':120,'full_or2000_QM_release':False,
    'automatic_scientific_PASS':False}
NATIVE_DATA=[{'path':str(ROOT/'artifacts/pprime_native72_readonly_v2/v1/native72_report.json'),
       'bytes':2456111,'sha256':'0720c0fec59631ab02b6b574bf00933b31bd62062a38052b12c9de8375b77c8f'},
      {'path':str(ROOT/'inputs/native72_v1/main/runs/data_v1_20261025/artifacts/vector_frame_audit/cpu_auto_memory_20261026_v1/frame_evaluation.json'),
       'bytes':766822,'sha256':'36732244c5bcdaddfec9e22be847f3244076fdb3594d0ab8a663fbc9b3b91725'}]
NATIVE_CONFIG={'path':str(ROOT/'inputs/native72_v1/main/runs/data_v1_20261025/repository/configs/data_v1/pprime/vector_frame_audit_root_v1.json'),
    'bytes':6165,'sha256':'17d579c09ead14f01c747ca40d70796af1df0e6619f5ddcba334d595d94ad8fe'}
NATIVE_SMALL_SUMMARY={'path':str(ROOT/'artifacts/pprime_native72_readonly_v2/v1/diagnosis_summary.json'),
    'bytes':14184,'sha256':'68741f9fe70fb5094741b0c9d6f7f6a2858703ffd423ba9b7f36b7c6d8892d6d'}
NATIVE_OLD_HELPERS=[{'path':str(OLD/name),'bytes':size,'sha256':sha} for name,size,sha in (
    ('precision.py',6476,'1de0073f2face3b0b40a70e5a95b7ef98b1c2ee1ed2746bb33ac79791f2986d2'),
    ('tokens.py',4657,'8b1e7fdf21a0fc77b0684727750f8d3cf9947a30ee2a5ff33fbf1e398fb529fc'),
    ('test_v2.py',4673,'7ea819eb20c9ada17768e937db86090961649d9a04d7d19f770d1afb119b96ec'),
    ('math_v1.py',9377,'98db545b56f87b4fb2fc4c0f7ad69c3e6f05ebbe507f4d19369a037599241e24'))]

COUNTS={'molecules':1140133,'entries':1799004};TOTAL=2939137
ENV={'python':'3.11.14','numpy':'2.2.6','RDKit':'2025.09.5','pyarrow':'17.0.0'}
PROFILE={
 '__init__.py':(84,'efd575f612865eb944b512c5910fe669eb5c08762d3117962c3b7384d7414376'),
 'contracts.py':(13615,'bc569267b5854959231f290f02848bb40ed0908d82b46ab4b18ce15917f1a827'),
 'runtime.py':(4377,'29d3ec8464e8bde5d66a718d6a8bb37ae78feaad8dfca063115f863af011848f'),
 'run.py':(20852,'62397760fc59718e965eb44c02b5e4bf7be81d2ca54ab3428aff551f8c2fe9a2')}

def full_parameters():
    return {'mode':'full','input_tables':['molecules','entries'],'expected_physical_rows_by_table':dict(COUNTS),
      'expected_physical_rows':TOTAL,'record_selection':'ALL_PARQUET_PHYSICAL_ROWS_ORIGINAL_ORDER','workers':16,'maximum_pending':32,
      'actual_profile_job_id':'1884785','environment':dict(ENV),'same_profile_function_objects':True,'same_three_profile_fixtures':True,
      'present_SMILES_variants_separately':True,'stored_full_keys_strict':False,'status_invalid_or_identity_filter':False,
      'raw_identity_rows_retained':True,'X_rules_or_features_called':False,'maximum_input_JSON_bytes_per_record':2*1024**2,
      'maximum_result_JSON_bytes_per_record':8*1024**2,'maximum_source_rowgroup_uncompressed_bytes':256*1024**2,
      'journal_part_maximum_rows':65536,'journal_part_maximum_bytes':256*1024**2,'Parquet_buffer_maximum_rows':16,
      'full_source_normalization_authorized':True,'global_identity_acceptance_or_pool_release':False,
      'algorithm_current_RSS_reference_bytes':48*1024**3,'runtime_MemAvailable_min_fraction':.15,'cost_overrun_action':'REPORT_AND_CONTINUE'}

def account(ref,job,node,parents):
    value=q.load_ref(ref);p=value['actual_parent'];raw_ref=value['raw_sacct_reference']
    need(ref in parents and raw_ref in parents and value['query_returncode']==0 and value['endpoint']==q.ENDPOINT and value['uid']==UID and
      p['JobIDRaw']==job and p['State']=='COMPLETED' and p['ExitCode']=='0:0' and p['UID']==str(UID) and p['AllocCPUS']=='16' and
      p['NodeList']==node and p['Partition']=='cpu','ACTUAL_C0_PARENT_ACCOUNT_REQUIRED')
    rows=list(csv.DictReader(io.StringIO(q.read_small(q.verify(raw_ref)).decode()),delimiter='|'));matching=[r for r in rows if r.get('JobIDRaw')==job]
    need(len(matching)==1 and all(matching[0][k]==p[k] for k in ('State','ExitCode','UID','ElapsedRaw','AllocCPUS','NodeList','Partition')) and
      value['allocated_core_seconds_observed']==16*int(p['ElapsedRaw']),'ACTUAL_RAW_SACCT_AND_ALLOCATION_COST_REQUIRED')
    return value

def triple(value):
    need(isinstance(value,dict) and set(value)=={'path','bytes','sha256'} and type(value['bytes']) is int and value['bytes']>=0
        and isinstance(value['sha256'],str) and len(value['sha256'])==64 and set(value['sha256'])<=set('0123456789abcdef'),
        'EXACT_BODY_LOCATOR_TRIPLE_REQUIRED_WITHOUT_LOGIN_BODY_READ')
    literal(value['path']);return value


def native_authority(plan):
    need(plan['data_references']==NATIVE_DATA,'ONLY_TWO_FIXED_EXISTING_NATIVE_REPORT_BODY_LOCATORS_ALLOWED')
    for value in (NATIVE_CONFIG,NATIVE_SMALL_SUMMARY,*NATIVE_OLD_HELPERS):
        need(value in plan['source_references'],'EXACT_EXISTING_NATIVE_SMALL_SOURCE_OR_HELPER_REQUIRED')
    return {'existing_report_bodies':2,'original_main_job_id':'4521124','source_diagnosis_job_id':'1884773',
        'original15FAIL_retained':True,'full_or2000_release':'HOLD','body_SHA_verified_by_login_controller':False}

def full_authority(plan,review):
    need(plan.get('mode')=='full' and plan['cost_decision_reference'] in plan['source_references']
        and review.get('actual_profile_cost_and_quality_reviewed') is True
        and review.get('all_physical_rows_including_no_key_authorized') is True,'EXACT_ACTUAL_PROFILE_COST_QUALITY_AND_ALL_ROWS_FULL_REVIEW_REQUIRED')
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
        ref=q.ref(ROOT/'code/secondary_coconut_identity_norm_profile_v1'/name)
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
    need(a['input_reference']['bytes']==37876914074
        and a['input_reference']['sha256']=='bb61f8e074f876beaaf251b9abe5b4334aebbda28717120ac482db39d58ced29'
        and len(a['inventory']['DDL_tables_seen'])==15
        and a['inventory']['source_bytes_consumed_at_record_boundary']==a['inventory']['source_bytes_read_including_read_ahead']==37876914074,
        'ACTUAL_FULL_SQL_SOURCE_SHA_BYTES_AND15_TABLE_EOF_REQUIRED')
    a_package=ROOT/'code/secondary_coconut_sql_identity_v1'
    a_kernel=[q.ref(a_package/name) for name in ('__init__.py','contracts.py','copy_text.py','run.py')]
    need(len(a['kernel_source_references'])==4 and all(value in a['kernel_source_references']
        and value in plan['source_references'] and value in a_plan['source_references'] for value in a_kernel),
        'EXACT_FOUR_FROZEN_A_KERNELS_APPROVED_BY_A_AND_FULL_REQUIRED')
    need(q.ref(ROOT/'code/workflows/expansion/identity_v2/readers_v2.py') in plan['source_references'],
        'ACTUAL_TRANSITIVE_FROZEN_READER_IMPORT_MUST_BE_PINNED')
    for path in (ROOT/'code/workflows',ROOT/'code/workflows/expansion',ROOT/'code/workflows/expansion/identity_v2'):
        initializer=path/'__init__.py'
        if initializer.is_file():need(q.ref(initializer) in plan['source_references'],'EVERY_ACTUAL_FROZEN_IMPORT_INITIALIZER_MUST_BE_PINNED')
    return {'actual_profile_receipt_reference':plan['accepted_profile_receipt_reference'],'actual_profile_job_id':'1884785',
        'actual_A_full_receipt_reference':plan['a_full_receipt_reference'],'actual_A_full_job_id':'1884772',
        'physical_rows_by_table':dict(COUNTS),'physical_rows':TOTAL,'body_SHA_verified_by_login_controller':False,
        'global_identity_acceptance_or_pool_release':False}

def readonly(input_path,deployment_path,node,seconds,**unused):
    need(deployment_path is None,'EXACT_V7_READONLY_PLAN_HAS_NO_DEPLOYMENT_WRAPPER')
    plan=load(input_path);refs={};key=plan.get('producer_key')
    need(key in PROTOCOLS,'ONLY_EXACT_NORM_FULL_OR_NATIVE2_INVARIANTS_PROTOCOL_ALLOWED')
    protocol=PROTOCOLS[key]
    need(plan.get('schema')==protocol['plan'] and plan.get('scope_key')==key and plan.get('stage')==protocol['stage']
        and plan.get('endpoint')==ENDPOINT and plan.get('uid')==UID and plan.get('run_root')==str(ROOT) and plan.get('node')==node
        and plan.get('cpus')==16 and plan.get('memory_policy')==POLICY and plan.get('kind','analysis')=='analysis' and plan.get('pilot') is False
        and type(plan.get('wall_seconds')) is int and plan['wall_seconds']==seconds and 0<seconds<=172800 and seconds%60==0,
        'EXACT_ALPHA_CPU16_NO_MEMORY_V7_READONLY_RESOURCE_PLAN_REQUIRED')
    if key==NORM_FULL_KEY:
        need(plan.get('mode')=='full' and plan.get('scope_parameters')==full_parameters()
            and plan.get('output_cap_bytes')==32<<30,'EXACT_ALL2939137_PHYSICAL_ROWS_FULL_NORMALIZATION_SCOPE_REQUIRED')
    else:
        need(seconds==600 and plan.get('scope_parameters')==NATIVE_PARAMETERS and plan.get('output_cap_bytes')==32<<20
            and plan.get('data_references')==NATIVE_DATA,'EXACT_NATIVE2_SAME_SCIENTIFIC_INVARIANTS_SCOPE_REQUIRED')
    review=load_ref(plan['root_review_reference'])
    need(review.get('schema')=='EXACT_SECONDARY_BOUNDED_READONLY_ROOT_REVIEW_V1'
        and review.get('status')=='APPROVED_FOR_EXACT_STAGE' and review.get('reviewer')=='root'
        and review.get('kind','analysis')=='analysis','EXACT_V7_READONLY_ROOT_REVIEW_REQUIRED')
    for field in REVIEW_FIELDS:need(plan[field]==review[field],'EXACT_V7_ROOT_SCOPE_DIFFERS:'+field)
    need(plan['source_references']==review['approved_source_references'],'EXACT_V7_REVIEWED_SOURCE_SET_REQUIRED')
    bodies=plan['data_references'];need(isinstance(bodies,list) and len(bodies)==2,'EXACT_V7_TWO_READONLY_BODY_LOCATORS_REQUIRED')
    body_paths={triple(value)['path'] for value in bodies}
    need(len(body_paths)==2 and not any(value['path'] in body_paths for value in
        [*plan['source_references'],*plan['parent_evidence_references']]),'NO_BODY_MAY_BE_READ_AS_STARTUP_SOURCE_OR_PARENT_METADATA')
    for value in [*plan['source_references'],*plan['parent_evidence_references'],ref(input_path),plan['root_review_reference']]:
        value=normalized(value);verify(value)
        need(value['path'] not in refs or refs[value['path']]==value,'CONFLICTING_V7_SMALL_SOURCE_REFERENCE')
        refs[value['path']]=value
    for name in ('controller.py','adapters.py'):
        need(ref(HERE/name) in plan['source_references'],'ACTUAL_V7_CONTROLLER_AND_ADAPTER_SOURCES_MUST_BE_APPROVED')
    need(ref(Path(__file__).absolute()) in plan['source_references'],'ACTUAL_V7_ADAPTER_SOURCE_REQUIRED')
    primary=ROOT/'code'/Path(protocol['module'].replace('.','/')+'.py')
    for path in primary.parent.iterdir():
        if path.is_file() and path.suffix in {'.py','.json','.md'}:
            need(ref(path) in plan['source_references'],'EVERY_NEW_V7_CONSUMER_SOURCE_MUST_BE_APPROVED:'+path.name)
    for path in (primary,ROOT/'code/secondary_cpu_queue_v1/common.py',ROOT/'code/secondary_cpu_queue_v1/__init__.py'):
        need(ref(path) in plan['source_references'],'EXACT_V7_PRIMARY_AND_IMPORTED_BASE_SOURCES_REQUIRED')
    need(plan['resource_authority_reference'] in plan['source_references'],'ACTUAL_ALPHA_RESOURCE_AUTHORITY_MUST_BE_APPROVED')
    proof=literal(plan['startup_proof_path']);out=literal(plan['output_directory'])
    need(ROOT/'artifacts' in out.parents,'NEW_ALPHA_V7_READONLY_ARTIFACT_CHILD_REQUIRED')
    argv=[plan['python'],'-B','-m',protocol['module'],'--plan',str(Path(input_path)),'--startup-proof',str(proof)]
    need(plan['execution_argv']==argv and Path(argv[0]).is_absolute(),'EXACT_V7_MODULE_AND_COMPLETE_EIGHT_ARGV_REQUIRED')
    archive=full_authority(plan,review) if key==NORM_FULL_KEY else native_authority(plan)
    return {'producer':'readonly','input_reference':ref(input_path),'producer_argv':argv,
        'producer_plan_reference':ref(input_path),'producer_review_reference':plan['root_review_reference'],
        'producer_authority_reference':plan['resource_authority_reference'],'source_references':list(refs.values()),
        'data_reference_locators_only':bodies,'data_body_hashes_claimed_by_controller':False,
        'startup_proof_path':str(proof),'science_output':str(out),'output_cap_bytes':plan['output_cap_bytes'],
        'producer_working_directory':str(ROOT/'code'),'proof_schema':protocol['proof'],
        'request_kind':'analysis','pilot':False,'scope_key':key,'scope_parameters':plan['scope_parameters'],
        'stage':plan['stage'],'scope_mode':'BOUNDED_READONLY_ANALYSIS','performance_profile':False,'fixed_archive_authority':archive}

def startup_proof(request,jid,raw,job,probe,storage,storage_reference,controller_evidence):
    adapter=request['adapter']
    need(adapter['producer']=='readonly' and adapter['scope_key'] in PROTOCOLS and request['kind']==adapter['request_kind']=='analysis'
        and request['pilot'] is adapter['pilot'] and request['scope_key']==adapter['scope_key']
        and request['scope_parameters']==adapter['scope_parameters'] and request['stage']==adapter['stage']
        and request['scope_mode']==adapter['scope_mode'] and request['performance_profile'] is adapter['performance_profile'],
        'ONLY_EXACT_NORM_FULL_OR_NATIVE2_INVARIANTS_REQUEST_PROTOCOL_ALLOWED')
    return {'schema':adapter['proof_schema'],'endpoint':ENDPOINT,'uid':UID,'node':request['node'],
        'boot_id':probe['boot_id'],'job_id':str(jid),'observed_unix_seconds':probe['observed_unix_seconds'],
        'memory_policy':POLICY,'memory_limits_requested':False,'exclusive_requested':False,
        'script_reference':request['script_reference'],'controller_evidence':controller_evidence,
        'source_target_verification':request['verified_target_references'],
        'actual_gate_process':probe['gate_process'],'actual_memory_environment':probe['actual_memory_environment'],
        'scheduler_memory_is_recorded_not_an_admission_threshold':True,
        'other_jobs_modified':False,'forced_signals_sent':False,'job_metadata':raw,
        'request':{'kind':'analysis','pilot':adapter['pilot'],'cpus':16,'memory_policy':POLICY,
                   'wall_seconds':request['wall_seconds'],'execution_argv':adapter['producer_argv']},
        'plan_reference':adapter['producer_plan_reference'],'root_review_reference':adapter['producer_review_reference'],
        'account_free_bytes':storage['effective_free_bytes'],'effective_free_basis':storage['effective_free_basis'],
        'storage_observation_reference':storage_reference,'storage_observation':storage,
        'scope_key':adapter['scope_key'],'stage':adapter['stage'],'scope_mode':adapter['scope_mode'],
        'performance_profile':adapter['performance_profile'],'bounded_readonly_scope_only':True,
        'bounded_source_acquisition_scope_only':False,'scientific_population_or_full_SQL_status_coverage_accepted':False}

