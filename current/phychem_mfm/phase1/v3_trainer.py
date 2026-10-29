"""Bound-adapter v3 step training; no physical D-1 schema is inferred here.

Real runners supply a verified read-only node-local provider and persistent
W&B run. Synthetic tests exercise the protocol only, not tracking durability.
"""
from __future__ import annotations

from contextlib import contextmanager, nullcontext
from copy import deepcopy
from dataclasses import asdict, dataclass, field
import hashlib
import json
import math
from pathlib import Path
import time
from typing import Mapping

import torch
from torch import Tensor
from torch_geometric.utils import to_dense_batch

from ..model.v3_multiview import V3MultiViewModel
from .v3_contract import FieldTarget, canonical_hash, observed_rows, require, selected_groups
from .v3_structural import StructuralViewConfig, _masked_for_role
from .v3_training import (SampleClock, ValidationAccumulator, _bindings, _check_output_path, _file_sha,
    capture_rng_state, commit_consumed_batch, load_checkpoint, restore_rng_state,
    runtime_metrics, save_new_checkpoint, shared_backbone_gradient_norms)


@dataclass(frozen=True)
class PreparedV3Batch:
    """Provider-supplied typed projection, bound independently of storage layout."""
    choices: tuple
    views: object
    pd_targets: Mapping[str, FieldTarget]
    adapter_sha256: str
    data_version: str
    role: str = "TRAIN"
    pair_indices: Mapping[str, Tensor] = field(default_factory=dict)
    prediction_offsets: Mapping[str, Tensor] = field(default_factory=dict)
    atom_eligibility: Mapping[str, Tensor] = field(default_factory=dict)
    bond_pair_eligibility: Tensor | None = None
    domain_inputs: Mapping[str, object] = field(default_factory=dict)
    geometry_context: Mapping[str, object] = field(default_factory=dict)

    def to(self, device):
        from .v3_data import _target_to
        return PreparedV3Batch(tuple(self.choices), self.views.to(device, non_blocking=True),
            {name: _target_to(value, device, non_blocking=True)
             for name, value in self.pd_targets.items()}, self.adapter_sha256, self.data_version, self.role,
            {name: value.to(device, non_blocking=True) for name, value in self.pair_indices.items()},
            {name: value.to(device, non_blocking=True) for name, value in self.prediction_offsets.items()},
            {name: value.to(device, non_blocking=True) for name, value in self.atom_eligibility.items()},
            None if self.bond_pair_eligibility is None else self.bond_pair_eligibility.to(device, non_blocking=True),
            {name: value.to(device, non_blocking=True) for name, value in self.domain_inputs.items()},
            self.geometry_context)


class SampleLRScheduler:
    """Serializable learning-rate clock driven by consumed base samples."""
    def __init__(self, optimizer, *, sample_budget, warmup_samples=0, mode="cosine",
                 decay_start_samples=None, minimum_ratio=0.):
        require(type(sample_budget) is int and sample_budget > 0
                and type(warmup_samples) is int and 0 <= warmup_samples < sample_budget,
                "Invalid sample scheduler budget/warmup")
        require(mode in ("cosine", "wsd") and 0 <= minimum_ratio <= 1, "Invalid sample scheduler mode/floor")
        if mode == "wsd":
            require(type(decay_start_samples) is int and warmup_samples <= decay_start_samples < sample_budget,
                    "WSD needs a fixed declared decay boundary")
        else:
            require(decay_start_samples is None, "Cosine does not accept a WSD boundary")
        self.optimizer = optimizer
        self.contract = {"schema": "model_v3_sample_lr_v1", "sample_budget": sample_budget,
                         "warmup_samples": warmup_samples, "mode": mode,
                         "decay_start_samples": decay_start_samples, "minimum_ratio": float(minimum_ratio),
                         "base_lrs": [float(group["lr"]) for group in optimizer.param_groups]}
        self.binding_sha256 = canonical_hash(self.contract)
        self.samples_consumed = 0
        self.set_consumed(0)

    def set_consumed(self, count):
        require(type(count) is int and 0 <= count <= self.contract["sample_budget"], "Scheduler sample cursor differs")
        warmup, budget = self.contract["warmup_samples"], self.contract["sample_budget"]
        if warmup and count < warmup:
            ratio = count / warmup
        elif self.contract["mode"] == "wsd" and count < self.contract["decay_start_samples"]:
            ratio = 1.
        else:
            begin = warmup if self.contract["mode"] == "cosine" else self.contract["decay_start_samples"]
            progress = (count - begin) / (budget - begin)
            ratio = self.contract["minimum_ratio"] + (1 - self.contract["minimum_ratio"]) * .5 * (1 + math.cos(math.pi * progress))
        for group, base in zip(self.optimizer.param_groups, self.contract["base_lrs"]):
            group["lr"] = base * ratio
        self.samples_consumed = count

    def state_dict(self):
        return {"contract": deepcopy(self.contract), "binding_sha256": self.binding_sha256,
                "samples_consumed": self.samples_consumed}

    def load_state_dict(self, state):
        require(state["contract"] == self.contract and state["binding_sha256"] == self.binding_sha256,
                "Sample scheduler configuration changed")
        self.set_consumed(state["samples_consumed"])


