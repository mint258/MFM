"""Independent tiny-LMDB transport, coverage and committed-resume oracles.

All structures/labels/identities are synthetic. No full-corpus QA, real target,
Slurm/GPU capacity, aggregate RAM enforcement or formal-run completion is implied.
"""
from copy import deepcopy
import hashlib
import importlib.util
import os
from pathlib import Path
import pickle
import random
import struct
import sys
import time

import lmdb
import pytest
import torch
from rdkit import Chem
from torch_geometric.data import Data

from conftest import small_config
from phychem_mfm.factory import build_model
from phychem_mfm.data.descriptor_schema import RDKIT_GRAPH_DESC_DIM
from phychem_mfm.phase1.data import Phase1ViewDataset
from phychem_mfm.phase1.downstream_readout import SourceAlignedH0Readout
from phychem_mfm.phase1.full_corpus_loader import (
    BlockAtomBatchSampler, CompactNativeIndex, FullCorpusLoaderError,
    FullCorpusViewsDataset, NativeByteLRU, _length_header,
    close_prefetch_iterator, collate_native_views, make_prefetch_loader,
)
from phychem_mfm.phase1.identity import canonical_hash


# This is Data's single shared QA/statistics primitive, not a test copy of its
# grammar. Root binds/deploys this source before the bounded remote CPU suite.
TRANSPORT_PATH = Path(os.environ["PHASE1_NATIVE_TRANSPORT_PATH"]).resolve(strict=True)
sys.path.insert(0, str(TRANSPORT_PATH.parent))  # Importable callback for spawn as well as fork.
_transport_spec = importlib.util.spec_from_file_location(TRANSPORT_PATH.stem, TRANSPORT_PATH)
_transport_module = importlib.util.module_from_spec(_transport_spec)
sys.modules[_transport_spec.name] = _transport_module
_transport_spec.loader.exec_module(_transport_module)
transport_native_record = _transport_module.transport_native_record


def transport_binding():
    return {"policy": _transport_module.MASK_POLICY, "source_sha256": digest(TRANSPORT_PATH.read_bytes())}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def seal(manifest):
    manifest = deepcopy(manifest)
    manifest.pop("content_sha256", None)
    manifest["content_sha256"] = canonical_hash(manifest)
    return manifest


def synthetic_record(smiles, ordinal):
    mol = Chem.AddHs(Chem.MolFromSmiles(smiles))
    n = mol.GetNumAtoms()
    return Data(
        x=torch.tensor([[a.GetAtomicNum() - 1] for a in mol.GetAtoms()], dtype=torch.long),
        pos=torch.arange(n * 3, dtype=torch.float32).reshape(n, 3) / 11 + ordinal / 7,
        y=torch.arange(n, dtype=torch.float32).reshape(n, 1) / 10 + ordinal,
        charge_mask=torch.ones(n, 1), energy=123. + ordinal, energy_unit="kcal/mol",
        energy_mask=torch.ones(1, dtype=torch.bool), sample_key=f"tiny-{ordinal}",
        canonical_smiles=smiles, smiles=smiles,
        rdkit_graph_desc=torch.arange(RDKIT_GRAPH_DESC_DIM, dtype=torch.float32) + ordinal,
        rdkit_graph_desc_mask=torch.ones(RDKIT_GRAPH_DESC_DIM, dtype=torch.bool),
        rdkit_node_mask=torch.ones(n, 1, dtype=torch.bool),
    )


