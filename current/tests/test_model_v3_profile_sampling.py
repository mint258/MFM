import importlib.util
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location('profile_sampling', Path(__file__).resolve().parents[2]/'tools/model_v3/profile_sampling.py')
sampling = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sampling)


def test_fixed_representative_steps_cover_same_front_middle_tail():
    assert sampling.representative_steps(20) == (0, 10, 19)
    assert sampling.representative_steps(2) == (0, 1)
    assert sampling.representative_steps(1) == (0,)
    for value in (0, 21, True, 2.5):
        with pytest.raises(ValueError):
            sampling.representative_steps(value)


def row(ordinal, profiled, seconds, count):
    return dict(ordinal=ordinal, profiled=profiled, end_to_end_step_seconds=seconds,
                base_molecules=count, molecule_presentations=count, base_atoms=3*count, encoder_atoms=9*count)


def test_training_throughput_excludes_diagnostic_and_export_time():
    rows = [row(2, True, 100., 10), row(3, False, 2., 4), row(4, False, 3., 6)]
    result = sampling.throughput_summary(rows)
    assert result['throughput_scope'] == 'unprofiled_steps'
    assert result['throughput_step_ordinals'] == [3, 4]
    assert result['throughput_elapsed_seconds'] == 5.
    assert result['base_structures_per_second'] == 2.
    assert result['native_atoms_per_second'] == 6.


def test_small_smoke_cannot_be_mislabeled_unprofiled():
    assert sampling.throughput_summary([row(1, True, 1., 2)])['throughput_scope'] == 'profiled_smoke_only'
    with pytest.raises(ValueError):
        sampling.throughput_summary([row(1, False, 0., 2)])
    with pytest.raises(ValueError):
        sampling.throughput_summary([row(1, False, 1., 2), row(1, False, 1., 2)])
