"""A disk recovery can continue only its unchanged allocation after fresh admission."""
import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('v2_recover_quota_pause',
    Path(__file__).absolute().parents[2] / 'tools/model_v3/v2_recover_quota_pause.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


ENTRY = dict(job=42, node='compute-0-21', restarts=0, mode='v31', configuration='/cfg.json',
             gpu='GPU-test', python='/python', output='/output')
GUARD = dict(status='DISK_PAUSED', jobs=[42], node='compute-0-21')


def observation(state='STOPPED'):
    return (f"JobId=42 UserId=zixiao(1278) JobState={state} Restarts=0 NodeList=compute-0-21 "
            f"Command={m.WRAPPER} v31 /cfg.json GPU-test /python WorkDir={m.REPO}")


@pytest.mark.parametrize('old,new', [('zixiao(1278)', 'other(1283)'),
    ('NodeList=compute-0-21', 'NodeList=compute-0-20'), ('Restarts=0', 'Restarts=1'),
    ('GPU-test', 'GPU-other')])
def test_changed_or_foreign_allocation_never_reaches_admission(old, new):
    calls = []
    with pytest.raises(ValueError):
        m.recover_one(ENTRY, observation().replace(old, new), GUARD,
            admit=lambda entry: calls.append('admit'), observe_again=lambda entry: observation(),
            send_cont=lambda entry: calls.append('CONT'))
    assert calls == []


def test_unknown_capacity_keeps_original_job_paused():
    signals = []
    def unavailable(entry):
        raise OSError('Actual quota is unknown')
    with pytest.raises(OSError):
        m.recover_one(ENTRY, observation(), GUARD, admit=unavailable,
            observe_again=lambda entry: observation(), send_cont=signals.append)
    assert signals == []


def test_changed_state_after_admission_does_not_receive_a_signal():
    signals = []
    result = m.recover_one(ENTRY, observation(), GUARD, admit=lambda entry: {'passed': True},
        observe_again=lambda entry: observation('RUNNING'), send_cont=signals.append)
    assert result['status'] == 'STATE_CHANGED_NO_SIGNAL' and signals == []


def test_guard_from_another_job_cannot_authorize_a_resume():
    calls = []
    with pytest.raises(ValueError, match='another allocation'):
        m.recover_one(ENTRY, observation(), dict(GUARD, jobs=[43]), admit=calls.append,
            observe_again=lambda entry: observation(), send_cont=calls.append)
    assert calls == []


def test_original_paused_job_is_admitted_then_rechecked_before_cont():
    calls = []
    def admission(entry):
        calls.append('actual-capacity')
        return {'passed': True}
    def reread(entry):
        calls.append('controller')
        return observation()
    result = m.recover_one(ENTRY, observation(), GUARD, admit=admission,
        observe_again=reread, send_cont=lambda entry: calls.append(('CONT', entry['job'])))
    assert calls == ['actual-capacity', 'controller', ('CONT', 42)]
    assert result['status'] == 'CONT_SENT'


@pytest.mark.parametrize('state,guard', [('RUNNING', GUARD), ('STOPPED', {})])
def test_running_or_manually_stopped_job_is_left_alone(state, guard):
    calls = []
    m.recover_one(ENTRY, observation(state), guard, admit=calls.append,
        observe_again=lambda entry: observation(), send_cont=calls.append)
    assert calls == []
