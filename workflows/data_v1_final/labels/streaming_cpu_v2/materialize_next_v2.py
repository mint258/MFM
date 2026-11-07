"""Root metadata-only close/prepare one next CPU median/MAD/reduce/mask stage.

No scientific imports or data-body reads. Queries sacct, validates small closed
metadata, writes one explicit command, then invokes frozen central prepare_request
only. Never sbatch, launch, retry, follow a chain automatically, or authorize full.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys

PROJECT = Path("/share/home/zixiao/descriptor_analysis")
RUN = PROJECT / "runs/data_v1_20261025"
REPO = RUN / "repository"
HERE = REPO / "workflows/data_v1_final/labels/streaming_cpu_v2"
OUTPUT = RUN / "artifacts/labels/streaming_v1"
PYTHON = "/share/home/zixiao/.conda/envs/chemprop/bin/python"
DEPS = PROJECT / "docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
BOOTSTRAP = OUTPUT / "reduce_med_r6_p32_v1/reduction.json"
SCOPE = "label_canonical_512"
BASIS = "CPU_BOUNDED_TEST_LIVE_MEMORY_V1"
MAX_SMALL = 2 * 1024**2
REFS = {}
RAW = {}


def literal(path):
    p = Path(path)
    if not p.is_absolute() or ".." in p.parts or any(x.is_symlink() for x in (p, *p.parents)):
        raise ValueError("ABSOLUTE_LITERAL_CANONICAL_PATH_REQUIRED:" + str(p))
    return p


def add(path, expected=None):
    p = literal(path)
    if p.suffix.lower() in {".parquet", ".sqlite", ".lmdb", ".dict"}:
        raise ValueError("NO_DATA_BODY_HASH_IN_METADATA_MATERIALIZER")
    if expected and expected["bytes"] > MAX_SMALL:
        raise ValueError("DECLARED_SMALL_METADATA_OVER_2MIB")
    if str(p) not in REFS:
        with p.open("rb") as stream:
            before = os.fstat(stream.fileno())
            if before.st_uid != 1278 or before.st_size > MAX_SMALL:
                raise ValueError("SMALL_METADATA_OWNER_OR_2MIB_LIMIT")
            raw = stream.read(MAX_SMALL + 1)
            after = os.fstat(stream.fileno())
        if (before.st_ino, before.st_mtime_ns, before.st_size) != (after.st_ino, after.st_mtime_ns, after.st_size) or len(raw) != before.st_size:
            raise ValueError("SMALL_METADATA_CHANGED_DURING_READ")
        REFS[str(p)] = {"path": str(p), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
        RAW[str(p)] = raw
    if expected and REFS[str(p)] != {k: expected[k] for k in ("path", "bytes", "sha256")}:
        raise ValueError("EXACT_PATH_BYTES_SHA_REFERENCE_DIFFERS:" + str(p))
    return REFS[str(p)]


def load(path, expected=None):
    return json.loads(RAW[add(path, expected)["path"]].decode("utf-8-sig"))


def pinload(pin):
    return load(pin["path"], pin)


def write_new(path, value):
    path = literal(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def option(argv, name):
    if argv.count(name) != 1:
        raise ValueError("ONE_EXPLICIT_COMMAND_OPTION_REQUIRED:" + name)
    index = argv.index(name)
    if index + 1 >= len(argv):
        raise ValueError("COMMAND_OPTION_VALUE_MISSING")
    return argv[index + 1]


def sacct(job):
    argv = ["sacct", "-j", job, "--format=JobIDRaw,State,ExitCode,ElapsedRaw,AllocCPUS,NodeList,Partition", "-P"]
    result = subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=45)
    if result.returncode:
        raise RuntimeError({"argv": argv, "returncode": result.returncode, "stderr": result.stderr})
    lines = [line.split("|") for line in result.stdout.strip().splitlines()]
    found = [dict(zip(lines[0], row)) for row in lines[1:] if row[0] == job]
    if len(found) != 1 or found[0]["State"] != "COMPLETED" or found[0]["ExitCode"] != "0:0" or int(found[0]["AllocCPUS"]) < 16:
        raise ValueError("ACTUAL_PARENT_NOT_COMPLETED_0_WITH_16_CPU:" + repr(found))
    return found[0], {"argv": argv, "stdout": result.stdout, "stderr": result.stderr}


def close_parent(path, data, job):
    parent, observed = sacct(job)
    intent_pin = data["root_preflight"]
    intent = pinload(intent_pin)
    request = intent["request"]
    script_pin = request["script_reference"]
    add(script_pin["path"], script_pin)
    cpu = request.get("resource_policy") == BASIS
    monitor_pin = None
    if cpu:
        if (parent["Partition"] != "cpu" or request["scope_key"] != SCOPE or request["pilot"] is not True
                or parent["NodeList"] != request["node"]
                or request.get("formal_generation_authorized") is not False):
            raise ValueError("CPU_PARENT_NOT_EXACT_BOUNDED_SCOPE")
        parent_name = Path(intent_pin["path"]).name.removesuffix(".intent.json")
        monitor_path = RUN / "artifacts/cpu_analysis_guards" / parent_name / "closure.json"
        monitor = load(monitor_path)
        monitor_pin = add(monitor_path)
        if (monitor["status"] != "COMPLETED_NO_MEMORY_DENIAL" or monitor["job_id"] != job
                or monitor["scope_key"] != SCOPE or monitor["intent_reference"] != intent_pin
                or monitor["command"] != request["execution_argv"] or monitor["child_returncode"] != 0
                or monitor["failure"] is not None or monitor["first_denial"] is not None
                or monitor["monitor_io_failure"] is not None or monitor["signals_sent"] is not False
                or monitor["formal_generation_authorized"] is not False
                or monitor["monitor_thread_closed"] is not True or monitor["samples"] < 1
                or monitor.get("durable_evidence_exported") is not True or monitor.get("heartbeat_clock") != "BOOT_MONOTONIC"):
            raise ValueError("ACTUAL_CPU_PARENT_MONITOR_NOT_CLOSED_PASS")
        exports = monitor.get("evidence_exports", [])
        export_names = {Path(e["path"]).name for e in exports}
        if not {"heartbeat.json", "samples.jsonl"} <= export_names or len({e["path"] for e in exports}) != len(exports):
            raise ValueError("V2_CPU_MONITOR_DURABLE_EXPORT_SET_INCOMPLETE")
        for exported in exports:
            if Path(exported["path"]).parent != monitor_path.parent or type(exported["bytes"]) is not int or exported["bytes"] < 0 or not re.fullmatch(r"[a-f0-9]{64}", exported["sha256"]):
                raise ValueError("V2_CPU_MONITOR_EXPORT_REFERENCE_INVALID")
        closed_exports = exports  # producer has checked complete SHA/stable stat; no large samples read here
        command = request["execution_argv"]
        if str(HERE / "run_stage_v1.py") in command:
            inner_path = option(command, "--science-command")
            inner_pin = next((r for r in request["source_references"] if r["path"] == inner_path), None)
            if inner_pin is None:
                raise ValueError("DRIVER_SCIENCE_COMMAND_NOT_PINNED")
            inner = load(inner_path, inner_pin)
            if option(command, "--output") != option(inner, "--output"):
                raise ValueError("DRIVER_AND_INNER_SOURCE_OUTPUT_DIFFER")
            stage_path = literal(option(command, "--stage-receipt"))
            stage = load(stage_path)
            if (stage["status"] != "BOUNDARY_AND_ONE_SOURCE_PASS_COMPLETED" or stage["source_returncode"] != 0
                    or stage["science_command"] != inner or stage["job_id"] != job or stage["failure"] is not None
                    or stage["science_command_reference"] != inner_pin):
                raise ValueError("FIRST_MAD_DRIVER_STAGE_NOT_CLOSED")
            boundary = pinload(stage["boundary_reference"])
            if boundary["status"] != "PASS" or boundary["tests"] != 4 or boundary["failures"] or boundary["errors"]:
                raise ValueError("FIRST_MAD_FOUR_BOUNDARIES_NOT_ACTUALLY_CLOSED")
            command = inner
    else:
        if path != BOOTSTRAP or job != "4520444":
            raise ValueError("ONLY_EXPLICIT_CLOSED_R6_4520444_MAY_BOOTSTRAP_CPU_CHAIN")
        text = RAW[script_pin["path"]].decode("utf-8")
        command = shlex.split(text, comments=True)
    if literal(option(command, "--output")) != path.parent:
        raise ValueError("ACTUAL_PARENT_COMMAND_DOES_NOT_OWN_THIS_OUTPUT")
    if path.name == "scan_manifest.json" and data["job_id"] != job:
        raise ValueError("SCAN_MANIFEST_ACTUAL_PARENT_JOB_DIFFERS")
    if cpu:
        entries = (HERE / "reduce.py",) if path.name == "reduction.json" else (HERE / "scan_v2.py",)
        if not any(str(entry) in command for entry in entries):
            raise ValueError("CPU_PARENT_ENTRY_NOT_THE_PINNED_CPU_SCAN_OR_REDUCER")
    if path.name == "reduction.json":
        if option(command, "--scan-manifest") != data["scan_manifest"]["path"]:
            raise ValueError("PARENT_REDUCER_INPUT_MANIFEST_DIFFERS")
    elif (option(command, "--plan") != data["plan"]["path"] or option(command, "--phase") != data["phase"]
          or option(command, "--queries") != data["queries"]["path"]):
        raise ValueError("PARENT_SCAN_PLAN_PHASE_OR_QUERY_DIFFERS")
    return {"actual_parent": parent, "sacct_observation": observed, "input": add(path),
            "parent_intent": intent_pin, "cpu_monitor_closure": monitor_pin,
            "allocated_core_seconds": int(parent["ElapsedRaw"]) * int(parent["AllocCPUS"]),
            "actual_source_command": command, "ordinary_closed_r6_bootstrap": not cpu}


def population(data):
    plan = pinload(data["plan"])
    cfg = pinload(plan["config"])
    fields = pinload(plan["field_map"])
    ids = {str(f["field_id"]) for f in fields}
    if (plan["mode"] != "pilot" or plan["records"] != 4251 or plan["molecules"] != 512
            or len(plan["groups"]) != 16 or len(ids) != 146 or len(fields) != 146
            or sum(g["expected_records"] for g in plan["groups"]) != 4251
            or plan["full_common_population_frozen"] is not False or plan["diagnostic_exclusions_frozen"] is not False
            or plan["normalization_completed"] is not False
            or data["coverage_fingerprint"] != plan["coverage_fingerprint"] or data["mode"] != "pilot"):
        raise ValueError("EXACT_4251_512_16_146_PILOT_SCOPE_REQUIRED")
    if len(plan["task_codes"]) != 14 or cfg["workers"] != 16:
        raise ValueError("FOURTEEN_TASKS_AND_SIXTEEN_WORKERS_REQUIRED")
    for pin in cfg["adapter_source_pins"]:
        add(pin["path"], pin)
    return plan, cfg, ids


def reduction_checks(data, plan, ids):
    if (data["status"] != "SOURCE_COVERAGE_CONSERVED_MORE_SCIENTIFIC_GATES_PENDING"
            or data["groups_verified"] != 16 or data["actual_workers"] != 16
            or set(data["field_counts"]) != ids or data["records"] != 4251 or data["molecules"] != 512
            or data["quantum_record_task_slots"] != 4251 * 12
            or data["all_record_task_slots_including_D20_D3"] != 4251 * 14
            or data["roles"] != plan["roles"]):
        raise ValueError("REDUCTION_COVERAGE_FIELDS_TASKS_OR_ROLES_NOT_CONSERVED")
    fractions = []
    for row in data["field_counts"].values():
        if row["records"] != 4251 or not 0 <= row["newly_masked_records"] <= 4251:
            raise ValueError("REDUCTION_FIELD_MASK_MASS_INVALID")
        fraction = row["newly_masked_records"] / 4251
        if fraction != row["new_mask_fraction"]:
            raise ValueError("REDUCTION_NEW_MASK_FRACTION_INCONSISTENT")
        fractions.append(fraction)
    if data["stop_fields"] or max(fractions) > .01:
        raise ValueError("STOP_NEW_MASK_ABOVE_ONE_PERCENT_NO_NEXT_REQUEST")
    for key in ("radix_next_queries", "exact_medians", "MAD_queries", "exact_TRAIN_median_MAD", "energy_reference", "TRAIN_size_rho", "worst20_by_field_reason", "scan_manifest"):
        if data.get(key):
            add(data[key]["path"], data[key])
    return max(fractions)


def scan_checks(data, plan, ids):
    if data["status"] != "GROUP_SCANS_COMPLETE_REDUCTION_REQUIRED" or len(set(data["actual_worker_pids"])) != 16:
        raise ValueError("SCAN_NOT_CLOSED_WITH_SIXTEEN_ACTUAL_WORKERS")
    groups = {g["group_index"]: g for g in plan["groups"]}
    seen, pids, totals = set(), set(), {fid: 0 for fid in ids}
    for pin in data["group_receipts"]:
        row = pinload(pin)
        index = row["group_index"]
        if index not in groups or index in seen:
            raise ValueError("SCAN_DUPLICATE_OR_UNPLANNED_OWNER_GROUP")
        seen.add(index)
        pids.add(row["pid"])
        group = groups[index]
        n = group["expected_records"]
        if (row["status"] != "SOURCE_GROUP_SCANNED" or row["owner_index"] != group["owner_index"]
                or row["records"] != n or set(row["field_counts"]) != ids
                or set(row["task_coverage"]) != set(plan["task_codes"])):
            raise ValueError("SCAN_OWNER_FIELD_OR_TASK_COVERAGE_DIFFERS")
        digests = set()
        for task in row["task_coverage"].values():
            if task["records"] != n or not re.fullmatch(r"[a-f0-9]{64}", task["ordinal_sha256"]):
                raise ValueError("SCAN_TASK_ORDINAL_OR_RECORD_COUNT_INVALID")
            digests.add(task["ordinal_sha256"])
        if len(digests) != 1:
            raise ValueError("SCAN_TASKS_DO_NOT_SHARE_CANONICAL_ORDINAL_POPULATION")
        for fid, count in row["field_counts"].items():
            if count["records"] != n or not 0 <= count["newly_masked_records"] <= n:
                raise ValueError("SCAN_FIELD_RECORD_DENOMINATOR_DIFFERS")
            totals[fid] += count["newly_masked_records"]
    if seen != set(groups) or pids != set(data["actual_worker_pids"]) or len(pids) != 16:
        raise ValueError("SCAN_GROUPS_OR_WORKERS_INCOMPLETE")
    if any(n / 4251 > .01 for n in totals.values()):
        raise ValueError("STOP_NEW_MASK_ABOVE_ONE_PERCENT_NO_NEXT_REQUEST")
    for key in ("queries", "calibration", "energy_reference"):
        if data.get(key):
            add(data[key]["path"], data[key])
    return max(totals.values()) / 4251


def query_scope(pin, plan):
    query = pinload(pin)
    if (query["coverage_fingerprint"] != plan["coverage_fingerprint"] or query["mode"] != "pilot"
            or query["purpose"] not in {"median", "MAD"} or type(query["round"]) is not int or query["round"] < 0):
        raise ValueError("RADIX_QUERY_SCOPE_PURPOSE_OR_ROUND_INVALID")
    return query


def main():
    p = argparse.ArgumentParser(description=__doc__)
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--reduction")
    group.add_argument("--scan")
    p.add_argument("--job", required=True)
    p.add_argument("--node", required=True)
    a = p.parse_args()
    if os.getuid() != 1278 or Path(__file__).absolute() != HERE / "materialize_next_v2.py":
        raise ValueError("ROOT_ACTUAL_REPOSITORY_METADATA_ENTRY_REQUIRED")
    if not a.job.isdecimal() or a.node not in {"compute-0-2", *{f"compute-0-{n}" for n in range(8, 20)}}:
        raise ValueError("NUMERIC_PARENT_AND_AUTHORIZED_CPU_NODE_REQUIRED")
    path = literal(a.reduction or a.scan)
    if OUTPUT not in path.parents or path.name != ("reduction.json" if a.reduction else "scan_manifest.json"):
        raise ValueError("EXACT_CANONICAL_LABEL_METADATA_PATH_REQUIRED")
    data = load(path)
    closed = close_parent(path, data, a.job)
    plan, cfg, ids = population(data)
    max_new = reduction_checks(data, plan, ids) if a.reduction else scan_checks(data, plan, ids)
    closed.update(status="ACTUAL_BOUNDED_LABEL_PASS_CLOSED_NOT_FINAL_D4", records=4251, molecules=512,
                  groups=16, fields=146, roles=plan["roles"], new_mask_max=max_new, D4_published=False,
                  full_population_accepted=False, scientific_data_bodies_read_by_materializer=False)
    for source in sorted(HERE.glob("*.py")):
        add(source)
    for name in ("edits_v2.json", "source_mapping_v2.json"):
        add(HERE / name)
    reducer_guard = 'root_guard(a.root_preflight,a.scan_manifest,cfg["reduce_output_cap_bytes"],7200)'
    if RAW[add(HERE / "reduce.py")["path"]].decode().count(reducer_guard) != 1:
        raise ValueError("V2_REDUCER_REQUIRES_UNCHANGED_VERIFIED_7200_GUARD")
    proof_path = RUN / "control/sb3_stream_cpu_equivalence_v2.json"
    proof = load(proof_path)
    if proof["status"] != "PASS" or len(proof["files"]) != 5:
        raise ValueError("ACTUAL_FIVE_FILE_CONTROL_EQUIVALENCE_NOT_PASS")
    for row in proof["files"]:
        actual = add(HERE / row["filename"])
        if any(actual[k] != row["actual_variant_reference"][k] for k in ("bytes", "sha256")):
            raise ValueError("ACTUAL_ROOT_CPU_SOURCE_BYTES_DIFFER_FROM_PROVED_VARIANT")
    initial = path == BOOTSTRAP and a.job == "4520444"
    if initial:
        prior_boundary_path = RUN / "control/dv1_label_mad_r0_cpu_v1.boundary.json"
        prior_boundary = load(prior_boundary_path)
        if prior_boundary["status"] != "PASS" or prior_boundary["tests"] != 4 or prior_boundary["failures"] or prior_boundary["errors"]:
            raise ValueError("PRIOR_FOUR_CPU_BOUNDARIES_NOT_ACTUALLY_PASS")
        closed["prior_independent_four_boundary_result"] = add(prior_boundary_path)
        closed["failed_v1_source_job_preserved_not_reused"] = "4520497"
    if a.reduction:
        if data["phase"] == "mask":
            closed["status"] = "BOUNDED_PILOT_MEDIAN_MAD_MASK_COMPLETE_NO_NEXT_JOB"
            destination = RUN / f"control/label_cpu_closed_{a.job}_v2.json"
            write_new(destination, closed)
            print(json.dumps({"status": closed["status"], "closure": str(destination)}))
            return
        query_pin = data["radix_next_queries"] if data["radix_refinement_required"] else data["MAD_queries"]
        if query_pin:
            query = query_scope(query_pin, plan)
            if not query["fields"]:
                raise ValueError("NEXT_REFINEMENT_QUERY_IS_EMPTY")
            tag = ("med" if query["purpose"] == "median" else "mad") + "_r" + str(query["round"])
            phase = "refine"
            extra = ["--queries", query_pin["path"]]
        else:
            query_pin = data["radix_next_queries"]
            query = query_scope(query_pin, plan)
            calibration = pinload(data["exact_TRAIN_median_MAD"])
            if (query["fields"] or query["purpose"] != "MAD" or calibration["fit_role"] != "TRAIN_ONLY"
                    or calibration["coverage_fingerprint"] != plan["coverage_fingerprint"]
                    or calibration["mode"] != "pilot" or set(calibration["fields"]) != ids):
                raise ValueError("FINAL_MASK_REQUIRES_COMPLETED_EXACT_146_FIELD_TRAIN_CALIBRATION")
            tag, phase = "mask_v1", "mask"
            extra = ["--queries", query_pin["path"], "--calibration", data["exact_TRAIN_median_MAD"]["path"]]
        if initial and (query["purpose"] != "MAD" or query["round"] != 0 or not data["exact_medians"]):
            raise ValueError("R6_BOOTSTRAP_MUST_START_MAD_ROUND_ZERO")
        name = "dv1_label_" + tag + "_cpu_v2"
        output = OUTPUT / ("scan_" + tag + "_cpu_v2")
        command = [PYTHON, "-B", str(HERE / "scan_v2.py"), "--plan", data["plan"]["path"], "--phase", phase, *extra]
        if data.get("energy_reference"):
            command += ["--energy-reference", data["energy_reference"]["path"]]
    else:
        query = query_scope(data["queries"], plan)
        tag = "mask_v1" if data["phase"] == "mask" else ("med" if query["purpose"] == "median" else "mad") + "_r" + str(query["round"])
        name = "dv1_label_reduce_" + tag + "_cpu_v2"
        output = OUTPUT / ("reduce_" + tag + "_cpu_v2")
        command = [PYTHON, "-B", str(HERE / "reduce.py"), "--scan-manifest", str(path)]
    literal(output)
    if output.exists():
        raise FileExistsError("NEXT_SCIENTIFIC_OUTPUT_EXISTS_NO_RETRY")
    intent = RUN / f"control/submissions/{name}.intent.json"
    command += ["--root-preflight", str(intent), "--output", str(output)]
    command_path = RUN / f"control/commands/{name}.json"
    close_path = RUN / f"control/label_cpu_closed_{a.job}_v2.json"
    receipt = RUN / f"control/{name}.materialization.json"
    for dest in (command_path, close_path, receipt, intent, RUN / f"control/requests/{name}.json", RUN / f"control/scripts/{name}.sbatch", RUN / f"control/submissions/{name}.json"):
        if dest.exists():
            raise FileExistsError("REGISTERED_NEXT_STAGE_OR_CLOSURE_EXISTS_NO_OVERWRITE_OR_RETRY:" + str(dest))
    closed["next_source_command_prepared_not_executed"] = command
    write_new(close_path, closed)
    add(close_path)
    # v2 executes one source pass directly; four boundary results already exist.
    write_new(command_path, command)
    add(command_path)
    env = dict(os.environ, PYTHONPATH=str(REPO) + ":" + str(DEPS), PYTHONDONTWRITEBYTECODE="1")
    argv = [PYTHON, "-B", "-m", "workflows.data_v1_final.execution.cpu_analysis_v1.prepare_request_v2",
            "--scope", SCOPE, "--node", a.node, "--job-name", name, "--command-file", str(command_path)]
    for pin in sorted(REFS.values(), key=lambda row: row["path"]):
        argv += ["--source", pin["path"]]
    result = subprocess.run(argv, cwd=REPO, env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True)
    outcome = {"schema": "LABEL_CPU_NEXT_STAGE_MATERIALIZATION_V2", "status": "PREPARED_NOT_SUBMITTED" if result.returncode == 0 else "CENTRAL_PREPARATION_FAILED_NO_AUTOMATIC_RETRY",
               "parent_closure": add(close_path), "command_file": add(command_path), "next_output": str(output),
               "central_prepare_argv": argv, "central_prepare_returncode": result.returncode,
               "stdout": result.stdout, "stderr": result.stderr, "scheduler_submission_commands_run": [],
               "prior_four_boundary_results_reused": initial, "source_pass_has_no_boundary_driver": True, "scientific_passes_run_by_materializer": 0}
    write_new(receipt, outcome)
    print(json.dumps(outcome, ensure_ascii=False))
    if result.returncode:
        raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
