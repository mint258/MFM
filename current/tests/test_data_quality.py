import json
from pathlib import Path
from types import SimpleNamespace

import torch

from tools.build_quality_filtered_manifests import outside_robust_band, quality_reasons


def _policy():
    path = Path(__file__).parents[1] / "configs" / "iclr2027" / "data_quality_policy_v3.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _item(**updates):
    values = {
        "x": torch.tensor([6, 8]),
        "pos": torch.zeros((2, 3)),
        "energy": -100.0,
        "energy_unit": "kcal/mol",
        "y": torch.tensor([[0.1], [-0.1]]),
        "charge_mask": torch.ones((2, 1), dtype=torch.bool),
        "rdkit_graph_desc": torch.zeros(31),
        "rdkit_graph_desc_mask": torch.ones(31, dtype=torch.bool),
    }
    values.update(updates)
    return SimpleNamespace(**values)


def test_robust_quality_policy_keeps_normal_records_and_quarantines_gross_failures():
    policy = _policy()
    assert not quality_reasons(_item(), "principal", policy, 196)
    reasons = quality_reasons(_item(energy=500000.0), "principal", policy, 196)
    assert "energy_domain_robust_outlier" in reasons
    assert "energy_per_atom_robust_outlier" in reasons
    assert "atomic_charge_robust_outlier" in quality_reasons(
        _item(y=torch.tensor([[-15.0], [0.1]])), "principal", policy, 196
    )


def test_robust_band_uses_frozen_median_mad_scale():
    spec = {"median": 2.0, "robust_sigma": 3.0, "robust_sigma_multiplier": 4.0}
    assert not outside_robust_band(14.0, spec)
    assert outside_robust_band(14.01, spec)
