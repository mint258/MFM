"""Paired first10000-row feature evaluation; NOT_READY without a separate scope.

Never updates the historical pool or releases a proposed pool. This file does
not create requests/scopes or submit. The three-CID scope is explicitly denied.
"""
from __future__ import annotations

import argparse
from collections import Counter, deque
from concurrent.futures import ProcessPoolExecutor
import hashlib
from functools import lru_cache
import json
import multiprocessing
import os
from pathlib import Path
import sqlite3
import stat
import time
import traceback

from . import common, features_legacy_compatible_v2 as candidate, screen
from . import bounded_prefix_gate_v2 as full_gate
from .common import ARTIFACT_ROOT, check_quota, dump_new, require
from workflows.data_v1_final.execution.cpu_prefix_replay_v1 import policy, runtime_v2 as runtime


SCHEMA = "pubchem_paired_prefix_candidate_plan_v1"
# This constant is not an approval or a new central policy entry. Root must
# separately review/add this precise scope before any READY plan can run.
FUTURE_SCOPE = "prefix_feature_paired_10000"
PARAMETERS = {"prefix_start_ordinal": 1, "input_prefix_limit": 10000,
              "legacy_success_cids": 8198, "legacy_unique_full_keys": 8197,
              "legacy_rejections": 1802, "legacy_feature_errors": 753,
              "repair_or_pool_release": False}
FORBIDDEN = ("repair_applied", "pool_modified", "released_candidate_pool_authorized",
             "decontamination_acceptance_authorized", "uff_or_D_family_export_authorized",
             "training_authorized", "full_source_screening_authorized")
SMALL_KEYS = ("original_prefix_receipt", "original_prefix_plan", "original_rejections", "raw_receipt",
              "candidate_three_cid_receipt", "candidate_three_cid_monitor", "prior_four_test_stage_receipt",
              "prior_four_test_stdout", "prior_four_test_intent", "prior_four_test_monitor", "quota_publisher_source")


def validate_ready(plan):
    require(plan.get("schema") == SCHEMA and plan.get("status") == "READY" and
            isinstance(plan.get("independent_scope_policy_reference"), dict),
            "NOT_READY: independent Root-reviewed 10000-row CPU scope and READY bindings required")
    require(plan.get("scope_key") == FUTURE_SCOPE and plan.get("scope_parameters") == PARAMETERS,
            "The existing three-CID scope never authorizes a10000-row replay")
    require(plan["workers"] == 16 and plan["max_input_rows"] == 10000 and plan["prefix_start_ordinal"] == 1 and
            all(plan[k] is False for k in FORBIDDEN), "Only proposed, unreleased first10000 evaluation allowed")
    cap = plan["peak_output_cap_bytes"]
    require(type(cap) is int and 64 * 1024 ** 2 <= cap <= 256 * 1024 ** 2, "Finite64..256MiB science output cap required")
    require(plan.get("blocking_pending_items") in (None, []), "Unresolved READY blockers")
    return cap


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def field_differences(left, right):
    """Exact JSON field/value/type comparison; True is not an integer1."""
    return {key: {"legacy_present": key in left, "candidate_present": key in right,
                  "legacy": left.get(key), "candidate": right.get(key)}
            for key in sorted(set(left) | set(right))
            if key not in left or key not in right or encoded(left[key]) != encoded(right[key])}


def _capture(function, cid, smiles, ordinal):
    phase = "FEATURE_FUNCTION"
    try:
        value = function(cid, smiles, ordinal)
        phase = "OUTPUT_JSON_FINITE_VALUES"
        encoded(value)
        return {"status": "PASS", "output": value}
    except Exception as exc:
        return {"status": "ERROR", "phase": phase, "exception_type": type(exc).__name__, "message": str(exc),
                "historical_screen_batch_error": type(exc).__name__ + ": " + str(exc)[:500],
                "frames": [{"path": frame.filename, "line": frame.lineno, "function": frame.name}
                           for frame in traceback.extract_tb(exc.__traceback__)],
                "exact_traceback": traceback.format_exc()}


