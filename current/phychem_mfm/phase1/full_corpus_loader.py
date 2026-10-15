"""Draft compact-index loader: exact native reads, bounded transports, explicit cursors.

This module consumes future closed QA/split metadata and the same bound label
transport used by QA/statistics. It neither qualifies the whole corpus nor writes
source labels, group assignments or any frozen training recipe.
LMDB mmap pages, transient unpickles and DataLoader queues are outside the native
byte-cache cap; a caller must monitor the entire process group under its RAM cap.
"""
from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import inspect
import io
import math
import mmap
import os
from pathlib import Path
import pickle
import random
import struct
import sys
import threading
import time
from types import ModuleType
from multiprocessing.process import BaseProcess
from typing import Mapping

import lmdb
import torch
from torch.utils.data import DataLoader, Dataset, Sampler

from ..data.dataset_lmdb import LmdbMoleculeDataset
from ..data.descriptor_schema import RDKIT_GRAPH_DESC_DIM
from ..training.data import fast_collate
from ..training.degrade_molecules import DegradeConfig, degrade_once
from .identity import canonical_hash


INDEX_SCHEMA = "phase1_compact_native_index_v1"
VIEW_SCHEMA = "phase1_compact_native_view_v1"
SAMPLER_SCHEMA = "phase1_block_atom_sampler_v1"
NATIVE_TRANSPORT_POLICY = "phase1_native_finite_domain_mask_transport_v2"
INDEX_STRUCT = struct.Struct("<HHQI")
VIEW_STRUCT = struct.Struct("<Q")
MAX_NATIVE_INVENTORY_ROWS = (2 << 30) // INDEX_STRUCT.size


class FullCorpusLoaderError(RuntimeError):
    pass


def _require(condition, message):
    if not condition:
        raise FullCorpusLoaderError(message)


def _integer(value, name, *, minimum=0, maximum=None):
    _require(type(value) is int and value >= minimum, f"Invalid {name}")
    _require(maximum is None or value <= maximum, f"Invalid {name}")
    return value


def _sha(value):
    _require(type(value) is str and len(value) == 64
             and all(c in "0123456789abcdef" for c in value), "Invalid SHA256")
    return value


def _digest_file(path):
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        while raw := stream.read(1 << 20):
            hasher.update(raw)
    return hasher.hexdigest()


def _strict_normalizer():
    normalizer = LmdbMoleculeDataset.__new__(LmdbMoleculeDataset)
    normalizer.normalize_samples = True
    normalizer.strict_index = True
    normalizer._key_fmt = "09d"
    return normalizer


def _load_bound_native_transport(path, binding, identity):
    """Reload an external, byte-bound function without pickling its module name.

    A spawned worker need not have the parent's dynamically imported module in
    sys.modules or sys.path. The source is trusted only through the manifest's
    actual byte hash; no alternate source or legacy transport is substituted.
    compile/exec avoids writing a __pycache__ next to external evidence files.
    """
    stat = path.stat()
    _require((stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns) == identity,
             "Native transport source changed before worker reload")
    _require(0 < stat.st_size <= 1 << 20 and not path.is_symlink(),
             "Unsafe native transport source")
    with path.open("rb") as stream:
        raw = stream.read((1 << 20) + 1)
    _require(len(raw) == stat.st_size and hashlib.sha256(raw).hexdigest() == binding["source_sha256"],
             "Native transport source bytes differ before worker reload")
    name = "_phase1_bound_native_transport_" + binding["source_sha256"]
    module = ModuleType(name)
    module.__file__ = str(path)
    sys.modules[name] = module
    try:
        exec(compile(raw, str(path), "exec"), module.__dict__)
        function = getattr(module, "transport_native_record", None)
        _require(getattr(module, "MASK_POLICY", None) == binding["policy"]
                 and inspect.isfunction(function)
                 and function.__name__ == "transport_native_record"
                 and inspect.getsourcefile(function) == str(path),
                 "Reloaded native transport public contract differs")
        current = path.stat()
        _require((current.st_dev, current.st_ino, current.st_size, current.st_mtime_ns) == identity
                 and _digest_file(path) == binding["source_sha256"],
                 "Native transport changed during worker reload")
        return function
    except BaseException:
        sys.modules.pop(name, None)
        raise


class _IntegerHeaderUnpickler(pickle.Unpickler):
    def find_class(self, module, name):
        raise FullCorpusLoaderError("LMDB length header contains a class")


def _length_header(raw):
    _require(isinstance(raw, bytes) and 0 < len(raw) <= 4096,
             "Missing or oversized LMDB length header")
    stream = io.BytesIO(raw)
    try:
        result = _IntegerHeaderUnpickler(stream).load()
    except FullCorpusLoaderError:
        raise
    except Exception as exc:
        raise FullCorpusLoaderError("Invalid LMDB length header") from exc
    _require(stream.tell() == len(raw), "Trailing LMDB length-header bytes")
    return _integer(result, "LMDB length", minimum=1, maximum=MAX_NATIVE_INVENTORY_ROWS)


