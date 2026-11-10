"""Actual CSV clock/cadence behavior, without training or network calls."""
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

spec = importlib.util.spec_from_file_location('v2_wandb_tracking',
    Path(__file__).absolute().parents[2] / 'tools/model_v3/v2_wandb_tracking.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def test_partial_producer_line_is_not_consumed(tmp_path):
    path = tmp_path / 'losses.csv'
    path.write_text('samples,updates,total\n99968,3124,0.4\n100000,3125,')
    tail = m.CsvTail(path)
    assert [r['samples'] for r in tail.rows()] == [99968]
    with path.open('a') as stream:
        stream.write('0.3\n')
    assert list(tail.rows()) == [dict(samples=100000, updates=3125, total=.3)]
    assert list(tail.rows()) == []


def test_batch64_crosses_boundary_without_rewriting_clock():
    assert m.boundaries(99968, 100032) == [100000]
    assert m.boundaries(100032, 100096) == []
    assert m.boundaries(199968, 200000) == [200000]
    with pytest.raises(ValueError):
        m.boundaries(100000, 99968)


def test_resumed_execution_excludes_parent_work_and_filters_unknown_fields():
    row = dict(samples=500000, updates=15625, P=.3, total=.3, lr=.0003,
        seconds=20000., preclip_norm=2., arbitrary_secret='never a metric')
    payload = m.metrics(row, 480000, 19000., True)
    assert payload['samples/execution'] == 20000
    assert payload['time/samples_per_second'] == 20
    assert payload['history/imported'] is True
    assert 'arbitrary_secret' not in payload
    assert m.boundaries(480000, 500000) == [500000]


def test_unknown_scheduler_observation_is_not_terminal(monkeypatch):
    class Result:
        stdout = ''
    monkeypatch.setattr(m.subprocess, 'run', lambda *a, **k: Result())
    assert m.job_state(dict(job=123)) == 'UNKNOWN'
    assert m.job_state(dict(job=123, terminal_state='CANCELLED')) == 'CANCELLED'


def test_worker_commits_real_clock_and_emits_one_idempotent_boundary(tmp_path, monkeypatch):
    output = tmp_path / 'training'
    output.mkdir()
    (output / 'configuration.json').write_text(json.dumps(dict(seed=0, resume='parent.pt')))
    (output / 'execution.json').write_text(json.dumps(dict(initial_samples=99968,
        elapsed_seconds_prior=12.)))
    (output / 'losses.csv').write_text('samples,updates,total,seconds\n100000,3125,0.3,14\n')
    manifest = tmp_path / 'manifest.json'
    tracking = tmp_path / 'tracking'
    manifest.write_text(json.dumps(dict(project='synthetic', mode='offline', tracking_root=str(tracking),
        runs=[dict(job=123, output=str(output), name='test', group='test', node='test',
            gpu='test', source_revision='test', terminal_state='CANCELLED')])))
    calls = []
    class Run:
        id, url, disabled = 'test', None, False
        def __init__(self):
            self.summary = {}
        def log(self, payload, **kwargs):
            calls.append(('log', payload, kwargs))
        def save(self, *args, **kwargs):
            calls.append(('save', args, kwargs))
        def finish(self, **kwargs):
            calls.append(('finish', kwargs))
    monkeypatch.setitem(sys.modules, 'wandb', SimpleNamespace(
        Settings=lambda **kwargs: kwargs, init=lambda **kwargs: Run()))
    m.worker(manifest, 123)
    log = next(row for row in calls if row[0] == 'log')
    assert log[2] == dict(step=100000, commit=True)
    snapshot = json.loads((tracking / '123/snapshots/100000.json').read_text())
    assert snapshot['execution_samples'] == 32
    assert snapshot['imported_history'] is True
    assert snapshot['synchronization'] == 'OFFLINE_UNSYNCED'
    assert calls[-1] == ('finish', dict(exit_code=1))
    count = len(calls)
    m.worker(manifest, 123)
    assert len(calls) == count


def test_publication_exports_snapshots_not_sdk_or_weights(tmp_path):
    root = tmp_path / 'tracking'
    (root / '1/snapshots').mkdir(parents=True)
    (root / '1/snapshots/100000.json').write_text('{"actual_samples":100000}')
    (root / '1/private.wandb').write_text('private')
    destination = tmp_path / 'publication.json'
    m.export_snapshots(dict(tracking_root=str(root), publication_pending=str(destination), mode='offline'))
    result = json.loads(destination.read_text())
    assert result['records'] == [dict(actual_samples=100000)]
    assert result['status'] == 'OFFLINE_UNSYNCED'


def test_launch_registration_appends_once_and_does_not_guess_native_stage(tmp_path, monkeypatch):
    repo = tmp_path / 'repo'
    (repo / '.git/refs/heads').mkdir(parents=True)
    (repo / '.git/HEAD').write_text('ref: refs/heads/model-v3\n')
    (repo / '.git/refs/heads/model-v3').write_text('actual-source-revision\n')
    monkeypatch.setattr(m, '__file__', str(repo / 'tools/model_v3/runner.py'))
    manifest = tmp_path / 'manifest.json'
    manifest.write_text(json.dumps(dict(runs=[dict(job=1, terminal_state='FAILED')])))
    config = tmp_path / 'native.json'
    config.write_text(json.dumps(dict(output='/owned/M4_S', distance_bias='C1-0', seed=1)))
    for _ in range(2):
        m.register(manifest, config, job=2, node='actual-node', gpu='actual-gpu', mode='native_s')
    rows = json.loads(manifest.read_text())['runs']
    assert len(rows) == 2 and rows[0] == dict(job=1, terminal_state='FAILED')
    assert rows[1]['source_revision'] == 'actual-source-revision'
    assert rows[1]['group'].startswith('stageunspecified_S_')


def test_publication_only_materializes_unpublished_actual_boundaries(tmp_path):
    pending = tmp_path / 'pending.json'
    record = dict(job=23, boundary_samples=200000, actual_samples=200000,
        synchronization='OFFLINE_UNSYNCED', metrics={'loss/P': .3})
    pending.write_text(json.dumps(dict(records=[dict(job=23, boundary_samples=100000), record])))
    repo = tmp_path / 'repo'
    entries = m.prepare_publication(dict(publication_pending=str(pending)),
        dict(published_keys=['23:100000']), repo)
    assert len(entries) == 1
    assert entries[0]['path'] == 'results/model_v3_wandb/points/23/200000.json'
    assert json.loads(entries[0]['content']) == record
    assert json.loads((repo / entries[0]['path']).read_text()) == record
    assert not (repo / 'results/model_v3_wandb/points/23/100000.json').exists()


def test_publication_rejects_non_numeric_output_path(tmp_path):
    pending = tmp_path / 'pending.json'
    pending.write_text(json.dumps(dict(records=[dict(job='../outside', boundary_samples=100000)])))
    with pytest.raises(ValueError, match='numeric'):
        m.prepare_publication(dict(publication_pending=str(pending)), {}, tmp_path / 'repo')


def test_new_publication_attaches_observation_with_its_own_clock(tmp_path):
    root = tmp_path / 'tracking'
    directory = root / 'diagnostics/23'
    directory.mkdir(parents=True)
    observation = dict(job=23, observed_at=10., metrics={'gpu/power_watts': 100., 'samples/cumulative': 100032})
    (directory / 'latest.json').write_text(json.dumps(observation))
    pending = tmp_path / 'pending.json'
    pending.write_text(json.dumps(dict(records=[dict(job=23, boundary_samples=100000, actual_samples=100000)])))
    entries = m.prepare_publication(dict(publication_pending=str(pending), tracking_root=str(root)), {}, tmp_path / 'repo')
    record = json.loads(entries[0]['content'])
    assert record['actual_samples'] == 100000
    assert record['training_diagnostics'] == observation
    assert 'own sample/time clocks' in record['diagnostic_alignment']
