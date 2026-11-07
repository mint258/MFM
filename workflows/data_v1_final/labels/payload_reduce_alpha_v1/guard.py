"""New Alpha-only reducer startup authority, independent of either scan proof."""
from __future__ import annotations
import copy,csv,io,os,socket,sys,time
from pathlib import Path
from payload_audit_alpha_v1.relocation import ROOT,FROZEN,MAP,mapping,resolved_reference
from payload_audit_alpha_v1.support import load,small_ref,require,need
from payload_audit_alpha_v1.resource_runtime import start_observer
from .inputs import KINDS,triple,build_inventory

KEY='labels_payload512_reduce_readonly_alpha_v1'
STAGE='LABEL_PAYLOAD512_EXISTING_VALUES_REDUCTION'
PARAMETERS={'parent_alpha_job_id':'1884788','original_main_job_id':'4521327','input_molecules':512,'input_records':4251,
 'source_TRAIN_records':4211,'source_VAL_records':20,'source_FULL_records':20,'input_shard_manifests':1,'source_owner_groups':16,
 'group_details_files':16,'candidate_mask_files':16,'coverage_files':16,'selection_owner_index_files':16,'expected_role_files':1,
 'reduction_body_files':65,'global_role_records':11231854,'task_types':14,'expected_task_slots':59514,'coverage_output_bytes':157245956,
 'enabled_components':146,'registered_components':264,'synthetic_test_methods':6,'all6_tests_before_any_body_reads':True,
 'body_hash_after_tests_in_this_allocation':True,'body_hash_workers':16,'new_QM_calls':0,'new_UFF_calls':0,
 'source_values_read_only':True,'original_JSON_paths_rewritten':False,'Main_runtime_proof_reused':False,
 'scan_runtime_proof_reused_as_startup':False,'median_MAD_refit':False,'matched_pilot_TRAIN_reference_only':True,
 'full_or_export_or_final_D4_release':False,'minimum_mem_available_bytes':4294967296,
 'target_python':'3.11.14','target_numpy':'2.2.6','target_rdkit':'2025.09.5','target_pyarrow':'17.0.0','Main_pyarrow_major':25}
NODES={'compute-0-1','compute-0-3','compute-0-4','compute-0-5','compute-0-6','sonmi1'}

def actual_parent(plan):
    account=load(require(plan['parent_accounting_reference']));parent=account['actual_parent']
    need(account.get('query_returncode')==0 and account.get('endpoint')=='218.192.171.238:22' and account.get('uid')==1264,
      'ACTUAL_ALPHA_PARENT_ACCOUNTING_REQUIRED')
    need(parent.get('JobIDRaw')=='1884788' and parent.get('State')=='COMPLETED' and parent.get('ExitCode')=='0:0'
      and parent.get('UID')=='1264' and parent.get('AllocCPUS')=='16' and parent.get('Partition')=='cpu'
      and parent.get('NodeList') in NODES,'EXACT_ACTUAL_C0_ALPHA_SCAN_PARENT')
    raw=account['raw_sacct_reference'];need(raw==plan['parent_accounting_raw_reference'],'ACTUAL_PARENT_RAW_PIN_DIFFERS')
    rows=list(csv.DictReader(io.StringIO(require(raw).read_text()),delimiter='|'))
    matches=[row for row in rows if row.get('JobIDRaw')=='1884788']
    need(len(matches)==1 and all(matches[0].get(k)==parent.get(k) for k in ('State','ExitCode','UID','ElapsedRaw','AllocCPUS','NodeList','Partition'))
      and account.get('allocated_core_seconds_observed')==int(parent['ElapsedRaw'])*16,'RAW_ACTUAL_PARENT_AND_COST_DIFFER')

