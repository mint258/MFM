from confirmed_decisions import confirm
from finalize_recipe import select
import json
from pathlib import Path
import pytest


def entry(verdict, delta=0):
    return dict(status='COMPLETE', candidate_R3=.4+delta,
                R3=dict(verdict=verdict, delta=delta, ci_lower=-.01, ci_upper=.02))


def closed():
    loss = confirm(entry('LOSS'))
    return dict(status='COMPLETE', arms={'S-N1': loss, 'S-N2': loss,
                                         'S-R1': loss, 'S-R2': loss})


def test_all_decisions_including_geometry_are_required_before_freezing():
    c = closed()
    assert select(dict(status='PENDING'), c)['status'] == 'WAITING_ALL_DECISIONS'
    result = select(dict(status='COMPLETE'), c)
    assert result == dict(status='READY', recipe='S-B0', components=[])


def test_two_deletions_need_merge_and_non_win_falls_back_to_single():
    c = closed()
    c['arms']['S-R1'] = confirm(entry('TIE', .002))
    c['arms']['S-R2'] = confirm(entry('TIE', .001))
    first = dict(status='COMPLETE')
    assert select(first, c)['status'] == 'WAITING_MERGE'
    merged = select(first, c, entry('WIN', .04))
    assert merged['recipe'] == 'S-M1' and merged['components'] == ['S-R1', 'S-R2']
    fallback = select(first, c, entry('TIE'))
    assert fallback['recipe'] == 'S-R1' and fallback['components'] == ['S-R1']
    assert select(first, c, dict(status='UNRESOLVED', reason='repair limit'))['recipe'] == 'S-R1'


def test_9M_plan_requires_freeze_and_has_only_baseline_or_distinct_final(tmp_path, monkeypatch):
    import finalize_recipe as final
    monkeypatch.setattr(final, 'REPO', tmp_path)
    folder = tmp_path/'configs/s_recipe'
    folder.mkdir(parents=True)
    best = folder/'CURRENT_BEST.json'
    best.write_text(json.dumps(dict(status='PENDING', recipe='S-B0', components=[])))
    with pytest.raises(ValueError, match='final recipe freeze'):
        final.confirmation()
    best.write_text(json.dumps(dict(status='FROZEN', recipe='S-B0', components=[])))
    first = final.confirmation()
    assert len(first['configurations']) == 1
    best.write_text(json.dumps(dict(status='FROZEN', recipe='S-N1', components=['S-N1'])))
    plan = final.confirmation()
    configs = [json.loads(Path(p).read_text()) for p in plan['configurations']]
    assert [c['arm'] for c in configs] == ['S-B0', 'S-final']
    assert all(c['samples'] == 9000000 and c['seed'] == 0 for c in configs)
    assert all('resume' not in c for c in configs)
    assert configs[1]['components'] == ['S-N1'] and configs[1]['noise'] == 'multiscale'
    assert not plan['jobs_submitted'] and not plan['descriptive_geometry_9M']
