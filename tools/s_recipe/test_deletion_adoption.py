from confirmed_decisions import confirm, deletion_adopted, proposal


def result(verdict, lower, upper):
    return dict(status='COMPLETE', candidate_R3=.5,
                R3=dict(verdict=verdict, delta=.04, ci_lower=lower, ci_upper=upper))


def test_deletion_WIN_needs_two_wins_while_TIE_requires_zero_crossing():
    win = result('WIN', .02, .06)
    assert not deletion_adopted(confirm(win))
    assert deletion_adopted(confirm(win, win))
    assert not deletion_adopted(confirm(win, result('TIE', -.01, .03)))
    assert deletion_adopted(confirm(result('TIE', -.01, .01)))
    assert not deletion_adopted(confirm(result('TIE', -.02, -.001)))
    assert not deletion_adopted(confirm(result('LOSS', -.06, -.02)))


def test_two_individually_adopted_deletions_still_require_one_merge():
    tie = confirm(result('TIE', -.01, .01))
    loss = confirm(result('LOSS', -.06, -.02))
    plan = proposal({'S-N1': loss, 'S-N2': loss, 'S-R1': tie, 'S-R2': tie})
    assert plan['ready'] and plan['merge_required'] and not plan['recipe_frozen']
    assert plan['components'] == ['S-R1', 'S-R2']
