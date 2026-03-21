from __future__ import annotations

import argparse


def get_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser("Multi-task pretraining for MFM")

    # Dataset paths and split strategy.
    parser.add_argument("--data_roots", nargs="+", required=True, help="Training data roots (.lmdb or directory)")
    parser.add_argument("--val_data_roots", nargs="+", default=[], help="Explicit validation data roots (legacy path)")
    parser.add_argument("--starts", nargs="*", type=int, default=[], help="Start indices aligned with data_roots")
    parser.add_argument("--ends", nargs="*", type=int, default=[], help="End indices aligned with data_roots")
    parser.add_argument("--val_starts", nargs="*", type=int, default=[], help="Validation start indices")
    parser.add_argument("--val_ends", nargs="*", type=int, default=[], help="Validation end indices")
    parser.add_argument(
        "--random_val_size",
        type=int,
        default=20000,
        help="When val_data_roots is empty, draw this many validation samples uniformly from the union of data_roots.",
    )
    parser.add_argument("--split_seed", type=int, default=0, help="Seed for the random train/val split.")
    parser.add_argument(
        "--split_cache_path",
        type=str,
        default=None,
        help="Optional .pt cache file storing the generated random validation split.",
    )
    parser.add_argument(
        "--standardizer_ratio",
        type=float,
        default=0.01,
        help="Random sample ratio per training shard for standardizer estimation.",
    )
    parser.add_argument(
        "--standardizer_cap",
        type=int,
        default=100000,
        help="Maximum number of training samples used to estimate normalization statistics.",
    )
    parser.add_argument(
        "--filter_max_atoms",
        type=int,
        default=128,
        help="Drop molecules whose atom count exceeds this threshold before train/val split. Uses data.x.size(0).",
    )
    parser.add_argument(
        "--atom_budget_per_batch",
        type=int,
        default=512,
        help="Maximum total atom count per training batch after outlier filtering. 0 disables atom-budget batching.",
    )
    parser.add_argument(
        "--val_atom_budget_per_batch",
        type=int,
        default=0,
        help="Maximum total atom count per validation batch. 0 disables atom-budget batching for validation.",
    )
    parser.add_argument(
        "--atom_count_cache_dir",
        type=str,
        default=None,
        help="Directory for cached per-sample atom counts used by filtering and atom-budget batching.",
    )

    # Input perturbation (masked modeling).
    parser.add_argument(
        "--perturb_mix",
        type=str,
        default="none",
        help='Perturbation mix, e.g. "clean:@1,topo:0.3@0.2,geom:0.5@0.5,both:0.7@1.0"; "none" disables mix mode',
    )
    parser.add_argument("--perturb_mode", type=str, default="both", choices=["clean", "topo", "geom", "both"])
    parser.add_argument("--perturb_level", type=float, default=0.5)
    parser.add_argument("--perturb_replace_frac", type=float, default=None)
    parser.add_argument("--perturb_noise_std", type=float, default=None)
    parser.add_argument("--perturb_seed", type=int, default=114)

    # DataLoader / execution.
    parser.add_argument("--batch_size", type=int, default=16)
    parser.add_argument(
        "--val_batch_size",
        type=int,
        default=0,
        help="Validation batch size. 0 means reuse --batch_size.",
    )
    parser.add_argument("--num_workers", type=int, default=6)
    parser.add_argument(
        "--val_num_workers",
        type=int,
        default=-1,
        help="Validation DataLoader workers. Negative values mean reuse --num_workers.",
    )
    parser.add_argument("--device", type=str, default="auto", choices=["auto", "cpu", "cuda"])
    parser.add_argument("--distributed", action="store_true", help="Enable DDP when launched with torchrun")
    parser.add_argument("--backend", type=str, default=None, help="torch.distributed backend; defaults to nccl/gloo by device")
    parser.add_argument(
        "--dist_timeout_minutes",
        type=int,
        default=180,
        help="Process-group timeout in minutes. Increase this when rank 0 spends a long time in preprocessing before collectives.",
    )
    parser.add_argument("--ddp_broadcast_buffers", action="store_true", help="Broadcast module buffers in DDP")
    parser.add_argument("--ddp_static_graph", dest="ddp_static_graph", action="store_true", help="Enable DDP static graph optimization")
    parser.add_argument("--no_ddp_static_graph", dest="ddp_static_graph", action="store_false", help="Disable DDP static graph optimization")
    parser.add_argument(
        "--find_unused_parameters",
        dest="find_unused_parameters",
        action="store_true",
        help="Enable DDP unused-parameter detection (safer for sparse expert routing)",
    )
    parser.add_argument(
        "--no_find_unused_parameters",
        dest="find_unused_parameters",
        action="store_false",
        help="Disable DDP unused-parameter detection for maximum throughput",
    )
    parser.set_defaults(find_unused_parameters=False, ddp_static_graph=True)

    # Backbone.
    parser.add_argument("--hidden_channels", type=int, default=768)
    parser.add_argument("--bb_layers", type=int, default=6)
    parser.add_argument("--bb_heads", type=int, default=12)
    parser.add_argument("--bb_ff_mult", type=int, default=2)
    parser.add_argument("--bb_use_dist_bias", dest="bb_use_dist_bias", action="store_true")
    parser.add_argument("--no_bb_use_dist_bias", dest="bb_use_dist_bias", action="store_false")
    parser.set_defaults(bb_use_dist_bias=True)
    parser.add_argument("--bb_use_radius_mask", action="store_true")
    parser.add_argument("--bb_radius", type=float, default=8.0)

    # Experts and gates: dense single-expert formal default.
    parser.add_argument("--expert_number_E", type=int, default=1)
    parser.add_argument("--expert_number_Q", type=int, default=1)
    parser.add_argument("--expert_number_Z", type=int, default=1)
    parser.add_argument("--expert_number_G", type=int, default=1)
    parser.add_argument("--topkE", type=int, default=1)
    parser.add_argument("--topkQ", type=int, default=1)
    parser.add_argument("--topkZ", type=int, default=1)
    parser.add_argument("--topkG", type=int, default=1)
    parser.add_argument("--n_atom_types", type=int, default=95)

    # Loss weights.
    parser.add_argument("--lambda_e", type=float, default=1.0)
    parser.add_argument("--lambda_e_desc", type=float, default=0.25)
    parser.add_argument("--lambda_q", type=float, default=1.0)
    parser.add_argument("--lambda_q_desc", type=float, default=0.5)
    parser.add_argument("--lambda_z", type=float, default=1.0)
    parser.add_argument("--lambda_z_desc", type=float, default=0.5)
    parser.add_argument(
        "--lambda_coord",
        type=float,
        default=0.0,
        help="Retired and ignored; kept only for backward CLI compatibility",
    )
    parser.add_argument("--lambda_dist", type=float, default=1.0)
    parser.add_argument("--lambda_angle", type=float, default=1.0)
    parser.add_argument("--lambda_torsion", type=float, default=2.0)
    parser.add_argument(
        "--lambda_planar",
        type=float,
        default=0.0,
        help="Retired and ignored; kept only for backward CLI compatibility",
    )

    # Expert block config.
    parser.add_argument("--expert_real_layers", type=int, default=1)
    parser.add_argument("--expert_int_layers", type=int, default=0)
    parser.add_argument("--expert_heads", type=int, default=12)
    parser.add_argument("--expert_ff_mult", type=int, default=2)

    # Optimization.
    parser.add_argument("--lr", type=float, default=2e-4)
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--warmup_pct", type=float, default=0.02)
    parser.add_argument("--amp_dtype", type=str, default="none", choices=["none", "bf16", "fp16"])
    parser.add_argument(
        "--fp16",
        action="store_true",
        help="Backward-compatible alias for --amp_dtype fp16",
    )
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--dataloader_debug", action="store_true", help="Enable continuous DataLoader watchdog logging.")
    parser.add_argument(
        "--dataloader_debug_interval",
        type=int,
        default=30,
        help="Emit a DataLoader state snapshot every N seconds while waiting or processing.",
    )
    parser.add_argument(
        "--dataloader_stall_threshold",
        type=int,
        default=120,
        help="Mark the DataLoader as stalled when no state transition happens for N seconds.",
    )
    parser.add_argument(
        "--dataloader_timeout",
        type=int,
        default=0,
        help="Optional DataLoader batch timeout in seconds; 0 disables timeout.",
    )
    parser.add_argument(
        "--dataloader_slow_fetch_threshold",
        type=float,
        default=10.0,
        help="Log an immediate debug event when fetching the next batch takes longer than this many seconds.",
    )
    parser.add_argument(
        "--dataloader_debug_dir",
        type=str,
        default=None,
        help="Directory for DataLoader debug JSONL files. Defaults under the checkpoint root when debugging is enabled.",
    )
    parser.add_argument("--ddp_debug", action="store_true", help="Enable DDP training-phase watchdog logging.")
    parser.add_argument(
        "--ddp_debug_interval",
        type=int,
        default=15,
        help="Emit a DDP phase snapshot every N seconds while a rank is active.",
    )
    parser.add_argument(
        "--ddp_debug_stall_threshold",
        type=int,
        default=60,
        help="Mark the DDP training phase as stalled when no transition happens for N seconds.",
    )
    parser.add_argument(
        "--ddp_debug_dir",
        type=str,
        default=None,
        help="Directory for DDP phase debug JSONL files. Defaults under the checkpoint root when debugging is enabled.",
    )
    parser.add_argument(
        "--ddp_debug_grad_sample_size",
        type=int,
        default=12,
        help="Maximum number of parameter names to record when gradients are missing after backward.",
    )

    # Stage settings.
    parser.add_argument("--stage1_loss", type=float, default=0.3)
    parser.add_argument("--stage2_loss", type=float, default=0.1)
    parser.add_argument("--stage1_max_epochs", type=int, default=101)
    parser.add_argument(
        "--stage1_max_steps",
        type=int,
        default=20000,
        help="Number of optimizer steps to train with distance-only geometry loss before enabling angle/torsion.",
    )

    # Geometric/morse settings.
    parser.add_argument("--loss_cutoff", type=float, default=2.0)
    parser.add_argument("--morse_D", type=float, default=1.0)
    parser.add_argument("--morse_a", type=float, default=1.0)

    # Element classification regularization.
    parser.add_argument("--z_label_smooth", type=float, default=0.10)
    parser.add_argument("--z_focal_gamma", type=float, default=0.0)
    parser.add_argument("--z_temp", type=float, default=1.5)
    parser.add_argument("--z_entropy_reg", type=float, default=0.05)
    parser.add_argument("--z_logit_l2", type=float, default=1e-4)
    parser.add_argument(
        "--z_class_balance",
        type=str,
        default="none",
        choices=["none", "batch_inv", "effective"],
    )

    # Step-based validation / checkpointing / resume.
    parser.add_argument("--save_path", default="checkpoints/best.pt")
    parser.add_argument("--checkpoint_dir", type=str, default=None)
    parser.add_argument("--resume_from", type=str, default=None)
    parser.add_argument("--validate_every_steps", type=int, default=10000)
    parser.add_argument("--save_latest_every_steps", type=int, default=5000)
    parser.add_argument("--save_archive_every_steps", type=int, default=40000)
    parser.add_argument(
        "--max_optimizer_steps",
        type=int,
        default=0,
        help="Optional hard stop after N optimizer steps. Useful for short smoke and resume checks.",
    )
    parser.add_argument(
        "--save_every_epoch",
        action="store_true",
        help="Deprecated legacy option; ignored by the formal step-based training pipeline.",
    )

    # Weights & Biases.
    parser.add_argument("--use_wandb", action="store_true", help="Enable Weights & Biases logging")
    parser.add_argument("--wandb_project", type=str, default="mfm-pretrain")
    parser.add_argument("--wandb_entity", type=str, default=None)
    parser.add_argument("--wandb_run_name", type=str, default=None)
    parser.add_argument("--wandb_group", type=str, default=None)
    parser.add_argument("--wandb_tags", nargs="*", default=[])
    parser.add_argument("--wandb_notes", type=str, default=None)
    parser.add_argument("--wandb_mode", type=str, default="online", choices=["online", "offline", "disabled"])
    parser.add_argument("--wandb_dir", type=str, default="wandb")
    parser.add_argument(
        "--wandb_watch",
        type=str,
        default="gradients",
        choices=["none", "gradients", "parameters", "all"],
        help="Model monitoring level for W&B",
    )
    parser.add_argument("--wandb_watch_log_freq", type=int, default=1000)
    parser.add_argument(
        "--wandb_log_batch_every",
        type=int,
        default=200,
        help="Log train batch metrics to W&B every N optimizer steps; 0 disables batch logging",
    )
    parser.add_argument("--wandb_log_checkpoints", action="store_true")

    return parser.parse_args()
