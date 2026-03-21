from __future__ import annotations

import argparse
import os
import socket
import sys
from pathlib import Path

import torch.distributed as dist
import torch.multiprocessing as mp


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser("Local CPU DDP smoke launcher for distributed.pretrain.pipeline")
    parser.add_argument("--nproc", type=int, default=2)
    parser.add_argument("--data-root", default="test_data/principal_valid_test.lmdb")
    parser.add_argument("--train-start", type=int, default=875)
    parser.add_argument("--train-end", type=int, default=890)
    parser.add_argument("--val-start", type=int, default=891)
    parser.add_argument("--val-end", type=int, default=894)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--save-path", default="distributed/tmp/ddp_cpu_smoke.pt")
    return parser.parse_args()


def pick_free_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def assert_local_gloo_supported() -> None:
    try:
        dist.ProcessGroupGloo.create_device(hostname="127.0.0.1")
    except Exception as exc:
        raise RuntimeError(
            "This local PyTorch build does not expose a usable Gloo CPU device on Windows, "
            "so a real multi-process DDP smoke test cannot run here. "
            "Use Linux/WSL with PyTorch distributed support, or run the distributed smoke on the target server."
        ) from exc


def build_argv(args: argparse.Namespace) -> list[str]:
    return [
        "distributed.pretrain.pipeline",
        "--distributed",
        "--device",
        "cpu",
        "--data_roots",
        args.data_root,
        "--starts",
        str(args.train_start),
        "--ends",
        str(args.train_end),
        "--val_data_roots",
        args.data_root,
        "--val_starts",
        str(args.val_start),
        "--val_ends",
        str(args.val_end),
        "--epochs",
        "1",
        "--batch_size",
        str(args.batch_size),
        "--num_workers",
        "0",
        "--hidden_channels",
        "32",
        "--bb_layers",
        "2",
        "--bb_heads",
        "4",
        "--bb_ff_mult",
        "2",
        "--expert_number_E",
        "2",
        "--expert_number_Q",
        "2",
        "--expert_number_Z",
        "2",
        "--expert_number_G",
        "2",
        "--topkE",
        "1",
        "--topkQ",
        "1",
        "--topkZ",
        "1",
        "--topkG",
        "1",
        "--expert_real_layers",
        "1",
        "--expert_int_layers",
        "0",
        "--expert_heads",
        "4",
        "--expert_ff_mult",
        "2",
        "--lambda_e",
        "1.0",
        "--lambda_e_desc",
        "0.5",
        "--lambda_q",
        "1.0",
        "--lambda_q_desc",
        "0.5",
        "--lambda_z",
        "1.0",
        "--lambda_z_desc",
        "0.5",
        "--lambda_dist",
        "1.0",
        "--lambda_angle",
        "1.0",
        "--lambda_torsion",
        "2.0",
        "--stage1_loss",
        "0.1",
        "--stage1_max_epochs",
        "10",
        "--loss_cutoff",
        "2.0",
        "--perturb_mode",
        "both",
        "--perturb_level",
        "0.5",
        "--save_path",
        args.save_path,
    ]


def worker(rank: int, world_size: int, port: int, argv: list[str]) -> None:
    os.environ["MASTER_ADDR"] = "127.0.0.1"
    os.environ["MASTER_PORT"] = str(port)
    os.environ["WORLD_SIZE"] = str(world_size)
    os.environ["RANK"] = str(rank)
    os.environ["LOCAL_RANK"] = str(rank)
    os.environ["USE_LIBUV"] = "0"

    sys.argv = argv
    from distributed.pretrain.pipeline import main

    main()


def main() -> None:
    args = parse_args()
    os.chdir(REPO_ROOT)
    assert_local_gloo_supported()
    port = pick_free_port()
    argv = build_argv(args)
    mp.spawn(worker, args=(args.nproc, port, argv), nprocs=args.nproc, join=True)
    print("LOCAL_CPU_DDP_SMOKE_OK")


if __name__ == "__main__":
    main()
