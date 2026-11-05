"""Two exact resource phases; original scientific scope and objects are retained."""
import csv,io,json,time,traceback,unittest
from pathlib import Path
from secondary_cpu_queue_v1 import common as Q
from secondary_pubchem_screening_alpha_v1 import contracts as C,guard as OLD_GUARD,runtime as OLD_RUNTIME
HERE=Q.ROOT/'code/secondary_pubchem_resource_phase_alpha_v2'
QUEUE=Q.ROOT/'code/secondary_cpu_readonly_pubchem_phase_v1'
FILES=('__init__.py','phase.py','run.py','qa0.py','guard.py','inverse.py','test_phase.py','metadata.py','README.md')
MODES={
 'QA0':{'key':'pubchem_c_resource_phase_qa0_alpha_v2','plan':'SECONDARY_PUBCHEM_RESOURCE_PHASE_QA0_PLAN_V2',
  'proof':'SECONDARY_PUBCHEM_RESOURCE_PHASE_QA0_STARTUP_V2','stage':'PUBCHEM_RESOURCE_PHASE_QA0_NO_DATA',
  'scope_mode':'BOUNDED_RESOURCE_PHASE_QA0','performance_profile':False,'pilot':False},
 'FULL_SHARD':{'key':'pubchem_c_resource_phase_shard_alpha_v2','plan':'SECONDARY_PUBCHEM_RESOURCE_PHASE_SHARD_PLAN_V2',
  'proof':'SECONDARY_PUBCHEM_RESOURCE_PHASE_SHARD_STARTUP_V2','stage':'PUBCHEM_EXCLUSIVE_ORDINAL_FEATURE_SHARD_RESOURCE_PHASE_V2',
  'scope_mode':'EXCLUSIVE_ORDINAL_FEATURE_SHARD','performance_profile':False,'pilot':False}}


def phase(plan):
    value=plan['resource_phase'];Q.need(value in MODES and plan['mode']=='full_shard','EXACT_RESOURCE_PHASE_OVER_ORIGINAL_C_SCOPE');return value
def spec(value):return MODES[value]
def module(value):return 'secondary_pubchem_resource_phase_alpha_v2.'+('qa0' if value=='QA0' else 'run')
def primary(value):return HERE/('qa0.py' if value=='QA0' else 'run.py')


def parameters(plan):
    value=phase(plan);original=C.parameters('full_shard',*[plan[k] for k in ('first_part','last_part','first_ordinal','last_ordinal')])
    return {**original,'resource_phase':value,'old5_plus_new3_before_Budget':True,'resource_monitor_starts_after_fixture_cleanup':True,
        'runtime_Budget_and_thresholds_unchanged':True,'resource_phase_QA_only':value=='QA0',
        'scientific_DATA_read':value!='QA0','production_ordinal_claim_allowed':value!='QA0',
        'ProcessPool_allowed':value!='QA0','extra_pure_fixture_methods':3,'new_science_or_selection_or_once_semantics':False}


def startup_phase(old_fixtures,new_fixtures,budget_factory):
    old=old_fixtures();new=new_fixtures();budget=budget_factory()
    return old,new,budget


def sources():return [*[Q.ref(HERE/n) for n in FILES],Q.ref(QUEUE/'controller.py'),Q.ref(QUEUE/'adapters.py')]


def terminal(reference,job,parents,C0):
    Q.need(reference in parents,'ACTUAL_ACCOUNTING_IN_APPROVED_PARENT_SET');value=Q.load_ref(reference);p=value['actual_parent'];raw=value['raw_sacct_reference']
    Q.need(raw in parents and value['schema']=='SECONDARY_CPU_ACTUAL_ACCOUNTING_EVIDENCE_V1' and value['query_returncode']==0
        and value['endpoint']==Q.ENDPOINT and value['uid']==1264 and p['JobIDRaw']==str(job) and p['UID']=='1264'
        and p['AllocCPUS']=='16' and p['Partition']=='cpu' and p['NodeList'] in Q.NODES,'REAL_ALPHA_CPU16_ACCOUNTING')
    rows=[r for r in csv.DictReader(io.StringIO(Q.read_small(Q.verify(raw)).decode()),delimiter='|') if r.get('JobIDRaw')==str(job)]
    Q.need(len(rows)==1 and all(rows[0][k]==p[k] for k in ('State','ExitCode','UID','ElapsedRaw','AllocCPUS','NodeList','Partition'))
        and value['allocated_core_seconds_observed']==int(p['ElapsedRaw'])*16,'RAW_ACCOUNTING_ALL_EXECUTED_COST_RETAINED')
    if C0:Q.need(p['State']=='COMPLETED' and p['ExitCode']=='0:0','REAL_QA0_C0_REQUIRED')
    else:Q.need(str(job)=='1884853' and p['State']=='FAILED' and p['ExitCode']=='1:0'
        and int(p['ElapsedRaw'])==21 and value['allocated_core_seconds_observed']==336,'ORIGINAL_FAILED51_IS_NOT_ERASED_OR_CALLED_C0')
    return value


