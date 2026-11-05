"""Strict checkpoint/configuration bridges for source-aligned H0 evaluation.

Only known source checkpoint schemas are accepted. No unsafe pickle fallback,
implicit floating dtype conversion, downstream records or targets are used.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
from copy import deepcopy

from .v3_dev_panel import canonical, encoder_state_sha256
from .v3_dev_store import bound_json
from .v3_h0_runtime import physical_source_binding


class EncoderBindingError(ValueError):
    pass


def source_model_configuration(configuration):
    """Separate model identity from a flat training recipe and its seed."""
    if "model" in configuration:
        return deepcopy(configuration["model"])
    if "backbone" not in configuration or "architecture" not in configuration:
        raise EncoderBindingError("An explicit source model configuration is required")
    return {key: deepcopy(configuration.get(key, {}))
            for key in ("architecture", "backbone", "expert", "head")}


@dataclass(frozen=True)
class EncoderPair:
    candidate: object
    random_reference: object
    model_configuration: dict
    provenance: dict


def _raw(ref, *, maximum=2*1024**3):
    path = Path(ref["path"])
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= maximum:
        raise EncoderBindingError("An ordinary bounded checkpoint/configuration source is required")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != ref["sha256"] or ("bytes" in ref and len(raw) != ref["bytes"]):
        raise EncoderBindingError("Source file bytes differ from their immutable reference")
    return raw


def _strict_state(model, state):
    import torch
    expected = model.state_dict()
    if not isinstance(state, dict) or set(state) != set(expected):
        raise EncoderBindingError("Checkpoint model-state keys differ")
    for key, value in expected.items():
        actual = state[key]
        if isinstance(value, torch.Tensor):
            if (not isinstance(actual, torch.Tensor) or actual.dtype != value.dtype or actual.shape != value.shape
                    or (actual.is_floating_point() and not bool(torch.isfinite(actual).all()))):
                raise EncoderBindingError("Checkpoint tensor shape/dtype/finiteness differs: "+key)
        elif actual != value:
            raise EncoderBindingError("Checkpoint extra-state contract differs: "+key)
    model.load_state_dict(state, strict=True)


def _historical_builder(configuration, checkpoint_ref, reference_ref):
    if reference_ref is None:
        raise EncoderBindingError("Historical B3 requires its frozen physical reference metadata, not a kind string")
    reference = bound_json(reference_ref["path"], reference_ref["sha256"])
    if reference.get("schema") != "model_v3_historical_b3_reference_v1":
        raise EncoderBindingError("An explicit historical B3 reference is required")
    if (reference["configuration"]["sha256"] != configuration["sha256"]
            or reference["checkpoint"]["sha256"] != checkpoint_ref["sha256"]):
        raise EncoderBindingError("Historical checkpoint/configuration do not match the frozen physical reference")
    receipt_ref = reference["source_receipt"]
    root = Path(__file__).absolute().parents[3]
    receipt_path = Path(receipt_ref["path"])
    if not receipt_path.is_absolute():
        receipt_path = root / receipt_path
    receipt = bound_json(receipt_path, receipt_ref["sha256"])
    for key in ("path", "sha256", "bytes"):
        if receipt[key] != reference["checkpoint"][key]:
            raise EncoderBindingError("Historical checkpoint receipt and immutable reference differ")
    if any(receipt[key] != reference["observed_cursors"][key]
           for key in ("consumed_records", "optimizer_updates", "label")):
        raise EncoderBindingError("Historical checkpoint receipt cursor differs")
    implementation = reference["memory_implementation"]
    # The metadata may identify the old source, but cannot choose arbitrary
    # executable code. Load only this repository's known frozen helper.
    source = physical_source_binding(root / "workflows/sprime_s/scripts/s_model_memory_v1.py")
    if source["sha256"] != implementation["sha256"]:
        raise EncoderBindingError("Frozen historical row-tiling implementation differs")
    name = "model_v3_historical_memory_"+source["sha256"][:16]+"_"+canonical(source["path"])[:8]
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, source["path"])
        module = importlib.util.module_from_spec(spec); sys.modules[name] = module
        spec.loader.exec_module(module)
    module = sys.modules[name]
    def builder(config):
        return module.build_memory_bounded_model(config, pair_rows=implementation["pair_rows"])
    return builder, reference


def load_encoder_pair(checkpoint_ref, configuration_ref, *, architecture_sha256,
                      pretraining_seed, reference_kind="primary", random_seed=20261025,
                      historical_reference=None, expected_state_key=None):
    import torch
    from phychem_mfm.factory import build_model
    config_raw = _raw(configuration_ref, maximum=2*1024**2)
    configuration = bound_json(configuration_ref["path"], configuration_ref["sha256"])
    model_config = source_model_configuration(configuration)
    if canonical(model_config) != architecture_sha256:
        raise EncoderBindingError("Model architecture differs from its pinned configuration")
    if type(pretraining_seed) is not int or pretraining_seed < 0 or type(random_seed) is not int:
        raise EncoderBindingError("Explicit actual and random-reference seeds required")
    if reference_kind == "primary":
        if (model_config["backbone"]["dim"], model_config["backbone"]["layers"]) != (512, 6):
            raise EncoderBindingError("Primary v3 H0 requires the exact declared 512x6 architecture")
        builder, historical = build_model, None
    elif reference_kind == "historical_sanity_only":
        builder, historical = _historical_builder(configuration_ref, checkpoint_ref, historical_reference)
        if ((model_config["backbone"]["dim"], model_config["backbone"]["layers"]) != (384, 4)
                or configuration.get("kind") != "B3" or configuration.get("variant") != "S"
                or configuration.get("epochs") != 3):
            raise EncoderBindingError("The frozen historical reference is specifically the source S B3 384x4 model")
    else:
        raise EncoderBindingError("Unknown checkpoint/reference scope")
    raw = _raw(checkpoint_ref)
    # Hash and deserialize the same immutable bytes, rather than reopening a
    # path between checksum and load. Keep the safe weights-only boundary.
    try:
        payload = torch.load(io.BytesIO(raw), map_location="cpu", weights_only=True)
    except Exception as exc:
        raise EncoderBindingError("Checkpoint cannot be loaded through the safe weights-only path") from exc
    del raw
    if not isinstance(payload, dict):
        raise EncoderBindingError("Known dictionary checkpoint schema required")
    if payload.get("scientific_stop") is True:
        raise EncoderBindingError("A scientifically stopped checkpoint cannot silently enter the development panel")
    if "model" in payload and "config_sha256" in payload:
        schema, state_key = "source_S_runner_raw_configuration_sha", "model"
        if payload["config_sha256"] != hashlib.sha256(config_raw).hexdigest():
            raise EncoderBindingError("S checkpoint original configuration SHA differs, even if tensor shapes match")
        actual_seed = configuration.get("seed")
        if ("memory_implementation_sha256" in payload
                and payload["memory_implementation_sha256"] != configuration.get("memory_implementation_sha256")):
            raise EncoderBindingError("S checkpoint memory implementation binding differs")
    elif "model_state" in payload and "model_config" in payload and "config" in payload and "config_sha256" in payload:
        from .formal_gate import canonical_sha256
        from .downstream_training import checkpoint_content_sha256
        schema, state_key = "source_full_corpus_typed_checkpoint", "model_state"
        if (payload.get("schema_version") != "phase1_full_corpus_checkpoint_v1"
                or payload["config_sha256"] != canonical_sha256(payload["config"])
                or payload.get("checkpoint_content_sha256") != checkpoint_content_sha256(payload)
                or payload.get("status") not in {"partial", "complete"}):
            raise EncoderBindingError("Full-corpus configuration or typed checkpoint seal differs")
        actual_seed = payload["config"].get("seed")
    elif "model_state" in payload and "model_config" in payload and payload.get("format_version") == 1:
        from ..training.checkpoint import semantic_config, contract_hash
        schema, state_key = "source_training_checkpoint_v1", "model_state"
        saved_semantics = payload.get("semantic_config")
        if (not isinstance(saved_semantics, dict)
                or payload.get("semantic_config_sha256") != contract_hash(saved_semantics)
                or source_model_configuration(saved_semantics) != model_config):
            raise EncoderBindingError("Generic checkpoint semantic configuration differs")
        if ("model" not in configuration and any(key in configuration for key in (
                "supervision", "loss", "schedule", "optimizer", "training", "phase1"))
                and saved_semantics != semantic_config(configuration)):
            raise EncoderBindingError("Provided full training recipe differs from checkpoint semantics")
        actual_seed = payload.get("seed")
    else:
        raise EncoderBindingError("Unsupported checkpoint schema; no permissive state-dict fallback is allowed")
    if actual_seed != pretraining_seed or (expected_state_key is not None and state_key != expected_state_key):
        raise EncoderBindingError("Checkpoint pretraining seed or state-key schema differs")
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(pretraining_seed)
        candidate = builder(model_config)
    if "model_config" in payload and payload["model_config"] != candidate.config_dict():
        raise EncoderBindingError("Checkpoint model configuration differs, including same-shape semantic options")
    if historical is not None:
        expected_records = configuration["train_records"]*configuration["epochs"]
        if (schema != "source_S_runner_raw_configuration_sha" or payload.get("development_only") is not False
                or payload.get("scientific_stop") is not False or payload.get("consumed_records") != expected_records
                or payload.get("consumed_records") != historical["observed_cursors"]["consumed_records"]
                or payload.get("optimizer_updates") != historical["observed_cursors"]["optimizer_updates"]
                or payload.get("memory_implementation_sha256") != historical["memory_implementation"]["sha256"]):
            raise EncoderBindingError("Historical source B3 completion/source cursor cannot be established")
    _strict_state(candidate, payload[state_key])
    source_checkpoint_status = payload.get("status", payload.get("checkpoint_type", "source_S_committed_snapshot"))
    del payload
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(random_seed)
        reference = builder(model_config)
    candidate.eval(); reference.eval()
    if candidate.config_dict() != reference.config_dict():
        raise EncoderBindingError("Candidate/random encoder configurations differ")
    if {id(p) for p in candidate.parameters()} & {id(p) for p in reference.parameters()}:
        raise EncoderBindingError("Candidate/random parameters must be independently owned")
    metadata = {"schema": "model_v3_bound_encoder_pair_v1", "checkpoint_schema": schema,
        "checkpoint": dict(checkpoint_ref), "original_configuration": dict(configuration_ref),
        "architecture_sha256": architecture_sha256, "pretraining_seed": pretraining_seed,
        "random_reference_seed": random_seed, "reference_kind": reference_kind,
        "source_checkpoint_status": source_checkpoint_status,
        "H0_dimension": candidate.latent_dim, "checkpoint_encoder_state_sha256": encoder_state_sha256(candidate),
        "random_encoder_state_sha256": encoder_state_sha256(reference),
        "loader_implementation": physical_source_binding(__file__),
        "historical_reference": dict(historical_reference) if historical_reference else None,
        "historical_memory_implementation": historical["memory_implementation"] if historical else None,
        "downstream_target_records_read": 0}
    return EncoderPair(candidate, reference, model_config, metadata)
