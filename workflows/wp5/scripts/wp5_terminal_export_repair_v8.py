"""Metadata-only closure verifier for an actual empty R10 export scope.
No finalizer, queue connection, SCI reader, QM, LMDB, or permanent-body rehash.
"""
from __future__ import annotations
import argparse,ast,concurrent.futures,hashlib,json,multiprocessing,os,time
from pathlib import Path
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
R13_SHA='258fd76ec1e0bac38db20fc2f3c0c1ef6f107d0d89261860f95b4b73099aed1f'
CLOSURE_SHA='827050b013e8b108dd9bb53ab4c0fd18cf928c140eb4e9ef88765bbefec75e80'
ACCOUNTING_SHA='8ccf483791458817d26bfdcddb2bcca69f6929cdacbcccc8d8ed3f8999a66aa5'
TERMINAL={'COMPLETED','FAILED','CANCELLED','NODE_FAIL','OUT_OF_MEMORY','TIMEOUT','BOOT_FAIL','DEADLINE','PREEMPTED'}
SCHEMA='WP5_TERMINAL_EXPORT_SCOPE_V8'
STATUS='TERMINAL_EXPORT_SCOPE_COMPLETE'

def require(condition,message):
    if not condition:raise ValueError(message)
def valid_sha(value):return isinstance(value,str) and len(value)==64 and all(c in '0123456789abcdef' for c in value)
def read_metadata(path,expected=None):
    path=Path(path);before=path.stat();require(before.st_size<=32*1024*1024,'SMALL_METADATA_ONLY:'+str(path));raw=path.read_bytes();after=path.stat()
    require((before.st_ino,before.st_size,before.st_mtime_ns)==(after.st_ino,after.st_size,after.st_mtime_ns),'METADATA_CHANGED_DURING_READ:'+str(path))
    reference={'path':str(path),'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}
    if expected is not None:require(valid_sha(expected) and reference['sha256']==expected,'METADATA_SHA_DIFFERS:'+str(path))
    return raw,reference

def bound(ref):
    raw,actual=read_metadata(ref['path'],ref['sha256']);return json.loads(raw),actual

def validate_empty_scope(plan,applied,exports,actions,run_reports,closed,plan_ref):
    require(plan.get('status')=='REVIEWABLE_TERMINAL_SUBSET_DRY_RUN' and plan.get('implementation_version')==10,'ACTUAL_REVIEWABLE_R10_REQUIRED')
    require(plan.get('registered_jobs_count')==463 and len(plan.get('registered_jobs',{}))==463,'ACTUAL463_REQUIRED')
    require(plan.get('all_registered_jobs_terminal') is True and plan.get('plan_was_all463_terminal') is True,'PLAN_TERMINAL_PROOF_REQUIRED')
    require(not plan.get('conflicts') and not plan.get('protected_jobs') and not plan.get('protected_tasks') and plan['skipped']['count']==0,'PLAN_CONFLICT_OR_PROTECTED_OR_SKIPPED')
    require(plan.get('all_selected_root_scans_complete') is True and len(run_reports)==plan['roots_requested'],'ALL_R10_SCANS_COMPLETE_REQUIRED')
    require(all(r.get('scan_complete') is True and not r.get('errors') and not r.get('conflicts') for r in run_reports),'INCOMPLETE_SCI_VALIDATION_METADATA')
    require(exports==[],'NONEMPTY_EXPORT_SCOPE_REQUIRES_A_REAL_EXPORT_PRODUCER')
    require(applied.get('status')=='APPLIED_AND_VERIFIED' and applied.get('implementation_version')==10 and applied.get('original_job_count')==463 and applied.get('registered_jobs_count')==463,'ACTUAL_FULL463_R10_APPLY_REQUIRED')
    for key in ('all_registered_jobs_terminal','plan_was_all463_terminal','all_applied_rows_verified','full463_terminal_scope_verified','old_SCI_contract_package_execution_provenance_preserved'):
        require(applied.get(key) is True,'APPLY_NOT_VERIFIED:'+key)
    require(applied.get('plan_skipped_count')==0 and not applied.get('protected_jobs') and not applied.get('protected_tasks'),'APPLY_HAS_SKIPPED_OR_PROTECTED')
    require({k:applied['plan'][k] for k in ('path','sha256')}=={k:plan_ref[k] for k in ('path','sha256')},'APPLY_PLAN_BINDING_DIFFERS')
    require(applied.get('export_repair_separate_no_QM_step')==plan['export_roots'],'APPLY_EXPORT_SCOPE_BINDING_DIFFERS')
    require(len(applied['results'])==len(actions) and all(r.get('verified') is True and r.get('status') in {'APPLIED','ALREADY_APPLIED'} for r in applied['results']),'APPLY_ROW_VERIFICATION_NOT_CLOSED')
    require(all(a['kind']=='RELEASE_TERMINAL_INFRASTRUCTURE_FAILURE' and a.get('scientific_attempt_unchanged') is True and a.get('desired_state')=='PENDING' for a in actions),'UNEXPECTED_ACTION_SCOPE')
    require(len(closed)==plan['already_closed_roots']['count'],'EXISTING_CLOSURE_LIST_COUNT_DIFFERS')


def inspect_existing(item):
    from wp5_collect_materialized_permanent_v2 import read_closure
    root=Path(item['run_root']);require(root.is_absolute() and root.is_relative_to(ROOT/'runtime'),'EXISTING_ROOT_SCOPE_DIFFERS')
    raw,run_ref=read_metadata(root/'run.json',item['run_json_sha256']);options=json.loads(raw)['options']
    require(str(options['job_id'])==str(item['job_id']),'EXISTING_ROOT_JOB_DIFFERS')
    path=root/'export_completion.json'
    if not path.exists():
        require(item['records']==0 and item['molecules']==0 and not item.get('expected_closure_sha256'),'SCI_ROOT_WITHOUT_PERMANENT_CLOSURE')
        return {'run_root':str(root),'job_id':str(item['job_id']),'run_json':run_ref,'closure':None,'scope':'ZERO_SCI_METADATA_ROOT_NO_EXPORT_REQUIRED','pid':os.getpid()}
    proof=read_closure(path);require(proof['issues']==[],'EXISTING_CLOSURE_STRUCTURE_DIFFERS:'+str(path))
    closure=proof['closure'];require(closure['molecules']==item['molecules'] and closure['records']==item['records'],'EXISTING_CLOSURE_COUNTS_DIFFERS:'+str(path))
    if item.get('expected_closure_sha256'):require(closure['sha256']==item['expected_closure_sha256'],'EXISTING_CLOSURE_SHA_DIFFERS')
    return {'run_root':str(root),'job_id':str(item['job_id']),'run_json':run_ref,'closure':closure,'permanent_references':proof['refs'],
      'original_contract':{'path':options['production_contract'],'sha256':options['production_contract_sha256']},
      'original_package':{'path':options['reproduction_package'],'sha256':options['reproduction_package_sha256']},
      'closure_metadata_and_reference_structure_verified':True,'permanent_bodies_rehashed':False,
      'full_SCI_validation_basis':item['validation_basis'],'scope':'EXISTING_PERMANENT_OUTPUT_REUSED_WITHOUT_EXPORT','pid':os.getpid()}

def fresh_terminal(jobs,out):
    from wp5_accounting_v2 import run_sacct
    result=run_sacct(['-X','-n','-P','-j',','.join(sorted(jobs)),'--format=JobID,User,State'],evidence_path=out/('accounting_'+str(time.time_ns())+'.json'),wait_seconds=120)
    require(result.returncode==0,'FRESH_ACCOUNTING_UNAVAILABLE:'+result.evidence_path)
    states={}
    for line in result.stdout.splitlines():
        parts=line.strip().split('|');require(len(parts)>=3 and parts[1]=='zixiao','ACCOUNTING_USER_OR_FORMAT_DIFFERS');states[parts[0]]=parts[2].split()[0]
    require(set(states)==set(jobs) and len(states)==463 and all(value in TERMINAL for value in states.values()),'FRESH_ALL463_TERMINAL_REQUIRED')
    _,proof=read_metadata(result.evidence_path)
    return {**proof,'states':states,'all_terminal':True,'registered_jobs_count':len(states)}

def main(args):
    require(os.getuid()==1278 and os.uname().nodename in {'compute-0-12','compute-0-13','compute-0-14','compute-0-17','compute-0-18','compute-0-19','compute-0-20'},'OWNED_APPROVED_COMPUTE_REQUIRED')
    out=args.out;require(out.is_absolute() and out.is_relative_to(ROOT/'reports'),'NEW_REPORT_OUTPUT_REQUIRED');out.mkdir(parents=True,exist_ok=False)
    plan,plan_ref=bound({'path':str(args.plan),'sha256':args.expected_plan_sha256})
    applied,apply_ref=bound({'path':str(args.apply_report),'sha256':args.expected_apply_sha256})
    contract,contract_ref=bound({'path':str(args.current_contract),'sha256':args.current_contract_sha256})
    require(args.current_contract==ROOT/'configs/production_contract_v7.json' and contract.get('status')=='PRODUCTION_CONTRACT_FROZEN' and 'wp5_runner_v14.py' in contract.get('current_runtime',{}),'ACTUAL_CURRENT_CONTRACT7_R14_REQUIRED')
    for path,expected in ((ROOT/'scripts/wp5_runner_v13.py',R13_SHA),(ROOT/'scripts/wp5_collect_materialized_permanent_v2.py',CLOSURE_SHA),(ROOT/'scripts/wp5_accounting_v2.py',ACCOUNTING_SHA)):
        read_metadata(path,expected)
    leaves={};refs={}
    for key in ('actions','run_reports','export_roots','already_closed_roots','skipped'):
        leaves[key],refs[key]=bound(plan[key])
    validate_empty_scope(plan,applied,leaves['export_roots'],leaves['actions'],leaves['run_reports'],leaves['already_closed_roots'],plan_ref)
    require(leaves['skipped']==[],'NONEMPTY_SKIP_LIST')
    for ref in [plan['control_jobmap'],plan['repair_scope'],*plan['manifests']]:bound(ref)
    accounting=fresh_terminal(plan['registered_jobs'],out)
    work={}
    for row in leaves['already_closed_roots']:
        work[row['run_root']]={**row,'expected_closure_sha256':row['closure_sha256'],'validation_basis':'R10_BOUND_PREVIOUS_PERMANENT_CLOSURE_METADATA'}
    for row in leaves['run_reports']:
        require(row['staged_molecules']==0,'EMPTY_EXPORT_SCOPE_HAS_UNEXPORTED_STAGE')
        item={'run_root':row['run_root'],'job_id':row['job_id'],'run_json_sha256':row['run_json_sha256'],'molecules':row['retired_molecules'],'records':row['records'],'validation_basis':'R10_H2_COMPLETE_RETIRED_SCI_WIRE_CANONICAL_12N_AND_PERMANENT_SHA_REVERIFIED'}
        require(item['run_root'] not in work,'R10_ROOT_CLASSIFICATION_DUPLICATED');work[item['run_root']]=item
    require(all(str(item['job_id']) in accounting['states'] for item in work.values()),'CLOSURE_ROOT_NOT_IN_ACTUAL463')
    workers=min(args.workers,len(work));verified=[]
    if work:
        with concurrent.futures.ProcessPoolExecutor(max_workers=workers,mp_context=multiprocessing.get_context('spawn')) as pool:
            verified=list(pool.map(inspect_existing,[work[key] for key in sorted(work)],chunksize=1))
    existing=[row for row in verified if row['closure'] is not None];zero=[row for row in verified if row['closure'] is None]
    _,source_ref=read_metadata(Path(__file__))
    report={'schema':SCHEMA,'status':STATUS,'created_epoch':time.time(),'source':source_ref,'plan':plan_ref,'reconciliation_apply':apply_ref,
      'frozen_runner_sha256':R13_SHA,'current_metadata_contract':contract_ref,'current_metadata_runtime_version':14,
      'roots':[],'already_closed_requested_roots':[],'requested_root_count':0,'molecules':0,'records':0,'requested_outcomes':0,
      'scope_meaning':'ZERO_PENDING_EXPORT_ROOTS_IN_ACTUAL_R10_PLAN; NOT_ZERO_SCI_POPULATION; ALL_EXISTING_PERMANENT_OUTPUTS_REUSED',
      'fresh_terminal_accounting':accounting,'registered_jobs_count':463,'actual_export_scope':refs['export_roots'],
      'bound_validation_metadata':refs,'all_selected_root_scans_complete':True,'H2_complete_scanned_roots':len(leaves['run_reports']),
      'H2_attempt_molecules_verified':plan['SCI_attempt_molecules_read'],'H2_attempt_records_verified':plan['SCI_attempt_records_read'],
      'verified_existing_closures':existing,'zero_SCI_metadata_roots_without_closure':zero,'existing_closure_count':len(existing),
      'workers_requested':args.workers,'actual_metadata_worker_pids':sorted({row['pid'] for row in verified}),
      'closure_checker':{'path':str(ROOT/'scripts/wp5_collect_materialized_permanent_v2.py'),'sha256':CLOSURE_SHA},
      'permanent_file_bodies_rehashed':False,'SCI_frames_or_numerical_labels_read':False,'queue_opened':False,'queue_modified':False,
      'QM_started':False,'original_LMDB_opened':False,'old_run_options_rewritten':False,'new_formal_phase_started':False,
      'permanent_outputs_reexported_or_overwritten':False,'old_SCI_contract_package_execution_provenance_preserved':True}
    with (out/'report.json').open('x') as stream:json.dump(report,stream,indent=2,allow_nan=False);stream.write('\n')
    print(json.dumps({key:report[key] for key in ('status','requested_root_count','existing_closure_count','H2_complete_scanned_roots','H2_attempt_molecules_verified','H2_attempt_records_verified','actual_metadata_worker_pids','QM_started','queue_opened')}))

def check():
    ast.parse(Path(__file__).read_text())
    plan={'status':'REVIEWABLE_TERMINAL_SUBSET_DRY_RUN','implementation_version':10,'registered_jobs_count':463,'registered_jobs':{str(i):{} for i in range(463)},'all_registered_jobs_terminal':True,'plan_was_all463_terminal':True,'skipped':{'count':0},'all_selected_root_scans_complete':True,'roots_requested':0,'already_closed_roots':{'count':0},'export_roots':{'path':'private','sha256':'0'*64}}
    ref={'path':'private_plan','sha256':'1'*64};applied={'status':'APPLIED_AND_VERIFIED','implementation_version':10,'original_job_count':463,'registered_jobs_count':463,'plan_skipped_count':0,'plan':ref,'export_repair_separate_no_QM_step':plan['export_roots'],'results':[]}
    for key in ('all_registered_jobs_terminal','plan_was_all463_terminal','all_applied_rows_verified','full463_terminal_scope_verified','old_SCI_contract_package_execution_provenance_preserved'):applied[key]=True
    validate_empty_scope(plan,applied,[],[],[],[],ref)
    try:validate_empty_scope(plan,applied,[{'run_root':'unexpected'}],[],[],[],ref);raise AssertionError('Nonempty scope accepted')
    except ValueError as error:assert str(error)=='NONEMPTY_EXPORT_SCOPE_REQUIRES_A_REAL_EXPORT_PRODUCER'
    print(json.dumps({'status':'EMPTY_EXPORT_SCOPE_PRIVATE_METADATA_CHECK_PASS','nonempty_scope_rejected':True,'production_SQL':False,'SCI_read':False,'QM_started':False}))
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');parser.add_argument('--plan',type=Path);parser.add_argument('--expected-plan-sha256');parser.add_argument('--apply-report',type=Path);parser.add_argument('--expected-apply-sha256');parser.add_argument('--current-contract',type=Path);parser.add_argument('--current-contract-sha256');parser.add_argument('--workers',type=int,default=24);parser.add_argument('--out',type=Path);args=parser.parse_args()
    if args.check:check()
    else:
        if any(getattr(args,key) is None for key in ('plan','expected_plan_sha256','apply_report','expected_apply_sha256','current_contract','current_contract_sha256','out')):parser.error('Actual plan/apply/current-contract paths and SHA256s plus a new --out are required')
        if args.workers<1:parser.error('--workers must be positive')
        main(args)
