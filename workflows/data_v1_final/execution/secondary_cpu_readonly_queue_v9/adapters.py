"""Only one bounded retained24 Native72 diagnostic; login never opens data bodies."""
import csv,io
from collections import Counter
from pathlib import Path
from secondary_cpu_queue_v1.common import ROOT,ENDPOINT,UID,POLICY,need,ref,load,load_ref,verify,normalized,literal,read_small
KEY='pprime_native72_retained_raw_diagnosis_alpha_v1'
PROTOCOLS={KEY:{'plan':'SECONDARY_NATIVE72_RETAINED_RAW_DIAGNOSIS_PLAN_V1','proof':'SECONDARY_NATIVE72_RETAINED_RAW_DIAGNOSIS_STARTUP_V1',
    'stage':'PPRIME_NATIVE72_RETAINED_SCF_TERMINATION_FRAME','module':'native72_retained_raw_diagnosis_alpha_v1.run'}}
HERE=ROOT/'code/secondary_cpu_readonly_queue_v9'
OLD=ROOT/'code/frame_native_precision_alpha_v2'
REVIEW_FIELDS=('scope_key','scope_parameters','stage','endpoint','uid','run_root','node','cpus','memory_policy','pilot',
    'wall_seconds','output_cap_bytes','execution_argv','data_references','parent_evidence_references')
KINDS={'source_byte_copy':6,'main_diagnostic_provenance':3,'frozen_function_source':12,'small_metadata':7,
    'raw_sqlite_locator_no_main_SHA':72,'pinned_case_result_metadata':72,'actual_input_stat_locator':144,'prepared_input_stat_locator':144}
SCOPE={'parent_alpha_job_id':'1884789','original_main_job_id':'4521124','precision_diagnosis_job_id':'1884773',
 'maximum_PM7_B_raw_calls':12,'maximum_xtb_noisy_raw_calls':12,'exact_selected_raw_calls':24,'actual_program_input_bodies':24,
 'target_python':'3.11.14','target_numpy':'2.2.6','population_members_added':0,
 'maximum_atoms':80,'new_synthetic_methods':3,'new_fixtures_before_data':True,'prior_eight_fixture_PASS_required':True,
 'original_covariance_failures':15,'original_tolerances_changed':False,'new_QM_calls':0,'new_UFF_calls':0,
 'maximum_raw_bytes_per_call':16777216,'maximum_result_bytes_per_call':8388608,'maximum_actual_input_bytes_per_call':65536,
 'maximum_database_locator_bytes':67108864,'maximum_pending':16,'workers':16,'wall_seconds':1800,'dispatch_reserve_seconds':120,
 'algorithm_rss_soft_cap_bytes':8589934592,'minimum_mem_available_bytes':4294967296,'whole_output_cap_bytes':67108864,
 'maximum_report_bytes':16777216,'maximum_summary_bytes':262144,'maximum_case_evidence_bytes':1048576,
 'maximum_marker_evidence_lines':32,'maximum_line_characters':1024,'same_frozen_SCF_metadata_V2':True,
 'own_output_coordinates_only':True,'borrow_companion_output_frame':False,'normal_exit_implies_SCF_convergence':False,
 'physical_cause_proven_automatically':False,'scientific_PASS':False,'full_or2000_QM_release':False,'cost_overrun_action':'REPORT_AND_CONTINUE'}
DATA=[{'path':str(ROOT/'artifacts/pprime_native72_readonly_v2/v1/native72_report.json'),
       'bytes':2456111,'sha256':'0720c0fec59631ab02b6b574bf00933b31bd62062a38052b12c9de8375b77c8f'},
      {'path':str(ROOT/'inputs/native72_v1/main/runs/data_v1_20261025/artifacts/vector_frame_audit/cpu_auto_memory_20261026_v1/frame_evaluation.json'),
       'bytes':766822,'sha256':'36732244c5bcdaddfec9e22be847f3244076fdb3594d0ab8a663fbc9b3b91725'}]
CONFIG={'path':str(ROOT/'inputs/native72_v1/main/runs/data_v1_20261025/repository/configs/data_v1/pprime/vector_frame_audit_root_v1.json'),
    'bytes':6165,'sha256':'17d579c09ead14f01c747ca40d70796af1df0e6619f5ddcba334d595d94ad8fe'}
