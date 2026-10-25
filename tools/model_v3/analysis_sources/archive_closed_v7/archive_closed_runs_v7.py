"""CPU-only task archive, preserving all originals and truthful failed states."""
from __future__ import annotations

import argparse
from contextlib import ExitStack
from datetime import datetime, timezone
import fcntl
import hashlib
import html
import importlib.util
import json
import os
from pathlib import Path
import re
import socket
import stat
import time

from bounded_history_v7 import require, strict_json, encoded, mirror_rows, verify_file

BASE = Path("/share/home/zixiao/descriptor_analysis")
TASK = BASE / "runs/model_v3_20261025"
ARCHIVE = BASE / "runs/phase1_full_corpus/wandb_archive"
DEST = ARCHIVE / "model_v3_20261025"
HELPER = BASE / "scripts/archive_phase1_wandb_v2.py"
HELPER_SHA = "3fbd821e85fe093e037c4b45e6bf666d08533eb07edaabf0435d5b8b1e8f975a"
B3_ROOT = TASK / "sa3_b3_verification_v2"
B3_CERT_SHA = "a8111a12425d7c4f8421ef645fac222def343727bc93e7ff5b1d446400a8dddf"
B3_VERIFY_SHA = "83d322d67184e75d7f11cd55ef597762744bb0b1a3a0137c917b0afe6f120e6b"
CASES = {
    "4520438": ("a_native_control_4520438", "COMPLETED", "0:0", 2, 500, "A_plain"),
    "4520457": ("A_a06_fused_4520457", "FAILED", "1:0", 2, 500, "A_plain"),
    "4520485": ("A06_optimizer_diagnostic_4520485", "COMPLETED", "0:0", 1, 101, "optimizer"),
    "4520486": ("A_a00_control_4520486", "COMPLETED", "0:0", 2, 500, "A_plain"),
    "4520513": ("precision_synthetic_SDK_4520513", "COMPLETED", "0:0", 1, 6, "precision"),
    "4520514": ("precision_synthetic_SDK_4520514", "COMPLETED", "0:0", 1, 4, "precision"),
    "4520482": ("c2_run_4520482", "FAILED", "1:0", 1, 0, "failed_empty"),
    "4520525": ("A_a05_compile_4520525", "FAILED", "1:0", 2, 0, "failed_compile"),
}
PHASE_FILES = ("configuration.json", "run_status.json", "summary.json", "member_result.json", "history.jsonl",
    "reference_history.jsonl", "candidate_history.jsonl", "fixed_batch_gate.json", "trajectory_gate.json",
    "consumption.jsonl", "stream_reset.json", "resources.jsonl", "FAILED.json", "input_binding.json")


def file_ref(path, maximum=128 << 20):
    path = Path(path).absolute()
    require(".." not in path.parts and not any(parent.is_symlink() for parent in (path, *path.parents)), "Physical source ancestry required")
    before = path.lstat()
    require(stat.S_ISREG(before.st_mode) and before.st_uid == os.getuid() and before.st_nlink == 1
            and before.st_size <= maximum, "Owned bounded ordinary file required")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    after = path.stat()
    require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) ==
            (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns), "Source changed while hashing")
    return {"path": str(path), "bytes": before.st_size, "sha256": digest.hexdigest()}


def read_json(path, expected=None):
    ref = file_ref(path, 8 << 20)
    require(expected is None or ref == expected, "Bound JSON source differs")
    raw = Path(path).read_bytes()
    require(hashlib.sha256(raw).hexdigest() == ref["sha256"], "JSON changed before decode")
    return strict_json(raw), ref


def copy_ref(reference, destination):
    require(file_ref(reference["path"]) == reference, "Copy source binding differs")
    destination = Path(destination)
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    digest, written = hashlib.sha256(), 0
    with Path(reference["path"]).open("rb") as source, destination.open("xb") as target:
        for block in iter(lambda: source.read(1 << 20), b""):
            digest.update(block); target.write(block); written += len(block)
        target.flush(); os.fsync(target.fileno())
    require(written == reference["bytes"] and digest.hexdigest() == reference["sha256"]
            and file_ref(reference["path"]) == reference, "Source changed during immutable copy")
    copied = file_ref(destination)
    require((copied["bytes"], copied["sha256"]) == (reference["bytes"], reference["sha256"]), "Copied on-disk bytes differ")


