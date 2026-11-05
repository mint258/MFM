"""Pilot-only admission and an optimizer-update stop over the original controller.

No data schema, trainer algorithm, sample clock, resource guard or panel evaluator
is replaced.  The generic engineering limit exercises this same stop mechanism
without granting authoritative_pilot admission.
"""
from __future__ import annotations
from copy import deepcopy
import re

from .v3_sample_budget_events import binding, read_bound, require, write_once, verify_checkpoint_record

PILOT_MODE = "authoritative_pilot"
PILOT_SCOPE = "pilot_smoke"
PILOT_UPDATE_CAP = 2000
ROLES = ("VAL", "TRAIN_UNSEEN_CONFORMATION")
EVIDENCE_KEYS = frozenset(("D1", "D2", "D3", "D4", "Model_policy_config_ACK", "Data_release", "reader"))
ACK = {"path": "/share/home/zixiao/descriptor_analysis/runs/model_v3_20261026/Model_same_version_policy_config_ACK_20261029_FINAL_v1/MODEL_ACK.json",
       "bytes": 12572, "sha256": "db3d0dae792a3e6ef044ea32a498a72974a6ab2dd1987d43742971b97831a1f0"}


def _digest(value):
    require(type(value) is str and re.fullmatch("[0-9a-f]{64}", value) is not None,
            "Actual complete pilot population/source digest required")


def _ref(value):
    from .v3_data_adapter import rawref, bound_bytes
    reference = rawref(value)
    bound_bytes(reference)
    return reference


def _ack_document(value):
    require(value.get("schema") == "MODEL_SAME_VERSION_POLICY_CONFIG_ACK_V1"
            and value.get("status") == "FINAL_SIGNED_POLICY_CONFIG_ACK"
            and value.get("contract_version") == "v3.0"
            and value["decision"]["policy_config_accepted"] is True
            and value["decision"]["policy_config_acceptance_is_unconditional"] is True
            and value["decision"]["acceptance_scope"] ==
                "ONLY_THE_EXACT_POLICY_AND_CONFIGURATION_SEMANTICS_IN_THE_BOUND_DATA_INPUTS"
            and value["decision"]["signature_status"] == "ACTUALLY_ROOT_SIGNED"
            and value["decision"]["effective_as_signed_Data_joint_reference"] is True
            and type(value["signature"]["signer"]) is str and value["signature"]["signer"]
            and type(value["signature"]["signed_utc"]) is str and value["signature"]["signed_utc"],
            "Actual signed same-version policy/config ACK required; draft is not admission")
    return value


def verify_model_ACK(reference):
    require(reference == ACK, "Pilot must bind the exact actual signed Model policy/config ACK")
    _ref(reference)
    from .v3_data_adapter import bound_json
    return _ack_document(bound_json(reference))


def validate_pilot_configuration(request, configuration):
    """A Model request extension; it never mints Data release authority."""
    pilot = request.get("mode") == PILOT_MODE
    require((request.get("scope") == PILOT_SCOPE) is pilot, "Pilot and proxy/full/grid scopes cannot cross")
    if not pilot:
        require("pilot_smoke" not in configuration, "Pilot contract cannot appear in a nonpilot request")
        return None
    require(configuration["engineering_only"] is False
            and configuration["experiment_scope"] == "AUTHORITATIVE_PILOT_SMOKE"
            and "training_execution" not in configuration
            and "performance_execution_v1" not in configuration["model"]
            and request.get("training_execution_admission") is None
            and request.get("panel_binding") is None
            and "full_train_contract" not in configuration and "grid_train_contract" not in configuration,
            "Pilot is explicit plain FP32, never an optimized/final/full/grid fallback")
    require("engineering_update_cap" not in configuration, "UNIT update limit cannot grant pilot authority")
    value = configuration.get("pilot_smoke")
    require(type(value) is dict and set(value) == {"schema", "optimizer_update_cap",
            "role_index_sha256", "validation_population_bindings", "evidence"} and value["schema"] == "model_v3_pilot_smoke_contract_v1"
            and type(value["optimizer_update_cap"]) is int and value["optimizer_update_cap"] == PILOT_UPDATE_CAP,
            "Exactly 2000 effective optimizer updates must be preregistered")
    require(type(value["role_index_sha256"]) is dict
            and set(value["role_index_sha256"]) == {"TRAIN", *ROLES},
            "Pilot TRAIN and both validation population identities required")
    for digest in value["role_index_sha256"].values(): _digest(digest)
    require(type(value["validation_population_bindings"]) is dict
            and set(value["validation_population_bindings"]) == set(ROLES)
            and value["validation_population_bindings"] ==
                configuration["proxy_contract"]["validation"]["population_bindings"],
            "Both validation population bindings must match the sealed training contract")
    for digest in value["validation_population_bindings"].values(): _digest(digest)
    require(type(value["evidence"]) is dict and set(value["evidence"]) == EVIDENCE_KEYS,
            "Pilot needs real D1/D2/D3/D4/scoped population/ACK/release/reader evidence, not D5 or future smoke")
    for reference in value["evidence"].values(): _ref(reference)
    verify_model_ACK(value["evidence"]["Model_policy_config_ACK"])
    require(configuration["proxy_contract"]["precision"] == {
        "mode": "fp32", "matmul_tf32": False, "cudnn_tf32": False, "matmul_precision": "highest"},
        "Pilot only supports the original plain FP32 path")
    return deepcopy(value)



