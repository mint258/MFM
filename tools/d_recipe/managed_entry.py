"""Future D entry with actual-allocation exit supervision.

Existing D launchers, guards, scientific loop and checkpoint protocol remain
the workers. This module is only active when explicitly used by a new entry.
"""
import argparse
from copy import deepcopy
import datetime
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import uuid

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))
from tools.d_recipe import exit_lifecycle as lifecycle

_CONTROL_ROOT = Path("/share/home/zixiao/descriptor_analysis/runs/d_recipe_20261120")
_METADATA_PYTHON = "/share/home/zixiao/.conda/envs/chemprop/bin/python"


def allocation_end(record, job):
    if record.get("JobId") != str(job):
        raise RuntimeError("Actual allocation identity differs")
    if record.get("TimeLimit") in (None, "Unknown", "NOT_SET", "N/A"):
        raise RuntimeError("Actual TimeLimit is unavailable")
    if record.get("TimeLimit") == "UNLIMITED":
        return None
    value = record.get("EndTime")
    if value in (None, "Unknown", "N/A", "None"):
        raise RuntimeError("Actual allocation end is unavailable")
    return datetime.datetime.fromisoformat(value).timestamp()


def require_healthy_node(record, node):
    state = record.get("State", "").upper()
    if record.get("NodeName") != node or not state:
        raise RuntimeError("Actual node identity/state unavailable")
    if any(word in state for word in
           ("DRAIN", "DOWN", "NOT_RESPONDING", "NO_RESPOND", "UNKNOWN", "FAIL")):
        raise RuntimeError("Actual target is not healthy: " + state)



