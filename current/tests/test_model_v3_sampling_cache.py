"""Streaming metadata cache, exact sampler replay and real readonly spawn."""
from dataclasses import asdict, replace
import hashlib
from itertools import islice
import json
import multiprocessing as mp
import os
from pathlib import Path
import pickle
import random
import shutil
import sqlite3
import types
import weakref

import pytest

from phychem_mfm.phase1 import v3_sampling_cache as cache_module
from phychem_mfm.phase1.v3_sampling import ConformationSelection, ConformerRef, MoleculeEntry, UniformMoleculeSampler
from phychem_mfm.phase1.v3_sampling_bridge import (CandidateProjectionInput, NativeConformerIdentity,
    PROJECTION_SOURCE_SHA256, build_candidate_sampling_index)
from phychem_mfm.phase1.v3_sampling_cache import (DB_NAME, MANIFEST_NAME, open_sampling_cache, write_sampling_cache)


def entry(ordinal):
    source = "PM7" if ordinal % 2 == 0 else "Sprime_UFF"
    count = ordinal % 4 + 1
    refs = tuple(ConformerRef(f"m{ordinal}:{source}:c{j}", j * 2, ordinal % 7 + 2,
                              ((source, f"opaque:{ordinal}:{source}:{j}"),), count - j - 1) for j in range(count))
    return MoleculeEntry(f"m{ordinal}", refs,
        (("P", ordinal % 3 != 0), ("S", True), ("D", False)),
        (("other", False), ("physics", True)), source, refs[-1].conformer_id)


class LazySource:
    version = "lazy-synthetic-metadata-v1"
    role, authority = "TRAIN", "synthetic_fixture"
    status, contract_finalized, real_data_export_accepted = "CANDIDATE_ONLY", False, False
    geometry_source, selection = "mixed", ConformationSelection()

    def __init__(self, count, *, fail_at=None, duplicate_at=None, change_at=None):
        self.count, self.fail_at, self.duplicate_at, self.change_at = count, fail_at, duplicate_at, change_at
        self.requests, self.max_live, self.sequential = 0, 0, True
        self.live = weakref.WeakSet()

    def __len__(self):
        return self.count

    @property
    def content_sha256(self):
        return hashlib.sha256(f"fixture-formula-v1:{self.count}:{self.version}:{self.role}:{self.authority}".encode()).hexdigest()

    @property
    def molecules(self):
        raise AssertionError("Do not materialize the whole Python manifest")

    @property
    def bindings(self):
        raise AssertionError("Do not copy an O(N) source bindings dictionary")

    @property
    def labels(self):
        raise AssertionError("Cache must not inspect scientific labels")

    @property
    def coordinates(self):
        raise AssertionError("Cache must not inspect coordinates")

    def molecule_at(self, ordinal):
        assert 0 <= ordinal < self.count
        self.sequential &= ordinal == self.requests
        self.requests += 1
        if ordinal == self.fail_at:
            raise RuntimeError("owned synthetic source interruption")
        if ordinal == self.change_at:
            self.version = "changed-during-write"
        result = entry(0 if ordinal == self.duplicate_at else ordinal)
        self.live.add(result)
        self.max_live = max(self.max_live, len(self.live))
        return result


class NativeLazySource(LazySource):
    def native_identity_for(self, geometry_id):
        mid, source, conf = geometry_id.split(":")
        index = int(conf[1:])
        return NativeConformerIdentity(geometry_id, mid, "pm7" if source == "PM7" else "uff_sprime",
            f"record:{mid}" if source == "PM7" else None, None if source == "PM7" else index * 11)


def write(source, path, **options):
    return write_sampling_cache(source, path, expected_source_content_sha256=source.content_sha256, **options)


def reopen(receipt, path=None):
    return open_sampling_cache(path or receipt["directory"], expected_manifest_sha256=receipt["manifest_sha256"],
                               expected_source_content_sha256=receipt["source_content_sha256"])