def validate(plan):
    value=phase(plan);wall=plan['wall_seconds'];cap=plan['output_cap_bytes']
    Q.need(type(wall) is int and wall%60==0 and 120<wall<=172800 and type(cap) is int,'FINITE_ORIGINAL_RESOURCE_FIELDS')
    if value=='QA0':Q.need(300<=wall<=7200 and cap==2<<30 and plan['data_references']==[],'QA0_ORIGINAL_DRAIN_RESERVE_REQUIRES2GIB_NO_DATA')
    for reference in sources():Q.need(reference in plan['source_references'],'EXPLICIT_NEW_ADAPTER_SOURCE_NOT_FALSE_OLD_PROFILE_SOURCE')
    review=Q.load_ref(plan['root_review_reference']);change=review['resource_phase_change'];parents=plan['parent_evidence_references']
    Q.need(change['schema']=='ROOT_PUBCHEM_FIXTURE_ORDER_ONLY_CHANGE_V2' and change['approved'] is True
        and change['resource_phase']==value and change['historical_failure_exact_cause']=='UNKNOWN_NOT_PERSISTED'
        and change['scientific_code_or_threshold_or_once_changed'] is False
        and change['original_runtime_unchanged'] is True and change['fixtures_before_Budget'] is True,'EXPLICIT_ROOT_RESOURCE_ONLY_CHANGE_APPROVAL')
    terminal(change['failed51_accounting_reference'],'1884853',parents,False)
    if value=='FULL_SHARD':
        # The first independently reviewed repair is exactly original51. Later
        # controller/range continuation is deliberately outside this package.
        Q.need(plan['shard_index']==plan['first_part']==plan['last_part']==51 and plan['first_ordinal']==12750001
            and plan['last_ordinal']==13000000,'ONLY_ORIGINAL51_COMPLETE250000_REPAIR_NO_RANGE_CONTINUATION')
        r=change['qa0_receipt_reference'];Q.need(r in parents,'ACTUAL_QA0_RECEIPT_APPROVED_PARENT');qa=Q.load_ref(r)
        Q.need(qa['schema']=='ALPHA_PUBCHEM_RESOURCE_PHASE_QA0_RECEIPT_V2' and qa['status']=='QA0_FRESH_BUDGET_SOURCE_PROOF_CLOSED_NO_DATA_OR_CLAIM'
            and qa['endpoint']==Q.ENDPOINT and qa['uid']==1264 and qa['resource_phase']=='QA0'
            and qa['scientific_DATA_read'] is False and qa['ordinal_claim_written'] is False and qa['ProcessPool_started'] is False
            and qa['runtime_budget']['first_stop_reason'] is None and qa['source_inverse_proof']['status']=='EXACT_RESOURCE_PHASE_MAIN_INVERSE_AST_AND_BYTES',
            'REAL_QA0_NOT_A_SCIENCE_OR_PROFILE_SUCCESS')
        for name,n in (('fixtures',5),('resource_fixtures',3)):
            t=qa[name];Q.need(t['tests_run']==n and all(t[k]==0 for k in ('failures','errors','skips','expected_failures','unexpected_successes')),'REAL_QA0_ALL8_PURE')
        Q.need(qa['startup_proof_reference'] in parents and qa['plan_reference'] in parents,'ACTUAL_QA0_PROOF_AND_PLAN_CHAIN')
        qp=Q.load_ref(qa['startup_proof_reference']);qplan=Q.load_ref(qa['plan_reference']);qspec=spec('QA0')
        Q.need(qp['schema']==qspec['proof'] and qp['job_id']==qa['job_id'] and qp['uid']==1264 and qp['endpoint']==Q.ENDPOINT
            and qp['node']==qa['node'] and qp['plan_reference']==qa['plan_reference'] and qp['scope_key']==qspec['key']
            and qplan['resource_phase']=='QA0' and qplan['scope_parameters']==parameters(qplan)
            and qp['request']['execution_argv']==qplan['execution_argv']
            and qplan['execution_argv']==[qplan['python'],'-B','-m',module('QA0'),'--plan',qa['plan_reference']['path'],
                '--startup-proof',qa['startup_proof_reference']['path']],'ACTUAL_QA0_FIXED_PRIMARY_AND_FULL_OPTIONS_CHAIN')
        for r in sources():Q.need(r in qa['source_references'] and r in qplan['source_references']
            and any(all(v.get(k)==r[k] for k in ('path','bytes','sha256')) for v in qp['source_target_verification']),
            'QA0_ACTUALLY_ATTESTED_THE_SAME_CURRENT_ADAPTER_SOURCE')
        terminal(change['qa0_accounting_reference'],qa['job_id'],parents,True)
        absence_ref=change['claim_absence_review_reference'];Q.need(absence_ref in parents,'INDEPENDENT_ACTUAL_CLAIM_ABSENCE_REVIEW')
        absence=Q.load_ref(absence_ref);target=C.ROOT/'control/pubchem_ordinal_claims'/C.RAW_SHA/'shard_000051.json'
        Q.need(absence['schema']=='ROOT_PUBCHEM_FAILED51_CLAIM_ABSENCE_REVIEW_V1' and absence['status']=='APPROVED_EXACT_ORIGINAL51_RESOURCE_REPAIR'
            and absence['reviewer']=='root' and absence['endpoint']==Q.ENDPOINT and absence['uid']==1264 and absence['failed_job_id']=='1884853'
            and absence['claim_path']==str(target) and absence['actual_absent'] is True and absence['old_claim_deleted_or_released'] is False
            and absence['full_shard_manifest_reference']==plan['full_shard_manifest_reference'],'NO_RETRY_OF_A_CONSUMED_OR_UNKNOWN_ORIGINAL_CLAIM')
        Q.need(not target.exists() and not target.is_symlink(),'CURRENT_ORIGINAL51_CLAIM_MUST_STILL_BE_ABSENT')
    return True


