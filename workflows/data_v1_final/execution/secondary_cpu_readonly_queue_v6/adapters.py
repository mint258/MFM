"""Only exact Alpha normalization profile and existing Native72 invariants."""
import csv,io,re
from pathlib import Path
from secondary_cpu_queue_v1.common import ROOT,ENDPOINT,UID,POLICY,NODES,need,ref,load,load_ref,verify,normalized,literal,read_small

NORM_KEY='coconut_identity_norm_profile_alpha_v1'
NATIVE_KEY='pprime_native72_invariants_readonly_alpha_v1'
PROTOCOLS={
 NORM_KEY:{'plan':'SECONDARY_COCONUT_IDENTITY_NORM_PROFILE_PLAN_V1','proof':'SECONDARY_COCONUT_IDENTITY_NORM_PROFILE_STARTUP_V1',
   'stage':'IDENTITY_KEY_NORMALIZATION_PROFILE','module':'secondary_coconut_identity_norm_profile_v1.run'},
 NATIVE_KEY:{'plan':'SECONDARY_NATIVE72_INVARIANTS_READONLY_PLAN_V1','proof':'SECONDARY_NATIVE72_INVARIANTS_READONLY_STARTUP_V1',
   'stage':'PPRIME_NATIVE72_EXISTING_REPORT_INVARIANTS','module':'native72_invariants_alpha_v1.run'}}
HERE=ROOT/'code/secondary_cpu_readonly_queue_v6'
OLD=ROOT/'code/frame_native_precision_alpha_v2'
REVIEW_FIELDS=('scope_key','scope_parameters','stage','endpoint','uid','run_root','node','cpus','memory_policy',
    'pilot','wall_seconds','output_cap_bytes','execution_argv','data_references','parent_evidence_references')
FROZEN={'projection':('workflows/expansion/identity_v2/projection_v2.py',8616,'7da54ccb4488950fb567c17cfa161bc339d8a377f2e2fb27362434ce88516d28'),
 'common':('workflows/expansion/common.py',4312,'8c988f617776ad05354deae1cf69933e7ff95210f7a2609f903e4826172ccbad')}

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

def norm_parameters(version):
    need(isinstance(version,str) and re.fullmatch(r'3\.[0-9]+\.[0-9]+',version),'EXPLICIT_ACTUAL_SAMPLER_PYTHON_VERSION_REQUIRED')
    return {'mode':'profile','sample_tables':['molecules','entries'],'maximum_sample_rows_per_table':10000,'seed':20261026,
      'ordinal_sampler':'PY_RANDOM_SAMPLE_SORTED_TABLE_SHA256_SEED_V1','sampler_python_version':version,'workers':16,'maximum_pending':32,
      'RDKit_version':'2025.09.5','present_SMILES_variants_separately':True,'stored_full_keys_strict':False,
      'status_invalid_or_identity_filter':False,'raw_identity_rows_retained':True,'X_rules_or_features_called':False,
      'maximum_input_JSON_bytes_per_record':2*1024**2,'maximum_result_JSON_bytes_per_record':8*1024**2,
      'maximum_source_rowgroup_uncompressed_bytes':256*1024**2,'full_source_normalization_authorized':False,
      'algorithm_current_RSS_reference_bytes':48*1024**3,'runtime_MemAvailable_min_fraction':.15,'cost_overrun_action':'REPORT_AND_CONTINUE'}


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


