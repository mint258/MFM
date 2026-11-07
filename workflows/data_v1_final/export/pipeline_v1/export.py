"""Disk-backed source -> float64 staging -> per-family MFM3 float32 LMDB CLI."""
from __future__ import annotations
import argparse
import concurrent.futures
import contextlib
import json
import multiprocessing as mp
import os
from pathlib import Path
import sqlite3
from .io import (batches, check_allocation, connect, disk_cap, fresh_dir, manifest,
                 memory_guard, quota_preflight, read_json, reject_rows, scalar, verify, write_json)
from .source import geometry_arrays, pack, source_columns, target_arrays, unpack, reason_annotations
from .masks import encode_row, decode_row
from .granular_store import GranularFamilyWriter
from wire_v1.codec import canonical_json
from wire_v1.mapping import family_schema, preflight_registry
from wire_v1.store import file_ref

PIECES_SCHEMA = "geometry_id TEXT,part TEXT,n_atoms INTEGER,source_index INTEGER,row_group INTEGER,row_number INTEGER,payload BLOB,PRIMARY KEY(geometry_id,part)"
_PART_BYTES = None
_PART_CAP = None


def stage_initializer(counter, cap):
    global _PART_BYTES, _PART_CAP
    _PART_BYTES, _PART_CAP = counter, cap


def resolve(db, row, spec):
    if any(row[column] != expected for column, expected in spec.get("row_filters", {}).items()):
        return None
    keys = spec["keys"]
    mid, src = row[keys["molecule_id"]], spec["geometry_source"]
    if not isinstance(mid, str) or src not in {"pm7", "uff_sprime"}:
        raise ValueError("SOURCE_ID_OR_GEOMETRY_LITERAL")
    native = row[keys["native_record_id"]] if keys.get("native_record_id") else None
    idx = row[keys["sprime_conf_idx"]] if keys.get("sprime_conf_idx") else None
    view = row[keys["view_id"]] if keys.get("view_id") else None
    if src == "pm7":
        clause, physical = "native_record_id=?", native
        if not isinstance(native, str) or not native or idx is not None:
            raise ValueError("SOURCE_PM7_NATIVE_KEY_REQUIRED")
    else:
        clause, physical = "sprime_conf_idx=?", idx
        if type(idx) is not int or idx < 0:
            raise ValueError("SOURCE_UFF_KEY_REQUIRED_NO_RECORD_ID_JOIN")
    query = "SELECT * FROM selected_geometry WHERE molecule_id=? AND geometry_source=? AND " + clause + " AND view_id IS ?"
    found = db.execute(query, (mid, src, physical, view)).fetchall()
    if not found:
        return None
    if len(found) != 1:
        raise ValueError("AMBIGUOUS_PHYSICAL_TO_OPAQUE_GEOMETRY_MAP")
    geometry = dict(found[0])
    if keys.get("geometry_id") and row[keys["geometry_id"]] != geometry["geometry_id"]:
        raise ValueError("SOURCE_OPAQUE_GEOMETRY_ID_DISAGREES_WITH_PHYSICAL_KEY")
    owner = db.execute("SELECT * FROM latest_owners WHERE geometry_id=? AND source_family=? AND task_name=?", (geometry["geometry_id"], spec["source_family"], spec.get("task", ""))).fetchone()
    if owner is not None:
        if any(canonical_json(row[column]).decode() != owner[key] for key, column in spec.get("owner_keys", {}).items()):
            return None
        if set(spec.get("owner_keys", {})) != {"attempt_id", "job_id", "task_id"}:
            raise ValueError("COMPLETE_LATEST_OWNER_IDENTITY_KEYS_REQUIRED")
    elif spec.get("requires_latest_owner", True):
        raise ValueError("SELECTED_GEOMETRY_LATEST_OWNER_MISSING")
    if spec.get("n_atoms_column"):
        n = row[spec["n_atoms_column"]]
    elif spec.get("n_atoms_from_array"):
        n = len(row[spec["n_atoms_from_array"]])
    elif spec.get("n_atoms_from_canonical_geometry") is True:
        item = db.execute("SELECT n_atoms FROM pieces WHERE geometry_id=? AND part='__geometry__'", (geometry["geometry_id"],)).fetchone()
        if item is None:
            raise ValueError("CANONICAL_GEOMETRY_ATOM_COUNT_MISSING_BEFORE_LABEL_WAVE")
        n = item[0]
    else:
        raise ValueError("EXPLICIT_ATOM_COUNT_AUTHORITY_REQUIRED")
    if type(n) is not int or n <= 0:
        raise ValueError("SOURCE_ATOM_COUNT_INVALID")
    geometry["n_atoms"] = n
    return geometry