class _MappedFile:
    """Open only after one parent hash verification; workers retain actual fstat."""
    def __init__(self, binding, stride):
        _require(set(binding) == {"path", "sha256", "bytes", "rows", "format"},
                 "Invalid compact-file binding")
        original = Path(binding["path"])
        _require(not original.is_symlink(), "Unsafe compact file")
        self.path = original.resolve(strict=True)
        _require(self.path.is_file(), "Unsafe compact file")
        self.binding = deepcopy(binding)
        _sha(binding["sha256"])
        _integer(binding["rows"], "compact rows", minimum=1)
        _require(binding["bytes"] == binding["rows"] * stride, "Compact stride/length differs")
        _require(binding["bytes"] <= 2 << 30, "Compact file exceeds metadata cap")
        stat = self.path.stat()
        _require(stat.st_size == binding["bytes"]
                 and _digest_file(self.path) == binding["sha256"], "Compact file bytes differ")
        self._identity = (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns)
        self._stream = self._map = None
        self._pid = None

    def _ensure(self):
        if self._pid != os.getpid():
            self.close()
        if self._map is None:
            stream = self.path.open("rb")
            try:
                stat = os.fstat(stream.fileno())
                _require((stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns) == self._identity,
                         "Compact file replaced or changed")
                # Same-size writes can retain/coarsely alias mtime. Check the
                # exact opened descriptor's bytes on every real map reopen.
                hasher = hashlib.sha256()
                while raw := stream.read(1 << 20):
                    hasher.update(raw)
                current = os.fstat(stream.fileno())
                _require(hasher.hexdigest() == self.binding["sha256"]
                         and (current.st_dev, current.st_ino, current.st_size, current.st_mtime_ns) == self._identity,
                         "Compact file bytes changed on reopen")
                stream.seek(0)
                mapped = mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ)
            except BaseException:
                stream.close()
                raise
            self._stream = stream
            self._map = mapped
            self._pid = os.getpid()
        return self._map

    def close(self):
        if self._map is not None:
            self._map.close()
        if self._stream is not None:
            self._stream.close()
        self._stream = self._map = self._pid = None

    def __getstate__(self):
        state = self.__dict__.copy()
        state.update(_stream=None, _map=None, _pid=None)
        return state

    def verify_unchanged(self):
        stat = self.path.stat()
        _require((stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns) == self._identity
                 and _digest_file(self.path) == self.binding["sha256"], "Compact file changed")


@dataclass(frozen=True)
class NativeRef:
    logical_index: int
    base_row: int
    shard_id: int
    real_index: int
    native_n_atoms: int


