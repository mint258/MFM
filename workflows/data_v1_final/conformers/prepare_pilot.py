"""Select a deterministic stratified fill pilot and materialize only its pointers."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import time

sys.dont_write_bytecode = True
from common import (load_config, new_output_directory, reference, require_pin,
                    require_preflight, runtime_guard, write_json_new,
                    prewrite_guard, write_parquet_new)


def quote(value):
    return "'" + str(value).replace("'", "''") + "'"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--root-preflight", type=Path, required=True)
    args = parser.parse_args()
    config = load_config(args.config)
    runtime = runtime_guard(16, metadata_only=True)
    preflight = require_preflight(args.root_preflight, args.config, config)
    for pin in config["authority_pins"]:
        require_pin(pin)
    out = new_output_directory(args.output, config)
    import duckdb
    import pyarrow as pa
    import pyarrow.parquet as pq
    pa.set_cpu_count(16)
    pa.set_io_thread_count(4)
    started = time.monotonic()
    db = duckdb.connect()
    db.execute("SET threads=16")
    db.execute("SET memory_limit='12GB'")
    # This query is a bounded 1.2M-row metadata scan; no original LMDB is opened.
    db.execute("CREATE VIEW p AS SELECT * FROM read_parquet(" + quote(config["per_molecule"]) + ")")
    db.execute("CREATE VIEW m AS SELECT * FROM read_parquet(" + quote(config["molecule_index"]) + ")")
    counts = db.execute("SELECT count(*),count(DISTINCT molecule_id) FROM p").fetchone()
    expected = config["expected_population_molecules"]
    if counts != (expected, expected):
        raise RuntimeError("ACTUAL_RECORD_MANIFEST_MISMATCH:alignment_population")
    db.execute("""CREATE TEMP TABLE annotated AS SELECT p.*,m.file_group,m.max_heavy_atoms,
        m.max_total_atoms,m.records,
        CASE WHEN p.Sprime_status='UFF_UNSUPPORTED' THEN 'excluded_unsupported'
             WHEN p.Sprime_conformers>=p.S_conformers THEN 'enough_control'
             WHEN p.Sprime_status='INSUFFICIENT_UNIQUE_CONFORMERS' THEN 'fill_10N'
             ELSE 'retry_once' END AS cohort,
        CASE WHEN p.heavy_atoms<=10 THEN '0_10' WHEN p.heavy_atoms<=20 THEN '11_20'
             WHEN p.heavy_atoms<=30 THEN '21_30' WHEN p.heavy_atoms<=50 THEN '31_50'
             WHEN p.heavy_atoms<=75 THEN '51_75' WHEN p.heavy_atoms<=100 THEN '76_100'
             ELSE 'above_100' END AS heavy_bin,
        CASE WHEN list_contains(p.elements_atomic_numbers,34) THEN 'Se'
             WHEN list_contains(p.elements_atomic_numbers,15) THEN 'P'
             WHEN list_contains(p.elements_atomic_numbers,14) THEN 'Si' ELSE 'other' END AS critical_element
        FROM p JOIN m USING(molecule_id)""")
    joined = db.execute("SELECT count(*),count(DISTINCT molecule_id),count(*) FILTER(WHERE S_conformers<>records) FROM annotated").fetchone()
    if joined != (expected, expected, 0):
        raise RuntimeError("ACTUAL_RECORD_MANIFEST_MISMATCH:molecule_index_join")
    cohort_counts = db.execute("SELECT cohort,split_role,Sprime_status,count(*) AS molecules FROM annotated GROUP BY ALL ORDER BY ALL").fetch_arrow_table().to_pylist()
    seed = quote(str(config["pilot_selection_seed"]))
    rank_sql = """SELECT *,row_number() OVER(PARTITION BY cohort,Sprime_status,file_group,
        heavy_bin,critical_element ORDER BY sha256(molecule_id||SEED),molecule_id) AS stratum_rank
        FROM annotated WHERE CONDITION""".replace("SEED", seed)
    problem_sql = rank_sql.replace("CONDITION", "cohort IN ('fill_10N','retry_once')")
    control_sql = rank_sql.replace("CONDITION", "cohort='enough_control'")
    order_sql = " ORDER BY stratum_rank,sha256(molecule_id||" + seed + "),molecule_id LIMIT "
    problem = db.execute("SELECT * FROM (" + problem_sql + ")" + order_sql + str(config["pilot_problem_molecules"])).fetch_arrow_table()
    control = db.execute("SELECT * FROM (" + control_sql + ")" + order_sql + str(config["pilot_control_molecules"])).fetch_arrow_table()
    selected = pa.concat_tables([problem, control])
    if selected.num_rows != config["pilot_problem_molecules"] + config["pilot_control_molecules"]:
        raise RuntimeError("PILOT_SAMPLE_SMALLER_THAN_CONFIG")
    db.register("selected", selected)
    pointer_columns = ["record_id", "molecule_id", "source_path", "real_index", "record_payload_sha256",
                       "total_atoms", "energy_raw", "smiles", "QC_molecule_chirality_conflict", "QC_molecule_ez_conflict"]
    pointers = db.execute("SELECT " + ",".join("r." + name for name in pointer_columns) +
                          " FROM read_parquet(" + quote(config["record_index"]) +
                          ") AS r JOIN selected USING(molecule_id) ORDER BY r.molecule_id,r.record_id").fetch_arrow_table()
    # The closed manifest supplies expected whole-file hashes; selected source rows
    # additionally receive geometry hashes in run_pilot, and LMDB payload hashes are verified.
    source_manifest = json.loads(Path(config["sprime_manifest"]).read_text(encoding="utf-8"))
    source_references, prior_rows = [], []
    ids = selected.column("molecule_id").to_pylist()
    for ref in source_manifest["references"]:
        if ref["kind"] != "conformers":
            continue
        source = Path(ref["path"])
        if not source.is_file() or source.stat().st_size != ref["bytes"]:
            raise RuntimeError("ACTUAL_RECORD_MANIFEST_MISMATCH:sprime_file_size")
        source_references.append(dict(ref, verification="closed_manifest_pin_and_size; selected_rows_verified_in_run"))
        table = pq.read_table(source, filters=[("molecule_id", "in", ids), ("status", "=", "SUCCESS"), ("converged", "=", True)])
        prior_rows.extend(table.to_pylist())
    grouped_pointers = {mid: [] for mid in ids}
    grouped_previous = {mid: [] for mid in ids}
    for row in pointers.to_pylist():
        grouped_pointers[row["molecule_id"]].append(row)
    for row in prior_rows:
        grouped_previous[row["molecule_id"]].append(row)
    metas = selected.to_pylist()
    lines = []
    for meta in sorted(metas, key=lambda row: row["molecule_id"]):
        mid = meta["molecule_id"]
        records, previous = grouped_pointers[mid], grouped_previous[mid]
        if len(records) != meta["S_conformers"] or len(previous) != meta["Sprime_conformers"]:
            raise RuntimeError("ACTUAL_RECORD_MANIFEST_MISMATCH:selected_counts")
        old_ids = [row["sprime_conf_idx"] for row in previous]
        if len(old_ids) != len(set(old_ids)):
            raise RuntimeError("ACTUAL_RECORD_MANIFEST_MISMATCH:duplicate_existing_indices")
        meta["expected_conformers"] = int(meta["S_conformers"])
        task = {"meta": meta, "records": records, "existing_conformers": previous}
        lines.append(json.dumps(task, ensure_ascii=False, allow_nan=False, sort_keys=True) + "\n")
    payload = "".join(lines).encode("utf-8")
    prewrite_guard(out / "tasks.jsonl", len(payload), reserve_bytes=2 << 20)
    with (out / "tasks.jsonl").open("xb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    write_parquet_new(out / "selected_molecules.parquet", selected)
    write_parquet_new(out / "selected_record_pointers.parquet", pointers)
    write_json_new(out / "cohort_counts.json", cohort_counts)
    counts_by_stratum = db.execute("SELECT cohort,Sprime_status,file_group,heavy_bin,critical_element,count(*) AS molecules FROM selected GROUP BY ALL ORDER BY ALL").fetch_arrow_table().to_pylist()
    report = {"status": "PILOT_INPUTS_READY_NOT_COMPUTED", "runtime": runtime,
              "config": reference(args.config), "root_preflight": preflight,
              "molecules": len(metas), "selected_strata": counts_by_stratum,
              "source_pins": config["science_source_pins"] + config["authority_pins"],
              "source_sprime_files": source_references, "canonical_pointer_source": config["record_index"],
              "original_lmdb_opened": False, "original_data_modified": False,
              "hash_scope": "all small authority pins and prepared outputs verified; whole S-prime large-file hashes inherited explicitly from pinned closed manifest",
              "seconds": time.monotonic() - started,
              "outputs": [reference(out / name) for name in ("tasks.jsonl", "selected_molecules.parquet", "selected_record_pointers.parquet", "cohort_counts.json")]}
    write_json_new(out / "prepared.json", report)
    db.close()
    print(json.dumps({"status": report["status"], "molecules": len(metas), "output": str(out)}))


if __name__ == "__main__":
    main()
