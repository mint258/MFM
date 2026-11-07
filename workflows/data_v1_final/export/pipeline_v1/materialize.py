"""D5 disk-backed authority validation, geometry map and real Parquet lists."""
from __future__ import annotations
import argparse
import concurrent.futures
import json
import multiprocessing as mp
import os
from pathlib import Path
import sqlite3
from .io import (batches, check_allocation, connect, disk_cap, fresh_dir, manifest,
                 memory_guard, query_parquet, quota_preflight, rank_hash, read_json, reject_rows, scalar, verify, write_json)
from wire_v1.store import file_ref

SCHEMA = {
 "roles": "molecule_id TEXT PRIMARY KEY,effective_role TEXT NOT NULL,source_role TEXT NOT NULL",
 "common": "molecule_id TEXT PRIMARY KEY,common_population INTEGER NOT NULL CHECK(common_population IN(0,1))",
 "geometries": "geometry_id TEXT PRIMARY KEY,molecule_id TEXT NOT NULL,geometry_source TEXT NOT NULL,native_record_id TEXT,sprime_conf_idx INTEGER,parent_geometry_id TEXT,view_id TEXT",
 "orders": "molecule_id TEXT NOT NULL,geometry_source TEXT NOT NULL,order_type TEXT NOT NULL,rank INTEGER NOT NULL CHECK(rank>=0),geometry_id TEXT NOT NULL,PRIMARY KEY(molecule_id,geometry_source,order_type,rank),UNIQUE(geometry_id,order_type)",
 "features": "molecule_id TEXT PRIMARY KEY,elements_json TEXT NOT NULL,heavy_atoms INTEGER NOT NULL,scaffold_id TEXT NOT NULL",
}
COLUMNS = {
 "roles": ["molecule_id", "effective_role", "source_role"],
 "common": ["molecule_id", "common_population"],
 "geometries": ["geometry_id", "molecule_id", "geometry_source", "native_record_id", "sprime_conf_idx", "parent_geometry_id", "view_id"],
 "orders": ["molecule_id", "geometry_source", "order_type", "rank", "geometry_id"],
 "features": ["molecule_id", "element_z", "heavy_atoms", "scaffold_id"],
}


def text(value):
    if not isinstance(value, str) or not value or "\0" in value:
        raise ValueError("NONEMPTY_LITERAL_STRING_ID_REQUIRED")
    return value


def normalize(kind, row):
    mid = text(row["molecule_id"])
    if kind == "roles":
        if row["effective_role"] not in {"TRAIN", "VAL", "FULL", "embargo"}:
            raise ValueError("ROLE_LITERAL_INVALID")
        return mid, row["effective_role"], text(row["source_role"])
    if kind == "common":
        if type(row["common_population"]) is not bool:
            raise ValueError("COMMON_MEMBERSHIP_MUST_BE_BOOL")
        return mid, int(row["common_population"])
    if kind == "features":
        z = row["element_z"]
        if not isinstance(z, list) or not z or any(type(v) is not int or not 1 <= v <= 118 for v in z):
            raise ValueError("ELEMENT_MEMBERSHIP_INVALID")
        if type(row["heavy_atoms"]) is not int or row["heavy_atoms"] <= 0:
            raise ValueError("MOLECULAR_SIZE_INVALID")
        # Empty scaffold string is an explicit acyclic category, not missing.
        if not isinstance(row["scaffold_id"], str):
            raise ValueError("SCAFFOLD_AUTHORITY_REQUIRED")
        return mid, json.dumps(sorted(set(z))), row["heavy_atoms"], row["scaffold_id"]
    src = row["geometry_source"]
    if src not in {"pm7", "uff_sprime"}:
        raise ValueError("GEOMETRY_SOURCE_LITERAL_INVALID")
    gid = text(row["geometry_id"])
    if kind == "orders":
        if row["order_type"] not in {"fixed_random", "energy", "diversity"} or type(row["rank"]) is not int:
            raise ValueError("ORDER_LITERAL_OR_RANK_INVALID")
        return mid, src, row["order_type"], row["rank"], gid
    native, idx = row["native_record_id"], row["sprime_conf_idx"]
    if src == "pm7" and (not isinstance(native, str) or not native or idx is not None):
        raise ValueError("PM7_NATIVE_RECORD_KEY_REQUIRED_NO_UFF_INDEX")
    if src == "uff_sprime" and (type(idx) is not int or idx < 0):
        raise ValueError("UFF_MOLECULE_CONFORMER_KEY_REQUIRED")
    parent, view = row["parent_geometry_id"], row["view_id"]
    if (parent is None) != (view is None):
        raise ValueError("VIEW_AND_PARENT_MUST_BE_EXPLICIT_TOGETHER")
    if parent is not None:
        text(parent); text(view)
        if parent == gid:
            raise ValueError("SELF_PARENT_GEOMETRY")
    return gid, mid, src, native, idx, parent, view


