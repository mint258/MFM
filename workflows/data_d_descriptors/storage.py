"""D write admission using actual-node facts and existing shared reservations."""
import json
import math
import os
from pathlib import Path
import stat


def physical_sqlite_bytes(directory):
    used = 0
    for path in Path(directory).glob("*.sqlite"):
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
            raise RuntimeError("Unknown peer database type/owner; cannot account its forecast")
        used += min(info.st_size, info.st_blocks * 512)
    return used


def concurrent_reservation(config):
    """Subtract committed physical bytes from declared future forecasts only."""
    total = (config["registered_model_share_future_bytes"] + config["benchmark_peer_environment_bytes"]
             + config["benchmark_miscellaneous_future_bytes"])
    for reference in config["B0_labels"]:
        total += max(2**26, reference["forecast_bytes"] - physical_sqlite_bytes(reference["directory"]))
    for directory in config["B0_geometry"]:
        folder = Path(directory)
        access = json.loads((folder / "access.json").read_text())
        closure = access.get("actual_closure_evidence", {}).get("raw", "")
        sealed = (access.get("immutable") is True and access.get("cross_node_read_allowed") is True
            and access.get("publishing_uid") == os.getuid()
            and "JobState=COMPLETED" in closure and "ExitCode=0:0" in closure)
        if not sealed:
            # A nonclosed geometry producer retains its registered future.
            manifest = json.loads((folder / "queue.manifest.json").read_text())
            total += max(2**26, int(manifest["storage_forecast_bytes"]) - physical_sqlite_bytes(folder))
    return total


def _inspect_output(path, inspect, *, share_root=Path("/share")):
    """Inspect the real target, or its nearest existing ancestor, without mkdir.

    Resolution happens before admission: a symlink escaping the registered
    shared tree cannot redirect an intended new directory to another disk.
    The injectable root is only for filesystem-selection unit fixtures;
    production guard always uses the actual /share root.
    """
    root = Path(share_root).resolve()
    target = Path(path).resolve()
    if not target.is_relative_to(root):
        raise RuntimeError("D output must use its registered /share quota and filesystem")
    actual = target
    while not actual.exists():
        actual = actual.parent
        if not actual.is_relative_to(root):
            raise RuntimeError("Registered /share ancestor is unavailable")
    if actual != target and not actual.is_dir():
        raise RuntimeError("New output ancestor is not a directory")
    facts = inspect(actual)
    if os.stat(actual).st_dev != os.stat(root).st_dev:
        raise RuntimeError("D output must use its registered /share quota and filesystem")
    return facts


def guard(path, peak_bytes):
    from workflows.data_v1_final.export.v31_stream_v1.disk_guard import inspect
    from workflows.data_v1_final.export.v31_stream_v1.quota_snapshot import read_available
    config = json.loads((Path(__file__).resolve().parents[2] / "configs/data_d_descriptors/storage_reservations.json").read_text())
    facts = _inspect_output(path, inspect)
    floor = config["quota_floor_bytes"]
    physical_floor = max(floor, 10 * 2**30, math.ceil(.1 * facts["total"])) if facts["root_filesystem"] else floor
    concurrent = concurrent_reservation(config)
    if facts["available"] < physical_floor + concurrent + peak_bytes or facts["inodes"] < 10000:
        raise RuntimeError("Storage headroom unavailable; retain existing outputs")
    available = read_available(config["quota_snapshot"], expected_uid=os.getuid(),
        expected_filesystem="/share", max_age_seconds=5)
    if available < floor + concurrent + peak_bytes:
        raise RuntimeError("Insufficient actual UID quota after registered peer reservations")
