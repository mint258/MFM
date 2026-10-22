"""Single metadata-only Slurm coordinator for the predeclared small controls."""
from __future__ import annotations

import argparse
import copy
import fcntl
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

from runtime import ROOT, SOURCE, ENV_PYTHON, DEPS, save, sha


def query(args):
    return subprocess.check_output(args, stdin=subprocess.DEVNULL, text=True, timeout=30)


def completed_result(condition, seed):
    path = ROOT / "reports" / f"{condition}_seed{seed}_latest.json"
    if not path.exists():
        return None
    ref = json.loads(path.read_text())
    assert sha(ref["path"]) == ref["sha256"]
    result = json.loads(Path(ref["path"]).read_text())
    assert result["status"] == "D3_CONDITION_COMPLETE" and result["optimizer_updates"] == 4000
    return result


def source_valid(binding):
    for row in binding["files"]:
        assert sha(row["path"]) == row["sha256"], "D3_REGISTERED_SOURCE_CHANGED"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True)
    args = parser.parse_args()
    assert os.getuid() == 1278 and socket.gethostname().split(".")[0] == "sonmi"
    plan_path = Path(args.plan)
    plan = json.loads(plan_path.read_text())
    phase = plan["phase"]
    control = ROOT / "control" / phase
    control.mkdir(parents=True, exist_ok=True)
    lock = (control / "root.lock").open("a")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    binding_path = ROOT / "configs/D3_source_binding_v4.json"
    binding = json.loads(binding_path.read_text())
    source_valid(binding)
    identity = {"pid": os.getpid(), "uid": os.getuid(), "host": socket.gethostname(),
                "start_ticks": int(Path(f"/proc/{os.getpid()}/stat").read_text().split(")", 1)[1].split()[19]),
                "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
                "source_sha256": sha(__file__), "plan_sha256": sha(plan_path), "started": time.time()}
    save(control / "identity.json", identity)
    ledger_path = control / "jobs.json"
    jobs = json.loads(ledger_path.read_text()) if ledger_path.exists() else {}
    tasks_path = control / "tasks.json"
    tasks = [(name, seed) for name in plan["conditions"] for seed in [0, 1]]
    if tasks_path.exists():
        tasks = [tuple(row) for row in json.loads(tasks_path.read_text())]
    else:
        save(tasks_path, tasks)
    nodes = ["compute-0-20", "compute-0-21", "compute-0-22"]
    stopping = ROOT / "GUIDE_STOP.json"
    try:
        while time.time() - identity["started"] < 72 * 3600:
            if stopping.exists():
                save(control / "status.json", {"status": "STOPPED_BY_GUIDE", "guide_stop": json.loads(stopping.read_text())})
                return
            assert sha(__file__) == identity["source_sha256"], "D3_REGISTERED_SOURCE_CHANGED"
            queue = query(["squeue", "-h", "-u", "zixiao", "-o", "%i|%j|%N|%T"])
            active = {line.split("|")[0]: line.split("|") for line in queue.splitlines() if line}
            results = {f"{condition}_seed{seed}": completed_result(condition, seed) for condition, seed in tasks}
            failures = []
            for key, job in jobs.items():
                if job["job_id"] in active:
                    continue
                rows = query(["sacct", "-j", job["job_id"], "--format=JobIDRaw,State,ExitCode", "-n", "-P"])
                actual = next((row.split("|") for row in rows.splitlines() if row.split("|")[0] == job["job_id"]), None)
                if actual is None:
                    continue
                job["actual_sacct"] = rows
                if actual[1:] == ["COMPLETED", "0:0"] and results.get(key) is None:
                    job.setdefault("first_terminal_metadata_seen", time.time())
                    if time.time() - job["first_terminal_metadata_seen"] < 1200:
                        continue
                if actual[1:] != ["COMPLETED", "0:0"] or results.get(key) is None:
                    failures.append({"condition": key, "actual_parent": actual, "job": job})
            save(ledger_path, jobs)
            if failures:
                save(control / "status.json", {"status": "ORDINARY_FAILURE_NEEDS_ROOT_REVIEW", "failures": failures,
                                               "other_active_scientific_jobs_unchanged": True})
                return
            if all(results.values()) and any(job['job_id'] in active for job in jobs.values()):
                save(control / "status.json", {"status": "WAITING_FOR_ACTUAL_PARENT_CLOSURE", "jobs": jobs})
                time.sleep(60)
                continue
            if all(results.values()):
                if len(tasks) == 2 * len(plan["conditions"]):
                    # Same selected LR, now one or two invariant scalar-message layers.
                    # Do not spend two more A5 fits on an architecture that cannot pass denoising.
                    assert len(plan["scan_groups"]) == 1 and len(plan["conditions"]) == 1
                    reference = plan["new_lookup_reference"]
                    assert sha(reference["path"]) == reference["sha256"]
                    lookup = json.loads(Path(reference["path"]).read_text())
                    assert lookup["status"] == "NEW_TRAIN_LOOKUP_REFIT_AND_FULL_EVALUATION_COMPLETE"
                    assert lookup["TRAIN_records"] == 11104772 and lookup["validation_values_used_for_fit"] is False
                    threshold = lookup["metrics"]["D3_FULL2000"]["lookup_rmse_A"]
                    only = plan["scan_groups"][0]
                    measured = [results[f"{only}_seed{seed}"]["final"]["local_rmse_A"] for seed in [0, 1]]
                    if not all(value < threshold for value in measured):
                        save(control / "status.json", {"status": "D3_MESSAGE_LAYER_CAPABILITY_FAILED", "condition": only,
                            "local_RMSE_A_by_seed": measured, "lookup_FULL2000_RMSE_A": threshold,
                            "message_layers": plan["message_layers"], "jobs": jobs,
                            "A5_not_launched": "Denoising gate failed; follow guide's next message layer or stop after layer2"})
                        return
                    scores = {name: sum(results[f"{name}_seed{s}"]["final"]["local_rmse_A"] for s in [0, 1]) / 2.0 for name in plan["scan_groups"]}
                    best = min(scores, key=lambda name: (scores[name], plan["scan_groups"].index(name)))
                    selection = {"status": "LR_SELECTED_BY_PREDECLARED_FINAL_ENDPOINT", "scores": scores, "selected": best}
                    selection_path = control / "LR_selection.json"
                    if selection_path.exists():
                        assert json.loads(selection_path.read_text()) == selection
                    else:
                        save(selection_path, selection)
                    for seed in [0, 1]:
                        cfg = json.loads((SOURCE / "workflows/s_denoise/configs" / f"{best}_seed{seed}_v3.json").read_text())
                        cfg["condition"] = plan["A5_name"]
                        cfg["loss_policy"]["structural_tasks"] = ["denoise_eps_mse"]
                        weight = cfg["loss_policy"]["task_weights"].get("denoise_eps_mse", 1.0)
                        cfg["total_loss_scale"] = weight / (weight + 2.0)
                        cfg["selected_multitask_group"] = best
                        cfg["selection_evidence"] = {"path": str(control / "LR_selection.json"), "sha256": sha(control / "LR_selection.json")}
                        dest = SOURCE / "workflows/s_denoise/configs" / f"{plan['A5_name']}_seed{seed}_v3.json"
                        if dest.exists():
                            assert json.loads(dest.read_text()) == cfg
                        else:
                            save(dest, cfg)
                    tasks += [(plan["A5_name"], seed) for seed in [0, 1]]
                    save(tasks_path, tasks)
                    continue
                save(control / "status.json", {"status": "D3_PHASE_COMPLETE_AWAITING_SCIENTIFIC_GATE", "tasks": len(tasks), "jobs": jobs})
                return
            occupied_nodes = {row[2] for row in active.values() if row[1].startswith("srepair_")}
            pending = [(condition, seed) for condition, seed in tasks if f"{condition}_seed{seed}" not in jobs]
            for node in nodes:
                if not pending or node in occupied_nodes:
                    continue
                condition, seed = pending[0]
                key = f"{condition}_seed{seed}"
                name = f"{phase}_{condition}s{seed}_n{node.rsplit('-', 1)[1]}"
                script = ROOT / "scripts" / (name + ".sbatch")
                configuration = SOURCE / "workflows/s_denoise/configs" / f"{condition}_seed{seed}_v3.json"
                text = f'''#!/bin/bash
#SBATCH --job-name=srepair_{name}
#SBATCH --partition=all
#SBATCH --nodelist={node}
#SBATCH --cpus-per-task=16
#SBATCH --mem=64G
#SBATCH --time=05:00:00
#SBATCH --output={ROOT}/logs/{name}_%j.log
set -euo pipefail
cd {SOURCE}
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
export PYTORCH_ALLOC_CONF=expandable_segments:True
export PYTHONPATH={SOURCE}/current:{DEPS}
srun --input=none --ntasks=1 --cpus-per-task=16 --cpu-bind=cores {ENV_PYTHON} -B workflows/s_denoise/train_diagnostic.py --configuration {configuration} --source-binding {binding_path}
'''
                if script.exists():
                    assert script.read_text() == text
                else:
                    save(control / "preparing.json", {"condition": key, "node": node})
                    script.write_text(text)
                source_valid(binding)
                quota = query(["quota", "-w"])
                quota_line = next(line.split() for line in quota.splitlines() if line.strip().startswith("/dev/"))
                used = int(quota_line[1].rstrip("*"))
                limits = [int(n) for n in quota_line[2:4] if int(n) > 0]
                assert limits and min(limits) - used > 32 * 1024 ** 2, "D3_OUTPUT_QUOTA_NOT_AVAILABLE"
                phase_bytes = int(query(["du", "-sb", str(ROOT)]).split()[0])
                assert phase_bytes < 32 * (1 << 30), "D3_OUTPUT_BUDGET_REACHED"
                save(control / "quota_latest.json", {"raw": quota, "used_KiB": used,
                     "limit_KiB": min(limits), "current_task_bytes": phase_bytes, "scope": "D3 diagnostic phase only"})
                result = subprocess.run([sys.executable, str(SOURCE / "workflows/s_denoise/submit.py"), str(script), "--node", node, "--cpus", "16", "--mem-gib", "64"], stdin=subprocess.DEVNULL, capture_output=True, text=True)
                receipt = ROOT / "submission" / (script.stem + ".json")
                if result.returncode:
                    save(control / ("waiting_" + node + ".json"), {"condition": key, "reason": result.stderr[-3000:], "timestamp": time.time()})
                    continue
                registered = json.loads(receipt.read_text())
                jobs[key] = {"job_id": registered["job_id"], "script": str(script), "configuration": str(configuration), "configuration_sha256": sha(configuration), "node": node}
                save(ledger_path, jobs)
                pending.pop(0)
            save(control / "status.json", {"status": "D3_RUNNING", "completed": sum(result is not None for result in results.values()),
                                           "expected": len(tasks), "registered_jobs": jobs, "timestamp": time.time()})
            time.sleep(60)
        save(control / "status.json", {"status": "BOUNDED_COORDINATOR_DEADLINE", "jobs": jobs})
    except Exception as exc:
        if "D3_REGISTERED_SOURCE_CHANGED" in str(exc) and not stopping.exists():
            save(stopping, {"reason": "GUIDE_STOP_FROZEN_SOURCE_CHANGED", "error": repr(exc), "phase": phase})
        save(control / "status.json", {"status": "METADATA_COORDINATOR_ERROR", "error": repr(exc), "jobs": jobs})
        raise
    finally:
        lock.close()


if __name__ == "__main__":
    main()
