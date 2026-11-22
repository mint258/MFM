"""Shared storage/RAM admission for all MFM lines (stdlib only, no package imports).

One registry directory; each line writes only its own file `<line>.json`.
A guard sums the unexpired reservations of the *other* lines, adds its own
peak, keeps the fixed system reserve, and refuses when that does not fit.

Reserves are the existing project values:
  node-local disk (root, /tmp): max(10 GiB, 10% of total)
  shared NFS/Lustre:            100 GB + 8 GiB
  node RAM:                     max(16 GiB, 10% of total)
"""
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time

GIB = 2**30
SHARED_RESERVE = 100_000_000_000 + 8 * GIB
REGISTRY = Path(os.environ.get(
    "MFM_RESERVATION_DIR",
    "/share/home/zixiao/descriptor_analysis/runs/shared_storage_reservations"))
KINDS = {"node_disk", "node_ram", "shared_fs"}
MOUNTS = {"node_disk": ("/", "/tmp"), "shared_fs": ("/share", "/lfshome")}
DEFAULT_TTL = 24 * 3600


class AdmissionRefused(OSError):
    pass


def node_name():
    return socket.gethostname().split(".")[0]


def _mount(kind, path):
    if kind == "node_ram":
        return None
    if str(path) not in MOUNTS[kind]:
        raise ValueError(f"{kind} path must be one of {MOUNTS[kind]}, got {path!r}")
    return str(path)


def _same_device(kind, path):
    """On this node, the canonical mounts that share the device of `path` (e.g. /tmp on /)."""
    if kind != "node_disk":
        return {path}
    dev = os.stat(path).st_dev
    return {m for m in MOUNTS[kind] if os.path.exists(m) and os.stat(m).st_dev == dev}


def claim(line, entries, ttl=DEFAULT_TTL, registry=REGISTRY, now=None):
    """Replace this line's own reservations atomically. Entries hold REMAINING future bytes.

    entry = {"id", "kind" in KINDS, "bytes" >= 0, "path" (disk/fs mount), "node" (node kinds)}
    """
    now = time.time() if now is None else now
    clean = []
    for e in entries:
        if e["kind"] not in KINDS or int(e["bytes"]) < 0:
            raise ValueError(f"bad reservation {e}")
        if e["kind"] != "shared_fs" and not e.get("node"):
            raise ValueError(f"node reservation without node: {e}")
        clean.append(dict(e, bytes=int(e["bytes"]), path=_mount(e["kind"], e.get("path"))))
    registry.mkdir(parents=True, exist_ok=True)
    body = {"line": line, "updated": now, "expires": now + ttl, "entries": clean}
    fd, tmp = tempfile.mkstemp(dir=registry, prefix=f".{line}.", suffix=".tmp")
    with os.fdopen(fd, "w") as f:
        json.dump(body, f, indent=1)
    os.replace(tmp, registry / f"{line}.json")
    return body


def release(line, registry=REGISTRY, now=None):
    """Writing is finished: keep the file, clear the reservations."""
    return claim(line, [], registry=registry, now=now)


def others(line, kind, node=None, path=None, registry=REGISTRY, now=None, paths=None):
    """Sum unexpired reservations of other lines on the same capacity. Unreadable file -> refuse."""
    now = time.time() if now is None else now
    paths = paths or {_mount(kind, path)}
    total = 0
    if not registry.exists():
        return 0
    for f in sorted(registry.glob("*.json")):
        if f.stem == line:
            continue
        try:
            body = json.loads(f.read_text())
            expires = float(body["expires"])
            entries = body["entries"]
        except Exception as exc:
            raise AdmissionRefused(f"reservation file unreadable: {f} ({exc})")
        if expires < now:
            continue
        for e in entries:
            if e["kind"] != kind or (kind != "shared_fs" and e.get("node") != node):
                continue
            if kind == "node_ram" or e.get("path") in paths:
                total += int(e["bytes"])
    return total


def disk_status(path):
    s = os.statvfs(path)
    return dict(total=s.f_blocks * s.f_frsize, available=s.f_bavail * s.f_frsize,
                inodes=s.f_favail, total_inodes=s.f_files)


def ram_status():
    info = {}
    for row in Path("/proc/meminfo").read_text().splitlines():
        key, value = row.split(":", 1)
        info[key] = int(value.split()[0]) * 1024
    return dict(total=info["MemTotal"], available=info["MemAvailable"])


def reserve_for(kind, total):
    if kind == "shared_fs":
        return SHARED_RESERVE
    if kind == "node_ram":
        return max(16 * GIB, total // 10)
    return max(10 * GIB, total // 10)


def check(line, kind, own_bytes, path=None, node=None, new_inodes=1000,
          quota_available=None, registry=REGISTRY, status=None, now=None):
    """Raise AdmissionRefused unless own_bytes fits. Returns the numbers used."""
    if kind not in KINDS or own_bytes < 0:
        raise ValueError("bad request")
    node = node or (None if kind == "shared_fs" else node_name())
    path = _mount(kind, path)
    if status is None:
        status = ram_status() if kind == "node_ram" else disk_status(path)
    paths = _same_device(kind, path) if (kind == "node_disk" and node == node_name()) else {path}
    peers = others(line, kind, node, path, registry, now, paths)
    reserve = reserve_for(kind, status["total"])
    need = reserve + own_bytes + peers
    report = dict(line=line, kind=kind, node=node, path=str(path), own=own_bytes,
                  peers=peers, reserve=reserve, available=status["available"])
    if status["total"] <= 0 or status["available"] < need:
        raise AdmissionRefused(f"insufficient {kind}: {report}")
    if kind != "node_ram" and status["inodes"] <= new_inodes:
        raise AdmissionRefused(f"insufficient inodes: {report}, inodes={status['inodes']}")
    if quota_available is not None and quota_available < SHARED_RESERVE + own_bytes + peers:
        raise AdmissionRefused(f"insufficient UID quota: {report}, quota={quota_available}")
    return report


def check_with_timeout(line, kind, own_bytes, path=None, node=None, new_inodes=1000,
                       quota_available=None, timeout=60):
    """Run check in a child process so a hung NFS cannot hang the caller. Timeout = refusal."""
    argv = [sys.executable, "-I", str(Path(__file__).resolve()), "check", line, kind,
            str(own_bytes), "--new-inodes", str(new_inodes)]
    if path is not None:
        argv += ["--path", str(path)]
    if node is not None:
        argv += ["--node", node]
    if quota_available is not None:
        argv += ["--quota", str(quota_available)]
    try:
        out = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise AdmissionRefused(f"admission timed out after {timeout}s (filesystem unresponsive)")
    if out.returncode != 0:
        raise AdmissionRefused(out.stderr.strip().splitlines()[-1] if out.stderr else "refused")
    return json.loads(out.stdout)


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("line"); c.add_argument("kind"); c.add_argument("own", type=int)
    c.add_argument("--path"); c.add_argument("--node")
    c.add_argument("--new-inodes", type=int, default=1000)
    c.add_argument("--quota", type=int)
    a = p.parse_args()
    try:
        r = check(a.line, a.kind, a.own, a.path, a.node, a.new_inodes, a.quota)
    except AdmissionRefused as exc:
        print(f"REFUSED {exc}", file=sys.stderr)
        sys.exit(3)
    print(json.dumps(r))


if __name__ == "__main__":
    main()
