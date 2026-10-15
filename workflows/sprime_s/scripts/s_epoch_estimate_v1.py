"""Descriptive B3 S-loss marginal-gain estimate; never changes training or judgment."""
import math
TASKS=('element','distance','bond_order')

def estimate_epochs(integer):
    result={'status':'AWAITING_THREE_INTEGER_B3_FULL_ENDPOINTS','estimated_epochs':None,'lower_bound_epochs':None,
        'per_task':{},'basis':'Await complete B3 integer-epoch FULL endpoints.',
        'scope':'FULL S-loss marginal gain only; joint downstream convergence is a separate predefined criterion.',
        'extrapolation_verified':False,'additional_training_authorized_or_executed':False}
    if set(integer)!={1,2,3}:return result
    for task in TASKS:
        values=[float(integer[e][task]) for e in (1,2,3)]
        assert all(math.isfinite(v) and v>0 for v in values)
        a,b,c=values;g12=abs(a-b)/b;g23=abs(b-c)/c
        result['per_task'][task]={'epoch_losses':values,'relative_change_1_to_2':g12,'relative_change_2_to_3':g23}
    for epoch in (1,2):
        key='relative_change_1_to_2' if epoch==1 else 'relative_change_2_to_3'
        if all(v[key]<.02 for v in result['per_task'].values()):
            result.update(status='OBSERVED_NEXT_INTEGER_EPOCH_GAIN_BELOW_TWO_PERCENT',estimated_epochs=epoch,lower_bound_epochs=epoch,
                basis='All three FULL S losses change by less than2% from B3 epoch '+str(epoch)+' to '+str(epoch+1)+'. This is an S-curve estimate, not a joint probe convergence claim.')
            return result
    result['lower_bound_epochs']=3
    invalid=[]
    for task,row in result['per_task'].items():
        if row['relative_change_2_to_3']<.02:
            row['projection_status']='ALREADY_OBSERVED_WITHIN_TOLERANCE_HELD_FLAT_FOR_CONDITIONAL_FORECAST'
            continue
        a,b,c=row['epoch_losses'];d12=a-b;d23=b-c
        if d12<=0 or d23<=0:
            row['projection_status']='NO_MONOTONIC_DECAY_IDENTIFIED';invalid.append(task);continue
        ratio=d23/d12
        if not 0<ratio<1:
            row['projection_status']='NO_DECELERATING_DECAY_IDENTIFIED';invalid.append(task);continue
        floor=c-d23*ratio/(1-ratio)
        row.update(fitted_decay_ratio=ratio,fitted_loss_floor=floor)
        if floor<=0:
            row['projection_status']='NO_POSITIVE_ASYMPTOTIC_FLOOR_IDENTIFIED';invalid.append(task);continue
        row['projection_status']='CONDITIONAL_THREE_POINT_EXPONENTIAL_WITH_POSITIVE_FLOOR'
    if invalid:
        result.update(status='LOWER_BOUND_ONLY_FINITE_EPOCH_COUNT_NOT_IDENTIFIED',
            basis='Epoch2 to3 still exceeds2% for at least one FULL S loss, so the earliest candidate is epoch3 and verification needs another endpoint. No defensible finite upper estimate from this curve: '+','.join(invalid)+'.')
        return result
    for epoch in range(3,51):
        changes=[]
        for row in result['per_task'].values():
            if row['projection_status'].startswith('ALREADY_'):changes.append(0.);continue
            a=row['epoch_losses'][0];floor=row['fitted_loss_floor'];ratio=row['fitted_decay_ratio']
            now=floor+(a-floor)*ratio**(epoch-1);nxt=floor+(a-floor)*ratio**epoch
            changes.append(abs(now-nxt)/nxt)
        if all(value<.02 for value in changes):
            result.update(status='CONDITIONAL_UNVERIFIED_EXPONENTIAL_S_CURVE_FORECAST',estimated_epochs=epoch,
                basis='Conditional three-integer-point positive-floor exponential extrapolation predicts marginal FULL S gains below2% at epoch '+str(epoch)+'. The learning-rate horizon ends at3; extrapolation and joint probe convergence are unverified.')
            result['projected_relative_changes_at_estimated_epoch']=dict(zip(TASKS,changes))
            return result
    result.update(status='LOWER_BOUND_ONLY_THRESHOLD_NOT_IDENTIFIED_WITHIN_FIFTY_PROJECTED_EPOCHS',
        basis='No sub2% marginal threshold within50 projected epochs under the conditional three-point fit; no validated finite estimate.')
    return result