def repin_owned_corrupt_copy(path):
    """Negative fixtures only: retain the original cache and alter a new copy."""
    manifest_path = path / MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text())
    manifest["database_bytes"] = (path / DB_NAME).stat().st_size
    manifest["database_sha256"] = cache_module._file_sha(path / DB_NAME)
    raw = (cache_module._canonical(manifest) + "\n").encode()
    manifest_path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def test_lazy_streaming_holds_constant_source_objects_and_pickle_has_no_corpus(tmp_path):
    sizes = []
    for n in (64, 8192):
        source = LazySource(n)
        receipt = write(source, tmp_path / f"cache-{n}", batch_rows=32)
        assert source.requests == n and source.sequential and source.max_live <= 2
        with reopen(receipt) as cached:
            assert len(cached) == n and cached.content_sha256 == source.content_sha256
            assert cached.molecule_at(n - 1) == entry(n - 1)
            assert not hasattr(cached, "molecules") and not hasattr(cached, "native_identity_for")
            encoded = pickle.dumps(cached)
            assert len(encoded) < 8192
            sizes.append(len(encoded))
            assert cached._connection is not None  # The connection itself is not pickled.
            restored = pickle.loads(encoded)
            assert restored._connection is None and restored.molecule_at(0) == entry(0)
            restored.close()
    assert sizes[1] <= sizes[0] + 512


def test_copy_reopen_and_native_scope_keep_sampler_checkpoint_and_all_metadata_exact(tmp_path):
    source = NativeLazySource(17)
    receipt = write(source, tmp_path / "original", batch_rows=3)
    shutil.copytree(receipt["directory"], tmp_path / "copied")
    before_rng = random.getstate()
    direct = UniformMoleculeSampler(source, seed=73, sample_budget=50, selection=source.selection, geometry_source=source.geometry_source)
    with reopen(receipt, tmp_path / "copied") as cached:
        assert cached.authority == source.authority and cached.role == source.role and cached.version == source.version
        assert cached.status == source.status and cached.contract_finalized is False and cached.real_data_export_accepted is False
        assert cached.content_sha256 == source.content_sha256
        replay = cached.make_sampler(seed=73, sample_budget=50)
        draws = list(islice(direct, 5))
        assert list(islice(replay, 5)) == draws
        direct.commit_batch(draws)
        speculative = list(islice(direct, 9))
        replay.load_state_dict(direct.state_dict())
        assert list(islice(replay, 9)) == speculative
        for ordinal in (0, 8, 16):
            restored = cached.molecule_at(ordinal)
            assert restored == entry(ordinal)
            for ref in restored.conformers:
                native = cached.native_identity_for(ref.conformer_id)
                assert native.as_dict() == source.native_identity_for(ref.conformer_id).as_dict()
                assert native.content_sha256 == source.native_identity_for(ref.conformer_id).content_sha256
        assert cached.cache_manifest["header"]["native_identity_scope"] == "sampleable_conformers_only"
        with pytest.raises(KeyError):
            cached.native_identity_for("non-sampleable-source-geometry")
        with pytest.raises(ValueError, match="selection differs"):
            cached.make_sampler(seed=73, sample_budget=50, selection=ConformationSelection("minimum_energy"))
    assert random.getstate() == before_rng


def test_actual_pinned_data_projection_and_a_native_api_survive_cache(tmp_path):
    path = Path(os.environ.get("MODEL_V3_D5_PROJECTION_SOURCE",
        "/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository/"
        "workflows/data_v1_final/export/wire_v1/sampling_projection_v1.py"))
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == PROJECTION_SOURCE_SHA256
    module = types.ModuleType("cache_pinned_data_projection")
    exec(compile(raw, str(path), "exec"), module.__dict__)
    geometries, orders, atoms = [], [], {}
    for src, ids in (("pm7", ("p7", "p2")), ("uff_sprime", ("u9", "u1", "u5"))):
        for j, gid in enumerate(ids):
            geometries.append({"molecule_id": "m", "geometry_id": gid, "geometry_source": src,
                "native_record_id": f"record-{j}" if src == "pm7" else None,
                "sprime_conf_idx": j * 13 if src == "uff_sprime" else None, "parent_geometry_id": None, "view_id": None})
            atoms[gid] = 4
        for kind in ("fixed_random", "energy", "diversity"):
            for rank, gid in enumerate(ids if kind == "fixed_random" else tuple(reversed(ids))):
                orders.append({"molecule_id": "m", "geometry_id": gid, "geometry_source": src,
                    "order_type": kind, "rank": rank + 1, "training_rank": rank})
    args = {"effective_role": "TRAIN", "training_geometries": geometries, "training_orders": orders,
        "native_atom_counts": atoms, "diagnostic_targets": [{"molecule_id": "m", "geometry_source": "pm7", "geometry_id": "held-p"}],
        "group_mask": {"S": True, "D": False, "P": True}, "family_mask": {"physics": True}}
    projected = module.project_training_sources("m", **args)
    original = build_candidate_sampling_index([CandidateProjectionInput("m", projected, args, PROJECTION_SOURCE_SHA256)],
        data_version="cache-and-provider-caller-version", geometry_source="Sprime_UFF", selected_molecule_ids=["m"],
        selection=ConformationSelection("first_k", 1), allow_candidate=True)
    receipt = write(original, tmp_path / "actual-a")
    with reopen(receipt) as cached:
        assert list(cached.make_sampler(seed=6, sample_budget=30)) == list(original.make_sampler(seed=6, sample_budget=30))
        assert cached.content_sha256 == original.content_sha256 and cached.authority == "synthetic_fixture"
        assert cached.cache_manifest["header"]["native_identities"] == 3  # Full selected source, not k=1 only.
        for gid in ("u9", "u1", "u5"):
            assert cached.native_identity_for(gid).as_dict() == original.native_identity_for(gid).as_dict()
            assert cached.native_identity_for(gid).content_sha256 == original.native_identity_for(gid).content_sha256
        with pytest.raises(KeyError):
            cached.native_identity_for("p7")  # Explicitly declared scope excludes unselected-source audit.
    assert hashlib.sha256(path.read_bytes()).hexdigest() == PROJECTION_SOURCE_SHA256