def verify_pilot_evidence_aliases(declared, release_evidence, release_projection):
    """Exact metadata aliases only; this function grants NO release authority.

    The production caller first reverifies the original actual Data release.
    Population identity is separately canonical, never a metadata-file raw SHA.
    """
    from .v3_data_adapter import bound_json
    joint = bound_json(release_evidence["joint_contract"])
    expected = {"D1": joint["contract_reference"], "D2": release_evidence["registry"],
        "D3": release_evidence["release"], "D4": release_evidence["d4_statistics"],
        "Model_policy_config_ACK": joint["model_ack_reference"],
        "Data_release": release_evidence["release"], "reader": release_projection["reader_source"]}
    expected = {key: _ref(reference) for key, reference in expected.items()}
    require(declared == expected,
            "Pilot evidence aliases do not join the same actual joint/registry/release/D4/ACK/reader")


def verify_pilot_inputs(inputs, request, configuration):
    """Reverify the original actual bounded release/interpreter, never a header."""
    from .v3_data_adapter import VerifiedDataRelease
    from .v3_contract import canonical_hash
    value = validate_pilot_configuration(request, configuration)
    release = getattr(inputs.provider, "release", None)
    require(isinstance(release, VerifiedDataRelease), "Pilot provider must retain its actual verified Data release")
    release.reverify()
    require(release.is_actual_data_release is True and release.is_final is False
            and release.projection["scope"] == PILOT_MODE
            and release.request_sha256 == canonical_hash(request)
            and release.request == request,
            "Pilot requires the exact actual bounded release, not UNIT/source FULL/final-D authority")
    require(inputs.authority_kind == "data_line_pilot" and inputs.release_accepted is True
            and inputs.verified_request_sha256 == canonical_hash(request)
            and inputs.authority_receipt["model_consumption_projection_sha256"] == release.sha256
            and inputs.authority_receipt["evidence"] == release.evidence
            and inputs.authority_receipt["verifier"] == release.verifier,
            "Pilot hook must bind the same actual release/interpreter to this exact request")
    require(inputs.index.role == "TRAIN"
            and value["role_index_sha256"] == release.projection["role_index_sha256"]
            and inputs.index.content_sha256 == value["role_index_sha256"]["TRAIN"]
            and value["validation_population_bindings"] == inputs.validation_population_bindings
            == release.projection["validation_population_bindings"],
            "Pilot TRAIN/VAL/unseen populations differ from the actual scoped release")
    verify_pilot_evidence_aliases(value["evidence"], release.evidence, release.projection)
    return inputs


def update_limit(request, configuration):
    """Return a stop count, not a source/data/scientific acceptance certificate."""
    if request["mode"] == PILOT_MODE:
        return validate_pilot_configuration(request, configuration)["optimizer_update_cap"]
    value = configuration.get("engineering_update_cap")
    if value is None: return None
    require(request["mode"] == "synthetic_engineering" and configuration["engineering_only"] is True
            and type(value) is int and 1 <= value <= PILOT_UPDATE_CAP,
            "A small engineering update limit is synthetic-only, never pilot/final authority")
    return value


