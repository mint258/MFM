from __future__ import annotations

import logging
from pathlib import Path
import time
import warnings
import numpy as np
import torch
from torch.utils.data import ConcatDataset, DataLoader, Subset
from torch.utils.data.distributed import DistributedSampler

try:
    from ..models.moe import MultiTaskMoE
except ImportError:
    from models.moe import MultiTaskMoE

from .args import get_args
from .checkpoint import load_checkpoint, resolve_checkpoint_paths, save_checkpoint
from .data import (
    DistributedEvalAtomBudgetBatchSampler,
    DistributedEvalSampler,
    DistributedAtomBudgetBatchSampler,
    DomainWrapperDataset,
    ExcludingSubsetDataset,
    IndexedSubsetDataset,
    MaskedPerturbDataset,
    OnlyStableWrapper,
    SampleTypeWrapperDataset,
    atom_count_cache_path,
    create_dataset_or_none,
    dataset_atom_counts,
    fast_collate,
    resolve_atom_counts,
    resolve_random_val_split,
    seed_worker,
    standardizer,
    try_load_atom_count_cache,
)
from .dataloader_debug import DataLoaderDebugConfig, configure_worker_debug_env
from .ddp_debug import DDPDebugConfig
from .degrade_molecules import DegradeConfig
from .dist_utils import barrier, broadcast_object, cleanup_distributed, init_distributed, unwrap_model, wrap_ddp
from .train_loop import build_grad_scaler, run_epoch
from .utils import build_lr_scheduler, pad_list, set_seed
from .wandb_utils import finish_run, init_wandb_run, log_checkpoint_artifact, log_metrics, update_summary

warnings.filterwarnings("ignore", category=UserWarning)
logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
LOGGER = logging.getLogger("multitask")


def _enforce_runtime_policy(args) -> None:
    for arg_name in ("lambda_coord", "lambda_planar"):
        value = float(getattr(args, arg_name, 0.0))
        if value != 0.0:
            LOGGER.warning("--%s is retired and will be forced to 0.0", arg_name.replace("_", "-"))
        setattr(args, arg_name, 0.0)

    if getattr(args, "save_every_epoch", False):
        LOGGER.warning("--save_every_epoch is deprecated and ignored; step-based checkpointing is always used.")

    if getattr(args, "fp16", False):
        if args.amp_dtype != "fp16":
            LOGGER.warning("--fp16 is a deprecated alias; switching amp dtype to fp16.")
        args.amp_dtype = "fp16"

    if int(getattr(args, "val_batch_size", 0)) <= 0:
        args.val_batch_size = min(int(args.batch_size), 4)
    if int(getattr(args, "val_num_workers", -1)) < 0:
        args.val_num_workers = int(args.num_workers)
    if int(getattr(args, "val_atom_budget_per_batch", 0)) < 0:
        LOGGER.warning("--val_atom_budget_per_batch must be >= 0; forcing it to 0.")
        args.val_atom_budget_per_batch = 0
    elif int(getattr(args, "val_atom_budget_per_batch", 0)) == 0 and int(getattr(args, "atom_budget_per_batch", 0)) > 0:
        args.val_atom_budget_per_batch = min(int(args.atom_budget_per_batch), 2048)


def _build_model_cfg(args, bb_cfg):
    return {
        "backbone_config": bb_cfg,
        "n_atom_types": args.n_atom_types,
        "n_experts_energy": args.expert_number_E,
        "n_experts_charge": args.expert_number_Q,
        "n_experts_elem": args.expert_number_Z,
        "n_experts_geom": args.expert_number_G,
        "top_k_energy": args.topkE,
        "top_k_charge": args.topkQ,
        "top_k_elem": args.topkZ,
        "top_k_geom": args.topkG,
        "expert_real_layers": args.expert_real_layers,
        "expert_int_layers": args.expert_int_layers,
        "expert_heads": args.expert_heads,
        "expert_ff_mult": args.expert_ff_mult,
        "descriptor_head_mode": "rdkit_descriptor_pack_v1",
    }


def _summarize_metrics(stats, *, stage: int, stage_step: int, lr: float, loss_total: float, selection_loss: float, lam_d: float, lam_a: float, lam_t: float):
    summary = {
        "stage": stage,
        "stage_step": stage_step,
        "loss_total": loss_total,
        "loss_selection": selection_loss,
        "loss_energy": stats["E"],
        "loss_energy_desc": stats["E_desc"],
        "loss_charge": stats["Q"],
        "loss_charge_desc": stats["Q_desc"],
        "loss_elem": stats["Z"],
        "loss_elem_desc": stats["Z_desc"],
        "loss_geom": stats["Geom"],
        "loss_geom_dist": stats["Geom_d"],
        "loss_geom_angle": stats["Geom_a"],
        "loss_geom_torsion": stats["Geom_t"],
        "loss_balance": stats["Bal"],
        "r2_energy": stats["R2_e"],
        "r2_charge": stats["R2_q"],
        "r2_elem": stats["R2_z"],
        "acc_elem": stats["Acc_z"],
        "bad_batches": stats["bad"],
        "lr": lr,
        "lambda_dist": lam_d,
        "lambda_angle": lam_a,
        "lambda_torsion": lam_t,
    }
    summary.update(
        {
            key: value
            for key, value in stats.items()
            if key.startswith("loss_energy_desc_")
            or key.startswith("r2_energy_desc_")
            or key.startswith("loss_charge_desc_")
            or key.startswith("r2_charge_desc_")
            or key.startswith("acc_charge_desc_")
            or key.startswith("loss_elem_desc_")
            or key.startswith("acc_elem_desc_")
        }
    )
    return summary


def _selection_loss(args, stats) -> float:
    return (
        args.lambda_e * stats["E"]
        + args.lambda_e_desc * stats["E_desc"]
        + args.lambda_q * stats["Q"]
        + args.lambda_q_desc * stats["Q_desc"]
        + args.lambda_z * stats["Z"]
        + args.lambda_z_desc * stats["Z_desc"]
        + stats["Geom"]
    )


def _total_loss(args, stats) -> float:
    return _selection_loss(args, stats) + stats["Bal"]


def _pooling_weight_metrics(model) -> dict[str, float]:
    raw_model = unwrap_model(model)
    getter = getattr(raw_model, "get_pooling_weight_metrics", None)
    if callable(getter):
        try:
            return {key: float(value) for key, value in getter().items()}
        except Exception as exc:
            LOGGER.warning("Failed to read pooling weight metrics: %s", exc)
    return {}


