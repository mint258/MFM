"""Independent Alpha startup authority; never evaluates or reuses Main guards."""
from __future__ import annotations
import copy,json,os,socket,sys,time
from pathlib import Path
from .relocation import ROOT,FROZEN,MAP,mapping,resolved_reference
from .support import load,small_ref,require,need
from .resource_runtime import start_observer
KEY='labels_payload512_readonly_alpha_v1'
STAGE='LABEL_PAYLOAD512_EXISTING_VALUES_PILOT'
PARAMETERS={'original_main_job_id':'4521327','input_molecules':512,'input_records':4251,'source_TRAIN_records':4211,
 'source_VAL_records':20,'source_FULL_records':20,'source_owner_jobs':16,'family_parquet_files':209,
 'selection_owner_index_files':16,'canonical_index_files':1,'scan_required_body_files':226,
 'scan_required_body_bytes':2703431455,'transfer_hash_body_files':227,'transfer_hash_body_bytes':2714663309,
 'role_ledger_reduce_only_files':1,'synthetic_test_methods':6,'all6_tests_before_any_body_reads':True,
 'body_hash_after_tests_in_this_allocation':True,'body_hash_workers':16,'expected_task_slots':59514,'task_types':14,
 'enabled_components':146,'registered_components':264,'new_QM_calls':0,'new_UFF_calls':0,'source_values_read_only':True,
 'original_JSON_paths_rewritten':False,'Main_runtime_proof_reused':False,'full_or_export_or_final_D4_release':False,
 'algorithm_worker_rss_soft_cap_bytes':3221225472,'minimum_mem_available_bytes':4294967296,
 'target_python':'3.11.14','target_numpy':'2.2.6','target_rdkit':'2025.09.5','target_pyarrow':'17.0.0','Main_pyarrow_major':25}

