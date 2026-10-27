"""Only exact52..499 after actual QA0 and repaired51C0; original science unchanged."""
import re
from pathlib import Path
from secondary_cpu_queue_v1 import common as Q
ROOT=Q.ROOT;ENDPOINT=Q.ENDPOINT;UID=Q.UID;POLICY=Q.POLICY
HERE=ROOT/'code/secondary_cpu_readonly_pubchem_cont_v1'
STORAGE_SCOPE=ROOT/'control/secondary_cpu_queue/storage_scope_v7_pubchem_uniform_index_copy_v1.json'
FIXTURE_KEY='pubchem_c_continuation_state5_alpha_v3'
PROTOCOLS={
 'pubchem_c_continuation_shard_alpha_v3':{'plan':'SECONDARY_PUBCHEM_C_CONTINUATION_SHARD_PLAN_V3','proof':'SECONDARY_PUBCHEM_C_CONTINUATION_SHARD_STARTUP_V3',
    'module':'secondary_pubchem_continuation_alpha_v3.run','pilot':False},
 FIXTURE_KEY:{'plan':'SECONDARY_PUBCHEM_CONTINUATION_STATE5_PLAN_V3','proof':'SECONDARY_PUBCHEM_CONTINUATION_STATE5_STARTUP_V3',
    'module':'pubchem_c_finite500_continuation_v3.fixture_cpu','pilot':False}}
REVIEW_FIELDS=('scope_key','scope_parameters','stage','endpoint','uid','run_root','node','cpus','memory_policy','kind','pilot',
    'wall_seconds','output_cap_bytes','execution_argv','data_references','parent_evidence_references','scope_mode','performance_profile')


def body_locator(value):
    Q.need(isinstance(value,dict) and set(value)=={'path','bytes','sha256'} and type(value['bytes']) is int and value['bytes']>0
        and isinstance(value['sha256'],str) and re.fullmatch('[0-9a-f]{64}',value['sha256']),'EXACT_PRODUCER_PINNED_DATA_LOCATOR_ONLY')
    Q.literal(value['path'])  # No body open/stat/hash/parse is performed here.