def merge_entries(old, new):
    result, keys = list(old), {(row["job_id"], row["run_id"]): row for row in old}
    require(len(keys) == len(old), "Existing task index already contains duplicate identities")
    for row in new:
        key = row["job_id"], row["run_id"]
        if key in keys:
            require(keys[key]["path"] == row["path"], "Existing archive identity has a different target")
        else:
            result.append(row); keys[key] = row
    return result


def check_receipt(path, sha, jobs):
    value, reference = read_json(path)
    require(reference["sha256"] == sha and value["host"] == "sonmi" and value["uid"] == 1278
            and value["returncode"] == 0, "Fresh authoritative sonmi quota/closedjob receipt required")
    require(0 <= datetime.now(timezone.utc).timestamp() - value["unix_time"] <= 120, "Quota/closedjob receipt older than120seconds")
    quota = [line.split() for line in value["stdout"].splitlines() if line.split() and line.split()[0] == "/dev/sda1"]
    require(len(quota) == 1, "Authoritative quota row missing")
    used, soft, hard = (int(v.rstrip("*")) for v in quota[0][1:4])
    limits = [v for v in (soft, hard) if v > 0]
    require(limits and (min(limits)-used)*1024 > 34 << 30, "Authoritative quota reserve below34GiB")
    for job, state, exit_code in jobs:
        require(value["closed_jobs"][job].split("|")[:3] == [job, state, exit_code], "Actual terminal job receipt differs: " + job)
    return value, reference


def validate_lineage(parent, child, first_rows, next_rows, state, trainer_marker):
    require(parent["input_kind"] == child["input_kind"] == "synthetic"
            and parent["scientific_acceptance"] is False and child["scientific_acceptance"] is False,
            "Only explicit synthetic recovery certificate is in this archive task")
    require(parent["contract"] == child["contract"] and parent["tracker"] == child["resume_parent_tracker"], "Resume source/member/provider/tracker lineage differs")
    require(parent["tracker"]["id"] != child["tracker"]["id"] and child["parent_checkpoint"], "Fresh SDK resume lineage required")
    require((parent["optimizer_updates"], parent["samples_consumed"], child["optimizer_updates"], child["samples_consumed"])
            == (2, 4, 4, 8), "Actual synthetic update/sample recovery endpoints differ")
    require((state["optimizer_updates"], state["samples_consumed"], state["log_cursor"])
            == (2, 4, 6) and (trainer_marker["optimizer_updates"], trainer_marker["samples_consumed"]) == (2, 4),
            "Checkpoint optimizer/sample/log clocks differ")
    require([row["step"] for row in first_rows] == list(range(6)) and [row["step"] for row in next_rows] == list(range(6, 10)),
            "SDK global log cursor is missing/replayed across resume")
    for row in (*first_rows, *next_rows):
        require(row["commit"] is True and row["row"]["log_cursor"] == row["step"], "Uncommitted or mismatched resume cursor")
    require(all(row["row"].get("resume_parent_run_id") == parent["tracker"]["id"] for row in next_rows), "Resume parent history annotation differs")
    require(state["points"] == parent["validation"] and all(child["validation"][key] == value for key, value in parent["validation"].items()),
            "Saved validation points changed/replayed across recovery")
    require(not any(row["row"]["event"] == "VALIDATION" and row["row"]["optimizer_updates"] <= 2 for row in next_rows),
            "Resumed segment replayed the original validation grid")
    draws = [ordinal for row in (*first_rows, *next_rows) if row["row"]["event"] == "TRAIN_STEP"
             for ordinal in row["row"]["sample_ordinals"]]
    require(draws == list(range(8)), "Consumed sample ordinals are missing or duplicated")
    return {"schema": "model_v3_synthetic_precision_recovery_lineage_v7", "status": "VERIFIED_SOURCE_CLOCK_LINEAGE",
        "parent_run_id": parent["tracker"]["id"], "child_run_id": child["tracker"]["id"],
        "parent_updates_samples_cursor": [2, 4, 6], "child_updates_samples_cursor": [4, 8, 10],
        "sample_ordinals": draws, "saved_zero_validation_not_replayed": True,
        "SDK_payload_verification_required_separately": True, "scientific_acceptance": False}


