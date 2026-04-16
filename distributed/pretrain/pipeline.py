from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path
import re
import socket
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

try:
    from ..dataset.descriptor_schema import graph_descriptor_indices, resolve_graph_descriptor_selection
except ImportError:
    from dataset.descriptor_schema import graph_descriptor_indices, resolve_graph_descriptor_selection

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
    try_build_precomputed_recipe_dataset,
    try_load_atom_count_cache,
)
from .dataloader_debug import DataLoaderDebugConfig, configure_worker_debug_env
from .ddp_debug import DDPDebugConfig
from .degrade_molecules import DegradeConfig
from .dist_utils import barrier, broadcast_object, cleanup_distributed, init_distributed, unwrap_model, wrap_ddp
from .timing_utils import StepTimingLogger, summarize_step_timing_logs
from .train_loop import build_grad_scaler, run_epoch
from .utils import (
    apply_runtime_stability_settings,
    build_lr_scheduler,
    collect_environment_fingerprint,
    pad_list,
    sanitize_for_json,
    write_json,
)
from .wandb_utils import finish_run, init_wandb_run, log_checkpoint_artifact, log_metrics, update_summary

warnings.filterwarnings("ignore", category=UserWarning)
logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
LOGGER = logging.getLogger("multitask")
_PERTURB_LMDB_FILENAME_RE = re.compile(
    r"(?P<mode>clean|geom|topo|both)(?:\s*[:_\-]?\s*(?P<level>\d+(?:[.p]\d+)?))?\s*@\s*(?P<ratio>\d+(?:[.p]\d+)?)",
    re.IGNORECASE,
)


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

    if int(getattr(args, "stage1_signal_decay_steps", 0)) < 0:
        LOGGER.warning("--stage1_signal_decay_steps must be >= 0; forcing it to 0.")
        args.stage1_signal_decay_steps = 0

    stage1_signal_floor = float(getattr(args, "stage1_signal_floor", 1.0))
    clamped_stage1_signal_floor = min(1.0, max(0.0, stage1_signal_floor))
    if clamped_stage1_signal_floor != stage1_signal_floor:
        LOGGER.warning("--stage1_signal_floor must be in [0, 1]; clamping to %.3f.", clamped_stage1_signal_floor)
        args.stage1_signal_floor = clamped_stage1_signal_floor

    selected_energy_desc_names, selected_energy_desc_indices = resolve_graph_descriptor_selection(
        getattr(args, "energy_desc_include", None),
        getattr(args, "energy_desc_exclude", None),
    )
    args.energy_desc_names = selected_energy_desc_names
    args.energy_desc_indices = selected_energy_desc_indices
    if len(selected_energy_desc_names) == 0 and float(getattr(args, "lambda_e_desc", 0.0)) > 0.0:
        LOGGER.warning(
            "Energy descriptor supervision is enabled (lambda_e_desc=%s) but the descriptor selector resolved to zero heads.",
            getattr(args, "lambda_e_desc", 0.0),
        )
    if bool(getattr(args, "old_pretraining_strategy", False)):
        LOGGER.info(
            "Legacy pretraining strategy enabled for training: full-batch E/Q/Z/Geom supervision, no train atom-budget sampler, perturb samples forced to the online degradation path, old energy readout and E/Q regression losses, and epoch-based geometry stage switching."
        )


def _apply_resume_model_overrides(args, resume_payload: dict | None) -> None:
    if resume_payload is None:
        return

    model_cfg = resume_payload.get("model_cfg") or {}
    resume_graph_descriptor_names = model_cfg.get("graph_descriptor_names")
    if resume_graph_descriptor_names is None:
        return

    resume_graph_descriptor_names = tuple(resume_graph_descriptor_names)
    current_graph_descriptor_names = tuple(getattr(args, "energy_desc_names", ()))
    if current_graph_descriptor_names == resume_graph_descriptor_names:
        return

    has_cli_override = getattr(args, "energy_desc_include", None) is not None or bool(getattr(args, "energy_desc_exclude", ()))
    if has_cli_override:
        raise ValueError(
            "Resume checkpoint graph descriptor selection "
            f"{resume_graph_descriptor_names} does not match the requested CLI selection {current_graph_descriptor_names}. "
            "Resume with matching selector flags, or omit the selector flags to restore the checkpoint configuration."
        )

    args.energy_desc_include = list(resume_graph_descriptor_names)
    args.energy_desc_exclude = []
    args.energy_desc_names = resume_graph_descriptor_names
    args.energy_desc_indices = graph_descriptor_indices(resume_graph_descriptor_names)
    LOGGER.info(
        "Restored graph descriptor selection from resume checkpoint: %s",
        ", ".join(resume_graph_descriptor_names) if resume_graph_descriptor_names else "<none>",
    )


def _build_model_cfg(args, bb_cfg):
    return {
        "backbone_config": bb_cfg,
        "n_atom_types": args.n_atom_types,
        "n_experts_energy": args.expert_number_E,
        "n_experts_charge": args.expert_number_Q,
        "n_experts_elem": args.expert_number_Z,
        "n_experts_geom": args.expert_number_G,
        "n_experts_bond": args.expert_number_B,
        "top_k_energy": args.topkE,
        "top_k_charge": args.topkQ,
        "top_k_elem": args.topkZ,
        "top_k_geom": args.topkG,
        "top_k_bond": args.topkB,
        "expert_real_layers": args.expert_real_layers,
        "expert_int_layers": args.expert_int_layers,
        "expert_heads": args.expert_heads,
        "expert_ff_mult": args.expert_ff_mult,
        "bond_negative_ratio": args.bond_negative_ratio,
        "direct_linear_noexpert": bool(getattr(args, "direct_linear_noexpert", False)),
        "descriptor_head_mode": "rdkit_descriptor_pack_v2_fused_staged",
        "graph_descriptor_names": tuple(getattr(args, "energy_desc_names", ())),
        "graph_descriptor_target_indices": tuple(getattr(args, "energy_desc_indices", ())),
    }


