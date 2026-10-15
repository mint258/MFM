#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import torch

from phychem_mfm.config import load_experiment_config
from phychem_mfm.factory import build_model
from phychem_mfm.model.adaptation import semantic_parameter_groups
from phychem_mfm.supervision import Objective
from phychem_mfm.training.data import create_dataset, fast_collate


def count(parameters):
    return sum(parameter.numel() for parameter in parameters)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/iclr2027/base.yaml")
    parser.add_argument("--task-route", choices=("light", "expert"), required=True)
    parser.add_argument("--data-root", default="/share/home/zixiao/dataset/lmdb_new")
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--warmup", type=int, default=3)
    parser.add_argument("--repeats", type=int, default=10)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    config = load_experiment_config(root / args.config).to_dict()
    model = build_model(config, preset=args.task_route).cuda().train()
    groups = semantic_parameter_groups(model)
    dataset = create_dataset(str(Path(args.data_root) / "principal_00000001_00300000.lmdb"), 0, args.batch_size - 1)
    batch = fast_collate([dataset[index] for index in range(args.batch_size)]).cuda()

    for _ in range(args.warmup):
        model.zero_grad(set_to_none=True)
        output = model.forward_pretrain(batch, Objective)
        loss = sum(tensor.float().square().mean() for tensor in (
            output.energy_pred, output.charge_pred, output.element_logits, output.coordinate_pred,
            output.graph_descriptor_pred,
        ) if tensor is not None)
        loss.backward()
    torch.cuda.synchronize()
    torch.cuda.reset_peak_memory_stats()

    forward_times = []
    backward_times = []
    for _ in range(args.repeats):
        model.zero_grad(set_to_none=True)
        start = time.perf_counter()
        output = model.forward_pretrain(batch, Objective)
        torch.cuda.synchronize()
        middle = time.perf_counter()
        tensors = [
            output.energy_pred, output.charge_pred, output.element_logits, output.coordinate_pred,
            output.graph_descriptor_pred, *output.charge_descriptor_pred.values(),
            *output.element_descriptor_pred.values(), output.bond.existence, output.bond.order,
        ]
        sum(tensor.float().square().mean() for tensor in tensors if tensor is not None and tensor.numel()).backward()
        torch.cuda.synchronize()
        end = time.perf_counter()
        forward_times.append(middle - start)
        backward_times.append(end - middle)

    payload = {
        "task_route": args.task_route,
        "total_parameters": count(model.parameters()),
        "backbone_parameters": count(groups["backbone"]),
        "adapter_expert_parameters": count(groups["experts_adapters"]),
        "head_parameters": count(groups["pretraining_heads"]),
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
