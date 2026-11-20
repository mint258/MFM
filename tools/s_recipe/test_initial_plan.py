"""Registered exposure and readout scope; no encoder or scheduler calls."""
import json

from configuration import make
from prepare_initial import ARMS, prepare


def test_trend_snapshots_belong_only_to_the_seed0_baseline():
    assert make('S-B0', seed=0)['evaluation_samples'] == [1000000, 2000000, 3000000]
    assert make('S-B0', seed=1)['evaluation_samples'] == [3000000]


def test_initial_plan_prepares_exactly_six_registered_seed0_conditions(tmp_path):
    plan = prepare(tmp_path)
    configurations = [json.loads(__import__('pathlib').Path(path).read_text()) for path in plan['configurations']]
    assert tuple(c['arm'] for c in configurations) == ARMS
    assert all(c['seed'] == 0 and c['samples'] == 3000000 for c in configurations)
    assert sum(c['samples'] for c in configurations) == 18000000
    assert not plan['jobs_submitted'] and not plan['training_executed']
    # A repeated preparation must retain the same condition files.
    assert prepare(tmp_path)['configurations'] == plan['configurations']