def _print_metrics(prefix: str, stats) -> None:
    print(
        f"{prefix} E={stats['E']:.3f} E_desc={stats['E_desc']:.3f} | "
        f"Q={stats['Q']:.3f} Q_desc={stats['Q_desc']:.3f} | "
        f"Z={stats['Z']:.3f} Z_desc={stats['Z_desc']:.3f} | "
        f"Geom={stats['Geom']:.3f}"
    )
    print(
        f"      Geom(Morse={stats['Geom_d']:.4f} Ang={stats['Geom_a']:.4f} Tor={stats['Geom_t']:.4f}) | "
        f"R2(E={stats['R2_e']:.3f}, Q={stats['R2_q']:.3f}, Z={stats['R2_z']:.3f}) | "
        f"Acc(Z)={stats['Acc_z']:.3f} | Bad={stats['bad']}"
    )


def _build_degrade_cfg(args, mode: str, level: float) -> DegradeConfig:
    return DegradeConfig(
        mode=mode,
        level=level,
        topo_replace_frac=args.perturb_replace_frac,
        topo_delete_frac=0.0,
        geom_noise_std=args.perturb_noise_std,
        geom_angle_std_deg=0.0,
        geom_bond_scale_std=0.0,
    )


def parse_perturb_mix(spec: str, base_seed: int):
    out = []
    for idx, segment in enumerate([s for s in spec.split(",") if s.strip()]):
        token = segment.strip()
        if token.lower() == "none" or "@" not in token:
            continue
        left, ratio_str = token.rsplit("@", 1)
        if ":" in left:
            mode, level_str = left.split(":", 1)
        else:
            mode, level_str = left, ""
        mode = mode.strip().lower()
        if mode not in {"clean", "topo", "geom", "both"}:
            continue
        level_str = level_str.strip()
        try:
            ratio = float(ratio_str)
            if ratio <= 0:
                continue
            if mode == "clean":
                level = float(level_str) if level_str else 0.0
            else:
                if not level_str:
                    LOGGER.warning("Skip perturb_mix segment without level: %s", token)
                    continue
                level = float(level_str)
        except ValueError:
            LOGGER.warning("Skip malformed perturb_mix segment: %s", token)
            continue
        out.append((mode, level, ratio, base_seed + 10000 * idx))
    return out


def _build_sample_type_dataset(base_dataset, *, mode: str, level: float, seed: int, args):
    mode = str(mode).strip().lower()
    if mode == "clean":
        return SampleTypeWrapperDataset(base_dataset, sample_type="clean")
    cfg = _build_degrade_cfg(args, mode, level)
    return MaskedPerturbDataset(base_dataset, cfg, seed=seed)


def build_perturb_parts(base_dataset, mix_specs, seed_base: int, args):
    parts = []
    for mode, level, ratio, seed in mix_specs:
        part_base = _build_sample_type_dataset(
            base_dataset,
            mode=mode,
            level=level,
            seed=seed_base + seed,
            args=args,
        )

        whole = int(ratio)
        frac = float(ratio) - whole
        parts.extend([part_base] * whole)
        if frac > 1e-8:
            take = max(1, int(len(base_dataset) * frac))
            parts.append(Subset(part_base, list(range(take))))
    return parts


def build_dataloader(
    dataset,
    *,
    batch_size: int,
    num_workers: int,
    shuffle: bool,
    sampler=None,
    batch_sampler=None,
    pin_memory: bool,
    seed: int,
    timeout_s: int = 0,
):
    generator = torch.Generator()
    generator.manual_seed(int(seed))
    kwargs = {
        "num_workers": num_workers,
        "pin_memory": pin_memory,
        "persistent_workers": False,
        "collate_fn": fast_collate,
        "worker_init_fn": seed_worker,
        "generator": generator,
        "timeout": max(0, int(timeout_s)) if int(num_workers) > 0 else 0,
    }
    if batch_sampler is not None:
        kwargs["batch_sampler"] = batch_sampler
    else:
        kwargs["batch_size"] = batch_size
        kwargs["shuffle"] = shuffle if sampler is None else False
        kwargs["sampler"] = sampler
    if num_workers > 0:
        kwargs["prefetch_factor"] = 2
    return DataLoader(dataset, **kwargs)


def build_model(args, device):
    bb_cfg = {
        "hidden_channels": args.hidden_channels,
        "atom_embedding_dim": args.hidden_channels,
        "bb_layers": args.bb_layers,
        "bb_heads": args.bb_heads,
        "bb_ff_mult": args.bb_ff_mult,
        "bb_use_dist_bias": args.bb_use_dist_bias,
        "bb_use_radius_mask": args.bb_use_radius_mask,
        "bb_radius": args.bb_radius,
    }
    model = MultiTaskMoE(
        bb_cfg,
        n_atom_types=args.n_atom_types,
        n_experts_energy=args.expert_number_E,
        n_experts_charge=args.expert_number_Q,
        n_experts_geom=args.expert_number_G,
        n_experts_elem=args.expert_number_Z,
        top_k_energy=args.topkE,
        top_k_charge=args.topkQ,
        top_k_geom=args.topkG,
        top_k_elem=args.topkZ,
        expert_real_layers=args.expert_real_layers,
        expert_int_layers=args.expert_int_layers,
        expert_heads=args.expert_heads,
        expert_ff_mult=args.expert_ff_mult,
    ).to(device)
    return model, bb_cfg


def _make_split_spec(path: str, start: int | None, end: int | None, length: int) -> dict:
    return {
        "path": str(Path(path).resolve()),
        "start": int(start) if start is not None else 0,
        "end": None if end is None else int(end),
        "length": int(length),
    }


def _build_domain_parts(base_dataset, *, domain_id: int, args, seed_base: int):
    if getattr(args, "perturb_mix", "none") not in (None, "none"):
        specs = parse_perturb_mix(args.perturb_mix, seed_base)
        parts = build_perturb_parts(base_dataset, specs, seed_base, args)
        if not parts:
            parts = [
                _build_sample_type_dataset(
                    base_dataset,
                    mode=args.perturb_mode,
                    level=args.perturb_level,
                    seed=seed_base,
                    args=args,
                )
            ]
    else:
        parts = [
            _build_sample_type_dataset(
                base_dataset,
                mode=args.perturb_mode,
                level=args.perturb_level,
                seed=seed_base,
                args=args,
            )
        ]
    return [DomainWrapperDataset(part, domain_id) for part in parts]


