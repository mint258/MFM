"""Canonical admission for new D GPU entries; original process monitor reused.

No peer forecast is copied from historical configurations. The existing disk
monitor retains real root/UID protection; its own phase budgets are explicit.
"""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import uuid

ROOT = Path("/share/home/zixiao/descriptor_analysis")
REPO = ROOT / "MFM_d_recipe"
RUNS = ROOT / "runs/d_recipe_20261120"
GIB = 2**30
SHARED_FLOOR = 100000000000 + 8 * GIB


def scope(configuration, path):
    local = Path(configuration["local_output_root"]).resolve()
    target = Path(path).resolve()
    if target.is_relative_to(local):
        return "local"
    if any(target.is_relative_to(root.resolve()) for root in (RUNS, REPO / "results/d_recipe")):
        return "share"
    raise ValueError("Canonical D writer escaped its owned runtime scopes")


def guard_plan(c):
    if c.get("canonical_admission") is not True or c.get("output_filesystem", "/share") != "/share":
        raise ValueError("This explicit new D GPU profile uses its registered NFS output")
    local = Path(c["local_output_root"]).resolve()
    if local.parent != Path("/tmp").resolve() or not local.name.startswith("d_recipe_"):
        raise ValueError("Explicit owned D /tmp root required")
    shared = c["shared_future_bytes"]["/share"]
    if any(type(value) is not int or value <= 0 for value in (c["local_future_bytes"], shared)):
        raise ValueError("Positive own remaining phase budgets required")
    common = dict(peak_additional_inodes=10000, reserve_inodes=10000,
        concurrent_bytes=0, concurrent_inodes=0,
        runtime_margin_bytes=2**26, runtime_margin_inodes=1000)
    root = dict(common, paths=["/", str(local)], peak_additional_bytes=c["local_future_bytes"],
                reserve_bytes=10 * GIB, quota_scope="not_applicable")
    share = dict(common, paths=[str(RUNS), str(REPO / "results/d_recipe")],
        peak_additional_bytes=shared, reserve_bytes=SHARED_FLOOR, quota_scope="limited",
        quota_peak_additional_bytes=shared, quota_concurrent_bytes=0,
        quota_reserve_bytes=SHARED_FLOOR,
        quota_available_reference=str(ROOT / "runs/data_v1_20261025/control/window2_20261105/share_quota_available_v3.json"),
        quota_expected_uid=os.getuid(), quota_expected_filesystem="/share", quota_max_age_seconds=5)
    return dict(poll_seconds=5, targets=[root, share])


def guard_class(resources):
    class CanonicalGuard(resources.Guard):
        def __init__(self, configuration, *, admit=True):
            self.configuration = configuration
            plan = guard_plan(configuration)
            if admit:
                from .shared_admission import admit as phase_admit
                phase_admit(configuration, [configuration["output"], configuration["local_output_root"],
                                            REPO / "results/d_recipe"])
            super().__init__(plan, admit=False)

        def check(self, path, bytes_needed=0, inodes_needed=0):
            try:
                scope(self.configuration, path)
                allocated = resources.allocated_local_bytes(Path(self.configuration["local_output_root"]))
                local = max(0, self.configuration["local_storage_peak_bytes"] - allocated)
                local += self.configuration["exit_root_log_future_bytes"]
                self.check_target(self.targets[0], bytes_needed=max(bytes_needed, local),
                                  inodes_needed=inodes_needed)
                self.check_target(self.targets[1], bytes_needed=max(bytes_needed,
                    self.configuration["shared_future_bytes"]["/share"]), inodes_needed=inodes_needed)
            except resources.DiskUnavailable:
                raise
            except Exception as error:
                raise resources.DiskUnavailable("Canonical D runtime capacity unavailable: " + str(error)) from error

        def check_control(self, path):
            if scope(self.configuration, path) != "share":
                raise ValueError("Cooperative control belongs in the existing shared scope")
            # Control is part of the already admitted small metadata margin.
            # A fresh actual disk/UID floor is retained, without re-admitting RAM.
            for target in self.targets:
                self.check_target(target)

    return CanonicalGuard


def prepare_snapshot(c, job, kind):
    from . import managed_entry, resources
    from .shared_admission import admit, atomic_json
    if kind not in ("train", "gpu"):
        raise ValueError("Canonical CPU followups use the authenticated SSH entry")
    resources.execution_site(c, cpu=False)
    destination, runtime = managed_entry.runtime_payload(c, job, kind)
    if destination.exists():
        raise FileExistsError("Inspect the existing runtime snapshot before reentry")
    report = admit(runtime, [destination.parent, runtime["output"], runtime["local_output_root"],
                             REPO / "results/d_recipe"])
    runtime["canonical_phase_admission"] = dict(job_id=str(job), node=report["node"],
        own_reservation_ids=report["own_reservation_ids"], phase="registered_GPU_startup")
    atomic_json(destination, runtime)


def request_snapshot(c, job):
    from . import resources
    from .shared_admission import atomic_json
    if c["safe_exit_control"]["job_id"] != str(job):
        raise ValueError("Cooperative request belongs to a different actual allocation")
    path = Path(c["handoff_request"])
    if path.exists() or Path(c["handoff_ack"]).exists():
        raise FileExistsError("Preserve the existing handoff state")
    guard_class(resources)(c, admit=False).check_control(path)
    atomic_json(path, dict(action="SAVE_AND_EXIT", run=c["run"], job_id=int(job),
                           request_id=str(uuid.uuid4())))


@contextmanager
def installed_writers(c, resources):
    previous = resources.admit_output, resources.DJointGuard
    cls = guard_class(resources)
    monitor = cls(c, admit=False)

    def admitted(configuration, path):
        if configuration.get("canonical_admission") is not True:
            raise ValueError("A canonical worker cannot dispatch a legacy writer")
        monitor.check(path)

    try:
        resources.admit_output, resources.DJointGuard = admitted, cls
        yield
    finally:
        resources.admit_output, resources.DJointGuard = previous


@contextmanager
def allocated_threads(torch_module, limit):
    if type(limit) is not int or limit <= 0:
        raise ValueError("Actual positive allocated CPU count required")
    original = torch_module.set_num_threads
    prior = torch_module.get_num_threads()
    original(1)  # Original training/reader policy; probes may request up to limit.
    torch_module.set_num_threads = lambda count: original(min(count, limit))
    try:
        yield
    finally:
        torch_module.set_num_threads = original
        original(min(prior, limit))