SMALL_SUMMARY={"bytes":36483,"path":"/gfshome/alpha/codex_data_v1_20261026/artifacts/native72_invariants_v2/v1/diagnosis_summary.json","sha256":"72724983b0109abfaaefaf3ef615e243cdc6eb2e334a9104cda4dd08ec7c6086"}
PARENT_ACCOUNT={"bytes":1657,"path":"/gfshome/alpha/codex_data_v1_20261026/control/secondary_cpu_queue/native72_invariants_v2/accounting_1793027680547697018.json","sha256":"f5b0ca51e89c41fa88b474f6d0584387e144cab3cc3f77b3e2bb99031e7a7cf5"}
PARENT_RAW_ACCOUNT={"bytes":273,"path":"/gfshome/alpha/codex_data_v1_20261026/control/secondary_cpu_queue/native72_invariants_v2/sacct_1793027680547697018.txt","sha256":"bd7de6956257072843e4b8ad92258c3c9c232f29e9983d6052fa9bc3ce048d8f"}
EXPECTED_FAILURES=[{"field":"pm7_dipole_Debye","group":["molecule_01200493","pm7","pm7_B"],"reason":"VECTOR_NOT_COVARIANT"},{"field":"pm7_gradient_kcal_mol_A","group":["molecule_01200493","pm7","pm7_B"],"reason":"VECTOR_NOT_COVARIANT"},{"field":"xtb_dipole_Debye","group":["molecule_01200493","pm7","xtb_perturbed_gradient"],"reason":"VECTOR_NOT_COVARIANT"},{"field":"xtb_gradient_Eh_bohr","group":["molecule_01200493","pm7","xtb_perturbed_gradient"],"reason":"VECTOR_NOT_COVARIANT"},{"field":"xtb_dipole_Debye","group":["molecule_01200493","pm7","xtb_singlepoint_noisy_companion"],"reason":"VECTOR_NOT_COVARIANT"},{"field":"pm7_dipole_Debye","group":["molecule_01201800","pm7","pm7_B"],"reason":"VECTOR_NOT_COVARIANT"},{"field":"pm7_gradient_kcal_mol_A","group":["molecule_01201800","pm7","pm7_B"],"reason":"VECTOR_NOT_COVARIANT"},{"field":"pm7_gradient_kcal_mol_A","group":["molecule_01201800","uff_sprime","pm7_B"],"reason":"VECTOR_NOT_COVARIANT"},{"field":"xtb_dipole_Debye","group":["molecule_01201800","uff_sprime","xtb_perturbed_gradient"],"reason":"VECTOR_NOT_COVARIANT"},{"field":"xtb_dipole_Debye","group":["molecule_01201800","uff_sprime","xtb_singlepoint_noisy_companion"],"reason":"VECTOR_NOT_COVARIANT"},{"field":"pm7_gradient_kcal_mol_A","group":["molecule_01207072","pm7","pm7_B"],"reason":"VECTOR_NOT_COVARIANT"},{"field":"pm7_gradient_kcal_mol_A","group":["molecule_01207072","uff_sprime","pm7_B"],"reason":"VECTOR_NOT_COVARIANT"},{"field":"pm7_gradient_kcal_mol_A","group":["principal_00112266","pm7","pm7_B"],"reason":"VECTOR_NOT_COVARIANT"},{"field":"xtb_dipole_Debye","group":["principal_00112266","pm7","xtb_perturbed_gradient"],"reason":"VECTOR_NOT_COVARIANT"},{"field":"xtb_dipole_Debye","group":["principal_00112266","pm7","xtb_singlepoint_noisy_companion"],"reason":"VECTOR_NOT_COVARIANT"}]
OLD_HELPERS=[{"path":"/gfshome/alpha/codex_data_v1_20261026/code/frame_native_precision_alpha_v2/__init__.py","sha256":"f0fa5b74e3491e16039bfd91bc42ac5d4c300c4be2a4803a504882e142025d7f","bytes":89},{"path":"/gfshome/alpha/codex_data_v1_20261026/code/frame_native_precision_alpha_v2/precision.py","sha256":"1de0073f2face3b0b40a70e5a95b7ef98b1c2ee1ed2746bb33ac79791f2986d2","bytes":6476},{"path":"/gfshome/alpha/codex_data_v1_20261026/code/frame_native_precision_alpha_v2/tokens.py","sha256":"8b1e7fdf21a0fc77b0684727750f8d3cf9947a30ee2a5ff33fbf1e398fb529fc","bytes":4657},{"path":"/gfshome/alpha/codex_data_v1_20261026/code/frame_native_precision_alpha_v2/math_v1.py","sha256":"98db545b56f87b4fb2fc4c0f7ad69c3e6f05ebbe507f4d19369a037599241e24","bytes":9377},{"path":"/gfshome/alpha/codex_data_v1_20261026/code/frame_native_precision_alpha_v2/raw_reader.py","sha256":"f13d3b2ba7869dd8b402c621ba21f5957d6635ffd4d68567c9dccaeafd4d708a","bytes":4317},{"path":"/gfshome/alpha/codex_data_v1_20261026/code/frame_native_precision_alpha_v2/read_outputs_v1.py","sha256":"ba56625441ca390e24d00fe3f630c05dee3d38861614c25a2fcec93a16599849","bytes":5328},{"path":"/gfshome/alpha/codex_data_v1_20261026/code/frame_native_precision_alpha_v2/relocation.py","sha256":"9cea98a7db51e05d09084335d22f6169f3166eca45f691346336efd7934b1439","bytes":12606},{"path":"/gfshome/alpha/codex_data_v1_20261026/code/frame_native_precision_alpha_v2/origin_inventory.json","sha256":"83e58412628c6c0048f39b9cdc8f8ddda2bfe181eca8f9d7d74b40f9d99022cf","bytes":546050}]