def require_startup(plan_path,proof_path):
    plan=load(plan_path);proof=load(proof_path);primary=ROOT/'code/payload_reduce_alpha_v1/run.py'
    need(plan['schema']=='SECONDARY_LABEL_PAYLOAD512_REDUCE_READONLY_PLAN_V1'
      and proof['schema']=='SECONDARY_LABEL_PAYLOAD512_REDUCE_READONLY_STARTUP_V1','EXACT_NEW_ALPHA_REDUCER_PLAN_PROOF')
    for key,value in (('scope_key',KEY),('stage',STAGE),('endpoint','218.192.171.238:22'),('uid',1264)):
        need(plan[key]==proof[key]==value,'NEW_ALPHA_REDUCER_SCOPE_ENDPOINT_UID:'+key)
    need(plan['producer_key']==KEY and plan['scope_parameters']==PARAMETERS,'EXACT_ALPHA_REDUCER_PARAMETERS')
    need(plan['run_root']==str(ROOT) and plan['kind']=='analysis' and plan['pilot'] is False and plan['cpus']==16,'ALPHA_REDUCER_ANALYSIS_NONPILOT16')
    need(plan['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED' and 0<plan['wall_seconds']<=3600 and plan['output_cap_bytes']==2<<30,'ALPHA_REDUCER_NO_MEMORY_ONE_HOUR_TWO_GIB')
    need(plan['resource_evidence_output_cap_bytes']==64<<20 and plan['resource_evidence_output']==plan['output_directory']+'_resource_observation','SEPARATE_OBSERVER64MIB_RESERVATION')
    need(proof['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED' and proof['memory_limits_requested'] is False and proof['exclusive_requested'] is False,'NO_MEMORY_REQUEST_OR_EXCLUSIVE')
    need(plan['output_directory']==str(ROOT/'artifacts/labels_payload512_readonly_v1/reduction_v1'),'EXACT_NEW_LEGAL_REDUCER_OUTPUT_PREFIX')
    node=socket.gethostname().split('.')[0]
    need(os.getuid()==1264 and os.environ.get('SLURM_JOB_ID')==str(proof['job_id']) and node==plan['node']==proof['node'] and node in NODES,'ACTUAL_NEW_ALPHA_REDUCER_IDENTITY')
    need(os.environ.get('SLURM_JOB_PARTITION')=='cpu' and os.environ.get('SLURM_CPUS_PER_TASK')=='16' and os.environ.get('CUDA_VISIBLE_DEVICES')=='','ACTUAL_ALPHA_CPU16_ONLY')
    boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    need(proof['boot_id']==boot and 0<=time.time()-proof['observed_unix_seconds']<=120,'ACTUAL_NEW_ALPHA_BOOT_FRESH_TARGET_CLOCK')
    need(str(proof['job_id']) not in {'1884787','1884788','4521327'},'PARENT_OR_MAIN_PROOF_IS_NOT_NEW_STARTUP')
    need(proof['plan_reference']==small_ref(plan_path) and proof['root_review_reference']==plan['root_review_reference'],'EXACT_NEW_ALPHA_PLAN_REVIEW_PINS')
    request=proof['request']
    need(request['kind']=='analysis' and request['pilot'] is False and request['cpus']==16 and request['wall_seconds']==plan['wall_seconds'],'EXACT_NEW_ALPHA_NONPILOT_REQUEST_SCOPE')
    expected=[plan['python'],'-B','-m','payload_reduce_alpha_v1.run','--plan',str(Path(plan_path).absolute()),'--startup-proof',str(Path(proof_path).absolute())]
    need(plan['execution_argv']==request['execution_argv']==expected and sys.argv[1:]==expected[4:],'ACTUAL_NEW_ALPHA_REDUCER_ARGV')
    need(Path(sys.modules['__main__'].__file__).absolute()==primary and Path(sys.executable).absolute()==Path(plan['python']),'ACTUAL_NEW_ALPHA_REDUCER_PRIMARY_PYTHON')
    review=load(require(plan['root_review_reference']))
    need(review['schema']=='EXACT_SECONDARY_BOUNDED_READONLY_ROOT_REVIEW_V1' and review['status']=='APPROVED_FOR_EXACT_STAGE' and review['reviewer']=='root','NEW_EXACT_ALPHA_ROOT_REVIEW')
    keys=('scope_key','scope_parameters','stage','endpoint','uid','run_root','node','cpus','memory_policy','pilot','wall_seconds','output_cap_bytes',
      'execution_argv','data_references','data_total_bytes','parent_evidence_references','resource_evidence_output','resource_evidence_output_cap_bytes')
    for key in keys:need(review[key]==plan[key],'EXACT_ALPHA_REDUCER_ROOT_REVIEW:'+key)
    need(review['approved_source_references']==plan['source_references'],'EXACT_APPROVED_REDUCER_SOURCES')
    need(not ({r['path'] for r in plan['source_references']}&{r['path'] for r in plan['data_references']}),'BODY_INPUT_CANNOT_BE_HASHED_AS_PRE_FIXTURE_SOURCE')
    for pin in plan['source_references']:
        need(pin['bytes']<=2<<20,'ONLY_SMALL_SOURCE_PINS_BEFORE_FIXTURES');require(pin)
    for pin in plan['parent_evidence_references']:
        need(pin in plan['source_references'],'EVERY_PARENT_EVIDENCE_PIN_APPROVED_SMALL_SOURCE')
    for directory in (primary.parent,ROOT/'code/payload_audit_alpha_v1'):
        for path in directory.iterdir():
            if path.is_file() and path.suffix in ('.py','.json','.md'):need(small_ref(path) in plan['source_references'],'EVERY_NEW_AND_REUSED_ALPHA_SOURCE_PIN')
    for key in ('config_reference','owner_plan_reference','input_inventory_reference','origin_inventory_reference','relocation_map_reference',
      'fixture_auxiliary_config_reference','fixture_auxiliary_original_reference','fixture_auxiliary_transform_reference','source_equivalence_reference','storage_reservation_reference'):
        need(plan[key] in plan['source_references'],'EXPLICIT_APPROVED_REDUCER_AUTHORITY:'+key)
    for key in ('scan_manifest_reference','scan_plan_reference','scan_startup_proof_reference','scan_transfer_verification_reference',
      'scan_fixture_gate_reference','parent_accounting_reference','parent_accounting_raw_reference'):
        need(plan[key] in plan['parent_evidence_references'],'EXACT_REAL_SCAN_PARENT_EVIDENCE:'+key)
    actual_parent(plan)
    origin=load(require(plan['origin_inventory_reference']));m=mapping();need(plan['relocation_map_reference']==small_ref(MAP),'EXACT_FROZEN_281_RELOCATION_MAP')
    expected_rows={r['origin_reference']['path']:r for r in [*origin['data'],*origin['small']]}
    need(len(origin['data'])==227 and len(origin['small'])==54 and len(m['body']['entries'])==281 and set(m['origin'])==set(expected_rows),'UNCHANGED_227_PLUS54_RELOCATION_MEMBERS')
    for old,row in m['origin'].items():
        expected_row=expected_rows[old]
        need(row['origin_reference']==expected_row['origin_reference'] and triple(row['target_reference'])==triple(expected_row['target_locator']),'UNCHANGED_281_RELOCATION_TRIPLES')
    for row in origin['small']:need(resolved_reference(row['origin_reference']) in plan['source_references'],'EVERY_REUSED_FROZEN_SMALL_SOURCE_PIN')
    cfg=load(require(plan['config_reference']));owner=load(require(plan['owner_plan_reference']));manifest=load(require(plan['scan_manifest_reference']))
    scan_plan=load(require(plan['scan_plan_reference']));scan_proof=load(require(plan['scan_startup_proof_reference']))
    need(Path(plan['scan_manifest_reference']['path'])==ROOT/'artifacts/labels_payload512_readonly_v1/v2/manifest.json'
      and scan_plan['output_directory']==str(Path(plan['scan_manifest_reference']['path']).parent),'ACTUAL_SUCCESSFUL_V2_OUTPUT_PREFIX')
    need(str(scan_proof['job_id'])=='1884788' and scan_proof['uid']==1264 and scan_proof['endpoint']=='218.192.171.238:22'
      and scan_proof['plan_reference']==plan['scan_plan_reference'] and scan_plan['root_review_reference'] in plan['parent_evidence_references']
      and scan_proof['root_review_reference']==scan_plan['root_review_reference'],'ACTUAL_SCAN_PLAN_PROOF_AND_ROOT_REVIEW_PARENT_ONLY')
    need(plan['config_reference']['bytes']==3861 and plan['config_reference']['sha256']=='48357da799b8772a4b18c1288aa5e582daf6c5c1126f7bbb4927cf4c852f5528','ORIGINAL_SCIENTIFIC_CONFIG_BYTES_REQUIRED')
    need(plan['owner_plan_reference']==resolved_reference(cfg['sources']['plan']),'ORIGINAL_OWNER_PLAN_COPY_REQUIRED')
    inventory=load(require(plan['input_inventory_reference']));reports=[]
    for pin in inventory['group_report_references']:
        need(pin in plan['source_references'],'EVERY_ACTUAL_GROUP_REPORT_PIN');reports.append(load(require(pin)))
    rebuilt=build_inventory(manifest,plan['scan_manifest_reference'],cfg,plan['config_reference'],owner,plan['owner_plan_reference'],
      m['body'],plan['relocation_map_reference'],reports,inventory['source_small_metadata_observed'])
    need(inventory==rebuilt and inventory['kind_counts']==KINDS,'SIXTY_FIVE_INPUT_INVENTORY_REBUILT_FROM_REAL_REPORTS')
    need(inventory['body_files']==65 and inventory['body_bytes']==38437705,'EXACT_ACTUAL_PARENT_SIXTY_FIVE_INPUT_BYTES')
    need(plan['data_references']==[r['reference'] for r in inventory['entries']] and plan['data_total_bytes']==inventory['body_bytes'],'EXACT_EXPECTED_DATA_LOCATORS_NOT_PREVERIFIED')
    detail_bytes=sum(r['reference']['bytes'] for r in inventory['entries'] if r['kind']=='group_details')
    report_bytes=sum(r['bytes'] for r in inventory['group_report_references'])
    need(detail_bytes+2*report_bytes+157245956+(32<<20)<=plan['output_cap_bytes'],'CONSERVATIVE_REDUCTION_OUTPUT_ENVELOPE')
    need(plan['transfer_verification_reference'] is None and plan['transfer_verification_expected_output_path']==str(Path(plan['output_directory'])/'input_verification.json'),'FUTURE_INPUT_HASH_RECEIPT_NOT_PRECLAIMED')
    need(manifest['actual_transfer_verification']==plan['scan_transfer_verification_reference'] and manifest['pre_scan_fixture_gate']==plan['scan_fixture_gate_reference'],'REAL_SCAN_HASH_AND_FIXTURE_RECEIPTS')
    prior_hash=load(require(plan['scan_transfer_verification_reference']));prior_gate=load(require(plan['scan_fixture_gate_reference']))
    need(prior_hash['status']=='ACTUAL_ALL227_SHA_PASS' and str(prior_hash['job_id'])=='1884788' and prior_hash['uid']==1264
      and prior_hash['body_count']==227 and prior_hash['pre_scan_fixture_gate']==plan['scan_fixture_gate_reference'],'ACTUAL_SCAN227_HASH_PARENT_CLOSURE')
    need(prior_gate['status']=='PASS' and prior_gate['counts']['run']==6,'ACTUAL_SCAN_SIX_FIXTURES_PARENT_CLOSURE')
    auxiliary=plan['fixture_auxiliary_config_reference'];need(Path(auxiliary['path'])==FROZEN/'configs/data_v1/labels/streaming_v1.json','ORIGINAL_FIXTURE_PACKAGE_DEPTH')
    original_ref=plan['fixture_auxiliary_original_reference']
    need(original_ref['bytes']==4022 and original_ref['sha256']=='92445408cf6a64de2e3b30e41cb0ee99136046acaf6f4848faeb3e8b80694bb3','EXACT_ORIGINAL_STREAMING_FIXTURE_CONFIG')
    original=load(require(original_ref));expected_aux=copy.deepcopy(original)
    expected_aux['adapter_source_pins']=[resolved_reference(p) for p in original['adapter_source_pins']]
    need(len(expected_aux['adapter_source_pins'])==4 and load(require(auxiliary))==expected_aux,'ONLY_FOUR_EXISTING_ADAPTER_PATHS_CHANGED')
    equivalence=load(require(plan['source_equivalence_reference']));need(equivalence['status']=='PASS' and equivalence['schema']=='ALPHA_LABEL_PAYLOAD512_REDUCER_SOURCE_EQUIVALENCE_V1','ACTUAL_SOURCE_ONLY_REDUCER_EQUIVALENCE_PROOF')
    need(equivalence['science_reduction_body_inverse_source_bytes_equal'] is True and equivalence['science_reduction_body_inverse_AST_equal'] is True,'ACTUAL_REDUCTION_CORE_BYTES_AND_AST_PROOF')
    for recorded,actual in ((equivalence['alpha_reducer_reference'],small_ref(primary)),
      (equivalence['original_reducer_reference'],small_ref(FROZEN/'workflows/data_v1_final/labels/payload_audit_v1/reduce.py')),
      (equivalence['coverage_helper_module_reference'],small_ref(FROZEN/'workflows/data_v1_final/labels/source_status_v1/reduce.py')),
      (equivalence['unchanged_numeric_shape_mask_kernel_reference'],small_ref(FROZEN/'workflows/data_v1_final/labels/payload_audit_v1/payload.py')),
      (equivalence['unchanged_six_fixture_source_reference'],small_ref(FROZEN/'workflows/data_v1_final/labels/payload_audit_v1/test_payload.py'))):
        need(all(recorded[k]==actual[k] for k in ('bytes','sha256')),'SOURCE_EQUIVALENCE_EXACT_BYTES_BINDING')
    import numpy,pyarrow,rdkit
    environment={'python':'.'.join(str(x) for x in sys.version_info[:3]),'numpy':numpy.__version__,'pyarrow':pyarrow.__version__,'rdkit':rdkit.__version__,
      'executable':sys.executable,'Main_pyarrow_major':25,'different_Arrow_version_is_not_scientific_acceptance':True}
    need((environment['python'],environment['numpy'],environment['pyarrow'],environment['rdkit'])==('3.11.14','2.2.6','17.0.0','2025.09.5'),'ACTUAL_ALPHA_REDUCER_ENVIRONMENT')
    need(proof['account_free_bytes']-((2<<30)+(64<<20))>=200_000_000_000,'ACTUAL_ALPHA_QUOTA_PLUS_REDUCER_AND_OBSERVER_RESERVATIONS')
    binding={'resource_evidence_output':plan['resource_evidence_output'],'memavailable_soft_floor_bytes':4<<30,'resource_evidence_local_cap_bytes':64<<20}
    start_observer(proof,binding)
    return dict(plan,actual_environment=environment),proof
