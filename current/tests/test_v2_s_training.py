import numpy as np
import pytest
import torch

from phychem_mfm.phase1.v2_s_training import GroupedSIndex, s_model, structural_record


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


def test_native_atom_descriptor_index_is_not_collated_as_an_edge():
    from torch_geometric.data import Batch, Data
    from phychem_mfm.data.descriptor_schema import BOND_INDEX_FIELD, BOND_ORDER_FIELD, BOND_STATUS_FIELD
    rows = []
    for n in (3, 5):
        row = Data(x=torch.zeros(n, 1, dtype=torch.long), pos=torch.zeros(n, 3),
                   rdkit_node_estate_index=torch.ones(n, 1))
        setattr(row, BOND_INDEX_FIELD, torch.tensor([[0], [1]]))
        setattr(row, BOND_ORDER_FIELD, torch.tensor([2]))
        setattr(row, BOND_STATUS_FIELD, 'ok')
        rows.append(structural_record(row))
    batch = Batch.from_data_list(rows)
    assert batch.num_nodes == 8 and 'rdkit_node_estate_index' not in batch
    assert getattr(batch, BOND_INDEX_FIELD).tolist() == [[0, 3], [1, 4]]
    assert getattr(batch, BOND_ORDER_FIELD).tolist() == [2, 2]


def test_validation_roles_keep_source_ordinals_and_never_pool_diagnostic_into_full():
    from phychem_mfm.phase1.v2_s_validation import validation_populations
    rows = [dict(role='FULL', routine=False), dict(role='FULL', routine=True),
            dict(role='TRAIN_UNSEEN_CONFORMATION', routine=False)]
    selected = validation_populations(rows, 'ROUTINE')
    assert [i for i, _ in selected['ROUTINE']] == [1]
    assert [i for i, _ in selected['TRAIN_UNSEEN_CONFORMATION']] == [2]
    assert [i for i, _ in validation_populations(rows, 'FULL')['FULL']] == [0, 1]