def _stats_weight_key(key: str) -> str:
    if key in {"E", "E_desc", "R2_e"} or key.startswith("loss_energy_desc_") or key.startswith("r2_energy_desc_"):
        return "W_e"
    if key in {"Q", "Q_desc", "R2_q"} or key.startswith("loss_charge_desc_") or key.startswith("r2_charge_desc_") or key.startswith("acc_charge_desc_"):
        return "W_q"
    return "B"


def _resolve_atom_counts_for_all_ranks(dataset, *, args, ctx):
    if not ctx.enabled:
        return resolve_atom_counts(dataset, cache_dir=args.atom_count_cache_dir)

    if ctx.is_main_process:
        return resolve_atom_counts(dataset, cache_dir=args.atom_count_cache_dir, force_recompute=False)

    cache_file = atom_count_cache_path(dataset, args.atom_count_cache_dir)
    if cache_file is None:
        raise ValueError("atom_count_cache_dir must be set when distributed preprocessing is enabled.")

    deadline = time.monotonic() + max(60, int(args.dist_timeout_minutes) * 60)
    while True:
        cached = try_load_atom_count_cache(dataset, cache_dir=args.atom_count_cache_dir)
        if cached is not None:
            return cached
        if time.monotonic() >= deadline:
            raise TimeoutError(
                f"Timed out waiting for atom-count cache {cache_file} to appear for rank {ctx.rank}. "
                "Increase --dist_timeout_minutes or precompute the cache before torchrun."
            )
        time.sleep(5.0)


def _resolve_random_val_split_for_all_ranks(dataset_specs, *, args, ctx):
    if not ctx.enabled or not args.split_cache_path:
        return resolve_random_val_split(
            dataset_specs,
            val_size=args.random_val_size,
            seed=args.split_seed,
            cache_path=args.split_cache_path,
        )

    if ctx.is_main_process:
        resolve_random_val_split(
            dataset_specs,
            val_size=args.random_val_size,
            seed=args.split_seed,
            cache_path=args.split_cache_path,
            force_recompute=False,
        )
    barrier()
    return resolve_random_val_split(
        dataset_specs,
        val_size=args.random_val_size,
        seed=args.split_seed,
        cache_path=args.split_cache_path,
        force_recompute=False,
    )


def _build_train_val_datasets(args, ctx):
    starts = pad_list(args.starts, len(args.data_roots), 0)
    ends = pad_list(args.ends, len(args.data_roots), None)
    val_starts = pad_list(args.val_starts, len(args.val_data_roots), 0)
    val_ends = pad_list(args.val_ends, len(args.val_data_roots), None)

    base_infos = []
    for domain_id, (path, start, end) in enumerate(zip(args.data_roots, starts, ends)):
        base_root = create_dataset_or_none(path, start, end, role="train")
        if base_root is None:
            continue
        base_raw = OnlyStableWrapper(base_root)
        if len(base_raw) == 0:
            LOGGER.warning("Skip empty dataset root: %s (start=%s end=%s)", path, start, end)
            continue
        atom_counts = _resolve_atom_counts_for_all_ranks(base_raw, args=args, ctx=ctx)
        valid_mask = (atom_counts > 0) & (atom_counts <= int(args.filter_max_atoms))
        keep_indices = np.nonzero(valid_mask)[0]
        dropped = int(len(atom_counts) - len(keep_indices))
        if len(keep_indices) == 0:
            LOGGER.warning(
                "Skip dataset root after atom filtering: %s (start=%s end=%s filter_max_atoms=%s dropped=%s)",
                path,
                start,
                end,
                args.filter_max_atoms,
                dropped,
            )
            continue
        if dropped > 0:
            LOGGER.info(
                "Atom filtering kept %d / %d samples for %s (filter_max_atoms=%s)",
                len(keep_indices),
                len(atom_counts),
                path,
                args.filter_max_atoms,
            )
        base_filtered = IndexedSubsetDataset(base_raw, keep_indices, atom_counts=atom_counts[keep_indices])
        base_infos.append({"domain_id": domain_id, "path": path, "start": start, "end": end, "base": base_filtered})

    if not base_infos:
        raise ValueError("No training datasets were built. Check data_roots and index ranges.")

    train_list = []
    val_list = []
    std_bases = []

    if args.val_data_roots:
        for info in base_infos:
            std_bases.append(info["base"])
            train_list.extend(
                _build_domain_parts(
                    info["base"],
                    domain_id=info["domain_id"],
                    args=args,
                    seed_base=args.perturb_seed + info["domain_id"] * 100000,
                )
            )

        for offset, (path, start, end) in enumerate(zip(args.val_data_roots, val_starts, val_ends)):
            domain_id = len(base_infos) + offset
            base_root = create_dataset_or_none(path, start, end, role="val")
            if base_root is None:
                continue
            base = OnlyStableWrapper(base_root)
            if len(base) == 0:
                LOGGER.warning("Skip empty val dataset root: %s (start=%s end=%s)", path, start, end)
                continue
            atom_counts = _resolve_atom_counts_for_all_ranks(base, args=args, ctx=ctx)
            valid_mask = (atom_counts > 0) & (atom_counts <= int(args.filter_max_atoms))
            keep_indices = np.nonzero(valid_mask)[0]
            if len(keep_indices) == 0:
                LOGGER.warning(
                    "Skip val dataset root after atom filtering: %s (start=%s end=%s filter_max_atoms=%s)",
                    path,
                    start,
                    end,
                    args.filter_max_atoms,
                )
                continue
            if len(keep_indices) < len(atom_counts):
                LOGGER.info(
                    "Atom filtering kept %d / %d validation samples for %s (filter_max_atoms=%s)",
                    len(keep_indices),
                    len(atom_counts),
                    path,
                    args.filter_max_atoms,
                )
            base = IndexedSubsetDataset(base, keep_indices, atom_counts=atom_counts[keep_indices])
            val_list.extend(
                _build_domain_parts(
                    base,
                    domain_id=domain_id,
                    args=args,
                    seed_base=args.perturb_seed + 1000000 + domain_id * 100000,
                )
            )
    else:
        split_specs = [_make_split_spec(info["path"], info["start"], info["end"], len(info["base"])) for info in base_infos]
        val_indices_by_root = _resolve_random_val_split_for_all_ranks(split_specs, args=args, ctx=ctx)

        for info, val_indices in zip(base_infos, val_indices_by_root):
            base_raw = info["base"]
            domain_id = info["domain_id"]
            val_indices = sorted({int(i) for i in val_indices})

            train_base = ExcludingSubsetDataset(base_raw, val_indices) if val_indices else base_raw
            std_bases.append(train_base)
            train_list.extend(
                _build_domain_parts(
                    train_base,
                    domain_id=domain_id,
                    args=args,
                    seed_base=args.perturb_seed + domain_id * 100000,
                )
            )

            if val_indices:
                val_base = IndexedSubsetDataset(base_raw, val_indices)
                if len(val_base) > 0:
                    val_list.extend(
                        _build_domain_parts(
                            val_base,
                            domain_id=domain_id,
                            args=args,
                            seed_base=args.perturb_seed + 1000000 + domain_id * 100000,
                        )
                    )

    train_ds = ConcatDataset(train_list)
    val_ds = ConcatDataset(val_list) if val_list else None
    return train_ds, val_ds, std_bases


