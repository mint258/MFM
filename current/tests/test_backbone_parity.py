from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
import torch

from phychem_mfm.model.backbone import RealCoordTransformerBackbone as NewBackbone


def test_backbone_parity(mixed_real_batch):
    legacy_root = Path(
        os.environ.get(
            "PHYCHEM_LEGACY_ROOT",
            "/share/home/zixiao/descriptor_analysis/modern_ML_representation/support_scripts/MFM_descriptor",
        )
    )
    if not legacy_root.exists():
        pytest.skip(f"Legacy reference unavailable: {legacy_root}")
    sys.path.insert(0, str(legacy_root))
    try:
        from models.moe.backbone import RealCoordTransformerBackbone as OldBackbone
    finally:
        sys.path.pop(0)

    torch.manual_seed(123)
    old = OldBackbone(95, 32, layers=2, heads=4, ff_mult=2, dropout=0.0).eval()
    new = NewBackbone(95, 32, layers=2, heads=4, ff_mult=2, dropout=0.0).eval()
    new.load_state_dict(old.state_dict(), strict=True)
    with torch.no_grad():
        old_h0 = old(mixed_real_batch)
        new_h0 = new(mixed_real_batch)
    torch.testing.assert_close(new_h0, old_h0, rtol=0.0, atol=0.0)
