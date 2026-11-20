"""Reuse the data-line process guard with current D/NFS peer reservations.

No scheduler or process-control implementation is duplicated. The inherited
guard pauses only its own launched process group and preserves partial output.
"""
import argparse
import json
import os
from pathlib import Path
import platform
import sys

from workflows.data_v1_final.export.v31_stream_v1.disk_guard import DiskUnavailable, Guard
from workflows.data_d_descriptors.storage import guard as share_admission


def protection_plan(configuration):
    peak = configuration["storage_peak_bytes"]
    if type(peak) is not int or peak <= 0:
        raise ValueError("Explicit positive D storage peak required")
    common = dict(peak_additional_inodes=10000, reserve_inodes=10000,
                  concurrent_bytes=0, concurrent_inodes=0,
                  runtime_margin_bytes=2**26, runtime_margin_inodes=1000)
    root = dict(common, paths=["/"], peak_additional_bytes=0,
                reserve_bytes=10 * 2**30, quota_scope="not_applicable")
    share = dict(common, paths=[str(Path(configuration["output"]).resolve())],
        peak_additional_bytes=peak, reserve_bytes=100_000_000_000,
        quota_scope="limited", quota_peak_additional_bytes=peak,
        quota_concurrent_bytes=0, quota_reserve_bytes=100_000_000_000,
        quota_available_reference="/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/window2_20261105/share_quota_available_v3.json",
        quota_expected_uid=os.getuid(), quota_expected_filesystem="/share", quota_max_age_seconds=5)
    return dict(poll_seconds=5, targets=[root, share])


class DJointGuard(Guard):
    def __init__(self, configuration):
        self.configuration = configuration
        super().__init__(protection_plan(configuration))
        self.check(configuration["output"])

    def check(self, path, bytes_needed=0, inodes_needed=0):
        try:
            # Check both actual filesystems, even though the child writes its
            # model output on NFS. Root reserve is max(10GiB,10%) in Guard.
            for target in self.targets:
                self.check_target(target, bytes_needed=bytes_needed, inodes_needed=inodes_needed)
            # Refresh the real shared UID quota and remaining peer forecasts.
            # Do not freeze B0's initial future as its databases grow.
            share_admission(path, peak_bytes=self.configuration["storage_peak_bytes"])
        except DiskUnavailable:
            raise
        except Exception as error:
            raise DiskUnavailable("D target capacity or joint reservation unavailable: " + str(error)) from error


def execution_site(configuration, *, cpu):
    """Apply the same node/allocation policy to parent and direct entries."""
    node = platform.node().split(".")[0]
    allowed = ({"compute-0-" + str(i) for i in range(8, 20)} if cpu else
               {"compute-0-" + str(i) for i in (*range(8), 20, 22)})
    native = configuration.get("execution") == "native_SSH"
    if node not in allowed or (native and (cpu or node not in ("compute-0-20", "compute-0-22"))):
        raise RuntimeError("D resource guard is on the wrong registered execution node")
    if not native and not os.environ.get("SLURM_JOB_ID"):
        raise RuntimeError("A real Slurm allocation is required")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("train", "cpu_statistics", "diagnostic_forward", "diagnostic_statistics", "layer_readouts", "development_panel"))
    parser.add_argument("--configuration", required=True)
    arguments = parser.parse_args()
    configuration = json.loads(Path(arguments.configuration).read_text(encoding="utf-8"))
    cpu = arguments.command in ("cpu_statistics", "diagnostic_statistics") or (
        arguments.command in ("layer_readouts", "development_panel") and configuration.get("phase") == "cpu")
    execution_site(configuration, cpu=cpu)
    guard = DJointGuard(configuration)
    guard.run([sys.executable, "-B", "-m", "tools.d_recipe." + arguments.command,
               "--configuration", arguments.configuration], configuration["output"])


if __name__ == "__main__":
    main()