def write_fixture(root, *, smiles=("C", "O", "CC", "CF", "CCCC"), view=None,
                  flags=None, missing=None, role="train", mutate_record=None):
    """Hand '<HHQI' layout; no production index writer is reused by the oracle."""
    records = [synthetic_record(s, i) for i, s in enumerate(smiles)]
    if mutate_record is not None:
        for record in records:
            mutate_record(record)
    groups = [records[:2], records[2:4], records[4:]]
    shards, entries, ordinal = [], [], 0
    for sid, group in enumerate(groups):
        if not group:
            continue
        path = root / f"tiny-{sid}.lmdb"
        header = pickle.dumps(len(group), protocol=4)
        env = lmdb.open(str(path), subdir=False, map_size=8 << 20)
        with env.begin(write=True) as txn:
            txn.put(b"__len__", header)
            for real, record in enumerate(group):
                if ordinal != missing:
                    txn.put(f"{real:09d}".encode(), pickle.dumps(record, protocol=4))
                entries.append((sid, 0 if flags is None else flags[ordinal], real, len(record.x)))
                ordinal += 1
        info, stat = env.info(), env.stat()
        env.close()
        actual = path.stat()
        shards.append({"shard_id": sid, "name": path.name, "path": str(path), "length": len(group),
                       "source_size": actual.st_size, "source_mtime_ns": actual.st_mtime_ns,
                       "len_header_sha256": digest(header), "last_txnid": info["last_txnid"],
                       "entries": stat["entries"]})
    base_path, view_path = root / "base.idx", root / "train.view"
    base_raw = b"".join(struct.pack("<HHQI", *row) for row in entries)
    order = list(range(len(records))) if view is None else list(view)
    view_raw = b"".join(struct.pack("<Q", row) for row in order)
    base_path.write_bytes(base_raw)
    view_path.write_bytes(view_raw)
    manifest = seal({
        "schema_version": "phase1_compact_native_view_v1", "index_schema": "phase1_compact_native_index_v1",
        "atom_encoding": "zero_based", "record_key_format": "09d",
        "quality_and_identity_artifact_sha256": "a" * 64,
        "native_transport": transport_binding(),
        "base_index": {"path": str(base_path), "sha256": digest(base_raw), "bytes": len(base_raw),
                       "rows": len(entries), "format": "<HHQI"},
        "view": {"path": str(view_path), "sha256": digest(view_raw), "bytes": len(view_raw),
                 "rows": len(order), "format": "<Q", "role": role},
        "shards": shards,
    })
    return manifest, records


def open_index(manifest):
    return CompactNativeIndex(manifest, expected_manifest_sha256=manifest["content_sha256"])


def dataset(index, **kwargs):
    return FullCorpusViewsDataset(index, native_transport=transport_native_record,
                                  native_transport_binding=transport_binding(),
                                  seed=19, geometry_level=.2, topology_level=.3,
                                  close_at_block_size=4, **kwargs)


def assert_tensor_fields_equal(left, right, names):
    for name in names:
        a, b = getattr(left, name), getattr(right, name)
        assert a.dtype == b.dtype and a.shape == b.shape
        assert torch.allclose(a, b, equal_nan=True)


def test_hand_native_layout_nontrivial_view_order_and_no_lmdb_constructor(tmp_path, monkeypatch):
    manifest, records = write_fixture(tmp_path, view=[4, 1, 3, 0])
    monkeypatch.setattr("phychem_mfm.phase1.full_corpus_loader.LmdbMoleculeDataset.__init__",
                        lambda *a, **k: pytest.fail("Large index-list constructor called"))
    index = open_index(manifest)
    try:
        assert len(index) == 4
        assert [(index.ref(i).base_row, index.ref(i).real_index) for i in range(4)] == [(4, 0), (1, 1), (3, 1), (0, 0)]
        native = dataset(index)
        result = native[0]
        assert result.base_row == 4 and result.logical_index == 0
        assert result.native_n_atoms == len(records[4].x)
        assert result.record_key == "tiny-2.lmdb:0"
        assert not hasattr(native.normalizer, "idx_list")
        assert_tensor_fields_equal(result.views[0], records[4], ("x", "pos", "y", "charge_mask", "rdkit_graph_desc"))
        assert result.views[0].energy == 127. and bool(result.views[0].energy_mask.all())
        assert result.views[0].canonical_smiles == "CCCC" and result.views[0].sample_key == "tiny-4"
        native.close()
    finally:
        index.close()


