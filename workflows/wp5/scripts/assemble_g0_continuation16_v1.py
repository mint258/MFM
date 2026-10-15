"""Phase16 metadata G0: actual463 R10/E8 evidence and R14 metadata-only transfer."""
from __future__ import annotations
import argparse,copy,hashlib,json,math,os,time
from pathlib import Path
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011');PROJECT=ROOT.parent.parent
BASE=ROOT/'gates/g0_ready_for_recovery_v15.json'
BASE_SHA='48906614f0748d9ddd7388a37d68f20c843c177965862d03d61c7b73cf5e235b'

def read(path):return json.loads(Path(path).read_text())
def ref(path):return {'path':str(Path(path)),'sha256':hashlib.sha256(Path(path).read_bytes()).hexdigest()}
def identity(value):return {k:value[k] for k in ('path','sha256')}
def require(ok,message):
    if not ok:raise ValueError(message)
def bound(value):
    require(ref(value['path'])['sha256']==value['sha256'],'ACTUAL_BINDING_CHANGED:'+value['path'])
    return read(value['path'])
def number(v):return isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v)
def integer(v):return isinstance(v,int) and not isinstance(v,bool) and v>=0

def assemble(a):
    require(os.getuid()==1278 and os.uname().nodename=='sonmi','ROOT_LOGIN_METADATA_CONTROL_ONLY')
    require(ref(BASE)['sha256']==BASE_SHA,'FROZEN_PHASE15_G0_CHANGED')
    old=read(BASE);require(old['status']=='READY_FOR_ONE_PHASE_FORMAL_SUBMISSION' and old['runtime_version']==13 and old['scientific_configuration_changed'] is False,'ACTUAL_R13_SCIENCE_BASE_REQUIRED')
    for binding in old['bindings']:require(ref(binding['path'])['sha256']==binding['sha256'],'OLD_SCIENCE_CACHE_BINDING_CHANGED:'+binding['path'])
    from wp5_continue_formal_v16 import registry,prepare,required_reference,reconciliation_evidence
    references,ids=registry();plan=read(a.plan);expected,contract=prepare()
    require(plan==expected and plan['version']==16 and plan['runtime_version']==14 and plan['prior_unique_jobs']==463 and len(plan['main'])==72 and len(plan['cleanup'])==6,'ACTUAL_PREPARED16_RUNTIME14_SCOPE_REQUIRED')
    require(plan['prior_submissions']==references and plan['prior_job_ids']==ids and plan['submission_cwd']==str(PROJECT),'EXACT463_REGISTRY_AND_PROJECT_CWD_REQUIRED')
    old_contract=bound(old['production_contract']);contract_ref=identity(plan['production_contract'])
    require(identity(contract['previous_contract'])==identity(old['production_contract']),'CURRENT_CONTRACT7_PARENT_MUST_BE_FROZEN_CONTRACT6')
    require(contract['sources'][:len(old_contract['sources'])]==old_contract['sources'],'PARENT_FROZEN_SOURCE_DICTIONARIES_MUST_REMAIN_EXACT')
    for key in ('audit_manifest','protocol','registry','node_authority','node_scope_plan','authority','trace_fields','seeds','policy','final200_required'):
        require(contract[key]==old_contract[key],'SCIENTIFIC_PROTOCOL_CHANGED:'+key)
    prior_science={k:v for k,v in old_contract['current_runtime'].items() if not k.startswith(('wp5_runner_','wp5_main_'))}
    current_science={k:v for k,v in contract['current_runtime'].items() if not k.startswith(('wp5_runner_','wp5_main_'))}
    require(current_science==prior_science,'R13_SCIENTIFIC_RUNTIME_SHA_DIFFERENCE')
    for value in contract['current_runtime'].values():require(ref(value['path'])['sha256']==value['sha256'],'CURRENT_FROZEN_RUNTIME_CHANGED')
    bridge=bound(contract['metadata_only_AST_bridge']);fixture=bound(contract['cross_root_repair_validation'])
    require(bridge['schema']=='WP5_R14_METADATA_AST_BRIDGE_V1' and bridge['status']=='METADATA_ONLY_AST_BRIDGE_PASS' and bridge['changed_definitions']==['main','repair_unexported'] and bridge['own_finalize_AST_identical'] is True and bridge['scientific_runtime_SHA_unchanged'] is True and identity(bridge['runner13'])==identity(old_contract['current_runtime']['wp5_runner_v13.py']) and identity(bridge['runner14'])==identity(contract['current_runtime']['wp5_runner_v14.py']),'ACTUAL_R13_TO_R14_METADATA_AST_BRIDGE_REQUIRED')
    pids=fixture['actual_worker_pids']
    require(fixture['status']=='METADATA_ONLY_FOREIGN_EXPORT_DELEGATION_FIXTURE_PASS' and fixture['QM_calls']==0 and fixture['SCI_rows']==0 and fixture['production_queue_written'] is False and fixture['effective_worker_count']==16 and len(pids)==len(set(pids))==16 and fixture['issues']==[] and identity(fixture['AST_bridge'])==identity(contract['metadata_only_AST_bridge']),'ACTUAL16_WORKER_METADATA_ONLY_FIXTURE_REQUIRED')
    require(all(fixture[k] is True for k in ('active_foreign_lanes_untouched','active_writers_durable_after_repair_call','closed_own_finalizer_real_A5_readback_PASS','repair_only_rejected_before_queue')),'FOREIGN_LIVE_EXPORT_FIXTURE_NOT_CLOSED')
    package=bound(plan['reproduction_package']);parent_package=bound(old_contract['reproduction_package'])
    require(package['schema']=='WP5_REPRODUCTION_PACKAGE_V1' and package['status']=='REPRODUCTION_PACKAGE_CLOSED' and identity(package['original_manifest'])==identity(old_contract['reproduction_package']),'ACTUAL_CLOSED_R14_APPEND_ONLY_PACKAGE_REQUIRED')
    for key in ('protocol','registry','software_versions','environment','recipes','audit_membership','software_environment_exports','software_binary_dependency_closure'):
        require(package.get(key)==parent_package.get(key),'SCI_SOFTWARE_OR_ENVIRONMENT_CHANGED:'+key)
    applied,recovery,exports=reconciliation_evidence(a.reconciliation_plan,a.reconciliation_plan_sha256,a.apply_report,a.apply_report_sha256)
    rplan=required_reference(a.reconciliation_plan,a.reconciliation_plan_sha256);rapply=required_reference(a.apply_report,a.apply_report_sha256)
    export_ref=required_reference(a.export_report,a.export_report_sha256);exported=bound(export_ref)
    # E8's final producer name/status are explicit inputs until its source is frozen.
    # No fixed historical root count, action count, job IDs, or old plan SHA is used.
    require(a.expected_export_schema.startswith('WP5_') and a.expected_export_schema.endswith('_V8') and a.expected_export_status.endswith('COMPLETE'),'EXACT_E8_COMPLETE_SCHEMA_STATUS_EXPECTATION_REQUIRED')
    require(exported['schema']==a.expected_export_schema and exported['status']==a.expected_export_status,'ACTUAL_E8_NOT_CLOSED')
    require(all(exported[k] is False for k in ('QM_started','original_LMDB_opened','old_run_options_rewritten','new_formal_phase_started')),'EXPORT_MUST_NOT_RECOMPUTE_OR_CHANGE_OPTIONS')
    require(identity(exported['plan'])==rplan and identity(exported['reconciliation_apply'])==rapply and exported['frozen_runner_sha256']==old_contract['current_runtime']['wp5_runner_v13.py']['sha256'] and identity(exported['current_metadata_contract'])==contract_ref,'E8_ACTUAL_R10_OR_HISTORICAL_SCI_OR_CURRENT_METADATA_BINDING_DIFFERS')
    declared={row['run_root']:row for row in exports};completed=exported['roots'];prior=exported.get('already_closed_requested_roots',[])
    require(len({row['run_root'] for row in completed})==len(completed),'E8_DUPLICATE_REPAIRED_ROOT')
    # Every R10 root with durable stage must be in the newly verified repaired set;
    # an old export_completion file alone cannot certify an additional live prefix.
    require(set(declared)<={row['run_root'] for row in completed},'E8_MUST_CLOSE_EVERY_ACTUAL_R10_EXPORT_ROOT')
    require(exported['requested_root_count']==len(completed)+len(prior),'E8_REQUESTED_SCOPE_COUNT_NOT_CLOSED')
    from wp5_collect_materialized_permanent_v2 import read_closure
    closures=[]
    for row in completed:
        root=row['run_root'];expected_row=declared.get(root)
        require(integer(row['molecules']) and integer(row['records']) and row['requested_outcomes']==12*row['records'] and row['receipt_wire_package_context_readback'] is True and row['original_run_json_unchanged'] is True,'E8_OWN_EXECUTION_CONTEXT_OR_12N_DIFFERS')
        if expected_row is not None:
            require(row['molecules']==expected_row['molecules'] and row['records']==expected_row['records'],'E8_R10_DURABLE_STAGE_COUNTS_DIFFER')
        require(identity(row['original_contract'])==identity(old['production_contract']) and identity(row['original_package'])==identity(old_contract['reproduction_package']),'E8_HISTORICAL_R13_CONTRACT_PACKAGE_NOT_PRESERVED')
        proofs=row['permanent_SHA_readback'];require(bool(proofs) and all(v['actual_sha256']==v['sha256'] and v['actual_bytes']==v['bytes'] for v in proofs),'E8_PERMANENT_READBACK_NOT_CLOSED')
        path=Path(root)/'export_completion.json';require(read_closure(path)['issues']==[],'EXPORT_COMPLETION_NOT_CLOSED:'+str(path));closures.append(ref(path))
    require(exported['molecules']==sum(row['molecules'] for row in completed) and exported['records']==sum(row['records'] for row in completed) and exported['requested_outcomes']==12*exported['records'],'E8_AGGREGATE_COUNTS_NOT_CLOSED')
    for row in prior:bound({'path':row['closure_path'],'sha256':row['closure_sha256']})
    g3_ref=required_reference(a.g3,a.g3_sha256);g3=bound(g3_ref)
    require(g3['status']=='PASS' and g3['storage_capacity_pass'] is True and g3['scientific_configuration_changed'] is False and identity(g3['production_contract'])==contract_ref and identity(g3['queue_reconciliation_report'])==rapply and identity(g3['source_plan'])==rplan,'ACTUAL_ROOT_CLOSED_CURRENT_G3_REQUIRED')
    free=g3['quota']['remaining_bytes'];head=g3['headroom_bytes'];remaining=g3['remaining_writeback_peak_bytes']
    require(all(number(v) and v>=0 for v in (free,head,remaining)) and free>=300000000000 and head>=200000000000 and head==free-remaining and g3['required_headroom_bytes']==200000000000 and g3['future_training_reserve_bytes']==400000000000,'ACTUAL_300GB_FREE_200GB_HEADROOM_400GB_FUTURE_REQUIRED')
    require(integer(g3['remaining_molecules']) and integer(g3['remaining_records']) and g3['remaining_molecules']>0 and g3['remaining_records']>0 and isinstance(g3['counts'],dict),'ACTUAL_NONZERO_REMAINING_POPULATION_REQUIRED')
    g4_ref=required_reference(a.g4,a.g4_sha256);g4=bound(g4_ref)
    require(g4['status']=='PASS' and identity(g4['production_contract'])==contract_ref and g4['actual_workers']>=24 and g4['QM_started'] is False and g4['original_data_written'] is False and g4['science_recipe_changed'] is False and g4['final200_required'] is True,'ACTUAL_CURRENT_R14_G4_REQUIRED')
    bound(g4['spec']);bound(g4['report'])
    smoke=bound(old['cwd_complete_chain_smoke'])
    require(smoke['status']=='CWD_COMPLETE_CHAIN_SMOKE_PASS' and smoke['issues']==[] and smoke['effective_worker_count']==24 and smoke['science_rows']==12 and smoke['actual_cwd']==str(PROJECT) and smoke['runtime_subprocess_cwd']==str(PROJECT) and identity(smoke['runner'])==identity(old_contract['current_runtime']['wp5_runner_v13.py']) and identity(smoke['production_contract'])==identity(old['production_contract']) and identity(smoke['reproduction_package'])==identity(old_contract['reproduction_package']),'ACTUAL_OLD_R13_CWD_COMPLETE_CHAIN_SMOKE_REQUIRED')
    for name in ('G1','G2','G6','REPRO50'):require(old['gates'][name]['status']=='PASS','ORIGINAL_SCI_GATE_NOT_CLOSED:'+name)
    require(old['gates']['G5']['status'] in ('PASS','PASS_FULL_FIELD_EXTRACTION'),'ORIGINAL_FULL_FIELD_EXTRACTION_NOT_CLOSED')
    obj=copy.deepcopy(old);stop_present=(ROOT/'STOP_NEW_MOLECULES.json').exists() or (ROOT/'control/STOP.json').exists()
    obj.update(schema='WP5_CONTINUOUS_G0_READY_V16',status='READY_FOR_ONE_PHASE_FORMAL_SUBMISSION',created_at_epoch=time.time(),
        previous_G0=ref(BASE),prepared_plan=ref(a.plan),production_contract=contract_ref,reproduction_package=identity(plan['reproduction_package']),
        current_runtime=copy.deepcopy(contract['current_runtime']),source_chain_inventory=copy.deepcopy(contract['source_chain_inventory']),
        queue_reconciliation_report=rapply,reconciliation_plan=rplan,pure_export_report=export_ref,remaining_storage_gate=g3_ref,runtime_freeze_gate=g4_ref,
        cwd_complete_chain_smoke=copy.deepcopy(old['cwd_complete_chain_smoke']),submission_cwd=str(PROJECT),runtime_version=14,coordination_version=16,
        actual_prior_formal_job_count=463,actual_remaining_molecules=g3['remaining_molecules'],actual_remaining_records=g3['remaining_records'],
        stop_retained_for_normal_drain=stop_present,submission_requires_STOP_absent=True,scientific_configuration_changed=False,final200_required=True,submission_authority_pending=False,
        scientific_evidence_transfer={'method':'R13_SCIENCE_PROOFS_INHERITED_THROUGH_ACTUAL_R14_METADATA_AST_BRIDGE','new_QM_calls':0,
            'new_R14_QM_smoke_performed':False,'R13_science_sources_SHA_identical':True,'R14_own_finalize_AST_identical':True,
            'metadata_AST_bridge':copy.deepcopy(contract['metadata_only_AST_bridge']),'actual16worker_fixture':copy.deepcopy(contract['cross_root_repair_validation']),
            'R13_cwd_smoke':copy.deepcopy(old['cwd_complete_chain_smoke']),'R13_REPRO50':copy.deepcopy(old['gates']['REPRO50'])})
    obj['gates']['G3']={**g3_ref,'status':'PASS'};obj['gates']['G4']={**g4_ref,'status':'PASS'}
    obj['previous_quota_validation']=copy.deepcopy(old['current_quota_validation'])
    obj['current_quota_validation']={'source_G3':g3_ref,'quota_remaining_bytes':free,'peak_headroom_bytes':head,'required_peak_headroom_bytes':200000000000,
        'remaining_writeback_peak_bytes':remaining,'future_float32_reserve_bytes':400000000000,'actual_remaining_molecules':g3['remaining_molecules'],'actual_remaining_records':g3['remaining_records'],'actual_counts':g3['counts']}
    obj['previous_prior_terminal_snapshot']=copy.deepcopy(old.get('prior_terminal_snapshot'))
    obj['prior_terminal_snapshot']={'source':rapply,'unique_jobs':463,'all_registered_jobs_terminal':True,'basis':'Actual full463 R10 terminal/readback proof; no scheduler or population query by assembler'}
    additions=[ref(BASE),ref(a.plan),contract_ref,identity(plan['reproduction_package']),contract['source_chain_inventory'],contract['metadata_only_AST_bridge'],contract['cross_root_repair_validation'],rplan,rapply,export_ref,g3_ref,g4_ref,*closures,
        ref(ROOT/'scripts/wp5_continue_formal_v16.py'),ref(Path(__file__).resolve())]
    for value in additions:
        value=identity(value);hits=[item for item in obj['bindings'] if item['path']==value['path']]
        require(all(item['sha256']==value['sha256'] for item in hits),'G0_BOUND_SOURCE_WOULD_CHANGE:'+value['path'])
        if not hits:obj['bindings'].append(value)
    out=Path(a.out);require(out==ROOT/'gates/g0_ready_for_recovery_v16.json','INDEPENDENT_PHASE16_G0_OUTPUT_REQUIRED')
    with out.open('x') as stream:json.dump(obj,stream,indent=2,allow_nan=False);stream.write('\n');stream.flush();os.fsync(stream.fileno())
    require(read(out)==obj,'G0_METADATA_READBACK_DIFFERS')
    print(json.dumps({'status':obj['status'],'g0':ref(out),'prior_jobs':463,'next_jobs':78,'cost_union_after_actual_submission':541,
        'remaining_molecules':g3['remaining_molecules'],'remaining_records':g3['remaining_records'],'headroom_bytes':head,'runtime_version':14,
        'inherited_science_proofs_not_new_QM':True,'STOP_present_at_assembly':stop_present,'QM_started':False,'queue_written':False,'Slurm_submitted':False}))

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--check',action='store_true')
    p.add_argument('--plan',type=Path,default=ROOT/'submission/recovery_attempt_v16/prepared_plan_v16.json')
    for name in ('reconciliation-plan','apply-report','export-report','g3','g4'):
        p.add_argument('--'+name,type=Path);p.add_argument('--'+name+'-sha256')
    p.add_argument('--expected-export-schema');p.add_argument('--expected-export-status')
    p.add_argument('--out',type=Path,default=ROOT/'gates/g0_ready_for_recovery_v16.json');a=p.parse_args()
    if a.check:
        import ast;ast.parse(Path(__file__).read_text());print('G0_CONTINUATION16_AST_ONLY_NO_SQL_SCI_OR_SUBMISSION');return
    names=('reconciliation-plan','apply-report','export-report','g3','g4')
    if any(getattr(a,n.replace('-','_')) is None or getattr(a,n.replace('-','_')+'_sha256') is None for n in names) or not a.expected_export_schema or not a.expected_export_status:
        p.error('Actual evidence absolute paths/SHA256s and exact E8 producer schema/status required')
    assemble(a)
if __name__=='__main__':main()