@pytest.mark.parametrize("role,authority", [("TRAIN", "synthetic_fixture"), ("VAL", "data_line"), ("TRAIN_UNSEEN_CONFORMATION", "synthetic_fixture")])
def test_role_authority_and_version_are_preserved_not_inferred_from_cache_completion(tmp_path, role, authority):
    source = LazySource(3)
    source.role, source.authority = role, authority
    receipt = write(source, tmp_path / "cache")
    with reopen(receipt) as cached:
        assert (cached.role, cached.authority, cached.version) == (source.role, source.authority, source.version)
        assert cached.status == "CANDIDATE_ONLY" and cached.contract_finalized is False


def test_independent_open_hashes_database_once_and_reopen_after_close_uses_receipt(tmp_path, monkeypatch):
    receipt = write(LazySource(5), tmp_path / "cache")
    original = cache_module._file_sha
    calls = []
    def observed(path):
        calls.append(Path(path).name)
        return original(path)
    monkeypatch.setattr(cache_module, "_file_sha", observed)
    cached = reopen(receipt)
    assert calls.count(DB_NAME) == 1
    assert cached.molecule_at(4) == entry(4)
    connection = cached._connection
    cached.close()
    with pytest.raises(sqlite3.ProgrammingError):
        connection.execute("SELECT 1")
    assert cached.molecule_at(1) == entry(1) and calls.count(DB_NAME) == 1
    cached.close()


def test_changed_owner_pid_closes_inherited_handle_before_opening_new_one(tmp_path):
    receipt = write(LazySource(3), tmp_path / "cache")
    with reopen(receipt) as cached:
        cached.molecule_at(0)
        previous = cached._connection
        cached._pid = -1
        assert cached.molecule_at(2) == entry(2) and cached._pid == os.getpid()
        assert cached._connection is not previous
        with pytest.raises(sqlite3.ProgrammingError):
            previous.execute("SELECT 1")


_WORKER_CACHE = _WORKER_BARRIER = None


def _worker_init(encoded, barrier):
    global _WORKER_CACHE, _WORKER_BARRIER
    _WORKER_CACHE, _WORKER_BARRIER = pickle.loads(encoded), barrier
    original = cache_module._file_sha
    def no_database_rescan(path):
        if Path(path).name == DB_NAME:
            raise AssertionError("Spawn must reuse verified same-node receipt, not scan the whole database")
        return original(path)
    cache_module._file_sha = no_database_rescan


def _worker_lookup(ordinal):
    _WORKER_BARRIER.wait(timeout=20.)
    value = _WORKER_CACHE.molecule_at(ordinal)
    connection = _WORKER_CACHE._connection
    owner = _WORKER_CACHE._pid
    readonly = False
    try:
        connection.execute("UPDATE metadata SET value='forbidden' WHERE key='header'")
    except sqlite3.OperationalError:
        readonly = True
    _WORKER_CACHE.close()
    closed = False
    try:
        connection.execute("SELECT 1")
    except sqlite3.ProgrammingError:
        closed = True
    return os.getpid(), owner, readonly, closed, asdict(value)


