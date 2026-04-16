from __future__ import annotations

import argparse
import json
import logging
import os
import socket
import time

import torch
import torch.distributed as dist
import torch.nn as nn
from torch.nn.parallel import DistributedDataParallel as DDP
from torch.utils.data import DataLoader, DistributedSampler

LOGGER = logging.getLogger("slurm-smoke")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser("Multi-GPU smoke and benchmark helper")
    parser.add_argument("--mode", choices=["allreduce", "pretrain"], required=True)
    parser.add_argument("--backend", default="nccl")

    parser.add_argument("--seed", type=int, default=0)

    parser.add_argument("--tensor-mb", type=int, default=256)
    parser.add_argument("--warmup-iters", type=int, default=10)
    parser.add_argument("--iters", type=int, default=30)
    parser.add_argument("--dtype", choices=["float16", "float32", "bfloat16"], default="float32")

    parser.add_argument("--data-root", default="test_data/principal_valid_test.lmdb")
    parser.add_argument("--train-start", type=int, default=875)
    parser.add_argument("--train-end", type=int, default=1514)
    parser.add_argument("--steps", type=int, default=20)
    parser.add_argument("--batch-size", type=int, default=8, help="Per-process batch size")
    parser.add_argument("--num-workers", type=int, default=6, help="Per-process DataLoader workers")

    parser.add_argument("--perturb-mode", choices=["topo", "geom", "both"], default="both")
    parser.add_argument("--perturb-level", type=float, default=0.5)
    parser.add_argument("--perturb-replace-frac", type=float, default=None)
    parser.add_argument("--perturb-noise-std", type=float, default=None)

    parser.add_argument("--hidden-channels", type=int, default=64)
    parser.add_argument("--bb-layers", type=int, default=3)
    parser.add_argument("--bb-heads", type=int, default=4)
    parser.add_argument("--bb-ff-mult", type=int, default=2)
    parser.add_argument("--bb-radius", type=float, default=8.0)

    parser.add_argument("--expert-number-e", type=int, default=1)
    parser.add_argument("--expert-number-q", type=int, default=1)
    parser.add_argument("--expert-number-z", type=int, default=1)
    parser.add_argument("--expert-number-g", type=int, default=1)
    parser.add_argument("--topk-e", type=int, default=1)
    parser.add_argument("--topk-q", type=int, default=1)
    parser.add_argument("--topk-z", type=int, default=1)
    parser.add_argument("--topk-g", type=int, default=1)
    parser.add_argument("--expert-real-layers", type=int, default=1)
    parser.add_argument("--expert-int-layers", type=int, default=0)
    parser.add_argument("--expert-heads", type=int, default=4)
    parser.add_argument("--expert-ff-mult", type=int, default=2)
    parser.add_argument("--n-atom-types", type=int, default=95)

    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--loss-cutoff", type=float, default=2.0)
    parser.add_argument("--morse-D", type=float, default=1.0)
    parser.add_argument("--morse-a", type=float, default=1.0)

    parser.add_argument("--lambda-e", type=float, default=1.0)
    parser.add_argument("--lambda-e-desc", type=float, default=0.5)
    parser.add_argument("--lambda-q", type=float, default=1.0)
    parser.add_argument("--lambda-q-desc", type=float, default=0.5)
    parser.add_argument("--lambda-z", type=float, default=1.0)
    parser.add_argument("--lambda-z-desc", type=float, default=0.5)
    parser.add_argument("--lambda-dist", type=float, default=1.0)
    parser.add_argument("--lambda-angle", type=float, default=1.0)
    parser.add_argument("--lambda-torsion", type=float, default=2.0)

    parser.add_argument("--z-label-smooth", type=float, default=0.10)
    parser.add_argument("--z-focal-gamma", type=float, default=0.0)
    parser.add_argument("--z-temp", type=float, default=1.5)
    parser.add_argument("--z-class-balance", choices=["none", "batch_inv", "effective"], default="none")
    parser.add_argument("--z-entropy-reg", type=float, default=0.05)
    parser.add_argument("--z-logit-l2", type=float, default=1e-4)

    parser.add_argument("--std-ratio", type=float, default=0.2)
    parser.add_argument("--std-cap", type=int, default=128)
    return parser


def configure_logging(rank: int) -> None:
    level = logging.INFO if rank == 0 else logging.ERROR
    logging.basicConfig(level=level, format=f"[%(asctime)s][rank={rank}] %(levelname)s: %(message)s")
    logging.getLogger("multitask").setLevel(level)


