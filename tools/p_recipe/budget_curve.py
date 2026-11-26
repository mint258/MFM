"""The 22 authorized L6/H0 readouts of existing 9M checkpoints; no training."""
import argparse
import contextlib
import csv
import io
import json
import os
from pathlib import Path
import runpy
import shlex
import socket
import subprocess
import time

from checkpoint_paths import evaluation_checkpoint
from execution_ledger import C, locked_ledger, read, write

REPO = Path(__file__).resolve().parents[2]
PROJECT = C.parents[1]
PLAN = REPO / "configs/p_recipe/fixed_20261115/confirmation/budget_curve_plan.json"
OUTPUT = C / "budget_curve_20261122"
CONFIGURATIONS = C / "fixed_20261115/budget_curve_configurations"
PYTHON = "/share/home/zixiao/.venvs/model_v2_cu118_20261105/bin/python"
AUTHORITY = "docs/p_recipe/USER_DIRECTIVE_20261121.md"
POOL_BYTES = 3 * 2**30
READOUT_BYTES = 128 * 2**20
WAITING = "GPU_READOUT_COMPLETE_WAITING_CPU_STATISTICS"
GPU_NODES = {"compute-0-" + str(i) for i in range(8)}
STORE = PROJECT / "runs/model_v3_20261025/selected_train_store_4520421/native_store/training_store.json"


def expected_points():
    return [(arm, n * 1000000) for arm in ("T2", "T1", "T4", "T5", "T6")
            for n in (range(1, 9) if arm in ("T1", "T2") else (3, 6))]


def validate_plan(plan):
    points = [(row["arm"], row["samples"]) for row in plan["readouts"]]
    if plan["authority"] != AUTHORITY or points != expected_points():
        raise ValueError("Only the 22 ordered, explicitly authorized checkpoint readouts are allowed")
    if plan["source_training_budget"] != 9000000:
        raise ValueError("Intermediate checkpoints belong to their original 9M schedule")
    if any(row.get("layer") != 6 or row.get("representation") != "H0"
           for row in plan["readouts"]):
        raise ValueError("The budget curve uses only L6/H0")
    if any(plan.get(key) for key in ("new_training", "new_seeds", "normalization_changes",
                                      "stop_or_migrate_training")):
        raise ValueError("The descriptive curve cannot change the training study")
    return plan


def validate_card(node, gpu, cards, contexts, allocated_cpus=None):
    if node not in GPU_NODES:
        raise ValueError("Budget readouts are restricted to compute-0-0..7")
    card = next((row for row in cards if row["uuid"] == gpu), None)
    if card is None or not 23000 <= card["total_mib"] <= 25000:
        raise ValueError("An actual 24GiB card is required; preserve >=36GiB cards for S")
    if any(row["gpu_uuid"] == gpu for row in contexts):
        raise ValueError("The selected GPU has an existing compute context")
    if card["total_mib"] - card["used_mib"] < 22000:
        raise ValueError("The 24GiB GPU has insufficient free memory")
    if allocated_cpus is not None and allocated_cpus < 16:
        raise ValueError("The original evaluator needs 16 allocated CPUs")
    return card


def gpu_facts():
    cards = [dict(uuid=row[0].strip(), used_mib=float(row[1]), total_mib=float(row[2]))
             for row in csv.reader(subprocess.check_output(
                 ["nvidia-smi", "--query-gpu=uuid,memory.used,memory.total",
                  "--format=csv,noheader,nounits"], text=True, timeout=15).splitlines())]
    contexts = [dict(gpu_uuid=row[0].strip(), pid=int(row[1]))
                for row in csv.reader(subprocess.check_output(
                    ["nvidia-smi", "--query-compute-apps=gpu_uuid,pid",
                     "--format=csv,noheader,nounits"], text=True, timeout=15).splitlines()) if row]
    return cards, contexts


def source_complete(source, ledger):
    record = ledger.get("runs", {}).get(source["run"], {})
    if record.get("state") != "COMPLETED" or record.get("exit_code") not in (0, "0:0"):
        return False
    cpu = ledger.get("cpu_statistics", {}).get(source["run"], {})
    if source.get("statistics_backend") == "slurm_cpu" and (
            cpu.get("state") != "COMPLETED" or cpu.get("exit_code") not in (0, "0:0")):
        return False
    summary_path = Path(source["output"]) / "summary.json"
    if not summary_path.is_file():
        return False
    summary = read(summary_path)
    return (source["samples"] == 9000000 and summary.get("samples") == 9000000
            and summary.get("status") == "COMPLETE" and summary.get("statistics_complete") is True)


