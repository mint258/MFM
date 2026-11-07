"""Read seven existing EA cases and their canonical context; never run QM or mask."""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import importlib.util
import json
import math
import multiprocessing
import os
from pathlib import Path
import re
import resource
import sqlite3
import sys
import time
from urllib.parse import quote

from workflows.data_v1_final.labels.streaming_cpu_v2.support import checkpoint, checkpoint_iter

STATE = {}
IDENTITY = ("record_id", "molecule_id", "attempt_id", "job_id", "task_id")
META = [*IDENTITY, "lane", "calc_type", "total_atoms", "status", "source_status",
        "failure_code", "software_version_id", "converged", "scf_iterations",
        "input_bundle_sha256", "input_file_sha256", "raw_audit_selected",
        "raw_output_locator_json", "registry_source_evidence_json",
        "precision_by_field_json", "numeric_issues", "reproduction_package_sha256"]


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in checkpoint_iter(iter(lambda: stream.read(1 << 20), b"")):
            h.update(block)
    return h.hexdigest()


def checked(pin, content=True):
    path = Path(pin["path"])
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise ValueError("INPUT_NOT_ABSOLUTE_REGULAR_FILE:" + str(path))
    s = path.stat()
    if s.st_uid != os.getuid() or s.st_size != pin["bytes"]:
        raise ValueError("INPUT_OWNER_OR_SIZE_DIFFERS:" + str(path))
    if content and sha(path) != pin["sha256"]:
        raise ValueError("INPUT_SHA_DIFFERS:" + str(path))
    return path


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def identity(path):
    s = Path(path).stat()
    return [s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns]


def module(pin, name):
    spec = importlib.util.spec_from_file_location(name, checked(pin))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def initialize(cfg, candidates, barrier):
    checkpoint()
    import pyarrow as pa
    pa.set_cpu_count(1)
    pa.set_io_thread_count(1)
    STATE.update(cfg=cfg, candidates=candidates, barrier=barrier)


