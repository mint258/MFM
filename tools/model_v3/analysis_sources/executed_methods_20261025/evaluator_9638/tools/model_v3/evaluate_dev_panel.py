#!/usr/bin/env python3
"""Execute the frozen TRAIN-only panel from an explicit byte-bound request.

No submission occurs here. The root coordinator supplies a single-GPU Slurm
allocation and its resource supervision. --validate-only reads metadata only.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).absolute().parents[2]
sys.path.insert(0, str(ROOT / "current"))


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024**2), b""):
            digest.update(block)
    return digest.hexdigest()


def exclusive_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n"); stream.flush(); os.fsync(stream.fileno())


def configure_wandb_layout(output):
    """Declare the site's canonical owned SDK paths before importing W&B."""
    output = Path(output).absolute()
    if not output.is_dir() or output.is_symlink():
        raise ValueError("An owned ordinary evaluation output directory is required")
    paths = {"WANDB_DIR": output, "WANDB_CACHE_DIR": output / "cache",
             "WANDB_DATA_DIR": output / "wandb_data"}
    for path in paths.values():
        if path.is_symlink():
            raise ValueError("Canonical W&B directories must not be symlinks")
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
        if not path.is_dir():
            raise ValueError("Canonical W&B path must be a directory")
    os.environ.update({name: str(path) for name, path in paths.items()})
    os.environ["WANDB_MODE"] = "offline"
    return {name: str(path) for name, path in paths.items()}


def _model_config(value):
    from phychem_mfm.phase1.v3_encoder_bridge import source_model_configuration
    return source_model_configuration(value)


def load_plan(request_path, request_sha, *, allow_unbound_packing=False):
    from phychem_mfm.phase1.v3_dev_store import bound_json, TrainOnlyPackedStore
    from phychem_mfm.phase1.v3_dev_membership import GroupedTrainingView
    from phychem_mfm.phase1.v3_dev_evaluation import TaskSpec
    from phychem_mfm.phase1.v3_dev_panel import canonical
    from phychem_mfm.phase1.v3_h0_packing import budget_arguments, packing_plans_for_views
    request = bound_json(request_path, request_sha)
    if request.get("schema") != "model_v3_dev_evaluation_request_v1":
        raise ValueError("Explicit model v3 development evaluation request required")
    for key in ("code_sha", "preregistration_sha"):
        if not re.fullmatch(r"[0-9a-f]{40}", request.get(key, "")):
            raise ValueError("Actual code/preregistration commit bindings required")
    if type(request.get("pretraining_seed")) is not int or request["pretraining_seed"] < 0:
        raise ValueError("The candidate checkpoint's actual pretraining seed is required")
    for key in ("output_root", "cache_root"):
        if Path(request[key]).resolve().is_relative_to(ROOT.resolve()):
            raise ValueError("Evaluation products and H0 must stay outside Git")
    if not 60 <= request["maximum_wall_seconds"] <= 7200 or request["device"] != "cuda:0":
        raise ValueError("One GPU and an explicit bounded runtime are required")
    budget_arguments(request.get("h0_packing"))
    if canonical(request["h0_packing"]) != request.get("h0_packing_budget_sha256"):
        raise ValueError("The requested H0 packing budget/recipe hash differs")
    panel_ref, store_ref = request["panel"], request["training_store"]
    panel = bound_json(panel_ref["path"], panel_ref["sha256"])
    if (panel.get("schema") != "model_v3_dev_panel_v1"
            or panel.get("status") != "FROZEN_TASKS_AND_RULES_AWAITING_PHYSICAL_BINDINGS"
            or len(panel.get("tasks", [])) != 9):
        raise ValueError("Frozen nine-task panel required; candidate definitions cannot execute")
    store = TrainOnlyPackedStore(store_ref["path"], store_ref["sha256"])
    if store.data_version != request["data_version"]:
        raise ValueError("TRAIN source data version differs")
    tasks = tuple(TaskSpec(**{key: row[key] for key in (
        "task_id", "dataset_id", "field", "output_level", "error_metric", "pooling")}) for row in panel["tasks"])
    select = panel["source_roles"]["selection"]
    views = {}
    for dataset in sorted({task.dataset_id for task in tasks}):
        fold = "official" if dataset == "expansionrx" else panel["source_roles"]["scaffold_datasets"]["fold_id"]
        view = GroupedTrainingView(store, dataset, fold, store.group_map,
            seed=select["seed"], max_train_groups=select["max_train_molecule_groups"],
            max_validation_groups=select["max_inner_validation_molecule_groups"])
        if any(task.field not in view.tasks or task.output_level != view.output_level
               for task in tasks if task.dataset_id == dataset):
            raise ValueError("Selected fields differ from native frozen target declarations")
        views[dataset] = view
    plans = packing_plans_for_views(store, views, request["h0_packing"])
    actual = {dataset: plan["plan_sha256"] for dataset, plan in plans.items()}
    pinned = request.get("h0_packing_plan_sha256", {})
    if pinned and pinned != actual:
        raise ValueError("The pinned H0 packing plan differs; members or budgets drifted")
    if not pinned and not allow_unbound_packing:
        raise ValueError("Actual execution requires metadata-planned per-dataset H0 packing hashes")
    if request.get("packing_binding_status") != ("BOUND" if pinned else "METADATA_PLANNING_REQUIRED"):
        raise ValueError("The H0 packing binding state is inconsistent")
    config_ref = request["model_configuration"]
    config = _model_config(bound_json(config_ref["path"], config_ref["sha256"]))
    architecture_sha = canonical(config)
    if architecture_sha != request["architecture_sha256"]:
        raise ValueError("Architecture/configuration binding differs")
    if request.get("reference_kind", "primary") == "primary":
        if (config["backbone"]["dim"], config["backbone"]["layers"]) != (512, 6):
            raise ValueError("Primary v3 panel requires the declared 512x6 model")
    elif request["reference_kind"] != "historical_sanity_only":
        raise ValueError("Historical results must be explicitly descriptive")
    elif request.get("historical_reference") is None:
        raise ValueError("Historical B3 evaluation requires frozen physical reference metadata")
    for reference in request["source_files"]:
        path = ROOT / reference["path"]
        if not path.resolve().is_relative_to(ROOT.resolve()) or sha(path) != reference["sha256"]:
            raise ValueError("Executed source bytes differ from the root-bound request")
    if not request["source_files"]:
        raise ValueError("A nonempty exact source inventory is required")
    return request, panel, store, views, tasks, config