def source_worker(task):
    index, spec, groups, database, output, compiled = task
    db = connect(database, readonly=True)
    stage = connect(output)
    stage.execute("CREATE TABLE pieces(" + PIECES_SCHEMA + ")")
    count, examined, accounted = 0, 0, 0
    try:
        for rg in groups:
            number = 0
            for batch in batches(spec["file"], columns=source_columns(spec), row_groups=[rg], batch_size=16, hash_input=False):
                for row in batch.to_pylist():
                    geometry = resolve(db, row, spec)
                    examined += 1
                    if geometry is not None:
                        if spec["kind"] == "geometry":
                            parts = [("__geometry__", geometry_arrays(row, spec, geometry["n_atoms"]), {})]
                        else:
                            parts = []
                            def loader(cs):
                                if "column" in cs:
                                    from .source import extract
                                    return extract(row, cs)
                                code = row[cs["task_code_column"]] if "task_code_column" in cs else cs["task_code"]
                                mask = db.execute("SELECT payload FROM compact_masks WHERE geometry_id=? AND task_code=?", (geometry["geometry_id"], code)).fetchone()
                                if mask is None:
                                    raise ValueError("CANONICAL_COMPACT_MASK_BINDING_MISSING")
                                return decode_row(mask[0])
                            for tid in spec["targets"]:
                                annotations = {}
                                arrays = target_arrays(row, spec, compiled["physical_targets"][tid], geometry["n_atoms"], compact_loader=loader, annotations=annotations)
                                parts.append((tid, arrays, annotations))
                        for part, arrays, annotations in parts:
                            stage.execute("INSERT INTO pieces VALUES(?,?,?,?,?,?,?)", (geometry["geometry_id"], part, geometry["n_atoms"], index, rg, number, pack(arrays, annotations)))
                            count += 1
                    number += 1
                stage.commit()
                memory_guard()
                actual = Path(output).stat().st_size
                with _PART_BYTES.get_lock():
                    _PART_BYTES.value += actual - accounted
                    accounted = actual
                    if _PART_BYTES.value > _PART_CAP:
                        raise ValueError("SHARED_SOURCE_STAGING_PART_BYTE_CAP_EXCEEDED")
    finally:
        stage.close(); db.close()
    return {"path": str(output), "source_index": index, "row_groups": groups,
            "source_rows_examined": examined, "pieces": count, "pid": os.getpid(), "process_peak_rss_bytes": memory_guard()}


def check_source_spec(spec, compiled, production):
    if spec["kind"] not in {"geometry", "labels"} or spec["geometry_source"] not in {"pm7", "uff_sprime"}:
        raise ValueError("SOURCE_KIND_OR_GEOMETRY_CONTEXT")
    if production and (spec.get("source_identity_verified") is not True or spec.get("mask_authority_verified") is not True):
        raise ValueError("SOURCE_OR_MASK_AUTHORITY_NOT_VERIFIED")
    if spec["kind"] == "geometry":
        if production and (spec.get("position_unit") != "angstrom" or spec.get("atom_order_verified") is not True):
            raise ValueError("SOURCE_GEOMETRY_UNIT_OR_ATOM_ORDER_PENDING")
    else:
        if not spec.get("targets") or len(set(spec["targets"])) != len(spec["targets"]):
            raise ValueError("SOURCE_TARGET_LIST_INVALID")
        expected = set()
        for tid in spec["targets"]:
            target = compiled["physical_targets"][tid]
            if target["geometry_source"] != spec["geometry_source"]:
                raise ValueError("SOURCE_TARGET_GEOMETRY_MISMATCH")
            expected.update(m["field_key"] for m in target["members"])
        if expected != set(spec["components"]):
            raise ValueError("SOURCE_COMPONENT_SELECTORS_EXACT_COVERAGE_REQUIRED")
        if production and not spec.get("mask_authority"):
            raise ValueError("MASK_AUTHORITY_PIN_REQUIRED")
        if spec.get("mask_authority"):
            verify(spec["mask_authority"])
        if production and spec.get("requires_latest_owner", True) is not True:
            raise ValueError("PRODUCTION_LABELS_REQUIRE_COMPLETE_LATEST_OWNER_KEYS")