def ingest_worker(task):
    kind, ref, groups, destination = task
    db = connect(destination)
    db.execute("CREATE TABLE data(" + SCHEMA[kind] + ")")
    count = 0
    try:
        for batch in batches(ref, columns=COLUMNS[kind], row_groups=groups, hash_input=False):
            rows = [normalize(kind, row) for row in batch.to_pylist()]
            db.executemany("INSERT INTO data VALUES(" + ",".join("?" for _ in rows[0]) + ")", rows)
            db.commit(); count += len(rows)
            memory_guard()
    finally:
        db.close()
    return {"kind": kind, "path": destination, "rows": count, "pid": os.getpid(), "row_groups": groups, "process_peak_rss_bytes": memory_guard()}


def import_tables(db, sources, output, workers):
    import pyarrow.parquet as pq
    tasks = []
    for kind, refs in sources.items():
        for ref in refs:
            p = verify(ref)
            metadata = pq.ParquetFile(p).metadata
            # One row-group assigned once. No worker repeats another input scan.
            for rg in range(metadata.num_row_groups):
                tasks.append((kind, ref, [rg], str(output / ("ingest-" + str(len(tasks)).zfill(6) + ".sqlite"))))
    results = []
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers, mp_context=mp.get_context("spawn")) as pool:
        for result in pool.map(ingest_worker, tasks, chunksize=1):
            db.execute("ATTACH DATABASE ? AS shard", (result["path"],))
            try:
                db.execute("INSERT INTO " + result["kind"] + " SELECT * FROM shard.data")
                db.commit()
            finally:
                db.execute("DETACH DATABASE shard")
            results.append(result)
    return results