def readonly(input_path,deployment_path,node,seconds,**unused):
    if Q.load(input_path).get('scope_key')==FIXTURE_KEY:return fixture_readonly(input_path,deployment_path,node,seconds)
    from secondary_pubchem_screening_alpha_v1 import contracts as C
    from secondary_pubchem_screening_alpha_v1.guard import main_authority,account
    from secondary_pubchem_continuation_alpha_v3 import contracts as A
    Q.need(deployment_path is None,'PUBCHEM_C_HAS_NO_DEPLOYMENT_WRAPPER')
    plan=Q.load(input_path);mode=plan.get('mode');Q.need(mode=='full_shard','ONLY_ORIGINAL_FULL_SHARD_METADATA_UNDER_NEW_RESOURCE_PHASE')
    bounds=[plan[name] for name in ('first_part','last_part','first_ordinal','last_ordinal')]
    spec=A.spec(A.phase(plan));key=spec['key'];params=A.parameters(plan);refs={}
    Q.need(plan.get('schema')==spec['plan'] and plan.get('producer_key')==plan.get('scope_key')==key
        and plan.get('stage')==spec['stage'] and plan.get('scope_parameters')==params and plan.get('kind')=='analysis'
        and plan.get('pilot') is spec['pilot'] and plan.get('scope_mode')==spec['scope_mode']
        and plan.get('performance_profile') is spec['performance_profile'] and plan.get('endpoint')==ENDPOINT
        and plan.get('uid')==UID and plan.get('run_root')==str(ROOT) and plan.get('node')==node and node in Q.NODES
        and plan.get('cpus')==16 and plan.get('memory_policy')==POLICY and type(plan.get('wall_seconds')) is int
        and plan['wall_seconds']==seconds and 0<seconds<=172800 and seconds%60==0
        and type(plan.get('output_cap_bytes')) is int and (16<<20)<=plan['output_cap_bytes']<=(1<<40),'ONLY_EXACT_ALPHA_PUBCHEM_C_SCOPE')
    review=Q.load_ref(plan['root_review_reference'])
    Q.need(review.get('schema')=='EXACT_SECONDARY_BOUNDED_READONLY_ROOT_REVIEW_V1' and review.get('status')=='APPROVED_FOR_EXACT_STAGE'
        and review.get('reviewer')=='root','EXACT_PUBCHEM_C_ROOT_REVIEW_REQUIRED')
    for name in REVIEW_FIELDS:Q.need(plan[name]==review[name],'EXACT_PUBCHEM_C_REVIEW_FIELD_DIFFERS:'+name)
    Q.need(plan['source_references']==review['approved_source_references'],'EXACT_PUBCHEM_C_REVIEWED_SOURCE_SET')
    for value in plan['data_references']:body_locator(value)
    body_paths={row['path'] for row in plan['data_references']}
    Q.need(len(body_paths)==len(plan['data_references']) and not any(row['path'] in body_paths for row in
        [*plan['source_references'],*plan['parent_evidence_references']]),'SCIENTIFIC_INDEX_JOURNAL_OR_RAW_NEVER_LOGIN_METADATA')
    for value in [*plan['source_references'],*plan['parent_evidence_references'],Q.ref(input_path),plan['root_review_reference']]:
        value=Q.normalized(value);Q.verify(value);Q.need(value['path'] not in refs or refs[value['path']]==value,'CONFLICTING_PUBCHEM_C_SOURCE_PIN')
        refs[value['path']]=value
    for path in [*(C.HERE/name for name in C.FILES),HERE/'controller.py',HERE/'adapters.py',
                 ROOT/'code/secondary_cpu_queue_v1/common.py',ROOT/'code/secondary_cpu_queue_v1/__init__.py']:
        Q.need(Q.ref(path) in plan['source_references'],'ALL_ACTUAL_PUBCHEM_C_AND_QUEUE_SOURCES_APPROVED')
    for name in ('resource_authority_reference','cost_decision_reference','metadata_relocation_reference','frozen_manifest_reference'):
        Q.need(plan[name] in plan['source_references'],'APPROVED_ALPHA_PUBCHEM_C_AUTHORITY:'+name)
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
    Q.need(plan['alpha_inventory_receipt_reference'] in plan['parent_evidence_references'],'ACTUAL_ALPHA_A_RECEIPT_REQUIRED')
    inventory=Q.load_ref(plan['alpha_inventory_receipt_reference']);data=inventory['inventory']
    Q.need(inventory['schema']=='ALPHA_PUBCHEM_PHYSICAL_INVENTORY_RECEIPT_V1' and inventory['mode']=='inventory'
        and inventory['status']=='ALPHA_PHYSICAL500_COMPLETE_NO_CHEMISTRY' and inventory['endpoint']==ENDPOINT and inventory['uid']==UID
        and inventory['raw_reference']==plan['raw_reference'] and inventory['frozen_manifest_reference']==plan['frozen_manifest_reference']
        and data['records']==C.N and data['uncompressed_bytes']==C.UNCOMPRESSED_BYTES and data['part_count']==500
        and data['all500_parts_equal_Main_SHA_rows_bytes'] is True and data['gzip_EOF_CRC_revalidated'] is True,'ACTUAL_COMPLETE500_A_NOT_A_PARTIAL_OR_FORECAST')
    account(plan['alpha_inventory_accounting_reference'],inventory['job_id'],ENDPOINT,UID,plan['parent_evidence_references'])
    Q.need(plan['data_references']==([] if A.phase(plan)=='QA0' else [data['source_index']]),'C_ONLY_ACTUAL_A_INDEX_DATA_PARTS_DEFERRED_IN_PRODUCER_PINNED_INDEX')
    Q.need(review.get('actual_profile_equivalence_and_cost_reviewed') is True,'C_ACTUAL_EQUIVALENCE_AND_COST_ROOT_REVIEW')
    Q.need(plan['accepted_profile_receipt_reference'] in plan['parent_evidence_references'],'ACTUAL_B_RECEIPT_APPROVED_PARENT')
    profile=Q.load_ref(plan['accepted_profile_receipt_reference'])
    Q.need(profile['schema']=='ALPHA_PUBCHEM_UNIFORM_PROFILE_RECEIPT_V1' and profile['mode']=='profile'
        and profile['status']=='ALPHA_UNIFORM10000_EQUIVALENT_PROFILE_COMPLETE' and profile['endpoint']==ENDPOINT and profile['uid']==UID
        and profile['raw_reference']==plan['raw_reference'] and profile['frozen_manifest_reference']==plan['frozen_manifest_reference']
        and profile['scope_parameters']==C.parameters('profile') and profile['uniform']['counts']==main_uniform['uniform']['counts']
        and profile['uniform']['completed_rows']==profile['uniform']['dispatched_rows']==10000
        and len(profile['uniform']['worker_records'])==16 and profile['comparison']['scientific_mismatches']==0
        and profile['comparison']['compared_rows']==10000 and profile['longest_diagnostic']['completed_rows']==16
        and profile['longest_excluded_from_uniform_mean'] is True and profile['full_source_pool_release_authorized'] is False,
        'ACTUAL_EQUIVALENT10000_B_C0_SCOPE_NOT_A_FUTURE_PIN_OR_POOL_RELEASE')
    account(plan['accepted_profile_accounting_reference'],profile['job_id'],ENDPOINT,UID,plan['parent_evidence_references'])
    core=[*(C.HERE/name for name in C.FILES),*(Path(row['target_reference']['path']) for row in manifest['files']),
          ROOT/'code/secondary_cpu_queue_v1/common.py',ROOT/'code/secondary_cpu_queue_v1/__init__.py']
    for path in core:Q.need(Q.ref(path) in profile['source_references'],'C_SAME_ACTUAL_B13_PLUS_FROZEN6_EXECUTION_CORE')
    for name in ('full_shard_manifest_reference','profile_output_budget_reference'):
        Q.need(plan[name] in plan['source_references'],'ROOT_FROZEN_SHARD_AUTHORITY:'+name)
    budget=Q.load_ref(plan['profile_output_budget_reference'])
    Q.need(budget['schema']=='ALPHA_PUBCHEM_PROFILE_DERIVED_OUTPUT_BUDGET_V1'
        and budget['status']=='ROOT_REVIEWED_ACTUAL_PROFILE_COST_AND_STORAGE'
        and budget['profile_receipt_reference']==plan['accepted_profile_receipt_reference']
        and budget['frozen_manifest_reference']==plan['frozen_manifest_reference'] and budget['uniform_rows']==10000
        and budget['longest_excluded_from_uniform_projection'] is True and budget['worst_case_feature_size_proven'] is False,
        'ACTUAL_PROFILE_DERIVED_COST_OUTPUT_NOT_A_FALSE_WORST_CASE_BOUND')
    limits=[row for row in budget['reviewed_shards'] if row['shard_index']==plan['shard_index']]
    Q.need(len(limits)==1 and (A.phase(plan)=='QA0' or (limits[0]['wall_seconds']==seconds and limits[0]['output_cap_bytes']==plan['output_cap_bytes'])),'EXACT_REVIEWED_SHARD_WALL_CAP')
    from secondary_pubchem_screening_alpha_v1.materialize_shards import validate as validate_manifest
    partition=validate_manifest(Q.load_ref(plan['full_shard_manifest_reference']))
    Q.need(partition['status']=='ROOT_FROZEN_EXCLUSIVE_SUBMISSION_MANIFEST'
        and partition['source_index_reference']==data['source_index']
        and partition['alpha_inventory_receipt_reference']==plan['alpha_inventory_receipt_reference']
        and partition['profile_receipt_reference']==plan['accepted_profile_receipt_reference']
        and partition['profile_output_budget_reference']==plan['profile_output_budget_reference'],'ACTUAL_A_B_BOUND_COMPLETE_MUTUALLY_EXCLUSIVE_MANIFEST')
    Q.need(type(plan['shard_index']) is int and 0<=plan['shard_index']<len(partition['shards']),'EXACT_FROZEN_SHARD_INDEX')
    matches=[row for row in partition['shards'] if row['shard_index']==plan['shard_index']]
    Q.need(len(matches)==1 and all(matches[0][name]==plan[name] for name in ('first_part','last_part','first_ordinal','last_ordinal')),'EXACT_FROZEN_SELECTED_FOUR_BOUNDS')
    authority_description={'source_population_N':C.N,'original_raw_SHA256':C.RAW_SHA,'complete_partition_parts':500,
        'requested_exclusive_part_range':[plan['first_part'],plan['last_part']],
        'requested_exclusive_ordinal_range':[plan['first_ordinal'],plan['last_ordinal']],
        'immutable_global_and_per_shard_claims_created_by_CPU_worker_only':True,'login_claim_writes':0,
        'claim_namespace':str(ROOT/'control/pubchem_ordinal_claims'/C.RAW_SHA),
        'automatic_claim_release_retry_or_pool_release':False,'actual_A_B_terminal_costs_required':True}
    A.validate(plan)
    authority_description.update(resource_phase=A.phase(plan),execution_permits_ordinal_claim=A.phase(plan)!='QA0',scientific_body_read_by_QA0=False)
    proof=Q.literal(plan['startup_proof_path']);out=Q.literal(plan['output_directory'])
    Q.need(ROOT/'artifacts' in out.parents and not out.exists() and len(str(out))<=1024,'NEW_PUBCHEM_C_OUTPUT_LEAF_REQUIRED')
    argv=[plan['python'],'-B','-m',A.module(A.phase(plan)),'--plan',str(Path(input_path)),'--startup-proof',str(proof)]
    Q.need(plan['execution_argv']==argv and Path(argv[0]).is_absolute(),'EXACT_PUBCHEM_C_PRIMARY_AND_ALL_EIGHT_ARGV_REQUIRED')
    return {'producer':'readonly','input_reference':Q.ref(input_path),'producer_argv':argv,'producer_plan_reference':Q.ref(input_path),
        'producer_review_reference':plan['root_review_reference'],'producer_authority_reference':plan['resource_authority_reference'],
        'source_references':list(refs.values()),'data_reference_locators_only':plan['data_references'],'data_body_hashes_claimed_by_controller':False,
        'startup_proof_path':str(proof),'science_output':str(out),'output_cap_bytes':plan['output_cap_bytes'],
        'producer_working_directory':str(ROOT/'code'),'proof_schema':spec['proof'],'request_kind':'analysis','pilot':spec['pilot'],
        'scope_key':key,'scope_parameters':params,'stage':spec['stage'],'scope_mode':spec['scope_mode'],
        'performance_profile':spec['performance_profile'],'fixed_archive_authority':authority_description}


