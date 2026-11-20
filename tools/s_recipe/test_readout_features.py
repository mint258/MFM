"""Only new closed-feature transport; never run an encoder or a probe here."""
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch

import readouts
from readouts import ensure_features, release_closed_feature_cache


def evaluator(producer):
    def path(c, name):
        return Path(c['features'][name]) if isinstance(c['features'], dict) else Path(c['features'])/(name+'.pt')
    return SimpleNamespace(feature_path=path, produce_missing_features=producer)


def test_one_closed_feature_production_serves_later_consumers(tmp_path):
    calls = []
    def produce(c, dataset, view):
        calls.append(dataset)
        torch.save({'h': torch.arange(4)}, c['features'][dataset])
    e = evaluator(produce)
    configuration = dict(features=str(tmp_path))
    first = ensure_features(e, configuration, 'dataset', None)
    second = ensure_features(e, configuration, 'dataset', None)
    assert first == second
    assert calls == ['dataset']
    assert torch.equal(torch.load(first, weights_only=True)['h'], torch.arange(4))


def test_failed_feature_write_is_preserved_and_not_consumed_as_closed(tmp_path):
    def fail(c, dataset, view):
        Path(c['features'][dataset]).write_bytes(b'incomplete')
        raise OSError('simulated interrupted serialization')
    configuration = dict(features=str(tmp_path))
    with pytest.raises(OSError, match='interrupted'):
        ensure_features(evaluator(fail), configuration, 'dataset', None)
    assert not (tmp_path/'dataset.pt').exists()
    partials = list(tmp_path.glob('*.writing.*'))
    assert len(partials) == 1
    def succeed(c, dataset, view):
        torch.save({'h': torch.ones(2)}, c['features'][dataset])
    path = ensure_features(evaluator(succeed), configuration, 'dataset', None)
    assert path.is_file()
    assert partials[0].read_bytes() == b'incomplete'


def test_completed_scratch_cleanup_retains_failed_partials(tmp_path, monkeypatch):
    monkeypatch.setattr(readouts, 'CONTROL', tmp_path)
    directory = tmp_path/'scratch/readout_features/run/3000000'
    directory.mkdir(parents=True)
    (directory/'qm9.pt').write_bytes(b'closed H')
    partial = directory/'qm9.pt.writing.failed'
    partial.write_bytes(b'partial')
    result = release_closed_feature_cache(dict(run='run', evaluation_samples=[3000000]))
    assert result['files'] == 1
    assert not (directory/'qm9.pt').exists()
    assert partial.read_bytes() == b'partial'


def test_feature_cleanup_rejects_a_run_outside_owned_scratch(tmp_path, monkeypatch):
    monkeypatch.setattr(readouts, 'CONTROL', tmp_path)
    with pytest.raises(ValueError, match='directly inside S scratch'):
        release_closed_feature_cache(dict(run='../other', evaluation_samples=[3000000]))


def test_feature_cleanup_rejects_a_relocated_scratch_root(tmp_path, monkeypatch):
    control, outside = tmp_path/'control', tmp_path/'outside'
    control.mkdir()
    outside.mkdir()
    (control/'scratch').symlink_to(outside, target_is_directory=True)
    monkeypatch.setattr(readouts, 'CONTROL', control)
    with pytest.raises(ValueError, match='base escaped S scratch'):
        release_closed_feature_cache(dict(run='run', evaluation_samples=[3000000]))
