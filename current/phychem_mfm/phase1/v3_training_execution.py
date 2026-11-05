"""One opt-in training execution contract; no data authority or job scheduler.

A-only qualification stays in model.v3_checkpoint_policy.  Operational capacity
refs are deliberately absent from the resumable mathematical contract.
"""
from __future__ import annotations

from contextlib import contextmanager, nullcontext
from copy import deepcopy
from dataclasses import asdict, dataclass, field, replace
import json
import os
from typing import Any

import torch

from ..model.v3_architecture import ArchitectureOptions, build_architecture_model
from ..model.v3_checkpoint_policy import canonical, require, verify_observed_sources
from ..model.v3_logical_batch import LogicalBatchPadding
from ..model.v3_performance import PerformanceOptions, execution_context, install_training_performance
from .v3_training_execution_policy import h0_runtime_controls_from_deterministic
from ..model.v3_training_capacity import (TrainingCapacityObserver, resolve_training_capacity,
    training_implementation_sources)

CONTRACT_SCHEMA = "model_v3_training_execution_contract_v1"
EXPORT_SCHEMA = "model_v3_training_h0_export_v1"
WORKLOAD_SCHEMA = "model_v3_training_workload_v1"
CONTRACT_KEYS = {"schema", "model_configuration", "requested_execution", "resolved_options",
    "architecture", "module_layout", "checkpoint_scope_map", "optimizer_dispatch",
    "implementation_sha256", "workload_sha256", "h0_export", "execution_state"}


def _json(value):
    return json.loads(json.dumps(value, sort_keys=True, allow_nan=False))


@dataclass(frozen=True)
class TrainingExecutionSpec:
    schema: str = "model_v3_training_execution_v1"
    options: dict = field(default_factory=dict)
    checkpoint_policy: str = "manual"
    geometry_scope: str = "c1_scalar_distance_v1"
    padding: dict | None = None
    batch_padded_cost: int = 8000000
    resident_models: int = 1

    def __post_init__(self):
        require(self.schema == "model_v3_training_execution_v1" and self.checkpoint_policy in
            {"manual", "auto_closed_training_profile_v1", "auto_adopted_A_v1"}, "Unknown training execution policy")
        require(self.geometry_scope in {"c1_scalar_distance_v1", "c1_shared_pair_v1"},
                "Unknown explicit geometry checkpoint scope")
        require(type(self.options) is dict, "Explicit performance options mapping required")
        PerformanceOptions(**self.options)
        require(type(self.batch_padded_cost) is int and self.batch_padded_cost > 0
                and self.resident_models == 1 and type(self.resident_models) is int,
                "Training is one complete model, never paired R2 residency")
        if self.padding is not None:
            LogicalBatchPadding(**self.padding)
        _json(asdict(self))

    def semantic(self):
        result = asdict(self)
        result["options"] = asdict(PerformanceOptions(**self.options))
        if self.padding is not None:
            result["padding"] = asdict(LogicalBatchPadding(**self.padding))
        return _json(result)


def validate_workload(binding, configuration):
    required = {"schema", "scope", "seed", "model_configuration", "data", "groups", "fields",
                "heads", "views", "view_policy", "loss", "optimizer", "validation"}
    require(type(binding) is dict and set(binding) == required and binding["schema"] == WORKLOAD_SCHEMA,
            "Complete versioned training workload binding required")
    value = _json(binding)
    require(type(value["seed"]) is int and value["model_configuration"] == _json(configuration),
            "Training workload seed/model differs")
    require(value["scope"] in {"engineering_synthetic_fixture", "authoritative_proxy",
            "authoritative_full_train", "authoritative_grid_cell"}, "Unknown training workload scope")
    require(type(value["groups"]) is list and bool(value["groups"])
            and len(set(value["groups"])) == len(value["groups"])
            and set(value["groups"]) <= {"S", "D", "P"}, "Explicit enabled training groups required")
    require(type(value["fields"]) is list and len(set(value["fields"])) == len(value["fields"]),
            "Explicit unique enabled training fields required")
    data = value["data"]
    require(type(data) is dict and {"registry_sha256", "normalization_sha256", "data_version",
            "authority_sha256", "selection"} <= set(data), "Actual validated input/role/selection binding required")
    require(all(type(data[key]) is str and len(data[key]) == 64
                and all(c in "0123456789abcdef" for c in data[key])
                for key in ("registry_sha256", "normalization_sha256", "authority_sha256"))
            and type(data["data_version"]) is str and bool(data["data_version"])
            and type(data["selection"]) is dict, "Actual input digests/selection required")
    require(value["views"] in ("one", "two", "three") and all(type(value[key]) is dict
            for key in ("heads", "view_policy", "loss", "optimizer", "validation")),
            "Actual heads/views/loss/optimizer/validation contract required")
    # The input provider owns its physical schema. All supplied projection keys
    # remain in the digest; this adapter does not mint D3/D4/D5 authority.
    return value