def init_dist(backend: str) -> tuple[int, int, int, torch.device]:
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required for this smoke script.")

    rank = int(os.environ.get("RANK", "0"))
    world_size = int(os.environ.get("WORLD_SIZE", "1"))
    local_rank = int(os.environ.get("LOCAL_RANK", "0"))

    torch.cuda.set_device(local_rank)
    device = torch.device("cuda", local_rank)
    dist.init_process_group(backend=backend)
    return rank, world_size, local_rank, device


def cleanup_dist() -> None:
    if dist.is_available() and dist.is_initialized():
        dist.barrier()
        dist.destroy_process_group()


def max_across_ranks(value: float, device: torch.device) -> float:
    tensor = torch.tensor([value], dtype=torch.float64, device=device)
    dist.all_reduce(tensor, op=dist.ReduceOp.MAX)
    return float(tensor.item())


def dtype_from_name(name: str) -> torch.dtype:
    mapping = {
        "float16": torch.float16,
        "float32": torch.float32,
        "bfloat16": torch.bfloat16,
    }
    return mapping[name]


def patch_rank_local_output(rank: int) -> None:
    import pretrain.data as pretrain_data_mod
    import pretrain.train_loop as train_loop_mod

    original_train_loop_tqdm = train_loop_mod.tqdm
    original_data_tqdm = pretrain_data_mod.tqdm

    def rank_train_loop_tqdm(*args, **kwargs):
        kwargs.setdefault("disable", rank != 0)
        return original_train_loop_tqdm(*args, **kwargs)

    def rank_data_tqdm(*args, **kwargs):
        kwargs.setdefault("disable", rank != 0)
        return original_data_tqdm(*args, **kwargs)

    train_loop_mod.tqdm = rank_train_loop_tqdm
    pretrain_data_mod.tqdm = rank_data_tqdm


def build_model(args: argparse.Namespace, device: torch.device) -> MultiTaskMoE:
    from models.moe import MultiTaskMoE

    backbone_config = {
        "hidden_channels": args.hidden_channels,
        "atom_embedding_dim": args.hidden_channels,
        "bb_layers": args.bb_layers,
        "bb_heads": args.bb_heads,
        "bb_ff_mult": args.bb_ff_mult,
        "bb_use_dist_bias": True,
        "bb_use_radius_mask": False,
        "bb_radius": args.bb_radius,
    }

    model = MultiTaskMoE(
        backbone_config,
        n_atom_types=args.n_atom_types,
        n_experts_energy=args.expert_number_e,
        n_experts_charge=args.expert_number_q,
        n_experts_elem=args.expert_number_z,
        n_experts_geom=args.expert_number_g,
        top_k_energy=args.topk_e,
        top_k_charge=args.topk_q,
        top_k_elem=args.topk_z,
        top_k_geom=args.topk_g,
        expert_real_layers=args.expert_real_layers,
        expert_int_layers=args.expert_int_layers,
        expert_heads=args.expert_heads,
        expert_ff_mult=args.expert_ff_mult,
    ).to(device)
    return model


def attach_runtime_attrs(ddp_model: DDP, raw_model: MultiTaskMoE) -> None:
    ddp_model.graph_descriptor_names = raw_model.graph_descriptor_names
    ddp_model.charge_descriptor_specs = raw_model.charge_descriptor_specs
    ddp_model.element_descriptor_specs = raw_model.element_descriptor_specs
    ddp_model.pad_elem_index = raw_model.pad_elem_index
    ddp_model.n_atom_types = raw_model.n_atom_types


def build_optimizer(model: nn.Module, lr: float) -> torch.optim.Optimizer:
    decay, no_decay = [], []
    for name, param in model.named_parameters():
        target = no_decay if name.endswith("bias") or "norm" in name.lower() else decay
        target.append(param)

    return torch.optim.AdamW(
        [
            {"params": decay, "weight_decay": 0.01},
            {"params": no_decay, "weight_decay": 0.0},
        ],
        lr=lr,
        betas=(0.9, 0.95),
        eps=1e-8,
    )


