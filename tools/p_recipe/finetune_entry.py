"""NEW registered F1 worker. Requires the spooled managed supervisor and admission.

Not validated or enabled yet. Configurations are generated only after actual
healthy target/UUID/resource selection; this entry never submits or steals work.
"""
import argparse
import csv
import fcntl
import json
import os
from pathlib import Path
import socket
import sys
import time
import signal
import subprocess
import datetime
import re
import math
from contextlib import contextmanager
from types import SimpleNamespace

REPO = Path(__file__).resolve().parents[2]
ROOT = Path("/share/home/zixiao/descriptor_analysis")
sys.path[0:0] = [str(REPO / "current"),
    str(ROOT / "runs/data_v1_20261025/repository"),
    str(ROOT / "docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps")]
sys.path.insert(0, str(REPO / "tools"))

import exit_lifecycle as lifecycle
import shared_guard


def admission(c):
    node = socket.gethostname().split(".")[0]
    if node != c["node"] or node not in {"compute-0-"+str(i) for i in range(8)}:
        raise ValueError("F work requires its actual configured0-7 node")
    parent = lifecycle.identity(os.getppid())
    current = lifecycle.identity(os.getpid())
    if (os.environ.get("D_EXIT_OUTER_SUPERVISION") != "1"
            or os.getppid() != int(os.environ["D_RESIDENT_SUPERVISOR_PID"])
            or parent is None or parent.uids != (1278,)*4 or current is None
            or parent.start_ticks != int(os.environ["D_RESIDENT_SUPERVISOR_START_TICKS"])
            or parent.cgroup != current.cgroup):
        raise ValueError("Exact existing-provider parent UID/start/job cgroup is not verified")
    scope = json.loads((shared_guard.REGISTRY / "p-recipe.json").read_text())
    if scope["line"] != "p-recipe" or scope["expires"] < time.time():
        raise ValueError("Current own reservation is absent or expired")
    entries = scope["entries"]
    own = {e["id"]: e for e in entries}
    if not c["reservation_ids"] or not set(c["reservation_ids"]) <= own.keys():
        raise ValueError("Coordinator has not registered this run's future writes/RAM")
    # Own-line simultaneous requests are summed; canonical guard adds all peers.
    paths = shared_guard._same_device("node_disk", "/tmp")
    local = sum(e["bytes"] for e in entries if e["kind"] == "node_disk"
                and e.get("node") == node and e.get("path") in paths)
    ram = sum(e["bytes"] for e in entries if e["kind"] == "node_ram" and e.get("node") == node)
    mount = c["output_mount"]
    validate_output_filesystem(c["output"], mount)
    future = sum(e["bytes"] for e in entries if e["kind"] == "shared_fs" and e.get("path") == mount)
    if local < 32 * 2**20 + 65536 or ram < c["ram_peak_bytes"] or future < c["remaining_output_bytes"]:
        raise ValueError("Own aggregate reservation does not contain this actual run")
    shared_guard.check_with_timeout("p-recipe", "node_disk", local, path="/tmp", node=node)
    shared_guard.check_with_timeout("p-recipe", "node_ram", ram, node=node)
    # The coordinator binds a producer's fresh UID snapshot when one exists.
    # A stale/missing snapshot is not passed as a fictional available-byte value.
    quota = None
    descriptor = c.get("uid_quota_snapshot")
    if descriptor is not None:
        try:
            snapshot = json.loads(Path(descriptor["path"]).read_text())
            age = time.time() - float(snapshot[descriptor["timestamp_field"]])
            if 0 <= age <= descriptor["fresh_seconds"]:
                quota = int(snapshot[descriptor["available_field"]])
        except (OSError, ValueError, KeyError):
            pass  # No fresh optional snapshot; canonical df+registry still apply.
    shared_guard.check_with_timeout("p-recipe", "shared_fs", future,
                                    path=mount, quota_available=quota)
    return node


@contextmanager
def CooperativeStop():
    state = SimpleNamespace(requested=False)
    previous = {}
    def request(signum, frame):
        state.requested = True
    for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGUSR1):
        previous[sig] = signal.signal(sig, request)
    try:
        yield state
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)


