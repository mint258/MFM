"""Label-free H0 capacity plans preserve every native row and atom mapping."""
from pathlib import Path

import pytest
import torch

from phychem_mfm.phase1.v3_dev_panel import NativeGeometry, FrozenH0Cache, canonical
from phychem_mfm.phase1.v3_h0_packing import (packing_budget, packing_plan, packing_plans_for_views,
    H0PackingBudgetError)


def geometries(counts):
    records = []
    for i, n in enumerate(counts):
        positions = torch.stack((torch.arange(n).float()/3, torch.arange(n).float()/5,
                                 torch.full((n,), float(i))), dim=1)
        records.append(NativeGeometry('synthetic', f'native:{i}', i,
            torch.full((n, 1), 5+i, dtype=torch.long), positions,
            torch.arange(n-1, -1, -1, dtype=torch.long)))
    return tuple(records)


class IdentityAwareEncoder(torch.nn.Module):
    latent_dim = 4
    def __init__(self):
        super().__init__(); self.scale = torch.nn.Parameter(torch.tensor(2.)); self.calls = []
    def encode_atoms(self, batch):
        self.calls.append((batch.ptr[1:]-batch.ptr[:-1]).tolist())
        means = torch.zeros((len(batch.ptr)-1, 3), dtype=batch.pos.dtype)
        means.index_add_(0, batch.batch, batch.pos)
        means /= (batch.ptr[1:]-batch.ptr[:-1]).view(-1, 1)
        return torch.cat((batch.x.float().reshape(-1, 1)*self.scale,
                          batch.pos-means[batch.batch]), dim=1)


def order_sha(records):
    return canonical([[r.dataset_id, r.member_index, r.molecule_uid] for r in records])


def test_mixed_sizes_respect_budgets_without_changing_source_or_atom_order(tmp_path):
    from torch_geometric.data import Batch, Data
    records = geometries([3, 20, 4, 2, 11, 5]); encoder = IdentityAwareEncoder().eval()
    plan = packing_plan([len(r.x) for r in records], record_order_sha256=order_sha(records),
        max_graphs=3, max_native_atoms=24, max_padded_pairs=500, atom_bucket_width=8)
    assert plan['batches'] == [[3, 0, 2], [5], [4], [1]]
    assert sorted(i for batch in plan['batches'] for i in batch) == list(range(6))
    assert all(row['graphs'] <= 3 and row['native_atoms'] <= 24 and row['padded_pairs'] <= 500
               for row in plan['batch_statistics'])
    expected = []
    with torch.no_grad():
        for r in records:
            expected.append(encoder.encode_atoms(Batch.from_data_list([Data(x=r.x, pos=r.pos)])).clone())
    encoder.calls.clear()
    cache = FrozenH0Cache(tmp_path / 'cache', repository_root=tmp_path / 'repo')
    values, metadata = cache.get_or_compute(encoder, records, architecture_sha256='a'*64,
        membership_sha256='b'*64, max_graphs=3, max_native_atoms=24,
        max_padded_pairs=500, atom_bucket_width=8, expected_plan_sha256=plan['plan_sha256'])
    assert encoder.calls == [[2, 3, 4], [5], [11], [20]]
    assert [row.member_index for row in values] == list(range(6))
    for actual, original, expected_h0 in zip(values, records, expected):
        assert torch.equal(actual.h0, expected_h0)
        assert torch.equal(actual.source_atom_ids, original.source_atom_ids)
    assert metadata['binding']['packing_plan_sha256'] == plan['plan_sha256']
    assert metadata['binding']['packing_budget']['max_graphs'] == 3


def test_cache_cannot_reuse_or_execute_a_drifted_request_budget(tmp_path):
    records = geometries([4, 3, 2]); encoder = IdentityAwareEncoder()
    cache = FrozenH0Cache(tmp_path / 'cache', repository_root=tmp_path / 'repo')
    _, first = cache.get_or_compute(encoder, records, architecture_sha256='a'*64,
                                   membership_sha256='b'*64, max_padded_pairs=500)
    calls = len(encoder.calls)
    pinned = first['binding']['packing_plan_sha256']
    with pytest.raises(ValueError, match='budget drift'):
        cache.get_or_compute(encoder, records, architecture_sha256='a'*64,
            membership_sha256='b'*64, max_padded_pairs=501, expected_plan_sha256=pinned)
    assert len(encoder.calls) == calls
    _, second = cache.get_or_compute(encoder, records, architecture_sha256='a'*64,
        membership_sha256='b'*64, max_padded_pairs=500, expected_plan_sha256=pinned)
    assert len(encoder.calls) == calls and first['cache_key'] == second['cache_key']


