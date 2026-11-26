"""New D entries use the canonical registry, without historical peer copies."""
import json
import os
from pathlib import Path
import socket
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import shared_guard

LOCAL_BASE = Path("/tmp")


def admit(transport, output_paths):
    node = socket.gethostname().split(".")[0]
    claim = json.loads((shared_guard.REGISTRY / "d-recipe.json").read_text())
    entries = claim["entries"]
    own = {entry["id"]: entry for entry in entries}
    required = transport["reservation_ids"]
    if (claim["line"] != "d-recipe" or claim["expires"] <= time.time()
            or not required or not set(required) <= own.keys() or node != transport["node"]):
        raise ValueError("Current own D reservations and actual target node required")
    roots = (Path("/share/home/zixiao/descriptor_analysis/runs/d_recipe_20261120").resolve(),
             Path(__file__).resolve().parents[2] / "results/d_recipe",
             Path("/lfshome/zixiao/model_v31_20261105/D_RECIPE_20261120").resolve())
    local = transport.get("local_output_root")
    if local is not None:
        local = Path(local).resolve()
        if (local.parent != LOCAL_BASE.resolve() or not local.name.startswith("d_recipe_")
                or not local.is_dir() or local.stat().st_uid != os.getuid()):
            raise ValueError("An existing owned D node-local root is required")
        roots += (local,)
    mounts = set()
    for path in output_paths:
        path = Path(path).resolve()
        if not any(path.is_relative_to(root) for root in roots):
            raise ValueError("New D writer escaped its registered result/model scopes")
        if local is None or not path.is_relative_to(local):
            mounts.add("/lfshome" if str(path).startswith("/lfshome/") else "/share")
    ram = sum(e["bytes"] for e in entries if e["kind"] == "node_ram" and e.get("node") == node)
    paths = shared_guard._same_device("node_disk", "/tmp")
    disk = sum(e["bytes"] for e in entries if e["kind"] == "node_disk"
               and e.get("node") == node and e["path"] in paths)
    if ram < transport["ram_peak_bytes"] or disk < transport["local_future_bytes"]:
        raise ValueError("Own current node claims do not cover this producer")
    shared_guard.check_with_timeout("d-recipe", "node_ram", ram, node=node)
    shared_guard.check_with_timeout("d-recipe", "node_disk", disk, path="/tmp", node=node)
    for mount in mounts:
        future = sum(e["bytes"] for e in entries if e["kind"] == "shared_fs" and e["path"] == mount)
        if future < transport["shared_future_bytes"][mount]:
            raise ValueError("Own remaining output forecast does not cover this producer")
        shared_guard.check_with_timeout("d-recipe", "shared_fs", future, path=mount)
    return dict(node=node, mounts=sorted(mounts), own_reservation_ids=required)


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_name(path.name + ".partial")
    with pending.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(pending, path)