def validate_output_filesystem(output, mount, stat=os.stat):
    if mount not in ("/share", "/lfshome") or not str(output).startswith(mount+"/"):
        raise ValueError("Explicit registered canonical output mount required")
    parent = Path(output).parent
    while True:
        try:
            actual = stat(parent)
            break
        except FileNotFoundError:
            if parent.parent == parent:
                raise ValueError("Output ancestor is unavailable")
            parent = parent.parent
    if actual.st_dev != stat(Path(mount)).st_dev:
        raise ValueError("Canonical mount does not identify the actual output filesystem")
    return parent


def native_query(argv, stop):
    # Same Popen/communicate and exact pidfd-scoped TERM mechanism as the
    # existing validated provider. No custom PID/PGID tree scanner is used.
    scope = lifecycle.slurm_scope(os.environ["SLURM_JOB_ID"])
    raw_cutoff = os.environ.get("P_MANAGED_STOP_NEW_UNITS_AT")
    cutoff = float(raw_cutoff) if raw_cutoff else time.time()+15
    if not math.isfinite(cutoff):
        raise ValueError("Native-query cutoff must be finite")
    until = time.monotonic()+min(15,max(0,cutoff-time.time()))
    # Validate the timing before creating any child.
    child = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    bound = lifecycle.identity(child.pid)
    interrupted = False
    while True:
        try:
            out, err = child.communicate(timeout=.2)
            break
        except subprocess.TimeoutExpired:
            if stop.requested or time.monotonic() >= until:
                interrupted = True
                if bound is not None:
                    lifecycle.signal_owned(bound, signal.SIGTERM, uid=os.getuid(), scope=scope)
                try:
                    out, err = child.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    print(json.dumps(dict(stage="ADMIN_REQUIRED_QUERY_EXIT_UNPROVEN",pid=child.pid)),flush=True)
                    out, err = child.communicate()
                break
    if interrupted or child.returncode:
        raise RuntimeError("Native query did not close normally: "+err.decode("utf-8",errors="replace")[:500])
    return out.decode("utf-8",errors="strict")


def set_actual_deadline(c, stop):
    text = native_query(["/usr/bin/scontrol","show","job",os.environ["SLURM_JOB_ID"],"-o"],stop)
    values = dict(re.findall(r"(\w+)=(\S+)",text))
    node = socket.gethostname().split(".")[0]
    if (values.get("JobId") != os.environ["SLURM_JOB_ID"]
            or values.get("JobState") != "RUNNING"
            or values.get("UserId") != "zixiao(1278)"
            or values.get("NodeList") != node or values.get("NumNodes") != "1"
            or values.get("TimeLimit") in (None,"UNLIMITED","Unknown","N/A")):
        raise ValueError("Actual finite native allocation is not verified")
    reserve = c["cleanup_seconds"]
    unit = c["work_unit_seconds"]
    if not isinstance(unit,(int,float)) or not math.isfinite(unit) or unit<=0:
        raise ValueError("A positive bounded/measured work-unit duration is required")
    if not isinstance(reserve,int) or reserve < 180:
        raise ValueError("Actual cleanup reserve must be at least180 seconds")
    end = datetime.datetime.fromisoformat(values["EndTime"]).timestamp()
    os.environ["P_MANAGED_HARD_END"] = str(end)
    os.environ["P_MANAGED_STOP_NEW_UNITS_AT"] = str(end-reserve)
    os.environ["P_MANAGED_UNIT_SECONDS"] = str(unit)

def gpu_lock_and_check(c, stop):
    locks = Path("/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage46_shared_gpu_launch/.own_gpu_uuid_locks")
    lock = (locks / (c["gpu_uuid"] + ".lock")).open("a")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        binary = c["nvidia_smi"]
        if not os.path.isabs(binary):
            raise ValueError("Bind the actual absolute nvidia-smi executable")
        text = native_query([binary, "--id="+c["gpu_uuid"],
            "--query-gpu=uuid,name,memory.used,memory.total", "--format=csv,noheader,nounits"], stop)
        rows = list(csv.reader(text.splitlines()))
        if len(rows) != 1 or rows[0][0].strip() != c["gpu_uuid"]:
            raise ValueError("Target GPU UUID differs")
        _, name, used, total = [x.strip() for x in rows[0]]
        if float(total) < 24000 or float(total)-float(used) < c["minimum_free_gpu_mib"]:
            raise ValueError("Target is not an available24GiB card")
        contexts = native_query([binary, "--query-compute-apps=gpu_uuid,pid",
                                "--format=csv,noheader,nounits"], stop)
        if any(row and row[0].strip() == c["gpu_uuid"] for row in csv.reader(contexts.splitlines())):
            raise ValueError("Registered F work requires an actually empty target GPU")
        return lock, dict(uuid=c["gpu_uuid"], name=name, memory_used_mib=float(used),
                         memory_total_mib=float(total))
    except BaseException:
        lock.close()
        raise


