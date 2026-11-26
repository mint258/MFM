"""Original budget R1/R3 statistics with the current canonical admission."""
import argparse
import json
import os
from pathlib import Path
import socket
import time
from finetune_entry import CooperativeStop,set_actual_deadline
import exit_lifecycle as lifecycle
import shared_guard
from budget_resume_admission import validate_canonical_filesystem as validate_output_filesystem

def require_cpu_admission(c):
    node = socket.gethostname().split(".")[0]
    if node != c["node"] or node not in {"compute-0-"+str(i) for i in range(8,20)}:
        raise ValueError("Statistics must run on the configured CPU node")
    if node in set(c["excluded_nodes"]):
        raise ValueError("Known fault channel excluded")
    parent, current = lifecycle.identity(os.getppid()), lifecycle.identity(os.getpid())
    if (os.environ.get("D_EXIT_OUTER_SUPERVISION") != "1"
            or os.getppid() != int(os.environ["D_RESIDENT_SUPERVISOR_PID"])
            or parent is None or current is None or parent.uids != (1278,)*4
            or parent.start_ticks != int(os.environ["D_RESIDENT_SUPERVISOR_START_TICKS"])
            or parent.cgroup != current.cgroup):
        raise ValueError("Resident supervisor identity/cgroup not verified")
    claim = json.loads((shared_guard.REGISTRY/"p-recipe.json").read_text())
    own = {e["id"]:e for e in claim["entries"]}
    if claim["expires"] <= time.time() or not set(c["reservation_ids"]) <= own.keys():
        raise ValueError("Current own CPU statistics claims absent")
    entries = list(own.values())
    paths = shared_guard._same_device("node_disk","/tmp")
    disk = sum(e["bytes"] for e in entries if e["kind"]=="node_disk"
               and e.get("node")==node and e.get("path") in paths)
    ram = sum(e["bytes"] for e in entries if e["kind"]=="node_ram" and e.get("node")==node)
    mount = c["output_mount"]
    validate_output_filesystem(c["output"],mount)
    future = sum(e["bytes"] for e in entries if e["kind"]=="shared_fs" and e.get("path")==mount)
    if ram<c["ram_peak_bytes"] or future<c["remaining_output_bytes"]:
        raise ValueError("Own aggregate future does not contain this statistics phase")
    shared_guard.check_with_timeout("p-recipe","node_disk",disk,path="/tmp",node=node)
    shared_guard.check_with_timeout("p-recipe","node_ram",ram,node=node)
    shared_guard.check_with_timeout("p-recipe","shared_fs",future,path=mount)


def run(c):
    if c.get("ready") is not True:
        raise ValueError("Registered CPU statistics must be activated")
    with CooperativeStop() as stop:
        set_actual_deadline(c,stop);require_cpu_admission(c)
        from execution_ledger import read
        import cpu_statistics
        import torch
        torch.set_num_threads(1)
        original=read(c["original_configuration"])
        if (original["output"]!=c["output"] or original["run"]!=c["original_run"]
                or original["samples"]!=c["samples"] or not original["budget_curve"]):
            raise ValueError("Only the exact original readout may be finalized")
        def admit(candidate):
            if candidate!=original:
                raise ValueError("Statistics configuration changed")
            require_cpu_admission(c)
        old=cpu_statistics.admit
        cpu_statistics.admit=admit
        try:
            # Original score, retained bootstrap, CSV locking and finalizer.
            result=cpu_statistics.finalize(original)
        finally:
            cpu_statistics.admit=old
        print(json.dumps(result),flush=True)
        return 0


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--configuration",required=True)
    args=p.parse_args()
    raise SystemExit(run(json.loads(Path(args.configuration).read_text())))
