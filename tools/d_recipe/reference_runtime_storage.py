"""Keep original local physical write checks after canonical phase admission."""
from contextlib import contextmanager
from pathlib import Path
import os


def local_runtime_guard(root, *, guard_class):
    # Canonical admission already covered the remaining whole-phase budget.
    # Reuse Guard's original runtime margin, reserve and device/inode checks;
    # neither legacy peer forecasts nor repeated canonical admission are read.
    return guard_class(dict(poll_seconds=5, targets=[dict(
        paths=[str(Path(root).resolve())], peak_additional_bytes=0,
        peak_additional_inodes=0, reserve_bytes=10 * 2**30,
        reserve_inodes=10000, concurrent_bytes=0, concurrent_inodes=0,
        runtime_margin_bytes=2**26, runtime_margin_inodes=1000,
        quota_scope="not_applicable")]), admit=False)


def shared_runtime_guard(path, *, guard_class, quota_snapshot):
    """Original NFS physical/quota floors just before the final small copy."""
    return guard_class(dict(poll_seconds=5, targets=[dict(
        paths=[str(Path(path).resolve())], peak_additional_bytes=0,
        peak_additional_inodes=0, reserve_bytes=100_000_000_000,
        reserve_inodes=10000, concurrent_bytes=0, concurrent_inodes=0,
        runtime_margin_bytes=8 * 2**30, runtime_margin_inodes=1000,
        quota_scope="limited", quota_peak_additional_bytes=0,
        quota_concurrent_bytes=0, quota_reserve_bytes=100_000_000_000,
        quota_available_reference=str(quota_snapshot), quota_max_age_seconds=5,
        quota_expected_uid=os.getuid(), quota_expected_filesystem="/share")]), admit=False)


@contextmanager
def scoped_physical_writes(resources, root):
    root = Path(root).resolve()
    physical = local_runtime_guard(root, guard_class=resources.Guard)
    previous = resources.admit_output

    def checked(configuration, path):
        if not Path(path).resolve().is_relative_to(root):
            raise ValueError("Collector write escaped its admitted local phase")
        return physical.check(path)

    try:
        resources.admit_output = checked
        yield
    finally:
        resources.admit_output = previous
