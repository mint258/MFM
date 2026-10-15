#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import torch


def tensor_loss(value):
    if isinstance(value, torch.Tensor) and value.numel() and value.is_floating_point():
        return value.float().square().mean()
    if isinstance(value, dict):
        terms = [term for item in value.values() if (term := tensor_loss(item)) is not None]
        if not terms:
            return None
        total = terms[0]
        for term in terms[1:]:
            total = total + term
        return total
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--legacy-root",
        default="/share/home/zixiao/descriptor_analysis/modern_ML_representation/support_scripts/MFM_descriptor",
    )
    parser.add_argument("--data-root", default="/share/home/zixiao/dataset/lmdb_new")
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--warmup", type=int, default=5)
    parser.add_argument("--repeats", type=int, default=20)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    legacy_root = str(Path(args.legacy_root).resolve())
    sys.path.insert(0, legacy_root)
    from models.moe.multitask import MultiTaskMoE

    from phychem_mfm.training.data import create_dataset, fast_collate

    model = MultiTaskMoE(
        {
            "hidden_channels": 512,
            "atom_embedding_dim": 512,
            "bb_layers": 6,
            "bb_heads": 8,
            "bb_ff_mult": 2,
            "bb_use_dist_bias": True,
            "bb_use_radius_mask": False,
            "bb_radius": 8.0,
        },
        n_atom_types=95,
        n_experts_energy=1,
        n_experts_charge=1,
        n_experts_geom=1,
        n_experts_elem=1,
        n_experts_bond=1,
        top_k_energy=1,
        top_k_charge=1,
        top_k_geom=1,
        top_k_elem=1,
        top_k_bond=1,
        expert_real_layers=2,
        expert_int_layers=0,
        expert_heads=8,
        expert_ff_mult=2,
        bond_negative_ratio=1.0,
        graph_descriptor_names=(
            "MolLogP", "MolMR", "TPSA", "LabuteASA", "ExactMolWt", "NumValenceElectrons",
            "HeavyAtomCount", "NumHeteroatoms", "NumHAcceptors", "NumHDonors", "NumRotatableBonds",
            "FractionCSP3", "RingCount", "NumAromaticRings", "NumAliphaticRings",
            "NumSaturatedRings", "NumHeterocycles", "NumBridgeheadAtoms", "NumSpiroAtoms",
            "NumAmideBonds", "BertzCT", "HallKierAlpha", "Kappa1", "NPR1", "NPR2",
            "Asphericity", "PBF",
        ),
    ).cuda().train()
    shard = Path(args.data_root) / "principal_00000001_00300000.lmdb"
    dataset = create_dataset(str(shard), 0, args.batch_size - 1)
    batch = fast_collate([dataset[index] for index in range(args.batch_size)]).cuda()

    for _ in range(args.warmup):
        model.zero_grad(set_to_none=True)
        loss = tensor_loss(model(batch))
        if loss is None:
            raise RuntimeError("Legacy forward produced no differentiable outputs")
        loss.backward()
    torch.cuda.synchronize()
    torch.cuda.reset_peak_memory_stats()

    forward_times = []
    backward_times = []
    for _ in range(args.repeats):
        model.zero_grad(set_to_none=True)
        start = time.perf_counter()
        output = model(batch)
        torch.cuda.synchronize()
        middle = time.perf_counter()
        tensor_loss(output).backward()
        torch.cuda.synchronize()
        end = time.perf_counter()
        forward_times.append(middle - start)
        backward_times.append(end - middle)

    counts = {"backbone": 0, "experts": 0, "heads": 0, "gates": 0, "fusion": 0}
    for name, parameter in model.named_parameters():
        if name.startswith("backbone."):
            group = "backbone"
        elif name.startswith("experts_"):
            group = "experts"
        elif name.startswith("gate_"):
            group = "gates"
        elif name.startswith("fusion."):
            group = "fusion"
        else:
            group = "heads"
        counts[group] += parameter.numel()
    payload = {
        "task_route": "legacy_moe_fusion",
        "total_parameters": sum(counts.values()),
        "parameter_groups": counts,
        "mean_forward_seconds": sum(forward_times) / len(forward_times),
        "mean_backward_seconds": sum(backward_times) / len(backward_times),
        "peak_memory_gib": torch.cuda.max_memory_allocated() / (1024**3),
        "batch_size": args.batch_size,
        "atom_count": int(batch.x.size(0)),
    }
    rendered = json.dumps(payload, indent=2, sort_keys=True)
    print(rendered)
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")


if __name__ == "__main__":
    main()
