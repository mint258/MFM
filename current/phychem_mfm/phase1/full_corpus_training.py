"""Finite-epoch compact-corpus training with global exposure and update clocks.

New full-corpus science; this does not consume the historical 58k formal schema
or its source bridge. The CLI supplies physically checked frozen artifacts and
an external owned-process/GPU supervisor. No final-test data is accepted here.
"""
from __future__ import annotations

from copy import copy, deepcopy
import math
import time

import torch

from ..model.shared import SharedBackboneMFM
from ..supervision import SupervisionConfig
from ..training.losses import LossWeights, compute_pretrain_loss
from ..training.optim import build_adamw
from .downstream_training import checkpoint_content_sha256, _copy_cpu
from .seed_runtime import validate_runtime_selection
from .full_corpus_controls import load_full_corpus_controls
from .evaluation import OriginalUnitEvaluator
from .dynamic_loss import DynamicLossConfig, EMAGradientBalancer
from .formal_gate import canonical_sha256 as canonical_hash
from .formal_runtime import backbone_state_hash
from .full_corpus_loader import BlockAtomBatchSampler, CorpusBatch, close_prefetch_iterator
from .objectives import GROUP_TASKS, Phase1JointSchedule, Phase1LossPolicy, canonical_variant
from .positive_strategy import JOINT, PositiveExposureStrategy

SCHEMA = "phase1_full_corpus_training_v1"
CHECKPOINT = "phase1_full_corpus_checkpoint_v1"


class FullCorpusTrainingError(RuntimeError):
    pass


def _require(value, message):
    if not value:
        raise FullCorpusTrainingError(message)


def _integer(value, name, minimum=0):
    _require(type(value) is int and value >= minimum, name + " must be an integer >= " + str(minimum))
    return value


def _finite(value, name, positive=False):
    _require(type(value) in (int, float) and math.isfinite(value)
             and (not positive or value > 0), name + " must be finite" + (" and positive" if positive else ""))
    return float(value)


class BaseExposureCosine:
    """LR for the next consumed batch, independent of whether its labels exist.

    A zero-label batch advances consumed-base exposure and therefore this data
    clock, but never performs an AdamW step. Batch cardinality is variable. The
    finite warmup endpoint and full multi-epoch horizon are frozen in base structures.
    """
    def __init__(self, optimizer, *, total_base_exposures, warmup_base_exposures, min_lr_ratio):
        self.optimizer = optimizer
        self.total = _integer(total_base_exposures, "exposure horizon", 1)
        self.warmup = _integer(warmup_base_exposures, "warmup exposure")
        _require(self.warmup <= self.total, "Warmup exceeds the declared exposure horizon")
        self.minimum = _finite(min_lr_ratio, "minimum LR ratio")
        _require(0 <= self.minimum <= 1, "LR ratio outside [0,1]")
        self.base_lrs = [_finite(g["lr"], "base LR", True) for g in optimizer.param_groups]
        self.consumed = 0
        self.set_consumed(0)

    def set_consumed(self, consumed):
        consumed = _integer(consumed, "scheduler exposure")
        _require(consumed <= self.total, "Scheduler exposure exceeds the declared horizon")
        self.consumed = consumed
        if self.warmup and consumed < self.warmup:
            factor = (consumed + 1) / self.warmup
        else:
            progress = (consumed - self.warmup) / max(1, self.total - self.warmup)
            factor = self.minimum + (1 - self.minimum) * (1 + math.cos(math.pi * min(1, max(0, progress)))) / 2
        for group, base in zip(self.optimizer.param_groups, self.base_lrs):
            group["lr"] = base * factor

    def state_dict(self):
        return {"schema_version": "phase1_base_exposure_cosine_v1", "total_base_exposures": self.total,
                "warmup_base_exposures": self.warmup, "min_lr_ratio": self.minimum,
                "base_lrs": self.base_lrs.copy(), "consumed_base_exposures": self.consumed}

    def load_state_dict(self, state):
        expected = self.state_dict()
        _require(isinstance(state, dict) and set(state) == set(expected), "Scheduler fields differ")
        for name in expected.keys() - {"consumed_base_exposures"}:
            _require(state[name] == expected[name], "Scheduler recipe differs: " + name)
        self.set_consumed(state["consumed_base_exposures"])


def _optimizer(model, config):
    _require(set(config) == {"lr", "weight_decay", "betas"}, "Unsupported optimizer fields")
    _finite(config["lr"], "AdamW LR", True)
    _finite(config["weight_decay"], "weight decay")
    _require(config["weight_decay"] >= 0 and type(config["betas"]) is list and len(config["betas"]) == 2,
             "Invalid AdamW parameters")
    for value in config["betas"]:
        _require(0 <= _finite(value, "AdamW beta") < 1, "AdamW beta outside [0,1)")
    return build_adamw(model, **config)


def _optimizer_candidate(optimizer, state, updates, parameter_updates):
    """Validate sparse AdamW state: missing-label heads legitimately lack moments.

    Parameter IDs/groups are exact. Every saved moment is finite and has the
    parameter shape/dtype, and its step is positive and <= global updates. The
    typed checkpoint seal binds the exact sparse map; unlike downstream heads,
    these heads are not all observed at every optimizer step.
    """
    template = optimizer.state_dict()
    _require(isinstance(state, dict) and set(state) == {"state", "param_groups"}, "Invalid optimizer fields")
    _require(type(state["param_groups"]) is list and len(state["param_groups"]) == len(template["param_groups"]),
             "Optimizer group count differs")
    params = {}
    for live, expected, saved in zip(optimizer.param_groups, template["param_groups"], state["param_groups"]):
        _require(isinstance(saved, dict) and set(saved) == set(expected), "Optimizer group fields differ")
        for key in expected.keys() - {"lr"}:
            _require(saved[key] == expected[key], "Optimizer recipe/parameter IDs differ: " + key)
        _finite(saved["lr"], "saved optimizer LR")
        for ident, parameter in zip(expected["params"], live["params"]):
            params[ident] = parameter
    _require(isinstance(state["state"], dict) and all(type(i) is int and i in params for i in state["state"]),
             "Optimizer moments contain unknown parameter IDs")
    expected_steps = {ident: parameter_updates[id(parameter)] for ident, parameter in params.items()}
    _require(set(state["state"]) == {ident for ident, count in expected_steps.items() if count > 0},
             "Optimizer moment inventory differs from actual parameter-update counters")
    _require(updates > 0 or not state["state"], "Zero-update checkpoint has optimizer moments")
    for ident, values in state["state"].items():
        _require(isinstance(values, dict) and set(values) == {"step", "exp_avg", "exp_avg_sq"}, "AdamW moment fields differ")
        step = values["step"]
        _require(isinstance(step, torch.Tensor) and step.numel() == 1 and torch.isfinite(step).all()
                 and float(step) == int(float(step)) and float(step) == expected_steps[ident]
                 and 1 <= float(step) <= updates, "AdamW step differs from actual parameter-update count")
        for key in ("exp_avg", "exp_avg_sq"):
            value = values[key]
            _require(isinstance(value, torch.Tensor) and value.shape == params[ident].shape
                     and value.dtype == params[ident].dtype and bool(torch.isfinite(value).all()), "Malformed/nonfinite AdamW moment")
        _require(bool(values["exp_avg_sq"].ge(0).all()), "Negative AdamW second moment")
    optimizer.load_state_dict(_copy_cpu(state))


