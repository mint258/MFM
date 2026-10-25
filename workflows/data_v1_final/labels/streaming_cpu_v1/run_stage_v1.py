"""Same-allocation first MAD0 driver: four CPU fixtures, then one source pass."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from workflows.data_v1_final.execution.cpu_analysis_v1 import policy, runtime

HERE = Path(__file__).parent.absolute()
PYTHON = "/share/home/zixiao/.conda/envs/chemprop/bin/python"


def option(command, key):
    if command.count(key) != 1:
        raise ValueError("ONE_PINNED_SCIENCE_OPTION_REQUIRED")
    return command[command.index(key) + 1]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--science-command", required=True)
    p.add_argument("--boundary-output", required=True)
    p.add_argument("--stage-receipt", required=True)
    p.add_argument("--output", required=True)
    a = p.parse_args()
    intent = os.environ["DATA_V1_CPU_INTENT"]
    proof = runtime.root_guard(intent, a.science_command, 8 * 1024**3, 7200)
    if (proof["request"]["scope_key"] != "label_canonical_512" or HERE != policy.REPO / "workflows/data_v1_final/labels/streaming_cpu_v1"):
        raise ValueError("ONLY_ROOT_CANONICAL_512_INITIAL_DRIVER_ALLOWED")
    command = policy.load(a.science_command)
    if (command[:3] != [PYTHON, "-B", str(HERE / "scan_v2.py")]
            or option(command, "--phase") != "refine" or option(command, "--root-preflight") != intent
            or option(command, "--output") != a.output):
        raise ValueError("EXACT_SINGLE_INITIAL_SOURCE_PASS_REQUIRED")
    query = policy.load(option(command, "--queries"))
    plan = policy.load(option(command, "--plan"))
    if (query["purpose"] != "MAD" or query["round"] != 0 or query["mode"] != "pilot"
            or plan["mode"] != "pilot" or plan["records"] != 4251 or plan["molecules"] != 512
            or len(plan["groups"]) != 16 or query["coverage_fingerprint"] != plan["coverage_fingerprint"]):
        raise ValueError("ONLY_SAME_FIXED_PILOT_MAD_ZERO_WITH_FOUR_BOUNDARIES")
    boundary_path, receipt_path = Path(a.boundary_output), Path(a.stage_receipt)
    if boundary_path.exists() or receipt_path.exists() or Path(a.output).exists():
        raise FileExistsError("INITIAL_STAGE_DESTINATION_EXISTS_NO_RETRY")
    status = "INITIAL_STAGE_FAILED_NO_RETRY"
    code = 1
    failure = None
    boundary = None
    try:
        runtime.checkpoint()
        test = subprocess.run([PYTHON, "-B", str(HERE / "test_boundary.py"), "--output", str(boundary_path)], stdin=subprocess.DEVNULL)
        if test.returncode:
            raise RuntimeError("FOUR_CPU_BOUNDARY_FIXTURES_FAILED")
        boundary = policy.load(boundary_path)
        if boundary["status"] != "PASS" or boundary["tests"] != 4 or boundary["failures"] or boundary["errors"]:
            raise ValueError("ACTUAL_FOUR_BOUNDARIES_NOT_CLOSED_PASS")
        if boundary_path.stat().st_size > 64 * 1024:
            raise ValueError("BOUNDARY_EVIDENCE_BUDGET_EXCEEDED")
        runtime.checkpoint()
        source = subprocess.run(command, stdin=subprocess.DEVNULL)
        code = source.returncode
        status = "BOUNDARY_AND_ONE_SOURCE_PASS_COMPLETED" if code == 0 else "SOURCE_PASS_FAILED_NO_RETRY"
    except BaseException as exc:
        failure = repr(exc)
    result = {"schema": "FIRST_MAD_CPU_STAGE_RECEIPT_V1", "status": status, "job_id": os.environ["SLURM_JOB_ID"],
              "science_command_reference": policy.ref(Path(a.science_command)), "science_command": command,
              "boundary_reference": policy.ref(boundary_path) if boundary_path.exists() else None,
              "boundary_summary": boundary, "source_returncode": code, "failure": failure,
              "tests_repeated": "Only four new CPU boundary fixtures; no old19/24/13 suite", "source_passes_attempted_at_most": 1,
              "forced_signals_sent": False, "automatic_submission_or_retry": False, "final_D4": False}
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode()
    if len(raw) > 64 * 1024:
        raise ValueError("STAGE_RECEIPT_EVIDENCE_BUDGET_EXCEEDED")
    with receipt_path.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return 0 if status == "BOUNDARY_AND_ONE_SOURCE_PASS_COMPLETED" and failure is None else (code or 1)


if __name__ == "__main__":
    raise SystemExit(main())
