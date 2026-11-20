"""A shared initialization must not make different trained arms interchangeable."""
from copy import deepcopy
import pytest

from checkpoint_binding import validate_resume
from configuration import make


@pytest.mark.parametrize('key,value', [('noise', 'baseline'), ('seed', 1)])
def test_resume_rejects_a_different_condition_with_the_same_architecture(key, value):
    configuration = make('S-N1')
    saved = deepcopy(configuration)
    saved[key] = value
    with pytest.raises(ValueError, match='S resume condition differs: '+key):
        validate_resume(configuration, saved)


def test_complete_state_can_move_between_execution_handles():
    configuration = make('S-N1')
    saved = deepcopy(configuration)
    saved.update(run='old_native_handle', output='/old/output', node='compute-0-20')
    validate_resume(configuration, saved)