def lineage_certificate():
    left, right = TASK / CASES["4520513"][0], TASK / CASES["4520514"][0]
    parent, parent_ref = read_json(left / "member_result.json")
    child, child_ref = read_json(right / "member_result.json")
    marker_ref = child["parent_checkpoint"]
    marker_path = Path(marker_ref["path"])
    require(marker_path.is_relative_to(left) and marker_path.name == "PRECISION_COMPLETE.json", "Unexpected resume checkpoint source")
    marker, _ = read_json(marker_path, marker_ref)
    state, state_ref = read_json(marker["state"]["path"], marker["state"])
    trainer, trainer_ref = read_json(marker["trainer_marker"]["path"], marker["trainer_marker"])
    require(Path(state_ref["path"]).parent == marker_path.parent and Path(trainer_ref["path"]).parent == marker_path.parent / "trainer",
            "Checkpoint state/marker escaped its declared parent")
    payload_ref = file_ref(marker_path.parent / "trainer/payload.pt")  # hash only; never deserialize weights
    require(payload_ref["sha256"] == trainer["payload_sha256"] == marker["trainer_payload_sha256"]
            and payload_ref["bytes"] == trainer["payload_bytes"], "Original resume payload hash differs")
    histories = []
    for phase in (left, right):
        reference = file_ref(phase / "history.jsonl", 1 << 20)
        with Path(reference["path"]).open("rb") as stream:
            rows = [strict_json(line) for line in stream]
        histories.append(rows)
    result = validate_lineage(parent, child, *histories, state, trainer)
    result["inputs"] = [parent_ref, child_ref, marker_ref, state_ref, trainer_ref, payload_ref]
    return result


def basic_exports(normalized, output):
    # This path avoids the fixed helper's50000-packet limit when needed.
    import csv
    keys = set()
    with normalized.open("rb") as stream:
        for raw in stream:
            keys.update(strict_json(raw)["row"])
    with (output / "metrics.csv").open("x", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["_step", *sorted(keys)])
        writer.writeheader()
        with normalized.open("rb") as source:
            for raw in source:
                row = strict_json(raw)
                writer.writerow({"_step": row["step"], **{key: json.dumps(value, allow_nan=False) if type(value) in (list, dict) else value for key, value in row["row"].items()}})
    (output / "index.html").write_text('<!doctype html><meta charset="utf-8"><p>Offline unsynced archive. See <a href="verification.json">native verification</a>, <a href="history.normalized.jsonl">complete history</a> and <a href="metrics.csv">CSV</a>.</p>')