def paired_one(cid, smiles, ordinal):
    runtime.checkpoint()
    # Independent feature calls each parse their own original SMILES. No failed
    # SanitizeMol input is reused by the proposed function.
    legacy = _capture(screen.features, cid, smiles, ordinal)
    runtime.checkpoint()
    proposed = _capture(candidate.features_candidate, cid, smiles, ordinal)
    runtime.checkpoint()
    flags, audit = None, None
    try:
        mol, flags = screen.chemical_flags(smiles)
        if legacy["status"] == "ERROR" and mol is not None and not any(flags.values()):
            audit = {"status": "PASS", "fragments": candidate.evaluate_fragment_orders(mol)}
    except Exception as exc:
        audit = {"status": "ERROR", "exception_type": type(exc).__name__, "message": str(exc),
                 "exact_traceback": traceback.format_exc()}
    return {"cid": cid, "ordinal": ordinal, "source_smiles": smiles, "old_chemical_flags": flags,
            "legacy": legacy, "candidate": proposed, "fragment_order_audit": audit}


def _initialize(barrier):
    screen.rdkit_modules()
    runtime.checkpoint()
    barrier.wait(timeout=180)


def paired_batch(batch):
    return {"worker_pid": os.getpid(), "rows": [paired_one(*row) for row in batch]}


def ordered_results(batches):
    context = multiprocessing.get_context("spawn")
    with ProcessPoolExecutor(max_workers=16, mp_context=context, initializer=_initialize,
                             initargs=(context.Barrier(16),)) as pool:
        waiting = deque()
        for batch in batches:
            runtime.checkpoint()
            waiting.append(pool.submit(paired_batch, batch))
            if len(waiting) >= 32:
                yield waiting.popleft().result(timeout=3600)
        while waiting:
            runtime.checkpoint()
            yield waiting.popleft().result(timeout=3600)


def file_frame(path):
    value = Path(path).stat()
    require(stat.S_ISREG(value.st_mode) and not Path(path).is_symlink() and value.st_uid == 1278,
            "Task-owned literal regular data file required")
    return {"device": value.st_dev, "inode": value.st_ino, "size": value.st_size,
            "mtime_ns": value.st_mtime_ns, "uid": value.st_uid}


def hash_stable(pin, expected=None):
    path = Path(pin["path"])
    require(path.is_absolute() and ".." not in path.parts, "Literal absolute data path required")
    before = file_frame(path)
    require(before["size"] == pin["bytes"] and (expected is None or before == expected), "Data frame changed")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        opened = os.fstat(stream.fileno())
        require((opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns) ==
                tuple(before[k] for k in ("device", "inode", "size", "mtime_ns")), "Opened data identity differs")
        while True:
            runtime.checkpoint()
            block = stream.read(1 << 20)
            if not block:
                break
            digest.update(block)
        after = os.fstat(stream.fileno())
        require((opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns) ==
                (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns), "Open data changed during SHA")
    require(digest.hexdigest() == pin["sha256"] and file_frame(path) == before, "Complete current data SHA/frame differs")
    return before


def seal_output(path):
    before = file_frame(path)
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        opened = os.fstat(stream.fileno())
        require((opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns) ==
                tuple(before[k] for k in ("device", "inode", "size", "mtime_ns")), "Output open identity differs")
        for block in iter(lambda: stream.read(1 << 20), b""):
            runtime.checkpoint()
            digest.update(block)
        after = os.fstat(stream.fileno())
        require((opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns) ==
                (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns), "Output changed while sealed")
    require(file_frame(path) == before, "Output path changed while sealed")
    return {"path": str(path), "bytes": before["size"], "sha256": digest.hexdigest()}


