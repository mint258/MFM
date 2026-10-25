"""Cache identity follows effective FP32 policy and actual physical sources."""
from dataclasses import replace
import hashlib
from pathlib import Path

import pytest
import torch

from phychem_mfm.phase1.v3_dev_panel import FrozenH0Cache, NativeGeometry
from phychem_mfm.phase1.v3_h0_runtime import h0_runtime_fingerprint, physical_source_binding


class AutocastSensitiveEncoder(torch.nn.Module):
    latent_dim = 3
    def __init__(self):
        super().__init__(); self.projection = torch.nn.Linear(4, 3); self.autocast_seen = []
    def encode_atoms(self, batch):
        self.autocast_seen.append(torch.is_autocast_enabled('cpu'))
        return self.projection(torch.cat((batch.x.float().reshape(-1, 1), batch.pos), dim=1))


def records():
    return (NativeGeometry('synthetic', 'member:0', 0, torch.tensor([[5], [0]]),
        torch.tensor([[0., 0., 0.], [1., 0., 0.]]), torch.tensor([1, 0])),)


def compute(cache, encoder, geometry=None, **kwargs):
    return cache.get_or_compute(encoder, records() if geometry is None else geometry,
        architecture_sha256='a'*64, membership_sha256='b'*64, **kwargs)


def test_outer_autocast_is_locally_disabled_and_global_policy_is_preserved(tmp_path):
    encoder = AutocastSensitiveEncoder().train()
    cache = FrozenH0Cache(tmp_path / 'cache', repository_root=tmp_path / 'repo')
    precision = torch.get_float32_matmul_precision(); tf32 = torch.backends.cuda.matmul.allow_tf32
    from torch_geometric.data import Batch, Data
    source = records()[0]; batch = Batch.from_data_list([Data(x=source.x, pos=source.pos)])
    with torch.autocast('cpu', dtype=torch.bfloat16):
        assert encoder.encode_atoms(batch).dtype == torch.bfloat16
        rows, metadata = compute(cache, encoder)
        assert torch.is_autocast_enabled('cpu') and rows[0].h0.dtype == torch.float32
    assert encoder.autocast_seen == [True, False] and encoder.training is True
    assert torch.get_float32_matmul_precision() == precision and torch.backends.cuda.matmul.allow_tf32 == tf32
    assert metadata['binding']['effective_runtime']['matmul_precision'] == precision
    with torch.no_grad():
        expected = encoder.encode_atoms(batch)
    torch.testing.assert_close(rows[0].h0, expected, rtol=0, atol=0)


def test_effective_matmul_policy_produces_a_distinct_cache(tmp_path):
    encoder = AutocastSensitiveEncoder()
    cache = FrozenH0Cache(tmp_path / 'cache', repository_root=tmp_path / 'repo')
    precision = torch.get_float32_matmul_precision(); tf32 = torch.backends.cuda.matmul.allow_tf32
    try:
        _, first = compute(cache, encoder)
        torch.set_float32_matmul_precision('high' if precision != 'high' else 'highest')
        _, second = compute(cache, encoder)
        assert first['cache_key'] != second['cache_key']
        assert first['binding']['effective_runtime_sha256'] != second['binding']['effective_runtime_sha256']
    finally:
        torch.set_float32_matmul_precision(precision)
        torch.backends.cuda.matmul.allow_tf32 = tf32


def test_cache_identity_binds_execution_source_and_native_geometry(tmp_path):
    encoder = AutocastSensitiveEncoder()
    cache = FrozenH0Cache(tmp_path / 'cache', repository_root=tmp_path / 'repo')
    _, first = compute(cache, encoder, execution_source={'code_sha': 'a'*40, 'origin': 'checkpoint'})
    _, replay = compute(cache, encoder, execution_source={'code_sha': 'a'*40, 'origin': 'checkpoint'})
    assert first['cache_key'] == replay['cache_key'] and len(encoder.autocast_seen) == 1
    _, source_changed = compute(cache, encoder, execution_source={'code_sha': 'b'*40, 'origin': 'checkpoint'})
    _, origin_changed = compute(cache, encoder, execution_source={'code_sha': 'a'*40, 'origin': 'random'})
    r = records()[0]; positions = r.pos.clone(); positions[1, 0] = 2.
    _, geometry_changed = compute(cache, encoder, geometry=(replace(r, pos=positions),),
        execution_source={'code_sha': 'a'*40, 'origin': 'checkpoint'})
    assert len({m['cache_key'] for m in (first, source_changed, origin_changed, geometry_changed)}) == 4


def test_physical_sources_do_not_follow_torch_pseudo_file(monkeypatch):
    monkeypatch.setattr(torch, '__file__', '<torch pseudo-module>')
    fingerprint = h0_runtime_fingerprint(AutocastSensitiveEncoder(), 'cpu')
    assert fingerprint['encoder_module_sources']
    for key in ('encoder_class_source', 'cache_exporter_source', 'packing_source', 'runtime_binding_source'):
        value = fingerprint[key]; path = Path(value['path'])
        assert path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == value['sha256']
    with pytest.raises(ValueError, match='ordinary physical'):
        physical_source_binding('<not a physical file>')


def test_no_implicit_encoder_floating_dtype_conversion(tmp_path):
    encoder = AutocastSensitiveEncoder().double()
    cache = FrozenH0Cache(tmp_path / 'cache', repository_root=tmp_path / 'repo')
    with pytest.raises(ValueError, match='already be FP32'):
        compute(cache, encoder)
    assert not (tmp_path / 'cache').exists() and encoder.projection.weight.dtype == torch.float64
