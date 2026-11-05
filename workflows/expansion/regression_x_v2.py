"""Isolated replay of raw nullable rules and the actual WP0 enrichment cache.

This bounded repair pilot preserves v1 code/output and compares every selected
record with the frozen 8,741-row STOP. No source screening or full acceptance.
"""
from __future__ import annotations

import argparse
from collections import Counter, deque
from concurrent.futures import ProcessPoolExecutor
import json
import multiprocessing
import os
from pathlib import Path
import socket
import time

from . import regression_x_v1 as legacy
from . import common, data_authority_v1 as data_authority
from .common import ARTIFACT_ROOT, check_quota, dump_new, load, reference, require, verify

CODES, EXTRA = legacy.CODES, legacy.EXTRA
COALESCE_CAUSE = "HISTORICAL_UNASSIGNED_X01_UNKNOWN_COALESCED_TO_FALSE"
BOOL_FIELDS = ("old_chemical_admit", "new_graph_admit", "old_final", "conditional_new_final",
               "native_rule_mismatch", "portable_flag_mismatch", "unexplained", "cached_geometry_x1_augmentation",
               "legacy_native_rule_mismatch", "legacy_unexplained", "historical_unassigned_x1_coalesce",
               "raw_native_rule_mismatch", "enriched_native_rule_mismatch", "enrichment_metadata_mismatch")


def evaluate(row):
    # Reuse the immutable graph, admission, geometry/identity formulas and
    # portable comparison. Only the cache-comparison layer is corrected below.
    result = legacy.evaluate(row)
    result["legacy_native_rule_mismatch"] = result["native_rule_mismatch"]
    result["legacy_unexplained"] = result["unexplained"]
    graph = legacy.graph(row.get("smiles"))
    dot = "." in row["smiles"] if isinstance(row.get("smiles"), str) else None
    fragments = row.get("stored_graph_fragments")
    raw = {c: row[c] for c in CODES}
    raw["X01"] = legacy.nullable_or(dot, fragments > 1 if fragments is not None else None)
    native_raw = {c: graph.get(c) for c in CODES}
    native_raw["X02"] = (any(z not in legacy.WHITELIST for z in row["elements"])
                         if row.get("native_x_encoding_or_shape_invalid") is False and row.get("elements") is not None else None)
    native_raw["X05"] = row["electron_count"] % 2 == 1 if row.get("electron_count") is not None else None
    components = row.get("cached_geometry_components")
    component_hit = components is not None and components > 1
    native_enriched = dict(native_raw)
    # Exact enrich_geometry_cache.py:24-25: SQL coalesce on BOTH operands,
    # regardless of whether cached components are known. Unknown raw stays
    # unknown in the separate raw layer and becomes false only in this cache.
    native_enriched["X01"] = native_raw["X01"] is True or component_hit
    replayed_cache_x1 = raw["X01"] is True or component_hit
    raw_drift = [c for c in CODES if native_raw[c] != raw[c]]
    enriched_drift = [c for c in CODES if native_enriched[c] != row[c]]
    metadata_drift = []
    if row.get("X01_geometry_checked") != (components is not None):
        metadata_drift.append("X01_geometry_checked")
    if row["X01"] != replayed_cache_x1:
        metadata_drift.append("stored_X01_vs_exact_enrichment_formula")
    known_boundary = (row.get("member_train") is False and row.get("member_full") is False and
                      row.get("parse_failed") is True and row.get("sanitize_failed") is True and
                      fragments is None and components is None and raw["X01"] is None and
                      row["X01"] is False and row.get("X01_geometry_checked") is False and
                      raw["X03"] is None and raw["X04"] is None)
    result["historical_unassigned_x1_coalesce"] = known_boundary
    result["raw_native_rule_mismatch"] = bool(raw_drift)
    result["enriched_native_rule_mismatch"] = bool(enriched_drift)
    result["enrichment_metadata_mismatch"] = bool(metadata_drift)
    result["native_rule_mismatch"] = bool(raw_drift or enriched_drift or metadata_drift)
    old_detail = result.get("mismatch", {})
    causes = [c for c in old_detail.get("causes", []) if c != "UNEXPLAINED_CACHED_RULE_DRIFT"]
    if known_boundary:
        causes.append(COALESCE_CAUSE)
    if result["native_rule_mismatch"]:
        causes.append("UNEXPLAINED_CACHED_RULE_DRIFT")
    changed = (result["old_chemical_admit"] != result["new_graph_admit"] or
               result["old_final"] != result["conditional_new_final"] or result["portable_flag_mismatch"])
    result["unexplained"] = result["native_rule_mismatch"] or (changed and not causes)
    layers = {"record_id": row["record_id"], "molecule_id": row["molecule_id"],
              "original_raw_nullable_flags": raw, "original_enriched_flags": {c: row[c] for c in CODES},
              "native_replayed_raw_flags": native_raw, "native_replayed_enriched_flags": native_enriched,
              "portable_graph_flags": {c: graph.get(c) for c in CODES},
              "cached_geometry_components": components, "X01_geometry_checked": row.get("X01_geometry_checked"),
              "raw_native_mismatch": raw_drift, "enriched_native_mismatch": enriched_drift,
              "enrichment_metadata_mismatch_fields": metadata_drift, "causes": causes}
    result["layers"] = layers
    if old_detail or result["native_rule_mismatch"] or known_boundary:
        result["mismatch"] = {**old_detail, **layers, "source_path": row.get("source_path"),
                              "real_index": row.get("real_index"), "record_payload_sha256": row.get("record_payload_sha256"),
                              "smiles": row.get("smiles"), "native_mismatch": sorted(set(raw_drift + enriched_drift)),
                              "native_replayed_flags": native_enriched, "causes": causes,
                              "unexplained": result["unexplained"],
                              **{k: result[k] for k in BOOL_FIELDS}}
    return result


