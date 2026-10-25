"""Bounded synthetic corruption, target, LMDB and spawn tests; fixtures stay external."""
from __future__ import annotations
import argparse
import copy
import hashlib
import io
import json
import multiprocessing as mp
import os
from pathlib import Path
import struct
import time
import unittest
import numpy as np
from .codec import Limits, canonical_json, decode_record, encode_record
from .mapping import assemble_target, preflight_registry, validate_geometry, validate_labels
from .store import FamilyReader, FamilyWriter
from .subsets import plan_subsets

ROOT = None
_BARRIER = None


def metadata(record="g0", molecule="m0"):
    return {"export_record_id": record, "molecule_id": molecule, "geometry_source": "pm7",
            "effective_role": "TRAIN", "source_role": "TRAIN", "n_atoms": 2,
            "group_exposure_mask": {"P": True}, "family_exposure_mask": {"multipole": True, "bonding": True}}


def geometry():
    return {"atomic_numbers": np.array([6, 1], dtype="<i2"),
            "positions_A": np.array([[0., 0., 0.], [1.1, 0., 0.]], dtype="<f8"),
            "bond_pairs": np.array([[0, 1]], dtype="<i4"),
            "bond_order_codes": np.array([1], dtype="i1")}


def fixture_mapping(kind="vector", level="molecule", name="dipole", family="multipole"):
    components = ["x", "y", "z"] if kind == "vector" else (
        ["xx", "xy", "yy", "xz", "yz", "zz"] if kind == "symmetric_tensor" else ["value"])
    source_level = {"vector": "molecule_vector", "symmetric_tensor": "molecule_tensor"}.get(
        kind, "sparse_atom_pair" if level == "pair" else level)
    fields = [{"field_key": name + "." + c, "status": "enabled", "source_path": "values." + name,
               "registry_id": 1, "component": c, "group": "P", "level": source_level,
               "unit": "synthetic-unit", "family_v1_final": family,
               "reference_frame": {"verification": "VERIFIED"}} for c in components]
    target = {"target_id": name, "kind": kind, "level": level, "group": "P", "family": family,
              "condition": "P", "geometry_source": "pm7", "unit": "synthetic-unit",
              "unit_status": "VERIFIED", "members": [{key: f[key] for key in (
                  "field_key", "source_path", "registry_id", "component")} for f in fields],
              "mask_reduction": "elementwise" if kind == "scalar" else "all_components",
              "component_order": components, "storage": "matrix3x3",
              "pair_index_policy": {"directed": False, "allow_self": False}}
    registry = {"status": "FROZEN", "fields": fields}
    mapping = {"status": "FROZEN", "physical_targets": [target]}
    return registry, mapping, preflight_registry(registry, mapping)


def mutate(raw, change):
    n = struct.unpack("<I", raw[4:8])[0]
    header = json.loads(raw[8:8+n])
    change(header)
    updated = canonical_json(header)
    return raw[:4] + struct.pack("<I", len(updated)) + updated + raw[8+n:]


def init_spawn(barrier):
    global _BARRIER
    _BARRIER = barrier


def spawn_read(task):
    import psutil
    path, records = task
    _BARRIER.wait(300)
    with FamilyReader(path) as reader:
        digests = []
        for rid in records:
            meta, arrays = reader.get(rid)
            assert rid in reader.records_for_molecule(meta["molecule_id"])
            digests.append(hashlib.sha256(arrays["positions_A"].tobytes()).hexdigest())
    return {"pid": os.getpid(), "start": psutil.Process().create_time(), "digests": digests}


