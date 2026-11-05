"""Read-only Native-S checkpoint semantics; no data access or weight conversion."""
from copy import deepcopy
from dataclasses import asdict, replace
from pathlib import Path
import re

from .v3_contract import canonical_hash
from .v3_h0_runtime import physical_source_binding

MEMBER_SCHEMA = "existing_native_S_precision_member_v1"
NATIVE_SCOPE = "existing_native_S_original_TRAIN_record_sampler_not_D5"
NATIVE_BINDINGS = {"code_sha", "configuration_sha256", "registry_sha256",
                   "normalization_sha256", "data_version", "source_inventory_sha256"}


class NativeCheckpointError(ValueError):
    pass


def need(value, message):
    if not value:
        raise NativeCheckpointError(message)


def native_member_contract(member):
    """Recognize only the producer's existing closed-member metadata envelope."""
    need(type(member) is dict and member.get("schema") == MEMBER_SCHEMA,
         "Known Native-S member-result schema required")
    contract = member.get("member_contract")
    need(type(contract) is dict and type(contract.get("model")) is dict,
         "Native member contract/model is required")
    need(member.get("status") in {"SEGMENT_PAUSED", "UPDATES_COMPLETE_PENDING_OUTER_TERMINAL"},
         "A completed Native member segment is required")
    need(member.get("scope") == contract.get("source_scope") == NATIVE_SCOPE
         and contract.get("plan", {}).get("input_scope") == NATIVE_SCOPE,
         "Only the explicitly descriptive original Native-S population is supported")
    need(member.get("D5_authority") is False and member.get("scientific_acceptance") is False
         and contract.get("D5_authority") is False,
         "Native fallback metadata must not acquire scientific/D5 authority")
    need(type(member.get("seed")) is int and member["seed"] in (0, 1)
         and type(contract.get("seed")) is int and member["seed"] == contract["seed"], "Native pretraining seed differs")
    need(member.get("precision") in ("fp32", "bf16")
         and member["precision"] == contract.get("precision"), "Native pretraining precision differs")
    need(contract.get("loss_semantics") ==
         "V3_S_mean_of_observed_original_raw_fields; not_legacy_weighted_total",
         "Native producer loss/contract semantics differ")
    need(contract.get("validation_role") == "PRETRAIN_VAL"
         and type(contract.get("validation_seed")) is int and contract["validation_seed"] == 0
         and type(contract.get("validation_epoch")) is int and contract["validation_epoch"] == 0
         and contract.get("TRAIN_UNSEEN_CONFORMATION") == "NOT_PROVIDED",
         "Native population/validation semantics differ")
    plan_data = contract.get("plan")
    need(type(plan_data) is dict and type(plan_data.get("warmup_samples")) is int,
         "Native plan and integer warmup required")
    transported = dict(plan_data)
    for name in ("validation_updates", "checkpoint_updates"):
        grid = transported.get(name)
        need(type(grid) in (list, tuple) and all(type(v) is int for v in grid),
             "Native plan grid must contain integer update indices")
        transported[name] = tuple(grid)
    from .v3_native_s_precision import NativeSPrecisionPlan
    try:
        plan = NativeSPrecisionPlan(**transported)
    except (TypeError, ValueError) as exc:
        raise NativeCheckpointError("Original NativeSPrecisionPlan rejects this contract") from exc
    need(canonical_hash(asdict(plan)) == canonical_hash(plan_data), "Native plan transport differs")
    specific = {"seed", "precision", "input_binding", "sampler_contract_sha256", "execution"}
    need(member.get("common_binding") == {k: v for k, v in contract.items() if k not in specific},
         "Native member/common configuration differs")
    model = contract["model"]
    backbone = model.get("backbone", {})
    need((backbone.get("dim"), backbone.get("layers"), backbone.get("heads")) == (512, 6, 8)
         and not any(k in backbone for k in ("v3_architecture", "v3_legacy_memory")),
         "Native bridge requires the original 512x6x8 encoder")
    return contract