def validate(db):
    reject_rows(db, "SELECT molecule_id FROM common EXCEPT SELECT molecule_id FROM roles", "UNKNOWN_COMMON_MOLECULE")
    reject_rows(db, "SELECT molecule_id FROM roles EXCEPT SELECT molecule_id FROM common", "COMMON_AUTHORITY_MISSING_MOLECULES")
    reject_rows(db, "SELECT 1 FROM common JOIN roles USING(molecule_id) WHERE common_population=1 AND effective_role NOT IN('TRAIN','VAL')", "COMMON_INCLUDES_FULL_OR_EMBARGO")
    reject_rows(db, "SELECT 1 FROM geometries g LEFT JOIN common c USING(molecule_id) WHERE c.molecule_id IS NULL OR c.common_population!=1", "GEOMETRY_OUTSIDE_FROZEN_COMMON")
    reject_rows(db, "SELECT 1 FROM geometries g LEFT JOIN geometries p ON p.geometry_id=g.parent_geometry_id WHERE g.parent_geometry_id IS NOT NULL AND (p.geometry_id IS NULL OR p.parent_geometry_id IS NOT NULL OR p.molecule_id!=g.molecule_id OR p.geometry_source!=g.geometry_source OR p.native_record_id IS NOT g.native_record_id OR p.sprime_conf_idx IS NOT g.sprime_conf_idx)", "VIEW_PARENT_KEY_OR_CONTEXT_INVALID")
    db.executescript("""
      CREATE UNIQUE INDEX IF NOT EXISTS pm7_physical ON geometries(molecule_id,native_record_id) WHERE geometry_source='pm7' AND parent_geometry_id IS NULL;
      CREATE UNIQUE INDEX IF NOT EXISTS uff_physical ON geometries(molecule_id,sprime_conf_idx) WHERE geometry_source='uff_sprime' AND parent_geometry_id IS NULL;
      CREATE INDEX IF NOT EXISTS geometry_mol ON geometries(molecule_id,geometry_source);
      CREATE INDEX IF NOT EXISTS geometry_parent ON geometries(parent_geometry_id);
    """)
    reject_rows(db, "SELECT 1 FROM orders o LEFT JOIN geometries g USING(geometry_id) WHERE g.geometry_id IS NULL OR g.parent_geometry_id IS NOT NULL OR o.molecule_id!=g.molecule_id OR o.geometry_source!=g.geometry_source", "ORDER_NOT_BOUND_TO_BASE_GEOMETRY")
    reject_rows(db, "SELECT 1 FROM geometries g LEFT JOIN orders o USING(geometry_id) WHERE g.parent_geometry_id IS NULL GROUP BY g.geometry_id HAVING count(o.order_type)!=3", "THREE_COMPLETE_ORDER_PERMUTATIONS_REQUIRED")
    reject_rows(db, "SELECT 1 FROM orders GROUP BY molecule_id,geometry_source,order_type HAVING min(rank)!=0 OR max(rank)+1!=count(*)", "ORDER_RANK_NOT_CONTIGUOUS_ZERO_BASED")
    reject_rows(db, "SELECT 1 FROM common c LEFT JOIN geometries g ON c.molecule_id=g.molecule_id AND g.parent_geometry_id IS NULL WHERE c.common_population=1 GROUP BY c.molecule_id HAVING count(DISTINCT g.geometry_source)!=2", "COMMON_REQUIRES_BOTH_GEOMETRY_SOURCES")
    reject_rows(db, "SELECT 1 FROM common c LEFT JOIN features f USING(molecule_id) WHERE c.common_population=1 AND f.molecule_id IS NULL", "FROZEN_ELEMENT_SIZE_SCAFFOLD_FEATURES_MISSING")


