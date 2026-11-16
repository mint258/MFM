from copy import deepcopy

import numpy as np
import pytest

from phychem_mfm.phase1.v31_prefetch import ordered_sample_batches
from phychem_mfm.phase1.v3_training import SampleClock


class Population:
    indices = np.array([3, 11, 17])

    def choices(self, molecule):
        return {3: (0,), 11: (2, 5, 8), 17: (1, 4)}[molecule]


class RecordingExecutor:
    """Like Executor.map, submit eagerly but return ordered results lazily."""
    def __init__(self):
        self.submitted = []

    def map(self, function, choices, chunksize):
        assert chunksize == 1
        self.submitted.append(tuple(choices))
        return map(function, choices)


def serial_batches(seed, stop=23):
    rng = np.random.default_rng(seed)
    population = Population()
    clock = SampleClock(23, milestones=(5, 9, 17))
    batches = []
    while clock.samples_consumed < stop:
        count = min(clock.max_next_samples(4), stop - clock.samples_consumed)
        choices = []
        for _ in range(count):
            molecule = int(rng.choice(population.indices))
            choices.append((molecule, int(rng.choice(population.choices(molecule)))))
        clock.advance(count)
        batches.append((choices, deepcopy(rng.bit_generator.state)))
    return batches


@pytest.mark.parametrize('seed', [0, 1])
def test_prefetch_preserves_serial_molecule_conformer_order_and_batch_boundaries(seed):
    expected = serial_batches(seed)
    clock = SampleClock(23, milestones=(5, 9, 17))
    rng = np.random.default_rng(seed)
    original_rng = deepcopy(rng.bit_generator.state)
    executor = RecordingExecutor()
    received = []
    for samples, consumed_rng in ordered_sample_batches(
            executor, lambda choice: choice, Population(), clock, rng, 4, 23):
        # Merely preparing/delivering a batch cannot count it as trained.
        assert clock.samples_consumed == sum(len(batch) for batch, _ in received)
        assert rng.bit_generator.state == (received[-1][1] if received else original_rng)
        received.append((samples, consumed_rng))
        clock.advance(len(samples))
        rng.bit_generator.state = consumed_rng
    assert received == expected
    assert [len(batch) for batch, _ in received] == [4, 1, 4, 4, 4, 4, 2]
    assert clock.samples_consumed == 23 and clock.optimizer_updates == 7
    assert len(executor.submitted) == len(expected)


@pytest.mark.parametrize('checkpoint', [5, 9])
def test_resume_discards_unconsumed_prefetch_without_skipping_or_repeating_draws(checkpoint):
    clock = SampleClock(23, milestones=(5, 9, 17))
    rng = np.random.default_rng(7)
    executor = RecordingExecutor()
    iterator = ordered_sample_batches(executor, lambda choice: choice,
                                     Population(), clock, rng, 4, 23)
    prefix = []
    while clock.samples_consumed < checkpoint:
        samples, state = next(iterator)
        prefix.append((samples, state))
        clock.advance(len(samples))
        rng.bit_generator.state = state
    assert len(executor.submitted) == len(prefix) + 1
    saved_clock, saved_rng = clock.state_dict(), deepcopy(rng.bit_generator.state)
    iterator.close()
    restored_clock = SampleClock(23, milestones=(5, 9, 17))
    restored_clock.load_state_dict(saved_clock)
    restored_rng = np.random.default_rng(0)
    restored_rng.bit_generator.state = saved_rng
    suffix = list(ordered_sample_batches(RecordingExecutor(), lambda choice: choice,
                  Population(), restored_clock, restored_rng, 4, 23))
    assert prefix + suffix == serial_batches(7)
    assert restored_clock.state_dict() == saved_clock
    assert restored_rng.bit_generator.state == saved_rng


def test_one_batch_is_submitted_ahead_before_caller_computes_without_committing_rng():
    executor = RecordingExecutor()
    rng = np.random.default_rng(0)
    initial = deepcopy(rng.bit_generator.state)
    clock = SampleClock(23, milestones=(5, 9, 17))
    iterator = ordered_sample_batches(executor, lambda choice: choice,
                                     Population(), clock, rng, 4, 9)
    samples, state = next(iterator)
    assert [len(batch) for batch in executor.submitted] == [4, 1]
    assert len(samples) == 4 and state != initial
    assert clock.samples_consumed == 0 and rng.bit_generator.state == initial
    remaining = list(iterator)
    assert [len(batch) for batch in executor.submitted] == [4, 1, 4]
    assert [len(batch) for batch, _ in remaining] == [1, 4]


def test_completed_segment_submits_no_reads():
    executor = RecordingExecutor()
    clock = SampleClock(23, milestones=(5, 9, 17), samples_consumed=9)
    assert list(ordered_sample_batches(executor, lambda choice: choice,
                Population(), clock, np.random.default_rng(0), 4, 9)) == []
    assert executor.submitted == []


def test_reader_failure_cannot_advance_consumed_cursor_or_rng():
    def fail(_):
        raise OSError('existing worker read failure')
    executor = RecordingExecutor()
    clock = SampleClock(23, milestones=(5, 9, 17))
    rng = np.random.default_rng(0)
    initial = deepcopy(rng.bit_generator.state)
    with pytest.raises(OSError, match='worker read failure'):
        next(ordered_sample_batches(executor, fail, Population(), clock, rng, 4, 23))
    assert clock.samples_consumed == 0 and clock.optimizer_updates == 0
    assert rng.bit_generator.state == initial
    assert len(executor.submitted) == 1