def norm_authority(plan,review):
    need(plan.get('sampler_python_version')=='3.11.14' and plan.get('mode')=='profile',
        'ACTUAL_ALPHA_PY31114_SAMPLER_PROFILE_ONLY')
    need(plan['cost_decision_reference'] in plan['source_references'],'EXACT_COST_AUTHORITY_SOURCE_REQUIRED')
    for key in ('a_full_receipt_reference','a_full_accounting_reference','a_full_plan_reference','a_full_startup_proof_reference'):
        need(plan[key] in plan['parent_evidence_references'],'ACTUAL_A1884772_FULL_PARENT_REQUIRED:'+key)
    a=load_ref(plan['a_full_receipt_reference'])
    need(a.get('schema')=='SECONDARY_COCONUT_SQL_IDENTITY_INVENTORY_RECEIPT_V1' and a.get('mode')=='full'
        and a.get('status')=='FULL_SQL_PHYSICAL_IDENTITY_FIELD_INVENTORY_COMPLETE' and a.get('endpoint')==ENDPOINT
        and a.get('uid')==UID and a.get('job_id')=='1884772'
        and a['input_reference']['bytes']==37876914074
        and a['input_reference']['sha256']=='bb61f8e074f876beaaf251b9abe5b4334aebbda28717120ac482db39d58ced29'
        and a.get('all_statuses_classes_invalid_and_NULL_rows_retained') is True
        and a['plan']==plan['a_full_plan_reference'] and a['startup_proof']==plan['a_full_startup_proof_reference'],
        'ACTUAL_A1884772_COMPLETE_SQL_IDENTITY_RECEIPT_NOT_PREFIX_PROFILE_REQUIRED')
    details=a['inventory']
    need(details.get('current_full_SQL_SHA_reverified') is True and details.get('full_EOF_and_all_tables_proven') is True
        and len(details['DDL_tables_seen'])==15
        and details['source_bytes_consumed_at_record_boundary']==details['source_bytes_read_including_read_ahead']==37876914074
        and details['reconciliation'].get('no_status_or_invalid_class_filtered') is True and a['input_before']==a['input_after'],
        'ACTUAL_A_FULL_EOF_STATUS_CONSERVATION_AND_UNCHANGED_INPUT_REQUIRED')
    ap=load_ref(plan['a_full_plan_reference']);sp=load_ref(plan['a_full_startup_proof_reference'])
    a_module='secondary_coconut_sql_identity_v1.run';a_key='coconut_sql_identity_inventory_alpha_v1'
    a_argv=[ap['python'],'-B','-m',a_module,'--plan',plan['a_full_plan_reference']['path'],'--startup-proof',plan['a_full_startup_proof_reference']['path']]
    need(ap.get('schema')=='SECONDARY_COCONUT_SQL_IDENTITY_INVENTORY_PLAN_V1'
        and ap.get('producer_key')==ap.get('scope_key')==a_key and ap.get('mode')=='full' and ap.get('pilot') is False
        and ap.get('stage')=='SQL_IDENTITY_PROJECTION_FULL' and ap.get('endpoint')==ENDPOINT and ap.get('uid')==UID
        and ap.get('run_root')==str(ROOT) and ap.get('node')==a['node'] and ap.get('node') in NODES
        and ap.get('cpus')==16 and ap.get('memory_policy')==POLICY
        and ap.get('execution_argv')==a_argv and ap.get('startup_proof_path')==plan['a_full_startup_proof_reference']['path']
        and ap.get('data_references')==[a['input_reference']]
        and ap['scope_parameters'].get('mode')=='full' and ap['scope_parameters'].get('profile_limit_bytes')==0,
        'ACTUAL_A_PARENT_PLAN_MUST_BE_FULL_SQL_PHASE_WITH_EXACT_INPUT_AND_ARGV')
    need(type(ap.get('wall_seconds')) is int and 0<ap['wall_seconds']<=172800 and ap['wall_seconds']%60==0
        and sp.get('schema')=='SECONDARY_COCONUT_SQL_IDENTITY_INVENTORY_STARTUP_V1' and sp.get('job_id')=='1884772'
        and sp.get('endpoint')==ENDPOINT and sp.get('uid')==UID and sp.get('node')==ap['node']
        and sp.get('scope_key')==a_key and sp.get('stage')=='SQL_IDENTITY_PROJECTION_FULL'
        and sp.get('plan_reference')==plan['a_full_plan_reference'] and sp.get('root_review_reference')==ap['root_review_reference']
        and sp.get('memory_limits_requested') is False and sp.get('exclusive_requested') is False
        and sp.get('request')=={'kind':'analysis','pilot':False,'cpus':16,'memory_policy':POLICY,
            'wall_seconds':ap['wall_seconds'],'execution_argv':a_argv},'ACTUAL_A1884772_STARTUP_FULL_PHASE_IDENTITY_REQUIRED')
    account=load_ref(plan['a_full_accounting_reference']);parent=account['actual_parent']
    need(account.get('query_returncode')==0 and account.get('uid')==UID and account.get('endpoint')==ENDPOINT
        and parent.get('JobIDRaw')==a['job_id'] and parent.get('State')=='COMPLETED' and parent.get('ExitCode')=='0:0'
        and parent.get('UID')==str(UID) and parent.get('AllocCPUS')=='16' and parent.get('Partition')=='cpu'
        and parent.get('NodeList')==ap['node'],'ACTUAL_A1884772_C0_CPU16_PARENT_AND_NODE_REQUIRED')
    need(account['raw_sacct_reference'] in plan['parent_evidence_references'],'ACTUAL_A_RAW_SACCT_MUST_BE_PARENT_PIN')
    raw=list(csv.DictReader(io.StringIO(read_small(verify(account['raw_sacct_reference'])).decode()),delimiter='|'))
    matches=[x for x in raw if x.get('JobIDRaw')==a['job_id']]
    need(len(matches)==1 and all(matches[0].get(k)==parent.get(k) for k in
        ('State','ExitCode','UID','ElapsedRaw','AllocCPUS','NodeList','Partition'))
        and account.get('allocated_core_seconds_observed')==int(parent['ElapsedRaw'])*16
        and review.get('actual_A_full_cost_and_identity_projection_reviewed') is True,'ACTUAL_A_RAW_ACCOUNT_COST_AND_ROOT_REVIEW_REQUIRED')
    wanted=[]
    for table in ('molecules','entries'):
        found=[row for row in a['physical_output_references'] if Path(row['path']).name==table+'.raw_identity.parquet']
        need(len(found)==1 and details['physical_COPY_rows_by_table'][table]==details['reconciliation']['projected_rows_by_table'][table]>0,
            'ONE_EXACT_ACTUAL_A_POSITIVE_ROWCOUNT_OUTPUT_PER_TABLE_REQUIRED')
        wanted.append(triple(found[0]))
    need(plan['data_references']==wanted,'ONLY_ACTUAL_A_FULL_MOLECULES_AND_ENTRIES_BODY_LOCATORS_ALLOWED')
    package=ROOT/'code/secondary_coconut_sql_identity_v1'
    kernels=[ref(package/name) for name in ('__init__.py','contracts.py','copy_text.py','run.py')]
    need(len(a['kernel_source_references'])==4 and all(value in a['kernel_source_references']
        and value in plan['source_references'] and value in ap['source_references'] for value in kernels),
        'ACTUAL_A_EXACT_FOUR_FROZEN_KERNEL_SOURCES_APPROVED_BY_B_AND_HISTORICAL_A_REQUIRED')
    need(ref(ROOT/'code/workflows/expansion/identity_v2/readers_v2.py') in plan['source_references'],
        'ACTUAL_FROZEN_PROJECTION_TRANSITIVE_READER_IMPORT_MUST_BE_PINNED')
    for name,(relative,size,sha) in FROZEN.items():
        value=plan['frozen_identity_source_references'][name]
        need(value in plan['source_references'] and value['path']==str(ROOT/'code'/relative)
            and value['bytes']==size and value['sha256']==sha,'ACTUAL_UNCHANGED_FROZEN_IDENTITY_SOURCE:'+name)
        for parent_path in (ROOT/'code/workflows',*(ROOT/'code'/relative).parents):
            if parent_path==ROOT/'code':break
            initializer=parent_path/'__init__.py'
            if initializer.is_file():need(ref(initializer) in plan['source_references'],'EVERY_ACTUAL_FROZEN_IMPORT_INITIALIZER_MUST_BE_PINNED')
    return {'a_full_receipt_reference':plan['a_full_receipt_reference'],'a_full_job_id':'1884772','raw_identity_tables':['molecules','entries'],
        'sampler_python_version':'3.11.14','full_source_normalization_authorized':False,'body_SHA_verified_by_login_controller':False}


