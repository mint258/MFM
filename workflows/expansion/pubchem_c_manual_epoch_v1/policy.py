"""Pure mixed-grant/cost/once boundaries. No scheduler, DATA or source IO."""
import math


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