def make_case(helper, job, pending):
    name, state, exit_code, expected_runs, expected_rows, kind = CASES[job]
    phase = TASK / name
    runs = sorted((phase / "wandb").glob("offline-run-*"))
    require(len(runs) == expected_runs, "Exact source SDK run count differs")
    inventories = [(run, helper.source_manifest(run)) for run in runs]
    attachments = [file_ref(phase / name) for name in PHASE_FILES if (phase / name).exists()]
    primary_cause = None
    if kind == "failed_compile":
        supervisor, supervisor_ref = read_json(TASK / "A_candidate_supervisor_4520525.json")
        stdout_ref = file_ref(TASK / "A_candidate_4520525.log", 8 << 20)
        stdout = Path(stdout_ref["path"]).read_text()
        require(str(supervisor["job_id"]) == job and supervisor["status"] == "FAILED"
                and supervisor["first_failure"]["type"] == "MemoryError"
                and "85%" in supervisor["first_failure"]["message"] and "torch.OutOfMemoryError" in stdout,
                "Actual compile primary supervisor/stdout failure evidence differs")
        attachments.extend((supervisor_ref, stdout_ref))
        primary_cause = {"supervisor_first_failure": supervisor["first_failure"], "supervisor": supervisor_ref,
                         "stdout": stdout_ref, "stdout_contains_torch_OutOfMemoryError": True,
                         "run_status_failure_null_is_not_success": True, "numeric_gate_pass": False, "timing_gate_pass": False}
    if kind == "optimizer":
        extra = list(phase.glob("*_step*.json")); require(len(extra) <= 64, "Bounded optimizer diagnostic attachments required")
        attachments.extend(file_ref(path) for path in extra)
    source_bytes = sum(row["bytes"] for _, inventory in inventories for row in inventory) + sum(ref["bytes"] for ref in attachments)
    require(source_bytes <= 128 << 20, "Case selected sources exceed128MiB")
    for ref in attachments:
        copy_ref(ref, pending / "case_files" / Path(ref["path"]).name)
    verified, entries = [], []
    for run, inventory in inventories:
        match = re.fullmatch(r"offline-run-\d{8}_\d{6}-([a-z0-9]+)", run.name)
        require(match is not None, "Invalid source run name")
        run_id = match[1]
        raw_root = pending / "wandb" / run.name
        for row in inventory:
            copy_ref({"path": row["read_path"], "bytes": row["bytes"], "sha256": row["sha256"]}, raw_root / row["relative_path"])
        output = pending / "sdk_exports" / run_id; output.mkdir(parents=True)
        with ExitStack() as stack:
            chosen = {}
            def mirror_factory(config):
                if kind.startswith("failed_"):
                    return iter(())
                if kind == "A_plain":
                    role = config.get("paired_role")
                    require(role in ("reference", "candidate"), "Native A role not bound before scientific history")
                    path = phase / (role + "_history.jsonl"); chosen["role"] = role
                else:
                    path = phase / "history.jsonl"
                chosen["source"] = file_ref(path)
                return mirror_rows(stack.enter_context(path.open("rb")), kind)
            with (output / "history.normalized.jsonl").open("xb") as stream:
                details = verify_file(raw_root / ("run-"+run_id+".wandb"), stream, expected_run_id=run_id,
                    expected_exit=None if kind.startswith("failed_") else 1 if job == "4520457" else 0,
                    expected_rows=expected_rows, mirror_factory=mirror_factory, allow_incomplete=kind.startswith("failed_"))
        details.update(mirror=chosen, run_id=run_id, job_id=job, slurm_state=state, slurm_exit_code=exit_code,
            semantics="SYNTHETIC_OPTIMIZER_GRADIENT_DIAGNOSTIC_NOT_TRAINING" if kind == "optimizer" else
                      "SYNTHETIC_PRECISION_EXECUTION_RECOVERY_NOT_PROXY" if kind == "precision" else "PRESERVED_ORIGINAL_SEGMENT")
        if details["native_packets"] < 50000 and details["decode_error"] is None and (not kind.startswith("failed_") or details["native_closed"]):
            old_exports = helper.export_history(raw_root / ("run-"+run_id+".wandb"), output, state == "FAILED")
            require(old_exports["history_rows"] == details["history_rows"], "Fixed helper/native mirror row count differs")
            details["fixed_helper_exports"] = old_exports
        else:
            basic_exports(output / "history.normalized.jsonl", output)
        helper.atomic_json(output / "verification.json", details)
        require(helper.source_manifest(run) == inventory, "Original SDK files changed during archive")
        verified.append({"run_id": run_id, "source_run": str(run), "source_files": inventory, "verification": details})
        entries.append({"job_id": job, "run_id": run_id, "name": name + " / " + chosen.get("role", kind),
                        "slurm_state": state, "exit_code": exit_code, "offline_unsynced": True})
    if kind == "A_plain":
        require({row["verification"]["paired_role"] for row in verified} == {"reference", "candidate"}, "Two distinct A scientific roles required")
    lineage = None
    if kind == "precision":
        lineage = lineage_certificate()
        require(source_bytes + sum(ref["bytes"] for ref in lineage["inputs"]) <= 128 << 20, "Precision evidence sources exceed128MiB")
        helper.atomic_json(pending / "recovery_lineage_certificate.json", lineage)
    return {"schema": "model_v3_closed_case_archive_v7", "job_id": job, "source_phase": str(phase),
        "slurm_state": state, "exit_code": exit_code, "source_attachments": attachments,
        "primary_cause": primary_cause,
        "SDK_runs": verified, "selected_source_bytes": source_bytes, "recovery_lineage": lineage is not None,
        "original_files_preserved": True, "online_sync_performed": False, "scientific_acceptance": False}, entries


