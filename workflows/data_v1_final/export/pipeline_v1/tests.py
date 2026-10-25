"""External-only fixtures exercise real Parquet adapters, joins and LMDB CLI core."""
from __future__ import annotations
import argparse
import copy
import json
from pathlib import Path
import unittest
import numpy as np
from . import distributions, export, materialize, mask_binding
from . import verify as roundtrip
from .io import connect, fresh_dir, read_json, write_json
from .masks import restore
from .source import extract, pack, unpack
from wire_v1.store import FamilyReader, file_ref
from wire_v1.tests import fixture_mapping

ROOT = None


def parquet(path, rows, schema=None):
    import pyarrow as pa
    import pyarrow.parquet as pq
    pq.write_table(pa.Table.from_pylist(rows, schema=schema), path, compression="zstd", row_group_size=2)
    return file_ref(path)


def fixture(root):
    import pyarrow as pa
    root.mkdir()
    (root / "molecule_roles").mkdir()
    mols = ["t" + str(i).zfill(2) for i in range(10)] + ["v" + str(i) for i in range(3)] + ["f0"]
    roles = [{"molecule_id": m, "effective_role": "TRAIN" if m[0] == "t" else ("VAL" if m[0] == "v" else "FULL"), "source_role": "TRAIN" if m[0] == "t" else "FULL"} for m in mols]
    role_table = parquet(root / "molecule_roles" / "part-0.parquet", roles)
    role_source_ref = write_json(root / "roles_source.json", {"status": "ROUTINE_MOLECULE_VAL_ROLES_FROZEN", "outputs": [role_table]})
    role_ref = write_json(root / "roles.json", {"status": "FROZEN", "validation_source": "ROUTINE", "all_conformers_same_role": True, "source_role_manifest": role_source_ref, "roles": {"TRAIN": {"molecules": 10}, "VAL": {"molecules": 3}, "FULL": {"molecules": 1}}})
    common_table = parquet(root / "common.parquet", [{"molecule_id": m, "common_population": m != "f0"} for m in mols])
    common_ref = write_json(root / "common.json", {"status": "COMMON_POPULATION_V1_FROZEN", "membership_tables": [common_table], "roles_manifest_sha256": role_source_ref["sha256"]})
    geometries, orders, geometry_source, label_source, owner_index, masks = [], [], [], [], [], []
    bits = lambda ids: sum(1 << i for i in ids).to_bytes(19, "little")
    for m in mols[:-1]:
        for src in ("pm7", "uff_sprime"):
            for i in range(3):
                gid = "opaque-" + m + "-" + src + "-" + str(i)
                native = m + "-pm7-" + str(i) if src == "pm7" else "IGNORED_NATIVE_COLLISION"
                ordinal = len(owner_index)
                if src == "pm7":
                    owner_index.append({"record_ordinal": ordinal, "molecule_id": m, "record_id": native})
                for view in (None, "noise1"):
                    view_gid = gid if view is None else gid + "-noise"
                    geometries.append({"geometry_id": view_gid, "molecule_id": m, "geometry_source": src, "native_record_id": native,
                        "sprime_conf_idx": None if src == "pm7" else i, "parent_geometry_id": None if view is None else gid, "view_id": view})
                    geometry_source.append({"gid": view_gid, "mid": m, "src": src, "record": native, "idx": None if src == "pm7" else i, "view": view, "n": 2,
                        "z": [6, 1], "xyz": [[-0., 0., 0.], [0.1 + i, float(view is not None), 0.]]})
                    if src == "pm7":
                        label_source.append({"gid": view_gid, "mid": m, "src": src, "record": native, "idx": None, "view": view, "n": 2,
                            "mask_task": 0 if view is None else 1, "nested": {"energy": None if i == 1 else (-0. if i == 0 else 0.123456789 + i), "mask": 1, "reason": 0}})
                        masks.append({"record_ordinal": ordinal, "task_code": 0 if view is None else 1,
                            "in_scope_fields": bits([0]), "source_valid_fields": bits([] if i == 1 else [0]), "valid_fields": bits([] if i == 1 else [0]),
                            "all_leaves_valid_fields": bits([] if i == 1 else [0]), "newly_masked_fields": bits([]),
                            "source_reason_groups": [{"code": 3, "fields": bits([0])}] if i == 1 else [], "new_reason_groups": [],
                            "review_groups": [{"code": 1, "fields": bits([0])}] if i == 2 else [], "leaf_exceptions": []})
                for order, index in (("fixed_random", i), ("energy", 2 - i), ("diversity", (i + 1) % 3)):
                    orders.append({"molecule_id": m, "geometry_source": src, "order_type": order, "rank": index, "geometry_id": gid})
    geom_table = parquet(root / "source_geometry.parquet", geometries)
    order_table = parquet(root / "orders.parquet", orders)
    order_ref = write_json(root / "orders.json", {"status": "CONFORMER_ORDER_V1_FROZEN", "order_tables": [order_table], "source_geometry_tables": [geom_table], "order_types": ["fixed_random", "energy", "diversity"], "rank_base": 0, "common_population_manifest_sha256": common_ref["sha256"], "roles_manifest_sha256": role_source_ref["sha256"]})
    feature_ref = parquet(root / "features.parquet", [{"molecule_id": m, "element_z": [1, 6] + ([8] if i % 2 else []), "heavy_atoms": 1 + i % 4, "scaffold_id": "" if i % 2 else "ring"} for i, m in enumerate(mols)])
    config = {"roles_authority": role_ref, "common_manifest": common_ref, "order_manifest": order_ref,
        "source_geometry_tables": [geom_table], "feature_tables": [feature_ref], "seed": 20261025, "maximum_output_bytes": 100_000_000,
        "fixture_counts": {"sizes": [4, 6, 8], "pilot_train": 3, "pilot_val": 2, "diagnostic": 3}}
    reg, mapping, _ = fixture_mapping(kind="scalar", name="energy", family="energy")
    registry_ref = write_json(root / "registry.json", reg)
    mapping_ref = write_json(root / "mapping.json", mapping)
    mask_schema = pa.schema([("record_ordinal", pa.uint64()), ("task_code", pa.uint8()), *[(n, pa.binary(19)) for n in ("in_scope_fields", "source_valid_fields", "valid_fields", "all_leaves_valid_fields", "newly_masked_fields")],
        *[(n, pa.list_(pa.struct([("code", pa.uint16()), ("fields", pa.binary(19))]))) for n in ("source_reason_groups", "new_reason_groups", "review_groups")],
        ("leaf_exceptions", pa.list_(pa.struct([("field_id", pa.uint16()), ("leaf_index", pa.uint32()), ("code", pa.uint16())])))])
    mask_file = parquet(root / "compact_masks.parquet", masks, mask_schema)
    owner_file = parquet(root / "mask_owner_index.parquet", owner_index)
    codebook = write_json(root / "codebook.json", {"3": "SOURCE_CELL_NULL", "1": "REVIEW_ONLY"})
    field_map = write_json(root / "field_map.json", [{"field_id": 0, "field_key": "energy.value"}])
    config["_fixture_mask_config"] = {"registry": registry_ref, "field_map": field_map, "reason_codebook": codebook, "groups": [{"owner_index": owner_file, "owner_columns": {"record_ordinal": "record_ordinal", "molecule_id": "molecule_id", "native_record_id": "record_id"}, "geometry_source": "pm7", "mask_tables": [mask_file], "task_view_map": {"0": None, "1": "noise1"}}]}
    keys = {"molecule_id": "mid", "native_record_id": "record", "sprime_conf_idx": "idx", "view_id": "view", "geometry_id": "gid"}
    specs = []
    for src in ("pm7", "uff_sprime"):
        ref = parquet(root / (src + "_geometry_values.parquet"), [r for r in geometry_source if r["src"] == src])
        specs.append({"file": ref, "kind": "geometry", "geometry_source": src, "source_family": "geometry", "keys": keys, "n_atoms_from_array": "z", "requires_latest_owner": False,
            "arrays": {"atomic_numbers": {"column": "z"}, "positions_A": {"column": "xyz"}}})
    ref = parquet(root / "pm7_label_values.parquet", label_source)
    specs.append({"file": ref, "kind": "labels", "geometry_source": "pm7", "source_family": "synthetic", "keys": keys, "n_atoms_from_canonical_geometry": True, "requires_latest_owner": False,
        "targets": ["energy"], "components": {"energy.value": {"shape": [], "null_value_policy": "masked_nan", "value": {"column": "nested", "path": ["energy"]}, "compact": {"task_code_column": "mask_task", "field_id": 0}}}})
    export_config = {"registry": registry_ref, "mapping": mapping_ref, "subsets": ["pilot_train", "pilot_val"],
        "maximum_output_bytes": 200_000_000, "group_exposure_mask": {"P": True}, "family_exposure_mask": {"energy": True}, "partitions": []}
    for src in ("pm7", "uff_sprime"):
        for view in (None, "noise1"):
            export_config["partitions"].append({"name": src + ("_noise" if view else "_base"), "kind": "geometry", "geometry_source": src, "view_id": view, "map_bytes": 2 ** 24})
    for view in (None, "noise1"):
        export_config["partitions"].append({"name": "labels_" + ("noise" if view else "base"), "kind": "labels", "geometry_source": "pm7", "view_id": view, "family": "energy", "map_bytes": 2 ** 24})
    return config, specs, export_config


class PipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config, cls.specs, cls.export_config = fixture(ROOT / "inputs")
        cls.mask_config = cls.config.pop("_fixture_mask_config")
        cls.d5 = materialize.run(cls.config, ROOT / "d5", fixture=True)

    def test_01_materialized_nesting_diagnostic_and_view_filter(self):
        db = connect(ROOT / "d5" / "authority.sqlite", readonly=True)
        try:
            for a, b in (("pilot_train", "train_4"), ("train_4", "train_6"), ("train_6", "train_8"), ("train_8", "train_all")):
                self.assertEqual(db.execute("SELECT molecule_id FROM subset_members WHERE subset=? EXCEPT SELECT molecule_id FROM subset_members WHERE subset=?", (a, b)).fetchall(), [])
            self.assertEqual(db.execute("SELECT count(*) FROM diagnostic_base").fetchone()[0], 6)
            self.assertEqual(db.execute("SELECT count(*) FROM diagnostic_targets").fetchone()[0], 12)
            self.assertEqual(db.execute("SELECT count(*) FROM training_orders JOIN diagnostic_targets USING(geometry_id)").fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT count(*) FROM training_geometry JOIN diagnostic_targets USING(geometry_id)").fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT count(*) FROM diagnostic_base d JOIN orders o USING(geometry_id) WHERE o.order_type='fixed_random' AND o.rank!=2").fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT count(DISTINCT molecule_id) FROM ranked WHERE effective_role='VAL'").fetchone()[0], 3)
        finally:
            db.close()

    def test_02_distribution_denominators_and_absent_categories(self):
        result = distributions.run(ROOT / "d5" / "manifest.json", ROOT / "distributions", True)
        import pyarrow.parquet as pq
        rows = pq.read_table(result["tables"][0]["path"]).to_pylist()
        self.assertTrue(any(r["dimension"] == "scaffold" for r in rows))
        self.assertTrue(all(0 <= r["fraction"] <= 1 for r in rows))
        self.assertTrue(all(r["fraction_difference"] == 0 for r in rows if r["subset"] == r["baseline_subset"]))

    def test_03_production_does_not_accept_small_fixture_or_unfrozen_common(self):
        bad = copy.deepcopy(self.config)
        with self.assertRaisesRegex(ValueError, "FIXTURE_COUNTS_FORBIDDEN"):
            # This validates the production count guard directly, without
            # pretending a fixture is a Slurm allocation.
            old = materialize.check_allocation
            try:
                materialize.check_allocation = lambda fixture: None
                materialize.run(bad, ROOT / "forbidden_production")
            finally:
                materialize.check_allocation = old
        self.assertFalse((ROOT / "forbidden_production").exists())
        common = read_json(bad["common_manifest"]["path"]); common["status"] = "DRAFT"
        bad["common_manifest"] = write_json(ROOT / "inputs" / "draft_common.json", common)
        with self.assertRaisesRegex(ValueError, "MANIFEST_NOT_FROZEN"):
            materialize.run(bad, ROOT / "unfrozen", fixture=True)
        self.assertFalse((ROOT / "unfrozen").exists())

    def test_04_uff_identity_uses_molecule_and_index_not_native_record(self):
        db = connect(ROOT / "resolver.sqlite")
        try:
            db.execute("CREATE TABLE selected_geometry(geometry_id,molecule_id,geometry_source,native_record_id,sprime_conf_idx,parent_geometry_id,view_id,effective_role,source_role)")
            db.execute("CREATE TABLE latest_owners(geometry_id,source_family,task_name,attempt_id,job_id,task_id)")
            db.executemany("INSERT INTO selected_geometry VALUES(?,?,?,?,?,?,?,?,?)", [("opaque1", "m1", "uff_sprime", "same", 0, None, None, "TRAIN", "TRAIN"), ("opaque2", "m2", "uff_sprime", "same", 0, None, None, "VAL", "FULL")])
            spec = {"keys": {"molecule_id": "mid", "sprime_conf_idx": "idx", "native_record_id": "record"}, "geometry_source": "uff_sprime", "source_family": "geometry", "n_atoms_column": "n", "requires_latest_owner": False}
            result = export.resolve(db, {"mid": "m2", "idx": 0, "record": "ignored", "n": 2}, spec)
            self.assertEqual(result["geometry_id"], "opaque2")
            self.assertEqual(result["effective_role"], "VAL")
        finally:
            db.close()

    def test_05_source_selectors_float64_shape_and_compact_reason_granularity(self):
        row = {"cells": [{"registry_id": 9, "kind": 5, "shape": [3], "array_f64": [1., -0., 3.]}]}
        value = extract(row, {"column": "cells", "cell_registry_id": 9, "select_index": 1})
        self.assertTrue(np.signbit(value))
        for x in (np.array(0.123456789), np.array([-0., 1e-100])):
            actual = unpack(pack({"v": x}))["v"]
            self.assertEqual(actual.dtype, np.dtype("<f8")); self.assertEqual(actual.shape, x.shape)
            self.assertEqual(actual.tobytes(), x.tobytes())
        bits = lambda ids: sum(1 << i for i in ids).to_bytes(19, "little")
        row = {"in_scope_fields": bits([1]), "valid_fields": bits([]), "source_reason_groups": [{"code": 3, "fields": bits([1])}], "new_reason_groups": [], "leaf_exceptions": [], "review_groups": []}
        result = restore(row, 1, 3)
        self.assertEqual(result["valid"].tolist(), [0, 0, 0]); self.assertEqual(result["reason"].tolist(), [65535] * 3)
        self.assertEqual(result["field_reason_codes"], [3])

    def test_06_real_source_adapter_export_and_source_re_read(self):
        cfg = copy.deepcopy(self.export_config)
        cfg["d5_manifest"] = file_ref(ROOT / "d5" / "manifest.json")
        mask_cfg = copy.deepcopy(self.mask_config); mask_cfg["d5_manifest"] = cfg["d5_manifest"]
        bound = mask_binding.run(mask_cfg, ROOT / "bound_masks", True)
        cfg["source_manifest"] = write_json(ROOT / "inputs" / "source_manifest.json", {"status": "CANDIDATE", "geometry_map_manifest_sha256": self.d5["geometry_map"]["sha256"], "files": self.specs, "compact_mask_manifest": file_ref(ROOT / "bound_masks" / "manifest.json")})
        exported = export.run(cfg, ROOT / "export", fixture=True, candidate=True)
        self.assertEqual(len(exported["stores"]), 6)
        self.assertTrue(exported["source_float64_preserved_in_stage"])
        from .granular_store import GranularFamilyReader
        with GranularFamilyReader(ROOT / "export" / "labels_base") as reader:
            with reader.env.begin() as tx, tx.cursor(db=reader.records) as cursor:
                ids = [key.decode() for key, value in cursor]
            records = [reader.get(key) for key in ids]
            self.assertTrue(any(not arrays["valid/energy"].item() for meta, arrays in records))
            self.assertTrue(all("reason/energy" not in arrays for meta, arrays in records))
            self.assertTrue(all(meta["reason_codebook_sha256"] == bound["reason_codebook"]["sha256"] for meta, arrays in records))
        checked = roundtrip.run(ROOT / "export" / "manifest.json", ROOT / "roundtrip.json", fixture=True, sample_records=32)
        self.assertEqual(checked["records_checked_against_original_parquet"], 32)
        self.assertEqual(len({r["pid"] for r in checked["spawn_workers"]}), 16)
        self.assertTrue(checked["spawn_workers_all_joined"])
        self.assertFalse(checked["gpu_node_local_disk_benchmark"])

    def test_07_missing_order_and_parent_source_mismatch_fail(self):
        for mutation, expected in (("order", "THREE_COMPLETE_ORDER"), ("parent", "VIEW_PARENT_KEY")):
            original = connect(ROOT / "d5" / "authority.sqlite", readonly=True)
            db = connect(ROOT / ("corrupt_" + mutation + ".sqlite"))
            try:
                original.backup(db)
                if mutation == "order":
                    db.execute("DELETE FROM orders WHERE rowid=(SELECT min(rowid) FROM orders WHERE order_type='energy')")
                else:
                    db.execute("UPDATE geometries SET parent_geometry_id='missing-parent' WHERE rowid=(SELECT min(rowid) FROM geometries WHERE parent_geometry_id IS NOT NULL)")
                db.commit()
                with self.assertRaisesRegex(ValueError, expected):
                    materialize.validate(db)
            finally:
                db.close(); original.close()

    def test_08_compact_partial_and_review_preserve_granularity(self):
        from .source import target_arrays
        from .granular_store import validate
        from wire_v1.mapping import family_schema
        reg, mapping, compiled = fixture_mapping(kind="vector")
        bits = lambda ids: sum(1 << i for i in ids).to_bytes(19, "little")
        mask = {"in_scope_fields": bits([0, 1, 2]), "valid_fields": bits([0, 2]), "source_reason_groups": [{"code": 5, "fields": bits([1])}], "new_reason_groups": [], "review_groups": [{"code": 24, "fields": bits([0])}], "leaf_exceptions": []}
        components = {"dipole." + c: {"shape": [], "value": {"column": c}, "compact": {"column": "mask", "field_id": i}} for i, c in enumerate(("x", "y", "z"))}
        annotation = {}
        arrays = target_arrays({"x": 1., "y": 2., "z": 3., "mask": mask}, {"components": components}, mapping["physical_targets"][0], 2, annotations=annotation)
        metadata = {"molecule_id": "m", "export_record_id": "g", "geometry_source": "pm7", "effective_role": "TRAIN", "source_role": "TRAIN", "n_atoms": 2,
            "group_exposure_mask": {"P": True}, "family_exposure_mask": {"multipole": True}, "reason_granularity": annotation}
        schema = family_schema(compiled, "multipole", "pm7"); schema["mask_encoding"] = "field-set+sparse-leaf-v1"
        from wire_v1.codec import encode_record, decode_record
        _, converted = decode_record(encode_record(metadata, arrays))
        validate(metadata, converted, schema)
        self.assertEqual(converted["valid/dipole"].tolist(), [1, 0, 1])
        self.assertEqual(converted["reason_fields_review/dipole.x"].tolist(), [24])
        self.assertNotIn("reason/dipole", converted)
        # Partial per-atom generic exception is retained sparsely, never spread
        # to every atom or used to turn review flags into invalidity.
        mask["in_scope_fields"] = bits([0]); mask["valid_fields"] = bits([0]); mask["source_reason_groups"] = []
        mask["leaf_exceptions"] = [{"field_id": 0, "leaf_index": 1, "code": 5}]
        restored = restore(mask, 0, 3)
        self.assertEqual(restored["valid"].tolist(), [1, 0, 1])
        self.assertEqual(restored["partial_leaf_reason_codes"], [{"leaf_index": 1, "code": 5}])

    def test_09_latest_owner_types_task_partition_and_numeric_corruption(self):
        from wire_v1.codec import canonical_json
        db = connect(ROOT / "typed_owner.sqlite")
        try:
            db.execute("CREATE TABLE selected_geometry(geometry_id,molecule_id,geometry_source,native_record_id,sprime_conf_idx,parent_geometry_id,view_id,effective_role,source_role)")
            db.execute("CREATE TABLE latest_owners(geometry_id,source_family,task_name,attempt_id,job_id,task_id)")
            db.execute("INSERT INTO selected_geometry VALUES('g','m','pm7','native',NULL,NULL,NULL,'TRAIN','TRAIN')")
            db.execute("INSERT INTO latest_owners VALUES(?,?,?,?,?,?)", ("g", "pm7_neutral", "pm7_B", *[canonical_json(v).decode() for v in (1, 4514, "task-string")]))
            spec = {"keys": {"molecule_id": "m", "native_record_id": "r"}, "geometry_source": "pm7", "source_family": "pm7_neutral", "task": "pm7_B", "n_atoms_column": "n", "owner_keys": {"attempt_id": "a", "job_id": "job", "task_id": "task"}, "row_filters": {"calc_type": "pm7_B"}}
            row = {"m": "m", "r": "native", "n": 2, "a": 1, "job": 4514, "task": "task-string", "calc_type": "pm7_B"}
            self.assertEqual(export.resolve(db, row, spec)["geometry_id"], "g")
            self.assertIsNone(export.resolve(db, {**row, "a": "1"}, spec))
            self.assertIsNone(export.resolve(db, {**row, "calc_type": "other"}, spec))
        finally:
            db.close()
        expected = {"v": np.array([-0., .123456789])}
        actual = {"v": expected["v"].astype("<f4")}
        roundtrip.compare(expected, actual)
        actual["v"][0] = 0.
        with self.assertRaisesRegex(ValueError, "SIGNED_ZERO"):
            roundtrip.compare(expected, actual)

    def test_10_explicit_atom_scatter_and_missing_code_required(self):
        from .source import target_arrays
        reg, mapping, compiled = fixture_mapping(kind="scalar", level="atom", name="charge")
        selector = {"shape": ["n_atoms"], "value": {"column": "v"}, "valid": {"column": "ok"}, "reason": {"column": "why"}, "atom_indices": {"column": "idx"}, "missing_atom_reason_code": 60000}
        row = {"v": [2., 4.], "ok": [1, 1], "why": [0, 0], "idx": [2, 0]}
        result = target_arrays(row, {"components": {"charge.value": selector}}, mapping["physical_targets"][0], 3)
        self.assertEqual(result["valid/charge"].tolist(), [1, 0, 1])
        self.assertEqual(result["reason/charge"].tolist(), [0, 60000, 0])
        self.assertTrue(np.isnan(result["values/charge"][1]))
        bad = dict(selector); bad.pop("missing_atom_reason_code")
        with self.assertRaisesRegex(ValueError, "EXPLICIT_FROZEN_CODEBOOK"):
            target_arrays(row, {"components": {"charge.value": bad}}, mapping["physical_targets"][0], 3)


def main():
    global ROOT
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args(); ROOT = fresh_dir(args.output)
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(PipelineTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    write_json(ROOT / "test_summary.json", {"status": "PASS" if result.wasSuccessful() else "FAIL", "tests": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
        "source_data_read": False, "fixture_parquet_data_read": True, "contract_finalized": False, "source_files": [file_ref(path) for path in sorted(Path(__file__).parent.glob("*.py"))]})
    if not result.wasSuccessful():
        raise SystemExit(1)


if __name__ == "__main__":
    main()