def require_local_log(record):
    """Keep Slurm log creation away from the shared-data filesystem."""
    path = Path(record.get("StdOut", ""))
    if path.parent != Path("/tmp") or not path.name.startswith("d_recipe_managed_"):
        raise RuntimeError("Use the managed entry's declared node-local log")
    if os.stat("/tmp").st_dev != os.stat("/").st_dev:
        raise RuntimeError("Register a distinct /tmp filesystem before this entry")
    facts = os.statvfs("/")
    reserve = max(10 * 2**30, (facts.f_blocks * facts.f_frsize + 9) // 10)
    if facts.f_bavail * facts.f_frsize < reserve + 96 * 2**20 or facts.f_favail < 10000:
        raise RuntimeError("Actual local log/system reserve is unavailable")


def runtime_payload(configuration, job, kind):
    c = deepcopy(configuration)
    run = c["run"]
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", run) or run in (".", ".."):
        raise ValueError("Run label cannot escape its exit-control scope")
    control = Path(c.get("control_directory", str(_CONTROL_ROOT))).resolve()
    if not control.is_relative_to(_CONTROL_ROOT.resolve()):
        raise ValueError("D exit control escaped the registered shared scope")
    folder = control / "exit_control" / run / ("job_" + str(int(job)))
    if kind == "train":
        c["handoff_request"] = str(folder / "request.json")
        c["handoff_ack"] = str(folder / "ack.json")
    joint_logs = c.get("exit_root_log_future_bytes")
    if type(joint_logs) is not int or joint_logs < 32 * 2**20:
        raise ValueError("Register actual concurrent node-local log growth before launch")
    c["local_concurrent_bytes"] = c.get("local_concurrent_bytes", 0) + joint_logs
    c["safe_exit_control"] = dict(job_id=str(job), kind=kind,
                                  source_configuration_unchanged=True)
    return folder / "runtime.json", c


def _query(arguments, scope):
    """Bound a local read-only query; TERM/reap without SIGKILL."""
    process = subprocess.Popen(arguments, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
    bound = lifecycle.identity(process.pid)
    try:
        out, error = process.communicate(timeout=10)
    except subprocess.TimeoutExpired:
        if bound is not None:
            lifecycle.signal_owned(bound, signal.SIGTERM,
                                   uid=os.getuid(), scope=scope)
        try:
            process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            print(json.dumps(dict(phase="ADMIN_REQUIRED_CONTROL_QUERY_EXIT",
                                  pid=process.pid)), flush=True)
            # No scientific work starts; no orphan is declared cleaned.
            process.wait()
        raise RuntimeError("Control observation failed; no new work may start")
    if process.returncode:
        raise RuntimeError(error.decode("utf-8", "replace"))
    return dict(re.findall(r"(\w+)=(\S+)", out.decode()))


def _prepare(configuration_path, job, kind):
    selected = json.loads(Path(configuration_path).read_text())
    if selected.get("canonical_admission") is True:
        from tools.d_recipe.canonical_runtime import prepare_snapshot
        return prepare_snapshot(selected, job, kind)
    from tools.d_recipe.resources import admit_output, execution_site
    from tools.d_recipe.train import publish_summary
    c = json.loads(Path(configuration_path).read_text())
    execution_site(c, cpu=kind in ("cpu", "compare"))
    destination, runtime = runtime_payload(c, job, kind)
    if destination.exists():
        raise FileExistsError("Inspect existing runtime snapshot before reentry")
    admit_output(runtime, destination.parent)
    destination.parent.mkdir(parents=True, exist_ok=True)
    publish_summary(destination, runtime, runtime)


def _request(snapshot, job):
    selected = json.loads(Path(snapshot).read_text())
    if selected.get("canonical_admission") is True:
        from tools.d_recipe.canonical_runtime import request_snapshot
        return request_snapshot(selected, job)
    from tools.d_recipe.train import publish_summary
    c = json.loads(Path(snapshot).read_text())
    if c["safe_exit_control"]["job_id"] != str(job):
        raise ValueError("Cooperative request belongs to another allocation")
    path = Path(c["handoff_request"])
    if path.exists() or Path(c["handoff_ack"]).exists():
        raise FileExistsError("Preserve and inspect the prior handoff state")
    request = dict(action="SAVE_AND_EXIT", run=c["run"], job_id=int(job),
                   request_id=str(uuid.uuid4()))
    publish_summary(path, request, c)


def _worker_command(kind, resource_command, snapshot, arguments):
    base = _ROOT / "tools/d_recipe"
    if kind in ("train", "gpu"):
        if not arguments.gpu_uuid:
            raise ValueError("Actual assigned GPU UUID required")
        return ["/bin/bash", str(base / "run.sbatch"), str(snapshot),
                arguments.gpu_uuid, resource_command]
    if kind == "cpu":
        return ["/bin/bash", str(base / "cpu.sbatch"), str(snapshot),
                resource_command]
    if not arguments.control_configuration or not arguments.comparison_output:
        raise ValueError("Original matched control/output required")
    return ["/bin/bash", str(base / "comparison.sbatch"), str(snapshot),
            arguments.control_configuration, arguments.comparison_output]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--configuration", required=True)
    parser.add_argument("--kind", choices=("train", "gpu", "cpu", "compare"),
                        required=True)
    parser.add_argument("--resource-command")
    parser.add_argument("--gpu-uuid")
    parser.add_argument("--control-configuration")
    parser.add_argument("--comparison-output")
    parser.add_argument("--cleanup-seconds", type=int, default=900)
    parser.add_argument("--metadata-python", default=_METADATA_PYTHON)
    parser.add_argument("--prepare-runtime", action="store_true")
    parser.add_argument("--publish-request", action="store_true")
    args = parser.parse_args()
    job = os.environ.get("SLURM_JOB_ID")
    if not job:
        raise RuntimeError("Real allocation required")
    scope = lifecycle.slurm_scope(job)
    if args.prepare_runtime:
        _prepare(args.configuration, job, args.kind)
        return 0
    if args.publish_request:
        _request(args.configuration, job)
        return 0

    lifecycle.enable_subreaper()
    node = os.uname().nodename.split(".")[0]
    require_healthy_node(_query(["/usr/bin/scontrol", "show", "node", node, "-o"],
                               scope), node)
    allocation = _query(["/usr/bin/scontrol", "show", "job", job, "-o"], scope)
    end = allocation_end(allocation, job)
    require_local_log(allocation)
    grace = lifecycle.cleanup_seconds(args.cleanup_seconds)
    command = args.resource_command or ("train" if args.kind == "train"
                                       else "cpu_statistics")
    permitted = {
        "train": {"train"},
        "gpu": {"diagnostic_forward", "layer_readouts", "development_panel", "budget_readout"},
        "cpu": {"cpu_statistics", "diagnostic_statistics", "layer_readouts",
                "development_panel"}, "compare": {"cpu_statistics"}}
    if command not in permitted[args.kind]:
        raise ValueError("Use only existing registered D worker commands")
    configuration = json.loads(Path(args.configuration).read_text())
    if configuration.get("canonical_admission") is True:
        os.environ["D_CANONICAL_ADMISSION"] = "1"
    else:
        os.environ.pop("D_CANONICAL_ADMISSION", None)
    snapshot, _ = runtime_payload(configuration, job, args.kind)
    worker = _worker_command(args.kind, command, snapshot, args)
    helper = [args.metadata_python, "-B", "-m", "tools.d_recipe.managed_entry",
              "--configuration", args.configuration, "--kind", args.kind,
              "--prepare-runtime"]
    emit = lambda event: print(json.dumps(event), flush=True)
    result = lifecycle.supervise(helper, end_epoch=end, scope=scope,
                                 grace_seconds=grace, report=emit)
    if result:
        return result

    def request_stop():
        return subprocess.Popen([
            args.metadata_python, "-B", "-m", "tools.d_recipe.managed_entry",
            "--configuration", str(snapshot), "--kind", args.kind,
            "--publish-request"], start_new_session=True)

    return lifecycle.supervise(
        worker, end_epoch=end, scope=scope, grace_seconds=grace,
        request_stop=request_stop if args.kind == "train" else None,
        report=emit)


if __name__ == "__main__":
    result = main()
    raise SystemExit(128 - result if result < 0 else result)