@pytest.mark.parametrize("change", ["hash", "role", "format", "stride", "duplicate", "range", "flags", "atoms", "alias", "transport"])
def test_invalid_closed_index_metadata_rejects_before_any_native_read(tmp_path, change):
    manifest, _ = write_fixture(tmp_path)
    if change == "hash":
        manifest["base_index"]["sha256"] = "f" * 64
    elif change == "role":
        manifest["view"]["role"] = "test"
    elif change == "format":
        manifest["base_index"]["format"] = ">HHQI"
    elif change == "stride":
        manifest["base_index"]["bytes"] += 1
    elif change == "transport":
        manifest["native_transport"]["policy"] = "legacy_direct_long_cast"
    elif change in {"duplicate", "range"}:
        raw = b"".join(struct.pack("<Q", x) for x in ([0, 0, 2, 3, 4] if change == "duplicate" else [0, 1, 2, 3, 5]))
        path = tmp_path / "train.view"
        path.write_bytes(raw)
        manifest["view"]["sha256"] = digest(raw)
    else:
        raw = bytearray((tmp_path / "base.idx").read_bytes())
        if change == "alias":
            raw[16:32] = raw[:16]
        else:
            struct.pack_into("<H" if change == "flags" else "<I", raw, 2 if change == "flags" else 12, 1 if change == "flags" else 0)
        (tmp_path / "base.idx").write_bytes(raw)
        manifest["base_index"]["sha256"] = digest(raw)
    manifest = seal(manifest)
    with pytest.raises(FullCorpusLoaderError):
        open_index(manifest)


@pytest.mark.parametrize("filename", ["train.view", "base.idx"])
def test_closed_index_same_size_restored_mtime_mutation_detected_after_open(tmp_path, filename):
    manifest, _ = write_fixture(tmp_path)
    index = open_index(manifest)
    index.close()
    path = tmp_path / filename
    original_stat = path.stat()
    raw = bytearray(path.read_bytes())
    raw[0] ^= 1
    path.write_bytes(raw)
    os.utime(path, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))
    current = path.stat()
    assert current.st_size == original_stat.st_size and current.st_ino == original_stat.st_ino
    assert current.st_mtime_ns == original_stat.st_mtime_ns
    with pytest.raises(FullCorpusLoaderError, match="changed"):
        index.ref(0)
    index.close()


@pytest.mark.parametrize("header", [pickle.dumps(True), pickle.dumps(-1), pickle.dumps(2) + b"x",
                                  pickle.dumps(object()), pickle.dumps(1 << 64)])
def test_integer_only_header_rejects_noninteger_trailing_and_class(header):
    with pytest.raises(FullCorpusLoaderError):
        _length_header(header)


def test_missing_exact_key_never_selects_neighbor(tmp_path):
    manifest, _ = write_fixture(tmp_path, missing=1)
    index = open_index(manifest)
    native = dataset(index)
    try:
        assert native[0].record_key == "tiny-0.lmdb:0"
        with pytest.raises(FullCorpusLoaderError, match="no fallback"):
            native[1]
        assert native[2].record_key == "tiny-1.lmdb:0"
    finally:
        native.close()


def test_cache_byte_and_entry_bounds_lru_and_oversize_bypass():
    cache = NativeByteLRU(6, max_entries=2)
    cache.put("A", b"aaa")
    cache.put("B", b"bb")
    assert cache.get("A") == b"aaa"
    cache.put("C", b"ccc")
    assert cache.get("B") is None and list(cache.entries) == ["A", "C"] and cache.bytes == 6
    cache.put("C", b"0123456")
    assert list(cache.entries) == ["A"] and cache.bytes == 3
    cache.put("D", b"d")
    cache.put("E", b"e")
    assert list(cache.entries) == ["D", "E"] and cache.bytes == 2
    cache.clear()
    assert cache.bytes == 0 and not cache.entries