def make_configuration(source, row, *, output_root=OUTPUT, resolver=evaluation_checkpoint):
    if source["arm"] != row["arm"] or source["samples"] != 9000000:
        raise ValueError("Wrong source arm or original training budget")
    if (row["arm"], row["samples"]) not in expected_points():
        raise ValueError("No new 9M endpoint or unregistered checkpoint")
    if row.get("layer") != 6 or row.get("representation") != "H0":
        raise ValueError("Only L6/H0 is authorized")
    checkpoint = Path(resolver(source, row["samples"]))
    run = "fixed_20261115_budget_" + row["id"]
    output = Path(output_root) / run
    # Do not edit or inherit training control/resume fields into the new readout.
    return dict(run=run, arm=row["arm"], stage=0, round=0,
                study_revision="fixed_20261115", samples=row["samples"],
                source_run=source["run"], source_configuration=row["source_configuration"],
                source_training_budget=9000000, checkpoint=str(checkpoint),
                checkpoint_resolver="checkpoint_paths.evaluation_checkpoint",
                layer=6, representation="H0", output=str(output),
                features=str(output / "features_not_persisted"), persist_features=False,
                store=str(STORE), statistics_backend="slurm_cpu",
                evaluation_samples=[row["samples"]], budget_curve=True,
                authority=AUTHORITY, bootstrap_samples=1000, bootstrap_seed=20261025,
                descriptive_only=True, new_training=False, new_seeds=False)


def physical_bytes(directory):
    total = 0
    seen = set()
    if not Path(directory).exists():
        return total
    for path in Path(directory).rglob("*"):
        info = path.lstat()
        if path.is_symlink():
            raise RuntimeError("No output symlink or unbudgeted cache in the readout scope")
        if path.is_file():
            if info.st_uid != os.getuid():
                raise RuntimeError("Unknown output owner")
            key = (info.st_dev, info.st_ino)
            if key not in seen:
                total += info.st_blocks * 512
                seen.add(key)
    return total


def admit_joint_storage():
    """Add declared same-node root futures before the existing fresh joint NFS guard."""
    node = socket.gethostname().split(".")[0]
    resources = read(PLAN)["resources"]
    peers = resources.get("declared_peer_root_future_bytes")
    if not isinstance(peers, dict):
        raise RuntimeError("Declared same-node peer root futures are missing")
    peer = int(peers.get(node, 0))
    if peer < 0:
        raise ValueError("A peer reservation cannot be negative")
    disk = runpy.run_path(str(REPO / "tools/model_v3/v2_diagnosis_disk.py"))
    disk["m"].require_capacity(disk["m"].filesystem_status("/"), 16777216 + peer, 2000)
    with contextlib.redirect_stdout(io.StringIO()):
        return runpy.run_path(str(C / "fixed_20261115/confirmation_storage_admission_20261120.py"))


def admit_storage(configuration):
    """Fresh actual-node joint admission; the 3GiB claim is counted exactly once."""
    registry = PROJECT / "MFM_d_descriptors_20261120/configs/data_d_descriptors/storage_reservations.json"
    reservations = read(registry)
    if reservations.get("registered_model_share_components", {}).get(
            "P_confirmation_budget_curve", 0) < POOL_BYTES:
        raise RuntimeError("The new P readout pool has not been registered with shared peers")
    output = Path(configuration["output"]).resolve()
    if not output.is_relative_to(OUTPUT.resolve()):
        raise RuntimeError("Budget readout output must remain inside its own registered NFS scope")
    parent = output
    while not parent.exists():
        parent = parent.parent
    if os.stat(parent).st_dev != os.stat(C).st_dev:
        raise RuntimeError("No local disk or Lustre output fallback")
    if physical_bytes(OUTPUT) >= POOL_BYTES:
        raise RuntimeError("Readout pool is full; preserve outputs and stop adding writes")
    if physical_bytes(output) >= READOUT_BYTES:
        raise RuntimeError("This readout exhausted its output allowance")
    # This established guard reads the latest D/S/B0/benchmark claims and fresh UID quota.
    admit_joint_storage()


