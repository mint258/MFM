"""Exact continuation authority and pre-Budget lifecycle; never invent a C0."""
import ast,copy,csv,hashlib,io,json,time,unittest
from pathlib import Path
from secondary_cpu_queue_v1 import common as Q
from secondary_pubchem_screening_alpha_v1 import contracts as C,runtime as R
from secondary_pubchem_resource_phase_alpha_v2 import phase as P
HERE=Q.ROOT/'code/secondary_pubchem_continuation_alpha_v3'
QUEUE=Q.ROOT/'code/secondary_cpu_readonly_pubchem_cont_v1'
CONTROLLER=Q.ROOT/'code/pubchem_c_finite500_continuation_v3'
FILES=('__init__.py','contracts.py','run.py','guard.py','test_startup.py','README.md')
CONTROL_FILES=('__init__.py','controller.py','state.py','test_state.py')
KEY='pubchem_c_continuation_shard_alpha_v3';MODULE='secondary_pubchem_continuation_alpha_v3.run'
PLAN='SECONDARY_PUBCHEM_C_CONTINUATION_SHARD_PLAN_V3';PROOF='SECONDARY_PUBCHEM_C_CONTINUATION_SHARD_STARTUP_V3'
RANGE='ROOT_APPROVED_PUBCHEM_C_CONTINUATION52_499_V3';STAGE='PUBCHEM_EXCLUSIVE_ORDINAL_CONTINUATION_AFTER51_V3'
REPAIR_PLAN_PATH=str(Q.ROOT/'control/readonly_specs/pubchem_C_repair51_v2/plan.json')
REPAIR_PLAN_SHA='19ba47e57948909ac7def394c4506cb38ef8a1cbc2810fc432e514ef5ee9f4b9'
REPAIR_REVIEW_SHA='76ce474bc9cf62a87cf9bff999ceae41a95ed60c99c919ae73085de33ea791f8'
SPEC={'key':KEY,'plan':PLAN,'proof':PROOF,'stage':STAGE,'scope_mode':'EXCLUSIVE_ORDINAL_FEATURE_SHARD','performance_profile':False,'pilot':False}
startup_phase=P.startup_phase;failure_details=P.failure_details


def phase(plan):
    Q.need(plan['resource_phase']=='CONTINUATION52_499' and plan['mode']=='full_shard','ONLY_HONEST_NEW_CONTINUATION_PHASE');return 'CONTINUATION52_499'
def spec(value):Q.need(value=='CONTINUATION52_499','ONLY_ONE_NEW_PROTOCOL');return SPEC
def module(value):spec(value);return MODULE
def primary(value):spec(value);return HERE/'run.py'
def sources():return [*[Q.ref(HERE/n) for n in FILES],Q.ref(QUEUE/'controller.py'),Q.ref(QUEUE/'adapters.py'),*[Q.ref(CONTROLLER/n) for n in CONTROL_FILES],Q.ref(CONTROLLER/'fixture_cpu.py')]


def parameters(plan):
    phase(plan);base=C.parameters('full_shard',*[plan[k] for k in ('first_part','last_part','first_ordinal','last_ordinal')])
    return {**base,'resource_phase':'CONTINUATION52_499','old5_plus_v2new3_plus_v3new3_before_Budget':True,
        'resource_monitor_starts_after_all_fixture_cleanup':True,'runtime_Budget_and_thresholds_unchanged':True,
        'extra_pure_fixture_methods':6,'base_resource_pure_methods':3,'continuation_pure_methods':3,'all11_before_Budget':True,
        'actual_repaired51_C0_required':True,'original_FAILED51_cost_retained':True,'original_partition_claim_namespace_unchanged':True,
        'scientific_DATA_read':True,'production_ordinal_claim_allowed':True,'ProcessPool_allowed':True,'new_science_or_selection_or_once_semantics':False}


def merge(values):
    out={}
    for r in values:
        Q.normalized(r);Q.need(r['path'] not in out or out[r['path']]==r,'CONFLICTING_SMALL_OR_DATA_PINS');out[r['path']]=r
    return list(out.values())


def pure_counts(value,n):
    return value['tests_run']==n and all(value[k]==0 for k in ('failures','errors','skips','expected_failures','unexpected_successes'))


