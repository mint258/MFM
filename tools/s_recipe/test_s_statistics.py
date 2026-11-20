"""Only new S threshold and paired-producer binding rules."""
from copy import deepcopy
import pytest

from s_statistics import paired


def summary(value):
    return dict(complete=True, bootstrap_defined=1000, bootstrap_samples=1000,
                mean_normalized_improvement=value, tasks={'seven_task_mean': {}},
                paired_bootstrap=dict(groups={'dataset': ['m1', 'm2']}, seed=20261025,
                                      samples=1000, confidence=.95, values=[value]*1000))


def test_s_loss_requires_negative_ci_without_the_old_p_effect_size_gate():
    result = paired(summary(.499), summary(.5))
    assert result['verdict'] == 'LOSS'
    assert abs(result['delta']) < result['tau']
    assert paired(summary(.501), summary(.5))['verdict'] == 'TIE'
    assert paired(summary(.6), summary(.5))['verdict'] == 'WIN'


def test_bootstrap_comparison_rejects_different_molecule_draw_ownership():
    candidate = summary(.6)
    baseline = summary(.5)
    baseline['paired_bootstrap']['groups']['dataset'] = ['m1', 'different']
    with pytest.raises(ValueError, match='not paired by molecule'):
        paired(candidate, baseline)
