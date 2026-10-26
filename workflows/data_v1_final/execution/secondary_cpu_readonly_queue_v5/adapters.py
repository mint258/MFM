"""Only exact Labels512 readonly and official MoleculeNet11 acquisition protocols."""
import csv,io
from collections import Counter
from pathlib import Path
from secondary_cpu_queue_v1.common import ROOT,ENDPOINT,UID,POLICY,need,ref,load,load_ref,verify,normalized,literal,read_small,NODES

LABEL_KEY='labels_payload512_readonly_alpha_v1'
EXTERNAL_KEY='moleculenet_missing11_acquisition_alpha_v1'
PROTOCOLS={
 LABEL_KEY:{'plan':'SECONDARY_LABEL_PAYLOAD512_READONLY_PLAN_V1','proof':'SECONDARY_LABEL_PAYLOAD512_READONLY_STARTUP_V1',
   'stage':'LABEL_PAYLOAD512_EXISTING_VALUES_PILOT','module':'payload_audit_alpha_v1.run'},
 EXTERNAL_KEY:{'plan':'SECONDARY_EXTERNAL_SOURCE_ACQUISITION_PLAN_V1','proof':'SECONDARY_EXTERNAL_SOURCE_ACQUISITION_STARTUP_V1',
   'stage':None,'module':'secondary_external_sources_acquisition_v1.run'}}
HERE=ROOT/'code/secondary_cpu_readonly_queue_v5'
REVIEW_FIELDS=('scope_key','scope_parameters','stage','endpoint','uid','run_root','node','cpus','memory_policy',
    'pilot','wall_seconds','output_cap_bytes','execution_argv','data_references','parent_evidence_references')
LABEL_PARAMETERS={'original_main_job_id':'4521327','input_molecules':512,'input_records':4251,
    'source_TRAIN_records':4211,'source_VAL_records':20,'source_FULL_records':20,'source_owner_jobs':16,
    'family_parquet_files':209,'selection_owner_index_files':16,'canonical_index_files':1,
    'scan_required_body_files':226,'scan_required_body_bytes':2703431455,
    'transfer_hash_body_files':227,'transfer_hash_body_bytes':2714663309,'role_ledger_reduce_only_files':1,
    'synthetic_test_methods':6,'all6_tests_before_any_body_reads':True,'body_hash_after_tests_in_this_allocation':True,
    'body_hash_workers':16,'expected_task_slots':59514,'task_types':14,'enabled_components':146,'registered_components':264,
    'new_QM_calls':0,'new_UFF_calls':0,'source_values_read_only':True,'original_JSON_paths_rewritten':False,
    'Main_runtime_proof_reused':False,'full_or_export_or_final_D4_release':False,
    'algorithm_worker_rss_soft_cap_bytes':3221225472,'minimum_mem_available_bytes':4294967296,
    'target_python':'3.11.14','target_numpy':'2.2.6','target_rdkit':'2025.09.5','target_pyarrow':'17.0.0','Main_pyarrow_major':25}
LABEL_KINDS={'canonical_index_scan':1,'expected_role_reduce_only':1,'family_parquet_scan':209,'selection_owner_index_scan':16}
IDS=('hiv','muv','pcba','sider','tox21','toxcast','qm7b_mat','qm8_sdf','pdbbind_general','pdbbind_refined','pdbbind_core')
FILENAMES=('HIV.csv','muv.csv.gz','pcba.csv.gz','sider.csv.gz','tox21.csv.gz','toxcast_data.csv.gz','qm7b.mat','gdb8.tar.gz',
 'pdbbindv2019/pdbbind_v2019_other_PL.tar.gz','pdbbindv2019/pdbbind_v2019_refined.tar.gz','pdbbind_v2013_core_set.tar.gz')
SIZES=(2193844,1755511,15449358,34759,122925,404948,16067096,8764619,1759178739,651882567,45317121)
URLS=dict(zip(IDS,('https://deepchemdata.s3-us-west-1.amazonaws.com/datasets/'+x for x in FILENAMES)))
EXTERNAL_STAGE='OFFICIAL_MOLECULENET11_DOWNLOAD_AND_CONTAINER_INVENTORY'


