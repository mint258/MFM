"""Draft positive SDP curriculum on committed base-structure exposure.

Joint returns the original dynamic objective without another tensor operation.
The auxiliary recipe preserves nominal full-pass integrals and the *current*
complete group budget. It does not promise equal adaptive coefficient integrals,
equal gradients, or absence of future feedback through the changed model.
No targets, files of samples, sampler, optimizer, or controller state are read.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from pathlib import Path

import torch

from .formal_gate import canonical_sha256 as canonical_hash
from .objectives import GROUP_TASKS, PHASE1_VARIANTS, canonical_variant

JOINT = "joint"
POSITIVE = "sdp_positive_nominal_equal_integral_v2"
STRATEGIES = (JOINT, POSITIVE)
SCHEMA = "phase1_positive_base_exposure_strategy_v2"


class PositiveStrategyError(ValueError):
    pass


def _require(ok, message):
    if not ok:
        raise PositiveStrategyError(message)


def _integer(value, name, minimum=0):
    _require(type(value) is int and minimum <= value < 2 ** 63, name + " is not a valid bounded integer")
    return value


def _positive(value, name):
    try:
        ok = type(value) in (int, float) and math.isfinite(value) and value > 0
        result = float(value) if ok else 0.0
    except (OverflowError, ValueError):
        ok, result = False, 0.0
    _require(ok, name + " must be finite and positive")
    return result


def _sum(values):
    try:
        return math.fsum(values)
    except (ValueError, OverflowError) as exc:
        raise PositiveStrategyError("Positive budget accumulation overflowed") from exc


def implementation_sha256():
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


@dataclass(frozen=True)
class StrategyLoss:
    total: torch.Tensor
    weighted: dict[str, torch.Tensor]
    coefficients: dict[str, float]
    metrics: dict


@dataclass(frozen=True)
class PositiveExposureStrategy:
    name: str
    variant: str
    total_base_exposures: int

    def __post_init__(self):
        _require(self.name in STRATEGIES, "Unknown training strategy")
        _integer(self.total_base_exposures, "total base exposures", 1)
        _require(self.variant in PHASE1_VARIANTS and canonical_variant(self.variant) == self.variant,
                 "Variant must use its canonical name")
        _require(self.name == JOINT or self.variant == "SDP", "Positive curriculum is SDP-only")

    @property
    def groups(self):
        return tuple(group for group in GROUP_TASKS if group in self.variant)

    def recipe_dict(self):
        n = self.total_base_exposures
        early = n // 2
        first = {"S": 1.5, "D": .75, "P": .75}
        late = {g: (n - early * first[g]) / (n - early) for g in first}
        if self.name == JOINT:
            first = late = {g: 1.0 for g in first}
        return {"schema_version": SCHEMA, "name": self.name, "total_base_exposures": n,
                "early_count": early, "late_count": n - early,
                "early_nominal_factors": first, "late_nominal_factors": late,
                "clock": "committed_base_records_including_zero_label_batches",
                "normalization": "complete_enabled_current_group_budget_per_segment_then_exposure_integral",
                "controller_input": "unscheduled_loss_and_gradients",
                "missing_groups_removed_from_denominator": False,
                "nominal_equal_integral_is_adaptive_coefficient_equal_integral": False}

    def config_dict(self):
        recipe = self.recipe_dict()
        return {"recipe": recipe, "recipe_sha256": canonical_hash(recipe),
                "implementation_sha256": implementation_sha256()}

    @classmethod
    def from_config(cls, config, *, variant, total_base_exposures):
        _require(type(config) is dict and set(config) == {
            "recipe", "recipe_sha256", "implementation_sha256"}, "Strategy config fields differ")
        recipe = config["recipe"]
        _require(type(recipe) is dict and type(recipe.get("name")) is str, "Missing strategy recipe")
        candidate = cls(recipe["name"], variant, total_base_exposures)
        expected = candidate.config_dict()
        try:
            same = (config == expected and canonical_hash(recipe) == config["recipe_sha256"]
                    and canonical_hash(config) == canonical_hash(expected))
        except (TypeError, ValueError, OverflowError) as exc:
            raise PositiveStrategyError("Strategy config is not finite canonical JSON") from exc
        _require(same, "Strategy recipe/N/implementation binding differs")
        return candidate

    def factors(self, start, count, group_budget):
        """Integrate separately normalized segment coefficients over [start,end).

        group_budget is the complete enabled b_g * dynamic_multiplier_g, before
        any curriculum. Its sum is conserved even when some groups have no labels.
        """
        start, count = _integer(start, "exposure start"), _integer(count, "base batch size", 1)
        end = start + count
        _require(end <= self.total_base_exposures, "Exposure interval exceeds the fixed pass")
        _require(type(group_budget) is dict and set(group_budget) == set(self.groups),
                 "Complete enabled group budget required, including missing groups")
        budget = {g: _positive(group_budget[g], "group budget " + g) for g in self.groups}
        total = _sum(budget.values())
        _require(math.isfinite(total) and (total > 0 or not self.groups), "Group budget sum is invalid")
        early = self.total_base_exposures // 2
        before = max(0, min(end, early) - start)
        after = count - before
        recipe = self.recipe_dict()
        nominal = {g: math.fsum((before * recipe["early_nominal_factors"][g],
                                after * recipe["late_nominal_factors"][g])) / count for g in self.groups}
        effective = {g: 0.0 for g in self.groups}
        segment_factors = {}
        for segment, size in (("early", before), ("late", after)):
            raw = recipe[segment + "_nominal_factors"]
            denominator = _sum(budget[g] * raw[g] for g in self.groups)
            _require(math.isfinite(denominator) and (denominator > 0 or not self.groups),
                     "Segment normalization overflowed")
            factors = {g: _positive(total * raw[g] / denominator, "normalized outer factor")
                       for g in self.groups}
            segment_factors[segment] = factors
            for g in self.groups:
                effective[g] += size / count * factors[g]
        # Joint uses exactly unit factors rather than floating re-normalization.
        if self.name == JOINT:
            effective = {g: 1.0 for g in self.groups}
            segment_factors = {s: dict(effective) for s in ("early", "late")}
        for g in self.groups:
            _positive(effective[g], "effective outer factor")
        _require(math.isclose(_sum(budget[g] * effective[g] for g in self.groups),
                              total, rel_tol=1e-12, abs_tol=1e-12), "Complete group budget drifted")
        return {"name": self.name, "recipe_sha256": canonical_hash(recipe),
                "exposure_start": start, "exposure_stop": end,
                "early_base_records": before, "late_base_records": after,
                "phase": "crossing" if before and after else "early" if before else "late",
                "nominal_factors": nominal, "effective_outer_factors": effective,
                "segment_outer_factors": segment_factors, "complete_group_budget": budget,
                "complete_group_budget_sum": total,
                "outer_factor_range": [min(effective.values()), max(effective.values())] if effective else None,
                "controller_multiplier_bounds_are_final_coefficient_bounds": False}

    def apply(self, balanced, *, start, count, group_budget):
        receipt = self.factors(start, count, group_budget)
        if self.name == JOINT:
            # Preserve object identity and exact original tensor summation order.
            return StrategyLoss(balanced.total, balanced.weighted, balanced.coefficients, receipt)
        expected = {task for g in self.groups for task in GROUP_TASKS[g]}
        _require(set(balanced.weighted) == set(balanced.coefficients) == expected,
                 "Balanced loss must retain every enabled leaf, including missing leaves")
        weighted, coefficients = {}, {}
        for group in self.groups:
            factor = receipt["effective_outer_factors"][group]
            for task in GROUP_TASKS[group]:
                source = balanced.weighted[task]
                _require(isinstance(source, torch.Tensor) and source.ndim == 0 and source.is_floating_point(),
                         "Balanced leaves must be scalar floating tensors")
                coef = _positive(balanced.coefficients[task] * factor, "final task coefficient")
                for value in (factor, coef):
                    represented = source.new_tensor(value)
                    _require(bool(torch.isfinite(represented)) and bool(represented > 0),
                             "Positive curriculum value is not representable in the actual loss dtype")
                coefficients[task] = coef
                weighted[task] = source * factor
                _require(bool(torch.isfinite(weighted[task])), "Postscheduled task loss is nonfinite")
        total = torch.stack(tuple(weighted.values())).sum()
        _require(bool(torch.isfinite(total)) and total.requires_grad, "Postscheduled aggregate lost finite supervision")
        measured = balanced.metrics.get("measured_group_gradient_norms")
        _require(measured is None or type(measured) is dict and set(measured) == set(self.groups),
                 "Measured group norm inventory differs from complete enabled groups")
        receipt["measured_postscheduled_group_gradient_norms"] = (
            {g: _positive_norm(measured[g] * receipt["effective_outer_factors"][g]) for g in self.groups}
            if measured is not None else None)
        # A norm of vector sums cannot be reconstructed from scalar group norms.
        receipt["measured_postscheduled_shared_total_gradient_norm"] = None
        receipt["additional_autograd_probe_seconds"] = 0.0
        receipt["group_norm_recipe"] = "actual_unscheduled_group_vector_norm_times_positive_outer_factor"
        receipt["final_task_coefficients"] = coefficients.copy()
        receipt["coefficient_recipe"] = "reported_scalar_product; actual_tensor_operation_is_balanced_weighted_loss_times_outer"
        receipt["final_coefficient_range"] = [min(coefficients.values()), max(coefficients.values())]
        return StrategyLoss(total, weighted, coefficients, receipt)


def _positive_norm(value):
    _require(type(value) in (int, float) and math.isfinite(value) and value >= 0,
             "Invalid post-scheduled measured group norm")
    return float(value)


def strategy_from_protocol(protocol, name, variant, seed, *, total_base_exposures=None):
    """Select a frozen declaration, never an arbitrary CLI training config."""
    _require(type(protocol) is dict and protocol.get("state") == "frozen", "Frozen protocol required")
    _require(name in STRATEGIES and variant in PHASE1_VARIANTS, "Unknown condition/strategy")
    _integer(seed, "strategy seed")
    declarations = protocol.get("strategies")
    _require(type(declarations) is dict and JOINT in declarations
             and set(declarations) <= set(STRATEGIES) and name in declarations,
             "Frozen strategy declaration is missing")
    selected, declared_n = None, None
    for key, entry in declarations.items():
        _require(type(entry) is dict and set(entry) == {"variants", "seeds", "config"},
                 "Frozen strategy entry fields differ")
        variants, seeds = entry["variants"], entry["seeds"]
        _require(type(variants) is list and variants and all(type(v) is str and v in PHASE1_VARIANTS for v in variants)
                 and len(set(variants)) == len(variants), "Invalid strategy variant allowlist")
        _require(type(seeds) is list and seeds and all(type(s) is int and s in (0, 1, 2) for s in seeds)
                 and len(set(seeds)) == len(seeds), "Invalid strategy seed allowlist")
        _require(all(v in protocol.get("variants", []) for v in variants)
                 and all(s in protocol.get("seeds", []) for s in seeds), "Strategy exceeds frozen main condition/seed scope")
        _require(key != JOINT or (
            canonical_hash({"value": variants}) == canonical_hash({"value": protocol.get("variants")})
            and canonical_hash({"value": seeds}) == canonical_hash({"value": protocol.get("seeds")})),
            "Joint allowlist must cover the complete ordered main variants and seeds")
        _require(key == JOINT or (variants == ["SDP"] and seeds == [0, 1, 2]),
                 "Auxiliary strategy must be exactly SDP across paired seeds 0,1,2")
        cfg = entry["config"]
        _require(type(cfg) is dict and type(cfg.get("recipe")) is dict, "Missing frozen strategy config")
        n = cfg["recipe"].get("total_base_exposures")
        declared_n = n if declared_n is None else declared_n
        _require(n == declared_n, "Strategies declare different complete training horizons")
        check = PositiveExposureStrategy.from_config(cfg, variant=variants[0], total_base_exposures=n)
        _require(check.name == key, "Strategy key and recipe name differ")
        if key == name:
            _require(variant in variants and seed in seeds, "Condition/seed is not allowed for strategy")
            actual_n = n if total_base_exposures is None else total_base_exposures
            selected = PositiveExposureStrategy.from_config(cfg, variant=variant, total_base_exposures=actual_n)
    _require(selected is not None, "Requested frozen strategy was not selected")
    return selected