def make_b3_case(helper, pending):
    execution = B3_ROOT / "execution_4520487"
    certificate, certificate_ref = read_json(execution / "native_sdk/verification.json")
    require(certificate_ref["sha256"] == B3_CERT_SHA and certificate["status"] == "VERIFIED"
            and certificate["schema"] == "model_v3_B3_native_history_verification_v2"
            and certificate["clean_eof"] is True and certificate["sdk_exit_code"] == 0
            and certificate["native_records"] == 170299 and certificate["history_rows"] == 56738,
            "Existing independent B3 verification certificate differs")
    implementation = file_ref(B3_ROOT / "verify_native_history.py")
    require(implementation == certificate["verifier_implementation"] and implementation["sha256"] == B3_VERIFY_SHA,
            "B3 verifier implementation differs")
    closure, closure_ref = read_json(execution / "closure.json")
    require(closure["status"] == "COMPLETED" and closure["job_id"] == "4520487"
            and closure["native_certificate_sha256"] == B3_CERT_SHA
            and closure["sources_before"] == closure["sources_after"], "B3 actual verification closure differs")
    for name, expected in closure["sources_before"].items():
        require(file_ref(name)["sha256"] == expected, "B3 frozen verification source differs")
    source_pins, pins_ref = read_json(B3_ROOT / "source_pins_v2.json")
    require(source_pins["schema"] == "model_v3_B3_independent_verification_sources_v2", "B3 source inventory differs")
    for reference in source_pins["files"]:
        require(file_ref(reference["path"]) == reference, "B3 pinned source bytes differ")
    require(file_ref(certificate["sdk_reader"]["DataStore"]["path"]) == certificate["sdk_reader"]["DataStore"],
            "B3 independently verified SDK reader source differs")
    for reference in certificate["inputs"].values():
        require(file_ref(reference["path"]) == reference, "B3 original SDK/journal/request/result binding differs")
    normalized = file_ref(execution / "native_sdk/history.scalars.jsonl")
    require(normalized["bytes"] == certificate["normalized_history_bytes"] == 14296086
            and normalized["sha256"] == certificate["normalized_history_sha256"], "Existing normalized B3 history differs")
    report, report_ref = read_json(execution / "report/report_manifest.json")
    require(report["verification"]["certificate"] == certificate_ref and report["verification"]["independently_verified"] is True,
            "B3 compact report certificate binding differs")
    for reference in report["inputs"].values():
        require(file_ref(reference["path"]) == reference, "B3 compact report original source differs")
    references = [certificate_ref, normalized, closure_ref, pins_ref, implementation, report_ref, *report["outputs"]]
    for reference in report["outputs"]:
        require(file_ref(reference["path"]) == reference, "B3 compact report output bytes differ")
    sdk_ref = certificate["inputs"]["sdk"]
    run = Path(sdk_ref["path"]).parent
    inventory = helper.source_manifest(run)
    require(sum(row["bytes"] for row in inventory) + sum(ref["bytes"] for ref in references) <= 128 << 20,
            "B3 selected archive source bytes exceed128MiB")
    bound_inputs = {ref["path"]: ref for ref in (*references, *certificate["inputs"].values(), *report["inputs"].values(),
                    *source_pins["files"], certificate["sdk_reader"]["DataStore"])}
    for row in inventory:
        bound_inputs[row["read_path"]] = {"path": row["read_path"], "bytes": row["bytes"], "sha256": row["sha256"]}
    require(sum(ref["bytes"] for ref in bound_inputs.values()) <= 128 << 20, "All unique B3 metadata/source inputs exceed128MiB")
    for row in inventory:
        copy_ref({"path": row["read_path"], "bytes": row["bytes"], "sha256": row["sha256"]}, pending / "wandb" / run.name / row["relative_path"])
    for reference in references:
        path = Path(reference["path"])
        if path.is_relative_to(execution):
            relative = path.relative_to(execution)
        else:
            relative = Path("verified_sources") / path.name
        copy_ref(reference, pending / "certified_b3" / relative)
    require(helper.source_manifest(run) == inventory, "B3 original raw SDK changed during archive")
    run_id = certificate["sdk_run_id"]
    manifest = {"schema": "model_v3_certified_B3_archive_v7", "job_id": "4520487", "source_evaluation_job_id": certificate["evaluation_job_id"],
        "slurm_state": "COMPLETED", "exit_code": "0:0", "source_attachments": references,
        "additional_bound_inputs": list(bound_inputs.values()),
        "SDK_runs": [{"run_id": run_id, "source_run": str(run), "source_files": inventory}],
        "native_history_certificate": certificate_ref, "native_packets": certificate["native_records"], "history_rows": certificate["history_rows"],
        "raw_SDK_not_rescanned_with_legacy_50000_limit": True, "existing_verifier_sha256": B3_VERIFY_SHA,
        "source_core_verification_flag_preserved": certificate["original_core_verification_flag"],
        "reference_kind": "historical_sanity_only", "H0_dimension": 384, "targets_opened_or_recomputed": 0,
        "original_files_preserved": True, "scientific_acceptance": False, "online_sync_performed": False}
    return manifest, [{"job_id": "4520487", "run_id": run_id, "name": "B3 independently verified historical384 sanity / evaluation4520437",
                       "slurm_state": "COMPLETED", "exit_code": "0:0", "offline_unsynced": True}]


