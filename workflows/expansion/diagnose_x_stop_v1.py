"""Read-only projection for one frozen STOP mismatch set; no chemistry replay.

Root submits this metadata diagnosis in a real compute-0-20 Slurm allocation.
Large source authorization uses the existing small compute pin receipt. The
original index is fully hashed on compute, then only requested IDs/columns are
projected. Nothing imports or changes the registered regression implementation.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import os
from pathlib import Path
import socket
import time

from . import common, data_authority_v1 as authority_source
from .common import ARTIFACT_ROOT, dump_new, load, reference, require, verify


COLUMNS = ("record_id", "molecule_id", "source_family", "smiles", "parse_failed", "sanitize_failed",
           "stored_graph_fragments", "X01", "X01_geometry_checked", "cached_geometry_components",
           "member_train", "member_full", "elements", "electron_count", "X02", "X03", "X04", "X05")


def summarize(rows):
    """Exact observed column combinations, not explanations or gate overrides."""
    keys = ("parse_failed", "sanitize_failed", "stored_graph_fragments", "X01", "X01_geometry_checked",
            "cached_geometry_components", "X02", "X03", "X04", "X05", "member_train", "member_full")
    counts = Counter(json.dumps({k: r[k] for k in keys if k in r}, sort_keys=True) for r in rows)
    return [{"fields": json.loads(k), "records": n} for k, n in sorted(counts.items())]


def run(plan_path, intent_path):
    started = time.monotonic()
    node = socket.gethostname().split(".")[0]
    require(node == "compute-0-20" and os.getuid() == 1278 and os.environ.get("SLURM_JOB_ID") and
            int(os.environ.get("SLURM_CPUS_PER_TASK", "0")) >= 16,
            "STOP diagnosis requires actual zixiao Slurm >=16CPU compute-0-20 allocation")
    plan, intent = load(plan_path), load(intent_path)
    require(plan["schema"] == "v1_X_stop_readonly_diagnosis_v1" and plan["status"] == "READY",
            "Root-bound READY diagnosis plan required")
    require(plan["expected_mismatch_rows"] == 489 and plan["expected_native_mismatch_rows"] == 335 and
            plan["expected_stop_job_id"] == "4520357", "This diagnosis only covers the exact frozen STOP")
    request = intent["request"]
    require(intent["uid"] == 1278 and request["root_review"]["status"] == "APPROVED" and
            request["node"] == node and request["cpus"] == 16 and request["memory_gib"] == 4 and
            0 < request["wall_seconds"] <= 3600 and plan["peak_output_cap_bytes"] == 32 * 1024 ** 2 and
            request["estimated_peak_output_bytes"] == plan["peak_output_cap_bytes"],
            "Root diagnosis authority or budget differs")
    declared = {r["path"]: r for r in request["source_references"]}
    refs = [reference(plan_path), *plan["code_sources"], *plan["data_authorization_receipts"],
            plan["stop_receipt"], plan["stop_submission_receipt"], plan["mismatches"]]
    require(all(declared.get(r["path"]) == r for r in refs), "Root intent does not bind exact diagnosis inputs")
    for ref in plan["code_sources"]:
        verify(ref)
    actual = {str(Path(p).absolute()) for p in (__file__, common.__file__, authority_source.__file__)}
    require(actual <= {r["path"] for r in plan["code_sources"]}, "Actual diagnostic import chain not pinned")
    stop = load(verify(plan["stop_receipt"]))
    require(stop["schema"] == "pubchem_v1_complete_input_regression_v1" and stop["status"] == "STOP_REVIEW" and
            stop["mode"] == "pilot" and stop["all_mismatches"] == plan["mismatches"] and
            stop["source_refs"]["original_index"] == plan["original_index"], "Wrong frozen STOP receipt/source")
    require(declared.get(stop["root_submission"]["path"]) == stop["root_submission"],
            "Root intent does not bind the frozen STOP's original small submission intent")
    old_submission = load(verify(plan["stop_submission_receipt"]))
    old_intent = load(verify(stop["root_submission"]))
    require(old_submission["request"] == old_intent["request"] and old_submission["sbatch_returncode"] == 0 and
            str(old_submission["job_id"]) == plan["expected_stop_job_id"],
            "Frozen STOP submission does not identify exact actual pilot job")
    mismatch = [json.loads(line) for line in verify(plan["mismatches"]).read_text(encoding="utf-8").splitlines()]
    target = [r for r in mismatch if r["native_mismatch"]]
    require(len(mismatch) == plan["expected_mismatch_rows"] and len(target) == plan["expected_native_mismatch_rows"],
            "Frozen mismatch population differs")
    ids = sorted(r["record_id"] for r in target)
    require(len(ids) == len(set(ids)) and all(r["native_mismatch"] == ["X01"] for r in target),
            "Frozen STOP is not the exact unique X01-only mismatch set")
    out = Path(plan["output_root"]).absolute()
    require(out.is_relative_to(ARTIFACT_ROOT / "regression") and not out.exists(), "Fresh external diagnosis output required")
    out.mkdir(parents=True)
    authority = authority_source.authorize_data(plan, intent, [plan["original_index"]], node=node)
    require(request["data_references"] == [plan["original_index"]], "Only the original index may be read by this diagnosis")
    authority_source.verify_authorized_data(authority)
    hash_seconds = time.monotonic() - started
    import duckdb
    import pyarrow as pa
    db = duckdb.connect()
    try:
        db.execute("SET threads=16")
        db.execute("SET memory_limit='2GB'")
        db.execute("SET max_temp_directory_size='16MB'")
        spill = out / "spill"
        spill.mkdir()
        db.execute("SET temp_directory=?", [str(spill)])
        db.register("requested", pa.table({"record_id": ids}))
        db.read_parquet(plan["original_index"]["path"]).create_view("original")
        schema = [{"name": v[0], "type": v[1]} for v in db.execute("DESCRIBE original").fetchall()]
        present = {v["name"] for v in schema}
        require({"record_id", "molecule_id"} <= present, "Source lacks mandatory record/molecule identity columns")
        columns = [c for c in COLUMNS if c in present]
        cursor = db.execute("SELECT " + ",".join("i." + c for c in columns) +
                            " FROM original i JOIN requested r USING(record_id) ORDER BY i.record_id")
        rows = [dict(zip(columns, values)) for values in cursor.fetchall()]
        require([r["record_id"] for r in rows] == ids, "Projection is missing/duplicating requested records")
        authority_source.verify_final_stats(authority)
        dump_new(out / "native_mismatch_original_fields.json", {"rows": rows})
        report = {"schema": "v1_X_stop_readonly_diagnosis_receipt_v1", "status": "OBSERVED_FIELDS_ONLY_NO_GATE_CHANGE",
                  "node": node, "job_id": os.environ["SLURM_JOB_ID"], "uid": os.getuid(),
                  "plan": reference(plan_path), "root_submission": reference(intent_path),
                  "source": plan["original_index"], "data_authority": authority,
                  "frozen_stop": plan["stop_receipt"], "mismatches": plan["mismatches"],
                  "stop_submission_receipt": plan["stop_submission_receipt"],
                  "source_schema": schema, "requested_columns": list(COLUMNS), "projected_columns": columns,
                  "missing_requested_columns": [c for c in COLUMNS if c not in present],
                  "projected_records": len(rows), "molecules": len({r["molecule_id"] for r in rows}),
                  "field_combinations": summarize(rows), "output": reference(out / "native_mismatch_original_fields.json"),
                  "source_authorization_and_hash_seconds": hash_seconds, "wall_seconds": time.monotonic() - started,
                  "chemistry_replayed": False, "full_regression_run": False, "source_screening_run": False,
                  "original_lmdb_opened_or_modified": False, "registered_source_changed": False}
        require(report["output"]["bytes"] <= 2 * 1024 ** 2, "Unexpected diagnosis output size")
        require(sum(p.stat().st_size for p in out.rglob("*") if p.is_file()) < plan["peak_output_cap_bytes"] - 1024 ** 2,
                "Diagnosis output/spill cap exceeded")
        dump_new(out / "receipt.json", report)
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--root-submit-intent", type=Path, required=True)
    args = parser.parse_args()
    run(args.plan, args.root_submit_intent)


if __name__ == "__main__":
    main()
