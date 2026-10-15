"""Assemble phase15 G0 from actual closed control evidence; no QM/SQL/Slurm."""
import argparse,ast,copy,hashlib,json,math,os,time
from pathlib import Path
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
PROJECT=ROOT.parent.parent
BASE=ROOT/'gates/g0_ready_for_recovery_v14.json'
BASE_SHA='a92524f4b7de55048f95f9084e02d19cb1ca327caf6a459303a68764ae51efa1'
R9_PLAN_SHA='3e1b956ef0c3493f875ec636d9ecb86f6a688a6a37c01f596ca160a810d633a7'
STATIC=ROOT/'reports/phase15_control_actual_static_check_root_v1.json'
STATIC_SHA='c933e26e780e276640df9271193158d45d3d6e38686c8ff91f5df3653a21c7fd'
CONTROLS={
 'wp5_continue_formal_v15.py':'a72364ff1b9a39fe4e464c4bdf2542b118729d6225217050aeda5749bb2dfb51',
 'wp5_hourly_observe_v9.py':'ec60daa3326a1c247910cca1ddff660345b6d2e6d16b6c238092debcb90f9cd7',
 'wp5_recovery_hourly_watch_v10.py':'49d7c9bbec2033c7faa27fe569c220fcd696bf6e8fbe78a5d96dbd50920ecd96'}
def read(path):return json.loads(Path(path).read_text())
def ref(path):return {'path':str(Path(path)),'sha256':hashlib.sha256(Path(path).read_bytes()).hexdigest()}
def identity(value):return {key:value[key] for key in ('path','sha256')}
def require(condition,message):
    if not condition:raise ValueError(message)
def bound(value):
    require(ref(value['path'])['sha256']==value['sha256'],'ACTUAL_BINDING_CHANGED:'+value['path'])
    return read(value['path'])
def number(value):
    return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)
