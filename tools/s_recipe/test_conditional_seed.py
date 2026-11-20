import json
from pathlib import Path

from conditional_seed import candidates, prepare


def result(primary, secondary='WIN'):
    return dict(status='COMPLETE', R3=dict(verdict=primary), R1=dict(verdict=secondary))


def test_only_seed0_primary_wins_trigger_confirmations():
    decisions = {'S-N1': result('WIN', 'LOSS'), 'S-N2': result('TIE'),
                 'S-R1': result('LOSS'), 'S-G1': result('WIN')}
    assert candidates(decisions) == ['S-N1']
    assert candidates({'S-G1': result('WIN')}) == []


def test_multiple_winners_share_one_terminal_only_baseline(tmp_path):
    decisions = {'S-N1': result('WIN'), 'S-R2': result('WIN')}
    plan = prepare(decisions, tmp_path)
    configs = [json.loads(Path(path).read_text()) for path in plan['configurations']]
    assert [c['arm'] for c in configs] == ['S-B0', 'S-N1', 'S-R2']
    assert all(c['seed'] == 1 and c['samples'] == 3000000 for c in configs)
    assert configs[0]['evaluation_samples'] == [3000000]
    assert prepare(decisions, tmp_path)['configurations'] == plan['configurations']
    assert not plan['jobs_submitted']