def recheck_manifest(helper, manifest, target):
    for reference in (*manifest["source_attachments"], *manifest.get("additional_bound_inputs", ())):
        require(file_ref(reference["path"]) == reference, "Existing archive original attachment changed")
    for sdk in manifest["SDK_runs"]:
        require(helper.source_manifest(Path(sdk["source_run"])) == sdk["source_files"], "Existing archive original SDK changed")
    for reference in manifest["archived_files"]:
        relative = Path(reference["relative_path"])
        require(not relative.is_absolute() and ".." not in relative.parts, "Invalid existing archive member path")
        current = file_ref(target / relative)
        require((current["bytes"], current["sha256"]) == (reference["bytes"], reference["sha256"]), "Existing archive copied bytes differ")


def verify_source_pins(path, expected_sha):
    value, reference = read_json(path)
    require(reference["sha256"] == expected_sha and value["schema"] == "model_v3_archive_closed_sources_v7", "Archive source inventory differs")
    for item in value["files"]:
        require(file_ref(item["path"]) == item, "Archive frozen implementation source differs")
    return value, reference


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quota-closed-receipt", type=Path, required=True)
    parser.add_argument("--quota-closed-sha256", required=True)
    parser.add_argument("--source-pins", type=Path, required=True)
    parser.add_argument("--source-pins-sha256", required=True)
    parser.add_argument("--expected-node", required=True)
    parser.add_argument("--expected-partition", default="cpu")
    parser.add_argument("--jobs", nargs="+", choices=(*CASES, "4520487"), default=[*CASES, "4520487"])
    args = parser.parse_args()
    require(os.getuid() == 1278 and os.environ.get("SLURM_JOB_ID") and int(os.environ.get("SLURM_CPUS_PER_TASK", "0")) >= 16,
            "Owned>=16CPU Slurm allocation required")
    require(socket.gethostname().split(".")[0] == args.expected_node and os.environ.get("SLURM_JOB_PARTITION") == args.expected_partition
            and args.expected_partition == "cpu" and args.expected_node not in {"compute-0-20", "compute-0-21", "compute-0-22"}
            and os.environ.get("CUDA_VISIBLE_DEVICES") == "", "Expected CPU-only node/partition/hidden-GPU binding differs")
    source_pins, source_ref = verify_source_pins(args.source_pins, args.source_pins_sha256)
    require(file_ref(HELPER)["sha256"] == HELPER_SHA, "Fixed archive helper differs")
    spec = importlib.util.spec_from_file_location("fixed_archive_helper_v7", HELPER)
    helper = importlib.util.module_from_spec(spec); spec.loader.exec_module(helper)
    jobs = [(job, *CASES[job][1:3]) if job in CASES else (job, "COMPLETED", "0:0") for job in args.jobs]
    if "4520487" in args.jobs:
        jobs.append(("4520437", "COMPLETED", "0:0"))
    if "4520513" in args.jobs or "4520514" in args.jobs:
        jobs.extend((job, "COMPLETED", "0:0") for job in ("4520513", "4520514"))
    check_receipt(args.quota_closed_receipt, args.quota_closed_sha256, jobs)
    DEST.mkdir(mode=0o700, parents=True, exist_ok=True); helper.owned(DEST, True)
    lock_path = DEST / ".archive.lock"
    descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    lock_info = helper.owned(lock_path)
    require((os.fstat(descriptor).st_dev, os.fstat(descriptor).st_ino) == (lock_info.st_dev, lock_info.st_ino), "Task archive lock identity changed")
    with os.fdopen(descriptor, "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        index_path = DEST / "index.json"
        old = read_json(index_path)[0] if index_path.exists() else {"entries": [], "errors": []}
        root = DEST / "closed_v7"; root.mkdir(mode=0o700, exist_ok=True); helper.owned(root, True)
        processed = []
        for job in dict.fromkeys(args.jobs):
            receipt, receipt_ref = check_receipt(args.quota_closed_receipt, args.quota_closed_sha256, jobs)
            target = root / ("job" + job)
            if target.exists():
                helper.owned(target, True)
                manifest = read_json(target / "manifest.json")[0]
                require(manifest["job_id"] == job and manifest["archive_source_pins"] == source_ref, "Existing archive implementation identity differs")
                recheck_manifest(helper, manifest, target)
                entries = manifest["task_index_entries"]
            else:
                pending = root / (".job"+job+".archive_job"+os.environ["SLURM_JOB_ID"]+".pending")
                pending.mkdir(mode=0o700, exist_ok=False)
                manifest, entries = make_b3_case(helper, pending) if job == "4520487" else make_case(helper, job, pending)
                for row in entries:
                    row["path"] = str(target.relative_to(ARCHIVE))
                manifest.update(archive_helper_sha256=HELPER_SHA, archive_source_pins=source_ref,
                    quota_closed_receipt=receipt_ref, actual_closed_job_lines={j: receipt["closed_jobs"][j] for j, _, _ in jobs},
                    task_index_entries=entries)
                helper.atomic_json(pending / "manifest.json", manifest)
                links = ''.join('<li><a href="sdk_exports/'+html.escape(row["run_id"])+'/index.html">'+html.escape(row["name"])+'</a></li>' for row in entries)
                if job == "4520487":
                    links = '<li><a href="certified_b3/report/B3_REPORT.md">B3 compact report</a></li><li><a href="certified_b3/native_sdk/verification.json">existing native certificate</a></li><li><a href="certified_b3/native_sdk/history.scalars.jsonl">complete56738-row normalized history</a></li>'
                helper.atomic_bytes(pending / "index.html", ('<!doctype html><meta charset="utf-8"><h1>'+html.escape(job)+' archive</h1><p>Offline unsynced; original Slurm state '+html.escape(manifest["slurm_state"]+' '+manifest["exit_code"])+'. No scientific acceptance inferred.</p><ul>'+links+'</ul><a href="manifest.json">Source manifest</a>').encode())
                items = list(pending.rglob("*")); require(len(items) <= 10000, "Case archive entry budget exceeded")
                for path in items:
                    helper.owned(path, path.is_dir())
                require(sum(path.stat().st_size for path in items if path.is_file()) <= 256 << 20, "Case archive exceeds256MiB")
                manifest["archived_files"] = [{"relative_path": str(path.relative_to(pending)),
                    **{key: value for key, value in file_ref(path).items() if key != "path"}}
                    for path in items if path.is_file() and path.name != "manifest.json"]
                helper.atomic_json(pending / "manifest.json", manifest)
                require(sum(path.stat().st_size for path in pending.rglob("*") if path.is_file()) <= 256 << 20,
                        "Final manifest exceeded256MiB case cap")
                check_receipt(args.quota_closed_receipt, args.quota_closed_sha256, jobs)
                verify_source_pins(args.source_pins, args.source_pins_sha256)
                os.rename(pending, target)
            old = {**old, "entries": merge_entries(old["entries"], entries), "offline_unsynced": True,
                   "updated_Asia_Shanghai": helper.stamp(), "errors": old.get("errors", [])}
            helper.atomic_json(index_path, old)
            links = ''.join('<li><a href="../'+html.escape(row["path"])+'/index.html">'+html.escape(row["name"]+' / '+row["job_id"]+' / '+row["run_id"])+'</a></li>' for row in old["entries"])
            helper.atomic_bytes(DEST / "index.html", ('<!doctype html><meta charset="utf-8"><h1>模型v3离线归档</h1><p>Originals preserved. Offline unsynced. Failed jobs retain actual terminal state; synthetic and historical diagnostics do not establish primary-model acceptance.</p><ul>'+links+'</ul>').encode())
            processed.append(job)
        verify_source_pins(args.source_pins, args.source_pins_sha256)
        print(json.dumps({"status": "ARCHIVED", "processed_jobs": processed, "total_index_entries": len(old["entries"]), "online_sync_performed": False}))


if __name__ == "__main__":
    main()