def startup_proof(request,jid,raw,job,probe,storage,storage_reference,controller_evidence):
    if request['adapter']['scope_key']==FIXTURE_KEY:return fixture_startup_proof(request,jid,raw,job,probe,storage,storage_reference,controller_evidence)
    adapter=request['adapter']
    Q.need(adapter['producer']=='readonly' and adapter['scope_key'] in PROTOCOLS and request['kind']==adapter['request_kind']=='analysis'
        and request['pilot'] is adapter['pilot'] and request['scope_key']==adapter['scope_key']
        and request['scope_parameters']==adapter['scope_parameters'] and request['stage']==adapter['stage']
        and request['scope_mode']==adapter['scope_mode'] and request['performance_profile'] is adapter['performance_profile'],
        'ONLY_EXACT_NEW_RESOURCE_PHASE_QA0_OR_ORIGINAL51_PROTOCOL')
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
        'root_reviewed_exclusive_shard_only':True,'global_pool_release_authorized':False,
        'resource_phase':adapter['fixed_archive_authority']['resource_phase'],
        'QA0_no_DATA_or_claim_allowed':adapter['fixed_archive_authority']['resource_phase']=='QA0'}


def fixture_readonly(input_path,deployment_path,node,seconds):
    from pubchem_c_finite500_continuation_v3 import fixture_cpu as F
    Q.need(deployment_path is None,'NO_STATE5_DEPLOYMENT_OR_DYNAMIC_MODULE_WRAPPER');plan=Q.load(input_path);F.validate_metadata(plan)
    Q.need(plan['node']==node and node in Q.NODES and seconds==600 and plan['data_references']==[],'FIXED_STATE5_NODE_WALL_NO_DATA')
    out=Q.literal(plan['output_directory']);proof=Q.literal(plan['startup_proof_path'])
    Q.need(ROOT/'artifacts/pubchem_continuation_state5_alpha_v3' in out.parents and not out.exists(),'NEW_FIXED_STATE5_OUTPUT')
    argv=[plan['python'],'-B','-m',F.MODULE,'--plan',str(Path(input_path)),'--startup-proof',str(proof)]
    Q.need(plan['execution_argv']==argv and Path(argv[0]).is_absolute(),'EXACT_ONLY_STATE5_PRIMARY_ALL_OPTIONS')
    refs={r['path']:r for r in [*plan['source_references'],Q.ref(input_path),plan['root_review_reference']]}
    for r in refs.values():Q.verify(r)
    return {'producer':'readonly','input_reference':Q.ref(input_path),'producer_argv':argv,'producer_plan_reference':Q.ref(input_path),
        'producer_review_reference':plan['root_review_reference'],'producer_authority_reference':plan['resource_authority_reference'],
        'source_references':list(refs.values()),'data_reference_locators_only':[],'data_body_hashes_claimed_by_controller':False,
        'startup_proof_path':str(proof),'science_output':str(out),'output_cap_bytes':64<<20,'producer_working_directory':str(ROOT/'code'),
        'proof_schema':F.PROOF,'request_kind':'analysis','pilot':False,'scope_key':FIXTURE_KEY,'scope_parameters':F.PARAMETERS,
        'stage':F.STAGE,'scope_mode':F.MODE,'performance_profile':False,
        'fixed_archive_authority':{'only_state5':True,'tested_controller_sources':4,'range_authority_required':False,'Budget_or_DATA_or_claim_or_pool':False}}


