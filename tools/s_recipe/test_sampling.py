from copy import deepcopy

import numpy as np

from s_data import paired_choices


def test_sources_share_molecule_order_despite_conformer_count_difference():
    rows = [dict(molecule_index=i, PM7=list(range(10)), UFF=[30+i]) for i in range(19)]
    a, b = np.random.default_rng(0), np.random.default_rng(0)
    pm7 = paired_choices(a, rows, 'PM7', seed=0, start=0, count=2000)
    uff = paired_choices(b, rows, 'UFF', seed=0, start=0, count=2000)
    assert [x[0] for x in pm7] == [x[0] for x in uff]
    assert [x[2] for x in pm7] == [x[2] for x in uff]
    assert all(c in rows[m]['PM7'] for m, c, _ in pm7)
    assert all(c in rows[m]['UFF'] for m, c, _ in uff)
    assert a.bit_generator.state == b.bit_generator.state


def test_resume_and_batch_boundaries_preserve_complete_draw_sequence():
    rows = [dict(molecule_index=i, PM7=list(range(i % 5 + 1))) for i in range(19)]
    whole_rng, split_rng = np.random.default_rng(7), np.random.default_rng(7)
    whole = paired_choices(whole_rng, rows, 'PM7', seed=7, start=0, count=96)
    first = paired_choices(split_rng, rows, 'PM7', seed=7, start=0, count=32)
    state = deepcopy(split_rng.bit_generator.state)
    # Simulate discarded, not-consumed prefetch before restoring checkpoint.
    paired_choices(split_rng, rows, 'PM7', seed=7, start=32, count=32)
    resumed = np.random.default_rng()
    resumed.bit_generator.state = state
    rest = paired_choices(resumed, rows, 'PM7', seed=7, start=32, count=64)
    assert first + rest == whole
