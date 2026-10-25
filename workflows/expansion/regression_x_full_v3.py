"""All-original-record replay with compact, budgeted, traceable Parquet output.

The immutable v2 evaluator supplies chemical/cache semantics. This entry adds
full coverage, compact output, closed-pilot regression checks and resource caps.
It cannot release the unfrozen common-population or downstream/training gates.
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

from . import regression_x_v2 as repaired
from . import regression_x_v1 as legacy
from . import common, data_authority_v1 as data_authority
from .common import ARTIFACT_ROOT, check_quota, dump_new, load, reference, require, verify

BOOL_FIELDS = repaired.BOOL_FIELDS
LAYER_FIELDS = ("original_raw_nullable_flags", "original_enriched_flags", "native_replayed_raw_flags",
                "native_replayed_enriched_flags", "portable_graph_flags")
CAUSES = ("INVALID_ORIGINAL_NATIVE_X", "NATIVE_GRAPH_ELEMENT_DIFFERENCE",
          "NATIVE_GRAPH_HYDROGEN_OR_ATOM_COUNT_DIFFERENCE", "ORIGINAL_SMILES_UNPARSEABLE",
          repaired.COALESCE_CAUSE, "UNEXPLAINED_CACHED_RULE_DRIFT")
ROW_FIELDS = ("record_id", "molecule_id", "source_family", "decision_bits", *LAYER_FIELDS, "cause_bits")


def encode_flags(flags):
    value = 0
    for i, code in enumerate(repaired.CODES):
        flag = flags[code]
        require(flag is None or type(flag) is bool, "Rule flag is not ternary")
        value |= (2 if flag is None else int(flag)) << (2 * i)
    return value


def decode_flags(value):
    require(type(value) is int and 0 <= value < 1024, "Invalid five-rule bit code")
    flags = {}
    for i, code in enumerate(repaired.CODES):
        token = (value >> (2 * i)) & 3
        require(token < 3, "Reserved ternary flag code")
        flags[code] = None if token == 2 else bool(token)
    return flags


def compact_result(result):
    bits = sum(int(result[k]) << i for i, k in enumerate(BOOL_FIELDS))
    causes = result["layers"]["causes"]
    require(set(causes) <= set(CAUSES), "Unregistered cause cannot be silently dropped")
    cause_bits = sum(1 << i for i, cause in enumerate(CAUSES) if cause in causes)
    row = (result["record_id"], result["molecule_id"], result["source_family"], bits,
           *(encode_flags(result["layers"][k]) for k in LAYER_FIELDS), cause_bits)
    mismatch = None
    if "mismatch" in result:
        mismatch = (row[0], row[1], row[2], json.dumps(result["mismatch"], separators=(",", ":"), allow_nan=False))
    return row, mismatch


def evaluate_batch(rows):
    compact, mismatches, counts, causes = [], [], Counter(), Counter()
    for source in rows:
        r = repaired.evaluate(source)
        row, mismatch = compact_result(r)
        compact.append(row)
        if mismatch is not None:
            mismatches.append(mismatch)
            causes.update(r["mismatch"]["causes"])
        counts["records"] += 1
        counts.update({k: int(r[k]) for k in BOOL_FIELDS})
        counts["chemical_admission_changed"] += int(r["old_chemical_admit"] != r["new_graph_admit"])
        counts["conditional_final_changed"] += int(r["old_final"] != r["conditional_new_final"])
    return {"rows": compact, "mismatches": mismatches, "counts": dict(counts), "causes": dict(causes),
            "worker_pid": os.getpid(), "records": len(rows)}


def parallel_results(batches):
    context = multiprocessing.get_context("spawn")
    with ProcessPoolExecutor(max_workers=16, mp_context=context, initializer=legacy._initialize,
                             initargs=(context.Barrier(16),)) as pool:
        waiting = deque()
        for batch in batches:
            waiting.append(pool.submit(evaluate_batch, batch))
            if len(waiting) >= 32:
                yield waiting.popleft().result(timeout=14400)
        while waiting:
            yield waiting.popleft().result(timeout=14400)


def closed_pilot_proof(plan):
    refs = plan["closed_v2_proof_refs"]
    for ref in refs.values():
        require(ref["bytes"] <= 8 * 1024 ** 2, "Closed pilot proof must be small")
        verify(ref)
    receipt = load(refs["receipt"]["path"])
    closure = load(refs["actual_closure"]["path"])
    pilot_plan = load(refs["plan"]["path"])
    require(receipt["schema"] == "pubchem_v1_complete_input_regression_v2" and receipt["mode"] == "pilot" and
            receipt["status"] == "PILOT_RULE_REPLAY_CLOSED" and receipt["job_id"] == "4520376" and
            receipt["evaluated_records"] == 8741 and receipt["source_refs"] == plan["sources"] and
            receipt["historical_proof_refs"] == plan["historical_proof_refs"] and receipt["plan"] == refs["plan"] and
            receipt["record_decisions"] == refs["decisions"], "Wrong closed v2 pilot or source scope")
    require(closure["status"] == "ROOT_X_REPLAY_V2_PILOT_ACTUAL_COMPLETED_SOURCE_BOUNDARY_CLOSED" and
            closure["receipt"] == refs["receipt"] and closure["actual_parent"]["JobIDRaw"] == "4520376" and
            closure["actual_parent"]["State"] == "COMPLETED" and closure["actual_parent"]["ExitCode"] == "0:0" and
            closure["actual_parent"]["AllocCPUS"] == "16" and closure["actual_parent"]["NodeList"] == "compute-0-20",
            "Actual successful v2 parent closure required")
    require(all(receipt["counts"][k] == 0 for k in ("native_rule_mismatch", "unexplained", "raw_native_rule_mismatch",
                "enriched_native_rule_mismatch", "enrichment_metadata_mismatch", "chemical_admission_changed", "conditional_final_changed")),
            "Closed repair pilot contains unresolved drift")
    by_name = {Path(r["path"]).name: r for r in pilot_plan["code_sources"]}
    for p in (repaired.__file__, legacy.__file__, common.__file__, data_authority.__file__, legacy.screen_source.__file__,
              legacy.quota_source.__file__, legacy.network_source.__file__):
        current = reference(p)
        old = by_name.get(Path(p).name)
        require(old and all(current[k] == old[k] for k in ("bytes", "sha256")), "Frozen v2 runtime source changed")
    return receipt


def decoded_projection():
    return ",".join(["record_id", "molecule_id", "source_family"] +
                    [f"((decision_bits & {1 << i}) != 0) AS {k}" for i, k in enumerate(BOOL_FIELDS)])


def coverage(db, path, expected_records):
    db.read_parquet(str(path)).create_view("compact_decisions")
    n, unique = db.execute("SELECT count(*),count(DISTINCT record_id) FROM compact_decisions").fetchone()
    matched = db.execute("SELECT count(*) FROM compact_decisions SEMI JOIN original USING(record_id)").fetchone()[0]
    require(n == unique == matched == expected_records, "Full output does not cover exactly every unique original source ID")
    db.execute("CREATE VIEW full_decisions AS SELECT " + decoded_projection() + " FROM compact_decisions")
    return {"records": n, "unique_records": unique, "matched_unique_original_ids": matched,
            "complete_original_source_coverage": True}


def compare_closed_pilot(db, subset_path, prior_path):
    db.read_parquet(str(subset_path)).create_view("full_pilot_subset")
    db.read_parquet(str(prior_path)).create_view("closed_v2_decisions")
    n, old_n = db.execute("SELECT (SELECT count(*) FROM full_pilot_subset),(SELECT count(*) FROM closed_v2_decisions)").fetchone()
    require(n == old_n == 8741, "Closed pilot comparison lacks its exact record population")
    fields = ("molecule_id", "source_family", *BOOL_FIELDS)
    changed = db.execute("SELECT count(*) FROM full_pilot_subset n FULL JOIN closed_v2_decisions o USING(record_id) WHERE " +
                         "n.record_id IS NULL OR o.record_id IS NULL OR " +
                         " OR ".join("n." + k + " IS DISTINCT FROM o." + k for k in fields)).fetchone()[0]
    require(changed == 0, "Full replay changed an already closed v2 pilot row")
    return {"compared_records": 8741, "changed_rows": changed, "all_v2_boolean_decisions_identical": True}


def output_usage(out, plan):
    artifact, spill = 0, 0
    for p in out.rglob("*"):
        if p.is_file():
            if p.is_relative_to(out / "spill"):
                spill += p.stat().st_size
            else:
                artifact += p.stat().st_size
    require(artifact <= plan["artifact_soft_cap_bytes"] and spill <= plan["spill_cap_bytes"] and
            artifact + spill <= plan["peak_output_cap_bytes"], "STOP: full replay output/spill budget reached")
    return {"artifact_bytes": artifact, "spill_bytes": spill, "total_bytes": artifact + spill}


def run(plan_path, intent_path):
    node = socket.gethostname().split(".")[0]
    require(os.getuid() == 1278 and node == "compute-0-20" and os.environ.get("SLURM_JOB_ID") and
            int(os.environ.get("SLURM_CPUS_PER_TASK", "0")) >= 16, "Actual zixiao Slurm16 compute20 required")
    plan, intent = load(plan_path), load(intent_path)
    require(plan["schema"] == "v1_X_full_regression_execution_plan_v3" and plan["status"] == "READY" and
            plan["mode"] == "full" and plan["workers"] == 16 and plan["expected_original_records"] == 15879477 and
            plan["rdkit"] == "2025.09.5" and plan["sources"].get("common_population") is None,
            "This full replay cannot release an unfrozen common-population scope")
    require(plan["peak_output_cap_bytes"] == 16 * 1024 ** 3 and plan["artifact_soft_cap_bytes"] == 7 * 1024 ** 3 and
            plan["spill_cap_bytes"] == 8 * 1024 ** 3 and plan["duckdb_memory_gib"] == 8 and
            plan["internal_wall_seconds"] == 13800, "Unreviewed full output/time caps")
    request = intent["request"]
    require(intent["uid"] == 1278 and request["root_review"]["status"] == "APPROVED" and request["node"] == node and
            request["cpus"] == 16 and request["memory_gib"] >= 32 and request["wall_seconds"] == 14400 and
            request["estimated_peak_output_bytes"] == plan["peak_output_cap_bytes"], "Root full resources differ")
    refs = [reference(plan_path), *plan["code_sources"], *plan["data_authorization_receipts"],
            *plan["historical_proof_refs"].values(), *plan["closed_v2_proof_refs"].values()]
    declared = {r["path"]: r for r in request["source_references"]}
    require(all(declared.get(r["path"]) == r for r in refs), "Root did not bind full code/proof refs")
    for ref in plan["code_sources"]:
        verify(ref)
    actual = {str(Path(p).absolute()) for p in (__file__, repaired.__file__, legacy.__file__, common.__file__, data_authority.__file__,
              legacy.screen_source.__file__, legacy.quota_source.__file__, legacy.network_source.__file__)}
    require(actual <= {r["path"] for r in plan["code_sources"]}, "Full runtime import chain is not pinned")
    diagnosis_ids = repaired.historical_proof(plan)
    closed = closed_pilot_proof(plan)
    out = Path(plan["output_root"]).absolute()
    require(out.is_relative_to(ARTIFACT_ROOT / "regression") and not out.exists(), "Fresh external full replay output required")
    out.mkdir(parents=True)
    started = time.monotonic()
    legacy.acquire_fresh_quota(plan["quota"], out / "quota_start.json")
    check_quota(out / "quota_start.json", plan["peak_output_cap_bytes"])
    import duckdb
    import pyarrow as pa
    import pyarrow.parquet as pq
    metadata = {b"schema": b"v1_full_x_compact_record_v3", b"boolean_bits": json.dumps(BOOL_FIELDS).encode(),
                b"ternary_rule_order": json.dumps(repaired.CODES).encode(), b"ternary_encoding": b"2 bits: 0=false,1=true,2=unknown,3=reserved",
                b"cause_bits": json.dumps(CAUSES).encode()}
    schema = pa.schema([(k, pa.string()) for k in ROW_FIELDS[:3]] +
                       [(k, pa.uint16()) for k in ROW_FIELDS[3:]], metadata=metadata)
    mismatch_schema = pa.schema([(k, pa.string()) for k in ("record_id", "molecule_id", "source_family", "details_json")])
    decisions, mismatches = out / "record_decisions.parquet", out / "all_mismatches.parquet"
    db = duckdb.connect()
    counts, causes, workers = Counter(), Counter(), Counter()
    peak_bytes, mismatch_rows = 0, 0
    try:
        db.execute("SET threads=16")
        db.execute("SET memory_limit='8GB'")
        db.execute("SET max_temp_directory_size='8GB'")
        db.execute("SET preserve_insertion_order=false")
        spill = out / "spill"; spill.mkdir()
        db.execute("SET temp_directory=?", [str(spill)])
        authority = data_authority.authorize_data(plan, intent, [r for r in plan["sources"].values() if r is not None], node=node)
        total = legacy.prepare_join(db, plan["sources"], plan["expected_original_records"], plan["expected_formal_records"])
        data_authority.verify_final_stats(authority)
        source_seconds = time.monotonic() - started
        db.execute("SET threads=1")
        cursor = db.execute("""SELECT j.*,i.sanitize_failed,i.cached_geometry_components FROM joined j
            JOIN original i USING(record_id)""")
        usage = output_usage(out, plan)
        peak_bytes = max(peak_bytes, usage["total_bytes"])
        workers_started = time.monotonic()
        row_buffer, mismatch_buffer, mismatch_buffer_bytes = [], [], 0
        with pq.ParquetWriter(decisions, schema, compression="zstd") as writer, \
                pq.ParquetWriter(mismatches, mismatch_schema, compression="zstd") as detail, \
                (out / "progress.jsonl").open("x", encoding="utf-8", newline="\n") as progress:
            for batch in parallel_results(legacy.input_batches(cursor, size=512)):
                counts.update(batch["counts"]); causes.update(batch["causes"])
                workers[batch["worker_pid"]] += batch["records"]
                row_buffer.extend(batch["rows"])
                mismatch_buffer.extend(batch["mismatches"])
                mismatch_rows += len(batch["mismatches"])
                mismatch_buffer_bytes += sum(len(r[-1].encode("utf-8")) for r in batch["mismatches"])
                wrote_output = False
                if len(row_buffer) >= 65536:
                    writer.write_table(pa.Table.from_pylist([dict(zip(ROW_FIELDS, r)) for r in row_buffer], schema=schema), row_group_size=65536)
                    row_buffer.clear()
                    wrote_output = True
                if len(mismatch_buffer) >= 2048 or mismatch_buffer_bytes >= 8 * 1024 ** 2:
                    detail.write_table(pa.Table.from_pylist([dict(zip(mismatch_schema.names, r)) for r in mismatch_buffer], schema=mismatch_schema))
                    mismatch_buffer.clear(); mismatch_buffer_bytes = 0
                    wrote_output = True
                if wrote_output or counts["records"] % 65536 == 0:
                    usage = output_usage(out, plan)
                    peak_bytes = max(peak_bytes, usage["total_bytes"])
                require(time.monotonic() - started < plan["internal_wall_seconds"], "STOP: internal full replay time budget reached")
                if counts["records"] % 65536 == 0:
                    event = {"records": counts["records"], "total_original_records": total, "worker_records": dict(workers),
                             "wall_seconds": time.monotonic() - started, "mismatch_rows": mismatch_rows, **usage}
                    progress.write(json.dumps(event, separators=(",", ":")) + "\n"); progress.flush(); os.fsync(progress.fileno())
                    print(json.dumps(event, separators=(",", ":")), flush=True)
            if row_buffer:
                writer.write_table(pa.Table.from_pylist([dict(zip(ROW_FIELDS, r)) for r in row_buffer], schema=schema))
            if mismatch_buffer:
                detail.write_table(pa.Table.from_pylist([dict(zip(mismatch_schema.names, r)) for r in mismatch_buffer], schema=mismatch_schema))
        worker_seconds = time.monotonic() - workers_started
        require(counts["records"] == total and len(workers) == 16 and all(n > 0 for n in workers.values()),
                "Incomplete full source replay or actual sixteen-worker execution")
        db.execute("SET threads=16")
        scope = coverage(db, decisions, total)
        db.read_parquet(plan["closed_v2_proof_refs"]["decisions"]["path"]).create_view("closed_pilot_ids")
        db.execute("CREATE TABLE pilot_subset AS SELECT d.* FROM full_decisions d SEMI JOIN closed_pilot_ids p USING(record_id)")
        subset = out / "closed_pilot_subset.parquet"
        db.execute("COPY pilot_subset TO ? (FORMAT PARQUET, COMPRESSION ZSTD)", [str(subset)])
        prior_check = repaired.compare_frozen_pilot(db, subset, plan["historical_proof_refs"]["frozen_v1_decisions"]["path"], diagnosis_ids)
        repaired_check = compare_closed_pilot(db, subset, plan["closed_v2_proof_refs"]["decisions"]["path"])
        molecular = db.execute("""SELECT count(*),count(*) FILTER(WHERE old_selected IS DISTINCT FROM new_selected),
            count(*) FILTER(WHERE old_selected),count(*) FILTER(WHERE new_selected) FROM (
            SELECT molecule_id,bool_or(old_final) AS old_selected,bool_or(conditional_new_final) AS new_selected
            FROM full_decisions GROUP BY molecule_id)""").fetchone()
        chemical = 1 - counts["chemical_admission_changed"] / total
        conditional = 1 - counts["conditional_final_changed"] / total
        molecule_agreement = 1 - molecular[1] / molecular[0]
        stored_mismatches = pq.ParquetFile(mismatches).metadata.num_rows
        require(stored_mismatches == mismatch_rows, "Not every generated mismatch was stored")
        data_authority.verify_final_stats(authority)
        usage = output_usage(out, plan); peak_bytes = max(peak_bytes, usage["total_bytes"])
        good = counts["native_rule_mismatch"] == counts["unexplained"] == 0 and min(chemical, conditional, molecule_agreement) >= .999
        report = {"schema": "pubchem_v1_complete_input_regression_full_v3", "mode": "full",
                  "status": "FULL_X_RULE_PASS_COMMON_SCOPE_PENDING" if good else "STOP_REVIEW", "node": node,
                  "job_id": os.environ["SLURM_JOB_ID"], "uid": os.getuid(), "plan": reference(plan_path),
                  "root_submission": reference(intent_path), "source_refs": plan["sources"], "data_authority": authority,
                  "historical_proof_refs": plan["historical_proof_refs"], "closed_v2_proof_refs": plan["closed_v2_proof_refs"],
                  "all_original_records": total, "evaluated_records": counts["records"], "complete_source_coverage": scope,
                  "counts": dict(counts), "causes": dict(causes), "frozen_v1_pilot_comparison": prior_check,
                  "closed_v2_pilot_comparison": repaired_check, "historical_coalesce_applied_to_all_source_records": True,
                  "original_335_ids_are_regression_checks_not_a_full_scope_whitelist": True,
                  "chemical_admission_agreement": chemical, "conditional_geometry_identity_selection_agreement": conditional,
                  "molecules_observed": molecular[0], "conditional_changed_molecules": molecular[1],
                  "conditional_molecule_agreement": molecule_agreement, "old_selected_molecules": molecular[2],
                  "conditional_new_selected_molecules": molecular[3], "five_portable_flag_agreement": 1 - counts["portable_flag_mismatch"] / total,
                  "actual_worker_records": dict(workers), "worker_pids_observed": sorted(workers), "rdkit": "2025.09.5",
                  "record_decisions": reference(decisions), "all_mismatches": reference(mismatches), "mismatch_rows": mismatch_rows,
                  "all_mismatch_details_stored": True, "compact_rule_layers_encoding": "2 bits per X01..X05; 0=false,1=true,2=unknown",
                  "boolean_bit_order": list(BOOL_FIELDS), "cause_bit_order": list(CAUSES), "peak_observed_owned_bytes": peak_bytes,
                  "final_owned_usage": usage, "wall_seconds": time.monotonic() - started,
                  "source_verification_and_join_seconds": source_seconds, "graph_worker_phase_seconds": worker_seconds,
                  "full_v1_selection_regression_passed": False, "common_population_scope_bound": False,
                  "final_training_or_full_expansion_gate_released": False, "source_screening_run": False,
                  "old_geometry_identity_decisions_held_fixed": True, "original_lmdb_opened_or_modified": False,
                  "sample_is_not_an_all_input_consistency_claim": False, "closed_pilot_receipt": reference(plan["closed_v2_proof_refs"]["receipt"]["path"])}
        dump_new(out / "receipt.json", report)
        require(good, "STOP: full raw/native/enrichment drift, unexplained mismatch or <99.9% selection agreement")
    except Exception as exc:
        dump_new(out / "failure.json", {"status": "FAILED_FULL_RULE_REPLAY", "error_type": type(exc).__name__,
                 "error": str(exc), "counts_so_far": dict(counts), "wall_seconds": time.monotonic() - started,
                 "complete_source_coverage_claimed": False, "no_training_or_expansion_gate_released": True,
                 "partial_artifacts_preserved": True})
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