def proof_chain(receipt,request_plan,proof_schema,key):
    proof=Q.load_ref(receipt['startup_proof_reference']);plan=Q.load_ref(receipt['plan_reference'])
    Q.need(receipt['plan_reference']==request_plan and proof['plan_reference']==request_plan
        and str(proof['job_id'])==str(receipt['job_id']) and proof['endpoint']==receipt['endpoint']==Q.ENDPOINT
        and proof['uid']==receipt['uid']==1264 and proof['node']==receipt['node']==plan['node']
        and proof['schema']==proof_schema and proof['scope_key']==plan['scope_key']==key
        and proof['request']['execution_argv']==plan['execution_argv'] and proof['request']['cpus']==16
        and proof['request']['kind']=='analysis' and proof['request']['pilot'] is False,'ACTUAL_PRODUCER_PLAN_PROOF_PARENT_IDENTITY')
    return plan,proof


def prerequisites(root):
    parents=root['parent_evidence_references'];P.terminal(root['failed51_accounting_reference'],'1884853',parents,False)
    qa=Q.load_ref(root['qa0_receipt_reference']);qplan,qproof=proof_chain(qa,qa['plan_reference'],P.spec('QA0')['proof'],P.spec('QA0')['key'])
    Q.need(str(qa['job_id'])=='1884854' and qa['status']=='QA0_FRESH_BUDGET_SOURCE_PROOF_CLOSED_NO_DATA_OR_CLAIM'
        and qa['scientific_DATA_read'] is False and qa['ordinal_claim_written'] is False and qa['ProcessPool_started'] is False
        and qa['runtime_budget']['first_stop_reason'] is None and qa['observation_failure'] is None
        and pure_counts(qa['fixtures'],5) and pure_counts(qa['resource_fixtures'],3)
        and qa['source_inverse_proof']['status']=='EXACT_RESOURCE_PHASE_MAIN_INVERSE_AST_AND_BYTES','REAL1884854_QA0_IS_NOT_FUTURE_V3_ATTESTATION')
    for r in P.sources():Q.need(r in qa['source_references'] and r in qplan['source_references'],'SAME_FROZEN_V2_SOURCE_ACTUALLY_QA_TESTED')
    P.terminal(root['qa0_accounting_reference'],qa['job_id'],parents,True)
    repaired=Q.load_ref(root['repaired51_receipt_reference']);p51,proof51=proof_chain(repaired,repaired['plan_reference'],P.spec('FULL_SHARD')['proof'],P.spec('FULL_SHARD')['key'])
    Q.need(str(repaired['job_id'])=='1884855' and repaired['plan_reference']['path']==REPAIR_PLAN_PATH
        and repaired['plan_reference']['sha256']==REPAIR_PLAN_SHA and p51['root_review_reference']['sha256']==REPAIR_REVIEW_SHA,
        'ACTUAL_SUBMITTED1884855_FIXED_PLAN_AND_ROOT_REVIEW_NOT_A_SUCCESS_PREDICTION')
    P.terminal(root['repaired51_accounting_reference'],repaired['job_id'],parents,True)
    result=repaired['result'];counts=result['counts'];claim=Q.load_ref(repaired['claim_reference'])
    Q.need(repaired['status']=='ALPHA_ORDINAL_SHARD_ROWS_CLOSED_NO_POOL_RELEASE' and repaired['resource_phase']=='FULL_SHARD'
        and p51['shard_index']==p51['first_part']==p51['last_part']==51 and p51['first_ordinal']==12750001 and p51['last_ordinal']==13000000
        and repaired['source_row_conservation'] is True and repaired['unread_rows']==0 and repaired['expected_rows']==250000
        and result['dispatched_rows']==result['completed_rows']==result['actual_input_rows_dispatched']==250000
        and result['last_dispatched_ordinal']==result['last_completed_ordinal']==13000000
        and set(counts)=={'accepted','chemReject','technicalUnresolved'} and all(type(v) is int and v>=0 for v in counts.values())
        and sum(counts.values())==250000 and repaired['technical_unknown_is_chemical_exclusion'] is False
        and repaired['full_source_pool_release_authorized'] is False and pure_counts(repaired['fixtures'],5)
        and pure_counts(repaired['resource_fixtures'],3) and repaired['source_inverse_proof']['status']=='EXACT_RESOURCE_PHASE_MAIN_INVERSE_AST_AND_BYTES',
        'COMPLETE_REAL_REPAIRED51_ROWS_AND_RESOURCE_SOURCE_PROOF')
    Q.need(claim['job_id']=='1884855' and claim['plan_reference']==repaired['plan_reference'] and claim['uid']==1264
        and claim['manifest_reference']==root['full_shard_manifest_reference'] and claim['range']=={'shard_index':51,'first_part':51,'last_part':51,
            'first_ordinal':12750001,'last_ordinal':13000000},'ACTUAL_REPAIR51_ORIGINAL_CLAIM_PRESERVED')
    return qa,repaired,p51