def selection(db, seed, sizes, pilot_train, pilot_val, diagnostic):
    db.create_function("rank_hash", 2, lambda domain, mid: rank_hash(seed, domain, mid), deterministic=True)
    db.executescript("""
      CREATE TABLE ranked AS SELECT r.molecule_id,r.effective_role,r.source_role,
       row_number() OVER(PARTITION BY effective_role ORDER BY rank_hash(effective_role,r.molecule_id),r.molecule_id)-1 AS selection_rank
       FROM roles r JOIN common c USING(molecule_id) WHERE c.common_population=1;
      CREATE UNIQUE INDEX ranked_mol ON ranked(molecule_id);
      CREATE TABLE subset_members(subset TEXT,molecule_id TEXT,effective_role TEXT,selection_rank INTEGER,PRIMARY KEY(subset,molecule_id));
    """)
    ntrain = scalar(db, "SELECT count(*) FROM ranked WHERE effective_role='TRAIN'")
    nval = scalar(db, "SELECT count(*) FROM ranked WHERE effective_role='VAL'")
    if ntrain < sizes[-1] or nval < pilot_val:
        raise ValueError("COMMON_POPULATION_TOO_SMALL_FOR_GUIDE_COUNTS")
    subsets = {"train_all": ("TRAIN", ntrain), "val_all": ("VAL", nval),
               "pilot_train": ("TRAIN", pilot_train), "pilot_val": ("VAL", pilot_val)}
    subsets.update({"train_" + str(n): ("TRAIN", n) for n in sizes})
    for name, (role, n) in subsets.items():
        db.execute("INSERT INTO subset_members SELECT ?,molecule_id,effective_role,selection_rank FROM ranked WHERE effective_role=? AND selection_rank<?", (name, role, n))
    db.execute("""CREATE TABLE diagnostic_molecules AS SELECT molecule_id FROM (
       SELECT r.molecule_id FROM ranked r JOIN geometries g USING(molecule_id)
       WHERE r.effective_role='TRAIN' AND g.parent_geometry_id IS NULL
       GROUP BY r.molecule_id HAVING sum(g.geometry_source='pm7')>=2 AND sum(g.geometry_source='uff_sprime')>=2)
       ORDER BY rank_hash('diagnostic',molecule_id),molecule_id LIMIT ?""", (diagnostic,))
    if scalar(db, "SELECT count(*) FROM diagnostic_molecules") != diagnostic:
        raise ValueError("NOT_ENOUGH_DIAGNOSTIC_MOLECULES_NO_COUNT_DOWNGRADE")
    db.executescript("""
      CREATE TABLE diagnostic_base AS SELECT o.molecule_id,o.geometry_source,o.geometry_id
        FROM orders o JOIN diagnostic_molecules d USING(molecule_id)
        WHERE o.order_type='fixed_random' AND o.rank=(SELECT max(x.rank) FROM orders x WHERE x.molecule_id=o.molecule_id AND x.geometry_source=o.geometry_source AND x.order_type='fixed_random');
      CREATE UNIQUE INDEX diagnostic_key ON diagnostic_base(geometry_id);
      CREATE TABLE diagnostic_targets AS SELECT g.molecule_id,g.geometry_source,g.geometry_id FROM geometries g
        JOIN diagnostic_base d ON g.geometry_id=d.geometry_id OR g.parent_geometry_id=d.geometry_id;
      CREATE UNIQUE INDEX diagnostic_target_key ON diagnostic_targets(geometry_id);
      CREATE TABLE training_orders AS SELECT o.*,row_number() OVER(PARTITION BY o.molecule_id,o.geometry_source,o.order_type ORDER BY o.rank)-1 AS training_rank
        FROM orders o LEFT JOIN diagnostic_targets d USING(geometry_id) WHERE d.geometry_id IS NULL;
      CREATE TABLE training_geometry AS SELECT g.* FROM geometries g LEFT JOIN diagnostic_targets d USING(geometry_id) WHERE d.geometry_id IS NULL;
    """)
    if scalar(db, "SELECT count(*) FROM diagnostic_base") != 2 * diagnostic:
        raise ValueError("DIAGNOSTIC_BASE_PAIR_COUNT_DIFFERS")
    db.commit()
    return {name: n for name, (_, n) in subsets.items()}


