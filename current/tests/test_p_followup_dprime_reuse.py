"""A later seed must reuse its own closed seed0 pair, never a different run."""
import importlib.util
import json
from pathlib import Path
import sys

import pytest


@pytest.fixture
def comparison(tmp_path, monkeypatch):
    tools = Path(__file__).resolve().parents[2] / 'tools/p_followup'
    monkeypatch.syspath_prepend(str(tools))
    spec = importlib.util.spec_from_file_location('dprime_reuse_under_test', tools / 'compare_dprime.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, 'REPO', tmp_path)
    monkeypatch.setattr(module, 'guard', lambda **kwargs: None)
    def save(path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))
    monkeypatch.setattr(module, 'save', save)
    (tmp_path / 'docs/p_followup').mkdir(parents=True)
    configs = tmp_path / 'configs/p_followup'
    configs.mkdir(parents=True)
    paths = [configs / name for name in (
        'Dprime_M2_seed0_continued.json', 'M2_reference.json', 'candidate1.json', 'baseline1.json')]
    values = [dict(seed=seed, samples=3000000, run=run, output=str(tmp_path / run))
              for seed, run in ((0, 'candidate0'), (0, 'baseline0'), (1, 'candidate1'), (1, 'baseline1'))]
    for path, value in zip(paths, values):
        save(path, value)
    def row(delta, lo, hi):
        return dict(delta=delta, ci95=[lo, hi], paired_draws=1000, included_tasks=['task'])
    old_pair = dict(candidate_configuration=str(paths[0]), baseline_configuration=str(paths[1]),
        candidate_run='candidate0', baseline_run='baseline0',
        candidate_scores=str(tmp_path / 'candidate0/readout/scores.json'),
        baseline_scores=str(tmp_path / 'baseline0/readout/scores.json'), baseline_R3=.468,
        comparisons=dict(R1=row(-.106, -.12, -.09), R3=row(-.045, -.056, -.034)))
    result = tmp_path / 'results/p_followup/Dprime_M2_comparison.json'
    previous = dict(status='SEED1_REQUIRED', samples=3000000, comparisons={'0': old_pair})
    save(result, previous)
    monkeypatch.setattr(sys, 'argv', ['compare', '--candidate-seed1', str(paths[2]),
                                    '--baseline-seed1', str(paths[3])])
    return module, result, previous, old_pair, row


def test_combining_seed1_does_not_read_or_recompute_closed_seed0(comparison, monkeypatch):
    module, result, previous, old_pair, row = comparison
    seen = []
    def scores(configuration, seed):
        assert seed == 1, 'Closed seed0 scores must not be reread'
        seen.append(configuration['run'])
        return {name: dict(mean_normalized_improvement=.48, name=name) for name in ('R1', 'R3')}
    monkeypatch.setattr(module, 'scores', scores)
    monkeypatch.setattr(module, 'paired_ci', lambda a, b: row(-.04, -.05, -.03))
    module.main()
    actual = json.loads(result.read_text())
    assert actual['seed0_statistics_reused'] is True
    assert actual['comparisons']['0'] == old_pair
    assert seen == ['candidate1', 'baseline1']
    assert actual['seeds'] == [0, 1]


def test_different_candidate_run_cannot_reuse_an_unrelated_seed0(comparison, monkeypatch):
    module, result, previous, old_pair, row = comparison
    previous['comparisons']['0']['candidate_run'] = 'different_completed_model'
    result.write_text(json.dumps(previous))
    seen = []
    def scores(configuration, seed):
        seen.append((seed, configuration['run']))
        return {name: dict(mean_normalized_improvement=.48, seed=seed) for name in ('R1', 'R3')}
    monkeypatch.setattr(module, 'scores', scores)
    monkeypatch.setattr(module, 'paired_ci', lambda a, b:
                        row(-.01, -.03, .01) if a['seed'] == 0 else row(-.04, -.05, -.03))
    module.main()
    actual = json.loads(result.read_text())
    assert actual['seed0_statistics_reused'] is False
    assert actual['comparisons']['0']['candidate_run'] == 'candidate0'
    assert actual['comparisons']['0']['comparisons']['R3']['delta'] == -.01
    assert seen == [(0, 'candidate0'), (0, 'baseline0'), (1, 'candidate1'), (1, 'baseline1')]