def fixture_startup_proof(request,jid,raw,job,probe,storage,storage_reference,controller_evidence):
    from pubchem_c_finite500_continuation_v3 import fixture_cpu as F
    a=request['adapter'];Q.need(a['scope_key']==request['scope_key']==FIXTURE_KEY and a['producer_argv'][3]==F.MODULE
        and request['kind']==a['request_kind']=='analysis' and request['pilot'] is a['pilot'] is False
        and request['scope_parameters']==a['scope_parameters']==F.PARAMETERS and request['wall_seconds']==600
        and a['output_cap_bytes']==64<<20 and a['data_reference_locators_only']==[] and request['stage']==a['stage']==F.STAGE
        and request['scope_mode']==a['scope_mode']==F.MODE and request['performance_profile'] is a['performance_profile'] is False,
        'ONLY_FIXED_FIVE_STATE_TESTS_NOT_ARBITRARY_READONLY_CODE')
    Q.need(storage['storage_scope_review_reference']['path']==str(STORAGE_SCOPE),'EXACT_FRESH_STORAGE7_FOR_STATE5')
    return {'schema':F.PROOF,'endpoint':ENDPOINT,'uid':UID,'node':request['node'],'boot_id':probe['boot_id'],'job_id':str(jid),
        'observed_unix_seconds':probe['observed_unix_seconds'],'memory_policy':POLICY,'memory_limits_requested':False,'exclusive_requested':False,
        'script_reference':request['script_reference'],'controller_evidence':controller_evidence,'source_target_verification':request['verified_target_references'],
        'actual_gate_process':probe['gate_process'],'actual_memory_environment':probe['actual_memory_environment'],
        'other_jobs_modified':False,'forced_signals_sent':False,'job_metadata':raw,
        'request':{'kind':'analysis','pilot':False,'cpus':16,'memory_policy':POLICY,'wall_seconds':600,'execution_argv':a['producer_argv']},
        'plan_reference':a['producer_plan_reference'],'root_review_reference':a['producer_review_reference'],'account_free_bytes':storage['effective_free_bytes'],
        'effective_free_basis':storage['effective_free_basis'],'storage_observation_reference':storage_reference,'storage_observation':storage,
        'scope_key':FIXTURE_KEY,'stage':F.STAGE,'scope_mode':F.MODE,'performance_profile':False,'state_only_no_science_or_range':True}
