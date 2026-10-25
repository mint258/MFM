"""Root-only adapter for the explicitly approved 336-molecule 32GiB pilot.

Only preparation of this adapter is authorized to SB2. Root reviews and executes
it. The old registered submission controller is imported by exact SHA unchanged.
"""
from __future__ import annotations

import argparse
import datetime
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

sys.dont_write_bytecode = True
from live_memory_policy_32g_v1 import (ALLOWED_NODES, BASIS, OLD_SOURCE_SHA, evaluate_memory,
                                      file_reference, parse_meminfo, require_reference,
                                      validate_approval_payload, validate_root_intent)

CONTROLLER = Path("/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository/workflows/data_v1_final/execution/submit_reviewed.py")
CONTROLLER_SHA = "6d1e3f5623bcdf04351d50710ccc81b5ca50f23d3b19051cba29f6fee173ee7f"


def load_controller():
    if hashlib.sha256(CONTROLLER.read_bytes()).hexdigest() != CONTROLLER_SHA:
        raise ValueError("REGISTERED_ROOT_CONTROLLER_SHA_CHANGED")
    spec = importlib.util.spec_from_file_location("_dv1_original_submit_reviewed", CONTROLLER)
    controller = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(controller)
    return controller


def validate_32g_request(controller, request):
    # Prevent any source guard from reading GiB assets on the login node.
    if any(int(ref["bytes"]) > 2 * 1024 ** 2 for ref in [request["script_reference"]] + request["source_references"]):
        raise ValueError("ONLY_SMALL_SOURCE_AND_AUTHORITY_RECEIPTS_IN_LOGIN_SOURCE_GUARD")
    for ref in [request["script_reference"]] + request["source_references"]:
        actual_size = Path(ref["path"]).stat().st_size
        if actual_size > 2 * 1024 ** 2 or actual_size != int(ref["bytes"]):
            raise ValueError("SOURCE_ACTUAL_SIZE_MUST_MATCH_SMALL_REFERENCE_BEFORE_READ")
    name = controller.validate_request(request)
    if not name.startswith("dv1_sb2_fill_32g_") or request.get("memory_basis") != BASIS:
        raise ValueError("ONLY_THE_NAMED_32G_SB2_PILOT_IS_ALLOWED")
    if (request.get("cpus"), request.get("memory_gib"), request.get("wall_seconds"), request.get("kind")) != (16, 32, 14400, "conformer") or request.get("pilot") is not True:
        raise ValueError("ONLY_336_PILOT_16CPU_32G_4H_NO_FULL_OR_PPRIME")
    approval_ref = request["approval_reference"]
    approval = json.loads(require_reference(approval_ref).read_text())
    scope = approval["scope"]
    config_ref, prepared_ref = scope["config_reference"], scope["prepared_reference"]
    require_reference(config_ref)
    require_reference(prepared_ref)
    validate_approval_payload(approval, config_ref, prepared_ref)
    if approval_ref not in request["source_references"]:
        raise ValueError("ACTUAL_APPROVAL_MUST_BE_A_PINNED_SOURCE")
    if config_ref not in request["source_references"] or prepared_ref not in request["source_references"]:
        raise ValueError("ORIGINAL_336_INPUTS_MUST_BE_PINNED")
    for name_expected in ("run_pilot_live_memory_32g_v1.py", "live_memory_policy_32g_v1.py"):
        ref = file_reference(Path(__file__).parent / name_expected)
        if ref not in request["source_references"]:
            raise ValueError("NEW_32G_SOURCE_NOT_PINNED:" + name_expected)
    for name_expected, expected_sha in OLD_SOURCE_SHA.items():
        ref = file_reference(Path(__file__).parent / name_expected)
        if ref["sha256"] != expected_sha or ref not in request["source_references"]:
            raise ValueError("UNCHANGED_CHEMISTRY_AND_OUTPUT_SOURCE_MUST_BE_PINNED:" + name_expected)
    if file_reference(__file__) not in request["source_references"]:
        raise ValueError("THIS_ROOT_ADAPTER_MUST_BE_PINNED")
    return name, approval_ref, config_ref, prepared_ref