def _architecture(configuration):
    return asdict(ArchitectureOptions(**configuration["backbone"].get("v3_architecture", {})))


def _validate_options(configuration, spec, options):
    require(torch.get_default_dtype() == torch.float32 and torch.get_default_device().type == "cpu",
            "Training execution requires original CPU/fp32 parameter initialization before device transfer")
    shared = _architecture(configuration)["distance_bias"] != "C1-0"
    require(spec.geometry_scope == ("c1_shared_pair_v1" if shared else "c1_scalar_distance_v1"),
            "Architecture needs its explicit geometry checkpoint scope")
    require(not options.tf32 and not options.fused_adamw,
            "Failed/unadmitted TF32 or fused optimizer is not a training default")
    if spec.checkpoint_policy == "auto_adopted_A_v1":
        require(options.precision == "fp32" and options.attention_backend == "dense"
                and not options.compile_backbone and spec.padding is None,
                "Adopted A policy does not combine unqualified precision/compile/packing changes")
    require(not (spec.padding is not None and options.compile_backbone
                 and spec.checkpoint_policy != "manual"),
            "Automatic compiled packing lacks observed actual chunk workspace evidence")
    if shared:
        require(options.precision == "fp32" and options.attention_backend == "dense"
                and options.distance_implementation == "dense",
                "SharedPair training requires explicit fp32/dense shared geometry; bf16/sparse/tiled not admitted")
    elif options.distance_implementation == "dense":
        require(not options.distance_checkpointing, "Dense original distance MLP has no tiled checkpoint scope")
    if options.attention_backend == "sparse_radius":
        require(configuration["backbone"].get("use_radius_mask", False) is True,
                "Global attention cannot be silently changed into a sparse radius architecture")
    if spec.padding is not None:
        require(options.precision == "fp32" and float(configuration["backbone"].get("dropout", 0.)) == 0.,
                "Training packing requires zero-dropout fp32 before construction/RNG consumption")


@dataclass
class TrainingEncoderExecution:
    encoder: Any
    resolved_options: PerformanceOptions | None
    contract: dict | None = None
    observer: TrainingCapacityObserver | None = None
    specification: TrainingExecutionSpec | None = None
    model_configuration: dict | None = None
    workload_binding: dict | None = None
    implementation_sha256: dict | None = None
    operational_admission: dict | None = None
    optimizer_dispatch: dict | None = None