def authorize(plan, intent_path, plan_path, cap):
    proof = runtime.root_guard(intent_path, plan_path, cap)
    request = proof["request"]
    require(request["scope_key"] == FUTURE_SCOPE and request["scope_parameters"] == PARAMETERS and
            request["scope_policy_reference"] == plan["independent_scope_policy_reference"] and
            request["cpus"] == 16 and request["wall_seconds"] <= 3600 and
            request["estimated_peak_output_bytes"] == cap + 32 * 1024 ** 2,
            "Independent central approval and whole-output budget required; no3CID scope extension")
    declared = {r["path"]: r for r in request["source_references"]}
    refs = [plan[k] for k in SMALL_KEYS] + plan["code_sources"] + [plan["independent_scope_policy_reference"]]
    for pin in refs:
        require(pin["bytes"] <= 2 * 1024 ** 2 and declared.get(pin["path"]) == pin, "Root small source pin missing")
        policy.verify(pin)
    original_plan = policy.load(plan["original_prefix_plan"]["path"])
    for pin in original_plan["full_gate_refs"].values():
        require(pin["bytes"] <= 2 * 1024 ** 2 and declared.get(pin["path"]) == pin, "Root small source pin missing")
        policy.verify(pin)
    actual = {str(Path(module.__file__).absolute()) for module in (common, screen, candidate, full_gate, runtime, policy)}
    actual.add(str(Path(__file__).absolute()))
    require(actual <= {r["path"] for r in plan["code_sources"]}, "Actual import/source chain not pinned")
    old = policy.load(plan["original_prefix_receipt"]["path"])
    raw = policy.load(plan["raw_receipt"]["path"])
    require(old["schema"] == "PUBCHEM_BOUNDED_PREFIX_PILOT_V2" and old["job_id"] == "4520427" and
            old["status"] == "BOUNDED_INPUT_PREFIX_PILOT_NOT_DECONTAMINATED" and old["node"] == "compute-0-20" and
            old["uid"] == 1278 and old["plan"] == plan["original_prefix_plan"] and
            old["input_prefix_records"] == 10000 and old["successful_cid_aliases"] == 8198 and old["unique_full_keys"] == 8197 and
            old["counts"]["first:IDENTITY_OR_FEATURE_FAILED"] == 753 and old["source_receipt"] == plan["raw_receipt"] and
            old["database"] == plan["legacy_database"] and old["all_rejections"] == plan["original_rejections"],
            "Exact original427 all8198aliases/8197stored rows/1802rejections authority required")
    require(raw["schema"] == "pubchem_download_complete_v1" and raw["job_id"] == "4520348" and
            raw["hostname"] == "compute-0-20" and raw["uid"] == 1278 and
            raw["status"] == "RAW_ACQUIRED_NO_CHEMICAL_SCREENING" and raw["file"] == plan["raw_file"] and
            raw["gzip"]["gzip_read_to_eof_crc_validated"] is True and
            raw["gzip"]["sha256"] == raw["file"]["sha256"] and len(raw["parts"]) == 16 and
            all(row["status"] == "COMPLETE" for row in raw["parts"]) and
            request["data_references"] == [plan["raw_file"], plan["legacy_database"]], "Only exact original raw and old readonlyDB")
    full_refs = original_plan["full_gate_refs"]
    full_proof = full_gate.validate_full_evidence(original_plan, policy.load(full_refs["receipt"]["path"]),
                      policy.load(full_refs["actual_closure"]["path"]), policy.load(full_refs["plan"]["path"]))
    three = policy.load(plan["candidate_three_cid_receipt"]["path"])
    monitor = policy.load(plan["candidate_three_cid_monitor"]["path"])
    require(three["job_id"] == monitor["job_id"] == "4520555" and three["status"] == "CANDIDATE_EVALUATED_NOT_APPLIED" and
            three["candidate_pass_cases"] == 3 and three["candidate_three_case_checks_passed"] is True and
            three["observed_non_ring_field_drift_cases"] == 0 and three["repair_applied"] is False and
            three["pool_modified"] is False and monitor["child_returncode"] == 0 and
            monitor["status"] == "COMPLETED_NO_MEMORY_DENIAL" and monitor["first_denial"] is None and
            monitor["durable_evidence_exported"] is True and three["root_submission"] == monitor["intent_reference"],
            "Actual completed3CID proposed-only evidence required; not a10000-row approval")
    old_test_intent = policy.load(plan["prior_four_test_intent"]["path"])
    test_stage = policy.load(plan["prior_four_test_stage_receipt"]["path"])
    test_monitor = policy.load(plan["prior_four_test_monitor"]["path"])
    test_log = policy.read_small(plan["prior_four_test_stdout"]["path"]).decode()
    require(test_monitor["job_id"] == "4520545" and test_monitor["intent_reference"] == plan["prior_four_test_intent"] and
            test_monitor["child_returncode"] == 1 and test_monitor["first_denial"] is None and
            test_monitor["durable_evidence_exported"] is True and
            test_stage["root_preflight"] == plan["prior_four_test_intent"] and
            test_stage["stages"][0]["returncode"] == 0 and
            test_stage["stages"][0]["argv"] == ["/share/home/zixiao/.conda/envs/chemprop/bin/python", "-B", "-m", "unittest",
                                               "workflows.expansion.test_feature_candidate_v1", "-v"] and
            "\nRan 4 tests in " in test_log and "\n\nOK\n" in test_log, "Actual545 test stage must remain bound")
    for module in (screen, candidate.generic_fallback_module):
        current = policy.ref(Path(module.__file__))
        require(current in old_test_intent["request"]["source_references"] and
                current in three["cpu_runtime_proof"]["request"]["source_references"], "Candidate/science changed after actual tests/3CID")
    source_proof = candidate.source_scope_proof()
    require(source_proof["status"] == "COMPOSITIONAL_OLD_SUCCESS_PASSTHROUGH_EXACT_RING_KEKULIZE_FALLBACK_V2" and
            source_proof["strategy"] == "OLD_SUCCESS_PASSTHROUGH_EXACT_OLD_RING_KEKULIZE_ONLY" and
            source_proof["nested_generic_fallback_proof"] == three["source_scope_proof"] and
            source_proof["frozen_old_ring_site"]["sanitize_line"] == 70 and
            source_proof["frozen_old_ring_site"]["traceback_code_object_identity_required"] is True and
            source_proof["wrapper_AST_equals_original_features_AST"] is False and
            source_proof["repair_applied"] is False and source_proof["pool_modified"] is False,
            "Exact compositional old-success passthrough/ring-only fallback proof changed")
    return proof, old, full_proof, source_proof