class RunJournal:
    def __init__(self, run, output, started, maximum_wall_seconds):
        self.run, self.started, self.maximum = run, started, maximum_wall_seconds
        self.stream = (output / "history.jsonl").open("x", encoding="utf-8")
        self.step = 0

    def check(self):
        if time.monotonic()-self.started > self.maximum:
            raise TimeoutError("The declared development-evaluation runtime was exhausted")

    def scoped(self, prefix):
        parent = self
        class Scoped:
            disabled = False
            def __init__(self):
                self.next_step = 0
            def log(self, row, *, step, commit):
                if step != self.next_step or commit is not True:
                    raise ValueError("Readout history cursor or explicit commit differs")
                parent.check()
                record = {prefix+"/"+key: value for key, value in row.items()}
                parent.run.log(record, step=parent.step, commit=True)
                parent.stream.write(json.dumps({"step": parent.step, **record}, allow_nan=False)+"\n")
                parent.stream.flush(); os.fsync(parent.stream.fileno())
                self.next_step += 1; parent.step += 1
        return Scoped()

    def close(self):
        self.stream.close()


def execute(request_path, request_sha):
    import fcntl
    started = time.monotonic()
    request, panel, store, views, tasks, config = load_plan(request_path, request_sha)
    if os.getuid() != 1278 or not os.environ.get("SLURM_JOB_ID") or int(os.environ.get("SLURM_CPUS_PER_TASK", "0")) < 16:
        raise RuntimeError("Execute only inside the root coordinator's owned 16-CPU Slurm allocation")
    uuid = os.environ.get("CUDA_VISIBLE_DEVICES", "")
    if not re.fullmatch(r"GPU-[0-9a-fA-F-]{16,64}", uuid):
        raise RuntimeError("The coordinator must bind one full, measured GPU UUID")
    shared_locks = Path("/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage46_shared_gpu_launch/.own_gpu_uuid_locks")
    lock = (shared_locks / (uuid+".lock")).open("a")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    output = Path(request["output_root"])
    output.mkdir(parents=True, exist_ok=False)
    journal = run = None
    status = "FAILED"
    try:
        from phychem_mfm.phase1.v3_h0_packing import (packing_plans_for_views,
            budget_arguments, H0PackingBudgetError)
        packing = packing_plans_for_views(store, views, request["h0_packing"])
        for dataset, view in views.items():
            exclusive_json(output / ("membership_"+dataset+".json"), view.membership)
            exclusive_json(output / ("packing_"+dataset+".json"), packing[dataset])
        for plan in packing.values():
            if plan["oversized_singleton_ordinals"]:
                raise H0PackingBudgetError(plan)
        configure_wandb_layout(output)
        import numpy as np
        import torch
        import wandb
        from phychem_mfm.phase1.v3_encoder_bridge import load_encoder_pair
        from phychem_mfm.phase1.v3_dev_panel import NativeGeometry, FrozenH0Cache, canonical
        from phychem_mfm.phase1.v3_dev_evaluation import task_rows, ridge_probe, nonlinear_probe, error, compare_panel
        if torch.cuda.device_count() != 1:
            raise RuntimeError("Exactly one CUDA device must be visible")
        torch.set_num_threads(16)
        # Membership and its target-free packing were already written above,
        # before opening a target frame or encoding any checkpoint.
        run = wandb.init(project=request["wandb_project"], mode="offline", dir=str(output),
            name=request["run_id"], config={"request_sha256": request_sha,
                "code_sha": request["code_sha"], "preregistration_sha": request["preregistration_sha"],
                "data_version": request["data_version"], "architecture_sha256": request["architecture_sha256"],
                "job_id": os.environ["SLURM_JOB_ID"], "gpu_uuid": uuid,
                "panel_sha256": request["panel"]["sha256"], "pretraining_seed": request["pretraining_seed"],
                "random_reference_initialization_seed": 20261025,
                "readout_seed": panel["readouts"]["linear64_relu"]["seed"]})
        if run is None or run.disabled:
            raise RuntimeError("Persistent W&B tracking is required")
        journal = RunJournal(run, output, started, request["maximum_wall_seconds"])
        state_key = request["checkpoint"]["state_key"]
        pair = load_encoder_pair(request["checkpoint"], request["model_configuration"],
            architecture_sha256=request["architecture_sha256"], pretraining_seed=request["pretraining_seed"],
            reference_kind=request.get("reference_kind", "primary"), random_seed=20261025,
            historical_reference=request.get("historical_reference"),
            expected_state_key=None if state_key == "auto" else state_key)
        candidate, reference = pair.candidate, pair.random_reference
        exclusive_json(output / "encoder_pair.json", pair.provenance)
        cache = FrozenH0Cache(request["cache_root"], repository_root=ROOT)
        predictions = {"candidate": {}, "reference": {}}
        details, cache_metadata = {}, {}
        common_runtime = None
        common_source = {"code_sha": request["code_sha"],
            "source_inventory_sha256": canonical(request["source_files"]),
            "configuration": request["model_configuration"], "loader_implementation": pair.provenance["loader_implementation"],
            "historical_memory_implementation": pair.provenance["historical_memory_implementation"]}
        for label, encoder in (("reference", reference), ("candidate", candidate)):
            encoder.to("cuda:0").eval()
            for dataset, view in views.items():
                journal.check()
                geometries, unavailable = [], 0
                for role in ("train", "train_inner_validation"):
                    for index in view.view(role):
                        sample = view.get(index, role=role)
                        if not sample.geometry_ready:
                            unavailable += 1
                            continue
                        geometries.append(NativeGeometry(dataset, sample.member_uid, index,
                            sample.x, sample.pos, sample.source_atom_ids))
                h0, metadata = cache.get_or_compute(encoder, geometries,
                    architecture_sha256=request["architecture_sha256"],
                    membership_sha256=view.membership_sha256, device="cuda:0",
                    expected_plan_sha256=request["h0_packing_plan_sha256"][dataset],
                    execution_source={**common_source, "weights_origin":
                        request["checkpoint"] if label == "candidate" else {"initialization_seed": 20261025,
                            "architecture_sha256": request["architecture_sha256"]}},
                    **budget_arguments(request["h0_packing"]))
                effective_runtime = metadata["binding"]["effective_runtime_sha256"]
                if common_runtime is not None and effective_runtime != common_runtime:
                    raise RuntimeError("Candidate/reference H0 effective runtimes differ")
                common_runtime = effective_runtime
                cache_metadata[label+"/"+dataset] = {**metadata, "unavailable_geometry_records": unavailable}
                for task in (task for task in tasks if task.dataset_id == dataset):
                    train = task_rows(view, h0, task, role="train")
                    validation = task_rows(view, h0, task, role="train_inner_validation")
                    journal.check()
                    ridge = panel["readouts"]["ridge"]
                    prediction, meta = ridge_probe(train, validation, task, alphas=ridge["alphas"],
                        folds=ridge["inner_folds"], seed=ridge["seed"])
                    key = task.task_id+"@ridge"
                    predictions[label][key] = prediction
                    details[label+"/"+key] = meta
                    journal.scoped(label+"/"+key).log({"validation_error": error(prediction)}, step=0, commit=True)
                    prediction, meta = nonlinear_probe(train, validation, task,
                        seed=panel["readouts"]["linear64_relu"]["seed"], device="cuda:0",
                        tracker=journal.scoped(label+"/"+task.task_id+"@linear64_relu"))
                    key = task.task_id+"@linear64_relu"
                    predictions[label][key] = prediction
                    history = meta.pop("history")
                    details[label+"/"+key] = {**meta, "history_records": len(history)}
                del h0
            encoder.cpu()
        uncertainty = panel["uncertainty"]
        kwargs = dict(architecture_sha256=request["architecture_sha256"],
            reference_architecture_sha256=request["architecture_sha256"],
            bootstrap_samples=uncertainty["bootstrap_samples"], confidence=uncertainty["confidence"], seed=uncertainty["seed"])
        summaries = {"primary_18_cells": compare_panel(predictions["candidate"], predictions["reference"], **kwargs)}
        for method in ("ridge", "linear64_relu"):
            selected = {k: v for k, v in predictions["candidate"].items() if k.endswith("@"+method)}
            matched = {k: predictions["reference"][k] for k in selected}
            summaries[method] = compare_panel(selected, matched, **kwargs)
        elapsed = time.monotonic()-started
        status = "COMPLETED" if summaries["primary_18_cells"]["complete"] else "NOT_ACCEPTED"
        result = {"schema": "model_v3_dev_evaluation_result_v1", "status": status,
            "request_sha256": request_sha, "code_sha": request["code_sha"],
            "panel_sha256": request["panel"]["sha256"], "training_store_sha256": request["training_store"]["sha256"],
            "membership_sha256": {dataset: view.membership_sha256 for dataset, view in views.items()},
            "h0_packing_budget_sha256": request["h0_packing_budget_sha256"],
            "h0_packing_plan_sha256": request["h0_packing_plan_sha256"],
            "preregistration_sha": request["preregistration_sha"], "architecture_sha256": request["architecture_sha256"],
            "data_version": request["data_version"], "job_id": os.environ["SLURM_JOB_ID"],
            "pretraining_seed": request["pretraining_seed"], "random_reference_initialization_seed": 20261025,
            "readout_seed": panel["readouts"]["linear64_relu"]["seed"],
            "gpu_uuid": uuid, "gpu_model": torch.cuda.get_device_name(0),
            "elapsed_seconds": elapsed, "gpu_peak_allocated_bytes": torch.cuda.max_memory_allocated(),
            "one_gpu_hour_target_met": elapsed <= panel["operating_rules"]["wall_target_gpu_seconds_per_checkpoint"],
            "summaries": summaries, "probe_details": details, "h0_caches": cache_metadata,
            "source_integrity_scope": store.integrity_scope, "wandb_run_id": str(run.id),
            "journal_records": journal.step, "wandb_history_independently_verified": False,
            "reference_kind": request.get("reference_kind", "primary")}
        result["encoder_pair"] = pair.provenance
        result["h0_effective_runtime_sha256"] = common_runtime
        run.summary["evaluation_status"] = status
        run.summary["dev_primary_score"] = summaries["primary_18_cells"]["mean_normalized_improvement"]
        exclusive_json(output / "result.json", result)
        print(json.dumps({"status": status, "output": str(output), "elapsed_seconds": elapsed}))
        return 0 if status == "COMPLETED" else 2
    except Exception as exc:
        exclusive_json(output / "failure.json", {"status": "FAILED", "exception": type(exc).__name__,
            "reason": str(exc), "elapsed_seconds": time.monotonic()-started,
            "job_id": os.environ.get("SLURM_JOB_ID"), "request_sha256": request_sha,
            "retained_packing_plan": getattr(exc, "packing_plan", None)})
        raise
    finally:
        if journal is not None:
            journal.close()
        if run is not None:
            run.finish(exit_code=0 if status == "COMPLETED" else 1)
        fcntl.flock(lock, fcntl.LOCK_UN); lock.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", required=True)
    parser.add_argument("--request-sha256", required=True)
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--plan-output", type=Path,
                        help="Optional new external JSON artifact containing target-free H0 packing plans")
    args = parser.parse_args()
    if args.validate_only:
        from phychem_mfm.phase1.v3_h0_packing import packing_plans_for_views
        request, _, store, views, _, _ = load_plan(args.request, args.request_sha256, allow_unbound_packing=True)
        packing = packing_plans_for_views(store, views, request["h0_packing"])
        if args.plan_output:
            if args.plan_output.resolve().is_relative_to(ROOT.resolve()):
                raise ValueError("Selected packing metadata must stay outside Git")
            exclusive_json(args.plan_output, packing)
        print(json.dumps({"status": "TRAIN_METADATA_PLAN_READY", "physical_target_records_read": 0,
            "memberships": {key: value.membership_sha256 for key, value in views.items()},
            "h0_packing_plan_sha256": {key: value["plan_sha256"] for key, value in packing.items()},
            "h0_packing_budget_sha256": request["h0_packing_budget_sha256"],
            "oversized_singleton_ordinals": {key: value["oversized_singleton_ordinals"] for key, value in packing.items()},
            "source_integrity_scope": store.integrity_scope, "data_version": request["data_version"]}))
        return 0
    return execute(args.request, args.request_sha256)


if __name__ == "__main__":
    raise SystemExit(main())
