"""A real Slurm allocation resumes only its fully closed native D source."""
import argparse
from copy import deepcopy
import importlib.util
import json
import os
from pathlib import Path
import sys
import time

from .gpu_native import P_TOOLS, stop_flags
from .shared_admission import atomic_json


def same(bound, actual):
    return (actual is not None and actual.pid == bound["pid"]
        and actual.start_ticks == bound["start_ticks"]
        and actual.uids == tuple(bound["uids"]) == (1278,) * 4
        and actual.cgroup == bound["cgroup"])


def require_closed_source(c, record, identity):
    if (record.get("execution_id") != c["ssh_execution_id"]
            or record.get("node") != c["node"] or record.get("gpu_uuid") != c["gpu_uuid"]
            or (record.get("status"), record.get("returncode")) not in (
                ("COMPLETE", 0), ("CURSOR_SAVED_NOT_COMPLETE", 75))
            or record.get("owned_tree_reaped") is not True or record.get("remaining_children") != []):
        raise ValueError("Matching complete native outcome and reaped tree required")
    for key in ("supervisor", "parent", "launcher"):
        if same(record[key], identity(record[key]["pid"])):
            raise ValueError("Original native source process still exists")


def continuation(c, record, *, reader, identity, checkpoint_stat):
    """Resolve metadata once; never load a checkpoint tensor for independent QA."""
    from .training import prepare_runtime
    require_closed_source(c, record, identity)
    phase = reader(c["native_phase_state"])
    binding = prepare_runtime(c)["d_recipe"]["scientific_binding"]
    if (phase.get("execution_id") != c["ssh_execution_id"] or phase.get("run") != c["run"]
            or phase.get("scientific_binding") != binding):
        raise ValueError("Different native phase or scientific binding")
    if phase["status"] == "GPU_READOUT_COMPLETE_WAITING_CPU_STATISTICS":
        if record["status"] != "COMPLETE" or record["returncode"] != 0:
            raise ValueError("Finished original readouts need the actual successful source receipt")
        return None
    result = deepcopy(c)
    if phase["status"] == "HANDOFF_SAVED":
        request, ack = reader(c["handoff_request"]), reader(c["handoff_ack"])
        if (request.get("execution_id") != c["ssh_execution_id"]
                or request.get("action") != "SAVE_AND_EXIT" or request.get("run") != c["run"]
                or ack.get("run") != c["run"] or ack.get("request_id") != request.get("request_id")
                or ack.get("request_id") != phase.get("request_id")
                or ack.get("job_id") != c["ssh_execution_id"]):
            raise ValueError("A matching original checkpoint acknowledgement is required")
        samples = ack["clock"]["samples_consumed"]
        path = Path(ack["checkpoint"])
        if (type(samples) is not int or not 0 < samples < c["samples"]
                or path.parent.resolve() != Path(c["output"]).resolve()
                or path.name != "samples_" + str(samples) + ".pt"):
            raise ValueError("Checkpoint must be a closed same-run committed sample point")
        checkpoint_stat(path)
        result.update(resume=str(path), resume_samples=samples, resume_from_output=c["output"])
    elif phase["status"] == "TRAINING_COMPLETE_READOUT_DEFERRED":
        summary = reader(Path(c["output"]) / "summary.json")
        if (record["returncode"] != 75 or summary.get("run") != c["run"]
                or summary.get("samples") != c["samples"]
                or summary.get("status") != "TRAINING_COMPLETE_EVALUATION_PENDING"):
            raise ValueError("Original full training must close before readout-only continuation")
        checkpoint_stat(Path(c["output"]) / ("samples_" + str(c["samples"]) + ".pt"))
    else:
        raise ValueError("Native source has no original saved continuation boundary")
    for key in list(result):
        if key.startswith("native_") or key.startswith("ssh_") or key in (
                "execution_id", "receipt", "worker_argv", "cores", "execution_backend",
                "canonical_phase_admission", "safe_exit_control", "handoff_request", "handoff_ack",
                "handoff_requires_worker_ready"):
            result.pop(key)
    result["execution"] = "Slurm"
    result["source_SSH_execution_id"] = c["ssh_execution_id"]
    if prepare_runtime(result)["d_recipe"]["scientific_binding"] != binding:
        raise ValueError("Takeover changed the original scientific configuration")
    return result


