"""Strict CPU identities, durable evidence and explicit pytest spawn enrollment.

Metadata validation is not evidence that Slurm or a test command completed.
The immutable signal-authority keys are the already frozen supervisor keys.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import stat
import sys
import time
import uuid

IDENTITY_KEYS = ("pid", "uid", "boot_id", "start_ticks", "pgid", "sid",
                 "argv_sha256", "cgroup", "slurm_job_id")
CORE_KEYS = tuple(key for key in IDENTITY_KEYS if key != "argv_sha256") + ("ppid",)
PINS_SCHEMA = "model_v3_CPU_supervisor_revision_v4_source_pins"
MANIFEST_SCHEMA = "model_v3_CPU_pytest_spawn_manifest_v4"
RECEIPT_SCHEMA = "model_v3_CPU_pytest_exec_receipt_v4"
EVENT_SCHEMA = "model_v3_CPU_identity_event_v4"
PENDING_SECONDS = 30.0
REGISTRATION_DIRECTORY = ".process_registration_v4"
PROJECT = Path("/share/home/zixiao/descriptor_analysis")
CONTROL = PROJECT / "runs/model_v3_20261026/numeric_full_regression_v1_source"
HELPERS = PROJECT / "MFM_model_v3_sa1_a/tools/model_v3"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def argv_sha256(argv):
    require(isinstance(argv, list) and argv and all(isinstance(s, str) and "\0" not in s for s in argv),
            "A complete nonempty argv is required")
    raw = b"".join(s.encode("utf-8", "surrogateescape") + b"\0" for s in argv)
    require(len(raw) <= 65536, "Bounded complete argv required")
    return hashlib.sha256(raw).hexdigest()


def read_regular(path, *, maximum=8 << 20):
    path = Path(path)
    require(path.is_absolute() and ".." not in path.parts and path.resolve(strict=True) == path,
            "Absolute physical metadata/source path required")
    with path.open("rb") as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_uid == os.getuid()
                and before.st_size <= maximum, "Owned bounded ordinary file required")
        require(not path.is_symlink(), "Metadata/source symlinks are rejected")
        raw = stream.read(maximum + 1)
        after = os.fstat(stream.fileno())
    after_path = path.lstat()
    require((after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns) ==
            (after_path.st_dev, after_path.st_ino, after_path.st_size, after_path.st_mtime_ns, after_path.st_ctime_ns),
            "Metadata/source path replaced during read")
    require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
            (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
            and len(raw) == before.st_size, "File changed during read")
    return raw


def file_ref(path):
    path = Path(path).absolute()
    raw = read_regular(path)
    return {"path": str(path), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def read_json(path, expected_sha=None):
    raw = read_regular(path)
    if expected_sha is not None:
        require(re.fullmatch("[a-f0-9]{64}", expected_sha) is not None
                and hashlib.sha256(raw).hexdigest() == expected_sha, "Raw SHA differs")
    return json.loads(raw)


def atomic_json(path, value):
    """Publish a complete exclusive file; readers never see a partial JSON."""
    path = Path(path)
    raw = json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False).encode() + b"\n"
    require(len(raw) <= 1 << 20, "Registration metadata cap exceeded")
    temporary = path.with_name("." + path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)  # atomic no-replace publication, same directory
        fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        temporary.unlink(missing_ok=True)
    return file_ref(path)


def verify_source_pins(path, sha):
    pins = read_json(path, sha)
    require(pins.get("schema") == PINS_SCHEMA, "Explicit new source inventory required")
    refs = pins.get("runtime_sources")
    require(isinstance(refs, list) and refs and len(refs) <= 32, "Bounded runtime inventory required")
    paths = [ref["path"] for ref in refs]
    require(len(paths) == len(set(paths)), "Duplicate runtime source")
    for ref in refs:
        require(file_ref(ref["path"]) == ref, "Runtime source bytes or path drift")
    return pins


def load_fixed_runtime(pins):
    """Reject a cached namespace from another tree; never patch __path__."""
    by_path = {ref["path"]: ref for ref in pins["runtime_sources"]}
    modules = {}
    for name in ("runtime_monitor", "private_runtime_storage", "run_supervised"):
        target = HELPERS / (name + ".py")
        require(str(target) in by_path and file_ref(target) == by_path[str(target)],
                "Frozen runtime helper missing or changed")
        previous = sys.modules.get(name)
        if previous is not None:
            require(Path(previous.__file__).absolute() == target, "Contaminated runtime helper namespace")
            modules[name] = previous
            continue
        spec = importlib.util.spec_from_file_location(name, target)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        try:
            spec.loader.exec_module(module)
        except BaseException:
            del sys.modules[name]
            raise
        modules[name] = module
    require(tuple(modules["run_supervised"].IDENTITY_KEYS) == IDENTITY_KEYS,
            "Original strict identity keys changed")
    return modules


def load_fixed_control(pins):
    target = CONTROL / "regression_control_v4.py"
    require(file_ref(target) in pins["runtime_sources"], "Frozen regression control missing")
    name = "_cpu_supervisor_revision_v4_frozen_control"
    previous = sys.modules.get(name)
    if previous is not None:
        require(Path(previous.__file__).absolute() == target, "Contaminated control namespace")
        return previous
    spec = importlib.util.spec_from_file_location(name, target)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def diagnostic_identity(runtime, pid):
    """Read-only rejected-frame evidence; NEVER an ACTIVE/signal identity."""
    import psutil
    try:
        first = runtime._proc_frame(pid)
        status = Path(f'/proc/{pid}/status').read_text()
        uid = int(next(line for line in status.splitlines() if line.startswith('Uid:')).split()[1])
        raw = Path(f'/proc/{pid}/cmdline').read_bytes()
        require(len(raw) <= 65536, 'Diagnostic argv cap exceeded')
        cgroup = Path(f'/proc/{pid}/cgroup').read_text()
        boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        created = psutil.Process(pid).create_time()
        second = runtime._proc_frame(pid)
        jobs = sorted(set(re.findall(r'(?:^|/)job[_-]?(\d+)(?:/|$)', cgroup, re.M)))
        return {'status': 'DIAGNOSTIC_ONLY', 'pid': pid, 'uid': uid, 'boot_id': boot,
                'start_ticks': second['start_ticks'], 'pgid': second['pgid'], 'sid': second['sid'],
                'ppid': second['ppid'], 'argv': [s.decode('utf-8', 'surrogateescape')
                    for s in raw.rstrip(b'\0').split(b'\0')],
                'argv_sha256': hashlib.sha256(raw).hexdigest(), 'cgroup': cgroup,
                'slurm_job_id': jobs[0] if len(jobs) == 1 else None, 'created': created,
                'stat_before': first, 'stat_after': second,
                'coherent_kernel_frame': all(first[k] == second[k]
                    for k in ('pid', 'start_ticks', 'pgid', 'sid', 'ppid'))}
    except (OSError, psutil.Error, ValueError, StopIteration) as exc:
        return {'status': 'DIAGNOSTIC_UNREADABLE', 'pid': pid, 'error': type(exc).__name__}


def capture_identity(runtime, pid, *, expected_cgroup, expected_argv=None):
    """Add a coherent PPID without changing any frozen signal-authority key."""
    try:
        before = runtime._proc_frame(pid)
        row = runtime.capture_process_identity(pid, expected_cgroup=expected_cgroup,
                                               expected_argv=expected_argv)
        if row["status"] != "ACTIVE":
            return row if row["status"] in {"GONE", "EXITING"} else {**row, "diagnostic_identity": diagnostic_identity(runtime, pid)}
        after = runtime._proc_frame(pid)
    except (FileNotFoundError, ProcessLookupError):
        return runtime.capture_process_identity(pid, expected_cgroup=expected_cgroup,
                                                expected_argv=expected_argv)
    if any(before[key] != after[key] or after[key] != row[key]
           for key in ("pid", "start_ticks", "pgid", "sid")) or before["ppid"] != after["ppid"]:
        return {"status": "IDENTITY_CHANGED", "pid": pid, "reason": "birth_session_or_parent_changed",
                "diagnostic_identity": diagnostic_identity(runtime, pid)}
    return {**row, "ppid": after["ppid"]}


def validate_identity(row):
    require(row.get("status") == "ACTIVE", "Only ACTIVE full identities can be enrolled")
    for key in ("pid", "start_ticks", "pgid", "sid", "ppid"):
        require(type(row.get(key)) is int and row[key] > 0, "Positive kernel identity field required: " + key)
    require(type(row.get("uid")) is int and row["uid"] >= 0, "Actual UID required")
    require(str(uuid.UUID(row["boot_id"])) == row["boot_id"], "Canonical kernel boot UUID required")
    require(isinstance(row.get("slurm_job_id"), str) and row["slurm_job_id"].isdigit()
            and isinstance(row.get("cgroup"), str)
            and re.search(r"(?:^|/)job[_-]?" + re.escape(row["slurm_job_id"]) + r"(?:/|$)",
                          row["cgroup"], re.M), "Actual Slurm job cgroup required")
    require(row.get("argv_sha256") == argv_sha256(row.get("argv")), "Raw argv hash differs")
    require(isinstance(row.get("created"), (float, int)) and math.isfinite(row["created"]),
            "Wall-clock creation diagnostic required")


def changed_keys(before, after, keys=IDENTITY_KEYS):
    return [key for key in keys if before.get(key) != after.get(key)]


class IdentityViolation(RuntimeError):
    def __init__(self, detail):
        self.detail = detail
        super().__init__(detail["reason"])


class EventLog:
    def __init__(self, path, *, cap_bytes=8 << 20):
        self.path, self.cap_bytes = Path(path), cap_bytes
        require(not self.path.exists(), "Fresh identity event journal required")
        self.sequence = 0

    def __call__(self, event):
        row = {"schema": EVENT_SCHEMA, "sequence": self.sequence,
               "monotonic_seconds": time.monotonic(), "wall_seconds": time.time(), **event}
        raw = json.dumps(row, sort_keys=True, ensure_ascii=True, allow_nan=False).encode() + b"\n"
        size = self.path.stat().st_size if self.path.exists() else 0
        require(size + len(raw) <= self.cap_bytes, "Identity event journal cap exceeded")
        with self.path.open("xb" if self.sequence == 0 else "ab") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        if self.sequence == 0:
            fd = os.open(self.path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
        self.sequence += 1


def partition_groups(files, workers=4):
    require(workers == 4 and len(files) >= 4, "This enrollment protocol is limited to exactly four pytest shards")
    groups, sizes = [[] for _ in range(workers)], [0] * workers
    for path in sorted(files, key=lambda value: (-value.stat().st_size, value.name)):
        group = min(range(workers), key=lambda index: (sizes[index], index))
        groups[group].append(path)
        sizes[group] += path.stat().st_size
    return groups


def pytest_roles(python, root, output, groups):
    root, output = Path(root), Path(output)
    return [{"role": f"pytest_shard_{index:02d}", "shard": index, "launch_kind": "exec",
             "expected_argv": [str(python), "-B", "-m", "pytest", *(str(p) for p in group),
                               "-q", "-p", "no:cacheprovider",
                               "--junitxml=" + str(output / f"shard_{index:02d}.xml"),
                               "--basetemp=" + str(output / ("tmp_" + str(index)))],
             "cwd": str(root / "current"), "start_new_session": False,
             "stdin": "DEVNULL"} for index, group in enumerate(groups)]


def make_manifest(parent, context):
    validate_identity(parent)
    return {"schema": MANIFEST_SCHEMA, "job_id": parent["slurm_job_id"], "uid": parent["uid"],
            "parent_identity": parent, **context}


def validate_manifest(manifest, parent, context):
    require(manifest.get("schema") == MANIFEST_SCHEMA, "New spawn manifest schema required")
    require(manifest.get("job_id") == parent["slurm_job_id"] and manifest.get("uid") == parent["uid"],
            "Manifest job/UID differs")
    validate_identity(manifest["parent_identity"])
    require(not changed_keys(parent, manifest["parent_identity"])
            and manifest["parent_identity"]["argv"] == parent["argv"], "Manifest parent identity differs")
    require(all(manifest.get(key) == value for key, value in context.items()), "Manifest source/plan/role binding differs")
    roles = manifest["roles"]
    require(len(roles) == 4 and [r["shard"] for r in roles] == list(range(4))
            and [r["role"] for r in roles] == [f"pytest_shard_{i:02d}" for i in range(4)],
            "Exactly four distinct declared pytest roles required")
    for role in roles:
        require(role["launch_kind"] == "exec" and role["start_new_session"] is False
                and role["stdin"] == "DEVNULL", "Only the fixed Popen exec policy is admitted")
        argv_sha256(role["expected_argv"])


def make_exec_receipt(manifest, manifest_ref, role, child):
    validate_identity(child)
    parent = manifest["parent_identity"]
    require(child["ppid"] == parent["pid"] and child["argv"] == role["expected_argv"],
            "Popen-returned child differs from declared direct exec")
    require(not changed_keys(parent, child, ("uid", "boot_id", "pgid", "sid", "cgroup", "slurm_job_id")),
            "Direct child changed its declared allocation/session")
    return {"schema": RECEIPT_SCHEMA, "manifest": manifest_ref, "role": role["role"],
            "launch_kind": "exec", "popen_returned_after_exec": True,
            "source_pins": manifest["source_pins"], "worker_source": manifest["worker_source"],
            "control_plan": manifest["control_plan"], "job_id": parent["slurm_job_id"],
            "uid": parent["uid"], "parent_pid": parent["pid"], "child_pid": child["pid"],
            "parent_identity": parent, "child_identity": child}


class IdentityRegistry:
    """A pending record is accounting/evidence, never signal authority.

    Only the four source-declared direct pytest execs get this enrollment path.
    Other descendants retain first-capture strict identity semantics.
    There is deliberately no automatic stable-N-frames or fork-only promotion.
    """
    def __init__(self, parent, emit, *, context=None, clock=time.monotonic):
        validate_identity(parent)
        self.parent, self.emit, self.context, self.clock = parent, emit, context, clock
        self.observed = {(parent["pid"], parent["start_ticks"]): dict(parent)}
        self.pending, self.quarantined, self.roles = {}, {}, {}
        self.creation_diagnostics = {(parent["pid"], parent["start_ticks"]): parent["created"]}
        self.manifest = self.manifest_ref = None
        self.last_failure = None
        emit({"kind": "ROOT_ENROLLED", "after": parent, "changed_keys": []})

    def violation(self, reason, before, after, *, keys=IDENTITY_KEYS):
        detail = {"kind": "IDENTITY_REJECTED", "reason": reason, "before": before,
                  "after": after, "changed_keys": changed_keys(before, after, keys)}
        self.last_failure = detail
        self.emit(detail)  # durable before raise and cleanup
        raise IdentityViolation(detail)

    def set_manifest(self, value, ref):
        require(self.context is not None, "No opt-in enrollment policy")
        validate_manifest(value, self.parent, self.context)
        require(self.manifest is None or (value == self.manifest and ref == self.manifest_ref),
                "Published manifest changed")
        if self.manifest is None:
            self.manifest, self.manifest_ref = value, ref
            self.emit({"kind": "MANIFEST_BOUND", "manifest": ref, "roles": value["roles"]})

    def observe(self, current):
        validate_identity(current)
        key = current["pid"], current["start_ticks"]
        if key in self.observed:
            before = self.observed[key]
            if changed_keys(before, current):
                self.violation("Recorded CPU descendant identity changed", before, current)
            if self.creation_diagnostics.get(key, before["created"]) != current["created"]:
                self.emit({"kind": "WALL_CLOCK_DIAGNOSTIC_CHANGED", "before": before,
                           "after": current, "changed_keys": []})
                self.creation_diagnostics[key] = current["created"]
            return "MATCH"
        if key in self.pending:
            before = self.pending[key]["first"]
            if changed_keys(before, current, CORE_KEYS):
                self.violation("Pending kernel/parent/session identity changed", before, current, keys=CORE_KEYS)
            allowed = [self.parent["argv"], *(role["expected_argv"] for role in self.manifest["roles"])]
            if current["argv"] not in allowed:
                self.violation("Pending child executed an undeclared argv", before, current)
            previous = self.pending[key]["last"]
            if changed_keys(previous, current):
                self.emit({"kind": "PENDING_EXEC_TRANSITION", "before": previous, "after": current,
                           "changed_keys": changed_keys(previous, current)})
            self.pending[key]["last"] = dict(current)
            if self.clock() - self.pending[key]["since"] > PENDING_SECONDS:
                self.violation("Pending direct pytest exec registration deadline exceeded", before, current)
            return "PENDING"
        direct_policy = (self.manifest is not None and current["ppid"] == self.parent["pid"]
                         and len(self.roles) < 4)
        if direct_policy:
            if changed_keys(self.parent, current,
                            ("uid", "boot_id", "pgid", "sid", "cgroup", "slurm_job_id")):
                self.violation("New direct pytest child changed session/allocation", self.parent, current)
            allowed = [self.parent["argv"], *(role["expected_argv"] for role in self.manifest["roles"])]
            if current["argv"] not in allowed:
                self.violation("New direct child is not a declared pytest exec or parent clone",
                               self.parent, current)
            self.pending[key] = {"first": dict(current), "last": dict(current), "since": self.clock()}
            self.emit({"kind": "PENDING_CORE", "after": current, "changed_keys": [],
                       "signal_authority": False})
            return "PENDING"
        self.observed[key] = dict(current)
        self.emit({"kind": "LEGACY_STRICT_DESCENDANT_ENROLLED", "after": current, "changed_keys": []})
        return "ENROLLED"

    def enroll_receipt(self, receipt, current):
        validate_identity(current)
        key = current["pid"], current["start_ticks"]
        require(key in self.pending and self.manifest is not None, "Receipt requires an observed pending birth")
        before = self.pending[key]["first"]
        if changed_keys(before, current, CORE_KEYS):
            self.violation("Receipt kernel/session differs from pending birth", before, current, keys=CORE_KEYS)
        require(receipt.get("schema") == RECEIPT_SCHEMA and receipt.get("manifest") == self.manifest_ref
                and receipt.get("launch_kind") == "exec" and receipt.get("popen_returned_after_exec") is True,
                "Source-bound actual Popen-return receipt required")
        role_name = receipt["role"]
        candidates = [role for role in self.manifest["roles"] if role["role"] == role_name]
        require(len(candidates) == 1 and role_name not in self.roles, "Unknown or reused pytest role")
        role = candidates[0]
        require(receipt == make_exec_receipt(self.manifest, self.manifest_ref, role,
                                            receipt["child_identity"]), "Receipt source/parent/job fields differ")
        if changed_keys(receipt["child_identity"], current) or receipt["child_identity"]["ppid"] != current["ppid"]:
            self.violation("Receipt child differs from fresh complete identity",
                           receipt["child_identity"], current, keys=(*IDENTITY_KEYS, "ppid"))
        require(current["argv"] == role["expected_argv"], "Exact declared exec argv required")
        require(self.clock() - self.pending[key]["since"] <= PENDING_SECONDS, "Exec receipt arrived after deadline")
        self.observed[key] = dict(current)
        self.roles[role_name] = key
        del self.pending[key]
        self.emit({"kind": "EXPLICIT_EXEC_ENROLLED", "before": before, "after": current,
                   "role": role_name, "manifest": self.manifest_ref,
                   "changed_keys": changed_keys(before, current), "signal_authority": True})

    def quarantine(self, current, reason):
        # Cleanup discovery cannot create or replace any signal authority.
        key = current.get("pid"), current.get("start_ticks")
        if key not in self.observed and key not in self.pending:
            self.quarantined[key] = {"identity": current, "reason": reason}
            self.emit({"kind": "CLEANUP_UNENROLLED", "after": current, "reason": reason,
                       "changed_keys": [], "signal_authority": False})

    def unresolved(self, capture):
        rows = []
        for key, value in [*((k, {"identity": v["first"], "reason": "PENDING_NO_SIGNAL_AUTHORITY"})
                             for k, v in self.pending.items()), *self.quarantined.items()]:
            previous = value["identity"]
            current = capture(previous["pid"])
            if current["status"] not in {"GONE", "EXITING"}:
                rows.append({"status": "UNRESOLVED_NO_SIGNAL_AUTHORITY", **value,
                             "current": current, "changed_keys": changed_keys(previous, current)})
        return rows

    def require_completed_enrollment(self):
        require(not self.pending and not self.quarantined, "Pending/quarantined descendants prevent completion")
        if self.context is not None:
            require(self.manifest is not None and len(self.roles) == 4,
                    "All four explicit pytest exec receipts must be enrolled")