def resolve_subset_bounds(args: argparse.Namespace, world_size: int) -> tuple[int, int, int]:
    requested = max(0, args.train_end - args.train_start + 1)
    required = args.steps * args.batch_size * world_size
    usable = min(requested, required)
    usable = (usable // (args.batch_size * world_size)) * (args.batch_size * world_size)
    if usable <= 0:
        raise ValueError(
            "Not enough samples for the requested DDP smoke test. "
            f"requested={requested}, required_per_global_epoch={required}"
        )
    end = args.train_start + usable - 1
    actual_steps = usable // (args.batch_size * world_size)
    return args.train_start, end, actual_steps


def build_ddp_loader(
    args: argparse.Namespace,
    rank: int,
    world_size: int,
) -> tuple[DataLoader, object, int]:
    from pretrain.data import (
        DomainWrapperDataset,
        MaskedPerturbDataset,
        OnlyStableWrapper,
        create_dataset,
        fast_collate,
    )
    from pretrain.degrade_molecules import DegradeConfig

    start_idx, end_idx, actual_steps = resolve_subset_bounds(args, world_size)
    base_dataset = OnlyStableWrapper(create_dataset(args.data_root, start_idx, end_idx))
    if len(base_dataset) <= 0:
        raise ValueError(f"Dataset is empty: {args.data_root} [{start_idx}, {end_idx}]")

    cfg = DegradeConfig(
        mode=args.perturb_mode,
        level=args.perturb_level,
        topo_replace_frac=args.perturb_replace_frac,
        topo_delete_frac=0.0,
        geom_noise_std=args.perturb_noise_std,
        geom_angle_std_deg=0.0,
        geom_bond_scale_std=0.0,
    )
    train_dataset = DomainWrapperDataset(
        MaskedPerturbDataset(base_dataset, cfg, seed=args.seed),
        domain_id=0,
    )

    sampler = DistributedSampler(
        train_dataset,
        num_replicas=world_size,
        rank=rank,
        shuffle=True,
        seed=args.seed,
        drop_last=True,
    )

    loader_kwargs = {
        "batch_size": args.batch_size,
        "sampler": sampler,
        "num_workers": args.num_workers,
        "pin_memory": True,
        "persistent_workers": False,
        "collate_fn": fast_collate,
    }
    if args.num_workers > 0:
        loader_kwargs["prefetch_factor"] = 2

    loader = DataLoader(train_dataset, **loader_kwargs)
    return loader, base_dataset, actual_steps


def build_std_payload(
    args: argparse.Namespace,
    base_dataset,
    rank: int,
) -> dict:
    from pretrain.data import standardizer

    return standardizer([base_dataset], ratio=args.std_ratio, cap=args.std_cap, seed=args.seed)


def run_allreduce_benchmark(
    args: argparse.Namespace,
    rank: int,
    world_size: int,
    device: torch.device,
) -> None:
    dtype = dtype_from_name(args.dtype)
    element_size = torch.tensor([], dtype=dtype).element_size()
    numel = max(1, (args.tensor_mb * 1024 * 1024) // element_size)
    tensor = torch.ones(numel, dtype=dtype, device=device)

    dist.barrier()
    for _ in range(args.warmup_iters):
        dist.all_reduce(tensor)
    torch.cuda.synchronize(device)
    dist.barrier()

    start_time = time.perf_counter()
    for _ in range(args.iters):
        dist.all_reduce(tensor)
    torch.cuda.synchronize(device)
    elapsed = time.perf_counter() - start_time
    elapsed = max_across_ranks(elapsed, device)

    avg_seconds = elapsed / max(1, args.iters)
    tensor_bytes = tensor.numel() * tensor.element_size()
    algbw_gbps = tensor_bytes / avg_seconds / 1e9
    busbw_gbps = algbw_gbps * (2.0 * (world_size - 1) / world_size)

    if rank == 0:
        payload = {
            "mode": "allreduce",
            "hostname": socket.gethostname(),
            "world_size": world_size,
            "dtype": args.dtype,
            "tensor_mb": args.tensor_mb,
            "iters": args.iters,
            "avg_ms": round(avg_seconds * 1000.0, 3),
            "algbw_gbps": round(algbw_gbps, 3),
            "busbw_gbps": round(busbw_gbps, 3),
        }
        print("[RESULT][allreduce] " + json.dumps(payload, ensure_ascii=True))


def run_pretrain_benchmark(
    args: argparse.Namespace,
    rank: int,
    world_size: int,
    local_rank: int,
    device: torch.device,
) -> None:
    import pretrain.train_loop as train_loop_mod
    from pretrain.train_loop import DummyScaler

    patch_rank_local_output(rank)
    torch.manual_seed(args.seed + rank)

    loader, base_dataset, actual_steps = build_ddp_loader(args, rank, world_size)
    std_payload = build_std_payload(args, base_dataset, rank)

    raw_model = build_model(args, device)
    ddp_model = DDP(raw_model, device_ids=[local_rank], output_device=local_rank, find_unused_parameters=False)
    attach_runtime_attrs(ddp_model, raw_model)
    optimizer = build_optimizer(ddp_model, args.lr)
    scaler = DummyScaler()

    sampler = loader.sampler
    if isinstance(sampler, DistributedSampler):
        sampler.set_epoch(args.seed)

    dist.barrier()
    torch.cuda.reset_peak_memory_stats(device)
    torch.cuda.synchronize(device)
    start_time = time.perf_counter()

    stats = train_loop_mod.run_epoch(
        ddp_model,
        loader,
        device,
        std_payload,
        scaler,
        loss_cutoff=args.loss_cutoff,
        n_atom_types=args.n_atom_types,
        lam_c=0.0,
        lam_d=args.lambda_dist,
        lam_a=args.lambda_angle,
        lam_t=args.lambda_torsion,
        lam_p=0.0,
        lam_e=args.lambda_e,
        lam_e_desc=args.lambda_e_desc,
        lam_q=args.lambda_q,
        lam_q_desc=args.lambda_q_desc,
        lam_z=args.lambda_z,
        lam_z_desc=args.lambda_z_desc,
        lam_bond_exist=1.0,
        lam_bond_order=1.0,
        z_label_smooth=args.z_label_smooth,
        z_focal_gamma=args.z_focal_gamma,
        z_temp=args.z_temp,
        z_class_balance=args.z_class_balance,
        z_entropy_reg=args.z_entropy_reg,
        z_logit_l2=args.z_logit_l2,
        morse_d=args.morse_D,
        morse_a=args.morse_a,
        stage1_max_steps=0,
        stage2_descriptor_ramp_steps=0,
        stage1_signal_decay_steps=0,
        stage1_signal_floor=1.0,
        optim=optimizer,
        amp_dtype="none",
        desc=f"ddp_smoke_r{rank}",
        scheduler=None,
        batch_logger=None,
        batch_log_interval=0,
        global_step_start=0,
    )

    torch.cuda.synchronize(device)
    elapsed = time.perf_counter() - start_time
    peak_mem_gb = torch.cuda.max_memory_allocated(device) / (1024 ** 3)

    elapsed = max_across_ranks(elapsed, device)
    peak_mem_gb = max_across_ranks(peak_mem_gb, device)

    if rank == 0:
        global_batch = args.batch_size * world_size
        samples_total = actual_steps * global_batch
        sec_per_step = elapsed / max(1, actual_steps)
        payload = {
            "mode": "pretrain",
            "hostname": socket.gethostname(),
            "world_size": world_size,
            "data_root": args.data_root,
            "train_start": args.train_start,
            "train_end": args.train_start + samples_total - 1,
            "steps_per_rank": actual_steps,
            "local_batch_size": args.batch_size,
            "global_batch_size": global_batch,
            "samples_total": samples_total,
            "elapsed_sec": round(elapsed, 3),
            "sec_per_step": round(sec_per_step, 3),
            "samples_per_sec": round(samples_total / elapsed, 3),
            "peak_mem_gb_max": round(peak_mem_gb, 3),
            "loss_energy_rank0": round(float(stats["E"]), 6),
            "loss_charge_rank0": round(float(stats["Q"]), 6),
            "loss_elem_rank0": round(float(stats["Z"]), 6),
            "loss_geom_rank0": round(float(stats["Geom"]), 6),
            "loss_balance_rank0": round(float(stats["Bal"]), 6),
            "global_steps_rank0": int(stats["global_step"]),
        }
        print("[RESULT][pretrain_ddp] " + json.dumps(payload, ensure_ascii=True))


def main() -> None:
    args = build_parser().parse_args()
    rank = world_size = local_rank = 0
    device = torch.device("cpu")

    try:
        rank, world_size, local_rank, device = init_dist(args.backend)
        configure_logging(rank)

        if rank == 0:
            LOGGER.info(
                "Starting %s benchmark on %s with world_size=%d",
                args.mode,
                socket.gethostname(),
                world_size,
            )

        if args.mode == "allreduce":
            run_allreduce_benchmark(args, rank, world_size, device)
        else:
            run_pretrain_benchmark(args, rank, world_size, local_rank, device)
    finally:
        cleanup_dist()


if __name__ == "__main__":
    main()
