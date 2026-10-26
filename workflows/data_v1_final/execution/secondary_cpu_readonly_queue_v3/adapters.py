"""Only three exact Alpha readonly protocols; existing v1 gate/probe remain unchanged."""
from collections import Counter
from pathlib import Path
from secondary_cpu_queue_v1.common import ROOT,ENDPOINT,UID,POLICY,need,ref,load,load_ref,verify,normalized,literal

PROTOCOLS={
 'pprime_native_precision72_readonly_alpha_v1':{
  'plan':'SECONDARY_NATIVE72_READONLY_PLAN_V1','proof':'SECONDARY_NATIVE72_READONLY_STARTUP_V1',
  'stage':'PPRIME_NATIVE72_EXISTING_OUTPUT_DIAGNOSIS','module':'frame_native_precision_alpha_v1.run'},
 'coconut_sql_identity_inventory_alpha_v1':{
  'plan':'SECONDARY_COCONUT_SQL_IDENTITY_INVENTORY_PLAN_V1','proof':'SECONDARY_COCONUT_SQL_IDENTITY_INVENTORY_STARTUP_V1',
  'stage':None,'module':'secondary_coconut_sql_identity_v1.run'},
 'pubchem_original_raw_copy_validation_alpha_v1':{
  'plan':'SECONDARY_PUBLIC_RAW_PIN_VALIDATION_PLAN_V1','proof':'SECONDARY_PUBLIC_RAW_PIN_VALIDATION_STARTUP_V1',
  'stage':'PUBLIC_RAW_COPY_SHA_GZIP_EOF','module':'secondary_pubchem_raw_validation_v1'}}
HERE=ROOT/'code/secondary_cpu_readonly_queue_v3'
SQL_BYTES=37876914074;RAW_BYTES=1488715010
RAW_SHA='2504bc00da1b0587ae208d8a5fb2a4fe6043c215436150f2023d59c57c5cd2b7'
NATIVE_PARAMETERS={'original_job_id':'4521124','retained_cases':72,'original_covariance_failures':15,'new_QM_calls':0,
    'synthetic_test_methods':4,'all4_tests_must_pass_before_raw_reads':True,'pilot':False,'production_membership':False,
    'native_raw_read_only':True,'bounded_gzip_decompression':True,'precision_arithmetic':'EXACT_FRACTION',
    'maximum_report_bytes':2097152,'algorithm_rss_soft_cap_bytes':8589934592,'minimum_mem_available_bytes':4294967296,
    'readback_endpoint':'218.192.171.238:22','readback_uid':1264,'origin_endpoint':'202.38.247.57:22',
    'Main_runtime_proof_reused':False,'original_JSON_paths_rewritten':False,'full_or2000_QM_release':False,
    'exact_database_files':72,'exact_case_result_files':72,'exact_input_files':288,
    'hash_basis':'FROZEN_PER_CALL_SHA_AND_INPUT_METADATA'}
RAW_PARAMETERS={'main_acquisition_job_id':'4520348','main_inventory_job_id':'4521093',
    'compressed_bytes':RAW_BYTES,'compressed_sha256':RAW_SHA,'uncompressed_bytes':8880849781,'physical_rows':124857440,
    'single_stream_reader':True,'new_network_requests':0,'chemical_parsing':False,
    'population_members_added':0,'feature_profile_authorized':False}
NATIVE_KINDS={'source_byte_copy':6,'main_diagnostic_provenance':3,'frozen_function_source':12,'small_metadata':7,
    'raw_sqlite_locator_no_main_SHA':72,'pinned_case_result_metadata':72,
    'actual_input_stat_locator':144,'prepared_input_stat_locator':144}
REVIEW_FIELDS=('scope_key','scope_parameters','stage','endpoint','uid','run_root','node','cpus','memory_policy',
    'pilot','wall_seconds','output_cap_bytes','execution_argv','data_references','parent_evidence_references')


def triple(value):
    need(isinstance(value,dict) and set(value)=={'path','bytes','sha256'} and type(value['bytes']) is int and value['bytes']>=0
        and isinstance(value['sha256'],str) and len(value['sha256'])==64 and set(value['sha256'])<=set('0123456789abcdef'),
        'EXACT_DATA_LOCATOR_TRIPLE_REQUIRED_WITHOUT_BODY_READ')
    literal(value['path']);return value