def test_native_cache_owned_labels_and_global_rng_unchanged(tmp_path):
    manifest, original = write_fixture(tmp_path)
    native = dataset(open_index(manifest), cache_bytes=1 << 20)
    rng, python = torch.get_rng_state().clone(), random.getstate()
    try:
        first = native[0]
        first.views[0].y.fill_(999)
        first.views[0].x.fill_(117)
        first.views[0].pos.fill_(-99)
        second = native[0]
        assert_tensor_fields_equal(second.views[0], original[0], ("x", "pos", "y", "charge_mask", "rdkit_graph_desc"))
        assert native.runtime_stats()["cache_hits"] == 1
        assert native.runtime_stats()["cache_payload_bytes"] <= 1 << 20
        assert torch.equal(torch.get_rng_state(), rng) and random.getstate() == python
    finally:
        native.close()


def test_shared_raw_transport_masks_invalid_tasks_without_discarding_native_row(tmp_path):
    def malformed(record):
        n = len(record.x)
        record.rdkit_node_min_ring_size = torch.full((n, 1), 2.)
        record.rdkit_node_min_ring_size[0] = 1.5  # Must not become class 1 by long().
        record.rdkit_node_donor = torch.zeros(n, 1)
        record.rdkit_node_donor[0] = 2.  # Illegal binary label remains unknown.
        record.rdkit_node_estate_index = torch.ones(n + 1, 1)  # Per-task shape missing.
        record.rdkit_graph_desc[0] = float("nan")
        record.y[0] = float("inf")
    manifest, originals = write_fixture(tmp_path, mutate_record=malformed)
    native = dataset(open_index(manifest))
    try:
        result = native[0].views[0]
        assert len(result.x) == len(originals[0].x)
        assert_tensor_fields_equal(result, originals[0], ("x", "pos"))
        assert result.rdkit_node_min_ring_size[0].item() == -1
        assert bool(result.rdkit_node_min_ring_size[1:].eq(2).all())
        assert bool(torch.isnan(result.rdkit_node_donor[0]).all())
        assert bool(torch.isnan(result.rdkit_node_estate_index).all())
        assert not bool(result.rdkit_graph_desc_mask[0])
        assert not bool(result.charge_mask[0]) and result.y[0].item() == 0.
        assert native[0].views[0].rdkit_node_min_ring_size[0].item() == -1  # Cache unchanged.
    finally:
        native.close()


def test_native_transport_actual_source_and_qa_binding_are_required(tmp_path):
    manifest, _ = write_fixture(tmp_path)
    manifest["native_transport"]["source_sha256"] = "f" * 64
    manifest = seal(manifest)
    index = open_index(manifest)
    try:
        with pytest.raises(FullCorpusLoaderError, match="differs from QA"):
            dataset(index)
        with pytest.raises(FullCorpusLoaderError, match="source bytes differ"):
            FullCorpusViewsDataset(index, native_transport=transport_native_record,
                                   native_transport_binding=manifest["native_transport"],
                                   seed=19, geometry_level=.2, topology_level=.3)
    finally:
        index.close()


def test_qa_accepted_integer_native_encoding_is_owned_long_without_value_change(tmp_path):
    manifest, original = write_fixture(tmp_path, mutate_record=lambda row: setattr(row, "x", row.x.int()))
    native = dataset(open_index(manifest))
    try:
        result = native[0].views[0]
        assert original[0].x.dtype == torch.int32 and result.x.dtype == torch.long
        assert torch.equal(result.x, original[0].x.long())
        assert_tensor_fields_equal(result, original[0], ("pos", "y"))
    finally:
        native.close()