def evaluate_batch(rows):
    return [evaluate(row) for row in rows]


def parallel_results(batches):
    context = multiprocessing.get_context("spawn")
    with ProcessPoolExecutor(max_workers=16, mp_context=context, initializer=legacy._initialize,
                             initargs=(context.Barrier(16),)) as pool:
        waiting = deque()
        for batch in batches:
            waiting.append(pool.submit(evaluate_batch, batch))
            if len(waiting) >= 32:
                yield waiting.popleft().result(timeout=3600)
        while waiting:
            yield waiting.popleft().result(timeout=3600)


def historical_proof(plan):
    refs = plan["historical_proof_refs"]
    for ref in refs.values():
        require(ref["bytes"] <= 8 * 1024 ** 2, "Historical proof must be small metadata/source only")
        verify(ref)
    exact_sources = {
        "assigned_parser_source": "73a4e3e9dbf5722c976bda640474b1778328bd79f9b24b3acf82de3c6617f632",
        "wp0_inventory_source": "dae1d25ade45719eb8a393dc83daec8853dc85471a3d2d6ead9520cf9b4a60c7",
        "unassigned_parser_source": "043cc9cd1fac0662c54ac357d682849482831a98aa1297013dd65d7b4dad50e1",
        "enrichment_source": "4fa8a1d6108691eb6b1a0700f7b11e8598737214e78194d94a0f26a020f9a6cd",
        "quality_source": "c8a5e896bb2560d80ad2bbefb00a36a90b9ace4e4bb69f8b6d4d2083d1114740"}
    require(all(refs[k]["sha256"] == v for k, v in exact_sources.items()), "Unreviewed historical implementation")
    assigned = load(refs["assigned_parser_receipt"]["path"])
    unassigned = load(refs["unassigned_execution"]["path"])
    wp0 = load(refs["wp0_execution"]["path"])
    enriched = load(refs["enrichment_execution"]["path"])
    stop = load(refs["frozen_v1_stop"]["path"])
    submitted = load(refs["frozen_v1_submission"]["path"])
    diagnosis = load(refs["diagnosis_receipt"]["path"])
    rows = load(refs["diagnosis_rows"]["path"])["rows"]
    require(assigned["scanner_sha256"] == exact_sources["assigned_parser_source"] and
            assigned["environment"]["RDKit"] == "2025.09.5", "Assigned parser execution proof differs")
    require(unassigned["job_id"] == "4512802" and unassigned["script"] == refs["unassigned_parser_source"] and
            unassigned["records"] == 8259 and unassigned["software"]["RDKit"] == "2025.09.5",
            "Unassigned parser execution proof differs")
    require(wp0["job_id"] == "4512799" and wp0["script"] == refs["wp0_inventory_source"],
            "WP0 inventory execution proof differs")
    require(enriched["job_id"] == "4512808" and enriched["script_sha256"] == exact_sources["enrichment_source"],
            "Actual enrichment execution proof differs")
    require(submitted["job_id"] == "4520357" and submitted["sbatch_returncode"] == 0 and
            stop["status"] == "STOP_REVIEW" and stop["mode"] == "pilot" and stop["evaluated_records"] == 8741 and
            stop["counts"]["native_rule_mismatch"] == 335 and stop["record_decisions"] == refs["frozen_v1_decisions"] and
            stop["source_refs"] == plan["sources"], "Wrong frozen v1 pilot/source scope")
    require(diagnosis["status"] == "OBSERVED_FIELDS_ONLY_NO_GATE_CHANGE" and diagnosis["job_id"] == "4520359" and
            diagnosis["node"] == "compute-0-20" and diagnosis["source"] == plan["sources"]["original_index"] and
            diagnosis["frozen_stop"] == refs["frozen_v1_stop"] and diagnosis["output"] == refs["diagnosis_rows"] and
            diagnosis["missing_requested_columns"] == [] and diagnosis["projected_records"] == len(rows) == 335,
            "Wrong actual STOP diagnosis/source proof")
    ids = {r["record_id"] for r in rows}
    require(len(ids) == 335, "Diagnosis IDs are not unique")
    for r in rows:
        require(r["parse_failed"] is True and r["sanitize_failed"] is True and r["stored_graph_fragments"] is None and
                r["cached_geometry_components"] is None and r["X01"] is False and r["X01_geometry_checked"] is False and
                r["member_train"] is False and r["member_full"] is False and r["X03"] is None and r["X04"] is None and
                isinstance(r["smiles"], str) and "." not in r["smiles"], "Diagnosis does not prove the exact nullable/coalesce boundary")
    return ids


