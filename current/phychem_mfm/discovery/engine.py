from __future__ import annotations

import hashlib
import json
import logging
import time
from pathlib import Path

import torch

from ..supervision import SupervisionConfig
from ..training.checkpoint import load_training_checkpoint, save_training_checkpoint
from ..training.engine import _set_loader_epoch, _sync, evaluate
from ..training.losses import LossWeights, compute_pretrain_loss, objectives_for_step
from .convergence import ConvergenceGate
from .registry import ExperimentRegistry


LOGGER = logging.getLogger("phychem_mfm.discovery")


def budget_status(*, completed_passes: int, max_passes: int, optimization_status: str) -> str:
    """Report budget exhaustion separately from scientific convergence.

    ``STILL_IMPROVING`` is an optimization observation, whereas reaching the
    configured pass ceiling is an operational termination reason.  Keeping the
    two fields separate prevents a safety cap from being misreported as either
    convergence or convergence failure.
    """

    if int(completed_passes) >= int(max_passes) and optimization_status == "STILL_IMPROVING":
        return "BUDGET_LIMIT_REACHED"
    return "WITHIN_BUDGET"


def should_stop_for_maturity(decision) -> bool:
    """Stop on Gate-A maturity whether Gate B passes or needs diagnosis."""

    return bool(decision.optimization_mature)


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(path)


