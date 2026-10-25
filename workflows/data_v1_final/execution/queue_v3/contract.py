"""Pure v3 scope, registry and held-job contracts; strict v1 resource math stays."""
from __future__ import annotations
import hashlib
import json
from pathlib import PurePosixPath
import re
from ..queue_v1 import queue_contract as old

MODES = {"FIXTURE_ONLY", "BOUNDED_METADATA_PREPARATION", "BOUNDED_PERFORMANCE_BATCH",
         "FULL_SOURCE_INVENTORY_PRIOR_CRC", "FULL_SOURCE_AFTER_PROFILE"}
RUN = old.RUN
REGISTRY_DIR = RUN + "/control/queue_v3_registries"


def need(ok, code):
    if not ok:
        raise ValueError(code)


def _pin_bytes(ref, read_small):
    ref = old._pin(ref, small=True)
    raw = read_small(ref["path"])
    need(type(raw) is bytes and len(raw) == ref["bytes"]
         and hashlib.sha256(raw).hexdigest() == ref["sha256"], "SCOPE_REVIEW_PIN_CHANGED")
    return raw


def validate_scope_spec(spec, *, read_small):
    need(spec.get("schema") in {"ROOT_REVIEWED_QUEUED_STAGE_SPEC_V1",
         "ROOT_REVIEWED_QUEUED_STAGE_SPEC_V3"}, "EXACT_REVIEWED_STAGE_SPEC_REQUIRED")
    need(spec.get("kind") == "analysis", "QUEUE_V3_ANALYSIS_ONLY_NO_NEW_QM_OR_UFF")
    need(type(spec.get("pilot")) is bool, "HONEST_PILOT_BOOLEAN_REQUIRED")
    need(type(spec.get("scope_key")) is str and
         re.fullmatch(r"[a-z][a-z0-9_]{0,127}", spec["scope_key"]), "EXPLICIT_SCOPE_KEY_REQUIRED")
    need(type(spec.get("scope_parameters")) is dict, "EXPLICIT_SCOPE_PARAMETERS_REQUIRED")
    old._same(spec["scope_parameters"], spec["scope_parameters"])
    need(type(spec.get("wall_seconds")) is int and 0 < spec["wall_seconds"] <= 14400,
         "FINITE_FOUR_HOUR_WALL_REQUIRED")
    need(type(spec.get("estimated_peak_output_bytes")) is int
         and spec["estimated_peak_output_bytes"] > 0, "WHOLE_PHASE_OUTPUT_BUDGET_REQUIRED")
    for key, value in (("cpus", 16), ("memory_gib", 64)):
        need(key not in spec or type(spec[key]) is int and spec[key] == value,
             "EXACT_16CPU64G_STAGE_SPEC_REQUIRED")
    scope = spec.get("scope")
    need(type(scope) is dict and scope.get("mode") in MODES
         and "parent_profile" in scope, "EXPLICIT_SCOPE_MODE_REVIEW_AND_PARENT_REQUIRED")
    mode = scope["mode"]
    if mode == "FIXTURE_ONLY":
        need(spec["pilot"] is True, "FIXTURE_ONLY_REQUIRES_TRUE_PILOT")
    elif mode != "BOUNDED_PERFORMANCE_BATCH":
        need(spec["pilot"] is False, "FULL_OR_PREPARATION_REQUIRES_FALSE_PILOT")
    review = json.loads(_pin_bytes(scope.get("review"), read_small))
    need(review.get("schema") == "EXACT_ANALYSIS_QUEUE_SCOPE_ROOT_REVIEW_V3"
         and review.get("status") == "APPROVED_FOR_EXACT_STAGE"
         and review.get("reviewer") == "root", "EXACT_ROOT_STAGE_REVIEW_REQUIRED")
    for key in ("scope_key", "scope_parameters", "pilot", "wall_seconds",
                "estimated_peak_output_bytes", "execution_argv", "source_status_stage"):
        need(old._same(review.get(key), spec.get(key)), "ROOT_REVIEW_STAGE_FIELD_DIFFERS:" + key)
    need(review.get("scope_mode") == mode, "ROOT_REVIEW_MODE_DIFFERS")
    cap = spec.get("stage_output_cap_bytes", spec["estimated_peak_output_bytes"])
    need(type(cap) is int and 0 < cap <= spec["estimated_peak_output_bytes"]
         and review.get("stage_output_cap_bytes") == cap, "STAGE_CAP_WITHIN_WHOLE_PHASE_BUDGET_REQUIRED")
    parents = review.get("parent_evidence_references")
    need(type(parents) is list and (parents or mode == "FIXTURE_ONLY"),
         "ACTUAL_PINNED_PARENT_EVIDENCE_REQUIRED")
    normalized = [old._pin(p, small=True) for p in parents]
    need(len({p["path"] for p in normalized}) == len(parents), "UNIQUE_PARENT_EVIDENCE_REQUIRED")
    for ref in normalized:
        _pin_bytes(ref, read_small)
    profile = scope["parent_profile"]
    if profile is not None:
        need(old._pin(profile, small=True) in normalized, "PARENT_PROFILE_NOT_IN_EXACT_REVIEW")
    if mode == "BOUNDED_PERFORMANCE_BATCH":
        need(review.get("bounded_batch_limits_reviewed") is True, "BOUNDED_PROFILE_LIMITS_REQUIRED")
    if mode == "FULL_SOURCE_AFTER_PROFILE":
        need(profile is not None and review.get("profile_reviewed") is True
             and review.get("approved_profile_reference") == profile,
             "FULL_STAGE_REQUIRES_ACTUAL_REVIEWED_PROFILE")
    if mode == "FULL_SOURCE_INVENTORY_PRIOR_CRC":
        need(cap <= 10 * old.GIB and review.get("inventory_only") is True
             and review.get("candidate_release_authorized") is False
             and review.get("crc_full_eof_actual_passed") is True
             and review.get("crc_receipt_reference") in normalized,
             "EXACT_PRIOR_CRC_INVENTORY_ONLY_10GIB_CAP_REQUIRED")
    return {"mode": mode, "review": review, "parent_evidence_references": normalized,
            "stage_output_cap_bytes": cap, "full_population_acceptance_granted": False}