def run(config, output, *, fixture=False, workers=16):
    import pyarrow as pa
    if workers != 16:
        raise ValueError("EXACTLY_16_DISJOINT_INPUT_WORKERS_REQUIRED")
    check_allocation(fixture)
    roles, roles_ref = manifest(verify(config["roles_authority"]), "FROZEN")
    if roles.get("validation_source") != "ROUTINE" or roles.get("all_conformers_same_role") is not True:
        raise ValueError("FROZEN_ROUTINE_ROLES_REQUIRED")
    source_roles = read_json(verify(roles["source_role_manifest"]))
    if source_roles.get("status") != "ROUTINE_MOLECULE_VAL_ROLES_FROZEN":
        raise ValueError("SOURCE_ROLE_MANIFEST_STATUS")
    common, common_ref = manifest(verify(config["common_manifest"]), "COMMON_POPULATION_V1_FROZEN")
    orders, order_ref = manifest(verify(config["order_manifest"]), "CONFORMER_ORDER_V1_FROZEN")
    if common["roles_manifest_sha256"] != roles["source_role_manifest"]["sha256"]:
        raise ValueError("COMMON_ROLES_SHA_BINDING")
    if orders["common_population_manifest_sha256"] != common_ref["sha256"] or orders["roles_manifest_sha256"] != roles["source_role_manifest"]["sha256"]:
        raise ValueError("ORDER_COMMON_OR_ROLE_BINDING")
    if set(orders["order_types"]) != {"fixed_random", "energy", "diversity"} or orders.get("rank_base") != 0:
        raise ValueError("THREE_FROZEN_ORDER_TYPES_ZERO_RANK_REQUIRED")
    counts = config.get("fixture_counts") if fixture else None
    if not fixture and "fixture_counts" in config:
        raise ValueError("FIXTURE_COUNTS_FORBIDDEN_IN_PRODUCTION")
    sizes = tuple(counts["sizes"]) if counts else (120000, 240000, 600000)
    pt, pv, nd = (counts["pilot_train"], counts["pilot_val"], counts["diagnostic"]) if counts else (50000, 5000, 20000)
    if not sizes or tuple(sorted(set(sizes))) != sizes or sizes[0] < pt or min(pt, pv, nd) <= 0:
        raise ValueError("INVALID_EXPLICIT_SUBSET_COUNTS")
    seed = config["seed"]
    if type(seed) is not int or not 0 <= seed < 2 ** 63:
        raise ValueError("BOUNDED_INTEGER_SEED_REQUIRED")
    cap = config["maximum_output_bytes"]
    if type(cap) is not int or cap <= 0:
        raise ValueError("EXPLICIT_OUTPUT_CAP_REQUIRED")
    quota_preflight(config, fixture)
    out = fresh_dir(output)
    db = connect(out / "authority.sqlite")
    try:
        for kind, definition in SCHEMA.items():
            db.execute("CREATE TABLE " + kind + "(" + definition + ")")
        refs = config.get("role_tables")
        if refs is None:
            refs = [r for r in source_roles["outputs"] if Path(r["path"]).parent.name == "molecule_roles"]
        authority_outputs = {(r["path"], r["bytes"], r["sha256"]) for r in source_roles["outputs"]}
        if not refs or any((r["path"], r["bytes"], r["sha256"]) not in authority_outputs for r in refs):
            raise ValueError("ROLE_TABLES_NOT_FROM_FROZEN_SOURCE_MANIFEST")
        if {r["path"] for r in refs} != {r["path"] for r in source_roles["outputs"] if Path(r["path"]).parent.name == "molecule_roles"}:
            raise ValueError("ROLE_AUTHORITY_MUST_BE_COMPLETE")
        source_geometry = config["source_geometry_tables"]
        if source_geometry != orders["source_geometry_tables"]:
            raise ValueError("ORDER_SOURCE_GEOMETRY_PINS_DIFFER")
        results = import_tables(db, {"roles": refs, "common": common["membership_tables"],
            "geometries": source_geometry, "orders": orders["order_tables"], "features": config["feature_tables"]}, out, workers)
        disk_cap(out, cap)
        validate(db)
        for role, expected in roles["roles"].items():
            if scalar(db, "SELECT count(*) FROM roles WHERE effective_role=?", (role,)) != expected["molecules"]:
                raise ValueError("ROLE_SOURCE_CLOSURE_DIFFERS")
        subsets = selection(db, seed, sizes, pt, pv, nd)
        geometry_schema = pa.schema([(name, pa.int64() if name == "sprime_conf_idx" else pa.string()) for name in COLUMNS["geometries"]] + [("effective_role", pa.string()), ("source_role", pa.string())])
        key_schema = pa.schema([(n, pa.string()) for n in ("molecule_id", "geometry_source", "geometry_id")])
        subset_schema = pa.schema([("subset", pa.string()), ("molecule_id", pa.string()), ("effective_role", pa.string()), ("selection_rank", pa.int64())])
        order_schema = pa.schema([(name, pa.int64() if name in {"rank", "training_rank"} else pa.string()) for name in COLUMNS["orders"] + ["training_rank"]])
        geometry_table = query_parquet(db, "SELECT g.*,r.effective_role,r.source_role FROM geometries g JOIN roles r USING(molecule_id) ORDER BY g.geometry_id", out / "geometry_map.parquet", geometry_schema)
        geometry_manifest = {"status": "FIXTURE_ONLY" if fixture else "CANONICAL_GEOMETRY_MAP_V1_FROZEN", "map_tables": [geometry_table], "order_manifest": order_ref, "common_population_manifest_sha256": common_ref["sha256"], "roles_manifest_sha256": roles["source_role_manifest"]["sha256"], "roles_authority": roles_ref, "source_geometry_tables": source_geometry, "fixture": fixture}
        gm_ref = write_json(out / "geometry_map_manifest.json", geometry_manifest)
        base = query_parquet(db, "SELECT * FROM diagnostic_base ORDER BY molecule_id,geometry_source", out / "diagnostic_base.parquet", key_schema)
        targets = query_parquet(db, "SELECT * FROM diagnostic_targets ORDER BY molecule_id,geometry_source,geometry_id", out / "diagnostic_targets.parquet", key_schema)
        dm = {"status": "FIXTURE_ONLY" if fixture else "SEEN_MOLECULE_UNSEEN_GEOMETRY_DIAGNOSTIC_FROZEN", "excluded_geometry_tables": [base], "target_exclusion_tables": [targets], "diagnostic_TRAIN_molecules": nd, "excluded_PM7_geometries": nd, "excluded_Sprime_geometries": nd, "all_excluded_geometries_materialized": True, "common_population_manifest_sha256": common_ref["sha256"], "geometry_map_manifest_sha256": gm_ref["sha256"], "order_manifest_sha256": order_ref["sha256"], "use": "pretraining-loss diagnostics only; never model selection", "fixture": fixture}
        diag_ref = write_json(out / "diagnostic_manifest.json", dm)
        subset_refs = {name: query_parquet(db, "SELECT * FROM subset_members WHERE subset=? ORDER BY selection_rank", out / (name + ".parquet"), subset_schema, (name,)) for name in subsets}
        train_orders = query_parquet(db, "SELECT * FROM training_orders ORDER BY molecule_id,geometry_source,order_type,training_rank", out / "training_orders.parquet", order_schema)
        train_geometry = query_parquet(db, "SELECT g.*,r.effective_role,r.source_role FROM training_geometry g JOIN roles r USING(molecule_id) ORDER BY g.geometry_id", out / "training_geometry.parquet", geometry_schema)
        result = {"status": "FIXTURE_ONLY" if fixture else "D5_PARQUET_LISTS_FROZEN", "fixture": fixture, "roles_authority": roles_ref, "common_population": common_ref, "conformer_orders": order_ref, "geometry_map": gm_ref, "diagnostic": diag_ref, "subsets": subset_refs, "training_orders": train_orders, "training_geometry": train_geometry, "seed": seed, "sampling_algorithm": "SHA256-uniform-order-v1; hash(seed,domain,molecule_id), tie=molecule_id", "subset_counts": subsets, "diagnostic_molecules": nd, "all_training_conditions_filter": "anti-join diagnostic target keys BEFORE first-k conformer selection", "database": file_ref(out / "authority.sqlite"), "input_workers": results, "effective_worker_pids": sorted({r["pid"] for r in results}), "peak_python_rows_per_batch": 512, "sqlite_cache_bytes_per_process": 33554432, "output_cap_bytes": cap,
            "producer_sources": [file_ref(p) for p in sorted(Path(__file__).parent.glob("*.py"))]}
        disk_cap(out, cap)
        write_json(out / "manifest.json", result)
        return result
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--fixture", action="store_true")
    args = parser.parse_args()
    run(read_json(args.config), args.output, fixture=args.fixture)


if __name__ == "__main__":
    main()
