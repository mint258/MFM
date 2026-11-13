"""CPU-only checks; no MPS daemon, CUDA work or driver settings are launched."""
import importlib
import os
from pathlib import Path
import pytest


@pytest.fixture
def module(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2]/'tools/model_v3'))
    monkeypatch.setenv('SLURM_JOB_ID','123')
    return importlib.import_module('cpu_perf_mps')


def identity(pid=10):
    return dict(status='ACTIVE',pid=pid,uid=os.getuid(),boot_id='boot',start_ticks=3,
        pgid=pid,sid=pid,argv_sha256='original',cgroup='job_123',slurm_job_id='123')


def test_private_namespace_binds_one_gpu_and_current_job(module,tmp_path):
    gpu='GPU-12345678-1234-1234-1234-123456789abc'
    service=module.PrivateMPS(gpu,tmp_path)
    assert service.env['CUDA_VISIBLE_DEVICES']==gpu
    assert service.env['CUDA_MPS_PIPE_DIRECTORY']==f'/tmp/mfm_cpu_mps_{os.getuid()}_123'
    assert service.env['CUDA_MPS_LOG_DIRECTORY']==str(tmp_path/'mps_logs')
    with pytest.raises(ValueError):module.PrivateMPS('0',tmp_path)


@pytest.mark.parametrize('response',['error: server not ready','0','10 11','10\nunknown'])
def test_control_errors_are_not_interpreted_as_no_clients(module,response):
    with pytest.raises(RuntimeError):module.numeric_pids(response)


def test_pid_reuse_cannot_authorize_service_commands(module):
    assert module.same_identity(identity(),identity())
    assert not module.same_identity(identity(),dict(identity(),start_ticks=4))


def test_client_cuda_work_is_drained_before_caller_may_signal(module,tmp_path,monkeypatch):
    service=module.PrivateMPS('GPU-12345678-1234-1234-1234-123456789abc',tmp_path)
    service.server=identity(20)
    monkeypatch.setattr(service,'clients',lambda:{10})
    monkeypatch.setattr(module,'capture_process_identity',lambda pid:identity(pid))
    commands=[]
    monkeypatch.setattr(service,'command',lambda text:(commands.append(text) or '0\n'))
    service.terminate_clients({10:identity()})
    assert commands==['terminate_client 20 10']
    with pytest.raises(RuntimeError,match='Unknown MPS client'):
        service.terminate_clients({})


def test_support_context_exemption_keeps_unknown_gpu_processes_visible(module,tmp_path,monkeypatch):
    service=module.PrivateMPS('GPU-12345678-1234-1234-1234-123456789abc',tmp_path)
    service.server=identity(20)
    monkeypatch.setattr(service,'check',lambda:None)
    monkeypatch.setattr(service,'clients',lambda:{10})
    monkeypatch.setattr(module,'capture_process_identity',lambda pid:identity(pid))
    assert service.validate_gpu_contexts({20,999},{10})=={999}
    service.confirm_clients({10})
    with pytest.raises(RuntimeError,match='not observed'):
        service.confirm_clients({10,11})
    assert service.validate_gpu_contexts({20,10},{10})=={10}
    with pytest.raises(RuntimeError,match='bypassed'):
        service.validate_gpu_contexts({20,11},{10,11})


def test_existing_service_with_unreadable_arguments_is_left_untouched(module,tmp_path,monkeypatch):
    import psutil
    from types import SimpleNamespace
    service=module.PrivateMPS('GPU-12345678-1234-1234-1234-123456789abc',tmp_path)
    monkeypatch.setattr(service,'check',lambda:None)
    monkeypatch.setattr(psutil,'process_iter',lambda attrs:[
        SimpleNamespace(info=dict(pid=999,name='nvidia-cuda-mps',cmdline=None))])
    with pytest.raises(RuntimeError,match='already exists'):
        service.__enter__()
    assert service.process is None


def test_mps_phase_hooks_preserve_unknown_process_rejection_and_restore_defaults(module,monkeypatch):
    from types import SimpleNamespace
    suite=importlib.import_module('cpu_perf_mps_suite')
    original=suite.bench.require_controlled_contexts
    monkeypatch.setattr(suite.bench,'compute_pids',lambda gpu:{10,20,999})
    monkeypatch.setattr(suite.bench,'capture_process_identity',lambda pid,**kw:identity(pid))
    service=SimpleNamespace(validate_gpu_contexts=lambda active,own:set(active)-{20})
    with suite.mps_observer(service):
        with pytest.raises(RuntimeError,match='Unexpected context'):
            suite.bench.require_controlled_contexts('GPU-test',{10:identity()},[30])
    assert suite.bench.require_controlled_contexts is original


def test_mps_clients_are_drained_before_process_cleanup(module,monkeypatch):
    from types import SimpleNamespace
    suite=importlib.import_module('cpu_perf_mps_suite')
    calls=[]
    monkeypatch.setattr(suite.bench,'stop_own',lambda children,ids:calls.append('signal'))
    service=SimpleNamespace(terminate_clients=lambda ids:calls.append('drain'))
    with suite.mps_observer(service):
        suite.bench.stop_own([SimpleNamespace(poll=lambda:None)],{10:identity()})
    assert calls==['drain','signal']


def test_confirmed_client_exit_race_is_allowed_but_pid_reuse_is_rejected(module,tmp_path,monkeypatch):
    service=module.PrivateMPS('GPU-12345678-1234-1234-1234-123456789abc',tmp_path)
    service.server=identity(20)
    clients={10};current=identity(10)
    monkeypatch.setattr(service,'check',lambda:None)
    monkeypatch.setattr(service,'clients',lambda:set(clients))
    monkeypatch.setattr(module,'capture_process_identity',lambda pid:identity(20) if pid==20 else current)
    assert service.validate_gpu_contexts({20,10},{10})=={10}
    clients.clear()
    assert service.validate_gpu_contexts({20,10},{10})=={10}
    current=dict(status='GONE',pid=10)
    assert service.validate_gpu_contexts({20,10},{10})==set()
    clients.add(10)
    assert service.validate_gpu_contexts({20,10},{10})==set()
    clients.clear()
    current=dict(identity(10),start_ticks=999)
    with pytest.raises(RuntimeError,match='identity changed'):
        service.validate_gpu_contexts({20,10},{10})


def test_partial_exit_observation_repolls_same_kernel_lifetime(module,tmp_path,monkeypatch):
    service=module.PrivateMPS('GPU-12345678-1234-1234-1234-123456789abc',tmp_path)
    service.client_identities[10]=identity(10)
    observed=[]
    monkeypatch.setattr(module.time,'sleep',lambda seconds:None)
    def capture(pid):
        observed.append(pid)
        return dict(status='GONE',pid=pid)
    monkeypatch.setattr(module,'capture_process_identity',capture)
    assert service.verified_exit(10,dict(status='EXITING',pid=10,start_ticks=3))
    assert observed==[10]
    assert not service.verified_exit(10,dict(status='EXITING',pid=10,start_ticks=4))
