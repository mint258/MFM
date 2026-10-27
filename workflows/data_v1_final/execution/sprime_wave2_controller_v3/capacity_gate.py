"""Resource-only pretransition gate; frozen central CPU parser and own lock checks."""
from contextlib import contextmanager
from pathlib import Path
import fcntl,os,pathlib,stat,sys
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.contract import free_cpu_observation,fields
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.registry import own_directory
LOCK_NAME='central_submission_serialization_v1.lock';NODE='compute-0-13'


def need(ok,message):
    if not ok:raise ValueError(message)


@contextmanager
def serialization_lock(path):
    path = Path(path); own_directory(path.parent)
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(fd)
        need(stat.S_ISREG(info.st_mode) and info.st_uid == 1278 and info.st_nlink == 1,
             "OWN_ORDINARY_METADATA_LOCK_REQUIRED")
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield fd
    finally:
        os.close(fd)


def capacity(raw):
    try:return {'action':'PROCEED','observation':free_cpu_observation({'node':NODE,'cpus':16},raw)}
    except ValueError as exc:
        # Original predicate uses this same error for malformed CPU ranges.
        # Only a valid actual node with 0..15 free is a capacity WAIT.
        if str(exc)!='WAIT_ACTUAL16_FREE_CPU_REQUIRED':raise
        node=fields(raw) if isinstance(raw,str) else raw
        total=int(node['CPUTot']);allocated=int(node['CPUAlloc'])
        if not(0<=allocated<=total and 0<=total-allocated<16):raise
        return {'action':'WAIT_EXISTING_JOBS_OR_CAPACITY','reason':'ACTUAL_FREE_CPU_BELOW16',
            'observation':{'node':NODE,'total_cpus':total,'allocated_cpus':allocated,'free_cpus':total-allocated,
                'raw':raw,'memory_admission_evaluated':False}}


def guarded_transition(read_node,transition,lock_factory,on_capacity=None):
    manager=lock_factory()
    try:fd=manager.__enter__()
    except BlockingIOError:
        return {'action':'WAIT_EXISTING_JOBS_OR_CAPACITY','reason':'OUTER_SUBMISSION_SERIALIZATION_LOCK_BUSY',
            'node_query_started':False,'transition_intents_created':0,'submissions_started':0}
    try:
        decision=capacity(read_node())
        if decision['action']!='PROCEED':return decision
        if on_capacity is not None:on_capacity(decision)
        transition(fd)
        return {'action':'TRANSITION_FINISHED','capacity':decision}
    finally:
        # Catch only acquisition contention above. Errors in query/generator/
        # activation (including EAGAIN) propagate to the original HOLD path.
        manager.__exit__(*sys.exc_info())


def recovery_inputs(pin,load,root):
    review_ref=pin(root/'control/sprime59_held_activation_root_review_v1.json');review=load(review_ref['path'])
    need(review['schema']=='ROOT_HELD59_ACTIVATION_RECOVERY_REVIEW_V1' and review['status']=='APPROVED_COMPLETE_UNACTIVATED_HELD_JOB_ONCE'
        and review['reviewer']=='root' and review['held_job_id']=='4521756' and review['old_once_or_claims_cleared'] is False
        and review['other_jobs_signalled_or_modified'] is False,'ACTUAL_ROOT59_EXISTING_HELD_ACTIVATION_REVIEW')
    hold_ref=review['prior_HOLD_reference'];need(pin(hold_ref['path'])==hold_ref,'ACTUAL_PRIOR59_HOLD_PIN')
    hold=load(hold_ref['path']);need(hold['status'].startswith('HOLD') and hold['stages']['batch-00059']['run']['job_id']=='4521747'
        and 'close' not in hold['stages']['batch-00059'],'REAL_PRIOR_HOLD_WITHOUT59_ACTIVATION')
    previous_review_ref=hold['review_reference'];need(pin(previous_review_ref['path'])==previous_review_ref,'ACTUAL_PREVIOUS_CONTROLLER_REVIEW_PIN')
    previous_review=load(previous_review_ref['path']);need(previous_review['schema']=='ROOT_FINITE_SPRIME_WAVE2_CONTROLLER_REVIEW_V2'
        and previous_review['reviewer']=='root' and previous_review['status']=='APPROVED_FINITE_METADATA_CONTROLLER','REAL_PREVIOUS_V2_ROOT_REVIEW')
    phase='sprime_v3_w2_ctl_b00059_close_20261027_v1'
    activation_ref=pin(root/'control/cpu_auto_memory_activations'/(phase+'.json'));activation=load(activation_ref['path'])
    registry_ref=activation['registry_reference'];need(pin(registry_ref['path'])==registry_ref,'ACTUAL59_CANONICAL_REGISTRY_PIN')
    registry=load(registry_ref['path']);expected=review['original_held_checked_row']
    need(len(registry['jobs'])==len(activation['releases'])==1 and registry['jobs'][0]['job_id']==activation['releases'][0]['job_id']=='4521756'
        and registry['jobs'][0]['request_reference']==expected['request_reference']
        and registry['jobs'][0]['receipt_reference']==expected['receipt_reference'],'SAME_EXISTING1756_NO_NEW_SUBMISSION')
    for key in ('request_reference','receipt_reference'):need(pin(expected[key]['path'])==expected[key],'ORIGINAL1756_REQUEST_OR_SUBMISSION_CHANGED')
    return {'manual_activation_recovery_review_reference':review_ref,'manual_activation_recovery_activation_reference':activation_ref,
        'manual_activation_original_HOLD_reference':hold_ref,'outer_submission_serialization_lock_path':str(root/'control'/LOCK_NAME),
        'prior_controller_review_reference':previous_review_ref,'prior_state_repair_cpu_test_reference':previous_review['pure_state_cpu_test_reference'],
        'cpu_capacity_gate':'ORIGINAL_FREE_CPU_OBSERVATION_ACTUAL_NODE13_MINIMUM16_BEFORE_TRANSITION',
        'outer_lock_fd_inherited_by_metadata_helpers':True,'science_or_once_retry_authorized':False}