def build_training_encoder(model_configuration, *, execution=None, workload_binding=None,
                           operational_admission=None):
    require("performance_execution_v1" not in model_configuration
            and "training_execution" not in model_configuration,
            "Execution must be consumed by the explicit training adapter, not ignored model keys")
    if execution is None:
        require(operational_admission is None, "No policy may silently consume a capacity admission")
        return TrainingEncoderExecution(build_architecture_model(model_configuration), None)
    spec = execution if isinstance(execution, TrainingExecutionSpec) else TrainingExecutionSpec(**execution)
    spec = TrainingExecutionSpec(**spec.semantic())
    configuration = _json(model_configuration)
    workload = validate_workload(workload_binding, configuration)
    options = PerformanceOptions(**spec.options)
    _validate_options(configuration, spec, options)
    sources = training_implementation_sources()
    resolved, guard, admission = resolve_training_capacity(spec, configuration, workload, options,
                                                          sources, operational_admission)
    if resolved.backbone_checkpointing is None:
        resolved = replace(resolved, backbone_checkpointing=bool(configuration["backbone"].get("activation_checkpointing", False)))
    encoder = build_architecture_model(configuration)
    padding = None if spec.padding is None else LogicalBatchPadding(**spec.padding)
    install_training_performance(encoder, resolved, padding=padding, capacity_guard=guard)
    observer = TrainingCapacityObserver(workload, spec.semantic(), asdict(resolved), sources)
    observer.capacity_selection = (deepcopy(admission) if spec.checkpoint_policy == "auto_adopted_A_v1" and guard is None
        else None if guard is None else deepcopy(guard.capacity_selection))
    return TrainingEncoderExecution(encoder, resolved, observer=observer, specification=spec,
        model_configuration=configuration, workload_binding=workload, implementation_sha256=sources,
        operational_admission=admission)


def make_training_optimizer(full_model, declared_optimizer, execution):
    require(execution.contract is None and execution.optimizer_dispatch is None,
            "Optimizer/execution contract is finalized exactly once")
    declared = _json(declared_optimizer)
    if execution.specification is None:
        return torch.optim.AdamW(full_model.parameters(), **declared)
    require(declared == execution.workload_binding["optimizer"], "Optimizer differs from bound workload")
    require(all(parameter.dtype == torch.float32 for parameter in full_model.parameters()),
            "Selective execution retains complete fp32 master parameters")
    for key in ("fused", "foreach"):
        require(key not in declared or declared[key] is None or type(declared[key]) is bool,
                "Explicit optimizer dispatch values required")
    require(declared.get("fused") is not True and not execution.resolved_options.fused_adamw,
            "Unadmitted fused optimizer cannot enter training")
    # Preserve omission/None/False and foreach exactly. The A builder's policy
    # of omitting fused=False is NOT substituted for a declared proxy dispatch.
    optimizer = torch.optim.AdamW(full_model.parameters(), **declared)
    execution.optimizer_dispatch = {"class": "torch.optim.AdamW", "declared": declared,
        "effective": {key: optimizer.defaults.get(key) for key in ("fused", "foreach", "capturable",
                       "differentiable", "amsgrad", "maximize")}}
    return optimizer


def _layout(model):
    return {name: {"class": type(module).__module__ + "." + type(module).__qualname__,
        "checkpoint_flags": {key: value for key, value in vars(module).items()
            if type(value) is bool and (key.endswith("checkpointing") or key in ("checkpoint_pairs", "use_checkpoint"))}}
        for name, module in model.named_modules()}


def _scope_map(encoder):
    shared = hasattr(encoder.backbone, "pair_encoder")
    distances = ["encoder.backbone.pair_encoder"] if shared else [
        "encoder.backbone.layers.%d.attn.dist_mlp" % index for index, layer in enumerate(encoder.backbone.layers)
        if hasattr(layer.attn.dist_mlp, "activation_checkpointing")]
    return {"backbone_checkpointing": {"modules": ["encoder.backbone"], "attribute": "activation_checkpointing",
                "meaning": "all_transformer_layers"},
            "distance_checkpointing": {"modules": distances, "attribute": "activation_checkpointing",
                "meaning": "shared_pair_encoder_complete" if shared else "per_layer_scalar_distance_tiles"},
            "head_checkpointing": {"modules": ["encoder.geometry_head"], "attribute": "activation_checkpointing",
                "meaning": "original_S_geometry_head_only_PD_heads_unchanged"}}


def _h0_runtime_controls(state):
    return h0_runtime_controls_from_deterministic(state["deterministic_algorithms"])


