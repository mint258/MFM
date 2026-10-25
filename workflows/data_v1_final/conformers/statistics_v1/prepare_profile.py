"""Prepare bounded D7 molecules, canonical HOF, existing UFF and original pointers."""
from __future__ import annotations
import argparse
import concurrent.futures as cf
import json
import multiprocessing as mp
import os
from pathlib import Path
import re
import time

from profile_common import IO, bind_formal_input, file_identity, load_config, read_hof_file, runtime


def q(value):
    return "'" + str(value).replace("'", "''") + "'"


def history_audit(paths):
    pattern = re.compile(r"numConfs|num_confs|n_conform|EmbedMultipleConfs|rotatable|conformer|n=len\(rows\)", re.I)
    output = []
    for name in paths:
        path = Path(name)
        if not path.is_file():
            output.append({"path": name, "status": "NOT_FOUND_AT_DECLARED_PATH"})
            continue
        if path.stat().st_size > 2 * 1024 ** 2:
            output.append({"path": name, "status": "SKIPPED_SOURCE_EXCEEDS_2MIB"})
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        matches = [{"line": i + 1, "text": line} for i, line in enumerate(lines) if pattern.search(line)]
        output.append({"reference": IO.reference(path), "matches": matches[:120], "match_count": len(matches),
                       "matches_truncated": len(matches)>120})
    return {"status": "BOUNDED_SOURCE_SEARCH_ONLY", "files": output,
            "original_PM7_N_policy": "NOT_ESTABLISHED_BY_THIS_SOURCE_SEARCH",
            "interpretation": "No inference from names or correlations. Existing S-prime copies PM7 N; original PM7 N policy must have an explicit generation-source citation."}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", type=Path, required=True)
    ap.add_argument("--root-preflight", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    config = load_config(args.config)
    environment = runtime(config, args.root_preflight, args.config)
    formal = bind_formal_input(config)
    owner_receipt = json.loads(Path(config["owner_receipt"]).read_text())
    owner_ref = owner_receipt["latest_molecules_runtime_ref"]
    IO.require_pin(owner_ref)  # 30MB observed ref, compute20 only; never in login source_refs
    owner_before = file_identity(owner_ref["path"])
    projection = json.loads(Path(config["projection_receipt"]).read_text())
    if projection["status"] != "CATALOG_METADATA_PROJECTION_VERIFIED":
        raise ValueError("CLOSED_CATALOG_PROJECTION_REQUIRED")
    for key in ("catalog", "verification", "source_files"):
        IO.require_pin(projection[key])
    sources = json.loads(Path(projection["source_files"]["path"]).read_text())
    out = IO.new_output_directory(args.output, config)
    started = time.monotonic()
    import duckdb
    import pyarrow as pa
    import pyarrow.parquet as pq
    pa.set_cpu_count(16)
    pa.set_io_thread_count(2)
    db = duckdb.connect()
    db.execute("SET threads=16")
    db.execute("SET memory_limit='12GB'")
    db.execute("CREATE VIEW p AS SELECT * FROM read_parquet(" + q(config["per_molecule"]) + ")")
    db.execute("CREATE VIEW o AS SELECT * FROM read_parquet(" + q(owner_ref["path"]) + ") WHERE state='COMPLETE' AND receipt_context_consistent AND export_published")
    db.execute("""CREATE TEMP TABLE eligible AS SELECT p.*,o.attempt_id,o.job_id,o.task_id,o.lane,
        CASE WHEN heavy_atoms<=10 THEN '0_10' WHEN heavy_atoms<=20 THEN '11_20'
             WHEN heavy_atoms<=30 THEN '21_30' WHEN heavy_atoms<=50 THEN '31_50'
             WHEN heavy_atoms<=100 THEN '51_100' ELSE 'above_100' END AS size_bin,
        CASE WHEN S_conformers=1 THEN '1' WHEN S_conformers<5 THEN '2_4'
             WHEN S_conformers<10 THEN '5_9' ELSE '10plus' END AS n_bin
        FROM p JOIN o USING(molecule_id) WHERE p.Sprime_status='SUCCESS'
        AND p.Sprime_conformers=p.S_conformers AND p.S_usable_conformers=p.S_conformers
        AND p.S_conformers>0""")
    # Cover role/size/N strata before filling remaining bounded job slots by count.
    # This is explicitly a cost/correctness profile, not an unbiased survey.
    job_rows=db.execute("SELECT job_id,split_role,size_bin,n_bin,count(*) FROM eligible GROUP BY ALL").fetchall()
    coverage,counts={},{}
    for job,role,size,n,count in job_rows:
        coverage.setdefault(job,set()).add((role,size,n))
        counts[job]=counts.get(job,0)+count
    uncovered=set().union(*coverage.values()) if coverage else set()
    chosen=[]
    for _ in range(min(config["max_owner_jobs"],len(coverage))):
        remaining=set(coverage)-set(chosen)
        best=min(remaining,key=lambda job:(-len(coverage[job]&uncovered),-counts[job],job))
        chosen.append(best)
        uncovered-=coverage[best]
    db.register("jobs",pa.table({"job_id":pa.array(chosen,type=pa.int64())}))
    seed = q(str(config["selection_seed"]))
    selected = db.execute("""SELECT * FROM (
        SELECT e.*,row_number() OVER(PARTITION BY split_role,size_bin,n_bin
            ORDER BY sha256(molecule_id||SEED),molecule_id) AS stratum_rank
        FROM eligible e JOIN jobs USING(job_id))
        ORDER BY stratum_rank,sha256(molecule_id||SEED),molecule_id LIMIT LIMIT_N"""
        .replace("SEED", seed).replace("LIMIT_N", str(config["molecules"]))).fetch_arrow_table()
    if selected.num_rows != config["molecules"] or len(set(selected.column("molecule_id").to_pylist())) != config["molecules"]:
        raise ValueError("D7_FULL_MOLECULE_SAMPLE_COUNT_MISMATCH")
    db.register("selected", selected)
    columns = ["record_id","molecule_id","source_path","real_index","record_payload_sha256","total_atoms",
               "energy_raw","smiles","QC_molecule_chirality_conflict","QC_molecule_ez_conflict","member_routine","conformer_id","file_group"]
    pointers = db.execute("SELECT " + ",".join("r." + key for key in columns) +
        ",s.attempt_id,s.job_id,s.task_id,s.lane,s.split_role AS source_role FROM read_parquet(" + q(formal["path"]) +
        ") r JOIN selected s USING(molecule_id) ORDER BY r.molecule_id,r.record_id").fetch_arrow_table()
    owners = {row["record_id"]: row for row in pointers.to_pylist()}
    if len(owners) != pointers.num_rows:
        raise ValueError("D7_DUPLICATE_SOURCE_RECORD_ID")
    wanted_jobs = set(selected.column("job_id").to_pylist())
    wanted_groups = set(pointers.column("file_group").to_pylist())
    refs = [ref for ref in sources if ref["family"] == "pm7_neutral" and ref["source_job_id"] in wanted_jobs and ref["source_file_group"] in wanted_groups]
    if not refs:
        raise ValueError("D7_NO_CANONICAL_HOF_SOURCE")
    hof, source_observations = {}, []
    with cf.ProcessPoolExecutor(max_workers=16, mp_context=mp.get_context("spawn")) as pool:
        for result in pool.map(read_hof_file, [{"ref": ref, "owners": {rid: owner for rid, owner in owners.items() if owner["job_id"] == ref["source_job_id"]}} for ref in refs]):
            if set(hof) & set(result["hof"]):
                raise ValueError("D7_DUPLICATE_CANONICAL_HOF_ACROSS_FILES")
            hof.update(result["hof"])
            source_observations.append({key: value for key, value in result.items() if key != "hof"})
    if set(hof) != set(owners):
        raise ValueError("D7_CANONICAL_HOF_ROWS_MISSING:" + str(len(set(owners) - set(hof))))
    ids = selected.column("molecule_id").to_pylist()
    existing, sprime_observations = {mid: [] for mid in ids}, []
    manifest = json.loads(Path(config["sprime_manifest"]).read_text())
    sp_columns = ["molecule_id","sprime_conf_idx","coordinates","uff_energy_kcal_mol","converged","status",
                  "atom_order_sha256","stereo_signature","source_record_id","seed"]
    for ref in manifest["references"]:
        if ref["kind"] != "conformers":
            continue
        before = file_identity(ref["path"])
        if before["bytes"] != ref["bytes"]:
            raise ValueError("D7_SPRIME_FILE_SIZE_CHANGED")
        table = pq.read_table(ref["path"], columns=sp_columns,
                              filters=[("molecule_id","in",ids),("status","=","SUCCESS"),("converged","=",True)])
        for row in table.to_pylist():
            existing[row["molecule_id"]].append(row)
        if file_identity(ref["path"]) != before:
            raise ValueError("D7_SPRIME_FILE_IDENTITY_CHANGED")
        sprime_observations.append({"reference": ref, "identity": before,
            "hash_scope": "whole-file SHA inherited from pinned closed manifest; selected geometry verified in profile"})
    grouped = {mid: [] for mid in ids}
    for row in pointers.to_pylist():
        grouped[row["molecule_id"]].append(row)
    lines = []
    for meta in selected.to_pylist():
        mid = meta["molecule_id"]
        if len(grouped[mid]) != meta["S_conformers"] or len(existing[mid]) != meta["Sprime_conformers"]:
            raise ValueError("D7_COMPLETE_MOLECULE_CARDINALITY_MISMATCH")
        lines.append(json.dumps({"meta": meta, "records": grouped[mid],
            "sprime": existing[mid], "hof": {row["record_id"]: hof[row["record_id"]] for row in grouped[mid]}},
            ensure_ascii=False, allow_nan=False, sort_keys=True) + "\n")
    payload = "".join(lines).encode()
    IO.prewrite_guard(out / "tasks.jsonl", len(payload), reserve_bytes=2 << 20)
    with (out / "tasks.jsonl").open("xb") as stream:
        stream.write(payload);stream.flush();os.fsync(stream.fileno())
    IO.write_parquet_new(out / "selected_molecules.parquet", selected)
    IO.write_parquet_new(out / "record_owners.parquet", pointers)
    IO.write_json_new(out / "history_search.json", history_audit(config["history_search_files"]))
    if file_identity(owner_ref["path"]) != owner_before:
        raise ValueError("D7_LATEST_OWNER_FILE_CHANGED")
    bind_formal_input(config)
    report = {"status": "D7_PROFILE_PREPARED_NO_GEOMETRY_COMPUTED", "runtime": environment,
              "config": IO.reference(args.config), "root_intent": IO.reference(args.root_preflight),
              "molecules": config["molecules"], "records": len(owners), "owner_jobs": sorted(wanted_jobs),
              "formal_population": formal, "latest_owners": owner_ref, "owner_identity": owner_before,
              "source_observations": source_observations, "sprime_observations": sprime_observations,
              "selection_bias": "Complete successful original molecules, at most16 owner jobs greedily covering role/size/N then by count; not population estimates",
              "uncovered_metadata_strata_after_job_limit": sorted(uncovered),
              "selected_strata": db.execute("SELECT split_role,size_bin,n_bin,count(*) AS molecules FROM selected GROUP BY ALL ORDER BY ALL").fetch_arrow_table().to_pylist(),
              "outputs": [IO.reference(out / name) for name in ("tasks.jsonl","selected_molecules.parquet","record_owners.parquet","history_search.json")],
              "elapsed_seconds": time.monotonic() - started, "original_data_modified": False,
              "embedding_or_optimization_calls": 0, "common_population_published": False}
    IO.write_json_new(out / "prepared.json", report)
    db.close()
    print(json.dumps({"status": report["status"], "molecules": config["molecules"], "output": str(out)}))


if __name__ == "__main__":
    main()
