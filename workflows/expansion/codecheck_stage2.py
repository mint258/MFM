"""Persist bounded synthetic checks and exact source pins on a compute node."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

from .common import dump_new, external_output, reference, require, require_compute


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--tests-only", action="store_true", help="Explicit default: static checker runs separately on sonmi")
    mode.add_argument("--with-sourcechecker", action="store_true", help="Only if this compute environment actually has git")
    args = parser.parse_args()
    node = require_compute()
    root = Path(__file__).absolute().parents[2]
    out = external_output(args.output)
    out.mkdir(parents=True)
    files = sorted((root / "workflows/expansion").glob("*.py"))
    before = [reference(p) for p in files]
    dump_new(out / "sources_before.json", before)
    commands = [
        [sys.executable, "-B", "-m", "unittest", "workflows.expansion.test_preparation",
         "workflows.expansion.test_exact_and_external", "workflows.expansion.test_external_io", "-v"],
    ]
    if args.with_sourcechecker:
        require(shutil.which("git") is not None, "No git on this compute node; use --tests-only and run the unchanged checker on sonmi")
        commands.append([sys.executable, "-B", "tools/check_repository.py"])
    results = []
    for i, argv in enumerate(commands):
        began = time.monotonic()
        run = subprocess.run(argv, cwd=root, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, text=True, timeout=180, check=False)
        log = out / ("tests.log" if i == 0 else "repository_check.log")
        with log.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(run.stdout)
            stream.flush(); os.fsync(stream.fileno())
        results.append({"argv": argv, "returncode": run.returncode, "seconds": time.monotonic() - began,
                        "skipped_lines": len(re.findall(r"\.\.\. skipped ", run.stdout)), "log": reference(log)})
    after = [reference(p) for p in files]
    dump_new(out / "sources_after.json", after)
    passed = before == after and all(r["returncode"] == 0 and r["skipped_lines"] == 0 for r in results)
    state = "NOT_PASS" if not passed else "PASS" if args.with_sourcechecker else "UNIT_TESTS_PASS_STATIC_CHECK_PENDING"
    result = {"schema": "expansion_stage2_synthetic_code_validation_v1", "status": state,
        "hostname": node, "python_logical_entry": sys.executable, "sources_unchanged": before == after,
        "results": results, "real_molecular_data_used": False, "quantum_calls": 0,
        "repository_check_completed_here": args.with_sourcechecker,
        "required_separate_static_check": None if args.with_sourcechecker else "Run unmodified python -B tools/check_repository.py on sonmi; retain actual receipt before commit"}
    dump_new(out / "summary.json", result)
    print(json.dumps(result, indent=2))
    require(passed, "Synthetic code checks did not close; preserve original logs")


if __name__ == "__main__":
    main()