def finalize_training_execution(full_model, optimizer, execution):
    if execution.specification is None:
        return None
    require(execution.contract is None and full_model.encoder is execution.encoder
            and execution.optimizer_dispatch is not None, "Finalize the real complete model/optimizer exactly once")
    members = [p for group in optimizer.param_groups for p in group["params"]]
    actual = {id(p) for p in members}
    require(len(members) == len(actual), "Duplicate complete-model optimizer parameters")
    require(actual == {id(p) for p in full_model.parameters()}, "Optimizer must contain the full model including PD heads")
    require(execution.optimizer_dispatch["declared"] == execution.workload_binding["optimizer"],
            "Final optimizer differs from execution workload")
    options = asdict(execution.resolved_options)
    export_options = dict(options, precision="fp32", compile_backbone=False)
    from .v3_trainer import _execution_state
    expected_state = deepcopy(_execution_state(full_model))
    expected_state.pop("training_execution", None)
    contract = {"schema": CONTRACT_SCHEMA, "model_configuration": execution.model_configuration,
        "requested_execution": execution.specification.semantic(), "resolved_options": options,
        "architecture": _architecture(execution.model_configuration), "module_layout": _layout(full_model),
        "checkpoint_scope_map": _scope_map(execution.encoder), "optimizer_dispatch": execution.optimizer_dispatch,
        "implementation_sha256": execution.implementation_sha256,
        "workload_sha256": canonical(execution.workload_binding), "execution_state": expected_state,
        "h0_export": {"schema": EXPORT_SCHEMA,
            "builder": "phychem_mfm.phase1.v3_training_execution.build_h0_export_encoder",
            "precision": "fp32", "resolved_options": export_options,
            "padding": execution.specification.semantic()["padding"], "architecture": _architecture(execution.model_configuration),
            "allowed_changes": ["precision", "compile_backbone"],
            "runtime_controls": _h0_runtime_controls(expected_state),
            "fp32_same_path_replay_expected": options["precision"] == "fp32" and not options["compile_backbone"]}}
    contract = validate_training_execution_contract(contract)
    execution.contract = deepcopy(contract)
    full_model.training_execution_contract = deepcopy(contract)
    execution.observer.bind_contract(contract)
    return deepcopy(contract)


