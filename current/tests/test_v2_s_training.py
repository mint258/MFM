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


@pytest.mark.parametrize('input_only_counts', [False, True])
def test_microbatch_backward_preserves_field_observation_means_and_gradient(input_only_counts):
    from torch_geometric.data import Data
    from phychem_mfm.phase1.v2_s_training import accumulated_s_backward
    from phychem_mfm.phase1.v3_losses import V3LossResult
    class Model(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.weight = torch.nn.Parameter(torch.tensor(.7))
            self.forwards = 0
        def forward_pretrain(self, batch, **kwargs):
            self.forwards += 1
            return batch.x * self.weight
        def compute_loss(self, prediction, batch, *args, **kwargs):
            masks = {'s_element': batch.x[:, 0] > 1, 's_noise': batch.x[:, 0] > 0,
                     's_bond': batch.x[:, 0] > 3}
            counts = {k: int(v.sum()) for k, v in masks.items()}
            fields = {k: (prediction[v].square().mean() if counts[k] else prediction.sum() * 0.)
                      for k, v in masks.items()}
            total = torch.stack([fields[k] for k, n in counts.items() if n]).mean()
            return V3LossResult(total, fields, {'S': total}, counts,
                                {'S': sum(n > 0 for n in counts.values())}, ('S',))
    model = Model()
    records = [Data(x=torch.arange(1, n + 1, dtype=torch.float32)[:, None]) for n in (2, 5, 3)]
    from torch_geometric.data import Batch
    full = Batch.from_data_list(records)
    expected = model.compute_loss(model.forward_pretrain(full), full)
    expected.total.backward()
    gradient = model.weight.grad.clone()
    model.zero_grad()
    model.forwards = 0
    def count_inputs(model, batch):
        return {'s_element':int((batch.x[:,0] > 1).sum()),
                's_noise':int((batch.x[:,0] > 0).sum()), 's_bond':int((batch.x[:,0] > 3).sum())}
    actual = accumulated_s_backward(model, records, (0, 1, 2), lambda batch, **kw: batch,
                                    None, 1, 0, count_observations=count_inputs if input_only_counts else None)
    assert actual.counts == expected.counts
    torch.testing.assert_close(actual.total, expected.total.detach(), atol=1e-6, rtol=1e-6)
    torch.testing.assert_close(model.weight.grad, gradient, atol=1e-6, rtol=1e-6)
    assert model.forwards == (3 if input_only_counts else 6)


def test_preregistered_wsd_has_two_percent_warmup_and_linear_final_twenty_percent():
    from phychem_mfm.phase1.v2_s_training import sample_lr_ratio
    assert sample_lr_ratio(100, 10000, 'wsd') == pytest.approx(.5, abs=1e-6, rel=1e-6)
    assert sample_lr_ratio(7000, 10000, 'wsd') == pytest.approx(1., abs=1e-6, rel=1e-6)
    assert sample_lr_ratio(8500, 10000, 'wsd') == pytest.approx(.75, abs=1e-6, rel=1e-6)
    assert sample_lr_ratio(10000, 10000, 'wsd') == pytest.approx(0., abs=1e-6, rel=1e-6)