def _summarize_metrics(stats, *, stage: int, stage_step: int, lr: float, loss_total: float, selection_loss: float, lam_d: float, lam_a: float, lam_t: float):
    total_step_s = float(stats.get("T_step_s", 0.0))
    total_fetch_s = float(stats.get("T_fetch_s", 0.0))
    total_process_s = float(stats.get("T_process_s", 0.0))
    optimizer_steps = max(1, int(stats.get("optimizer_steps", 0)))
    total_graphs = max(0, int(stats.get("B", 0)))
    total_nodes = max(0, int(stats.get("N_nodes", 0)))
    summary = {
        "stage": stage,
        "stage_step": stage_step,
        "loss_total": loss_total,
        "loss_selection": selection_loss,
        "descriptor_ramp": stats.get("DescRamp", 0.0),
        "stage1_signal_scale": stats.get("Stage1Scale", 1.0),
        "loss_energy": stats["E"],
        "loss_energy_desc": stats["E_desc"],
        "loss_charge": stats["Q"],
        "loss_charge_desc": stats["Q_desc"],
        "loss_elem": stats["Z"],
        "loss_elem_desc": stats["Z_desc"],
        "loss_bond_exist": stats.get("Bond_exist", 0.0),
        "acc_bond_exist": stats.get("Acc_bond_exist", 0.0),
        "loss_bond_order": stats.get("Bond_order", 0.0),
        "acc_bond_order": stats.get("Acc_bond_order", 0.0),
        "loss_geom": stats["Geom"],
        "loss_geom_dist": stats["Geom_d"],
        "loss_geom_angle": stats["Geom_a"],
        "loss_geom_torsion": stats["Geom_t"],
        "loss_balance": stats["Bal"],
        "r2_energy": stats["R2_e"],
        "r2_charge": stats["R2_q"],
        "r2_elem": stats["R2_z"],
        "acc_elem": stats["Acc_z"],
        "graph_frac_clean": stats.get("Graphs_clean", 0.0),
        "graph_frac_geom": stats.get("Graphs_geom", 0.0),
        "graph_frac_topo": stats.get("Graphs_topo", 0.0),
        "graph_frac_both": stats.get("Graphs_both", 0.0),
        "bond_graph_fraction": float(stats.get("W_bond_graphs", 0)) / max(1, int(stats.get("B", 0))),
        "bad_batches": stats["bad"],
        "lr": lr,
        "lambda_dist": lam_d,
        "lambda_angle": lam_a,
        "lambda_torsion": lam_t,
        "fetch_time_s": total_fetch_s / optimizer_steps,
        "process_time_s": total_process_s / optimizer_steps,
        "step_time_s": total_step_s / optimizer_steps,
        "graphs_per_s": float(total_graphs) / max(total_step_s, 1e-9),
        "nodes_per_s": float(total_nodes) / max(total_step_s, 1e-9),
        "fetch_share": total_fetch_s / max(total_step_s, 1e-9),
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
    if "Loss_selection" in stats:
        return float(stats["Loss_selection"])
    descriptor_ramp = float(stats.get("DescRamp", 1.0))
    stage1_signal_scale = float(stats.get("Stage1Scale", 1.0))
    stage1_selection = (
        args.lambda_e * stats["E"]
        + args.lambda_q * stats["Q"]
        + args.lambda_z * stats["Z"]
        + args.lambda_bond_exist * stats.get("Bond_exist", 0.0)
        + args.lambda_bond_order * stats.get("Bond_order", 0.0)
        + stats["Geom"]
    )
    stage2_selection = (
        descriptor_ramp * args.lambda_e_desc * stats["E_desc"]
        + descriptor_ramp * args.lambda_q_desc * stats["Q_desc"]
        + descriptor_ramp * args.lambda_z_desc * stats["Z_desc"]
    )
    return stage1_signal_scale * stage1_selection + stage2_selection


def _total_loss(args, stats) -> float:
    if "Loss_total" in stats:
        return float(stats["Loss_total"])
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


_DESCRIPTOR_WANDB_PREFIXES = (
    "loss_energy_desc",
    "loss_charge_desc",
    "loss_elem_desc",
    "r2_energy_desc",
    "r2_charge_desc",
    "acc_charge_desc",
    "acc_elem_desc",
    "pooling/graph_desc/",
)


def _descriptor_supervision_active(args, global_step: int) -> bool:
    if _descriptor_ramp(args, global_step) <= 0.0:
        return False
    return any(
        float(getattr(args, name, 0.0)) > 0.0
        for name in ("lambda_e_desc", "lambda_q_desc", "lambda_z_desc")
    )


def _descriptor_logging_enabled(args, *, global_step: int | None = None, payload: dict | None = None) -> bool:
    if payload is not None and "descriptor_ramp" in payload:
        try:
            return float(payload["descriptor_ramp"]) > 0.0
        except (TypeError, ValueError):
            pass
    if global_step is None:
        return True
    return _descriptor_supervision_active(args, global_step)


def _filter_stage1_descriptor_metrics(payload: dict) -> dict:
    return {
        key: value
        for key, value in payload.items()
        if not key.startswith(_DESCRIPTOR_WANDB_PREFIXES)
    }


def _prepare_wandb_payload(args, payload: dict, *, global_step: int | None = None, descriptor_logging_enabled: bool | None = None) -> dict:
    filtered = dict(payload)
    if descriptor_logging_enabled is None:
        descriptor_logging_enabled = _descriptor_logging_enabled(args, global_step=global_step, payload=filtered)
    if descriptor_logging_enabled:
        return filtered
    return _filter_stage1_descriptor_metrics(filtered)


def _print_metrics(prefix: str, stats) -> None:
    print(
        f"{prefix} E={stats['E']:.3f} E_desc={stats['E_desc']:.3f} | "
        f"Q={stats['Q']:.3f} Q_desc={stats['Q_desc']:.3f} | "
        f"Z={stats['Z']:.3f} Z_desc={stats['Z_desc']:.3f} | "
        f"Bond(ex={stats.get('Bond_exist', 0.0):.3f}, ord={stats.get('Bond_order', 0.0):.3f}) | "
        f"Geom={stats['Geom']:.3f}"
    )
    print(
        f"      Geom(Morse={stats['Geom_d']:.4f} Ang={stats['Geom_a']:.4f} Tor={stats['Geom_t']:.4f}) | "
        f"R2(E={stats['R2_e']:.3f}, Q={stats['R2_q']:.3f}, Z={stats['R2_z']:.3f}) | "
        f"Acc(Z)={stats['Acc_z']:.3f} | Acc(Bond ex={stats.get('Acc_bond_exist', 0.0):.3f}, ord={stats.get('Acc_bond_order', 0.0):.3f}) | "
        f"Mix(clean={stats.get('Graphs_clean', 0.0):.3f}, geom={stats.get('Graphs_geom', 0.0):.3f}, topo={stats.get('Graphs_topo', 0.0):.3f}, both={stats.get('Graphs_both', 0.0):.3f}) | "
        f"Ramp={stats.get('DescRamp', 0.0):.3f} | Stage1Scale={stats.get('Stage1Scale', 1.0):.3f} | Bad={stats['bad']}"
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


def _format_mix_float(value: float) -> str:
    return f"{float(value):g}"


def _perturb_binding_key(mode: str, level: float, ratio: float) -> str:
    normalized_mode = str(mode).strip().lower()
    ratio_token = _format_mix_float(ratio)
    if normalized_mode == "clean":
        return f"clean@{ratio_token}"
    return f"{normalized_mode}:{_format_mix_float(level)}@{ratio_token}"


def _binding_key_from_mix_token(token: str) -> str:
    parsed = parse_perturb_mix(str(token).strip(), 0)
    if len(parsed) != 1:
        raise ValueError(f"Could not parse perturb binding token: {token}")
    mode, level, ratio, _ = parsed[0]
    return _perturb_binding_key(mode, level, ratio)


def _binding_key_from_path(path: str) -> str:
    stem = Path(path).stem
    match = _PERTURB_LMDB_FILENAME_RE.search(stem)
    if match is None:
        raise ValueError(
            f"Could not infer perturb recipe from filename '{stem}'. "
            "Use an explicit binding like 'geom:0.2@0.2=/path/to/file.lmdb'."
        )
    mode = str(match.group("mode")).lower()
    level_token = match.group("level")
    ratio_token = match.group("ratio")
    level = 0.0 if not level_token else float(level_token.replace("p", "."))
    ratio = float(str(ratio_token).replace("p", "."))
    return _perturb_binding_key(mode, level, ratio)


def _parse_explicit_perturb_lmdb_bindings(items, *, arg_name: str) -> dict[str, list[str]]:
    bindings: dict[str, list[str]] = {}
    for raw_item in items or ():
        item = str(raw_item).strip()
        if not item:
            continue
        if "=" in item:
            binding_token, path = item.split("=", 1)
            key = _binding_key_from_mix_token(binding_token.strip())
        else:
            path = item
            key = _binding_key_from_path(path)
        resolved = str(Path(path).resolve())
        bindings.setdefault(key, []).append(resolved)
    if bindings:
        LOGGER.info("%s explicit perturb bindings: %s", arg_name, ", ".join(f"{key} -> {len(paths)}" for key, paths in bindings.items()))
    return bindings


def _combine_datasets(datasets, *, source_label: str | None = None):
    parts = [dataset for dataset in datasets if dataset is not None]
    if not parts:
        return None
    if len(parts) == 1:
        combined = parts[0]
    else:
        combined = ConcatDataset(parts)
        try:
            combined.atom_counts = np.concatenate([dataset_atom_counts(part) for part in parts]).astype(np.int32)
        except Exception:
            pass
    if source_label:
        setattr(combined, "source_path", source_label)
    return combined


def _filter_dataset_by_atom_limit(dataset, *, args, ctx, role: str, path_label: str):
    if dataset is None:
        return None
    if len(dataset) == 0:
        LOGGER.warning("Skip empty %s dataset: %s", role, path_label)
        return None
    atom_counts = _resolve_atom_counts_for_all_ranks(dataset, args=args, ctx=ctx)
    valid_mask = (atom_counts > 0) & (atom_counts <= int(args.filter_max_atoms))
    keep_indices = np.nonzero(valid_mask)[0]
    dropped = int(len(atom_counts) - len(keep_indices))
    if len(keep_indices) == 0:
        LOGGER.warning(
            "Skip %s dataset after atom filtering: %s (filter_max_atoms=%s dropped=%s)",
            role,
            path_label,
            args.filter_max_atoms,
            dropped,
        )
        return None
    if dropped > 0:
        LOGGER.info(
            "Atom filtering kept %d / %d samples for %s dataset %s (filter_max_atoms=%s)",
            len(keep_indices),
            len(atom_counts),
            role,
            path_label,
            args.filter_max_atoms,
        )
    return IndexedSubsetDataset(dataset, keep_indices, atom_counts=atom_counts[keep_indices])


def _load_explicit_perturb_datasets(items, *, args, ctx, arg_name: str, role: str) -> dict[str, object]:
    bindings = _parse_explicit_perturb_lmdb_bindings(items, arg_name=arg_name)
    datasets: dict[str, object] = {}
    for key, paths in bindings.items():
        opened_parts = []
        for path in paths:
            dataset = create_dataset_or_none(path, 0, None, role=role)
            if dataset is None:
                raise ValueError(f"Failed to load explicit perturb LMDB for {key}: {path}")
            filtered = _filter_dataset_by_atom_limit(
                dataset,
                args=args,
                ctx=ctx,
                role=role,
                path_label=path,
            )
            if filtered is not None:
                opened_parts.append(filtered)
        combined = _combine_datasets(opened_parts, source_label=f"{role}:{key}")
        if combined is not None:
            datasets[key] = combined
            LOGGER.info("Loaded explicit perturb dataset for %s from %d path(s), len=%d", key, len(paths), len(combined))
    return datasets


def _build_sample_type_dataset(
    base_dataset,
    *,
    mode: str,
    level: float,
    seed: int,
    args,
    allow_precomputed_autodiscovery: bool = True,
    force_online_perturb: bool = False,
):
    mode = str(mode).strip().lower()
    if mode == "clean":
        return SampleTypeWrapperDataset(base_dataset, sample_type="clean")
    if allow_precomputed_autodiscovery and not force_online_perturb:
        precomputed = try_build_precomputed_recipe_dataset(base_dataset, mode=mode, level=level)
        if precomputed is not None:
            LOGGER.info("Using precomputed perturb LMDB for %s:%s", mode, level)
            return SampleTypeWrapperDataset(precomputed, sample_type=mode)
    cfg = _build_degrade_cfg(args, mode, level)
    return MaskedPerturbDataset(base_dataset, cfg, seed=seed)


def build_perturb_parts(
    base_dataset,
    mix_specs,
    seed_base: int,
    args,
    *,
    explicit_perturb_datasets: dict[str, object] | None = None,
    allow_precomputed_autodiscovery: bool = True,
):
    parts = []
    explicit_perturb_datasets = explicit_perturb_datasets or {}
    for mode, level, ratio, seed in mix_specs:
        binding_key = _perturb_binding_key(mode, level, ratio)
        explicit_base = explicit_perturb_datasets.get(binding_key)
        if explicit_base is not None:
            part_base = SampleTypeWrapperDataset(explicit_base, sample_type=mode)
            LOGGER.info("Using explicit perturb LMDB for %s (len=%d)", binding_key, len(part_base))
            parts.append(part_base)
            continue

        part_base = _build_sample_type_dataset(
            base_dataset,
            mode=mode,
            level=level,
            seed=seed_base + seed,
            args=args,
            allow_precomputed_autodiscovery=allow_precomputed_autodiscovery,
        )

        whole = int(ratio)
        frac = float(ratio) - whole
        parts.extend([part_base] * whole)
        if frac > 1e-8:
            take = max(1, int(len(base_dataset) * frac))
            parts.append(Subset(part_base, list(range(take))))
    return parts


def _view_is_disabled(spec: str | None) -> bool:
    if spec is None:
        return False
    return str(spec).strip().lower() in {"disabled", "disable", "off", "skip"}


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
    prefetch_factor: int = 4,
    persistent_workers: bool = True,
):
    generator = torch.Generator()
    generator.manual_seed(int(seed))
    kwargs = {
        "num_workers": num_workers,
        "pin_memory": pin_memory,
        "persistent_workers": bool(persistent_workers) if int(num_workers) > 0 else False,
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
        kwargs["prefetch_factor"] = max(2, int(prefetch_factor))
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
        n_experts_bond=args.expert_number_B,
        top_k_energy=args.topkE,
        top_k_charge=args.topkQ,
        top_k_geom=args.topkG,
        top_k_elem=args.topkZ,
        top_k_bond=args.topkB,
        expert_real_layers=args.expert_real_layers,
        expert_int_layers=args.expert_int_layers,
        expert_heads=args.expert_heads,
        expert_ff_mult=args.expert_ff_mult,
        bond_negative_ratio=args.bond_negative_ratio,
        graph_descriptor_names=getattr(args, "energy_desc_names", None),
        direct_linear_noexpert=bool(getattr(args, "direct_linear_noexpert", False)),
    ).to(device)
    return model, bb_cfg


def _make_split_spec(path: str, start: int | None, end: int | None, length: int) -> dict:
    return {
        "path": str(Path(path).resolve()),
        "start": int(start) if start is not None else 0,
        "end": None if end is None else int(end),
        "length": int(length),
    }


def _build_domain_parts(
    base_dataset,
    *,
    domain_id: int,
    args,
    seed_base: int,
    perturb_mix: str | None = None,
    perturb_mode: str | None = None,
    perturb_level: float | None = None,
    explicit_perturb_datasets: dict[str, object] | None = None,
    force_online_perturb: bool = False,
):
    mix_spec = getattr(args, "perturb_mix", "none") if perturb_mix is None else perturb_mix
    mode = getattr(args, "perturb_mode", "both") if perturb_mode is None else perturb_mode
    level = getattr(args, "perturb_level", 0.5) if perturb_level is None else perturb_level
    effective_explicit_perturb_datasets = {} if force_online_perturb else (explicit_perturb_datasets or {})
    allow_precomputed_autodiscovery = (not bool(effective_explicit_perturb_datasets)) and (not force_online_perturb)

    mix_token = None if mix_spec is None else str(mix_spec).strip()
    if mix_token not in (None, "", "none"):
        specs = parse_perturb_mix(mix_token, seed_base)
        parts = build_perturb_parts(
            base_dataset,
            specs,
            seed_base,
            args,
            explicit_perturb_datasets=effective_explicit_perturb_datasets,
            allow_precomputed_autodiscovery=allow_precomputed_autodiscovery,
        )
        if not parts:
            parts = [
                _build_sample_type_dataset(
                    base_dataset,
                    mode=mode,
                    level=level,
                    seed=seed_base,
                    args=args,
                    allow_precomputed_autodiscovery=allow_precomputed_autodiscovery,
                    force_online_perturb=force_online_perturb,
                )
            ]
    else:
        parts = [
            _build_sample_type_dataset(
                base_dataset,
                mode=mode,
                level=level,
                seed=seed_base,
                args=args,
                allow_precomputed_autodiscovery=allow_precomputed_autodiscovery,
                force_online_perturb=force_online_perturb,
            )
        ]
    return [DomainWrapperDataset(part, domain_id) for part in parts]


def _extend_validation_views(target_views: dict[str, list], base_dataset, *, domain_id: int, args, seed_base: int) -> None:
    target_views["main"].extend(
        _build_domain_parts(
            base_dataset,
            domain_id=domain_id,
            args=args,
            seed_base=seed_base,
            perturb_mix=args.val_perturb_mix,
            perturb_mode=args.val_perturb_mode,
            perturb_level=args.val_perturb_level,
        )
    )

    if not _view_is_disabled(getattr(args, "val_diag_perturb_mix", None)):
        target_views["diag"].extend(
            _build_domain_parts(
                base_dataset,
                domain_id=domain_id,
                args=args,
                seed_base=seed_base + 50000,
                perturb_mix=args.val_diag_perturb_mix,
                perturb_mode=args.val_diag_perturb_mode,
                perturb_level=args.val_diag_perturb_level,
            )
        )


def _stats_weight_key(key: str) -> str:
    if key in {"E", "E_desc", "R2_e"} or key.startswith("loss_energy_desc_") or key.startswith("r2_energy_desc_"):
        return "W_e"
    if key in {"Q", "Q_desc", "R2_q"} or key.startswith("loss_charge_desc_") or key.startswith("r2_charge_desc_") or key.startswith("acc_charge_desc_"):
        return "W_q"
    if key in {"Z", "R2_z", "Acc_z"}:
        return "W_z"
    if key in {"Z_desc"} or key.startswith("loss_elem_desc_") or key.startswith("acc_elem_desc_"):
        return "W_z_desc"
    if key in {"Bond_exist", "Bond_order", "Acc_bond_exist", "Acc_bond_order"}:
        return "W_bond_pairs"
    if key in {"Geom", "Geom_d", "Geom_a", "Geom_t"}:
        return "W_geom"
    return "B"


def _resolve_atom_counts_for_all_ranks(dataset, *, args, ctx):
    force_recompute = bool(getattr(args, "force_recompute_atom_counts", False))
    if not ctx.enabled:
        return resolve_atom_counts(
            dataset,
            cache_dir=args.atom_count_cache_dir,
            force_recompute=force_recompute,
        )

    if ctx.is_main_process:
        return resolve_atom_counts(
            dataset,
            cache_dir=args.atom_count_cache_dir,
            force_recompute=force_recompute,
        )

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
    explicit_train_perturb = _load_explicit_perturb_datasets(
        getattr(args, "perturb_lmdbs", ()),
        args=args,
        ctx=ctx,
        arg_name="--perturb_lmdbs",
        role="train-explicit-perturb",
    )
    explicit_val_main_perturb = _load_explicit_perturb_datasets(
        getattr(args, "val_perturb_lmdbs", ()),
        args=args,
        ctx=ctx,
        arg_name="--val_perturb_lmdbs",
        role="val-main-explicit-perturb",
    )
    explicit_val_diag_perturb = _load_explicit_perturb_datasets(
        getattr(args, "val_diag_perturb_lmdbs", ()),
        args=args,
        ctx=ctx,
        arg_name="--val_diag_perturb_lmdbs",
        role="val-diag-explicit-perturb",
    )
    legacy_train_strategy = bool(getattr(args, "old_pretraining_strategy", False))

    base_infos = []
    for domain_id, (path, start, end) in enumerate(zip(args.data_roots, starts, ends)):
        base_root = create_dataset_or_none(path, start, end, role="train")
        if base_root is None:
            continue
        base_raw = OnlyStableWrapper(base_root)
        base_filtered = _filter_dataset_by_atom_limit(
            base_raw,
            args=args,
            ctx=ctx,
            role="train-base",
            path_label=f"{path} (start={start} end={end})",
        )
        if base_filtered is None:
            continue
        base_infos.append({"domain_id": domain_id, "path": path, "start": start, "end": end, "base": base_filtered})

    if not base_infos:
        raise ValueError("No training datasets were built. Check data_roots and index ranges.")

    train_list = []
    val_views = {"main": [], "diag": []}
    std_bases = []
    train_bases: list[tuple[object, int, int]] = []
    val_bases: list[tuple[object, int, int]] = []

    if args.val_data_roots:
        for info in base_infos:
            std_bases.append(info["base"])
            train_bases.append((info["base"], info["domain_id"], args.perturb_seed + info["domain_id"] * 100000))

        for offset, (path, start, end) in enumerate(zip(args.val_data_roots, val_starts, val_ends)):
            domain_id = len(base_infos) + offset
            base_root = create_dataset_or_none(path, start, end, role="val")
            if base_root is None:
                continue
            base = OnlyStableWrapper(base_root)
            base = _filter_dataset_by_atom_limit(
                base,
                args=args,
                ctx=ctx,
                role="val-base",
                path_label=f"{path} (start={start} end={end})",
            )
            if base is None:
                continue
            val_bases.append((base, domain_id, args.perturb_seed + 1000000 + domain_id * 100000))
    else:
        split_specs = [_make_split_spec(info["path"], info["start"], info["end"], len(info["base"])) for info in base_infos]
        val_indices_by_root = _resolve_random_val_split_for_all_ranks(split_specs, args=args, ctx=ctx)

        for info, val_indices in zip(base_infos, val_indices_by_root):
            base_raw = info["base"]
            domain_id = info["domain_id"]
            val_indices = sorted({int(i) for i in val_indices})

            train_base = ExcludingSubsetDataset(base_raw, val_indices) if val_indices else base_raw
            std_bases.append(train_base)
            train_bases.append((train_base, domain_id, args.perturb_seed + domain_id * 100000))

            if val_indices:
                val_base = IndexedSubsetDataset(base_raw, val_indices)
                if len(val_base) > 0:
                    val_bases.append((val_base, domain_id, args.perturb_seed + 1000000 + domain_id * 100000))

    if explicit_train_perturb and legacy_train_strategy and ctx.is_main_process:
        LOGGER.info("Ignoring explicit train perturb LMDB bindings because --old_pretraining_strategy forces online perturb generation during training.")

    if explicit_train_perturb and not legacy_train_strategy:
        if not args.val_data_roots and int(getattr(args, "random_val_size", 0)) > 0:
            LOGGER.warning(
                "Using explicit train perturb LMDBs together with a random train/val split. "
                "If those LMDBs were built from the full dataset, they may include validation samples."
            )
        train_union = _combine_datasets([dataset for dataset, _, _ in train_bases], source_label="train-union-base")
        if train_union is None:
            raise ValueError("No train base datasets available for explicit perturb LMDB composition.")
        train_list.extend(
            _build_domain_parts(
                train_union,
                domain_id=0,
                args=args,
                seed_base=args.perturb_seed,
                explicit_perturb_datasets=explicit_train_perturb,
            )
        )
    else:
        for dataset, domain_id, seed_base in train_bases:
            train_list.extend(
                _build_domain_parts(
                    dataset,
                    domain_id=domain_id,
                    args=args,
                    seed_base=seed_base,
                    force_online_perturb=legacy_train_strategy,
                )
            )

    val_union = None
    if explicit_val_main_perturb or explicit_val_diag_perturb:
        val_union = _combine_datasets([dataset for dataset, _, _ in val_bases], source_label="val-union-base")
        if val_union is None:
            LOGGER.warning("Explicit validation perturb LMDBs were provided, but no validation base dataset was built.")

    if explicit_val_main_perturb and val_union is not None:
        val_views["main"].extend(
            _build_domain_parts(
                val_union,
                domain_id=0,
                args=args,
                seed_base=args.perturb_seed + 1000000,
                perturb_mix=args.val_perturb_mix,
                perturb_mode=args.val_perturb_mode,
                perturb_level=args.val_perturb_level,
                explicit_perturb_datasets=explicit_val_main_perturb,
            )
        )
    else:
        for dataset, domain_id, seed_base in val_bases:
            val_views["main"].extend(
                _build_domain_parts(
                    dataset,
                    domain_id=domain_id,
                    args=args,
                    seed_base=seed_base,
                    perturb_mix=args.val_perturb_mix,
                    perturb_mode=args.val_perturb_mode,
                    perturb_level=args.val_perturb_level,
                )
            )

    if not _view_is_disabled(getattr(args, "val_diag_perturb_mix", None)):
        if explicit_val_diag_perturb and val_union is not None:
            val_views["diag"].extend(
                _build_domain_parts(
                    val_union,
                    domain_id=0,
                    args=args,
                    seed_base=args.perturb_seed + 1050000,
                    perturb_mix=args.val_diag_perturb_mix,
                    perturb_mode=args.val_diag_perturb_mode,
                    perturb_level=args.val_diag_perturb_level,
                    explicit_perturb_datasets=explicit_val_diag_perturb,
                )
            )
        else:
            for dataset, domain_id, seed_base in val_bases:
                val_views["diag"].extend(
                    _build_domain_parts(
                        dataset,
                        domain_id=domain_id,
                        args=args,
                        seed_base=seed_base + 50000,
                        perturb_mix=args.val_diag_perturb_mix,
                        perturb_mode=args.val_diag_perturb_mode,
                        perturb_level=args.val_diag_perturb_level,
                    )
                )

    train_ds = ConcatDataset(train_list)
    val_datasets = {
        name: (ConcatDataset(parts) if parts else None)
        for name, parts in val_views.items()
    }
    return train_ds, val_datasets, std_bases


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
        elif key.startswith("N_"):
            merged[key] = int(accum.get(key, 0)) + int(stats.get(key, 0))
        elif key.startswith("T_"):
            merged[key] = float(accum.get(key, 0.0)) + float(stats.get(key, 0.0))
    for key in set(accum) | set(stats):
        if (
            key in {"B", "bad", "global_step", "optimizer_steps", "completed_pass"}
            or key.startswith("W_")
            or key.startswith("N_")
            or key.startswith("T_")
        ):
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


def _descriptor_ramp(args, global_step: int) -> float:
    if int(global_step) < int(args.stage1_max_steps):
        return 0.0
    ramp_steps = int(getattr(args, "stage2_descriptor_ramp_steps", 0))
    if ramp_steps <= 0:
        return 1.0
    progress = (int(global_step) - int(args.stage1_max_steps)) / max(1, ramp_steps)
    return float(min(1.0, max(0.0, progress)))


def _train_geom_lambdas(args, stage: int) -> tuple[float, float, float]:
    if int(stage) <= 0:
        return float(args.lambda_dist), 0.0, 0.0
    return float(args.lambda_dist), float(args.lambda_angle), float(args.lambda_torsion)


def _validation_geom_lambdas(args, stage: int) -> tuple[float, float, float]:
    return _train_geom_lambdas(args, stage)


def _requires_dynamic_ddp(args) -> bool:
    descriptor_enabled = any(
        float(getattr(args, name, 0.0)) > 0.0
        for name in ("lambda_e_desc", "lambda_q_desc", "lambda_z_desc")
    )
    descriptor_staged = (
        int(getattr(args, "stage1_max_steps", 0)) > 0
        or int(getattr(args, "stage2_descriptor_ramp_steps", 0)) > 0
    )
    bond_enabled = any(
        float(getattr(args, name, 0.0)) > 0.0
        for name in ("lambda_bond_exist", "lambda_bond_order")
    )
    return bool(descriptor_enabled or descriptor_staged or bond_enabled)


def _normalize_ddp_args(args, *, distributed_enabled: bool) -> None:
    if not distributed_enabled:
        return
    if not _requires_dynamic_ddp(args):
        return

    if bool(getattr(args, "ddp_static_graph", False)):
        LOGGER.warning(
            "Disabling DDP static_graph because staged descriptors / bond supervision make parameter usage vary across iterations."
        )
        args.ddp_static_graph = False

    if not bool(getattr(args, "find_unused_parameters", False)):
        LOGGER.warning(
            "Enabling DDP find_unused_parameters because staged descriptors / bond supervision can leave some heads unused on a given batch."
        )
        args.find_unused_parameters = True


def _ddp_runtime_mode(args, global_step: int) -> str:
    if not bool(getattr(args, "ddp_enable_stage_fastpath", True)):
        return "dynamic"
    if _descriptor_supervision_active(args, global_step):
        return "stage2_static"
    return "stage1_static"


def _ddp_runtime_cfg(args, *, global_step: int) -> dict[str, bool | str]:
    mode = _ddp_runtime_mode(args, global_step)
    fast_path = mode != "dynamic"
    return {
        "mode": mode,
        "fast_path": fast_path,
        "find_unused_parameters": bool(getattr(args, "find_unused_parameters", False)) and not fast_path,
        "static_graph": bool(getattr(args, "ddp_static_graph", False)) or fast_path,
    }


def _wrap_train_model(model, ctx, args, *, global_step: int):
    runtime_cfg = _ddp_runtime_cfg(args, global_step=global_step)
    wrapped = wrap_ddp(
        model,
        ctx,
        find_unused_parameters=runtime_cfg["find_unused_parameters"],
        broadcast_buffers=args.ddp_broadcast_buffers,
        static_graph=runtime_cfg["static_graph"],
    )
    return wrapped, runtime_cfg


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
    env_fingerprint: dict | None = None,
    legacy_stage_epoch: int | None = None,
):
    save_epoch, save_epoch_step = _normalize_position(current_epoch, epoch_step, steps_per_epoch)
    optimizer_summary = None
    if optimizer is not None:
        optimizer_summary = {
            "param_groups": [
                {
                    "lr": float(group.get("lr", 0.0)),
                    "weight_decay": float(group.get("weight_decay", 0.0)),
                    "betas": list(group.get("betas", ())) if "betas" in group else None,
                    "eps": float(group.get("eps", 0.0)) if "eps" in group else None,
                }
                for group in optimizer.param_groups
            ],
        }
    scheduler_summary = None
    if scheduler is not None:
        scheduler_summary = {
            "type": type(scheduler).__name__,
            "last_epoch": int(getattr(scheduler, "last_epoch", -1)),
            "state_dict_keys": sorted(scheduler.state_dict().keys()),
        }
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
        metadata={
            "hostname": socket.gethostname(),
            "save_path": str(Path(save_path).resolve()),
            "save_epoch": int(save_epoch),
            "save_epoch_step": int(save_epoch_step),
            "global_step": int(global_step),
            "current_stage": int(current_stage),
            "stage_step": int(stage_step),
            "seed": int(getattr(args, "seed", 0)),
            "amp_dtype": str(getattr(args, "amp_dtype", "none")),
            "num_workers": int(getattr(args, "num_workers", 0)),
            "val_num_workers": int(getattr(args, "val_num_workers", 0)),
            "fixed_train_order": int(bool(getattr(args, "fixed_train_order", False))),
            "deterministic_algorithms": int(bool(getattr(args, "deterministic_algorithms", False))),
            "cudnn_deterministic": int(bool(getattr(args, "cudnn_deterministic", False))),
            "disable_cudnn_benchmark": int(bool(getattr(args, "disable_cudnn_benchmark", False))),
            "disable_tf32": int(bool(getattr(args, "disable_tf32", False))),
            "float32_matmul_precision": getattr(args, "float32_matmul_precision", None),
            "grad_clip_norm": float(getattr(args, "grad_clip_norm", 0.0)),
            "optimizer_summary": optimizer_summary,
            "scheduler_summary": scheduler_summary,
            "environment": env_fingerprint or {},
            "is_ema": False,
            "legacy_stage_epoch": (None if legacy_stage_epoch is None else int(legacy_stage_epoch)),
        },
    )