def _producer_sources(contract):
    """Check producer/builder implementations, not unrelated later tools."""
    declared = contract.get("source_files")
    need(type(declared) is dict and declared, "Native source inventory required")
    need(all(type(k) is str and type(v) is str and re.fullmatch("[0-9a-f]{64}", v)
             for k, v in declared.items()), "Native source inventory digests differ")
    required = {"current/phychem_mfm/" + name for name in (
        "config.py", "factory.py", "model/v3_performance.py", "model/v3_multiview.py",
        "model/shared.py", "model/backbone.py", "model/attention.py",
        "model/common.py", "model/heads.py", "model/routes.py", "model/outputs.py",
        "model/normalization.py", "model/phase1_specs.py", "model/adaptation.py", "model/expert_blocks.py",
        "data/descriptor_schema.py", "supervision.py",
        "phase1/v3_native_s_precision.py", "phase1/v3_native_s_precision_data.py",
        "phase1/v3_training.py", "phase1/v3_contract.py")}
    need(required <= declared.keys(), "Native constructor/producer source binding is incomplete")
    package = Path(__file__).absolute().parents[1]
    keys = sorted(required | {k for k in declared if k.startswith("current/phychem_mfm/model/")})
    result = {}
    for key in keys:
        suffix = key.removeprefix("current/phychem_mfm/")
        need(not Path(suffix).is_absolute() and ".." not in Path(suffix).parts,
             "Native implementation path escapes the package")
        ref = physical_source_binding(package / suffix)
        need(ref["sha256"] == declared[key], "Native producer/encoder implementation differs: " + key)
        result[key] = ref
    return result


