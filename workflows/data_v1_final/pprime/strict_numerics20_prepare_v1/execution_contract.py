"""Future executor's hard authority gate; this package contains no QM executor."""
import re
from . import contract as C

def user_fields(decision,plan):
    q=C.Q
    q.need(decision['schema']=='USER_AUTHORIZED_PPRIME_NEW20_ALL12_STRICT_QA_V1' and decision['status']=='USER_AUTHORIZED'
        and decision['authorization_basis']=='EXPLICIT_USER_MESSAGE_IN_THIS_SESSION'
        and isinstance(decision['actual_user_statement'],str) and decision['actual_user_statement'].strip()
        and decision['candidate_protocol_reference']==plan['candidate_protocol_reference']
        and decision['original_protocol_reference']==plan['original_protocol_reference']
        and decision['prepared20_reference']==plan['prepared20_reference']
        and decision['maximum_new_QM_calls']==1200 and decision['new_unique_MIDs']==20
        and decision['task_names']==list(C.TASKS) and decision['arms']==list(C.ARMS)
        and decision['cpus']==16 and type(decision['maximum_wall_seconds']) is int and 0<decision['maximum_wall_seconds']<=86400 and decision['per_call_timeout_seconds']==900
        and decision['combined_shared_output_cap_bytes']==C.WHOLE_CAP and decision['automatic_retry'] is False
        and decision['original_quality_thresholds_unchanged'] is True and decision['production_recipe_unchanged'] is True
        and decision['original15FAIL_preserved'] is True and decision['production_or2000_full_release']=='HOLD',
        'REAL_NEW20_EXACT1200_USER_DECISION_REQUIRED_NOT_OLD15_OR_COST_AUTHORITY')

def require_user(plan):
    ref=plan.get('user_decision_reference');C.Q.need(isinstance(ref,dict),'NEW20_USER_DECISION_ABSENT_NO_BODY_INITIALIZE_OR_INVOKE')
    value=C.meta(ref);user_fields(value,plan);return value

def once_key(protocol,prepared20,qa_id):
    C.O.triple(protocol);C.O.triple(prepared20)
    C.Q.need(isinstance(qa_id,str) and re.fullmatch(r'qa20-(?:0[0-9]|1[0-9])-[0-5][0-9]',qa_id),'EXACT_NEW20_CALL_ID_REQUIRED')
    return C.O.sha(C.O.canonical(['independent-strict-numerics20-all12-QA-v1',protocol,prepared20,qa_id]))
