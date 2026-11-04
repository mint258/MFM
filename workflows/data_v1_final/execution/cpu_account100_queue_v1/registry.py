"""Small local registry/claim/process metadata only; never inspect data bodies."""
from __future__ import annotations
from contextlib import contextmanager
import fcntl
import hashlib
import os
from pathlib import Path
import stat
from .shared import ROOT, load, need, pin, write_new
from .contract import registry_path, row_keys, validate_disjoint

REGISTRIES = ROOT / "control/cpu_auto_memory_registries"
PRIOR_V2_REGISTRIES = ROOT / "control/queue_v2_registries"
PRIOR_V3_REGISTRIES = ROOT / "control/queue_v3_registries"
CLAIMS = ROOT / "control/cpu_auto_memory_claims"
LOCKS = ROOT / "control/cpu_auto_memory_phase_locks"


def own_directory(path):
    path = Path(path); control = ROOT / "control"
    need(path.is_absolute() and ".." not in path.parts and
         (path == control or control in path.parents), "OWN_CONTROL_METADATA_PATH_REQUIRED")
    current = control
    for component in (None, *path.relative_to(control).parts):
        if component is not None:
            current = current / component
        try:
            current.mkdir(mode=0o700)
        except FileExistsError:
            pass
        info = current.lstat()
        need(stat.S_ISDIR(info.st_mode) and not current.is_symlink() and info.st_uid == 1278,
             "OWN_LITERAL_METADATA_DIRECTORY_REQUIRED")
    return path

@contextmanager
def lock_file(path):
    path = Path(path); own_directory(path.parent)
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(fd)
        need(stat.S_ISREG(info.st_mode) and info.st_uid == 1278 and info.st_nlink == 1,
             "OWN_ORDINARY_METADATA_LOCK_REQUIRED")
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        os.close(fd)


def phase_lock_path(path):
    value = registry_path(path)
    return LOCKS / (hashlib.sha256(value.encode()).hexdigest() + ".lock")


def load_request(ref):
    need(pin(ref["path"]) == ref, "REGISTERED_REQUEST_PHYSICAL_PIN_CHANGED")
    return load(ref["path"])


def existing_registries():
    paths = sorted((ROOT / "control").glob("queued_phase_*.json"))
    for directory in (PRIOR_V2_REGISTRIES, PRIOR_V3_REGISTRIES, REGISTRIES):
        if directory.exists():
            own_directory(directory)
            paths += sorted(directory.glob("*.json"))
    result = []
    for path in paths:
        need(not path.is_symlink(), "LITERAL_REGISTRY_REQUIRED")
        obj = load(path)
        if obj.get("schema") in {"REGISTERED_QUEUED_CPU_JOBS_V1", "REGISTERED_QUEUED_CPU_JOBS_V2", "REGISTERED_QUEUED_CPU_JOBS_V3", "REGISTERED_CPU_AUTO_MEMORY_JOBS_V1"}:
            result.append((str(path), obj))
        else:
            need(path.parent not in {PRIOR_V2_REGISTRIES, PRIOR_V3_REGISTRIES, REGISTRIES}, "UNRECOGNIZED_VERSIONED_REGISTRY_FILE")
    return result


def verify_disjoint(path, registry, *, new):
    path = registry_path(path)
    previous = existing_registries()
    matches = [item for item in previous if item[0] == path]
    if new:
        need(not matches, "REGISTRY_ALREADY_EXISTS_NO_REACTIVATION")
        previous.append((path, registry))
    else:
        need(len(matches) == 1 and matches[0][1] == registry, "EXACT_CURRENT_REGISTERED_PHASE_REQUIRED")
    return validate_disjoint(previous, load_request=load_request)


def claim_record(path, row, request):
    return {"schema": "PERSISTENT_CPU_AUTO_MEMORY_JOB_CLAIM_V1", "registry_path": registry_path(path),
            "keys": row_keys(row, request), "request_reference": row["request_reference"],
            "receipt_reference": row["receipt_reference"]}


def claim_paths(record):
    keys = record["keys"]
    return [CLAIMS / "jobs" / keys["job_id"],
            CLAIMS / "requests" / hashlib.sha256(keys["request_path"].encode()).hexdigest(),
            CLAIMS / "proofs" / hashlib.sha256(keys["proof_path"].encode()).hexdigest()]


def register_claims(path, registry):
    """Call under the registration lock. Partial claims persist on any failure."""
    records = []
    for row in registry["jobs"]:
        request = load_request(row["request_reference"])
        record = claim_record(path, row, request)
        for destination in claim_paths(record):
            own_directory(destination.parent)
            destination.mkdir(mode=0o700, exist_ok=False)
            write_new(destination / "claim.json", record)
        records.append(record)
    return records


def verify_claims(path, registry):
    for row in registry["jobs"]:
        record = claim_record(path, row, load_request(row["request_reference"]))
        for destination in claim_paths(record):
            need(destination.is_dir() and not destination.is_symlink()
                 and destination.lstat().st_uid == 1278, "PERSISTENT_JOB_CLAIM_REQUIRED")
            need(load(destination / "claim.json") == record, "JOB_CLAIM_BELONGS_TO_DIFFERENT_PHASE")
    return True


def process_identity(pid):
    need(type(pid) is int and pid > 0, "EXACT_PROCESS_PID_REQUIRED")
    proc = Path("/proc") / str(pid)
    raw = (proc / "stat").read_text(); fields = raw[raw.rfind(")") + 2:].split()
    argv_raw = (proc / "cmdline").read_bytes()
    cgroup = (proc / "cgroup").read_bytes()
    need(len(argv_raw) <= 128 * 1024 and len(cgroup) <= 128 * 1024, "BOUNDED_PROC_IDENTITY_REQUIRED")
    owners = [line.split()[1:] for line in (proc / "status").read_text().splitlines() if line.startswith("Uid:")]
    need(len(owners) == 1 and len(owners[0]) == 4 and all(int(v) == 1278 for v in owners[0]),
         "EXACT_OWN_OBSERVER_UID_REQUIRED")
    argv = [part.decode("utf-8") for part in argv_raw.rstrip(b"\0").split(b"\0")]
    need(argv_raw and argv, "FULL_OBSERVER_ARGV_REQUIRED")
    pgid, sid = int(fields[2]), int(fields[3])
    need(pgid == os.getpgid(pid) and sid == os.getsid(pid), "PROC_GROUP_SESSION_CHANGED")
    after_raw = (proc / "stat").read_text()
    after = after_raw[after_raw.rfind(")") + 2:].split()
    need((after[19], after[2], after[3]) == (fields[19], fields[2], fields[3]),
         "PROCESS_IDENTITY_CHANGED_DURING_OBSERVATION")
    return {"pid": pid, "uid": 1278, "start_ticks": int(fields[19]),
        "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
        "pgid": pgid, "sid": sid, "argv": argv,
        "argv_sha256": hashlib.sha256(argv_raw).hexdigest(),
        "cgroup": cgroup.decode("utf-8"), "cgroup_sha256": hashlib.sha256(cgroup).hexdigest()}