def registry_path(path):
    value = old._literal_path(str(path))
    p = PurePosixPath(value)
    need(str(p.parent) == REGISTRY_DIR and re.fullmatch(r"[a-z0-9_]+\.json", p.name),
         "NEW_CANONICAL_V3_REGISTRY_PATH_REQUIRED")
    return value


def row_keys(row, request):
    jid = row.get("job_id")
    need(type(jid) is str and jid.isdecimal(), "REGISTERED_DECIMAL_JOB_ID_REQUIRED")
    ref = old._pin(row.get("request_reference"), small=True)
    proof = old._literal_path(request.get("startup_proof_path"))
    name = request.get("job_name")
    need(type(name) is str and re.fullmatch(r"dv1_q_[A-Za-z0-9_]+", name), "REGISTERED_JOB_NAME_REQUIRED")
    need(ref["path"] == RUN + "/control/requests/" + name + ".json"
         and proof == RUN + "/control/queue_startup/" + name + ".json",
         "REGISTERED_REQUEST_OR_PROOF_NAMESPACE_DIFFERS")
    return {"job_id": jid, "request_path": ref["path"], "proof_path": proof, "job_name": name}


def validate_disjoint(registries, *, load_request):
    """registries is [(literal registry path, object)]; old V1 rows are included."""
    seen = {key: {} for key in ("job_id", "request_path", "proof_path", "job_name")}
    paths = set()
    for path, registry in registries:
        path = old._literal_path(str(path))
        need(path not in paths, "DUPLICATE_REGISTRY_PATH"); paths.add(path)
        need(registry.get("schema") in {"REGISTERED_QUEUED_CPU_JOBS_V1",
             "REGISTERED_QUEUED_CPU_JOBS_V2", "REGISTERED_QUEUED_CPU_JOBS_V3"} and type(registry.get("jobs")) is list
             and bool(registry["jobs"]), "EXACT_NONEMPTY_REGISTERED_JOB_SET")
        for row in registry["jobs"]:
            request = load_request(row["request_reference"])
            for key, value in row_keys(row, request).items():
                need(value not in seen[key], "REGISTRY_OVERLAP:" + key)
                seen[key][value] = path
    return seen