def _make_optimizer(model, args):
    decay, no_decay = [], []
    for name, param in model.named_parameters():
        target = no_decay if name.endswith("bias") or "norm" in name.lower() else decay
        target.append(param)
    return torch.optim.AdamW(
        [
            {"params": decay, "weight_decay": 0.01},
            {"params": no_decay, "weight_decay": 0.0},
        ],
        lr=args.lr,
        betas=(0.9, 0.95),
        eps=1e-8,
    )


def _merge_stats(accum, stats):
    if accum is None:
        return dict(stats)

    prev_weight = int(accum.get("B", 0))
    new_weight = int(stats.get("B", 0))
    total_weight = prev_weight + new_weight
    merged = {
        "B": total_weight,
        "bad": int(accum.get("bad", 0)) + int(stats.get("bad", 0)),
        "global_step": int(stats.get("global_step", accum.get("global_step", 0))),
        "optimizer_steps": int(accum.get("optimizer_steps", 0)) + int(stats.get("optimizer_steps", 0)),
        "completed_pass": int(bool(accum.get("completed_pass", 1)) and bool(stats.get("completed_pass", 1))),
    }
    for key in set(accum) | set(stats):
        if key.startswith("W_"):
            merged[key] = int(accum.get(key, 0)) + int(stats.get(key, 0))
    for key in set(accum) | set(stats):
        if key in {"B", "bad", "global_step", "optimizer_steps", "completed_pass"} or key.startswith("W_"):
            continue
        weight_key = _stats_weight_key(key)
        prev_key_weight = int(accum.get(weight_key, prev_weight if weight_key == "B" else 0))
        new_key_weight = int(stats.get(weight_key, new_weight if weight_key == "B" else 0))
        total_key_weight = prev_key_weight + new_key_weight
        if total_key_weight <= 0:
            merged[key] = float(stats.get(key, accum.get(key, 0.0)))
            continue
        merged[key] = (
            float(accum.get(key, 0.0)) * prev_key_weight
            + float(stats.get(key, 0.0)) * new_key_weight
        ) / total_key_weight
    return merged


def _steps_until_next_multiple(current_step: int, every: int) -> float:
    if every is None or int(every) <= 0:
        return float("inf")
    every = int(every)
    remainder = int(current_step) % every
    return float(every if remainder == 0 else every - remainder)


def _current_stage(args, global_step: int) -> int:
    return 0 if int(global_step) < int(args.stage1_max_steps) else 1


def _train_geom_lambdas(args, stage: int) -> tuple[float, float, float]:
    if int(stage) <= 0:
        return float(args.lambda_dist), 0.0, 0.0
    return float(args.lambda_dist), float(args.lambda_angle), float(args.lambda_torsion)


def _validation_geom_lambdas(args) -> tuple[float, float, float]:
    return float(args.lambda_dist), float(args.lambda_angle), float(args.lambda_torsion)


def _normalize_position(epoch: int, epoch_step: int, steps_per_epoch: int) -> tuple[int, int]:
    next_epoch = int(epoch)
    next_step = int(epoch_step)
    while steps_per_epoch > 0 and next_step >= steps_per_epoch:
        next_epoch += 1
        next_step -= steps_per_epoch
    return next_epoch, next_step


def _skip_batches(iterator, steps_to_skip: int) -> None:
    for _ in range(max(0, int(steps_to_skip))):
        next(iterator)


def _save_runtime_checkpoint(
    *,
    model,
    model_cfg,
    std,
    args,
    optimizer,
    scheduler,
    save_path: str,
    current_epoch: int,
    epoch_step: int,
    steps_per_epoch: int,
    global_step: int,
    current_stage: int,
    stage_step: int,
    best_selection_loss: float,
    checkpoint_kind: str,
):
    save_epoch, save_epoch_step = _normalize_position(current_epoch, epoch_step, steps_per_epoch)
    save_checkpoint(
        model,
        model_cfg,
        std,
        save_path,
        train_cfg=dict(vars(args)),
        optimizer=optimizer,
        scheduler=scheduler,
        current_epoch=save_epoch,
        epoch_step=save_epoch_step,
        global_step=global_step,
        current_stage=current_stage,
        stage_step=stage_step,
        best_selection_loss=best_selection_loss,
        checkpoint_kind=checkpoint_kind,
    )


