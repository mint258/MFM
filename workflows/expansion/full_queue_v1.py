"""Strict queued64GiB startup and bounded cooperative execution primitives.

Startup freshness is verified once, before body I/O. Runtime sampling uses
current /proc RSS/MemAvailable, never inherited ru_maxrss or scheduler calls.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import socket
import stat
import threading
import time

from workflows.data_v1_final.execution.queue_v1 import queue_contract, shared
from .common import require


ROOT = shared.ROOT
ARTIFACTS = ROOT / "artifacts/expansion"
RESERVE = 200_000_000_000
GIB = 1024 ** 3


class CooperativeStop(RuntimeError):
    pass


def verify_small(pin, declared=None):
    require(set(pin) == {"path", "bytes", "sha256"} and pin["bytes"] <= 2 * 1024 ** 2 and
            (declared is None or declared.get(pin["path"]) == pin) and shared.pin(Path(pin["path"])) == pin,
            "Exact Root-bound small reference required: " + str(pin.get("path")))
    return Path(pin["path"])


def startup(plan_path, proof_path, entry_path, *, scope):
    """Only this main-process call checks120s startup freshness."""
    proof = shared.load(proof_path)
    request = proof["request"]
    queue_contract.validate_request(request, read_small=shared.read_small)
    validation = queue_contract.validate_fresh_startup_proof(proof, request, now_unix=time.time(), uid=os.getuid(),
        boot_id=Path("/proc/sys/kernel/random/boot_id").read_text().strip(), max_age_seconds=120)
    node = socket.gethostname().split(".")[0]
    require(str(os.environ.get("SLURM_JOB_ID")) == proof["job_id"] and node == request["node"] and
            os.environ.get("SLURM_JOB_PARTITION") == "cpu" and int(os.environ.get("SLURM_CPUS_PER_TASK", "0")) == 16 and
            int(os.environ.get("SLURM_MEM_PER_NODE", "0")) == 65536 and os.environ.get("CUDA_VISIBLE_DEVICES") == "" and
            all(os.environ.get(key) == "1" for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")),
            "Actual own CPU16/64GiB Slurm/node/environment differs")
    require(Path(proof_path) == Path(request["startup_proof_path"]) and request["kind"] == "analysis" and
            request["memory_gib"] == 64 and request["cpus"] == 16 and request["exclusive_user"] is True and
            proof["memory_basis"] == queue_contract.MEMORY_BASIS, "Strict full-resource queued execution required")
    declared = {pin["path"]: pin for pin in request["source_references"]}
    for path in (Path(plan_path), Path(entry_path), Path(__file__), Path(queue_contract.__file__), Path(shared.__file__)):
        verify_small(shared.pin(path), declared)
    plan = shared.load(plan_path)
    require(plan["status"] == "READY" and plan["scope_key"] == scope and request.get("scope_key") == scope and
            plan["scope_parameters"] == request.get("scope_parameters") and
            type(plan["pilot"]) is bool and plan["pilot"] == request["pilot"], "New exact scope/plan/pilot binding required")
    require(plan["whole_output_cap_bytes"] == request["estimated_peak_output_bytes"] and
            request["wall_seconds"] <= 14400 and request["estimated_total_core_hours"] >= 0,
            "Whole immutable output/time budget differs")
    for pin in [*plan["code_sources"], *plan["authority_references"]]:
        verify_small(pin, declared)
    for pin in plan["anchors"].values():
        verify_small(pin, declared)
    validate_scientific_anchors(plan)
    require(proof["account_free_bytes"] - plan["whole_output_cap_bytes"] >= RESERVE, "Keep200GB after whole output")
    require(request["execution_argv"][-4:] == ["--plan", str(Path(plan_path)), "--root-preflight", str(Path(proof_path))],
            "Actual immutable execution argv does not bind this plan/startup proof")
    return plan, proof, validation


def validate_scientific_anchors(plan):
    """Separate full chemistry proof from still-unreleased final-common gates."""
    anchors = plan["anchors"]
    full = shared.load(anchors["full_x_receipt"]["path"])
    closure = shared.load(anchors["full_x_actual_closure"]["path"])
    require(full["job_id"] == closure["actual_parent"]["JobIDRaw"] == "4520414" and
            full["status"] == "FULL_X_RULE_PASS_COMMON_SCOPE_PENDING" and closure["receipt"] == anchors["full_x_receipt"] and
            closure["actual_parent"]["State"] == "COMPLETED" and closure["actual_parent"]["ExitCode"] == "0:0" and
            full["evaluated_records"] == full["complete_source_coverage"]["unique_records"] == 15879477 and
            full["chemical_admission_agreement"] == full["conditional_geometry_identity_selection_agreement"] == 1.0 and
            all(full["counts"][key] == 0 for key in ("native_rule_mismatch", "raw_native_rule_mismatch", "enriched_native_rule_mismatch",
                                                   "enrichment_metadata_mismatch", "unexplained")) and
            full["five_portable_flag_agreement"] >= .999 and full["all_mismatch_details_stored"] is True and
            full["common_population_scope_bound"] is False and full["final_training_or_full_expansion_gate_released"] is False,
            "Exact full-X chemistry proof required; common/final-training status is not relabeled")
    pins = shared.load(anchors["identity_input_pins"]["path"])
    compat = shared.load(anchors["compat_receipt"]["path"])
    require(pins["job_id"] == "4520547" and pins["status"] == "CURRENT_BOUND_INPUT_PINS_COMPLETE" and
            compat["job_id"] == "4520597" and compat["status"] == "PAIRED_PREFIX_CANDIDATE_EVALUATED_NOT_APPLIED" and
            compat["counts"]["classification:OLD_PASS_ALL_FIELDS_PRESERVED"] == 8198 and
            compat["counts"]["classification:RECOVERED_CONFIRMED_GENERIC_RING_ORDER"] == 753 and
            compat["counts"]["classification:CHEMICAL_REJECTION_UNCHANGED"] == 1049 and
            compat["complete_input_and_historical_coverage"] is True and compat["inputs_unchanged"] is True and
            compat["repair_applied"] is False and compat["pool_modified"] is False,
            "Current pins and actual bounded compatible-feature proof required; no full-space recovery claim")


def frame(path):
    path = Path(path)
    value = path.stat()
    require(path.is_absolute() and ".." not in path.parts and not path.is_symlink() and stat.S_ISREG(value.st_mode) and value.st_uid == 1278,
            "Task-owned literal regular body required")
    return {"device": value.st_dev, "inode": value.st_ino, "size": value.st_size, "mtime_ns": value.st_mtime_ns, "uid": value.st_uid}


def portable(value):
    return {key: value[key] for key in ("inode", "size", "mtime_ns", "uid")}


def file_pin(path, *, expected=None, expected_frame=None, stop=None):
    path = Path(path)
    before = frame(path)
    require(expected_frame is None or before == expected_frame, "Current same-node body frame differs")
    require(expected is None or before["size"] == expected["bytes"], "Body byte count differs")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        opened = os.fstat(stream.fileno())
        require((opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns) ==
                tuple(before[key] for key in ("device", "inode", "size", "mtime_ns")), "Opened body identity differs")
        for block in iter(lambda: stream.read(1 << 20), b""):
            if stop is not None and stop.is_set():
                raise CooperativeStop("Memory/output/wall stop before next hash block")
            digest.update(block)
        after = os.fstat(stream.fileno())
        require((opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns) ==
                (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns), "Body changed while open")
    pin = {"path": str(path), "bytes": before["size"], "sha256": digest.hexdigest()}
    require(frame(path) == before and (expected is None or pin == expected), "Complete body SHA/current frame differs")
    return pin


def fresh_output(path):
    path = Path(path)
    require(path.is_absolute() and ".." not in path.parts and path.is_relative_to(ARTIFACTS) and
            not path.exists() and not path.is_symlink(), "New owned output root required; no resume by overwriting")
    path.mkdir(parents=True)
    return path


def owned_bytes(path):
    seen, total = set(), 0
    for value in Path(path).rglob("*"):
        try:
            info = value.stat()
        except FileNotFoundError:
            continue  # Another owned worker may have atomically renamed it.
        if stat.S_ISREG(info.st_mode):
            require(not value.is_symlink() and info.st_uid == 1278, "Output ownership/symlink differs")
            identity = (info.st_dev, info.st_ino)
            if identity not in seen:
                total += info.st_size
                seen.add(identity)
    return total


def memory_sample(root_pid):
    memory = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        parts = line.split()
        if parts[0] in {"MemTotal:", "MemAvailable:"}:
            memory[parts[0][:-1]] = int(parts[1]) * 1024
    require(0 < memory["MemAvailable"] <= memory["MemTotal"], "Current MemAvailable unavailable")
    processes = {}
    for path in Path("/proc").iterdir():
        if not path.name.isdecimal():
            continue
        try:
            if path.stat().st_uid != os.getuid():
                continue
            text = (path / "stat").read_text()
            values = text[text.rfind(")") + 2:].split()
            processes[int(path.name)] = (int(values[1]), int(values[21]) * os.sysconf("SC_PAGE_SIZE"))
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            continue
    accepted = {root_pid}
    while True:
        added = {pid for pid, (parent, _) in processes.items() if parent in accepted} - accepted
        if not added:
            break
        accepted.update(added)
    return {"observed_monotonic_seconds": time.monotonic(), "total_bytes": memory["MemTotal"],
            "available_bytes": memory["MemAvailable"], "own_current_tree_rss_bytes": sum(processes[p][1] for p in accepted if p in processes),
            "own_process_count": len(accepted)}


class RuntimeBudget:
    """Sample current memory1s; cooperative stop prevents new dispatch, no kills."""
    def __init__(self, output, plan, proof, stop):
        self.output, self.plan, self.proof, self.stop = Path(output), plan, proof, stop
        self.closed = threading.Event()
        self.started = time.monotonic()
        self.reason = None
        self.last_output_sample = float("-inf")
        self.peak_output_bytes = self.peak_current_rss_bytes = self.samples = 0
        self.thread = threading.Thread(target=self._loop, name="expansion-current-memory", daemon=False)

    def _stop(self, reason):
        self.reason = self.reason or reason
        self.stop.set()

    def _loop(self):
        try:
            while not self.closed.is_set():
                started = time.monotonic()
                value = memory_sample(os.getpid())
                self.samples += 1
                self.peak_current_rss_bytes = max(self.peak_current_rss_bytes, value["own_current_tree_rss_bytes"])
                if value["own_current_tree_rss_bytes"] >= 64 * GIB * .75:
                    self._stop("OWN_CURRENT_RSS_AT75PCT_64GIB")
                if value["available_bytes"] < value["total_bytes"] * .15:
                    self._stop("CURRENT_NODE_MEMAVAILABLE_BELOW15PCT")
                if time.monotonic() - started > 2:
                    self._stop("CURRENT_MEMORY_SAMPLE_EXCEEDS2SECONDS")
                if time.monotonic() - self.started >= self.proof["request"]["wall_seconds"] - 120:
                    self._stop("STOP_NEW_DISPATCH_WITH120SECOND_DRAIN_MARGIN")
                self.closed.wait(1)
        except BaseException as exc:
            self._stop("CURRENT_MEMORY_MONITOR_FAILED:" + repr(exc))

    def __enter__(self):
        self.thread.start()
        self.check()
        return self

    def check(self, *, force=False):
        if self.stop.is_set():
            raise CooperativeStop(self.reason or "COOPERATIVE_WORKER_STOP")
        now = time.monotonic()
        if not force and now - self.last_output_sample < .5:
            return
        self.last_output_sample = now
        value = owned_bytes(self.output)
        self.peak_output_bytes = max(self.peak_output_bytes, value)
        if value > self.plan["whole_output_cap_bytes"] - 8 * 1024 ** 2:
            self._stop("OWNED_OUTPUT_CAP_REACHED")
        if self.stop.is_set():
            raise CooperativeStop(self.reason or "COOPERATIVE_WORKER_STOP")

    def __exit__(self, *args):
        self.closed.set()
        self.thread.join(timeout=5)
        require(not self.thread.is_alive(), "Current memory monitor did not close")
        if self.stop.is_set() and args[0] is None:
            raise CooperativeStop(self.reason or "Runtime stop detected while naturally closing")

    def receipt(self):
        return {"samples": self.samples, "peak_current_owned_tree_rss_bytes": self.peak_current_rss_bytes,
                "peak_owned_output_bytes": self.peak_output_bytes, "first_stop_reason": self.reason,
                "forced_signals_sent": False, "current_RSS_not_inherited_ru_maxrss": True,
                "startup_freshness_checked_once_not_after_hash_or_in_workers": True}