def sql_parameters(mode,limit):
    need(mode in ('profile','full') and type(limit) is int and
        (16*1024**2<=limit<SQL_BYTES if mode=='profile' else limit==0),'EXACT_FINITE_SQL_IDENTITY_PHASE_LIMIT_REQUIRED')
    return {'mode':mode,'profile_limit_bytes':limit,'stop_at_complete_logical_record':True,
        'maximum_profile_boundary_overshoot_bytes':64*1024**2,'maximum_selected_field_bytes':1024**2,
        'input_chunk_bytes':1024**2,'SQL_metadata_statement_cap_bytes':1024**2,
        'decode_or_persist_nonidentity_values':False,'execute_downloaded_SQL':False,'chemical_normalization':False,
        'all_physical_statuses_and_invalid_entries_retained':True,'unpublished_hard_deleted_history_required':False,
        'algorithm_self_RSS_softcap_bytes':2*1024**3,'runtime_MemAvailable_min_fraction':.15,
        'cost_overrun_action':'REPORT_AND_CONTINUE'}


def native_archive_authority(plan):
    """Check all460 frozen metadata locators; never open a DB/input body on login."""
    map_ref=plan['relocation_map_reference']
    need(plan.get('archive_locator_authority_reference')==map_ref and map_ref in plan['source_references'],
        'EXACT_REVIEWED_TRANSITIVE_NATIVE72_ARCHIVE_AUTHORITY_REQUIRED')
    mapping=load_ref(map_ref)
    need(mapping.get('schema')=='NATIVE72_READONLY_RELOCATION_MAP_V1','EXACT_NATIVE72_RELOCATION_SCHEMA_REQUIRED')
    inventory_path=ROOT/'code/frame_native_precision_alpha_v1/origin_inventory.json'
    inventory_ref=ref(inventory_path)
    need(mapping.get('origin_inventory_reference')==inventory_ref and inventory_ref in plan['source_references'],
        'EXACT_REVIEWED_NATIVE72_FROZEN_INVENTORY_REQUIRED')
    inventory=load_ref(inventory_ref)
    need(inventory.get('schema')=='NATIVE72_MAIN_TO_ALPHA_ORIGIN_INVENTORY_V1'
        and inventory.get('main_endpoint')=='202.38.247.57:22' and inventory.get('alpha_endpoint')==ENDPOINT
        and inventory.get('alpha_root')==str(ROOT),'INDEPENDENT_ALPHA_NATIVE72_ORIGIN_INVENTORY_REQUIRED')
    expected={row['origin']['path']:row for row in inventory['entries']};entries=mapping['entries']
    need(len(expected)==len(inventory['entries'])==len(entries)==460,'EXACT_UNIQUE_NATIVE72_FULL460_MAPPING_REQUIRED')
    need(dict(Counter(row['kind'] for row in inventory['entries']))==NATIVE_KINDS
        and dict(Counter(row['kind'] for row in entries))==NATIVE_KINDS,'EXACT72_DB72_RESULT288_INPUT28_SMALL_METADATA_SET_REQUIRED')
    origins=set();targets=set();main=Path('/share/home/zixiao/descriptor_analysis')
    no_sha={'raw_sqlite_locator_no_main_SHA','actual_input_stat_locator','prepared_input_stat_locator'}
    source_kinds={'source_byte_copy','main_diagnostic_provenance','frozen_function_source','small_metadata'}
    for row in entries:
        origin=row['origin'];target=row['target_reference'];old=origin['path'];new=target['path']
        need(old in expected and old not in origins and new not in targets,'UNIQUE_FROZEN_NATIVE72_ORIGIN_AND_TARGET_SET_REQUIRED')
        frozen=expected[old]
        need(origin==frozen['origin'] and row['kind']==frozen['kind'] and new==frozen['target_locator']
            and row.get('origin_stat')==frozen.get('origin_stat'),'FROZEN_NATIVE72_ENTRY_OR_STAT_WAS_REWRITTEN')
        original=Path(old);literal(new)
        need(original.is_absolute() and main in original.parents and '..' not in original.parts
            and type(origin['bytes']) is int and origin['bytes']>=0 and origin['bytes']==target['bytes'],
            'EXACT_MAIN_ORIGIN_ALPHA_TARGET_BYTES_REQUIRED')
        if origin.get('sha256') is None:
            need(row['kind'] in no_sha and set(target)=={'path','bytes'},'NO_INVENTED_MAIN_DATABASE_OR_INPUT_SHA_ALLOWED')
        else:
            triple(target);need(origin['sha256']==target['sha256'],'EXACT_ORIGINAL_SHA_FOR_PINNED_METADATA_REQUIRED')
        if row['kind'] in source_kinds:need(target in plan['source_references'],'EVERY_FROZEN_SMALL_SOURCE_COPY_MUST_BE_APPROVED')
        origins.add(old);targets.add(new)
    need(origins==set(expected),'NATIVE72_RELOCATION_FULL_SET_CHANGED')
    return {'archive_locator_authority_reference':map_ref,'fixed_transitive_locator_count':460,
        'Main_database_whole_SHA_claimed':False,'hash_basis':'FROZEN_PER_CALL_SHA_AND_INPUT_METADATA'}