def range_review(reference):
    root=Q.load_ref(reference)
    Q.need(root['schema']==RANGE and root['status']=='ROOT_APPROVED' and root['reviewer']=='root' and root['endpoint']==Q.ENDPOINT
        and root['uid']==1264 and root['run_root']==str(Q.ROOT) and root['first_shard']==52 and root['last_shard']==499
        and root['max_nonterminal_C_parents']==6 and root['reserved_non_C_cpus']==16 and root['maximum_foreground_seconds']==72000
        and 0<root['deadline_unix_seconds']-root['authorized_unix_seconds']<=72000 and root['poll_seconds']==30
        and root['wall_seconds']==28800 and root['output_cap_bytes']==8<<30 and root['controller_metadata_cap_bytes']==16<<20,
        'EXACT_ROOT_FINITE52_499_RANGE_AND_FIXED_ABSOLUTE_DEADLINE')
    for key in ('delegate_exact_per_shard_metadata_template','no_automatic_retry','no_automatic_renewal','no_signals_or_cancel',
                'old_failed51_cost_retained','original_claim_namespace_unchanged','all11_fixtures_before_Budget'):
        Q.need(root[key] is True,'ROOT_EXPLICIT_CONTINUATION_INVARIANT:'+key)
    Q.need(root['scientific_or_pool_release'] is False and root['cost_overrun_action']=='REPORT_AND_CONTINUE'
        and root['source_references']==sources() and isinstance(root['delegated_template_reason'],str)
        and root['delegated_template_reason'].strip(),'EXACT_CURRENT13_SOURCE_RANGE_NOT_OLD_QA_SOURCE_MASQUERADE')
    for r in root['source_references']:Q.verify(r)
    fixture=Q.load_ref(root['state_fixture_evidence_reference']);runtime=fixture['actual_runtime'];parent=fixture['actual_parent']
    Q.need(fixture['schema']=='ROOT_REVIEWED_PUBCHEM_CONTINUATION_STATE_FIXTURES_V3' and fixture['status']=='PASS'
        and fixture['reviewer']=='root' and pure_counts(fixture,5) and fixture['scientific_body_reads']==0
        and (runtime['endpoint'],runtime['uid']) in (('202.38.247.57:22',1278),(Q.ENDPOINT,1264))
        and str(runtime['job_id'])==parent['JobIDRaw'] and str(runtime['uid'])==parent['UID'] and runtime['cpus']==16
        and parent['State']=='COMPLETED' and parent['ExitCode']=='0:0' and parent['AllocCPUS']=='16'
        and fixture['allocated_core_seconds_observed']==16*int(parent['ElapsedRaw']),'ACTUAL5_STATE_FIXTURES_C0_WITH_REAL_ENDPOINT_IDENTITY')
    actual={Path(r['path']).name:r for r in fixture['source_references'] if Path(r['path']).parent.name=='pubchem_c_finite500_continuation_v3'}
    Q.need(set(actual)==set(CONTROL_FILES),'EXACT_FOUR_STATE_FIXTURE_SOURCE_ROLES')
    for name in CONTROL_FILES:
        wanted=Q.ref(CONTROLLER/name);Q.need(name in actual and all(actual[name][k]==wanted[k] for k in ('bytes','sha256')),
            'REAL_STATE_FIXTURE_SOURCE_BYTES_MAY_HAVE_EXPLICIT_DIFFERENT_MAIN_LOCATOR')
    raw=fixture['raw_sacct_reference'];Q.need(raw in root['parent_evidence_references'],'ACTUAL_FIXTURE_RAW_ACCOUNT_DECLARED')
    rows=[r for r in csv.DictReader(io.StringIO(Q.read_small(Q.verify(raw)).decode()),delimiter='|') if r.get('JobIDRaw')==parent['JobIDRaw']]
    Q.need(len(rows)==1 and all(rows[0][k]==parent[k] for k in ('UID','State','ExitCode','ElapsedRaw','AllocCPUS','NodeList','Partition')),'RAW_STATE_FIXTURE_PARENT_NOT_INVENTED_PASS')
    prerequisites(root);return root


