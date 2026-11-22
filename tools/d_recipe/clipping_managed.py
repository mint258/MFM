"""Safe continuation of the registered full-TRAIN clipping producer.

Pass its original configuration, closed collection and original report output
unchanged. No runtime scientific configuration is derived or refitted here.
"""
import argparse
import json
import os
from pathlib import Path

from tools.d_recipe import exit_lifecycle as lifecycle
from tools.d_recipe.managed_entry import (
    _query, allocation_end, require_healthy_node, require_local_log)

_ROOT = Path(__file__).resolve().parents[2]


def require_joint_local_reserve(facts, registered_future):
    if type(registered_future) is not int or registered_future < 32 * 2**20:
        raise ValueError("Register joint future local growth, including this log")
    system = max(10 * 2**30, (facts.f_blocks * facts.f_frsize + 9) // 10)
    if facts.f_bavail * facts.f_frsize < system + registered_future:
        raise RuntimeError("Actual local disk does not cover joint future and system reserve")
    if facts.f_favail < 10000:
        raise RuntimeError("Actual local inode reserve unavailable")


def original_worker(configuration, collection, output):
    # clip_report binds its cursor to the entire original configuration.
    # In particular do not pass the training managed entry's runtime clone.
    return ["/bin/bash", str(_ROOT / "tools/d_recipe/clipping.sbatch"),
            configuration, collection, output]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--configuration", required=True)
    parser.add_argument("--collection", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--joint-local-future-bytes", required=True, type=int)
    parser.add_argument("--cleanup-seconds", default=900, type=int)
    args = parser.parse_args()
    job = os.environ.get("SLURM_JOB_ID")
    if not job:
        raise RuntimeError("Real allocation required")
    scope = lifecycle.slurm_scope(job)
    lifecycle.enable_subreaper()
    node = os.uname().nodename.split(".")[0]
    if node not in {"compute-0-%d" % n for n in range(8, 20)}:
        raise RuntimeError("Clipping statistics require a CPU node")
    require_healthy_node(_query(
        ["/usr/bin/scontrol", "show", "node", node, "-o"], scope), node)
    allocation = _query(["/usr/bin/scontrol", "show", "job", job, "-o"], scope)
    end = allocation_end(allocation, job)
    require_local_log(allocation)
    require_joint_local_reserve(os.statvfs("/"), args.joint_local_future_bytes)
    return lifecycle.supervise(
        original_worker(args.configuration, args.collection, args.output),
        end_epoch=end, scope=scope, grace_seconds=args.cleanup_seconds,
        report=lambda event: print(json.dumps(event), flush=True))


if __name__ == "__main__":
    result = main()
    raise SystemExit(128 - result if result < 0 else result)