def test_three_views_match_existing_seed_recipe_from_one_native_read(tmp_path, monkeypatch):
    manifest, _ = write_fixture(tmp_path)
    index = open_index(manifest)
    native = dataset(index)
    original_read = native.normalizer._normalize_item
    calls = []
    def counted(item, real):
        calls.append(real)
        return original_read(item, real)
    monkeypatch.setattr(native.normalizer, "_normalize_item", counted)
    class MemoryBase:
        atom_encoding = "zero_based"
        def __len__(self):
            return len(index)
        def __getitem__(self, i):
            return native._native(index.ref(i))
    try:
        actual = native[3]
        assert calls == [1]  # one normalize, not three views' repeated reads.
        for mode, level, got in zip(("clean", "geom", "topo"), (.3, .2, .3), actual.views):
            expected = Phase1ViewDataset(MemoryBase(), mode=mode, level=level, seed=19)[3]
            assert_tensor_fields_equal(got, expected, ("x", "pos", "target_x", "target_pos", "y", "charge_mask",
                                                       "rdkit_graph_desc", "sample_type_id", "element_corrupt_mask"))
            assert got.pretrain_recipe_seed == 22 and got.pretrain_base_key == "tiny-1.lmdb:1"
    finally:
        native.close()


def test_shard_maps_and_block_boundary_close_are_bounded(tmp_path):
    manifest, _ = write_fixture(tmp_path)
    native = dataset(open_index(manifest), max_handles=2, cache_bytes=0)
    try:
        native[0]
        old = native._handles.entries[0]
        native[2]
        assert len(native._handles.entries) == 2
        native[4]  # next logical block closes both maps before third shard.
        assert list(native._handles.entries) == [2]
        with pytest.raises(lmdb.Error):
            old.begin()
        assert native.runtime_stats()["open_shard_maps"] == 1
    finally:
        native.close()


def test_worker_pickle_drops_maps_and_cache(tmp_path):
    manifest, _ = write_fixture(tmp_path)
    native = dataset(open_index(manifest))
    try:
        native[0]
        restored = pickle.loads(pickle.dumps(native))
        assert restored._cache is None and restored._handles is None and restored._pid is None
        assert restored.native_transport is None and restored.normalizer is None
        native.close()
        assert restored[0].record_key == "tiny-0.lmdb:0"
        restored.close()
    finally:
        native.close()


