from copy import deepcopy
import pytest
from configuration import make
from recovery import retry_configuration
from checkpoint_binding import baseline_acceptance_required


def test_failed_baseline_retains_acceptance_and_uses_same_zero_state_condition():
    current = make('S-B0')
    saved = deepcopy(current)
    saved['baseline_acceptance'] = dict(source_order=True)
    retry = retry_configuration(current, saved, acceptance_source='/archive/configuration.json')
    assert retry['execution_attempt'] == 2 and 'resume' not in retry
    assert retry['seed'] == 0 and retry['samples'] == 3000000
    assert retry['clip_calibration']['initial_clip'] == 281.7
    assert retry['baseline_acceptance'] == saved['baseline_acceptance']
    with pytest.raises(ValueError, match='sole baseline acceptance'):
        retry_configuration(current, current)


def test_handoff_recovery_keeps_partial_cursor_and_rejects_changed_science():
    current = make('S-N1')
    current.update(node='compute-0-7', gpu_uuid='old', handoff_request='/old/request')
    retry = retry_configuration(current, current, checkpoint='/closed/partial.pt', resume_samples=32000)
    assert retry['resume_samples'] == 32000 and retry['noise'] == 'multiscale'
    assert 'node' not in retry and 'handoff_request' not in retry
    changed = deepcopy(current)
    changed['seed'] = 1
    with pytest.raises(ValueError, match='condition differs'):
        retry_configuration(current, changed, checkpoint='/closed/partial.pt', resume_samples=32000)
    with pytest.raises(ValueError, match='failed baseline'):
        retry_configuration(current, current, acceptance_source='/archive/configuration.json')


def test_the_sole_acceptance_is_not_repeated_on_seed1_9M_or_recovery():
    c = make('S-B0')
    assert baseline_acceptance_required(c, 0)
    assert not baseline_acceptance_required(c, 32)
    assert not baseline_acceptance_required(c, 0, validation_pass=True)
    assert not baseline_acceptance_required(make('S-B0', seed=1), 0)
    assert not baseline_acceptance_required(make('S-B0', samples=9000000), 0)
    assert not baseline_acceptance_required(dict(c, baseline_acceptance={'source_order': True}), 0)
