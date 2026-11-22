"""CPU checks of new deadline, process identity and real worker cleanup."""
import multiprocessing
import os
import signal
import subprocess
import sys
import time
import pytest
import lifecycle_20261122 as life


def _worker_identity(_):
    return os.getpid()


@pytest.mark.parametrize('fails', [False, True])
def test_guarded_entry_preserves_configuration_and_joins_on_exception(tmp_path, monkeypatch, fails):
    import json
    from types import SimpleNamespace
    import dispatch
    import train_guarded_20261122 as entry
    monkeypatch.setattr(dispatch, 'gate', lambda: None)
    monkeypatch.setattr(entry, 'ROOT', tmp_path)
    monkeypatch.setattr(entry, 'CONTROL', tmp_path)
    monkeypatch.setattr(entry, 'capacity', lambda: None)
    monkeypatch.setattr(entry, 'query_gpu', lambda uuid: [uuid, 'fixture', '0', '49140', '0', '0'])
    monkeypatch.setenv('SLURM_JOB_ID', '4530001')
    monkeypatch.setenv('SLURM_JOB_END_TIME', str(int(time.time()+4000)))
    monkeypatch.setenv('CUDA_VISIBLE_DEVICES', 'fixture-uuid')
    (tmp_path/'docs/phase1/evidence/stage46_shared_gpu_launch/.own_gpu_uuid_locks').mkdir(parents=True)
    c = dict(run='S_R1_s0_3M', arm='S-R1', seed=0, samples=3000000,
             node=entry.socket.gethostname().split('.')[0], gpu_uuid='fixture-uuid',
             minimum_free_gpu_mib=30720, output=str(tmp_path/'output'),
             batch_size=32, microbatch_size=32)
    before = dict(c)
    def fake_train(configuration):
        assert configuration == before
        assert life.active().phase == 'preparing'
        if fails:
            raise ValueError('fixture training exception')
        return {'status': 'HANDOFF_SAVED'}
    monkeypatch.setitem(sys.modules, 's_training_lifecycle_20261122', SimpleNamespace(train=fake_train))
    if fails:
        with pytest.raises(ValueError, match='fixture training exception'):
            entry.run(c, scheduler_record=None)
    else:
        assert entry.run(c, scheduler_record=None)['status'] == 'HANDOFF_SAVED'
    assert c == before
    state = json.loads((tmp_path/'S_R1_s0_3M_guarded_4530001.json').read_text())
    assert state['owned_descendants_exited'] and state['observer_joined']
    assert state['status'] == ('FAILED' if fails else 'HANDOFF_SAVED')


def test_deadline_rejects_unlimited_or_missing_real_end():
    for end in ('', 'UNLIMITED', 'infinite'):
        with pytest.raises(ValueError):
            life.Guard.from_slurm(environment={'SLURM_JOB_ID': '123', 'SLURM_JOB_END_TIME': end})
    with pytest.raises(ValueError):
        life.Guard.from_slurm(environment={'SLURM_JOB_END_TIME': str(int(time.time()+4000))})
    with pytest.raises(ValueError):
        life.Guard(time.time()+100, 180)


def test_closing_window_requests_checkpoint_before_hard_end():
    clock = [1000.]
    guard = life.Guard(2000., 180, now=lambda: clock[0])
    assert not guard.stopping()
    clock[0] = 1820.
    assert guard.stopping()
    assert guard.reason == 'closing_window'
    assert clock[0] < guard.end_epoch


def test_controller_deadline_binds_actual_job_uid_and_node():
    env = {'SLURM_JOB_ID': '4530001', 'SLURMD_NODENAME': 'compute-0-11'}
    record = dict(schema='S_REAL_SLURM_LIMIT_V1', source='scontrol_show_job_utc',
                  job_id=4530001, uid=os.getuid(), node='compute-0-11',
                  observed_time=time.time(), time_limit_seconds=600,
                  anchor_epoch=time.time(), deadline_basis='actual_start')
    guard = life.Guard.from_slurm(180, environment=env, scheduler_record=record)
    assert guard.end_epoch == record['anchor_epoch']+600
    for changed in (dict(job_id=4530002), dict(uid=os.getuid()+1),
                    dict(node='compute-0-20'), dict(observed_time=time.time()-61)):
        with pytest.raises(ValueError):
            life.Guard.from_slurm(180, environment=env, scheduler_record=dict(record, **changed))


def test_signal_cannot_interrupt_half_optimizer_update():
    guard = life.Guard(time.time()+4000)
    guard.phase = 'optimizer_update'
    guard._handle(signal.SIGTERM, None)
    assert guard.stopping()
    guard.phase = 'waiting_batch'
    with pytest.raises(life.StopAtBoundary):
        guard._handle(signal.SIGTERM, None)


