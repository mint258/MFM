"""Boundary checks of the user's D-prime conditional seed rule."""
import importlib.util
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location('dprime_decision',
    Path(__file__).resolve().parents[2] / 'tools/p_followup/dprime_decision.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def row(delta, lo, hi):
    return dict(delta=delta, ci95=[lo, hi])


def test_single_seed_requires_both_effect_and_strict_ci():
    assert module.decision([row(.06, .001, .09)], [.468])['verdict'] == 'win'
    assert module.decision([row(-.06, -.09, -.001)], [.468])['verdict'] == 'loss'
    for value in [row(.059, .001, .09), row(.07, 0., .1), row(-.07, -.1, 0.)]:
        assert module.decision([value], [.468])['status'] == 'SEED1_REQUIRED'


def test_two_seeds_require_joint_sign_and_average_effect():
    baseline = [.468, .482]
    assert module.decision([row(.04, .01, .07)] * 2, baseline)['verdict'] == 'win'
    assert module.decision([row(.035, .01, .06)] * 2, baseline)['verdict'] == 'tie'
    assert module.decision([row(.04, .01, .07), row(.04, -.01, .09)], baseline)['verdict'] == 'tie'
    assert module.decision([row(-.02, -.04, -.001)] * 2, baseline)['verdict'] == 'loss'
    with pytest.raises(ValueError, match='not triggered'):
        module.decision([row(.06, .001, .09)] * 2, baseline)
