"""Profile or export all original local identities under a new queued64GiB scope."""
from __future__ import annotations

import argparse
from collections import Counter, deque
from concurrent.futures import ProcessPoolExecutor
import itertools
import json
import multiprocessing
import os
from pathlib import Path
import time

from .. import full_queue_v1 as execution
from ..common import require
from ..identity_v2 import coverage_v2 as coverage, projection_v2 as projection
from . import cohorts, input_authority, readers
from workflows.data_v1_final.execution.queue_v1 import shared


SCOPES = {"profile": "sb5_identity_profile_all_roles_v3", "full": "sb5_identity_full_all_roles_v3"}
_TICKETS = _STOP = _OUTPUT = _UNIT_CAP = None


def _initialize(tickets, stop, output, unit_cap, barrier):
    global _TICKETS, _STOP, _OUTPUT, _UNIT_CAP
    _TICKETS, _STOP, _OUTPUT, _UNIT_CAP = tickets, stop, Path(output), unit_cap
    barrier.wait(timeout=180)


def output_schema():
    import pyarrow as pa
    return pa.schema([(name, pa.string()) for name in ("dataset", "source_id", "role", "molecule_id", "conservative_reason",
                                                      "non_h_composition_json", "source_metadata_json")] +
                     [(name, pa.list_(pa.string())) for name in ("memberships", "smiles_variants", "inchikeys", "wp5_keys")] +
                     [(name, pa.bool_()) for name in ("missing_full_key", "missing_identity_or_composition", "unresolved_source_variant")])