def validate_held_job(request, job, *, expected_job_id):
    need(job.get("JobId") == expected_job_id and old._uid(job) == 1278,
         "EXACT_OWN_HELD_JOB_ID_REQUIRED")
    need(job.get("JobState") == "PENDING" and job.get("Reason") == "JobHeldUser"
         and job.get("Priority") == "0", "ACTUAL_USER_HELD_JOB_REQUIRED")
    need(job.get("JobName") == request["job_name"] and job.get("Partition") == "cpu"
         and job.get("ReqNodeList") == request["node"] and job.get("NumNodes") in {"1", "1-1"},
         "HELD_NAME_PARTITION_OR_NODE_DIFFERS")
    raw_tres = job.get("TRES", "")
    parts = [value.split("=") for value in raw_tres.split(",")]
    need(parts and all(len(pair) == 2 and pair[0] and pair[1] for pair in parts)
         and len({pair[0] for pair in parts}) == len(parts), "EXACT_HELD_TRES_REQUIRED")
    tres = dict(parts)
    need(tres.get("node") == "1" and tres.get("cpu") == "16"
         and old._memory_bytes(tres.get("mem")) == 64 * old.GIB
         and not any("gpu" in key.lower() for key in tres), "HELD_TRES_SINGLE_CPU_NODE64G_REQUIRED")
    need(job.get("NumCPUs") == "16" and old._job_memory(job) == 64 * old.GIB
         and job.get("OverSubscribe") == "USER" and job.get("Requeue") == "0",
         "HELD_EXACT_CPU_MEMORY_USER_NO_REQUEUE_REQUIRED")
    need(job.get("NumTasks", "1") == "1" and job.get("Command") == request["script_reference"]["path"]
         and job.get("WorkDir") == request["workdir"] == old.PROJECT
         and old._wall(job.get("TimeLimit", "")) == request["wall_seconds"],
         "HELD_SCRIPT_WORKDIR_TASK_OR_WALL_DIFFERS")
    return True


def validate_bound_request(request, *, read_small):
    """Bind preserved producer fields and substituted argv to the original spec."""
    ref = request.get("root_review", {}).get("stage_spec_reference")
    spec = json.loads(_pin_bytes(ref, read_small))
    result = validate_scope_spec(spec, read_small=read_small)
    controls = {"schema", "kind", "pilot", "cpus", "memory_gib", "wall_seconds",
                "estimated_peak_output_bytes", "execution_argv", "source_references",
                "data_references", "deferred_authority_references"}
    for key, value in spec.items():
        if key not in controls:
            need(old._same(request.get(key), value), "PRODUCER_DOMAIN_FIELD_NOT_PRESERVED:" + key)
    for key in ("kind", "pilot", "wall_seconds", "estimated_peak_output_bytes"):
        need(old._same(request.get(key), spec[key]), "BOUND_STAGE_CONTROL_DIFFERS:" + key)
    for key in ("data_references", "deferred_authority_references"):
        need(old._same(request.get(key, []), spec.get(key, [])), "BOUND_STAGE_LOCATORS_DIFFERS:" + key)
    expected = [v.replace("__ROOT_STARTUP_PROOF__", request["startup_proof_path"])
                for v in spec["execution_argv"]]
    need(request.get("execution_argv") == expected, "BOUND_STAGE_EXECUTION_ARGV_DIFFERS")
    sources = request["source_references"]
    required = [ref, spec["scope"]["review"], *spec["source_references"],
                *result["parent_evidence_references"]]
    need(all(r in sources for r in required), "EXACT_STAGE_REVIEW_SOURCE_PINS_REQUIRED")
    return result


def validate_observer_identity(saved, current, *, expected_argv, registry_reference, source_reference):
    for key in ("pid", "uid", "boot_id", "start_ticks", "pgid", "sid", "argv_sha256", "argv",
                "cgroup_sha256", "cgroup"):
        need(saved.get(key) == current.get(key), "LIVE_OBSERVER_IDENTITY_CHANGED:" + key)
    need(saved.get("uid") == 1278 and saved.get("argv") == expected_argv
         and saved.get("pgid") == saved.get("pid") == saved.get("sid"),
         "EXACT_OWN_OBSERVER_ARGV_REQUIRED")
    need(saved.get("registry_reference") == registry_reference
         and saved.get("source_reference") == source_reference,
         "OBSERVER_SOURCE_OR_REGISTRY_BINDING_CHANGED")
    return True
