"""Read-only A00 export/primary panel/terminal provenance chain; stdlib only."""
from __future__ import annotations

import importlib.util
import math
from pathlib import Path
import sys

EVALUATOR_CODE = "9638f7c461a6a88b6b2469f2c7e9ec8023d276e5"
EXPORT_CODE = "8ece64c685fe287d6863fbbe2f6f52006632a5cc"
EXPORT_JOB = "4520486"
RUN_NAME = "A00_short500_primary512_dev9_v1"
HELPER_PATH = Path("/share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/sa3_primary512_panel_launch_v2/export_admission.py")
MAX_CHECKPOINT_BYTES = 512 << 20


def require(condition, message):
    if not condition:
        raise ValueError(message)


def same_semantics(candidate, authority, *, state_key=None):
    """The raw byte authority is measured separately; request refs omit bytes."""
    require(candidate["path"] == authority["path"] and candidate["sha256"] == authority["sha256"],
        "Path/raw SHA differs from original READY source")
    if state_key is not None:
        require(candidate.get("state_key") == authority.get("state_key") == state_key, "Source state_key differs")
    if "bytes" in candidate:
        require(candidate["bytes"] == authority["bytes"], "Optional reference size differs")


def successful_supervisor(value, job_id):
    require(value["status"] == "COMPLETED" and value["exit_code"] == 0
        and str(value["job_id"]) == str(job_id) and value["first_failure"] is None,
        "Actual successful supervisor closure required")
    keys = {"remaining", "remaining_recorded_processes_before_retirement"} & set(value)
    require(keys and all(value[key] == [] for key in keys), "Supervisor still records live descendants")
    if "private_storage_cleanup_errors" in value:
        require(value["private_storage_cleanup_errors"] == [], "Private-storage cleanup failed")
    for key in ("private_storage", "private_storage_final"):
        if value.get(key) is not None:
            require(value[key]["first_sampling_failure"] is None, "Private storage observation failed")


def timing_observation(guard, admission):
    outer = admission['evaluation_job']['elapsed_seconds']
    inclusive = guard['inclusive_panel_wall_seconds']
    require(type(outer) is int and outer >= 0 and type(inclusive) in (int, float)
        and math.isfinite(inclusive) and inclusive >= 0, 'Actual allocation/guard wall observations required')
    return {'observed_outer_allocation_seconds': outer, 'observed_guard_inclusive_wall_seconds': inclusive,
        'inclusive_one_gpu_hour_observed': outer <= 3600 and inclusive <= 3600}


def validate_primary_scope(result, guard, request, spec, configuration, exported):
    require(request["run_id"] == RUN_NAME and result["reference_kind"] == request["reference_kind"] == spec["reference_kind"] == "primary",
        "Only the declared A00 primary diagnostic run is in scope")
    require(spec["schema"] == "model_v3_primary512_dev9_external_launch_v2"
        and result["code_sha"] == request["code_sha"] == guard["code_sha"] == spec["code_sha"] == EVALUATOR_CODE,
        "Actual frozen9638 evaluator/spec differs")
    require((configuration["backbone"]["dim"], configuration["backbone"]["layers"]) == (512, 6)
        and spec["H0_dimension"] == result["encoder_pair"]["H0_dimension"] == 512, "Actual full configuration must be512x6")
    require(spec["export_job_id"] == exported["export_job_id"] == EXPORT_JOB
        and spec["export_code_sha"] == exported["export_code_sha"] == EXPORT_CODE,
        "The successful A00 export486 is required; failed457 cannot substitute")
    require(spec["architecture_selection_claimed"] is False and spec["formal_pretraining_complete"] is False
        and exported["ready"]["optimizer_updates"] == 500, "This is short500 diagnostic tooling/timing only")
    require(exported["configuration"]["candidate"]["precision"] == "fp32"
        and exported["configuration"]["candidate"]["fused_adamw"] is False,
        "A00 control runtime options required; fused A06 cannot substitute")
    require(spec["fresh_cache_required"] is True and guard["cache_started_cold"] is True,
        "The measured run must begin with cold H0 cache")
    require(spec["native_fields_units_masks_atom_ids_changed"] is False, "Native data semantics changed")
    require(spec["counts"] == {"cyp_isoform": 1803, "expansionrx": 5326, "qm9": 10473}
        and spec["expected_tasks"] == 9 and spec["expected_comparison_cells"] == 18
        and spec["readouts"] == ["ridge", "linear64_relu"], "Original selectedTRAIN panel membership/readouts differ")
    pair = result["encoder_pair"]
    require(pair["checkpoint_schema"] == "source_training_checkpoint_v1" and pair["reference_kind"] == "primary"
        and pair["historical_reference"] is None and pair["historical_memory_implementation"] is None,
        "Actual standard primary512 loader proof required")
    for value in (request["checkpoint"], pair["checkpoint"], spec["source_checkpoint"]):
        same_semantics(value, exported["checkpoint"], state_key="model_state")
    for value in (request["model_configuration"], pair["original_configuration"], spec["original_configuration"]):
        same_semantics(value, exported["model_configuration"])
    require(pair["architecture_sha256"] == result["architecture_sha256"] == request["architecture_sha256"] == exported["architecture_sha256"]
        and pair["pretraining_seed"] == result["pretraining_seed"] == request["pretraining_seed"] == exported["pretraining_seed"],
        "Actual source architecture/pretraining seed differs")