def load_rejections(pin):
    result = {}
    for line in policy.read_small(pin["path"]).decode().splitlines():
        value = json.loads(line)
        ordinal = value["ordinal"]
        require(type(ordinal) is int and 1 <= ordinal <= 10000 and ordinal not in result and value["reasons"],
                "Original rejection ordinal missing/duplicated/out of prefix")
        result[ordinal] = value
    require(len(result) == 1802 and sum(v["reasons"] == ["IDENTITY_OR_FEATURE_FAILED"] for v in result.values()) == 753,
            "Exact original1802rejections including753errors required")
    require(len({v["cid"] for v in result.values()}) == len(result), "Original rejection CID duplicated")
    return result


@lru_cache(maxsize=1)
def _legacy_ring_failure_lines():
    # The unchanged source file and actual Python traceback locate the failed
    # old SanitizeMol, rather than guessing from a KekulizeException type.
    import ast
    tree = ast.parse(policy.read_small(Path(screen.__file__)))
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "features")
    return {n.lineno for n in ast.walk(function) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and
            isinstance(n.func.value, ast.Name) and n.func.value.id == "Chem" and n.func.attr == "SanitizeMol"}


def _ring_origin_confirmed(row):
    lines = _legacy_ring_failure_lines()
    audit = row["fragment_order_audit"]
    return (any(f["path"] == str(Path(screen.__file__)) and f["function"] == "features" and f["line"] in lines
                for f in row["legacy"].get("frames", [])) and audit is not None and audit["status"] == "PASS" and
            any(f["legacy"]["status"] == "ERROR" for f in audit["fragments"]) and
            all(f["candidate"]["status"] == "PASS" and f["candidate"]["retained_heavy_atom_adjacency_equal"] is True
                for f in audit["fragments"]))


