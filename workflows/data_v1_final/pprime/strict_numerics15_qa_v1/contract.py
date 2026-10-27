"""Exact proposed protocol, genuine user-decision requirement and old controls."""
import pathlib
from workflows.data_v1_final.pprime.causal15_native_electronic_readonly_v1 import contract as N
from workflows.data_v1_final.pprime.strict_numerics_qa_proposal_v1 import proposal as P
Q=N.Q;meta=N.meta;unique=N.unique;O=N.G.P.O;HERE=Q.REPO/'workflows/data_v1_final/pprime/strict_numerics15_qa_v1'
FILES=('__init__.py','contract.py','io.py','prepare.py','worker.py','run.py','test_v1.py','metadata.py','README.md')
MODULE='workflows.data_v1_final.pprime.strict_numerics15_qa_v1.run';KEY='pprime_strict_numerics15_independent_qa_v1';STAGE='PPRIME_USER_AUTHORIZED_STRICT_NUMERICS15_QA_ONLY'
BASE=Q.ROOT/'artifacts/pprime_strict_numerics15_qa_v1';LEDGER=BASE/'qa_once_ledger';CAP=2<<30;WORKER_CAP=112<<20;PARENT_CAP=256<<20
CANDIDATE=Q.REPO/'configs/data_v1/pprime/strict_numerics15_qa_v1_protocol_proposed.json'
PARAMETERS={'maximum_new_QM_calls':15,'original_source_cases':['case-054','case-055','case-058','case-059','case-060','case-061'],
    'molecule_id':O.MID,'conditions':list(O.CASES),'arms':list(O.ARMS),'mopac_SCFCRT':'1.D-9','xTB_acc':'0.01',
    'original_seed':20261010,'sigma_A':0.1,'per_call_timeout_seconds':900,'cpus':16,'maximum_native_workers':15,
    'wall_seconds':7200,'whole_output_cap_bytes':CAP,'worker_partition_bytes':WORKER_CAP,'parent_partition_bytes':PARENT_CAP,
    'new_pure_fixture_methods':3,'all3_before_scientific_bodies':True,'original_native_invoke_function_unchanged':True,
    'new_once_protocol_binding':True,'old_once_reused_or_removed':False,'automatic_retry':False,
    'original15FAIL_preserved':True,'original_quality_tolerances_unchanged':True,'production_full_or2000_release':'HOLD'}


def require_user(plan):
    ref=plan.get('user_decision_reference');Q.need(isinstance(ref,dict),'REAL_USER_DECISION_REQUIRED_BEFORE_BODY_OR_INITIALIZE')
    d=meta(ref);user_fields(d,plan);return d


def user_fields(d,plan):
    Q.need(d['schema']=='USER_AUTHORIZED_PPRIME_STRICT_NUMERICS15_QA_V1' and d['status']=='USER_AUTHORIZED'
        and d['authorization_basis']=='EXPLICIT_USER_MESSAGE_IN_THIS_SESSION' and isinstance(d['actual_user_statement'],str) and d['actual_user_statement'].strip()
        and d['candidate_protocol_reference']==plan['candidate_protocol_reference'] and d['original_protocol_reference']==plan['original_protocol_reference']
        and d['maximum_new_QM_calls']==15 and d['cpus']==16 and d['maximum_wall_seconds']==7200 and d['per_call_timeout_seconds']==900
        and d['whole_output_cap_bytes']==CAP and d['original_quality_thresholds_unchanged'] is True
        and d['production_recipe_unchanged'] is True and d['automatic_retry'] is False and d['full_or2000_release']=='HOLD',
        'REAL_EXACT_LIMITED15_USER_DECISION_NOT_GENERIC_COST_AUTHORITY')


def protocol(plan):
    original_ref=plan['original_protocol_reference'];candidate_ref=plan['candidate_protocol_reference']
    Q.need(original_ref['path']==str(P.ORIGINAL_PROTOCOL) and original_ref['sha256']==P.ORIGINAL_PROTOCOL_SHA
        and candidate_ref['path']==str(CANDIDATE),'EXACT_FIXED_ORIGINAL_AND_NEW_PROTOCOL_LOCATORS')
    old=meta(original_ref);new=meta(candidate_ref);expected,diff=P.derive(old)
    Q.need(new==expected and P.restore(new)==old,'EXACT_THREE_NUMERICAL_FIELDS_ONLY_NO_OTHER_RECIPE_CHANGE');return old,new,diff


def parents(plan):
    old,new,diff=protocol(plan);r=meta(plan['native_control_receipt_reference']);np=meta(r['plan_reference']);proof=meta(r['startup_proof_reference'])
    Q.need(r['schema']=='PPRIME_CAUSAL15_NATIVE_ELECTRONIC_RECEIPT_V1' and r['status']=='EXACT15_RETAINED_NATIVE_EVIDENCE_RECORDED_UNKNOWN_CAUSE_HOLD'
        and r['job_id']=='4521891' and r['uid']==1278 and r['endpoint']=='202.38.247.57:22' and r['new_QM_calls']==0
        and np['scope_parameters']==N.PARAMETERS==proof['request']['scope_parameters'] and proof['uid']==1278
        and str(proof['job_id'])=='4521891' and proof['request']['scope_key']==N.KEY,'ACTUAL1891_CONTROL_NOT_PRODUCTION_ACCEPTANCE')
    for path in (N.HERE/n for n in N.FILES):Q.need(Q.pin(path) in proof['request']['source_references'],'UNCHANGED1891_CONTROL_SOURCE')
    _,raw=N.G.D.account(plan['native_control_accounting_reference'],r)
    gp,source,prepared,cases,data,refs,prior=N.parents(np);rp=meta(gp['recovery_plan_reference']);execution=meta(rp['execution_receipt_reference'])
    prepared_ref=execution['prepared_reference'];Q.need([v['qa_id'] for v in prepared['tasks']]==['qa-%02d'%i for i in range(15)],'EXACT_ORIGINAL15_NO_SUBSTITUTION')
    # Only old task/input/evidence/control-record bodies are consumed. Raw controls
    # stay preserved, and the new native calls produce their own retained raw.
    # Original initialize_worker also validates its immutable reproduction assets
    # and the audit-membership Parquet. Keep their original producer pins as DATA.
    wanted=list(source['execution_asset_references'])
    for row in prepared['tasks']:wanted.extend([row['task_reference'],row['original_evidence_reference'],cases[row['qa_id']]['record_reference'],*row['target_input_references'],*cases[row['qa_id']]['actual_input_references']])
    refs=unique([*refs,plan['native_control_receipt_reference'],plan['native_control_accounting_reference'],raw,r['plan_reference'],r['startup_proof_reference'],
        plan['original_protocol_reference'],plan['candidate_protocol_reference']])
    return old,new,diff,source,prepared,prepared_ref,cases,unique(wanted),refs,proof['request']['source_references']


def once_key(plan,prepared_ref,old_qa):return P.once_key(plan['candidate_protocol_reference'],prepared_ref,old_qa)
