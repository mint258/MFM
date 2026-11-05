"""Exact quota-age failure only: pause before model work, then original full revalidation."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import socket
import time

MESSAGE='Quota feed stale or future'
MAX_WAIT_SECONDS=30
MAX_REJECTIONS_PER_SEGMENT=256


def require(ok,message):
    if not ok:raise ValueError(message)


def rejected_snapshot(error,validator):
    frames=[];trace=error.__traceback__
    while trace is not None:
        if trace.tb_frame.f_code is validator.__code__:frames.append(trace.tb_frame.f_locals)
        trace=trace.tb_next
    require(len(frames)==1,'Exact rejected native validator frame required; never substitute a later feed')
    local=frames[0];raw=local['raw_feed'];feed=local['feed'];value=local['feed_ref'];now=local['observation_now']
    require(type(raw) is bytes and 0<len(raw)<=2<<20 and len(raw)==value['bytes']
        and hashlib.sha256(raw).hexdigest()==value['sha256'] and json.loads(raw)==feed,'Rejected raw feed bytes/ref differ')
    age=now-feed['captured_unix']
    require(age<0 or age>local['limits']['quota_max_age_seconds'],'Original quota-age refusal must actually be outside original0..max_age')
    return raw,dict(schema='native_S_rejected_quota_age_observation_v1',error=MESSAGE,feed=value,
        observation_now=now,captured_unix=feed['captured_unix'],age_seconds=age,
        unchanged_max_age_seconds=local['limits']['quota_max_age_seconds'],classification='future' if age<0 else 'stale',
        consumer_host=socket.gethostname(),uid=os.getuid(),producer_host=feed['host'],
        producer_source_sha256=feed['producer_source_sha256'],validator_source=validator.__code__.co_filename,
        source_sha256=hashlib.sha256(Path(validator.__code__.co_filename).read_bytes()).hexdigest(),
        full_model_or_native_records_not_serialized=True)


def retry_refresh(refresh,capture,record,guard,*,clock=time.monotonic,sleep=time.sleep):
    """No model callback or skipped validation. Tests may substitute only the clock/sinks."""
    started=clock();attempts=0
    while True:
        guard(0)
        try:
            value=refresh()
            if attempts and clock()-started>MAX_WAIT_SECONDS:
                raise TimeoutError('Original quota admission completed after fixed30s; no model work resumed')
            guard(0)
            return value
        except ValueError as error:
            if error.args!=(MESSAGE,):raise
            raw,observation=capture(error);attempts+=1
            observation={**observation,'waiting_elapsed_seconds':clock()-started,'refresh_attempt':attempts,
                'fixed_wait_limit_seconds':MAX_WAIT_SECONDS,'original_age_tolerance_unchanged':True}
            record(raw,observation)
            remaining=MAX_WAIT_SECONDS-(clock()-started)
            if remaining<=0:raise TimeoutError('Original quota admission did not pass within fixed30s; no model work resumed') from error
            sleep(min(1.,remaining))


def install(policy,native_module,child_root,guard):
    """Instance-only operational hook. Numeric contract, original validator/module stay unchanged."""
    ledger=policy.ledger;original=ledger.refresh;validator=native_module.validate_admission
    directory=Path(child_root)/'quota_age_rejections';state={'records':0}
    def record(raw,observation):
        require(state['records']<MAX_REJECTIONS_PER_SEGMENT,'Finite rejected-feed record budget exhausted')
        encoded=(json.dumps(observation,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
        require(len(encoded)<=65536,'Compact rejection observation required')
        guard(len(raw)+len(encoded)+8192)
        if not directory.exists():directory.mkdir(mode=0o700)
        state['records']+=1;prefix=f'rejected_{state["records"]:04d}'
        for name,value in ((prefix+'.feed.json',raw),(prefix+'.observation.json',encoded)):
            with (directory/name).open('xb') as stream:stream.write(value);stream.flush();os.fsync(stream.fileno())
    def wrapped():
        return retry_refresh(original,lambda error:rejected_snapshot(error,validator),record,guard)
    ledger.refresh=wrapped
    return dict(scope='OPERATIONAL_ORIGINAL_QUOTA_REVALIDATION_ONLY',wait_seconds=30,
        max_rejected_snapshots=MAX_REJECTIONS_PER_SEGMENT,source_path=str(Path(__file__).absolute()),
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        numeric_code_data_seed_precision_optimizer_RNG_unchanged=True)
