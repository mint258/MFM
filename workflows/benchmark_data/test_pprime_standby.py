"""A reserved replacement must never race the live writer or extend Slurm time."""
from datetime import datetime, timezone
import os
import subprocess
from unittest.mock import patch

import pytest

from workflows.benchmark_data.pprime_standby import main, native_job, previous_closed, remaining_wall, validate_acceptance


def test_unaccepted_allocated_main_exits_without_starting_producer(tmp_path, monkeypatch):
    monkeypatch.setenv('SLURM_JOB_ID', '20')
    own = dict(JobId='20', NodeList='compute-0-18', Partition='cpu', JobState='RUNNING',
               UserId='zixiao(' + str(os.getuid()) + ')', NumCPUs='16', **{'CPUs/Task': '16'})
    argv = ['standby', '--root', str(tmp_path / 'data'), '--control', str(tmp_path),
            '--quota-snapshot', str(tmp_path / 'quota.json'), '--previous-job', '10']
    with patch('sys.argv', argv), patch('socket.gethostname', return_value='compute-0-18'), \
            patch('workflows.benchmark_data.pprime_standby.native_job', return_value=own), \
            patch('workflows.benchmark_data.pprime_standby.remaining_wall', return_value=50000), \
            patch('workflows.benchmark_data.pprime_tmpfs_queue.capacity') as capacity, \
            patch('workflows.benchmark_data.shared_access.completed_evidence') as completed, \
            patch('time.monotonic', side_effect=[0, 0, 301]), patch('time.sleep'), \
            patch('os.execv') as execute:
        main()
    capacity.assert_called_once()
    completed.assert_not_called()
    execute.assert_not_called()


def test_transient_native_observation_waits_for_the_same_job():
    with patch('subprocess.check_output', side_effect=[subprocess.TimeoutExpired(['scontrol'], 30),
                                                       'JobId=10 JobState=RUNNING']) as native, \
            patch('time.sleep') as sleep:
        assert native_job('10')['JobState'] == 'RUNNING'
    assert native.call_count == 2
    assert all(call.args[0] == ['scontrol', 'show', 'job', '10', '-o'] for call in native.call_args_list)
    sleep.assert_called_once_with(5)


def test_unaccepted_metadata_observation_has_a_reservation_deadline():
    with patch('time.monotonic', return_value=301), patch('subprocess.check_output') as native:
        with pytest.raises(TimeoutError, match='reservation window expired'):
            native_job('10', expires=300)
    native.assert_not_called()


def test_acceptance_binds_allocation_process_and_fallback():
    identity = dict(job='20', previous_job='10', node='compute-0-18', uid=1278,
                    pid=500, start_ticks='900', root='/shared/B0', workers=16)
    accepted = dict(identity, previous_parent_sigterm_verified=True, followup_requires_both_jobs=True)
    validate_acceptance(accepted, identity)
    for key in identity:
        with pytest.raises(ValueError, match='identity differs'):
            validate_acceptance(dict(accepted, **{key: 'different'}), identity)
    for key in ('previous_parent_sigterm_verified', 'followup_requires_both_jobs'):
        with pytest.raises(ValueError):
            validate_acceptance(dict(accepted, **{key: False}), identity)


@pytest.mark.parametrize('state', ['PENDING', 'RUNNING', 'COMPLETING'])
def test_no_handoff_while_previous_is_live(state):
    assert not previous_closed({'JobState': state}, {'producer_job': '10'}, None, 10)


def test_handoff_requires_native_c0_closed_writers_and_zero_intent():
    previous = {'JobState': 'COMPLETED', 'ExitCode': '0:0'}
    access = {'producer_job': '10', 'writers_closed': True}
    report = {'job': '10', 'states': {'PENDING': 100, 'INTENT': 0}}
    assert previous_closed(previous, access, report, 10)
    assert not previous_closed(previous, dict(access, writers_closed=False), report, 10)
    assert not previous_closed(previous, access, None, 10)
    with pytest.raises(ValueError, match='not native'):
        previous_closed(dict(previous, ExitCode='1:0'), access, report, 10)
    with pytest.raises(ValueError, match='identity changed'):
        previous_closed(previous, dict(access, producer_job='11'), report, 10)
    with pytest.raises(ValueError, match='INTENT'):
        previous_closed(previous, access, dict(report, states={'INTENT': 1}), 10)


def test_wall_time_uses_actual_remaining_allocation_with_margin():
    end = datetime(2026, 11, 20, 12, tzinfo=timezone.utc)
    job = {'EndTime': end.isoformat()}
    assert remaining_wall(job, end.timestamp() - 50000) == 49940
    assert remaining_wall(job, end.timestamp() - 30) == 0
    assert remaining_wall(job, end.timestamp() + 10) == 0
