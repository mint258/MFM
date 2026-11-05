"""Explicitly approved pilot-only live-memory policy; contains no science calls."""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import threading
import time

GIB = 1024 ** 3
MIB = 1024 ** 2
RESERVED_BYTES = 32 * GIB
RSS_STOP_BYTES = 24 * GIB
POLL_SECONDS = 1.0
MAX_SAMPLE_AGE_SECONDS = 2.0
BASIS = "LIVE_NODE_MEMAVAILABLE_PLUS_FULL_32G_USER_SMALL_PILOT_EXCEPTION"
ALLOWED_NODES = {f"compute-0-{i}" for i in range(14, 20)}
CONFIG_SHA = "cfd153fb524ad823d3903b0ff7d78e402bbbcb74e124136b4bfeb3035279407a"
PREPARED_SHA = "74b1cda893683e070097d1784b557c6600cdf088a77a077f3026ab9d34b72d34"
OLD_SOURCE_SHA = {
    "run_pilot.py": "f7733b23602d9883159bbedc2ea712fb3054e9e7963950c6fd6c10c1f582868f",
    "common.py": "ffa4fc9b6ce97be5b62af926c35337168b687f1f80a0fdd3564957dfe169b83b",
    "science.py": "2476767636d97b2a334dcf1f8b8e789e137a268acc6404ade61b7162690d211f",
    "selection.py": "41f21f5586c06f3c6fd7cfa9712623adc8091da996c72f6d71170dd4b716e2cb",
    "statistics_tools.py": "22422b92fde096a64c019683cf265514b99351b002fa8bc450f6eeaf932808ed",
}
ACTUAL_USER_REPLY = "在小规模数据测试时可以降低资源使用情况，但是之后的正式数据生成必须使用原有硬件要求"