def triple(value):
    need(isinstance(value,dict) and set(value)=={'path','bytes','sha256'} and type(value['bytes']) is int and value['bytes']>=0
        and isinstance(value['sha256'],str) and len(value['sha256'])==64 and set(value['sha256'])<=set('0123456789abcdef'),
        'EXACT_DATA_LOCATOR_TRIPLE_REQUIRED_WITHOUT_BODY_READ')
    literal(value['path']);return value


def strip_triple(value):return {k:value[k] for k in ('path','bytes','sha256')}


def external_parameters(mode):
    need(mode in ('profile','full'),'EXACT_ACQUISITION_MODE_REQUIRED')
    return {'mode':mode,'catalog_sources':list(IDS),'download_source_ids':['sider'] if mode=='profile' else [x for x in IDS if x!='sider'],
      'reuse_profile_sider_without_GET':mode=='full','maximum_concurrent_GETs':16,'GET_attempts_per_source':1,
      'conditional_ETag_and_LastModified':True,'normal_proxy_environment_inherited':True,'network_configuration_changed':False,
      'alternate_domains_or_mirrors':False,'extract_archive_members':False,'chemical_normalization':False,
      'maximum_inventory_record_bytes':4096,'maximum_expanded_bytes_per_source':256*1024**3,
      'container_buffer_bytes':1024**2,'MAT_variable_arrays_inspected':False,'identity_coverage_accepted':False,
      'algorithm_RSS_reference_bytes':48*1024**3,'runtime_MemAvailable_min_fraction':.15,'cost_overrun_action':'REPORT_AND_CONTINUE'}


