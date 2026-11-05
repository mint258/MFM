import pytest

from phychem_mfm.phase1.v2_decisions import (
    condition_aggregates, seed_standard_deviation, choose_within_seed_sd,
    convergence_budget, shared_training_budget,
)


def test_condition_scores_are_combined_within_seed_not_as_extra_seeds():
    rows = [dict(candidate='a', seed=0, condition='S', score=.2),
            dict(candidate='a', seed=0, condition='P', score=.4),
            dict(candidate='a', seed=1, condition='S', score=.3),
            dict(candidate='a', seed=1, condition='P', score=.5),
            dict(candidate='b', seed=0, condition='S', score=.9)]
    complete, pending = condition_aggregates(rows, ('S','P'))
    assert complete['a'] == pytest.approx({0:.3, 1:.4}, abs=1e-6, rel=1e-6)
    assert pending == [dict(candidate='b', seed=0, missing_conditions=['P'])]
    assert seed_standard_deviation(complete['a'].values()) == pytest.approx(.1 / 2**.5, abs=1e-6, rel=1e-6)


def test_within_one_seed_sd_uses_predeclared_simplicity_not_training_loss():
    result = choose_within_seed_sd({'C1-0': .28, 'C1-a': .30, 'C1-b': .20},
        seed_sd=.03, simplicity_order=('C1-0','C1-a','C1-b'))
    assert result['best_dev_candidate'] == 'C1-a' and result['selected'] == 'C1-0'
    assert result['eligible'] == ['C1-0','C1-a']


def test_budget_uses_earliest_actual_doubling_then_larger_s_p_result():
    s = convergence_budget({1_000_000:.1, 2_000_000:.2, 4_000_000:.205, 8_000_000:.206}, seed_sd=.01)
    p = convergence_budget({1_000_000:.1, 2_000_000:.2, 4_000_000:.3, 8_000_000:.305}, seed_sd=.01)
    assert s['budget'] == 4_000_000 and p['budget'] == 8_000_000
    assert shared_training_budget(s,p) == 8_000_000
    assert shared_training_budget(s, convergence_budget({1_000_000:.1}, seed_sd=.01)) is None


def test_ceiling_does_not_claim_a_plateau_and_one_seed_does_not_supply_sd():
    result = convergence_budget({32_000_000:.2, 64_000_000:.4}, seed_sd=.01)
    assert result['status'] == 'CEILING_REACHED_WITHOUT_OBSERVED_PLATEAU'
    assert result['budget'] is None and result['tested_limit'] == 64_000_000
    with pytest.raises(ValueError, match='two actual'):
        seed_standard_deviation([.3])