def test_true_spawn_workers_open_only_readonly_handles_without_pickling_corpus(tmp_path):
    receipt = write(NativeLazySource(20), tmp_path / "cache")
    cached = reopen(receipt)
    cached.molecule_at(0)  # Parent has a live connection; it must not be passed.
    encoded = pickle.dumps(cached)
    context = mp.get_context("spawn")
    barrier = context.Barrier(2)
    pool = context.Pool(2, initializer=_worker_init, initargs=(encoded, barrier))
    workers = tuple(pool._pool)
    try:
        outputs = pool.map(_worker_lookup, (1, 3, 7, 12), chunksize=1)
        pool.close()
        pool.join()
    finally:
        if any(worker.is_alive() for worker in workers):
            pool.terminate()
            pool.join()
        cached.close()
    assert len({row[0] for row in outputs}) == 2
    assert all(pid == owner and pid != os.getpid() and readonly and closed for pid, owner, readonly, closed, _ in outputs)
    assert all(not worker.is_alive() for worker in workers)
    assert [row[-1] for row in outputs] == [asdict(entry(i)) for i in (1, 3, 7, 12)]


@pytest.mark.parametrize("failure", ["interrupted", "source_changed", "duplicate_molecule"])
def test_failed_writes_remain_partial_and_are_rejected_without_deleting_evidence(tmp_path, failure):
    source = LazySource(6, **{"interrupted": {"fail_at": 3}, "source_changed": {"change_at": 5}, "duplicate_molecule": {"duplicate_at": 2}}[failure])
    destination = tmp_path / "partial"
    with pytest.raises((RuntimeError, ValueError, sqlite3.IntegrityError)):
        write(source, destination, batch_rows=2)
    assert (destination / DB_NAME).exists() and not (destination / MANIFEST_NAME).exists()
    with pytest.raises(ValueError, match="Partial/WRITING"):
        open_sampling_cache(destination, expected_manifest_sha256="a" * 64, expected_source_content_sha256="b" * 64)


def test_existing_directory_and_wrong_source_pin_are_rejected_before_overwrite(tmp_path):
    source = LazySource(2)
    destination = tmp_path / "existing"
    receipt = write(source, destination)
    with pytest.raises(FileExistsError):
        write(LazySource(2), destination)
    assert cache_module._file_sha(destination / MANIFEST_NAME) == receipt["manifest_sha256"]
    with pytest.raises(ValueError, match="Source content pin"):
        write_sampling_cache(LazySource(2), tmp_path / "wrong", expected_source_content_sha256="f" * 64)
    assert not (tmp_path / "wrong").exists()


@pytest.mark.parametrize("invalid", [-1, 4, True, 1.5])
def test_random_access_rejects_out_of_bounds_and_noninteger_ordinals(tmp_path, invalid):
    receipt = write(LazySource(4), tmp_path / "cache")
    with reopen(receipt) as cached, pytest.raises(IndexError):
        cached.molecule_at(invalid)