def require_startup(plan_path,proof_path,config_path):
    plan=load(plan_path);proof=load(proof_path);primary=ROOT/'code/payload_audit_alpha_v1/run.py'
    need(plan['schema']=='SECONDARY_LABEL_PAYLOAD512_READONLY_PLAN_V1' and proof['schema']=='SECONDARY_LABEL_PAYLOAD512_READONLY_STARTUP_V1','EXACT_NEW_ALPHA_PLAN_PROOF')
    for key,value in (('scope_key',KEY),('stage',STAGE),('endpoint','218.192.171.238:22'),('uid',1264)):
        need(plan[key]==proof[key]==value,'ALPHA_SCOPE_ENDPOINT_UID:'+key)
    need(plan['producer_key']==KEY and plan['scope_parameters']==PARAMETERS,'EXACT_LABELS512_PARAMETERS')
    need(plan['run_root']==str(ROOT) and plan['kind']=='analysis' and plan['pilot'] is True and plan['cpus']==16,'ALPHA_ANALYSIS_PILOT16')
    need(plan['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED' and plan['wall_seconds']==7200 and plan['output_cap_bytes']==8<<30,'EXACT_ALPHA_NO_MEMORY_RESOURCE_POLICY')
    need(proof['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED' and proof['memory_limits_requested'] is False and proof['exclusive_requested'] is False,'NO_MAIN_MEMORY_GUARD_REUSE')
    node=socket.gethostname().split('.')[0]
    need(os.getuid()==1264 and os.environ.get('SLURM_JOB_ID')==str(proof['job_id']) and node==plan['node']==proof['node'],'ACTUAL_ALPHA_JOB_NODE_UID')
    need(node in {'compute-0-1','compute-0-3','compute-0-4','compute-0-5','compute-0-6','sonmi1'},'ACTUAL_ALPHA_CPU_NODE')
    need(os.environ.get('SLURM_JOB_PARTITION')=='cpu' and os.environ.get('SLURM_CPUS_PER_TASK')=='16' and os.environ.get('CUDA_VISIBLE_DEVICES')=='','CPU16_ONLY')
    boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    need(proof['boot_id']==boot and 0<=time.time()-proof['observed_unix_seconds']<=120,'ACTUAL_ALPHA_BOOT_AND_FRESH_TARGET_CLOCK')
    need(proof['plan_reference']==small_ref(plan_path) and proof['root_review_reference']==plan['root_review_reference'],'ACTUAL_ALPHA_PLAN_REVIEW_PINS')
    need(proof['request']['kind']=='analysis' and proof['request']['pilot'] is True and proof['request']['cpus']==16 and proof['request']['wall_seconds']==7200,'ACTUAL_ALPHA_REQUEST_SCOPE')
    expected=[plan['python'],'-B','-m','payload_audit_alpha_v1.run','--plan',str(Path(plan_path).absolute()),'--startup-proof',str(Path(proof_path).absolute())]
    need(plan['execution_argv']==proof['request']['execution_argv']==expected and sys.argv[1:]==expected[4:],'ACTUAL_ALL_ALPHA_PRIMARY_OPTIONS')
    need(Path(sys.modules['__main__'].__file__).absolute()==primary and Path(sys.executable).absolute()==Path(plan['python']),'ACTUAL_ALPHA_PRIMARY_PYTHON')
    review=load(require(plan['root_review_reference']))
    need(review['schema']=='EXACT_SECONDARY_BOUNDED_READONLY_ROOT_REVIEW_V1' and review['status']=='APPROVED_FOR_EXACT_STAGE' and review['reviewer']=='root','ACTUAL_ALPHA_ROOT_REVIEW')
    for key in ('scope_key','scope_parameters','stage','endpoint','uid','run_root','node','cpus','memory_policy','pilot','wall_seconds','output_cap_bytes','execution_argv','data_references','parent_evidence_references'):
        need(review[key]==plan[key],'EXACT_ROOT_REVIEW:'+key)
    need(review['approved_source_references']==plan['source_references'],'EXACT_APPROVED_ALPHA_SOURCES')
    for pin in plan['source_references']:require(pin)
    for path in primary.parent.iterdir():
        if path.is_file() and path.suffix in ('.py','.json','.md'):need(small_ref(path) in plan['source_references'],'EVERY_NEW_ALPHA_SOURCE_PIN')
    need(plan['relocation_map_reference']==small_ref(MAP) and plan['origin_inventory_reference'] in plan['source_references'],'ACTUAL_EXPLICIT_RELOCATION_SOURCE')
    inventory=load(require(plan['origin_inventory_reference']));m=mapping()
    need(len(m['body']['entries'])==281 and len(inventory['data'])==227 and len(inventory['small'])==54,'EXACT_ORIGINAL_281_MAPPING')
    expected_rows={r['origin_reference']['path']:r for r in [*inventory['data'],*inventory['small']]}
    need(set(m['origin'])==set(expected_rows),'EXACT_ORIGINAL_MAPPING_MEMBERS')
    for old,row in m['origin'].items():
        expected_row=expected_rows[old]
        need(row['origin_reference']==expected_row['origin_reference'],'UNCHANGED_ORIGIN_TRIPLE')
        need(row['target_reference']=={k:expected_row['target_locator'][k] for k in ('path','bytes','sha256')},'UNCHANGED_EXPECTED_ALPHA_TRIPLE')
    body=[m['origin'][r['origin_reference']['path']]['target_reference'] for r in inventory['data']]
    need(plan['data_references']==body and len(body)==227 and sum(p['bytes'] for p in body)==2714663309,'EXACT_227_EXPECTED_BODY_LOCATORS')
    need(plan['transfer_verification_reference'] is None and plan['transfer_verification_expected_output_path']==str(Path(plan['output_directory'])/'transfer_verification.json'),'SHA_IS_PENDING_THIS_ALLOCATION_NOT_PRECLAIMED')
    need(plan['config_reference']==resolved_reference(inventory_config(inventory)) and str(config_path)==plan['config_reference']['path'],'ORIGINAL_CONFIG_COPY_REQUIRED')
    auxiliary=plan['fixture_auxiliary_config_reference'];need(auxiliary in plan['source_references'],'EXPLICIT_NEW_FIXTURE_AUXILIARY_CONFIG')
    need(Path(auxiliary['path'])==FROZEN/'configs/data_v1/labels/streaming_v1.json','FROZEN_FIXTURE_REPO_DEPTH_PRESERVED')
    original_ref=plan['fixture_auxiliary_original_reference'];transform_ref=plan['fixture_auxiliary_transform_reference']
    need(original_ref in plan['source_references'] and transform_ref in plan['source_references'],'EXPLICIT_ONLY_FOUR_CODE_PIN_PATH_TRANSFORM_EVIDENCE')
    need(original_ref['bytes']==4022 and original_ref['sha256']=='92445408cf6a64de2e3b30e41cb0ee99136046acaf6f4848faeb3e8b80694bb3','EXACT_ORIGINAL_STREAMING_CONFIG_PROVENANCE')
    original=load(require(original_ref));actual_aux=load(require(auxiliary));expected_aux=copy.deepcopy(original)
    expected_aux['adapter_source_pins']=[resolved_reference(p) for p in original['adapter_source_pins']]
    need(len(expected_aux['adapter_source_pins'])==4 and actual_aux==expected_aux,'ONLY_FOUR_ADAPTER_LOCATORS_MAY_CHANGE_IN_NEW_AUXILIARY')
    import numpy,pyarrow,rdkit
    environment={'python':'.'.join(str(x) for x in sys.version_info[:3]),'numpy':numpy.__version__,
      'pyarrow':pyarrow.__version__,'rdkit':rdkit.__version__,'executable':sys.executable,
      'Main_pyarrow_major':25,'different_Arrow_version_is_not_scientific_acceptance':True}
    need(environment['python']=='3.11.14' and environment['numpy']=='2.2.6' and environment['pyarrow']=='17.0.0' and environment['rdkit']=='2025.09.5','ACTUAL_ALPHA_TARGET_COMPATIBILITY_ENVIRONMENT')
    plan=dict(plan,actual_environment=environment)
    need(proof['account_free_bytes']-(8<<30)>=200_000_000_000,'ACTUAL_ALPHA_QUOTA200GB_PLUS_OUTPUT')
    binding={'resource_evidence_output':plan['output_directory']+'_resource_observation','memavailable_soft_floor_bytes':4<<30,'resource_evidence_local_cap_bytes':64<<20}
    start_observer(proof,binding)
    return plan,proof

def inventory_config(inventory):
    path='/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/payload_audit_v1_pilot_metadata/config.json'
    return next(row['origin_reference'] for row in inventory['small'] if row['origin_reference']['path']==path)