def prepare_selection(db, d5, config, fixture, output):
    import pyarrow as pa
    from .io import query_parquet
    if d5.get("status") != ("FIXTURE_ONLY" if fixture else "D5_PARQUET_LISTS_FROZEN"):
        raise ValueError("D5_LISTS_NOT_FROZEN_FOR_REQUESTED_MODE")
    db.executescript("""
      CREATE TABLE selected_molecules(molecule_id TEXT PRIMARY KEY,effective_role TEXT);
      CREATE TABLE selected_geometry(geometry_id TEXT PRIMARY KEY,molecule_id TEXT,geometry_source TEXT,native_record_id TEXT,sprime_conf_idx INTEGER,parent_geometry_id TEXT,view_id TEXT,effective_role TEXT,source_role TEXT);
      CREATE TABLE latest_owners(geometry_id TEXT,source_family TEXT,task_name TEXT,attempt_id TEXT,job_id TEXT,task_id TEXT,PRIMARY KEY(geometry_id,source_family,task_name));
      CREATE TABLE compact_masks(geometry_id TEXT,task_code INTEGER,payload TEXT,PRIMARY KEY(geometry_id,task_code));
      CREATE TABLE pieces(""" + PIECES_SCHEMA + ");")
    names = config["subsets"]
    if not fixture and names != ["pilot_train", "pilot_val"]:
        if config.get("full_export_authorized_after_model_loader_acceptance") is not True:
            raise ValueError("FULL_EXPORT_REQUIRES_PRIOR_REAL_PILOT_MODEL_LOADER_ACCEPTANCE")
    if not names or len(names) != len(set(names)):
        raise ValueError("SUBSETS_MUST_BE_EXPLICIT_AND_UNIQUE")
    for name in names:
        for batch in batches(d5["subsets"][name]):
            for row in batch.to_pylist():
                old = db.execute("SELECT effective_role FROM selected_molecules WHERE molecule_id=?", (row["molecule_id"],)).fetchone()
                if old is not None and old[0] != row["effective_role"]:
                    raise ValueError("SUBSET_ROLE_DISAGREES")
                db.execute("INSERT OR IGNORE INTO selected_molecules VALUES(?,?)", (row["molecule_id"], row["effective_role"]))
    for batch in batches(d5["training_geometry"]):
        for row in batch.to_pylist():
            selected = db.execute("SELECT effective_role FROM selected_molecules WHERE molecule_id=?", (row["molecule_id"],)).fetchone()
            if selected is None:
                continue
            if row["effective_role"] != selected[0]:
                raise ValueError("GEOMETRY_SUBSET_ROLE_DISAGREES")
            db.execute("INSERT INTO selected_geometry VALUES(?,?,?,?,?,?,?,?,?)", tuple(row[k] for k in ("geometry_id", "molecule_id", "geometry_source", "native_record_id", "sprime_conf_idx", "parent_geometry_id", "view_id", "effective_role", "source_role")))
    db.execute("CREATE INDEX physical_lookup ON selected_geometry(molecule_id,geometry_source,native_record_id,sprime_conf_idx,view_id)")
    diagnostic = read_json(verify(d5["diagnostic"]))
    if diagnostic.get("status") != ("FIXTURE_ONLY" if fixture else "SEEN_MOLECULE_UNSEEN_GEOMETRY_DIAGNOSTIC_FROZEN"):
        raise ValueError("DIAGNOSTIC_EXCLUSION_AUTHORITY_NOT_FROZEN")
    if diagnostic["geometry_map_manifest_sha256"] != d5["geometry_map"]["sha256"]:
        raise ValueError("DIAGNOSTIC_GEOMETRY_MAP_BINDING")
    for ref in diagnostic["target_exclusion_tables"]:
        for batch in batches(ref):
            for row in batch.to_pylist():
                if db.execute("SELECT 1 FROM selected_geometry WHERE geometry_id=?", (row["geometry_id"],)).fetchone():
                    raise ValueError("DIAGNOSTIC_BASE_OR_VIEW_LEAKS_INTO_EXPORT_TRAINING_SELECTION")
    if not fixture and names == ["pilot_train", "pilot_val"]:
        if scalar(db, "SELECT count(*) FROM selected_molecules WHERE effective_role='TRAIN'") != 50000 or scalar(db, "SELECT count(*) FROM selected_molecules WHERE effective_role='VAL'") != 5000:
            raise ValueError("PRODUCTION_PILOT_MOLECULE_COUNTS_MUST_BE_50000_AND_5000")
    db.commit()


