"""Run all core test files in bounded, independent CPU processes."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import xml.etree.ElementTree as ET


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--code-commit", required=True)
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--partitions", type=int, default=1)
    parser.add_argument("--partition-index", type=int, default=0)
    parser.add_argument("--expected-node", choices=tuple("compute-0-"+str(i) for i in (2, *range(8, 20))),
                        required=True,
                        help="Explicit CPU node; user reserves GPU nodes for GPU work")
    args = parser.parse_args()
    if not os.environ.get("SLURM_JOB_ID") or socket.gethostname().split(".")[0] != args.expected_node:
        raise RuntimeError("Regression needs its own Slurm allocation on the explicitly expected node")
    if not 1 <= args.workers <= int(os.environ["SLURM_CPUS_PER_TASK"]):
        raise ValueError("Worker count exceeds the actual allocation")
    root, out = args.root.absolute(), args.output.absolute()
    out.mkdir(parents=True, exist_ok=False)
    files = sorted((root / "current/tests").glob("test_*.py"))
    if not files:
        raise RuntimeError("No core test files found")
    all_files = list(files)
    if not 0 <= args.partition_index < args.partitions <= min(8, len(files)):
        raise ValueError("Invalid bounded regression partition")
    if args.partitions > 1:
        partitions, weights = [[] for _ in range(args.partitions)], [0] * args.partitions
        for path in sorted(files, key=lambda p: (-p.stat().st_size, p.name)):
            chosen = min(range(args.partitions), key=lambda i: (weights[i], i))
            partitions[chosen].append(path)
            weights[chosen] += path.stat().st_size
        files = sorted(partitions[args.partition_index])
    workers = min(args.workers, len(files))
    # Size-balanced assignment avoids putting every large parametrized module
    # into the same worker while preserving a reproducible assignment.
    groups, sizes = [[] for _ in range(workers)], [0] * workers
    for path in sorted(files, key=lambda p: (-p.stat().st_size, p.name)):
        group = min(range(workers), key=lambda i: (sizes[i], i))
        groups[group].append(path)
        sizes[group] += path.stat().st_size

    def run(index):
        log, xml = out / f"shard_{index:02d}.log", out / f"shard_{index:02d}.xml"
        argv = [sys.executable, "-B", "-m", "pytest", *(str(p) for p in groups[index]),
                "-q", "-p", "no:cacheprovider", f"--junitxml={xml}",
                f"--basetemp={out / ('tmp_' + str(index))}"]
        started = time.monotonic()
        with log.open("wb") as stream:
            process = subprocess.run(argv, cwd=root / "current", stdin=subprocess.DEVNULL,
                                     stdout=stream, stderr=subprocess.STDOUT, check=False)
        counts = dict(tests=0, failures=0, errors=0, skipped=0)
        if xml.exists():
            tree = ET.parse(xml).getroot()
            suites = list(tree.iter("testsuite"))
            for suite in suites:
                for key in counts:
                    counts[key] += int(suite.attrib.get(key, 0))
        row = {"shard": index, "returncode": process.returncode,
               "elapsed_seconds": time.monotonic() - started, "argv": argv,
               "files": [str(p.relative_to(root)) for p in groups[index]], "counts": counts}
        (out / f"shard_{index:02d}.json").write_text(json.dumps(row, indent=2) + "\n")
        print(json.dumps({"shard": index, "returncode": process.returncode, "counts": counts}), flush=True)
        return row

    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=workers) as executor:
        rows = list(executor.map(run, range(workers)))
    total = {key: sum(row["counts"][key] for row in rows) for key in ("tests", "failures", "errors", "skipped")}
    result = {"status": "PASS" if all(r["returncode"] == 0 for r in rows) else "FAIL",
              "node": socket.gethostname(), "job_id": os.environ["SLURM_JOB_ID"],
              "expected_node": args.expected_node,
              "partitions": args.partitions, "partition_index": args.partition_index,
              "all_test_file_sha256": {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in all_files},
              "code_commit": args.code_commit, "test_file_count": len(files),
              "test_source_sha256": {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
              "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "workers": workers, "elapsed_seconds": time.monotonic() - started,
              "counts": total, "shards": rows}
    (out / "summary.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "counts": total}), flush=True)
    return int(result["status"] != "PASS")


if __name__ == "__main__":
    raise SystemExit(main())