def validate(plan):
    phase(plan);r=plan['continuation_range_review_reference'];Q.need(r in plan['source_references'] and r in plan['parent_evidence_references'],'EXPLICIT_RANGE_AUTHORITY_REFERENCE')
    root=range_review(r);i=plan['shard_index'];Q.need(type(i) is int and 52<=i<=499,'NO_PRETENDING52_IS51_OR_REDISPATCHING_IMPORTED_SHARD')
    expected={'first_part':i,'last_part':i,'first_ordinal':i*250000+1,'last_ordinal':min((i+1)*250000,C.N)}
    Q.need(all(plan[k]==v for k,v in expected.items()) and plan['full_shard_manifest_reference']==root['full_shard_manifest_reference']
        and plan['metadata_freeze_receipt_reference']==root['metadata_freeze_receipt_reference'] and plan['node'] in root['allowed_nodes']
        and plan['wall_seconds']==root['wall_seconds'] and plan['output_cap_bytes']==root['output_cap_bytes']
        and root['authorized_unix_seconds']<=plan['derived_unix_seconds']<=root['deadline_unix_seconds'],'EXACT_ORIGINAL_FROZEN_WHOLE_SHARD_TEMPLATE')
    review=Q.load_ref(plan['root_review_reference']);Q.need(review['continuation_range_review_reference']==r
        and review['derived_from_exact_Root_range_template'] is True,'DELEGATED_ROOT_TEMPLATE_NOT_NEW_CHILD_APPROVAL')
    for value in sources():Q.need(value in plan['source_references'],'ALL_NEW_CONTINUATION_SOURCE_APPROVED')
    return True


def source_inverse_proof():
    from secondary_pubchem_resource_phase_alpha_v2 import run as OLD_RUN,guard as OLD_GUARD
    from . import run as NEW_RUN
    for name in ('run','guard'):
        old=(P.HERE/(name+'.py')).read_text();new=(HERE/(name+'.py')).read_text()
        expected=old.replace('from . import phase as A','from . import contracts as A')
        if name=='run':expected=expected.replace('from .inverse import proof as source_inverse','from .contracts import source_inverse_proof as source_inverse')
        Q.need(new==expected,'ONLY_EXPLICIT_CONTINUATION_RESOURCE_CONTRACT_IMPORT_DELTA:'+name)
        restored=new.replace('from . import contracts as A','from . import phase as A')
        if name=='run':restored=restored.replace('from .contracts import source_inverse_proof as source_inverse','from .inverse import proof as source_inverse')
        Q.need(restored==old and ast.dump(ast.parse(restored),include_attributes=False)==ast.dump(ast.parse(old),include_attributes=False),'EXACT_CONTINUATION_MAIN_GUARD_BYTES_AST_INVERSE')
    for name in ('fixtures','reference_rows','differences','scientific','run_group','validate_requested_parts','Budget','Stop','owned_bytes','source','kernel','journal','materialize_shards'):
        Q.need(getattr(NEW_RUN,name) is getattr(OLD_RUN,name),'DIRECT_UNCHANGED_V2_ORIGINAL_SCIENCE_OBJECT:'+name)
    return {'status':'EXACT_CONTINUATION_MAIN_GUARD_BYTES_AST_INVERSE','science_runtime_objects_direct':True,
        'old5_then_v2new3_then_v3new3_before_Budget':True,'old_global_monkeypatch':False,'scientific_DATA_read':False}


def fixtures3(out):
    old=P.fixtures3(out)
    from .test_startup import Boundaries
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Boundaries))
    new={'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'skips':len(result.skipped),
        'expected_failures':len(result.expectedFailures),'unexpected_successes':len(result.unexpectedSuccesses),'scientific_body_reads':0}
    from secondary_pubchem_screening_alpha_v1 import source
    source.write_json(out/'continuation_fixtures3.json',new);Q.need(pure_counts(new,3),'ALL3_NEW_CONTINUATION_BOUNDARIES_BEFORE_BUDGET')
    return {k:old[k]+new[k] for k in ('tests_run','failures','errors','skips','expected_failures','unexpected_successes')}|{'v2_resource_fixtures':old,'v3_continuation_fixtures':new}