def native_checkpoint_state(payload, member, marker, checkpoint_ref, payload_size):
    """Validate an already weights-only-decoded payload; return strict encoder state.

    The caller binds and reads COMPLETE and the payload before invoking this
    function. No optimizer/sampler/RNG restoration or runtime-policy mutation.
    """
    contract = native_member_contract(member)
    need(payload.get("schema") == "model_v3_training_checkpoint_v1"
         and marker.get("schema") == payload["schema"], "Native checkpoint schema differs")
    need(marker.get("payload_sha256") == checkpoint_ref["sha256"]
         and type(marker.get("payload_bytes")) is int and marker["payload_bytes"] == payload_size
         and marker.get("bindings") == payload.get("bindings"),
         "Native COMPLETE/payload digest, bytes or bindings differ")
    bindings = payload.get("bindings")
    need(type(bindings) is dict and set(bindings) == NATIVE_BINDINGS,
         "Exact Native source/config/registry/data bindings required")
    need(all(type(v) is str and re.fullmatch("[0-9a-f]{40}" if k == "code_sha" else "[0-9a-f]{64}", v)
             for k, v in bindings.items()), "Native binding digest type differs")
    need(bindings["configuration_sha256"] == canonical_hash(contract)
         and bindings["code_sha"] == contract.get("code_sha")
         and bindings["data_version"] == contract.get("data_version")
         and bindings["normalization_sha256"] == canonical_hash({})
         and bindings["source_inventory_sha256"] == canonical_hash(contract.get("source_files")),
         "Native configuration/data/source contract differs")
    extra = payload.get("extra_state")
    need(type(extra) is dict and canonical_hash(extra.get("contract")) == canonical_hash(contract),
         "Native checkpoint and bound member contract differ")
    clock, sampler = payload.get("clock"), payload.get("sampler")
    need(type(clock) is dict and type(sampler) is dict, "Native committed clock/sampler required")
    need(set(clock) == {"schema", "sample_budget", "milestones", "samples_consumed", "optimizer_updates", "saved_milestones"}
         and clock.get("schema") == "model_v3_consumed_sample_clock_v1"
         and clock.get("milestones") == [] and clock.get("saved_milestones") == []
         and type(clock.get("sample_budget")) is int and clock["sample_budget"] > 0,
         "Native sample-clock schema differs")
    for key in ("samples_consumed", "optimizer_updates"):
        value = clock.get(key)
        need(type(value) is int and value >= 0 and type(marker.get(key)) is int
             and marker[key] == value and type(member.get(key)) is int and member[key] == value,
             "Native committed member/header cursor differs: " + key)
    for value in (sampler.get("contract_sha256"), contract.get("sampler_contract_sha256"),
                  extra.get("input_chain"), member.get("training_input_chain_sha256")):
        need(type(value) is str and re.fullmatch("[0-9a-f]{64}", value),
             "Both sampler-contract/input-chain SHA bindings are mandatory")
    need(type(sampler.get("samples_consumed")) is int
         and sampler["samples_consumed"] == clock["samples_consumed"]
         and sampler.get("contract_sha256") == contract.get("sampler_contract_sha256")
         and clock.get("sample_budget") == contract["plan"].get("sample_budget")
         and clock["optimizer_updates"] <= clock["samples_consumed"] <= clock["sample_budget"]
         and clock["optimizer_updates"] <= contract["plan"].get("updates", -1),
         "Native sampler/budget cursor differs")
    saved = extra.get("saved_updates")
    need(type(saved) is list and all(type(v) is int and 0 <= v <= clock["optimizer_updates"] for v in saved)
         and saved == sorted(set(saved)) and clock["optimizer_updates"] in saved
         and type(extra.get("log_cursor")) is int and extra["log_cursor"] >= clock["optimizer_updates"]
         and type(extra.get("model_training")) is bool
         and type(member.get("tracker")) is dict and type(extra.get("tracker")) is dict
         and canonical_hash(extra["tracker"]) == canonical_hash(member["tracker"])
         and extra.get("input_chain") == member.get("training_input_chain_sha256"),
         "Native acknowledged input/checkpoint cursor differs")
    state = payload.get("model")
    need(type(state) is dict and state and all(type(k) is str and k.startswith("encoder.") for k in state),
         "Native S state must contain exactly the encoder namespace; no arbitrary prefix stripping")
    encoder_state = {k[len("encoder."):]: value for k, value in state.items()}
    from ..model.v3_performance import PerformanceOptions, build_performance_model
    options = PerformanceOptions(**contract.get("base_options", {}))
    need(asdict(options) == asdict(PerformanceOptions(precision="fp32", backbone_checkpointing=True))
         == contract.get("base_options") and options.precision == "fp32"
         and not options.compile_backbone, "Native performance options differ or are unsupported")
    # The producer explicitly records base_options with precision='fp32', while
    # actual training wrappers may open their own BF16 autocast internally.
    # Reconstruct its declared FP32 H0 path; do not mutate a trained module or
    # pretend an outer autocast(False) overrides those internal BF16 contexts.
    training_options = replace(options, precision=contract["precision"])
    need(contract.get("execution", {}).get("performance_options") == {"encoder": asdict(training_options)},
         "Native recorded execution/pretraining performance semantics differ")
    sources = _producer_sources(contract)
    # source_registry constructs only the frozen three S field definitions; it
    # opens no native data or targets. Bind its raw source and semantic registry.
    from .v3_native_s_precision_data import source_registry
    registry, _ = source_registry(bindings["data_version"])
    need(registry.source_sha256 == bindings["registry_sha256"]
         and registry.content_sha256 == contract.get("registry"),
         "Native structural registry source/content differs")
    def builder(configuration):
        need(configuration == contract["model"], "Native candidate/random configuration differs")
        return build_performance_model(configuration, options)
    provenance = {"schema": "model_v3_native_S_checkpoint_encoder_binding_v1",
        "scope": "NATIVE_S_FALLBACK_DESCRIPTIVE_DEV_PANEL_ONLY",
        "pretraining_code_sha": bindings["code_sha"], "pretraining_data_version": bindings["data_version"],
        "pretraining_registry_source_sha256": bindings["registry_sha256"],
        "native_contract_sha256": bindings["configuration_sha256"],
        "source_inventory_sha256": bindings["source_inventory_sha256"],
        "pretraining_precision": contract["precision"], "performance_options": asdict(options),
        "pretraining_performance_options": asdict(training_options),
        "H0_export_performance_options": asdict(options),
        "H0_export_precision": "fp32_noAMP_declared_base_options",
        "BF16_training_forward_bitwise_replay_claimed": False,
        "producer_implementations": sources, "bridge_implementation": physical_source_binding(__file__),
        "optimizer_updates": clock["optimizer_updates"], "samples_consumed": clock["samples_consumed"],
        "checkpoint_runtime": deepcopy(payload.get("runtime")),
        "pretraining_execution": deepcopy(contract.get("execution")),
        "D5_authority": False, "scientific_acceptance": False, "pretraining_seed_SD_claimed": False}
    return encoder_state, builder, provenance
