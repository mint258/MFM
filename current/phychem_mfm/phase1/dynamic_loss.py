"""Train-only calibrated loss scales and bounded hierarchical EMA gradient balancing.

This is an explicit EMA heuristic, NOT the published GradNorm optimizer. It
changes only scalar loss coefficients, not tasks, masks, heads or gradient
directions. Norms on a declared shared-parameter subset are diagnostic proxies;
bounded coefficients cannot guarantee equal full-backbone contributions.
Calibration uses the first observed training losses and then freezes each
scale. Validation losses must never update this controller. Save its state at
the same successful optimizer-update boundary as model/optimizer/RNG state.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
import hashlib
import json
import math

import torch
from torch import Tensor

from .objectives import GROUP_TASKS, Phase1LossPolicy, canonical_variant

METHOD = "phase1_calibrated_hierarchical_ema_gradient_v1"


class DynamicLossError(ValueError):
    pass


def _hash(value):
    try:
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    except (TypeError, ValueError, OverflowError, RecursionError) as error:
        raise DynamicLossError("Controller metadata must be finite acyclic JSON") from error
    return hashlib.sha256(raw).hexdigest()


def _finite(value, name, *, positive=False):
    if type(value) not in (int, float) or not math.isfinite(value) or (positive and value <= 0):
        raise DynamicLossError(f"{name} must be finite{' and positive' if positive else ''}")
    return float(value)


def _integer(value, name, minimum=0):
    if type(value) is not int or value < minimum:
        raise DynamicLossError(f"{name} must be an integer >= {minimum}")
    return value


@dataclass(frozen=True)
class DynamicLossConfig:
    calibration_observations: int = 8
    scale_beta: float = 0.9
    gradient_beta: float = 0.9
    weight_beta: float = 0.8
    balance_interval: int = 32
    scale_floor: float = 1e-3
    scale_ceiling: float = 1e6
    gradient_floor: float = 1e-12
    min_multiplier: float = 0.25
    max_multiplier: float = 4.0

    def __post_init__(self):
        for name in ("calibration_observations", "balance_interval"):
            _integer(getattr(self, name), name, 1)
        if self.calibration_observations > 1024 or self.balance_interval > 100000:
            raise DynamicLossError("Calibration/interval exceeds supported bounded recipe")
        for name in ("scale_beta", "gradient_beta", "weight_beta"):
            value = _finite(getattr(self, name), name)
            if not 0 <= value < 1:
                raise DynamicLossError(f"{name} must lie in [0,1)")
        for name in ("scale_floor", "scale_ceiling", "gradient_floor", "min_multiplier", "max_multiplier"):
            _finite(getattr(self, name), name, positive=True)
        if not self.scale_floor <= self.scale_ceiling or not self.min_multiplier <= 1 <= self.max_multiplier:
            raise DynamicLossError("Scale bounds and multiplier bounds must contain a valid recipe")


@dataclass(frozen=True)
class BalancedLossResult:
    total: Tensor
    normalized: dict[str, Tensor]
    weighted: dict[str, Tensor]
    coefficients: dict[str, float]
    metrics: dict


def _norm(vector):
    value = float(torch.linalg.vector_norm(vector.detach().double()))
    if not math.isfinite(value):
        raise DynamicLossError("Nonfinite measured shared gradient norm")
    return value


def _vector(loss, parameters):
    derivatives = torch.autograd.grad(loss, parameters, retain_graph=True,
                                      create_graph=False, allow_unused=True)
    if all(value is None for value in derivatives):
        raise DynamicLossError("Observed task has no connected declared shared parameter")
    chunks = [torch.zeros_like(param).reshape(-1) if value is None else value.detach().reshape(-1)
              for param, value in zip(parameters, derivatives)]
    vector = torch.cat(chunks).double()
    if not bool(torch.isfinite(vector).all()):
        raise DynamicLossError("Nonfinite measured shared gradient")
    return vector


def _ema(old, new, beta):
    return new if old is None else beta * old + (1 - beta) * new


def _project(current, desired, base, lower, upper):
    """Keep unobserved weights fixed and the complete base-weighted sum fixed."""
    if not desired:
        return dict(current)
    adjustable = tuple(desired)
    complete = math.fsum(base.values())
    budget = complete - math.fsum(base[name] * value for name, value in current.items() if name not in desired)
    minimum = math.fsum(base[name] * lower for name in adjustable)
    maximum = math.fsum(base[name] * upper for name in adjustable)
    tolerance = 1e-12 * max(1.0, complete)
    if budget < minimum - tolerance or budget > maximum + tolerance:
        raise DynamicLossError("Remaining fixed weight budget is genuinely outside feasible bounds")
    # A previously valid complete sum can leave a few ulps beyond a saturated
    # adjustable bound after subtraction. Match the existing sum tolerance;
    # otherwise a saturated fitted(hi) would never reach its rounded budget.
    budget = min(maximum, max(minimum, budget))
    def fitted(factor):
        return {name: min(upper, max(lower, desired[name] * factor)) for name in adjustable}
    lo, hi = 0.0, 1.0
    while math.fsum(base[name] * value for name, value in fitted(hi).items()) < budget:
        hi *= 2
        if not math.isfinite(hi):
            raise DynamicLossError("Cannot project finite positive dynamic weights")
    for _ in range(80):
        mid = (lo + hi) / 2
        if math.fsum(base[name] * value for name, value in fitted(mid).items()) < budget:
            lo = mid
        else:
            hi = mid
    return {**current, **fitted((lo + hi) / 2)}


class EMAGradientBalancer:
    def __init__(self, variant: str, shared_parameter_names: tuple[str, ...], *,
                 config: DynamicLossConfig | None = None, base_policy: Phase1LossPolicy | None = None):
        self.variant = canonical_variant(variant)
        if self.variant == "none":
            raise DynamicLossError("none has no optimizer supervision to balance")
        if (type(shared_parameter_names) is not tuple or not shared_parameter_names
                or any(type(name) is not str or not name for name in shared_parameter_names)
                or len(set(shared_parameter_names)) != len(shared_parameter_names)):
            raise DynamicLossError("Declare unique nonempty shared parameter names")
        self.shared_parameter_names = shared_parameter_names
        self.config = config or DynamicLossConfig()
        if not isinstance(self.config, DynamicLossConfig):
            raise DynamicLossError("config must be DynamicLossConfig")
        original = base_policy or Phase1LossPolicy()
        self.base_policy = Phase1LossPolicy(dict(original.group_weights), dict(original.task_weights))
        for name, value in (*self.base_policy.group_weights.items(), *self.base_policy.task_weights.items()):
            _finite(value, name + ".base_weight", positive=True)
        self.groups = tuple(group for group in GROUP_TASKS if group in self.variant)
        self.tasks = tuple(name for group in self.groups for name in GROUP_TASKS[group])
        self.next_update = 0
        self.task_state = {name: {"observations": 0, "scale": 1.0, "scale_frozen": False,
                                 "loss_ema": None, "initial_loss": None, "gradient_ema": None,
                                 "multiplier": 1.0, "last_observed_update": None,
                                 "last_probe_update": None} for name in self.tasks}
        self.group_state = {group: {"gradient_ema": None, "multiplier": 1.0,
                                   "last_probe_update": None} for group in self.groups}

    def state_dict(self):
        payload = {"schema_version": METHOD + "_state", "variant": self.variant,
                   "shared_parameter_names": list(self.shared_parameter_names),
                   "config": asdict(self.config), "base_policy": self.base_policy.to_dict(),
                   "next_update": self.next_update, "task_state": deepcopy(self.task_state),
                   "group_state": deepcopy(self.group_state)}
        payload["state_sha256"] = _hash(payload)
        return payload

    def load_state_dict(self, payload):
        if type(payload) is not dict or set(payload) != set(self.state_dict()):
            raise DynamicLossError("Incomplete dynamic controller checkpoint")
        candidate = deepcopy(payload)
        digest = candidate.pop("state_sha256")
        if type(digest) is not str or _hash(candidate) != digest:
            raise DynamicLossError("Dynamic controller checkpoint seal mismatch")
        expected = self.state_dict()
        for name in ("schema_version", "variant", "shared_parameter_names", "config", "base_policy"):
            if _hash(candidate[name]) != _hash(expected[name]):
                raise DynamicLossError(f"Dynamic checkpoint {name} binding mismatch")
        cursor = _integer(candidate["next_update"], "next_update")
        if type(candidate["task_state"]) is not dict or set(candidate["task_state"]) != set(self.tasks):
            raise DynamicLossError("Checkpoint task set differs from enabled supervision")
        if type(candidate["group_state"]) is not dict or set(candidate["group_state"]) != set(self.groups):
            raise DynamicLossError("Checkpoint group set differs from enabled supervision")
        for name, row in candidate["task_state"].items():
            if type(row) is not dict or set(row) != set(self.task_state[name]):
                raise DynamicLossError("Incomplete task EMA checkpoint")
            observations = _integer(row["observations"], "observations")
            if observations > cursor or type(row["scale_frozen"]) is not bool:
                raise DynamicLossError("Task observation/freeze checkpoint is inconsistent")
            if row["scale_frozen"] != (observations >= self.config.calibration_observations):
                raise DynamicLossError("Calibration freeze boundary mismatch")
            scale = _finite(row["scale"], "scale", positive=True)
            if not self.config.scale_floor <= scale <= self.config.scale_ceiling:
                # Unobserved state uses unit scale, which may lie outside explicit custom bounds.
                if observations or scale != 1.0:
                    raise DynamicLossError("Calibration scale exceeds declared bounds")
            for key in ("loss_ema", "initial_loss", "gradient_ema"):
                if row[key] is not None and _finite(row[key], key) < 0:
                    raise DynamicLossError("Negative EMA checkpoint")
            if (row["initial_loss"] is None) != (observations == 0) or (row["loss_ema"] is None) != (observations == 0):
                raise DynamicLossError("Missing observed-loss checkpoint")
            for key in ("last_observed_update", "last_probe_update"):
                if row[key] is not None and _integer(row[key], key) >= cursor:
                    raise DynamicLossError("Checkpoint EMA cursor is outside completed updates")
            if (row["last_observed_update"] is None) != (observations == 0):
                raise DynamicLossError("Observation cursor checkpoint mismatch")
            if observations and row["last_observed_update"] < observations - 1:
                raise DynamicLossError("Too many observations for the saved task cursor")
            if (row["gradient_ema"] is None) != (row["last_probe_update"] is None):
                raise DynamicLossError("Gradient EMA/probe cursor checkpoint mismatch")
            probe_cursor = row["last_probe_update"]
            if probe_cursor is not None and (probe_cursor > row["last_observed_update"]
                    or not (probe_cursor < self.config.calibration_observations or probe_cursor % self.config.balance_interval == 0)):
                raise DynamicLossError("Task probe cursor was not a scheduled observed update")
            if not observations and any(
                    row[key] != value for key, value in {"scale": 1.0, "multiplier": 1.0,
                                                       "gradient_ema": None, "last_probe_update": None}.items()):
                raise DynamicLossError("An unobserved task cannot have adapted state")
            self._validate_multiplier(row["multiplier"])
        for group, row in candidate["group_state"].items():
            if type(row) is not dict or set(row) != {"gradient_ema", "multiplier", "last_probe_update"}:
                raise DynamicLossError("Incomplete group EMA checkpoint")
            if row["gradient_ema"] is not None and _finite(row["gradient_ema"], "gradient_ema") < 0:
                raise DynamicLossError("Negative group gradient EMA")
            if row["last_probe_update"] is not None and _integer(row["last_probe_update"], "last_probe_update") >= cursor:
                raise DynamicLossError("Group EMA cursor is outside completed updates")
            if (row["gradient_ema"] is None) != (row["last_probe_update"] is None):
                raise DynamicLossError("Group gradient EMA/probe cursor mismatch")
            probe_cursor = row["last_probe_update"]
            if probe_cursor is not None and not (probe_cursor < self.config.calibration_observations
                                                or probe_cursor % self.config.balance_interval == 0):
                raise DynamicLossError("Group probe cursor was not scheduled")
            task_probes = [candidate["task_state"][name]["last_probe_update"] for name in GROUP_TASKS[group]
                           if candidate["task_state"][name]["last_probe_update"] is not None]
            if probe_cursor != (max(task_probes) if task_probes else None):
                raise DynamicLossError("Group probe cursor does not match its observed leaf probes")
            if row["last_probe_update"] is None and row["multiplier"] != 1.0:
                raise DynamicLossError("Unobserved group cannot have adapted weight")
            self._validate_multiplier(row["multiplier"])
        self._validate_sums(candidate["task_state"], candidate["group_state"])
        self.task_state, self.group_state, self.next_update = candidate["task_state"], candidate["group_state"], cursor

    def _validate_multiplier(self, value):
        if not self.config.min_multiplier <= _finite(value, "multiplier", positive=True) <= self.config.max_multiplier:
            raise DynamicLossError("Dynamic multiplier exceeds positive declared bounds")

    def _validate_sums(self, tasks, groups):
        sets = [(GROUP_TASKS[group], self.base_policy.task_weights, tasks) for group in self.groups]
        sets.append((self.groups, self.base_policy.group_weights, groups))
        for names, base, rows in sets:
            expected = math.fsum(base[name] for name in names)
            actual = math.fsum(base[name] * rows[name]["multiplier"] for name in names)
            if not math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12):
                raise DynamicLossError("Complete enabled weight sum drifted")

    def balance(self, loss_result, shared_parameters: tuple[Tensor, ...], *, update: int):
        _integer(update, "update")
        if update != self.next_update:
            raise DynamicLossError("Actual optimizer update must equal controller next_update")
        if (type(shared_parameters) is not tuple or len(shared_parameters) != len(self.shared_parameter_names)
                or len({id(value) for value in shared_parameters}) != len(shared_parameters)
                or any(not isinstance(value, Tensor) or not value.requires_grad or value.numel() == 0 for value in shared_parameters)):
            raise DynamicLossError("Shared tensors must match declared unique differentiable parameter names")
        if len({value.device for value in shared_parameters}) != 1:
            raise DynamicLossError("Shared parameter probe must use one device")
        if set(loss_result.raw) != set(self.tasks):
            raise DynamicLossError("Raw loss set must exactly match enabled leaf tasks")
        tasks, groups = deepcopy(self.task_state), deepcopy(self.group_state)
        observed = []
        for name in self.tasks:
            count = _integer(loss_result.counts.get(name), name + ".count")
            value = loss_result.raw[name]
            if not isinstance(value, Tensor) or value.ndim != 0 or value.device != shared_parameters[0].device:
                raise DynamicLossError("Leaf losses must be scalar tensors on the shared parameter device")
            magnitude = abs(float(value.detach()))
            if not math.isfinite(magnitude):
                raise DynamicLossError("Nonfinite raw task loss")
            if not count:
                if magnitude != 0 or value.requires_grad:
                    raise DynamicLossError("Missing tasks must retain detached zero without state updates")
                continue
            if not value.requires_grad:
                raise DynamicLossError("Observed task loss is detached from supervision")
            observed.append(name)
            row = tasks[name]
            if not row["scale_frozen"]:
                measured = min(self.config.scale_ceiling, max(self.config.scale_floor, magnitude))
                row["scale"] = measured if row["observations"] == 0 else _ema(row["scale"], measured, self.config.scale_beta)
            row["observations"] += 1
            row["scale_frozen"] = row["observations"] >= self.config.calibration_observations
            row["initial_loss"] = magnitude if row["initial_loss"] is None else row["initial_loss"]
            row["loss_ema"] = _ema(row["loss_ema"], magnitude, self.config.scale_beta)
            row["last_observed_update"] = update
        if not observed:
            raise DynamicLossError("No observed enabled task; do not perform a zero-label optimizer update")
        normalized = {name: value / tasks[name]["scale"] if name in observed else value
                      for name, value in loss_result.raw.items()}
        probe = update < self.config.calibration_observations or update % self.config.balance_interval == 0
        vectors = {}
        task_base = self.base_policy.task_weights
        group_base = self.base_policy.group_weights
        denominator_g = math.fsum(group_base[group] for group in self.groups)
        denominators = {group: math.fsum(task_base[name] for name in GROUP_TASKS[group]) for group in self.groups}
        if probe:
            for name in observed:
                vectors[name] = _vector(normalized[name], shared_parameters)
                group = next(group for group in self.groups if name in GROUP_TASKS[group])
                measured = _norm(vectors[name]) * task_base[name] / denominators[group]
                row = tasks[name]
                row["gradient_ema"] = _ema(row["gradient_ema"], measured, self.config.gradient_beta)
                row["last_probe_update"] = update
            for group in self.groups:
                names = GROUP_TASKS[group]
                adjustable = [name for name in names if name in vectors and _norm(vectors[name]) > self.config.gradient_floor
                              and tasks[name]["gradient_ema"] > self.config.gradient_floor]
                if not adjustable:
                    continue
                target = math.exp(math.fsum(math.log(tasks[name]["gradient_ema"]) for name in adjustable) / len(adjustable))
                desired = {name: math.exp(min(80.0, max(-80.0,
                                         self.config.weight_beta * math.log(tasks[name]["multiplier"])
                                          + (1 - self.config.weight_beta) * (math.log(target) - math.log(tasks[name]["gradient_ema"])))))
                           for name in adjustable}
                weights = _project({name: tasks[name]["multiplier"] for name in names}, desired,
                                   {name: task_base[name] for name in names}, self.config.min_multiplier, self.config.max_multiplier)
                for name in adjustable:
                    tasks[name]["multiplier"] = weights[name]
            current_group_vectors = {}
            for group in self.groups:
                present = [name for name in GROUP_TASKS[group] if name in vectors]
                if not present:
                    continue
                vector = sum((vectors[name] * task_base[name] * tasks[name]["multiplier"] / denominators[group]
                              for name in present), torch.zeros_like(vectors[present[0]]))
                current_group_vectors[group] = vector
                measured = _norm(vector) * group_base[group] / denominator_g
                groups[group]["gradient_ema"] = _ema(groups[group]["gradient_ema"], measured, self.config.gradient_beta)
                groups[group]["last_probe_update"] = update
            adjustable = [group for group in current_group_vectors if _norm(current_group_vectors[group]) > self.config.gradient_floor
                          and groups[group]["gradient_ema"] > self.config.gradient_floor]
            if adjustable:
                target = math.exp(math.fsum(math.log(groups[group]["gradient_ema"]) for group in adjustable) / len(adjustable))
                desired = {group: math.exp(min(80.0, max(-80.0,
                                          self.config.weight_beta * math.log(groups[group]["multiplier"])
                                           + (1 - self.config.weight_beta) * (math.log(target) - math.log(groups[group]["gradient_ema"])))))
                           for group in adjustable}
                weights = _project({group: groups[group]["multiplier"] for group in self.groups}, desired,
                                   {group: group_base[group] for group in self.groups}, self.config.min_multiplier, self.config.max_multiplier)
                for group in adjustable:
                    groups[group]["multiplier"] = weights[group]
        self._validate_sums(tasks, groups)
        coefficients = {}
        for group in self.groups:
            for name in GROUP_TASKS[group]:
                coefficients[name] = (task_base[name] * tasks[name]["multiplier"] / denominators[group]
                                      * group_base[group] * groups[group]["multiplier"] / denominator_g / tasks[name]["scale"])
                if not math.isfinite(coefficients[name]) or coefficients[name] <= 0:
                    raise DynamicLossError("Effective task coefficient must stay finite and positive")
                represented = loss_result.raw[name].new_tensor(coefficients[name])
                if not bool(torch.isfinite(represented)) or not bool(represented > 0):
                    raise DynamicLossError("Effective positive coefficient is not representable in the actual loss dtype")
        weighted = {name: loss_result.raw[name] * coefficients[name] for name in self.tasks}
        total = torch.stack(tuple(weighted.values())).sum()
        if not bool(torch.isfinite(total)) or not total.requires_grad:
            raise DynamicLossError("Dynamic aggregate must remain finite connected supervision")
        metrics = {"method": METHOD, "state": "NOT_FROZEN", "formal_eligible": False,
                   "update": update, "probe_performed": probe, "shared_parameter_names": list(self.shared_parameter_names),
                   "shared_probe_numel": sum(value.numel() for value in shared_parameters),
                   "normalization": "train_first_observed_calibration_ema_then_per_task_frozen_scale",
                   "denominators": {"groups": denominator_g, "tasks": denominators},
                   "tasks": {name: {"raw_loss": float(loss_result.raw[name].detach()),
                                    "normalized_loss": float(normalized[name].detach()),
                                    "valid_labels": loss_result.counts[name], "scale": tasks[name]["scale"],
                                    "scale_frozen": tasks[name]["scale_frozen"], "multiplier": tasks[name]["multiplier"],
                                    "coefficient": coefficients[name], "observed": name in observed,
                                    "relative_loss_ema": None if not tasks[name]["initial_loss"] else tasks[name]["loss_ema"] / tasks[name]["initial_loss"],
                                    "gradient_ema": tasks[name]["gradient_ema"], "observations": tasks[name]["observations"],
                                    "last_probe_update": tasks[name]["last_probe_update"]}
                             for name in self.tasks},
                   "group_multipliers": {group: groups[group]["multiplier"] for group in self.groups},
                   "measured_raw_gradient_norms": None, "measured_normalized_gradient_norms": None,
                   "measured_weighted_gradient_norms": None, "measured_group_gradient_norms": None,
                   "measured_total_gradient_norm": None,
                   "measured_fixed_task_gradient_norms": None,
                   "measured_normalized_only_task_gradient_norms": None,
                   "measured_fixed_total_gradient_norm": None,
                   "measured_normalized_only_total_gradient_norm": None,
                   "norm_estimation_recipe": "actual normalized-loss autograd; raw/weighted leaf norms scalar-rescaled from that vector; aggregate autograd measured independently",
                   "limits": "subset norms; positive bounded weights; no guarantee of equal full gradients or conflict removal"}
        if probe:
            metrics["measured_normalized_gradient_norms"] = {name: _norm(vectors[name]) for name in observed}
            metrics["measured_raw_gradient_norms"] = {name: _norm(vectors[name]) * tasks[name]["scale"] for name in observed}
            metrics["measured_weighted_gradient_norms"] = {name: _norm(vectors[name]) * tasks[name]["scale"] * coefficients[name] for name in observed}
            metrics["measured_group_gradient_norms"] = {
                group: _norm(sum((vectors[name] * tasks[name]["scale"] * coefficients[name]
                                 for name in GROUP_TASKS[group] if name in vectors), torch.zeros_like(next(iter(vectors.values())))))
                for group in self.groups}
            metrics["measured_total_gradient_norm"] = _norm(_vector(total, shared_parameters))
            fixed_coefficients = {name: task_base[name] / denominators[group] * group_base[group] / denominator_g
                                  for group in self.groups for name in GROUP_TASKS[group]}
            metrics["measured_fixed_task_gradient_norms"] = {
                name: _norm(vectors[name]) * tasks[name]["scale"] * fixed_coefficients[name] for name in observed}
            metrics["measured_normalized_only_task_gradient_norms"] = {
                name: _norm(vectors[name]) * fixed_coefficients[name] for name in observed}
            metrics["measured_fixed_total_gradient_norm"] = _norm(sum(
                (vectors[name] * tasks[name]["scale"] * fixed_coefficients[name] for name in observed),
                torch.zeros_like(next(iter(vectors.values())))))
            metrics["measured_normalized_only_total_gradient_norm"] = _norm(sum(
                (vectors[name] * fixed_coefficients[name] for name in observed),
                torch.zeros_like(next(iter(vectors.values())))))
        # Validate every reported scalar before committing any controller mutation.
        _hash(metrics)
        self.task_state, self.group_state, self.next_update = tasks, groups, update + 1
        return BalancedLossResult(total, normalized, weighted, coefficients, metrics)