class WireTests(unittest.TestCase):
    def test_once_float32_and_canonical_roundtrip(self):
        source = np.array([0.1, np.nextafter(0.1, 1.), -0., 1e-40], dtype=">f8")
        before = source.tobytes()
        raw = encode_record({"unicode": "原子"}, {"value": source})
        meta, arrays = decode_record(raw)
        self.assertEqual(arrays["value"].dtype.str, "<f4")
        self.assertEqual(arrays["value"].tobytes(), source.astype("<f4").tobytes())
        self.assertEqual(source.tobytes(), before)
        self.assertEqual(encode_record(meta, arrays), raw)
        self.assertFalse(arrays["value"].flags.writeable)
        with self.assertRaises(ValueError):
            encode_record({}, {"bad": np.array([1e300])})
        with self.assertRaises(ValueError):
            encode_record({}, {"bad": np.array([object()], dtype=object)})

    def test_corrupted_payload_and_descriptor_rejection(self):
        raw = encode_record({}, {"a": np.array([1., 2.]), "b": np.array([3.])})
        changes = [
            lambda h: h["arrays"][1].update(offset=0),
            lambda h: h["arrays"][0].update(offset=4),
            lambda h: h["arrays"][0].update(dtype="|O8"),
            lambda h: h["arrays"][0].update(shape=[2**63]),
            lambda h: h["arrays"][0].update(nbytes=1),
        ]
        for change in changes:
            with self.subTest(change=repr(change)), self.assertRaises(ValueError):
                decode_record(mutate(raw, change))
        damaged = bytearray(raw); damaged[-1] ^= 1
        for value in (bytes(damaged), raw[:-1], raw + b"x", b"BAD!" + raw[4:],
                      raw[:4] + struct.pack("<I", 2**32 - 1) + raw[8:]):
            with self.subTest(kind=value[:8]), self.assertRaises(ValueError):
                decode_record(value)
        duplicate = b'{"format":"MFM3","version":1,"metadata":{},"arrays":[],"format":"MFM3"}'
        with self.assertRaises(ValueError):
            decode_record(b"MFM3" + struct.pack("<I", len(duplicate)) + duplicate)

    def test_mapping_requires_grouped_vector_and_exact_components(self):
        registry, mapping, compiled = fixture_mapping()
        self.assertEqual(compiled["source_component_count"], 3)
        self.assertEqual(compiled["physical_target_count"], 1)
        for change in ("scalar", "order", "unit", "omitted", "draft", "mixed_source", "Pprime"):
            candidate = copy.deepcopy(mapping)
            source = copy.deepcopy(registry)
            if change == "scalar": candidate["physical_targets"][0]["kind"] = "scalar"
            if change == "order": candidate["physical_targets"][0]["members"].reverse()
            if change == "unit": candidate["physical_targets"][0]["unit"] = "guessed"
            if change == "omitted": candidate["physical_targets"][0]["members"].pop()
            if change == "draft": source["status"] = "DRAFT"
            if change == "mixed_source":
                source["fields"][1]["registry_id"] = 2
                candidate["physical_targets"][0]["members"][1]["registry_id"] = 2
            if change == "Pprime":
                candidate["physical_targets"][0].update(condition="Pprime", geometry_source="uff_sprime")
            with self.subTest(change=change), self.assertRaises(ValueError):
                preflight_registry(source, candidate)

    def test_symmetric_tensor_grouping_and_masks(self):
        _, mapping, compiled = fixture_mapping("symmetric_tensor", name="quad")
        target = mapping["physical_targets"][0]
        source = {m["field_key"]: np.asarray(i + 0.125) for i, m in enumerate(target["members"])}
        tensor = assemble_target(target, source)
        np.testing.assert_array_equal(tensor, tensor.T)
        self.assertEqual(tensor[0, 2], source["quad.xz"])
        arrays = {"values/quad": tensor, "valid/quad": np.ones((3, 3), dtype=bool),
                  "reason/quad": np.zeros((3, 3), dtype="<u2")}
        _, arrays = decode_record(encode_record(metadata(), arrays))
        validate_labels(metadata(), arrays, compiled)
        bad = {k: v.copy() for k, v in arrays.items()}
        bad["values/quad"][0, 1] += 1
        with self.assertRaises(ValueError):
            validate_labels(metadata(), bad, compiled)
        target["storage"] = "symmetric6"
        packed = assemble_target(target, source)
        self.assertEqual(packed.shape, (6,))

    def test_geometry_pair_bounds_and_label_validity(self):
        meta, arrays = decode_record(encode_record(metadata(), geometry()))
        validate_geometry(meta, arrays)
        for pairs in (np.array([[0, 2]], dtype="<i4"), np.array([[0, 1], [0, 1]], dtype="<i4"),
                      np.array([[1, 0]], dtype="<i4")):
            bad = dict(arrays); bad["bond_pairs"] = pairs
            bad["bond_order_codes"] = np.ones(len(pairs), dtype="|u1")
            with self.assertRaises(ValueError):
                validate_geometry(meta, bad)
        _, _, compiled = fixture_mapping("scalar", "pair", "bond", "bonding")
        payload = {"values/bond": np.array([np.nan]), "valid/bond": np.array([False]),
                   "reason/bond": np.array([7], dtype="<u2"),
                   "pairs/bond": np.array([[0, 1]], dtype="<i4")}
        _, decoded = decode_record(encode_record(metadata(), payload))
        validate_labels(metadata(), decoded, compiled)
        bad = {k: v.copy() for k, v in decoded.items()}; bad["valid/bond"][:] = 1
        with self.assertRaises(ValueError):
            validate_labels(metadata(), bad, compiled)
        bad = {k: v.copy() for k, v in decoded.items()}; bad["valid/bond"] = np.array([[0]], dtype="|u1")
        with self.assertRaises(ValueError):
            validate_labels(metadata(), bad, compiled)

    def test_lmdb_transaction_index_and_separate_masks(self):
        path = ROOT / "geometry"
        with FamilyWriter(path, {"kind": "geometry", "version": 1}, map_bytes=16 * 1024**2) as writer:
            with self.assertRaises(ValueError):
                writer.write_batch([(metadata("dup"), geometry()), (metadata("dup"), geometry())])
            self.assertEqual(writer.count, 0)
            writer.write_batch([(metadata("g0"), geometry()), (metadata("g1"), geometry())])
        with FamilyReader(path) as reader:
            self.assertEqual(reader.count, 2)
            self.assertEqual(reader.records_for_molecule("m0"), ["g0", "g1"])
            self.assertEqual(reader.records_for_molecule("missing"), [])
            detached = reader.get("g0")[1]["positions_A"]
        self.assertEqual(detached.shape, (2, 3))
        _, _, compiled = fixture_mapping()
        path = ROOT / "labels"
        arrays = {"values/dipole": np.array([1., 2., 3.]), "valid/dipole": np.ones(3, dtype=bool),
                  "reason/dipole": np.zeros(3, dtype="<u2")}
        with FamilyWriter(path, {"kind": "labels", "family": "multipole", "compiled": compiled},
                          map_bytes=16 * 1024**2) as writer:
            writer.write_batch([(metadata("p0"), arrays)])
        with FamilyReader(path) as reader:
            np.testing.assert_array_equal(reader.get("p0")[1]["values/dipole"], [1., 2., 3.])
            with reader.env.begin() as tx:
                self.assertEqual(tx.stat(db=reader.masks)["entries"], 1)

    def test_incomplete_store_is_not_readable(self):
        path = ROOT / "incomplete"
        writer = FamilyWriter(path, {"kind": "geometry"}, map_bytes=1024**2)
        writer.write_batch([(metadata("partial"), geometry())])
        writer.close()
        with self.assertRaises(ValueError):
            FamilyReader(path)

    def test_subsets_refuse_unfrozen_and_exclude_both_geometries(self):
        roles = {"status": "FROZEN", "validation_source": "ROUTINE", "all_conformers_same_role": True}
        common = {"status": "FROZEN", "geometries_frozen": True, "roles_authority_sha256": "r"}
        orders_manifest = {"status": "FROZEN", "common_manifest_sha256": "c",
                           "roles_authority_sha256": "r", "order_types": ["random", "energy", "diversity"],
                           "geometry_sources": ["pm7", "uff_sprime"]}
        rows = [{"molecule_id": str(i), "effective_role": "TRAIN" if i < 10 else "VAL"} for i in range(13)]
        orders = {(r["molecule_id"], g): {key: ["a", "b", "c"] for key in ("random", "energy", "diversity")}
                  for r in rows for g in ("pm7", "uff_sprime")}
        kwargs = dict(roles=roles, common=common, orders=orders_manifest, roles_sha="r", common_sha="c",
                      orders_sha="o", seed=123, sizes=(3, 6, 8), pilot_train=2, pilot_val=2,
                      diagnostic=2, fixture=True)
        result = plan_subsets(rows, orders, **kwargs)
        self.assertEqual(result["nested_train"]["3"], result["nested_train"]["6"][:3])
        self.assertEqual(result["pilot_train"], result["nested_train"]["3"][:2])
        self.assertEqual(len(result["exclude_from_every_training_condition"]), 4)
        self.assertTrue(all(x["conformer_id"] == "c" for x in result["exclude_from_every_training_condition"]))
        kwargs["common"] = {**common, "status": "DRAFT"}
        with self.assertRaises(ValueError):
            plan_subsets(rows, orders, **kwargs)


