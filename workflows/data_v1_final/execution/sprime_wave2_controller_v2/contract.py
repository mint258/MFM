"""Pure once-only transition, HOLD and bounded admission rules."""
TERMINAL={'COMPLETED','FAILED','TIMEOUT','CANCELLED','OUT_OF_MEMORY','NODE_FAIL','PREEMPTED','BOOT_FAIL','DEADLINE','REVOKED','SPECIAL_EXIT'}
STAGES=('prepare','run','close')
PRIORITY={'close':0,'run':1,'prepare':2}


def need(ok,message):
    if not ok:raise ValueError(message)


def c0(row):return bool(row and row.get('terminal') and row.get('state')=='COMPLETED' and row.get('exit_code')=='0:0')


def close_hold(report):
    if report.get('schema')!='SPRIME_FORMAL_CPU_CLOSED_BATCH_V3' or report.get('status')!='ACTUAL_TERMINAL_BATCH_CLASSIFIED':return 'INVALID_CLOSURE_CHAIN'
    if report.get('errors') or report.get('consumed_elsewhere'):return 'CLOSURE_ERRORS_OR_EXTERNAL_CONSUMPTION'
    if report.get('valid_packets',0)<=0:return 'NO_VALIDATED_PACKETS'
    if report.get('execution_unresolved',0)>0:return 'CONSUMED_UNKNOWN_NO_RETRY'
    if report.get('unstarted_count',0)>0:return 'UNSTARTED_REQUIRES_NEW_ROOT_CONTINUATION'
    return None


def next_stage(stages):
    for name,row in stages.items():
        if row.get('ambiguous'):return {'action':'HOLD','reason':'UNCERTAIN_'+name.upper()+'_NO_RESUBMISSION'}
    p,s,c=(stages.get(k) for k in STAGES)
    if c:
        if not c.get('terminal'):return {'action':'WAIT'}
        if not c0(c):return {'action':'HOLD','reason':'CLOSER_NOT_ACTUAL_C0'}
        reason=close_hold(c.get('report') or {})
        return {'action':'HOLD','reason':reason} if reason else {'action':'DONE'}
    if s:
        return {'action':'close'} if s.get('terminal') else {'action':'WAIT'}
    if p:
        if not p.get('terminal'):return {'action':'WAIT'}
        return {'action':'run'} if c0(p) else {'action':'HOLD','reason':'PREPARATION_NOT_ACTUAL_C0'}
    return {'action':'prepare'}


def capacity(stage,*,nonterminal_science,nonterminal_aux,owned_run_pending):
    need(stage in STAGES,'EXACT_STAGE')
    if owned_run_pending>=4:return False
    return nonterminal_science<2 if stage=='run' else nonterminal_aux<1


def submission_resolution(intent_exists,request_exists,submission,activation_exists):
    if submission is not None:
        if submission.get('sbatch_returncode')!=0 or not str(submission.get('job_id','')).isdecimal():return 'HOLD_UNKNOWN_OR_FAILED_SUBMISSION_NO_RETRY'
        return 'REGISTERED' if activation_exists else 'HOLD_ACTIVATION_REQUIRES_ROOT_RECOVERY'
    if intent_exists or request_exists:return 'HOLD_UNCERTAIN_PARTIAL_SUBMISSION_NO_RETRY'
    return 'NEW_NOT_SUBMITTED'


def choose(candidates):
    return min(candidates,key=lambda row:(PRIORITY[row['stage']],row['batch_id'])) if candidates else None