def project(partition):
    checkpoint()
    import pyarrow as pa
    import pyarrow.parquet as pq
    STATE["barrier"].wait(timeout=180)
    cfg = STATE["cfg"]
    selected = []
    observations = []
    for pin, row_group in checkpoint_iter(partition):
        path = checked(pin, content=False)
        before = identity(path)
        source = pq.ParquetFile(path)
        # Select actual physical scalar/charge leaves, never the complete CELL.
        leaves = [source.schema.column(i).path for i in range(len(source.schema))]
        numeric = [p for p in leaves if p.startswith("values.") and
                   (p.endswith(".registry_id") or p.endswith(".kind") or
                    p.endswith(".f64") or ".array_f64." in p)]
        if not any(p.endswith(".f64") for p in numeric):
            raise ValueError("NO_TYPED_F64_CELL_LEAF")
        columns = META + numeric
        count = matches = 0
        for batch in checkpoint_iter(source.iter_batches(row_groups=[row_group], batch_size=cfg["source_batch_records"],
                                         columns=columns, use_threads=False)):
            count += len(batch)
            ids = batch.column(batch.schema.get_field_index("record_id")).to_pylist()
            keep = [rid in STATE["candidates"] for rid in ids]
            if any(keep):
                for row in batch.filter(pa.array(keep)).to_pylist():
                    expected = STATE["candidates"][row["record_id"]]
                    if any(str(row[k]) != str(expected[k]) for k in IDENTITY):
                        continue  # Historical owner has no canonical authority.
                    if int(row["lane"]) != int(expected["lane"]):
                        raise ValueError("CANONICAL_LANE_DIFFERS")
                    if row["calc_type"] != pin["family"]:
                        raise ValueError("CANONICAL_FAMILY_DIFFERS")
                    for cell in row.get("values") or []:
                        if cell.get("kind") == 1 and cell.get("f64") is not None and not math.isfinite(cell["f64"]):
                            raise ValueError("NONFINITE_SELECTED_SCALAR_REQUIRES_EXPLICIT_DIAGNOSIS")
                    row["source_reference"] = pin
                    row["source_row_group"] = row_group
                    selected.append(row)
                    matches += 1
            if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024 > cfg["worker_rss_stop_bytes"]:
                raise RuntimeError("EA_DIAGNOSTIC_WORKER_RSS_LIMIT")
        if identity(path) != before:
            raise ValueError("SOURCE_IDENTITY_CHANGED")
        observations.append({"reference": pin, "row_group": row_group, "records_projected": count,
                             "canonical_case_matches": matches, "before_after_identity": before,
                             "content_sha256_inherited_not_rehashed": True})
    report = {"pid": os.getpid(), "rows": selected, "observations": observations,
              "maxrss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024}
    if len(json.dumps(report, allow_nan=False).encode()) > cfg["worker_report_cap_bytes"]:
        raise RuntimeError("EA_DIAGNOSTIC_SELECTED_REPORT_TOO_LARGE")
    return report


def latest_owners(cfg):
    checkpoint()
    import pyarrow.parquet as pq
    pin = cfg["latest_molecules"]
    path = checked(pin)
    before = identity(path)
    wanted = {r["molecule_id"] for r in cfg["cases"]}
    result = {}
    columns = ["molecule_id", "attempt_id", "job_id", "task_id", "lane", "state",
               "receipt_context_consistent", "export_published"]
    for batch in checkpoint_iter(pq.ParquetFile(path).iter_batches(batch_size=4096, columns=columns, use_threads=False)):
        for row in batch.to_pylist():
            if row["molecule_id"] not in wanted:
                continue
            if row["molecule_id"] in result or row["state"] != "COMPLETE" or row["receipt_context_consistent"] is not True or row["export_published"] is not True:
                raise ValueError("LATEST_COMPLETE_OWNER_NOT_UNIQUE_OR_CLOSED")
            result[row["molecule_id"]] = row
    if identity(path) != before or set(result) != wanted:
        raise ValueError("LATEST_OWNER_METADATA_IDENTITY_OR_CASE_COVERAGE_DIFFERS")
    cases = {}
    for old in cfg["cases"]:
        current = result[old["molecule_id"]]
        if any(str(current[k]) != str(old[k]) for k in ("attempt_id", "job_id", "task_id")):
            raise ValueError("KNOWN_CASE_OWNER_CHANGED_REBIND_REQUIRED:" + old["record_id"])
        if old.get("lane") is not None and old["lane"] != current["lane"]:
            raise ValueError("KNOWN_CASE_LANE_CHANGED")
        cases[old["record_id"]] = {**old, "lane": current["lane"], "canonical_owner": current}
    return cases


def raw_context(cfg, cases, rows, output, support):
    """PK metadata lookups first; decode only completed canonical retained calls."""
    checkpoint()
    checked(cfg["archive_reader_v4"])
    sys.path.insert(0, str(Path(cfg["archive_reader_v4"]["path"]).parent))
    try:
        archive = module(cfg["archive_reader_v5"], "_ea_frozen_archive_v5")
    finally:
        sys.path.pop(0)
    if Path(archive.A.__file__).absolute() != Path(cfg["archive_reader_v4"]["path"]).absolute():
        raise ValueError("FROZEN_ARCHIVE_IMPORT_PATH_COLLISION")
    checked(cfg["dictionary_manifest"])
    scf = module(cfg["scf_metadata"], "_ea_frozen_scf_metadata")
    legacy_pin = next(p for p in cfg["metadata_sources"] if p["path"].endswith("/wp4_parsers.py"))
    parser = module(legacy_pin, "_ea_frozen_legacy_scalars")
    answer = []
    consumed = 0
    for pin in checkpoint_iter(cfg["archives"]):
        path = checked(pin, content=False)
        before = identity(path)
        db = sqlite3.connect("file:" + quote(str(path)) + "?mode=ro", uri=True)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA query_only=ON")
        db.execute("PRAGMA cache_size=-8192")
        try:
            for case in checkpoint_iter(cases.values()):
                if str(case["job_id"]) != str(pin["job_id"]):
                    continue
                receipt = db.execute("SELECT receipt_json FROM completion_receipts WHERE molecule_id=?", (case["molecule_id"],)).fetchone()
                complete = json.loads(receipt[0]) if receipt else None
                context = complete.get("context", {}) if complete else {}
                if not complete or any(str(context.get(k)) != str(case[k]) for k in ("attempt_id", "job_id", "task_id", "lane")):
                    raise ValueError("ARCHIVE_COMPLETION_CONTEXT_NOT_CANONICAL")
                execution = complete.get("execution_id") or context.get("execution_id")
                if not execution:
                    raise ValueError("ARCHIVE_COMPLETION_EXECUTION_MISSING")
                for task in checkpoint_iter(("xtb_vipea", "xtb_singlepoint")):
                    entries = db.execute("SELECT execution_id,molecule_id,scope_status,source_status,retention_reason,raw_bytes,metadata_bytes,input_bundle_sha256 FROM records WHERE record_id=? AND calc_type=? LIMIT 5", (case["record_id"], task)).fetchall()
                    if len(entries) >= 5:
                        raise ValueError("UNEXPECTED_MANY_HISTORICAL_RAW_CALLS_STOP")
                    observed = [dict(r) for r in entries]
                    canonical = [r for r in observed if r["execution_id"] == execution]
                    item = {"record_id": case["record_id"], "task": task, "archive_reference": pin,
                            "canonical_execution_id": execution, "retained_metadata_rows": observed,
                            "canonical_output_found": bool(canonical), "body_read": False}
                    if canonical:
                        r = canonical[0]
                        raw_size = r["raw_bytes"] + r["metadata_bytes"]
                        if raw_size > cfg["raw_call_cap_bytes"] or consumed + raw_size > cfg["raw_total_cap_bytes"]:
                            raise RuntimeError("RAW_BODY_BUDGET_EXCEEDED_NO_PARTIAL_CAUSAL_CLAIM")
                        checkpoint()
                        reader = archive.ArchiveReader(path, cfg["dictionary_manifest"]["path"])
                        try:
                            actual = reader.get(case["record_id"], task, execution)
                        finally:
                            reader.close()
                        formal = rows[(case["record_id"], task)]
                        if actual["molecule_id"] != case["molecule_id"] or actual["input_bundle_sha256"] != formal["input_bundle_sha256"]:
                            raise ValueError("RAW_BODY_AND_FORMAL_OWNER_INPUT_BINDING_DIFFERS")
                        consumed += raw_size
                        files = actual["output_files"]
                        item.update(body_read=True, raw_bundle_sha256=actual["raw_sha256"],
                                    raw_metadata=actual["metadata"], actual_scf=scf.extract_scf(task, files), output_files=[])
                        text_files = {Path(f["name"]).name: f["data"] for f in files}
                        if "process.out" in text_files:
                            text = text_files["process.out"].decode("utf-8", errors="replace")
                            item["frozen_scalar_reparse"] = {
                                "EA_eV": parser.scalar(text, r"delta SCC EA \(eV\):\s*(" + parser.FLOAT + r")"),
                                "IP_eV": parser.scalar(text, r"delta SCC IP \(eV\):\s*(" + parser.FLOAT + r")"),
                                "last_TOTAL_ENERGY_Eh": parser.scalar(text, r"\bTOTAL ENERGY\s+(" + parser.FLOAT + r")\s*Eh"),
                                "last_TOTAL_ENERGY_stage": "UNASSIGNED; last print is not assumed neutral"}
                            item["ordered_printed_energy_SCC_evidence"] = [
                                {"line_1_based": n, "text": line[:1000]}
                                for n, line in enumerate(text.splitlines(), 1)
                                if re.search(r"TOTAL ENERGY|total energy|delta SCC|empirical .* shift|convergen|SCC|SCF|terminated|failed|warning|param_.*xtb|GFN[012]|IPEA|charge", line, re.I)]
                        if "xtbout.json" in text_files:
                            raw_json = json.loads(text_files["xtbout.json"])
                            item["xtbout_method_energy_charge_scalars"] = {
                                k: v for k, v in raw_json.items()
                                if (re.search(r"energy|charge|method|version", k, re.I) and
                                    isinstance(v, (str, int, float, type(None))))}
                        for f in files:
                            if Path(f["name"]).name not in {"process.out", "xtbout.json"}:
                                continue
                            body = f["data"]
                            name = hashlib.sha256((case["record_id"] + task).encode()).hexdigest()[:20] + "_" + Path(f["name"]).name
                            destination = output / "raw" / name
                            destination.parent.mkdir(exist_ok=True)
                            item["output_files"].append(support.write_blob(destination, body, output, cfg["output_cap_bytes"]))
                    else:
                        item["evidence_status"] = "CANONICAL_RAW_NOT_RETAINED_OR_NOT_PRESENT_NO_SCF_FAILURE_INFERENCE"
                    answer.append(item)
        finally:
            db.close()
        if identity(path) != before:
            raise ValueError("ARCHIVE_CHANGED_DURING_READONLY_PK_PROBE")
    return answer, consumed


def compare(case, rows, constant):
    def cells(task):
        return {int(c["registry_id"]): c for c in rows[(case["record_id"], task)]["values"]}
    def scalar(c, key):
        item = c.get(key, {})
        return item.get("f64") if item.get("kind") == 1 else None
    vi, sp = cells("xtb_vipea"), cells("xtb_singlepoint")
    ea, ip = scalar(vi, 751), scalar(vi, 752)
    if ea != case["EA_eV"] or ip != case["IP_eV"]:
        raise ValueError("CLOSED_EA_CASE_VALUE_CHANGED")
    energy, homo, lumo = scalar(sp, 670), scalar(sp, 671), scalar(sp, 672)
    charge = sp.get(668, {}).get("array_f64")
    return {"record_id": case["record_id"], "EA_eV": ea, "IP_eV": ip, "IP_minus_EA_eV": ip - ea,
            "SP_total_energy_Eh": energy, "SP_homo_eV": homo, "SP_lumo_eV": lumo,
            "SP_gap_eV": None if homo is None or lumo is None else lumo - homo,
            "SP_atomic_charge_sum_e": None if charge is None or any(x is None for x in charge) else math.fsum(charge),
            "SP_abs_total_energy_eV": None if energy is None else abs(energy) * constant,
            "EA_minus_SP_abs_total_energy_eV": None if energy is None else ea - abs(energy) * constant,
            "methods_equivalent": False, "comparison_status": "CROSS_METHOD_DIAGNOSTIC_ONLY_NO_MASK_RULE",
            "VIPEA_exported_registry_ids": sorted(vi),
            "VIPEA_state_energy_and_charge_status": "NOT_REGISTERED_IN_TWO_FIELD_WP5_VIPEA_WIRE; raw required for state attribution",
            "program_failure_hypothesis": "UNPROVEN; no magnitude, closeness, NULL, or cross-method gap sign implies failure"}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config", required=True)
    p.add_argument("--root-preflight", required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args()
    cfg = load(args.config)
    support = module(cfg["support_source"], "_ea_readonly_support")
    proof = support.root_guard(args.root_preflight, args.config, cfg["output_cap_bytes"], cfg["wall_seconds"])
    checkpoint()
    if cfg["workers"] != 16 or cfg["memory_gib"] < 32 or proof["request"]["memory_gib"] < cfg["memory_gib"] or int(os.environ.get("SLURM_MEM_PER_NODE", "0")) < cfg["memory_gib"] * 1024:
        raise ValueError("EA_BOUNDED_ANALYSIS_REQUIRES_16CPU_REVIEWED_ACTUAL_32G")
    if os.environ.get("CUDA_VISIBLE_DEVICES") != "" or any(os.environ.get(k) != "1" for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")):
        raise ValueError("CPU_ONLY_SINGLE_THREAD_ENVIRONMENT_REQUIRED")
    if cfg["schema"] != "EA_CANONICAL_BOUNDED_DIAGNOSTIC_V1" or len(cfg["cases"]) != 7 or len(cfg["sources"]) != 6:
        raise ValueError("EXACT_BOUNDED_CASE_OR_FILE_SCOPE_DIFFERS")
    for pin in checkpoint_iter(cfg["metadata_sources"]):
        checked(pin)
    projection = load(next(p["path"] for p in cfg["metadata_sources"] if p["path"].endswith("/sb3_catalog_projection_v1/source_files.json")))
    verified = load(next(p["path"] for p in cfg["metadata_sources"] if p["path"].endswith("/D20_failure_aware_v2_4515602/verification_report.json")))
    source_lookup = {p["path"]: p for p in projection}
    verified_lookup = {p["path"]: p for p in verified["files_verified"]}
    for pin in [*cfg["sources"], *cfg["archives"]]:
        other = verified_lookup.get(pin["path"], {})
        if any(pin[k] != other.get(k) for k in ("bytes", "sha256", "family")):
            raise ValueError("SOURCE_PIN_NOT_IN_CLOSED_FULL_VERIFICATION")
        if pin["family"] != "raw_archive" and any(pin[k] != source_lookup.get(pin["path"], {}).get(k) for k in ("bytes", "sha256", "family")):
            raise ValueError("SOURCE_PIN_NOT_IN_CANONICAL_SOURCE_PROJECTION")
    registry = load(checked(cfg["physical_registry"]))
    registered = {task: [r for r in registry if r["task"] == task] for task in ("xtb_vipea", "xtb_singlepoint")}
    if {r["registry_id"] for r in registered["xtb_vipea"]} != {751, 752}:
        raise ValueError("VIPEA_WIRE_REGISTRY_SCOPE_CHANGED")
    protocol = load(checked(cfg["protocol"]))
    tasks = {t["name"]: t for t in protocol["tasks"]}
    if any(tasks[task]["args"] != expected for task, expected in cfg["expected_task_args"].items()):
        raise ValueError("FROZEN_METHOD_ARGUMENTS_DIFFER")
    cases = latest_owners(cfg)
    import pyarrow.parquet as pq
    units = []
    total = 0
    for pin in checkpoint_iter(cfg["sources"]):
        path = checked(pin, content=False)
        total += pin["bytes"]
        units.extend((pin, i) for i in range(pq.ParquetFile(path).num_row_groups))
    if total > cfg["source_file_bytes_cap"] or len(units) < 16:
        raise ValueError("SOURCE_BUDGET_OR_16_NONEMPTY_PARTITIONS_NOT_SATISFIED")
    output = support.new_root(args.output, cfg["external_output_root"])
    context = multiprocessing.get_context("spawn")
    barrier = context.Barrier(16)
    started = time.monotonic()
    try:
        checkpoint()
        with concurrent.futures.ProcessPoolExecutor(max_workers=16, mp_context=context, initializer=initialize,
                initargs=(cfg, cases, barrier)) as pool:
            partitions = [units[i::16] for i in range(16)]
            workers = list(pool.map(project, checkpoint_iter(partitions), chunksize=1))
        if len({w["pid"] for w in workers}) != 16:
            raise ValueError("16_ACTUAL_DIAGNOSTIC_WORKERS_NOT_OBSERVED")
        rows = {}
        for w in workers:
            for row in w["rows"]:
                key = row["record_id"], row["calc_type"]
                if key in rows:
                    raise ValueError("DUPLICATE_CANONICAL_CASE_TASK")
                rows[key] = row
        if set(rows) != {(rid, task) for rid in cases for task in ("xtb_vipea", "xtb_singlepoint")}:
            raise ValueError("EXACT_CANONICAL_CASE_CONTEXT_COVERAGE_INCOMPLETE")
        for rid in cases:
            if rows[rid, "xtb_vipea"]["total_atoms"] != rows[rid, "xtb_singlepoint"]["total_atoms"]:
                raise ValueError("SAME_RECORD_ATOM_COUNT_DIFFERS")
        raw, raw_bytes = raw_context(cfg, cases, rows, output, support)
        result = {"schema": cfg["schema"], "status": "ACTUAL_BOUNDED_DIAGNOSIS_CAUSAL_REVIEW_PENDING",
                  "config": support.ref(args.config), "root_preflight": support.ref(args.root_preflight),
                  "cases": list(cases.values()), "registered_task_fields": registered,
                  "frozen_task_args": cfg["expected_task_args"], "formal_context_rows": list(rows.values()),
                  "comparisons": [compare(c, rows, cfg["frozen_Eh_to_eV"]) for c in cases.values()],
                  "raw_context": raw, "raw_uncompressed_bytes_read": raw_bytes,
                  "worker_receipts": workers, "actual_worker_pids": sorted(w["pid"] for w in workers),
                  "physical_source_file_bytes_bound": total, "elapsed_seconds": time.monotonic() - started,
                  "guide_approximately_390_SUCCESS_NULL_population_count_reestablished": False,
                  "new_masks": 0, "source_values_or_status_changed": False, "new_QM_calls": 0,
                  "cause": "UNKNOWN_UNTIL_CASE_SPECIFIC_RAW_AND_METHOD_STAGE_EVIDENCE_SUPPORTS_A_CONCLUSION"}
        support.save(output / "diagnostic.json", result, output, cfg["output_cap_bytes"])
        print("EA_CANONICAL_BOUNDED_DIAGNOSTIC_COMPLETE", len(cases), len(rows), len(raw), flush=True)
    except BaseException as exc:
        support.save(output / "failure.json", {"status": "BOUNDED_DIAGNOSIS_FAILED_EVIDENCE_PRESERVED",
                     "exception": type(exc).__name__, "message": str(exc), "new_masks": 0})
        raise


if __name__ == "__main__":
    main()
