"""Pure-stdlib, fail-closed queued execution contracts; no I/O or scheduler calls.

Only validate_request invokes the caller's read_small callback for small pinned
code/metadata. Data references are validated as locators and never opened.
PENDING/release is not admission. Science requires a fresh actual startup proof.
"""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
import math
from pathlib import PurePosixPath
import re

PROJECT = "/share/home/zixiao/descriptor_analysis"
RUN = PROJECT + "/runs/data_v1_20261025"
PYTHON = "/share/home/zixiao/.conda/envs/chemprop/bin/python"
MIB = 1024**2
GIB = 1024**3
SMALL_CAP = 2 * MIB
MEMORY_BASIS = "STRICT_ALL_USERS_DECLARED_85PCT_NO_EXEMPTION"
CPU_NODES = {f"compute-0-{n}" for n in (2, *range(8, 20))}
QM_NODES = {f"compute-0-{n}" for n in range(14, 20)}
ACTIVE = {"RUNNING", "COMPLETING", "CONFIGURING", "SUSPENDED", "STOPPED", "RESIZING", "STAGE_OUT"}
INACTIVE = {"PENDING", "COMPLETED", "CANCELLED", "FAILED", "TIMEOUT", "OUT_OF_MEMORY", "NODE_FAIL",
            "PREEMPTED", "BOOT_FAIL", "DEADLINE", "REVOKED", "SPECIAL_EXIT"}
BODY_SUFFIXES = {".parquet", ".arrow", ".ipc", ".sqlite", ".db", ".lmdb", ".dict", ".gz", ".npz", ".npy"}


class ContractError(ValueError):
    def __init__(self, code, details=None):
        self.code, self.details = code, details
        super().__init__(code if details is None else code + ":" + str(details))


def _need(ok, code, details=None):
    if not ok:
        raise ContractError(code, details)


def _integer(value, code, minimum=0):
    _need(type(value) is int and value >= minimum, code, value)
    return value


def _finite(value, code):
    _need(type(value) in (int, float) and math.isfinite(value), code, value)
    return value


def _literal_path(value):
    _need(isinstance(value, str) and value and "\x00" not in value and "\n" not in value and "\r" not in value,
          "LITERAL_ABSOLUTE_POSIX_PATH_REQUIRED", value)
    p = PurePosixPath(value)
    _need(p.is_absolute() and ".." not in p.parts and str(p) == value, "LITERAL_ABSOLUTE_POSIX_PATH_REQUIRED", value)
    return value


def _pin(value, small=False):
    _need(isinstance(value, dict) and {"path", "bytes", "sha256"} <= set(value), "EXACT_REFERENCE_REQUIRED")
    result = {key: value[key] for key in ("path", "bytes", "sha256")}
    _literal_path(result["path"])
    _integer(result["bytes"], "REFERENCE_BYTE_COUNT_INVALID")
    _need(isinstance(result["sha256"], str) and re.fullmatch(r"[a-f0-9]{64}", result["sha256"]), "REFERENCE_SHA256_INVALID")
    if small:
        _need(result["bytes"] <= SMALL_CAP and PurePosixPath(result["path"]).suffix.lower() not in BODY_SUFFIXES,
              "SMALL_SOURCE_ONLY_NO_DATA_BODY_READ", result["path"])
    return result


