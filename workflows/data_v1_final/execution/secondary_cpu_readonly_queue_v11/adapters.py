"""Only PubChem physical500 inventory and actual uniform10000 profile; no full shard."""
import re
from pathlib import Path
from secondary_cpu_queue_v1 import common as Q
from secondary_pubchem_screening_alpha_v1 import contracts as C
from secondary_pubchem_screening_alpha_v1.guard import main_authority,account
ROOT=Q.ROOT;ENDPOINT=Q.ENDPOINT;UID=Q.UID;POLICY=Q.POLICY
HERE=ROOT/'code/secondary_cpu_readonly_queue_v11'
STORAGE_SCOPE=C.STORAGE_SCOPE
PROTOCOLS={C.MODES[mode]['key']:{**C.MODES[mode],'mode':mode,'module':C.MODULE} for mode in ('inventory','profile')}
REVIEW_FIELDS=('scope_key','scope_parameters','stage','endpoint','uid','run_root','node','cpus','memory_policy','kind','pilot',
    'wall_seconds','output_cap_bytes','execution_argv','data_references','parent_evidence_references','scope_mode','performance_profile')


def body_locator(value):
    Q.need(isinstance(value,dict) and set(value)=={'path','bytes','sha256'} and type(value['bytes']) is int and value['bytes']>0
        and isinstance(value['sha256'],str) and re.fullmatch('[0-9a-f]{64}',value['sha256']),'EXACT_PRODUCER_PINNED_DATA_LOCATOR_ONLY')
    Q.literal(value['path'])  # No body open/stat/hash/parse is performed here.