def labels_archive_authority(plan):
    """Freeze227 body locators and54 small copies without opening any body."""
    inventory_ref=plan['origin_inventory_reference'];map_ref=plan['relocation_map_reference']
    need(inventory_ref in plan['source_references'] and map_ref in plan['source_references'],
        'LABELS_INVENTORY_AND_RELOCATION_MAP_MUST_BE_APPROVED_SMALL_SOURCES')
    need(inventory_ref==ref(ROOT/'code/payload_audit_alpha_v1/transfer_inventory_v1.json')
        and inventory_ref['bytes']==515109
        and inventory_ref['sha256']=='b20b5a8a707dc2614d1e77dda7ac7c7371f89e6cb673218900c35171bb20282d',
        'EXACT_FROZEN_LABELS227_PLUS54_INVENTORY_BYTES_REQUIRED')
    inventory=load_ref(inventory_ref);mapping=load_ref(map_ref)
    need(inventory.get('schema')=='SECONDARY_LABEL_PAYLOAD512_TRANSFER_INVENTORY_V1'
        and inventory.get('source_endpoint')=='zixiao@202.38.247.57:22'
        and inventory.get('target_endpoint')=='alpha@218.192.171.238:22'
        and inventory.get('data_files')==227 and inventory.get('data_total_bytes')==2714663309
        and inventory.get('scan_required_data_files')==226 and inventory.get('scan_required_data_bytes')==2703431455
        and inventory.get('small_files')==54,'EXACT_LABELS_INVENTORY_SCOPE_REQUIRED')
    need(mapping.get('schema')=='LABEL_PAYLOAD512_READONLY_RELOCATION_MAP_V1'
        and Path(map_ref['path'])==ROOT/'metadata/labels_payload512_v1/relocation_map.json',
        'EXACT_LABELS_RELOCATION_SCHEMA_AND_CONSUMER_PATH_REQUIRED')
    body_rows=inventory['data'];small_rows=inventory['small'];rows=body_rows+small_rows
    need(dict(Counter(x['kind'] for x in body_rows))==LABEL_KINDS and len(body_rows)==227 and len(small_rows)==54,
        'EXACT_LABELS_BODY_AND_SMALL_KIND_COUNTS_REQUIRED')
    expected={x['origin_reference']['path']:x for x in rows};entries=mapping['entries']
    need(len(expected)==len(rows)==len(entries)==281,'EXACT_UNIQUE_LABELS281_TRANSFER_MAP_REQUIRED')
    origins=set();targets=set();main=Path('/share/home/zixiao/descriptor_analysis')
    for row in entries:
        origin=row['origin_reference'];target=triple(row['target_reference']);old=origin['path']
        need(old in expected and old not in origins and target['path'] not in targets,'UNIQUE_FROZEN_LABELS_TRANSFER_SET_REQUIRED')
        frozen=expected[old];source=Path(old)
        need(source.is_absolute() and main in source.parents and '..' not in source.parts
            and origin==frozen['origin_reference'] and target==strip_triple(frozen['target_locator']) and row['kind']==frozen['kind']
            and origin['bytes']==target['bytes'] and origin['sha256']==target['sha256'],'ORIGINAL_LABELS_TRANSFER_BYTES_OR_MAP_CHANGED')
        if frozen in small_rows:need(target in plan['source_references'],'EVERY_LABELS_FROZEN_SMALL_COPY_MUST_BE_APPROVED')
        origins.add(old);targets.add(target['path'])
    bodies=[triple(strip_triple(x['target_locator'])) for x in body_rows]
    need(plan['data_references']==bodies and sum(x['bytes'] for x in bodies)==2714663309,
        'ALL227_EXACT_PURE_TRIPLE_BODY_LOCATORS_REQUIRED')
    need(plan['fixture_auxiliary_config_reference'] in plan['source_references'],
        'LABELS_NEW_FIXTURE_AUXILIARY_CONFIG_MUST_BE_APPROVED_OUTSIDE_ORIGINAL281_MAP')
    config=triple(plan['config_reference'])
    need(config in [strip_triple(x['target_locator']) for x in small_rows]
        and config in plan['source_references'] and config['bytes']==3861
        and config['sha256']=='48357da799b8772a4b18c1288aa5e582daf6c5c1126f7bbb4927cf4c852f5528',
        'EXACT_ORIGINAL_LABELS3861B_SCIENTIFIC_CONFIG_COPY_REQUIRED')
    need(plan.get('transfer_verification_reference') is None
        and plan.get('transfer_verification_expected_output_path')==str(Path(plan['output_directory'])/'transfer_verification.json'),
        'NO_FUTURE_TRANSFER_RECEIPT_PIN_ALLOWED_ACTUAL227_HASH_AFTER_FIXTURES_IN_SAME_JOB')
    return {'origin_inventory_reference':inventory_ref,'relocation_map_reference':map_ref,'body_files':227,'body_bytes':2714663309,
        'small_files':54,'target_body_SHA_verified_by_login_controller':False,'actual_transfer_verification_pending_this_job':True}


def actual_profile_account(reference,job_id):
    account=load_ref(reference);parent=account['actual_parent']
    need(account.get('query_returncode')==0 and account.get('endpoint')==ENDPOINT and account.get('uid')==UID
        and parent.get('JobIDRaw')==str(job_id) and parent.get('State')=='COMPLETED' and parent.get('ExitCode')=='0:0'
        and parent.get('UID')==str(UID) and parent.get('AllocCPUS')=='16' and parent.get('Partition')=='cpu'
        and parent.get('NodeList') in NODES,'ACTUAL_ALPHA_PROFILE_C0_CPU16_PARENT_REQUIRED')
    rows=list(csv.DictReader(io.StringIO(read_small(verify(account['raw_sacct_reference'])).decode()),delimiter='|'))
    matches=[x for x in rows if x.get('JobIDRaw')==str(job_id)]
    need(len(matches)==1 and all(matches[0].get(k)==parent.get(k) for k in
        ('State','ExitCode','UID','ElapsedRaw','AllocCPUS','NodeList','Partition'))
        and account.get('allocated_core_seconds_observed')==int(parent['ElapsedRaw'])*16,'ACTUAL_PROFILE_RAW_PARENT_COST_REQUIRED')
    return account


