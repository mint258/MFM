"""Four bounded operational metadata cases; no model/SDK/data/Slurm."""
import pytest
import hashlib
import json
from quota_retry import retry_refresh,rejected_snapshot,MESSAGE


class Clock:
    def __init__(self):self.value=0.
    def now(self):return self.value
    def sleep(self,delay):self.value+=delay


def test_transient_exact_refusal_waits_for_original_full_success():
    clock=Clock();calls=[];saved=[]
    def validator():
        raw_feed=json.dumps(dict(captured_unix=1.,host='sonmi',producer_source_sha256='a'*64)).encode()
        feed=json.loads(raw_feed);feed_ref=dict(path='/synthetic/feed',bytes=len(raw_feed),sha256=hashlib.sha256(raw_feed).hexdigest())
        observation_now=.99;limits=dict(quota_max_age_seconds=90)
        raise ValueError(MESSAGE)
    def refresh():
        calls.append(clock.now())
        if len(calls)<3:validator()
        return {'original_full_validation':'PASS'}
    result=retry_refresh(refresh,lambda error:rejected_snapshot(error,validator),
        lambda raw,row:saved.append((raw,row)),lambda n:None,clock=clock.now,sleep=clock.sleep)
    assert result=={'original_full_validation':'PASS'} and len(calls)==3 and len(saved)==2 and clock.now()==2
    assert all(json.loads(raw)['captured_unix']==1. and row['classification']=='future'
        and row['age_seconds']<0 and row['original_age_tolerance_unchanged'] for raw,row in saved)


def test_persistent_refusal_times_out_without_success_or_model_callback():
    clock=Clock();saved=[]
    def refresh():raise ValueError(MESSAGE)
    with pytest.raises(TimeoutError,match='fixed30s'):
        retry_refresh(refresh,lambda error:(b'old',{'age_seconds':91}),lambda raw,row:saved.append(row),lambda n:None,
            clock=clock.now,sleep=clock.sleep)
    assert clock.now()==30 and saved[-1]['waiting_elapsed_seconds']==30


def test_other_validation_failure_exits_immediately_without_retry_or_snapshot():
    clock=Clock();calls=[]
    def refresh():calls.append(1);raise ValueError('Different source or lease')
    with pytest.raises(ValueError,match='Different source'):
        retry_refresh(refresh,lambda error:pytest.fail('must not capture unrelated failure'),
            lambda raw,row:pytest.fail('must not record fake quota failure'),lambda n:None,clock=clock.now,sleep=clock.sleep)
    assert calls==[1] and clock.now()==0


def test_missing_exact_rejected_frame_or_budget_failure_is_never_suppressed():
    clock=Clock()
    def refresh():raise ValueError(MESSAGE)
    def unrelated_validator():pass
    def capture(error):return rejected_snapshot(error,unrelated_validator)
    with pytest.raises(ValueError,match='Exact rejected'):
        retry_refresh(refresh,capture,lambda raw,row:None,lambda n:None,clock=clock.now,sleep=clock.sleep)
    with pytest.raises(MemoryError):
        retry_refresh(refresh,lambda error:(b'x',{}),lambda raw,row:None,
            lambda n:(_ for _ in ()).throw(MemoryError('original cap')),clock=clock.now,sleep=clock.sleep)