def test_dynamic_parent_only_transport_is_reloaded_by_path_after_pickle(tmp_path):
    manifest, _ = write_fixture(tmp_path)
    name = "phase1_test_transport_parent_only"
    spec = importlib.util.spec_from_file_location(name, TRANSPORT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    index = open_index(manifest)
    native = FullCorpusViewsDataset(index, native_transport=module.transport_native_record,
        native_transport_binding=transport_binding(), seed=19, geometry_level=.2,
        topology_level=.3, close_at_block_size=4)
    restored = None
    try:
        # Python cannot pickle a function from this now-unregistered dynamic
        # module. The dataset must serialize its bound bytes/path, not callable.
        sys.modules.pop(name)
        restored = pickle.loads(pickle.dumps(native))
        assert restored.native_transport is None
        native.close()
        assert restored[0].record_key == "tiny-0.lmdb:0"
        assert restored.native_transport.__module__.startswith("_phase1_bound_native_transport_")
        assert Path(restored.native_transport.__code__.co_filename) == TRANSPORT_PATH
        assert restored.normalizer.strict_index and restored.normalizer.normalize_samples
    finally:
        sys.modules.pop(name, None)
        if restored is not None:
            restored.close()
        native.close()


def test_atom_bucket_epoch_exact_once_natural_domains_partial_and_large_tail(tmp_path):
    manifest, records = write_fixture(tmp_path)
    index = open_index(manifest)
    try:
        sampler = BlockAtomBatchSampler(index, seed=9, block_size=4, max_molecules=3, max_native_atoms=8,
                                       max_padded_cost=10000, padded_cost_multiplier=3)
        state = sampler.state_dict()
        batches = list(sampler)
        assert sampler.state_dict() == state  # enumerating/prefetching is not consumption.
        flattened = [i for batch in batches for i in batch]
        assert sorted(flattened) == list(range(5)) and len(flattened) == len(set(flattened))
        assert sum(index.ref(i).shard_id == 0 for i in flattened) == 2
        assert sum(index.ref(i).shard_id == 1 for i in flattened) == 2
        assert sum(index.ref(i).shard_id == 2 for i in flattened) == 1
        assert any(batch == [4] for batch in batches) and len(records[4].x) > 8
        for batch in batches:
            assert len(batch) <= 3
            assert sum(index.ref(i).native_n_atoms for i in batch) <= 8 or len(batch) == 1
            sampler.commit_batch(batch)
        assert sampler.samples_consumed == 5
        assert list(sampler) == []
        sampler.advance_epoch()
        assert sampler.epoch == 1 and sorted(i for batch in sampler for i in batch) == list(range(5))
    finally:
        index.close()


def test_committed_resume_discards_prefetch_and_matches_uninterrupted_remainder(tmp_path):
    manifest, _ = write_fixture(tmp_path)
    index = open_index(manifest)
    try:
        args = dict(seed=28, block_size=4, max_molecules=2, max_native_atoms=20,
                    max_padded_cost=10000, padded_cost_multiplier=3)
        source = BlockAtomBatchSampler(index, **args)
        expected = list(source)
        iterator = iter(source)
        first = next(iterator)
        next(iterator)  # prefetched but never consumed.
        source.commit_batch(first)
        checkpoint = source.state_dict()
        resumed = BlockAtomBatchSampler(index, **args)
        resumed.load_state_dict(checkpoint)
        assert resumed.state_dict() == checkpoint
        assert list(resumed) == expected[1:]
        assert source.state_dict() == checkpoint
    finally:
        index.close()


def test_padded_cost_splits_batch_even_when_sum_atoms_allows_it_and_keeps_tail(tmp_path):
    manifest, _ = write_fixture(tmp_path)
    index = open_index(manifest)
    try:
        sampler = BlockAtomBatchSampler(index, seed=7, block_size=5, max_molecules=5,
                                       max_native_atoms=999, atom_bucket_width=1,
                                       max_padded_cost=300, padded_cost_multiplier=3)
        batches = list(sampler)
        assert [len(batch) for batch in batches] == [3, 1, 1]
        assert set(batches[0]) == {0, 1, 3}  # native N=5,3,5; 3*3*5^2=225.
        assert batches[1] == [2]  # adding N=8 would cost 3*4*8^2=768 >300, despite sum 21<999.
        assert batches[2] == [4]  # N=14 singleton cost588 reported, never removed.
        assert sorted(i for batch in batches for i in batch) == list(range(5))
    finally:
        index.close()


@pytest.mark.parametrize("tamper", ["samples_consumed", "batches_consumed", "item_offset", "epoch", "contract_sha256"])
def test_resealed_invalid_sampler_resume_rejects_atomically(tmp_path, tamper):
    manifest, _ = write_fixture(tmp_path)
    index = open_index(manifest)
    sampler = BlockAtomBatchSampler(index, seed=5, block_size=4, max_molecules=2, max_native_atoms=100,
                                   max_padded_cost=10000, padded_cost_multiplier=3)
    try:
        original = sampler.state_dict()
        corrupt = deepcopy(original)
        corrupt[tamper] = "f" * 64 if tamper == "contract_sha256" else corrupt[tamper] + 1
        corrupt.pop("content_sha256")
        corrupt["content_sha256"] = canonical_hash(corrupt)
        with pytest.raises(FullCorpusLoaderError):
            sampler.load_state_dict(corrupt)
        assert sampler.state_dict() == original
    finally:
        index.close()


def test_reject_wrong_consume_and_incomplete_epoch_advance(tmp_path):
    manifest, _ = write_fixture(tmp_path)
    index = open_index(manifest)
    sampler = BlockAtomBatchSampler(index, seed=5, block_size=4, max_molecules=3, max_native_atoms=100,
                                   max_padded_cost=10000, padded_cost_multiplier=3)
    try:
        initial = sampler.state_dict()
        with pytest.raises(FullCorpusLoaderError):
            sampler.commit_batch([999])
        with pytest.raises(FullCorpusLoaderError):
            sampler.advance_epoch()
        assert sampler.state_dict() == initial
    finally:
        index.close()


def test_cpu_loader_actual_prefetch_contract_and_rng_preservation(tmp_path):
    manifest, _ = write_fixture(tmp_path)
    index = open_index(manifest)
    native = dataset(index)
    sampler = BlockAtomBatchSampler(index, seed=19, block_size=4, max_molecules=2, max_native_atoms=100,
                                   max_padded_cost=10000, padded_cost_multiplier=3)
    rng = torch.get_rng_state().clone()
    try:
        loader = make_prefetch_loader(native, sampler, num_workers=0, pin_memory=False)
        batches = list(loader)
        assert sorted(i for batch in batches for i in batch.logical_indices) == list(range(5))
        assert all(batch.encoder_batch.num_graphs == 3 * len(batch.logical_indices) for batch in batches)
        assert sampler.samples_consumed == 0
        assert torch.equal(torch.get_rng_state(), rng)
        for batch in batches:
            sampler.commit_batch(batch.logical_indices)
        assert sampler.samples_consumed == 5
    finally:
        native.close()


@pytest.mark.parametrize("partial", [False, True])
def test_actual_spawn_workers_prefetch_retains_exact_ids_and_committed_cursor(tmp_path, partial):
    manifest, _ = write_fixture(tmp_path)
    index = open_index(manifest)
    native = dataset(index, cache_bytes=1 << 20)
    sampler = BlockAtomBatchSampler(index, seed=19, block_size=4, max_molecules=2, max_native_atoms=100,
                                   max_padded_cost=10000, padded_cost_multiplier=3)
    expected = list(sampler)
    rng = torch.get_rng_state().clone()
    iterator = None
    workers = []
    try:
        # Exercise the relevant ordering: initialize CPU Torch work first, then
        # create fresh workers. This is not a stack diagnosis of the old hang.
        torch.ones(8, 8).matmul(torch.ones(8, 8))
        loader = make_prefetch_loader(native, sampler, num_workers=2, prefetch_factor=2,
                                      pin_memory=False, persistent_workers=False,
                                      worker_timeout_seconds=45.)
        assert loader.multiprocessing_context.get_start_method() == "spawn" and loader.timeout == 45.
        iterator = iter(loader)
        workers = list(iterator._workers)
        first = next(iterator)
        assert first.logical_indices == tuple(expected[0])
        actual = [first.logical_indices]
        if not partial:
            actual.extend(batch.logical_indices for batch in iterator)
            assert actual == [tuple(batch) for batch in expected]
        else:
            # Some later rows may be prefetched, but the scientific cursor is
            # still zero until the one returned row is explicitly committed.
            assert sampler.samples_consumed == 0
        assert torch.equal(torch.get_rng_state(), rng)
        sampler.commit_batch(actual[0])
        resumed = BlockAtomBatchSampler(index, seed=19, block_size=4, max_molecules=2, max_native_atoms=100,
                                       max_padded_cost=10000, padded_cost_multiplier=3)
        resumed.load_state_dict(sampler.state_dict())
        assert list(resumed) == expected[1:]
    finally:
        if iterator is not None:
            close_prefetch_iterator(iterator)
            close_prefetch_iterator(iterator)  # cleanup is safe after exhaustion.
        native.close()
    assert workers and all(not worker.is_alive() for worker in workers)


class _SlowNativeDataset(FullCorpusViewsDataset):
    def __getitem__(self, logical_index):
        time.sleep(10.)
        return super().__getitem__(logical_index)


def test_actual_spawn_timeout_releases_owned_workers_without_committing(tmp_path):
    manifest, _ = write_fixture(tmp_path)
    index = open_index(manifest)
    native = _SlowNativeDataset(index, native_transport=transport_native_record,
        native_transport_binding=transport_binding(), seed=19, geometry_level=.2,
        topology_level=.3, close_at_block_size=4)
    sampler = BlockAtomBatchSampler(index, seed=19, block_size=4, max_molecules=2,
        max_native_atoms=100, max_padded_cost=10000, padded_cost_multiplier=3)
    before = sampler.state_dict()
    iterator = None
    workers = []
    try:
        loader = make_prefetch_loader(native, sampler, num_workers=1, pin_memory=False,
                                      worker_timeout_seconds=1.)
        iterator = iter(loader)
        workers = list(iterator._workers)
        with pytest.raises(RuntimeError, match="timed out"):
            next(iterator)
        assert sampler.state_dict() == before
    finally:
        if iterator is not None:
            close_started = time.monotonic()
            close_prefetch_iterator(iterator, timeout_seconds=8.)
            assert time.monotonic() - close_started <= 8.5
        native.close()
    assert workers and all(not worker.is_alive() for worker in workers)


def test_actual_spawn_native_failure_releases_workers_without_committing(tmp_path):
    manifest, _ = write_fixture(tmp_path, missing=1)
    index = open_index(manifest)
    native = dataset(index)
    sampler = BlockAtomBatchSampler(index, seed=19, block_size=4, max_molecules=2,
        max_native_atoms=100, max_padded_cost=10000, padded_cost_multiplier=3)
    iterator = None
    workers = []
    try:
        loader = make_prefetch_loader(native, sampler, num_workers=2, pin_memory=False,
                                      worker_timeout_seconds=45.)
        iterator = iter(loader)
        workers = list(iterator._workers)
        with pytest.raises(FullCorpusLoaderError, match="no fallback"):
            list(iterator)
        assert sampler.samples_consumed == 0 and sampler.batches_consumed == 0
    finally:
        if iterator is not None:
            close_prefetch_iterator(iterator)
        native.close()
    assert workers and all(not worker.is_alive() for worker in workers)


@pytest.mark.parametrize("timeout", [0., float("nan"), 601.])
def test_invalid_worker_timeout_rejects_before_spawning(tmp_path, timeout):
    manifest, _ = write_fixture(tmp_path)
    native = dataset(open_index(manifest))
    sampler = BlockAtomBatchSampler(native.index, seed=19, block_size=4, max_molecules=2,
        max_native_atoms=100, max_padded_cost=10000, padded_cost_multiplier=3)
    try:
        with pytest.raises(FullCorpusLoaderError, match="timeout"):
            make_prefetch_loader(native, sampler, num_workers=2, worker_timeout_seconds=timeout)
    finally:
        native.close()


def test_real_tiny_shared_h0_and_native_readout_preserve_native_rows(tmp_path):
    manifest, _ = write_fixture(tmp_path)
    native = dataset(open_index(manifest))
    try:
        packed = collate_native_views([native[0], native[1]])
        batch = packed.encoder_batch
        with torch.random.fork_rng(devices=[]):
            torch.manual_seed(71)
            cfg = small_config("expert")
            cfg["backbone"].update(dim=8, layers=1, heads=2, dropout=0.)
            cfg["expert"]["heads"] = 2
            cfg["head"]["profile"] = "phase1"
            model = build_model(cfg).eval()
            readout = SourceAlignedH0Readout(8, 1, output_level="atom", hidden_dim=8).eval()
            source_ids = torch.cat([torch.arange(int(end - start)) for start, end in zip(batch.ptr[:-1], batch.ptr[1:])])
            safe = Data(x=batch.x.view(-1), pos=batch.pos, batch=batch.batch, ptr=batch.ptr)
            with torch.no_grad():
                h0 = model.encode_atoms(safe)
                output = readout(h0, source_atom_ids=source_ids, batch=batch.batch, ptr=batch.ptr)
        assert h0.shape == (sum(packed.native_atom_counts) * 3, 8)
        assert output.predictions.shape == (h0.size(0), 1)
        assert torch.equal(output.source_atom_ids, source_ids)
        assert packed.record_keys == ("tiny-0.lmdb:0", "tiny-0.lmdb:1")
    finally:
        native.close()