def external_archive_authority(plan,review):
    for key in ('locator_catalog_reference','head_receipt_reference','cost_decision_reference'):
        need(plan[key] in plan['source_references'],'EXACT_EXTERNAL_SMALL_AUTHORITY_MUST_BE_APPROVED:'+key)
    catalog_ref=plan['locator_catalog_reference']
    need(catalog_ref['bytes']==18060 and catalog_ref['sha256']=='4e9252ced07075c56032387a2b9668bb12b2b57d4f0ee7c29ebbc9befbbcacdf',
        'EXACT_ACTUAL1094_ELEVEN_OFFICIAL_LOCATOR_CATALOG_BYTES_REQUIRED')
    catalog=load_ref(catalog_ref)
    need(catalog.get('schema')=='MOLECULENET_MISSING11_ACTUAL_HEAD_LOCATORS_V1' and catalog.get('head_job_id')=='4521094'
        and catalog.get('physical_file_count')==11 and catalog.get('total_expected_compressed_bytes')==2501171487,
        'EXACT_ELEVEN_OFFICIAL_HEAD_LOCATOR_SCOPE_REQUIRED')
    head=load_ref(plan['head_receipt_reference'])
    need(head.get('job_id')=='4521094' and head.get('status')=='HEAD_OBSERVATIONS_COMPLETE_ALL_SOURCE_COVERAGE_PENDING'
        and plan['head_receipt_reference']['bytes']==catalog['head_receipt_reference']['bytes']
        and plan['head_receipt_reference']['sha256']==catalog['head_receipt_reference']['sha256'],'EXACT_ORIGINAL1094_HEAD_RECEIPT_COPY_REQUIRED')
    rows={x['source_id']:x for x in catalog['entries']};copies=plan['head_observation_references']
    need(len(rows)==len(catalog['entries'])==len(copies)==11 and set(rows)==set(IDS)
        and {x['source_id'] for x in copies}==set(IDS),'ALL_ELEVEN_NO_EXTRA_OFFICIAL_HEAD_COPIES_REQUIRED')
    for id,size in zip(IDS,SIZES):
        row=rows[id];value=next(x['reference'] for x in copies if x['source_id']==id)
        need(row['url']==URLS[id] and row['expected_compressed_bytes']==size and row['head_http_status']==200
            and value in plan['source_references'] and all(value[k]==row['head_reference'][k] for k in ('bytes','sha256')),
            'EXACT_OFFICIAL_URL_LENGTH_AND_ORIGINAL_HEAD_COPY_REQUIRED')
        observation=load_ref(value);block=observation['redirect_chain'][-1]['http_blocks'][-1]
        need(observation['http_status']==200 and observation['candidate']['url']==observation['final_url']['url']==row['url']
            and block['content_length_bytes']==size and block['headers']['etag'][0]['value']==row['expected_etag']
            and block['headers']['last-modified'][0]['value']==row['expected_last_modified'],'FROZEN_OFFICIAL_HEAD_SEMANTICS_DIFFER')
    if plan['mode']=='profile':need(plan['data_references']==[],'SIDER_PROFILE_HAS_NO_PREEXISTING_DATA_BODY')
    else:
        for key in ('accepted_profile_receipt_reference','accepted_profile_accounting_reference'):
            need(plan[key] in plan['parent_evidence_references'],'ACTUAL_PROFILE_PARENT_MUST_BE_PINNED:'+key)
        prior=load_ref(plan['accepted_profile_receipt_reference']);package=ROOT/'code/secondary_external_sources_acquisition_v1'
        need(prior.get('schema')=='SECONDARY_EXTERNAL_SOURCE_ACQUISITION_RECEIPT_V1'
            and prior.get('status')=='OFFICIAL_SINGLE_SOURCE_CONTAINER_PROFILE_COMPLETE' and prior.get('mode')=='profile'
            and prior.get('locator_catalog_sha256')==catalog_ref['sha256']
            and prior.get('kernel_source_references')==[ref(package/x) for x in ('__init__.py','contracts.py','runtime.py','run.py')]
            and review.get('actual_profile_cost_and_container_path_reviewed') is True,'SAME_KERNEL_ACTUAL_SIDER_PROFILE_REVIEW_BEFORE_FULL')
        actual_profile_account(plan['accepted_profile_accounting_reference'],prior['job_id'])
        need(len(prior['sources'])==1 and prior['sources'][0]['source_id']=='sider'
            and prior['sources'][0]['status']=='COMPLETE_CONTAINER_OBSERVED'
            and plan['data_references']==[prior['sources'][0]['payload_reference']],'EXACT_ACTUAL_OLD_SIDER_PAYLOAD_REUSE_ONLY')
        body=triple(plan['data_references'][0])
        need(body['bytes']==34759 and ROOT/'artifacts' in Path(body['path']).parents,'EXACT_ORIGINAL_SIDER34759B_PAYLOAD_LOCATOR_REQUIRED')
    return {'official_locator_catalog_reference':catalog_ref,'source_ids':list(IDS),
        'existing_data_body_SHA_verified_by_login_controller':False,'full_chemical_identity_or_release_accepted':False}