@contextmanager
def _preserve_rng():
    state = capture_rng_state()
    try:
        yield
    finally:
        restore_rng_state(state)


def _tracker(tracker, allow_unit_tracker):
    mode = getattr(getattr(tracker, "settings", None), "mode", None)
    require(mode in ("offline", "online") and not getattr(tracker, "disabled", False)
            and type(getattr(tracker, "id", None)) is str and bool(tracker.id)
            and type(getattr(tracker, "path", None)) is str and bool(tracker.path), "Active identified tracker required")
    log = getattr(tracker, "log", None)
    require(callable(log) and getattr(log, "__self__", None) is tracker, "Bound tracker.log required")
    require(type(getattr(tracker, "step", None)) is int and tracker.step >= 0, "Explicit tracker history cursor required")
    unit = getattr(tracker, "model_v3_unit_test_tracker", False)
    require(not unit or allow_unit_tracker, "Unit tracker cannot be used as a persistent-run substitute")
    return {"id": tracker.id, "path": tracker.path, "mode": mode,
            "unit_protocol_only": bool(unit), "durability_verified_by_this_library": False}


def _execution_state(model):
    options, flags = {}, {}
    for name, module in model.named_modules():
        if hasattr(module, "v3_performance_options"):
            options[name] = deepcopy(module.v3_performance_options)
        selected = {key: value for key, value in vars(module).items()
                    if type(value) is bool and (key.endswith("checkpointing") or key in ("checkpoint_pairs", "use_checkpoint"))}
        if selected:
            flags[name] = selected
    state = {"performance_options": options, "resolved_checkpoint_flags": flags,
             "float32_matmul_precision": torch.get_float32_matmul_precision(),
             "matmul_tf32": bool(torch.backends.cuda.matmul.allow_tf32),
             "cudnn_tf32": bool(torch.backends.cudnn.allow_tf32),
             "deterministic_algorithms": torch.are_deterministic_algorithms_enabled()}
    integration = {name: deepcopy(module.performance_execution_contract)
                   for name, module in model.named_modules() if hasattr(module, "performance_execution_contract")}
    if integration:state["performance_integration"] = integration
    if hasattr(model, "training_execution_contract"):
        from .v3_training_execution import validate_training_execution_contract
        state["training_execution"] = validate_training_execution_contract(model.training_execution_contract)
    json.dumps(state, allow_nan=False)
    return state


def _restore_execution(model, state):
    current = _execution_state(model)
    require(current.get("training_execution") == state.get("training_execution"),
            "Training execution contract changed before any restore mutation")
    if "training_execution" in current:
        from .v3_training_execution import validate_training_execution_state
        validate_training_execution_state(current["training_execution"], current)
        validate_training_execution_state(current["training_execution"], state)
    require(current.get("performance_integration", {}) == state.get("performance_integration", {}),
            "Logical-batch/profile execution contract changed before resume")
    require(current["performance_options"] == state["performance_options"],
            "Performance options changed; construct the same bound implementation before resume")
    require({name: set(flags) for name, flags in current["resolved_checkpoint_flags"].items()}
            == {name: set(flags) for name, flags in state["resolved_checkpoint_flags"].items()},
            "Resolved checkpoint module layout differs")
    for name, flags in state["resolved_checkpoint_flags"].items():
        module = model.get_submodule(name) if name else model
        for key, value in flags.items():
            require(type(value) is bool, "Resolved checkpoint flags must be booleans")
            setattr(module, key, value)
    torch.set_float32_matmul_precision(state["float32_matmul_precision"])
    torch.backends.cuda.matmul.allow_tf32 = state["matmul_tf32"]
    torch.backends.cudnn.allow_tf32 = state["cudnn_tf32"]
    torch.use_deterministic_algorithms(state["deterministic_algorithms"])