def export_families(db, out, compiled, config):
    stores = []
    # Explicit partitions prevent a gradient view being silently treated as a
    # parent geometry, or a P value copied to an S' condition.
    partitioned = set()
    for partition in config["partitions"]:
        name, kind, src, view = (partition[k] for k in ("name", "kind", "geometry_source", "view_id"))
        if not isinstance(name, str) or not name or Path(name).name != name:
            raise ValueError("SAFE_EXPLICIT_PARTITION_NAME_REQUIRED")
        if kind == "geometry":
            schema, targets = {"kind": "geometry"}, ["__geometry__"]
        elif kind == "labels":
            schema = family_schema(compiled, partition["family"], src)
            schema["mask_encoding"] = "field-set+sparse-leaf-v1"
            targets = list(schema["compiled"]["physical_targets"])
            for tid in targets:
                key = (tid, view)
                if key in partitioned:
                    raise ValueError("DUPLICATE_TARGET_VIEW_PARTITION")
                partitioned.add(key)
        else:
            raise ValueError("PARTITION_KIND_INVALID")
        query = "SELECT * FROM selected_geometry WHERE geometry_source=? AND view_id IS ? ORDER BY geometry_id"
        path = out / name
        with contextlib.ExitStack() as stack:
            writer = GranularFamilyWriter(path, schema, map_bytes=partition["map_bytes"])
            stack.callback(writer.close)
            for geometry in db.execute(query, (src, view)):
                size = scalar(db, "SELECT coalesce(sum(length(payload)),0) FROM pieces WHERE geometry_id=?", (geometry["geometry_id"],))
                if size > 128 * 1024 ** 2:
                    raise ValueError("GEOMETRY_STAGING_PAYLOAD_EXCEEDS_128MIB")
                pieces = db.execute("SELECT part,n_atoms,payload FROM pieces WHERE geometry_id=?", (geometry["geometry_id"],)).fetchall()
                by_part = {p["part"]: p for p in pieces}
                missing = set(targets) - set(by_part)
                if missing:
                    raise ValueError("CANONICAL_SOURCE_RECORD_OR_TARGET_MISSING:" + geometry["geometry_id"] + ":" + ",".join(sorted(missing)))
                ns = {by_part[t]["n_atoms"] for t in targets}
                if len(ns) != 1 or ("__geometry__" in by_part and by_part["__geometry__"]["n_atoms"] not in ns):
                    raise ValueError("SOURCE_GEOMETRY_AND_LABEL_ATOM_COUNTS_DISAGREE")
                arrays, granularity, null_fields = {}, {}, []
                for tid in targets:
                    value = unpack(by_part[tid]["payload"])
                    if set(arrays) & set(value):
                        raise ValueError("DUPLICATED_EXPORT_ARRAY")
                    arrays.update(value)
                    note = reason_annotations(by_part[tid]["payload"])
                    null_fields.extend(note.pop("_source_null_fields", []))
                    granularity.update(note)
                metadata = {"molecule_id": geometry["molecule_id"], "export_record_id": geometry["geometry_id"],
                    "geometry_source": src, "effective_role": geometry["effective_role"], "source_role": geometry["source_role"],
                    "n_atoms": ns.pop(), "parent_geometry_id": geometry["parent_geometry_id"], "view_id": view}
                if kind == "labels":
                    # These are recipe exposure decisions, not validity masks.
                    metadata["group_exposure_mask"] = config["group_exposure_mask"]
                    metadata["family_exposure_mask"] = config["family_exposure_mask"]
                    if granularity:
                        metadata["reason_granularity"] = granularity
                        metadata["reason_codebook_sha256"] = config.get("_reason_codebook_sha256")
                    if null_fields:
                        metadata["source_null_fields_with_masked_nan_placeholder"] = sorted(null_fields)
                writer.write_batch([(metadata, arrays)])
                db.execute("INSERT INTO exported VALUES(?,?,?,?)", (name, geometry["geometry_id"], kind, canonical_json(targets).decode()))
                memory_guard(3_000_000_000)
                if writer.count % 512 == 0:
                    disk_cap(out, config["maximum_output_bytes"])
            receipt = writer.finish()
        if receipt["records"] <= 0:
            raise ValueError("EMPTY_EXPORT_PARTITION_NOT_ALLOWED")
        expected_records = scalar(db, "SELECT count(*) FROM selected_geometry WHERE geometry_source=? AND view_id IS ?", (src, view))
        expected_molecules = scalar(db, "SELECT count(DISTINCT molecule_id) FROM selected_geometry WHERE geometry_source=? AND view_id IS ?", (src, view))
        if receipt["records"] != expected_records or receipt["molecules"] != expected_molecules:
            raise ValueError("D5_EXPECTED_RECORD_OR_MOLECULE_COUNT_DIFFERS_FROM_WRITTEN_STORE")
        stores.append({"name": name, "kind": kind, "path": str(path), "manifest": file_ref(path / "manifest.json"), **receipt,
            "expected_records_from_frozen_selection": expected_records, "expected_molecules_from_frozen_selection": expected_molecules,
            "geometry_source": src, "view_id": view, "base_conformers": expected_records if view is None else 0})
    expected = set(compiled["physical_targets"])
    if {tid for tid, _ in partitioned} != expected:
        raise ValueError("MAPPING_TARGETS_NOT_FULLY_EXPORTED")
    reject_rows(db, "SELECT geometry_id FROM selected_geometry EXCEPT SELECT geometry_id FROM exported WHERE kind='geometry'", "SELECTED_BASE_OR_VIEW_GEOMETRY_NOT_EXPORTED")
    db.commit()
    return stores