def live_node_sample(controller, node, real_memory_mib):
    if node not in ALLOWED_NODES:
        raise ValueError("UNAUTHORIZED_NODE")
    prefix = ["ssh", "-n", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes", node]
    hostname = controller.query(prefix + ["hostname"]).strip().split(".")[0]
    if hostname != node:
        raise ValueError("NODE_SSH_HOSTNAME_MISMATCH")
    raw = controller.query(prefix + ["cat", "/proc/meminfo"])
    observed = time.time()
    sample = evaluate_memory(parse_meminfo(raw), int(real_memory_mib) * 1024 ** 2, 0)
    if not sample["dispatch_allowed"]:
        raise ValueError("WAIT_FOR_LIVE_NODE_MEMORY_32G_PLUS_85_PERCENT")
    return {"observed_epoch": observed, "hostname": hostname, "raw_meminfo": raw, "sample": sample}


def submit_once(controller, request, record, intent, receipt):
    """Persist intent once, then persist actual ID before any readback may fail."""
    name, node = request["script_reference"]["path"], request["node"]
    controller.write_new(intent, record)
    argv = ["sbatch", "--parsable", "--chdir=" + str(controller.PROJECT), name]
    try:
        process = subprocess.run(argv, cwd=controller.PROJECT, stdin=subprocess.DEVNULL,
                                 capture_output=True, text=True, timeout=45)
        record.update(sbatch_argv=argv, sbatch_returncode=process.returncode,
                      stdout=process.stdout, stderr=process.stderr)
    except subprocess.TimeoutExpired:
        record.update(sbatch_argv=argv, status="SUBMISSION_OUTCOME_UNKNOWN_NO_AUTOMATIC_RETRY")
        controller.write_new(receipt, record)
        raise
    if process.returncode == 0:
        job_id = process.stdout.strip().split(";")[0]
        if not job_id.isdecimal():
            record["status"] = "UNRECOGNIZED_SUBMISSION_RESPONSE_NO_AUTOMATIC_RETRY"
            controller.write_new(receipt, record)
            raise RuntimeError("Unrecognized sbatch response; inspect immutable receipt")
        record.update(job_id=job_id, status="SUBMITTED_NOT_COMPLETED")
    else:
        record["status"] = "SUBMISSION_FAILED_NO_AUTOMATIC_RETRY"
    controller.write_new(receipt, record)
    if process.returncode:
        raise RuntimeError("Slurm rejected request; inspect preserved receipt")
    verification = {"job_id": job_id, "receipt_reference": controller.file_ref(receipt)}
    verification_path = receipt.with_name(receipt.stem + ".verification.json")
    try:
        actual = controller.query(["scontrol", "show", "job", job_id, "--oneliner"])
        verification["actual_job_metadata"] = actual
        info = controller.fields(actual)
        if info["WorkDir"] != str(controller.PROJECT) or info["ReqNodeList"] != node or int(info["NumCPUs"]) != 16:
            raise ValueError("POST_SUBMISSION_JOB_METADATA_MISMATCH")
        if controller.memory_mib(info["MinMemoryNode"]) != 32 * 1024:
            raise ValueError("POST_SUBMISSION_JOB_MEMORY_NOT_32_GIB")
        verification["status"] = "SUBMITTED_JOB_METADATA_VERIFIED"
    except Exception as exc:
        verification.update(status="POST_SUBMISSION_VERIFICATION_FAILED_NO_AUTOMATIC_RETRY",
                            exception_type=type(exc).__name__, exception=str(exc))
        controller.write_new(verification_path, verification)
        raise
    controller.write_new(verification_path, verification)
    return job_id


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    args = parser.parse_args()
    if os.getuid() != 1278 or socket.gethostname().split(".")[0] != "sonmi":
        raise ValueError("ROOT_LOGIN_METADATA_COORDINATOR_ONLY")
    controller = load_controller()
    request = json.loads(args.request.read_text())
    name, approval_ref, config_ref, prepared_ref = validate_32g_request(controller, request)
    node_name = request["node"]
    submissions = controller.ROOT / "control/submissions"
    submissions.mkdir(parents=True, exist_ok=True)
    intent, receipt = submissions / (name + ".intent.json"), submissions / (name + ".json")
    with (submissions / "root.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if intent.exists() or receipt.exists():
            raise ValueError("REGISTERED_ATTEMPT_EXISTS_NO_AUTOMATIC_RETRY")
        queue = controller.query(["squeue", "-h", "-u", "zixiao", "-o", "%i|%j|%N|%T"])
        if any(line.split("|")[1] == name for line in queue.splitlines()):
            raise ValueError("DUPLICATE_ACTIVE_JOB")
        quota = controller.query(["quota", "-v", "-u", "zixiao"])
        free = controller.quota_available_bytes(quota)
        if free - request["estimated_peak_output_bytes"] < 200_000_000_000:
            raise ValueError("QUOTA_RESERVE_WOULD_FALL_BELOW_200GB")
        sinfo = controller.query(["sinfo", "--Node", "--nodes=" + node_name, "--noheader", "--format=%N|%P|%t|%C|%m"])
        node_raw = controller.query(["scontrol", "show", "node", node_name, "--oneliner"])
        node = controller.fields(node_raw)
        if int(node["CPUTot"]) - int(node["CPUAlloc"]) < 16:
            raise ValueError("WAIT_FOR_16_FREE_CPUS")
        ids = controller.query(["squeue", "-h", "-w", node_name, "-t", "RUNNING,COMPLETING", "-o", "%i"])
        declared, jobs, unknown = 0.0, [], []
        for job_id in ids.split():
            raw = controller.query(["scontrol", "show", "job", job_id, "--oneliner"])
            job = controller.fields(raw)
            if "MinMemoryNode" in job:
                memory = controller.memory_mib(job["MinMemoryNode"])
            elif "MinMemoryCPU" in job:
                memory = controller.memory_mib(job["MinMemoryCPU"]) * int(job["NumCPUs"])
            else:
                raise ValueError("ALL_USER_MEMORY_DECLARATION_UNAVAILABLE")
            if memory == 0:
                unknown.append(job_id)
                memory = float(node["RealMemory"])  # retain unknown as unbounded, never as zero usage
            declared += memory
            jobs.append({"job_id": job_id, "metadata": raw, "memory_mib_budgeted_on_node": memory})
        # Original CPU/pin/SBATCH/Root-review checks run again. This never edits the old controller.
        validate_32g_request(controller, request)
        memory_observation = live_node_sample(controller, node_name, node["RealMemory"])
        record = {"observed_at": datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
                  "uid": os.getuid(), "request_reference": controller.file_ref(args.request), "request": request,
                  "queue_before": queue, "quota_raw": quota, "account_free_bytes": free,
                  "sinfo": sinfo, "node_metadata": node_raw, "existing_jobs_all_users": jobs,
                  "committed_memory_mib": max(float(node["AllocMem"]), declared),
                  "unknown_memory_job_ids": unknown, "memory_basis": BASIS,
                  "node_live_memory_observation": memory_observation,
                  "formal_generation_uses_original_hardware_requirements": True,
                  "registered_controller": {"path": str(CONTROLLER), "sha256": CONTROLLER_SHA}}
        validate_root_intent(record, approval_ref, config_ref, prepared_ref, node=node_name, now_epoch=time.time())
        if time.time() - memory_observation["observed_epoch"] > 2:
            raise ValueError("LIVE_NODE_MEMORY_OBSERVATION_STALE_BEFORE_SBATCH")
        job_id = submit_once(controller, request, record, intent, receipt)
        print(json.dumps({"job_id": job_id, "status": record["status"], "receipt": str(receipt)}))


if __name__ == "__main__":
    main()
