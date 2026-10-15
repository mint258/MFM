"""Prepare fresh CPU initialization artifacts; no files or protocol freezing.

Artifacts match the existing formal consumers exactly. The separate proof is
always NOT_FROZEN and cannot establish full fitted-data coverage, authorization
or formal eligibility. No checkpoints, data, labels or prior weights are read.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import math

import torch

from ..factory import build_model
from ..model.normalization import validate_regression_normalization
from ..training.checkpoint import contract_hash
from .formal_runtime import (
    INIT_RECIPE, backbone_state_hash, module_manifest, verify_architecture, verify_paired_initialization,
)


PREPARATION_SCHEMA = "phase1_initialization_preparation_v1"
ARCHITECTURE_BLOCKS = ("architecture", "backbone", "expert", "head")


def _json_values(value):
    """Require JSON-native configuration, avoiding a lossy artifact roundtrip."""
    if type(value) is dict:
        if any(type(key) is not str for key in value):
            raise ValueError("Configuration keys must be JSON strings")
        for item in value.values():
            _json_values(item)
    elif type(value) is list:
        for item in value:
            _json_values(item)
    elif type(value) not in (str, int, float, bool, type(None)):
        raise ValueError("Configuration must contain only JSON-native values")
    elif type(value) is float and not math.isfinite(value):
        raise ValueError("Configuration numbers must be finite")


def _integer(value, name, minimum=1):
    if type(value) is not int or value < minimum:
        raise ValueError(f"{name} must be an explicit integer >= {minimum}")
    return value


def _configuration(config, scope):
    if scope not in ("preparation", "synthetic_test_fixture"):
        raise ValueError("scope must be preparation or synthetic_test_fixture, never formal")
    if not isinstance(config, Mapping):
        raise ValueError("Initialization requires an explicit configuration mapping")
    payload = deepcopy(dict(config))
    _json_values(payload)
    if any(type(payload.get(key)) is not dict for key in (*ARCHITECTURE_BLOCKS, "phase1")):
        raise ValueError("Initialization requires explicit architecture/backbone/expert/head/phase1 blocks")
    architecture, backbone, head, phase1 = (payload[key] for key in ("architecture", "backbone", "head", "phase1"))
    if architecture.get("type") != "shared_multitask" or head.get("profile") != "phase1":
        raise ValueError("Initialization requires the existing Phase 1 shared-H0 model")
    if not architecture.get("preset") and not architecture.get("task_route_per_task"):
        raise ValueError("Architecture must explicitly declare a preset or task routes")
    expected_status = {"synthetic_test_fixture"} if scope == "synthetic_test_fixture" else {"preparation", "formal"}
    if phase1.get("status") not in expected_status or any(name in phase1 for name in (
            "train_limit", "validation_limit", "diagnostic_limit", "train_manifest", "validation_manifest", "max_wall_seconds")):
        raise ValueError("Diagnostic/subset configuration cannot produce formal-compatible initialization artifacts")
    if phase1.get("atom_encoding") != "zero_based" or phase1.get("regression_output_mode") != "train_affine":
        raise ValueError("Initialization requires explicit zero_based encoding and train_affine outputs")
    if head.get("geometry_head") not in ("legacy", "residual"):
        raise ValueError("Existing geometry head must be explicit; no architecture selection is inferred")
    required = {"n_atom_types", "dim", "layers", "heads", "ff_mult", "dropout",
                "use_dist_bias", "use_radius_mask", "radius"}
    if not required.issubset(backbone):
        raise ValueError("Complete actual backbone construction parameters are required")
    _integer(backbone["n_atom_types"], "backbone.n_atom_types", 2)
    for name in ("dim", "layers", "heads", "ff_mult"):
        _integer(backbone[name], "backbone." + name)
    if backbone["dim"] % backbone["heads"]:
        raise ValueError("Backbone dimension must be divisible by its explicit heads")
    for name in ("use_dist_bias", "use_radius_mask"):
        if type(backbone[name]) is not bool:
            raise ValueError("Backbone feature switches must be explicit booleans")
    for name in ("dropout", "radius"):
        value = backbone[name]
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError("Backbone dropout/radius must be finite numeric values")
    if not 0 <= backbone["dropout"] < 1 or backbone["radius"] <= 0:
        raise ValueError("Backbone dropout/radius is outside its supported range")
    for name, minimum in (("real_layers", 0), ("internal_layers", 0), ("heads", 1), ("ff_mult", 1)):
        if name in payload["expert"]:
            _integer(payload["expert"][name], "expert." + name, minimum)
    normalization = validate_regression_normalization(head.get("regression_output_normalization"))
    if normalization["training_provenance"].get("diagnostic_only") is not False:
        raise ValueError("Diagnostic or undeclared normalizer scope cannot prepare formal-compatible initialization")
    return payload, normalization


def prepare_initialization(config, seed, *, scope="preparation"):
    """Return paired_initialization, architecture and a separate preparation proof.

    ``seed`` is the construction seed, independent of a template's per-condition
    training seed. The caller must bind that seed in its eventual execution.
    Only the CPU default generator is seeded: its sequence is identical to the
    formal entry's torch.manual_seed(seed), without touching CUDA generators.
    The caller's CPU RNG state and configuration remain unchanged on failure too.
    """
    _integer(seed, "seed", 0)
    if seed > 2 ** 64 - 1:
        raise ValueError("seed exceeds the PyTorch generator's unsigned 64-bit range")
    if torch.get_default_dtype() != torch.float32 or torch.get_default_device().type != "cpu":
        raise ValueError("CPU float32 defaults are required, as in the formal construction entry")
    payload, normalization = _configuration(config, scope)
    with torch.random.fork_rng(devices=[]):
        torch.random.default_generator.manual_seed(seed)
        model = build_model(payload)
        state = model.state_dict()
        if any(not isinstance(value, torch.Tensor) or value.device.type != "cpu"
               or (value.is_floating_point() and value.dtype != torch.float32) for value in state.values()):
            raise ValueError("Actual initialized model must remain on CPU with standard float32 state")
        paired = {"schema_version": "phase1_paired_init_v1", "seed": seed,
                  "backbone_state_sha256": backbone_state_hash(model), "hash_recipe": INIT_RECIPE}
        architecture = {"schema_version": "phase1_architecture_v1",
                        "config": {key: deepcopy(payload[key]) for key in ARCHITECTURE_BLOCKS},
                        "module_manifest": module_manifest(model)}
        verify_paired_initialization(model, paired, seed)
        verify_architecture(model, payload, architecture)
        proof = {"schema_version": PREPARATION_SCHEMA, "state": "NOT_FROZEN", "formal_eligible": False,
                 "scope": scope, "construction": "fresh_cpu_build_model_no_checkpoint",
                 "construction_seed": seed, "device": "cpu", "floating_dtype": "torch.float32",
                 "rng_policy": "fork_cpu_rng; seed_cpu_default_generator_only; restore_caller_state",
                 "config_sha256": contract_hash(payload), "actual_model_config_sha256": contract_hash(model.config_dict()),
                 "paired_artifact_sha256": contract_hash(paired), "architecture_artifact_sha256": contract_hash(architecture),
                 "affine_contract_sha256": normalization["contract_sha256"],
                 "training_statistics_sha256": normalization["training_statistics_sha256"],
                 "training_provenance_sha256": normalization["provenance_sha256"],
                 "strict_formal_consumer_selfcheck_passed": True,
                 "historical_weights_or_data_read": False,
                 "boundaries": ["Internally validated train-affine contract, not independently verified training pool/fit coverage",
                                "Synthetic scope proves code semantics only; artifacts are not formal experiment evidence",
                                "No final protocol, architecture choice, geometry, data scope or authorization is frozen",
                                "No real artifacts are written; eventual preparation and execution require their own authorized scope"]}
    return {"paired_initialization": paired, "architecture": architecture, "proof": proof}
