"""Calibration selection uses final R3 and actual winner-only observations."""
import importlib.util
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location('select_calibration', Path(__file__).resolve().parents[2] / 'tools/p_recipe/select_calibration.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def groups():
    return [dict(run='cal_' + str(index), arm='G' + str(index), samples=3000000,
                 state='COMPLETED', batch_size=32 if index == 1 else 128,
                 lr=lr, activation_checkpointing=index != 1, R1=.1, R3=score,
                 observations=[dict(run='cal_' + str(index), samples=1500000, R3=.2),
                               dict(run='cal_' + str(index), samples=3000000, R3=score)])
            for index, (lr, score) in enumerate(((3e-4, .4), (3e-4, .3), (6e-4, .5), (1.2e-3, .35)), 1)]


def test_highest_final_r3_wins_and_registered_crossing_sets_budget():
    result = module.choose(groups())
    assert result['winner_group'] == 'G3'
    assert result['batch_size'] == 128 and result['lr'] == 6e-4
    assert result['screening_samples'] == 3000000


def test_first_observation_is_rounded_up_without_interpolation():
    data = groups()
    observations = [dict(run='cal_3', samples=500000, R3=.31),
                    dict(run='cal_3', samples=1100000, R3=.29),
                    dict(run='cal_3', samples=3000000, R3=.5)]
    result = module.choose(data, observations)
    assert result['screening_samples'] == 500000
    observations[0]['samples'] = 500001
    assert module.choose(data, observations)['screening_samples'] == 1000000
    for group in data:
        group['R3'] -= .3
        group['observations'][-1]['R3'] -= .3
    assert module.choose(data)['screening_samples'] == 3000000


def test_incomplete_or_foreign_scores_cannot_select_a_recipe():
    data = groups()
    data[0]['state'] = 'RUNNING'
    with pytest.raises(ValueError, match='complete 3M'):
        module.choose(data)
    with pytest.raises(ValueError, match='winning run'):
        module.choose(groups(), [dict(run='cal_1', samples=500000, R3=.9)])


def test_selected_base_keeps_frozen_data_and_restarts_clip_fitting_per_run():
    result = module.choose(groups())
    base = dict(output='/weights/old_B0', normalizations='frozen_11-07', corpus='clean_TRAIN',
                batch_size=128, lr=3e-4, activation_checkpointing=True)
    protocol = dict(rescreening=dict(study_revision='new', run_prefix='new_',
                    results_directory='results/new', control_directory='/control/new',
                    checkpoint_policy='screen_final_confirmation_milestones'))
    selected = module.selected_base(base, result, protocol)
    assert selected['normalizations'] == 'frozen_11-07' and selected['corpus'] == 'clean_TRAIN'
    assert selected['clip_calibration'] == dict(fraction=.05, initial_clip=281.7, quantile=.99)
    assert selected['output'] == '/weights/new/new_base'
    assert selected['batch_size'] == selected['microbatch_size'] == 128
    assert selected['checkpoint_policy'] == 'screen_final_confirmation_milestones'
