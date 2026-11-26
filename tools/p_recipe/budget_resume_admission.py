"""Actual-file-system admission for the six remaining original T1 readouts.

The F entry stays frozen. Its identical resource/identity checks are reused
here with the canonical physical output probe for the NFS autofs root.
"""
import os
from pathlib import Path
import socket
import time
import json
import exit_lifecycle as lifecycle
from finetune_entry import REPO  # Initialize the established standalone entry paths.
import shared_guard


def validate_canonical_filesystem(output, mount):
    target = Path(output).absolute()
    root = Path(mount).absolute()
    if os.path.commonpath([str(target), str(root)]) != str(root):
        raise ValueError("Output is outside the registered mount")
    existing = target
    while not existing.exists():
        existing = existing.parent
    if os.path.commonpath([str(existing.resolve()), str(root.resolve())]) != str(root.resolve()):
        raise ValueError("Output parent escapes the registered mount")
    probe = shared_guard.disk_probe_target(mount)
    if os.stat(existing).st_dev != os.stat(probe).st_dev:
        raise ValueError("Output and canonical physical probe differ")


def admission(c):
    node = socket.gethostname().split(".")[0]
    if node != c["node"] or node not in {"compute-0-"+str(i) for i in range(8)}:
        raise ValueError("F work requires its actual configured0-7 node")
    parent = lifecycle.identity(os.getppid())
    current = lifecycle.identity(os.getpid())
    if (os.environ.get("D_EXIT_OUTER_SUPERVISION") != "1"
            or os.getppid() != int(os.environ["D_RESIDENT_SUPERVISOR_PID"])
            or parent is None or parent.uids != (1278,)*4 or current is None
            or parent.start_ticks != int(os.environ["D_RESIDENT_SUPERVISOR_START_TICKS"])
            or parent.cgroup != current.cgroup):
        raise ValueError("Exact existing-provider parent UID/start/job cgroup is not verified")
    scope = json.loads((shared_guard.REGISTRY / "p-recipe.json").read_text())
    if scope["line"] != "p-recipe" or scope["expires"] < time.time():
        raise ValueError("Current own reservation is absent or expired")
    entries = scope["entries"]
    own = {e["id"]: e for e in entries}
    if not c["reservation_ids"] or not set(c["reservation_ids"]) <= own.keys():
        raise ValueError("Coordinator has not registered this run's future writes/RAM")
    # Own-line simultaneous requests are summed; canonical guard adds all peers.
    paths = shared_guard._same_device("node_disk", "/tmp")
    local = sum(e["bytes"] for e in entries if e["kind"] == "node_disk"
                and e.get("node") == node and e.get("path") in paths)
    ram = sum(e["bytes"] for e in entries if e["kind"] == "node_ram" and e.get("node") == node)
    mount = c["output_mount"]
    validate_canonical_filesystem(c["output"], mount)
    future = sum(e["bytes"] for e in entries if e["kind"] == "shared_fs" and e.get("path") == mount)
    if local < 32 * 2**20 + 65536 or ram < c["ram_peak_bytes"] or future < c["remaining_output_bytes"]:
        raise ValueError("Own aggregate reservation does not contain this actual run")
    shared_guard.check_with_timeout("p-recipe", "node_disk", local, path="/tmp", node=node)
    shared_guard.check_with_timeout("p-recipe", "node_ram", ram, node=node)
    # The coordinator binds a producer's fresh UID snapshot when one exists.
    # A stale/missing snapshot is not passed as a fictional available-byte value.
    quota = None
    descriptor = c.get("uid_quota_snapshot")
    if descriptor is not None:
        try:
            snapshot = json.loads(Path(descriptor["path"]).read_text())
            age = time.time() - float(snapshot[descriptor["timestamp_field"]])
            if 0 <= age <= descriptor["fresh_seconds"]:
                quota = int(snapshot[descriptor["available_field"]])
        except (OSError, ValueError, KeyError):
            pass  # No fresh optional snapshot; canonical df+registry still apply.
    shared_guard.check_with_timeout("p-recipe", "shared_fs", future,
                                    path=mount, quota_available=quota)
    return node
