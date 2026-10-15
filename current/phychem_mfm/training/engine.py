from __future__ import annotations

import json
import logging
import time
from collections import defaultdict
from pathlib import Path
from typing import Mapping

import torch

from ..supervision import SupervisionConfig
from .checkpoint import load_training_checkpoint, save_training_checkpoint
from .losses import LossWeights, StageSchedule, compute_pretrain_loss, objectives_for_step


LOGGER = logging.getLogger("phychem_mfm")


def _sync(device: torch.device) -> None:
    if device.type == "cuda":
        torch.cuda.synchronize(device)


def _set_loader_epoch(loader, epoch: int) -> None:
    batch_sampler = getattr(loader, "batch_sampler", None)
    if hasattr(batch_sampler, "set_epoch"):
        batch_sampler.set_epoch(epoch)


def _resume_train_iterator(loader, epoch: int, batch_offset: int):
    """Reconstruct a deterministic sampler epoch and in-epoch cursor."""
    epoch = int(epoch)
    batch_offset = int(batch_offset)
    if len(loader) <= 0:
        raise RuntimeError("Training loader has no batches")
    if epoch < 0 or batch_offset < 0 or batch_offset > len(loader):
        raise RuntimeError(f"Invalid data-loader resume state: epoch={epoch}, batch_offset={batch_offset}")
    _set_loader_epoch(loader, epoch)
    iterator = iter(loader)
    for _ in range(batch_offset):
        next(iterator)
    return iterator


@torch.no_grad()
def evaluate(
    model,
    loader,
    *,
    device: torch.device,
    standardizers: Mapping[str, object],
    supervision: SupervisionConfig,
    weights: LossWeights,
    schedule: StageSchedule,
    exposure_step: int,
    max_batches: int | None = None,
    precision: str = "fp32",
) -> dict[str, float]:
    model.eval()
    sums: dict[str, float] = defaultdict(float)
    batches = 0
    active = objectives_for_step(supervision, schedule, exposure_step)
    with torch.random.fork_rng(devices=[device] if device.type == "cuda" else []):
        torch.manual_seed(0)
        for batch_idx, batch in enumerate(loader):
            if max_batches is not None and batch_idx >= max_batches:
                break
            batch = batch.to(device)
            with torch.autocast(
                device_type=device.type,
                dtype=torch.bfloat16,
                enabled=device.type == "cuda" and str(precision).lower() == "bf16",
            ):
                outputs = model.forward_pretrain(batch, active)
            result = compute_pretrain_loss(
                outputs,
                batch,
                standardizers,
                supervision,
                weights,
                schedule,
                exposure_step,
                graph_descriptor_indices=model.graph_descriptor_target_indices,
            )
            for key, value in result.scalar_metrics(prefix="val/").items():
                sums[key] += float(value)
            batches += 1
    if batches == 0:
        raise RuntimeError("Validation loader yielded no batches")
    return {key: value / batches for key, value in sums.items()}