def failure_details(exc,budget):
    reason=budget.reason if budget is not None else None
    return {'exception_type':type(exc).__name__,'exception_repr':repr(exc),'exception_filename':getattr(exc,'filename',None),
        'exception_errno':getattr(exc,'errno',None),'traceback':traceback.format_exc(),'latched_first_stop_reason':reason,
        'exact_latched_monitor_path':'UNKNOWN_ORIGINAL_RUNTIME_DID_NOT_PERSIST_PATH' if reason and reason.startswith('MEMORY_OR_STORAGE_OBSERVATION_UNKNOWN:') else None}


def fixtures3(out):
    from .test_phase import Boundaries
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Boundaries);result=unittest.TextTestRunner(verbosity=2).run(suite)
    report={'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'skips':len(result.skipped),
        'expected_failures':len(result.expectedFailures),'unexpected_successes':len(result.unexpectedSuccesses),'scientific_body_reads':0}
    from secondary_pubchem_screening_alpha_v1 import source
    source.write_json(out/'resource_fixtures3.json',report)
    Q.need(result.testsRun==3 and result.wasSuccessful() and not(result.skipped or result.expectedFailures or result.unexpectedSuccesses),'ALL3_RESOURCE_BOUNDARIES_BEFORE_BUDGET_OR_DATA')
    return report


def close_qa0(plan,proof,out,tests,resource_tests,scope_proof,budget,started):
    from .inverse import proof as inverse
    from secondary_pubchem_screening_alpha_v1 import source
    budget.finish();Q.need(not budget.thread.is_alive(),'QA0_ORIGINAL_RESOURCE_MONITOR_NATURALLY_FINISHED');budget.check()
    value={'schema':'ALPHA_PUBCHEM_RESOURCE_PHASE_QA0_RECEIPT_V2','status':'QA0_FRESH_BUDGET_SOURCE_PROOF_CLOSED_NO_DATA_OR_CLAIM',
        'endpoint':Q.ENDPOINT,'uid':1264,'node':proof['node'],'job_id':str(proof['job_id']),'resource_phase':'QA0',
        'plan_reference':proof['plan_reference'],'startup_proof_reference':Q.ref(plan['startup_proof_path']),
        'fixtures':tests,'resource_fixtures':resource_tests,'source_scope_proof':scope_proof,'source_inverse_proof':inverse(),
        'runtime_budget':budget.receipt(),'observation_failure':None,'wall_seconds':time.monotonic()-started,
        'source_references':plan['source_references'],'scientific_DATA_read':False,'ordinal_claim_written':False,'ProcessPool_started':False,
        'actual_terminal_parent_cost_pending_Root_accounting':True,'pool_release_authorized':False,'science_pass_claimed':False}
    source.write_json(out/'receipt.json',value);return 0
