"""Fixed-seed uniform raw-row cost pilot, with a separate longest16 diagnostic.

No prefix substitution, guide1M reference, decontamination, ranking or pool
release. Every completed result is journaled before its Parquet batch flush.
"""
from __future__ import annotations

import argparse
from collections import Counter, deque
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import tempfile
import time
import traceback
import unittest

from workflows.data_v1_final.execution.queue_v1 import shared
from .. import full_queue_v1 as files
from . import policy, runtime, source


STOP = None
INITIALIZATION = {}
FLOAT_FEATURES = ("molecular_weight_Da", "tpsa_A2", "logp")
INT_FEATURES = ("heavy_atoms", "isotopic_atoms", "rings", "aromatic_rings", "rotatable_bonds", "hbd", "hba", "stereocenters")
TEXT_FEATURES = ("isomeric_smiles", "full_key", "wp5_key", "non_h_composition", "element_combination", "generic_murcko", "ecfp4_2048_hex")
FEATURE_KEYS = {"cid", "ordinal", "reasons", "source_smiles", "elements", "generic_ring_systems",
                *FLOAT_FEATURES, *INT_FEATURES, *TEXT_FEATURES}


def initialize(stop, barrier, chemical=False):
    global STOP, INITIALIZATION
    STOP = source.STOP = stop
    began, cpu = time.monotonic(), time.process_time()
    if chemical:
        from .. import features_legacy_compatible_v2 as compatible
        compatible.rdkit_modules()
    INITIALIZATION = {"pid": os.getpid(), "elapsed_seconds": time.monotonic() - began,
                      "CPU_seconds": time.process_time() - cpu, "chemical": chemical}
    barrier.wait(timeout=180)


def bounded(pool, function, tasks, stop):
    """At most32 pending tasks; stop new submissions and drain every submitted task."""
    waiting = deque()
    def collect():
        task_id, future = waiting.popleft()
        try:
            return task_id, future.result(), None
        except Exception as exc:
            stop.set()
            return task_id, None, {"type": type(exc).__name__, "error": str(exc), "traceback": traceback.format_exc()}
    for task_id, task in tasks:
        if stop.is_set():
            break
        waiting.append((task_id, pool.submit(function, task)))
        if len(waiting) >= policy.PENDING:
            yield collect()
    while waiting:
        yield collect()