def read_source_chain(result, guard, request, spec, admission, refs, *, binding, bound_json):
    """Rehash actual export bytes through the same bound stdlib admission helper."""
    def read(name, ref, limit=8 << 20):
        value, actual = bound_json(ref["path"], ref["sha256"], limit=limit)
        if "bytes" in ref:
            require(actual["bytes"] == ref["bytes"], "Bound metadata byte count differs: "+name)
        refs[name] = actual
        return value
    require(spec["request"]["path"] == refs["request"]["path"]
        and spec["request"]["sha256"] == refs["request"]["sha256"]
        and guard["spec_sha256"] == refs["launch_spec"]["sha256"], "Actual launched spec/request raw bytes differ")
    helper_ref = spec["export_admission_implementation"]
    require(Path(helper_ref["path"]) == HELPER_PATH and binding(HELPER_PATH) == helper_ref,
        "Use the exact frozen source-admission helper bound before evaluation")
    refs["export_admission_implementation"] = helper_ref
    name = "primary512_readonly_admission_"+helper_ref["sha256"]
    if name not in sys.modules:
        loader = importlib.util.spec_from_file_location(name, HELPER_PATH)
        module = importlib.util.module_from_spec(loader); sys.modules[name] = module; loader.loader.exec_module(module)
    module = sys.modules[name]
    # Fresh terminal admission was mandatory at launch. Immutable successful
    # export receipts are rechecked here without imposing a new one-hour age on
    # historical export metadata; the current evaluation/quota receipt is fresh.
    exported = module.read_validated_export(spec["export_ready"], spec["export_terminal_admission"], check_freshness=False)
    ready = read("export_ready", spec["export_ready"])
    export_admission = read("export_terminal_admission", spec["export_terminal_admission"])
    require(export_admission["export_job"]["job_id"] == EXPORT_JOB, "Wrong export terminal job")
    for key in ("supervisor", "run_status", "summary"):
        read("export_"+key, export_admission[key])
    for key in ("a_run_configuration", "provenance"):
        read("export_"+key, ready[key])
    configuration = read("export_model_configuration", ready["model_configuration"])
    checkpoint_ref = {key: ready["checkpoint"][key] for key in ("path", "bytes", "sha256")}
    require(binding(checkpoint_ref["path"], MAX_CHECKPOINT_BYTES) == checkpoint_ref, "Actual exported checkpoint raw bytes differ")
    refs["export_checkpoint"] = checkpoint_ref
    require(ready == exported["ready"], "Export metadata changed while verifying")
    validate_primary_scope(result, guard, request, spec, configuration, exported)
    supervisor = read("evaluation_supervisor", admission["evaluation_supervisor"])
    successful_supervisor(supervisor, result["job_id"])
    require(admission["launch_spec"] == refs["launch_spec"], "Root terminal admission must bind this launched spec")
    require(spec["external_guard"] == guard["guard_implementation"], "Guard implementation differs from frozen launch")
    return {"export_job_id": EXPORT_JOB, "export_code_sha": EXPORT_CODE, "optimizer_updates": 500,
        "consumed_base_records": ready["consumed_base_records"], "H0_dimension": 512, "layers": 6,
        "configuration": refs["export_model_configuration"], "checkpoint": checkpoint_ref,
        "source_kind": "short_A00_native20_500_diagnostic_only", "formal_pretraining_complete": False,
        "architecture_selection_claimed": False, "export_bytes_rehashed_without_deserialization": True}