def _run_validation(train_model, val_loader, *, args, device, std, global_step, current_epoch, current_stage, ctx, dataloader_debug, ddp_debug):
    val_lam_d, val_lam_a, val_lam_t = _validation_geom_lambdas(args)
    stats = run_epoch(
        train_model,
        val_loader,
        device,
        std,
        scaler=build_grad_scaler(device, "none"),
        loss_cutoff=args.loss_cutoff,
        n_atom_types=args.n_atom_types,
        lam_c=0.0,
        lam_d=val_lam_d,
        lam_a=val_lam_a,
        lam_t=val_lam_t,
        lam_p=0.0,
        lam_e=args.lambda_e,
        lam_e_desc=args.lambda_e_desc,
        lam_q=args.lambda_q,
        lam_q_desc=args.lambda_q_desc,
        lam_z=args.lambda_z,
        lam_z_desc=args.lambda_z_desc,
        z_label_smooth=args.z_label_smooth,
        z_focal_gamma=args.z_focal_gamma,
        z_temp=args.z_temp,
        z_class_balance=args.z_class_balance,
        z_entropy_reg=args.z_entropy_reg,
        z_logit_l2=args.z_logit_l2,
        morse_d=args.morse_D,
        morse_a=args.morse_a,
        optim=None,
        amp_dtype=args.amp_dtype,
        desc=f"Val@{global_step}",
        scheduler=None,
        global_step_start=global_step,
        is_main_process=ctx.is_main_process,
        distributed_sync=ctx.enabled,
        dataloader_debug=dataloader_debug,
        ddp_debug=ddp_debug,
        current_epoch=current_epoch,
        current_stage=current_stage,
    )
    total = _total_loss(args, stats)
    selection = _selection_loss(args, stats)
    summary = _summarize_metrics(
        stats,
        stage=current_stage,
        stage_step=0,
        lr=0.0,
        loss_total=total,
        selection_loss=selection,
        lam_d=val_lam_d,
        lam_a=val_lam_a,
        lam_t=val_lam_t,
    )
    return stats, total, selection, summary


