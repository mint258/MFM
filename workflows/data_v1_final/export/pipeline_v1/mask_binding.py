"""Join frozen compact masks to opaque geometry IDs without dense leaf causes."""
from __future__ import annotations
import argparse
import concurrent.futures
import multiprocessing as mp
from pathlib import Path
import os
from .io import (arrow_batches, batches, check_allocation, connect, fresh_dir,
                 manifest, read_json, scalar, verify, write_json)
from .masks import field_ids
from wire_v1.store import file_ref


def bind_group(task):
    import pyarrow as pa
    import pyarrow.parquet as pq
    index, spec, geometry_db, output = task
    db = connect(geometry_db, readonly=True)
    own = connect(Path(output) / ("mask-owner-" + str(index).zfill(5) + ".sqlite"))
    own.execute("CREATE TABLE owner(record_ordinal INTEGER PRIMARY KEY,molecule_id TEXT,native_record_id TEXT,sprime_conf_idx INTEGER)")
    cols = spec["owner_columns"]
    if not cols.get("molecule_id") or not cols.get("record_ordinal"):
        raise ValueError("MASK_OWNER_ORDINAL_AND_MOLECULE_REQUIRED")
    try:
        for batch in arrow_batches(spec["owner_index"], columns=sorted({v for v in cols.values() if v})):
            for row in batch.to_pylist():
                mid = row[cols["molecule_id"]]
                native = row[cols["native_record_id"]] if cols.get("native_record_id") else None
                idx = row[cols["sprime_conf_idx"]] if cols.get("sprime_conf_idx") else None
                src = spec["geometry_source"]
                clause, key = ("native_record_id=?", native) if src == "pm7" else ("sprime_conf_idx=?", idx)
                if src not in {"pm7", "uff_sprime"} or (src == "uff_sprime" and (type(idx) is not int or idx < 0)) or (src == "pm7" and not isinstance(native, str)):
                    raise ValueError("COMPACT_OWNER_PHYSICAL_KEY_REQUIRED")
                if db.execute("SELECT 1 FROM geometries WHERE molecule_id=? AND geometry_source=? AND " + clause, (mid, src, key)).fetchone():
                    own.execute("INSERT INTO owner VALUES(?,?,?,?)", (row[cols["record_ordinal"]], mid, native, idx))
            own.commit()
        path = Path(output) / ("compact-bound-" + str(index).zfill(5) + ".parquet")
        writer, rows_written = None, 0
        try:
            for ref in spec["mask_tables"]:
                for batch in batches(ref):
                    rows = []
                    for row in batch.to_pylist():
                        owner = own.execute("SELECT * FROM owner WHERE record_ordinal=?", (row["record_ordinal"],)).fetchone()
                        if owner is None:
                            continue
                        task_code = row["task_code"]
                        if str(task_code) not in spec["task_view_map"]:
                            raise ValueError("MASK_TASK_VIEW_MAPPING_MUST_BE_EXPLICIT")
                        view = spec["task_view_map"][str(task_code)]
                        src = spec["geometry_source"]
                        clause, key = ("native_record_id=?", owner["native_record_id"]) if src == "pm7" else ("sprime_conf_idx=?", owner["sprime_conf_idx"])
                        result = db.execute("SELECT geometry_id FROM geometries WHERE molecule_id=? AND geometry_source=? AND " + clause + " AND view_id IS ?", (owner["molecule_id"], src, key, view)).fetchall()
                        if len(result) != 1:
                            raise ValueError("MASK_SOURCE_ORDINAL_TASK_TO_GEOMETRY_NOT_UNIQUE")
                        field_ids(row["in_scope_fields"]); field_ids(row["valid_fields"])
                        rows.append({**row, "geometry_id": result[0][0]})
                    schema = batch.schema.append(pa.field("geometry_id", pa.string()))
                    if writer is None:
                        writer = pq.ParquetWriter(path, schema, compression="zstd")
                    writer.write_table(pa.Table.from_pylist(rows, schema=schema))
                    rows_written += len(rows)
        finally:
            if writer is not None:
                writer.close()
        if writer is None:
            raise ValueError("EMPTY_INPUT_MASK_GROUP")
        return {"file": file_ref(path), "rows": rows_written, "pid": os.getpid(), "owner_group": spec, "geometry_native_id_not_used_for_UFF": True}
    finally:
        own.close(); db.close()


def run(config, output, fixture=False):
    check_allocation(fixture)
    d5, d5_ref = manifest(verify(config["d5_manifest"]), "FIXTURE_ONLY" if fixture else "D5_PARQUET_LISTS_FROZEN")
    geometry_db = verify(d5["database"])
    registry = read_json(verify(config["registry"]))
    fields = read_json(verify(config["field_map"]))
    verify(config["reason_codebook"])
    expected = {f["field_key"] for f in registry["fields"] if f["status"] == "enabled"}
    if len(fields) != len(expected) or {f["field_key"] for f in fields} != expected or len({f["field_id"] for f in fields}) != len(fields) or any(type(f["field_id"]) is not int or not 0 <= f["field_id"] < 146 for f in fields):
        raise ValueError("MASK_FIELD_MAP_MUST_EXACTLY_BIND_ENABLED_REGISTRY")
    for group in config["groups"]:
        verify(group["owner_index"])
        for ref in group["mask_tables"]:
            verify(ref)
    out = fresh_dir(output)
    with concurrent.futures.ProcessPoolExecutor(max_workers=16, mp_context=mp.get_context("spawn")) as pool:
        results = list(pool.map(bind_group, [(i, spec, str(geometry_db), str(out)) for i, spec in enumerate(config["groups"])], chunksize=1))
    result = {"status": "FIXTURE_ONLY" if fixture else "COMPACT_MASK_GEOMETRY_BINDING_V1_FROZEN", "fixture": fixture,
        "geometry_map_manifest_sha256": d5["geometry_map"]["sha256"], "registry_sha256": config["registry"]["sha256"], "reason_codebook": config["reason_codebook"], "field_map": config["field_map"],
        "mask_tables": [r["file"] for r in results], "groups": results, "d5_manifest": d5_ref,
        "reason_granularity": "exact leaf validity; original source/new/review field reason sets; original sparse generic leaf exceptions", "dense_per_leaf_causes_fabricated": False}
    write_json(out / "manifest.json", result)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config", type=Path, required=True); p.add_argument("--output", type=Path, required=True)
    p.add_argument("--fixture", action="store_true")
    a = p.parse_args(); run(read_json(a.config), a.output, a.fixture)


if __name__ == "__main__":
    main()
