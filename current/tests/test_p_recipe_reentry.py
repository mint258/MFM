"""Allocation re-entry keeps completed work and avoids a second SSH handoff."""
from contextlib import contextmanager
import importlib.util,json,os
from pathlib import Path
import pytest


def setup_case(tmp_path,monkeypatch):
    tools=Path(__file__).resolve().parents[2]/'tools/p_recipe'
    monkeypatch.syspath_prepend(str(tools))
    spec=importlib.util.spec_from_file_location('scheduled_reentry_test',tools/'scheduled_run.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    monkeypatch.setattr(m,'C',tmp_path)
    output=tmp_path/'old';output.mkdir()
    cfg=dict(run='old',output=str(output),samples=3000000,stage=2,round=2,batch_size=32)
    task=dict(configuration=str(tmp_path/'M1.json'),handoff_state=str(tmp_path/'handoff.json'),
              reservation_key='old_standby',node='node',gpu_uuid='gpu')
    m.write(task['configuration'],cfg)
    m.write(task['handoff_state'],dict(phase='SOURCE_EXITED_RESUME_READY',job_id=9,run='old'))
    ledger=dict(runs={'old':dict(state='RUNNING',elapsed_seconds=12,job_id=9)},reservations={'old_standby':{}})
    @contextmanager
    def lock():yield ledger
    monkeypatch.setattr(m,'locked_ledger',lock)
    m.write(tmp_path/'plan.json',dict(batch_size_by_run={'old':32}))
    return m,cfg,task,ledger


def test_complete_run_is_not_restarted(tmp_path,monkeypatch):
    m,c,t,l=setup_case(tmp_path,monkeypatch)
    m.write(Path(c['output'])/'summary.json',dict(status='COMPLETE'))
    assert m.reentered_handoff(t,c,9,100)=='COMPLETE'
    assert len(l['runs'])==1


def test_surviving_trainer_is_waited_for(tmp_path,monkeypatch):
    m,c,t,l=setup_case(tmp_path,monkeypatch)
    bound=dict(pid=123,uid=os.getuid(),start_ticks=456,pgid=123)
    m.write(tmp_path/'old_slurm.json',bound)
    calls=[]
    def observed(pid):
        if calls:raise ProcessLookupError()
        return bound
    def wait(seconds):
        calls.append(seconds);m.write(Path(c['output'])/'summary.json',dict(status='COMPLETE'))
    monkeypatch.setattr(m,'identity',observed);monkeypatch.setattr(m.time,'sleep',wait)
    assert m.reentered_handoff(t,c,9,100)=='COMPLETE'
    assert calls==[1] and len(l['runs'])==1


@pytest.mark.parametrize('sample',[2000000,3000000])
def test_dead_worker_uses_newest_complete_point_in_distinct_output(tmp_path,monkeypatch,sample):
    m,c,t,l=setup_case(tmp_path,monkeypatch)
    out=Path(c['output']);(out/'samples_1000000.pt').touch();(out/f'samples_{sample}.pt').touch()
    (out/'samples_2999999.pt.partial').touch();(out/'losses.csv').write_text('samples,u,l,g,lr,seconds\n100,1,0,0,0,20\n200,2,0,0,0,70\n')
    r=m.reentered_handoff(t,c,9,100)
    assert r['run']=='old_reentry_100' and r['resume_samples']==sample
    assert r['output']!=c['output'] and r['resume_from_output']==c['output']
    assert l['runs']['old']['accounting_closed'] and l['runs']['old']['elapsed_seconds']==50
    assert json.loads(Path(l['runs']['old']['configuration']).read_text())==c
    assert json.loads((tmp_path/'plan.json').read_text())['batch_size_by_run']=={'old_reentry_100':32}
    assert not Path(r['output']).exists() and (out/f'samples_{sample}.pt').exists()


def test_resume_ancestor_is_used_without_reading_checkpoint(tmp_path,monkeypatch):
    m,c,t,l=setup_case(tmp_path,monkeypatch);cp=tmp_path/'samples_2195584.pt';cp.touch()
    c.update(resume=str(cp),resume_samples=2195584)
    assert m.reentered_handoff(t,c,9,100)['resume']==str(cp)


def test_missing_checkpoint_and_wrong_job_do_not_launch(tmp_path,monkeypatch):
    m,c,t,l=setup_case(tmp_path,monkeypatch)
    with pytest.raises(RuntimeError,match='identity mismatch'):m.reentered_handoff(t,c,10,100)
    with pytest.raises(RuntimeError,match='No complete checkpoint'):m.reentered_handoff(t,c,9,100)
    assert len(l['runs'])==1


def test_main_does_not_reenter_ssh_protocol_after_handoff(tmp_path,monkeypatch):
    m,c,t,l=setup_case(tmp_path,monkeypatch)
    (Path(c['output'])/'samples_2000000.pt').touch()
    c['workers']=14;m.write(t['configuration'],c)
    t.update(mode='native_with_standby',python='/python',minimum_free_gpu_mib=100)
    task_path=tmp_path/'task.json';m.write(task_path,t)
    monkeypatch.setattr(m,'REPO',tmp_path)
    policy=tmp_path/'configs/p_recipe/scheduling.json';policy.parent.mkdir(parents=True)
    m.write(policy,dict(cpu_overhead=2))
    monkeypatch.setenv('SLURM_JOB_ID','9');monkeypatch.setenv('SLURM_CPUS_PER_TASK','16')
    monkeypatch.setattr(m.socket,'gethostname',lambda:'node')
    monkeypatch.setattr(m,'allocation_start',lambda job:100)
    monkeypatch.setattr(m,'handoff',lambda *args:pytest.fail('Repeated SSH handoff'))
    monkeypatch.setattr(m.subprocess,'check_output',lambda *args,**kwargs:'')
    import launch_plan
    monkeypatch.setattr(launch_plan,'own_gpu_busy',lambda *args,**kwargs:False)
    launched=[];monkeypatch.setattr(m,'guarded_run',lambda launch:launched.append(launch) or 0)
    assert m.main(task_path)==0
    assert launched[0]['run']=='old_reentry_100'
    assert launched[0]['command'][-1]==t['configuration']