def archive_authority(plan):
    need(plan['relocation_map_reference'] in plan['source_references'],'FROZEN460_TRANSITIVE_ARCHIVE_AUTHORITY_MUST_BE_APPROVED')
    mapping=load_ref(plan['relocation_map_reference']);inventory_ref=ref(OLD/'origin_inventory.json')
    need(mapping.get('schema')=='NATIVE72_READONLY_RELOCATION_MAP_V1' and mapping.get('origin_inventory_reference')==inventory_ref
        and inventory_ref in plan['source_references'] and inventory_ref['bytes']==546050
        and inventory_ref['sha256']=='83e58412628c6c0048f39b9cdc8f8ddda2bfe181eca8f9d7d74b40f9d99022cf','EXACT_ORIGINAL460_INVENTORY_BYTES_REQUIRED')
    inventory=load_ref(inventory_ref);expected={row['origin']['path']:row for row in inventory['entries']};entries=mapping['entries']
    need(len(expected)==len(inventory['entries'])==len(entries)==460 and dict(Counter(row['kind'] for row in entries))==KINDS,
        'COMPLETE_FROZEN460_MEMBER_AND_KIND_SET_REQUIRED')
    origins=set();targets=set();source_kinds={'source_byte_copy','main_diagnostic_provenance','frozen_function_source','small_metadata'}
    no_sha={'raw_sqlite_locator_no_main_SHA','actual_input_stat_locator','prepared_input_stat_locator'};body_paths={row['path'] for row in DATA}
    for row in entries:
        origin=row['origin'];target=row['target_reference'];old=origin['path'];new=target['path'];literal(new)
        need(old in expected and old not in origins and new not in targets,'UNIQUE_FROZEN_ORIGIN_AND_TARGET_REQUIRED');frozen=expected[old]
        need(origin==frozen['origin'] and row['kind']==frozen['kind'] and new==frozen['target_locator']
            and row.get('origin_stat')==frozen.get('origin_stat') and target['bytes']==origin['bytes'],'ORIGINAL_ARCHIVE_LOCATORS_MUST_NOT_BE_REWRITTEN')
        if origin.get('sha256') is None:
            need(row['kind'] in no_sha and set(target)=={'path','bytes'},'NO_INVENTED_MAIN_WHOLE_DATABASE_OR_INPUT_SHA')
        else:need(set(target)=={'path','bytes','sha256'} and target['sha256']==origin['sha256'],'EXACT_ORIGINAL_PINNED_COPY_SHA_REQUIRED')
        if row['kind'] in source_kinds and new not in body_paths:
            need(target in plan['source_references'],'EVERY_REUSED_FROZEN_SMALL_SOURCE_MUST_BE_APPROVED')
        origins.add(old);targets.add(new)
    return {'fixed_transitive_locator_count':460,'selected_calls_after_new3_fixtures':24,'raw_SQLite_bodies_read_by_login':0,
        'whole_Main_database_SHA_claimed':False,'hash_basis':'FROZEN_PER_CALL_SHA_PLUS_PRIOR_ACTUAL_ALPHA_DB_SHA_AND_INPUT_METADATA'}


