from __future__ import annotations

import argparse


def get_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser("Multi-task pretraining for MFM")

    # Dataset paths and index slices.
    parser.add_argument("--data_roots", nargs="+", required=True, help="Training data roots (.lmdb or directory)")
    parser.add_argument("--val_data_roots", nargs="+", default=[], help="Validation data roots")
    parser.add_argument("--starts", nargs="*", type=int, default=[], help="Start indices aligned with data_roots")
    parser.add_argument("--ends", nargs="*", type=int, default=[], help="End indices aligned with data_roots")
    parser.add_argument("--val_starts", nargs="*", type=int, default=[], help="Validation start indices")
    parser.add_argument("--val_ends", nargs="*", type=int, default=[], help="Validation end indices")

    # Input perturbation (masked modeling).
    parser.add_argument(
        "--perturb_mix",
        type=str,
        default="none",
        help='Perturbation mix, e.g. "topo:0.3@0.2,geom:0.5@0.5,both:0.7@1.0"; "none" disables mix mode',
    )
    parser.add_argument("--perturb_mode", type=str, default="both", choices=["topo", "geom", "both"])
    parser.add_argument("--perturb_level", type=float, default=0.5)
    parser.add_argument("--perturb_replace_frac", type=float, default=None)
    parser.add_argument("--perturb_noise_std", type=float, default=None)
    parser.add_argument("--perturb_seed", type=int, default=114)

    # DataLoader.
    parser.add_argument("--batch_size", type=int, default=4)
    parser.add_argument("--num_workers", type=int, default=0)

    # Backbone.
    parser.add_argument("--hidden_channels", type=int, default=512)
    parser.add_argument("--bb_layers", type=int, default=6)
    parser.add_argument("--bb_heads", type=int, default=8)
    parser.add_argument("--bb_ff_mult", type=int, default=4)
    parser.add_argument("--bb_use_dist_bias", dest="bb_use_dist_bias", action="store_true")
    parser.add_argument("--no_bb_use_dist_bias", dest="bb_use_dist_bias", action="store_false")
    parser.set_defaults(bb_use_dist_bias=True)
    parser.add_argument("--bb_use_radius_mask", action="store_true")
    parser.add_argument("--bb_radius", type=float, default=8.0)

    # Experts and gates.
    parser.add_argument("--expert_number_E", type=int, default=2)
    parser.add_argument("--expert_number_Q", type=int, default=2)
    parser.add_argument("--expert_number_Z", type=int, default=1)
    parser.add_argument("--expert_number_G", type=int, default=4)
    parser.add_argument("--topkE", type=int, default=1)
    parser.add_argument("--topkQ", type=int, default=1)
    parser.add_argument("--topkZ", type=int, default=1)
    parser.add_argument("--topkG", type=int, default=1)
    parser.add_argument("--n_atom_types", type=int, default=95)

    # Loss weights.
    parser.add_argument("--lambda_e", type=float, default=1.0)
    parser.add_argument("--lambda_q", type=float, default=1.0)
    parser.add_argument("--lambda_z", type=float, default=1.0)
    parser.add_argument("--lambda_coord", type=float, default=1.0)
    parser.add_argument("--lambda_dist", type=float, default=0.0)
    parser.add_argument("--lambda_angle", type=float, default=0.0)
    parser.add_argument("--lambda_torsion", type=float, default=0.0)
    parser.add_argument("--lambda_planar", type=float, default=1.0)

    # Expert block config.
    parser.add_argument("--expert_real_layers", type=int, default=2)
    parser.add_argument("--expert_int_layers", type=int, default=0)
    parser.add_argument("--expert_heads", type=int, default=4)
    parser.add_argument("--expert_ff_mult", type=int, default=2)

    # Optimization.
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--warmup_pct", type=float, default=0.06)
    parser.add_argument(
        "--fp16",
        action="store_true",
        help="Deprecated/disabled for pretraining; kept only for backward CLI compatibility",
    )
    parser.add_argument("--seed", type=int, default=0)

    # Stage settings.
    parser.add_argument("--stage1_loss", type=float, default=0.3)
    parser.add_argument("--stage2_loss", type=float, default=0.1)
    parser.add_argument("--stage1_max_epochs", type=int, default=101)

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

    parser.add_argument("--save_path", default="ckpt_multitask.pt")
    parser.add_argument("--save_every_epoch", action="store_true")

    return parser.parse_args()