def readonly(input_path,deployment_path,node,seconds,**unused):
    need(deployment_path is None,'READONLY_PLAN_HAS_NO_ACQUISITION_DEPLOYMENT')
    plan=load(input_path);refs={};key=plan.get('producer_key')
    need(key in PROTOCOLS,'ONLY_THREE_EXACT_ALPHA_READONLY_PROTOCOLS_ALLOWED')
    protocol=PROTOCOLS[key]
    need(plan.get('schema')==protocol['plan'] and plan.get('scope_key')==key and plan.get('endpoint')==ENDPOINT
        and plan.get('uid')==UID and plan.get('run_root')==str(ROOT) and plan.get('node')==node
        and plan.get('cpus')==16 and plan.get('memory_policy')==POLICY and plan.get('kind','analysis')=='analysis'
        and type(plan.get('wall_seconds')) is int and plan['wall_seconds']==seconds and 0<seconds<=172800 and seconds%60==0,
        'EXACT_ALPHA_CPU16_NO_MEMORY_READONLY_RESOURCE_PLAN_REQUIRED')
    pilot=False;scope_mode='BOUNDED_READONLY_ANALYSIS';archive=None
    if key=='pprime_native_precision72_readonly_alpha_v1':
        need(plan.get('stage')==protocol['stage'] and plan.get('pilot') is False and seconds==3600
            and plan.get('output_cap_bytes')==64<<20 and plan.get('scope_parameters')==NATIVE_PARAMETERS
            and plan.get('data_references')==[],'EXACT_NATIVE72_READONLY_SCOPE_AND_NO_FAKE_WHOLE_DB_SHA_REQUIRED')
    elif key=='coconut_sql_identity_inventory_alpha_v1':
        mode=plan.get('mode');limit=plan.get('scope_parameters',{}).get('profile_limit_bytes')
        need(plan.get('scope_parameters')==sql_parameters(mode,limit),'EXACT_SQL_IDENTITY_KERNEL_SCOPE_REQUIRED')
        pilot=mode=='profile';scope_mode='BOUNDED_PERFORMANCE_BATCH' if pilot else 'BOUNDED_READONLY_ANALYSIS'
        need(plan.get('pilot') is pilot and plan.get('stage')==('SQL_IDENTITY_PROJECTION_PROFILE' if pilot else 'SQL_IDENTITY_PROJECTION_FULL')
            and plan.get('output_cap_bytes')==(2<<30 if pilot else 64<<30),'EXACT_SQL_IDENTITY_PROFILE_OR_FULL_SCOPE_REQUIRED')
    else:
        need(plan.get('stage')==protocol['stage'] and plan.get('pilot') is False and seconds==3600
            and plan.get('output_cap_bytes')==64<<20 and plan.get('scope_parameters')==RAW_PARAMETERS,
            'EXACT_PUBCHEM_ORIGINAL_RAW_COPY_ONLY_SCOPE_REQUIRED')
    review=load_ref(plan['root_review_reference'])
    need(review.get('schema')=='EXACT_SECONDARY_BOUNDED_READONLY_ROOT_REVIEW_V1'
        and review.get('status')=='APPROVED_FOR_EXACT_STAGE' and review.get('reviewer')=='root'
        and review.get('kind','analysis')=='analysis','EXACT_READONLY_ROOT_REVIEW_REQUIRED')
    for field in REVIEW_FIELDS:need(plan[field]==review[field],'EXACT_READONLY_ROOT_SCOPE_DIFFERS:'+field)
    need(plan['source_references']==review['approved_source_references'],'EXACT_REVIEWED_READONLY_SOURCES_REQUIRED')
    for value in [*plan['source_references'],*plan['parent_evidence_references'],ref(input_path),plan['root_review_reference']]:
        value=normalized(value);verify(value)
        need(value['path'] not in refs or refs[value['path']]==value,'CONFLICTING_READONLY_SMALL_SOURCE_REFERENCE')
        refs[value['path']]=value
    for name in ('controller.py','adapters.py'):
        need(ref(HERE/name) in plan['source_references'],'NEW_V3_READONLY_CONTROLLER_SOURCE_MUST_BE_PINNED')
    need(ref(Path(__file__).absolute()) in plan['source_references'],'ACTUAL_V3_READONLY_ADAPTER_SOURCE_REQUIRED')
    primary=ROOT/'code'/Path(protocol['module'].replace('.','/')+'.py')
    need(ref(primary) in plan['source_references'],'EXACT_WHITELISTED_READONLY_PRIMARY_SOURCE_REQUIRED')
    need(plan['resource_authority_reference'] in plan['source_references'],'ACTUAL_ALPHA_RESOURCE_AUTHORITY_MUST_BE_APPROVED')
    proof=literal(plan['startup_proof_path']);out=literal(plan['output_directory'])
    need(ROOT/'artifacts' in out.parents,'NEW_ALPHA_READONLY_ARTIFACT_CHILD_REQUIRED')
    argv=[plan['python'],'-B','-m',protocol['module'],'--plan',str(Path(input_path)),'--startup-proof',str(proof)]
    need(plan['execution_argv']==argv and Path(argv[0]).is_absolute(),'EXACT_WHITELISTED_READONLY_MODULE_AND_ALL_ARGV_REQUIRED')
    bodies=plan['data_references'];need(isinstance(bodies,list),'EXACT_READONLY_DATA_LOCATOR_LIST_REQUIRED')
    if key=='pprime_native_precision72_readonly_alpha_v1':archive=native_archive_authority(plan)
    else:
        need(len(bodies)==1,'ONE_EXACT_SQL_OR_PUBLIC_RAW_DATA_LOCATOR_REQUIRED')
        payload=triple(bodies[0]);path=literal(payload['path'])
        need(payload['path'] not in refs,'LARGE_DATA_BODY_MUST_BE_DISJOINT_FROM_SMALL_SOURCE_REFS')
        if key=='coconut_sql_identity_inventory_alpha_v1':
            need(ROOT/'artifacts/source_acquisition' in path.parents and payload['bytes']==SQL_BYTES,'ONLY_ACTUAL_COMPLETE_ORIGINAL_SQL_DATA_LOCATOR')
            if not pilot:
                need(review.get('actual_profile_cost_and_coverage_reviewed') is True
                    and plan['accepted_profile_receipt_reference'] in plan['parent_evidence_references']
                    and plan['accepted_profile_accounting_reference'] in plan['parent_evidence_references'],
                    'FULL_SQL_IDENTITY_REQUIRES_ACTUAL_PROFILE_PARENT_REVIEW')
        else:
            need(ROOT/'inputs' in path.parents and payload['bytes']==RAW_BYTES and payload['sha256']==RAW_SHA,
                'ONLY_EXACT_ORIGINAL_MAIN_PUBLIC_GZIP_COPY_ALLOWED')
    return {'producer':'readonly','input_reference':ref(input_path),'producer_argv':argv,
        'producer_plan_reference':ref(input_path),'producer_review_reference':plan['root_review_reference'],
        'producer_authority_reference':plan['resource_authority_reference'],'source_references':list(refs.values()),
        'data_reference_locators_only':bodies,'data_body_hashes_claimed_by_controller':False,
        'startup_proof_path':str(proof),'science_output':str(out),'output_cap_bytes':plan['output_cap_bytes'],
        'producer_working_directory':str(ROOT/'code'),'proof_schema':protocol['proof'],
        'request_kind':'analysis','pilot':pilot,'scope_key':key,'scope_parameters':plan['scope_parameters'],
        'stage':plan['stage'],'scope_mode':scope_mode,'performance_profile':pilot,'fixed_archive_authority':archive}


def startup_proof(request,jid,raw,job,probe,storage,storage_reference,controller_evidence):
    adapter=request['adapter']
    need(adapter['producer']=='readonly' and adapter['scope_key'] in PROTOCOLS and request['kind']==adapter['request_kind']=='analysis'
        and request['pilot'] is adapter['pilot'] and request['scope_key']==adapter['scope_key']
        and request['scope_parameters']==adapter['scope_parameters'] and request['stage']==adapter['stage']
        and request['scope_mode']==adapter['scope_mode'] and request['performance_profile'] is adapter['performance_profile'],
        'ONLY_THREE_EXACT_HONEST_READONLY_REQUEST_PROTOCOLS_ALLOWED')
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
        'scientific_population_or_full_SQL_status_coverage_accepted':False}