def test_oversized_native_member_stays_in_singleton_plan_and_fails_without_drop(tmp_path):
    records = geometries([10, 1, 3]); encoder = IdentityAwareEncoder()
    cache = FrozenH0Cache(tmp_path / 'cache', repository_root=tmp_path / 'repo')
    with pytest.raises(H0PackingBudgetError) as caught:
        cache.get_or_compute(encoder, records, architecture_sha256='a'*64,
            membership_sha256='b'*64, max_graphs=3, max_native_atoms=100, max_padded_pairs=50)
    plan = caught.value.packing_plan
    assert plan['records_retained'] == 3 and plan['native_atoms_retained'] == 14
    assert plan['oversized_singleton_ordinals'] == [0] and [0] in plan['batches']
    assert sorted(i for batch in plan['batches'] for i in batch) == [0, 1, 2]
    assert not encoder.calls and not (tmp_path / 'cache').exists()
    assert 'not a measured GPU-capacity' in str(caught.value)


@pytest.mark.parametrize('change', [dict(max_graphs=0), dict(max_graphs=True),
    dict(max_native_atoms=-1), dict(max_padded_pairs=1.5), dict(atom_bucket_width=0)])
def test_budget_types_and_limits_are_explicit(change):
    with pytest.raises(ValueError):
        packing_budget(**change)


def test_packing_plan_uses_only_metadata_and_matches_runtime_record_order():
    records = geometries([4, 3, 2])
    class Store:
        def native_geometry_metadata(self, dataset, i):
            r = records[i]
            return dict(dataset_id=dataset, member_index=i, member_uid=r.molecule_uid,
                        native_n_atoms=len(r.x), geometry_ready=True)
        def get(self, *args):
            raise AssertionError('Target payload cannot be read while planning H0 packing')
    class View:
        def view(self, role):
            return (0, 1) if role == 'train' else (2,)
    budget = packing_budget(max_graphs=2)
    actual = packing_plans_for_views(Store(), {'synthetic': View()}, budget)['synthetic']
    expected = packing_plan([4, 3, 2], record_order_sha256=order_sha(records), max_graphs=2)
    assert actual == expected


def test_real_backbone_h0_matches_singletons_after_bucket_order_is_restored(tmp_path):
    from phychem_mfm.factory import build_model
    from torch_geometric.data import Batch, Data
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(17)
        encoder = build_model({'architecture': {'preset': 'shared_light'},
            'backbone': {'n_atom_types': 119, 'dim': 16, 'layers': 1, 'heads': 4,
                         'ff_mult': 2, 'dropout': 0., 'activation_checkpointing': False},
            'head': {'profile': 'phase1', 'geometry_head': 'equivariant_noise',
                     'geometry_hidden_dim': 8, 'geometry_rbf_count': 8}}).eval()
    records = geometries([2, 9, 3])
    with torch.no_grad():
        expected = [encoder.encode_atoms(Batch.from_data_list([Data(x=r.x, pos=r.pos)])).clone() for r in records]
    cache = FrozenH0Cache(tmp_path / 'cache', repository_root=tmp_path / 'repo')
    values, _ = cache.get_or_compute(encoder, records, architecture_sha256='a'*64,
        membership_sha256='b'*64, max_graphs=2, max_native_atoms=12, max_padded_pairs=100,
        atom_bucket_width=4)
    for actual, original, h0 in zip(values, records, expected):
        assert actual.member_index == original.member_index
        assert torch.equal(actual.source_atom_ids, original.source_atom_ids)
        torch.testing.assert_close(actual.h0, h0, rtol=1e-5, atol=1e-6)
