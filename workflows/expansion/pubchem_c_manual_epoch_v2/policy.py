"""Pure mixed-grant/cost/once boundaries. No scheduler, DATA or source IO."""
import math
from pubchem_c_finite500_continuation_v3 import state as S
next_shard=S.next_shard;choose_node=S.choose_node
initial_gate=S.OLD.initial_gate;BLOCKED=S.BLOCKED


def need(ok,reason):
    if not ok:raise ValueError(reason)


def finite_epoch(old_deadline,authorized,new_deadline):
    need(all(type(x) in (int,float) and math.isfinite(x) for x in (old_deadline,authorized,new_deadline))
      and 0<new_deadline-authorized<=72000,'EXPLICIT_NEW_FINITE_GRANT_NOT_AUTOMATIC_RENEWAL')
    return {'old_deadline_unchanged':old_deadline,'new_authorized':authorized,'new_deadline':new_deadline}


def merge_rows(initial,rows,initial_attempts):
    population=dict(initial);attempts=dict(initial_attempts);grants={}
    for row in rows:
        i=row['shard_index'];need(type(i) is int and 52<=i<=499 and i not in grants,'ONE_REGISTERED_PHYSICAL_PARENT_PER_SHARD_ACROSS_EPOCHS')
        grants[i]=row['root_range_review_reference'];need(i not in population,'NO_REPLACEMENT_OF_IMPORTED_POPULATION')
        population[i]=row
        if 'actual_allocated_core_seconds' in row:
            job=row['job_id'];need(job not in attempts,'NO_PHYSICAL_PARENT_COST_DOUBLE_COUNT');attempts[job]=row
    return population,attempts


def safe_next(population,attempted,global_claimed,decision,free,now,deadline):
    if now>=deadline:return 'FINITE_ABSOLUTE_DEADLINE_NO_RENEWAL',None,None
    # Parenthesize the entire consumed union: no intent/claim ever disappears.
    missing=(set(attempted)|set(global_claimed))-set(population)
    if missing:return 'HOLD_CONSUMED_WITHOUT_ACTUAL_REGISTRATION_NO_RETRY',None,None
    return decision(population,set(attempted),free,now,deadline)


def transition_gate(old_live,global_lock_owned,old_deadline,now,new_deadline,stable):
    if old_live or not global_lock_owned:return 'WAIT_PREDECESSOR_OR_GLOBAL_OWNER_ZERO_INTENT'
    need(now>=old_deadline and stable,'ACTUAL_OLD_DEADLINE_AND_STABLE_CUTOVER_REQUIRED')
    if now>=new_deadline:return 'FINITE_ABSOLUTE_DEADLINE_NO_RENEWAL'
    return 'ROOT_REVIEWED_NEW_EPOCH_CAN_OBSERVE'


def exact_union(entries):
    result={}
    for value in entries:
        key=(value['endpoint'],value['uid'],str(value['job_id']))
        need(type(value['allocated_core_seconds']) is int and value['allocated_core_seconds']>=0,'ACTUAL_NONNEGATIVE_PARENT_COST')
        if key in result:need(result[key]['allocated_core_seconds']==value['allocated_core_seconds'],'CONFLICTING_ACTUAL_PARENT_COST_HOLD')
        else:result[key]=value
    return list(result.values())

def effective_cap(root):
    """Old six is a preserved v3 frame;new effective authority is explicit."""
    info=root['manual_resource_epoch'];cap=info['effective_max_nonterminal_C_parents']
    need(type(cap)is int and 1<=cap<=12 and root['max_nonterminal_C_parents']==info['base_v3_max_nonterminal_C_parents']==6
        and info['root_explicit_resource_cap_override'] is True and info['reserved_non_C_cpus']==root['reserved_non_C_cpus']==16,
        'REAL_ROOT_EFFECTIVE_CAP1_TO12_NOT_OLD6_AS_AUTHORITY')
    return cap

def resource_decision(population,attempted,free,now,deadline,effective_max_nonterminal_C_parents):
    need(type(effective_max_nonterminal_C_parents)is int and 1<=effective_max_nonterminal_C_parents<=12,'EXPLICIT_ROOT_EFFECTIVE_RESOURCE_CAP')
    need(type(deadline) in (int,float) and type(now) in (int,float),'REAL_FIXED_DEADLINE_VALUES')
    if now>=deadline:return 'FINITE_ABSOLUTE_DEADLINE_NO_RENEWAL',None,None
    if attempted-set(population):return 'HOLD_ATTEMPTED_WITHOUT_ACTUAL_REGISTRATION_NO_RETRY',None,None
    action,index=resource_next_shard(population,attempted,{i:population[i] for i in (0,1) if i in population},effective_max_nonterminal_C_parents)
    if action!='ELIGIBLE':return action,index,None
    need(52<=index<=499,'NO_REDISPATCH_IMPORTED_OR_REPAIRED_SHARD')
    node=choose_node(free)
    if node is None:return 'WAIT_ACTUAL16_CPU_PLUS_CONTIGUOUS16_NON_C_RESERVE',index,None
    return 'ELIGIBLE',index,node

def nonterminal_count(population):
    return sum(row['status'] not in S.TERMINAL and row['status']!='CLOSED' for row in population.values())

def known_nonterminal_count(population):
    return sum(row.get('job_id') is not None and row['status'] not in S.TERMINAL and row['status'] not in S.BLOCKED and row['status']!='CLOSED'
        for row in population.values())

def resource_next_shard(observed,attempted,initial,max_nonterminal=2):
    if type(max_nonterminal) is not int or not 1<=max_nonterminal<=12:raise ValueError('ROOT_EXPLICIT_NONTERMINAL_CAP_1_THROUGH12')
    if not initial_gate(initial):return 'HOLD_INITIAL_TWO_ACTUAL_C0_CLOSURES',None
    if any(v['status'] in BLOCKED for v in observed.values()):return 'HOLD_FAILED_UNKNOWN_OR_PARTIAL_NO_RETRY',None
    if sum(v['status']!='CLOSED' for v in observed.values())>=max_nonterminal:return 'WAIT_AT_ROOT_NONTERMINAL_C_CAP',None
    for index in range(2,500):
        if index not in observed and index not in attempted:return 'ELIGIBLE',index
    if len(observed)==500 and all(v['status']=='CLOSED' for v in observed.values()):return 'ALL500_PHYSICAL_SHARDS_CLOSED_NO_POOL_RELEASE',None
    return 'HOLD_ATTEMPTED_WITHOUT_UNAMBIGUOUS_PARENT_NO_RETRY',None
