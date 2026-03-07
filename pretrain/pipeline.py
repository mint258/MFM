from __future__ import annotations

import logging
import os
import warnings

import torch
from torch.cuda.amp import GradScaler
from torch.utils.data import ConcatDataset, Subset
from torch_geometric.loader import DataLoader

from degrade_molecules import DegradeConfig
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
from .train_loop import DummyScaler, run_epoch
from .utils import build_lr_scheduler, pad_list, set_seed

warnings.filterwarnings("ignore", category=UserWarning)
logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
LOGGER = logging.getLogger("multitask")


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

    scaler = GradScaler(init_scale=2**8) if args.fp16 else DummyScaler()

    total_steps = len(train_loader) * args.epochs
    warm_steps = int(total_steps * args.warmup_pct)
    scheduler = build_lr_scheduler(optimizer, total_steps, warm_steps)

    best_loss = float("inf")
    stage = 0
    stage_ep = 0
    LOGGER.info("Training started: Stage-0")

    for ep in range(1, args.epochs + 1):
        if stage == 0:
            active = ("dist",)
        else:
            active = ("dist", "angle", "torsion", "planar")

        def lambda_for(name: str) -> float:
            return getattr(args, f"lambda_{name}", 0.0) if name in active else 0.0

        lam_c = lambda_for("coord")
        lam_d = lambda_for("dist")
        lam_a = lambda_for("angle")
        lam_t = lambda_for("torsion")
        lam_p = lambda_for("planar")

        LOGGER.info(
            "Epoch %d stage %d: lam_c=%s lam_d=%s lam_a=%s lam_t=%s lam_p=%s",
            ep,
            stage,
            lam_c,
            lam_d,
            lam_a,
            lam_t,
            lam_p,
        )

        tr = run_epoch(
            model,
            train_loader,
            device,
            std,
            scaler,
            loss_cutoff=args.loss_cutoff,
            n_atom_types=args.n_atom_types,
            lam_c=lam_c,
            lam_d=lam_d,
            lam_a=lam_a,
            lam_t=lam_t,
            lam_p=lam_p,
            lam_e=args.lambda_e,
            lam_q=args.lambda_q,
            lam_z=args.lambda_z,
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
        )

        print(
            f"Train E={tr['E']:.3f} Q={tr['Q']:.3f} Z={tr['Z']:.3f} | "
            f"Geom={tr['Geom']:.3f} (Coord={tr['Geom_c']:.4f} Morse={tr['Geom_d']:.4f} "
            f"Ang={tr['Geom_a']:.4f} Tor={tr['Geom_t']:.4f} Planar={tr['Geom_p']:.4f})"
        )
        print(
            f"      R2(E={tr['R2_e']:.3f}, Q={tr['R2_q']:.3f}, Z={tr['R2_z']:.3f}), RMSD={tr['RMSD']:.3f} | "
            f"Acc(Z)={tr['Acc_z']:.3f} | Bad={tr['bad']}"
        )

        cfg = {
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
        }

        if args.save_every_epoch:
            epoch_save_path = f"{args.save_path}_epoch_{ep:03d}.pt"
            save_checkpoint(model, cfg, std, epoch_save_path)
            LOGGER.info("Saved per-epoch ckpt to %s", epoch_save_path)

        torch.cuda.empty_cache()

        if val_loader is not None:
            va = run_epoch(
                model,
                val_loader,
                device,
                std,
                scaler,
                loss_cutoff=args.loss_cutoff,
                n_atom_types=args.n_atom_types,
                lam_c=lam_c,
                lam_d=lam_d,
                lam_a=lam_a,
                lam_t=lam_t,
                lam_p=lam_p,
                lam_e=args.lambda_e,
                lam_q=args.lambda_q,
                lam_z=args.lambda_z,
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
            )
            print(
                f"Val   E={va['E']:.3f} Q={va['Q']:.3f} Z={va['Z']:.3f} | "
                f"Geom={va['Geom']:.3f} (Coord={va['Geom_c']:.4f} Morse={va['Geom_d']:.4f} "
                f"Ang={va['Geom_a']:.4f} Tor={va['Geom_t']:.4f} Planar={va['Geom_p']:.4f})"
            )
            print(
                f"      R2(E={va['R2_e']:.3f}, Q={va['R2_q']:.3f}, Z={va['R2_z']:.3f}), RMSD={va['RMSD']:.3f} | "
                f"Acc(Z)={va['Acc_z']:.3f} | Bad={va['bad']}"
            )
            cur_loss = va["E"] + va["Q"] + va["Geom"]
        else:
            cur_loss = tr["E"] + tr["Q"] + tr["Geom"]

        if cur_loss < best_loss:
            best_loss = cur_loss
            save_checkpoint(model, cfg, std, args.save_path)
            LOGGER.info("Saved best checkpoint for stage %d to %s (loss=%.4f)", stage, args.save_path, best_loss)

        stage_ep += 1
        stage_transition = False
        next_stage = stage

        if stage == 0:
            cond = (tr["Geom"] < args.stage1_loss) or (stage_ep >= args.stage1_max_epochs)
            if cond:
                stage_transition = True
                next_stage = 1

        if stage_transition:
            LOGGER.info("Stage-%d finished at epoch %d", stage, ep)
            stage_save_path = f"stage_{stage}_end_epoch_{ep}.pt"
            save_checkpoint(model, cfg, std, stage_save_path)
            LOGGER.info("Saved final model for stage %d to %s", stage, stage_save_path)

            best_loss = float("inf")
            stage = next_stage
            stage_ep = 0
            LOGGER.info("Entering Stage-%d", stage)

        torch.cuda.empty_cache()


if __name__ == "__main__":
    main()
