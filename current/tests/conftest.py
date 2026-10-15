from __future__ import annotations

import os
from pathlib import Path

import pytest
import torch

from phychem_mfm.factory import build_model
from phychem_mfm.training.data import fast_collate
from phychem_mfm.training.datasets import build_pilot_data


@pytest.fixture(scope="session")
def data_root() -> Path:
    path = Path(os.environ.get("PHYCHEM_TEST_DATA_ROOT", "/share/home/zixiao/dataset/lmdb_new"))
    if not path.exists():
        pytest.skip(f"Real LMDB test data unavailable: {path}")
    return path


@pytest.fixture(scope="session")
def real_data_bundle(data_root):
    return build_pilot_data(
        data_root,
        train_limit=16,
        val_limit=4,
        batch_size=4,
        num_workers=0,
        seed=7,
        standardizer_cap=16,
    )


@pytest.fixture(scope="session")
def mixed_real_batch(real_data_bundle):
    dataset = real_data_bundle.train_dataset
    parts = dataset.datasets
    samples = [parts[0][0], parts[1][0], parts[3][0], parts[4][0]]
    return fast_collate(samples)


def small_config(route: str = "light") -> dict:
    return {
        "architecture": {"preset": f"shared_{route}", "task_route": route},
        "backbone": {
            "n_atom_types": 95,
            "dim": 32,
            "layers": 1,
            "heads": 4,
            "ff_mult": 2,
            "dropout": 0.0,
            "use_dist_bias": True,
            "use_radius_mask": False,
            "radius": 8.0,
        },
        "expert": {"real_layers": 1, "internal_layers": 0, "heads": 4, "ff_mult": 2, "dropout": 0.0},
        "head": {"bond_negative_ratio": 1.0},
        "supervision": {"variant": "SPD"},
        "loss": {},
        "schedule": {},
        "optimizer": {"lr": 3e-5, "weight_decay": 0.01, "betas": [0.9, 0.95], "grad_clip_norm": 1.0},
        "training": {"seed": 0},
    }


@pytest.fixture(params=("light", "expert"))
def small_model(request):
    torch.manual_seed(11)
    return build_model(small_config(request.param), preset=request.param)
