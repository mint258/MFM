"""Sample clocks, immutable checkpoints and field-level v3 validation metrics.

These components do not start jobs, select models or read benchmark stores.
The training runner must supply the agreed data adapter and persistent tracker.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path
import random
import resource
import sys
import time

import numpy as np
import torch

from .v3_contract import LabelRegistry, observed_rows, require

DEFAULT_SAMPLE_MILESTONES = (1000000, 2000000, 4000000, 8000000,
                             16000000, 32000000, 64000000)


@dataclass
class SampleClock:
    sample_budget: int
    milestones: tuple[int, ...] = DEFAULT_SAMPLE_MILESTONES
    samples_consumed: int = 0
    optimizer_updates: int = 0
    saved_milestones: list[int] = field(default_factory=list)

    def __post_init__(self):
        require(type(self.sample_budget) is int and self.sample_budget > 0, "Positive sample budget required")
        self.milestones = tuple(self.milestones)
        require(self.milestones == tuple(sorted(set(self.milestones)))
                and all(type(value) is int and value > 0 for value in self.milestones), "Invalid milestones")
        require(type(self.samples_consumed) is int and 0 <= self.samples_consumed <= self.sample_budget
                and type(self.optimizer_updates) is int and self.optimizer_updates >= 0, "Invalid consumed clock")
        require(self.saved_milestones == sorted(set(self.saved_milestones))
                and all(value in self.milestones and value <= self.samples_consumed for value in self.saved_milestones),
                "Invalid saved milestone list")

    def max_next_samples(self, requested):
        require(type(requested) is int and requested > 0, "Positive proposed batch size required")
        next_event = next((value for value in self.milestones if value > self.samples_consumed), self.sample_budget)
        return min(requested, self.sample_budget - self.samples_consumed, next_event - self.samples_consumed)

    def advance(self, count, *, optimizer_updated=True):
        require(type(count) is int and count > 0 and count == self.max_next_samples(count),
                "Consumed batch crosses a checkpoint event or sample budget")
        require(type(optimizer_updated) is bool, "Explicit optimizer-update status required")
        self.samples_consumed += count
        self.optimizer_updates += int(optimizer_updated)

    def state_dict(self):
        return {"schema": "model_v3_consumed_sample_clock_v1", "sample_budget": self.sample_budget,
                "milestones": list(self.milestones), "samples_consumed": self.samples_consumed,
                "optimizer_updates": self.optimizer_updates, "saved_milestones": list(self.saved_milestones)}

    def load_state_dict(self, state):
        require(type(state) is dict and set(state) == set(self.state_dict())
                and state["schema"] == self.state_dict()["schema"]
                and state["sample_budget"] == self.sample_budget
                and state["milestones"] == list(self.milestones), "Sample clock contract differs")
        checked = SampleClock(state["sample_budget"], tuple(state["milestones"]), state["samples_consumed"],
                              state["optimizer_updates"], list(state["saved_milestones"]))
        self.samples_consumed, self.optimizer_updates = checked.samples_consumed, checked.optimizer_updates
        self.saved_milestones = checked.saved_milestones


def commit_consumed_batch(sampler, clock: SampleClock, choices, *, optimizer_updated=True):
    """Validate both clocks first; commit only samples consumed by the caller."""
    choices = tuple(choices)
    require(sampler.samples_consumed == clock.samples_consumed, "Sampler and training clocks disagree")
    require(bool(choices) and len(choices) == clock.max_next_samples(len(choices)), "Batch crosses a sample boundary")
    require(choices == tuple(sampler.choice(clock.samples_consumed + i) for i in range(len(choices))),
            "Consumed draws are not the next committed sequence")
    require(type(optimizer_updated) is bool, "Explicit optimizer-update status required")
    sampler.commit_batch(choices)
    clock.advance(len(choices), optimizer_updated=optimizer_updated)


def _cpu_tree(value):
    if isinstance(value, torch.Tensor):
        return value.detach().cpu().clone()
    if type(value) is dict:
        return {key: _cpu_tree(item) for key, item in value.items()}
    if type(value) is list:
        return [_cpu_tree(item) for item in value]
    if type(value) is tuple:
        return tuple(_cpu_tree(item) for item in value)
    if value is None or type(value) in (str, int, float, bool):
        return value
    raise TypeError(f"Unsafe checkpoint metadata type: {type(value).__name__}")


def capture_rng_state():
    state = np.random.get_state()
    return {"python": random.getstate(),
            "numpy": {"kind": state[0], "keys": [int(value) for value in state[1]],
                      "position": int(state[2]), "has_gauss": int(state[3]), "cached_gauss": float(state[4])},
            "torch_cpu": torch.get_rng_state().clone(),
            "torch_cuda": [value.cpu().clone() for value in torch.cuda.get_rng_state_all()]
                          if torch.cuda.is_initialized() else None}


def restore_rng_state(state):
    random.setstate(state["python"])
    value = state["numpy"]
    np.random.set_state((value["kind"], np.asarray(value["keys"], dtype=np.uint32),
                         value["position"], value["has_gauss"], value["cached_gauss"]))
    torch.set_rng_state(state["torch_cpu"])
    if state["torch_cuda"] is not None:
        require(torch.cuda.is_available() and torch.cuda.device_count() == len(state["torch_cuda"]),
                "CUDA RNG device count differs")
        torch.cuda.set_rng_state_all(state["torch_cuda"])


def _runtime_contract():
    return {"torch_version": str(torch.__version__), "python_version": sys.version.split()[0],
            "num_threads": torch.get_num_threads(), "default_dtype": str(torch.get_default_dtype()),
            "deterministic_algorithms": torch.are_deterministic_algorithms_enabled(),
            "float32_matmul_precision": torch.get_float32_matmul_precision(),
            "cuda_version": torch.version.cuda,
            "cuda_rng_devices": torch.cuda.device_count() if torch.cuda.is_initialized() else 0}


def _file_sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _check_output_path(directory, output_root):
    directory, root = Path(directory).absolute(), Path(output_root).absolute()
    require(root.is_dir() and not root.is_symlink() and directory != root
            and directory.is_relative_to(root), "Checkpoint must be inside the explicit output root")
    require(directory.resolve(strict=False).is_relative_to(root.resolve(strict=True)), "Checkpoint path escapes output root")
    current = directory
    while current != root:
        require(not current.is_symlink(), "Checkpoint ancestry may not contain symlinks")
        current = current.parent
    return directory


def _bindings(value):
    required = ("code_sha", "configuration_sha256", "registry_sha256", "normalization_sha256", "data_version")
    require(type(value) is dict and set(required) <= set(value), "Explicit source/config/registry/stats/data bindings required")
    require(all(type(value[key]) is str and bool(value[key]) for key in required), "String bindings required")
    for key, length in (("code_sha", 40), ("configuration_sha256", 64), ("registry_sha256", 64), ("normalization_sha256", 64)):
        require(len(value[key]) == length and all(c in "0123456789abcdef" for c in value[key]), "Invalid source binding digest")
    json.dumps(value, allow_nan=False)
    return value


def save_new_checkpoint(directory, *, output_root, model, optimizer, sampler, clock: SampleClock,
                        bindings, extra_state=None):
    """Write a new immutable directory and publish COMPLETE.json last.

    Existing paths are never overwritten or deleted. Partial directories remain
    evidence and are rejected by the reader. The caller chooses a fresh run/job
    path for recovery checkpoints. A complete marker binds every payload byte.
    """
    directory = _check_output_path(directory, output_root)
    _bindings(bindings)
    require(sampler.samples_consumed == clock.samples_consumed, "Cannot save uncommitted sample clocks")
    state = clock.state_dict()
    if clock.samples_consumed in clock.milestones and clock.samples_consumed not in clock.saved_milestones:
        state["saved_milestones"] = sorted([*clock.saved_milestones, clock.samples_consumed])
    payload = {"schema": "model_v3_training_checkpoint_v1", "bindings": dict(bindings),
               "runtime": _runtime_contract(), "model": _cpu_tree(dict(model.state_dict())),
               "optimizer": _cpu_tree(optimizer.state_dict()), "sampler": sampler.state_dict(),
               "clock": state, "rng": capture_rng_state(), "extra_state": _cpu_tree(extra_state)}
    directory.mkdir(parents=True, exist_ok=False)
    path = directory / "payload.pt"
    with path.open("xb") as stream:
        torch.save(payload, stream)
        stream.flush(); os.fsync(stream.fileno())
    checked = torch.load(path, map_location="cpu", weights_only=True)
    require(checked["bindings"] == bindings and checked["clock"] == state
            and checked["sampler"] == payload["sampler"], "Safe checkpoint readback differs")
    complete = {"schema": payload["schema"], "payload_bytes": path.stat().st_size,
                "payload_sha256": _file_sha(path), "bindings": dict(bindings),
                "samples_consumed": clock.samples_consumed, "optimizer_updates": clock.optimizer_updates}
    raw = (json.dumps(complete, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
    with (directory / "COMPLETE.json").open("xb") as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    clock.saved_milestones = state["saved_milestones"]
    return complete


def load_checkpoint(directory, *, output_root, model, optimizer, sampler, clock: SampleClock, expected_bindings):
    directory = _check_output_path(directory, output_root)
    _bindings(expected_bindings)
    marker, path = directory / "COMPLETE.json", directory / "payload.pt"
    require(marker.is_file() and path.is_file() and not marker.is_symlink() and not path.is_symlink(),
            "Incomplete or unsafe checkpoint directory")
    complete = json.loads(marker.read_text(encoding="utf-8"))
    require(complete["bindings"] == expected_bindings and complete["payload_bytes"] == path.stat().st_size
            and complete["payload_sha256"] == _file_sha(path), "Checkpoint binding/payload digest differs")
    payload = torch.load(path, map_location="cpu", weights_only=True)
    require(payload["schema"] == "model_v3_training_checkpoint_v1" and payload["bindings"] == expected_bindings
            and payload["runtime"] == _runtime_contract(), "Checkpoint source or runtime contract differs")
    require(payload["sampler"]["samples_consumed"] == payload["clock"]["samples_consumed"]
            == complete["samples_consumed"] and payload["clock"]["optimizer_updates"] == complete["optimizer_updates"],
            "Checkpoint consumed/optimizer cursors differ")
    require(payload["sampler"]["contract_sha256"] == sampler.content_sha256,
            "Checkpoint sampler contract differs")
    # Validate the entire clock before mutating model/optimizer state.
    preview = SampleClock(clock.sample_budget, clock.milestones)
    preview.load_state_dict(payload["clock"])
    model.load_state_dict(payload["model"], strict=True)
    optimizer.load_state_dict(payload["optimizer"])
    sampler.load_state_dict(payload["sampler"])
    clock.load_state_dict(payload["clock"])
    restore_rng_state(payload["rng"])
    return payload["extra_state"]


def shared_backbone_gradient_norms(group_losses, parameters, *, optimizer_update, interval=500):
    require(type(optimizer_update) is int and optimizer_update > 0 and type(interval) is int and interval > 0,
            "Positive optimizer update/probe interval required")
    if optimizer_update % interval:
        return {}
    parameters = tuple(parameter for parameter in parameters if parameter.requires_grad)
    result = {}
    for group, value in group_losses.items():
        if not value.requires_grad or not parameters:
            result[group] = 0.
            continue
        gradients = torch.autograd.grad(value, parameters, retain_graph=True, allow_unused=True)
        norm2 = sum(float(gradient.detach().double().square().sum())
                    for gradient in gradients if gradient is not None)
        result[group] = norm2 ** .5
    return result


class ValidationAccumulator:
    """Separate raw-unit field metrics for the two authorized validation roles."""
    _TENSOR6_WEIGHTS = (1., 2., 1., 2., 2., 1.)  # xx,xy,yy,xz,yz,zz

    def __init__(self, registry: LabelRegistry, *, role, enabled_groups, enabled_fields=None):
        require(role in ("VAL", "TRAIN_UNSEEN_CONFORMATION"), "Explicit v3 validation role required")
        self.registry, self.role = registry, role
        self.fields = registry.enabled(enabled_groups, enabled_fields)
        self.rows = {field.name: {"count": 0, "loss_sum": 0., "absolute": 0., "squared": 0.,
                                  "target_sum": [0.] * field.target_width,
                                  "target_squared": 0., "correct": 0} for field in self.fields}
        for field in self.fields:
            if field.representation == "symmetric_tensor6":
                self.rows[field.name].update(frobenius_squared=0., frobenius_target_squared=0.,
                                             frobenius_absolute_d9=0.)

    def add(self, predictions, targets, loss_result):
        for field in self.fields:
            if field.name in predictions:
                prediction, target, count = observed_rows(field, predictions[field.name], targets[field.name])
            else:
                from .v3_losses import source_observed_rows
                require(loss_result.loss_counts[field.name] == 0 and loss_result.loss_status.get(field.name) in (
                    "LOSS_DISABLED_SCALE_UNBOUND_OR_DEGENERATE", "LOSS_DISABLED_PHYSICAL_POLICY_UNBOUND"),
                    "Validation cannot omit a ready prediction")
                target, count = source_observed_rows(field, targets[field.name])
                prediction = None
            require(loss_result.counts[field.name] == count, "Validation loss/metric population differs")
            row = self.rows[field.name]
            require(row.get("prediction_available", prediction is not None) == (prediction is not None),
                    "Prediction availability changed within a fixed validation population")
            if prediction is None: row["prediction_available"] = False
            if loss_result.has_loss_readiness:
                effective = loss_result.loss_counts[field.name]
                require(type(effective) is int and 0 <= effective <= count, "Validation source/loss population differs")
                disabled = loss_result.loss_status[field.name] in ("LOSS_DISABLED_SCALE_UNBOUND_OR_DEGENERATE", "LOSS_DISABLED_PHYSICAL_POLICY_UNBOUND")
                require("loss_disabled" not in row or row["loss_disabled"] == disabled,
                        "Target readiness changed within a fixed validation population")
                row["loss_disabled"] = disabled
                row["loss_count"] = row.get("loss_count", 0) + effective
                row["loss_status"] = loss_result.loss_status[field.name]
                if loss_result.physical_policy_sha256 is not None:
                    row["physical_status"] = loss_result.physical_status[field.name]
                    row["scale_status"] = loss_result.scale_status[field.name]
                    row["physical_policy_sha256"] = loss_result.physical_policy_sha256
                    if field.name in loss_result.scale_reasons:
                        row["scale_disabled_reason"] = loss_result.scale_reasons[field.name]
                if field.name in loss_result.loss_reasons: row["loss_disabled_reason"] = loss_result.loss_reasons[field.name]
            if not count:
                continue
            row["count"] += count
            effective = loss_result.loss_counts[field.name]
            if effective: row["loss_sum"] += effective * float(loss_result.fields[field.name].detach())
            if prediction is None: continue
            prediction, target = prediction.detach().double(), target.detach().double()
            if field.kind in ("binary", "classification"):
                label = prediction.argmax(-1) if field.kind == "classification" else (prediction[:, 0] >= 0).long()
                row["correct"] += int((label == target[:, 0].long()).sum())
            else:
                error = prediction - target
                row["absolute"] += float(error.abs().sum())
                row["squared"] += float(error.square().sum())
                row["target_squared"] += float(target.square().sum())
                row["target_sum"] = [old + new for old, new in zip(row["target_sum"], target.sum(0).cpu().tolist())]
                if field.representation == "symmetric_tensor6":
                    # Keep native-six absolute/component SSE statistics for
                    # existing source-component MAE/RMSE consumers. Tensor R2
                    # uses independent Frobenius SSE/SST; one row is one
                    # eligible complete tensor, never six separate targets.
                    weights = error.new_tensor(self._TENSOR6_WEIGHTS)
                    squared_frobenius = (error.square() * weights).sum(-1)
                    row["frobenius_squared"] += float(squared_frobenius.sum())
                    row["frobenius_target_squared"] += float((target.square() * weights).sum())
                    row["frobenius_absolute_d9"] += float((squared_frobenius / 9.).sqrt().sum())

    def result(self):
        metrics = {}
        for field in self.fields:
            row, count = self.rows[field.name], self.rows[field.name]["count"]
            item = {"valid_labels": count, "loss": row["loss_sum"] / count if count else None,
                    "MAE": None, "R2": None, "accuracy": None}
            if "loss_count" in row:
                item["loss_count"] = row["loss_count"]
                item["loss"] = row["loss_sum"] / row["loss_count"] if row["loss_count"] else None
                item["loss_status"] = (row["loss_status"] if row["loss_disabled"] else
                                       "READY" if row["loss_count"] else "NO_VALID_LABELS")
                if "loss_disabled_reason" in row: item["loss_disabled_reason"] = row["loss_disabled_reason"]
                for key in ("physical_status", "scale_status", "scale_disabled_reason", "physical_policy_sha256"):
                    if key in row: item[key] = row[key]
            tensor6 = field.representation == "symmetric_tensor6"
            if tensor6:
                item.update(Frobenius_MAE_d9=None, Frobenius_SSE=None, Frobenius_SST=None,
                    valid_labels_definition="eligible_complete_same_actual_geometry_tensors",
                    MAE_definition="mean_i,j(abs(Qhat_ij-Q_ij)); source6=(xx,xy,yy,xz,yz,zz)",
                    Frobenius_MAE_d9_definition="mean_i(sqrt(sum_j(w_j*(Qhat_ij-Q_ij)^2)/9)); raw_unit; w=(1,2,1,2,2,1)",
                    R2_definition="1-sum_i||Qhat_i-Q_i||_F^2/sum_i||Q_i-mean(Q)||_F^2; w=(1,2,1,2,2,1)")
            if row.get("prediction_available") is False:
                item["prediction_status"] = "LOSS_DISABLED_NO_PREDICTION"
                item["R2_unavailable_reason"] = "prediction_not_computed_for_loss_disabled_target"
                metrics[field.name] = item
                continue
            if field.kind in ("binary", "classification"):
                item["accuracy"] = row["correct"] / count if count else None
                item["R2_unavailable_reason"] = "categorical_field"
            elif count:
                item["MAE"] = row["absolute"] / (count * field.target_width)
                if tensor6:
                    variance = row["frobenius_target_squared"] - sum(weight * value ** 2
                        for weight, value in zip(self._TENSOR6_WEIGHTS, row["target_sum"])) / count
                    squared = row["frobenius_squared"]
                    item.update(Frobenius_MAE_d9=row["frobenius_absolute_d9"] / count,
                                Frobenius_SSE=squared, Frobenius_SST=variance)
                else:
                    variance = row["target_squared"] - sum(value ** 2 for value in row["target_sum"]) / count
                    squared = row["squared"]
                if count > 1 and variance > 0:
                    item["R2"] = 1. - squared / variance
                else:
                    item["R2_unavailable_reason"] = "insufficient_or_constant_labels"
            metrics[field.name] = item
        return {"role": self.role, "fields": metrics}


def runtime_metrics(*, samples, started, step_started=None):
    elapsed = time.perf_counter() - started
    require(type(samples) is int and samples >= 0 and elapsed > 0, "Valid consumed/time counters required")
    result = {"samples_consumed": samples, "elapsed_seconds": elapsed,
              "samples_per_second": samples / elapsed,
              "process_peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
              "gpu_peak_allocated_bytes": None, "gpu_peak_reserved_bytes": None}
    if step_started is not None:
        result["step_seconds"] = time.perf_counter() - step_started
    if torch.cuda.is_initialized():
        result["gpu_peak_allocated_bytes"] = torch.cuda.max_memory_allocated()
        result["gpu_peak_reserved_bytes"] = torch.cuda.max_memory_reserved()
    return result