def regular_checkpoint(path):
    import stat
    info = Path(path).lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_size <= 0:
        raise ValueError("Actual owned complete checkpoint is unavailable")


def load_waiter():
    sys.path.insert(0, str(P_TOOLS))
    spec = importlib.util.spec_from_file_location("d_existing_same_task_waiter", P_TOOLS / "a5_takeover_entry.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--configuration", required=True)
    a = p.parse_args()
    c = json.loads(Path(a.configuration).read_text())
    job = os.environ.get("SLURM_JOB_ID")
    from . import exit_lifecycle as life, managed_entry, resources
    if (not job or not job.isdigit() or os.uname().nodename.split(".")[0] != c["node"]
            or c["node"] not in {"compute-0-20", "compute-0-22"}):
        raise ValueError("An actual same-node Slurm takeover allocation is required")
    scope = life.slurm_scope(job)
    current = life.identity(os.getpid())
    if not life.owned_scope(current, 1278, scope):
        raise ValueError("The controller is outside its actual own Slurm cgroup")
    allocation = managed_entry._query(["/usr/bin/scontrol", "show", "job", job, "-o"], scope)
    end = managed_entry.allocation_end(allocation, job)
    if end is None or end - time.time() <= c["cleanup_seconds"]:
        raise ValueError("Actual finite allocation work/cleanup window is unavailable")
    os.environ["P_MANAGED_STOP_NEW_UNITS_AT"] = str(end - c["cleanup_seconds"])
    waiter = load_waiter()
    with stop_flags() as flags:
        class Stop:
            @property
            def requested(self):
                return flags["requested"]
        state = waiter.wait_for_source(c, Stop())
        if state == "WAIT_NOT_COMPLETE":
            return 75
        reader = lambda path: json.loads(Path(path).read_text())
        record = reader(c["ssh_runtime_receipt"])
        ready = reader(c["ssh_runtime_receipt"] + ".worker_ready.json")
        if (ready.get("execution_id") != c["ssh_execution_id"]
                or same(ready["worker"], life.identity(ready["worker"]["pid"]))):
            raise ValueError("Original native scientific worker exit is not proven")
        selected = continuation(c, record, reader=reader,
            identity=life.identity, checkpoint_stat=regular_checkpoint)
        if selected is None:
            print(json.dumps(dict(phase="D_SOURCE_ALREADY_COMPLETE_NO_REPEAT", job_id=job,
                                  execution_id=c["ssh_execution_id"])), flush=True)
            return 0
        allocated = resources.allocated_local_bytes(Path(c["local_output_root"]))
        selected["local_future_bytes"] = (max(0, c["local_storage_peak_bytes"] - allocated)
                                           + c["exit_root_log_future_bytes"])
        from .canonical_runtime import guard_class
        destination = Path(c["native_control_directory"]) / ("takeover_job_" + job + ".json")
        if destination.exists():
            raise FileExistsError("Inspect the prior actual takeover; do not duplicate it")
        guard_class(resources)(selected, admit=False).check_control(destination)
        atomic_json(destination, selected)
    # The original prepared Slurm entry obtains a fresh canonical phase admission,
    # UUID lock, actual job snapshot and original complete-state training/readouts.
    os.execv(sys.executable, [sys.executable, "-B", "-m", "tools.d_recipe.managed_entry",
        "--configuration", str(destination), "--kind", "train", "--gpu-uuid", c["gpu_uuid"],
        "--cleanup-seconds", str(c["cleanup_seconds"])])


if __name__ == "__main__":
    raise SystemExit(main())