def run_readout(configuration):
    """Only the original GPU feature/probe producer; CPU bootstrap is deferred."""
    c = configuration
    if not c.get("budget_curve") or c.get("new_training") or c.get("new_seeds"):
        raise ValueError("Not an authorized existing-checkpoint readout")
    if c.get("layer") != 6 or c.get("persist_features") is not False:
        raise ValueError("Only nonpersistent L6/H0 features")
    source = read(c["source_configuration"])
    if not source_complete(source, read(C / "study_execution.json")):
        raise RuntimeError("The source 9M producer and its original endpoint must finish first")
    if str(evaluation_checkpoint(source, c["samples"])) != c["checkpoint"]:
        raise ValueError("Checkpoint ancestry changed; inspect rather than guessing a checkpoint")
    output = Path(c["output"])
    if (output / "summary.json").exists():
        raise RuntimeError("Readout summary already exists; inspect the existing execution")
    admit_storage(c)
    output.mkdir(parents=True, exist_ok=True)
    write(output / "configuration.json", c)
    started = time.monotonic()
    from evaluate import run
    run(dict(c, output=str(output / "readout")))
    seconds = time.monotonic() - started
    write(output / "summary.json", dict(
        run=c["run"], samples=c["samples"], status=WAITING, statistics_complete=False,
        statistics_backend="slurm_cpu", source_run=c["source_run"],
        source_training_budget=9000000, training_performed=False,
        gpu_readout_seconds=seconds, training_and_gpu_readout_seconds=seconds,
        gpu_job_id=os.environ.get("SLURM_JOB_ID"), gpu_node=socket.gethostname().split(".")[0],
        gpu_uuid=c["gpu_uuid"]))
    return dict(run=c["run"], status=WAITING, gpu_readout_seconds=seconds)


def launch(configuration_path):
    c = read(configuration_path)
    node = socket.gethostname().split(".")[0]
    if not os.environ.get("SLURM_JOB_ID"):
        raise ValueError("A real ordinary GPU sbatch allocation is required")
    cards, contexts = gpu_facts()
    validate_card(node, c["gpu_uuid"], cards, contexts,
                  int(os.environ.get("SLURM_CPUS_PER_TASK", 0)))
    admit_storage(c)
    from native_run import run
    return run(dict(
        run=c["run"], node=node, gpu_uuid=c["gpu_uuid"], execution="Slurm",
        gpu_work=True, output=c["output"], budget_curve_storage=True,
        minimum_free_gpu_mib=22000, root_future_bytes=16777216,
        nfs_future_bytes=67108864,
        state_path=str(C / (c["run"] + "_slurm.json")),
        command=[PYTHON, "-B", "-u", "tools/p_recipe/budget_curve.py",
                 "--readout-configuration", str(configuration_path)]))


def choose_row(plan, ledger):
    """Choose the highest-priority ready point; existing handles are never resubmitted."""
    validate_plan(plan)
    available = {}
    for row in plan["readouts"]:
        if row.get("state") == "COMPLETE":
            continue
        if row.get("configuration"):
            c = read(row["configuration"])
            summary = Path(c["output"]) / "summary.json"
            record = ledger["runs"].get(c["run"], {})
            statistics = ledger.get("cpu_statistics", {}).get(c["run"], {})
            if (record.get("state") == "COMPLETED" and record.get("exit_code") in (0, "0:0")
                    and statistics.get("state") == "COMPLETED"
                    and statistics.get("exit_code") in (0, "0:0")
                    and summary.is_file() and read(summary).get("status") == "COMPLETE"):
                row["state"] = "COMPLETE"
            # A live/queued/failed/uncertain handle must be inspected, never duplicated.
            # Other authorized points can use a different actually free card.
            continue
        filename = row["source_configuration"]
        if filename not in available:
            available[filename] = source_complete(read(filename), ledger)
        if available[filename]:
            return row
    return None


