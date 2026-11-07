"""Refresh only Root's all-writer future forecast at original quota observations."""
import fcntl,os,pathlib,stat,time
from . import contract as C
POINTER=C.Q.ROOT/'control/root_current_all_future_ledger_v1.json'
LOCK=C.Q.ROOT/'control/root_current_all_future_ledger_v1.lock'

def validate(pointer,review):
    C.need(pointer['schema']=='ROOT_CURRENT_ALL_FUTURE_METADATA_POINTER_V1'
      and type(pointer['total_future_reserved_bytes'])is int and pointer['total_future_reserved_bytes']>=0,
      'ACTUAL_ROOT_ALL_FUTURE_RESOURCE_POINTER')
    C.need(review['reviewer']=='root' and review['status'].startswith('APPROVED')
      and type(review['total_future_reserved_bytes'])is int
      and review['total_future_reserved_bytes']==pointer['total_future_reserved_bytes'],
      'EXACT_SIGNED_CURRENT_ROOT_ALL_WRITER_FUTURE_TOTAL')
    return pointer['total_future_reserved_bytes']

def checked(budget,original,dispatch,force):
    if time.monotonic()<budget.next_quota:
        return original(budget,dispatch=dispatch,force=force)
    # Root writes this pointer only under the same existing lock. Hold SH across
    # the original fresh quota observation and floor check, so new reservations
    # cannot race this observation. No CAS, Source, DATA or once state is written.
    fd=os.open(LOCK,os.O_RDONLY|os.O_NOFOLLOW)
    with os.fdopen(fd,'rb')as lock:
        s=os.fstat(lock.fileno())
        C.need(s.st_uid==1278 and stat.S_ISREG(s.st_mode),'ORIGINAL_OWN_ROOT_FUTURE_LOCK')
        fcntl.flock(lock,fcntl.LOCK_SH)
        reference=C.Q.pin(POINTER);pointer=C.meta(reference)
        review_reference=pointer['review_reference'];path=pathlib.Path(review_reference['path'])
        C.need(C.Q.ROOT/'control'in path.parents,'EXACT_ROOT_CONTROL_RESOURCE_REVIEW_ONLY')
        total=validate(pointer,C.meta(review_reference))
        budget.total=total
        budget.current_future_observation={'observed_unix_seconds':time.time(),
          'total_future_reserved_bytes':total,'review_reference':review_reference,
          'pointer_path':str(POINTER),'pointer_is_mutable_observation_not_immutable_Source':True,
          'same_original_200GB_floor':True,'same_existing_Root_lock_held_during_quota_check':True}
        return original(budget,dispatch=dispatch,force=force)