def _prune_archive_checkpoints(archive_dir: str, keep_last_k: int) -> None:
    keep_last_k = int(keep_last_k)
    if keep_last_k <= 0:
        return

    archive_root = Path(archive_dir).resolve()
    checkpoint_paths = sorted(archive_root.glob("step_*.pt"))
    if len(checkpoint_paths) <= keep_last_k:
        return

    for stale_path in checkpoint_paths[:-keep_last_k]:
        if stale_path.parent != archive_root:
            continue
        stale_path.unlink(missing_ok=True)
        sidecar_path = Path(str(stale_path) + ".meta.json")
        sidecar_path.unlink(missing_ok=True)


def _hash_indices(indices) -> str:
    text = ",".join(str(int(index)) for index in indices)
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]


def _preview_train_batches(
    *,
    dataset_size: int,
    batch_size: int,
    atom_counts,
    batch_sampler,
    sampler,
    shuffle: bool,
    seed: int,
    max_batches: int,
) -> list[dict[str, object]]:
    preview_batches = max(0, int(max_batches))
    if preview_batches <= 0:
        return []

    batches: list[list[int]] = []
    if batch_sampler is not None:
        iterator = iter(batch_sampler)
        for _ in range(preview_batches):
            try:
                batches.append([int(index) for index in next(iterator)])
            except StopIteration:
                break
    else:
        if sampler is not None:
            indices = [int(index) for index in sampler]
        elif shuffle:
            generator = torch.Generator()
            generator.manual_seed(int(seed))
            indices = torch.randperm(int(dataset_size), generator=generator).tolist()
        else:
            indices = list(range(int(dataset_size)))
        for start in range(0, len(indices), int(batch_size)):
            if len(batches) >= preview_batches:
                break
            batches.append(indices[start : start + int(batch_size)])

    atom_counts_array = np.asarray(atom_counts, dtype=np.int32)
    preview = []
    for batch_index, batch_indices in enumerate(batches):
        batch_atom_counts = atom_counts_array[np.asarray(batch_indices, dtype=np.int64)] if batch_indices else np.zeros(0, dtype=np.int32)
        preview.append(
            {
                "batch_index": int(batch_index),
                "hash": _hash_indices(batch_indices),
                "size": int(len(batch_indices)),
                "atom_total": int(batch_atom_counts.sum()) if batch_atom_counts.size else 0,
                "atom_min": int(batch_atom_counts.min()) if batch_atom_counts.size else 0,
                "atom_max": int(batch_atom_counts.max()) if batch_atom_counts.size else 0,
                "first_indices": [int(index) for index in batch_indices[:8]],
            }
        )
    return preview