def encoded_row(row):
    from ..common import wp5_key
    fixed = {name: row.get(name) for name in ("dataset", "source_id", "role", "molecule_id", "conservative_reason",
             "memberships", "smiles_variants", "inchikeys", "missing_full_key", "missing_identity_or_composition", "unresolved_source_variant")}
    fixed["wp5_keys"] = sorted({wp5_key(key) for key in row["inchikeys"]})
    fixed["non_h_composition_json"] = None if row["non_h_composition"] is None else json.dumps(row["non_h_composition"], separators=(",", ":"))
    fixed["source_metadata_json"] = json.dumps({name: value for name, value in row.items() if name not in fixed and name != "non_h_composition"},
                                               ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    return fixed


def _unit_rows(task):
    kind = task["kind"]
    if kind == "formal":
        batches = readers.parquet_identity_batches(_TICKETS["v1_formal"], row_groups=[task["row_group"]], batch_size=4096)
        for batch in batches:
            for row in batch.to_pylist():
                yield projection.formal_row(row)
            if task["profile"]:
                break
    elif kind == "embargo":
        for batch in readers.parquet_identity_batches(_TICKETS["v1_embargo4900"], embargo=True, batch_size=4096):
            for row in batch.to_pylist():
                yield projection.embargo_row(row)
    elif kind == "already_projected":
        yield from task["rows"]
    else:
        require(kind == "graph", "Unknown identity export task")
        for source in task["rows"]:
            if _STOP.is_set():
                raise execution.CooperativeStop("Stop before next graph identity")
            yield cohorts.project_task(source)


def write_unit(task):
    import pyarrow as pa
    import pyarrow.parquet as pq
    started = time.monotonic()
    partial = _OUTPUT / (task["unit_id"] + ".partial.parquet")
    final = _OUTPUT / (task["unit_id"] + ".parquet")
    require(not partial.exists() and not final.exists(), "Owned unit exists; preserve partial, never overwrite")
    counts, roles, classes, datasets, buffer = Counter(), Counter(), Counter(), Counter(), []
    schema = output_schema()
    with pq.ParquetWriter(partial, schema, compression="zstd", use_dictionary=True) as writer:
        for row in _unit_rows(task):
            if _STOP.is_set():
                raise execution.CooperativeStop("Stop before next identity record")
            counts["records"] += 1
            counts["missing_full_key"] += int(row["missing_full_key"])
            counts["missing_identity_or_composition"] += int(row["missing_identity_or_composition"])
            counts["unresolved_source_variant"] += int(row["unresolved_source_variant"])
            roles[row["role"]] += 1
            datasets[row["dataset"]] += 1
            if "original_embargo_class" in row:
                classes[row["original_embargo_class"]] += 1
            buffer.append(encoded_row(row))
            if len(buffer) == 4096:
                writer.write_table(pa.Table.from_pylist(buffer, schema=schema)); buffer = []
                require(partial.stat().st_size <= _UNIT_CAP, "Per-unit bounded output cap reached")
        if buffer:
            writer.write_table(pa.Table.from_pylist(buffer, schema=schema))
    require(partial.stat().st_size <= _UNIT_CAP, "Final unit output cap reached")
    os.rename(partial, final)
    return {"unit_id": task["unit_id"], "kind": task["kind"], "worker_pid": os.getpid(), "counts": dict(counts),
            "roles": dict(roles), "datasets": dict(datasets), "embargo_classes": dict(classes),
            "file": execution.file_pin(final, stop=_STOP), "seconds": time.monotonic() - started}


def task_stream(plan, tickets, small_rows, qm9_folds, historical_qm9):
    for row_group in plan["formal_row_groups"]:
        yield {"kind": "formal", "row_group": row_group, "profile": plan["mode"] == "profile", "unit_id": f"formal_rg_{row_group:03d}"}
    yield {"kind": "embargo", "unit_id": "embargo_all4900"}
    for index, offset in enumerate(range(0, len(small_rows), 512)):
        yield {"kind": "already_projected", "unit_id": f"small_identity_{index:05d}", "rows": small_rows[offset:offset + 512]}
    for index, rows in enumerate(cohorts.graph_tasks(tickets, qm9_folds, historical_qm9)):
        yield {"kind": "graph", "unit_id": f"graph_identity_{index:06d}", "rows": rows}


def global_coverage(output, plan, units, budget):
    import duckdb
    spill = output / "spill"
    spill.mkdir()
    db = duckdb.connect()
    try:
        db.execute("SET threads=16")
        db.execute("SET memory_limit='32GB'")
        db.execute("SET temp_directory=?", [str(spill)])
        db.execute("SET max_temp_directory_size=?", [str(plan["spill_cap_bytes"]) + "B"])
        files = [row["file"]["path"] for row in units]
        db.read_parquet(files).create_view("identities")
        duplicate = db.execute("SELECT dataset,source_id,count(*) FROM identities GROUP BY dataset,source_id HAVING count(*)<>1 LIMIT 1").fetchall()
        require(not duplicate, "Duplicate/missing original(dataset,source_id); never accept aggregate-only proof")
        total, unique = db.execute("SELECT count(*),count(DISTINCT (dataset,source_id)) FROM identities").fetchone()
        v1 = db.execute("SELECT role,count(*) FROM identities WHERE dataset='v1_all_roles_and_embargo' GROUP BY role").fetchall()
        missing_v1 = db.execute("SELECT count(*) FROM identities WHERE dataset='v1_all_roles_and_embargo' AND missing_identity_or_composition").fetchone()[0]
        # No DISTINCT key projection replaces original record coverage.
        classes = Counter()
        for unit in units:
            classes.update(unit["embargo_classes"])
        if plan["mode"] == "full":
            v1_proof = coverage.v1_whole_scope_proof(total_rows=sum(n for _, n in v1),
                unique_source_ids=db.execute("SELECT count(DISTINCT source_id) FROM identities WHERE dataset='v1_all_roles_and_embargo'").fetchone()[0],
                role_counts=dict(v1), embargo_class_counts=classes, missing_identity_rows=missing_v1)
        else:
            require(sum(n for _, n in v1) == 65536 + 4900 and missing_v1 == 0 and classes ==
                    {"known_fullkey_embargo": 4100, "unknown_non_h_composition_embargo": 800}, "Profile formal65536/whole4900 scope differs")
            v1_proof = {"status": "PROFILE65536_FORMAL_AND_ALL4900_ONLY", "records": sum(n for _, n in v1), "whole_v1_coverage_claimed": False}
        missing_path = output / "missing_identities.parquet"
        db.execute("COPY (SELECT * FROM identities WHERE missing_identity_or_composition OR unresolved_source_variant) TO ? (FORMAT PARQUET,COMPRESSION ZSTD)", [str(missing_path)])
        budget.check()
        return {"records": total, "globally_unique_source_ids": unique, "v1": v1_proof,
                "missing_or_unresolved": execution.file_pin(missing_path), "all_source_global_decontamination_accepted": False}
    finally:
        db.close()


def run(plan_path, proof_path):
    preview = shared.load(plan_path)
    require(preview["schema"] == "SB5_IDENTITY_EXPORT_PLAN_V3" and preview["mode"] in SCOPES, "Exact new identity plan required")
    plan, proof, startup_proof = execution.startup(plan_path, proof_path, __file__, scope=SCOPES[preview["mode"]])
    require(plan["pilot"] is (plan["mode"] == "profile") and plan["apply_common_filter"] is False and
            plan["source_policy"]["targets_or_features_materialized"] is False and
            plan["source_policy"]["all_source_decontamination_accepted"] is False, "Common/source/release policy differs")
    out = execution.fresh_output(plan["output_root"])
    context = multiprocessing.get_context("spawn")
    stop = context.Event()
    units, worker_counts = [], Counter()
    began = time.monotonic()
    budget = execution.RuntimeBudget(out, plan, proof, stop)
    try:
        with budget:
            boundary_tests = None
            if plan["run_boundary_tests"]:
                from ..test_full_sources_v1 import run_boundaries
                boundary_tests = run_boundaries()
            tickets, source_authority = input_authority.authorize(plan, proof)
            hash_started = time.monotonic()
            body_hashes = input_authority.verify_bodies(tickets, stop)
            hash_seconds = time.monotonic() - hash_started
            budget.check()
            cohort_began = time.monotonic()
            small_rows, qm9_folds, historical_qm9, cohort_proofs = cohorts.prepare_small_cohorts(tickets)
            cohort_prepare_seconds = time.monotonic() - cohort_began
            import pyarrow.parquet as pq
            row_groups = pq.ParquetFile(tickets["v1_formal"].current_path()).num_row_groups
            expected_groups = list(range(row_groups)) if plan["mode"] == "full" else [i * (row_groups - 1) // 15 for i in range(16)]
            require(plan["formal_row_groups"] == expected_groups and len(set(expected_groups)) >= 16, "Exact full/profile physical row-group scope differs")
            parts = out / "parts"; parts.mkdir()
            compute_began = time.monotonic()
            with ProcessPoolExecutor(max_workers=16, mp_context=context, initializer=_initialize,
                    initargs=(tickets, stop, str(parts), plan["unit_output_cap_bytes"], context.Barrier(16))) as pool:
                waiting = deque()
                def collect():
                    row = waiting.popleft().result(timeout=plan["worker_result_timeout_seconds"])
                    units.append(row); worker_counts[row["worker_pid"]] += row["counts"]["records"]
                    shared.write_new(out / (row["unit_id"] + ".receipt.json"), row)
                    budget.check()
                for task in task_stream(plan, tickets, small_rows, qm9_folds, historical_qm9):
                    budget.check()
                    waiting.append(pool.submit(write_unit, task))
                    if len(waiting) >= 32:
                        collect()
                while waiting:
                    collect()
            require(len(worker_counts) == 16 and all(n > 0 for n in worker_counts.values()), "Actual16 nonempty identity workers required")
            compute_seconds = time.monotonic() - compute_began
            coverage_proof = global_coverage(out, plan, units, budget)
            input_authority.verify_final(tickets)
            catalog = shared.load(plan["source_catalog"]["path"])
            counts, datasets = Counter(), Counter()
            for unit in units:
                counts.update(unit["counts"]); datasets.update(unit["datasets"])
            require(coverage_proof["records"] == sum(worker_counts.values()) == counts["records"], "Written/worker/unique coverage conservation differs")
            for dataset, count in {"som_cyp": 2003, "som_az": 120, "qm7": 7165, "qm9": 133885, "expansionrx": 7608}.items():
                require(datasets[dataset] == count, "Whole local identity cohort omitted: " + dataset)
            expected_records = (65536 if plan["pilot"] else 11231854) + 4900 + 2003 + 120 + 7165 + 133885 + 7608 + \
                sum(tickets[source_id].physical_count for source_id in cohorts.LOCAL_MOLNET)
            require(counts["records"] == expected_records, "All-local source row conservation differs")
            receipt = {"schema": "SB5_IDENTITY_EXPORT_RECEIPT_V3", "status": "LOCAL_IDENTITY_PROFILE_COMPLETE_EXTERNAL_PENDING" if plan["pilot"] else "LOCAL_ORIGINAL_SOURCE_RECORDS_EXPORTED_EXTERNAL_PENDING",
                "job_id": proof["job_id"], "node": proof["request"]["node"], "uid": os.getuid(), "mode": plan["mode"],
                "plan": shared.pin(Path(plan_path)), "startup_proof": shared.pin(Path(proof_path)), "startup_validation": startup_proof,
                "source_authority": source_authority, "body_hashes": body_hashes, "counts": dict(counts), "dataset_counts": dict(datasets),
                "new_boundary_tests": boundary_tests,
                "actual_worker_records": dict(worker_counts), "coverage": coverage_proof, "small_cohort_proofs": cohort_proofs,
                "closed_units": [{"unit_id": row["unit_id"], "file": row["file"]} for row in units],
                "phase_seconds": {"complete_source_hashes": hash_seconds, "whole_cohort_proof_preparation": cohort_prepare_seconds,
                                  "worker_and_unit_output": compute_seconds},
                "formal_unit_worker_seconds": sum(row["seconds"] for row in units if row["kind"] == "formal"),
                "nonformal_unit_worker_seconds": sum(row["seconds"] for row in units if row["kind"] != "formal"),
                "formal_unit_bytes": sum(row["file"]["bytes"] for row in units if row["kind"] == "formal"),
                "final_owned_output_bytes": execution.owned_bytes(out),
                "external_pending": coverage.external_pending_manifest(catalog), "apply_common_filter": False,
                "all_source_all_split_decontamination_accepted": False, "pool_UFF_QM_training_release_authorized": False,
                "runtime_budget": budget.receipt(), "wall_seconds": time.monotonic() - began}
            budget.check(force=True)
            shared.write_new(out / "receipt.json", receipt)
    except BaseException as exc:
        stop.set()
        shared.write_new(out / "failure.json", {"status": "IDENTITY_EXPORT_FAILED_NO_RELEASE", "type": type(exc).__name__, "error": str(exc),
            "closed_units": len(units), "actual_worker_records_so_far": dict(worker_counts), "runtime_budget": budget.receipt(),
            "partials_preserved": True, "forced_signals_sent": False})
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--root-preflight", type=Path, required=True)
    args = parser.parse_args()
    run(args.plan, args.root_preflight)


if __name__ == "__main__":
    main()
