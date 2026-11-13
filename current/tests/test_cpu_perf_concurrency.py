"""CPU-only tests of admission, kernel identities and disjoint core assignment."""
import importlib
import json
import os
from pathlib import Path
import socket

import pytest


@pytest.fixture
def modules(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2]/'tools/model_v3'))
    return importlib.import_module('model_gpu_registry'), importlib.import_module('cpu_perf_concurrency')


def identity():
    return dict(status='ACTIVE',pid=100,uid=os.getuid(),boot_id='kernel-boot',start_ticks=771,
        pgid=100,sid=100,argv_sha256='original-command',cgroup='1:freezer:/slurm/job_123/step_batch\n',
        slurm_job_id='123')


def record():
    return dict(identity(),schema='MODEL_GPU_PROCESS_V1',gpu='GPU-test',host=socket.gethostname())


def test_registered_live_same_uid_is_admitted_but_same_uid_alone_is_not(modules,monkeypatch,tmp_path):
    guard,_ = modules
    monkeypatch.setattr(guard,'REGISTRY',tmp_path)
    directory=tmp_path/'GPU-test';directory.mkdir()
    monkeypatch.setattr(guard,'capture_process_identity',lambda pid,**kw: identity())
    assert guard.registered_model_pids('GPU-test') == set()
    (directory/(socket.gethostname()+'_100_771.json')).write_text(json.dumps(record()))
    assert guard.registered_model_pids('GPU-test') == {100}
    monkeypatch.setattr(guard,'compute_pids',lambda gpu:{100,999})
    with pytest.raises(RuntimeError,match='999'):
        guard.require_only_registered('GPU-test')


@pytest.mark.parametrize('key,value',[
    ('uid',99999),('pid',101),('boot_id','rebooted'),('start_ticks',772),('pgid',101),
    ('sid',101),('argv_sha256','changed-command'),('cgroup','another-job'),('slurm_job_id','456'),
    ('status','GONE')])
def test_stale_or_changed_process_is_never_admitted(modules,key,value):
    guard,_ = modules
    current=identity();current[key]=value
    assert not guard.matches(record(),current,'GPU-test')


def test_other_host_other_gpu_and_unrecognized_registration_fail(modules):
    guard,_ = modules
    for patch in ({'host':'another-node'},{'gpu':'GPU-other'},{'schema':'arbitrary-own-process'}):
        assert not guard.matches(dict(record(),**patch),identity(),'GPU-test')


def test_three_models_receive_exactly_16_distinct_allocated_cores(modules):
    _,suite=modules
    layout=suite.cpu_layout(set(range(20,68)),3,16)
    assert list(map(len,layout)) == [16,16,16]
    assert set().union(*map(set,layout)) == set(range(20,68))
    assert all(not set(layout[a])&set(layout[b]) for a,b in ((0,1),(0,2),(1,2)))
    with pytest.raises(ValueError):
        suite.cpu_layout(range(32),3,16)


def test_slurm_cpu_ids_take_precedence_over_a_wide_kernel_affinity(modules,monkeypatch):
    _,suite=modules
    monkeypatch.setenv('SLURM_JOB_ID','123');monkeypatch.setenv('SLURM_CPUS_PER_TASK','8')
    monkeypatch.setattr(suite,'query',lambda *a:'Nodes=compute-0-22 CPU_IDs=16-19,24-27 Mem=0')
    monkeypatch.setattr(os,'sched_getaffinity',lambda pid:set(range(104)))
    assert suite.allocated_cpus() == [16,17,18,19,24,25,26,27]


def test_registration_cannot_name_another_jobs_benchmark_output(modules,monkeypatch):
    guard,_ = modules
    monkeypatch.setenv('SLURM_JOB_ID','123')
    assert guard.validate_output(guard.PERF/'concurrency_123/single/task0',benchmark=True)
    with pytest.raises(ValueError):
        guard.validate_output(guard.PERF/'concurrency_456/single/task0',benchmark=True)


def test_previous_exclusive_launcher_cannot_be_joined(modules,monkeypatch,tmp_path):
    import fcntl
    guard,_=modules
    monkeypatch.setattr(guard,'LOCKS',tmp_path)
    monkeypatch.setattr(guard,'metadata_capacity',lambda:None)
    with (tmp_path/'GPU-test.lock').open('a') as old:
        fcntl.flock(old,fcntl.LOCK_EX|fcntl.LOCK_NB)
        with pytest.raises(BlockingIOError):
            with guard.shared_model_gpu('GPU-test','unused'):
                pytest.fail('An existing exclusive job must remain protected')


def test_new_registered_launchers_can_hold_shared_lock_together(modules,monkeypatch,tmp_path):
    guard,_=modules
    monkeypatch.setattr(guard,'LOCKS',tmp_path)
    monkeypatch.setattr(guard,'metadata_capacity',lambda:None)
    monkeypatch.setattr(guard,'require_only_registered',lambda gpu:None)
    seen=[]
    monkeypatch.setattr(guard,'register_current',lambda gpu,output:seen.append(output))
    with guard.shared_model_gpu('GPU-test','model1'):
        with guard.shared_model_gpu('GPU-test','model2'):
            assert seen == ['model1','model2']