def file_reference(path):
    path = Path(path).absolute()
    raw = path.read_bytes()
    return {"path": str(path), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def require_reference(pin):
    path = Path(pin["path"])
    if not path.is_absolute() or path.is_symlink() or not path.is_file() or file_reference(path) != pin:
        raise ValueError("EXPLICIT_APPROVAL_OR_INPUT_REFERENCE_MISMATCH")
    return path


def validate_approval_payload(approval, config_ref, prepared_ref):
    if approval.get("schema") != "DATA_V1_LIVE_MEMORY_32G_USER_APPROVAL_V1":
        raise ValueError("EXPLICIT_USER_APPROVAL_SCHEMA_REQUIRED")
    if approval.get("status") != "APPROVED_BY_USER" or not isinstance(approval.get("user_reply"), str) or not approval["user_reply"].strip():
        raise ValueError("ACTUAL_USER_APPROVAL_REQUIRED")
    if approval["user_reply"] != ACTUAL_USER_REPLY:
        raise ValueError("EXACT_SMALL_SCALE_USER_REPLY_REQUIRED")
    scope = approval["scope"]
    if not isinstance(scope.get("root_interpretation"), str) or not scope["root_interpretation"].strip():
        raise ValueError("ROOT_PILOT_SCOPE_INTERPRETATION_REQUIRED")
    if scope.get("formal_generation_uses_original_hardware_requirements") is not True:
        raise ValueError("FORMAL_GENERATION_MUST_RETAIN_ORIGINAL_HARDWARE")
    required = {"task": "SB2_SPRIME_FILL_336_PILOT_ONLY", "molecules": 336,
                "cpus": 16, "memory_gib": 32, "wall_seconds": 14400}
    if any(scope.get(key) != value for key, value in required.items()):
        raise ValueError("APPROVAL_SCOPE_IS_NOT_THIS_336_MOLECULE_PILOT")
    if set(scope["allowed_nodes"]) != ALLOWED_NODES:
        raise ValueError("APPROVAL_NODE_SCOPE_MISMATCH")
    if config_ref["sha256"] != CONFIG_SHA or prepared_ref["sha256"] != PREPARED_SHA:
        raise ValueError("ORIGINAL_CONFIG_AND_CLOSED_PREPARED_SHA_REQUIRED")
    if scope["config_reference"] != config_ref or scope["prepared_reference"] != prepared_ref:
        raise ValueError("APPROVAL_INPUT_PINS_MISMATCH")
    return scope


def validate_root_intent(receipt, approval_ref, config_ref, prepared_ref, *, node, now_epoch):
    request = receipt["request"]
    age = now_epoch - datetime.fromisoformat(receipt["observed_at"]).timestamp()
    if not 0 <= age <= 3600:
        raise ValueError("ROOT_INTENT_STALE")
    if request.get("memory_basis") != BASIS or request.get("approval_reference") != approval_ref:
        raise ValueError("ROOT_INTENT_MUST_BIND_EXPLICIT_LIVE_MEMORY_APPROVAL")
    if request.get("node") != node or node not in ALLOWED_NODES:
        raise ValueError("ROOT_INTENT_NODE_MISMATCH")
    if (request.get("cpus"), request.get("memory_gib"), request.get("wall_seconds"),
        request.get("kind"), request.get("pilot")) != (16, 32, 14400, "conformer", True):
        raise ValueError("ROOT_INTENT_PILOT_RESOURCES_MISMATCH")
    if request.get("root_review", {}).get("status") != "APPROVED":
        raise ValueError("ROOT_CODE_REVIEW_APPROVAL_REQUIRED")
    if config_ref not in request["source_references"] or prepared_ref not in request["source_references"]:
        raise ValueError("ROOT_INTENT_INPUT_PINS_MISSING")
    if request["estimated_peak_output_bytes"] < 8 * GIB or receipt["account_free_bytes"] - request["estimated_peak_output_bytes"] < 200_000_000_000:
        raise ValueError("ROOT_INTENT_STORAGE_BUDGET_REJECTED")
    if not isinstance(receipt["existing_jobs_all_users"], list):
        raise ValueError("ALL_USER_MEMORY_DECLARATIONS_MUST_REMAIN_IN_EVIDENCE")
    match = re.search(r"(?:^|\s)RealMemory=(\d+)(?:\s|$)", receipt["node_metadata"])
    if match is None or int(match[1]) <= 0:
        raise ValueError("SLURM_REAL_MEMORY_MISSING")
    # MinMemoryNode=0 remains unknown/unbounded in the preserved job metadata.
    # This approved policy uses live physical memory; it never substitutes zero.
    return int(match[1]) * MIB


def parse_meminfo(text):
    found = {}
    for line in text.splitlines():
        match = re.fullmatch(r"(MemTotal|MemAvailable):\s+(\d+)\s+kB\s*", line)
        if match:
            if match[1] in found:
                raise ValueError("DUPLICATE_MEMINFO_FIELD")
            found[match[1]] = int(match[2]) * 1024
    if set(found) != {"MemTotal", "MemAvailable"}:
        raise ValueError("MEMTOTAL_AND_MEMAVAILABLE_REQUIRED")
    if found["MemTotal"] <= 0 or not 0 <= found["MemAvailable"] <= found["MemTotal"]:
        raise ValueError("INVALID_MEMINFO_RANGE")
    return found


def evaluate_memory(meminfo, slurm_real_bytes, owned_rss_bytes):
    if slurm_real_bytes <= 0 or owned_rss_bytes < 0:
        raise ValueError("INVALID_MEMORY_METRIC")
    capacity = min(slurm_real_bytes, meminfo["MemTotal"])
    used = meminfo["MemTotal"] - meminfo["MemAvailable"]
    # Integer arithmetic retains the exact <=85% admission boundary.
    node_ok = (used + RESERVED_BYTES) * 100 <= capacity * 85
    rss_ok = owned_rss_bytes < RSS_STOP_BYTES
    return {"memory_basis": BASIS, "node_used_bytes": used, "mem_total_bytes": meminfo["MemTotal"],
            "mem_available_bytes": meminfo["MemAvailable"], "capacity_bytes": capacity,
            "reserved_bytes": RESERVED_BYTES, "owned_rss_bytes": owned_rss_bytes,
            "owned_rss_stop_bytes": RSS_STOP_BYTES, "node_gate_passed": node_ok,
            "owned_rss_gate_passed": rss_ok, "dispatch_allowed": node_ok and rss_ok,
            "runtime_reservation_double_counts_own_memory_conservatively": True,
            "MinMemoryNode_zero_interpretation": "UNKNOWN_UNBOUNDED_NOT_ZERO_USAGE"}


def parse_stat(text):
    end = text.rfind(")")
    if end < 0:
        raise ValueError("INVALID_PROC_STAT")
    pid = int(text[:text.index("(")].strip())
    fields = text[end + 2:].split()
    if len(fields) < 22:
        raise ValueError("TRUNCATED_PROC_STAT")
    return {"pid": pid, "state": fields[0], "ppid": int(fields[1]),
            "pgid": int(fields[2]), "sid": int(fields[3]), "flags": int(fields[6]),
            "start_ticks": int(fields[19]), "rss_pages": int(fields[21])}


def identity(row):
    return tuple(row[key] for key in ("pid", "ppid", "pgid", "sid", "start_ticks"))


class ProcSampler:
    """Read only this UID/job's parent and descendants; never signals processes."""
    def __init__(self, job_id, slurm_real_bytes, proc_root=Path("/proc")):
        self.proc = Path(proc_root)
        self.pid, self.uid, self.job_id = os.getpid(), os.getuid(), str(job_id)
        self.page_size, self.slurm_real_bytes = os.sysconf("SC_PAGE_SIZE"), slurm_real_bytes
        initial = parse_stat((self.proc / str(self.pid) / "stat").read_text())
        self.parent_identity = identity(initial)
        self.cgroup = tuple(sorted((self.proc / str(self.pid) / "cgroup").read_text().splitlines()))
        if not self.cgroup:
            raise ValueError("PARENT_CGROUP_UNAVAILABLE")

    def read_process(self, pid, expected_parent=None):
        root = self.proc / str(pid)
        try:
            first = parse_stat((root / "stat").read_text())
            second = parse_stat((root / "stat").read_text())
            if identity(first) != identity(second):
                raise ValueError("OWNED_PROCESS_IDENTITY_CHANGED")
            if second["state"] in {"Z", "X"}:
                return None
            if second["flags"] & 4:
                third = parse_stat((root / "stat").read_text())
                if identity(second) == identity(third) and third["flags"] & 4:
                    return None
                raise ValueError("OWNED_EXIT_FLAG_NOT_STABLE")
            if first["flags"] & 4:
                raise ValueError("OWNED_EXIT_FLAG_REGRESSED")
            uid_line = next(line for line in (root / "status").read_text().splitlines() if line.startswith("Uid:"))
            if any(int(value) != self.uid for value in uid_line.split()[1:]):
                raise ValueError("OWNED_UID_MISMATCH")
            with (root / "environ").open("rb") as stream:
                environment = stream.read(2 * MIB + 1)
            if len(environment) > 2 * MIB:
                raise ValueError("OWNED_ENVIRONMENT_TOO_LARGE")
            job_values = [item.split(b"=", 1)[1] for item in environment.split(b"\0") if item.startswith(b"SLURM_JOB_ID=")]
            if job_values != [self.job_id.encode()]:
                raise ValueError("OWNED_JOB_ID_MISMATCH")
            if tuple(sorted((root / "cgroup").read_text().splitlines())) != self.cgroup:
                raise ValueError("OWNED_CGROUP_MISMATCH")
            last = parse_stat((root / "stat").read_text())
            if identity(first) != identity(last):
                raise ValueError("OWNED_PROCESS_IDENTITY_CHANGED")
            if last["state"] in {"Z", "X"} or last["flags"] & 4:
                # Re-enter the bounded double-read exit path on a fresh snapshot.
                check = parse_stat((root / "stat").read_text())
                if identity(last) == identity(check) and (check["state"] in {"Z", "X"} or check["flags"] & 4):
                    return None
                raise ValueError("OWNED_PROCESS_EXIT_RACE_UNRESOLVED")
            if expected_parent is not None and last["ppid"] != expected_parent:
                raise ValueError("OWNED_PARENT_RELATION_CHANGED")
            if last["pgid"] != self.parent_identity[2] or last["sid"] != self.parent_identity[3]:
                raise ValueError("OWNED_PROCESS_GROUP_OR_SESSION_MISMATCH")
            if last["rss_pages"] < 0:
                raise ValueError("NEGATIVE_OWNED_RSS")
            return {**last, "uid": self.uid, "rss_bytes": last["rss_pages"] * self.page_size}
        except FileNotFoundError:
            if not root.exists():
                return None
            raise ValueError("OWNED_PROCESS_EXISTS_BUT_METADATA_MISSING")

    def children(self, pid):
        root, children = self.proc / str(pid), set()
        try:
            threads = list((root / "task").iterdir())
            for thread in threads:
                try:
                    children.update(int(value) for value in (thread / "children").read_text().split())
                except FileNotFoundError:
                    if thread.exists():
                        raise ValueError("OWNED_THREAD_CHILDREN_UNAVAILABLE")
        except FileNotFoundError:
            if root.exists():
                raise ValueError("OWNED_PROCESS_TASKS_UNAVAILABLE")
        return children

    def __call__(self):
        begin = time.monotonic()
        meminfo = parse_meminfo((self.proc / "meminfo").read_text())
        pending, rows, seen = [(self.pid, None)], [], set()
        while pending:
            pid, parent = pending.pop()
            if pid in seen:
                raise ValueError("OWNED_DESCENDANT_TREE_IS_NOT_UNIQUE")
            seen.add(pid)
            row = self.read_process(pid, parent)
            if row is None:
                if pid == self.pid:
                    raise ValueError("PARENT_NOT_ACTIVE")
                continue
            if pid == self.pid and identity(row) != self.parent_identity:
                raise ValueError("PARENT_IDENTITY_CHANGED")
            rows.append(row)
            pending.extend((child, pid) for child in self.children(pid))
        parent = self.read_process(self.pid)
        if parent is None or identity(parent) != self.parent_identity:
            raise ValueError("PARENT_IDENTITY_CHANGED_AFTER_SAMPLE")
        sample = evaluate_memory(meminfo, self.slurm_real_bytes, sum(row["rss_bytes"] for row in rows))
        sample.update(observed_epoch=time.time(), observed_monotonic=begin,
                      sample_seconds=time.monotonic() - begin,
                      processes=sorted(rows, key=lambda row: row["pid"]))
        if sample["sample_seconds"] > MAX_SAMPLE_AGE_SECONDS:
            raise ValueError("OWNED_MEMORY_SAMPLE_EXCEEDED_TWO_SECONDS")
        return sample


class MemoryMonitor:
    """Sticky dispatch denial. An existing task always finishes without signals."""
    def __init__(self, sampler):
        self.sampler, self.samples, self.first_denial = sampler, [], None
        self.lock, self.stop_event = threading.Lock(), threading.Event()
        self.thread = None

    def mark_denied(self, reason):
        with self.lock:
            if self.first_denial is None:
                self.first_denial = {"reason": reason, "observed_epoch": time.time()}

    def observe(self):
        try:
            sample = self.sampler()
        except Exception as exc:
            sample = {"dispatch_allowed": False, "observed_epoch": time.time(),
                      "observed_monotonic": time.monotonic(), "memory_basis": BASIS,
                      "metric_invalid": True, "error_type": type(exc).__name__, "error": str(exc)[:1000]}
        with self.lock:
            self.samples.append(sample)
        if not sample["dispatch_allowed"]:
            self.mark_denied("METRIC_INVALID" if sample.get("metric_invalid") else "LIVE_MEMORY_THRESHOLD_REACHED")
        return sample

    def start(self):
        self.observe()
        def loop():
            deadline = time.monotonic() + POLL_SECONDS
            while not self.stop_event.wait(max(0.0, deadline - time.monotonic())):
                self.observe()
                deadline += POLL_SECONDS
        self.thread = threading.Thread(target=loop, name="dv1-live-memory", daemon=True)
        self.thread.start()

    def allow_dispatch(self):
        with self.lock:
            latest = self.samples[-1] if self.samples else None
            denied = self.first_denial is not None
        if latest is None or time.monotonic() - latest["observed_monotonic"] > MAX_SAMPLE_AGE_SECONDS:
            self.mark_denied("LIVE_MEMORY_SAMPLE_STALE")
            return False
        return not denied and latest["dispatch_allowed"]

    def stop(self):
        self.stop_event.set()
        if self.thread is not None:
            self.thread.join(timeout=2)
            if self.thread.is_alive():
                self.mark_denied("MEMORY_MONITOR_THREAD_DID_NOT_CLOSE")