def compare_frozen_pilot(db, decisions, previous, diagnosis_ids):
    db.read_parquet(str(decisions)).create_view("v2_decisions")
    db.read_parquet(str(previous)).create_view("v1_decisions")
    import pyarrow as pa
    db.register("diagnosed_ids", pa.table({"record_id": sorted(diagnosis_ids)}))
    n, unique_n, old_n, unique_old, both = db.execute("""SELECT (SELECT count(*) FROM v2_decisions),
        (SELECT count(DISTINCT record_id) FROM v2_decisions),(SELECT count(*) FROM v1_decisions),
        (SELECT count(DISTINCT record_id) FROM v1_decisions),
        (SELECT count(*) FROM v2_decisions JOIN v1_decisions USING(record_id))""").fetchone()
    require(n == unique_n == old_n == unique_old == both == 8741, "Repair pilot does not cover every frozen v1 record")
    equal = ("molecule_id", "source_family", "old_chemical_admit", "new_graph_admit", "old_final", "conditional_new_final",
             "portable_flag_mismatch", "cached_geometry_x1_augmentation")
    changed = db.execute("SELECT count(*) FROM v2_decisions n JOIN v1_decisions o USING(record_id) WHERE " +
                         " OR ".join("n." + k + " IS DISTINCT FROM o." + k for k in equal)).fetchone()[0]
    legacy_drift = db.execute("""SELECT count(*) FROM v2_decisions n JOIN v1_decisions o USING(record_id)
        WHERE n.legacy_native_rule_mismatch IS DISTINCT FROM o.native_rule_mismatch
           OR n.legacy_unexplained IS DISTINCT FROM o.unexplained""").fetchone()[0]
    cohort_drift = db.execute("""SELECT count(*) FROM v2_decisions n LEFT JOIN diagnosed_ids d USING(record_id)
        WHERE n.historical_unassigned_x1_coalesce IS DISTINCT FROM (d.record_id IS NOT NULL)
           OR n.legacy_native_rule_mismatch IS DISTINCT FROM (d.record_id IS NOT NULL)
           OR n.legacy_unexplained IS DISTINCT FROM (d.record_id IS NOT NULL)""").fetchone()[0]
    require(changed == legacy_drift == cohort_drift == 0, "Repair changes a decision, frozen v1 result, or diagnosed correction cohort")
    return {"compared_records": n, "decision_or_portable_changes": changed, "legacy_replay_changes": legacy_drift,
            "cohort_symmetric_difference": cohort_drift, "exact_diagnosed_cohort_records": len(diagnosis_ids),
            "all_frozen_v1_pilot_records_checked": True}