def test_other_registered_job_uses_its_own_cgroup_without_changing_environment(modules,monkeypatch):
    guard,_=modules
    import runtime_monitor
    original=Path.read_text
    def text(path,*a,**kw):
        if str(path)==f'/proc/{os.getpid()}/cgroup':
            return '1:freezer:/slurm/uid_'+str(os.getuid())+'/job_456/step_batch\n'
        return original(path,*a,**kw)
    monkeypatch.setattr(Path,'read_text',text)
    monkeypatch.setenv('SLURM_JOB_ID','123')
    assert runtime_monitor.capture_process_identity(os.getpid()).get('status') == 'IDENTITY_CHANGED'
    assert runtime_monitor.capture_process_identity(os.getpid(),expected_job='456').get('status') == 'ACTIVE'
    assert os.environ['SLURM_JOB_ID'] == '123'


@pytest.mark.parametrize('free,expected',[(48,(16,48)),(36,(16,32)),(8,(8,8)),(4,(4,4))])
def test_resource_plan_never_claims_or_uses_more_than_free_allocated_cores(modules,free,expected):
    wait=importlib.import_module('cpu_perf_concurrency_wait')
    plan=dict(node='compute-0-22')
    assert wait.allocation(plan,[dict(node=plan['node'],free_cpu=free)]) == expected


def test_resource_observer_exempts_registered_models_and_retains_foreign_guard(modules,monkeypatch):
    guard,_=modules
    import runtime_monitor
    monkeypatch.setattr(guard,'registered_model_pids',lambda gpu:{100})
    def query(argv):
        if '--query-compute-apps=gpu_uuid,pid,used_memory' in argv:
            return 'GPU-test,10,100\nGPU-test,100,100\nGPU-test,999,100\n'
        return 'GPU-test,RTX 5090,driver,32768,32000,768,50\n'
    monkeypatch.setattr(runtime_monitor,'query',query)
    result=runtime_monitor.gpu_observation('GPU-test',own_pids=[10])
    assert [row['pid'] for row in result['foreign_processes']] == [999]


@pytest.mark.parametrize('reused',[False,True])
def test_failed_cohort_cleanup_signals_only_bound_own_process_group(modules,monkeypatch,reused):
    _,suite=modules
    class Child:
        pid=100
        def poll(self):return None
        def wait(self,**kwargs):return 0
    current=identity()
    if reused:current['start_ticks']+=1
    monkeypatch.setattr(suite,'capture_process_identity',lambda pid:current)
    sent=[]
    monkeypatch.setattr(os,'killpg',lambda pid,signum:sent.append((pid,signum)))
    suite.stop_own([Child()],{100:identity()})
    assert len(sent) == (0 if reused else 1)


def test_shared_comparison_allows_only_the_named_background_and_registered_cohort(modules,monkeypatch):
    _,suite=modules
    background={100:identity()}
    active={100,200}
    monkeypatch.setattr(suite,'compute_pids',lambda gpu:active)
    monkeypatch.setattr(suite,'capture_process_identity',lambda pid,**kw:identity())
    monkeypatch.setattr(suite,'registered_model_pids',lambda gpu:{200})
    suite.require_controlled_contexts('GPU-test',background,[200],registered=True)
    active.add(999)
    with pytest.raises(RuntimeError,match='unregistered context'):
        suite.require_controlled_contexts('GPU-test',background,[200],registered=True)
    active.remove(999);active.remove(100)
    with pytest.raises(RuntimeError,match='disappeared'):
        suite.require_controlled_contexts('GPU-test',background,[200],registered=True)


def test_background_pid_reuse_or_command_change_invalidates_comparison(modules,monkeypatch):
    _,suite=modules
    monkeypatch.setattr(suite,'compute_pids',lambda gpu:{100})
    monkeypatch.setattr(suite,'capture_process_identity',lambda pid,**kw:dict(identity(),start_ticks=772))
    with pytest.raises(RuntimeError,match='identity changed'):
        suite.require_controlled_contexts('GPU-test',{100:identity()})


def test_background_registration_requires_the_actual_named_live_job(modules,monkeypatch):
    _,suite=modules
    monkeypatch.setenv('MFM_CPU_BACKGROUND_JOB','123')
    monkeypatch.setenv('MFM_CPU_BACKGROUND_PIDS','100')
    monkeypatch.setattr(suite,'compute_pids',lambda gpu:{100})
    monkeypatch.setattr(suite,'capture_process_identity',lambda pid,**kw:identity())
    assert suite.capture_background('GPU-test') == {100:identity()}
    monkeypatch.setattr(suite,'capture_process_identity',lambda pid,**kw:dict(status='IDENTITY_CHANGED'))
    with pytest.raises(RuntimeError,match='live identified'):
        suite.capture_background('GPU-test')


def test_background_log_is_read_only_and_incomplete_append_is_excluded(modules,monkeypatch,tmp_path):
    _,suite=modules
    path=tmp_path/'background.csv'
    original=b'samples,seconds\n32,1.0\n64,2.0\n96,3.'
    path.write_bytes(original)
    monkeypatch.setenv('MFM_CPU_BACKGROUND_LOSSES',str(path))
    assert suite.background_progress() == 64
    assert path.read_bytes() == original
    path.write_bytes(b'samples,seconds\n')
    assert suite.background_progress() is None
