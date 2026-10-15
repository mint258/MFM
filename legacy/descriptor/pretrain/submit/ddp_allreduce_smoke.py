from __future__ import annotations

import argparse
import json
import os
import socket
import time

import torch
import torch.distributed as dist


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser("NCCL all-reduce smoke benchmark for DDP bring-up")
    parser.add_argument("--backend", default="nccl")
    parser.add_argument("--tensor-mb", type=int, default=256)
    parser.add_argument("--warmup-iters", type=int, default=10)
    parser.add_argument("--iters", type=int, default=30)
    parser.add_argument("--dtype", choices=["float16", "float32", "bfloat16"], default="float32")
    return parser


def dtype_from_name(name: str) -> torch.dtype:
    mapping = {
        "float16": torch.float16,
        "float32": torch.float32,
        "bfloat16": torch.bfloat16,
    }
    return mapping[name]


def max_across_ranks(value: float, device: torch.device) -> float:
    tensor = torch.tensor([value], dtype=torch.float64, device=device)
    dist.all_reduce(tensor, op=dist.ReduceOp.MAX)
    return float(tensor.item())


def main() -> None:
    args = build_parser().parse_args()
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required for ddp_allreduce_smoke.py.")

    rank = int(os.environ.get("RANK", "0"))
    world_size = int(os.environ.get("WORLD_SIZE", "1"))
    local_rank = int(os.environ.get("LOCAL_RANK", "0"))

    torch.cuda.set_device(local_rank)
    device = torch.device("cuda", local_rank)
    dist.init_process_group(backend=args.backend, init_method="env://")

    try:
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
            nccl_version = None
            if hasattr(torch.cuda, "nccl") and hasattr(torch.cuda.nccl, "version"):
                try:
                    nccl_version = torch.cuda.nccl.version()
                except Exception:
                    nccl_version = None

            payload = {
                "mode": "allreduce",
                "hostname": socket.gethostname(),
                "world_size": world_size,
                "local_world_size": int(os.environ.get("LOCAL_WORLD_SIZE", world_size)),
                "dtype": args.dtype,
                "tensor_mb": args.tensor_mb,
                "warmup_iters": args.warmup_iters,
                "iters": args.iters,
                "avg_ms": round(avg_seconds * 1000.0, 3),
                "algbw_gbps": round(algbw_gbps, 3),
                "busbw_gbps": round(busbw_gbps, 3),
                "torch_version": torch.__version__,
                "cuda_device_name": torch.cuda.get_device_name(local_rank),
                "nccl_version": nccl_version,
            }
            print("[RESULT][allreduce] " + json.dumps(payload, ensure_ascii=True))
    finally:
        dist.barrier()
        dist.destroy_process_group()


if __name__ == "__main__":
    main()
