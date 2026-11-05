"""Bind and sample this job's private scratch/compiler storage, without cleanup.

Observed maxima are sampling lower bounds, never exact filesystem peaks. Reused
compiler bytes are recorded as existing inputs, separately from observed growth.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import socket
import stat
import threading
import time

SCHEMA = "model_v3_private_storage_v1"
MARKER = ".model_v3_private_storage.json"
TASK_SCRATCH_DIRECTORY = Path("/tmp")


def _ordinary_ancestors(path):
    path = Path(path)
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("Absolute private storage path without parent traversal required")
    for ancestor in reversed((path, *path.parents)):
        try:
            entry = ancestor.lstat()
        except FileNotFoundError:
            continue
        if not stat.S_ISDIR(entry.st_mode):
            raise ValueError("Private storage ancestor is not an ordinary directory: " + str(ancestor))
    return path


def _identity(path):
    value = Path(path).lstat()
    if not stat.S_ISDIR(value.st_mode) or value.st_uid != os.getuid() or stat.S_IMODE(value.st_mode) != 0o700:
        raise ValueError("Private storage root must be an owned ordinary mode0700 directory: " + str(path))
    return {"path": str(path), "uid": value.st_uid, "device": value.st_dev, "inode": value.st_ino}


def _write_exclusive(path, value):
    raw = (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return hashlib.sha256(raw).hexdigest()


def _read_ordinary(path, maximum=1024**2):
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, "rb") as stream:
        before = os.fstat(stream.fileno())
        if (not stat.S_ISREG(before.st_mode) or before.st_uid != os.getuid()
                or before.st_nlink != 1 or before.st_size > maximum):
            raise ValueError("Owned bounded single-link ordinary storage metadata required")
        raw = stream.read(maximum + 1)
        after = os.fstat(stream.fileno())
        if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
                after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns) or len(raw) != after.st_size:
            raise ValueError("Storage metadata changed while reading")
    return raw


def sampled_storage_bytes(roots):
    """Strict dirfd census; Unix sockets allowed only inside the task scratch."""
    for attempt in range(3):
        try:
            seen, total, entries = set(), 0, 0
            per_root = {}
            for root in roots:
                path = _ordinary_ancestors(root["path"])
                if _identity(path) != {key: root[key] for key in ("path", "uid", "device", "inode")}:
                    raise ValueError("Bound private storage root identity changed: " + str(path))
                descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
                subtotal = 0
                def visit(directory, display):
                    nonlocal total, subtotal, entries
                    info = os.fstat(directory)
                    if (info.st_uid, info.st_dev) != (root["uid"], root["device"]):
                        raise ValueError("Private storage UID/device changed: " + display)
                    key = info.st_dev, info.st_ino
                    if key in seen:
                        raise ValueError("Private storage roots overlap or repeat an inode")
                    seen.add(key)
                    total += info.st_size
                    subtotal += info.st_size
                    with os.scandir(directory) as iterator:
                        for entry in iterator:
                            entries += 1
                            if entries > 100_000:
                                raise ValueError("Private storage entry count exceeded bounded census")
                            item = entry.stat(follow_symlinks=False)
                            where = display + "/" + entry.name
                            if (item.st_uid, item.st_dev) != (root["uid"], root["device"]):
                                raise ValueError("Private storage UID/device changed: " + where)
                            if stat.S_ISDIR(item.st_mode):
                                child = os.open(entry.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
                                try:
                                    opened = os.fstat(child)
                                    if (opened.st_dev, opened.st_ino) != (item.st_dev, item.st_ino):
                                        raise ValueError("Private storage directory changed before opening: " + where)
                                    visit(child, where)
                                finally:
                                    os.close(child)
                            else:
                                allowed = stat.S_ISREG(item.st_mode) or (root["kind"] == "task_scratch" and stat.S_ISSOCK(item.st_mode))
                                if not allowed or item.st_nlink != 1:
                                    raise ValueError("Unsupported private storage entry/link: " + where)
                                key = item.st_dev, item.st_ino
                                if key in seen:
                                    raise ValueError("Private storage inode repeated: " + where)
                                seen.add(key)
                                total += item.st_size
                                subtotal += item.st_size
                try:
                    opened = os.fstat(descriptor)
                    if (opened.st_dev, opened.st_ino) != (root["device"], root["inode"]):
                        raise ValueError("Private root changed before opening")
                    visit(descriptor, str(path))
                finally:
                    os.close(descriptor)
                per_root[str(path)] = subtotal
            return {"bytes": total, "root_bytes": per_root, "entries": entries}
        except FileNotFoundError:
            if attempt == 2:
                raise


def _job_context():
    job = os.environ.get("SLURM_JOB_ID", "")
    if not re.fullmatch(r"[0-9]+", job):
        raise ValueError("Actual numeric SLURM_JOB_ID required for private scratch")
    return {"job_id": job, "uid": os.getuid(), "node": socket.gethostname(),
            "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip()}


class PrivateStorage:
    def __del__(self):
        descriptor = getattr(self, "_cache_lock", None)
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass
            self._cache_lock = None

    def __init__(self, scratch, *, budget_bytes, cache_root=None, cache_key=None, reuse_cache=False):
        context = _job_context()
        scratch = Path(scratch)
        if scratch != TASK_SCRATCH_DIRECTORY / ("mv3n_" + context["job_id"]):
            raise ValueError("Private scratch must be exactly /tmp/mv3n_<actual SLURM_JOB_ID>")
        if not 32 * 1024**2 <= budget_bytes <= 2 * 1024**3:
            raise ValueError("Private storage cap must be between32MiB and2GiB")
        if cache_root is None and (cache_key is not None or reuse_cache):
            raise ValueError("Explicit compiler cache root required with key/reuse")
        if cache_root is not None:
            cache_root = _ordinary_ancestors(cache_root)
            if not isinstance(cache_key, str) or not re.fullmatch(r"[0-9a-f]{64}", cache_key):
                raise ValueError("Explicit64hex compiler cache compatibility key required")
            if cache_root.is_relative_to(scratch) or scratch.is_relative_to(cache_root):
                raise ValueError("Reusable cache must be disjoint from task scratch")
            if not cache_root.parent.is_dir():
                raise ValueError("Reviewed existing compiler cache parent required")
        _ordinary_ancestors(scratch.parent)
        scratch.mkdir(mode=0o700, exist_ok=False)
        roots = [{**_identity(scratch), "kind": "task_scratch", "reused": False}]
        _write_exclusive(scratch / MARKER, {"schema": SCHEMA, **context, "root": roots[0]})
        if cache_root is None:
            cache_root = scratch / "compiler_cache"
            cache_root.mkdir(mode=0o700)
        else:
            cache_exists = cache_root.exists()
            if cache_exists != bool(reuse_cache):
                raise ValueError("Existing compiler cache requires explicit reuse; fresh cache must not exist")
            if not cache_exists:
                cache_root.mkdir(mode=0o700)
            root = {**_identity(cache_root), "kind": "compiler_cache", "reused": bool(reuse_cache)}
            marker = {"schema": SCHEMA, "uid": context["uid"], "node": context["node"],
                      "compatibility_key": cache_key,
                      "root": {key: root[key] for key in ("path", "uid", "device", "inode")}}
            if reuse_cache:
                if json.loads(_read_ordinary(cache_root / MARKER)) != marker:
                    raise ValueError("Reusable compiler cache marker/key/node does not match")
            else:
                _write_exclusive(cache_root / MARKER, marker)
            # An explicitly reused cache is exclusive to this invocation while
            # measured; never count concurrent writers as this job's growth.
            import fcntl
            self._cache_lock = os.open(cache_root / ".model_v3_cache.lock",
                                       os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
            lock_info = os.fstat(self._cache_lock)
            if not stat.S_ISREG(lock_info.st_mode) or lock_info.st_uid != os.getuid() or lock_info.st_nlink != 1:
                os.close(self._cache_lock)
                self._cache_lock = None
                raise ValueError("Owned single-link compiler cache lock required")
            try:
                fcntl.flock(self._cache_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BaseException:
                os.close(self._cache_lock)
                self._cache_lock = None
                raise
            roots.append(root)
        environment = {"TMPDIR": str(scratch), "XDG_CACHE_HOME": str(scratch / "xdg"),
                       "TORCHINDUCTOR_CACHE_DIR": str(cache_root / "inductor"),
                       "TRITON_CACHE_DIR": str(cache_root / "triton"),
                       "TORCH_EXTENSIONS_DIR": str(cache_root / "extensions"),
                       "CUDA_CACHE_PATH": str(scratch / "cuda")}
        # Reject any pre-existing cache link/type before mkdir follows parents.
        sampled_storage_bytes(roots)
        for value in environment.values():
            _ordinary_ancestors(value)
            Path(value).mkdir(mode=0o700, parents=True, exist_ok=True)
        self.roots, self.budget_bytes = roots, budget_bytes
        initial = sampled_storage_bytes(roots)
        self.bindings = {"schema": SCHEMA, **context, "roots": roots, "environment": environment,
                         "compiler_cache_key": cache_key, "compiler_cache_reused": bool(reuse_cache),
                         "initial_bytes": initial, "private_storage_budget_bytes": budget_bytes,
                         "peak_semantics": "sampled maximum is a lower bound; short-lived files may be missed",
                         "cache_contains": "compiler artifacts only; no dataset/weights",
                         "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
        self._lock, self._stop = threading.Lock(), threading.Event()
        self._thread, self._failure = None, None
        self._last, self._max, self._samples = initial, initial["bytes"], 1
        self.check()

    def sample(self):
        current = sampled_storage_bytes(self.roots)
        with self._lock:
            self._last = current
            self._max = max(self._max, current["bytes"])
            self._samples += 1
        if current["bytes"] > self.budget_bytes:
            raise MemoryError("Private scratch/compiler storage exceeded explicit budget")
        return self.observation()

    def observation(self):
        with self._lock:
            return {"last": self._last, "sampled_max_bytes": self._max,
                    "sampled_growth_above_initial_bytes": max(0, self._max - self.bindings["initial_bytes"]["bytes"]),
                    "samples": self._samples, "sample_interval_seconds": .5,
                    "exact_peak": False, "first_sampling_failure": self._failure,
                    "budget_bytes": self.budget_bytes}

    def check(self):
        result = self.observation()
        if result["first_sampling_failure"]:
            raise RuntimeError("Private storage sampling failed: " + str(result["first_sampling_failure"]))
        if result["sampled_max_bytes"] > self.budget_bytes:
            raise MemoryError("Private scratch/compiler storage exceeded explicit budget")
        return result

    def start(self):
        def run():
            while not self._stop.wait(.5):
                try:
                    self.sample()
                except BaseException as exc:
                    with self._lock:
                        self._failure = {"type": type(exc).__name__, "message": str(exc)}
                    return
        self._thread = threading.Thread(target=run, name="model-v3-private-storage", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
            if self._thread.is_alive():
                raise RuntimeError("Private storage sampler did not join within5seconds")
        try:
            self.sample()
            return self.check()
        finally:
            descriptor = getattr(self, "_cache_lock", None)
            if descriptor is not None:
                os.close(descriptor)
                self._cache_lock = None


def load_storage_bindings():
    """Child verifies supervisor receipt after env is set, before making files."""
    name = os.environ.get("MODEL_V3_STORAGE_BINDINGS_PATH")
    pin = os.environ.get("MODEL_V3_STORAGE_BINDINGS_SHA256", "")
    if not name or not re.fullmatch(r"[0-9a-f]{64}", pin):
        raise ValueError("Supervisor private storage bindings and prelaunch SHA required")
    path = Path(name)
    _ordinary_ancestors(path.parent)
    raw = _read_ordinary(path)
    if hashlib.sha256(raw).hexdigest() != pin:
        raise ValueError("Supervisor storage receipt changed")
    value = json.loads(raw)
    if value.get("schema") != SCHEMA or any(value.get(key) != expected for key, expected in _job_context().items()):
        raise ValueError("Supervisor storage receipt belongs to another job/UID/node/boot")
    if any(os.environ.get(key) != expected for key, expected in value["environment"].items()):
        raise ValueError("Private compiler/temp environment differs from supervisor binding")
    sampled_storage_bytes(value["roots"])
    return {"receipt_path": str(path), "receipt_sha256": pin, **value}
