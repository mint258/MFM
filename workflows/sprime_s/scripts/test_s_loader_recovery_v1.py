"""Verify timeout recovery, cursor/RNG preservation and strict fatal errors."""
import json,os
from pathlib import Path
from prepare import ROOT,save,sha
from s_loader_recovery_v1 import RecoveringLoaderIterator,LoaderRetryExhausted

def main():
    assert os.environ.get('SLURM_JOB_ID') and int(os.environ['SLURM_CPUS_PER_TASK'])>=16
    import torch
    torch.set_num_threads(16);torch.set_num_interop_threads(1);torch.manual_seed(1234)
    class Sampler:
        committed=0
        def state_dict(self):return {'committed':self.committed}
    class CursorIterator:
        def __init__(self,sampler,fail_after=None,error=None):
            self.cursor=sampler.committed;self.fail_after=fail_after;self.error=error;self.closed=False
            torch.rand(7)  # Actual CPU RNG movement during worker creation.
        def __iter__(self):return self
        def __next__(self):
            if self.cursor==self.fail_after:
                raise self.error or RuntimeError('DataLoader timed out after 60.0 seconds')
            if self.cursor>=17:raise StopIteration
            value=(self.cursor,self.cursor*self.cursor);self.cursor+=1;return value
        def close(self):self.closed=True
    sampler=Sampler();attempts=[];events=[]
    def factory():
        value=CursorIterator(sampler,fail_after=5 if not attempts else None);attempts.append(value);return value
    iterator=RecoveringLoaderIterator(factory,sampler,lambda v:v.close(),torch,role='fixture',on_retry=events.append)
    expected_rng=torch.get_rng_state().clone();actual=[]
    for item in iterator:
        actual.append(item);sampler.committed+=1
    iterator.close()
    assert actual==[(i,i*i) for i in range(17)]
    assert torch.equal(expected_rng,torch.get_rng_state()) and all(v.closed for v in attempts)
    assert len(events)==1 and events[0]['committed_sampler']=={'committed':5}
    exhausted=Sampler();created=[]
    def always_timeout():
        value=CursorIterator(exhausted,fail_after=0);created.append(value);return value
    iterator=RecoveringLoaderIterator(always_timeout,exhausted,lambda v:v.close(),torch,role='exhaustion')
    try:next(iterator)
    except LoaderRetryExhausted:pass
    else:raise AssertionError('Expected bounded exhaustion')
    finally:iterator.close()
    assert len(created)==4 and exhausted.committed==0 and all(v.closed for v in created)
    fatal_results=[]
    for error in [RuntimeError('ACTUAL_RECORD_MANIFEST_MISMATCH'),
                  RuntimeError('DataLoader worker exited unexpectedly'),
                  AssertionError('NONFINITE_VALIDATION_LOSS')]:
        failed=Sampler();creations=[]
        def fatal_factory():
            value=CursorIterator(failed,fail_after=0,error=error);creations.append(value);return value
        iterator=RecoveringLoaderIterator(fatal_factory,failed,lambda v:v.close(),torch,role='fatal')
        try:next(iterator)
        except BaseException as caught:assert caught is error
        else:raise AssertionError('Fatal error was hidden')
        finally:iterator.close()
        assert len(creations)==1 and failed.committed==0
        fatal_results.append(str(error))
    result={'status':'LOADER_RECOVERY_CURSOR_RNG_AND_FATAL_CLASSIFICATION_PASS',
        'job_id':os.environ['SLURM_JOB_ID'],'implementation_sha256':sha(ROOT/'scripts/s_loader_recovery_v1.py'),
        'fixture_records':17,'duplicate_or_missing':0,'injected_timeout_at_committed_record':5,
        'restarts':1,'parent_cpu_rng_exact':True,'max_restarts':3,'exhaustion_creations':4,
        'fatal_errors_preserved':fatal_results,'native_lmdb_test_performed':False,
        'formal_training_performed':False}
    save(ROOT/'reports/s_loader_recovery_fixture_v1.json',result);print(json.dumps(result),flush=True)

if __name__=='__main__':main()
