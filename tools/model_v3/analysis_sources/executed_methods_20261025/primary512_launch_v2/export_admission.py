"""Read-only admission of an actual standard primary512 H0 export bundle.

READY alone is explicitly insufficient: Root must byte-bind fresh successful
Slurm and outer-supervisor/run-cleanup receipts. No model or target is loaded.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat

EXPORT_CODE_SHA = "8ece64c685fe287d6863fbbe2f6f52006632a5cc"
EVALUATION_CODE_SHA = "9638f7c461a6a88b6b2469f2c7e9ec8023d276e5"
MAX_CHECKPOINT_BYTES = 512 << 20


def require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def binding(path, limit=MAX_CHECKPOINT_BYTES):
    path = Path(path).absolute()
    require(".." not in path.parts, "Parent traversal is not allowed")
    for ancestor in (path, *path.parents):
        require(not ancestor.is_symlink(), "Physical source path required")
    before = path.lstat()
    require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_uid == os.getuid()
        and before.st_size <= limit, "Owned ordinary bounded single-link source required")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    after = path.stat()
    require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) ==
        (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns), "Source changed during hashing")
    return {"path": str(path), "bytes": before.st_size, "sha256": digest.hexdigest()}


def read_ref(ref, *, limit=8 << 20):
    actual = binding(ref["path"], limit)
    require(actual == {key: ref[key] for key in ("path", "bytes", "sha256")}, "Export/admission source bytes differ")
    raw = Path(actual["path"]).read_bytes()
    require(hashlib.sha256(raw).hexdigest() == actual["sha256"], "JSON changed before decode")
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "Duplicate metadata JSON key")
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs)


def require_same_reference(candidate, authority, *, state_key=None):
    """Compare frozen request/result refs to a fully measured READY authority.

    The original make_request.binding omits bytes. Do not compare dictionary
    shapes or discard the authoritative size: hash/stat the physical file here.
    """
    require(state_key in (None, "model_state"), "Declared primary state key required")
    allowed = {"path", "sha256", "bytes"} | ({"state_key"} if state_key is not None else set())
    for ref in (candidate, authority):
        require(type(ref) is dict and {"path", "sha256"} <= set(ref) <= allowed,
            "Recognized reference fields required")
        require(type(ref["path"]) is str and Path(ref["path"]).is_absolute()
            and ".." not in Path(ref["path"]).parts
            and re.fullmatch(r"[0-9a-f]{64}", ref["sha256"] or ""), "Absolute path/raw SHA reference required")
        if "bytes" in ref:
            require(type(ref["bytes"]) is int and ref["bytes"] >= 0, "Reference byte count must be an integer")
        if state_key is not None:
            require(ref.get("state_key") == state_key, "Checkpoint state_key differs")
    require(type(authority.get("bytes")) is int, "READY authority must retain measured bytes")
    require(candidate["path"] == authority["path"] and candidate["sha256"] == authority["sha256"],
        "Reference path/raw SHA differs from READY")
    actual = binding(authority["path"])
    require(actual == {key: authority[key] for key in ("path", "bytes", "sha256")}, "Measured READY bytes/SHA differ")
    if "bytes" in candidate:
        require(candidate["bytes"] == actual["bytes"], "Candidate byte count differs from physical READY source")
    return True


def validate_receipts(ready, ready_ref, admission, supervisor, run_status, summary, *, check_freshness=True):
    require(ready.get("schema") == "model_v3_A_H0_export_ready_v1"
        and ready.get("status") == "H0_BYTES_VERIFIED_PENDING_OUTER_JOB_TERMINAL",
        "Actual H0 READY schema is required; it does not claim outer-job completion")
    require(admission.get("schema") == "model_v3_primary512_export_admission_v1"
        and admission["ready"] == ready_ref, "Root's exact READY-byte admission is required")
    job = admission["export_job"]
    require(str(job["job_id"]) == str(run_status["job_id"]) == str(supervisor["job_id"])
        and job["state"] == "COMPLETED" and job["exit_code"] == "0:0", "Actual successful terminal Slurm export required")
    if check_freshness:
        observed = datetime.fromisoformat(admission["checked_at_utc"].replace("Z", "+00:00"))
        require(observed.utcoffset() is not None, "Root admission timestamp needs a UTC offset")
        require(-60 <= (datetime.now(timezone.utc)-observed).total_seconds() <= 3600,
            "Use fresh Root terminal admission within one hour of preparation/launch")
    require(supervisor["status"] == "COMPLETED" and supervisor["exit_code"] == 0
        and supervisor["first_failure"] is None and supervisor["remaining_recorded_processes_before_retirement"] == []
        and supervisor["private_storage_cleanup_errors"] == [], "Export outer supervisor is not successfully closed")
    require(run_status["status"] == "PAIRED_GATES_PASS" and run_status["failure"] is None
        and run_status["cleanup_errors"] == [] and run_status["checkpoint_export"]["ready"] == ready_ref,
        "Native input/SDK/export cleanup and ready publication must be closed")
    require(summary["status"] == "PAIRED_GATES_PASS" and summary["full_A_numeric_acceptance"] is True
        and summary["fixed_batch_pass"] is True and summary["trajectory_pass"] is True
        and summary["input"] == "native_s" and summary["smoke"] is False,
        "Original complete native20/500 numeric gates required")
    require(ready["code_sha"] == summary["code_sha"] == admission["expected_export_code_sha"] == EXPORT_CODE_SHA,
        "The tested actual exporter source commit differs")
    require(ready["optimizer_updates"] == 500 and ready["resume_supported"] is False
        and ready["generic_checkpoint_schema"] == "source_training_checkpoint_v1"
        and ready["training_rng_unchanged"] is True and ready["training_rng_before"] == ready["training_rng_after"],
        "Bound H0 export scope/schema/RNG proof differs")
    provenance = ready["H0_loader_provenance"]
    require(provenance["H0_dimension"] == 512 and provenance["reference_kind"] == "primary"
        and provenance["checkpoint_schema"] == "source_training_checkpoint_v1"
        and provenance["architecture_sha256"] == ready["architecture_sha256"], "Safe primary512 load proof differs")
    require(provenance["checkpoint"] == ready["checkpoint"]
        and provenance["original_configuration"] == ready["model_configuration"]
        and provenance["pretraining_seed"] == ready["pretraining_seed"], "READY loader source/configuration/seed differs")


def read_validated_export(ready_ref, admission_ref, *, check_freshness=True):
    ready, admission = read_ref(ready_ref), read_ref(admission_ref)
    supervisor = read_ref(admission["supervisor"])
    run_status = read_ref(admission["run_status"])
    summary = read_ref(admission["summary"])
    validate_receipts(ready, ready_ref, admission, supervisor, run_status, summary, check_freshness=check_freshness)
    directory = Path(ready_ref["path"]).parent
    require(directory.name == "candidate_h0", "Original candidate_h0 export destination required")
    for name, filename in (("checkpoint", "candidate.pt"), ("model_configuration", "model_configuration.json"),
                           ("a_run_configuration", "a_run_configuration.json"), ("provenance", "provenance.json")):
        ref = ready[name]
        require(Path(ref["path"]).absolute() == directory / filename, "Bundle must use its original sealed files")
        require(binding(ref["path"]) == {key: ref[key] for key in ("path", "bytes", "sha256")}, "Actual exported bundle SHA differs")
    require(ready["checkpoint"]["state_key"] == "model_state", "Use the declared standard state key")
    recipe = read_ref(ready["model_configuration"])
    configuration = read_ref(ready["a_run_configuration"])
    provenance = read_ref(ready["provenance"])
    require((recipe["backbone"]["dim"], recipe["backbone"]["layers"]) == (512, 6), "Full original configuration is not512x6")
    require(ready["pretraining_seed"] == configuration["seed"] == provenance["seed"] == recipe["training"]["seed"],
        "Original checkpoint seed differs")
    require(configuration["code_sha"] == provenance["code_sha"] == ready["code_sha"]
        and canonical(configuration["source_sha256"]) == ready["source_inventory_sha256"] == provenance["source_inventory_sha256"],
        "Original source inventory/code provenance differs")
    require(configuration["configuration_sha256"] == canonical({key: value for key, value in configuration.items()
        if key != "configuration_sha256"}), "Original A run configuration seal differs")
    require(configuration["input"] == "native_s" and configuration["smoke"] is False
        and configuration["fixed_batches"] == 20 and configuration["trajectory_updates"] == 500
        and configuration["candidate"]["precision"] == "fp32"
        and provenance["full_native_A_numeric_gates_passed"] is True
        and provenance["optimizer_updates"] == 500 and provenance["formal_pretraining_complete"] is False
        and provenance["A_resume_supported"] is False, "Original native diagnostic scope differs")
    require(provenance["consumed_base_records"] == ready["consumed_base_records"] == summary["consumed_trajectory_base_records"]
        and ready["consumed_base_records"] > 0, "Committed native record clock differs")
    require(recipe["phase1"]["performance_options"] == provenance["performance_options"] == configuration["candidate"],
        "Original runtime options differ; do not reconstruct a training recipe")
    for name, ref in (("ready", ready_ref), ("admission", admission_ref),
        *((key, admission[key]) for key in ("supervisor", "run_status", "summary"))):
        require(binding(ref["path"]) == {key: ref[key] for key in ("path", "bytes", "sha256")},
            "Export metadata changed during admission: "+name)
    return {"ready": ready, "admission": admission, "ready_ref": ready_ref, "admission_ref": admission_ref,
        "checkpoint": ready["checkpoint"], "model_configuration": ready["model_configuration"],
        "pretraining_seed": ready["pretraining_seed"], "architecture_sha256": ready["architecture_sha256"],
        "export_job_id": str(admission["export_job"]["job_id"]), "export_code_sha": ready["code_sha"],
        "consumed_base_records": ready["consumed_base_records"], "configuration": configuration}
