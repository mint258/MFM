from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
import torch

from phychem_mfm.training.losses import StageSchedule, masked_binary_loss, standardized_huber


def _legacy_helpers():
    root = Path(
        os.environ.get(
            "PHYCHEM_LEGACY_ROOT",
            "/share/home/zixiao/descriptor_analysis/modern_ML_representation/support_scripts/MFM_descriptor",
        )
    )
    if not root.exists():
        pytest.skip(f"Legacy reference unavailable: {root}")
    sys.path.insert(0, str(root))
    try:
        from pretrain.train_loop import (
            _descriptor_ramp,
            _masked_binary_loss_and_acc,
            _stage1_signal_scale,
            _standardized_huber,
        )
    finally:
        sys.path.pop(0)
    return _descriptor_ramp, _masked_binary_loss_and_acc, _stage1_signal_scale, _standardized_huber


def test_loss_mask_normalization_and_weighting_parity():
    _, old_binary, _, old_huber = _legacy_helpers()
    pred = torch.tensor([[1.2], [-0.4], [0.8]])
    target = torch.tensor([[0.1], [0.3], [-0.2]])
    mask = torch.tensor([[1.0], [0.0], [1.0]])
    old_raw = old_huber(pred, target, mask, mean=0.25, std_value=1.7)
    new_raw = standardized_huber(pred, target, mask, mean=0.25, std_value=1.7)
    torch.testing.assert_close(new_raw, old_raw, rtol=0.0, atol=1e-7)
    torch.testing.assert_close(new_raw * 0.25, old_raw * 0.25, rtol=0.0, atol=1e-7)

    logits = torch.tensor([[2.0], [-1.0], [0.5]])
    labels = torch.tensor([[1.0], [0.0], [0.0]])
    old_value, _ = old_binary(logits, labels, mask)
    new_value = masked_binary_loss(logits, labels, mask)
    torch.testing.assert_close(new_value, old_value, rtol=0.0, atol=1e-7)


def test_ramp_and_stage_scale_parity():
    old_ramp, _, old_stage, _ = _legacy_helpers()
    schedule = StageSchedule(15000, 5000, 5000, 0.3)
    for step in (0, 14999, 15000, 16000, 19999, 20000, 25000):
        assert schedule.descriptor_scale(step) == old_ramp(step, 15000, 5000)
        assert schedule.stage1_scale(step) == old_stage(step, 15000, 5000, 0.3)
