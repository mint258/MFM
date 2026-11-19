"""Receive official source assets over SSH when compute-node HTTPS is unavailable."""
import argparse
import base64
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from .acquire import quota_headroom, safe_asset, guard


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--plan", type=Path, required=True)
    p.add_argument("--dataset", default="MoleculeACE")
    p.add_argument("--concurrent-reserve-bytes", type=int, required=True)
    a = p.parse_args()
    plan = json.loads(a.plan.read_text())
    source = plan["assets"][a.dataset]
    expected = {safe_asset(x): x for x in source["files"]}
    root = Path(plan["data_root"])
    ancestor = root
    while not ancestor.exists():
        ancestor = ancestor.parent
    q = subprocess.check_output(["ssh", "-n", "-o", "BatchMode=yes",
        "-o", "ConnectTimeout=10", "sonmi", "quota", "-v", "-u", "zixiao"],
        text=True, timeout=60)
    left = quota_headroom(q, os.getuid())
    observed = time.monotonic()
    peak = sum(x["bytes"] for x in expected.values()) * 2 + 1048576
    guard(ancestor, peak, left, observed, a.concurrent_reserve_bytes)
    folder = root / "raw" / a.dataset
    folder.mkdir(parents=True, exist_ok=True)
    received = {}
    for line in sys.stdin:
        msg = json.loads(line)
        name = msg["name"]
        asset = expected[name]
        if name in received:
            raise ValueError("duplicate asset frame")
        data = base64.b64decode(msg["data"], validate=True)
        if len(data) != asset["bytes"]:
            raise ValueError("asset transport length differs")
        guard(folder, peak, left, observed, a.concurrent_reserve_bytes)
        target = folder / name
        if target.exists():
            if target.stat().st_size != len(data):
                raise ValueError("preserve mismatched existing file: " + str(target))
            status = "EXISTING_CLOSED_SIZE_MATCH"
        else:
            with target.open("xb") as f:
                f.write(data)
            left -= len(data)
            status = "DOWNLOADED_VIA_SSH"
        received[name] = dict(asset, path=str(target), status=status)
        print("CLOSED", name, len(data), flush=True)
    if set(received) != set(expected):
        raise ValueError("incomplete source batch; retain closed prefix")
    guard(root, 1048576, left, observed, a.concurrent_reserve_bytes)
    manifest = root / "acquisition" / (a.dataset + ".json")
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps({
        "status": "SOURCE_ASSETS_ACQUIRED", "source_commit": source["source_commit"],
        "files": list(received.values()), "files_count": len(received),
        "declared_bytes": sum(x["bytes"] for x in received.values()),
        "transport": "official HTTPS to client memory, guarded SSH receiver on compute-0-16",
        "numerical_payload_readback": False, "new_content_hashes": False,
        "filtering_or_training_ready": False
    }, indent=2) + "\n")
    print("MANIFEST", manifest, flush=True)


if __name__ == "__main__":
    main()