def _write_stability_summary(path: str | Path, payload: dict) -> None:
    write_json(path, sanitize_for_json(payload))


def _run_validation(
    train_model,
    val_loader,
    *,
    args,
    device,
    std,
    global_step,
    current_epoch,
    current_stage,
    ctx,
    dataloader_debug,
    ddp_debug,
    desc_prefix: str,
):
    val_lam_d, val_lam_a, val_lam_t = _validation_geom_lambdas(args, current_stage)
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
        lam_bond_exist=args.lambda_bond_exist,
        lam_bond_order=args.lambda_bond_order,
        z_label_smooth=args.z_label_smooth,
        z_focal_gamma=args.z_focal_gamma,
        z_temp=args.z_temp,
        z_class_balance=args.z_class_balance,
        z_entropy_reg=args.z_entropy_reg,
        z_logit_l2=args.z_logit_l2,
        morse_d=args.morse_D,
        morse_a=args.morse_a,
        stage1_max_steps=args.stage1_max_steps,
        stage2_descriptor_ramp_steps=args.stage2_descriptor_ramp_steps,
        stage1_signal_decay_steps=args.stage1_signal_decay_steps,
        stage1_signal_floor=args.stage1_signal_floor,
        optim=None,
        amp_dtype=args.amp_dtype,
        old_pretraining_strategy=False,
        grad_clip_norm=float(getattr(args, "grad_clip_norm", 0.0)),
        desc=f"{desc_prefix}@{global_step}",
        scheduler=None,
        global_step_start=global_step,
        is_main_process=ctx.is_main_process,
        distributed_sync=ctx.enabled,
        dataloader_debug=dataloader_debug,
        ddp_debug=ddp_debug,
        current_epoch=current_epoch,
        current_stage=current_stage,
        progress_mininterval=float(getattr(args, "tqdm_mininterval", 10.0)),
        progress_miniters=int(getattr(args, "tqdm_miniters", 100)),
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


