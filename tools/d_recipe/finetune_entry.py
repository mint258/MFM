"""D transport wrapper around P's unchanged full fine-tuning worker.

This entry submits nothing. Actual source checkpoints, complete main-work
dependency, compliant GPU and own reservations must be bound before launch.
P's source extraction, geometry, optimization and complete-state resume stay
inside the original worker. Scratch predictions are reused separately.
"""
import argparse
import importlib.util
import json
import math
import os
from pathlib import Path
import sys


TASKS = ("qm9.U0_atom", "qm9.homo", "exp.LogD", "exp.LogS")
MAIN_ARMS = ("D-R0", "D-R1", "D-G1", "D-L1", "D-L2", "D-K1")


def fallback_card(row, minimum_free_gpu_mib):
    uuid, name, used, total = [value.strip() for value in row]
    used, total = float(used), float(total)
    if (not all(math.isfinite(x) for x in (used, total, minimum_free_gpu_mib))
            or used < 0 or total < 24000 or minimum_free_gpu_mib <= 0
            or used / total > .30 or total - used < minimum_free_gpu_mib):
        raise ValueError("Actual fallback GPU memory does not meet the registered allowance")
    return dict(uuid=uuid, name=name, memory_used_mib=used, memory_total_mib=total)


def validate(c):
    if (c.get("D_authority") != "docs/d_recipe/USER_DIRECTIVE_20261123.md"
            or c.get("authority") != "docs/p_recipe/USER_DIRECTIVE_20261122B.md"
            or c.get("kind") != "F" or c.get("mode") != "full"
            or c.get("task") not in TASKS or type(c.get("seed")) is not int
            or c["seed"] not in (0, 1, 2)
            or c.get("selection_change_allowed") is not False):
        raise ValueError("Only the prescribed descriptive four-task full fine-tuning protocol")
    source = c["source_binding"]
    if source.get("pretraining_seed") != 0 or not source.get("checkpoint"):
        raise ValueError("Use the original seed0 source checkpoint")
    scope, arm, samples = source.get("scope"), source.get("arm"), source.get("samples")
    allowed = ((scope == "registered_3M" and arm in MAIN_ARMS and samples == 3000000)
               or (scope == "confirmation_9M" and arm in ("9M-D-R0", "9M-D-final")
                   and samples == 9000000)
               or (scope == "selected_9M_budget_curve" and arm == "9M-D-final"
                   and samples in (1000000, 3000000, 6000000, 9000000))
               or (scope == "molecule_scaling_9M" and arm == "9M-D-final"
                   and samples == 9000000 and source.get("molecules") in (250000, 500000)))
    if not allowed:
        raise ValueError("Source endpoint is outside the registered D fine-tuning/scaling scope")
    if scope in ("selected_9M_budget_curve", "molecule_scaling_9M") and c.get("scaling_authority") != "docs/d_recipe/USER_DIRECTIVE_20261123B.md":
        raise ValueError("Additional endpoint requires its existing scaling directive")


def main(configuration):
    c = json.loads(Path(configuration).read_text())
    validate(c)
    # This explicit gate is checked against the real main-study result by Root
    # before materializing a runnable configuration; it is never set by this entry.
    if c.get("registered_main_work_complete") is not True:
        raise ValueError("Supplemental fine-tuning follows the registered main work")
    base = Path("/share/home/zixiao/descriptor_analysis/MFM_p_recipe/tools/p_recipe")
    sys.path.insert(0, str(base))
    spec = importlib.util.spec_from_file_location("d_original_p_finetune_entry", base / "finetune_entry.py")
    entry = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(entry)
    from .shared_admission import admit

    def own_admission(config):
        parent, current = entry.lifecycle.identity(os.getppid()), entry.lifecycle.identity(os.getpid())
        job = os.environ.get("SLURM_JOB_ID")
        if (not job or os.environ.get("D_EXIT_OUTER_SUPERVISION") != "1"
                or parent is None or current is None or parent.uids != (1278,) * 4
                or current.uids != (1278,) * 4
                or parent.pid != int(os.environ["D_RESIDENT_SUPERVISOR_PID"])
                or parent.start_ticks != int(os.environ["D_RESIDENT_SUPERVISOR_START_TICKS"])
                or current.cgroup != parent.cgroup):
            raise ValueError("Actual allocated, supervised D worker identity required")
        entry.lifecycle.slurm_scope(job)
        node = entry.socket.gethostname().split(".")[0]
        if node not in {"compute-0-" + str(i) for i in (*range(8), 20, 22)}:
            raise ValueError("Supplemental fine-tuning requires an admitted allowed GPU node")
        admit(config, [config["output"]])
        entry.validate_output_filesystem(config["output"], config["output_mount"])
        return node

    old_admission, old_repo = entry.admission, entry.REPO
    old_card_check = entry.gpu_lock_and_check

    def card_check(config, stop):
        if entry.socket.gethostname().split(".")[0] not in ("compute-0-20", "compute-0-22"):
            return old_card_check(config, stop)
        import csv
        import fcntl
        locks = Path("/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage46_shared_gpu_launch/.own_gpu_uuid_locks")
        lock = (locks / (config["gpu_uuid"] + ".lock")).open("a")
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if not os.path.isabs(config["nvidia_smi"]):
                raise ValueError("Bind the actual absolute nvidia-smi executable")
            output = entry.native_query([config["nvidia_smi"], "--id=" + config["gpu_uuid"],
                "--query-gpu=uuid,name,memory.used,memory.total", "--format=csv,noheader,nounits"], stop)
            rows = list(csv.reader(output.splitlines()))
            if len(rows) != 1 or rows[0][0].strip() != config["gpu_uuid"]:
                raise ValueError("Actual fallback GPU UUID differs")
            return lock, fallback_card(rows[0], config["minimum_free_gpu_mib"])
        except BaseException:
            lock.close()
            raise
    try:
        entry.admission = own_admission
        entry.gpu_lock_and_check = card_check
        entry.REPO = Path(__file__).resolve().parents[2]
        return entry.main(configuration)
    finally:
        entry.admission, entry.REPO = old_admission, old_repo
        entry.gpu_lock_and_check = old_card_check


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--configuration", required=True)
    raise SystemExit(main(parser.parse_args().configuration))