def readonly(input_path,deployment_path,node,seconds,**unused):
    Q.need(deployment_path is None,'PUBCHEM_AB_HAS_NO_DEPLOYMENT_WRAPPER')
    plan=Q.load(input_path);mode=plan.get('mode');Q.need(mode in ('inventory','profile'),'V11_ONLY_PUBCHEM_A_OR_B_NO_FULL_SHARD')
    spec=C.MODES[mode];key=spec['key'];params=C.parameters(mode);refs={}
    Q.need(plan.get('schema')==spec['plan'] and plan.get('producer_key')==plan.get('scope_key')==key
        and plan.get('stage')==spec['stage'] and plan.get('scope_parameters')==params and plan.get('kind')=='analysis'
        and plan.get('pilot') is spec['pilot'] and plan.get('scope_mode')==spec['scope_mode']
        and plan.get('performance_profile') is spec['performance_profile'] and plan.get('endpoint')==ENDPOINT
        and plan.get('uid')==UID and plan.get('run_root')==str(ROOT) and plan.get('node')==node and node in Q.NODES
        and plan.get('cpus')==16 and plan.get('memory_policy')==POLICY and type(plan.get('wall_seconds')) is int
        and plan['wall_seconds']==seconds==spec['wall'] and plan.get('output_cap_bytes')==spec['cap'],'ONLY_EXACT_ALPHA_PUBCHEM_AB_SCOPE')
    review=Q.load_ref(plan['root_review_reference'])
    Q.need(review.get('schema')=='EXACT_SECONDARY_BOUNDED_READONLY_ROOT_REVIEW_V1' and review.get('status')=='APPROVED_FOR_EXACT_STAGE'
        and review.get('reviewer')=='root','EXACT_PUBCHEM_AB_ROOT_REVIEW_REQUIRED')
    for name in REVIEW_FIELDS:Q.need(plan[name]==review[name],'EXACT_PUBCHEM_AB_REVIEW_FIELD_DIFFERS:'+name)
    Q.need(plan['source_references']==review['approved_source_references'],'EXACT_PUBCHEM_AB_REVIEWED_SOURCE_SET')
    for value in plan['data_references']:body_locator(value)
    body_paths={row['path'] for row in plan['data_references']}
    Q.need(len(body_paths)==len(plan['data_references']) and not any(row['path'] in body_paths for row in
        [*plan['source_references'],*plan['parent_evidence_references']]),'SCIENTIFIC_INDEX_JOURNAL_OR_RAW_NEVER_LOGIN_METADATA')
    for value in [*plan['source_references'],*plan['parent_evidence_references'],Q.ref(input_path),plan['root_review_reference']]:
        value=Q.normalized(value);Q.verify(value);Q.need(value['path'] not in refs or refs[value['path']]==value,'CONFLICTING_PUBCHEM_AB_SOURCE_PIN')
        refs[value['path']]=value
    for path in [*(C.HERE/name for name in C.FILES),HERE/'controller.py',HERE/'adapters.py',
                 ROOT/'code/secondary_cpu_queue_v1/common.py',ROOT/'code/secondary_cpu_queue_v1/__init__.py']:
        Q.need(Q.ref(path) in plan['source_references'],'ALL_ACTUAL_PUBCHEM_AB_AND_QUEUE_SOURCES_APPROVED')
    for name in ('resource_authority_reference','cost_decision_reference','metadata_relocation_reference','frozen_manifest_reference'):
        Q.need(plan[name] in plan['source_references'],'APPROVED_ALPHA_PUBCHEM_AB_AUTHORITY:'+name)
    Q.need(set(plan['main_evidence_references'])=={'inventory1093','uniform1316','full414','full414_closure','compat597'},'EXACT_FIVE_MAIN_AUTHORITY_KEYS')
    manifest=Q.load_ref(plan['frozen_manifest_reference']);expected={'__init__.py','common.py','screen.py','features_generic_candidate_v1.py','features_legacy_compatible_v2.py','raw_uniform_cost_source.py'}
    Q.need(manifest.get('schema')=='PUBCHEM_ALPHA_EXACT_SCIENTIFIC_SOURCE_COPIES_V1' and manifest.get('chemical_source_bytes_modified') is False
        and len(manifest['files'])==6 and {Path(row['target_reference']['path']).name for row in manifest['files']}==expected,'EXACT_SIX_UNCHANGED_FROZEN_SOURCE_COPIES')
    for row in manifest['files']:
        value=row['target_reference'];Q.need(Path(value['path']).parent==C.FROZEN and value in plan['source_references']
            and all(value[k]==row['origin_reference'][k] for k in ('bytes','sha256')),'ORIGINAL_KERNEL_BYTES_AND_ISOLATED_IMPORT_PATH')
    main_inv,main_uniform=main_authority(plan)
    raw=Q.load_ref(plan['alpha_raw_validation_receipt_reference'])
    Q.need(plan['alpha_raw_validation_receipt_reference'] in plan['parent_evidence_references'] and raw['job_id']=='1884769'
        and raw['status']=='EXACT_MAIN_PUBLIC_RAW_COPY_SHA_GZIP_EOF_VALIDATED' and raw['endpoint']==ENDPOINT and raw['uid']==UID
        and raw['actual_alpha_raw_reference']==plan['raw_reference'] and plan['raw_reference']['bytes']==C.RAW_BYTES
        and plan['raw_reference']['sha256']==C.RAW_SHA and raw['counts']['physical_rows']==C.N and raw['counts']['gzip_EOF_CRC_verified'] is True,
        'ACTUAL_ALPHA1884769_FULL_RAW_PIN_AND_CRC_PARENT_REQUIRED')
    account(plan['alpha_raw_validation_accounting_reference'],'1884769',ENDPOINT,UID,plan['parent_evidence_references'])
    Q.need(all(plan['main_index_reference'][name]==main_inv['source_index']['reference'][name] for name in ('bytes','sha256')),'ACTUAL1093_INDEX_PRODUCER_PIN_REQUIRED')
    if mode=='inventory':
        expected_data=[plan['raw_reference'],plan['main_index_reference']]
        authority_description={'original_full_raw_rows':C.N,'Main_exact_index_parts':500,'new_chemical_calls':0}
    else:
        Q.need(plan['alpha_inventory_receipt_reference'] in plan['parent_evidence_references'],'ACTUAL_ALPHA_A_RECEIPT_PARENT_REQUIRED')
        inventory=Q.load_ref(plan['alpha_inventory_receipt_reference']);data=inventory['inventory']
        Q.need(inventory['status']=='ALPHA_PHYSICAL500_COMPLETE_NO_CHEMISTRY' and inventory['endpoint']==ENDPOINT and inventory['uid']==UID
            and inventory['raw_reference']==plan['raw_reference'] and inventory['frozen_manifest_reference']==plan['frozen_manifest_reference']
            and data['records']==C.N and data['uncompressed_bytes']==C.UNCOMPRESSED_BYTES and data['part_count']==500
            and data['all500_parts_equal_Main_SHA_rows_bytes'] is True and data['gzip_EOF_CRC_revalidated'] is True,'ACTUAL_COMPLETE_ALPHA_A_NOT_PARTIAL')
        account(plan['alpha_inventory_accounting_reference'],inventory['job_id'],ENDPOINT,UID,plan['parent_evidence_references'])
        Q.need(all(plan['main_uniform_journal_reference'][name]==main_uniform['uniform']['full_result_journal'][name] for name in ('bytes','sha256')),
            'ACTUAL_MAIN1316_COMPLETE10000_JOURNAL_PIN_REQUIRED')
        expected_data=[data['source_index'],data['uniform_locators'],data['longest_locators'],plan['main_uniform_journal_reference']]
        authority_description={'producer_pinned_Alpha_part_locators_in_scientific_index':500,'whole_parts_verified_by_worker_before_selected_rows':True,
            'uniform_main_comparison_rows':10000,'longest16_is_independent_diagnostic_not_in_uniform_mean':True,'full_dispatch_allowed':False}
    Q.need(plan['data_references']==expected_data,'EXACT_MODE_SCIENTIFIC_DATA_LOCATORS')
    proof=Q.literal(plan['startup_proof_path']);out=Q.literal(plan['output_directory'])
    Q.need(ROOT/'artifacts' in out.parents and not out.exists() and len(str(out))<=1024,'NEW_PUBCHEM_AB_OUTPUT_LEAF_REQUIRED')
    argv=[plan['python'],'-B','-m',C.MODULE,'--plan',str(Path(input_path)),'--startup-proof',str(proof)]
    Q.need(plan['execution_argv']==argv and Path(argv[0]).is_absolute(),'EXACT_PUBCHEM_AB_PRIMARY_AND_ALL_EIGHT_ARGV_REQUIRED')
    return {'producer':'readonly','input_reference':Q.ref(input_path),'producer_argv':argv,'producer_plan_reference':Q.ref(input_path),
        'producer_review_reference':plan['root_review_reference'],'producer_authority_reference':plan['resource_authority_reference'],
        'source_references':list(refs.values()),'data_reference_locators_only':plan['data_references'],'data_body_hashes_claimed_by_controller':False,
        'startup_proof_path':str(proof),'science_output':str(out),'output_cap_bytes':plan['output_cap_bytes'],
        'producer_working_directory':str(ROOT/'code'),'proof_schema':spec['proof'],'request_kind':'analysis','pilot':spec['pilot'],
        'scope_key':key,'scope_parameters':params,'stage':spec['stage'],'scope_mode':spec['scope_mode'],
        'performance_profile':spec['performance_profile'],'fixed_archive_authority':authority_description}


def startup_proof(request,jid,raw,job,probe,storage,storage_reference,controller_evidence):
    adapter=request['adapter']
    Q.need(adapter['producer']=='readonly' and adapter['scope_key'] in PROTOCOLS and request['kind']==adapter['request_kind']=='analysis'
        and request['pilot'] is adapter['pilot'] and request['scope_key']==adapter['scope_key']
        and request['scope_parameters']==adapter['scope_parameters'] and request['stage']==adapter['stage']
        and request['scope_mode']==adapter['scope_mode'] and request['performance_profile'] is adapter['performance_profile'],
        'V11_ONLY_EXACT_PUBCHEM_AB_REQUEST_PROTOCOL_ALLOWED')
    Q.need(storage['storage_scope_review_reference']['path']==str(STORAGE_SCOPE),'EXACT_CURRENT_PUBCHEM_SCOPE7_REQUIRED')
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
        'bounded_source_acquisition_scope_only':False,'scientific_population_or_full_SQL_status_coverage_accepted':False,
        'full_PubChem_dispatch_or_pool_release_authorized':False}