def validate_training_execution_contract(contract, *, verify_sources=True):
    require(type(contract) is dict and set(contract) == CONTRACT_KEYS
            and contract["schema"] == CONTRACT_SCHEMA, "Unknown complete training execution contract")
    value = _json(contract)
    spec = TrainingExecutionSpec(**value["requested_execution"])
    options = PerformanceOptions(**value["resolved_options"])
    requested_options = asdict(PerformanceOptions(**spec.options))
    resolved_options = asdict(options)
    require(all(resolved_options[key] == item for key, item in requested_options.items()
                if key not in ("backbone_checkpointing", "distance_checkpointing", "head_checkpointing")),
            "A resolved policy changed non-checkpoint execution mathematics")
    if spec.checkpoint_policy == "manual":
        manual = dict(requested_options)
        if manual["backbone_checkpointing"] is None:
            manual["backbone_checkpointing"] = bool(value["model_configuration"]["backbone"].get("activation_checkpointing", False))
        require(resolved_options == manual, "Manual checkpoint options changed")
    _validate_options(value["model_configuration"], spec, options)
    require(type(options.backbone_checkpointing) is bool and value["architecture"] == _architecture(value["model_configuration"]),
            "Resolved architecture/checkpoint contract differs")
    require(type(value["module_layout"]) is dict and "encoder.backbone" in value["module_layout"],
            "Complete actual module layout required")
    require(type(value["workload_sha256"]) is str and len(value["workload_sha256"]) == 64,
            "Training workload digest required")
    state = value["execution_state"]
    require(type(state) is dict and "training_execution" not in state,
            "Execution state projection must not recursively contain the contract")
    flags = {name: row["checkpoint_flags"] for name, row in value["module_layout"].items() if row["checkpoint_flags"]}
    require(state["resolved_checkpoint_flags"] == flags, "Saved layout/checkpoint flags differ")
    shared = value["architecture"]["distance_bias"] != "C1-0"
    distance_paths = ["encoder.backbone.pair_encoder"] if shared else sorted(name for name in flags
        if name.startswith("encoder.backbone.layers.") and name.endswith(".attn.dist_mlp"))
    expected_scopes = {"backbone_checkpointing": {"modules": ["encoder.backbone"], "attribute": "activation_checkpointing",
            "meaning": "all_transformer_layers"},
        "distance_checkpointing": {"modules": distance_paths, "attribute": "activation_checkpointing",
            "meaning": "shared_pair_encoder_complete" if shared else "per_layer_scalar_distance_tiles"},
        "head_checkpointing": {"modules": ["encoder.geometry_head"], "attribute": "activation_checkpointing",
            "meaning": "original_S_geometry_head_only_PD_heads_unchanged"}}
    require(value["checkpoint_scope_map"] == expected_scopes, "Checkpoint semantic scope map differs")
    require(state["performance_options"] == {"encoder": value["resolved_options"]},
            "Saved actual encoder performance options differ")
    runtime_contract = {"schema": "model_v3_training_encoder_runtime_v1", "architecture": "shared_pair" if shared else "C1-0",
        "padding": spec.semantic()["padding"],
        "distance_scope": "shared_pair_encoder_complete" if shared else "per_layer_scalar_distance",
        "source_sha256": value["implementation_sha256"]["current/phychem_mfm/model/v3_logical_batch.py"]}
    require(state.get("performance_integration") == {"encoder.backbone": runtime_contract},
            "Saved actual packing/source execution differs")
    require(state["matmul_tf32"] is False and state["cudnn_tf32"] is False
            and state["float32_matmul_precision"] == "highest", "Unadmitted effective runtime precision")
    for name, scope in value["checkpoint_scope_map"].items():
        require(name in ("backbone_checkpointing", "distance_checkpointing", "head_checkpointing")
                and set(scope) == {"modules", "attribute", "meaning"}, "Unknown checkpoint scope map")
        for path in scope["modules"]:
            require(path in flags and flags[path][scope["attribute"]] == value["resolved_options"][name],
                    "Checkpoint scope does not match the real module flag")
    require(set(value["checkpoint_scope_map"]) == {"backbone_checkpointing", "distance_checkpointing", "head_checkpointing"},
            "All three checkpoint scopes required")
    export = value["h0_export"]
    require(set(export) == {"schema", "builder", "precision", "resolved_options", "padding", "architecture",
            "allowed_changes", "runtime_controls", "fp32_same_path_replay_expected"} and export["schema"] == EXPORT_SCHEMA
            and export["builder"] == "phychem_mfm.phase1.v3_training_execution.build_h0_export_encoder"
            and export["precision"] == "fp32" and export["architecture"] == value["architecture"]
            and export["padding"] == spec.semantic()["padding"]
            and export["allowed_changes"] == ["precision", "compile_backbone"]
            and export["runtime_controls"] == _h0_runtime_controls(state), "Unknown FP32 H0 export mapping")
    expected = dict(value["resolved_options"], precision="fp32", compile_backbone=False)
    require(export["resolved_options"] == expected and export["fp32_same_path_replay_expected"] ==
            (options.precision == "fp32" and not options.compile_backbone), "H0 export mapping silently changed execution")
    dispatch = value["optimizer_dispatch"]
    require(set(dispatch) == {"class", "declared", "effective"} and dispatch["class"] == "torch.optim.AdamW"
            and dispatch["declared"].get("fused") is not True, "Unknown optimizer dispatch contract")
    defaults = {"fused": None, "foreach": None, "capturable": False,
                "differentiable": False, "amsgrad": False, "maximize": False}
    require(dispatch["effective"] == {key: dispatch["declared"].get(key, item) for key, item in defaults.items()},
            "Actual optimizer dispatch differs from explicit declared omission/None/False")
    if verify_sources:
        sources = training_implementation_sources()
        require(value["implementation_sha256"] == sources, "Training execution source graph changed")
        verify_observed_sources(value["implementation_sha256"], sources)
    return value


def validate_training_execution_state(contract, execution_state):
    value = validate_training_execution_contract(contract)
    require(type(execution_state) is dict and execution_state.get("training_execution") == value,
            "Checkpoint execution lacks its identical training contract")
    actual = deepcopy(execution_state)
    actual.pop("training_execution")
    require(actual == value["execution_state"], "Actual saved execution projection differs from contract")