def submit(plan_path, node, gpu):
    """One held native submission, recorded before release; never guess a lost job ID."""
    import fcntl
    lock_path = C / "fixed_20261115/budget_curve_submission.lock"
    with lock_path.open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        plan = validate_plan(read(plan_path))
        ledger = read(C / "study_execution.json")
        row = choose_row(plan, ledger)
        if row is None:
            write(plan_path, plan)
            return dict(status="WAITING_EXISTING_PRODUCER_OR_READOUT", submitted=False)
        remote = ("import sys,json;sys.path.insert(0,'tools/p_recipe');"
                  "from budget_curve import gpu_facts,validate_card;"
                  "cards,contexts=gpu_facts();"
                  "print(json.dumps(validate_card(" + repr(node) + "," + repr(gpu)
                  + ",cards,contexts)))")
        facts = subprocess.check_output(
            ["ssh", "-n", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", node,
             "cd " + shlex.quote(str(REPO)) + " && "
             + shlex.join([PYTHON, "-B", "-c", remote])], text=True, timeout=30)
        state = subprocess.check_output(["scontrol", "show", "node", node, "-o"],
                                        text=True, timeout=15)
        node_values = dict(part.split("=", 1) for part in state.split() if "=" in part)
        if ("gpu" not in node_values.get("Partitions", "").split(",") or
                int(node_values.get("CPUTot", 0)) - int(node_values.get("CPUAlloc", 0)) < 16):
            raise RuntimeError("Insufficient allocatable GPU-node CPUs; no exclusive or SSH fallback")
        source = read(row["source_configuration"])
        c = make_configuration(source, row)
        c.update(node=node, gpu_uuid=gpu)
        # The actual-node launch performs fresh storage admission before any scientific output.
        CONFIGURATIONS.mkdir(parents=True, exist_ok=True)
        filename = CONFIGURATIONS / (row["id"] + ".json")
        if filename.exists() or Path(c["output"]).exists():
            raise RuntimeError("Existing configuration/output requires handle inspection, not resubmission")
        write(filename, c)
        row.update(configuration=str(filename), run=c["run"], state="SUBMITTING",
                   node=node, gpu_uuid=gpu, submitted_at=time.time())
        write(plan_path, plan)
        with locked_ledger() as current:
            current["runs"][c["run"]] = dict(
                backend="Slurm", node=node, gpu_uuid=gpu, state="SUBMITTING",
                configuration=str(filename), stage=0, round=0, submitted_at=row["submitted_at"],
                study_revision="fixed_20261115", purpose="Authorized descriptive budget-curve GPU readout",
                new_training=False, cpu_count=16, exclusive=False)
        command = ["sbatch", "--parsable", "--hold", "--partition=gpu", "--nodes=1",
                   "--nodelist=" + node, "--cpus-per-task=16",
                   "--job-name=" + c["run"], "--output=" + str(C / (c["run"] + "_%j.log")),
                   str(REPO / "tools/p_recipe/budget_curve.sbatch"), str(filename)]
        try:
            job = int(subprocess.check_output(command, cwd=REPO, text=True,
                                               timeout=30).strip().split(";")[0])
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            row.update(state="SUBMISSION_OBSERVATION_UNCERTAIN", observation_error=str(error))
            write(plan_path, plan)
            raise
        row.update(gpu_job_id=job, state="HELD_NATIVE_ID_RECORDED")
        write(plan_path, plan)
        with locked_ledger() as current:
            current["runs"][c["run"]].update(job_id=job, state="PENDING")
        subprocess.check_call(["scontrol", "release", str(job)], timeout=30)
        row["state"] = "SUBMITTED"
        plan["status"] = "READOUTS_SUBMITTED"
        write(plan_path, plan)
        return dict(status="SUBMITTED", job_id=job, run=c["run"], actual_card=json.loads(facts))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--launch-configuration")
    mode.add_argument("--readout-configuration")
    mode.add_argument("--submit", action="store_true")
    parser.add_argument("--plan", default=str(PLAN))
    parser.add_argument("--node")
    parser.add_argument("--gpu")
    args = parser.parse_args()
    if args.launch_configuration:
        return launch(args.launch_configuration)
    if args.readout_configuration:
        print(json.dumps(run_readout(read(args.readout_configuration))), flush=True)
        return 0
    print(json.dumps(submit(args.plan, args.node, args.gpu)), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