def _same(left, right):
    return json.dumps(left, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":")) == \
        json.dumps(right, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


def _memory_bytes(value):
    _need(isinstance(value, str), "SCHEDULER_MEMORY_UNAVAILABLE", value)
    match = re.fullmatch(r"(\d+)([KMGTP]?)(?:i?B)?", value)
    _need(match is not None, "SCHEDULER_MEMORY_UNAVAILABLE", value)
    return int(match[1]) * {"K": 1024, "M": MIB, "G": GIB, "T": 1024**4, "P": 1024**5, "": MIB}[match[2]]


def _uint(value, code):
    _need(isinstance(value, str) and value.isdecimal(), code, value)
    return int(value)


def _wall(value):
    match = re.fullmatch(r"(?:(\d+)-)?(\d+):(\d{2}):(\d{2})", value)
    _need(match is not None and int(match[3]) < 60 and int(match[4]) < 60, "SBATCH_WALL_INVALID", value)
    return int(match[1] or 0) * 86400 + int(match[2]) * 3600 + int(match[3]) * 60 + int(match[4])


def _directives(text):
    _need(isinstance(text, str) and text.startswith("#!/bin/bash\n") and "\r" not in text, "LF_BASH_SCRIPT_REQUIRED")
    found = {}
    for line in text.splitlines():
        if not line.lstrip().startswith("#SBATCH"):
            continue
        match = re.fullmatch(r"#SBATCH --([\w-]+)=(\S+)", line)
        _need(match is not None, "UNRECOGNIZED_SBATCH_DIRECTIVE", line)
        _need(match[1] not in found, "DUPLICATE_SBATCH_DIRECTIVE", match[1])
        found[match[1]] = match[2]
    return found


def _script_contract(request, text):
    d = _directives(text)
    expected = {"job-name": request["job_name"], "partition": "cpu", "nodelist": request["node"],
                "nodes": "1", "ntasks": "1", "cpus-per-task": "16", "exclusive": "user"}
    _need(all(d.get(k) == v for k, v in expected.items()), "SBATCH_RESOURCE_IDENTITY_DIFFERS", expected)
    _need("mem" in d and _memory_bytes(d["mem"]) == 64 * GIB and "time" in d and
          _wall(d["time"]) == request["wall_seconds"], "SBATCH_MEMORY_OR_WALL_DIFFERS")
    forbidden = {"gres", "gpus", "gpus-per-node", "gpus-per-task", "cpus-per-gpu", "mem-per-cpu", "mem-per-gpu",
                 "ntasks-per-node", "overcommit", "oversubscribe", "requeue"}
    _need(not forbidden.intersection(d), "SBATCH_GPU_OVERCOMMIT_OR_REQUEUE_FORBIDDEN")
    _need(d.get("chdir", PROJECT) == PROJECT, "SBATCH_WORKDIR_DIFFERS")
    return d


def validate_request(request, *, read_small, script_text=None):
    """Check the immutable64GiB request, small exact pins and CPU script only."""
    _need(request.get("schema") == "DATA_V1_QUEUED_REQUEST_V1", "QUEUED_REQUEST_SCHEMA_REQUIRED")
    _need(request.get("kind") in {"analysis", "qm", "conformer"}, "UNKNOWN_COMPUTE_ROLE")
    allowed = CPU_NODES if request["kind"] == "analysis" else QM_NODES
    _need(request.get("node") in allowed, "NODE_OUTSIDE_AUTHORIZED_CPU_ROLE")
    _need(type(request.get("cpus")) is int and request["cpus"] == 16 and
          type(request.get("memory_gib")) is int and request["memory_gib"] == 64, "EXACT_16CPU_64GIB_REQUIRED")
    _integer(request.get("wall_seconds"), "WALL_INVALID", 1)
    _need(request["wall_seconds"] <= 4 * 3600, "STRICT_SITE_FOUR_HOUR_WALL_REQUIRED")
    _integer(request.get("estimated_peak_output_bytes"), "WHOLE_OUTPUT_BUDGET_INVALID")
    _need(type(request.get("pilot")) is bool, "PILOT_BOOLEAN_REQUIRED")
    _need(_finite(request.get("estimated_total_core_hours"), "CORE_HOURS_INVALID") >= 0, "CORE_HOURS_INVALID")
    _need(request.get("workdir") == PROJECT and request.get("exclusive_user") is True, "WORKDIR_OR_USER_EXCLUSIVITY_REQUIRED")
    _need(isinstance(request.get("job_name"), str) and re.fullmatch(r"dv1_q_[A-Za-z0-9_]+", request["job_name"]), "NEW_QUEUED_JOB_NAME_REQUIRED")
    _need(request.get("startup_proof_path") == RUN + "/control/queue_startup/" + request["job_name"] + ".json" and
          request.get("startup_wait_seconds") == 120, "EXACT_STARTUP_PROOF_PATH_AND_WAIT_REQUIRED")
    review = request.get("root_review", {})
    _need(review.get("status") == "APPROVED" and review.get("reviewer") == "root", "ROOT_REVIEW_REQUIRED")
    _need(request.get("resource_policy") != "CPU_BOUNDED_TEST_LIVE_MEMORY_V1" and
          request.get("memory_exemption", False) is False, "NO_MEMORY_EXEMPTION_FOR_QUEUED_EXECUTION")
    argv = request.get("execution_argv")
    _need(isinstance(argv, list) and argv and argv[0] == PYTHON and
          all(isinstance(v, str) and not any(c in v for c in ("\x00", "\n", "\r")) for v in argv), "EXACT_EXECUTION_ARGV_REQUIRED")
    dependencies = request.get("dependencies", [])
    _need(isinstance(dependencies, list) and all(isinstance(v, str) and v.isdecimal() for v in dependencies) and
          len(set(dependencies)) == len(dependencies), "EXACT_AFTEROK_JOB_IDS_REQUIRED")
    sources = request.get("source_references")
    _need(isinstance(sources, list) and sources, "SOURCE_REFERENCES_REQUIRED")
    normalized = [_pin(p, small=True) for p in sources]
    _need(len({p["path"] for p in normalized}) == len(normalized), "DUPLICATE_SOURCE_REFERENCE")
    script = _pin(request.get("script_reference"), small=True)
    authority = _pin(request.get("queue_authority_reference"), small=True)
    _need(authority in normalized, "EXACT_QUEUE_AUTHORITY_PIN_NOT_IN_SOURCES")
    bodies = request.get("data_references", [])
    _need(isinstance(bodies, list), "DATA_LOCATOR_LIST_REQUIRED")
    locators = [_pin(p) for p in bodies]  # Deliberately no read/stat callback.
    _need(len({p["path"] for p in locators}) == len(locators), "DUPLICATE_DATA_LOCATOR")
    _need(not {p["path"] for p in locators}.intersection(p["path"] for p in normalized), "DATA_BODY_CANNOT_BE_SMALL_SOURCE")
    seen = {}
    for pin in [script, *normalized]:
        if pin["path"] in seen:
            _need(seen[pin["path"]] == pin, "CONFLICTING_SCRIPT_SOURCE_PIN")
            continue
        raw = read_small(pin["path"])
        _need(isinstance(raw, bytes) and len(raw) <= SMALL_CAP and len(raw) == pin["bytes"] and
              hashlib.sha256(raw).hexdigest() == pin["sha256"], "SMALL_SOURCE_PHYSICAL_PIN_CHANGED", pin["path"])
        seen[pin["path"]] = pin
        if pin == script:
            actual_text = raw.decode("utf-8")
    if script_text is not None:
        _need(script_text == actual_text, "SUPPLIED_SCRIPT_NOT_ACTUAL_PINNED_BYTES")
    _script_contract(request, actual_text)
    return {"status": "VALIDATED_QUEUED_REQUEST_NOT_ADMISSION", "job_name": request["job_name"],
            "source_count": len(normalized), "data_locator_count": len(locators), "data_bodies_read_or_stat": False}


def _fields(raw):
    _need(isinstance(raw, str), "SCONTROL_TEXT_REQUIRED")
    matches = list(re.finditer(r"(?<!\S)([A-Za-z][A-Za-z0-9_./+-]*)=", raw))
    _need(matches, "SCONTROL_FIELDS_UNAVAILABLE")
    result = {"_raw": raw}
    for index, match in enumerate(matches):
        key = match[1]
        _need(key not in result, "DUPLICATE_OR_AMBIGUOUS_SCONTROL_FIELD", key)
        result[key] = raw[match.end():matches[index + 1].start() if index + 1 < len(matches) else len(raw)].strip()
    return result


def parse_scontrol_jobs(text):
    """Parse all-user --oneliner or multiline records; duplicate IDs fail closed."""
    if not text.strip() or text.strip() == "No jobs in the system":
        return []
    starts = list(re.finditer(r"(?<!\S)JobId=", text))
    _need(starts and not text[:starts[0].start()].strip(), "SCONTROL_JOB_RECORDS_REQUIRED")
    jobs = [_fields(text[m.start():starts[i + 1].start() if i + 1 < len(starts) else len(text)]) for i, m in enumerate(starts)]
    _need(all(re.fullmatch(r"\d+(?:_\d+|\+\d+)?", j.get("JobId", "")) for j in jobs), "SCONTROL_JOB_ID_INVALID")
    _need(len({j["JobId"] for j in jobs}) == len(jobs), "DUPLICATE_JOB_RECORD")
    return jobs


def parse_scontrol_node(text):
    node = _fields(text)
    _need(node.get("NodeName") in CPU_NODES, "EXACT_CPU_NODE_METADATA_REQUIRED")
    for key in ("RealMemory", "AllocMem", "CPUTot", "CPUAlloc"):
        _uint(node.get(key), "NODE_FIELD_UNAVAILABLE:" + key)
    _need("cpu" in node.get("Partitions", "").split(","), "NODE_NOT_IN_CPU_PARTITION")
    return node


def _job(value):
    if isinstance(value, str):
        rows = parse_scontrol_jobs(value)
        _need(len(rows) == 1, "ONE_JOB_METADATA_RECORD_REQUIRED")
        return rows[0]
    _need(isinstance(value, dict), "JOB_METADATA_REQUIRED")
    if "metadata" in value:
        return _job(value["metadata"])
    return value


def _uid(job):
    value = job.get("UserId", "")
    match = re.fullmatch(r"[^\s()]+\((\d+)\)", str(value))
    if match:
        return int(match[1])
    return _uint(value, "JOB_UID_UNAVAILABLE")


def _nodes(value):
    _need(isinstance(value, str), "ALLOCATED_NODELIST_UNAVAILABLE")
    if value in {"(null)", "None", ""}:
        return set()
    tokens, current, depth = [], "", 0
    for char in value:
        depth += (char == "[") - (char == "]")
        _need(depth in {0, 1}, "NODELIST_UNRECOGNIZED", value)
        if char == "," and depth == 0:
            tokens.append(current); current = ""
        else:
            current += char
    _need(depth == 0, "NODELIST_UNRECOGNIZED", value)
    tokens.append(current)
    result = set()
    for token in tokens:
        match = re.fullmatch(r"([^\[\]]+)\[([\d,-]+)\]([^\[\]]*)", token)
        if not match:
            _need(token and "[" not in token and "]" not in token, "NODELIST_UNRECOGNIZED", value)
            result.add(token)
            continue
        for part in match[2].split(","):
            bounds = part.split("-")
            _need(1 <= len(bounds) <= 2 and all(p.isdecimal() for p in bounds), "NODELIST_UNRECOGNIZED", value)
            start, end = int(bounds[0]), int(bounds[-1])
            _need(start <= end and end - start <= 10000, "NODELIST_UNRECOGNIZED", value)
            width = len(bounds[0]) if bounds[0].startswith("0") else 0
            result.update(match[1] + str(i).zfill(width) + match[3] for i in range(start, end + 1))
    return result


def _job_memory(job):
    options = []
    if "MinMemoryNode" in job:
        options.append(_memory_bytes(job["MinMemoryNode"]))
    if "MinMemoryCPU" in job:
        options.append(_memory_bytes(job["MinMemoryCPU"]) * _uint(job.get("NumCPUs"), "JOB_CPU_COUNT_UNAVAILABLE"))
    _need(options and len(set(options)) == 1, "OTHER_JOB_MEMORY_DECLARATION_MISSING_OR_CONFLICTING", job.get("JobId"))
    _need(options[0] > 0, "OTHER_JOB_ZERO_MEMORY_IS_UNBOUNDED_NO_ADMISSION", job.get("JobId"))
    return options[0]


def _mib(value):
    return value // MIB if value % MIB == 0 else value / MIB


def admit_memory(request, node, jobs, *, own_job_id=None, uid=1278):
    """Strict declared85%; own allocation is removed once, never double-counted."""
    node = parse_scontrol_node(node) if isinstance(node, str) else node
    _need(node.get("NodeName") == request["node"], "MEMORY_NODE_DIFFERS")
    _need(request["cpus"] == 16 and request["memory_gib"] == 64, "EXACT_16CPU_64GIB_REQUIRED")
    real = _uint(node.get("RealMemory"), "REAL_MEMORY_UNAVAILABLE") * MIB
    allocated = _uint(node.get("AllocMem"), "ALLOC_MEMORY_UNAVAILABLE") * MIB
    total_cpu = _uint(node.get("CPUTot"), "CPU_TOTAL_UNAVAILABLE")
    alloc_cpu = _uint(node.get("CPUAlloc"), "CPU_ALLOC_UNAVAILABLE")
    _need(real > 0 and alloc_cpu <= total_cpu and "cpu" in node.get("Partitions", "").split(","), "NODE_CAPACITY_INVALID")
    values = [_job(j) for j in jobs]
    _need(len({j.get("JobId") for j in values}) == len(values), "DUPLICATE_JOB_RECORD")
    own_memory = own_cpu = other_sum = listed_other_cpu = 0
    own_seen = 0
    other = []
    for job in values:
        state = job.get("JobState", "").split("+")[0]
        _need(state in ACTIVE | INACTIVE, "JOB_STATE_UNAVAILABLE", job.get("JobId"))
        if state in INACTIVE:
            _need(job.get("JobId") != own_job_id, "OWN_JOB_NOT_ALLOCATED")
            continue
        allocated_nodes = _nodes(job.get("NodeList"))
        _need(allocated_nodes, "ACTIVE_JOB_NODELIST_UNAVAILABLE", job.get("JobId"))
        if request["node"] not in allocated_nodes:
            _need(job.get("JobId") != own_job_id, "OWN_JOB_ON_DIFFERENT_NODE")
            continue
        owner = _uid(job)
        cpus = _uint(job.get("NumCPUs"), "JOB_CPU_COUNT_UNAVAILABLE")
        memory = _job_memory(job)
        if own_job_id is not None and job.get("JobId") == str(own_job_id):
            _need(owner == uid and state == "RUNNING" and cpus == 16 and memory == 64 * GIB and
                  allocated_nodes == {request["node"]}, "OWN_JOB_NOT_EXACT_KNOWN_16CPU_64G_ALLOCATION")
            own_seen += 1
            own_memory, own_cpu = memory, cpus
            continue
        other_sum += memory
        listed_other_cpu += cpus  # Count all CPUs for multi-node per-CPU declarations conservatively.
        other.append({"job_id": job["JobId"], "uid": owner, "memory_mib_budgeted_on_node": _mib(memory),
                      "metadata": job.get("_raw", {k: v for k, v in job.items() if k != "_raw"})})
    _need(own_job_id is None or own_seen == 1, "EXACT_OWN_JOB_METADATA_REQUIRED_BEFORE_SUBTRACTION")
    other_alloc_cpu = max(0, alloc_cpu - own_cpu)
    _need(listed_other_cpu >= other_alloc_cpu, "INCOMPLETE_ALL_USER_JOB_INVENTORY")
    _need(total_cpu - other_alloc_cpu >= 16, "WAIT_FOR_REAL_CPU_CAPACITY")
    other_alloc = max(0, allocated - own_memory)  # CR_CORE may report AllocMem below own declaration.
    committed = max(other_alloc, other_sum)
    projected = committed + 64 * GIB
    _need(projected * 100 <= real * 85, "WAIT_FOR_STRICT_ALL_USER_DECLARED_MEMORY", {
        "committed_other_mib": _mib(committed), "projected_mib": _mib(projected), "real_mib": _mib(real)})
    return {"status": "ADMITTED", "memory_basis": MEMORY_BASIS, "node": request["node"],
        "real_memory_mib": _mib(real), "alloc_memory_mib": _mib(allocated), "own_job_id": own_job_id,
        "own_memory_mib_excluded": _mib(own_memory), "alloc_memory_other_mib": _mib(other_alloc),
        "sum_other_declared_memory_mib": _mib(other_sum), "committed_memory_mib": _mib(committed),
        "requested_memory_mib": 65536, "projected_memory_mib": _mib(projected), "allowed_memory_mib": real * 85 / (100 * MIB),
        "existing_jobs_all_users": other, "cpu_allocation": {"total": total_cpu, "allocated": alloc_cpu,
            "own_excluded": own_cpu, "available_for_request": total_cpu - other_alloc_cpu}}


def validate_startup_job(request, job, *, expected_job_id, uid, script_reference, script_text=None):
    job = _job(job)
    _need(isinstance(expected_job_id, str) and expected_job_id.isdecimal() and job.get("JobId") == expected_job_id,
          "ACTUAL_STARTUP_JOB_ID_DIFFERS")
    _need(_uid(job) == uid == 1278 and job.get("JobState") == "RUNNING", "ACTUAL_ROOT_RUNNING_JOB_REQUIRED")
    _need(job.get("JobName") == request["job_name"] and job.get("Partition") == "cpu" and
          _nodes(job.get("NodeList")) == {request["node"]} and
          _uint(job.get("NumNodes"), "STARTUP_NUM_NODES_UNAVAILABLE") == 1, "ACTUAL_STARTUP_NODE_OR_NAME_DIFFERS")
    _need(_uint(job.get("NumCPUs"), "STARTUP_CPU_COUNT_UNAVAILABLE") == 16 and
          _job_memory(job) == 64 * GIB, "ACTUAL_STARTUP_ALLOCATION_NOT_EXACT_16CPU_64G")
    _need(job.get("OverSubscribe") == "USER" and job.get("Requeue") == "0", "ACTUAL_EXCLUSIVE_USER_NO_REQUEUE_REQUIRED")
    if "NumTasks" in job:
        _need(job["NumTasks"] == "1", "ACTUAL_ONE_TASK_REQUIRED")
    script = _pin(script_reference, small=True)
    _need(script == _pin(request["script_reference"], small=True) and job.get("Command") == script["path"] and
          job.get("WorkDir") == request["workdir"] == PROJECT, "ACTUAL_WORKDIR_OR_SCRIPT_BINDING_DIFFERS")
    if script_text is not None:
        _need(len(script_text.encode()) == script["bytes"] and hashlib.sha256(script_text.encode()).hexdigest() == script["sha256"],
              "ACTUAL_SCRIPT_TEXT_PIN_DIFFERS")
        _script_contract(request, script_text)
    return {"status": "ACTUAL_STARTUP_IDENTITY_VERIFIED", "job_id": expected_job_id, "uid": uid,
            "node": request["node"], "cpus": 16, "memory_gib": 64, "exclusive_user": True, "requeue": False}


def _timestamp(value):
    _need(isinstance(value, str), "TARGET_NODE_TIMESTAMP_REQUIRED")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ContractError("TARGET_NODE_TIMESTAMP_INVALID", value) from exc
    _need(parsed.tzinfo is not None, "TIMEZONE_AWARE_TARGET_NODE_TIMESTAMP_REQUIRED")
    return parsed.timestamp()


def validate_fresh_startup_proof(proof, request, *, now_unix, uid, boot_id, max_age_seconds=120):
    """Validate the actual allocated job and fresh Root node-clock proof, not hold time."""
    _need(_same(proof.get("request"), request), "STARTUP_PROOF_REQUEST_DIFFERS")
    _pin(proof.get("request_reference"), small=True)  # Physical ref is checked by Root's launcher/ready marker.
    _need(type(proof.get("uid")) is int and proof["uid"] == uid == 1278 and
          isinstance(boot_id, str) and boot_id and proof.get("boot_id") == boot_id, "STARTUP_UID_OR_BOOT_DIFFERS")
    _need(type(max_age_seconds) in (int, float) and 0 < max_age_seconds <= 120, "NO_STARTUP_FRESHNESS_EXTENSION")
    observed = _timestamp(proof.get("observed_at"))
    _finite(now_unix, "CURRENT_TARGET_TIME_INVALID")
    observation = proof.get("memory_observation", {})
    _need(observation.get("node") == request["node"] and observation.get("uid") == uid and
          observation.get("boot_id") == boot_id, "TARGET_NODE_MEMORY_OBSERVATION_IDENTITY_DIFFERS")
    observation_epoch = _finite(observation.get("observed_unix_seconds"), "TARGET_NODE_OBSERVATION_CLOCK_REQUIRED")
    _need(abs(observation_epoch - observed) <= 1 and abs(_timestamp(observation.get("observed_at")) - observed) <= 1,
          "OBSERVATION_NOT_SAME_FRESH_TARGET_CLOCK")
    # The existing probe captures time.time() immediately before ISO observed_at.
    # Use its numeric target-node sample clock, not a later formatting timestamp.
    age = now_unix - observation_epoch
    _need(0 <= age <= max_age_seconds, "STARTUP_PROOF_STALE_OR_FUTURE", age)
    total = _integer(observation.get("total_bytes"), "OBSERVED_MEMORY_TOTAL_INVALID", 1)
    available = _integer(observation.get("available_bytes"), "OBSERVED_MEMORY_AVAILABLE_INVALID")
    _need(available <= total and observation.get("used_bytes") == total - available, "OBSERVED_MEMORY_ARITHMETIC_INVALID")
    if "script_reference" in proof:
        _need(_same(proof["script_reference"], request["script_reference"]), "STARTUP_SCRIPT_REFERENCE_DIFFERS")
    if "source_references" in proof:
        _need(_same(proof["source_references"], request["source_references"]), "STARTUP_SOURCE_REFERENCES_DIFFER")
    if "queue_authority_reference" in proof:
        _need(_same(proof["queue_authority_reference"], request["queue_authority_reference"]), "STARTUP_AUTHORITY_REFERENCE_DIFFERS")
    _need(proof.get("memory_basis", MEMORY_BASIS) == MEMORY_BASIS and
          proof.get("memory_exemption", False) is False and proof.get("small_test_exception_not_formal", False) is False,
          "STARTUP_MEMORY_EXEMPTION_FORBIDDEN")
    _need(proof.get("live_envelope_admission_passed", True) is True and
          proof.get("execution_admission_granted", True) is True, "LIVE_OR_EXECUTION_ADMISSION_NOT_GRANTED")
    identity = validate_startup_job(request, proof.get("job_metadata"), expected_job_id=proof.get("job_id"),
                                    uid=uid, script_reference=request["script_reference"])
    others = proof.get("existing_jobs_all_users")
    _need(isinstance(others, list), "EXPLICIT_ALL_USER_OTHER_JOBS_REQUIRED")
    _need(all(_job(j).get("JobId") != proof["job_id"] for j in others), "OWN_JOB_REPEATED_IN_OTHER_JOBS")
    node = proof.get("node_metadata")
    budget = admit_memory(request, parse_scontrol_node(node) if isinstance(node, str) else node,
                          [*others, proof["job_metadata"]], own_job_id=proof["job_id"], uid=uid)
    _need(_finite(proof.get("committed_memory_mib"), "COMMITTED_MEMORY_VALUE_REQUIRED") == budget["committed_memory_mib"],
          "DECLARED_MEMORY_PROOF_NOT_RECOMPUTABLE")
    free = _integer(proof.get("account_free_bytes"), "ACTUAL_ACCOUNT_QUOTA_REQUIRED")
    _need(isinstance(proof.get("quota_raw"), str) and proof["quota_raw"].strip() and
          free - request["estimated_peak_output_bytes"] >= 200_000_000_000, "WHOLE_OUTPUT_PLUS_200GB_RESERVE_REQUIRED")
    return {"status": "FRESH_STRICT_STARTUP_PROOF_VERIFIED", "age_seconds": age,
            "job_identity": identity, "memory_admission": budget, "memory_exemption": False,
            "remaining_account_bytes_after_output": free - request["estimated_peak_output_bytes"]}