def assess(row, alias, stored, rejected):
    """Return observations/mismatches without inventing a new exclusion rule."""
    failures, comparisons = [], {}
    legacy, proposed = row["legacy"], row["candidate"]
    def check(value, name):
        if not value:
            failures.append(name)
    flags = row["old_chemical_flags"]
    reasons = [k for k, v in flags.items() if v] if isinstance(flags, dict) else None
    check((alias is None) != (rejected is None), "HISTORICAL_MEMBERSHIP_NOT_EXACTLY_ONE")
    if failures:
        return {"cohort": "HISTORICAL_PARTITION_DRIFT", "classification": "HISTORICAL_PARTITION_HAS_DRIFT",
                "mismatch_codes": failures, "comparisons": {}, "historical_full_feature_row_exists": stored is not None,
                "old_alias_has_no_separate_historical_feature_row": False}
    if alias is not None:
        cohort = "ORIGINAL_SUCCESS_ALIAS"
        check((row["cid"], row["ordinal"]) == (alias["cid"], alias["ordinal"]), "HISTORICAL_ALIAS_COORDINATE_DRIFT")
        check(reasons == [], "ORIGINAL_SUCCESS_CHEMICAL_ADMISSION_DRIFT")
        check(legacy["status"] == proposed["status"] == "PASS", "ORIGINAL_SUCCESS_NOW_ERRORS")
        if legacy["status"] == "PASS":
            check(not legacy["output"]["reasons"] and legacy["output"]["full_key"] == alias["full_key"], "HISTORICAL_ALIAS_KEY_DRIFT")
        if legacy["status"] == proposed["status"] == "PASS":
            comparisons["paired_all_fields"] = field_differences(legacy["output"], proposed["output"])
            check(not comparisons["paired_all_fields"], "OLD_PASS_FEATURE_FIELD_DRIFT")
        if stored is not None and legacy["status"] == "PASS":
            comparisons["historical_stored_all_fields"] = field_differences(stored, legacy["output"])
            check(not comparisons["historical_stored_all_fields"], "HISTORICAL_STORED_FEATURE_FIELD_DRIFT")
        classification = "OLD_PASS_ALL_FIELDS_PRESERVED" if not failures else "OLD_PASS_HAS_DRIFT"
    else:
        cohort = "ORIGINAL_FEATURE_ERROR" if rejected["reasons"] == ["IDENTITY_OR_FEATURE_FAILED"] else "ORIGINAL_CHEMICAL_REJECTION"
        check((row["cid"], row["ordinal"]) == (rejected["cid"], rejected["ordinal"]), "HISTORICAL_REJECTION_COORDINATE_DRIFT")
        if cohort == "ORIGINAL_CHEMICAL_REJECTION":
            check(reasons == rejected["reasons"], "ORIGINAL_CHEMICAL_FLAGS_OR_REASON_ORDER_DRIFT")
            for name, observed in (("LEGACY", legacy), ("CANDIDATE", proposed)):
                check(observed["status"] == "PASS" and observed["output"] == rejected, name + "_CHEMICAL_REJECTION_DRIFT")
            classification = "CHEMICAL_REJECTION_UNCHANGED" if not failures else "CHEMICAL_REJECTION_HAS_DRIFT"
        else:
            check(reasons == [], "ORIGINAL_FEATURE_ERROR_CHEMICAL_ADMISSION_DRIFT")
            check(legacy["status"] == "ERROR" and legacy.get("historical_screen_batch_error") == rejected.get("error"),
                  "ORIGINAL_FEATURE_ERROR_NOT_EXACTLY_REPRODUCED")
            if failures:
                classification = "ORIGINAL_ERROR_HAS_REPLAY_DRIFT"
            elif proposed["status"] == "ERROR":
                classification = "STILL_FAILING_PROPOSED_FEATURES"
            elif proposed["output"].get("reasons"):
                classification = "PROPOSED_NEW_EXCLUSION_NOT_ALLOWED"
                failures.append("PROPOSED_CHANGED_CHEMICAL_REASON")
            elif _ring_origin_confirmed(row):
                classification = "RECOVERED_CONFIRMED_GENERIC_RING_ORDER"
            else:
                classification = "RECOVERED_ORIGIN_NOT_CONFIRMED"
                failures.append("RECOVERY_NOT_LOCALIZED_TO_OLD_GENERIC_RING_STEP")
    return {"cohort": cohort, "classification": classification, "mismatch_codes": failures,
            "comparisons": comparisons, "historical_full_feature_row_exists": stored is not None,
            "old_alias_has_no_separate_historical_feature_row": alias is not None and stored is None}


