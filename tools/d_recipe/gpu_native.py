"""Authenticated D training on the existing P GPU SSH supervisor.

Only execution plumbing is added. The original D/P training, checkpoint and
R1/R3 producers remain unchanged; a same-task Slurm twin owns any takeover.
"""
import argparse
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import asdict
import csv
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
import uuid

ROOT = Path("/share/home/zixiao/descriptor_analysis")
P_TOOLS = ROOT / "MFM_p_recipe/tools/p_recipe"
RUNS = ROOT / "runs/d_recipe_20261120"


def load_provider():
    sys.path.insert(0, str(P_TOOLS))
    spec = importlib.util.spec_from_file_location("d_existing_gpu_ssh", P_TOOLS / "gpu_ssh_runtime.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def native_payload(configuration, execution_id, receipt):
    if not re.fullmatch(r"ssh:P_D_[A-Za-z0-9_.-]+", execution_id):
        raise ValueError("An actual explicit D SSH execution handle is required")
    c = deepcopy(configuration)
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", c["run"]) or c["run"] in (".", ".."):
        raise ValueError("Run label escaped its D control scope")
    folder = RUNS / "exit_control" / c["run"] / execution_id.removeprefix("ssh:")
    if Path(receipt).resolve() != (folder / "receipt.json").resolve():
        raise ValueError("Native receipt must use its unique owned D control folder")
    c.update(execution="native_SSH", execution_backend="ssh_gpu", line="D",
        execution_id=execution_id, ssh_execution_id=execution_id,
        receipt=str(receipt), ssh_runtime_receipt=str(receipt),
        native_control_directory=str(folder), native_phase_state=str(folder / "phase.json"),
        handoff_request=str(folder / "request.json"), handoff_ack=str(folder / "ack.json"),
        handoff_requires_worker_ready=True,
        safe_exit_control=dict(execution_id=execution_id, kind="train",
                               source_configuration_unchanged=True))
    c.pop("canonical_phase_admission", None)
    c.pop("native_monitor", None)
    return c


def require_transport(c, node, visible, actual_cores):
    if (c.get("canonical_admission") is not True or c.get("execution") != "native_SSH"
            or c.get("execution_backend") != "ssh_gpu" or node != c["node"]
            or c.get("local_node") != node
            or node not in {"compute-0-20", "compute-0-22"}
            or visible != c["gpu_uuid"] or set(actual_cores) != set(c["cores"])
            or not c["workers"] + 2 <= len(actual_cores) <= 16
            or c["safe_exit_control"].get("execution_id") != c["ssh_execution_id"]
            or c["execution_id"] != c["ssh_execution_id"]
            or c["receipt"] != c["ssh_runtime_receipt"] or c["cleanup_seconds"] < 900):
        raise ValueError("Actual native GPU/node/CPU/control identity differs")


def gpu_facts(c, row):
    if len(row) != 4 or row[0].strip() != c["gpu_uuid"]:
        raise ValueError("Actual selected GPU UUID differs")
    name, used, total = row[1].strip(), float(row[2]), float(row[3])
    if (not all(math.isfinite(x) for x in (used, total)) or total <= 0
            or not 0 <= used <= total or used / total > .30
            or total - used < c["minimum_free_gpu_mib"]):
        raise ValueError("Actual GPU memory is unknown or outside the admitted allowance")
    return dict(uuid=c["gpu_uuid"], name=name, used_MiB=used, total_MiB=total)


@contextmanager
def gpu_lock(c):
    import fcntl
    path = ROOT / "docs/phase1/evidence/stage46_shared_gpu_launch/.own_gpu_uuid_locks" / (c["gpu_uuid"] + ".lock")
    with path.open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        raw = subprocess.run(["/usr/bin/nvidia-smi", "--id=" + c["gpu_uuid"],
            "--query-gpu=uuid,name,memory.used,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10, check=True).stdout
        rows = list(csv.reader(raw.splitlines()))
        if len(rows) != 1:
            raise ValueError("Exactly one actual target GPU is required")
        yield gpu_facts(c, rows[0])


def request_once(c, check, atomic):
    """Use the original P request schema; job_id holds the real SSH handle."""
    path = Path(c["handoff_request"])
    if path.exists():
        value = json.loads(path.read_text())
        if (value.get("run") != c["run"] or value.get("action") != "SAVE_AND_EXIT"
                or value.get("execution_id") != c["ssh_execution_id"]
                or value.get("job_id") != c["ssh_execution_id"] or not value.get("request_id")):
            raise ValueError("Preserve and inspect the existing different stop request")
        return value
    check(path)
    value = dict(action="SAVE_AND_EXIT", run=c["run"], job_id=c["ssh_execution_id"],
        execution_id=c["ssh_execution_id"], request_id=str(uuid.uuid4()))
    atomic(path, value)
    return value


@contextmanager
def stop_flags():
    flags = dict(requested=False)
    old = {sig: signal.getsignal(sig) for sig in (signal.SIGUSR1, signal.SIGTERM, signal.SIGINT)}
    try:
        for sig in old:
            signal.signal(sig, lambda received, frame: flags.update(requested=True))
        yield flags
    finally:
        for sig, handler in old.items():
            signal.signal(sig, handler)


class ReadoutDeferred(RuntimeError):
    pass


def require_readout_window(c, *, now=None):
    now = time.time() if now is None else now
    unit = c["expected_readout_seconds"]
    if not isinstance(unit, (int, float)) or not math.isfinite(unit) or unit <= 0:
        raise ValueError("A finite original complete-readout work unit is required")
    if (Path(c["handoff_request"]).exists()
            or now + unit >= c["native_hard_end_epoch"] - c["cleanup_seconds"]):
        raise ReadoutDeferred("Retain the completed training budget; do not start a new readout unit")


def require_monitor(c, identity):
    parent, current = identity(os.getppid()), identity(os.getpid())
    bound = c["native_monitor"]
    admitted = c.get("canonical_phase_admission", {})
    if (os.environ.get("SLURM_JOB_ID") or parent is None or current is None
            or admitted.get("execution_id") != c["ssh_execution_id"] or admitted.get("node") != c["node"]
            or parent.pid != bound["pid"] or parent.start_ticks != bound["start_ticks"]
            or parent.uids != (1278,) * 4 or current.uids != (1278,) * 4
            or parent.cgroup != bound["cgroup"] or parent.cgroup != current.cgroup):
        raise ValueError("Actual native monitor UID/start/cgroup differs")


def worker(c):
    from . import exit_lifecycle as life, resources
    from .canonical_runtime import allocated_threads, installed_writers, guard_class
    from .shared_admission import atomic_json
    require_monitor(c, life.identity)
    resources.execution_site(c, cpu=False)
    require_transport(c, os.uname().nodename.split(".")[0],
                      os.environ.get("CUDA_VISIBLE_DEVICES"), os.sched_getaffinity(0))
    control_guard = guard_class(resources)(c, admit=False)
    ready = Path(c["ssh_runtime_receipt"] + ".worker_ready.json")
    control_guard.check_control(ready)
    atomic_json(ready, dict(execution_id=c["ssh_execution_id"], worker=asdict(life.identity(os.getpid()))))
    import torch
    from . import train, evaluate
    from .training import prepare_runtime
    phase = Path(c["native_phase_state"])
    def publish(value):
        control_guard.check_control(phase)
        atomic_json(phase, dict(value, execution_id=c["ssh_execution_id"], run=c["run"],
            scientific_binding=prepare_runtime(c)["d_recipe"]["scientific_binding"]))
    def evaluator(readout):
        require_readout_window(c)
        return evaluate.run(readout)
    with installed_writers(c, resources), allocated_threads(torch, len(c["cores"])), train.gpu_telemetry(c):
        try:
            result = train.run(c, evaluator=evaluator)
        except ReadoutDeferred:
            publish(dict(status="TRAINING_COMPLETE_READOUT_DEFERRED", samples=c["samples"]))
            return 75
        if result.get("status") == "HANDOFF_SAVED":
            publish(dict(status="HANDOFF_SAVED", acknowledgement=c["handoff_ack"],
                         request_id=result["request_id"]))
            return 75
        if result.get("status") not in ("GPU_READOUT_COMPLETE_WAITING_CPU_STATISTICS", "COMPLETE"):
            raise ValueError("Original D producer did not reach a valid execution boundary")
        publish(dict(status="GPU_READOUT_COMPLETE_WAITING_CPU_STATISTICS", samples=c["samples"]))
        marker = Path(c["output"]) / "primary_complete.json"
        if not marker.exists():
            control_guard.check_control(marker)
            atomic_json(marker, dict(status=result["status"], run=c["run"], samples=c["samples"],
                execution_id=c["ssh_execution_id"], original_prediction_manifest=result.get("predictions")))
        return 0


def monitor(c):
    provider = load_provider()
    end = provider.verified_deadline(c)
    require_transport(c, os.uname().nodename.split(".")[0],
                      os.environ.get("CUDA_VISIBLE_DEVICES"), os.sched_getaffinity(0))
    with stop_flags() as flags:
        state = subprocess.run(["/usr/bin/scontrol", "show", "node", c["node"], "-o"],
            capture_output=True, text=True, timeout=10, check=True).stdout
        if any(x in state for x in ("DRAIN", "DOWN", "NOT_RESPOND", "UNKNOWN", "FAIL")):
            raise RuntimeError("Native target is not healthy")
        from .shared_admission import admit, atomic_json
        folder = Path(c["native_control_directory"])
        admission = admit(c, [folder, c["output"], c["local_output_root"]])
        from . import resources
        resources.execution_site(c, cpu=False)
        from .canonical_runtime import guard_class
        snapshot = folder / "runtime.json"
        if snapshot.exists():
            raise FileExistsError("Inspect the original native execution; never relaunch it")
        runtime = deepcopy(c)
        runtime["native_monitor"] = asdict(provider.life.identity(os.getpid()))
        runtime["native_hard_end_epoch"] = end
        runtime["canonical_phase_admission"] = dict(execution_id=c["ssh_execution_id"],
            node=admission["node"], own_reservation_ids=admission["own_reservation_ids"])
        guard = guard_class(resources)(runtime, admit=False)
        with gpu_lock(c) as card:
            guard.check_control(snapshot)
            atomic_json(snapshot, runtime)
            original_check = guard.check
            def check(path, *args, **kwargs):
                if flags["requested"]:
                    request_once(runtime, guard.check_control, atomic_json)
                return original_check(path, *args, **kwargs)
            guard.check = check
            print(json.dumps(dict(phase="D_NATIVE_GPU_MONITOR", card=card,
                                  runtime=str(snapshot))), flush=True)
            try:
                guard.run([sys.executable, "-B", "-m", "tools.d_recipe.gpu_native",
                           "--configuration", str(snapshot), "--worker"], c["output"])
            except subprocess.CalledProcessError as error:
                if error.returncode != 75:
                    raise
                saved = json.loads(Path(c["native_phase_state"]).read_text())
                if (saved.get("execution_id") != c["ssh_execution_id"]
                        or saved.get("status") not in ("HANDOFF_SAVED", "TRAINING_COMPLETE_READOUT_DEFERRED")):
                    raise ValueError("Incomplete native phase has no matching saved boundary")
                return 75
        return 0


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--configuration", required=True)
    p.add_argument("--worker", action="store_true")
    a = p.parse_args()
    c = json.loads(Path(a.configuration).read_text())
    return worker(c) if a.worker else monitor(c)


if __name__ == "__main__":
    raise SystemExit(main())