def main(configuration):
    attempt_started = time.time()
    c = json.loads(Path(configuration).read_text())
    if c.get("authority") != "docs/p_recipe/USER_DIRECTIVE_20261122B.md" or c.get("kind") != "F":
        raise ValueError("Only the registered F protocol may enter this worker")
    if c.get("ready") is not True:
        raise ValueError("Configuration is not activated after required validation")
    closed = Path(c["output"]) / "summary.json"
    if closed.is_file() and json.loads(closed.read_text()).get("status") == "COMPLETE":
        raise ValueError("This producer already closed; preserve its outputs and do not rerun")
    with CooperativeStop() as stop:
        set_actual_deadline(c, stop)
        if stop.requested or time.time()+float(os.environ["P_MANAGED_UNIT_SECONDS"]) >= float(os.environ["P_MANAGED_STOP_NEW_UNITS_AT"]):
            return 75
        node = admission(c)
        lock, card = gpu_lock_and_check(c, stop)
        continuation_type = None
        try:
            os.environ["CUDA_VISIBLE_DEVICES"] = c["gpu_uuid"]
            # Heavy/shared scientific imports occur only inside the supervised,
            # admitted child, with the parent independent of shared source I/O.
            import torch
            from torch_geometric.data import Batch, Data
            from phychem_mfm.phase1.v2_s_training import s_model
            from phychem_mfm.phase1.v3_dev_evaluation import TaskSpec, task_rows
            from phychem_mfm.phase1.v3_dev_evaluation_v2 import _pack
            from phychem_mfm.phase1.v3_dev_membership import GroupedTrainingView
            from phychem_mfm.phase1.v3_dev_store import TrainOnlyPackedStore
            from phychem_mfm.phase1.v3_downstream_targets import atomization_rows, ATOMIZATION_TASK_ID
            from phychem_mfm.phase1.v3_latent_evaluation import cached_rows
            from finetune import run_finetune, ContinuationRequired, TASKS, MODES
            continuation_type = ContinuationRequired
            if c["task"] not in TASKS or c["mode"] not in MODES or c["seed"] not in (0, 1, 2):
                raise ValueError("Unregistered task/mode/finetuning seed")
            cpus = int(os.environ["SLURM_CPUS_PER_TASK"])
            if cpus < c["cpus"]:
                raise ValueError("Insufficient actual allocated CPUs")
            torch.set_num_threads(cpus)
            torch.set_float32_matmul_precision("highest")
            torch.backends.cuda.matmul.allow_tf32 = False
            torch.backends.cudnn.allow_tf32 = False
            output = Path(c["output"])
            output.mkdir(parents=True, exist_ok=True)
            cutoff = float(os.environ["P_MANAGED_STOP_NEW_UNITS_AT"])
            unit = float(os.environ["P_MANAGED_UNIT_SECONDS"])
            def should_stop():
                return stop.requested or time.time()+unit >= cutoff
            if should_stop():
                return 75
            state_path = output / "complete_state.pt"
            saved = torch.load(state_path, map_location="cpu", weights_only=True) if state_path.is_file() else None
            torch.manual_seed(c["seed"])
            torch.cuda.manual_seed_all(c["seed"])
            source = None
            if saved is not None:
                init = saved["initial_architecture"]
            else:
                source = torch.load(c["source_binding"]["checkpoint"], map_location="cpu", weights_only=True)
                base = source["configuration"]
                spec = source.get("architecture", {}).get("backbone", {}).get("v3_latent")
                init = dict(distance_bias=base["distance_bias"], views=base["views"], latent_spec=spec)
            spec = init["latent_spec"]
            model, _ = s_model(init["distance_bias"], init["views"],
                              latent="none" if spec is None else spec["kind"], latent_config=spec)
            if source is not None and c["mode"] != "scratch":
                weights = source["model"]
                if any(key.startswith("structural.") for key in weights):
                    weights = {key.removeprefix("structural."): value for key, value in weights.items()
                               if key.startswith("structural.")}
                model.load_state_dict(weights)
                del weights
            encoder = model.encoder.cuda().eval()
            del model, source
            panel = json.loads((REPO/"configs/dev_panel_v3.json").read_text())
            row = next(x for x in panel["tasks"] if x["task_id"] == c["task"])
            task = TaskSpec(**{key: row[key] for key in
                ("task_id", "dataset_id", "field", "output_level", "error_metric", "pooling")})
            store = TrainOnlyPackedStore(c["store"], verify_digests=False)
            view = GroupedTrainingView(store, task.dataset_id,
                "official" if task.dataset_id == "expansionrx" else "0", store.group_map)
            members = [(index, view.get(index, role=role)) for role in
                       ("train", "train_inner_validation") for index in view.view(role)]
            members = [(index, sample) for index, sample in members if sample.geometry_ready]
            fit = set(view.view("train"))
            sizes = [len(sample.x) for index, sample in members if index in fit]
            n_ref = sum(sizes)/len(sizes)
            records, geometries = [], {}
            with torch.no_grad():
                for start in range(0, len(members), 32):
                    if should_stop():
                        raise ContinuationRequired("No training update yet; original inputs retained")
                    selected = members[start:start+32]
                    if saved is None:
                        batch = Batch.from_data_list([Data(x=s.x.reshape(-1, 1), pos=s.pos)
                                                     for _, s in selected]).cuda()
                        atom = encoder.encode_atoms(batch).detach().cpu().float()
                    cursor = 0
                    for index, sample in selected:
                        count = len(sample.x)
                        h0 = (atom[cursor:cursor+count] if saved is None else
                              torch.zeros(count, saved["normalization"]["keep"].numel()))
                        records.append(dict(molecule_uid=sample.member_uid, member_index=index,
                                            h0=h0, source_atom_ids=sample.source_atom_ids))
                        geometries[sample.member_uid] = sample
                        cursor += count
            cached = cached_rows(dict(records=records, n_ref=n_ref))
            rows = atomization_rows if task.task_id == ATOMIZATION_TASK_ID else task_rows
            train = rows(view, cached, task, role="train")
            evaluation = rows(view, cached, task, role="train_inner_validation")
            class History:
                def log(self, row, *, step, commit):
                    with (output/"history.jsonl").open("a") as stream:
                        stream.write(json.dumps(dict(timestamp=time.time(), step=step, **row))+"\n")
            started = time.time()
            prediction, detail = run_finetune(encoder, train, evaluation, geometries, task,
                mode=c["mode"], seed=c["seed"], n_ref=n_ref, output=output,
                tracker=History(), should_stop=should_stop, source_binding=c["source_binding"],
                initial_architecture=init, resume_state=saved, device="cuda")
            # Original-unit predictions only; CPU producer handles paired F64
            # bootstrap and distinct per-seed/ensemble estimands.
            torch.save(dict(prediction=_pack(prediction), detail=detail), output/"prediction.pt")
            summary = dict(status="COMPLETE", configuration=str(configuration), node=node,
                job_id=os.environ["SLURM_JOB_ID"], card=card, detail=detail,
                membership_sha256=view.membership_sha256,
                producer_seconds_this_attempt=time.time()-attempt_started,
                optimization_and_selection_seconds_this_attempt=time.time()-started,
                geometry="original R3 native source geometry", no_bootstrap_on_gpu=True)
            (output/"summary.json").write_text(json.dumps(summary, indent=2)+"\n")
            return 0
        except BaseException as error:
            if continuation_type is not None and isinstance(error, continuation_type):
                return 75
            raise
        finally:
            lock.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--configuration", required=True)
    raise SystemExit(main(parser.parse_args().configuration))