def _state_candidate(model, state):
    expected = model.state_dict()
    _require(isinstance(state, dict) and set(state) == set(expected), "Model state keys differ")
    for name, reference in expected.items():
        value = state[name]
        _require(isinstance(value, torch.Tensor) and value.shape == reference.shape and value.dtype == reference.dtype,
                 "Model state shape/dtype differs: " + name)
        if value.is_floating_point() or value.is_complex():
            _require(bool(torch.isfinite(value).all()), "Nonfinite model state: " + name)
    model.load_state_dict(_copy_cpu(state), strict=True)


def _rng(device):
    return {"cpu": torch.get_rng_state().clone(),
            "cuda": torch.cuda.get_rng_state(0).cpu().clone() if device.type == "cuda" else None}


def _validate_rng(state, device):
    _require(isinstance(state, dict) and set(state) == {"cpu", "cuda"}, "RNG fields differ")
    for name in ("cpu", "cuda"):
        value = state[name]
        if name == "cuda" and device.type == "cpu":
            _require(value is None, "CPU checkpoint contains a CUDA RNG")
            continue
        _require(isinstance(value, torch.Tensor) and value.device.type == "cpu" and value.dtype == torch.uint8
                 and value.ndim == 1, "Invalid RNG tensor")
        generator = torch.Generator(device="cpu" if name == "cpu" else device)
        generator.set_state(value.clone())