def readonly(input_path,deployment_path,node,seconds,**unused):
    need(deployment_path is None,'EXACT_V6_READONLY_PLAN_HAS_NO_DEPLOYMENT_WRAPPER')
    plan=load(input_path);refs={};key=plan.get('producer_key')
    need(key in PROTOCOLS,'ONLY_EXACT_NORM_PROFILE_OR_NATIVE_INVARIANTS_PROTOCOL_ALLOWED')
    protocol=PROTOCOLS[key]
    need(plan.get('schema')==protocol['plan'] and plan.get('scope_key')==key and plan.get('stage')==protocol['stage']
        and plan.get('endpoint')==ENDPOINT and plan.get('uid')==UID and plan.get('run_root')==str(ROOT) and plan.get('node')==node
        and plan.get('cpus')==16 and plan.get('memory_policy')==POLICY and plan.get('kind','analysis')=='analysis'
        and type(plan.get('wall_seconds')) is int and plan['wall_seconds']==seconds and 0<seconds<=14400 and seconds%60==0,
        'EXACT_ALPHA_CPU16_NO_MEMORY_V6_READONLY_RESOURCE_PLAN_REQUIRED')
    pilot=key==NORM_KEY
    need(plan.get('pilot') is pilot,'EXACT_V6_PROFILE_OR_READONLY_PILOT_MARKER_REQUIRED')
    if pilot:
        need(plan.get('scope_parameters')==norm_parameters('3.11.14') and plan.get('sampler_python_version')=='3.11.14'
            and plan.get('mode')=='profile' and plan.get('output_cap_bytes')==2<<30,'EXACT_ACTUAL_PY31114_NORMALIZATION_PROFILE_SCOPE_REQUIRED')
    else:
        need(seconds==600 and plan.get('scope_parameters')==NATIVE_PARAMETERS and plan.get('output_cap_bytes')==32<<20
            and plan.get('data_references')==NATIVE_DATA,'EXACT_FIXED_NATIVE72_INVARIANTS_SCOPE_REQUIRED')
    review=load_ref(plan['root_review_reference'])
    need(review.get('schema')=='EXACT_SECONDARY_BOUNDED_READONLY_ROOT_REVIEW_V1'
        and review.get('status')=='APPROVED_FOR_EXACT_STAGE' and review.get('reviewer')=='root'
        and review.get('kind','analysis')=='analysis','EXACT_V6_READONLY_ROOT_REVIEW_REQUIRED')
    for field in REVIEW_FIELDS:need(plan[field]==review[field],'EXACT_V6_ROOT_SCOPE_DIFFERS:'+field)
    need(plan['source_references']==review['approved_source_references'],'EXACT_V6_REVIEWED_SOURCE_SET_REQUIRED')
    bodies=plan['data_references'];need(isinstance(bodies,list) and len(bodies)==2,'EXACT_V6_TWO_READONLY_BODY_LOCATORS_REQUIRED')
    body_paths={triple(value)['path'] for value in bodies}
    need(len(body_paths)==2 and not any(value['path'] in body_paths for value in
        [*plan['source_references'],*plan['parent_evidence_references']]),'NO_BODY_MAY_BE_READ_AS_STARTUP_SOURCE_OR_PARENT_METADATA')
    for value in [*plan['source_references'],*plan['parent_evidence_references'],ref(input_path),plan['root_review_reference']]:
        value=normalized(value);verify(value)
        need(value['path'] not in refs or refs[value['path']]==value,'CONFLICTING_V6_SMALL_SOURCE_REFERENCE')
        refs[value['path']]=value
    for name in ('controller.py','adapters.py'):
        need(ref(HERE/name) in plan['source_references'],'ACTUAL_V6_CONTROLLER_AND_ADAPTER_SOURCES_MUST_BE_APPROVED')
    need(ref(Path(__file__).absolute()) in plan['source_references'],'ACTUAL_V6_ADAPTER_SOURCE_REQUIRED')
    primary=ROOT/'code'/Path(protocol['module'].replace('.','/')+'.py')
    for path in primary.parent.iterdir():
        if path.is_file() and path.suffix in {'.py','.json','.md'}:
            need(ref(path) in plan['source_references'],'EVERY_NEW_V6_CONSUMER_SOURCE_MUST_BE_APPROVED:'+path.name)
    for path in (primary,ROOT/'code/secondary_cpu_queue_v1/common.py',ROOT/'code/secondary_cpu_queue_v1/__init__.py'):
        need(ref(path) in plan['source_references'],'EXACT_V6_PRIMARY_AND_IMPORTED_BASE_SOURCES_REQUIRED')
    need(plan['resource_authority_reference'] in plan['source_references'],'ACTUAL_ALPHA_RESOURCE_AUTHORITY_MUST_BE_APPROVED')
    proof=literal(plan['startup_proof_path']);out=literal(plan['output_directory'])
    need(ROOT/'artifacts' in out.parents,'NEW_ALPHA_V6_READONLY_ARTIFACT_CHILD_REQUIRED')
    argv=[plan['python'],'-B','-m',protocol['module'],'--plan',str(Path(input_path)),'--startup-proof',str(proof)]
    need(plan['execution_argv']==argv and Path(argv[0]).is_absolute(),'EXACT_V6_MODULE_AND_COMPLETE_EIGHT_ARGV_REQUIRED')
    archive=norm_authority(plan,review) if pilot else native_authority(plan)
    return {'producer':'readonly','input_reference':ref(input_path),'producer_argv':argv,
        'producer_plan_reference':ref(input_path),'producer_review_reference':plan['root_review_reference'],
        'producer_authority_reference':plan['resource_authority_reference'],'source_references':list(refs.values()),
        'data_reference_locators_only':bodies,'data_body_hashes_claimed_by_controller':False,
        'startup_proof_path':str(proof),'science_output':str(out),'output_cap_bytes':plan['output_cap_bytes'],
        'producer_working_directory':str(ROOT/'code'),'proof_schema':protocol['proof'],
        'request_kind':'analysis','pilot':pilot,'scope_key':key,'scope_parameters':plan['scope_parameters'],
        'stage':plan['stage'],'scope_mode':'BOUNDED_PERFORMANCE_BATCH' if pilot else 'BOUNDED_READONLY_ANALYSIS',
        'performance_profile':pilot,'fixed_archive_authority':archive}


def startup_proof(request,jid,raw,job,probe,storage,storage_reference,controller_evidence):
    adapter=request['adapter']
    need(adapter['producer']=='readonly' and adapter['scope_key'] in PROTOCOLS and request['kind']==adapter['request_kind']=='analysis'
        and request['pilot'] is adapter['pilot'] and request['scope_key']==adapter['scope_key']
        and request['scope_parameters']==adapter['scope_parameters'] and request['stage']==adapter['stage']
        and request['scope_mode']==adapter['scope_mode'] and request['performance_profile'] is adapter['performance_profile'],
        'ONLY_EXACT_NORM_PROFILE_OR_NATIVE_INVARIANTS_REQUEST_PROTOCOL_ALLOWED')
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
