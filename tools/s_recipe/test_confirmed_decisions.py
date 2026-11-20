"""Scientific confirmation and mutual exclusion, using synthetic decisions only."""
from confirmed_decisions import confirm, choose_noise


def decision(verdict='WIN', delta=.04, score=.5):
    return dict(status='COMPLETE', candidate_R3=score,
                R3=dict(verdict=verdict, delta=delta), R1=dict(verdict='LOSS'))


def test_only_both_individual_R3_wins_confirm_and_no_third_seed_is_requested():
    first = decision()
    assert confirm(first)['status'] == 'WAITING_SEED1'
    result = confirm(first, decision('TIE'))
    assert result['status'] == 'COMPLETE' and not result['confirmed_WIN']
    assert set(result['seed_results']) == {'0', '1'}
    assert not confirm(decision('LOSS'))['confirmed_WIN']
    assert confirm(first, decision())['confirmed_WIN']  # R1 LOSS is report-only.
    assert not confirm(first, dict(status='UNRESOLVED', reason='repair limit'))['confirmed_WIN']


def test_noise_exclusion_uses_two_seed_mean_delta_and_candidate_score_tau():
    a = confirm(decision(delta=.04, score=.5), decision(delta=.06, score=.6))
    b = confirm(decision(delta=.05, score=.51), decision(delta=.07, score=.61))
    result = choose_noise({'S-N1': a, 'S-N2': b})
    assert result['selected'] == 'S-N1'  # N2 advantage .01 is below tau .028.
    b = confirm(decision(delta=.10, score=.56), decision(delta=.12, score=.66))
    assert choose_noise({'S-N1': a, 'S-N2': b})['selected'] == 'S-N2'
    assert choose_noise({'S-N1': a})['status'] == 'WAITING_NOISE_CONFIRMATIONS'
    none = confirm(decision('TIE'))
    assert choose_noise({'S-N1': none, 'S-N2': none})['selected'] is None
    assert choose_noise({'S-N1': a, 'S-N2': none})['selected'] == 'S-N1'