def main():
    import concurrent.futures as cf
    import psutil
    global ROOT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=16)
    args = parser.parse_args()
    if args.workers != 16 or not args.output.is_absolute():
        parser.error("Use an external absolute output and 16 bounded spawn workers")
    ROOT = args.output
    ROOT.mkdir(parents=True, exist_ok=False)
    log = io.StringIO()
    result = unittest.TextTestRunner(stream=log, verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(WireTests))
    print(log.getvalue(), end="")
    summary = {"unit_tests": result.testsRun, "failures": len(result.failures),
               "errors": len(result.errors), "fixtures": str(ROOT),
               "source_data_read": False, "contract_finalized": False,
               "hostname": os.uname().nodename, "uid": os.getuid(),
               "numpy_version": str(np.__version__),
               "source_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in Path(__file__).parent.glob("*.py")}}
    if result.wasSuccessful():
        store = ROOT / "spawn"
        with FamilyWriter(store, {"kind": "geometry"}, map_bytes=16 * 1024**2) as writer:
            writer.write_batch([(metadata(f"s{i}", f"m{i // 2}"), geometry()) for i in range(32)])
        context = mp.get_context("spawn")
        barrier = context.Barrier(args.workers)
        tasks = [(str(store), [f"s{2*i}", f"s{2*i+1}"]) for i in range(args.workers)]
        with cf.ProcessPoolExecutor(max_workers=args.workers, mp_context=context,
                initializer=init_spawn, initargs=(barrier,)) as pool:
            spawned = list(pool.map(spawn_read, tasks, chunksize=1))
        assert len({x["pid"] for x in spawned}) == args.workers
        for child in spawned:
            try:
                alive = psutil.Process(child["pid"]).create_time() == child["start"]
            except psutil.NoSuchProcess:
                alive = False
            assert not alive, "OWN_SPAWN_WORKER_NOT_CLOSED"
        assert len({digest for x in spawned for digest in x["digests"]}) == 1
        summary.update(spawn_workers=len(spawned), spawn_records=32,
                       all_workers_actually_closed=True)
    summary["status"] = "PASS" if result.wasSuccessful() else "FAIL"
    (ROOT / "test_summary.json").write_bytes(canonical_json(summary) + b"\n")
    print(json.dumps(summary))
    if not result.wasSuccessful():
        raise SystemExit(1)


if __name__ == "__main__":
    main()
