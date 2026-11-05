"""Small synthetic domain builders; no real release, statistic or joint ACK."""
import torch

from phychem_mfm.phase1.v3_label_domains import (
    ChannelCodebook, ordered_entries_from_f64, tensor6_from_f64)

REF = {"path": "/unit-only/not-a-real-release.json", "bytes": 1, "sha256": "a" * 64}
FRAME = {"unit": "fixture-unit", "sign": "fixture-sign", "frame": "fixture-source-frame",
         "origin_policy": "fixture-declared-source-origin", "target_id": "fixture-r73",
         "condition": "fixture-condition", "joint_policy": REF}


def ordered_target():
    return ordered_entries_from_f64(values=torch.tensor([[0.], [0.], [0.], [float("nan")]], dtype=torch.float64),
        source_valid=torch.tensor([True, True, True, False]),
        atom_index=torch.tensor([[0, 0, 1, 0], [0, 0, 0, 1]]),
        channel_index=torch.tensor([[0, 0, 1, 2], [1, 1, 0, 0]]), entry_ordinal=torch.arange(4),
        n_atoms=2, geometry_id="g0", geometry_ref=REF,
        frame_origin=torch.tensor([[.5, -1., 2.]], dtype=torch.float32),
        frame_basis=torch.tensor([[[0., 1., 0.], [-1., 0., 0.], [0., 0., 1.]]], dtype=torch.float32),
        codebook=ChannelCodebook(("SIGMA", "DEL", "DELL"), REF), frame_binding=FRAME,
        reasons=({}, {}, {}, {"source_missing": True}), source_ref=REF)


def tensor_target():
    return tensor6_from_f64(
        values=torch.tensor([[0.] * 6, [0., float("nan"), 0., 0., 0., 0.], [0.] * 6], dtype=torch.float64),
        component_valid=torch.tensor([[True] * 6, [True, False, True, True, True, True], [True] * 6]),
        geometry_ids=("g0", "g1", "g2"),
        component_geometry_ids=(("g0",) * 6, ("g1",) * 6, ("g2",) * 5 + ("wrong-geometry",)),
        reasons=({}, {"original_component_missing": "xy"}, {"geometry_mismatch": "zz"}), source_ref=REF)