def _log_validation_view(
    *,
    run,
    train_model,
    stats,
    summary,
    epoch: int,
    global_step: int,
    prefix: str,
    label: str,
    args,
) -> None:
    _print_metrics(label, stats)
    descriptor_logging_enabled = _descriptor_logging_enabled(args, payload=summary)
    payload = _prepare_wandb_payload(
        args,
        {**dict(summary), **_pooling_weight_metrics(train_model)},
        global_step=global_step,
        descriptor_logging_enabled=descriptor_logging_enabled,
    )
    log_metrics(run, prefix, payload, epoch=epoch, global_step=global_step)
    update_summary(
        run,
        _prepare_wandb_payload(
            args,
            _pooling_weight_metrics(train_model),
            global_step=global_step,
            descriptor_logging_enabled=descriptor_logging_enabled,
        ),
    )


def main() -> None:
    args = get_args()
    _enforce_runtime_policy(args)

    ctx = init_distributed(args)
    if not ctx.is_main_process:
        LOGGER.setLevel(logging.WARNING)
    _normalize_ddp_args(args, distributed_enabled=ctx.enabled)

    runtime_stability = apply_runtime_stability_settings(
        seed=args.seed + ctx.rank,
        deterministic_algorithms=bool(getattr(args, "deterministic_algorithms", False)),
        cudnn_deterministic=bool(getattr(args, "cudnn_deterministic", False)),
        disable_cudnn_benchmark=bool(getattr(args, "disable_cudnn_benchmark", False)),
        disable_tf32=bool(getattr(args, "disable_tf32", False)),
        float32_matmul_precision=getattr(args, "float32_matmul_precision", None),
    )
    device = ctx.device
    pin_memory = device.type == "cuda"
    if device.type != "cuda" and args.amp_dtype != "none":
        LOGGER.warning("AMP dtype %s requested on non-CUDA device; forcing amp_dtype=none.", args.amp_dtype)
        args.amp_dtype = "none"
    if bool(getattr(args, "deterministic_algorithms", False)) and not bool(getattr(args, "disable_cudnn_benchmark", False)):
        LOGGER.warning(
            "deterministic_algorithms is enabled while disable_cudnn_benchmark is false. "
            "For the most stable CUDA runs, also disable cuDNN benchmark."
        )

    env_fingerprint = collect_environment_fingerprint(
        device=device,
        world_size=ctx.world_size,
        rank=ctx.rank,
        local_rank=ctx.local_rank,
        num_workers=args.num_workers,
        val_num_workers=args.val_num_workers,
    )

    if ctx.is_main_process:
        LOGGER.info(
            "Launch context: distributed=%s backend=%s world_size=%d rank=%d local_rank=%d device=%s ddp_static_graph=%s find_unused_parameters=%s ddp_final_barrier=%s",
            ctx.enabled,
            ctx.backend,
            ctx.world_size,
            ctx.rank,
            ctx.local_rank,
            device,
            bool(args.ddp_static_graph),
            bool(args.find_unused_parameters),
            bool(getattr(args, "ddp_final_barrier", False)),
        )
        LOGGER.info("Runtime stability: %s", sanitize_for_json(runtime_stability))
        LOGGER.info("Environment fingerprint: %s", sanitize_for_json(env_fingerprint))

    checkpoint_paths = resolve_checkpoint_paths(args.save_path, args.checkpoint_dir)
    if ctx.is_main_process:
        write_json(Path(checkpoint_paths["root_dir"]) / "environment_fingerprint.json", env_fingerprint)
        write_json(Path(checkpoint_paths["root_dir"]) / "runtime_stability.json", runtime_stability)
    if not args.atom_count_cache_dir:
        args.atom_count_cache_dir = str(Path(checkpoint_paths["root_dir"]) / "atom_count_cache")
    if int(getattr(args, "timing_log_every", 0)) > 0 and not getattr(args, "timing_log_dir", None):
        args.timing_log_dir = str(Path(checkpoint_paths["root_dir"]) / "timing")
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
    timing_logger = StepTimingLogger(
        getattr(args, "timing_log_dir", None),
        rank=ctx.rank,
        local_rank=ctx.local_rank,
        world_size=ctx.world_size,
        enabled=int(getattr(args, "timing_log_every", 0)) > 0,
        interval=int(getattr(args, "timing_log_every", 0)),
        sync_cuda=bool(getattr(args, "timing_sync_cuda", False)),
        collect_rank_skew=bool(getattr(args, "timing_collect_rank_skew", False)),
    )
    if ctx.is_main_process and timing_logger.enabled:
        LOGGER.info(
            "Step timing trace enabled: log_dir=%s interval=%s sync_cuda=%s collect_rank_skew=%s",
            getattr(args, "timing_log_dir", None),
            int(getattr(args, "timing_log_every", 0)),
            bool(getattr(args, "timing_sync_cuda", False)),
            bool(getattr(args, "timing_collect_rank_skew", False)),
        )

    train_ds, val_datasets, std_bases = _build_train_val_datasets(args, ctx)
    train_sampler = None
    train_batch_sampler = None
    train_atom_counts = dataset_atom_counts(train_ds)
    train_atom_budget_per_batch = 0 if bool(getattr(args, "old_pretraining_strategy", False)) else int(args.atom_budget_per_batch)
    train_shuffle = not bool(getattr(args, "fixed_train_order", False))
    if train_atom_budget_per_batch > 0:
        train_batch_sampler = DistributedAtomBudgetBatchSampler(
            train_atom_counts,
            max_atoms_per_batch=train_atom_budget_per_batch,
            max_samples_per_batch=args.batch_size,
            num_replicas=ctx.world_size if ctx.enabled else 1,
            rank=ctx.rank if ctx.enabled else 0,
            shuffle=train_shuffle,
            seed=args.seed,
            drop_last=False,
        )
    elif ctx.enabled:
        train_sampler = DistributedSampler(
            train_ds,
            num_replicas=ctx.world_size,
            rank=ctx.rank,
            shuffle=train_shuffle,
            drop_last=False,
            seed=args.seed,
        )
    train_loader = build_dataloader(
        train_ds,
        batch_size=args.batch_size,
        num_workers=args.num_workers,
        shuffle=train_sampler is None and train_batch_sampler is None and train_shuffle,
        sampler=train_sampler,
        batch_sampler=train_batch_sampler,
        pin_memory=pin_memory,
        seed=args.seed + ctx.rank,
        timeout_s=args.dataloader_timeout,
        prefetch_factor=args.dataloader_prefetch_factor,
        persistent_workers=args.dataloader_persistent_workers,
    )
    batch_order_preview = _preview_train_batches(
        dataset_size=len(train_ds),
        batch_size=args.batch_size,
        atom_counts=train_atom_counts,
        batch_sampler=train_batch_sampler,
        sampler=train_sampler,
        shuffle=train_sampler is None and train_batch_sampler is None and train_shuffle,
        seed=args.seed + ctx.rank,
        max_batches=args.batch_order_preview_batches,
    )
    if ctx.is_main_process:
        LOGGER.info(
            "Dataset build: train=%d val_main=%d val_diag=%d filter_max_atoms=%d atom_budget_per_batch=%d max_samples_per_batch=%d val_batch_size=%d val_atom_budget_per_batch=%d num_workers=%d prefetch_factor=%d persistent_workers=%s fixed_train_order=%s",
            len(train_ds),
            len(val_datasets.get("main")) if val_datasets.get("main") is not None else 0,
            len(val_datasets.get("diag")) if val_datasets.get("diag") is not None else 0,
            int(args.filter_max_atoms),
            int(train_atom_budget_per_batch),
            int(args.batch_size),
            int(args.val_batch_size),
            int(args.val_atom_budget_per_batch),
            int(args.num_workers),
            int(args.dataloader_prefetch_factor),
            bool(args.dataloader_persistent_workers),
            bool(args.fixed_train_order),
        )
        if batch_order_preview:
            LOGGER.info("Train batch order preview: %s", sanitize_for_json(batch_order_preview))
        LOGGER.info(
            "Validation views: main(mix=%s mode=%s level=%s) diag(mix=%s mode=%s level=%s)",
            args.val_perturb_mix,
            args.val_perturb_mode,
            args.val_perturb_level,
            args.val_diag_perturb_mix,
            args.val_diag_perturb_mode,
            args.val_diag_perturb_level,
        )
    val_loaders = {}
    for view_offset, (view_name, val_ds) in enumerate(val_datasets.items()):
        if val_ds is None:
            continue
        val_sampler = None
        val_batch_sampler = None
        if ctx.enabled:
            val_sampler = DistributedEvalSampler(val_ds, num_replicas=ctx.world_size, rank=ctx.rank)
        if int(args.val_atom_budget_per_batch) > 0:
            val_atom_counts = dataset_atom_counts(val_ds)
            val_batch_sampler = DistributedEvalAtomBudgetBatchSampler(
                val_atom_counts,
                max_atoms_per_batch=args.val_atom_budget_per_batch,
                max_samples_per_batch=args.val_batch_size,
                num_replicas=ctx.world_size if ctx.enabled else 1,
                rank=ctx.rank if ctx.enabled else 0,
            )
            val_sampler = None

        val_loaders[view_name] = build_dataloader(
            val_ds,
            batch_size=args.val_batch_size,
            num_workers=args.val_num_workers,
            shuffle=False,
            sampler=val_sampler,
            batch_sampler=val_batch_sampler,
            pin_memory=pin_memory,
            seed=args.seed + 1000 + view_offset * 100 + ctx.rank,
            timeout_s=args.dataloader_timeout,
            prefetch_factor=args.dataloader_prefetch_factor,
            persistent_workers=args.dataloader_persistent_workers,
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
    _apply_resume_model_overrides(args, resume_payload)

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

    scaler = build_grad_scaler(device, args.amp_dtype)

    legacy_train_strategy = bool(getattr(args, "old_pretraining_strategy", False))
    global_step = int(resume_payload.get("global_step", 0)) if resume_payload else 0
    current_epoch = int(resume_payload.get("current_epoch", 1)) if resume_payload else 1
    epoch_step = int(resume_payload.get("epoch_step", 0)) if resume_payload else 0
    if resume_payload is not None:
        current_stage = int(resume_payload.get("current_stage", 0))
    elif legacy_train_strategy:
        current_stage = 0
    else:
        current_stage = _current_stage(args, global_step)
    stage_step = int(resume_payload.get("stage_step", 0)) if resume_payload else 0
    best_selection_loss = float(resume_payload.get("best_selection_loss", float("inf"))) if resume_payload else float("inf")
    resume_metadata = resume_payload.get("metadata", {}) if resume_payload else {}
    legacy_stage_epoch = int(resume_metadata.get("legacy_stage_epoch", 0) or 0) if legacy_train_strategy else 0
    train_model, ddp_runtime_cfg = _wrap_train_model(model, ctx, args, global_step=global_step)
    if ctx.is_main_process and ctx.enabled:
        LOGGER.info(
            "DDP runtime config: mode=%s fast_path=%s find_unused_parameters=%s static_graph=%s at global_step=%d",
            ddp_runtime_cfg["mode"],
            bool(ddp_runtime_cfg["fast_path"]),
            bool(ddp_runtime_cfg["find_unused_parameters"]),
            bool(ddp_runtime_cfg["static_graph"]),
            global_step,
        )

    if current_epoch > args.epochs and global_step >= total_steps:
        if ctx.is_main_process:
            LOGGER.info("Checkpoint already represents a completed run; nothing to do.")
        cleanup_distributed()
        return

    run = None
    val_main_size = len(val_datasets.get("main")) if val_datasets.get("main") is not None else 0
    val_diag_size = len(val_datasets.get("diag")) if val_datasets.get("diag") is not None else 0
    if ctx.is_main_process:
        LOGGER.info(
            "Energy descriptor selector resolved to %d head(s): %s",
            len(getattr(args, "energy_desc_names", ())),
            ", ".join(getattr(args, "energy_desc_names", ())) if getattr(args, "energy_desc_names", ()) else "<none>",
        )
        run = init_wandb_run(
            args,
            model=model,
            device=str(device),
            train_size=len(train_ds),
            val_size=val_main_size,
        )
        update_summary(
            run,
            _prepare_wandb_payload(
                args,
                {
                "meta/device": str(device),
                "meta/train_size": len(train_ds),
                "meta/val_size": val_main_size,
                "meta/val_size_main": val_main_size,
                "meta/val_size_diag": val_diag_size,
                "meta/val_main_perturb_mix": args.val_perturb_mix,
                "meta/val_main_perturb_mode": args.val_perturb_mode,
                "meta/val_main_perturb_level": float(args.val_perturb_level),
                "meta/val_diag_perturb_mix": args.val_diag_perturb_mix,
                "meta/val_diag_perturb_mode": args.val_diag_perturb_mode,
                "meta/val_diag_perturb_level": float(args.val_diag_perturb_level),
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
                "meta/energy_desc_count": len(getattr(args, "energy_desc_names", ())),
                "meta/energy_desc_names": ",".join(getattr(args, "energy_desc_names", ())),
                "meta/dataloader_debug": int(dataloader_debug.enabled),
                "meta/dataloader_debug_dir": dataloader_debug.log_dir or "",
                "meta/dataloader_timeout_s": dataloader_debug.timeout_s,
                "meta/ddp_debug": int(ddp_debug.enabled),
                "meta/ddp_debug_dir": ddp_debug.log_dir or "",
                "meta/ddp_debug_interval_s": ddp_debug.interval_s,
                "meta/ddp_debug_stall_threshold_s": ddp_debug.stall_threshold_s,
                "meta/ddp_runtime_mode": ddp_runtime_cfg["mode"],
                "meta/ddp_find_unused_parameters": int(ddp_runtime_cfg["find_unused_parameters"]),
                "meta/ddp_static_graph_active": int(ddp_runtime_cfg["static_graph"]),
                "meta/ddp_stage_fastpath_enabled": int(bool(args.ddp_enable_stage_fastpath)),
                "meta/filter_max_atoms": int(args.filter_max_atoms),
                "meta/old_pretraining_strategy": int(bool(getattr(args, "old_pretraining_strategy", False))),
                "meta/atom_budget_per_batch": int(train_atom_budget_per_batch),
                "meta/val_batch_size": int(args.val_batch_size),
                "meta/val_atom_budget_per_batch": int(args.val_atom_budget_per_batch),
                "meta/fixed_train_order": int(bool(getattr(args, "fixed_train_order", False))),
                "meta/grad_clip_norm": float(getattr(args, "grad_clip_norm", 0.0)),
                "meta/deterministic_algorithms": int(bool(getattr(args, "deterministic_algorithms", False))),
                "meta/cudnn_deterministic": int(bool(getattr(args, "cudnn_deterministic", False))),
                "meta/disable_cudnn_benchmark": int(bool(getattr(args, "disable_cudnn_benchmark", False))),
                "meta/disable_tf32": int(bool(getattr(args, "disable_tf32", False))),
                "meta/float32_matmul_precision": getattr(args, "float32_matmul_precision", None) or "",
                "meta/atom_count_cache_dir": args.atom_count_cache_dir or "",
                "meta/dataloader_prefetch_factor": int(args.dataloader_prefetch_factor),
                "meta/dataloader_persistent_workers": int(bool(args.dataloader_persistent_workers)),
                "meta/batch_order_preview_batches": int(getattr(args, "batch_order_preview_batches", 0)),
                "meta/save_after_step": int(getattr(args, "save_after_step", 0)),
                "meta/save_last_k_checkpoints": int(getattr(args, "save_last_k_checkpoints", 0)),
                "meta/environment_hostname": env_fingerprint.get("hostname", ""),
                "meta/environment_gpu_names": ",".join(env_fingerprint.get("gpu_names", ())),
                "meta/timing_log_dir": args.timing_log_dir or "",
                "meta/timing_log_every": int(getattr(args, "timing_log_every", 0)),
                "meta/timing_sync_cuda": int(bool(getattr(args, "timing_sync_cuda", False))),
                "meta/timing_collect_rank_skew": int(bool(getattr(args, "timing_collect_rank_skew", False))),
                **_pooling_weight_metrics(model),
                },
                global_step=global_step,
            ),
        )
        if batch_order_preview:
            write_json(Path(checkpoint_paths["root_dir"]) / "batch_order_preview.json", batch_order_preview)

    def log_train_batch(batch_metrics, step):
        payload = _prepare_wandb_payload(
            args,
            {**dict(batch_metrics), **_pooling_weight_metrics(train_model)},
            global_step=step,
        )
        log_metrics(run, "train/batch", payload, global_step=step)

    last_validation_step = -1

    def run_validation_views(*, epoch_for_log: int, global_step_for_log: int, current_stage_for_log: int, epoch_step_for_log: int, stage_step_for_log: int) -> None:
        nonlocal best_selection_loss, last_validation_step

        if not val_loaders or global_step_for_log <= 0:
            return

        last_validation_step = global_step_for_log
        main_selection = None

        main_loader = val_loaders.get("main")
        if main_loader is not None:
            val_stats, _, val_selection, val_summary = _run_validation(
                train_model,
                main_loader,
                args=args,
                device=device,
                std=std,
                global_step=global_step_for_log,
                current_epoch=epoch_for_log,
                current_stage=current_stage_for_log,
                ctx=ctx,
                dataloader_debug=dataloader_debug,
                ddp_debug=ddp_debug,
                desc_prefix="Val(main)",
            )
            main_selection = val_selection
            if ctx.is_main_process:
                _log_validation_view(
                    run=run,
                    train_model=train_model,
                    stats=val_stats,
                    summary=val_summary,
                    epoch=epoch_for_log,
                    global_step=global_step_for_log,
                    prefix="val",
                    label="Val(main)",
                    args=args,
                )

        diag_loader = val_loaders.get("diag")
        if diag_loader is not None:
            diag_stats, _, _, diag_summary = _run_validation(
                train_model,
                diag_loader,
                args=args,
                device=device,
                std=std,
                global_step=global_step_for_log,
                current_epoch=epoch_for_log,
                current_stage=current_stage_for_log,
                ctx=ctx,
                dataloader_debug=dataloader_debug,
                ddp_debug=ddp_debug,
                desc_prefix="Val(diag)",
            )
            if ctx.is_main_process:
                _log_validation_view(
                    run=run,
                    train_model=train_model,
                    stats=diag_stats,
                    summary=diag_summary,
                    epoch=epoch_for_log,
                    global_step=global_step_for_log,
                    prefix="val_diag",
                    label="Val(diag)",
                    args=args,
                )

        if ctx.is_main_process and main_selection is not None and main_selection < best_selection_loss:
            best_selection_loss = main_selection
            _save_runtime_checkpoint(
                model=model,
                model_cfg=model_cfg,
                std=std,
                args=args,
                optimizer=optimizer,
                scheduler=scheduler,
                save_path=checkpoint_paths["best_path"],
                current_epoch=epoch_for_log,
                epoch_step=epoch_step_for_log,
                steps_per_epoch=steps_per_epoch,
                global_step=global_step_for_log,
                current_stage=current_stage_for_log,
                stage_step=stage_step_for_log,
                best_selection_loss=best_selection_loss,
                checkpoint_kind="best",
                env_fingerprint=env_fingerprint,
                legacy_stage_epoch=legacy_stage_epoch,
            )
            update_summary(
                run,
                {
                    "best/global_step": global_step_for_log,
                    "best/epoch": epoch_for_log,
                    "best/stage": current_stage_for_log,
                    "best/selection_loss": best_selection_loss,
                    "best/path": checkpoint_paths["best_path"],
                },
            )
            if args.wandb_log_checkpoints:
                log_checkpoint_artifact(
                    run,
                    checkpoint_paths["best_path"],
                    label="best",
                    aliases=["best", f"step_{global_step_for_log:08d}"],
                    metadata={"global_step": global_step_for_log, "epoch": epoch_for_log, "stage": current_stage_for_log},
                )

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
                if not legacy_train_strategy:
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
                if (not legacy_train_strategy) and current_stage == 0 and global_step < args.stage1_max_steps:
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
                    lam_bond_exist=args.lambda_bond_exist,
                    lam_bond_order=args.lambda_bond_order,
                    z_label_smooth=args.z_label_smooth,
                    z_focal_gamma=args.z_focal_gamma,
                    z_temp=args.z_temp,
                    z_class_balance=args.z_class_balance,
                    z_entropy_reg=args.z_entropy_reg,
                    z_logit_l2=args.z_logit_l2,
                    morse_d=args.morse_D,
                    morse_a=args.morse_a,
                    stage1_max_steps=args.stage1_max_steps,
                    stage2_descriptor_ramp_steps=args.stage2_descriptor_ramp_steps,
                    stage1_signal_decay_steps=args.stage1_signal_decay_steps,
                    stage1_signal_floor=args.stage1_signal_floor,
                    optim=optimizer,
                    amp_dtype=args.amp_dtype,
                    old_pretraining_strategy=bool(getattr(args, "old_pretraining_strategy", False)),
                    grad_clip_norm=float(getattr(args, "grad_clip_norm", 0.0)),
                    desc=f"Train@{global_step}",
                    scheduler=scheduler,
                    batch_logger=log_train_batch if run is not None else None,
                    step_timing_logger=timing_logger if timing_logger.enabled else None,
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
                    progress_mininterval=float(getattr(args, "tqdm_mininterval", 10.0)),
                    progress_miniters=int(getattr(args, "tqdm_miniters", 100)),
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
                    train_window_metrics = _prepare_wandb_payload(
                        args,
                        {**train_window_metrics, **_pooling_weight_metrics(train_model)},
                        global_step=global_step,
                    )
                    log_metrics(
                        run,
                        "train/window",
                        train_window_metrics,
                        epoch=epoch,
                        global_step=global_step,
                    )

                next_ddp_runtime_cfg = _ddp_runtime_cfg(args, global_step=global_step)
                ddp_rewrapped = next_ddp_runtime_cfg != ddp_runtime_cfg
                if ddp_rewrapped:
                    if ctx.enabled:
                        barrier()
                    train_model, ddp_runtime_cfg = _wrap_train_model(model, ctx, args, global_step=global_step)
                    if ctx.enabled:
                        barrier()
                    if ctx.is_main_process:
                        LOGGER.info(
                            "DDP runtime rewrap: mode=%s fast_path=%s find_unused_parameters=%s static_graph=%s at global_step=%d",
                            ddp_runtime_cfg["mode"],
                            bool(ddp_runtime_cfg["fast_path"]),
                            bool(ddp_runtime_cfg["find_unused_parameters"]),
                            bool(ddp_runtime_cfg["static_graph"]),
                            global_step,
                        )
                        log_metrics(
                            run,
                            "meta",
                            {
                                "ddp_runtime_mode": ddp_runtime_cfg["mode"],
                                "ddp_fast_path_active": int(bool(ddp_runtime_cfg["fast_path"])),
                                "ddp_find_unused_parameters": int(bool(ddp_runtime_cfg["find_unused_parameters"])),
                                "ddp_static_graph_active": int(bool(ddp_runtime_cfg["static_graph"])),
                            },
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
                            {
                                "stage_transition": 1,
                                "stage_to": current_stage,
                                "ddp_fast_path_active": int(bool(ddp_runtime_cfg["fast_path"])),
                                "ddp_find_unused_parameters": int(bool(ddp_runtime_cfg["find_unused_parameters"])),
                                "ddp_static_graph_active": int(bool(ddp_runtime_cfg["static_graph"])),
                            },
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
                        env_fingerprint=env_fingerprint,
                        legacy_stage_epoch=legacy_stage_epoch,
                    )

                if (
                    ctx.is_main_process
                    and args.save_archive_every_steps > 0
                    and global_step % args.save_archive_every_steps == 0
                    and global_step >= int(getattr(args, "save_after_step", 0))
                ):
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
                        env_fingerprint=env_fingerprint,
                        legacy_stage_epoch=legacy_stage_epoch,
                    )
                    _prune_archive_checkpoints(checkpoint_paths["archive_dir"], int(getattr(args, "save_last_k_checkpoints", 0)))

                should_validate = bool(val_loaders) and args.validate_every_steps > 0 and global_step % args.validate_every_steps == 0
                if should_validate:
                    run_validation_views(
                        epoch_for_log=epoch,
                        global_step_for_log=global_step,
                        current_stage_for_log=current_stage,
                        epoch_step_for_log=epoch_step,
                        stage_step_for_log=stage_step,
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
                epoch_payload = _prepare_wandb_payload(
                    args,
                    {**epoch_payload, **_pooling_weight_metrics(train_model)},
                    global_step=global_step,
                )
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

            if legacy_train_strategy and epoch_stats is not None:
                if current_stage == 0:
                    legacy_stage_epoch += 1
                    legacy_geom = float(epoch_stats.get("Geom", float("inf")))
                    should_advance_stage = (
                        legacy_geom < float(args.stage1_loss)
                        or legacy_stage_epoch >= int(args.stage1_max_epochs)
                    )
                    if should_advance_stage:
                        if ctx.is_main_process:
                            LOGGER.info(
                                "Legacy stage transition after epoch %d: stage0 Geom=%.4f, stage_epoch=%d -> entering stage 1",
                                epoch,
                                legacy_geom,
                                legacy_stage_epoch,
                            )
                        current_stage = 1
                        stage_step = 0
                        legacy_stage_epoch = 0
                else:
                    legacy_stage_epoch = 0

            if args.max_optimizer_steps > 0 and global_step >= args.max_optimizer_steps:
                break

            current_epoch = epoch + 1
            epoch_step = 0

        if val_loaders and global_step > 0 and global_step != last_validation_step:
            run_validation_views(
                epoch_for_log=min(args.epochs, max(1, current_epoch)),
                global_step_for_log=global_step,
                current_stage_for_log=current_stage,
                epoch_step_for_log=epoch_step,
                stage_step_for_log=stage_step,
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
                env_fingerprint=env_fingerprint,
                legacy_stage_epoch=legacy_stage_epoch,
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
                env_fingerprint=env_fingerprint,
                legacy_stage_epoch=legacy_stage_epoch,
            )
    finally:
        timing_logger.close()
        timing_summary = None
        if timing_logger.enabled and ctx.enabled:
            try:
                barrier()
            except Exception as exc:
                LOGGER.warning("Timing-summary barrier failed: %r", exc)
        if timing_logger.enabled and ctx.is_main_process:
            try:
                timing_summary = summarize_step_timing_logs(args.timing_log_dir)
            except Exception as exc:
                LOGGER.warning("Failed to summarize timing logs under %s: %r", args.timing_log_dir, exc)
            else:
                if timing_summary is not None:
                    global_metrics = timing_summary.get("global", {}).get("metrics", {})
                    step_mean = global_metrics.get("step_total_s", {}).get("mean")
                    fetch_mean = global_metrics.get("fetch_s", {}).get("mean")
                    process_mean = global_metrics.get("process_total_s", {}).get("mean")
                    LOGGER.info(
                        "Timing summary saved under %s (mean step_total_s=%s fetch_s=%s process_total_s=%s)",
                        args.timing_log_dir,
                        f"{step_mean:.6f}" if step_mean is not None else "n/a",
                        f"{fetch_mean:.6f}" if fetch_mean is not None else "n/a",
                        f"{process_mean:.6f}" if process_mean is not None else "n/a",
                    )
        if ctx.is_main_process:
            resolved_checkpoint_paths = locals().get("checkpoint_paths", {})
            stability_summary = {
                "config": {
                    "seed": int(getattr(args, "seed", 0)),
                    "amp_dtype": str(getattr(args, "amp_dtype", "none")),
                    "num_workers": int(getattr(args, "num_workers", 0)),
                    "val_num_workers": int(getattr(args, "val_num_workers", 0)),
                    "fixed_train_order": bool(getattr(args, "fixed_train_order", False)),
                    "deterministic_algorithms": bool(getattr(args, "deterministic_algorithms", False)),
                    "cudnn_deterministic": bool(getattr(args, "cudnn_deterministic", False)),
                    "disable_cudnn_benchmark": bool(getattr(args, "disable_cudnn_benchmark", False)),
                    "disable_tf32": bool(getattr(args, "disable_tf32", False)),
                    "float32_matmul_precision": getattr(args, "float32_matmul_precision", None),
                    "grad_clip_norm": float(getattr(args, "grad_clip_norm", 0.0)),
                    "validate_every_steps": int(getattr(args, "validate_every_steps", 0)),
                    "save_latest_every_steps": int(getattr(args, "save_latest_every_steps", 0)),
                    "save_archive_every_steps": int(getattr(args, "save_archive_every_steps", 0)),
                    "save_after_step": int(getattr(args, "save_after_step", 0)),
                    "save_last_k_checkpoints": int(getattr(args, "save_last_k_checkpoints", 0)),
                },
                "environment": locals().get("env_fingerprint", {}),
                "runtime_stability": locals().get("runtime_stability", {}),
                "checkpoint_paths": resolved_checkpoint_paths,
                "batch_order_preview": locals().get("batch_order_preview", []),
                "final_state": {
                    "global_step": int(locals().get("global_step", 0)),
                    "current_epoch": int(locals().get("current_epoch", 0)),
                    "current_stage": int(locals().get("current_stage", 0)),
                    "stage_step": int(locals().get("stage_step", 0)),
                    "best_selection_loss": float(locals().get("best_selection_loss", float("inf"))),
                },
                "timing_summary_path": str(Path(args.timing_log_dir).resolve()) if getattr(args, "timing_log_dir", None) else "",
                "hostname": socket.gethostname(),
                "use_ema": False,
            }
            summary_root = resolved_checkpoint_paths.get("root_dir")
            if summary_root:
                _write_stability_summary(Path(summary_root) / "stability_run_summary.json", stability_summary)
        finish_run(run)
        if ctx.enabled and bool(getattr(args, "ddp_final_barrier", False)):
            try:
                barrier()
            except Exception as exc:
                LOGGER.warning("Final DDP barrier failed during shutdown: %r", exc)
        cleanup_distributed()


if __name__ == "__main__":
    main()