def run_training(
    *,
    model,
    data_bundle,
    optimizer,
    scheduler,
    config: dict,
    supervision: SupervisionConfig,
    weights: LossWeights,
    schedule: StageSchedule,
    device: torch.device,
    max_steps: int,
    validate_every: int,
    max_val_batches: int,
    run_dir: str | Path,
    project_root: str | Path,
    wandb_run=None,
    resume_from: str | Path | None = None,
    log_every: int = 20,
) -> dict[str, object]:
    run_dir = Path(run_dir).resolve()
    checkpoint_dir = run_dir / "checkpoints"
    run_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    model.to(device)

    exposure_step = 0
    update_step = 0
    train_epoch = 0
    train_batch_offset = 0
    if resume_from:
        payload = load_training_checkpoint(
            resume_from,
            model=model,
            optimizer=optimizer,
            scheduler=scheduler,
            expected_config=config,
            map_location=device,
        )
        exposure_step = int(payload["global_exposure_step"])
        update_step = int(payload["optimizer_update_step"])
        extra = payload.get("extra", {})
        if "train_epoch" not in extra or "train_batch_offset" not in extra:
            raise RuntimeError("Checkpoint is missing exact data-loader resume state")
        train_epoch = int(extra["train_epoch"])
        train_batch_offset = int(extra["train_batch_offset"])

    train_iter = _resume_train_iterator(data_bundle.train_loader, train_epoch, train_batch_offset)
    history: list[dict[str, float]] = []
    validation_history: list[dict[str, float]] = []
    forward_total = 0.0
    backward_total = 0.0
    measured_steps = 0
    if device.type == "cuda":
        torch.cuda.reset_peak_memory_stats(device)

    while exposure_step < max_steps:
        try:
            batch = next(train_iter)
        except StopIteration:
            train_epoch += 1
            train_batch_offset = 0
            _set_loader_epoch(data_bundle.train_loader, train_epoch)
            train_iter = iter(data_bundle.train_loader)
            batch = next(train_iter)
        train_batch_offset += 1
        batch = batch.to(device, non_blocking=device.type == "cuda")
        model.train()
        optimizer.zero_grad(set_to_none=True)
        active = objectives_for_step(supervision, schedule, exposure_step)

        _sync(device)
        forward_start = time.perf_counter()
        rng_devices = [device] if device.type == "cuda" else []
        with torch.random.fork_rng(devices=rng_devices):
            step_seed = int(config["training"].get("seed", 0)) + int(exposure_step)
            torch.manual_seed(step_seed)
            if device.type == "cuda":
                torch.cuda.manual_seed(step_seed)
            with torch.autocast(
                device_type=device.type,
                dtype=torch.bfloat16,
                enabled=device.type == "cuda" and str(config["training"].get("precision", "fp32")).lower() == "bf16",
            ):
                outputs = model.forward_pretrain(batch, active)
        result = compute_pretrain_loss(
            outputs,
            batch,
            data_bundle.standardizers,
            supervision,
            weights,
            schedule,
            exposure_step,
            graph_descriptor_indices=model.graph_descriptor_target_indices,
        )
        _sync(device)
        forward_time = time.perf_counter() - forward_start

        backward_time = 0.0
        grad_norm = 0.0
        if result.total.requires_grad:
            _sync(device)
            backward_start = time.perf_counter()
            result.total.backward()
            grad_norm = float(
                torch.nn.utils.clip_grad_norm_(model.parameters(), float(config["optimizer"]["grad_clip_norm"]))
            )
            optimizer.step()
            update_step += 1
            _sync(device)
            backward_time = time.perf_counter() - backward_start

        # The canonical schedule is defined on data exposure.  In particular,
        # D-only has zero optimizer updates before descriptor activation while
        # its LR clock must still advance to the same canonical exposure.
        scheduler.step()
        exposure_step += 1
        forward_total += forward_time
        backward_total += backward_time
        measured_steps += 1
        metrics = result.scalar_metrics(prefix="train/")
        metrics.update(
            {
                "train/exposure_step": exposure_step,
                "train/optimizer_update_step": update_step,
                "train/lr": float(optimizer.param_groups[0]["lr"]),
                "train/grad_norm": grad_norm,
                "perf/forward_seconds": forward_time,
                "perf/backward_seconds": backward_time,
                "perf/graphs_per_second": float(batch.num_graphs) / max(1e-9, forward_time + backward_time),
            }
        )
        if device.type == "cuda":
            metrics["perf/peak_memory_gib"] = torch.cuda.max_memory_allocated(device) / (1024**3)
        history.append(metrics)
        if wandb_run is not None:
            wandb_run.log(metrics, step=exposure_step)
        if exposure_step % log_every == 0 or exposure_step == 1:
            LOGGER.info(
                "step=%d update=%d total=%.5f active=%s lr=%.3e fwd=%.3fs bwd=%.3fs",
                exposure_step,
                update_step,
                float(result.total.detach()),
                ",".join(sorted(item.value for item in active)),
                optimizer.param_groups[0]["lr"],
                forward_time,
                backward_time,
            )

        should_validate = validate_every > 0 and (exposure_step % validate_every == 0 or exposure_step == max_steps)
        if should_validate:
            val_metrics = evaluate(
                model,
                data_bundle.val_loader,
                device=device,
                standardizers=data_bundle.standardizers,
                supervision=supervision,
                weights=weights,
                schedule=schedule,
                exposure_step=exposure_step,
                max_batches=max_val_batches,
                precision=str(config["training"].get("precision", "fp32")),
            )
            val_metrics["val/exposure_step"] = exposure_step
            validation_history.append(val_metrics)
            if wandb_run is not None:
                wandb_run.log(val_metrics, step=exposure_step)
            LOGGER.info("validation step=%d total=%.5f", exposure_step, val_metrics["val/loss/total"])
            diagnostic_metrics = evaluate(
                model,
                data_bundle.diagnostic_val_loader,
                device=device,
                standardizers=data_bundle.standardizers,
                supervision=supervision,
                weights=weights,
                schedule=schedule,
                exposure_step=exposure_step,
                max_batches=max_val_batches,
                precision=str(config["training"].get("precision", "fp32")),
            )
            diagnostic_metrics = {
                key.replace("val/", "val_diag/", 1): value for key, value in diagnostic_metrics.items()
            }
            diagnostic_metrics["val_diag/exposure_step"] = exposure_step
            val_metrics.update(diagnostic_metrics)
            if wandb_run is not None:
                wandb_run.log(diagnostic_metrics, step=exposure_step)
            LOGGER.info(
                "diagnostic validation step=%d element=%.5f",
                exposure_step,
                diagnostic_metrics.get("val_diag/loss/raw/element", float("nan")),
            )
            save_training_checkpoint(
                checkpoint_dir / "latest.pt",
                model=model,
                optimizer=optimizer,
                scheduler=scheduler,
                config=config,
                supervision=supervision.to_dict(),
                dataset_manifest=data_bundle.manifest,
                exposure_step=exposure_step,
                optimizer_update_step=update_step,
                checkpoint_type="latest",
                project_root=project_root,
                extra={
                    "last_validation": val_metrics,
                    "train_epoch": train_epoch,
                    "train_batch_offset": train_batch_offset,
                },
            )

    summary = {
        "exposure_step": exposure_step,
        "optimizer_update_step": update_step,
        "mean_forward_seconds": forward_total / max(1, measured_steps),
        "mean_backward_seconds": backward_total / max(1, measured_steps),
        "peak_memory_gib": (
            torch.cuda.max_memory_allocated(device) / (1024**3) if device.type == "cuda" else 0.0
        ),
        "last_train": history[-1] if history else {},
        "validation_history": validation_history,
        "dataset_manifest": data_bundle.manifest,
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    return summary
