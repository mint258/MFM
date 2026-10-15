#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import torch


KEYS = (
    "n_atom_types", "hidden_channels", "bb_layers", "bb_heads", "bb_ff_mult", "bb_dropout",
    "bb_use_dist_bias", "bb_use_radius_mask", "bb_radius", "expert_real_layers", "expert_int_layers",
    "expert_heads", "expert_ff_mult", "bond_negative_ratio", "lambda_e", "lambda_e_desc", "lambda_q",
    "lambda_q_desc", "lambda_z", "lambda_z_desc", "lambda_bond_exist", "lambda_bond_order",
    "lambda_dist", "lambda_angle", "lambda_torsion", "loss_cutoff", "morse_D", "morse_a",
    "z_label_smooth", "z_focal_gamma", "z_temp", "z_class_balance", "z_entropy_reg", "z_logit_l2",
    "stage1_max_steps", "stage2_descriptor_ramp_steps", "stage1_signal_decay_steps",
    "stage1_signal_floor", "lr", "epochs", "warmup_pct", "grad_clip_norm", "seed", "amp_dtype",
    "weight_decay", "energy_desc_names", "perturb_mix", "val_perturb_mix", "filter_max_atoms",
    "batch_size", "atom_budget_per_batch",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(8 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("checkpoint")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    checkpoint = Path(args.checkpoint).resolve()
    payload = torch.load(checkpoint, map_location="cpu", weights_only=False)
    cfg = payload.get("cfg", {})
    result = {
        "checkpoint": str(checkpoint),
        "checkpoint_sha256": sha256(checkpoint),
        "checkpoint_kind": payload.get("checkpoint_kind"),
        "global_step": payload.get("global_step"),
        "cfg": {key: cfg.get(key, "<missing>") for key in KEYS},
        "model_cfg": payload.get("model_cfg", {}),
    }
    rendered = json.dumps(result, indent=2, sort_keys=True, default=str)
    Path(args.output).write_text(rendered, encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
