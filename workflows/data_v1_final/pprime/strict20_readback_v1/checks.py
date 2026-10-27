"""Pure cell/lineage boundaries, without chemistry formula copies."""
from __future__ import annotations
from . import contract as C

def qa_cell(qa):
    C.need(isinstance(qa,str),'LITERAL_QA_ID');parts=qa.split('-')
    C.need(len(parts)==3 and parts[0]=='qa20' and len(parts[1])==len(parts[2])==2 and parts[1].isdigit() and parts[2].isdigit(),'FIXED_QA_ID_FORMAT')
    i,j=int(parts[1]),int(parts[2]);C.need(0<=i<20 and 0<=j<60,'FIXED1200_CELL');return i,C.E.P.TASKS[j//5],C.E.P.ARMS[j%5]

def identity(row,task,result,claim,plan):
    qa=row['qa_id'];_,condition,arm=qa_cell(qa)
    C.need(task['qa_id']==result['qa_id']==claim['qa_id']==qa and task['condition']==result['condition']==condition
        and task['arm']==result['arm']==arm and task['molecule_id']==result['molecule_id']==row['molecule_id']
        and result['task_reference']==claim['task_reference']==row['task_reference'],'EXACT1200_IDENTITY_NOT_NAME_ONLY')
    for key in ('candidate_protocol_reference','prepared20_reference','user_decision_reference'):
        C.need(result[key]==claim[key]==plan[key],'EXACT_CLAIM_PROTOCOL_PREPARED_USER_LINEAGE')
    C.need(str(claim['job_id'])==C.JOB and claim['uid']==1278 and claim['automatic_retry'] is False
        and claim['state']=='INTENT_NOT_NATIVE_RETURN','ORIGINAL_ONCE_NOT_A_NATIVE_PROCESS_PROOF')

def exact(a,b,wire):
    """The actual frozen codec checks type, None, list order and every float bit."""
    wire.exact(a,b);return True

def expected_key(row):return (row['molecule_id'],row['condition'],*row['arms'])

def index_analysis(a):
    C.need(a['schema']=='PPRIME_NEW20_DEFINED_QA_CHECKS_V1' and len(a['own_call_checks'])==1200 and len(a['pair_checks'])==1200
        and a['old15FAIL_preserved'] is True and a['scientific_PASS'] is False and a['full_or2000_release']=='HOLD','ACTUAL_ALL1200_DECLARED_CHECKS')
    own={r['qa_id']:r for r in a['own_call_checks']};pair={expected_key(r):r for r in a['pair_checks']}
    C.need(len(own)==len(pair)==1200 and sum(len(r['defined_vector_checks']) for r in pair.values())==500,'UNIQUE1200_CHECKS_EXACT500_VECTORS')
    return own,pair