def run(config, output, *, fixture=False, candidate=False):
    import pyarrow.parquet as pq
    config = dict(config)
    check_allocation(fixture)
    quota_preflight(config, fixture)
    registry = read_json(verify(config["registry"]))
    mapping = read_json(verify(config["mapping"]))
    compiled = preflight_registry(registry, mapping, require_final=not candidate and not fixture)
    if not (candidate or fixture):
        contract = read_json(verify(config["joint_contract"]))
        if contract.get("status") != "MODEL_DATA_JOINT_CONTRACT_FROZEN" or contract.get("version") != "3.0" or not contract.get("model_confirmation") or not contract.get("data_confirmation"):
            raise ValueError("JOINT_MODEL_DATA_V3_0_CONTRACT_NOT_FROZEN")
        if contract.get("mask_granularity") != "field-set+sparse-leaf-v1":
            raise ValueError("GRANULAR_MASK_EXTENSION_NOT_JOINTLY_ACCEPTED")
    d5 = read_json(verify(config["d5_manifest"]))
    source = read_json(verify(config["source_manifest"]))
    if not (candidate or fixture) and source.get("status") != "CANONICAL_EXPORT_SOURCE_V1_FROZEN":
        raise ValueError("CANONICAL_SOURCE_MAPPING_NOT_FROZEN")
    if source.get("geometry_map_manifest_sha256") != d5["geometry_map"]["sha256"]:
        raise ValueError("SOURCE_GEOMETRY_MAP_NOT_BOUND")
    specs = source["files"]
    if not specs:
        raise ValueError("NO_PINNED_REAL_SOURCE_FILES_NO_FAKE_DATA_ALLOWED")
    for spec in specs:
        verify(spec["file"])
        check_source_spec(spec, compiled, not (candidate or fixture))
    out = fresh_dir(output)
    db = connect(out / "export_stage.sqlite")
    results = []
    try:
        prepare_selection(db, d5, config, fixture, out)
        compact_ref = source.get("compact_mask_manifest")
        if compact_ref:
            compact = read_json(verify(compact_ref))
            if compact.get("status") != ("FIXTURE_ONLY" if fixture else "COMPACT_MASK_GEOMETRY_BINDING_V1_FROZEN") or compact.get("geometry_map_manifest_sha256") != d5["geometry_map"]["sha256"] or compact.get("registry_sha256") != config["registry"]["sha256"]:
                raise ValueError("COMPACT_MASK_BINDING_NOT_FROZEN_OR_UNBOUND")
            verify(compact["reason_codebook"])
            config["_reason_codebook_sha256"] = compact["reason_codebook"]["sha256"]
            field_map = read_json(verify(compact["field_map"]))
            ids = {f["field_key"]: f["field_id"] for f in field_map}
            for spec in specs:
                for key, selector in spec.get("components", {}).items():
                    if "compact" in selector and ids.get(key) != selector["compact"]["field_id"]:
                        raise ValueError("COMPACT_FIELD_ID_DIFFERS_FROM_PINNED_SOURCE_FIELD_MAP")
            for ref in compact["mask_tables"]:
                for batch in batches(ref):
                    for row in batch.to_pylist():
                        if db.execute("SELECT 1 FROM selected_geometry WHERE geometry_id=?", (row["geometry_id"],)).fetchone():
                            db.execute("INSERT INTO compact_masks VALUES(?,?,?)", (row["geometry_id"], row["task_code"], encode_row(row)))
        owners_ref = source.get("latest_owner_manifest")
        if owners_ref:
            owners = read_json(verify(owners_ref))
            if owners.get("status") != "CANONICAL_LATEST_OWNERS_FROZEN":
                raise ValueError("LATEST_OWNER_MANIFEST_NOT_FROZEN")
            if owners.get("geometry_map_manifest_sha256") != d5["geometry_map"]["sha256"]:
                raise ValueError("LATEST_OWNERS_GEOMETRY_MAP_BINDING")
            for ref in owners["owner_tables"]:
                for batch in batches(ref):
                    for row in batch.to_pylist():
                        if db.execute("SELECT 1 FROM selected_geometry WHERE geometry_id=?", (row["geometry_id"],)).fetchone():
                            db.execute("INSERT INTO latest_owners VALUES(?,?,?,?,?,?)", (row["geometry_id"], row["source_family"], row["task_name"], *[canonical_json(row[k]).decode() for k in ("attempt_id", "job_id", "task_id")]))
        elif not (candidate or fixture):
            raise ValueError("LATEST_OWNER_AUTHORITY_REQUIRED_FOR_PRODUCTION")
        db.commit()
        tasks = []
        for index, spec in enumerate(specs):
            for rg in range(pq.ParquetFile(verify(spec["file"], content=False)).metadata.num_row_groups):
                tasks.append((index, spec, [rg], str(out / "export_stage.sqlite"), str(out / ("source-stage-" + str(len(tasks)).zfill(6) + ".sqlite")), compiled))
        # Real WP5 D20/D3 rows have no total_atoms column. The geometry wave
        # establishes the canonical atom count before any label worker starts.
        context = mp.get_context("spawn")
        counter = context.Value("q", 0)
        part_cap = config.get("maximum_staging_part_bytes", config["maximum_output_bytes"] // 3)
        if not 0 < part_cap <= config["maximum_output_bytes"]:
            raise ValueError("BOUNDED_SHARED_STAGING_PART_CAP_REQUIRED")
        for kind in ("geometry", "labels"):
            wave = [task for task in tasks if task[1]["kind"] == kind]
            with concurrent.futures.ProcessPoolExecutor(max_workers=16, mp_context=context, initializer=stage_initializer, initargs=(counter, part_cap)) as pool:
                for result in pool.map(source_worker, wave, chunksize=1):
                    db.execute("ATTACH DATABASE ? AS shard", (result["path"],))
                    try:
                        db.execute("INSERT INTO pieces SELECT * FROM shard.pieces")
                        db.commit()
                    finally:
                        db.execute("DETACH DATABASE shard")
                    results.append(result)
                    disk_cap(out, config["maximum_output_bytes"])
        # Mandatory geometry sources for both inputs, even if a label family
        # alone would otherwise happen to pass its shape checks.
        reject_rows(db, "SELECT 1 FROM selected_geometry g LEFT JOIN pieces p ON p.geometry_id=g.geometry_id AND p.part='__geometry__' WHERE p.geometry_id IS NULL", "MISSING_CANONICAL_SOURCE_GEOMETRY")
        db.execute("CREATE TABLE exported(store_name TEXT,geometry_id TEXT,kind TEXT,parts_json TEXT,PRIMARY KEY(store_name,geometry_id))")
        stores = export_families(db, out, compiled, config)
        total = disk_cap(out, config["maximum_output_bytes"])
        result = {"status": "FIXTURE_ONLY" if fixture else "CANDIDATE_FAMILY_EXPORT_WRITTEN_NOT_RELEASE", "candidate": candidate or fixture, "contract_finalized": False, "d3_accepted": False, "source_data_read": True, "config_sources": {k: config[k] for k in ("registry", "mapping", "d5_manifest", "source_manifest")}, "stores": stores, "stage": file_ref(out / "export_stage.sqlite"), "source_worker_results": results, "effective_worker_pids": sorted({r["pid"] for r in results}), "source_float64_preserved_in_stage": True, "final_float32_conversion": "once in MFM3 FamilyWriter", "total_bytes_before_receipt": total, "verification_required": ">=10000 records source re-read by verify CLI, plus 16-spawn read/close/count/hash; GPU local-disk throughput remains separate"}
        write_json(out / "manifest.json", result)
        return result
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--candidate-only", action="store_true")
    parser.add_argument("--fixture", action="store_true")
    args = parser.parse_args()
    run(read_json(args.config), args.output, fixture=args.fixture, candidate=args.candidate_only)


if __name__ == "__main__":
    main()