@pytest.mark.parametrize("corruption", ["manifest_pin", "source_pin", "database_bytes", "writing", "schema", "count", "row_sha", "row_ordinal", "native_identity"])
def test_corrupt_partial_schema_binding_and_row_metadata_are_rejected(tmp_path, corruption):
    receipt = write(NativeLazySource(4), tmp_path / "original")
    destination = tmp_path / "owned-corrupt-copy"
    shutil.copytree(receipt["directory"], destination)
    manifest_pin, source_pin = receipt["manifest_sha256"], receipt["source_content_sha256"]
    if corruption == "manifest_pin":
        manifest_pin = "f" * 64
    elif corruption == "source_pin":
        source_pin = "f" * 64
    elif corruption == "database_bytes":
        with (destination / DB_NAME).open("ab") as stream:
            stream.write(b"owned negative fixture corruption")
    elif corruption == "writing":
        manifest = json.loads((destination / MANIFEST_NAME).read_text())
        manifest["cache_state"] = "WRITING"
        raw = (cache_module._canonical(manifest) + "\n").encode()
        (destination / MANIFEST_NAME).write_bytes(raw)
        manifest_pin = hashlib.sha256(raw).hexdigest()
    else:
        connection = sqlite3.connect(destination / DB_NAME)
        if corruption == "schema":
            connection.execute("PRAGMA user_version=99")
        elif corruption == "count":
            header = json.loads(connection.execute("SELECT value FROM metadata WHERE key='header'").fetchone()[0])
            header["source"]["molecules"] += 1
            connection.execute("UPDATE metadata SET value=? WHERE key='header'", (cache_module._canonical(header),))
            manifest = json.loads((destination / MANIFEST_NAME).read_text())
            manifest["header"] = header
            (destination / MANIFEST_NAME).write_text(cache_module._canonical(manifest) + "\n")
        elif corruption in ("row_sha", "row_ordinal"):
            value = json.loads(connection.execute("SELECT payload FROM molecules WHERE ordinal=0").fetchone()[0])
            value["ordinal"] = 99
            raw = cache_module._canonical(value)
            if corruption == "row_sha":
                connection.execute("UPDATE molecules SET payload=? WHERE ordinal=0", (raw,))
            else:
                connection.execute("UPDATE molecules SET payload=?,payload_sha256=? WHERE ordinal=0", (raw, hashlib.sha256(raw.encode()).hexdigest()))
        else:
            gid = entry(0).conformers[0].conformer_id
            raw = connection.execute("SELECT payload FROM native_identity WHERE geometry_id=?", (gid,)).fetchone()[0]
            value = json.loads(raw)
            value["geometry_id"] = "different-native-geometry"
            raw = cache_module._canonical(value)
            connection.execute("UPDATE native_identity SET payload=?,payload_sha256=? WHERE geometry_id=?", (raw, hashlib.sha256(raw.encode()).hexdigest(), gid))
        connection.commit()
        connection.close()
        manifest_pin = repin_owned_corrupt_copy(destination)
    with pytest.raises((ValueError, sqlite3.DatabaseError)):
        cached = open_sampling_cache(destination, expected_manifest_sha256=manifest_pin, expected_source_content_sha256=source_pin)
        try:
            cached.molecule_at(0)
            for ref in entry(0).conformers:
                cached.native_identity_for(ref.conformer_id)
        finally:
            cached.close()


def test_stale_same_node_receipt_is_rejected_without_scanning_modified_database(tmp_path):
    receipt = write(LazySource(3), tmp_path / "cache")
    cached = reopen(receipt)
    encoded = pickle.dumps(cached)
    cached.close()
    with (Path(receipt["directory"]) / DB_NAME).open("ab") as stream:
        stream.write(b"changed after parent verification")
    stale = pickle.loads(encoded)
    with pytest.raises(ValueError, match="receipt is stale"):
        stale.molecule_at(0)


def test_reader_does_not_invent_selection_policy_without_source_hints(tmp_path):
    class NoHints:
        version, role, authority = "caller-version", "TRAIN", "synthetic_fixture"
        content_sha256 = "b" * 64
        def __len__(self): return 2
        def molecule_at(self, i): return entry(i)
    receipt = write(NoHints(), tmp_path / "cache")
    with reopen(receipt) as cached:
        with pytest.raises(ValueError, match="explicitly supply"):
            cached.make_sampler(seed=0, sample_budget=3)
        assert len(list(cached.make_sampler(seed=0, sample_budget=3, selection=ConformationSelection(), geometry_source="mixed"))) == 3


@pytest.mark.parametrize("failure", ["entry_bytes", "native_sidecar_bytes", "bad_native_atoms"])
def test_entry_boundaries_and_invalid_typed_metadata_do_not_create_complete_caches(tmp_path, failure):
    class OversizedEntry(LazySource):
        def molecule_at(self, i):
            value = super().molecule_at(i)
            refs = (replace(value.conformers[0], geometry_locators=(("PM7", "x" * 5000),)),) + value.conformers[1:]
            return replace(value, conformers=refs)
    class OversizedNative(NativeLazySource):
        def native_identity_for(self, gid):
            return replace(super().native_identity_for(gid), native_record_id="x" * 5000)
    class BadAtoms(LazySource):
        def molecule_at(self, i):
            value = super().molecule_at(i)
            object.__setattr__(value.conformers[0], "native_atoms", 0)
            return value
    source = {"entry_bytes": OversizedEntry, "native_sidecar_bytes": OversizedNative, "bad_native_atoms": BadAtoms}[failure](2)
    destination = tmp_path / "partial"
    with pytest.raises(ValueError):
        write(source, destination, **({"max_entry_bytes": 2048} if failure != "bad_native_atoms" else {}))
    assert (destination / DB_NAME).exists() and not (destination / MANIFEST_NAME).exists()
