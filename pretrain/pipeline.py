from __future__ import annotations

import logging
import warnings

import torch
from torch.utils.data import ConcatDataset, DataLoader, Subset

from models.moe import MultiTaskMoE

from .args import get_args
from .checkpoint import save_checkpoint
from .data import (
    DomainWrapperDataset,
    MaskedPerturbDataset,
    OnlyStableWrapper,
    create_dataset,
    fast_collate,
    standardizer,
)
from .degrade_molecules import DegradeConfig
from .train_loop import DummyScaler, run_epoch
from .utils import build_lr_scheduler, pad_list, set_seed
from .wandb_utils import finish_run, init_wandb_run, log_checkpoint_artifact, log_metrics, update_summary

warnings.filterwarnings("ignore", category=UserWarning)
logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
LOGGER = logging.getLogger("multitask")


def _enforce_retired_training_policy(args) -> None:
    for arg_name in ("lambda_coord", "lambda_planar"):
        value = float(getattr(args, arg_name, 0.0))
        if value != 0.0:
            LOGGER.warning("--%s is retired and will be forced to 0.0", arg_name.replace("_", "-"))
        setattr(args, arg_name, 0.0)


def _build_checkpoint_cfg(args, bb_cfg):
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


def _summarize_epoch(stats, *, stage: int, stage_epoch: int, lr: float, loss_total: float, selection_loss: float, lam_d: float, lam_a: float, lam_t: float):
    summary = {
        "stage": stage,
        "stage_epoch": stage_epoch,
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


def _print_epoch_metrics(prefix: str, stats) -> None:
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
    """Parse entries like `topo:0.3@0.2,geom:0.5@0.5`."""
    out = []
    for idx, segment in enumerate([s for s in spec.split(",") if s.strip()]):
        if segment.lower() == "none":
            continue
        if ":" not in segment or "@" not in segment:
            continue

        mode, rest = segment.split(":", 1)
        level_str, ratio_str = rest.split("@", 1)

        mode = mode.strip().lower()
        if mode not in {"topo", "geom", "both"}:
            continue

        level = float(level_str)
        ratio = float(ratio_str)
        out.append((mode, level, ratio, base_seed + 10000 * idx))

    return out


def build_perturb_parts(base_dataset, mix_specs, seed_base: int, args):
    """Expand perturbation specs into a list of datasets used by ConcatDataset."""
    parts = []
    for mode, level, ratio, seed in mix_specs:
        cfg = _build_degrade_cfg(args, mode, level)
        pert_base = MaskedPerturbDataset(base_dataset, cfg, seed=seed_base + seed)

        whole = int(ratio)
        frac = float(ratio) - whole
        parts.extend([pert_base] * whole)

        if frac > 1e-8:
            take = max(1, int(len(base_dataset) * frac))
            parts.append(Subset(pert_base, list(range(take))))

    return parts


def build_dataloader(dataset, *, batch_size: int, num_workers: int, shuffle: bool):
    kwargs = {
        "batch_size": batch_size,
        "shuffle": shuffle,
        "num_workers": num_workers,
        "pin_memory": True,
        "persistent_workers": False,
        "collate_fn": fast_collate,
    }
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


def main() -> None:
    args = get_args()
    _enforce_retired_training_policy(args)
    if args.fp16:
        LOGGER.warning("--fp16 is disabled by training policy; forcing FP32 execution.")
        args.fp16 = False
    set_seed(args.seed)
    device = "cuda" if torch.cuda.is_available() else "cpu"

    starts = pad_list(args.starts, len(args.data_roots), 0)
    ends = pad_list(args.ends, len(args.data_roots), None)
    val_starts = pad_list(args.val_starts, len(args.val_data_roots), 0)
    val_ends = pad_list(args.val_ends, len(args.val_data_roots), None)

    train_list = []
    val_list = []
    std_bases = []

    for domain_id, (path, start, end) in enumerate(zip(args.data_roots, starts, ends)):
        base_raw = OnlyStableWrapper(create_dataset(path, start, end))
        if len(base_raw) == 0:
            LOGGER.warning("Skip empty dataset root: %s (start=%s end=%s)", path, start, end)
            continue

        std_bases.append(base_raw)

        if getattr(args, "perturb_mix", "none") not in (None, "none"):
            specs = parse_perturb_mix(args.perturb_mix, args.perturb_seed + domain_id * 100000)
            parts = build_perturb_parts(base_raw, specs, args.perturb_seed + domain_id * 100000, args)
            if not parts:
                cfg = _build_degrade_cfg(args, args.perturb_mode, args.perturb_level)
                parts = [MaskedPerturbDataset(base_raw, cfg, seed=args.perturb_seed + domain_id * 100000)]
        else:
            cfg = _build_degrade_cfg(args, args.perturb_mode, args.perturb_level)
            parts = [MaskedPerturbDataset(base_raw, cfg, seed=args.perturb_seed + domain_id * 100000)]

        for part in parts:
            train_list.append(DomainWrapperDataset(part, domain_id))

    for domain_id, (path, start, end) in enumerate(
        zip(args.val_data_roots, val_starts, val_ends),
        start=len(train_list),
    ):
        base = OnlyStableWrapper(create_dataset(path, start, end))
        if len(base) == 0:
            LOGGER.warning("Skip empty val dataset root: %s (start=%s end=%s)", path, start, end)
            continue

        std_bases.append(base)
        if getattr(args, "perturb_mix", "none") not in (None, "none"):
            specs = parse_perturb_mix(args.perturb_mix, args.perturb_seed + 1000000 + domain_id * 100000)
            parts = build_perturb_parts(base, specs, args.perturb_seed + 1000000 + domain_id * 100000, args)
            if not parts:
                cfg = _build_degrade_cfg(args, args.perturb_mode, args.perturb_level)
                parts = [MaskedPerturbDataset(base, cfg, seed=args.perturb_seed + 1000000 + domain_id * 100000)]
        else:
            cfg = _build_degrade_cfg(args, args.perturb_mode, args.perturb_level)
            parts = [MaskedPerturbDataset(base, cfg, seed=args.perturb_seed + 1000000 + domain_id * 100000)]

        for part in parts:
            val_list.append(DomainWrapperDataset(part, domain_id))

    if not train_list:
        raise ValueError("No training datasets were built. Check data_roots and index ranges.")

    train_ds = ConcatDataset(train_list)
    val_ds = ConcatDataset(val_list) if val_list else None

    train_loader = build_dataloader(
        train_ds,
        batch_size=args.batch_size,
        num_workers=args.num_workers,
        shuffle=True,
    )
    val_loader = None
    if val_ds:
        val_loader = build_dataloader(
            val_ds,
            batch_size=args.batch_size,
            num_workers=args.num_workers,
            shuffle=False,
        )

    first_base_len = len(std_bases[0])
    ratio = 1.0 if first_base_len < 10000 else (0.1 if first_base_len < 100000 else 0.01)
    std = standardizer(std_bases, ratio=ratio, cap=10000, seed=args.seed)

    LOGGER.info("Building MultiTaskMoE model")
    model, bb_cfg = build_model(args, device)
    cfg = _build_checkpoint_cfg(args, bb_cfg)

    decay, no_decay = [], []
    for name, param in model.named_parameters():
        target = no_decay if name.endswith("bias") or "norm" in name.lower() else decay
        target.append(param)

    optimizer = torch.optim.AdamW(
        [
            {"params": decay, "weight_decay": 0.01},
            {"params": no_decay, "weight_decay": 0.0},
        ],
        lr=args.lr,
        betas=(0.9, 0.95),
        eps=1e-8,
    )

    scaler = DummyScaler()

    total_steps = len(train_loader) * args.epochs
    warm_steps = int(total_steps * args.warmup_pct)
    scheduler = build_lr_scheduler(optimizer, total_steps, warm_steps)

    best_loss = float("inf")
    stage = 0
    stage_ep = 0
    global_step = 0
    run = None
    LOGGER.info("Training started: Stage-0")
    try:
        run = init_wandb_run(
            args,
            model=model,
            device=device,
            train_size=len(train_ds),
            val_size=(len(val_ds) if val_ds is not None else 0),
        )
        update_summary(
            run,
            {
                "meta/device": device,
                "meta/train_size": len(train_ds),
                "meta/val_size": len(val_ds) if val_ds is not None else 0,
            },
        )

        def log_train_batch(batch_metrics, step):
            log_metrics(run, "train/batch", batch_metrics, global_step=step)

        for ep in range(1, args.epochs + 1):
            if torch.cuda.is_available():
                torch.cuda.reset_peak_memory_stats()

            if stage == 0:
                active = ("dist",)
            else:
                active = ("dist", "angle", "torsion")

            def lambda_for(name: str) -> float:
                return getattr(args, f"lambda_{name}", 0.0) if name in active else 0.0

            lam_d = lambda_for("dist")
            lam_a = lambda_for("angle")
            lam_t = lambda_for("torsion")

            LOGGER.info(
                "Epoch %d stage %d: lam_d=%s lam_a=%s lam_t=%s",
                ep,
                stage,
                lam_d,
                lam_a,
                lam_t,
            )

            tr = run_epoch(
                model,
                train_loader,
                device,
                std,
                scaler,
                loss_cutoff=args.loss_cutoff,
                n_atom_types=args.n_atom_types,
                lam_c=0.0,
                lam_d=lam_d,
                lam_a=lam_a,
                lam_t=lam_t,
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
                fp16=args.fp16,
                desc=f"Train{ep:03d}",
                scheduler=scheduler,
                batch_logger=log_train_batch if run is not None else None,
                batch_log_interval=args.wandb_log_batch_every,
                global_step_start=global_step,
            )
            global_step = tr["global_step"]
            current_lr = optimizer.param_groups[0]["lr"]
            train_total = _total_loss(args, tr)
            train_selection = _selection_loss(args, tr)

            _print_epoch_metrics("Train", tr)
            log_metrics(
                run,
                "train/epoch",
                _summarize_epoch(
                    tr,
                    stage=stage,
                    stage_epoch=stage_ep + 1,
                    lr=current_lr,
                    loss_total=train_total,
                    selection_loss=train_selection,
                    lam_d=lam_d,
                    lam_a=lam_a,
                    lam_t=lam_t,
                ),
                epoch=ep,
                global_step=global_step,
            )

            if args.save_every_epoch:
                epoch_save_path = f"{args.save_path}_epoch_{ep:03d}.pt"
                save_checkpoint(model, cfg, std, epoch_save_path)
                LOGGER.info("Saved per-epoch ckpt to %s", epoch_save_path)

            torch.cuda.empty_cache()

            va = None
            if val_loader is not None:
                va = run_epoch(
                    model,
                    val_loader,
                    device,
                    std,
                    scaler,
                    loss_cutoff=args.loss_cutoff,
                    n_atom_types=args.n_atom_types,
                    lam_c=0.0,
                    lam_d=lam_d,
                    lam_a=lam_a,
                    lam_t=lam_t,
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
                    fp16=args.fp16,
                    desc=f"Val{ep:03d}",
                    scheduler=None,
                    global_step_start=global_step,
                )
                val_total = _total_loss(args, va)
                val_selection = _selection_loss(args, va)
                _print_epoch_metrics("Val  ", va)
                log_metrics(
                    run,
                    "val",
                    _summarize_epoch(
                        va,
                        stage=stage,
                        stage_epoch=stage_ep + 1,
                        lr=current_lr,
                        loss_total=val_total,
                        selection_loss=val_selection,
                        lam_d=lam_d,
                        lam_a=lam_a,
                        lam_t=lam_t,
                    ),
                    epoch=ep,
                    global_step=global_step,
                )
                cur_loss = val_selection
            else:
                cur_loss = train_selection

            meta_metrics = {
                "stage": stage,
                "stage_epoch": stage_ep + 1,
                "best_selection_loss_so_far": best_loss,
                "global_step": global_step,
            }
            if torch.cuda.is_available():
                meta_metrics["cuda_peak_memory_gb"] = torch.cuda.max_memory_allocated() / (1024 ** 3)
            log_metrics(run, "meta", meta_metrics, epoch=ep, global_step=global_step)

            if cur_loss < best_loss:
                best_loss = cur_loss
                save_checkpoint(model, cfg, std, args.save_path)
                LOGGER.info("Saved best checkpoint for stage %d to %s (loss=%.4f)", stage, args.save_path, best_loss)
                update_summary(
                    run,
                    {
                        "best/epoch": ep,
                        "best/stage": stage,
                        "best/selection_loss": best_loss,
                        "best/source": "val" if va is not None else "train",
                        "best/path": args.save_path,
                    },
                )
                if args.wandb_log_checkpoints:
                    log_checkpoint_artifact(
                        run,
                        args.save_path,
                        label="best",
                        aliases=["best", f"stage_{stage}", f"epoch_{ep:03d}"],
                        metadata={"epoch": ep, "stage": stage, "selection_loss": best_loss},
                    )

            stage_ep += 1
            stage_transition = False
            next_stage = stage

            if stage == 0:
                cond = (tr["Geom"] < args.stage1_loss) or (stage_ep >= args.stage1_max_epochs)
                if cond:
                    stage_transition = True
                    next_stage = 1

            if stage_transition:
                prev_stage = stage
                LOGGER.info("Stage-%d finished at epoch %d", prev_stage, ep)
                stage_save_path = f"stage_{prev_stage}_end_epoch_{ep}.pt"
                save_checkpoint(model, cfg, std, stage_save_path)
                LOGGER.info("Saved final model for stage %d to %s", prev_stage, stage_save_path)
                if args.wandb_log_checkpoints:
                    log_checkpoint_artifact(
                        run,
                        stage_save_path,
                        label=f"stage_{prev_stage}_end",
                        aliases=[f"stage_{prev_stage}_end", f"epoch_{ep:03d}"],
                        metadata={"epoch": ep, "stage": prev_stage},
                    )
                log_metrics(
                    run,
                    "meta",
                    {"stage_transition": 1, "stage_from": prev_stage, "stage_to": next_stage},
                    epoch=ep,
                    global_step=global_step,
                )

                best_loss = float("inf")
                stage = next_stage
                stage_ep = 0
                LOGGER.info("Entering Stage-%d", stage)

            torch.cuda.empty_cache()
    finally:
        finish_run(run)


if __name__ == "__main__":
    main()