def readonly(input_path,deployment_path,node,seconds,**unused):
    need(deployment_path is None,'EXACT_V5_PLAN_HAS_NO_ACQUISITION_DEPLOYMENT_WRAPPER')
    plan=load(input_path);refs={};key=plan.get('producer_key')
    need(key in PROTOCOLS,'ONLY_EXACT_LABEL512_OR_MOLECULENET11_PROTOCOL_ALLOWED')
    protocol=PROTOCOLS[key]
    need(plan.get('schema')==protocol['plan'] and plan.get('scope_key')==key and plan.get('endpoint')==ENDPOINT
        and plan.get('uid')==UID and plan.get('run_root')==str(ROOT) and plan.get('node')==node
        and plan.get('cpus')==16 and plan.get('memory_policy')==POLICY and plan.get('kind','analysis')=='analysis'
        and type(plan.get('wall_seconds')) is int and plan['wall_seconds']==seconds and 0<seconds<=172800 and seconds%60==0,
        'EXACT_ALPHA_CPU16_NO_MEMORY_V5_RESOURCE_PLAN_REQUIRED')
    if key==LABEL_KEY:
        pilot=True;need(plan.get('scope_parameters')==LABEL_PARAMETERS and plan.get('stage')==protocol['stage']
            and plan.get('pilot') is True and seconds==7200 and plan.get('output_cap_bytes')==8<<30,
            'EXACT_LABELS512_ORIGINAL_SCIENCE_PILOT_SCOPE_REQUIRED')
    else:
        mode=plan.get('mode');pilot=mode=='profile'
        need(plan.get('scope_parameters')==external_parameters(mode) and plan.get('pilot') is pilot
            and plan.get('stage')==EXTERNAL_STAGE+('_PROFILE' if pilot else '_FULL')
            and (seconds==3600 if pilot else 0<seconds<=172800)
            and plan.get('output_cap_bytes')==(64<<20 if pilot else 16<<30),'EXACT_SIDER_PROFILE_OR_REMAINING10_FULL_SCOPE_REQUIRED')
    review=load_ref(plan['root_review_reference'])
    need(review.get('schema')=='EXACT_SECONDARY_BOUNDED_READONLY_ROOT_REVIEW_V1'
        and review.get('status')=='APPROVED_FOR_EXACT_STAGE' and review.get('reviewer')=='root'
        and review.get('kind','analysis')=='analysis','EXACT_V5_ROOT_REVIEW_REQUIRED')
    for field in REVIEW_FIELDS:need(plan[field]==review[field],'EXACT_V5_ROOT_SCOPE_DIFFERS:'+field)
    need(plan['source_references']==review['approved_source_references'],'EXACT_V5_REVIEWED_SOURCE_SET_REQUIRED')
    for value in [*plan['source_references'],*plan['parent_evidence_references'],ref(input_path),plan['root_review_reference']]:
        value=normalized(value);verify(value)
        need(value['path'] not in refs or refs[value['path']]==value,'CONFLICTING_V5_SMALL_SOURCE_REFERENCE')
        refs[value['path']]=value
    for name in ('controller.py','adapters.py'):
        need(ref(HERE/name) in plan['source_references'],'ACTUAL_V5_CONTROLLER_AND_ADAPTER_SOURCES_MUST_BE_APPROVED')
    need(ref(Path(__file__).absolute()) in plan['source_references'],'ACTUAL_V5_ADAPTER_SOURCE_REQUIRED')
    primary=ROOT/'code'/Path(protocol['module'].replace('.','/')+'.py')
    for path in primary.parent.iterdir():
        if path.is_file() and path.suffix in {'.py','.json','.md'}:
            need(ref(path) in plan['source_references'],'EVERY_NEW_V5_CONSUMER_SOURCE_MUST_BE_APPROVED:'+path.name)
    need(ref(primary) in plan['source_references'],'EXACT_V5_PRIMARY_SOURCE_REQUIRED')
    need(plan['resource_authority_reference'] in plan['source_references'],'ACTUAL_ALPHA_RESOURCE_AUTHORITY_MUST_BE_APPROVED')
    proof=literal(plan['startup_proof_path']);out=literal(plan['output_directory'])
    need(ROOT/'artifacts' in out.parents,'NEW_ALPHA_V5_ARTIFACT_CHILD_REQUIRED')
    argv=[plan['python'],'-B','-m',protocol['module'],'--plan',str(Path(input_path)),'--startup-proof',str(proof)]
    need(plan['execution_argv']==argv and Path(argv[0]).is_absolute(),'EXACT_V5_MODULE_AND_COMPLETE_EIGHT_ARGV_REQUIRED')
    bodies=plan['data_references'];need(isinstance(bodies,list),'EXACT_V5_BODY_LOCATOR_LIST_REQUIRED')
    archive=labels_archive_authority(plan) if key==LABEL_KEY else external_archive_authority(plan,review)
    for body in bodies:
        triple(body);need(body['path'] not in refs,'BODY_LOCATORS_MUST_BE_DISJOINT_FROM_SMALL_SOURCE_REFS')
    return {'producer':'readonly','input_reference':ref(input_path),'producer_argv':argv,
        'producer_plan_reference':ref(input_path),'producer_review_reference':plan['root_review_reference'],
        'producer_authority_reference':plan['resource_authority_reference'],'source_references':list(refs.values()),
        'data_reference_locators_only':bodies,'data_body_hashes_claimed_by_controller':False,
        'startup_proof_path':str(proof),'science_output':str(out),'output_cap_bytes':plan['output_cap_bytes'],
        'producer_working_directory':str(ROOT/'code'),'proof_schema':protocol['proof'],
        'request_kind':'analysis','pilot':pilot,'scope_key':key,'scope_parameters':plan['scope_parameters'],
        'stage':plan['stage'],'scope_mode':'BOUNDED_PERFORMANCE_BATCH' if pilot else 'BOUNDED_SOURCE_ACQUISITION',
        'performance_profile':pilot,'fixed_archive_authority':archive}


def startup_proof(request,jid,raw,job,probe,storage,storage_reference,controller_evidence):
    adapter=request['adapter']
    need(adapter['producer']=='readonly' and adapter['scope_key'] in PROTOCOLS and request['kind']==adapter['request_kind']=='analysis'
        and request['pilot'] is adapter['pilot'] and request['scope_key']==adapter['scope_key']
        and request['scope_parameters']==adapter['scope_parameters'] and request['stage']==adapter['stage']
        and request['scope_mode']==adapter['scope_mode'] and request['performance_profile'] is adapter['performance_profile'],
        'ONLY_EXACT_LABEL512_OR_MOLECULENET11_REQUEST_PROTOCOL_ALLOWED')
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
        'performance_profile':adapter['performance_profile'],'bounded_readonly_scope_only':adapter['scope_key']==LABEL_KEY,
        'bounded_source_acquisition_scope_only':adapter['scope_key']==EXTERNAL_KEY,
        'scientific_population_or_full_SQL_status_coverage_accepted':False}