def create_output_database(path, cap):
    db = sqlite3.connect(path)
    db.execute("PRAGMA page_size=4096")
    # This is a new disposable diagnostic DB, never a historical pool. OFF
    # avoids a second DB-sized rollback file. Failure is retained, never resumed;
    # success requires normal close plus integrity_check and a complete SHA.
    db.execute("PRAGMA journal_mode=OFF")
    db.execute("PRAGMA synchronous=FULL")
    db.execute("PRAGMA temp_store=MEMORY")
    db.execute("PRAGMA cache_size=-2048")
    db.execute("PRAGMA max_page_count=" + str((cap - 8 * 1024 ** 2) // 4096))
    db.execute("CREATE TABLE paired_cases(ordinal INTEGER PRIMARY KEY,cid INTEGER UNIQUE,cohort TEXT,classification TEXT,proof TEXT,pair TEXT)")
    db.execute("CREATE TABLE feature_failure_cases(ordinal INTEGER PRIMARY KEY,cid INTEGER UNIQUE,classification TEXT,details TEXT)")
    db.execute("CREATE TABLE mismatches(ordinal INTEGER PRIMARY KEY,cid INTEGER,details TEXT)")
    db.execute("CREATE TABLE proposed_candidates(full_key TEXT PRIMARY KEY,cid INTEGER UNIQUE,features TEXT)")
    db.execute("CREATE TABLE proposed_aliases(cid INTEGER PRIMARY KEY,full_key TEXT,ordinal INTEGER UNIQUE)")
    return db


def run(plan_path, intent_path):
    plan = policy.load(plan_path)
    cap = validate_ready(plan)  # NOT_READY is rejected before intent/guard/data I/O.
    proof, old, full_proof, source_proof = authorize(plan, intent_path, plan_path, cap)
    out = Path(plan["output_root"])
    require(out.is_absolute() and out.is_relative_to(ARTIFACT_ROOT / "diagnostics") and not out.exists() and
            not out.is_symlink(), "Use a new isolated diagnostic directory; never modify427 pool")
    out.mkdir(parents=True)
    began = time.monotonic()
    counts, workers, seen_cids, seen_stored = Counter(), Counter(), set(), set()
    rejected = load_rejections(plan["original_rejections"])
    historical_db = result_db = None
    try:
        def quota(name):
            feed = Path(plan["quota_feed"])
            require(feed.is_file() and not feed.is_symlink() and feed.stat().st_uid == 1278, "Task-owned livequota feed")
            dump_new(out / name, policy.load(feed))
            check_quota(out / name, proof["request"]["estimated_peak_output_bytes"])
        quota("quota_start.json")
        raw_frame = hash_stable(plan["raw_file"])
        old_raw = old["data_authority"]["files"][0]
        require(old_raw["reference"] == plan["raw_file"] and old_raw["producer_job_id"] == "4520348" and
                all(raw_frame[k] == old_raw["expected_stat"][k] for k in ("inode", "size", "mtime_ns", "uid")),
                "Only st_dev may differ across producer/CPU nodes")
        db_frame = hash_stable(plan["legacy_database"])
        old_path = Path(plan["legacy_database"]["path"])
        require(not Path(str(old_path) + "-wal").exists() and not Path(str(old_path) + "-journal").exists(), "HistoricalDB has sidecar state")
        historical_db = sqlite3.connect(old_path.as_uri() + "?mode=ro&immutable=1", uri=True)
        historical_db.execute("PRAGMA query_only=ON")
        require(historical_db.execute("SELECT count(*) FROM candidates").fetchone()[0] == 8197 and
                historical_db.execute("SELECT count(*) FROM aliases").fetchone()[0] == 8198, "HistoricalDB count differs")
        quota("quota_after_source_hashes.json")
        result_path = out / "paired_prefix_evaluation.sqlite"
        result_db = create_output_database(result_path, cap)
        for batch in ordered_results(screen.cid_batches(plan["raw_file"]["path"], max_rows=10000, batch_size=64)):
            workers[batch["worker_pid"]] += len(batch["rows"])
            for row in batch["rows"]:
                runtime.checkpoint()
                counts["input_records"] += 1
                require(row["ordinal"] == counts["input_records"] and row["cid"] not in seen_cids, "Input CID/ordinal missing/duplicated/reordered")
                seen_cids.add(row["cid"])
                found = historical_db.execute("SELECT cid,full_key,source_ordinal FROM aliases WHERE cid=?", (row["cid"],)).fetchone()
                alias = dict(zip(("cid", "full_key", "ordinal"), found)) if found else None
                stored_row = historical_db.execute("SELECT full_key,features FROM candidates WHERE cid=?", (row["cid"],)).fetchone()
                stored = json.loads(stored_row[1]) if stored_row else None
                if stored_row:
                    seen_stored.add(stored_row[0])
                result = assess(row, alias, stored, rejected.get(row["ordinal"]))
                counts[result["cohort"]] += 1
                counts["classification:" + result["classification"]] += 1
                if alias:
                    counts["legacy_aliases_checked"] += 1
                    counts["legacy_alias_without_separate_stored_features"] += int(stored is None)
                if stored is not None:
                    counts["historical_stored_rows_checked"] += 1
                if result["mismatch_codes"]:
                    counts["records_with_mismatch"] += 1
                    result_db.execute("INSERT INTO mismatches VALUES(?,?,?)", (row["ordinal"], row["cid"], encoded(result)))
                result_db.execute("INSERT INTO paired_cases VALUES(?,?,?,?,?,?)", (row["ordinal"], row["cid"], result["cohort"],
                                  result["classification"], encoded(result), encoded(row)))
                if result["cohort"] == "ORIGINAL_FEATURE_ERROR":
                    result_db.execute("INSERT INTO feature_failure_cases VALUES(?,?,?,?)", (row["ordinal"], row["cid"],
                                      result["classification"], encoded({"historical": rejected[row["ordinal"]], "pair": row, "proof": result})))
                proposed = row["candidate"]
                if proposed["status"] == "PASS" and not proposed["output"]["reasons"]:
                    value = proposed["output"]
                    result_db.execute("INSERT INTO proposed_aliases VALUES(?,?,?)", (value["cid"], value["full_key"], value["ordinal"]))
                    previous = result_db.execute("SELECT cid FROM proposed_candidates WHERE full_key=?", (value["full_key"],)).fetchone()
                    if previous is None or value["cid"] < previous[0]:
                        result_db.execute("INSERT OR REPLACE INTO proposed_candidates VALUES(?,?,?)", (value["full_key"], value["cid"], encoded(value)))
            result_db.commit()
            require(sum(p.stat().st_size for p in out.iterdir() if p.is_file()) <= cap - 4 * 1024 ** 2, "Finite output budget reached")
        coverage = (counts["input_records"] == len(seen_cids) == 10000 and len(workers) == 16 and
                    all(v > 0 for v in workers.values()) and sum(workers.values()) == 10000 and
                    counts["ORIGINAL_SUCCESS_ALIAS"] == counts["legacy_aliases_checked"] == 8198 and
                    counts["historical_stored_rows_checked"] == len(seen_stored) == 8197 and
                    counts["legacy_alias_without_separate_stored_features"] == 1 and
                    counts["ORIGINAL_FEATURE_ERROR"] == 753 and counts["ORIGINAL_CHEMICAL_REJECTION"] == 1049 and
                    result_db.execute("SELECT count(*) FROM feature_failure_cases").fetchone()[0] == 753)
        proposed_counts = {"aliases": result_db.execute("SELECT count(*) FROM proposed_aliases").fetchone()[0],
                           "unique_full_keys": result_db.execute("SELECT count(*) FROM proposed_candidates").fetchone()[0]}
        require(result_db.execute("PRAGMA integrity_check").fetchall() == [("ok",)], "New diagnosticDB integrity differs")
        result_db.close(); result_db = None
        historical_db.close(); historical_db = None
        require(file_frame(plan["raw_file"]["path"]) == raw_frame and file_frame(plan["legacy_database"]["path"]) == db_frame,
                "Original input changed while replayed")
        require(cap - sum(p.stat().st_size for p in out.iterdir() if p.is_file()) >= 4 * 1024 ** 2, "Receipt reserve exhausted")
        result_ref = seal_output(result_path)
        complete_recovery = counts["classification:RECOVERED_CONFIRMED_GENERIC_RING_ORDER"] == 753
        passed = coverage and counts["records_with_mismatch"] == 0 and complete_recovery
        receipt = {"schema": "pubchem_paired_prefix_candidate_receipt_v1",
                   "status": "PAIRED_PREFIX_CANDIDATE_EVALUATED_NOT_APPLIED" if passed else "PAIRED_PREFIX_HAS_DRIFT_OR_UNRESOLVED_ERRORS_NOT_APPLIED",
                   "job_id": os.environ["SLURM_JOB_ID"], "node": proof["request"]["node"], "uid": os.getuid(),
                   "plan": policy.ref(plan_path), "root_submission": policy.ref(intent_path), "counts": dict(counts),
                   "complete_input_and_historical_coverage": coverage, "all753_confirmed_recovered": complete_recovery,
                   "actual_worker_records": dict(workers), "full_X_proof": full_proof, "source_scope_proof": source_proof,
                   "legacy_success_aliases": 8198, "legacy_historical_full_feature_rows": 8197,
                   "historical_duplicate_alias_full_features_were_not_stored": True,
                   "historical_feature_fields_inferred_from_old_trace": False, "paired_result_database": result_ref,
                   "tables_with_all_records": ["paired_cases", "feature_failure_cases", "mismatches"],
                   "proposed_unreleased_feature_counts": proposed_counts, "inputs_unchanged": True,
                   "raw_current_full_SHA_and_frame": {"reference": plan["raw_file"], "frame": raw_frame},
                   "oldDB_current_full_SHA_and_frame": {"reference": plan["legacy_database"], "frame": db_frame},
                   "original_rejections": plan["original_rejections"], "candidate_three_case_evidence": plan["candidate_three_cid_receipt"],
                   "rdkit": screen.RDKIT, "heavy_atom_upper_bound": None, "isotope_policy": "preserve",
                   "common_scope_pending": True, "complete_source": False, "candidate_evaluated_only": True,
                   "wall_seconds": time.monotonic() - began, **{key: False for key in FORBIDDEN}}
        dump_new(out / "receipt.json", receipt)
        require(sum(p.stat().st_size for p in out.iterdir() if p.is_file()) <= cap, "Final output exceeds cap")
        require(passed, "Pairing drift or unresolved failures retained; no repair/pool release")
    except Exception as exc:
        dump_new(out / "failure.json", {"status": "FAILED_PAIRED_PREFIX_NOT_APPLIED", "type": type(exc).__name__,
                                      "error": str(exc), "counts_so_far": dict(counts), "repair_applied": False,
                                      "pool_modified": False, "forced_signals_sent": False})
        raise
    finally:
        if historical_db is not None:
            historical_db.close()
        if result_db is not None:
            result_db.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--root-submit-intent", type=Path, required=True)
    args = parser.parse_args()
    run(args.plan, args.root_submit_intent)


if __name__ == "__main__":
    main()