def run_discovery_training(
    *,
    model,
    data_bundle,
    optimizer,
    scheduler,
    config: dict,
    supervision: SupervisionConfig,
    weights: LossWeights,
    schedule,
    convergence_gate: ConvergenceGate,
    device: torch.device,
    max_passes: int,
    stop_after_pass: int | None,
    validation_points_per_pass: int,
    max_val_batches: int,
    run_dir: str | Path,
    project_root: str | Path,
    run_manifest: dict[str, object],
    registry: ExperimentRegistry,
    target_adequacy_evaluator=None,
    wandb_run=None,
    resume_from: str | Path | None = None,
) -> dict[str, object]:
    run_dir = Path(run_dir).resolve()
    run_dir.mkdir(parents=True, exist_ok=True)
    model.to(device)
    completed_passes = 0
    pass_index = 0
    batch_offset = 0
    optimizer_update_step = 0
    cumulative_structure_exposure = 0
    atom_exposure = 0
    validation_history: list[dict[str, float]] = []
    wall_start = time.perf_counter()
    wall_time_before_resume = 0.0
    forward_total = 0.0
    backward_total = 0.0
    measured_steps = 0
    peak_memory_before_resume = 0.0

    if resume_from:
        payload = load_training_checkpoint(
            resume_from,
            model=model,
            optimizer=optimizer,
            scheduler=scheduler,
            expected_config=config,
            map_location=device,
        )
        discovery = payload.get("discovery", {})
        if discovery.get("recipe_hash") != run_manifest["recipe_hash"]:
            raise RuntimeError("Discovery checkpoint recipe_hash mismatch")
        completed_passes = int(discovery.get("pass_count", 0))
        pass_index = int(discovery.get("current_pass_index", completed_passes))
        batch_offset = int(discovery.get("train_batch_offset", 0))
        optimizer_update_step = int(payload["optimizer_update_step"])
        cumulative_structure_exposure = int(discovery.get("cumulative_structure_exposure", 0))
        atom_exposure = int(discovery.get("atom_exposure", 0))
        validation_history = [dict(item) for item in discovery.get("validation_history", [])]
        wall_time_before_resume = float(discovery.get("wall_time_seconds", 0.0))
        forward_total = float(discovery.get("forward_total_seconds", 0.0))
        backward_total = float(discovery.get("backward_total_seconds", 0.0))
        measured_steps = int(discovery.get("measured_steps", 0))
        peak_memory_before_resume = float(discovery.get("peak_memory_gib", 0.0))

    if device.type == "cuda":
        torch.cuda.reset_peak_memory_stats(device)
    steps_per_pass = len(data_bundle.train_loader)
    validate_interval = max(1, steps_per_pass // max(1, int(validation_points_per_pass)))

    execution_pass_limit = min(int(max_passes), int(stop_after_pass or max_passes))
    while completed_passes < execution_pass_limit:
        _set_loader_epoch(data_bundle.train_loader, pass_index)
        iterator = iter(data_bundle.train_loader)
        for _ in range(batch_offset):
            next(iterator)

        for batch_number, batch in enumerate(iterator, start=batch_offset + 1):
            batch = batch.to(device, non_blocking=device.type == "cuda")
            batch_graphs = int(batch.num_graphs)
            batch_atoms = int(batch.x.size(0))
            model.train()
            optimizer.zero_grad(set_to_none=True)
            active = objectives_for_step(supervision, schedule, cumulative_structure_exposure)
            rng_devices = [device] if device.type == "cuda" else []
            _sync(device)
            forward_start = time.perf_counter()
            with torch.random.fork_rng(devices=rng_devices):
                step_seed = int(config["training"]["seed"]) + optimizer_update_step
                torch.manual_seed(step_seed)
                if device.type == "cuda":
                    torch.cuda.manual_seed(step_seed)
                with torch.autocast(
                    device_type=device.type,
                    dtype=torch.bfloat16,
                    enabled=device.type == "cuda" and str(config["training"]["precision"]).lower() == "bf16",
                ):
                    outputs = model.forward_pretrain(batch, active)
            result = compute_pretrain_loss(
                outputs,
                batch,
                data_bundle.standardizers,
                supervision,
                weights,
                schedule,
                cumulative_structure_exposure,
                graph_descriptor_indices=model.graph_descriptor_target_indices,
            )
            _sync(device)
            forward_time = time.perf_counter() - forward_start
            backward_start = time.perf_counter()
            result.total.backward()
            grad_norm = float(torch.nn.utils.clip_grad_norm_(model.parameters(), float(config["optimizer"]["grad_clip_norm"])))
            optimizer.step()
            scheduler.step()
            _sync(device)
            backward_time = time.perf_counter() - backward_start

            optimizer_update_step += 1
            cumulative_structure_exposure += batch_graphs
            atom_exposure += batch_atoms
            batch_offset = batch_number
            measured_steps += 1
            forward_total += forward_time
            backward_total += backward_time
            metrics = result.scalar_metrics(prefix="train/")
            metrics.update(
                {
                    "train/pass_index": pass_index + 1,
                    "train/pass_fraction": batch_number / steps_per_pass,
                    "train/unique_structure_count": int(run_manifest["unique_structure_count"]),
                    "train/unique_molecule_count": int(run_manifest["unique_molecule_count"]),
                    "train/cumulative_structure_exposure": cumulative_structure_exposure,
                    "train/atom_exposure": atom_exposure,
                    "train/optimizer_update_step": optimizer_update_step,
                    "train/lr": float(optimizer.param_groups[0]["lr"]),
                    "train/grad_norm": grad_norm,
                    "perf/forward_seconds": forward_time,
                    "perf/backward_seconds": backward_time,
                }
            )
            if device.type == "cuda":
                metrics["perf/peak_memory_gib"] = torch.cuda.max_memory_allocated(device) / (1024**3)
            if wandb_run is not None:
                wandb_run.log(metrics, step=optimizer_update_step)

            half_checkpoint = run_dir / f"pass_{pass_index + 1}" / "partial_half.pt"
            if batch_number >= (steps_per_pass + 1) // 2 and not half_checkpoint.exists():
                partial_discovery = {
                    "experiment_id": run_manifest["experiment_id"],
                    "recipe_hash": run_manifest["recipe_hash"],
                    "train_pool_hash": run_manifest["train_pool_hash"],
                    "validation_pool_hash": run_manifest["validation_pool_hash"],
                    "unique_structure_count": run_manifest["unique_structure_count"],
                    "unique_molecule_count": run_manifest["unique_molecule_count"],
                    "pass_count": completed_passes,
                    "current_pass_index": pass_index,
                    "train_batch_offset": batch_offset,
                    "cumulative_structure_exposure": cumulative_structure_exposure,
                    "atom_exposure": atom_exposure,
                    "validation_history": validation_history,
                    "wall_time_seconds": wall_time_before_resume + time.perf_counter() - wall_start,
                    "forward_total_seconds": forward_total,
                    "backward_total_seconds": backward_total,
                    "measured_steps": measured_steps,
                    "peak_memory_gib": max(
                        peak_memory_before_resume,
                        torch.cuda.max_memory_allocated(device) / (1024**3) if device.type == "cuda" else 0.0,
                    ),
                }
                save_training_checkpoint(
                    half_checkpoint,
                    model=model,
                    optimizer=optimizer,
                    scheduler=scheduler,
                    config=config,
                    supervision=supervision.to_dict(),
                    dataset_manifest=data_bundle.manifest,
                    exposure_step=cumulative_structure_exposure,
                    optimizer_update_step=optimizer_update_step,
                    checkpoint_type="partial",
                    project_root=project_root,
                    source_metadata={
                        "git_commit": run_manifest["source_commit"],
                        "git_dirty": run_manifest["source_dirty"],
                        "source_sha256": run_manifest["source_sha256"],
                    },
                    extra={"last_validation": validation_history[-1] if validation_history else {}},
                    discovery_metadata=partial_discovery,
                )
                partial_sha = file_sha256(half_checkpoint)
                registry.register_checkpoint(
                    {
                        "experiment_id": run_manifest["experiment_id"],
                        "recipe_hash": run_manifest["recipe_hash"],
                        "path": str(half_checkpoint),
                        "checkpoint_sha256": partial_sha,
                        "checkpoint_state": "partial",
                        "aliases": [],
                        "checkpoint_pass": completed_passes,
                        "current_pass_index": pass_index + 1,
                        "checkpoint_exposure": cumulative_structure_exposure,
                        "unique_structure_count": run_manifest["unique_structure_count"],
                        "unique_molecule_count": run_manifest["unique_molecule_count"],
                        "cumulative_structure_exposure": cumulative_structure_exposure,
                        "atom_exposure": atom_exposure,
                        "optimizer_update_step": optimizer_update_step,
                        "source_commit": run_manifest["source_commit"],
                        "source_sha256": run_manifest["source_sha256"],
                        "convergence_status": "PARTIAL",
                        "transfer_ready_status": False,
                        "result_paths": {"checkpoint": str(half_checkpoint), "run_dir": str(run_dir)},
                    }
                )

            should_validate = batch_number % validate_interval == 0 or batch_number == steps_per_pass
            if should_validate:
                val = evaluate(
                    model,
                    data_bundle.val_loader,
                    device=device,
                    standardizers=data_bundle.standardizers,
                    supervision=supervision,
                    weights=weights,
                    schedule=schedule,
                    exposure_step=cumulative_structure_exposure,
                    max_batches=max_val_batches,
                    precision=str(config["training"]["precision"]),
                )
                val.update(
                    {
                        "val/pass_index": pass_index + 1,
                        "val/pass_fraction": batch_number / steps_per_pass,
                        "val/cumulative_structure_exposure": cumulative_structure_exposure,
                        "val/optimizer_update_step": optimizer_update_step,
                    }
                )
                validation_history.append(val)
                if wandb_run is not None:
                    wandb_run.log(val, step=optimizer_update_step)
                LOGGER.info(
                    "pass=%d batch=%d/%d exposure=%d val=%.6f",
                    pass_index + 1,
                    batch_number,
                    steps_per_pass,
                    cumulative_structure_exposure,
                    val["val/loss/total"],
                )

        completed_passes += 1
        pass_index = completed_passes
        batch_offset = 0
        decision = convergence_gate.evaluate(
            validation_history,
            pass_count=completed_passes,
            schedule_mature=schedule.is_mature(cumulative_structure_exposure),
            warmup_complete=optimizer_update_step >= int(config["training"]["warmup_steps"]),
        )
        adequacy_report = None
        if decision.optimization_mature and target_adequacy_evaluator is not None:
            adequacy_report = target_adequacy_evaluator.evaluate_loaders(
                data_bundle.val_loader,
                element_loader=data_bundle.diagnostic_val_loader,
                max_batches=max_val_batches,
            )
            decision = convergence_gate.evaluate(
                validation_history,
                pass_count=completed_passes,
                schedule_mature=schedule.is_mature(cumulative_structure_exposure),
                warmup_complete=optimizer_update_step >= int(config["training"]["warmup_steps"]),
                target_adequate=bool(adequacy_report["target_adequate"]),
            )
        current_budget_status = budget_status(
            completed_passes=completed_passes,
            max_passes=max_passes,
            optimization_status=decision.status,
        )
        pass_dir = run_dir / f"pass_{completed_passes}"
        checkpoint_path = pass_dir / "checkpoint.pt"
        if checkpoint_path.exists():
            raise RuntimeError(f"Refusing to overwrite immutable pass checkpoint: {checkpoint_path}")
        discovery_metadata = {
            "experiment_id": run_manifest["experiment_id"],
            "recipe_hash": run_manifest["recipe_hash"],
            "train_pool_hash": run_manifest["train_pool_hash"],
            "validation_pool_hash": run_manifest["validation_pool_hash"],
            "unique_structure_count": run_manifest["unique_structure_count"],
            "unique_molecule_count": run_manifest["unique_molecule_count"],
            "pass_count": completed_passes,
            "current_pass_index": pass_index,
            "train_batch_offset": 0,
            "cumulative_structure_exposure": cumulative_structure_exposure,
            "atom_exposure": atom_exposure,
            "validation_history": validation_history,
            "convergence": decision.to_dict(),
            "target_adequacy": adequacy_report,
            "wall_time_seconds": wall_time_before_resume + time.perf_counter() - wall_start,
            "forward_total_seconds": forward_total,
            "backward_total_seconds": backward_total,
            "measured_steps": measured_steps,
            "peak_memory_gib": max(
                peak_memory_before_resume,
                torch.cuda.max_memory_allocated(device) / (1024**3) if device.type == "cuda" else 0.0,
            ),
        }
        save_training_checkpoint(
            checkpoint_path,
            model=model,
            optimizer=optimizer,
            scheduler=scheduler,
            config=config,
            supervision=supervision.to_dict(),
            dataset_manifest=data_bundle.manifest,
            exposure_step=cumulative_structure_exposure,
            optimizer_update_step=optimizer_update_step,
            checkpoint_type="transfer_ready" if decision.transfer_ready else "pass_end",
            project_root=project_root,
            source_metadata={
                "git_commit": run_manifest["source_commit"],
                "git_dirty": run_manifest["source_dirty"],
                "source_sha256": run_manifest["source_sha256"],
            },
            extra={"last_validation": validation_history[-1]},
            discovery_metadata=discovery_metadata,
        )
        sha256 = file_sha256(checkpoint_path)
        aliases = ["first_pass"] if completed_passes == 1 else []
        if decision.transfer_ready:
            aliases.append("transfer_ready")
        checkpoint_record = {
            "experiment_id": run_manifest["experiment_id"],
            "recipe_hash": run_manifest["recipe_hash"],
            "path": str(checkpoint_path),
            "checkpoint_sha256": sha256,
            "checkpoint_state": "transfer_ready" if decision.transfer_ready else "pass_end",
            "aliases": aliases,
            "checkpoint_pass": completed_passes,
            "checkpoint_exposure": cumulative_structure_exposure,
            "unique_structure_count": run_manifest["unique_structure_count"],
            "unique_molecule_count": run_manifest["unique_molecule_count"],
            "cumulative_structure_exposure": cumulative_structure_exposure,
            "atom_exposure": atom_exposure,
            "optimizer_update_step": optimizer_update_step,
            "source_commit": run_manifest["source_commit"],
            "source_sha256": run_manifest["source_sha256"],
            "convergence_status": decision.status,
            "optimization_status": decision.status,
            "budget_status": current_budget_status,
            "target_adequacy_status": None if adequacy_report is None else adequacy_report["target_adequacy_status"],
            "per_task_fidelity": None if adequacy_report is None else adequacy_report["per_task_fidelity"],
            "domain_protocol_version": run_manifest.get("domain_protocol_version"),
            "data_quality_protocol_version": run_manifest.get("data_quality_protocol_version"),
            "data_quality_policy_hash": run_manifest.get("data_quality_policy_hash"),
            "validation_manifest_hash": run_manifest.get("validation_manifest_hash"),
            "target_adequacy_version": run_manifest.get("target_adequacy_version"),
            "v3_validity": run_manifest.get("v3_validity"),
            "transfer_ready_status": decision.transfer_ready,
            "result_paths": {"checkpoint": str(checkpoint_path), "run_dir": str(run_dir)},
        }
        if adequacy_report is not None:
            task_metrics = adequacy_report.get("per_task_metrics", {})
            checkpoint_record.update({
                "energy_original_unit_metrics": task_metrics.get("energy"),
                "charge_original_unit_metrics": task_metrics.get("charge"),
                "geometry_original_unit_metrics": task_metrics.get("geometry"),
                "bond_metrics": task_metrics.get("bond"),
                "descriptor_metrics": {
                    key: task_metrics.get(key)
                    for key in ("graph_descriptor", "charge_descriptor", "element_descriptor")
                },
            })
        registry.register_checkpoint(checkpoint_record)
        if adequacy_report is not None:
            _atomic_json(pass_dir / "target_adequacy.json", adequacy_report)
        _atomic_json(run_dir / "latest.json", checkpoint_record)
        if completed_passes == 1:
            _atomic_json(run_dir / "first_pass.json", checkpoint_record)
        if decision.transfer_ready:
            _atomic_json(run_dir / "transfer_ready.json", checkpoint_record)
        # A mature but target-inadequate checkpoint is a diagnostic terminal
        # state, not an instruction to spend the remaining safety budget.
        # Additional passes are justified only while Gate A says the optimizer
        # is still learning; capacity/loss/target conflicts must be diagnosed
        # once the optimization curve has matured.
        if should_stop_for_maturity(decision):
            break

    summary = {
        **run_manifest,
        "pass_count": completed_passes,
        "cumulative_structure_exposure": cumulative_structure_exposure,
        "atom_exposure": atom_exposure,
        "optimizer_update_step": optimizer_update_step,
        "wall_time_seconds": wall_time_before_resume + time.perf_counter() - wall_start,
        "mean_forward_seconds": forward_total / max(1, measured_steps),
        "mean_backward_seconds": backward_total / max(1, measured_steps),
        "peak_memory_gib": max(
            peak_memory_before_resume,
            torch.cuda.max_memory_allocated(device) / (1024**3) if device.type == "cuda" else 0.0,
        ),
        "validation_history": validation_history,
        "convergence": decision.to_dict(),
        "target_adequacy": adequacy_report,
        "convergence_status": decision.status,
        "optimization_status": decision.status,
        "budget_status": current_budget_status,
        "transfer_ready_status": decision.transfer_ready,
        "checkpoint_exposure": checkpoint_record["checkpoint_exposure"],
        "checkpoint_pass": checkpoint_record["checkpoint_pass"],
        "checkpoint_sha256": checkpoint_record["checkpoint_sha256"],
        "result_paths": checkpoint_record["result_paths"],
    }
    _atomic_json(run_dir / "summary.json", summary)
    updated_manifest = {**run_manifest, **{key: summary[key] for key in (
        "pass_count", "cumulative_structure_exposure", "atom_exposure", "optimizer_update_step", "wall_time_seconds",
        "mean_forward_seconds", "mean_backward_seconds", "peak_memory_gib", "validation_history", "target_adequacy",
    )}}
    updated_manifest["convergence_status"] = decision.status
    updated_manifest["optimization_status"] = decision.status
    updated_manifest["budget_status"] = current_budget_status
    updated_manifest["transfer_ready_status"] = decision.transfer_ready
    updated_manifest["result_paths"] = {"run_dir": str(run_dir), "summary": str(run_dir / "summary.json")}
    registry.register_experiment(updated_manifest)
    return summary
