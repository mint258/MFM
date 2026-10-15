"""Actual H0-forward graph regression evaluation; NOT_FROZEN preparation.

Only explicit training-source inner-validation batches are accepted. Dataset,
split, source and role metadata remain caller declarations, not independent
file/label provenance proofs. No files, supplied predictions, final-test reader,
checkpoint selection or formal metric-record artifacts are provided here.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
import time

import torch
from torch import Tensor
from torch_geometric.data import Data

from ..model.shared import SharedBackboneMFM
from .downstream_readout import SourceAlignedH0Readout, SourceAlignedLinearGraphReadout
from .downstream_training import (
    _tree_hash,
    validate_downstream_batch,
    validate_training_config,
)
from .identity import canonical_hash


EVALUATION_SCHEMA = "phase1_graph_regression_evaluation_v1"
COMPUTATION_RECIPE = "fp32_h0_readout_fp64_affine_errors_observed_label_sums_v1"


class DownstreamEvaluationError(RuntimeError):
    """The explicit evaluation, state-preservation or cooperative budget failed."""


def _require(condition, message):
    if not condition:
        raise DownstreamEvaluationError(message)


def _positive(value, name, *, integer=False):
    _require(type(value) is int if integer else type(value) in (int, float), name + " has an invalid type")
    _require(value > 0 and math.isfinite(value), name + " must be positive finite")


def _sha(value, name):
    _require(type(value) is str and len(value) == 64 and all(c in "0123456789abcdef" for c in value),
             name + " must be a lowercase SHA256")


def _contract(value, config):
    names = {"schema_version", "role", "units", "primary_metric_per_task",
             "dataset_sha256", "split_manifest_sha256", "caps"}
    _require(type(value) is dict and set(value) == names, "Evaluation requires its exact contract fields")
    try:
        result = json.loads(json.dumps(value, allow_nan=False))
    except (ValueError, TypeError, RecursionError) as exc:
        raise DownstreamEvaluationError("Evaluation contract must be finite JSON") from exc
    _require(result["schema_version"] == EVALUATION_SCHEMA, "Unsupported evaluation schema")
    _require(result["role"] == "train_inner_validation", "Only training-source inner validation is supported")
    tasks = set(config["tasks"])
    for name in ("units", "primary_metric_per_task"):
        _require(type(result[name]) is dict and set(result[name]) == tasks, name + " must cover exact task IDs")
    _require(all(type(unit) is str and 0 < len(unit) <= 64 and unit.strip() == unit
                 for unit in result["units"].values()), "Every task requires an explicit bounded unit")
    _require(all(metric in ("MAE", "RMSE") for metric in result["primary_metric_per_task"].values()),
             "Primary metrics must be explicitly MAE or RMSE per task")
    for name in ("dataset_sha256", "split_manifest_sha256"):
        _sha(result[name], name)
    _require(result["split_manifest_sha256"] == config["bindings"]["split_manifest_sha256"],
             "Evaluation must use the declared training/inner split plan")
    caps = result["caps"]
    _require(type(caps) is dict and set(caps) == {"wall_seconds", "max_sequence_batches", "max_unique_samples",
             "max_graphs_per_batch", "max_atoms_per_batch"}, "Evaluation requires exact cooperative caps")
    _positive(caps["wall_seconds"], "wall cap")
    for name in set(caps) - {"wall_seconds"}:
        _positive(caps[name], name, integer=True)
    return result


def _copy_state(module):
    return {name: tensor.detach().clone() if isinstance(tensor, Tensor) else deepcopy(tensor)
            for name, tensor in module.state_dict().items()}


def _state_hash(module):
    return _tree_hash(module.state_dict())


def _backbone_hash(model):
    # The established formal_runtime.backbone_state_hash recipe, not a file SHA.
    digest = hashlib.sha256()
    for name, value in sorted(model.backbone.state_dict().items()):
        _require(isinstance(value, Tensor), "Backbone state must consist of tensors")
        tensor = value.detach().cpu().contiguous()
        digest.update(f"{name}:{tensor.dtype}:{tuple(tensor.shape)}\n".encode())
        digest.update(tensor.reshape(-1).view(torch.uint8).numpy().tobytes())
    return digest.hexdigest()


def _stream_tensor(digest, tensor, *, batch_index, sample_ids, field):
    # Versioned, length-framed, sequence-ordered raw tensor bytes. No predictions
    # or target vectors are retained in the receipt or accumulated in Python.
    header = json.dumps({"batch_index": batch_index, "sample_ids": sample_ids, "field": field,
                         "dtype": str(tensor.dtype), "shape": list(tensor.shape)},
                        sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    blob = tensor.detach().cpu().contiguous().reshape(-1).view(torch.uint8).numpy().tobytes()
    digest.update(len(header).to_bytes(8, "big"))
    digest.update(header)
    digest.update(len(blob).to_bytes(8, "big"))
    digest.update(blob)


def _snapshot(modules):
    states = [_copy_state(module) for module in modules]
    modes = [(submodule, submodule.training) for module in modules for submodule in module.modules()]
    parameters = [(parameter, parameter.requires_grad, parameter.grad,
                   None if parameter.grad is None else parameter.grad.detach().clone())
                  for module in modules for parameter in module.parameters()]
    return states, modes, parameters


def _restore(modules, snapshot):
    states, modes, parameters = snapshot
    with torch.no_grad():
        for module, state in zip(modules, states):
            # Normal eval should not copy identical weights or increment their
            # version counters. A mutated/error path still restores its backup.
            if _state_hash(module) != _tree_hash(state):
                module.load_state_dict(state, strict=True)
        for parameter, requires_grad, original_grad, saved_grad in parameters:
            if parameter.requires_grad != requires_grad:
                parameter.requires_grad_(requires_grad)
            parameter.grad = original_grad
            if original_grad is not None and _tree_hash(original_grad) != _tree_hash(saved_grad):
                original_grad.copy_(saved_grad)
    # Restore heterogeneous child modes without recursive train()/eval().
    for submodule, mode in modes:
        submodule.training = mode


def _check_grads(snapshot):
    for parameter, requires_grad, original_grad, saved_grad in snapshot[2]:
        _require(parameter.requires_grad == requires_grad and parameter.grad is original_grad,
                 "Evaluation altered parameter gradient ownership")
        if original_grad is not None:
            _require(_tree_hash(original_grad) == _tree_hash(saved_grad), "Evaluation altered an existing gradient")


def evaluate_graph_regression(model, readout, config, batches, *, evaluation_contract):
    """Run genuine H0/readout forward and aggregate raw-unit observed-label errors.

    The fixed batch sequence and source IDs are validated, never reordered or
    resampled. The current live weights may be trained; the initial encoder hash
    in config is recorded only as a declaration. Full temporary state/gradient
    copies remain on their existing device and require caller memory budgeting.
    Wall checks are cooperative; the caller must bound RSS/blocking operations.
    """
    started = time.monotonic()
    try:
        configuration = validate_training_config(config)
        devices = [0] if configuration["device"] == "cuda:0" else []
        # Also protect metadata/state hooks and exceptional restoration, rather
        # than protecting only the forward call's RNG consumption.
        with torch.random.fork_rng(devices=devices):
            return _evaluate_graph_regression(model, readout, configuration, batches,
                                               evaluation_contract=evaluation_contract, started=started)
    except DownstreamEvaluationError:
        raise
    except Exception as exc:
        raise DownstreamEvaluationError("Graph regression evaluation failed") from exc


def _evaluate_graph_regression(model, readout, configuration, batches, *, evaluation_contract, started):
    try:
        contract = _contract(evaluation_contract, configuration)
        _require(isinstance(model, SharedBackboneMFM)
                 and isinstance(readout, (SourceAlignedH0Readout, SourceAlignedLinearGraphReadout)),
                 "Actual SharedBackboneMFM and an allowed source-aligned readout are required")
        _require(configuration["loss"] == "mse" and readout.output_level == "graph",
                 "Only graph regression with an explicitly MSE-trained readout is supported")
        _require(readout.config_dict() == configuration["readout_config"]
                 and readout.input_dim == model.latent_dim and readout.output_dim == len(configuration["tasks"]),
                 "Readout architecture/task dimensions differ")
        device = torch.device(configuration["device"])
        modules = (model, readout)
        for module in modules:
            for tensor in list(module.parameters()) + list(module.buffers()):
                _require(tensor.device == device and (not tensor.is_floating_point() or tensor.dtype == torch.float32),
                         "Current model/readout must be FP32 on the single declared device")
                _require(not tensor.is_floating_point() or bool(torch.isfinite(tensor).all()),
                         "Current model/readout state is nonfinite")
        caps = contract["caps"]

        def wall_check():
            _require(time.monotonic() - started < caps["wall_seconds"], "Evaluation cooperative wall budget exhausted")

        wall_check()
        _require(type(batches) in (tuple, list) and 0 < len(batches) <= caps["max_sequence_batches"],
                 "A bounded fixed evaluation batch sequence is required")
        specs, seen = [], set()
        samples = atoms = 0
        mask_digest = hashlib.sha256(b"phase1_evaluation_label_masks_v1\0")
        raw_digest = hashlib.sha256(b"phase1_evaluation_raw_predictions_fp64_v1\0")
        z_digest = hashlib.sha256(b"phase1_evaluation_normalized_predictions_fp32_v1\0")
        for index, item in enumerate(batches):
            wall_check()
            spec = validate_downstream_batch(item, configuration, model,
                                            expected_role="train_inner_validation", require_observed=False)
            _require(spec["samples"] <= caps["max_graphs_per_batch"] and spec["atoms"] <= caps["max_atoms_per_batch"],
                     "Evaluation graph/atom cap exceeded")
            _require(not seen.intersection(item.sample_ids), "Evaluation sample IDs must be globally unique")
            seen.update(item.sample_ids)
            _require(len(seen) <= caps["max_unique_samples"], "Evaluation unique sample cap exceeded")
            specs.append(spec)
            samples += spec["samples"]
            atoms += spec["atoms"]
            for field in ("candidate_mask", "supervision_mask"):
                _stream_tensor(mask_digest, getattr(item, field), batch_index=index,
                               sample_ids=item.sample_ids, field=field)
        sequence_hash = canonical_hash([spec["hash"] for spec in specs])
        membership_hash = canonical_hash({"schema_version": "phase1_evaluation_sample_membership_v1",
                                          "sample_ids": sorted(seen)})
        before = {"model_state_sha256": _state_hash(model), "encoder_state_sha256": _backbone_hash(model),
                  "readout_state_sha256": _state_hash(readout)}
        snapshot = _snapshot(modules)
        snapshot_bytes = sum(value.numel() * value.element_size() for state in snapshot[0]
                             for value in state.values() if isinstance(value, Tensor))
        snapshot_bytes += sum(gradient.numel() * gradient.element_size()
                              for _, _, _, gradient in snapshot[2] if gradient is not None)
        means = torch.tensor(configuration["normalization"]["means"], dtype=torch.float64, device=device)
        scales = torch.tensor(configuration["normalization"]["scales"], dtype=torch.float64, device=device)
        counts = [0] * len(configuration["tasks"])
        absolute_sums, squared_sums = [0.0] * len(counts), [0.0] * len(counts)
        devices = [0] if device.type == "cuda" else []
        completed = False
        try:
            # fork_rng preserves caller CPU and the one declared CUDA device.
            with torch.random.fork_rng(devices=devices):
                model.eval()
                readout.eval()
                with torch.no_grad(), torch.autocast(device_type=device.type, enabled=False):
                    for index, item in enumerate(batches):
                        wall_check()
                        _require(validate_downstream_batch(item, configuration, model,
                                 expected_role="train_inner_validation", require_observed=False) == specs[index],
                                 "Evaluation batch changed after sequence binding")
                        data = item.encoder_batch
                        safe = Data(x=data.x.detach().clone(), pos=data.pos.detach().clone(),
                                    batch=data.batch.detach().clone(), ptr=data.ptr.detach().clone())
                        h0 = model.encode_atoms(safe)
                        output = readout(h0, source_atom_ids=item.source_atom_ids, batch=safe.batch, ptr=safe.ptr)
                        prediction = output.predictions
                        _require(output.output_level == "graph" and output.source_atom_ids is None
                                 and prediction.dtype == torch.float32 and prediction.device == device
                                 and prediction.shape == (specs[index]["samples"], len(counts))
                                 and torch.equal(output.graph_ids, torch.arange(specs[index]["samples"], device=device))
                                 and torch.equal(output.ptr, safe.ptr), "Readout returned a different graph/source contract")
                        _require(bool(torch.isfinite(prediction).all()), "Actual normalized predictions are nonfinite")
                        raw = prediction.to(torch.float64) * scales + means
                        _require(bool(torch.isfinite(raw).all()), "Actual raw-unit predictions are nonfinite")
                        _stream_tensor(z_digest, prediction, batch_index=index, sample_ids=item.sample_ids, field="normalized_z")
                        _stream_tensor(raw_digest, raw, batch_index=index, sample_ids=item.sample_ids, field="raw_units")
                        for task in range(len(counts)):
                            active = item.candidate_mask[:, task] & item.supervision_mask[:, task]
                            n_valid = int(active.sum())
                            counts[task] += n_valid
                            if n_valid:
                                error = raw[active, task] - item.targets[active, task].to(torch.float64)
                                absolute_sums[task] = math.fsum((absolute_sums[task], float(error.abs().sum())))
                                squared_sums[task] = math.fsum((squared_sums[task], float(error.square().sum())))
                        del output, h0, prediction, raw, safe
                        wall_check()
                _require(_state_hash(model) == before["model_state_sha256"]
                         and _state_hash(readout) == before["readout_state_sha256"], "Evaluation mutated current model/readout state")
                _check_grads(snapshot)
                wall_check()
                completed = True
        finally:
            _restore(modules, snapshot)
        after = {"model_state_sha256": _state_hash(model), "encoder_state_sha256": _backbone_hash(model),
                 "readout_state_sha256": _state_hash(readout)}
        _require(completed and before == after, "Evaluation did not complete with preserved current state")
        _check_grads(snapshot)
        wall_check()
        metrics = {}
        for index, task in enumerate(configuration["tasks"]):
            mae = absolute_sums[index] / counts[index] if counts[index] else None
            rmse = math.sqrt(squared_sums[index] / counts[index]) if counts[index] else None
            _require(mae is None or math.isfinite(mae) and math.isfinite(rmse), "Aggregated metric is nonfinite")
            primary = contract["primary_metric_per_task"][task]
            metrics[task] = {"unit": contract["units"][task], "n_valid": counts[index],
                             "MAE": mae, "RMSE": rmse, "status": "OK" if counts[index] else "NO_VALID_LABELS",
                             "primary_metric": primary, "primary_value": mae if primary == "MAE" else rmse}
        status = ("COMPLETE" if all(counts) else "PARTIAL_NO_VALID_LABELS" if any(counts) else "NO_VALID_LABELS")
        receipt = {
            "schema_version": EVALUATION_SCHEMA, "state": "NOT_FROZEN", "formal_eligible": False,
            "status": status, "role": contract["role"], "metrics": metrics,
            "batches": len(batches), "samples": samples, "atoms": atoms,
            "evaluation_contract": contract, "evaluation_contract_sha256": canonical_hash(contract),
            "training_config_sha256": canonical_hash(configuration), "model_config_sha256": canonical_hash(model.config_dict()),
            "readout_config_sha256": canonical_hash(readout.config_dict()),
            "actual_state_before": before, "actual_state_after": after,
            "evaluation_sequence_sha256": sequence_hash, "sample_membership_sha256": membership_hash,
            "label_masks_sha256": mask_digest.hexdigest(), "normalized_prediction_sha256": z_digest.hexdigest(),
            "raw_prediction_sha256": raw_digest.hexdigest(), "computation_recipe": COMPUTATION_RECIPE,
            "caller_declarations": {"evaluation_dataset_sha256": contract["dataset_sha256"],
                "split_manifest_sha256": contract["split_manifest_sha256"], **deepcopy(configuration["bindings"])},
            "source_dataset_role_truth_independently_verified": False,
            "checkpoint_file_sha256_independently_verified": False,
            "resource_limits": {"wall_enforcement": "cooperative", "rss_enforcement": "caller_supervisor_required",
                "temporary_copies": "full model/readout state and existing gradients on their declared device",
                "temporary_snapshot_tensor_bytes": snapshot_bytes,
                "wall_measurement_endpoint": "before receipt hashing; checked again after hashing",
                "prediction_retention": "one bounded batch; hashes and per-task aggregates only"},
        }
        wall_check()
        receipt["wall_seconds"] = time.monotonic() - started
        _require(receipt["wall_seconds"] < caps["wall_seconds"], "Evaluation cooperative wall budget exhausted")
        receipt["receipt_sha256"] = canonical_hash(receipt)
        wall_check()
        return receipt
    except DownstreamEvaluationError:
        raise
    except Exception as exc:
        raise DownstreamEvaluationError("Graph regression evaluation failed") from exc
