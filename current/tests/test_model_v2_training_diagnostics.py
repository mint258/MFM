"""Telemetry identity, counter rates and real-update loss-window boundaries."""
import importlib.util
import math
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('v2_training_diagnostics',
    Path(__file__).absolute().parents[2] / 'tools/model_v3/v2_training_diagnostics.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def test_resumed_window_contains_exactly_1000_new_updates():
    window = m.UpdateMeans()
    for update in range(17001, 18000):
        assert window.add(dict(updates=update, samples=update*32, total=update)) is None
    result = window.add(dict(updates=18000, samples=576000, total=18000))
    assert result['first_update'] == 17001 and result['last_update'] == 18000
    assert result['updates'] == 1000 and result['partial'] is False
    assert result['means']['total'] == 17500.5
    assert result['counts']['total'] == 1000
    assert window.summary() is None


def test_missing_components_have_their_own_counts_and_partial_is_explicit():
    window = m.UpdateMeans(3)
    window.add(dict(updates=1, samples=32, total=2., P=1., _imported=True))
    window.add(dict(updates=2, samples=64, total=4., P=math.nan))
    result = window.summary()
    assert result['partial'] is True and result['updates'] == 2
    assert result['means'] == dict(P=1., total=3.)
    assert result['counts'] == dict(P=1, total=2)
    assert result['imported_records'] == 1


@pytest.mark.parametrize('next_update', [1, 3])
def test_gap_or_rewind_cannot_be_silently_averaged(next_update):
    window = m.UpdateMeans()
    window.add(dict(updates=1, samples=32, total=1.))
    with pytest.raises(ValueError, match='consecutive'):
        window.add(dict(updates=next_update, samples=64, total=1.))


def test_gpu_uuid_and_process_ownership_are_independent_of_gpu_index():
    metrics, pids = m.gpu_observation('GPU-other,99,50,100,200,300,60,1400,2000\n'
        'GPU-target,20,30,1200,32000,140,40,2500,13000\n',
        'GPU-other,7,100\nGPU-target,8,1100\nGPU-target,9,100\n', 'GPU-target', lambda pid: pid == 8)
    assert pids == [8] and metrics['gpu/power_watts'] == 140
    assert metrics['gpu/memory_used_mib'] == 1200
    assert metrics['gpu/own_process_memory_mib'] == 1100
    assert metrics['gpu/other_process_count'] == 1


def test_unavailable_sensor_is_missing_not_zero_and_wrong_card_rejected():
    metrics, _ = m.gpu_observation('GPU-x,0,0,1,2,N/A,30,40,50', '', 'GPU-x', lambda pid: True)
    assert 'gpu/power_watts' not in metrics
    with pytest.raises(ValueError, match='UUID'):
        m.gpu_observation('GPU-other,0,0,1,2,3,30,40,50', '', 'GPU-x', lambda pid: True)


def test_uid_and_slurm_job_both_required(tmp_path):
    process = tmp_path / '12'
    process.mkdir()
    (process / 'status').write_text('Uid:\t1278\t1278\t1278\t1278\n')
    (process / 'cgroup').write_text('1:freezer:/slurm/uid_1278/job_123/step_batch\n')
    assert m.owns_job(12, 123, proc=tmp_path)
    assert not m.owns_job(12, 12, proc=tmp_path)
    (process / 'status').write_text('Uid:\t999\t999\t999\t999\n')
    assert not m.owns_job(12, 123, proc=tmp_path)


def observation(timestamp, start=1, cpu=0., read=0, available=True):
    return dict(available=available, observed_at=timestamp, gpu='GPU-x',
        metrics={'gpu/power_watts': 100.}, processes=[dict(pid=12, start_ticks=start,
            cpu_seconds=cpu, read_bytes=read, write_bytes=0, major_faults=0)])


def test_rates_use_interval_and_pid_birth_and_skip_unknown_or_long_energy_gaps():
    old, new = observation(1), observation(31, cpu=15., read=300)
    rates = m.rates(old, new)
    assert rates['process/main_cpu_percent'] == 50
    assert rates['io/main_read_bytes_per_second'] == 10
    assert rates['gpu/observed_interval_energy_joules'] == 3000
    assert 'process/main_cpu_percent' not in m.rates(old, observation(31, start=2, cpu=1.))
    assert m.rates(old, observation(31, available=False)) == {}
    assert m.rates(old, observation(0)) == {}
    assert 'gpu/observed_interval_energy_joules' not in m.rates(old, observation(100))