class FullCorpusTrainer:
    """Actual shared-H0 optimization; one W&B run per restartable segment.

    ``fit`` consumes each complete finite sampler epoch; no label-based replacement,
    no best-endpoint training and no prefetch cursor stored as real exposure.
    All successful optimizer updates are followed by an acknowledged tracker
    row before committing the sampler. Logging failure is terminal and its
    live state must not be exported as a resumable successful checkpoint.
    """
    def __init__(self, model, sampler, config, *, tracker, journal=None):
        _require(isinstance(model, SharedBackboneMFM) and isinstance(sampler, BlockAtomBatchSampler),
                 "Genuine SharedBackboneMFM and compact sampler required")
        self.config = deepcopy(config)
        required = {"schema_version", "variant", "seed", "device", "epochs", "views_per_base", "optimizer",
                    "schedule", "loss", "loss_policy", "dynamic_loss", "shared_parameter_names",
                    "gradient_clip_norm", "metric_interval", "bindings", "validation", "caps"}
        _require(required <= set(config) <= required | {"strategy", "original_unit_controls"}
                 and config["schema_version"] == SCHEMA, "Unsupported full-corpus training configuration")
        self.variant = canonical_variant(config["variant"])
        _require(self.variant != "none", "None is a paired-initialization export, not a corpus training loop")
        self.epochs = _integer(config["epochs"], "training epochs", 1)
        _require(config["views_per_base"] == 3, "Training requires three views per native exposure")
        self.total_base_exposures = self.epochs * len(sampler.index)
        _integer(config["seed"], "training seed")
        _integer(config["metric_interval"], "metric interval", 1)
        _require(sampler.epoch == 0 and sampler.samples_consumed == 0, "Fresh trainer requires a fresh epoch-zero sampler")
        _require(config["device"] in {"cpu", "cuda:0"}, "Only CPU or a single selected CUDA device is supported")
        self.device = torch.device(config["device"])
        _require(torch.get_default_dtype() == torch.float32, "Full-corpus recipe requires FP32 default dtype")
        self.strategy = (PositiveExposureStrategy.from_config(config["strategy"], variant=self.variant,
                         total_base_exposures=self.total_base_exposures) if "strategy" in config else
                         PositiveExposureStrategy(JOINT, self.variant, self.total_base_exposures))
        _require(self.strategy.name == JOINT or config["seed"] in (0, 1, 2), "Auxiliary strategy uses paired seeds 0,1,2 only")
        bindings = config["bindings"]
        required_bindings = {"protocol_sha256", "source_sha256",
                 "train_manifest_sha256", "routine_validation_manifest_sha256", "full_validation_manifest_sha256",
                 "normalization_contract_sha256", "initial_encoder_sha256", "environment"}
        _require(isinstance(bindings, dict) and set(bindings) in (required_bindings, required_bindings | {"runtime_selection"}),
                 "Exact new source/data/fit/init/runtime bindings required")
        if "runtime_selection" in bindings:
            selected_runtime = validate_runtime_selection(bindings["runtime_selection"], seed=config["seed"])
            _require(bindings["environment"] == selected_runtime["profile"]["runtime_environment"],
                     "Training environment differs from the paired-seed profile binding")
        # Validate the owned train-only controls before changing model placement
        # or modes. Legacy synthetic fixtures may omit this diagnostic interface;
        # the formal CLI requires its physically bound artifact.
        self.original_unit_baselines = None
        if "original_unit_controls" in self.config:
            try:
                self.original_unit_baselines = load_full_corpus_controls(
                    self.config["original_unit_controls"], model.head_config.get("regression_output_normalization"))
            except (ValueError, TypeError, KeyError, OverflowError) as exc:
                raise FullCorpusTrainingError("Invalid train-only original-unit controls") from exc
        self.model, self.sampler = model.to(self.device), sampler
        self.model.train()
        _require(all(parameter.requires_grad for parameter in model.parameters()), "All pretraining parameters must remain trainable")
        self.policy = Phase1LossPolicy.from_mapping(config["loss_policy"])
        self.loss_weights = LossWeights.from_mapping(config["loss"])
        self.supervision = SupervisionConfig.from_variant(self.variant)
        self.joint = Phase1JointSchedule()
        normal = model.head_config.get("regression_output_normalization")
        _require(normal and normal["version"] == "phase1_full_train_affine_output_v2", "Full-training affine contract is required")
        self.standardizers = deepcopy(normal["training_statistics"])
        _require(bindings["train_manifest_sha256"] == sampler.index.content_sha256
                 and bindings["normalization_contract_sha256"] == normal["contract_sha256"], "Training sampler/normalization differs from bindings")
        _require(sampler.index.role == "train", "Training cannot consume a validation/final-test view")
        _require(normal["training_provenance"]["train_manifest_sha256"] == sampler.index.content_sha256
                 and normal["training_provenance"]["retained_train_records"] == len(sampler.index), "Normalizer fitted another training view")
        provenance, manifest = normal["training_provenance"], sampler.index.manifest
        _require(provenance["train_view_sha256"] == manifest["view"]["sha256"]
                 and provenance["base_index_sha256"] == manifest["base_index"]["sha256"]
                 and provenance["quality_artifact_sha256"] == manifest["quality_and_identity_artifact_sha256"],
                 "Normalizer compact view/index/quality bytes differ from actual training bindings")
        _require(backbone_state_hash(model) == bindings["initial_encoder_sha256"], "Fresh paired encoder differs from new initialization artifact")
        self.initial_model_hash = checkpoint_content_sha256({"model": _copy_cpu(model.state_dict())})
        self.optimizer = _optimizer(model, config["optimizer"])
        _require(set(config["schedule"]) == {"warmup_base_exposures", "min_lr_ratio"}, "Exposure scheduler fields differ")
        self.scheduler = BaseExposureCosine(self.optimizer, total_base_exposures=self.total_base_exposures, **config["schedule"])
        names = tuple(config["shared_parameter_names"])
        selected = dict(model.backbone.named_parameters())
        _require(names and len(names) == len(set(names)) and all(name in selected for name in names), "Declared shared-gradient subset differs")
        self.shared_parameters = tuple(selected[name] for name in names)
        self.controller = EMAGradientBalancer(self.variant, names, config=DynamicLossConfig(**config["dynamic_loss"]), base_policy=self.policy)
        self.enabled_tasks = tuple(name for group in GROUP_TASKS if group in self.variant for name in GROUP_TASKS[group])
        validation = config["validation"]
        _require(set(validation) == {"criterion", "every_base_exposures", "task_scales"}
                 and validation["criterion"] == "fixed_standardized_leaf_macro_v1", "Validation must declare its fixed criterion")
        _integer(validation["every_base_exposures"], "validation exposure interval", 1)
        _require(isinstance(validation["task_scales"], dict) and set(validation["task_scales"]) == {n for g in GROUP_TASKS.values() for n in g}, "Fixed validation scales must cover every leaf")
        for value in validation["task_scales"].values():
            _finite(value, "fixed validation task scale", True)
        _require(set(config["caps"]) == {"segment_wall_seconds", "finalization_reserve_seconds"}, "Segment cap fields differ")
        _finite(config["caps"]["segment_wall_seconds"], "segment wall cap", True)
        _finite(config["caps"]["finalization_reserve_seconds"], "finalization reserve", True)
        _require(config["caps"]["finalization_reserve_seconds"] < config["caps"]["segment_wall_seconds"], "Reserve exceeds segment cap")
        if config["gradient_clip_norm"] is not None:
            _finite(config["gradient_clip_norm"], "gradient clip", True)
        self.tracker, self.journal = tracker, journal
        _require(callable(getattr(tracker, "log", None)) and type(getattr(tracker, "id", None)) is str
                 and tracker.id and type(getattr(tracker, "path", None)) is str and tracker.path
                 and getattr(getattr(tracker, "settings", None), "mode", getattr(tracker, "mode", None)) in {"online", "offline"}
                 and getattr(tracker, "disabled", False) is False, "Actual identified W&B-compatible tracker required")
        self.tracking = {"run_id": tracker.id, "run_path": tracker.path, "next_step": int(tracker.step),
                         "parent_run_id": None, "parent_checkpoint_sha256": None,
                         "offline_history_independently_decoded": False}
        self.counters = {"optimizer_updates": 0, "consumed_batches": 0, "consumed_base_exposures": 0,
                         "consumed_view_exposures": 0, "zero_label_batches": 0,
                         "successful_update_base_exposures": 0, "successful_update_view_exposures": 0,
                         "valid_labels": {name: 0 for name in self.enabled_tasks},
                         "optimizer_parameter_updates": {name: 0 for name, p in self.model.named_parameters()},
                         "total_wall_seconds": 0.0}
        self.validation_state = None
        # Sampler counters are local to the current epoch. Prior full-epoch batch
        # counts preserve the global clock even when atom buckets change counts.
        self.completed_epoch_batches = []
        self.last_validation = None
        self.best_validation = None
        self.next_validation_exposure = 0
        self.status = "partial"
        self._clock_started = None

    def _check_epoch_accounting(self, sampler, completed_batches, counters):
        _require(type(sampler.epoch) is int and 0 <= sampler.epoch < self.epochs,
                 "Training sampler epoch exceeds the frozen finite horizon")
        _require(type(completed_batches) is list and len(completed_batches) == sampler.epoch,
                 "Completed-epoch batch ledger differs from the active epoch")
        for count in completed_batches:
            _integer(count, "completed-epoch batches", 1)
        _require(sampler.epoch * len(sampler.index) + sampler.samples_consumed == counters["consumed_base_exposures"]
                 and sum(completed_batches) + sampler.batches_consumed == counters["consumed_batches"]
                 and counters["consumed_base_exposures"] <= self.total_base_exposures,
                 "Epoch-local sampler and global consumption clocks disagree")

    def _advance_training_epoch(self):
        """Called only after the previous iterator's workers have been closed."""
        self._check_epoch_accounting(self.sampler, self.completed_epoch_batches, self.counters)
        _require(self.sampler.samples_consumed == len(self.sampler.index)
                 and self.sampler.epoch + 1 < self.epochs and self.validation_state is None,
                 "Only a fully consumed nonfinal epoch may advance")
        self.completed_epoch_batches.append(self.sampler.batches_consumed)
        self.sampler.advance_epoch()  # Existing metadata order uses the same seed plus its new epoch.
        self._check_epoch_accounting(self.sampler, self.completed_epoch_batches, self.counters)

    def _log(self, row):
        cursor = self.tracking["next_step"]
        _require(self.tracker.step == cursor, "W&B local history cursor changed")
        row = {**row, "tracking/payload_sha256": canonical_hash(row)}
        self.tracker.log(row, step=cursor, commit=True)
        _require(self.tracker.step == cursor + 1, "W&B did not commit the history row")
        if self.journal is not None:
            self.journal(cursor, deepcopy(row))
        self.tracking["next_step"] += 1

    def _remaining(self):
        return self.config["caps"]["segment_wall_seconds"] - (time.monotonic() - self._clock_started)

    def _loss(self, batch, *, return_outputs=False):
        outputs = self.model.forward_pretrain(batch, objectives=self.supervision.objectives)
        result = compute_pretrain_loss(outputs, batch, self.standardizers, self.supervision,
             self.loss_weights, self.joint, self.counters["consumed_base_exposures"],
             graph_descriptor_indices=self.model.graph_descriptor_target_indices,
             phase1_mode=True, phase1_policy=self.policy)
        return (result, outputs) if return_outputs else result

    def _original_unit_evaluator(self):
        return (None if self.original_unit_baselines is None else
                OriginalUnitEvaluator(self.model, self.original_unit_baselines))

    def _check_original_unit_report(self, report):
        if report is None:
            return
        meter = self._original_unit_evaluator()
        names = {"original_unit_metrics", "original_unit_meter_state"}
        _require(isinstance(report, dict) and (names <= set(report) if meter is not None
                                             else not names.intersection(report)),
                 "Closed validation original-unit fields differ from the configured controls")
        if meter is not None:
            try:
                meter.load_state_dict(report["original_unit_meter_state"])
                _require(canonical_hash(meter.result()) == canonical_hash(report["original_unit_metrics"]),
                         "Closed original-unit report differs from its accumulators")
            except (ValueError, TypeError, KeyError, OverflowError) as exc:
                raise FullCorpusTrainingError("Invalid closed original-unit validation state") from exc

    def _consume(self, batch):
        _require(isinstance(batch, CorpusBatch), "Actual compact-corpus batch required")
        expected = self.sampler._next(self.sampler._cursor)
        _require(expected is not None and list(batch.logical_indices) == expected[0], "Prefetch batch differs from next real cursor")
        _require(len(batch.encoder_batch.ptr) - 1 == 3 * len(batch.logical_indices), "Batch does not contain exactly three native views")
        start = time.monotonic()
        actual = batch.encoder_batch.to(self.device, non_blocking=True)
        self.optimizer.zero_grad(set_to_none=True)
        loss = self._loss(actual)
        observed = [name for name in self.enabled_tasks if loss.counts.get(name, 0) > 0]
        update = self.counters["optimizer_updates"]
        lr_used = float(self.optimizer.param_groups[0]["lr"])
        balanced, scheduled = None, None
        exposure_start = self.counters["consumed_base_exposures"]
        if observed:
            balanced = self.controller.balance(loss, self.shared_parameters, update=update)
            _require(bool(torch.isfinite(balanced.total)), "Dynamic loss is nonfinite")
            group_budget = {g: self.policy.group_weights[g] * balanced.metrics["group_multipliers"][g]
                            for g in self.strategy.groups}
            scheduled = self.strategy.apply(balanced, start=exposure_start,
                              count=len(batch.logical_indices), group_budget=group_budget)
            scheduled.total.backward()
            for parameter in self.model.parameters():
                if parameter.grad is not None:
                    _require(bool(torch.isfinite(parameter.grad).all()), "Nonfinite true optimizer gradient")
            _require(all(p.grad is not None for p in self.model.backbone.parameters()), "Observed objectives lost a registered H0 gradient path")
            clip = self.config["gradient_clip_norm"]
            if clip is not None:
                norm = torch.nn.utils.clip_grad_norm_(self.model.parameters(), clip, error_if_nonfinite=True)
            else:
                norm = torch.linalg.vector_norm(torch.stack([p.grad.detach().double().norm() for p in self.model.parameters() if p.grad is not None]))
            self.optimizer.step()
            self.counters["optimizer_updates"] += 1
            for name, parameter in self.model.named_parameters():
                if parameter.grad is not None:
                    self.counters["optimizer_parameter_updates"][name] += 1
            self.counters["successful_update_base_exposures"] += len(batch.logical_indices)
            self.counters["successful_update_view_exposures"] += 3 * len(batch.logical_indices)
            for name in self.enabled_tasks:
                self.counters["valid_labels"][name] += int(loss.counts.get(name, 0))
        else:
            # No backwards, AdamW decay, controller observation, or replacement.
            norm = torch.zeros(())
            self.counters["zero_label_batches"] += 1
        if scheduled is None:
            # Zero-label consumption advances only the committed data clock.
            state = self.controller.state_dict()
            group_budget = {g: self.policy.group_weights[g] * state["group_state"][g]["multiplier"]
                            for g in self.strategy.groups}
            strategy_metrics = self.strategy.factors(exposure_start, len(batch.logical_indices), group_budget)
        else:
            strategy_metrics = scheduled.metrics
        row = {"train/optimizer_updates": self.counters["optimizer_updates"],
               "train/consumed_batches": self.counters["consumed_batches"] + 1,
               "train/base_exposures": self.counters["consumed_base_exposures"] + len(batch.logical_indices),
               "train/view_exposures": self.counters["consumed_view_exposures"] + 3 * len(batch.logical_indices),
               "train/zero_label_batch": int(not observed), "train/zero_label_batches": self.counters["zero_label_batches"],
               "train/base_batch_size": len(batch.logical_indices), "train/native_atoms": sum(batch.native_atom_counts),
               "train/max_native_atoms": max(batch.native_atom_counts),
               "train/padded_cost": batch.padded_cost(self.sampler.padded_cost_multiplier),
               "train/lr_used": lr_used, "train/true_gradient_norm": float(norm),
               "train/loss_fixed": float(loss.total.detach()),
               "train/loss_dynamic": float(balanced.total.detach()) if balanced is not None else 0.0,
               "train/step_seconds": time.monotonic() - start,
               "train/epoch": self.sampler.epoch, "train/first_logical_ordinal": batch.logical_indices[0]}
        row.update({"strategy/name": self.strategy.name,
                    "strategy/recipe_sha256": strategy_metrics["recipe_sha256"],
                    "strategy/phase": strategy_metrics["phase"],
                    "strategy/exposure_start": strategy_metrics["exposure_start"],
                    "strategy/exposure_stop": strategy_metrics["exposure_stop"],
                    "strategy/early_base_records": strategy_metrics["early_base_records"],
                    "strategy/late_base_records": strategy_metrics["late_base_records"],
                    "strategy/objective_applied": int(scheduled is not None),
                    "train/loss_postscheduled": float(scheduled.total.detach()) if scheduled is not None else 0.0,
                    "strategy/extra_probe_seconds": strategy_metrics.get("additional_autograd_probe_seconds", 0.0)})
        for group in self.strategy.groups:
            row["strategy/nominal_factor/" + group] = strategy_metrics["nominal_factors"][group]
            row["strategy/effective_outer_factor/" + group] = strategy_metrics["effective_outer_factors"][group]
        if scheduled is not None:
            for group, value in (strategy_metrics.get("measured_postscheduled_group_gradient_norms") or {}).items():
                row["strategy/postscheduled_group_gradient_norm/" + group] = value
        # This true optimizer norm is on the post-scheduled total. Scalar group
        # norms are never summed to fabricate a shared-total gradient norm.
        if self.device.type == "cuda":
            row.update({"memory/allocated_bytes": torch.cuda.memory_allocated(0),
                        "memory/reserved_bytes": torch.cuda.memory_reserved(0),
                        "memory/max_allocated_bytes": torch.cuda.max_memory_allocated(0)})
        calibration = balanced is not None and any(value["observed"] and not value["scale_frozen"]
                                                     for value in balanced.metrics["tasks"].values())
        probe = balanced is not None and balanced.metrics["probe_performed"]
        if calibration or probe or update % self.config["metric_interval"] == 0:
            row.update(loss.scalar_metrics(prefix="train/"))
            if balanced is not None:
                # Full final leaf coefficients follow the existing measurement
                # cadence; group factors and committed exposure are logged on
                # every batch, including all-missing consumption.
                for task, coefficient in scheduled.coefficients.items():
                    row["strategy/final_task_coefficient/" + task] = coefficient
                for name in self.enabled_tasks:
                    values = balanced.metrics["tasks"][name]
                    for field in ("scale", "observations", "multiplier", "scale_frozen"):
                        row["balance/" + field + "/" + name] = int(values[field]) if field == "scale_frozen" else values[field]
                    if name in balanced.normalized:
                        row["balance/normalized/" + name] = float(balanced.normalized[name].detach())
                    if name in balanced.coefficients:
                        row["balance/coefficient/" + name] = balanced.coefficients[name]
                row["balance/probe_performed"] = int(balanced.metrics["probe_performed"])
                for group, value in balanced.metrics["group_multipliers"].items():
                    row["balance/group_multiplier/" + group] = value
                for field in ("measured_raw_gradient_norms", "measured_normalized_gradient_norms",
                              "measured_weighted_gradient_norms", "measured_group_gradient_norms"):
                    for name, value in (balanced.metrics[field] or {}).items():
                        row["balance/" + field + "/" + name] = value
                measured = balanced.metrics["measured_weighted_gradient_norms"] or {}
                denominator = math.fsum(measured.values())
                for name, value in measured.items():
                    row["balance/subset_leaf_norm_sum_share/" + name] = value / denominator if denominator else 0.0
        try:
            self._log(row)
        except BaseException:
            self.status = "tracking_failed_after_consumption_attempt"
            raise
        self.sampler.commit_batch(batch.logical_indices)
        self.counters["consumed_batches"] += 1
        self.counters["consumed_base_exposures"] += len(batch.logical_indices)
        self.counters["consumed_view_exposures"] += 3 * len(batch.logical_indices)
        self.scheduler.set_consumed(self.counters["consumed_base_exposures"])

    def _validate(self, scope, sampler, loader):
        _require(scope in {"routine", "full"} and sampler.index.role == "validation", "Validation must use the declared validation role")
        binding = self.config["bindings"][scope + "_validation_manifest_sha256"]
        _require(sampler.index.content_sha256 == binding, "Validation view differs from the frozen membership")
        original = self._original_unit_evaluator()
        if self.validation_state is None:
            self.validation_state = {"scope": scope, "at_base_exposure": self.counters["consumed_base_exposures"],
                "at_optimizer_update": self.counters["optimizer_updates"], "sampler": sampler.state_dict(),
                "sums": {n: 0.0 for n in self.enabled_tasks}, "counts": {n: 0 for n in self.enabled_tasks}}
            if original is not None:
                self.validation_state["original_unit_meter_state"] = original.state_dict()
        else:
            _require(self.validation_state["scope"] == scope, "Pending validation scope differs")
            sampler.load_state_dict(self.validation_state["sampler"])
            if original is not None:
                original.load_state_dict(self.validation_state["original_unit_meter_state"])
        modes = {module: module.training for module in self.model.modules()}
        rng = _rng(self.device)
        state_before = checkpoint_content_sha256({"model": _copy_cpu(self.model.state_dict())})
        controller_before = self.controller.state_dict()
        self.model.eval()
        iterator = None
        try:
            with torch.no_grad():
                iterator = iter(loader)
                for batch in iterator:
                    if self._remaining() <= self.config["caps"]["finalization_reserve_seconds"]:
                        return False
                    expected = sampler._next(sampler._cursor)
                    _require(expected is not None and list(batch.logical_indices) == expected[0], "Validation prefetch differs from its real cursor")
                    actual = batch.encoder_batch.to(self.device, non_blocking=True)
                    if original is None:
                        result = self._loss(actual)
                    else:
                        result, outputs = self._loss(actual, return_outputs=True)
                        original.add(actual, outputs)
                    for name in self.enabled_tasks:
                        count = int(result.counts.get(name, 0))
                        if count:
                            value = float(result.raw[name])
                            _require(math.isfinite(value), "Nonfinite observed validation loss")
                            self.validation_state["sums"][name] += value * count
                            self.validation_state["counts"][name] += count
                    sampler.commit_batch(batch.logical_indices)
                    self.validation_state["sampler"] = sampler.state_dict()
                    if original is not None:
                        self.validation_state["original_unit_meter_state"] = original.state_dict()
        finally:
            try:
                if iterator is not None:
                    close_prefetch_iterator(iterator)
            finally:
                for module, mode in modes.items():
                    module.training = mode
                torch.set_rng_state(rng["cpu"])
                if rng["cuda"] is not None:
                    torch.cuda.set_rng_state(rng["cuda"], 0)
                _require(state_before == checkpoint_content_sha256({"model": _copy_cpu(self.model.state_dict())})
                         and controller_before == self.controller.state_dict(), "Validation changed model/buffers or dynamic controller state")
        _require(sampler.samples_consumed == len(sampler.index), "Validation ended before exact complete coverage")
        values = {name: (self.validation_state["sums"][name] / count if count else None)
                  for name, count in self.validation_state["counts"].items()}
        # Fixed complete task/group denominators; unavailable leaves are reported
        # rather than silently turned into model-success losses or best scores.
        complete = all(value is not None for value in values.values())
        score = None
        if complete:
            groups = []
            for group, names in GROUP_TASKS.items():
                if group in self.variant:
                    denominator = math.fsum(self.policy.task_weights[n] for n in names)
                    groups.append(self.policy.group_weights[group] * math.fsum(
                        self.policy.task_weights[n] * values[n] / self.config["validation"]["task_scales"][n]
                        for n in names) / denominator)
            score = math.fsum(groups) / math.fsum(self.policy.group_weights[g] for g in GROUP_TASKS if g in self.variant)
            _require(math.isfinite(score), "Fixed validation macro is nonfinite")
        report = {"scope": scope, "manifest_sha256": binding, "base_exposure": self.counters["consumed_base_exposures"],
                  "optimizer_update": self.counters["optimizer_updates"], "consumed_bases": sampler.samples_consumed,
                  "leaf_losses": values, "valid_labels": deepcopy(self.validation_state["counts"]),
                  "criterion": self.config["validation"]["criterion"], "criterion_value": score,
                  "status": "COMPLETE" if complete else "COMPLETE_WITH_UNAVAILABLE_TASKS"}
        if original is not None:
            report["original_unit_metrics"] = original.result()
            report["original_unit_meter_state"] = original.state_dict()
        row = {"validation/base_exposure": report["base_exposure"], "validation/optimizer_updates": report["optimizer_update"],
               "validation/consumed_bases": report["consumed_bases"], "validation/full": int(scope == "full"),
               "validation/all_tasks_available": int(complete)}
        if score is not None:
            row["validation/fixed_macro"] = score
        for name, value in values.items():
            row["validation/count/" + name] = report["valid_labels"][name]
            if value is not None:
                row["validation/loss/" + name] = value
        if original is not None:
            row["validation/original/unseen_charge_element_atoms"] = original.unseen_charge_atoms
            for target, estimates in report["original_unit_metrics"]["targets"].items():
                for estimate, metrics in estimates.items():
                    prefix = "validation/original/" + target + "/" + estimate + "/"
                    row[prefix + "available"] = int("count" in metrics and metrics["count"] > 0)
                    for field in ("count", "mae", "rmse", "accuracy", "macro_f1_present_classes"):
                        if metrics.get(field) is not None:
                            row[prefix + field] = metrics[field]
        self._log(row)
        self.last_validation = report
        if score is not None and scope == "routine" and (self.best_validation is None or score < self.best_validation["criterion_value"]):
            self.best_validation = deepcopy(report)
        self.validation_state = None
        return True

    def fit(self, training_loader, *, validation_factory, checkpoint_callback=None,
            checkpoint_every_batches=1000, segment_started_at=None):
        """Consume up to the segment wall reserve; resume any partial validation.

        ``validation_factory(scope)`` creates the declared metadata-bound compact
        sampler/loader without choosing samples by labels or scores. Checkpoint
        callbacks occur only at fully committed model+log+sampler boundaries.
        """
        _integer(checkpoint_every_batches, "checkpoint interval", 1)
        _require(self.status in {"partial", "complete"}, "Failed live state cannot be resumed/exported")
        if self.status == "complete":
            return self.result()
        now = time.monotonic()
        _require(segment_started_at is None or type(segment_started_at) in (int, float)
                 and math.isfinite(segment_started_at) and 0 <= segment_started_at <= now,
                 "Invalid actual segment clock")
        self._clock_started = now if segment_started_at is None else segment_started_at
        previous = self.counters["total_wall_seconds"]
        try:
            while True:
                if self._remaining() <= self.config["caps"]["finalization_reserve_seconds"]:
                    break
                self._check_epoch_accounting(self.sampler, self.completed_epoch_batches, self.counters)
                epoch_end = self.sampler.samples_consumed == len(self.sampler.index)
                terminal = epoch_end and self.sampler.epoch + 1 == self.epochs
                boundary_checked = (self.last_validation is not None
                    and self.last_validation["scope"] == "routine"
                    and self.last_validation["base_exposure"] == self.counters["consumed_base_exposures"])
                boundary_due = epoch_end and not terminal and not boundary_checked
                if (self.validation_state is not None or terminal or boundary_due
                        or self.counters["consumed_base_exposures"] >= self.next_validation_exposure):
                    scope = self.validation_state["scope"] if self.validation_state else ("full" if terminal else "routine")
                    sampler, loader = validation_factory(scope)
                    if not self._validate(scope, sampler, loader):
                        break
                    if terminal and scope == "full":
                        self.status = "complete"
                    else:
                        self.next_validation_exposure = self.counters["consumed_base_exposures"] + self.config["validation"]["every_base_exposures"]
                    if checkpoint_callback is not None:
                        checkpoint_callback(self, "validation")
                    if terminal and scope == "full":
                        break
                    if terminal:
                        continue  # A resumed pending routine check is not the FINAL full check.
                if epoch_end:
                    self._advance_training_epoch()
                    if checkpoint_callback is not None:
                        checkpoint_callback(self, "latest")
                iterator = iter(training_loader)
                budget_stop = False
                before_consumption = self.counters["consumed_base_exposures"]
                try:
                    for batch in iterator:
                        if self._remaining() <= self.config["caps"]["finalization_reserve_seconds"]:
                            budget_stop = True
                            break
                        self._consume(batch)
                        if checkpoint_callback is not None and self.counters["consumed_batches"] % checkpoint_every_batches == 0:
                            checkpoint_callback(self, "latest")
                        if self.counters["consumed_base_exposures"] >= self.next_validation_exposure:
                            break
                finally:
                    close_prefetch_iterator(iterator)
                if budget_stop:
                    break
                _require(self.sampler.samples_consumed <= len(self.sampler.index), "Training exposure exceeds its current epoch")
                _require(self.counters["consumed_base_exposures"] > before_consumption,
                         "Training iterator ended without committed exposure progress")
        except BaseException:
            if self.status != "tracking_failed_after_consumption_attempt":
                self.status = "failed"
            raise
        finally:
            self.counters["total_wall_seconds"] = previous + time.monotonic() - self._clock_started
            self._clock_started = None
        return self.result()

    def result(self):
        counters = deepcopy(self.counters)
        if self._clock_started is not None:
            counters["total_wall_seconds"] += time.monotonic() - self._clock_started
        result = {"schema_version": "phase1_full_corpus_segment_result_v1", "status": self.status,
                "counters": counters, "sampler": self.sampler.state_dict(),
                "pending_validation": self.validation_state is not None,
                "last_validation": deepcopy(self.last_validation), "best_validation": deepcopy(self.best_validation),
                "endpoint_encoder_sha256": backbone_state_hash(self.model), "tracking": deepcopy(self.tracking),
                "source_sha256": self.config["bindings"]["source_sha256"],
                "strategy": self.strategy.config_dict()}
        if self.epochs > 1:
            result["epoch_coverage"] = {"planned_epochs": self.epochs,
                "total_planned_base_exposures": self.total_base_exposures,
                "total_planned_view_exposures": 3 * self.total_base_exposures,
                "active_epoch": self.sampler.epoch,
                "completed_epoch_batches": self.completed_epoch_batches.copy()}
        return result

    def checkpoint(self):
        _require(self.status in {"partial", "complete"}, "Failure state is not a successful resumable checkpoint")
        counters = self.result()["counters"]
        payload = {"schema_version": CHECKPOINT, "config": deepcopy(self.config),
             "config_sha256": canonical_hash(self.config), "model_config": self.model.config_dict(),
             "initial_model_sha256": self.initial_model_hash, "model_state": _copy_cpu(self.model.state_dict()),
             "optimizer_state": _copy_cpu(self.optimizer.state_dict()), "scheduler_state": self.scheduler.state_dict(),
             "controller_state": self.controller.state_dict(), "sampler_state": self.sampler.state_dict(),
             "rng_state": _rng(self.device), "counters": counters, "tracking": deepcopy(self.tracking),
             "next_validation_exposure": self.next_validation_exposure, "validation_state": deepcopy(self.validation_state),
             "last_validation": deepcopy(self.last_validation), "best_validation": deepcopy(self.best_validation),
             "status": self.status}
        if self.epochs > 1:
            payload["completed_epoch_batches"] = self.completed_epoch_batches.copy()
        payload["checkpoint_content_sha256"] = checkpoint_content_sha256(payload)
        return payload

    def load_checkpoint(self, payload, *, checkpoint_file_sha256, validation_sampler_factory=None):
        """Fresh receiver only; malformed late optimizer/RNG rejects before live changes."""
        _require(self.counters["optimizer_updates"] == 0 and self.sampler.samples_consumed == 0
                 and self.tracking["parent_run_id"] is None, "Resume receiver must be fresh")
        reference = self.checkpoint()
        _require(isinstance(payload, dict) and set(payload) == set(reference)
                 and payload["schema_version"] == CHECKPOINT
                 and payload["checkpoint_content_sha256"] == checkpoint_content_sha256(payload), "Checkpoint fields or typed content seal differ")
        for key in ("config", "config_sha256", "model_config", "initial_model_sha256"):
            _require(payload[key] == reference[key], "Resume scientific/source/data/fit/init recipe differs: " + key)
        _require(payload["status"] in {"partial", "complete"}, "Only successful committed states are resumable")
        counters = payload["counters"]
        _require(isinstance(counters, dict) and set(counters) == set(self.counters), "Resume counter fields differ")
        for name in counters.keys() - {"valid_labels", "optimizer_parameter_updates", "total_wall_seconds"}:
            _integer(counters[name], "resume " + name)
        _finite(counters["total_wall_seconds"], "cumulative wall")
        _require(counters["total_wall_seconds"] >= 0 and counters["consumed_view_exposures"] == 3 * counters["consumed_base_exposures"]
                 and counters["successful_update_view_exposures"] == 3 * counters["successful_update_base_exposures"]
                 and counters["optimizer_updates"] + counters["zero_label_batches"] == counters["consumed_batches"], "Resume consumption/update clocks disagree")
        _require(isinstance(counters["valid_labels"], dict) and set(counters["valid_labels"]) == set(self.enabled_tasks), "Resume task counts differ")
        for value in counters["valid_labels"].values():
            _integer(value, "valid label exposure")
        _require(isinstance(counters["optimizer_parameter_updates"], dict)
                 and set(counters["optimizer_parameter_updates"]) == set(self.counters["optimizer_parameter_updates"]), "Parameter-update inventory differs")
        for name, count in counters["optimizer_parameter_updates"].items():
            _integer(count, "parameter update counter")
            _require(count <= counters["optimizer_updates"], "Parameter step exceeds global updates")
            if name.startswith("backbone."):
                _require(count == counters["optimizer_updates"], "H0 parameter step differs from successful updates")
        candidate = deepcopy(self.model).cpu()
        _state_candidate(candidate, payload["model_state"])
        optimizer = _optimizer(candidate, self.config["optimizer"])
        scheduler = BaseExposureCosine(optimizer, total_base_exposures=self.total_base_exposures, **self.config["schedule"])
        _optimizer_candidate(optimizer, payload["optimizer_state"], counters["optimizer_updates"],
              {id(p): counters["optimizer_parameter_updates"][name] for name, p in candidate.named_parameters()})
        scheduler.load_state_dict(payload["scheduler_state"])
        _require(scheduler.consumed == counters["consumed_base_exposures"], "Scheduler is not on the committed exposure clock")
        _require([float(g["lr"]) for g in optimizer.param_groups] == [float(g["lr"]) for g in payload["optimizer_state"]["param_groups"]], "Saved optimizer/scheduler LR disagree")
        controller = deepcopy(self.controller)
        controller.load_state_dict(payload["controller_state"])
        _require(controller.state_dict()["next_update"] == counters["optimizer_updates"], "Controller cursor differs from optimizer updates")
        sampler = copy(self.sampler)
        epoch = _integer(payload["sampler_state"].get("epoch"), "resume epoch")
        _require(epoch < self.epochs, "Resume epoch exceeds the frozen training horizon")
        sampler.epoch, sampler._block_cache = epoch, None
        sampler.load_state_dict(payload["sampler_state"])
        completed_batches = payload.get("completed_epoch_batches", [])
        self._check_epoch_accounting(sampler, completed_batches, counters)
        # Reconstruct prior epoch cardinalities from compact metadata only, never
        # LMDB/labels, to reject a resealed invented global-batch ledger.
        for prior_epoch, expected_batches in enumerate(completed_batches):
            prior = copy(self.sampler)
            prior.epoch, prior._block_cache = prior_epoch, None
            cursor, batches, samples = (0, 0), 0, 0
            while (batch_info := prior._next(cursor)) is not None:
                logicals, cursor = batch_info
                batches += 1
                samples += len(logicals)
            _require(samples == len(prior.index) and batches == expected_batches,
                     "Completed-epoch batch ledger differs from the actual compact order")
        _require(counters["successful_update_base_exposures"] <= counters["consumed_base_exposures"]
                 and counters["optimizer_updates"] <= counters["consumed_batches"], "Successful exposure exceeds consumed data")
        _validate_rng(payload["rng_state"], self.device)
        _integer(payload["next_validation_exposure"], "next validation exposure")
        old_tracker = payload["tracking"]
        _require(isinstance(old_tracker, dict) and set(old_tracker) == set(self.tracking)
                 and type(old_tracker["run_id"]) is str and old_tracker["run_id"]
                 and type(old_tracker["run_path"]) is str and old_tracker["run_path"]
                 and old_tracker["run_id"] != self.tracker.id, "A resumed offline segment must have a new real run ID")
        _integer(old_tracker["next_step"], "parent tracker cursor")
        validation = payload["validation_state"]
        self._check_original_unit_report(payload["last_validation"])
        self._check_original_unit_report(payload["best_validation"])
        if payload["status"] == "complete":
            _require(sampler.epoch + 1 == self.epochs and sampler.samples_consumed == len(sampler.index)
                     and counters["consumed_base_exposures"] == self.total_base_exposures and validation is None,
                     "Complete resume requires exact complete training coverage and no pending validation")
            report = payload["last_validation"]
            _require(isinstance(report, dict) and set(report) == {
                         "scope", "manifest_sha256", "base_exposure", "optimizer_update", "consumed_bases",
                         "leaf_losses", "valid_labels", "criterion", "criterion_value", "status"}
                         | ({"original_unit_metrics", "original_unit_meter_state"} if self.original_unit_baselines is not None else set())
                     and report.get("scope") == "full"
                     and report.get("manifest_sha256") == self.config["bindings"]["full_validation_manifest_sha256"]
                     and type(report.get("base_exposure")) is int and type(report.get("optimizer_update")) is int
                     and report.get("base_exposure") == counters["consumed_base_exposures"]
                     and report.get("optimizer_update") == counters["optimizer_updates"]
                     and report.get("criterion") == self.config["validation"]["criterion"]
                     and report.get("status") in {"COMPLETE", "COMPLETE_WITH_UNAVAILABLE_TASKS"}
                     and callable(validation_sampler_factory),
                     "Complete resume requires its closed full-validation report and actual frozen-view sampler factory")
            terminal_validation = validation_sampler_factory("full")
            _require(isinstance(terminal_validation, BlockAtomBatchSampler)
                     and terminal_validation.index.role == "validation"
                     and terminal_validation.index.content_sha256 == self.config["bindings"]["full_validation_manifest_sha256"]
                     and type(report.get("consumed_bases")) is int
                     and report["consumed_bases"] == len(terminal_validation.index),
                     "Complete resume full-validation coverage differs from its actual frozen view")
            _require(isinstance(report["leaf_losses"], dict) and isinstance(report["valid_labels"], dict)
                     and set(report["leaf_losses"]) == set(report["valid_labels"]) == set(self.enabled_tasks),
                     "Complete resume full-validation task inventory differs")
            for name in self.enabled_tasks:
                count = _integer(report["valid_labels"][name], "closed validation count")
                value = report["leaf_losses"][name]
                _require(value is None if count == 0 else value is not None and _finite(value, "closed validation loss") >= 0,
                         "Complete resume full-validation losses disagree with availability counts")
            available = all(value is not None for value in report["leaf_losses"].values())
            _require(report["status"] == ("COMPLETE" if available else "COMPLETE_WITH_UNAVAILABLE_TASKS")
                     and (report["criterion_value"] is not None and _finite(report["criterion_value"], "closed validation criterion") >= 0
                          if available else report["criterion_value"] is None),
                     "Complete resume full-validation criterion disagrees with availability")
        if validation is not None:
            _require(isinstance(validation, dict) and set(validation) == {"scope", "at_base_exposure", "at_optimizer_update", "sampler", "sums", "counts"}
                         | ({"original_unit_meter_state"} if self.original_unit_baselines is not None else set())
                     and validation["scope"] in {"routine", "full"}
                     and validation["at_base_exposure"] == counters["consumed_base_exposures"]
                     and validation["at_optimizer_update"] == counters["optimizer_updates"], "Pending validation does not belong to this exact endpoint")
            for name in ("sums", "counts"):
                _require(set(validation[name]) == set(self.enabled_tasks), "Pending validation task set differs")
            for name in self.enabled_tasks:
                _integer(validation["counts"][name], "pending validation count")
                _require(_finite(validation["sums"][name], "pending validation sum") >= 0, "Negative validation sum")
            _require(payload["status"] == "partial" and callable(validation_sampler_factory),
                     "Pending validation requires its actual frozen-view sampler factory")
            pending = validation_sampler_factory(validation["scope"])
            _require(isinstance(pending, BlockAtomBatchSampler) and pending.index.role == "validation"
                     and pending.index.content_sha256 == self.config["bindings"][validation["scope"] + "_validation_manifest_sha256"],
                     "Pending validation sampler belongs to another view")
            pending.load_state_dict(validation["sampler"])
            if self.original_unit_baselines is not None:
                try:
                    original = self._original_unit_evaluator()
                    original.load_state_dict(validation["original_unit_meter_state"])
                except (ValueError, TypeError, KeyError, OverflowError) as exc:
                    raise FullCorpusTrainingError("Invalid pending original-unit validation state") from exc
        # No live weights, moments, RNG, cursor or tracking fields were changed above.
        self.model.load_state_dict(_copy_cpu(candidate.state_dict()), strict=True)
        self.optimizer.load_state_dict(_copy_cpu(optimizer.state_dict()))
        self.scheduler.load_state_dict(scheduler.state_dict())
        self.controller = controller
        self.sampler.epoch, self.sampler._block_cache = sampler.epoch, None
        self.sampler.load_state_dict(sampler.state_dict())
        torch.set_rng_state(payload["rng_state"]["cpu"].clone())
        if self.device.type == "cuda":
            torch.cuda.set_rng_state(payload["rng_state"]["cuda"].clone(), 0)
        self.counters = deepcopy(counters)
        self.completed_epoch_batches = completed_batches.copy()
        self.validation_state = deepcopy(validation)
        self.last_validation, self.best_validation = deepcopy(payload["last_validation"]), deepcopy(payload["best_validation"])
        self.next_validation_exposure, self.status = payload["next_validation_exposure"], payload["status"]
        self.tracking["parent_run_id"], self.tracking["parent_checkpoint_sha256"] = old_tracker["run_id"], checkpoint_file_sha256
