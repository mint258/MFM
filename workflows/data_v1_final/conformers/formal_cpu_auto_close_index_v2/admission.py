"""Bounded future-only metadata wait, with original Client validation on every try."""
import math,time
from workflows.data_v1_final.conformers.formal_cpu_auto_v3 import contract as C,runtime_io as R
ERROR='STALE_FUTURE_OR_EXPIRED_ACCOUNT_QUOTA_PROVIDER'


def future_delay(error,last,now):
    if str(error)!=ERROR:return None
    sampled=last.get('observed_unix_seconds');expiry=last.get('publisher_expires_unix_seconds')
    if type(sampled) not in (int,float) or type(expiry) not in (int,float) or not all(math.isfinite(x) for x in (sampled,expiry,now)):return None
    gap=sampled-now
    if last.get('provider_status')!='RUNNING' or not last.get('identity_reference') or not last.get('snapshot_reference'):return None
    return gap if 0<gap<=2 and now<sampled<expiry else None


def strict_preprobe(proof,session,save):
    reuse,Q,_=R.quota_reuse(session['quota_reuse_review_reference'],C.sources());client=Q.Client(reuse['provider_review_reference'],proof['request'])
    began=time.monotonic();identity=None
    for attempt in range(2):
        before=time.time();start=time.monotonic()
        try:
            value=client.observe()
            save({'attempt':attempt,'status':'ORIGINAL_CLIENT_VALIDATION_PASS','cpu_begin_unix':before,'cpu_end_unix':time.time(),
                'elapsed_monotonic_seconds':time.monotonic()-start,'last_quota_evidence':client.last,'original_freshness_rule_unchanged':True})
            return value
        except Exception as exc:
            now=time.time();last=client.last or {};gap=future_delay(exc,last,now)
            save({'attempt':attempt,'status':'ORIGINAL_CLIENT_VALIDATION_FAILED','error':repr(exc),'cpu_begin_unix':before,'cpu_end_unix':now,
                'elapsed_monotonic_seconds':time.monotonic()-start,'last_quota_evidence':last,'eligible_future_wait_seconds':gap})
            if identity is not None:C.need(last.get('identity_reference')==identity,'PROVIDER_IDENTITY_CHANGED_DURING_METADATA_WAIT')
            identity=last.get('identity_reference')
            if attempt!=0 or gap is None or time.monotonic()-began>10:raise
            # Wait only, never alter the snapshot, timestamp, now argument or
            # 0<=age<=120/expiry predicate. Next attempt is original observe.
            time.sleep(min(2,gap+0.02))
    raise ValueError('BOUNDED_ORIGINAL_CLIENT_PREPROBE_FAILED')