def integer(value):return isinstance(value,int) and not isinstance(value,bool) and value>=0
def assemble(args):
    require(os.getuid()==1278 and os.uname().nodename=='sonmi','ROOT_LOGIN_METADATA_CONTROL_ONLY')
    require(ref(BASE)['sha256']==BASE_SHA,'FROZEN_PHASE14_G0_CHANGED')
    old=read(BASE);require(old['status']=='READY_FOR_ONE_PHASE_FORMAL_SUBMISSION','ORIGINAL_G0_NOT_CLOSED')
    require(old['runtime_version']==13 and old['scientific_configuration_changed'] is False,'ORIGINAL_SCIENCE_NOT_R13')
    for binding in old['bindings']:
        require(ref(binding['path'])['sha256']==binding['sha256'],'OLD_SCI_CACHE_BINDING_CHANGED:'+binding['path'])
    for name,wanted in CONTROLS.items():
        require(ref(ROOT/'scripts'/name)['sha256']==wanted,'PHASE15_CONTROL_SOURCE_CHANGED:'+name)
    require(ref(STATIC)['sha256']==STATIC_SHA,'ACTUAL_CONTROL_STATIC_PROOF_CHANGED')
    static=read(STATIC)
    require(static['returncode']==0 and static['source_shas']==CONTROLS and
        static['QM_started'] is False and static['production_SQL_requested'] is False and
        static['SCI_scan_requested'] is False and static['new_phase_submitted'] is False,
        'ACTUAL_CONTROL_STATIC_PROOF_NOT_CLOSED')
    from wp5_continue_formal_v15 import registry
    refs,ids=registry();plan=read(args.plan)
    require(plan['version']==15 and plan['status']=='PREPARED_NOT_SUBMITTED' and plan['runtime_version']==13 and
        plan['prior_unique_jobs']==385 and plan['prior_submissions']==refs and plan['prior_job_ids']==ids and
        plan['submission_cwd']==str(PROJECT) and len(plan['main'])==72 and len(plan['cleanup'])==6 and
        plan['script']==old['current_runtime']['wp5_main_v13.sbatch']['path'] and
        identity(plan['production_contract'])==identity(old['production_contract']) and
        plan['raw_policy']==old['raw_policy'],'ACTUAL_PREPARED15_UNCHANGED_SCIENCE_SCOPE_REQUIRED')
    package=bound(plan['reproduction_package'])
    require(package['schema']=='WP5_REPRODUCTION_PACKAGE_V1' and package['status']=='CLOSED','ORIGINAL_PACKAGE_NOT_CLOSED')
    contract=bound(plan['production_contract'])
    require(contract['status']=='PRODUCTION_CONTRACT_FROZEN' and contract['policy']==old['raw_policy'] and
        identity(contract['reproduction_package'])==identity(plan['reproduction_package']),
        'FROZEN_CONTRACT6_PACKAGE_OR_POLICY_DIFFERS')
    for value in old['current_runtime'].values():bound_source=ref(value['path']);require(bound_source['sha256']==value['sha256'],'R13_SCI_SOURCE_CHANGED')
    applied=read(args.apply_report)
    require(applied['schema']=='WP5_TERMINAL_SUBSET_RECONCILIATION_APPLY_V3' and
        applied['status']=='APPLIED_AND_VERIFIED' and applied['implementation_version']==9 and
        applied['registered_jobs_count']==385 and applied['prior_submissions']==refs and
        applied['plan_skipped_count']==0 and applied['protected_jobs']=={} and applied['protected_tasks']==[],
        'ACTUAL_FULL385_R9_APPLY_REQUIRED')
    require(all(applied[key] is True for key in
        ('all_registered_jobs_terminal','plan_was_all385_terminal','full385_terminal_scope_verified','all_applied_rows_verified')),
        'ACTUAL_FULL385_TERMINAL_READBACK_NOT_CLOSED')
    require(applied['plan']['sha256']==R9_PLAN_SHA,'ACTUAL_R9_PLAN_SHA_DIFFERS')
    r9=bound(applied['plan'])
    require(r9['implementation_version']==9 and r9['registered_jobs_count']==385 and r9['manifests']==refs and
        r9['all_registered_jobs_terminal'] is True and r9['plan_was_all385_terminal'] is True,
        'ACTUAL_R9_MIRRORED_PLAN_NOT_CLOSED')
    exports=bound(r9['export_roots'])
    require(len(exports)==6,'ACTUAL_SIX_UNCLOSED_ROOTS_REQUIRED')
    exported=read(args.export_report)
    require(exported['schema']=='WP5_PHASE14_TERMINAL_EXPORT_ROOT_REPAIR_V7' and
        exported['status']=='PHASE14_REQUESTED_TERMINAL_ROOT_EXPORT_REPAIR_COMPLETE' and
        exported['requested_root_count']==14 and len(exported['roots'])==6 and
        len(exported['already_closed_requested_roots'])==8,
        'ACTUAL_E7_SIX_ROOTS_PLUS_EIGHT_PRIOR_CLOSURES_REQUIRED')
    require(all(exported[key] is False for key in
        ('QM_started','original_LMDB_opened','old_run_options_rewritten','new_formal_phase_started')),
        'EXPORT_REPAIR_MUST_NOT_RECOMPUTE_OR_CHANGE_ORIGINAL_OPTIONS')
    require(exported['frozen_runner_sha256']==old['current_runtime']['wp5_runner_v13.py']['sha256'] and
        identity(exported['current_metadata_contract'])==identity(plan['production_contract']) and
        identity(exported['plan'])==identity(applied['plan']) and
        identity(exported['reconciliation_apply'])==ref(args.apply_report),
        'ACTUAL_E7_R9_R13_CONTRACT_BINDING_DIFFERS')
    declared={row['run_root']:row for row in exports}
    require(len(declared)==6 and {row['run_root'] for row in exported['roots']}==set(declared),'E7_ROOT_SCOPE_DIFFERS_FROM_ACTUAL_R9')
    from wp5_collect_materialized_permanent_v2 import read_closure
    closures=[]
    for row in exported['roots']:
        expected=declared[row['run_root']]
        require(row['molecules']==expected['molecules'] and row['records']==expected['records'] and
            integer(row['records']) and row['requested_outcomes']==12*row['records'] and
            row['receipt_wire_package_context_readback'] is True and row['original_run_json_unchanged'] is True and
            identity(row['original_contract'])==identity(plan['production_contract']) and
            identity(row['original_package'])==identity(plan['reproduction_package']),
            'E7_OWN_EXECUTION_SCI_CONTEXT_OR_TWELVE_N_DIFFERS')
        proofs=row['permanent_SHA_readback']
        require(bool(proofs) and all(value['actual_sha256']==value['sha256'] and
            value['actual_bytes']==value['bytes'] for value in proofs),'E7_PERMANENT_READBACK_NOT_CLOSED')
        path=Path(row['run_root'])/'export_completion.json'
        require(read_closure(path)['issues']==[],'ACTUAL_EXPORT_COMPLETION_NOT_CLOSED:'+str(path))
        closures.append(ref(path))
    require(exported['molecules']==sum(row['molecules'] for row in exported['roots']) and
        exported['records']==sum(row['records'] for row in exported['roots']) and
        exported['requested_outcomes']==12*exported['records'],'E7_AGGREGATE_COUNTS_NOT_CLOSED')
    for row in exported['already_closed_requested_roots']:bound({'path':row['closure_path'],'sha256':row['closure_sha256']})
    g3=read(args.g3)
    require(g3['status']=='PASS' and g3['storage_capacity_pass'] is True and
        g3['scientific_configuration_changed'] is False and
        identity(g3['production_contract'])==identity(plan['production_contract']) and
        identity(g3['queue_reconciliation_report'])==ref(args.apply_report) and
        identity(g3['source_plan'])==identity(applied['plan']),
        'ACTUAL_ROOT_CLOSED_CURRENT_G3_REQUIRED_NOT_AN_ESTIMATE')
    free=g3['quota']['remaining_bytes'];head=g3['headroom_bytes'];remaining=g3['remaining_writeback_peak_bytes']
    require(all(number(value) and value>=0 for value in (free,head,remaining)) and
        free>=300000000000 and head>=200000000000 and head==free-remaining and
        g3['required_headroom_bytes']==200000000000 and g3['future_training_reserve_bytes']==400000000000,
        'ACTUAL_REMAINING_CAPACITY_300GB_FREE_200GB_HEADROOM_400GB_RESERVE_REQUIRED')
    require(integer(g3['remaining_molecules']) and integer(g3['remaining_records']) and
        g3['remaining_molecules']>0 and g3['remaining_records']>0 and isinstance(g3['counts'],dict),
        'ACTUAL_NONZERO_REMAINING_POPULATION_REQUIRED')
    smoke_path=Path(old['cwd_complete_chain_smoke']['path']);smoke=bound(old['cwd_complete_chain_smoke'])
    require(smoke['status']=='CWD_COMPLETE_CHAIN_SMOKE_PASS' and smoke['issues']==[] and
        smoke['effective_worker_count']==24 and smoke['science_rows']==12 and
        smoke['actual_cwd']==str(PROJECT) and smoke['runtime_subprocess_cwd']==str(PROJECT) and
        identity(smoke['runner'])==identity(old['current_runtime']['wp5_runner_v13.py']) and
        identity(smoke['production_contract'])==identity(plan['production_contract']) and
        identity(smoke['reproduction_package'])==identity(plan['reproduction_package']),
        'ORIGINAL_COMPLETE_CHAIN_CWD_SMOKE_REQUIRED')
    for name in ('G1','G2','G4','G6','REPRO50'):require(old['gates'][name]['status']=='PASS','ORIGINAL_SCI_GATE_NOT_CLOSED:'+name)
    require(old['gates']['G5']['status'] in ('PASS','PASS_FULL_FIELD_EXTRACTION'),'ORIGINAL_FULL_FIELD_GATE_NOT_CLOSED')
    require(not (ROOT/'STOP_NEW_MOLECULES.json').exists() and not (ROOT/'control/STOP.json').exists(),'ACTUAL_STOP_REMAINS')
    obj=copy.deepcopy(old)
    obj.update(schema='WP5_CONTINUOUS_G0_READY_V15',status='READY_FOR_ONE_PHASE_FORMAL_SUBMISSION',
        created_at_epoch=time.time(),previous_G0=ref(BASE),prepared_plan=ref(args.plan),
        queue_reconciliation_report=ref(args.apply_report),pure_export_report=ref(args.export_report),
        cwd_complete_chain_smoke=ref(smoke_path),submission_cwd=str(PROJECT),runtime_version=13,
        coordination_version=15,actual_prior_formal_job_count=385,actual_remaining_molecules=g3['remaining_molecules'],
        actual_remaining_records=g3['remaining_records'],stop_retained_for_normal_drain=False,
        scientific_configuration_changed=False,final200_required=True,submission_authority_pending=False)
    obj['gates']['G3']={**ref(args.g3),'status':'PASS'}
    obj['previous_quota_validation']=copy.deepcopy(old['current_quota_validation'])
    obj['current_quota_validation']={'source_G3':ref(args.g3),'quota_remaining_bytes':free,'peak_headroom_bytes':head,
        'required_peak_headroom_bytes':200000000000,'remaining_writeback_peak_bytes':remaining,
        'future_float32_reserve_bytes':400000000000,'actual_remaining_molecules':g3['remaining_molecules'],
        'actual_remaining_records':g3['remaining_records'],'actual_counts':g3['counts']}
    obj['previous_prior_terminal_snapshot']=copy.deepcopy(old.get('prior_terminal_snapshot'))
    obj['prior_terminal_snapshot']={'source':ref(args.apply_report),'unique_jobs':385,'all_registered_jobs_terminal':True,
        'basis':'Actual R9 terminal/readback proof; no new scheduler or population query by assembler'}
    bindings=obj['bindings']
    additions=[ref(BASE),ref(args.plan),ref(args.apply_report),identity(applied['plan']),ref(args.export_report),ref(args.g3),
        ref(STATIC),ref(Path(__file__).resolve()),identity(plan['reproduction_package']),*closures]
    additions.extend(ref(ROOT/'scripts'/name) for name in CONTROLS)
    for value in additions:
        existing=[old_ref for old_ref in bindings if old_ref['path']==value['path']]
        require(all(old_ref['sha256']==value['sha256'] for old_ref in existing),'G0_BOUND_SOURCE_WOULD_CHANGE:'+value['path'])
        if not existing:bindings.append(value)
    output=Path(args.out);require(output==ROOT/'gates/g0_ready_for_recovery_v15.json','INDEPENDENT_PHASE15_G0_OUTPUT_REQUIRED')
    with output.open('x') as stream:
        json.dump(obj,stream,indent=2,allow_nan=False);stream.write('\n');stream.flush();os.fsync(stream.fileno())
    require(read(output)==obj,'G0_METADATA_READBACK_DIFFERS')
    print(json.dumps({'status':obj['status'],'g0':ref(output),'prior_jobs':385,'next_jobs':78,
        'remaining_molecules':g3['remaining_molecules'],'remaining_records':g3['remaining_records'],
        'headroom_bytes':head,'runtime_version':13,'QM_started':False,'queue_written':False,'Slurm_submitted':False}))
def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true')
    parser.add_argument('--plan',type=Path,default=ROOT/'submission/recovery_attempt_v15/prepared_plan_v15.json')
    parser.add_argument('--apply-report',type=Path,default=ROOT/'reports/actual385_apply_v9_job_4515196/report.json')
    parser.add_argument('--g3',type=Path);parser.add_argument('--export-report',type=Path)
    parser.add_argument('--out',type=Path,default=ROOT/'gates/g0_ready_for_recovery_v15.json')
    args=parser.parse_args()
    if args.check:ast.parse(Path(__file__).read_text());print('G0_CONTINUATION15_AST_ONLY_NOT_EXECUTED_NO_SQL_NO_SCI');return
    if args.g3 is None or args.export_report is None:parser.error('--g3 and --export-report actual closed evidence required')
    assemble(args)
if __name__=='__main__':main()