class CompactNativeIndex:
    """mmap-backed records and role view; no list(range(N)) or identity dictionary."""
    def __init__(self, manifest: Mapping, *, expected_manifest_sha256: str):
        self.manifest = deepcopy(dict(manifest))
        _require(set(self.manifest) == {
            "schema_version", "index_schema", "atom_encoding", "record_key_format",
            "quality_and_identity_artifact_sha256", "native_transport", "base_index", "view", "shards",
            "content_sha256"}, "Invalid compact manifest fields")
        seal = self.manifest.pop("content_sha256")
        _require(_sha(seal) == _sha(expected_manifest_sha256)
                 and canonical_hash(self.manifest) == seal, "Compact manifest seal differs")
        self.manifest["content_sha256"] = seal
        _require(self.manifest["schema_version"] == VIEW_SCHEMA
                 and self.manifest["index_schema"] == INDEX_SCHEMA
                 and self.manifest["atom_encoding"] == "zero_based"
                 and self.manifest["record_key_format"] == "09d", "Unsupported compact schema")
        _sha(self.manifest["quality_and_identity_artifact_sha256"])
        transport = self.manifest["native_transport"]
        _require(type(transport) is dict and set(transport) == {"policy", "source_sha256"}
                 and transport["policy"] == NATIVE_TRANSPORT_POLICY, "Unknown native label transport")
        _sha(transport["source_sha256"])
        base = self.manifest["base_index"]
        view = deepcopy(self.manifest["view"])
        _require(base.get("format") == "<HHQI" and view.pop("role", None)
                 in {"train", "validation"} and view.get("format") == "<Q",
                 "Explicit supported compact formats/role required")
        self.base = _MappedFile(base, INDEX_STRUCT.size)
        self.view = _MappedFile(view, VIEW_STRUCT.size)
        self.role = self.manifest["view"]["role"]
        self.content_sha256 = seal
        self.shards = {}
        _require(type(self.manifest["shards"]) is list and 0 < len(self.manifest["shards"]) <= 64,
                 "Invalid clean shard inventory")
        for shard in self.manifest["shards"]:
            _require(set(shard) == {"shard_id", "name", "path", "length", "source_size",
                                   "source_mtime_ns", "len_header_sha256", "last_txnid", "entries"},
                     "Invalid shard binding")
            sid = _integer(shard["shard_id"], "shard ID", maximum=65535)
            _require(sid not in self.shards, "Duplicate shard ID")
            for name in ("length", "source_size", "source_mtime_ns", "entries"):
                _integer(shard[name], name, minimum=1)
            _integer(shard["last_txnid"], "last transaction")
            _sha(shard["len_header_sha256"])
            original = Path(shard["path"])
            _require(not original.is_symlink(), "Invalid single-file shard path")
            path = original.resolve(strict=True)
            _require(path.is_file() and path.name == shard["name"],
                     "Invalid single-file shard path")
            self.shards[sid] = dict(shard, path=str(path))
        # A 16M-row membership proof needs ~2 MiB bitmap, never 16M Python ints.
        # This reads compact metadata only; it does not open/decode any LMDB row.
        offsets, source_rows = {}, 0
        # Only bounded header transactions; source length is not a caller's huge
        # integer that could force an unbounded membership bitmap allocation.
        checks = _ShardHandles(self.shards, max_handles=1)
        try:
            for sid in sorted(self.shards):
                checks.get(sid)
        finally:
            checks.close()
        for sid in sorted(self.shards):
            offsets[sid] = source_rows
            source_rows += self.shards[sid]["length"]
        _require(source_rows <= MAX_NATIVE_INVENTORY_ROWS,
                 "Native source inventory exceeds compact metadata row cap")
        _require(base["rows"] <= source_rows, "Base index exceeds native source inventory")
        seen = bytearray((base["rows"] + 7) // 8)
        seen_source = bytearray((source_rows + 7) // 8)
        try:
            for logical in range(view["rows"]):
                ref = self.ref(logical)
                slot, bit = divmod(ref.base_row, 8)
                _require(not (seen[slot] & (1 << bit)), "Duplicate compact-view membership")
                seen[slot] |= 1 << bit
                slot, bit = divmod(offsets[ref.shard_id] + ref.real_index, 8)
                _require(not (seen_source[slot] & (1 << bit)), "Duplicate physical native reference")
                seen_source[slot] |= 1 << bit
        finally:
            self.close()

    def __len__(self):
        return self.view.binding["rows"]

    def ref(self, logical_index):
        logical_index = _integer(logical_index, "logical index")
        _require(logical_index < len(self), "Logical index out of range")
        base_row, = VIEW_STRUCT.unpack_from(self.view._ensure(), logical_index * VIEW_STRUCT.size)
        _require(base_row < self.base.binding["rows"], "View base-row index out of range")
        sid, flags, real, atoms = INDEX_STRUCT.unpack_from(self.base._ensure(), base_row * INDEX_STRUCT.size)
        _require(flags == 0, "Unknown compact flags")
        _require(sid in self.shards and real < self.shards[sid]["length"] and atoms > 0,
                 "Invalid native compact reference")
        return NativeRef(logical_index, base_row, sid, real, atoms)

    def close(self):
        self.base.close()
        self.view.close()

    def verify_unchanged(self):
        self.base.verify_unchanged()
        self.view.verify_unchanged()
        self.verify_shard_stats()

    def verify_shard_stats(self):
        for shard in self.shards.values():
            stat = Path(shard["path"]).stat()
            _require(stat.st_size == shard["source_size"] and stat.st_mtime_ns == shard["source_mtime_ns"],
                     "LMDB source stat changed")


class NativeByteLRU:
    """Immutable normalized-pickle bytes; cap excludes Python table/temporary data."""
    def __init__(self, max_bytes, *, max_entries=65536):
        self.max_bytes = _integer(max_bytes, "cache bytes")
        self.max_entries = _integer(max_entries, "cache entries", minimum=1)
        self.entries = OrderedDict()
        self.bytes = self.hits = self.misses = 0

    def get(self, key):
        value = self.entries.pop(key, None)
        if value is None:
            self.misses += 1
            return None
        self.entries[key] = value
        self.hits += 1
        return value

    def put(self, key, value):
        _require(type(value) is bytes, "Cache owns immutable bytes only")
        old = self.entries.pop(key, None)
        if old is not None:
            self.bytes -= len(old)
        if len(value) > self.max_bytes or self.max_bytes == 0:
            return
        while self.entries and (self.bytes + len(value) > self.max_bytes
                                or len(self.entries) >= self.max_entries):
            _, removed = self.entries.popitem(last=False)
            self.bytes -= len(removed)
        self.entries[key] = value
        self.bytes += len(value)

    def clear(self):
        self.entries.clear()
        self.bytes = 0


class _ShardHandles:
    def __init__(self, shards, *, max_handles):
        self.shards = shards
        self.max_handles = _integer(max_handles, "open shard handles", minimum=1, maximum=3)
        self.entries = OrderedDict()
        self.pid = os.getpid()

    def _check_pid(self):
        if self.pid != os.getpid():
            self.close()
            self.pid = os.getpid()

    def get(self, sid):
        self._check_pid()
        if sid in self.entries:
            value = self.entries.pop(sid)
            self.entries[sid] = value
            return value
        shard = self.shards[sid]
        path = Path(shard["path"])
        stat = path.stat()
        _require(stat.st_size == shard["source_size"] and stat.st_mtime_ns == shard["source_mtime_ns"],
                 "LMDB source stat changed")
        # Evict before opening the next map, so even transient handle count is bounded.
        while len(self.entries) >= self.max_handles:
            _, previous = self.entries.popitem(last=False)
            previous.close()
        env = lmdb.open(str(path), subdir=False, readonly=True, lock=False,
                        readahead=False, meminit=False, max_readers=256)
        try:
            with env.begin() as txn:
                raw = txn.get(b"__len__")
                _require(_length_header(raw) == shard["length"]
                         and hashlib.sha256(raw).hexdigest() == shard["len_header_sha256"],
                         "LMDB length header changed")
                _require(txn.stat()["entries"] == shard["entries"], "LMDB entry count changed")
            _require(env.info()["last_txnid"] == shard["last_txnid"], "LMDB transaction changed")
        except BaseException:
            env.close()
            raise
        self.entries[sid] = env
        return env

    def close(self):
        for env in self.entries.values():
            env.close()
        self.entries.clear()


@dataclass(frozen=True)
class NativeViews:
    logical_index: int
    base_row: int
    record_key: str
    native_n_atoms: int
    views: tuple


class FullCorpusViewsDataset(Dataset):
    """Read and normalize a native record once, then create owned clean/geom/topo."""
    def __init__(self, index: CompactNativeIndex, *, native_transport, native_transport_binding,
                 seed, geometry_level, topology_level,
                 cache_bytes=1 << 30, max_cache_entries=65536, max_handles=2,
                 close_at_block_size=4096, max_record_bytes=64 << 20):
        self.index = index
        _require(type(native_transport_binding) is dict
                 and native_transport_binding == index.manifest["native_transport"],
                 "Native label transport differs from QA/view binding")
        _require(inspect.isfunction(native_transport)
                 and native_transport.__name__ == "transport_native_record",
                 "Bound public native transport function required")
        self.native_transport = native_transport
        self.native_transport_binding = deepcopy(native_transport_binding)
        source = inspect.getsourcefile(native_transport)
        _require(source is not None, "Native transport source is unavailable")
        original = Path(source)
        _require(not original.is_symlink(), "Unsafe native transport source")
        self._transport_path = original.resolve(strict=True)
        stat = self._transport_path.stat()
        _require(0 < stat.st_size <= 1 << 20
                 and _digest_file(self._transport_path) == native_transport_binding["source_sha256"],
                 "Native transport source bytes differ")
        module = inspect.getmodule(native_transport)
        _require(getattr(module, "MASK_POLICY", None) == native_transport_binding["policy"],
                 "Native transport module policy differs")
        self._transport_identity = (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns)
        self.seed = _integer(seed, "view seed", maximum=(1 << 63) - len(index))
        self.block_size = _integer(close_at_block_size, "close-map block size", minimum=1)
        self.max_record_bytes = _integer(max_record_bytes, "native record bytes", minimum=1)
        self.cache_bytes = _integer(cache_bytes, "cache bytes")
        self.max_cache_entries = _integer(max_cache_entries, "cache entries", minimum=1)
        self.max_handles = _integer(max_handles, "handles", minimum=1, maximum=3)
        self.cfgs = []
        for mode, level in (("clean", topology_level), ("geom", geometry_level), ("topo", topology_level)):
            _require(type(level) in (int, float) and math.isfinite(level) and level >= 0,
                     "Invalid degradation level")
            self.cfgs.append(DegradeConfig(mode=mode, level=float(level), atom_encoding="zero_based",
                            topo_delete_frac=0., geom_angle_std_deg=0., geom_bond_scale_std=0.).finalize())
        # QA's public transport validates source domains BEFORE the shared strict
        # normalizer's casts. Never silently substitute legacy direct normalization.
        self.normalizer = _strict_normalizer()
        self._cache = self._handles = None
        self._pid = self._block = None

    def __len__(self):
        return len(self.index)

    def _ensure_worker(self, logical_index):
        if self._pid != os.getpid():
            self.close()
            if self.native_transport is None:
                self.native_transport = _load_bound_native_transport(
                    self._transport_path, self.native_transport_binding, self._transport_identity)
            if self.normalizer is None:
                self.normalizer = _strict_normalizer()
            self._cache = NativeByteLRU(self.cache_bytes, max_entries=self.max_cache_entries)
            self._handles = _ShardHandles(self.index.shards, max_handles=self.max_handles)
            self._pid = os.getpid()
        block = logical_index // self.block_size
        if self._block != block:
            stat = self._transport_path.stat()
            _require((stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns) == self._transport_identity,
                     "Native transport source changed")
            self.index.verify_shard_stats()
            self._handles.close()  # release prior maps/resident pages, retain only byte cache.
        self._block = block

    def _native(self, ref):
        self._ensure_worker(ref.logical_index)
        key = (ref.shard_id, ref.real_index)
        cached = self._cache.get(key)
        if cached is None:
            with self._handles.get(ref.shard_id).begin() as txn:
                raw = txn.get(f"{ref.real_index:09d}".encode("ascii"))
            _require(raw is not None, "Exact LMDB record is missing; no fallback allowed")
            _require(len(raw) <= self.max_record_bytes, "Native serialized record exceeds declared cap")
            record = self.native_transport(pickle.loads(raw), real_index=ref.real_index,
                                           normalizer=self.normalizer)
            self._validate_native(record, ref)
            cached = pickle.dumps(record, protocol=pickle.HIGHEST_PROTOCOL)
            _require(len(cached) <= self.max_record_bytes, "Normalized native record exceeds declared cap")
            self._cache.put(key, cached)
        record = pickle.loads(cached)
        self._validate_native(record, ref)
        record.phase1_record_key = f"{self.index.shards[ref.shard_id]['name']}:{ref.real_index}"
        record.phase1_pool_hash = self.index.content_sha256
        record.phase1_atom_encoding = "zero_based"
        record.phase1_native_transport_sha256 = self.native_transport_binding["source_sha256"]
        # PyG auto-increments fields containing 'index' when batching graphs.
        record.phase1_logical_ordinal = ref.logical_index
        record.phase1_base_row = ref.base_row
        return record

    @staticmethod
    def _validate_native(record, ref):
        x, pos = getattr(record, "x", None), getattr(record, "pos", None)
        _require(isinstance(x, torch.Tensor) and x.device.type == "cpu"
                 and x.dtype == torch.long and tuple(x.shape) == (ref.native_n_atoms, 1)
                 and bool(((x >= 0) & (x <= 117)).all()), "Native atom encoding/count differs")
        _require(isinstance(pos, torch.Tensor) and pos.device.type == "cpu"
                 and tuple(pos.shape) == (ref.native_n_atoms, 3) and bool(torch.isfinite(pos).all()),
                 "Native coordinate count/finiteness differs")
        _require(tuple(record.y.shape) == (ref.native_n_atoms, 1)
                 and tuple(record.charge_mask.shape) == (ref.native_n_atoms, 1),
                 "Native charge correspondence differs")
        valid = record.charge_mask.bool()
        _require(bool(torch.isfinite(record.y[valid]).all()), "Non-finite valid charge labels")
        record.y = torch.where(valid, record.y, torch.zeros_like(record.y))
        graph, mask = record.rdkit_graph_desc, record.rdkit_graph_desc_mask.bool()
        _require(graph.numel() == RDKIT_GRAPH_DESC_DIM and mask.shape == graph.shape
                 and bool(torch.isfinite(graph[mask]).all()), "Graph descriptor correspondence differs")
        record.rdkit_graph_desc = torch.where(mask, graph, torch.zeros_like(graph))
        if str(getattr(record, "energy_unit", "")) != "kcal/mol":
            record.energy_mask = torch.zeros(1, dtype=torch.bool)

    def __getitem__(self, logical_index):
        ref = self.index.ref(logical_index)
        clean = self._native(ref)
        views = []
        for cfg in self.cfgs:
            source = deepcopy(clean)
            clean_x, clean_pos = source.x.clone(), source.pos.clone()
            generator = torch.Generator(device="cpu").manual_seed(self.seed + ref.logical_index)
            result = degrade_once(source, cfg, generator)
            result.target_x, result.target_pos = clean_x, clean_pos
            result.sample_type_id = torch.tensor([{"clean": 0, "geom": 1, "topo": 2}[cfg.mode]])
            result.pretrain_base_key = clean.phase1_record_key
            result.pretrain_recipe_name = f"{cfg.mode}:{float(cfg.level):g}"
            result.pretrain_recipe_level = float(cfg.level)
            result.pretrain_recipe_seed = self.seed + ref.logical_index
            for name in ("trajectory", "is_feasible", "neg_type"):
                if hasattr(result, name):
                    delattr(result, name)
            _require(torch.equal(result.x.ne(clean_x).any(dim=1),
                                 result.element_corrupt_mask.view(-1)), "Corruption mask differs")
            views.append(result)
        return NativeViews(ref.logical_index, ref.base_row, clean.phase1_record_key,
                           ref.native_n_atoms, tuple(views))

    def close(self):
        if self._handles is not None:
            self._handles.close()
        if self._cache is not None:
            self._cache.clear()
        self.index.close()
        self._cache = self._handles = self._pid = self._block = None

    def __getstate__(self):
        state = self.__dict__.copy()
        # External transport may have been imported under an arbitrary dynamic
        # name, unavailable in a fresh spawn. Serialize only its actual binding.
        state.update(_cache=None, _handles=None, _pid=None, _block=None,
                     native_transport=None, normalizer=None)
        return state

    def verify_unchanged(self):
        self.index.verify_unchanged()
        stat = self._transport_path.stat()
        _require((stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns) == self._transport_identity
                 and _digest_file(self._transport_path) == self.native_transport_binding["source_sha256"],
                 "Native transport source changed")

    def runtime_stats(self):
        return {"pid": os.getpid(), "cache_payload_bytes": self._cache.bytes if self._cache else 0,
                "cache_entries": len(self._cache.entries) if self._cache else 0,
                "cache_hits": self._cache.hits if self._cache else 0,
                "cache_misses": self._cache.misses if self._cache else 0,
                "open_shard_maps": len(self._handles.entries) if self._handles else 0,
                "memory": process_memory_observation()}


def process_memory_observation():
    """Current Linux-process RSS/PSS only, not total worker group or cgroup proof."""
    result = {"scope": "current_process_only", "pid": os.getpid(),
              "rss_bytes": None, "pss_bytes": None, "rss_anon_bytes": None, "rss_file_bytes": None}
    for filename, fields in (("status", {"VmRSS": "rss_bytes", "RssAnon": "rss_anon_bytes",
                                         "RssFile": "rss_file_bytes"}),
                             ("smaps_rollup", {"Pss": "pss_bytes"})):
        try:
            with Path(f"/proc/self/{filename}").open("r", encoding="ascii") as stream:
                for line in stream:
                    key, _, value = line.partition(":")
                    if key in fields:
                        parts = value.split()
                        if len(parts) == 2 and parts[1] == "kB" and parts[0].isdigit():
                            result[fields[key]] = int(parts[0]) * 1024
        except OSError:
            pass
    return result


class BlockAtomBatchSampler(Sampler):
    """One coverage pass; atom buckets within bounded original-order blocks.

    Local affine block permutation is deliberately a declared new order recipe,
    not a claim of uniform global shuffle. No domain balancing/oversampling occurs.
    Prefetch advances an iterator only. checkpoint state advances via commit_batch.
    """
    def __init__(self, index, *, seed, epoch=0, block_size=4096,
                 max_molecules=32, max_native_atoms=4096, atom_bucket_width=16,
                 max_padded_cost, padded_cost_multiplier):
        self.index = index
        self.seed = _integer(seed, "sampler seed")
        self.epoch = _integer(epoch, "epoch")
        self.block_size = _integer(block_size, "block size", minimum=1)
        self.max_molecules = _integer(max_molecules, "batch molecules", minimum=1)
        self.max_native_atoms = _integer(max_native_atoms, "batch native atoms", minimum=1)
        self.atom_bucket_width = _integer(atom_bucket_width, "atom bucket width", minimum=1)
        self.max_padded_cost = _integer(max_padded_cost, "padded cost", minimum=1)
        self.padded_cost_multiplier = _integer(padded_cost_multiplier, "padded cost multiplier", minimum=1)
        self.n_blocks = (len(index) + block_size - 1) // block_size
        self.contract = {"schema_version": SAMPLER_SCHEMA, "view_sha256": index.content_sha256,
                         "seed": seed, "block_size": block_size, "max_molecules": max_molecules,
                         "max_native_atoms": max_native_atoms, "atom_bucket_width": atom_bucket_width,
                         "max_padded_cost": max_padded_cost, "padded_cost_multiplier": padded_cost_multiplier,
                         "padded_cost_recipe": "multiplier_times_base_molecules_times_max_native_atoms_squared",
                         "oversized_molecule_policy": "singleton_no_discard",
                         "domain_policy": "original_view_natural_counts_no_oversampling",
                         "partial_block_and_epoch_batches": "retain"}
        self.contract_sha256 = canonical_hash(self.contract)
        self._cursor = (0, 0)
        self.batches_consumed = self.samples_consumed = 0
        self._block_cache = None

    def _ordered_block(self, block_position):
        if self._block_cache is not None and self._block_cache[0] == (self.epoch, block_position):
            return self._block_cache[1]
        material = canonical_hash({"contract": self.contract_sha256, "epoch": self.epoch})
        rng = random.Random(int(material, 16))
        multiplier = rng.randrange(1, self.n_blocks + 1)
        while math.gcd(multiplier, self.n_blocks) != 1:
            multiplier = multiplier % self.n_blocks + 1
        offset = rng.randrange(self.n_blocks)
        physical = (multiplier * block_position + offset) % self.n_blocks
        start, stop = physical * self.block_size, min((physical + 1) * self.block_size, len(self.index))
        order = list(range(start, stop))  # bounded block only, never corpus-sized.
        rng = random.Random(int(canonical_hash({"epoch": material, "block": physical}), 16))
        rng.shuffle(order)
        order.sort(key=lambda i: self.index.ref(i).native_n_atoms // self.atom_bucket_width)
        self._block_cache = ((self.epoch, block_position), order)
        return order

    def _next(self, cursor):
        block, offset = cursor
        if block == self.n_blocks:
            _require(offset == 0, "Invalid terminal cursor")
            return None
        order = self._ordered_block(block)
        _require(0 <= offset < len(order), "Invalid intra-block cursor")
        batch, total, largest = [], 0, 0
        while offset < len(order) and len(batch) < self.max_molecules:
            logical = order[offset]
            atoms = self.index.ref(logical).native_n_atoms
            candidate_largest = max(largest, atoms)
            padded = self.padded_cost_multiplier * (len(batch) + 1) * candidate_largest ** 2
            if batch and (total + atoms > self.max_native_atoms or padded > self.max_padded_cost):
                break
            batch.append(logical)
            total += atoms
            largest = candidate_largest
            offset += 1
            if total >= self.max_native_atoms or padded >= self.max_padded_cost:
                break  # a large tail row remains an explicit singleton.
        next_cursor = (block + 1, 0) if offset == len(order) else (block, offset)
        return batch, next_cursor

    def __iter__(self):
        cursor = self._cursor
        while (result := self._next(cursor)) is not None:
            batch, cursor = result
            yield batch

    def commit_batch(self, logical_indices):
        result = self._next(self._cursor)
        _require(result is not None and type(logical_indices) in (tuple, list)
                 and list(logical_indices) == result[0], "Consumed batch differs from next committed cursor")
        self._cursor = result[1]
        self.batches_consumed += 1
        self.samples_consumed += len(result[0])

    def state_dict(self):
        result = {"schema_version": SAMPLER_SCHEMA, "contract_sha256": self.contract_sha256,
                  "epoch": self.epoch, "block_position": self._cursor[0], "item_offset": self._cursor[1],
                  "batches_consumed": self.batches_consumed, "samples_consumed": self.samples_consumed}
        result["content_sha256"] = canonical_hash(result)
        return result

    def load_state_dict(self, payload):
        state = deepcopy(payload)
        _require(set(state) == {"schema_version", "contract_sha256", "epoch", "block_position",
                               "item_offset", "batches_consumed", "samples_consumed", "content_sha256"},
                 "Invalid sampler resume fields")
        seal = state.pop("content_sha256")
        _require(seal == canonical_hash(state) and state["schema_version"] == SAMPLER_SCHEMA
                 and state["contract_sha256"] == self.contract_sha256 and state["epoch"] == self.epoch,
                 "Sampler resume contract/epoch differs")
        for key in ("block_position", "item_offset", "batches_consumed", "samples_consumed"):
            _integer(state[key], key)
        target = (state["block_position"], state["item_offset"])
        _require(target[0] <= self.n_blocks, "Sampler cursor exceeds epoch")
        # Strict metadata replay validates boundaries and counters before mutation.
        # Bounded memory; resume may read prior compact counts, never native targets.
        cursor, batches, samples = (0, 0), 0, 0
        while cursor != target:
            result = self._next(cursor)
            _require(result is not None, "Resume cursor is not a real batch boundary")
            batch, cursor = result
            batches += 1
            samples += len(batch)
            _require(cursor <= target, "Resume cursor is not a real batch boundary")
        _require(batches == state["batches_consumed"] and samples == state["samples_consumed"],
                 "Resume exposure counters differ")
        self._cursor, self.batches_consumed, self.samples_consumed = target, batches, samples

    def advance_epoch(self):
        _require(self._cursor == (self.n_blocks, 0) and self.samples_consumed == len(self.index),
                 "Cannot advance an incomplete coverage epoch")
        self.epoch += 1
        self._cursor = (0, 0)
        self.batches_consumed = self.samples_consumed = 0
        self._block_cache = None


@dataclass
class CorpusBatch:
    encoder_batch: object
    logical_indices: tuple
    base_rows: tuple
    record_keys: tuple
    native_atom_counts: tuple

    def is_oversized_singleton(self, native_atom_cap):
        _integer(native_atom_cap, "native atom cap", minimum=1)
        return len(self.native_atom_counts) == 1 and self.native_atom_counts[0] > native_atom_cap

    def padded_cost(self, multiplier):
        _integer(multiplier, "padded cost multiplier", minimum=1)
        return multiplier * len(self.native_atom_counts) * max(self.native_atom_counts, default=0) ** 2

    def pin_memory(self):
        self.encoder_batch.pin_memory()
        return self


def collate_native_views(rows):
    _require(rows and all(isinstance(row, NativeViews) for row in rows), "Native views required")
    return CorpusBatch(fast_collate([view for row in rows for view in row.views]),
                       tuple(row.logical_index for row in rows), tuple(row.base_row for row in rows),
                       tuple(row.record_key for row in rows), tuple(row.native_n_atoms for row in rows))


def _worker_threads_one(_worker_id):
    torch.set_num_threads(1)


def make_prefetch_loader(dataset, sampler, *, num_workers=8, prefetch_factor=2,
                         pin_memory=True, persistent_workers=False,
                         worker_timeout_seconds=60.):
    _integer(num_workers, "loader workers", maximum=16)
    _integer(prefetch_factor, "prefetch factor", minimum=1, maximum=4)
    _require(type(pin_memory) is bool and type(persistent_workers) is bool, "Invalid loader booleans")
    _require(not persistent_workers, "Bounded segmented loading requires persistent_workers=False")
    _require(type(worker_timeout_seconds) in (int, float)
             and math.isfinite(worker_timeout_seconds) and 0 < worker_timeout_seconds <= 600,
             "Finite positive worker timeout <=600 seconds required")
    _require(dataset.index.content_sha256 == sampler.index.content_sha256
             and dataset.block_size == sampler.block_size, "Dataset/sampler binding or map-close blocks differ")
    generator = torch.Generator(device="cpu").manual_seed(sampler.seed)
    kwargs = dict(batch_sampler=sampler, collate_fn=collate_native_views,
                  num_workers=num_workers, pin_memory=pin_memory,
                  worker_init_fn=_worker_threads_one, generator=generator)
    if num_workers:
        # Never inherit initialized Torch/OpenMP/CUDA state through Linux fork.
        kwargs.update(prefetch_factor=prefetch_factor, persistent_workers=persistent_workers,
                      multiprocessing_context="spawn", timeout=float(worker_timeout_seconds))
    else:
        _require(not persistent_workers, "Persistent workers require workers")
    return DataLoader(dataset, **kwargs)


def close_prefetch_iterator(iterator, *, timeout_seconds=20.):
    """Release only this iterator's workers on exhaustion, break or exception.

    Torch's shutdown can terminate a worker without subsequently joining it.
    Its pin-thread/queue cleanup also has no overall deadline. Bound this close,
    then join/terminate/kill only its recorded child Process objects. Failure to
    close is raised, never disguised as successful cleanup. The caller must
    still impose its owned aggregate process-group wall/RAM budget.
    Keep persistent_workers=False when closing at each training/validation edge.
    """
    _require(type(timeout_seconds) in (int, float) and math.isfinite(timeout_seconds)
             and 0 < timeout_seconds <= 120, "Finite positive cleanup timeout <=120 seconds required")
    shutdown = getattr(iterator, "_shutdown_workers", None)
    if not callable(shutdown):
        close = getattr(iterator, "close", None)
        if callable(close):
            close()
        return
    workers = tuple(getattr(iterator, "_workers", ()))
    _require(len(workers) <= 16 and all(isinstance(worker, BaseProcess)
             and worker._parent_pid == os.getpid() for worker in workers),
             "Cleanup workers are not this process's recorded children")
    # Closing this iterator is intentional. Remove only its C-side crash
    # registration before planned terminate/kill; another iterator is untouched.
    if getattr(iterator, "_worker_pids_set", False):
        from torch.utils.data import _utils
        _utils.signal_handling._remove_worker_pids(id(iterator))
        iterator._worker_pids_set = False
    started = time.monotonic()
    deadline = started + float(timeout_seconds)
    errors = []
    def shutdown_owned():
        try:
            shutdown()
        except BaseException as error:
            errors.append(error)
    thread = threading.Thread(target=shutdown_owned, name="phase1-close-owned-loader", daemon=True)
    thread.start()
    thread.join(timeout=max(0., started + timeout_seconds * .5 - time.monotonic()))
    for worker in workers:
        if worker.is_alive():
            worker.terminate()
    grace_deadline = started + timeout_seconds * .75
    for worker in workers:
        worker.join(timeout=max(0., grace_deadline - time.monotonic()))
    for worker in workers:
        if worker.is_alive():
            worker.kill()
    for worker in workers:
        worker.join(timeout=max(0., deadline - time.monotonic()))
    thread.join(timeout=max(0., deadline - time.monotonic()))
    _require(not any(worker.is_alive() for worker in workers) and not thread.is_alive()
             and time.monotonic() <= deadline, "Owned DataLoader cleanup failed its finite deadline")
    if errors:
        raise FullCorpusLoaderError("Owned DataLoader shutdown raised after worker cleanup") from errors[0]
