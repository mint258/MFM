"""New GPU transport around the existing D scientific entry and disk monitor."""
import argparse
import importlib
import json
import os
from pathlib import Path
import sys

COMMANDS = ("train", "diagnostic_forward", "layer_readouts", "development_panel", "budget_readout")


def require_admitted_job(c, node, job):
    prior = c.get("canonical_phase_admission", {})
    if (not job or c.get("canonical_admission") is not True or c["node"] != node
            or prior.get("job_id") != job or prior.get("node") != node
            or c["safe_exit_control"]["job_id"] != job):
        raise ValueError("Actual prepared canonical Slurm job/node binding required")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=COMMANDS)
    parser.add_argument("--configuration", required=True)
    parser.add_argument("--worker", action="store_true")
    args = parser.parse_args()
    c = json.loads(Path(args.configuration).read_text())
    from . import resources, exit_lifecycle as life
    from .canonical_runtime import allocated_threads, guard_class, installed_writers
    resources.execution_site(c, cpu=False)
    job = os.environ.get("SLURM_JOB_ID")
    node = os.uname().nodename.split(".")[0]
    require_admitted_job(c, node, job)
    scope = life.slurm_scope(job)
    if not args.worker:
        me = life.identity(os.getpid())
        if me is None or me.uids != (os.getuid(),) * 4:
            raise ValueError("Actual own monitor identity unavailable")
        os.environ["D_CANONICAL_MONITOR_PID"] = str(me.pid)
        os.environ["D_CANONICAL_MONITOR_START"] = str(me.start_ticks)
        guard = guard_class(resources)(c, admit=False)
        # Keep the original Guard process control; the existing resident/managed
        # supervisors own cooperative SAVE_AND_EXIT and complete tree reaping.
        guard.run([sys.executable, "-B", "-m", "tools.d_recipe.canonical_resources", args.command,
                   "--configuration", args.configuration, "--worker"], c["output"])
        return 0
    parent, current = life.identity(os.getppid()), life.identity(os.getpid())
    if (parent is None or current is None or parent.uids != (os.getuid(),) * 4
            or parent.pid != int(os.environ["D_CANONICAL_MONITOR_PID"])
            or parent.start_ticks != int(os.environ["D_CANONICAL_MONITOR_START"])
            or parent.cgroup != current.cgroup or scope not in parent.cgroup.splitlines()):
        raise ValueError("Actual canonical monitor parent UID/start/cgroup differs")
    import torch
    with installed_writers(c, resources), allocated_threads(torch, int(os.environ["SLURM_CPUS_PER_TASK"])):
        module = importlib.import_module("tools.d_recipe." + args.command)
        previous = sys.argv
        try:
            sys.argv = [args.command, "--configuration", args.configuration]
            return module.main()
        finally:
            sys.argv = previous


if __name__ == "__main__":
    raise SystemExit(main())

