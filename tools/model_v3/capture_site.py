"""Capture read-only scheduler, account quota and GPU inventory metadata."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
import datetime as dt
import json
import os
from pathlib import Path
import socket
import subprocess


def query(argv):
    try:
        run = subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True,
                             text=True, timeout=30, check=False)
        return {"argv": argv, "returncode": run.returncode,
                "stdout": run.stdout, "stderr": run.stderr}
    except subprocess.TimeoutExpired:
        return {"argv": argv, "error": "TIMEOUT_30_SECONDS"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if socket.gethostname().split(".")[0] != "sonmi" or os.getuid() != 1278:
        raise RuntimeError("Use the established development-server login account")
    nodes = [f"compute-0-{i}" for i in (*range(8), 20, 21, 22)]
    commands = [["quota", "-v", "-u", "zixiao"],
                ["sinfo", "--Node", "-o", "%N %P %t %c %m %G"],
                ["squeue", "-h", "-o", "%i|%u|%j|%T|%C|%m|%N"],
                ["scontrol", "show", "partition"],
                ["df", "-Pk", "/share/home/zixiao/descriptor_analysis"],
                ["df", "-Pi", "/share/home/zixiao/descriptor_analysis"]]
    for node in nodes:
        commands.append(["ssh", "-n", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes", node,
                         "nvidia-smi --query-gpu=uuid,name,memory.total,memory.free --format=csv,noheader,nounits"])
        commands.append(["scontrol", "show", "node", node])
    with ThreadPoolExecutor(max_workers=6) as executor:
        rows = list(executor.map(query, commands))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"captured_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
                                      "uid": os.getuid(), "node": socket.gethostname(),
                                      "read_only": True, "observations": rows}, indent=2) + "\n")
    print(json.dumps({"observations": len(rows), "failures": sum(r.get("returncode", 1) != 0 for r in rows)}))


if __name__ == "__main__":
    main()