def test_submit_lower_bound_survives_queue_and_still_reserves_exit():
    env = {'SLURM_JOB_ID': '4530001', 'SLURMD_NODENAME': 'compute-0-11'}
    record = dict(schema='S_REAL_SLURM_LIMIT_V1', source='scontrol_show_job_utc',
                  job_id=4530001, uid=os.getuid(), node='compute-0-11',
                  observed_time=time.time()-120, time_limit_seconds=600,
                  anchor_epoch=time.time()-120, deadline_basis='submit_lower_bound')
    guard = life.Guard.from_slurm(180, environment=env, scheduler_record=record)
    assert guard.end_epoch == record['anchor_epoch']+600-5
    record['anchor_epoch'] = time.time()-500
    with pytest.raises(ValueError):
        life.Guard.from_slurm(180, environment=env, scheduler_record=record)


def test_already_requested_stop_starts_no_new_input_unit():
    guard = life.Guard(time.time()+4000)
    guard.request('closing_window')
    with pytest.raises(life.StopAtBoundary):
        guard.await_next()


def test_checkpoint_request_retains_run_and_actual_job(monkeypatch):
    monkeypatch.setenv('SLURM_JOB_ID', '4530001')
    guard = life.Guard(time.time()+4000)
    guard.request('migration')
    first = guard.handoff({'run': 'S_R1_s0_3M'})
    assert first == guard.handoff({'run': 'S_R1_s0_3M'})
    assert first['job_id'] == 4530001
    assert first['run'] == 'S_R1_s0_3M'
    assert first['action'] == 'SAVE_AND_EXIT'


def test_identity_reuse_or_foreign_uid_never_receives_signal(monkeypatch):
    saved = life.Identity(912345, os.getuid(), 100, os.getpid(), 'S')
    calls = []
    monkeypatch.setattr(life.os, 'kill', lambda *args: calls.append(args))
    for current in (life.Identity(saved.pid, saved.uid, 101, saved.ppid, 'S'),
                    life.Identity(saved.pid, saved.uid+1, 100, saved.ppid, 'S')):
        monkeypatch.setattr(life, 'identity', lambda pid, value=current: value)
        assert life.terminate_once(saved) == 'already_exited'
    assert calls == []


def test_d_state_is_reported_without_kill(monkeypatch):
    saved = life.Identity(912345, os.getuid(), 100, os.getpid(), 'D')
    monkeypatch.setattr(life, 'identity', lambda pid: saved)
    monkeypatch.setattr(life.os, 'kill', lambda *args: pytest.fail('D process must not be killed'))
    assert life.terminate_once(saved) == 'uninterruptible_requires_administrator'


def test_managed_spawn_pool_reaps_real_workers():
    with life.ManagedPool(2, mp_context=multiprocessing.get_context('spawn')) as pool:
        pids = set(pool.map(_worker_identity, range(6)))
        records = [life.identity(pid) for pid in pids]
    assert records
    assert all(not life.same_process(saved, life.identity(saved.pid)) for saved in records)


def test_cleanup_verifies_real_child_is_gone():
    child = subprocess.Popen([sys.executable, '-B', '-c', 'import time;time.sleep(5)'])
    saved = life.identity(child.pid)
    try:
        life.close_children(3)
        assert not life.same_process(saved, life.identity(saved.pid))
    finally:
        child.wait(timeout=6)


def test_guard_restores_signal_handlers_and_joins_timer():
    before = {sig: signal.getsignal(sig) for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGUSR1)}
    with life.Guard(time.time()+4000) as guard:
        assert life.active() is guard
    assert not guard._watcher.is_alive()
    assert all(signal.getsignal(sig) == handler for sig, handler in before.items())
    with pytest.raises(RuntimeError):
        life.active()


def test_pause_keeps_committed_clock_and_reuses_closed_checkpoint(tmp_path, monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setenv('SLURM_JOB_ID', '4530001')
    clock = SimpleNamespace(samples_consumed=1000000,
                            state_dict=lambda: {'samples_consumed': 1000000, 'optimizer_updates': 31250})
    calls = []
    def publish(payload, path):
        calls.append(payload)
        path.write_bytes(b'closed-unit-fixture')
    def finish(configuration, request, path, state):
        return {'request': request, 'checkpoint': str(path), 'clock': state}
    with life.Guard(time.time()+4000) as guard:
        guard.request('closing_window')
        configuration = {'run': 'S_R1_s0_3M', 'output': str(tmp_path)}
        first = life.pause_checkpoint(configuration, clock, lambda: {'committed': True}, publish, finish)
        second = life.pause_checkpoint(configuration, clock,
                                       lambda: pytest.fail('Closed state must not be republished'), publish, finish)
    assert calls == [{'committed': True}]
    assert first == second
    assert first['clock']['optimizer_updates'] == 31250


def test_pause_does_not_acknowledge_failed_save(tmp_path, monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setenv('SLURM_JOB_ID', '4530001')
    clock = SimpleNamespace(samples_consumed=32, state_dict=lambda: {'samples_consumed': 32})
    def publish(payload, path):
        raise OSError('unit-fixture storage failure')
    with life.Guard(time.time()+4000) as guard:
        guard.request('closing_window')
        with pytest.raises(OSError):
            life.pause_checkpoint({'run': 'S_R1_s0_3M', 'output': str(tmp_path)}, clock,
                                  lambda: {'committed': True}, publish,
                                  lambda *args: pytest.fail('Failed save must not be acknowledged'))
