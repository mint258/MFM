"""Only exact Alpha Native72 v2; 32MiB technical report cap, original science unchanged."""
from collections import Counter
from pathlib import Path
from secondary_cpu_queue_v1.common import ROOT,ENDPOINT,UID,POLICY,need,ref,load,load_ref,verify,normalized,literal

PROTOCOLS={'pprime_native_precision72_readonly_alpha_v2':{
    'plan':'SECONDARY_NATIVE72_READONLY_PLAN_V2','proof':'SECONDARY_NATIVE72_READONLY_STARTUP_V2',
    'stage':'PPRIME_NATIVE72_EXISTING_OUTPUT_DIAGNOSIS','module':'frame_native_precision_alpha_v2.run'}}
HERE=ROOT/'code/secondary_cpu_readonly_queue_v4'
NATIVE_PARAMETERS={'original_job_id':'4521124','retained_cases':72,'original_covariance_failures':15,'new_QM_calls':0,
    'synthetic_test_methods':4,'all4_tests_must_pass_before_raw_reads':True,'pilot':False,'production_membership':False,
    'native_raw_read_only':True,'bounded_gzip_decompression':True,'precision_arithmetic':'EXACT_FRACTION',
    'maximum_report_bytes':33554432,'algorithm_rss_soft_cap_bytes':8589934592,'minimum_mem_available_bytes':4294967296,
    'readback_endpoint':'218.192.171.238:22','readback_uid':1264,'origin_endpoint':'202.38.247.57:22',
    'Main_runtime_proof_reused':False,'original_JSON_paths_rewritten':False,'full_or2000_QM_release':False,
    'exact_database_files':72,'exact_case_result_files':72,'exact_input_files':288,
    'hash_basis':'FROZEN_PER_CALL_SHA_AND_INPUT_METADATA'}
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


def native_archive_authority(plan):
    """Check all460 frozen metadata locators; never open a DB/input body on login."""
    map_ref=plan['relocation_map_reference']
    need(plan.get('archive_locator_authority_reference')==map_ref and map_ref in plan['source_references'],
        'EXACT_REVIEWED_TRANSITIVE_NATIVE72_ARCHIVE_AUTHORITY_REQUIRED')
    mapping=load_ref(map_ref)
    need(mapping.get('schema')=='NATIVE72_READONLY_RELOCATION_MAP_V1','EXACT_NATIVE72_RELOCATION_SCHEMA_REQUIRED')
    inventory_path=ROOT/'code/frame_native_precision_alpha_v2/origin_inventory.json'
    inventory_ref=ref(inventory_path)
    need(inventory_ref['bytes']==546050
        and inventory_ref['sha256']=='83e58412628c6c0048f39b9cdc8f8ddda2bfe181eca8f9d7d74b40f9d99022cf',
        'ORIGINAL_NATIVE72_INVENTORY_BYTES_MUST_REMAIN_IDENTICAL')
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
    need(deployment_path is None,'NATIVE72_READONLY_HAS_NO_ACQUISITION_DEPLOYMENT')
    plan=load(input_path);refs={};key=plan.get('producer_key')
    need(key in PROTOCOLS,'ONLY_EXACT_NATIVE72_V2_PROTOCOL_ALLOWED')
    protocol=PROTOCOLS[key]
    need(plan.get('schema')==protocol['plan'] and plan.get('scope_key')==key and plan.get('stage')==protocol['stage']
        and plan.get('endpoint')==ENDPOINT and plan.get('uid')==UID and plan.get('run_root')==str(ROOT)
        and plan.get('node')==node and plan.get('cpus')==16 and plan.get('memory_policy')==POLICY
        and plan.get('kind','analysis')=='analysis' and plan.get('pilot') is False
        and type(plan.get('wall_seconds')) is int and plan['wall_seconds']==seconds==3600
        and plan.get('output_cap_bytes')==64<<20 and plan.get('scope_parameters')==NATIVE_PARAMETERS
        and plan.get('data_references')==[],'EXACT_NATIVE72_V2_SCOPE_RESOURCE_AND_NO_FAKE_WHOLE_DB_SHA_REQUIRED')
    review=load_ref(plan['root_review_reference'])
    need(review.get('schema')=='EXACT_SECONDARY_BOUNDED_READONLY_ROOT_REVIEW_V1'
        and review.get('status')=='APPROVED_FOR_EXACT_STAGE' and review.get('reviewer')=='root'
        and review.get('kind','analysis')=='analysis','EXACT_NATIVE72_V2_ROOT_REVIEW_REQUIRED')
    for field in REVIEW_FIELDS:need(plan[field]==review[field],'EXACT_NATIVE72_V2_ROOT_SCOPE_DIFFERS:'+field)
    need(plan['source_references']==review['approved_source_references'],'EXACT_REVIEWED_NATIVE72_V2_SOURCES_REQUIRED')
    for value in [*plan['source_references'],*plan['parent_evidence_references'],ref(input_path),plan['root_review_reference']]:
        value=normalized(value);verify(value)
        need(value['path'] not in refs or refs[value['path']]==value,'CONFLICTING_NATIVE72_V2_SMALL_SOURCE_REFERENCE')
        refs[value['path']]=value
    for name in ('controller.py','adapters.py'):
        need(ref(HERE/name) in plan['source_references'],'ACTUAL_V4_CONTROLLER_SOURCE_MUST_BE_APPROVED')
    need(ref(Path(__file__).absolute()) in plan['source_references'],'ACTUAL_V4_NATIVE72_ADAPTER_SOURCE_REQUIRED')
    primary=ROOT/'code/frame_native_precision_alpha_v2/run.py'
    for path in primary.parent.iterdir():
        if path.is_file() and path.suffix in {'.py','.json','.md'}:
            need(ref(path) in plan['source_references'],'EVERY_NEW_NATIVE72_V2_SOURCE_MUST_BE_APPROVED:'+path.name)
    need(ref(primary) in plan['source_references'],'EXACT_NATIVE72_V2_PRIMARY_SOURCE_REQUIRED')
    need(plan['resource_authority_reference'] in plan['source_references'],'ACTUAL_ALPHA_RESOURCE_AUTHORITY_MUST_BE_APPROVED')
    proof=literal(plan['startup_proof_path']);out=literal(plan['output_directory'])
    need(ROOT/'artifacts' in out.parents,'NEW_ALPHA_NATIVE72_V2_ARTIFACT_CHILD_REQUIRED')
    argv=[plan['python'],'-B','-m',protocol['module'],'--plan',str(Path(input_path)),'--startup-proof',str(proof)]
    need(plan['execution_argv']==argv and Path(argv[0]).is_absolute(),'EXACT_NATIVE72_V2_MODULE_AND_ALL_ARGV_REQUIRED')
    archive=native_archive_authority(plan)
    return {'producer':'readonly','input_reference':ref(input_path),'producer_argv':argv,
        'producer_plan_reference':ref(input_path),'producer_review_reference':plan['root_review_reference'],
        'producer_authority_reference':plan['resource_authority_reference'],'source_references':list(refs.values()),
        'data_reference_locators_only':[],'data_body_hashes_claimed_by_controller':False,
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
        'ONLY_EXACT_NATIVE72_V2_READONLY_REQUEST_PROTOCOL_ALLOWED')
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