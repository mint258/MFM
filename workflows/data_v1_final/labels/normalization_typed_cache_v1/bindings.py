"""Real frozen function objects; no altered science or module monkeypatch."""
from __future__ import annotations

from workflows.data_v1_final.labels.normalization_cache_v2 import reader as cache
from workflows.data_v1_final.labels.normalization_cache_v1 import reader as cache_original
from workflows.data_v1_final.labels.normalization_cache_v1 import profile as original_profile
from workflows.data_v1_final.labels.lossless_projection_pilot_v1 import projection
from workflows.data_v1_final.labels.streaming_v1 import calibration, compact
from workflows.data_v1_final.labels.normalization_v1 import series, moments

base_metadata = cache.base_metadata
projected_decode = cache.projected_decode
entries = cache.entries
RadixCounts = calibration.RadixCounts
advance = calibration.advance
initial_queries = calibration.initial_queries
TSQR = calibration.TSQR
merge_qr = calibration.merge_qr
WinsorMoments = calibration.WinsorMoments
train_values = calibration.train_values
views = series.views
inventory = series.inventory
energy_residual = series.energy_residual
JointMoments = moments.JointMoments
combine = moments.combine
combine_joint = moments.combine_joint


def verify_function_objects():
    checks = {
        "projected_decode_is_frozen": projected_decode is cache_original.projected_decode,
        "entries_is_frozen": entries is cache_original.entries,
        "projection_decode_is_frozen": cache_original.decode is projection.decode,
        "profile_TSQR_is_original": original_profile.TSQR is TSQR,
        "profile_RadixCounts_is_original": original_profile.RadixCounts is RadixCounts,
        "profile_entry_kernel_is_original": original_profile.entries is entries,
        "element_reference_is_original": merge_qr is calibration.merge_qr,
        "moment_classes_are_original": WinsorMoments is calibration.WinsorMoments and JointMoments is moments.JointMoments,
        "series_views_are_original": views is series.views,
    }
    if not all(checks.values()):
        raise ValueError("FROZEN_FUNCTION_OBJECT_IDENTITY_DIFFERS")
    return {"status": "ACTUAL_FROZEN_FUNCTION_OBJECT_BINDINGS", "checks": checks,
            "TSQR_chunk": 256, "QR_reduction": "original ordered left fold",
            "science_functions_copied_or_patched": False}
