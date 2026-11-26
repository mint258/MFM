"""A5 repaired caller contracts; no source reads before runtime validation."""
import math

def require_runtime_configuration(c):
    unit = c.get("work_unit_seconds")
    if isinstance(unit, bool) or not isinstance(unit, (int, float)) or not math.isfinite(unit) or unit <= 0:
        raise ValueError("Explicit positive work_unit_seconds required before source reads")
    if c.get("cleanup_seconds", 0) < 180:
        raise ValueError("Actual allocation cleanup reserve required")
    return c

def open_native_store(reference, reader=None):
    if reader is None:
        from phychem_mfm.phase1.v3_dev_store import TrainOnlyPackedStore
        reader = TrainOnlyPackedStore
    return reader(reference["path"], expected_sha256=reference["sha256"])

