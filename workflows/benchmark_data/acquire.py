"""Bounded B0 source acquisition; no scientific recomputation or content hashes."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import time
import urllib.request
from urllib.parse import urlsplit

FLOOR = 100_000_000_000


def quota_headroom(output, uid):
    if not re.search(r"\(uid\s+" + str(uid) + r"\)", output):
        raise ValueError("quota UID mismatch")
    for line in output.splitlines():
        parts = line.split()
        if len(parts) >= 7 and parts[0].startswith("/dev/"):
            used, limit = int(parts[1].rstrip("*")), int(parts[3])
            if limit <= 0 or used > limit:
                raise ValueError("unknown or exceeded hard quota")
            return (limit - used) * 1024
    raise ValueError("no authoritative quota row")


def safe_asset(asset):
    name = asset["name"]
    if Path(name).name != name or name in (".", "..") or "/" in name or "\\" in name:
        raise ValueError("asset name must be a basename")
    parsed = urlsplit(asset["url"])
    if (parsed.scheme != "https" or parsed.hostname not in {
            "raw.githubusercontent.com", "github.com", "huggingface.co", "ndownloader.figshare.com",
            "polarishub.io", "data.polarishub.io", "yzhang.hpc.nyu.edu",
            "dataverse.harvard.edu", "files.pythonhosted.org", "static-content.springer.com"}
            or parsed.username is not None or parsed.password is not None):
        raise ValueError("unexpected acquisition host")
    if not isinstance(asset["bytes"], int) or asset["bytes"] < 0:
        raise ValueError("unknown asset bytes")
    return name


def guard(root, needed, quota_remaining, quota_time, concurrent):
    if __package__:
        from .storage_reservations import current_concurrent
    else:
        from storage_reservations import current_concurrent
    concurrent = current_concurrent(root, concurrent)
    if time.monotonic() - quota_time > 180:
        raise RuntimeError("quota observation expired; refresh before writing")
    free = int(subprocess.check_output(
        ["df", "-B1", "--output=avail", str(root)], text=True).splitlines()[-1])
    stat = os.statvfs(root)
    if free < FLOOR + concurrent + needed or stat.f_favail < 1000:
        raise RuntimeError("disk/inode reserve would be crossed")
    if quota_remaining < FLOOR + concurrent + needed:
        raise RuntimeError("account quota reserve would be crossed")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--dataset", default="MoleculeACE")
    parser.add_argument("--concurrent-reserve-bytes", required=True, type=int)
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text())
    source = plan["assets"][args.dataset]
    assets = source["files"]
    for asset in assets:
        safe_asset(asset)
    root = Path(plan["data_root"])
    # Admit on an existing ancestor before mkdir; all data stays outside Git.
    ancestor = root
    while not ancestor.exists():
        ancestor = ancestor.parent
    quota = subprocess.check_output(
        ["ssh", "-n", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10",
         "sonmi", "quota", "-v", "-u", "zixiao"], text=True, timeout=60)
    remaining = quota_headroom(quota, os.getuid())
    observed = time.monotonic()
    peak = sum(asset["bytes"] for asset in assets) * 2 + 1_048_576
    guard(ancestor, peak, remaining, observed, args.concurrent_reserve_bytes)
    destination = root / "raw" / args.dataset
    destination.mkdir(parents=True, exist_ok=True)
    results = []
    for asset in assets:
        name = safe_asset(asset)
        final = destination / name
        if final.exists():
            if final.stat().st_size != asset["bytes"]:
                raise RuntimeError("existing file size differs; preserve it: " + str(final))
            results.append(dict(asset, path=str(final), status="EXISTING_CLOSED_SIZE_MATCH"))
            continue
        partial = final.with_suffix(final.suffix + ".partial")
        if partial.exists():
            raise RuntimeError("preserved partial requires explicit transport recovery: " + str(partial))
        guard(destination, peak, remaining, observed, args.concurrent_reserve_bytes)
        received = 0
        request = urllib.request.Request(asset["url"], headers={"User-Agent": "MFM-B0-data-acquisition"})
        with urllib.request.urlopen(request, timeout=45) as response, partial.open("xb") as target:
            while True:
                chunk = response.read(65536)
                if not chunk:
                    break
                if received + len(chunk) > asset["bytes"]:
                    raise RuntimeError("source exceeded declared asset size")
                guard(destination, peak, remaining, observed, args.concurrent_reserve_bytes)
                target.write(chunk)
                received += len(chunk)
                remaining -= len(chunk)
        if received != asset["bytes"]:
            raise RuntimeError("incomplete transport; partial retained")
        partial.rename(final)
        results.append(dict(asset, path=str(final), status="DOWNLOADED"))
        print("CLOSED", args.dataset, name, received, flush=True)
    manifest = root / "acquisition" / (args.dataset + ".json")
    manifest.parent.mkdir(parents=True, exist_ok=True)
    guard(root, 1_048_576, remaining, observed, args.concurrent_reserve_bytes)
    manifest.write_text(json.dumps({
        "status": "SOURCE_ASSETS_ACQUIRED", "dataset": args.dataset,
        "source_commit": source["source_commit"], "files": results,
        "files_count": len(results), "declared_bytes": sum(x["bytes"] for x in results),
        "numerical_payload_readback": False, "new_content_hashes": False,
        "filtering_or_training_ready": False
    }, indent=2) + "\n")
    print("MANIFEST", manifest)


if __name__ == "__main__":
    main()
