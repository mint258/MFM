import numpy as np
import pytest
import torch

from phychem_mfm.phase1.v2_s_training import GroupedSIndex, s_model


def test_molecule_first_draw_does_not_weight_by_conformer_count():
    pa = pytest.importorskip('pyarrow')
    table = pa.table(dict(molecule_id=['a'] + ['b'] * 9,
        record_id=[str(i) for i in range(10)], source_path=['source'] * 10,
        real_index=list(range(10)), total_atoms=[2] * 10))
    index = GroupedSIndex(table)
    rows = index.draw(np.random.default_rng(512), 20_000)
    fraction = sum(row['molecule_id'] == 'a' for row in rows) / len(rows)
    assert abs(fraction - .5) < .02
    b = [row['real_index'] for row in rows if row['molecule_id'] == 'b']
    counts = np.bincount(b, minlength=10)[1:]
    assert max(abs(counts / len(b) - 1 / 9)) < .02


def test_s_composition_uses_adopted_flags_and_omits_digest_work():
    torch.manual_seed(512)
    model, config = s_model('C1-0', 'three')
    assert model.latent_dim == 512 and config['backbone']['layers'] == 6
    assert not model.encoder.backbone.activation_checkpointing
    assert not model.encoder.geometry_head.activation_checkpointing
    assert model.encoder.s_memory_implementation['pair_rows'] == 65536
