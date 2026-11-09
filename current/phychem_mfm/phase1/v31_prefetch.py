"""Overlap one ordered CPU input batch with training, without consuming it."""
from copy import deepcopy


def ordered_sample_batches(pool, read_choice, dataset, clock, rng, batch_size, stop_samples):
    """Yield samples and their post-draw RNG state; caller commits after its update.

    Only the private planning clock/RNG run ahead. Checkpoints continue to contain
    the trained cursor, even when the next batch has already been read by workers.
    Executor.map preserves choice order, independently of worker completion order.
    """
    planned_clock, planned_rng = deepcopy(clock), deepcopy(rng)

    def submit_next():
        if planned_clock.samples_consumed >= stop_samples:
            return None
        count = min(planned_clock.max_next_samples(batch_size),
                    stop_samples - planned_clock.samples_consumed)
        choices = []
        for _ in range(count):
            molecule = int(planned_rng.choice(dataset.indices))
            choices.append((molecule, int(planned_rng.choice(dataset.choices(molecule)))))
        planned_clock.advance(count)
        state = deepcopy(planned_rng.bit_generator.state)
        return state, pool.map(read_choice, choices, chunksize=1)

    pending = submit_next()
    while pending is not None:
        state, reads = pending
        samples = list(reads)
        pending = submit_next()
        yield samples, state