def validate_h0_export_contract(contract):
    value = validate_training_execution_contract(contract)
    require(not value["resolved_options"]["compile_backbone"],
            "Compiled training H0 export has no admitted bitwise execution mapping")
    return value


def build_h0_export_encoder(model_configuration, contract):
    value = validate_h0_export_contract(contract)
    require(_json(model_configuration) == value["model_configuration"], "H0 model configuration differs")
    encoder = build_architecture_model(model_configuration)
    padding = value["h0_export"]["padding"]
    install_training_performance(encoder, PerformanceOptions(**value["h0_export"]["resolved_options"]),
        padding=None if padding is None else LogicalBatchPadding(**padding), capacity_guard=None)
    encoder.eval()
    encoder.training_h0_export_contract = deepcopy(value["h0_export"])
    return encoder


def training_execution_context(execution):
    return nullcontext() if execution.resolved_options is None else execution_context(execution.resolved_options)

def rebind_training_execution(full_model, optimizer, parent_execution, *, workload_binding,
                              execution=None, operational_admission=None):
    """WSD-only semantic rebind over the EXACT existing model/optimizer.

    The original WSD validator still owns parent COMPLETE/request/terminal,
    source-addition policy, clocks, sampler, schedule and Root admission. This
    function grants none of those and never copies/reinitializes model state.
    """
    require(isinstance(parent_execution, TrainingEncoderExecution), "Actual parent execution handle required")
    if parent_execution.specification is None:
        require(execution is None and operational_admission is None, "A legacy WSD parent cannot silently gain an execution policy")
        return parent_execution
    parent = validate_training_execution_contract(parent_execution.contract)
    require(full_model.encoder is parent_execution.encoder and full_model.training_execution_contract == parent,
            "WSD execution is not the actual restored parent model")
    from .v3_trainer import _execution_state
    actual = _execution_state(full_model)
    actual["training_execution"] = deepcopy(full_model.training_execution_contract)
    validate_training_execution_state(parent, actual)
    child_workload = validate_workload(workload_binding, parent_execution.model_configuration)
    parent_workload = deepcopy(parent_execution.workload_binding)
    require(canonical(parent_workload) == parent["workload_sha256"], "Actual parent workload binding differs")
    old, new = deepcopy(parent_workload), deepcopy(child_workload)
    for value in (old, new):
        require({"schedule", "sample_budget"} <= set(value["view_policy"]), "Explicit retained WSD workload schedule/budget required")
        value["view_policy"].pop("schedule")
        value["view_policy"].pop("sample_budget")
    require(old == new, "WSD may only change its already validated schedule and sample budget")
    spec = parent_execution.specification if execution is None else (
        execution if isinstance(execution, TrainingExecutionSpec) else TrainingExecutionSpec(**execution))
    spec = TrainingExecutionSpec(**spec.semantic())
    require(spec.semantic() == parent_execution.specification.semantic(), "WSD execution mathematics/policy cannot change")
    requested_options = PerformanceOptions(**spec.options)
    sources = training_implementation_sources()
    resolved, guard, admission = resolve_training_capacity(spec, parent_execution.model_configuration,
        child_workload, requested_options, sources, operational_admission, existing_model=True)
    if spec.checkpoint_policy == "auto_adopted_A_v1" and guard is None:
        # A missing operational receipt must not mutate the already restored
        # parent flags or prevent a schedule-only child. The exact workload
        # comparison above retains model/data/heads/views/shape policy; reuse
        # its SAME live size guard instead of inventing a larger capacity.
        parent_flags = parent_execution.resolved_options
        if any(getattr(parent_flags, key) is False for key in
                ("backbone_checkpointing", "distance_checkpointing", "head_checkpointing")):
            guard = full_model.encoder.backbone.capacity_guard
            require(guard is not None, "Parent adopted checkpoint flags require their existing actual capacity guard")
            resolved = parent_flags
            admission = {"schema": "model_v3_adopted_A_parent_capacity_retained_v1",
                "reason": "KEEP_RESTORED_PARENT_FLAGS_AND_SAME_WORKLOAD_SIZE_GUARD",
                "fresh_capacity_evidence": admission, "new_capacity_claimed": False}
    if resolved.backbone_checkpointing is None:
        resolved = replace(resolved, backbone_checkpointing=bool(
            parent_execution.model_configuration["backbone"].get("activation_checkpointing", False)))
    require(asdict(resolved) == asdict(parent_execution.resolved_options),
            "Child capacity selection changed actual parent checkpoint/options; no implicit rebuild")
    observer = TrainingCapacityObserver(child_workload, spec.semantic(), asdict(resolved), sources)
    observer.capacity_selection = (deepcopy(admission) if spec.checkpoint_policy == "auto_adopted_A_v1" and guard is None
        else None if guard is None else deepcopy(guard.capacity_selection))
    result = TrainingEncoderExecution(full_model.encoder, resolved, observer=observer, specification=spec,
        model_configuration=deepcopy(parent_execution.model_configuration), workload_binding=child_workload,
        implementation_sha256=sources, operational_admission=admission,
        optimizer_dispatch=deepcopy(parent_execution.optimizer_dispatch))
    # All rejecting predicates precede this metadata-only guard replacement.
    old_guard = full_model.encoder.backbone.capacity_guard
    try:
        full_model.encoder.backbone.capacity_guard = guard
        finalize_training_execution(full_model, optimizer, result)
    except BaseException:
        full_model.encoder.backbone.capacity_guard = old_guard
        full_model.training_execution_contract = deepcopy(parent)
        raise
    return result