def run(plan_path, intent_path):
    node = socket.gethostname().split(".")[0]
    require(os.getuid() == 1278 and node == "compute-0-20" and os.environ.get("SLURM_JOB_ID") and
            int(os.environ.get("SLURM_CPUS_PER_TASK", "0")) >= 16, "Actual Slurm >=16CPU compute20 required")
    plan, intent = load(plan_path), load(intent_path)
    require(plan["schema"] == "v1_X_regression_execution_plan_v2" and plan["status"] == "READY" and
            plan["mode"] == "pilot" and plan["workers"] == 16 and plan["seed"] == 20261025 and
            plan["pilot_max_rows"] == 10000 and plan["rdkit"] == "2025.09.5", "Unreviewed repair pilot scope")
    request = intent["request"]
    require(intent["uid"] == 1278 and request["root_review"]["status"] == "APPROVED" and request["node"] == node and
            request["cpus"] == 16 and request["memory_gib"] >= 32 and 0 < request["wall_seconds"] <= 3600 and
            request["estimated_peak_output_bytes"] >= plan["peak_output_cap_bytes"], "Root repair authority/resources differ")
    declared = {r["path"]: r for r in request["source_references"]}
    refs = [reference(plan_path), *plan["code_sources"], *plan["data_authorization_receipts"], *plan["historical_proof_refs"].values()]
    require(all(declared.get(r["path"]) == r for r in refs), "Root did not bind exact source/proof refs")
    for ref in plan["code_sources"]:
        verify(ref)
    actual = {str(Path(p).absolute()) for p in (__file__, legacy.__file__, common.__file__, data_authority.__file__,
              legacy.screen_source.__file__, legacy.quota_source.__file__, legacy.network_source.__file__)}
    require(actual <= {r["path"] for r in plan["code_sources"]}, "Actual repair runtime import chain is not pinned")
    ids = historical_proof(plan)
    out = Path(plan["output_root"]).absolute()
    require(out.is_relative_to(ARTIFACT_ROOT / "regression") and not out.exists(), "Fresh external repair output required")
    out.mkdir(parents=True)
    started = time.monotonic()
    legacy.acquire_fresh_quota(plan["quota"], out / "quota_start.json")
    check_quota(out / "quota_start.json", plan["peak_output_cap_bytes"])
    import duckdb
    import pyarrow as pa
    import pyarrow.parquet as pq
    db = duckdb.connect()
    counts, causes, pids = Counter(), Counter(), set()
    decisions, details, layers_path = out / "record_decisions.parquet", out / "all_mismatches.jsonl", out / "all_rule_layers.jsonl"
    try:
        db.execute("SET threads=16")
        db.execute(f"SET memory_limit='{int(plan['duckdb_memory_gib'])}GB'")
        spill = out / "spill"; spill.mkdir()
        db.execute("SET temp_directory=?", [str(spill)])
        db.execute(f"SET max_temp_directory_size='{int(plan['spill_gib'])}GB'")
        authority = data_authority.authorize_data(plan, intent, [r for r in plan["sources"].values() if r is not None], node=node)
        total = legacy.prepare_join(db, plan["sources"], plan["expected_original_records"], plan["expected_formal_records"])
        data_authority.verify_final_stats(authority)
        source_seconds = time.monotonic() - started
        sampling = legacy.select_pilot(db, plan["seed"], plan["pilot_max_rows"])
        require(db.execute("SELECT count(*) FROM pilot").fetchone()[0] == 8741, "Frozen stratified pilot membership changed")
        dump_new(out / "pilot_sampling.json", sampling)
        schema = pa.schema([(k, pa.string()) for k in ("record_id", "molecule_id", "source_family")] +
                           [(k, pa.bool_()) for k in BOOL_FIELDS])
        db.execute("SET threads=1")
        cursor = db.execute("""SELECT p.*,i.sanitize_failed,i.cached_geometry_components FROM pilot p
            JOIN original i USING(record_id) ORDER BY p.record_id""")
        workers_started = time.monotonic()
        with pq.ParquetWriter(decisions, schema, compression="zstd") as writer, \
                details.open("x", encoding="utf-8", newline="\n") as detail, \
                layers_path.open("x", encoding="utf-8", newline="\n") as layer_stream:
            for batch in parallel_results(legacy.input_batches(cursor)):
                payload = []
                for r in batch:
                    pids.add(r["worker_pid"])
                    counts["records"] += 1
                    counts.update({k: int(r[k]) for k in BOOL_FIELDS})
                    counts["chemical_admission_changed"] += int(r["old_chemical_admit"] != r["new_graph_admit"])
                    counts["conditional_final_changed"] += int(r["old_final"] != r["conditional_new_final"])
                    layer_stream.write(json.dumps(r["layers"], separators=(",", ":"), allow_nan=False) + "\n")
                    if "mismatch" in r:
                        detail.write(json.dumps(r["mismatch"], separators=(",", ":"), allow_nan=False) + "\n")
                        causes.update(r["mismatch"]["causes"])
                    payload.append({k: r[k] for k in schema.names})
                writer.write_table(pa.Table.from_pylist(payload, schema=schema))
                require(sum(p.stat().st_size for p in out.rglob("*") if p.is_file()) <= plan["peak_output_cap_bytes"], "Repair output/spill cap exceeded")
            for stream in (detail, layer_stream):
                stream.flush(); os.fsync(stream.fileno())
        comparison = compare_frozen_pilot(db, decisions, plan["historical_proof_refs"]["frozen_v1_decisions"]["path"], ids)
        good = counts["records"] == 8741 and counts["native_rule_mismatch"] == counts["unexplained"] == 0 and len(pids) == 16
        data_authority.verify_final_stats(authority)
        report = {"schema": "pubchem_v1_complete_input_regression_v2", "mode": "pilot",
                  "status": "PILOT_RULE_REPLAY_CLOSED" if good else "STOP_REVIEW", "node": node,
                  "job_id": os.environ["SLURM_JOB_ID"], "uid": os.getuid(), "plan": reference(plan_path),
                  "root_submission": reference(intent_path), "source_refs": plan["sources"], "data_authority": authority,
                  "historical_proof_refs": plan["historical_proof_refs"], "all_original_records": total,
                  "evaluated_records": counts["records"], "counts": dict(counts), "causes": dict(causes),
                  "frozen_v1_pilot_comparison": comparison, "rdkit": "2025.09.5", "worker_pids_observed": sorted(pids),
                  "chemical_admission_agreement": 1 - counts["chemical_admission_changed"] / counts["records"],
                  "conditional_geometry_identity_selection_agreement": 1 - counts["conditional_final_changed"] / counts["records"],
                  "five_portable_flag_agreement": 1 - counts["portable_flag_mismatch"] / counts["records"],
                  "record_decisions": reference(decisions), "all_mismatches": reference(details), "all_rule_layers": reference(layers_path),
                  "full_v1_selection_regression_passed": False, "sample_is_not_an_all_input_consistency_claim": True,
                  "pilot_rates_are_unweighted_stratified_observations_not_population_estimates": True,
                  "old_geometry_identity_decisions_held_fixed": True, "source_screening_run": False,
                  "original_lmdb_opened_or_modified": False, "wall_seconds": time.monotonic() - started,
                  "source_verification_and_join_seconds": source_seconds,
                  "sampling_and_ordering_seconds": workers_started - started - source_seconds,
                  "worker_pipeline_wall_seconds": time.monotonic() - workers_started}
        dump_new(out / "receipt.json", report)
        require(good, "STOP: raw/native/enrichment drift or unexplained repair mismatch")
    except Exception as exc:
        dump_new(out / "failure.json", {"status": "FAILED_REPAIR_PILOT", "error_type": type(exc).__name__,
                 "error": str(exc), "counts_so_far": dict(counts), "wall_seconds": time.monotonic() - started})
        raise
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
