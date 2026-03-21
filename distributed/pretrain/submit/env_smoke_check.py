from __future__ import annotations

import argparse
import importlib
import json
import sys
import warnings
from pathlib import Path

import torch


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


REQUIRED_MODULES = [
    "torch",
    "torch_geometric",
    "lmdb",
    "rdkit",
    "wandb",
    "numpy",
    "sklearn",
    "tqdm",
    "periodictable",
]

OPTIONAL_ACCEL_MODULES = [
    "pyg_lib",
    "torch_scatter",
    "torch_sparse",
    "torch_cluster",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser("Repo-specific environment smoke check")
    parser.add_argument("--data-root", default="test_data/principal_valid_test.lmdb")
    parser.add_argument("--train-start", type=int, default=875)
    parser.add_argument("--train-end", type=int, default=878)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    parser.add_argument("--strict-optional", action="store_true")
    return parser.parse_args()


def choose_device(spec: str) -> str:
    if spec == "cpu":
        return "cpu"
    if spec == "cuda":
        if not torch.cuda.is_available():
            raise RuntimeError("--device cuda was requested, but CUDA is not available.")
        return "cuda"
    return "cuda" if torch.cuda.is_available() else "cpu"


def print_json(prefix: str, payload: dict) -> None:
    print(f"{prefix} {json.dumps(payload, ensure_ascii=True, sort_keys=True)}")


def import_and_report(module_name: str, *, required: bool) -> tuple[bool, str]:
    try:
        module = importlib.import_module(module_name)
        version = getattr(module, "__version__", "unknown")
        print_json(
            "[IMPORT]",
            {"module": module_name, "ok": True, "required": required, "version": str(version)},
        )
        return True, str(version)
    except Exception as exc:
        print_json(
            "[IMPORT]",
            {"module": module_name, "ok": False, "required": required, "error": repr(exc)},
        )
        return False, repr(exc)


def run_import_checks(strict_optional: bool) -> None:
    missing_required = []
    failing_optional = []

    for name in REQUIRED_MODULES:
        ok, _ = import_and_report(name, required=True)
        if not ok:
            missing_required.append(name)

    for name in OPTIONAL_ACCEL_MODULES:
        ok, _ = import_and_report(name, required=False)
        if not ok:
            failing_optional.append(name)

    if missing_required:
        raise RuntimeError(f"Missing required Python modules: {missing_required}")

    if strict_optional and failing_optional:
        raise RuntimeError(f"Optional acceleration modules failed strict check: {failing_optional}")


def run_repo_smoke(args: argparse.Namespace, device: str) -> None:
    from dataset.dataset_lmdb import LmdbMoleculeDataset
    from models.moe import MultiTaskMoE
    from pretrain.data import DomainWrapperDataset, MaskedPerturbDataset, OnlyStableWrapper, fast_collate
    from pretrain.degrade_molecules import DegradeConfig

    data_root = Path(args.data_root)
    if not data_root.exists():
        raise FileNotFoundError(f"Data root does not exist: {data_root}")

    base_dataset = OnlyStableWrapper(
        LmdbMoleculeDataset(
            str(data_root),
            start_idx=args.train_start,
            end_idx=args.train_end,
            filter_missing_on_init=True,
        )
    )
    if len(base_dataset) < args.batch_size:
        raise RuntimeError(
            f"Dataset slice is too small for batch_size={args.batch_size}: len={len(base_dataset)}"
        )

    cfg = DegradeConfig(mode="both", level=0.5).finalize()
    wrapped = DomainWrapperDataset(MaskedPerturbDataset(base_dataset, cfg, seed=0), domain_id=0)
    samples = [wrapped[i] for i in range(args.batch_size)]
    batch = fast_collate(samples).to(device)

    print_json(
        "[DATA]",
        {
            "data_root": str(data_root),
            "slice": [args.train_start, args.train_end],
            "dataset_len": len(base_dataset),
            "batch_num_graphs": int(batch.num_graphs),
            "num_nodes": int(batch.x.size(0)),
            "device": device,
        },
    )

    model = MultiTaskMoE(
        {
            "hidden_channels": 64,
            "atom_embedding_dim": 64,
            "bb_layers": 3,
            "bb_heads": 4,
            "bb_ff_mult": 2,
            "bb_use_dist_bias": True,
            "bb_use_radius_mask": False,
            "bb_radius": 8.0,
        },
        n_atom_types=95,
        n_experts_energy=1,
        n_experts_charge=1,
        n_experts_elem=1,
        n_experts_geom=1,
        top_k_energy=1,
        top_k_charge=1,
        top_k_elem=1,
        top_k_geom=1,
        expert_real_layers=1,
        expert_int_layers=0,
        expert_heads=4,
        expert_ff_mult=2,
    ).to(device)
    model.eval()

    with torch.no_grad():
        outputs = model(batch)

    print_json(
        "[FORWARD]",
        {
            "coords": list(outputs["coords"].shape),
            "charge_mask": list(outputs["charge_mask"].shape),
            "node_mask": list(outputs["node_mask"].shape),
            "energy_keys": sorted(outputs["energy"].keys()),
            "charge_keys": sorted(outputs["charge"].keys()),
            "element_keys": sorted(outputs["element"].keys()),
        },
    )

    total_params = sum(p.numel() for p in model.parameters())
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print_json(
        "[MODEL]",
        {
            "total_params": int(total_params),
            "trainable_params": int(trainable_params),
            "device": device,
            "cuda_available": bool(torch.cuda.is_available()),
        },
    )


def main() -> None:
    args = parse_args()
    device = choose_device(args.device)
    print_json(
        "[ENV]",
        {
            "python": sys.executable,
            "python_version": sys.version.split()[0],
            "torch_version": torch.__version__,
            "device": device,
            "cuda_available": bool(torch.cuda.is_available()),
            "cuda_device_count": int(torch.cuda.device_count()),
        },
    )

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        run_import_checks(args.strict_optional)
        for item in caught:
            print_json("[WARNING]", {"category": item.category.__name__, "message": str(item.message)})

    run_repo_smoke(args, device)
    print("[SUCCESS] environment smoke check passed")


if __name__ == "__main__":
    main()