@contextmanager
def h0_export_context(contract, *, device_type):
    """Explicit eval scope; builder/load never silently alter caller globals.

    CUDA deterministic callers must arrange CUBLAS policy before initialization
    in their fresh worker. This function never sets that environment variable
    late or claims to establish its initialization history.
    """
    value = validate_h0_export_contract(contract)
    require(device_type in ("cpu", "cuda"), "Explicit actual H0 device type required")
    controls = value["h0_export"]["runtime_controls"]
    if device_type == "cuda" and controls["cublas_workspace_config_for_cuda"] is not None:
        require(os.environ.get("CUBLAS_WORKSPACE_CONFIG") == controls["cublas_workspace_config_for_cuda"],
                "Deterministic H0 CUDA requires the declared CUBLAS policy before initialization; no late environment repair")
    previous = {"float32_matmul_precision": torch.get_float32_matmul_precision(),
        "matmul_tf32": bool(torch.backends.cuda.matmul.allow_tf32), "cudnn_tf32": bool(torch.backends.cudnn.allow_tf32),
        "deterministic_algorithms": torch.are_deterministic_algorithms_enabled(),
        "deterministic_warn_only": torch.is_deterministic_algorithms_warn_only_enabled(),
        "cudnn_deterministic": bool(torch.backends.cudnn.deterministic), "cudnn_benchmark": bool(torch.backends.cudnn.benchmark)}
    try:
        # This setter also controls CUDA TF32. A second legacy allow_tf32
        # setter would corrupt a saved "medium" policy in PyTorch 2.10.
        torch.set_float32_matmul_precision(controls["float32_matmul_precision"])
        torch.backends.cudnn.allow_tf32 = controls["cudnn_tf32"]
        torch.use_deterministic_algorithms(controls["deterministic_algorithms"], warn_only=controls["deterministic_warn_only"])
        torch.backends.cudnn.deterministic = controls["cudnn_deterministic"]
        torch.backends.cudnn.benchmark = controls["cudnn_benchmark"]
        yield
    finally:
        torch.set_float32_matmul_precision(previous["float32_matmul_precision"])
        torch.backends.cudnn.allow_tf32 = previous["cudnn_tf32"]
        torch.use_deterministic_algorithms(previous["deterministic_algorithms"], warn_only=previous["deterministic_warn_only"])
        torch.backends.cudnn.deterministic = previous["cudnn_deterministic"]
        torch.backends.cudnn.benchmark = previous["cudnn_benchmark"]
