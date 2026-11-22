"""Reuse data-line process control and existing NFS/model-disk admission.

No scheduler or process-control implementation is duplicated. The inherited
guard pauses only its own launched process group and preserves partial output.
"""
import argparse
from functools import lru_cache
import importlib.util
import json
import os
from pathlib import Path
import platform
import stat
import sys

from workflows.data_v1_final.export.v31_stream_v1.disk_guard import DiskUnavailable, Guard
from workflows.data_d_descriptors.storage import guard as share_admission


@lru_cache(maxsize=1)
def _peer_storage_module(root):
    path = Path(root) / "tools/p_heads/h_resources.py"
    spec = importlib.util.spec_from_file_location("d_existing_shared_storage", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def peer_share_admission(configuration):
    """Reuse the live peer observer's already registered closeout/followup budgets.

    Only its read-only capacity function is called. Its watchdog and process
    control are not started; all D process control remains with this guard.
    """
    root = configuration.get("peer_storage_guard_root")
    if not root:
        return None
    directory = str(Path(root) / "tools/p_heads")
    sys.path.insert(0, directory)
    try:
        return _peer_storage_module(root).guard(force=True)
    finally:
        sys.path.remove(directory)


def storage_locations(configuration):
    """Lustre outputs opt in; their NFS control growth remains independent."""
    filesystem = configuration.get("output_filesystem", "/share")
    if filesystem == "/share":
        return filesystem, configuration["output"], configuration["storage_peak_bytes"]
    if filesystem not in ("/lfshome", "node_local"):
        raise ValueError("Use /share, /lfshome or an explicit node-local output")
    if filesystem == "/lfshome":
        root = Path(configuration["model_budget_root"]).resolve()
        base = Path("/lfshome/zixiao/model_v31_20261105").resolve()
        if root.parent != base or not Path(configuration["output"]).resolve().is_relative_to(root):
            raise ValueError("D model output must stay in its registered direct model-pool root")
    elif not Path(configuration["output"]).resolve().is_relative_to(local_scope(configuration)):
        raise ValueError("Node-local output must stay in its own D scratch root")
    share = Path(configuration["share_output"]).resolve()
    if not share.is_relative_to(Path("/share/home/zixiao/descriptor_analysis").resolve()):
        raise ValueError("NFS control output must stay in the existing shared project")
    peak = configuration["share_storage_peak_bytes"]
    if type(peak) is not int or peak <= 0:
        raise ValueError("Explicit positive joint NFS forecast required for Lustre output")
    if filesystem == "/lfshome":
        other = configuration["lustre_other_future_bytes"]
        if type(other) is not int or other < 6_000_000_000:
            raise ValueError("Retain the native model guard's 6GB other-future reserve")
    return filesystem, str(share), peak


def local_scope(configuration):
    root = Path(configuration["local_output_root"]).resolve()
    peak = configuration["local_storage_peak_bytes"]
    if (root.parent != Path("/tmp").resolve() or not root.name.startswith("d_recipe_")
            or type(peak) is not int or peak <= 0):
        raise ValueError("Explicit D-owned /tmp scope and positive local peak required")
    return root


def allocated_local_bytes(root):
    """Credit only owned regular-file blocks, once per inode; never follow links."""
    seen, allocated = set(), 0
    for path in Path(root).rglob("*"):
        try:
            info = path.lstat()
        except FileNotFoundError:
            continue
        identity = (info.st_dev, info.st_ino)
        if stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and identity not in seen:
            seen.add(identity)
            allocated += min(info.st_size, info.st_blocks * 512)
    return allocated


def remaining_local_bytes(configuration):
    if not configuration.get("local_output_root"):
        return 0
    peak = configuration["local_storage_peak_bytes"]
    # The native model guard's 8GiB serialization margin also bounds local
    # cache bursts. Small CPU collections retain their entire smaller peak.
    return max(min(peak, 8 * 2**30), peak - allocated_local_bytes(local_scope(configuration)))


def model_admission(configuration, path, *, native=None):
    """Consume the existing global model registry and Lustre UID observer.

    Registration is ordinary capacity accounting by Root before launch, not
    an approval record. The global forecast already includes registered D
    growth: do not add that same D forecast a second time.
    """
    storage_locations(configuration)
    scope = Path(configuration["model_budget_root"]).resolve()
    if not Path(path).resolve().is_relative_to(scope):
        raise ValueError("Model write escaped its registered D output root")
    if native is None:
        from tools.model_v3 import v2_diagnosis_disk as native
    registry = native.ROOT / "runs/model_v31_20261105/model_output_budget.json"
    record = json.loads(registry.read_text())
    if scope not in {Path(root).resolve() for root in record["roots"]}:
        raise ValueError("Register D model growth in the existing global pool before launch")
    _, remaining = native.model_growth_forecast()
    other = native.remaining_d6() + configuration["lustre_other_future_bytes"]
    facts = native.m.filesystem_status(path)
    if facts["root"]:
        raise ValueError("Lustre model output resolved onto the node root filesystem")
    native.m.require_capacity(facts, remaining + other, 10000)
    return native.m.quota_headroom(native.CONTROL / "lustre_quota_available_v2_20261107.json",
                                   "/lfshome", remaining, other)


def protection_plan(configuration):
    peak = configuration["storage_peak_bytes"]
    if type(peak) is not int or peak <= 0:
        raise ValueError("Explicit positive D storage peak required")
    _, share_path, share_peak = storage_locations(configuration)
    local_concurrent = configuration.get("local_concurrent_bytes", 0)
    if type(local_concurrent) is not int or local_concurrent < 0:
        raise ValueError("Known nonnegative peer root-disk forecast required")
    common = dict(peak_additional_inodes=10000, reserve_inodes=10000,
                  concurrent_bytes=0, concurrent_inodes=0,
                  runtime_margin_bytes=2**26, runtime_margin_inodes=1000)
    root = dict(common, paths=["/"], peak_additional_bytes=0,
                reserve_bytes=10 * 2**30, quota_scope="not_applicable",
                concurrent_bytes=local_concurrent)
    if configuration.get("local_output_root"):
        # Both paths must resolve to the same actual filesystem in Guard.
        # A separately mounted /tmp is not silently charged to node root.
        root.update(paths=["/", str(local_scope(configuration))],
                    peak_additional_bytes=configuration["local_storage_peak_bytes"])
    share = dict(common, paths=[str(Path(share_path).resolve())],
        peak_additional_bytes=share_peak, reserve_bytes=100_000_000_000,
        quota_scope="limited", quota_peak_additional_bytes=share_peak,
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
            # Root reserve is max(10GiB,10%) in the unchanged process guard.
            for index, target in enumerate(self.targets):
                local_peak = remaining_local_bytes(self.configuration) if index == 0 else 0
                self.check_target(target, bytes_needed=max(bytes_needed, local_peak),
                                  inodes_needed=inodes_needed)
            filesystem, share_path, share_peak = storage_locations(self.configuration)
            target = Path(path).resolve()
            local = (local_scope(self.configuration)
                     if self.configuration.get("local_output_root") else None)
            is_local = local is not None and target.is_relative_to(local)
            if filesystem == "/lfshome":
                scope = Path(self.configuration["model_budget_root"]).resolve()
                if target.is_relative_to(scope):
                    model_path = path
                elif target.is_relative_to(Path(share_path)) or is_local:
                    # Readout/diagnostic caches may use the explicitly
                    # budgeted NFS scope while checkpoints stay on Lustre.
                    model_path = self.configuration["output"]
                    if not is_local:
                        share_path = path
                else:
                    raise ValueError("Write escaped the registered D model and NFS scopes")
                # The native observer owns Lustre's distinct quota schema,
                # five-second freshness, 100GB floor and extra 8GiB margin.
                model_admission(self.configuration, model_path)
            elif filesystem == "node_local" and not (is_local or target.is_relative_to(Path(share_path))):
                raise ValueError("Write escaped the registered node-local and NFS scopes")
            # Refresh the real shared UID quota and remaining peer forecasts.
            # Do not freeze B0's initial future as its databases grow.
            share_admission(share_path if filesystem != "/share" or is_local else path,
                            peak_bytes=share_peak)
            peer_share_admission(self.configuration)
        except DiskUnavailable:
            raise
        except Exception as error:
            raise DiskUnavailable("D target capacity or joint reservation unavailable: " + str(error)) from error


def admit_output(configuration, path):
    """Direct writer entries share the parent monitor's filesystem handling."""
    if (configuration.get("output_filesystem", "/share") == "/share"
            and not configuration.get("local_output_root") and not configuration.get("peer_storage_guard_root")):
        from workflows.data_d_descriptors.storage import guard
        return guard(path, peak_bytes=configuration["storage_peak_bytes"])
    return DJointGuard(configuration).check(path)


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
    if configuration.get("local_node") and node != configuration["local_node"]:
        raise RuntimeError("Node-bound scratch must be consumed on its recorded host")


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