def journal(stream, value):
    raw = (json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=True) + "\n").encode()
    shared.need(len(raw) <= policy.CONTAINER_CAP // policy.PENDING, "RECORD_IPC_OUTPUT_CONTAINER_STOP_NO_TRUNCATION")
    stream.write(raw); stream.flush(); os.fsync(stream.fileno())


def check_drain(budget, errors):
    try:
        budget.check()
    except files.CooperativeStop as exc:
        if not errors:
            errors.append({"type": type(exc).__name__, "error": str(exc)})


def scan_task(task):
    part, ordinals, extract, frame = task
    began, cpu = time.monotonic(), time.process_time()
    value = source.scan_part(part, ordinals, extract=extract, expected_frame=frame)
    shared.need(len(json.dumps(value, ensure_ascii=False).encode()) <= policy.CONTAINER_CAP // policy.PENDING,
                "SOURCE_RESULT_IPC_CONTAINER_STOP_NO_TRUNCATION")
    return {**value, "elapsed_seconds": time.monotonic() - began, "CPU_seconds": time.process_time() - cpu}


def funnel(result, audit_flags, audit_parse, errors, original):
    """Preserve legacy reasons; undefined parse X bits never become false flags."""
    codes = list(errors)
    if not isinstance(result, dict) or type(result.get("reasons")) is not list:
        return "technicalUnresolved", [*codes, "DISPATCHER_RESULT_OR_REASONS_UNAVAILABLE"]
    if result.get("cid") != int(original["cid_source_ascii"]) or result.get("ordinal") != original["ordinal"]:
        codes.append("DISPATCHER_SOURCE_IDENTITY_MISMATCH")
    reasons = result["reasons"]
    full_boolean_audit = set(audit_flags) == {"X01", "X02", "X03", "X04", "X05"} and all(
        type(value) is bool for value in audit_flags.values())
    if reasons and all(reason in ("X01", "X02", "X03", "X04", "X05") for reason in reasons):
        expected = [name for name in ("X01", "X02", "X03", "X04", "X05") if audit_flags.get(name) is True]
        if audit_parse is not True or not full_boolean_audit or reasons != expected:
            codes.append("AUDIT_DISPATCHER_X_REASONS_CONFLICT")
        return ("technicalUnresolved", codes) if codes else ("chemReject", [])
    if reasons:
        return "technicalUnresolved", [*codes, "LEGACY_NON_X_REASON_PRESERVED:" + ",".join(map(str, reasons))]
    if audit_parse is not True or not full_boolean_audit or any(audit_flags.values()):
        codes.append("AUDIT_DISPATCHER_PARSE_OR_X_CONFLICT")
    if set(result) != FEATURE_KEYS or result.get("source_smiles") != original["source_smiles"]:
        codes.append("FULL_FEATURE_OR_SOURCE_FIELDS_DIFFER")
    try:
        json.dumps(result, allow_nan=False)
    except (ValueError, TypeError):
        codes.append("NONFINITE_OR_NONJSON_FEATURE_RESULT")
    return ("technicalUnresolved", codes) if codes else ("accepted", [])


def chemical_task(original):
    if STOP.is_set():
        raise files.CooperativeStop("STOP_BEFORE_NEXT_CHEMICAL_RECORD")
    from .. import features_legacy_compatible_v2 as compatible
    audit_flags, audit_parse, result, errors = {}, None, None, {}
    started, cpu = time.monotonic(), time.process_time()
    try:
        # The frozen signature is chemical_flags(smiles: str), not a Mol.
        molecule, audit_flags = compatible.chemical_flags(original["source_smiles"])
        audit_parse = molecule is not None
        del molecule
    except Exception as exc:
        errors["INDEPENDENT_X_AUDIT_EXCEPTION"] = {"type": type(exc).__name__, "message": str(exc), "traceback": traceback.format_exc()}
    audit_wall, audit_cpu = time.monotonic() - started, time.process_time() - cpu
    started, cpu = time.monotonic(), time.process_time()
    try:
        # This exact597 wrapper already includes original parse/X via legacy features.
        result = compatible.features_candidate(int(original["cid_source_ascii"]), original["source_smiles"], original["ordinal"])
    except Exception as exc:
        errors["COMPATIBLE_DISPATCHER_EXCEPTION"] = {"type": type(exc).__name__, "message": str(exc), "traceback": traceback.format_exc()}
    dispatch_wall, dispatch_cpu = time.monotonic() - started, time.process_time() - cpu
    category, codes = funnel(result, audit_flags, audit_parse, errors, original)
    value = {"input": original, "category": category, "technical_codes": codes,
        "audit_parse_succeeded": audit_parse, "audit_flags": audit_flags,
        "legacy_dispatcher_result": result, "errors": errors,
        "audit_wall_seconds": audit_wall, "audit_CPU_seconds": audit_cpu,
        "dispatcher_wall_seconds_includes_legacy_X_parse": dispatch_wall,
        "dispatcher_CPU_seconds_includes_legacy_X_parse": dispatch_cpu,
        "worker_pid": os.getpid(), "worker_initialization": INITIALIZATION}
    raw = json.dumps(value, ensure_ascii=False, allow_nan=True).encode()
    shared.need(len(raw) <= policy.CONTAINER_CAP // policy.PENDING, "RESULT_CONTAINER_STOP_NO_FEATURE_TRUNCATION")
    return value


def output_schema():
    import pyarrow as pa
    fields = [(name, pa.string()) for name in ("sample_group", "cid_source_ascii", "source_smiles", "source_smiles_sha256",
        "source_part_reference_json", "category", "audit_flags_json", "full_dispatcher_result_json", "error_evidence_json")]
    fields += [("ordinal", pa.int64()), ("worker_pid", pa.int64()), ("audit_parse_succeeded", pa.bool_()),
        ("technical_codes", pa.list_(pa.string())), ("legacy_reasons", pa.list_(pa.string()))]
    fields += [("audit_" + name, pa.bool_()) for name in ("X01", "X02", "X03", "X04", "X05")]
    fields += [(name, pa.float64()) for name in (*FLOAT_FEATURES, "audit_wall_seconds", "audit_CPU_seconds",
        "dispatcher_wall_seconds_includes_legacy_X_parse", "dispatcher_CPU_seconds_includes_legacy_X_parse")]
    fields += [(name, pa.int64()) for name in INT_FEATURES] + [(name, pa.string()) for name in TEXT_FEATURES]
    fields += [("elements", pa.list_(pa.int32())), ("generic_ring_systems", pa.list_(pa.string()))]
    return pa.schema(fields)


def parquet_row(value, group):
    original, feature = value["input"], value["legacy_dispatcher_result"] or {}
    encoded = {"sample_group": group, "ordinal": original["ordinal"], "cid_source_ascii": original["cid_source_ascii"],
        "source_smiles": original["source_smiles"], "source_smiles_sha256": original["source_smiles_sha256"],
        "source_part_reference_json": json.dumps(original["source_part"], sort_keys=True), "category": value["category"],
        "audit_parse_succeeded": value["audit_parse_succeeded"], "audit_flags_json": json.dumps(value["audit_flags"], sort_keys=True),
        "technical_codes": value["technical_codes"], "legacy_reasons": feature.get("reasons"),
        "full_dispatcher_result_json": json.dumps(value["legacy_dispatcher_result"], ensure_ascii=False, allow_nan=True),
        "error_evidence_json": json.dumps(value["errors"], ensure_ascii=False), "worker_pid": value["worker_pid"]}
    for name in ("X01", "X02", "X03", "X04", "X05"):
        encoded["audit_" + name] = value["audit_flags"].get(name)
    for name in (*FLOAT_FEATURES, *INT_FEATURES, *TEXT_FEATURES, "elements", "generic_ring_systems"):
        encoded[name] = feature.get(name)
    for name in ("audit_wall_seconds", "audit_CPU_seconds", "dispatcher_wall_seconds_includes_legacy_X_parse",
                 "dispatcher_CPU_seconds_includes_legacy_X_parse"):
        encoded[name] = value[name]
    return encoded


def chemical_group(pool, rows, group, output, stop, budget):
    import pyarrow as pa
    import pyarrow.parquet as pq
    started = time.monotonic()
    counters, workers, initialization = Counter({name: 0 for name in ("accepted", "chemReject", "technicalUnresolved")}), Counter(), {}
    timings, errors, buffer = Counter(), [], []
    path = output / (group + ".features.parquet")
    log = output / (group + ".completed_results.jsonl")
    with log.open("xb") as journal_file, pq.ParquetWriter(path, output_schema(), compression="zstd") as writer:
        for ordinal, value, failure in bounded(pool, chemical_task, ((r["ordinal"], r) for r in rows), stop):
            if failure:
                journal(journal_file, {"ordinal": ordinal, "task_not_completed": True, "failure": failure})
                errors.append(failure)
                continue
            journal(journal_file, value)  # Exact full feature/error values persist before the buffer.
            buffer.append(parquet_row(value, group))
            counters[value["category"]] += 1
            workers[str(value["worker_pid"])] += 1
            initialization[str(value["worker_pid"])] = value["worker_initialization"]
            for name in ("audit_wall_seconds", "audit_CPU_seconds", "dispatcher_wall_seconds_includes_legacy_X_parse",
                         "dispatcher_CPU_seconds_includes_legacy_X_parse"):
                timings[name] += value[name]
            if len(buffer) >= 64:
                writer.write_table(pa.Table.from_pylist(buffer, schema=output_schema())); buffer = []
            check_drain(budget, errors)
        if buffer:
            writer.write_table(pa.Table.from_pylist(buffer, schema=output_schema()))
    record = {"group": group, "input_rows": len(rows), "completed_rows": sum(counters.values()), "counts": dict(counters),
        "worker_records": dict(workers), "worker_initialization": initialization,
        "phase_wall_seconds": time.monotonic() - started, "worker_task_phase_sums": dict(timings),
        "features": files.file_pin(path), "full_result_journal": files.file_pin(log), "execution_failures": errors,
        "triple_conservation": sum(counters.values()) == len(rows),
        "technical_unknown_is_not_an_extra_chemical_exclusion": True}
    record["phase_wall_seconds"] = time.monotonic() - started
    record["per_row_worker_time_sums_not_parent_allocation"] = {name: value / len(rows) for name, value in timings.items()}
    record["per_row_full_audit_plus_dispatch_worker_CPU_seconds"] = (
        timings["audit_CPU_seconds"] + timings["dispatcher_CPU_seconds_includes_legacy_X_parse"]) / len(rows)
    record["parallel_phase_wall_seconds_per_input_row_not_CPU"] = record["phase_wall_seconds"] / len(rows)
    shared.write_new(output / (group + ".receipt.json"), record)
    shared.need(not errors and record["triple_conservation"], "INCOMPLETE_CHEMICAL_PHASE_PARTIALS_RETAINED")
    if group == "uniform10000":
        shared.need(len(workers) == 16 and min(workers.values()) > 0, "ACTUAL16_NONEMPTY_UNIFORM_CHEMICAL_WORKERS_REQUIRED")
    return record


def source_phase(pool, tasks, output, label, stop, budget):
    results, errors = [], []
    began = time.monotonic()
    log_path = output / (label + ".completed_parts.jsonl")
    with log_path.open("xb") as stream:
        for index, value, failure in bounded(pool, scan_task, tasks, stop):
            journal(stream, {"index": index, "result": value, "failure": failure})
            if failure:
                errors.append(failure)
            else:
                results.append(value)
            check_drain(budget, errors)
    shared.write_new(output / (label + ".receipt.json"), {"completed_parts": len(results), "execution_failures": errors,
        "completed_part_journal": files.file_pin(log_path),
        "wall_seconds": time.monotonic() - began, "CPU_seconds": sum(r["CPU_seconds"] for r in results),
        "processes": sorted({r["worker_pid"] for r in results})})
    shared.need(not errors and not stop.is_set(), "SOURCE_PHASE_STOPPED_PARTIALS_RETAINED:" + label)
    return results


def index_and_selection(plan, inventory):
    index = Path(plan["source_index"]["path"])
    before = files.frame(index)
    files.file_pin(index, expected=plan["source_index"], expected_frame=before, stop=source.STOP)
    uniform = source.sample_ordinals(plan["population_N"], seed=policy.SEED)
    parts, first, total_bytes = [], 1, 0
    for i, row in enumerate(source.index_rows(index)):
        source.validate_entry(row, root=plan["inventory_owned_root"], index=i, first_ordinal=first)
        parts.append(row); first = row["last_ordinal"] + 1; total_bytes += row["bytes"]
    shared.need(len(parts) == 500 and first - 1 == inventory["counts"]["records"] and
        total_bytes == inventory["counts"]["uncompressed_bytes"] and files.frame(index) == before,
        "FULL500_PART_INDEX_ROW_BYTE_ORDINAL_CONSERVATION")
    return parts, uniform, before


class RawUniformBoundaries(unittest.TestCase):
    def test_uniform_without_replacement_is_deterministic_and_not_a_prefix(self):
        values = source.sample_ordinals(1000, 100, policy.SEED)
        self.assertEqual(values, source.sample_ordinals(1000, 100, policy.SEED))
        self.assertEqual(len(set(values)), 100); self.assertNotEqual(values, list(range(1, 101)))
        with self.assertRaises(ValueError): source.sample_ordinals(3, 4)

    def test_exact_index_sequence_and_selected_source_bytes_are_preserved(self):
        raw = b"1\tC\n2\tCC\n3\tCCC\n"
        def cid(value):
            return {"decimal_digits": 1, "decimal_prefix": value, "complete_decimal": value,
                    "decimal_sha256": hashlib.sha256(value.encode()).hexdigest()}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "source_000000.tsv"; path.write_bytes(raw)
            part = {"index": 0, "first_ordinal": 1, "last_ordinal": 3, "records": 3, "bytes": len(raw),
                "first_cid": cid("1"), "last_cid": cid("3"), "reference": files.file_pin(path)}
            source.validate_entry(part, root=folder, index=0, first_ordinal=1)
            result = source.scan_part(part, [2], extract=True)
            self.assertEqual(result["extracted"][0]["source_smiles"], "CC")
            self.assertEqual(result["longest"][0]["ordinal"], 3)
            with self.assertRaises(ValueError): source.validate_entry(part, root=folder, index=1, first_ordinal=1)

    def test_legacy_parse_unknown_stays_technical_and_known_X_stays_chemical(self):
        original = {"ordinal": 2, "cid_source_ascii": "2", "source_smiles": "synthetic"}
        rejected = {"cid": 2, "ordinal": 2, "reasons": ["X03"]}
        all_flags = {name: name == "X03" for name in ("X01", "X02", "X03", "X04", "X05")}
        self.assertEqual(funnel(rejected, all_flags, True, {}, original)[0], "chemReject")
        rejected["reasons"] = ["PARSE_FAILED"]
        self.assertEqual(funnel(rejected, {"PARSE_FAILED": True}, False, {}, original)[0], "technicalUnresolved")
        rejected["reasons"] = ["X03"]
        self.assertEqual(funnel(rejected, {"X03": False}, True, {}, original)[0], "technicalUnresolved")

    def test_slow_valid_memory_is_not_high_memory_and_invalid_values_still_fail(self):
        value = {"own_current_tree_rss_bytes": 1024, "available_bytes": 900, "total_bytes": 1000}
        self.assertIsNone(runtime.memory_decision(value, 3.5))
        self.assertIsNotNone(runtime.memory_decision(dict(value, available_bytes=100), .1))
        with self.assertRaises(ValueError): runtime.memory_decision(dict(value, available_bytes=-1), .1)

    def test_physical_parquet_keeps_full_feature_payload_and_nullable_parse_flags(self):
        import pyarrow as pa
        import pyarrow.parquet as pq
        value = {"input": {"ordinal": 1, "cid_source_ascii": "1", "source_smiles": "synthetic",
            "source_smiles_sha256": "a" * 64, "source_part": {}}, "legacy_dispatcher_result": {"reasons": ["PARSE_FAILED"]},
            "category": "technicalUnresolved", "audit_parse_succeeded": False, "audit_flags": {"PARSE_FAILED": True},
            "technical_codes": ["legacy"], "errors": {}, "worker_pid": 1, "audit_wall_seconds": .1,
            "audit_CPU_seconds": .1, "dispatcher_wall_seconds_includes_legacy_X_parse": .2,
            "dispatcher_CPU_seconds_includes_legacy_X_parse": .2}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "synthetic.parquet"
            pq.write_table(pa.Table.from_pylist([parquet_row(value, "synthetic")], schema=output_schema()), path)
            saved = pq.read_table(path).to_pylist()[0]
            self.assertIsNone(saved["audit_X01"])
            self.assertEqual(json.loads(saved["full_dispatcher_result_json"]), value["legacy_dispatcher_result"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True); parser.add_argument("--root-preflight", type=Path, required=True)
    args = parser.parse_args()
    plan, proof, inventory = runtime.startup(args.plan, args.root_preflight)
    out = files.fresh_output(plan["output_root"])
    context = multiprocessing.get_context("spawn"); stop = context.Event()
    budget = runtime.RuntimeBudget(out, plan, proof, stop)
    started, phase_seconds = time.monotonic(), {}
    try:
        with budget:
            suite = unittest.defaultTestLoader.loadTestsFromTestCase(RawUniformBoundaries)
            shared.need(suite.countTestCases() == 5, "EXACT_FIVE_SMALL_SYNTHETIC_FIXTURES_REQUIRED")
            result = unittest.TextTestRunner(verbosity=2).run(suite)
            tests = {"tests_run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors), "skips": len(result.skipped)}
            shared.write_new(out / "synthetic_fixtures.json", tests)
            shared.need(result.wasSuccessful() and result.testsRun == 5 and not result.skipped, "FIXTURES_BEFORE_REAL_SOURCE_IO")
            budget.check()
            source.STOP = stop
            began, cpu = time.monotonic(), time.process_time()
            raw_frame = files.frame(plan["raw_file"]["path"])
            shared.need(files.portable(raw_frame) == files.portable(inventory["raw_current_frame"]), "ACTUAL1093_RAW_FRAME_CHANGED")
            files.file_pin(plan["raw_file"]["path"], expected=plan["raw_file"], expected_frame=raw_frame, stop=stop)
            budget.check()
            parts, uniform, index_frame = index_and_selection(plan, inventory)
            phase_seconds["raw_and_index_hash_and_selection"] = {"wall": time.monotonic() - began, "CPU": time.process_time() - cpu}
            shared.write_new(out / "uniform_ordinals.json", {"seed": policy.SEED, "population_N": plan["population_N"], "ordinals": uniform})
            uniform_set = set(uniform)
            tasks = ((p["index"], (p, [n for n in uniform if p["first_ordinal"] <= n <= p["last_ordinal"]], False, None)) for p in parts)
            with ProcessPoolExecutor(max_workers=16, mp_context=context, initializer=initialize,
                    initargs=(stop, context.Barrier(16), False)) as pool:
                began = time.monotonic()
                preflight = source_phase(pool, tasks, out, "all500_preflight", stop, budget)
                phase_seconds["all500_preflight_wall"] = time.monotonic() - began
                shared.need(len(preflight) == 500 and len({r["worker_pid"] for r in preflight}) == 16 and
                    sum(r["rows"] for r in preflight) == plan["population_N"] and
                    sum(r["bytes"] for r in preflight) == inventory["counts"]["uncompressed_bytes"] and
                    max(r["maximum_source_line_bytes"] for r in preflight) == inventory["counts"]["maximum_source_line_bytes"],
                    "CURRENT_ALL500_HASH_ROW_BYTE_MAXLINE_CONSERVATION")
                longest_heap = []
                facts = {r["ordinal"]: r for part in preflight for r in part["selected_facts"]}
                for part in preflight:
                    for row in part["longest"]: source.push_longest(longest_heap, row)
                longest = source.sorted_longest(longest_heap)
                facts.update({r["ordinal"]: r for r in longest})
                selected = uniform_set | {r["ordinal"] for r in longest}
                shared.need(len(longest) == 16 and set(facts) == selected and sum(r["source_row_bytes"] for r in facts.values()) * 8 <=
                    policy.CONTAINER_CAP, "SELECTED_SOURCE_CONTAINER_STOP_NOT_A_CHEMICAL_RULE")
                shared.write_new(out / "longest16_ordinals.json", {"facts": longest, "overlap_uniform_ordinals": sorted(uniform_set & {r["ordinal"] for r in longest}),
                    "source_byte_budget_is_not_RDKit_heap_proof": True})
                frames = {r["index"]: r["frame"] for r in preflight}
                extraction = ((p["index"], (p, [n for n in selected if p["first_ordinal"] <= n <= p["last_ordinal"]], True, frames[p["index"]]))
                    for p in parts if any(p["first_ordinal"] <= n <= p["last_ordinal"] for n in selected))
                began = time.monotonic()
                extracted = source_phase(pool, extraction, out, "selected_extraction", stop, budget)
                phase_seconds["selected_extraction_wall"] = time.monotonic() - began
            rows = [row for part in extracted for row in part["extracted"]]
            by_ordinal = {r["ordinal"]: r for r in rows}
            shared.need(len(rows) == len(by_ordinal) == len(selected) and set(by_ordinal) == selected and
                sum(len(json.dumps(r, ensure_ascii=False).encode()) for r in rows) <= policy.CONTAINER_CAP,
                "EXACT_SELECTED_INPUT_AND_IPC_CONTAINER_CONSERVATION")
            with ProcessPoolExecutor(max_workers=16, mp_context=context, initializer=initialize,
                    initargs=(stop, context.Barrier(16), True)) as pool:
                uniform_result = chemical_group(pool, [by_ordinal[n] for n in uniform], "uniform10000", out, stop, budget)
                longest_result = chemical_group(pool, [by_ordinal[r["ordinal"]] for r in longest], "longest16", out, stop, budget)
            for part in preflight:
                shared.need(files.frame(part["reference"]["path"]) == part["frame"], "PART_FRAME_CHANGED_BEFORE_COMPLETION")
            shared.need(files.frame(plan["raw_file"]["path"]) == raw_frame and files.frame(plan["source_index"]["path"]) == index_frame,
                "RAW_OR_INDEX_CHANGED_DURING_PROFILE")
            budget.check(force=True)
            receipt = {"schema": "PUBCHEM_RAW_UNIFORM_COST_RECEIPT_V1", "status": "RAW_UNIFORM_COST_PROFILE_COMPLETE_NOT_SCREEN_ACCEPTANCE",
                "job_id": proof["job_id"], "node": proof["request"]["node"], "uid": os.getuid(), "plan": shared.pin(args.plan),
                "startup_proof": shared.pin(args.root_preflight), "rdkit": "2025.09.5", "population_N": plan["population_N"],
                "seed": policy.SEED, "uniform": uniform_result, "longest_diagnostic": longest_result,
                "source_phase_seconds": phase_seconds, "raw_and_parts_SHA_currently_verified": True,
                "source_phase_receipts": {name: shared.pin(out / (name + ".receipt.json"))
                    for name in ("all500_preflight", "selected_extraction")},
                "independent_audit_not_subtracted_from_total_production_cost": True,
                "dispatcher_already_includes_legacy_parse_X": True, "longest_is_warm_pool_and_not_in_uniform_mean": True,
                "uniform_phase_wall_includes_worker_pool_initialization": True,
                "actual_inventory_parent": plan["inventory_actual_parent"], "inventory_parent_is_source_stage_measurement_not_chemical_forecast": True,
                "source_scope_proof": policy.verify_compatible_source(plan), "anchors": plan["anchors"],
                "cost_decision_reference": plan["cost_decision_reference"], "cost_action": "REPORT_AND_CONTINUE",
                "synthetic_fixtures": tests, "runtime_budget": budget.receipt(), "wall_seconds": time.monotonic() - started,
                "guide_filtered_deduplicated_1M_reference": False, "full_space_feature_recovery_claimed": False,
                "old_pool_modified": False, "decontamination_novelty_UFF_QM_training_performed": False,
                "full_source_screening_or_pool_release_authorized": False, "actual_parent_allocation_cost_pending_accounting": True}
        receipt["runtime_budget"] = budget.receipt()
        receipt["wall_seconds"] = time.monotonic() - started
        receipt["actual_owned_output_bytes_before_final_receipt"] = files.owned_bytes(out)
        shared.write_new(out / "receipt.json", receipt)
    except BaseException as exc:
        stop.set()
        shared.write_new(out / "failure.json", {"status": "RAW_UNIFORM_PROFILE_FAILED_PARTIALS_PRESERVED", "type": type(exc).__name__,
            "error": str(exc), "traceback": traceback.format_exc(), "runtime_budget": budget.receipt(),
            "forced_signals_sent": False, "pool_release_authorized": False})
        raise


if __name__ == "__main__":
    main()
