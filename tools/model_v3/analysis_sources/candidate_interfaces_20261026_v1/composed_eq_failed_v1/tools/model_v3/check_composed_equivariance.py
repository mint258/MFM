#!/usr/bin/env python3
"""Source-bound complete composed FP32 checks; Root owns CPU/GPU admission."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import time
import traceback
import xml.etree.ElementTree as ET

sys.dont_write_bytecode = True
ROOT = Path(__file__).absolute().parents[2]
sys.path.insert(0, str(ROOT/"current"))

import torch

from phychem_mfm.phase1.v3_contract import canonical_hash, require
from phychem_mfm.phase1.v3_composed_equivariance import (
    BASE_REVISION, CASE_SPECS, LEGACY_CUDA_NODES, SCHEMA, execution_source_inventory,
    measure_case, protocol,
)


MAX_OUTPUT_BYTES = 32*1024**2


def write_json(path, value):
    raw = (json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, indent=2)+"\n").encode("utf-8")
    require(len(raw) <= 8*1024**2, "Bounded metadata file required")
    pending = path.with_suffix(path.suffix+".pending")
    require(not path.exists() and not pending.exists(), "Never overwrite an earlier result")
    with pending.open("xb") as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    os.replace(pending, path)


def source_request(device, expected_node, *, gpu_uuid=None, threads=1):
    require(device in ("cpu", "cuda:0") and type(threads) is int and threads > 0, "Explicit device/thread policy required")
    require(re.fullmatch(r"compute-0-[0-9]+", expected_node), "Actual planned node name required")
    if device == "cpu":
        require(re.fullmatch(r"compute-0-(?:2|[89]|1[0-9])", expected_node) and gpu_uuid is None,
                "Pure CPU checks use a site CPU node, never a GPU-node fallback")
    else:
        require(type(gpu_uuid) is str and re.fullmatch(r"GPU-[0-9a-fA-F-]{36}", gpu_uuid), "Full assigned GPU UUID required")
    sources = execution_source_inventory(ROOT)
    return {"schema": SCHEMA+"_request", "status": "FROZEN_NOT_EXECUTED", "source_repository": str(ROOT),
        "base_revision": BASE_REVISION, "source_files": sources, "source_inventory_sha256": canonical_hash(sources),
        "protocol": protocol(), "protocol_sha256": canonical_hash(protocol()), "device": device,
        "expected_node": expected_node, "gpu_uuid": gpu_uuid, "intraop_threads": threads,
        "case_ids": [case.identity for case in CASE_SPECS], "expected_composed_cases": 48,
        "legacy_cuda_test_nodes": list(LEGACY_CUDA_NODES) if device == "cuda:0" else [],
        "expected_legacy_cuda_cases": 2 if device == "cuda:0" else 0,
        "maximum_output_bytes": MAX_OUTPUT_BYTES, "no_native_dataset_or_checkpoint_inputs": True,
        "admission": "Root Slurm allocation, UUID lock, actual resources/quota and 85% memory supervision remain required"}


def read_request(path, sha256):
    raw = Path(path).read_bytes()
    require(len(raw) <= 1024**2 and hashlib.sha256(raw).hexdigest() == sha256, "Frozen request raw SHA differs")
    value = json.loads(raw)
    expected = source_request(value["device"], value["expected_node"], gpu_uuid=value["gpu_uuid"], threads=value["intraop_threads"])
    require(value == expected, "Full source/config/case/request identity differs from this executing tree")
    return value


def admit_runtime(request):
    host = socket.gethostname().split(".")[0]
    require(host == request["expected_node"] == os.environ.get("SLURMD_NODENAME", host)
            and os.environ.get("SLURM_JOB_ID", "").isdigit()
            and int(os.environ.get("SLURM_CPUS_PER_TASK", "0")) >= 16,
            "Actual owned Slurm node/at-least-16CPU allocation required; never run on login")
    if request["device"] == "cpu":
        require(os.environ.get("CUDA_VISIBLE_DEVICES") in ("", "-1"), "CPU check must explicitly hide CUDA")
        return {"node": host, "job_id": os.environ["SLURM_JOB_ID"], "device": "cpu", "gpu_uuid": None}
    require(os.environ.get("CUDA_VISIBLE_DEVICES") == request["gpu_uuid"], "Scheduler-visible GPU UUID differs")
    require(torch.cuda.is_available() and torch.cuda.device_count() == 1, "Actual single visible CUDA device required; cannot skip")
    prop = torch.cuda.get_device_properties(0)
    require(str(prop.uuid) == request["gpu_uuid"], "Actual CUDA-visible UUID differs from frozen Root assignment")
    return {"node": host, "job_id": os.environ["SLURM_JOB_ID"], "device": "cuda:0",
        "gpu_uuid": str(prop.uuid), "gpu_name": prop.name, "cuda": torch.version.cuda}


def output_bytes(root):
    total = 0
    for path in root.rglob("*"):
        require(not path.is_symlink(), "This bounded result layout has no SDK/symlink outputs")
        if path.is_file(): total += path.stat().st_size
    require(total <= MAX_OUTPUT_BYTES, "Declared whole-job output budget exceeded")
    return total


def run_legacy_cuda_tests(output):
    """Execute the two previously skipped native tests, then reject any skip."""
    xml = output/"legacy_cuda.xml"
    argv = [sys.executable, "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider", *LEGACY_CUDA_NODES,
        "--junitxml", str(xml), "--basetemp", str(output/"legacy_pytest_tmp")]
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT/"current")
    result = subprocess.run(argv, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=300)
    (output/"legacy_cuda.stdout.txt").write_bytes(result.stdout)
    (output/"legacy_cuda.stderr.txt").write_bytes(result.stderr)
    cases = []
    if xml.is_file():
        for case in ET.parse(xml).getroot().iter("testcase"):
            cases.append({"name": case.get("name"), "class_name": case.get("classname"),
                "skipped": case.find("skipped") is not None,
                "failed": case.find("failure") is not None or case.find("error") is not None})
    expected = {node.split("::")[1] for node in LEGACY_CUDA_NODES}
    passed = result.returncode == 0 and len(cases) == 2 and {c["name"] for c in cases} == expected
    passed = passed and all(not c["skipped"] and not c["failed"] for c in cases)
    return {"argv": argv, "exit_code": result.returncode, "cases": cases, "required_cases": 2,
        "status": "PASS_ACTUAL_CUDA_NO_SKIP" if passed else "FAILED_OR_SKIPPED", "passed": passed,
        "stdout_sha256": hashlib.sha256(result.stdout).hexdigest(), "stderr_sha256": hashlib.sha256(result.stderr).hexdigest()}


def execute(request, request_path, output):
    runtime = admit_runtime(request)
    require(not output.exists() and not output.is_symlink() and output.parent.is_dir(), "Fresh external owned output directory required")
    # Actual terminal tensors from these public synthetic fixtures stay outside
    # Git. No native inputs, private IDs or parameter weights are exported.
    require(not output.absolute().is_relative_to(ROOT), "Results must remain outside the source repository")
    output.mkdir(mode=0o700)
    started, cases = time.perf_counter(), []
    if request["device"] == "cuda:0": torch.cuda.reset_peak_memory_stats()
    write_json(output/"INPUT_BINDING.json", {"schema": SCHEMA+"_input_binding", "request": {
        "path": str(request_path), "bytes": Path(request_path).stat().st_size,
        "sha256": hashlib.sha256(Path(request_path).read_bytes()).hexdigest()}, "runtime": runtime,
        "executed_source_inventory_sha256": canonical_hash(execution_source_inventory(ROOT)),
        "protocol_sha256": request["protocol_sha256"]})
    for index, spec in enumerate(CASE_SPECS):
        try:
            result = measure_case(spec, device=request["device"], threads=request["intraop_threads"], terminal_output_directory=output)
        except Exception as error:
            result = {"schema": SCHEMA+"_case_exception", "case_id": spec.identity, "case": {
                "distance_bias": spec.distance_bias, "views": spec.views, "head_policy": spec.head_policy, "weight_seed": spec.weight_seed},
                "passed": False, "exception": type(error).__name__, "message": str(error), "traceback": traceback.format_exc()}
            partial = output/(spec.identity+"__terminals.npz")
            if partial.is_file():
                raw_partial = partial.read_bytes()
                result["partial_actual_terminal_output_artifact"] = {"path": str(partial),
                    "bytes": len(raw_partial), "sha256": hashlib.sha256(raw_partial).hexdigest()}
        filename = f"case_{index:02d}_{spec.identity}.json"
        write_json(output/filename, result)
        raw = (output/filename).read_bytes()
        cases.append({"case_id": spec.identity, "passed": result["passed"], "path": filename,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
        output_bytes(output)
        print(json.dumps({"case": index+1, "case_id": spec.identity, "passed": result["passed"]}), flush=True)
    if request["device"] == "cuda:0":
        try:
            legacy = run_legacy_cuda_tests(output)
        except Exception as error:
            legacy = {"passed": False, "status": "EXCEPTION", "message": str(error), "traceback": traceback.format_exc()}
    else:
        legacy = {"passed": True, "status": "NOT_RUN_CPU_REQUEST", "actual_cases": 0,
            "note": "The two old CUDA tests require the separate Root GPU request"}
    write_json(output/"LEGACY_CUDA_TESTS.json", legacy)
    after = execution_source_inventory(ROOT)
    unchanged = after == request["source_files"]
    passed = len(cases) == 48 and all(c["passed"] for c in cases) and legacy["passed"] and unchanged
    result = {"schema": SCHEMA+"_result", "status": "PASS_DECLARED_DOMAIN" if passed else "FAILED_PRESERVED",
        "runtime": runtime, "protocol_sha256": request["protocol_sha256"], "cases": cases,
        "composed_case_count": len(cases), "composed_pass_count": sum(c["passed"] for c in cases),
        "legacy_cuda": legacy, "source_before_after_identical": unchanged,
        "source_before_sha256": request["source_inventory_sha256"], "source_after_sha256": canonical_hash(after),
        "wall_seconds": time.perf_counter()-started, "output_bytes_before_summary": output_bytes(output),
        "native_data_reads": 0, "model_selection_or_pretraining_claim": False,
        "all_real_weights_all_geometries_theorem": False}
    write_json(output/"RESULT.json", result)
    output_bytes(output)
    if passed:
        raw = (output/"RESULT.json").read_bytes()
        write_json(output/"COMPLETE.json", {"schema": SCHEMA+"_complete", "status": result["status"],
            "result": {"path": str(output/"RESULT.json"), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()},
            "composed_case_count": 48, "legacy_cuda_case_count": request["expected_legacy_cuda_cases"],
            "source_before_after_identical": True})
        output_bytes(output)
    return 0 if passed else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    prepare = sub.add_parser("prepare-request")
    prepare.add_argument("--device", choices=("cpu", "cuda:0"), required=True)
    prepare.add_argument("--expected-node", required=True)
    prepare.add_argument("--gpu-uuid")
    prepare.add_argument("--threads", type=int, default=1)
    prepare.add_argument("--output", type=Path, required=True)
    run = sub.add_parser("run")
    run.add_argument("--request", type=Path, required=True)
    run.add_argument("--request-sha256", required=True)
    run.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.action == "prepare-request":
        require(not args.output.absolute().is_relative_to(ROOT), "Frozen requests live outside Git")
        write_json(args.output, source_request(args.device, args.expected_node, gpu_uuid=args.gpu_uuid, threads=args.threads))
        raw = args.output.read_bytes()
        print(json.dumps({"path": str(args.output), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}))
        return 0
    request = read_request(args.request, args.request_sha256)
    return execute(request, args.request, args.output_root)


if __name__ == "__main__":
    raise SystemExit(main())