def readonly(input_path,deployment_path,node,seconds,**unused):
    need(deployment_path is None,'RETAINED24_HAS_NO_DEPLOYMENT_WRAPPER')
    plan=load(input_path);protocol=PROTOCOLS[KEY];refs={}
    need(plan.get('schema')==protocol['plan'] and plan.get('producer_key')==plan.get('scope_key')==KEY
        and plan.get('stage')==protocol['stage'] and plan.get('scope_parameters')==SCOPE and plan.get('kind')=='analysis'
        and plan.get('pilot') is False and plan.get('endpoint')==ENDPOINT and plan.get('uid')==UID and plan.get('run_root')==str(ROOT)
        and plan.get('node')==node and plan.get('cpus')==16 and plan.get('memory_policy')==POLICY
        and type(plan.get('wall_seconds')) is int and plan['wall_seconds']==seconds==1800 and plan.get('output_cap_bytes')==64<<20
        and plan.get('data_references')==DATA,'ONLY_EXACT_RETAINED24_RAW_DIAGNOSIS_SCOPE_ALLOWED')
    review=load_ref(plan['root_review_reference'])
    need(review.get('schema')=='EXACT_SECONDARY_BOUNDED_READONLY_ROOT_REVIEW_V1' and review.get('status')=='APPROVED_FOR_EXACT_STAGE'
        and review.get('reviewer')=='root','EXACT_RETAINED24_ROOT_REVIEW_REQUIRED')
    for key in REVIEW_FIELDS:need(plan[key]==review[key],'EXACT_RETAINED24_REVIEW_FIELD_DIFFERS:'+key)
    need(plan['source_references']==review['approved_source_references'],'EXACT_RETAINED24_REVIEWED_SOURCE_SET')
    body_paths={row['path'] for row in DATA}
    need(not any(row['path'] in body_paths for row in [*plan['source_references'],*plan['parent_evidence_references']]),
        'OLD_REPORT_DATA_BODIES_CANNOT_BE_PRE_FIXTURE_METADATA')
    for value in [*plan['source_references'],*plan['parent_evidence_references'],ref(input_path),plan['root_review_reference']]:
        value=normalized(value);verify(value);need(value['path'] not in refs or refs[value['path']]==value,'CONFLICTING_RETAINED24_SOURCE_PIN')
        refs[value['path']]=value
    primary=ROOT/'code/native72_retained_raw_diagnosis_alpha_v1/run.py'
    for path in primary.parent.iterdir():
        if path.is_file() and path.suffix in {'.py','.json','.md'}:need(ref(path) in plan['source_references'],'EVERY_NEW_RETAINED24_SOURCE_MUST_BE_APPROVED')
    for path in (HERE/'controller.py',HERE/'adapters.py',ROOT/'code/secondary_cpu_queue_v1/common.py',ROOT/'code/secondary_cpu_queue_v1/__init__.py'):
        need(ref(path) in plan['source_references'],'ACTUAL_V9_AND_BASE_SOURCES_MUST_BE_APPROVED')
    for value in (CONFIG,SMALL_SUMMARY,PARENT_ACCOUNT,PARENT_RAW_ACCOUNT,*OLD_HELPERS):
        need(value in plan['source_references'],'EXACT_RETAINED24_SMALL_AUTHORITY_OR_HELPER_REQUIRED')
    for value in (SMALL_SUMMARY,PARENT_ACCOUNT,PARENT_RAW_ACCOUNT):need(value in plan['parent_evidence_references'],'ACTUAL789_PARENT_PIN_REQUIRED')
    summary=load_ref(SMALL_SUMMARY);account=load_ref(PARENT_ACCOUNT);parent=account['actual_parent']
    need(summary.get('technical_analysis_complete') is True and summary.get('original15FAIL_preserved') is True
        and summary.get('retained_original_failure_rows')==15 and summary['fixture_receipt']['status']=='PASS'
        and summary['fixture_receipt']['tests_run']==8 and summary['full_or2000_release']=='HOLD'
        and parent['JobIDRaw']=='1884789' and parent['State']=='COMPLETED' and parent['ExitCode']=='0:0'
        and parent['UID']=='1264' and parent['AllocCPUS']=='16' and parent['NodeList']=='compute-0-6'
        and account['raw_sacct_reference']==PARENT_RAW_ACCOUNT and account['endpoint']==ENDPOINT and account['uid']==UID,'ACTUAL789_C0_EIGHT_FIXTURE15FAIL_PARENT_REQUIRED')
    raw=list(csv.DictReader(io.StringIO(read_small(verify(PARENT_RAW_ACCOUNT)).decode()),delimiter='|'));found=[row for row in raw if row.get('JobIDRaw')=='1884789']
    need(len(found)==1 and all(found[0][key]==parent[key] for key in ('State','ExitCode','UID','ElapsedRaw','AllocCPUS','NodeList','Partition'))
        and account['allocated_core_seconds_observed']==int(parent['ElapsedRaw'])*16,'ACTUAL789_RAW_COST_MUST_BE_RETAINED')
    for key in ('resource_authority_reference','cost_decision_reference'):need(plan[key] in plan['source_references'],'ACTUAL_RETAINED24_AUTHORITY_SOURCE_REQUIRED')
    proof=literal(plan['startup_proof_path']);out=literal(plan['output_directory']);need(ROOT/'artifacts' in out.parents,'NEW_RETAINED24_OUTPUT_LEAF_REQUIRED')
    argv=[plan['python'],'-B','-m',protocol['module'],'--plan',str(Path(input_path)),'--startup-proof',str(proof)]
    need(plan['execution_argv']==argv and Path(argv[0]).is_absolute(),'EXACT_RETAINED24_PRIMARY_AND_ALL_EIGHT_ARGV_REQUIRED')
    archive=archive_authority(plan)
    return {'producer':'readonly','input_reference':ref(input_path),'producer_argv':argv,'producer_plan_reference':ref(input_path),
        'producer_review_reference':plan['root_review_reference'],'producer_authority_reference':plan['resource_authority_reference'],
        'source_references':list(refs.values()),'data_reference_locators_only':DATA,'data_body_hashes_claimed_by_controller':False,
        'startup_proof_path':str(proof),'science_output':str(out),'output_cap_bytes':plan['output_cap_bytes'],
        'producer_working_directory':str(ROOT/'code'),'proof_schema':protocol['proof'],'request_kind':'analysis','pilot':False,
        'scope_key':KEY,'scope_parameters':SCOPE,'stage':protocol['stage'],'scope_mode':'BOUNDED_READONLY_ANALYSIS','performance_profile':False,'fixed_archive_authority':archive}

def startup_proof(request,jid,raw,job,probe,storage,storage_reference,controller_evidence):
    adapter=request['adapter']
    need(adapter['producer']=='readonly' and adapter['scope_key'] in PROTOCOLS and request['kind']==adapter['request_kind']=='analysis'
        and request['pilot'] is adapter['pilot'] and request['scope_key']==adapter['scope_key']
        and request['scope_parameters']==adapter['scope_parameters'] and request['stage']==adapter['stage']
        and request['scope_mode']==adapter['scope_mode'] and request['performance_profile'] is adapter['performance_profile'],
        'ONLY_EXACT_RETAINED24_RAW_DIAGNOSIS_REQUEST_PROTOCOL_ALLOWED')
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


