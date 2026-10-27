"""Strict consumer of the one training-execution contract and FP32 H0 map.

No policy is selected here. The canonical training adapter authenticates its
saved resolved policy and constructs both candidate and matched-random exports.
The original checkpoint envelope and downstream ACK schemas remain unchanged.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json


def _canonical(value):
    # Exact v3_contract canonical JSON bytes, without importing its Torch types.
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"),
                     ensure_ascii=False, allow_nan=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


class ExecutionCheckpointError(ValueError):
    pass


def _need(value, message):
    if not value:
        raise ExecutionCheckpointError(message)


def _bridge_source():
    from .v3_h0_runtime import physical_source_binding
    return physical_source_binding(__file__)


def _adapter():
    # Lazy: unchanged legacy/Native loaders do not depend on this new adapter.
    try:
        from .v3_training_execution import (
            validate_training_execution_contract,
            validate_training_execution_state,
            validate_h0_export_contract,
            build_h0_export_encoder,
        )
    except ImportError as exc:
        raise ExecutionCheckpointError(
            "The canonical training-execution adapter must be installed") from exc
    return (validate_training_execution_contract,
            validate_training_execution_state, build_h0_export_encoder, validate_h0_export_contract)


def validate_h0_export_capability(model_configuration, training_execution_contract):
    """Metadata capability only; no model, tensor, profile or device selection.

    The primary panel separately retains its exact six-layer, 512-wide gate.
    This helper also supports genuine tiny engineering checkpoints; capability
    is never data authority, a completed panel or a scientific acceptance.
    """
    _need(type(model_configuration) is dict
          and type(training_execution_contract) is dict,
          "Explicit model and training-execution contract required")
    _, _, _, validate = _adapter()
    try:
        contract = validate(training_execution_contract)
        _need(_canonical(contract) == _canonical(training_execution_contract),
              "The saved execution contract is not canonical")
        _need(contract["model_configuration"] == model_configuration,
              "Execution and source model configurations differ")
        mapping = contract["h0_export"]
        _need(type(mapping) is dict
              and mapping.get("schema") == "model_v3_training_h0_export_v1"
              and mapping.get("precision") == "fp32",
              "An explicit supported FP32 H0 export map is required")
        width = model_configuration["backbone"]["dim"]
        _need(type(width) is int and width > 0,
              "An explicit positive H0 dimension is required")
        result = {
            "supported": True,
            "training_execution_contract_sha256": _canonical(contract),
            "H0_export": deepcopy(mapping),
            "H0_export_sha256": _canonical(mapping),
            "H0_dimension": width,
            "downstream_capacity_authority": False,
            "scientific_acceptance": False,
        }
        _canonical(result)
        return result
    except (KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, ExecutionCheckpointError):
            raise
        raise ExecutionCheckpointError(
            "Unsupported or source-drifted training/H0 execution contract") from exc


def training_execution_cache_projection(provenance):
    """Check complete provenance identity before a small, fixed cache projection.

    This function is stdlib-only: it checks the complete contract/map/state hash
    closure and registered provenance fields, not policy capability. The loader
    and evaluator call the canonical adapter capability first; ACK additionally
    binds these full canonical hashes to the previously admitted event. A compact
    projection alone can never replace the original contract/admission proof.
    """
    keys = {
        "training_contract", "bridge_implementation",
        "training_execution_contract_sha256", "H0_export", "H0_export_sha256",
        "H0_export_precision", "BF16_training_forward_bitwise_replay_claimed",
        "training_capacity_reused_for_downstream_H0", "saved_runtime_execution_sha256",
        "committed_samples_consumed", "committed_optimizer_updates",
        "committed_log_cursor", "scientific_acceptance",
    }
    try:
        _need(type(provenance) is dict and set(provenance) == keys,
              "Complete registered execution provenance is required")
        contract, mapping = provenance["training_contract"], provenance["H0_export"]
        _need(type(contract) is dict
              and contract.get("schema") == "model_v3_training_execution_contract_v1"
              and type(mapping) is dict
              and mapping.get("schema") == "model_v3_training_h0_export_v1"
              and mapping.get("precision") == "fp32"
              and contract["h0_export"] == mapping,
              "The complete original execution contract and FP32 H0 map must agree")
        _need(_canonical(contract) == provenance["training_execution_contract_sha256"]
              and _canonical(mapping) == provenance["H0_export_sha256"],
              "Original contract/map hashes differ before cache projection")
        state = contract["execution_state"]
        _need(type(state) is dict and "training_execution" not in state,
              "Non-recursive original runtime execution state required")
        actual_state = {**state, "training_execution": contract}
        _need(_canonical(actual_state) == provenance["saved_runtime_execution_sha256"],
              "The original saved runtime execution hash differs")
        bridge = provenance["bridge_implementation"]
        _need(type(bridge) is dict and set(bridge) == {"path", "sha256"}
              and type(bridge["path"]) is str and bool(bridge["path"])
              and type(bridge["sha256"]) is str and len(bridge["sha256"]) == 64
              and all(c in "0123456789abcdef" for c in bridge["sha256"]),
              "Exact bridge implementation identity required")
        samples, updates, cursor = (provenance[name] for name in (
            "committed_samples_consumed", "committed_optimizer_updates", "committed_log_cursor"))
        _need(all(type(value) is int and value >= 0 for value in (samples, updates, cursor))
              and updates <= samples and updates <= cursor,
              "Committed execution cursors differ")
        _need(provenance["H0_export_precision"] == "fp32_no_internal_AMP"
              and provenance["BF16_training_forward_bitwise_replay_claimed"] is False
              and provenance["training_capacity_reused_for_downstream_H0"] is False
              and provenance["scientific_acceptance"] is False,
              "Export provenance cannot acquire replay/capacity/scientific authority")
        # Only the full contract is deduplicated; its canonical SHA remains.
        result = {key: deepcopy(provenance[key]) for key in sorted(keys - {"training_contract"})}
        _canonical(result)
        return result
    except (KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, ExecutionCheckpointError):
            raise
        raise ExecutionCheckpointError("Incomplete or nonfinite execution cache provenance") from exc


def _checked_export_builder(model_configuration, contract):
    _, _, build, _ = _adapter()

    def builder(configuration):
        import torch
        _need(configuration == model_configuration,
              "Candidate/random export configurations differ")
        model = build(configuration, contract)
        _need(callable(getattr(model, "encode_atoms", None))
              and getattr(model, "latent_dim", None)
                  == model_configuration["backbone"]["dim"],
              "Canonical source-ordered H0 API/dimension required")
        floating = [value for value in (*model.parameters(), *model.buffers())
                    if value.is_floating_point()]
        _need(all(value.dtype == torch.float32 for value in floating),
              "Export parameters and buffers must already be FP32")
        for module in model.modules():
            options = getattr(module, "v3_performance_options", None)
            if options is not None:
                _need(type(options) is dict and options.get("precision") == "fp32",
                      "An internal performance wrapper retains non-FP32 execution")
            precision = getattr(module, "precision", None)
            _need(precision is None or precision == "fp32",
                  "An internal module retains a non-FP32 precision policy")
        model.eval()
        return model

    return builder


def execution_checkpoint_state(payload, configuration):
    """Validate an already safe-decoded, byte-bound sample checkpoint.

    The caller authenticates the original COMPLETE/payload/config raw bytes and
    architecture extension before entering this branch. No mutable optimizer,
    sampler, provider, RNG or global precision state is restored by this reader.
    """
    _need(type(configuration) is dict
          and type(configuration.get("model")) is dict
          and type(configuration.get("training_execution")) is dict,
          "Explicit opt-in source training-execution configuration required")
    _need(type(payload) is dict
          and payload.get("schema") == "model_v3_training_checkpoint_v1",
          "The original immutable sample-checkpoint envelope is required")
    try:
        extra = payload["extra_state"]
        _need(type(extra) is dict, "Typed trainer resume state required")
        trainer_contract = extra["contract"]
        _need(type(trainer_contract) is dict and type(extra.get("execution")) is dict,
              "Typed trainer contract/runtime execution required")
        contract = trainer_contract["training_execution"]
        model_configuration = configuration["model"]
        capability = validate_h0_export_capability(model_configuration, contract)
        from .v3_training_execution import TrainingExecutionSpec
        requested = TrainingExecutionSpec(**configuration["training_execution"]).semantic()
        _need(requested == contract["requested_execution"],
              "The original execution request and saved contract differ")
        _, validate_state, _, _ = _adapter()
        validate_state(contract, extra["execution"])
        _need(extra["execution"].get("training_execution") == contract,
              "The saved runtime does not bind the same training contract")
        seed = configuration["seed"]
        _need(type(seed) is int and seed >= 0
              and type(trainer_contract["view_configuration"]["seed"]) is int
              and trainer_contract["view_configuration"]["seed"] == seed,
              "Actual pretraining/view seeds differ")
        from .v3_training import SampleClock
        clock = payload["clock"]
        _need(type(clock) is dict
              and set(clock) == {"schema", "sample_budget", "milestones",
                                 "samples_consumed", "optimizer_updates", "saved_milestones"}
              and clock["schema"] == "model_v3_consumed_sample_clock_v1"
              and all(type(clock[key]) is int for key in (
                  "sample_budget", "samples_consumed", "optimizer_updates"))
              and all(type(clock[key]) is list and all(type(v) is int for v in clock[key])
                      for key in ("milestones", "saved_milestones")),
              "The complete original typed sample-clock state is required")
        preview = SampleClock(clock["sample_budget"], tuple(clock["milestones"]))
        preview.load_state_dict(clock)
        sampler = payload["sampler"]
        _need(type(sampler) is dict
              and set(sampler) == {"schema", "contract_sha256", "samples_consumed"}
              and sampler["schema"] == "model_v3_uniform_molecule_sampler_v1"
              and type(sampler["contract_sha256"]) is str
              and len(sampler["contract_sha256"]) == 64
              and all(c in "0123456789abcdef" for c in sampler["contract_sha256"]),
              "The original typed, source-bound sampler state is required")
        proxy = configuration["proxy_contract"]
        from .v3_training_execution_policy import h0_runtime_controls_from_deterministic
        declared_controls = h0_runtime_controls_from_deterministic(proxy["execution"]["deterministic"])
        _need(contract["h0_export"]["runtime_controls"] == declared_controls,
              "Original declared precision controls and checkpoint H0 map differ")
        _need(type(proxy["sample_budget"]) is int
              and clock["sample_budget"] == proxy["sample_budget"]
              and clock["milestones"] == proxy["milestones"],
              "The checkpoint sample budget/milestones differ from the source configuration")
        _need(type(payload["sampler"].get("samples_consumed")) is int
              and payload["sampler"]["samples_consumed"] == clock["samples_consumed"],
              "The committed sampler/sample clocks differ")
        _need(type(extra.get("log_cursor")) is int
              and extra["log_cursor"] >= clock["optimizer_updates"]
              and "pending_log" in extra and extra["pending_log"] is None,
              "An acknowledged checkpoint history cursor is required")
        scheduler = extra["scheduler"]
        _need(type(scheduler) is dict and type(scheduler.get("samples_consumed")) is int
              and scheduler["samples_consumed"] == clock["samples_consumed"]
              and scheduler["binding_sha256"] == trainer_contract["scheduler_binding"]
              and type(scheduler["contract"]) is dict
              and type(scheduler["contract"].get("sample_budget")) is int
              and scheduler["contract"]["sample_budget"] == clock["sample_budget"],
              "The committed scheduler/sample clocks differ")
        full_state = payload["model"]
        _need(type(full_state) is dict and bool(full_state)
              and all(type(key) is str
                      and key.startswith(("encoder.", "pd_heads."))
                      for key in full_state),
              "Only the exact trained encoder/PD-head namespaces are supported")
        encoder_state = {
            key[len("encoder."):]: value for key, value in full_state.items()
            if key.startswith("encoder.")}
        _need(bool(encoder_state), "A complete trained encoder state is required")
        provenance = {
            "training_contract": deepcopy(contract),
            "bridge_implementation": _bridge_source(),
            "training_execution_contract_sha256":
                capability["training_execution_contract_sha256"],
            "H0_export": deepcopy(capability["H0_export"]),
            "H0_export_sha256": capability["H0_export_sha256"],
            "H0_export_precision": "fp32_no_internal_AMP",
            "BF16_training_forward_bitwise_replay_claimed": False,
            "training_capacity_reused_for_downstream_H0": False,
            "saved_runtime_execution_sha256": _canonical(extra["execution"]),
            "committed_samples_consumed": clock["samples_consumed"],
            "committed_optimizer_updates": clock["optimizer_updates"],
            "committed_log_cursor": extra["log_cursor"],
            "scientific_acceptance": False,
        }
        training_execution_cache_projection(provenance)
        _canonical(provenance)
    except (KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, ExecutionCheckpointError):
            raise
        raise ExecutionCheckpointError(
            "Checkpoint execution/export/cursor semantics differ") from exc
    return encoder_state, _checked_export_builder(model_configuration, contract), provenance