class V3StepTrainer:
    """One bound sample stream, one model/optimizer, one explicit tracker lineage."""
    def __init__(self, model: V3MultiViewModel, optimizer, scheduler, sampler, clock: SampleClock,
                 provider, normalizations, weights, tracker, bindings, *, enabled_groups,
                 enabled_fields=None, view_config=StructuralViewConfig(), gradient_clip_norm=1.,
                 gradient_probe_interval=500, probe_samples=4, allow_unit_tracker=False, validation_batch_cap=100000,
                 max_molecules=512, max_native_atoms=65536, max_padded_cost=8000000, training_execution=None, physical_policy=None):
        require(isinstance(model, V3MultiViewModel), "Canonical S/clean-PD multiview model required")
        _bindings(dict(bindings))
        self.model, self.optimizer, self.scheduler = model, optimizer, scheduler
        self.training_execution = training_execution
        self.training_execution_resources = None
        declared_execution = getattr(model, "training_execution_contract", None)
        require((training_execution is None) == (declared_execution is None),
                "An installed training execution requires its same finalized runtime handle")
        if training_execution is not None:
            from .v3_training_execution import validate_training_execution_contract
            require(training_execution.encoder is model.encoder and training_execution.observer is not None
                and validate_training_execution_contract(training_execution.contract) == declared_execution,
                "Complete-model training execution was not finalized by the bound adapter")
        self.sampler, self.clock, self.provider = sampler, clock, provider
        self.normalizations, self.weights = dict(normalizations), weights
        self.groups = selected_groups(enabled_groups)
        self.fields = tuple(field.name for field in model.registry.enabled(self.groups, enabled_fields))
        self.physical_policy = physical_policy
        bound_policy = getattr(provider, "physical_policy", None)
        require(bound_policy is None or (physical_policy is not None
                and physical_policy.projection == bound_policy.projection),
                "Trainer must consume the actual provider physical policy unchanged")
        if physical_policy is not None:
            from .v3_physical_policy import PhysicalLossPolicy
            require(isinstance(physical_policy, PhysicalLossPolicy)
                    and (not physical_policy.engineering_only or allow_unit_tracker),
                    "Physical-policy UNIT fixtures cannot grant production admission")
            from .v3_losses import loss_prediction_fields
            loss_prediction_fields(model.registry, self.normalizations, enabled_groups=self.groups,
                enabled_fields=self.fields, physical_policy=physical_policy)
        self.view_config = view_config
        require(math.isfinite(gradient_clip_norm) and gradient_clip_norm > 0 and type(gradient_probe_interval) is int
                and gradient_probe_interval > 0 and type(probe_samples) is int and probe_samples > 0,
                "Finite clip and bounded probe configuration required")
        require(type(validation_batch_cap) is int and validation_batch_cap > 0, "Validation batch bound required")
        require(all(type(value) is int and value > 0 for value in (max_molecules, max_native_atoms, max_padded_cost)),
                "Positive atom-aware batch budgets required")
        self.batch_limits = (max_molecules, max_native_atoms, max_padded_cost)
        require(getattr(provider, "read_only", None) is True and getattr(provider, "node_local", None) is True
                and provider.data_version == sampler.index.version == bindings["data_version"]
                and type(provider.source_sha256) is str and len(provider.source_sha256) == 64,
                "Explicit readonly node-local adapter/data binding required")
        require(callable(getattr(provider, "prepare", None)), "Bound provider.prepare required")
        require(callable(getattr(provider, "state_dict", None)) == callable(getattr(provider, "load_state_dict", None)),
                "Stateful provider requires paired committed-state save/restore hooks")
        require(sampler.sample_budget == clock.sample_budget and scheduler.contract["sample_budget"] == clock.sample_budget,
                "Sampler/scheduler/trainer sample budgets differ")
        require(sampler.samples_consumed == clock.samples_consumed == scheduler.samples_consumed, "Initial consumed clocks differ")
        optimized = [parameter for group in optimizer.param_groups for parameter in group["params"]]
        parameter_names = {id(parameter): name for name, parameter in model.named_parameters()}
        require(len({id(parameter) for parameter in optimized}) == len(optimized)
                and {id(parameter) for parameter in optimized} == {id(parameter) for parameter in model.parameters() if parameter.requires_grad},
                "Optimizer must own every selected model parameter exactly once")
        self.parameters = tuple(optimized)
        self.device = next(model.parameters()).device
        require(all(parameter.device == self.device and parameter.dtype == torch.float32 for parameter in self.parameters),
                "Single-device fp32 parameter storage required")
        require(all(bool(torch.isfinite(parameter).all()) for parameter in self.parameters), "Initial parameters must be finite")
        self.gradient_clip_norm, self.gradient_probe_interval = float(gradient_clip_norm), gradient_probe_interval
        self.probe_samples, self.validation_batch_cap = probe_samples, validation_batch_cap
        self.tracker, self.tracker_identity = tracker, _tracker(tracker, allow_unit_tracker)
        require(gradient_probe_interval == 500 or self.tracker_identity["unit_protocol_only"],
                "Production shared-gradient probes use the preregistered 500-update interval")
        self.contract = {"schema": "model_v3_step_trainer_v1", "enabled_groups": list(self.groups), "enabled_fields": list(self.fields),
            "view_configuration": asdict(view_config), "original_s_loss_weights": asdict(weights),
            "gradient_clip_norm": self.gradient_clip_norm, "gradient_probe_interval": gradient_probe_interval,
            "probe_samples": probe_samples, "scheduler_binding": scheduler.binding_sha256,
            "batch_limits": list(self.batch_limits), "schedule_clock": "consumed_samples_including_no_label_batches",
            "adapter_sha256": provider.source_sha256, "registry_projection": model.registry.content_sha256,
            "provider_class": type(provider).__module__ + "." + type(provider).__qualname__,
            "normalization_projection": canonical_hash({key: asdict(value) for key, value in self.normalizations.items()}),
            "performance_options": _execution_state(model)["performance_options"],
            "optimizer_class": type(optimizer).__module__ + "." + type(optimizer).__qualname__,
            "optimizer_parameter_groups": [[parameter_names[id(parameter)] for parameter in group["params"]]
                                            for group in optimizer.param_groups],
            "optimizer_options": [{key: deepcopy(value) for key, value in group.items()
                                   if key not in ("params", "lr", "initial_lr")} for group in optimizer.param_groups]}
        integration_state = _execution_state(model).get("performance_integration")
        if integration_state is not None:self.contract["performance_integration"] = integration_state
        if training_execution is not None:self.contract["training_execution"] = deepcopy(training_execution.contract)
        if physical_policy is not None:
            self.contract["physical_loss_policy"] = physical_policy.projection
        self.bindings = {**dict(bindings), "trainer_configuration_sha256": canonical_hash(self.contract),
                         "adapter_sha256": provider.source_sha256,
                         "trainer_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
        self.log_cursor = 0
        self.pending_log = None
        self.resume_parent = None
        self.validation_state = {role: {"completed_runs": 0, "last_result": None}
                                 for role in ("VAL", "TRAIN_UNSEEN_CONFORMATION")}
        self.started = time.perf_counter()
        self.segment_initial_samples = clock.samples_consumed

    def _within_capacity(self, choices):
        maximum, atom_limit, cost_limit = self.batch_limits
        return (len(choices) <= maximum and sum(choice.native_atoms for choice in choices) <= atom_limit
                and (3 if "S" in self.groups else 1) * len(choices) * max(choice.native_atoms for choice in choices) ** 2 <= cost_limit)

    def _draws(self, choices):
        require(self.sampler.samples_consumed == self.clock.samples_consumed == self.scheduler.samples_consumed,
                "Consumed sample clocks diverged before optimization")
        choices = tuple(choices)
        require(bool(choices) and len(choices) == self.clock.max_next_samples(len(choices)), "Draws cross sample checkpoint/budget boundary")
        require(len(choices) == 1 or self._within_capacity(choices), "Draw batch exceeds its declared atom/padded budgets")
        expected = tuple(self.sampler.choice(self.clock.samples_consumed + i) for i in range(len(choices)))
        require(choices == expected, "Draws differ from next committed stream before optimization")
        return choices

    def _prepared(self, batch, *, role, choices=None):
        require(isinstance(batch, PreparedV3Batch) and batch.role == role and batch.adapter_sha256 == self.provider.source_sha256
                and batch.data_version == self.provider.data_version, "Prepared adapter/data/role binding differs")
        require(tuple(batch.views.ordinals) == tuple(choice.ordinal for choice in batch.choices)
                and len(batch.views.clean_graph_rows) == len(batch.choices)
                and len(batch.views.clean_atom_rows) == sum(choice.native_atoms for choice in batch.choices)
                and batch.views.config == self.view_config and batch.views.includes_structural == ("S" in self.groups),
                "Prepared views/choice/clock configuration differs")
        require(bool(batch.choices) and (len(batch.choices) == 1 or self._within_capacity(batch.choices)),
                "Prepared batch exceeds its declared atom/padded budgets")
        if choices is not None:
            require(tuple(batch.choices) == tuple(choices), "Provider changed requested draws")
        return batch.to(self.device)

    def _prepare(self, choices, role="TRAIN"):
        value = self.provider.prepare(tuple(choices), role=role, view_config=self.view_config,
                                      enabled_groups=self.groups, enabled_fields=self.fields)
        return self._prepared(value, role=role, choices=choices)

    @contextmanager
    def _preserve_provider(self):
        # Adapters expose committed semantic state, never worker handles or
        # speculative-prefetch cursors. Stateless readonly adapters need no hook.
        save = getattr(self.provider, "state_dict", None)
        state = deepcopy(save()) if save is not None else None
        try:
            yield
        finally:
            if save is not None:
                self.provider.load_state_dict(state)

    def _execution_capture(self, role):
        if self.training_execution is None:
            return None
        return self.training_execution.observer.capture_forward(self.model, role=role)

    def _execution_complete(self, snapshot):
        if snapshot is None:
            return None
        require(callable(self.training_execution_resources),
                "Training execution requires an actual owned runtime resource callback")
        return self.training_execution.observer.record_completed(snapshot, optimizer=self.optimizer,
            optimizer_updates=self.clock.optimizer_updates, samples_consumed=self.clock.samples_consumed,
            resources=self.training_execution_resources())

    def _execution_validation_begin(self, role, count):
        if self.training_execution is not None:
            populations = self.training_execution.workload_binding['data']['validation_population_bindings']
            self.training_execution.observer.begin_validation(role, batch_count=count,
                population_binding=populations[role])

    def _execution_validation_complete(self, role):
        if self.training_execution is not None:
            self.training_execution.observer.complete_validation(role)

    def _forward_loss(self, batch):
        # Selective backbone bf16, when configured, is implemented inside the
        # bound performance model. Geometry/heads/loss stay outside autocast.
        if self.training_execution is None:
            execution_context = nullcontext()
        else:
            from .v3_training_execution import training_execution_context
            execution_context = training_execution_context(self.training_execution)
        observer_context = (nullcontext() if self.training_execution is None else
            self.training_execution.observer.forward_context(self.model, role=batch.role))
        with execution_context, observer_context, torch.autocast(device_type=self.device.type, enabled=False):
            domain_arguments = ({"domain_inputs": batch.domain_inputs, "geometry_context": batch.geometry_context}
                                if batch.domain_inputs else {})
            from .v3_losses import loss_prediction_fields
            prediction_fields = loss_prediction_fields(self.model.registry, self.normalizations,
                enabled_groups=self.groups, enabled_fields=self.fields, physical_policy=self.physical_policy)
            prediction = self.model.forward_pretrain(batch.views, enabled_groups=self.groups, enabled_fields=prediction_fields,
                pair_indices=batch.pair_indices, prediction_offsets=batch.prediction_offsets, **domain_arguments)
            loss_arguments = {}
            if self.physical_policy is not None:
                require(self.physical_policy.projection == self.contract["physical_loss_policy"],
                        "Physical target policy changed after trainer/CP binding")
                loss_arguments["physical_policy"] = self.physical_policy
            loss = self.model.compute_loss(prediction, batch.views, batch.pd_targets, self.normalizations,
                enabled_groups=self.groups, enabled_fields=self.fields, weights=self.weights,
                atom_eligibility=batch.atom_eligibility, bond_pair_eligibility=batch.bond_pair_eligibility,
                exposure_step=self.clock.samples_consumed, **loss_arguments)
        require(bool(torch.isfinite(loss.total)), "Nonfinite training/validation loss")
        return prediction, loss

    def _tables(self, prediction, batch):
        predictions, targets = dict(prediction.pd_predictions), dict(batch.pd_targets)
        if "S" not in self.groups:
            return predictions, targets
        binding, views = self.model.structural_binding, batch.views
        for role in ("element", "noise", "bond"):
            name = binding.field_name(role)
            if name not in self.fields:
                continue
            masked = _masked_for_role(prediction.source_outputs, views, role,
                atom_eligibility=batch.atom_eligibility.get(role), bond_pair_eligibility=batch.bond_pair_eligibility)
            if role == "bond":
                bond = masked.bond
                predictions[name] = bond.order
                targets[name] = FieldTarget(bond.order_target[:, None], torch.ones(len(bond.order), device=self.device, dtype=torch.bool))
                continue
            types = views.batch.sample_type_id.reshape(-1)
            node = masked.node_mask.squeeze(-1).bool()
            if role == "element":
                labels, _ = to_dense_batch(views.batch.target_x, views.batch.batch)
                corrupt, _ = to_dense_batch(views.batch.element_corrupt_mask, views.batch.batch)
                logits = masked.element_logits
                valid = node & types.eq(2)[:, None] & corrupt.reshape(node.shape).bool()
                valid &= labels[..., 0].ge(0) & labels[..., 0].lt(logits.size(-1) - 1)
                predictions[name] = logits.reshape(-1, logits.size(-1))
                targets[name] = FieldTarget(labels.reshape(-1, 1).long(), valid.reshape(-1))
            else:
                noisy, _ = to_dense_batch(views.batch.pos, views.batch.batch)
                clean, _ = to_dense_batch(views.batch.target_pos, views.batch.batch)
                valid = node & types.eq(1)[:, None] & torch.isfinite(noisy).all(-1) & torch.isfinite(clean).all(-1)
                predictions[name] = masked.noise_pred.reshape(-1, 3)
                targets[name] = FieldTarget((noisy - clean).reshape(-1, 3), valid.reshape(-1))
        return predictions, targets

    def _field_metrics(self, predictions, targets, loss):
        result = {}
        for field in self.model.registry.fields:
            name, enabled = field.name, field.name in self.fields
            count = loss.counts.get(name, 0) if enabled else 0
            result["field_enabled/" + name] = enabled
            result["valid_count/" + name] = count
            result["accuracy/" + name] = None
            result["MAE/" + name] = None
            result["R2/" + name] = None
            result["metric_status/" + name] = "INACTIVE" if not enabled else "NO_VALID_LABELS"
            if not enabled:
                continue
            effective = loss.loss_counts[name]
            if loss.has_loss_readiness:
                result["loss_count/" + name] = effective
                result["loss_status/" + name] = loss.loss_status[name]
                if name in loss.loss_reasons: result["loss_disabled_reason/" + name] = loss.loss_reasons[name]
                if loss.physical_policy_sha256 is not None:
                    result["physical_status/" + name] = loss.physical_status[name]
                    result["scale_status/" + name] = loss.scale_status[name]
                    result["physical_policy_sha256"] = loss.physical_policy_sha256
                    if name in loss.scale_reasons: result["scale_disabled_reason/" + name] = loss.scale_reasons[name]
            result["loss/" + name] = float(loss.fields[name].detach()) if effective else None
            if name not in predictions:
                from .v3_losses import source_observed_rows
                require(effective == 0 and loss.loss_status.get(name) in (
                    "LOSS_DISABLED_SCALE_UNBOUND_OR_DEGENERATE", "LOSS_DISABLED_PHYSICAL_POLICY_UNBOUND"),
                    "A ready target cannot omit its prediction")
                _, observed = source_observed_rows(field, targets[name])
                require(observed == count, "Source-only label population differs")
                result["metric_status/" + name] = "LOSS_DISABLED_NO_PREDICTION"
                continue
            pred, target, observed = observed_rows(field, predictions[name], targets[name])
            require(observed == count, "Single-step loss/metric label populations differ")
            if not count:
                continue
            if field.kind in ("binary", "classification"):
                labels = pred.argmax(-1) if field.kind == "classification" else (pred[:, 0] >= 0).long()
                result["accuracy/" + name] = float((labels == target[:, 0]).float().mean())
                result["metric_status/" + name] = "CATEGORICAL_R2_MAE_NA"
            else:
                difference = pred.detach().double() - target.double()
                result["MAE/" + name] = float(difference.abs().mean())
                variance = (target.double() - target.double().mean(0)).square().sum()
                if count > 1 and bool(variance > 0):
                    result["R2/" + name] = float(1 - difference.square().sum() / variance)
                    result["metric_status/" + name] = "AVAILABLE"
                else:
                    result["metric_status/" + name] = "R2_CONSTANT_OR_INSUFFICIENT_LABELS"
        return result

    def flush_pending_log(self):
        if self.pending_log is not None:
            require(self.tracker.step <= self.log_cursor,
                    "SDK cursor is ahead of checkpoint history; use a fresh bound resume lineage")
            self.tracker.log(self.pending_log, step=self.log_cursor, commit=True)
            self.log_cursor += 1
            self.pending_log = None

    def _log(self, row):
        require(self.pending_log is None, "Unacknowledged tracking record must be retried before new work")
        row["log_cursor"] = self.log_cursor
        if self.resume_parent is not None:
            row["resume_parent_run_id"] = self.resume_parent["id"]
        self.pending_log = row
        self.flush_pending_log()

    def step(self, batch: PreparedV3Batch):
        require(self.pending_log is None, "Unacknowledged tracking record blocks optimizer updates")
        choices = self._draws(batch.choices)
        batch = self._prepared(batch, role="TRAIN", choices=choices)
        step_started = time.perf_counter()
        self.model.train()
        self.optimizer.zero_grad(set_to_none=True)
        lr_used = [float(group["lr"]) for group in self.optimizer.param_groups]
        prediction, loss = self._forward_loss(batch)
        execution_snapshot = self._execution_capture("TRAIN")
        # Population/metric validation must also precede the numerical update.
        tables = self._tables(prediction, batch)
        metrics = self._field_metrics(*tables, loss)
        observed = any(value > 0 for value in loss.loss_counts.values())
        probe = {}
        if observed:
            require(loss.total.requires_grad, "Observed labels have no effective model gradient")
            update = self.clock.optimizer_updates + 1
            if update % self.gradient_probe_interval == 0:
                with _preserve_rng(), self._preserve_provider():
                    probe_batch = self._prepare(choices[:min(len(choices), self.probe_samples)])
                    _, probe_loss = self._forward_loss(probe_batch)
                    probe = shared_backbone_gradient_norms(probe_loss.groups, self.model.encoder.backbone.parameters(),
                        optimizer_update=update, interval=self.gradient_probe_interval)
                    require(all(math.isfinite(value) for value in probe.values()), "Nonfinite shared-gradient probe")
            loss.total.backward()
            norm = torch.nn.utils.clip_grad_norm_(self.parameters, self.gradient_clip_norm)
            require(bool(torch.isfinite(norm)) and all(bool(torch.isfinite(p.grad).all()) for p in self.parameters if p.grad is not None),
                    "Nonfinite gradient before optimizer update")
            self.optimizer.step()
        else:
            norm = None
        # Nothing above this line can advance the consumed sample cursor.
        commit_consumed_batch(self.sampler, self.clock, choices, optimizer_updated=observed)
        self.scheduler.set_consumed(self.clock.samples_consumed)
        row = {"event": "TRAIN_STEP", "samples_consumed": self.clock.samples_consumed,
               "optimizer_updates": self.clock.optimizer_updates, "optimizer_updated": observed,
               "loss/total": float(loss.total.detach()), "gradient_norm_before_clip": None if norm is None else float(norm),
               "lr_used": lr_used, "lr_next": [float(group["lr"]) for group in self.optimizer.param_groups],
               "sample_ordinals": [choice.ordinal for choice in choices], **metrics}
        if loss.has_loss_readiness and not observed: row["loss/total"] = None
        row.update({"shared_gradient_norm/" + key: value for key, value in probe.items()})
        if self.device.type == "cuda":
            torch.cuda.synchronize(self.device)
        runtime = runtime_metrics(samples=self.clock.samples_consumed - self.segment_initial_samples,
                                  started=self.started, step_started=step_started)
        runtime["segment_samples"] = runtime.pop("samples_consumed")
        runtime["segment_initial_samples"] = self.segment_initial_samples
        row.update({"runtime/" + key: value for key, value in runtime.items()})
        execution_row = self._execution_complete(execution_snapshot)
        if execution_row is not None:row["training_execution_observation"] = execution_row
        self._log(row)
        return row

    def next_step(self, max_samples=512):
        require(self.pending_log is None, "Unacknowledged tracking record blocks provider and optimizer work")
        require(type(max_samples) is int and max_samples > 0, "Positive requested batch size required")
        count = self.clock.max_next_samples(max_samples)
        require(count > 0, "Training sample budget exhausted")
        require(self.clock.samples_consumed not in self.clock.milestones
                or self.clock.samples_consumed in self.clock.saved_milestones,
                "Save the reached sample milestone before advancing training")
        choices = []
        for i in range(min(count, self.batch_limits[0])):
            candidate = self.sampler.choice(self.clock.samples_consumed + i)
            if choices and not self._within_capacity((*choices, candidate)):
                break
            choices.append(candidate)
        choices = tuple(choices)
        self._draws(choices)  # Validate before the provider can prepare tensors.
        return self.step(self._prepare(choices))

    def run(self, *, max_batch_samples=512, until_samples=None, checkpoint_root=None):
        target = self.clock.sample_budget if until_samples is None else until_samples
        require(type(target) is int and self.clock.samples_consumed <= target <= self.clock.sample_budget, "Invalid fixed sample endpoint")
        if checkpoint_root is None:
            require(not any(self.clock.samples_consumed <= value <= target and value not in self.clock.saved_milestones
                            for value in self.clock.milestones),
                    "Fixed-budget run requires an output root for its sample milestones")
        steps, checkpoints, last = 0, [], None
        if self.clock.samples_consumed in self.clock.milestones and self.clock.samples_consumed not in self.clock.saved_milestones:
            root = Path(checkpoint_root)
            path = root / f"seen_{self.clock.samples_consumed}_update_{self.clock.optimizer_updates}_log_{self.log_cursor}"
            self.save(path, output_root=root)
            checkpoints.append(str(path))
        while self.clock.samples_consumed < target:
            last = self.next_step(min(max_batch_samples, target - self.clock.samples_consumed))
            steps += 1
            if self.clock.samples_consumed in self.clock.milestones and self.clock.samples_consumed not in self.clock.saved_milestones:
                require(checkpoint_root is not None, "A declared sample milestone requires a checkpoint output root")
                root = Path(checkpoint_root)
                path = root / f"seen_{self.clock.samples_consumed}_update_{self.clock.optimizer_updates}_log_{self.log_cursor}"
                self.save(path, output_root=root)
                checkpoints.append(str(path))
        # History is streamed to the tracker; do not retain corpus-sized rows.
        return {"steps": steps, "samples_consumed": self.clock.samples_consumed,
                "optimizer_updates": self.clock.optimizer_updates, "log_cursor": self.log_cursor,
                "checkpoints": checkpoints, "last_step": last}

    def validate(self, role, batches=None):
        require(role in self.validation_state, "Only VAL and TRAIN_UNSEEN_CONFORMATION are permitted")
        require(self.pending_log is None, "Flush pending training history before validation")
        # Provider construction can itself draw random numbers; isolate it too.
        with _preserve_rng(), self._preserve_provider():
            return self._validate_population(role, batches)

    def _validate_population(self, role, batches):
        if batches is None:
            count, iterator = self.provider.validation_batches(role=role, view_config=self.view_config,
                enabled_groups=self.groups, enabled_fields=self.fields)
        else:
            require(type(batches) in (list, tuple), "Explicit validation batches must be a bounded list/tuple")
            count, iterator = len(batches), iter(batches)
        require(type(count) is int and 0 < count <= self.validation_batch_cap, "Bounded full validation batch count required")
        self._execution_validation_begin(role, count)
        metric = ValidationAccumulator(self.model.registry, role=role, enabled_groups=self.groups, enabled_fields=self.fields)
        previous_mode = self.model.training
        actual = 0
        try:
            with _preserve_rng(), torch.no_grad():
                self.model.eval()
                for value in iterator:
                    require(actual < count, "Validation provider exceeded its declared population")
                    batch = self._prepared(value, role=role)
                    prediction, loss = self._forward_loss(batch)
                    execution_snapshot = self._execution_capture(role)
                    metric.add(*self._tables(prediction, batch), loss)
                    self._execution_complete(execution_snapshot)
                    actual += 1
        finally:
            self.model.train(previous_mode)
        require(actual == count, "Validation provider ended before its declared population")
        self._execution_validation_complete(role)
        result = metric.result()
        for field in self.model.registry.fields:
            if field.name not in result["fields"]:
                result["fields"][field.name] = {"valid_labels": 0, "loss": None, "MAE": None, "R2": None,
                    "accuracy": None, "enabled": False, "metric_status": "INACTIVE"}
            else:
                row = result["fields"][field.name]
                row["enabled"] = True
                row["metric_status"] = ("NO_VALID_LABELS" if row["valid_labels"] == 0 else
                    "CATEGORICAL_R2_MAE_NA" if field.kind in ("binary", "classification") else
                    "R2_CONSTANT_OR_INSUFFICIENT_LABELS" if row["R2"] is None else "AVAILABLE")
        self.validation_state[role] = {"completed_runs": self.validation_state[role]["completed_runs"] + 1,
                                       "last_result": deepcopy(result)}
        self._log({"event": "VALIDATION", "samples_consumed": self.clock.samples_consumed,
                   "optimizer_updates": self.clock.optimizer_updates, **result})
        return result

    def save(self, directory, *, output_root):
        extra = {"schema": "model_v3_trainer_resume_v1", "contract": deepcopy(self.contract),
                 "scheduler": self.scheduler.state_dict(), "execution": _execution_state(self.model),
                 "tracker": self.tracker_identity, "log_cursor": self.log_cursor,
                 "pending_log": deepcopy(self.pending_log), "validation_state": deepcopy(self.validation_state),
                 "model_training": self.model.training,
                 "provider_state": deepcopy(self.provider.state_dict()) if hasattr(self.provider, "state_dict") else None}
        return save_new_checkpoint(directory, output_root=output_root, model=self.model, optimizer=self.optimizer,
            sampler=self.sampler, clock=self.clock, bindings=self.bindings, extra_state=extra)

    def load(self, directory, *, output_root):
        # Inspect and authenticate extra state before changing execution flags or
        # model/optimizer state. Source and physical file checks are repeated by
        # the existing tested checkpoint loader below.
        directory = _check_output_path(directory, output_root)
        marker = json.loads((directory / "COMPLETE.json").read_text(encoding="utf-8"))
        path = directory / "payload.pt"
        require(marker["bindings"] == self.bindings and marker["payload_sha256"] == _file_sha(path)
                and marker["payload_bytes"] == path.stat().st_size, "Trainer checkpoint binding/digest differs")
        preview_payload = torch.load(path, map_location="cpu", weights_only=True)
        preview = preview_payload["extra_state"]
        require(preview["schema"] == "model_v3_trainer_resume_v1" and preview["contract"] == self.contract
                and preview["scheduler"]["binding_sha256"] == self.scheduler.binding_sha256,
                "Trainer/scheduler configuration differs")
        require(type(preview["log_cursor"]) is int and preview["log_cursor"] >= 0
                and set(preview["validation_state"]) == set(self.validation_state), "Trainer history/validation state differs")
        require(preview["execution"].get("training_execution") == self.contract.get("training_execution"),
                "Trainer contract and saved training execution differ")
        _restore_execution(self.model, preview["execution"])
        extra = load_checkpoint(directory, output_root=output_root, model=self.model, optimizer=self.optimizer,
            sampler=self.sampler, clock=self.clock, expected_bindings=self.bindings)
        self.scheduler.load_state_dict(extra["scheduler"])
        require(self.scheduler.samples_consumed == self.clock.samples_consumed, "Restored scheduler/seen clocks differ")
        self.log_cursor, self.pending_log = extra["log_cursor"], extra["pending_log"]
        self.validation_state, self.resume_parent = extra["validation_state"], extra["tracker"]
        if extra["provider_state"] is not None:
            require(callable(getattr(self.provider, "load_state_dict", None)), "Restored provider lacks committed-state hook")
            self.provider.load_state_dict(extra["provider_state"])
        self.model.train(extra["model_training"])
        restore_rng_state(preview_payload["rng"])
        self.started = time.perf_counter()
        self.segment_initial_samples = self.clock.samples_consumed
        return extra