def main() -> None:
    args = get_args()
    _enforce_runtime_policy(args)

    ctx = init_distributed(args)
    if not ctx.is_main_process:
        LOGGER.setLevel(logging.WARNING)

    set_seed(args.seed + ctx.rank)
    device = ctx.device
    pin_memory = device.type == "cuda"
    if device.type != "cuda" and args.amp_dtype != "none":
        LOGGER.warning("AMP dtype %s requested on non-CUDA device; forcing amp_dtype=none.", args.amp_dtype)
        args.amp_dtype = "none"

    if ctx.is_main_process:
        LOGGER.info(
            "Launch context: distributed=%s backend=%s world_size=%d rank=%d local_rank=%d device=%s",
            ctx.enabled,
            ctx.backend,
            ctx.world_size,
            ctx.rank,
            ctx.local_rank,
            device,
        )

    checkpoint_paths = resolve_checkpoint_paths(args.save_path, args.checkpoint_dir)
    if not args.atom_count_cache_dir:
        args.atom_count_cache_dir = str(Path(checkpoint_paths["root_dir"]) / "atom_count_cache")
    dataloader_debug_dir = args.dataloader_debug_dir or str(Path(checkpoint_paths["root_dir"]) / "dataloader_debug")
    dataloader_debug = DataLoaderDebugConfig(
        enabled=bool(args.dataloader_debug),
        interval_s=float(args.dataloader_debug_interval),
        stall_threshold_s=float(args.dataloader_stall_threshold),
        timeout_s=float(args.dataloader_timeout),
        slow_fetch_threshold_s=float(args.dataloader_slow_fetch_threshold),
        log_dir=dataloader_debug_dir,
    )
    ddp_debug_dir = args.ddp_debug_dir or str(Path(checkpoint_paths["root_dir"]) / "ddp_debug")
    ddp_debug = DDPDebugConfig(
        enabled=bool(args.ddp_debug),
        interval_s=float(args.ddp_debug_interval),
        stall_threshold_s=float(args.ddp_debug_stall_threshold),
        log_dir=ddp_debug_dir,
        grad_sample_size=int(args.ddp_debug_grad_sample_size),
    )
    configure_worker_debug_env(dataloader_debug, rank=ctx.rank)
    if ctx.is_main_process and dataloader_debug.enabled:
        LOGGER.info(
            "DataLoader debug enabled: log_dir=%s interval=%ss stall_threshold=%ss timeout=%ss slow_fetch_threshold=%ss",
            dataloader_debug.log_dir,
            dataloader_debug.interval_s,
            dataloader_debug.stall_threshold_s,
            dataloader_debug.timeout_s,
            dataloader_debug.slow_fetch_threshold_s,
        )
    if ctx.is_main_process and ddp_debug.enabled:
        LOGGER.info(
            "DDP debug enabled: log_dir=%s interval=%ss stall_threshold=%ss grad_sample_size=%s",
            ddp_debug.log_dir,
            ddp_debug.interval_s,
            ddp_debug.stall_threshold_s,
            ddp_debug.grad_sample_size,
        )

    train_ds, val_ds, std_bases = _build_train_val_datasets(args, ctx)
    train_sampler = None
    train_batch_sampler = None
    val_sampler = None
    val_batch_sampler = None
    train_atom_counts = dataset_atom_counts(train_ds)
    if args.atom_budget_per_batch > 0:
        train_batch_sampler = DistributedAtomBudgetBatchSampler(
            train_atom_counts,
            max_atoms_per_batch=args.atom_budget_per_batch,
            max_samples_per_batch=args.batch_size,
            num_replicas=ctx.world_size if ctx.enabled else 1,
            rank=ctx.rank if ctx.enabled else 0,
            shuffle=True,
            seed=args.seed,
            drop_last=False,
        )
    elif ctx.enabled:
        train_sampler = DistributedSampler(
            train_ds,
            num_replicas=ctx.world_size,
            rank=ctx.rank,
            shuffle=True,
            drop_last=False,
            seed=args.seed,
        )
        if val_ds is not None:
            val_sampler = DistributedEvalSampler(val_ds, num_replicas=ctx.world_size, rank=ctx.rank)

    if ctx.enabled and val_ds is not None and val_sampler is None:
        val_sampler = DistributedEvalSampler(val_ds, num_replicas=ctx.world_size, rank=ctx.rank)

    if val_ds is not None and int(args.val_atom_budget_per_batch) > 0:
        val_atom_counts = dataset_atom_counts(val_ds)
        val_batch_sampler = DistributedEvalAtomBudgetBatchSampler(
            val_atom_counts,
            max_atoms_per_batch=args.val_atom_budget_per_batch,
            max_samples_per_batch=args.val_batch_size,
            num_replicas=ctx.world_size if ctx.enabled else 1,
            rank=ctx.rank if ctx.enabled else 0,
        )
        val_sampler = None

    train_loader = build_dataloader(
        train_ds,
        batch_size=args.batch_size,
        num_workers=args.num_workers,
        shuffle=train_sampler is None and train_batch_sampler is None,
        sampler=train_sampler,
        batch_sampler=train_batch_sampler,
        pin_memory=pin_memory,
        seed=args.seed + ctx.rank,
        timeout_s=args.dataloader_timeout,
    )
    if ctx.is_main_process:
        LOGGER.info(
            "Dataset build: train=%d val=%d filter_max_atoms=%d atom_budget_per_batch=%d max_samples_per_batch=%d val_batch_size=%d val_atom_budget_per_batch=%d",
            len(train_ds),
            len(val_ds) if val_ds is not None else 0,
            int(args.filter_max_atoms),
            int(args.atom_budget_per_batch),
            int(args.batch_size),
            int(args.val_batch_size),
            int(args.val_atom_budget_per_batch),
        )
    val_loader = None
    if val_ds is not None:
        val_loader = build_dataloader(
            val_ds,
            batch_size=args.val_batch_size,
            num_workers=args.val_num_workers,
            shuffle=False,
            sampler=val_sampler,
            batch_sampler=val_batch_sampler,
            pin_memory=pin_memory,
            seed=args.seed + 1000 + ctx.rank,
            timeout_s=args.dataloader_timeout,
        )

    steps_per_epoch = len(train_loader)
    if steps_per_epoch <= 0:
        raise ValueError("Training dataloader is empty after dataset construction.")
    total_steps = steps_per_epoch * args.epochs
    warm_steps = int(total_steps * args.warmup_pct)

    resume_payload = load_checkpoint(args.resume_from, map_location="cpu") if args.resume_from else None
    if resume_payload is not None and ctx.is_main_process:
        LOGGER.info(
            "Resuming from %s at epoch=%s epoch_step=%s global_step=%s stage=%s",
            args.resume_from,
            resume_payload.get("current_epoch"),
            resume_payload.get("epoch_step"),
            resume_payload.get("global_step"),
            resume_payload.get("current_stage"),
        )

    if resume_payload is not None:
        std = resume_payload["standardizer"]
    elif ctx.is_main_process:
        std = standardizer(
            std_bases,
            ratio=args.standardizer_ratio,
            cap=args.standardizer_cap,
            seed=args.seed,
        )
    else:
        std = None
    std = broadcast_object(std, src=0)

    model, bb_cfg = build_model(args, device)
    model_cfg = _build_model_cfg(args, bb_cfg)
    optimizer = _make_optimizer(model, args)
    scheduler = build_lr_scheduler(optimizer, total_steps, warm_steps)

    if resume_payload is not None:
        model.load_state_dict(resume_payload["model_state"], strict=True)
        if resume_payload.get("optimizer_state") is not None:
            optimizer.load_state_dict(resume_payload["optimizer_state"])
        if resume_payload.get("scheduler_state") is not None:
            scheduler.load_state_dict(resume_payload["scheduler_state"])

    train_model = wrap_ddp(
        model,
        ctx,
        find_unused_parameters=args.find_unused_parameters,
        broadcast_buffers=args.ddp_broadcast_buffers,
        static_graph=args.ddp_static_graph,
    )
    scaler = build_grad_scaler(device, args.amp_dtype)

    global_step = int(resume_payload.get("global_step", 0)) if resume_payload else 0
    current_epoch = int(resume_payload.get("current_epoch", 1)) if resume_payload else 1
    epoch_step = int(resume_payload.get("epoch_step", 0)) if resume_payload else 0
    current_stage = int(resume_payload.get("current_stage", _current_stage(args, global_step))) if resume_payload else _current_stage(args, global_step)
    stage_step = int(resume_payload.get("stage_step", 0)) if resume_payload else 0
    best_selection_loss = float(resume_payload.get("best_selection_loss", float("inf"))) if resume_payload else float("inf")

    if current_epoch > args.epochs and global_step >= total_steps:
        if ctx.is_main_process:
            LOGGER.info("Checkpoint already represents a completed run; nothing to do.")
        cleanup_distributed()
        return

    run = None
    if ctx.is_main_process:
        run = init_wandb_run(
            args,
            model=model,
            device=str(device),
            train_size=len(train_ds),
            val_size=(len(val_ds) if val_ds is not None else 0),
        )
        update_summary(
            run,
            {
                "meta/device": str(device),
                "meta/train_size": len(train_ds),
                "meta/val_size": len(val_ds) if val_ds is not None else 0,
                "meta/distributed": int(ctx.enabled),
                "meta/world_size": ctx.world_size,
                "meta/steps_per_epoch": steps_per_epoch,
                "meta/total_optimizer_steps": total_steps,
                "meta/effective_global_batch": args.batch_size * max(1, ctx.world_size),
                "meta/checkpoint_root": checkpoint_paths["root_dir"],
                "meta/checkpoint_best": checkpoint_paths["best_path"],
                "meta/checkpoint_latest": checkpoint_paths["latest_path"],
                "meta/checkpoint_archive_dir": checkpoint_paths["archive_dir"],
                "meta/resume_from": args.resume_from or "",
                "meta/dataloader_debug": int(dataloader_debug.enabled),
                "meta/dataloader_debug_dir": dataloader_debug.log_dir or "",
                "meta/dataloader_timeout_s": dataloader_debug.timeout_s,
                "meta/ddp_debug": int(ddp_debug.enabled),
                "meta/ddp_debug_dir": ddp_debug.log_dir or "",
                "meta/ddp_debug_interval_s": ddp_debug.interval_s,
                "meta/ddp_debug_stall_threshold_s": ddp_debug.stall_threshold_s,
                "meta/filter_max_atoms": int(args.filter_max_atoms),
                "meta/atom_budget_per_batch": int(args.atom_budget_per_batch),
                "meta/val_batch_size": int(args.val_batch_size),
                "meta/val_atom_budget_per_batch": int(args.val_atom_budget_per_batch),
                "meta/atom_count_cache_dir": args.atom_count_cache_dir or "",
                **_pooling_weight_metrics(model),
            },
        )

    def log_train_batch(batch_metrics, step):
        payload = dict(batch_metrics)
        payload.update(_pooling_weight_metrics(train_model))
        log_metrics(run, "train/batch", payload, global_step=step)

    last_val_step = -1
    try:
        for epoch in range(current_epoch, args.epochs + 1):
            if train_batch_sampler is not None:
                train_batch_sampler.set_epoch(epoch)
            elif train_sampler is not None:
                train_sampler.set_epoch(epoch)

            train_iter = iter(train_loader)
            if epoch == current_epoch and epoch_step > 0:
                if ctx.is_main_process:
                    LOGGER.info("Skipping %d already-completed batches at the start of epoch %d", epoch_step, epoch)
                _skip_batches(train_iter, epoch_step)

            epoch_stats = None
            if device.type == "cuda":
                torch.cuda.reset_peak_memory_stats()

            while epoch_step < steps_per_epoch:
                current_stage = _current_stage(args, global_step)
                train_lam_d, train_lam_a, train_lam_t = _train_geom_lambdas(args, current_stage)

                if ctx.is_main_process and stage_step == 0:
                    LOGGER.info(
                        "Epoch %d stage %d: global_step=%d lam_d=%s lam_a=%s lam_t=%s",
                        epoch,
                        current_stage,
                        global_step,
                        train_lam_d,
                        train_lam_a,
                        train_lam_t,
                    )

                remaining = [steps_per_epoch - epoch_step]
                if current_stage == 0 and global_step < args.stage1_max_steps:
                    remaining.append(args.stage1_max_steps - global_step)
                for interval in (
                    args.validate_every_steps,
                    args.save_latest_every_steps,
                    args.save_archive_every_steps,
                ):
                    delta = _steps_until_next_multiple(global_step, interval)
                    if delta != float("inf"):
                        remaining.append(int(delta))
                if args.max_optimizer_steps > 0:
                    remaining.append(args.max_optimizer_steps - global_step)

                chunk_steps = min(step for step in remaining if step > 0)
                train_chunk = run_epoch(
                    train_model,
                    train_iter,
                    device,
                    std,
                    scaler,
                    loss_cutoff=args.loss_cutoff,
                    n_atom_types=args.n_atom_types,
                    lam_c=0.0,
                    lam_d=train_lam_d,
                    lam_a=train_lam_a,
                    lam_t=train_lam_t,
                    lam_p=0.0,
                    lam_e=args.lambda_e,
                    lam_e_desc=args.lambda_e_desc,
                    lam_q=args.lambda_q,
                    lam_q_desc=args.lambda_q_desc,
                    lam_z=args.lambda_z,
                    lam_z_desc=args.lambda_z_desc,
                    z_label_smooth=args.z_label_smooth,
                    z_focal_gamma=args.z_focal_gamma,
                    z_temp=args.z_temp,
                    z_class_balance=args.z_class_balance,
                    z_entropy_reg=args.z_entropy_reg,
                    z_logit_l2=args.z_logit_l2,
                    morse_d=args.morse_D,
                    morse_a=args.morse_a,
                    optim=optimizer,
                    amp_dtype=args.amp_dtype,
                    desc=f"Train@{global_step}",
                    scheduler=scheduler,
                    batch_logger=log_train_batch if run is not None else None,
                    batch_log_interval=args.wandb_log_batch_every,
                    global_step_start=global_step,
                    is_main_process=ctx.is_main_process,
                    distributed_sync=ctx.enabled,
                    max_optimizer_steps=chunk_steps,
                    dataloader_debug=dataloader_debug,
                    ddp_debug=ddp_debug,
                    current_epoch=epoch,
                    current_stage=current_stage,
                    progress_total=steps_per_epoch,
                    progress_initial=epoch_step,
                )

                if train_chunk["optimizer_steps"] <= 0:
                    raise RuntimeError("Training chunk completed zero optimizer steps; iterator state is inconsistent.")

                global_step = int(train_chunk["global_step"])
                epoch_step += int(train_chunk["optimizer_steps"])
                stage_step += int(train_chunk["optimizer_steps"])
                epoch_stats = _merge_stats(epoch_stats, train_chunk)
                current_lr = optimizer.param_groups[0]["lr"]

                if ctx.is_main_process:
                    train_window_metrics = _summarize_metrics(
                        train_chunk,
                        stage=current_stage,
                        stage_step=stage_step,
                        lr=current_lr,
                        loss_total=_total_loss(args, train_chunk),
                        selection_loss=_selection_loss(args, train_chunk),
                        lam_d=train_lam_d,
                        lam_a=train_lam_a,
                        lam_t=train_lam_t,
                    )
                    train_window_metrics.update(_pooling_weight_metrics(train_model))
                    log_metrics(
                        run,
                        "train/window",
                        train_window_metrics,
                        epoch=epoch,
                        global_step=global_step,
                    )

                next_stage = _current_stage(args, global_step)
                if next_stage != current_stage:
                    current_stage = next_stage
                    stage_step = 0
                    if ctx.is_main_process:
                        LOGGER.info("Stage transition: entering stage %d at global_step=%d", current_stage, global_step)
                        log_metrics(
                            run,
                            "meta",
                            {"stage_transition": 1, "stage_to": current_stage},
                            epoch=epoch,
                            global_step=global_step,
                        )

                if ctx.is_main_process and args.save_latest_every_steps > 0 and global_step % args.save_latest_every_steps == 0:
                    _save_runtime_checkpoint(
                        model=model,
                        model_cfg=model_cfg,
                        std=std,
                        args=args,
                        optimizer=optimizer,
                        scheduler=scheduler,
                        save_path=checkpoint_paths["latest_path"],
                        current_epoch=epoch,
                        epoch_step=epoch_step,
                        steps_per_epoch=steps_per_epoch,
                        global_step=global_step,
                        current_stage=current_stage,
                        stage_step=stage_step,
                        best_selection_loss=best_selection_loss,
                        checkpoint_kind="latest",
                    )

                if ctx.is_main_process and args.save_archive_every_steps > 0 and global_step % args.save_archive_every_steps == 0:
                    archive_path = str(Path(checkpoint_paths["archive_dir"]) / f"step_{global_step:08d}.pt")
                    _save_runtime_checkpoint(
                        model=model,
                        model_cfg=model_cfg,
                        std=std,
                        args=args,
                        optimizer=optimizer,
                        scheduler=scheduler,
                        save_path=archive_path,
                        current_epoch=epoch,
                        epoch_step=epoch_step,
                        steps_per_epoch=steps_per_epoch,
                        global_step=global_step,
                        current_stage=current_stage,
                        stage_step=stage_step,
                        best_selection_loss=best_selection_loss,
                        checkpoint_kind="archive",
                    )

                should_validate = val_loader is not None and args.validate_every_steps > 0 and global_step % args.validate_every_steps == 0
                if should_validate:
                    val_stats, val_total, val_selection, val_summary = _run_validation(
                        train_model,
                        val_loader,
                        args=args,
                        device=device,
                        std=std,
                        global_step=global_step,
                        current_epoch=epoch,
                        current_stage=current_stage,
                        ctx=ctx,
                        dataloader_debug=dataloader_debug,
                        ddp_debug=ddp_debug,
                    )
                    last_val_step = global_step
                    if ctx.is_main_process:
                        _print_metrics("Val  ", val_stats)
                        val_payload = dict(val_summary)
                        val_payload.update(_pooling_weight_metrics(train_model))
                        log_metrics(run, "val", val_payload, epoch=epoch, global_step=global_step)
                        update_summary(run, _pooling_weight_metrics(train_model))
                        if val_selection < best_selection_loss:
                            best_selection_loss = val_selection
                            _save_runtime_checkpoint(
                                model=model,
                                model_cfg=model_cfg,
                                std=std,
                                args=args,
                                optimizer=optimizer,
                                scheduler=scheduler,
                                save_path=checkpoint_paths["best_path"],
                                current_epoch=epoch,
                                epoch_step=epoch_step,
                                steps_per_epoch=steps_per_epoch,
                                global_step=global_step,
                                current_stage=current_stage,
                                stage_step=stage_step,
                                best_selection_loss=best_selection_loss,
                                checkpoint_kind="best",
                            )
                            update_summary(
                                run,
                                {
                                    "best/global_step": global_step,
                                    "best/epoch": epoch,
                                    "best/stage": current_stage,
                                    "best/selection_loss": best_selection_loss,
                                    "best/path": checkpoint_paths["best_path"],
                                },
                            )
                            if args.wandb_log_checkpoints:
                                log_checkpoint_artifact(
                                    run,
                                    checkpoint_paths["best_path"],
                                    label="best",
                                    aliases=["best", f"step_{global_step:08d}"],
                                    metadata={"global_step": global_step, "epoch": epoch, "stage": current_stage},
                                )

                if args.max_optimizer_steps > 0 and global_step >= args.max_optimizer_steps:
                    break

            if epoch_stats is not None and ctx.is_main_process:
                _print_metrics("Train", epoch_stats)
                epoch_payload = _summarize_metrics(
                    epoch_stats,
                    stage=current_stage,
                    stage_step=stage_step,
                    lr=optimizer.param_groups[0]["lr"],
                    loss_total=_total_loss(args, epoch_stats),
                    selection_loss=_selection_loss(args, epoch_stats),
                    lam_d=train_lam_d,
                    lam_a=train_lam_a,
                    lam_t=train_lam_t,
                )
                epoch_payload.update(_pooling_weight_metrics(train_model))
                log_metrics(
                    run,
                    "train/epoch",
                    epoch_payload,
                    epoch=epoch,
                    global_step=global_step,
                )
                meta_metrics = {
                    "stage": current_stage,
                    "stage_step": stage_step,
                    "global_step": global_step,
                    "best_selection_loss_so_far": best_selection_loss,
                    "world_size": ctx.world_size,
                }
                if device.type == "cuda":
                    meta_metrics["cuda_peak_memory_gb"] = torch.cuda.max_memory_allocated() / (1024 ** 3)
                log_metrics(run, "meta", meta_metrics, epoch=epoch, global_step=global_step)

            if args.max_optimizer_steps > 0 and global_step >= args.max_optimizer_steps:
                break

            current_epoch = epoch + 1
            epoch_step = 0

        if val_loader is not None and global_step > 0 and global_step != last_val_step:
            val_stats, val_total, val_selection, val_summary = _run_validation(
                train_model,
                val_loader,
                args=args,
                device=device,
                std=std,
                global_step=global_step,
                current_epoch=min(args.epochs, max(1, current_epoch)),
                current_stage=current_stage,
                ctx=ctx,
                dataloader_debug=dataloader_debug,
                ddp_debug=ddp_debug,
            )
            if ctx.is_main_process:
                _print_metrics("Val  ", val_stats)
                final_val_payload = dict(val_summary)
                final_val_payload.update(_pooling_weight_metrics(train_model))
                log_metrics(run, "val", final_val_payload, epoch=min(args.epochs, max(1, current_epoch)), global_step=global_step)
                update_summary(run, _pooling_weight_metrics(train_model))
                if val_selection < best_selection_loss:
                    best_selection_loss = val_selection
                    _save_runtime_checkpoint(
                        model=model,
                        model_cfg=model_cfg,
                        std=std,
                        args=args,
                        optimizer=optimizer,
                        scheduler=scheduler,
                        save_path=checkpoint_paths["best_path"],
                        current_epoch=min(args.epochs, max(1, current_epoch)),
                        epoch_step=epoch_step,
                        steps_per_epoch=steps_per_epoch,
                        global_step=global_step,
                        current_stage=current_stage,
                        stage_step=stage_step,
                        best_selection_loss=best_selection_loss,
                        checkpoint_kind="best",
                    )

        if ctx.is_main_process:
            _save_runtime_checkpoint(
                model=model,
                model_cfg=model_cfg,
                std=std,
                args=args,
                optimizer=optimizer,
                scheduler=scheduler,
                save_path=checkpoint_paths["latest_path"],
                current_epoch=min(args.epochs, max(1, current_epoch)),
                epoch_step=epoch_step,
                steps_per_epoch=steps_per_epoch,
                global_step=global_step,
                current_stage=current_stage,
                stage_step=stage_step,
                best_selection_loss=best_selection_loss,
                checkpoint_kind="latest",
            )
            _save_runtime_checkpoint(
                model=model,
                model_cfg=model_cfg,
                std=std,
                args=args,
                optimizer=optimizer,
                scheduler=scheduler,
                save_path=checkpoint_paths["final_path"],
                current_epoch=min(args.epochs, max(1, current_epoch)),
                epoch_step=epoch_step,
                steps_per_epoch=steps_per_epoch,
                global_step=global_step,
                current_stage=current_stage,
                stage_step=stage_step,
                best_selection_loss=best_selection_loss,
                checkpoint_kind="final",
            )
    finally:
        finish_run(run)
        barrier()
        cleanup_distributed()


if __name__ == "__main__":
    main()