def check_update_limit(action, context, limit):
    from .v3_sample_budget_experiment import SegmentPause
    updates = context["optimizer_updates"]
    require(type(limit) is int and limit > 0 and type(updates) is int and 0 <= updates <= limit,
            "Committed optimizer cursor exceeded the registered update cap")
    if action == "STEP" and updates == limit:
        raise SegmentPause("registered optimizer-update cap reached")


def validate_update_limit_checkpoint(experiment, *, limit):
    """Before the ORIGINAL save: bind both actual populations to the cap.

    This runs within the original training lease and CHECKPOINT preflight.
    It avoids publishing two different checkpoints at the same sample cursor.
    A pending-log failure follows its unchanged original recovery path instead.
    """
    clock = experiment.trainer.clock
    require(clock.optimizer_updates == limit and experiment.trainer.pending_log is None,
            "Final pilot validation needs a complete effective update and committed log")
    key = str(clock.samples_consumed)
    validation = experiment.points.get(key)
    if validation is None:
        validation = []
        for role in ROLES:
            experiment._preflight("VALIDATION", allow_pause=False)
            result = experiment.trainer.validate(role)
            validation.append(write_once(experiment.segment / ("pilot_validation_" + key + "_" + role + ".json"),
                {"schema": "model_v3_sample_validation_point_v1", "samples_consumed": clock.samples_consumed,
                 "optimizer_updates": clock.optimizer_updates, "role": role, "result": result}))
        experiment.points[key] = validation
    rows = [read_bound(reference) for reference in validation]
    require(len(rows) == 2 and {row["role"] for row in rows} == set(ROLES)
            and all(row["samples_consumed"] == clock.samples_consumed
                and row["optimizer_updates"] == limit for row in rows),
            "Both complete actual validation populations must bind the final optimizer cursor")


def finish_update_limited_segment(experiment, outcome, *, limit, production):
    """Verify the original safe CP; early exhausted sample budget is HOLD."""
    clock = experiment.trainer.clock
    require(type(clock.optimizer_updates) is int and 0 <= clock.optimizer_updates <= limit,
            "Actual committed optimizer updates exceed cap")
    if clock.optimizer_updates != limit:
        require(clock.samples_consumed < experiment.plan.sample_budget,
                "HOLD: sample budget exhausted before the required effective optimizer updates")
        return dict(status="UPDATE_LIMIT_SEGMENT_PAUSED_NOT_COMPLETE",
                    optimizer_update_cap=limit, actual_optimizer_updates=clock.optimizer_updates,
                    last_checkpoint=experiment.last_checkpoint, scientific_acceptance=False,
                    actual_Data_acceptance=False)
    validation = experiment.points.get(str(clock.samples_consumed))
    require(validation is not None, "Final checkpoint did not validate both populations at the update cap")
    completion = outcome["last_checkpoint"]
    _, state = verify_checkpoint_record(completion)
    require(state["optimizer_updates"] == limit == clock.optimizer_updates
            and state["samples_consumed"] == clock.samples_consumed
            and state["log_cursor"] == experiment.trainer.log_cursor
            and state["pending_log"] is False and state["validation"] == validation,
            "Final original safe checkpoint/cursors/validations do not close at the exact update cap")
    return dict(status=("PILOT_2000_UPDATES_COMPLETE_PENDING_ROOT_CLOSURE" if production else
                        "ENGINEERING_UPDATE_LIMIT_COMPLETE_NOT_DATA_AUTHORITY"),
                optimizer_update_cap=limit, actual_optimizer_updates=clock.optimizer_updates,
                samples_consumed=clock.samples_consumed, log_cursor=experiment.trainer.log_cursor,
                final_checkpoint=completion, validation=validation,
                validation_population_bindings=deepcopy(experiment.trainer.validation_policy["population_bindings"]),
                original_segment_outcome=deepcopy(outcome), scientific_acceptance=False,
                actual_Data_acceptance=False, outer_C0_SDK_and_Root_review_required=True)
