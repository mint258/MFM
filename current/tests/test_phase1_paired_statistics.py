"""Synthetic reported-metric contracts and independently hand-counted tests.

These are in-memory fixtures, not formal protocols, real checkpoint evidence,
downstream labels, final-test scores, or authorization to start training.
"""
from __future__ import annotations

import builtins
from copy import deepcopy
import hashlib
import json
import random

import numpy as np
import pytest

from phychem_mfm.phase1.paired_statistics import (
    PairedStatisticsError,
    analyze_paired_statistics,
    validate_analysis_plan,
)


METHOD = "paired_seed_contrast_sign_flip_bootstrap_v1"
VARIANTS = ["none", "S", "D", "P", "SD", "SP", "DP", "SDP"]


def canonical_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def sha(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def reseal(case):
    """Rebind explicit toy declarations, without selecting scientific scope."""
    plan, protocol, records = case
    plan_hash = sha(plan)
    protocol["downstream"]["statistics"]["analysis_plan_sha256"] = plan_hash
    protocol["content_sha256"] = sha({k: v for k, v in protocol.items() if k != "content_sha256"})
    records["protocol_content_sha256"] = protocol["content_sha256"]
    records["statistics_plan_sha256"] = plan_hash
    return case


def fixture(n=3, *, effects=None, direction="higher", coefficients=None,
            condition_values=None, cell_pairs=(("0", 0),), weights=None):
    seeds = list(range(n))
    coefficients = {"S": 1., "none": -1.} if coefficients is None else dict(coefficients)
    effects = [1.] * n if effects is None else list(effects)
    assert len(effects) == n
    weights = [1. / len(cell_pairs)] * len(cell_pairs) if weights is None else list(weights)
    assert len(weights) == len(cell_pairs)
    cells = [{"fold_id": str(fold), "readout_seed": readout_seed, "weight": weight,
              "sample_set_sha256": sha(["synthetic samples", str(fold)]),
              "label_mask_sha256": sha(["synthetic label mask", str(fold)])}
             for (fold, readout_seed), weight in zip(cell_pairs, weights)]
    endpoint = {"dataset": "synthetic_dataset", "metric": "synthetic_score", "units": "toy_unit",
                "direction": direction, "mode": "frozen", "readout_config_sha256": sha("toy readout"),
                "split_manifest_sha256": sha("toy split"), "cells": cells}
    plan = {"schema_version": "phase1_paired_statistics_plan_v1", "method": METHOD,
            "independent_unit": "pretraining_seed", "aggregation": "fixed_cell_weighted_mean_v1",
            "alternative": "two_sided", "confidence_level": .95, "alpha": .05,
            "bootstrap": {"resamples": 200, "rng_seed": 7, "quantile_method": "linear"},
            "sign_flip": {"exact_max_seeds": 16, "monte_carlo_resamples": 101, "rng_seed": 11},
            "multiple_comparison_rule": "Holm", "endpoints": {"score": endpoint},
            "comparisons": [{"id": "contrast", "endpoint": "score", "coefficients": coefficients,
                             "pretraining_seeds": seeds}],
            "families": {"main": ["contrast"]}, "primary_families": ["main"]}
    protocol = {"schema_version": "phase1_formal_protocol_v1", "state": "frozen",
                "frozen_at": "2026-01-01T00:00:00+00:00", "strategy": {"contrasts": {}},
                "pretraining": {"variants": list(VARIANTS), "seeds": seeds,
                    "paired_random_initialization": {"enabled": True, "initialization_source": "random",
                        "same_seed_per_condition": True,
                        "encoder_sha256_by_seed": {str(s): sha(["toy init artifact", s]) for s in seeds}},
                    "budget": {"optimizer_steps_per_condition": 12}},
                "downstream": {"datasets": ["synthetic_dataset"], "modes": ["frozen"],
                    "seeds": sorted({readout for _, readout in cell_pairs}),
                    "main_comparisons": ["contrast"], "statistics": {"method": METHOD, "paired": True,
                        "primary_metric": "per_endpoint_declared", "confidence_level": .95,
                        "multiple_comparison_rule": "Holm"}}}
    rows = []
    for condition in coefficients:
        for seed in seeds:
            if condition_values is None:
                value = 10. + (effects[seed] if condition == "S" else 0.)
            else:
                values = condition_values[condition]
                value = values[seed] if isinstance(values, (list, tuple)) else values
            initial_h0 = sha(["toy initial H0 state", seed])
            for cell in cells:
                rows.append({"condition": condition, "pretraining_seed": seed, "endpoint": "score",
                    "fold_id": cell["fold_id"], "readout_seed": cell["readout_seed"], "metric_value": float(value),
                    "checkpoint_sha256": sha(["toy endpoint checkpoint FILE", condition, seed]),
                    "shared_initialization_sha256": protocol["pretraining"]["paired_random_initialization"][
                        "encoder_sha256_by_seed"][str(seed)],
                    "pretraining_updates": 0 if condition == "none" else 12,
                    "sample_set_sha256": cell["sample_set_sha256"], "label_mask_sha256": cell["label_mask_sha256"],
                    "readout_config_sha256": endpoint["readout_config_sha256"],
                    "split_manifest_sha256": endpoint["split_manifest_sha256"],
                    "initial_h0_sha256": initial_h0,
                    "endpoint_h0_sha256": initial_h0 if condition == "none" else sha(["toy trained H0", condition, seed])})
    records = {"schema_version": "phase1_downstream_metric_records_v1", "records": rows}
    return reseal((plan, protocol, records))


def analyze(case, **overrides):
    plan, protocol, records = case
    # Invalid numeric rows must reach the consumer, rather than failing in this
    # fixture's finite-JSON byte encoder before the public API is called.
    arguments = dict(overrides)
    if "plan_sha256" not in arguments:
        arguments["plan_sha256"] = sha(plan)
    if "records_sha256" not in arguments:
        arguments["records_sha256"] = sha(records)
    return analyze_paired_statistics(plan, records, protocol, **arguments)


def result(case):
    return analyze(case)["comparisons"]["contrast"]


def family_fixture(effect_vectors):
    """Different fixed endpoints share the same condition/seed checkpoints."""
    case = fixture(len(next(iter(effect_vectors.values()))))
    plan, protocol, envelope = case
    template_endpoint = deepcopy(plan["endpoints"]["score"])
    template_rows = deepcopy(envelope["records"])
    plan["endpoints"], plan["comparisons"], envelope["records"] = {}, [], []
    for identifier, effects in effect_vectors.items():
        endpoint_id = "endpoint-" + identifier
        endpoint = deepcopy(template_endpoint)
        endpoint["metric"] = "synthetic_" + identifier
        plan["endpoints"][endpoint_id] = endpoint
        plan["comparisons"].append({"id": identifier, "endpoint": endpoint_id,
            "coefficients": {"S": 1., "none": -1.}, "pretraining_seeds": list(range(len(effects)))})
        for original in template_rows:
            row = deepcopy(original)
            row["endpoint"] = endpoint_id
            row["metric_value"] = 10. + (effects[row["pretraining_seed"]] if row["condition"] == "S" else 0.)
            envelope["records"].append(row)
    members = list(effect_vectors)
    plan["families"] = {"main": members}
    protocol["downstream"]["main_comparisons"] = members.copy()
    return reseal(case)


def holm_by_id(receipt, family="main"):
    return {row["comparison_id"]: row for row in receipt["families"][family]["holm"]}


@pytest.mark.parametrize("n,p_value", [(3, .25), (5, .0625), (6, .03125)])
def test_exact_sign_flip_has_hand_counted_pretraining_seed_sample_size(n, p_value):
    output = result(fixture(n))
    assert output["n_independent"] == n
    assert output["raw_mean_effect"] == pytest.approx(1.)
    assert output["benefit_mean_effect"] == pytest.approx(1.)
    test = output["sign_flip"]
    assert test["method"] == "exact"
    assert test["n_independent"] == n
    assert test["draws"] == 2 ** n
    assert test["extreme_count"] == 2
    assert test["p_value"] == p_value
    assert test["minimum_attainable_p"] == p_value


def test_all_zero_effect_counts_null_ties_and_returns_one():
    output = result(fixture(5, effects=[0.] * 5))
    assert output["raw_mean_effect"] == output["benefit_mean_effect"] == 0.
    assert output["sign_flip"]["extreme_count"] == output["sign_flip"]["draws"] == 32
    assert output["sign_flip"]["p_value"] == 1.
    assert output["bootstrap"]["raw_ci"] == [0., 0.]
    assert output["bootstrap"]["benefit_ci"] == [0., 0.]
    assert output["bootstrap"]["degenerate"] is True


def test_constant_nonzero_effect_exposes_a_degenerate_bootstrap_interval():
    output = result(fixture(3))
    assert output["bootstrap"]["raw_ci"] == [1., 1.]
    assert output["bootstrap"]["degenerate"] is True
    # A zero-width empirical interval does not alter exact test resolution.
    assert output["sign_flip"]["p_value"] == .25


def test_bootstrap_resamples_whole_seed_contrasts_with_an_exhaustive_two_seed_oracle(monkeypatch):
    case = fixture(2, effects=[-1., 1.], cell_pairs=(("0", 0), ("1", 1)), weights=(.25, .75))
    case[0]["bootstrap"]["resamples"] = 4
    case[0]["confidence_level"] = .5
    case[1]["downstream"]["statistics"]["confidence_level"] = .5
    reseal(case)

    class ExhaustiveTwoSeedDraws:
        def integers(self, low, high, size, **kwargs):
            # Enumerate the four independent draws from the two seed clusters.
            # Fold/readout cells must not change the population size or shape.
            assert (low, high, size) == (0, 2, (4, 2))
            return np.array([[0, 0], [0, 1], [1, 0], [1, 1]], dtype=np.int64)

    monkeypatch.setattr(np.random, "default_rng", lambda seed: ExhaustiveTwoSeedDraws())
    output = result(case)
    # The four cluster means are [-1, 0, 0, 1]. Linear 25/75 percentiles
    # interpolate at positions .75 and 2.25, giving [-.25, .25].
    assert output["bootstrap"]["raw_ci"] == [-.25, .25]
    assert output["bootstrap"]["benefit_ci"] == [-.25, .25]
    assert output["bootstrap"]["degenerate"] is False
    assert output["bootstrap"]["resampling_unit"] == "whole_pretraining_seed_contrast"
    assert output["n_independent"] == 2


def test_repeated_fold_and_readout_cells_cannot_pseudo_replicate_pretraining_seeds():
    simple = result(fixture(3))
    repeated = result(fixture(3, cell_pairs=tuple((str(fold), readout)
                                               for fold in range(5) for readout in range(4))))
    assert repeated["n_independent"] == simple["n_independent"] == 3
    assert len(repeated["seed_effects"]) == 3
    assert repeated["raw_mean_effect"] == pytest.approx(simple["raw_mean_effect"])
    assert repeated["sign_flip"]["draws"] == 8
    assert repeated["sign_flip"]["p_value"] == simple["sign_flip"]["p_value"] == .25


def test_predeclared_cell_weights_determine_each_seed_effect_without_count_weighting():
    case = fixture(3, cell_pairs=(("0", 0), ("1", 1)), weights=(.25, .75))
    for row in case[2]["records"]:
        if row["condition"] == "S":
            row["metric_value"] = 11. if row["fold_id"] == "0" else 15.
    output = result(case)
    assert output["raw_mean_effect"] == pytest.approx(4.)
    assert all(row["condition_means"]["S"] == pytest.approx(14.) for row in output["seed_effects"])
    assert all(row["condition_means"]["none"] == pytest.approx(10.) for row in output["seed_effects"])
    assert output["sign_flip"]["p_value"] == .25


@pytest.mark.parametrize("coefficients,values,expected", [
    ({"SD": 1., "S": -1., "D": -1., "none": 1.},
     {"none": 10., "S": 11., "D": 12., "SD": 15.}, 2.),
    ({"S": .25, "SD": .25, "SP": .25, "SDP": .25,
      "none": -.25, "D": -.25, "P": -.25, "DP": -.25},
     {"none": 10., "S": 12., "D": 13., "P": 15., "SD": 16., "SP": 17., "DP": 18., "SDP": 21.}, 2.5),
])
def test_factorial_and_eight_cell_marginal_contrasts_have_analytic_means(coefficients, values, expected):
    output = result(fixture(3, coefficients=coefficients, condition_values=values))
    assert output["coefficients"] == coefficients
    assert output["raw_mean_effect"] == pytest.approx(expected)
    assert all(row["raw_effect"] == pytest.approx(expected) for row in output["seed_effects"])
    assert output["sign_flip"]["p_value"] == .25


def test_reversing_contrast_changes_effect_and_ci_sign_but_not_two_sided_p():
    forward = fixture(5, effects=[1., 2., 3., 4., 8.])
    reverse = deepcopy(forward)
    reverse[0]["comparisons"][0]["coefficients"] = {"S": -1., "none": 1.}
    reseal(reverse)
    first, second = result(forward), result(reverse)
    assert second["raw_mean_effect"] == pytest.approx(-first["raw_mean_effect"])
    assert second["benefit_mean_effect"] == pytest.approx(-first["benefit_mean_effect"])
    assert second["bootstrap"]["raw_ci"] == pytest.approx([-v for v in reversed(first["bootstrap"]["raw_ci"])])
    assert second["sign_flip"]["p_value"] == first["sign_flip"]["p_value"]


def test_lower_metric_direction_changes_benefit_only_without_picking_a_favorable_sign():
    higher = fixture(5, effects=[1., 2., 3., 4., 8.])
    lower = deepcopy(higher)
    lower[0]["endpoints"]["score"]["direction"] = "lower"
    reseal(lower)
    first, second = result(higher), result(lower)
    assert second["raw_mean_effect"] == first["raw_mean_effect"]
    assert second["benefit_mean_effect"] == pytest.approx(-first["benefit_mean_effect"])
    assert second["bootstrap"]["benefit_ci"] == pytest.approx([-v for v in reversed(first["bootstrap"]["benefit_ci"])])
    assert second["sign_flip"]["p_value"] == first["sign_flip"]["p_value"]


def test_common_score_translation_and_positive_scale_preserve_the_exact_test():
    original = fixture(5, effects=[1., 2., 3., 4., 8.])
    translated, scaled = deepcopy(original), deepcopy(original)
    for row in translated[2]["records"]:
        row["metric_value"] += 1000.
    for row in scaled[2]["records"]:
        row["metric_value"] *= 4.
    baseline, shifted, multiplied = result(original), result(translated), result(scaled)
    assert shifted["raw_mean_effect"] == baseline["raw_mean_effect"]
    assert shifted["bootstrap"]["raw_ci"] == baseline["bootstrap"]["raw_ci"]
    assert multiplied["raw_mean_effect"] == pytest.approx(4. * baseline["raw_mean_effect"])
    assert multiplied["bootstrap"]["raw_ci"] == pytest.approx([4. * v for v in baseline["bootstrap"]["raw_ci"]])
    assert shifted["sign_flip"]["p_value"] == multiplied["sign_flip"]["p_value"] == baseline["sign_flip"]["p_value"]


def test_local_monte_carlo_uses_declared_threshold_and_plus_one_counting():
    case = fixture(6)
    case[0]["sign_flip"]["exact_max_seeds"] = 2
    reseal(case)
    test = result(case)["sign_flip"]
    assert test["method"] == "monte_carlo"
    assert test["n_independent"] == 6
    assert test["draws"] == 101
    assert 0 <= test["extreme_count"] <= 101
    assert test["p_value"] == pytest.approx((test["extreme_count"] + 1) / 102)
    assert test["p_value"] >= 1 / 102
    assert test["minimum_attainable_p"] >= 1 / 102
    assert result(case)["sign_flip"] == test


@pytest.mark.parametrize("monte_carlo", [False, True])
def test_record_and_seed_cell_order_does_not_change_deterministic_statistics(monte_carlo):
    original = fixture(6, effects=[1., 2., 3., 4., 5., 8.],
                       cell_pairs=(("0", 0), ("0", 1), ("1", 0), ("1", 1)))
    if monte_carlo:
        original[0]["sign_flip"]["exact_max_seeds"] = 2
        reseal(original)
    permuted = deepcopy(original)
    permuted[2]["records"] = permuted[2]["records"][::-1]
    first, second = result(original), result(permuted)
    assert first == second


def test_json_roundtrip_and_normalized_result_are_detached_from_callers():
    case = fixture(3)
    original = deepcopy(case)
    normalized = validate_analysis_plan(case[0], case[1])
    normalized["endpoints"]["score"]["cells"][0]["weight"] = .25
    normalized["comparisons"][0]["pretraining_seeds"].append(63)
    assert case == original
    decoded = tuple(json.loads(json.dumps(part, allow_nan=False)) for part in case)
    assert analyze(decoded) == analyze(case)
    assert case == original


def test_analysis_is_no_io_and_does_not_touch_global_rng_or_inputs(monkeypatch):
    case = fixture(6, effects=[1., 2., 3., 4., 5., 8.])
    case[0]["sign_flip"]["exact_max_seeds"] = 2
    reseal(case)
    before = deepcopy(case)
    python_state, numpy_state = random.getstate(), np.random.get_state()
    def no_open(*args, **kwargs):
        pytest.fail("Pure statistics consumer must not read data or checkpoint files")
    monkeypatch.setattr(builtins, "open", no_open)
    receipt = analyze(case)
    assert receipt["comparisons"]["contrast"]["n_independent"] == 6
    assert case == before and random.getstate() == python_state
    current = np.random.get_state()
    assert current[0] == numpy_state[0] and np.array_equal(current[1], numpy_state[1])
    assert current[2:] == numpy_state[2:]


@pytest.mark.parametrize("value", [True, False, None, "1", float("nan"), float("inf"), -float("inf")])
def test_invalid_or_nonfinite_metric_values_fail_before_statistics(value):
    case = fixture(3)
    case[2]["records"][0]["metric_value"] = value
    with pytest.raises(PairedStatisticsError):
        analyze(case, records_sha256="a" * 64)


@pytest.mark.parametrize("defect", ["missing_cell", "duplicate_cell", "extra_fold", "extra_readout_seed",
                                  "undeclared_condition", "partial_seed", "extra_endpoint"])
def test_cells_must_be_complete_unique_and_predeclared(defect):
    case = fixture(3, cell_pairs=(("0", 0), ("1", 1)))
    rows = case[2]["records"]
    if defect == "missing_cell":
        rows.pop(0)
    elif defect == "duplicate_cell":
        rows.append(deepcopy(rows[0]))
    elif defect == "extra_fold":
        rows[0]["fold_id"] = "unplanned"
    elif defect == "extra_readout_seed":
        rows[0]["readout_seed"] = 99
    elif defect == "undeclared_condition":
        rows[0]["condition"] = "DP"
    elif defect == "partial_seed":
        rows[:] = [row for row in rows if row["pretraining_seed"] != 2]
    else:
        rows[0]["endpoint"] = "unplanned"
    with pytest.raises(PairedStatisticsError):
        analyze(case)


@pytest.mark.parametrize("field", ["sample_set_sha256", "label_mask_sha256", "readout_config_sha256",
                                  "split_manifest_sha256", "shared_initialization_sha256",
                                  "initial_h0_sha256", "checkpoint_sha256", "endpoint_h0_sha256"])
def test_hash_drift_cannot_be_hidden_by_equal_metric_values(field):
    case = fixture(3, cell_pairs=(("0", 0), ("1", 1)))
    case[2]["records"][0][field] = sha(["wrong producer binding", field])
    with pytest.raises(PairedStatisticsError):
        analyze(case)


@pytest.mark.parametrize("condition,field,value", [("none", "pretraining_updates", 1),
    ("S", "pretraining_updates", 11), ("S", "pretraining_updates", True),
    ("none", "endpoint_h0_sha256", "e" * 64)])
def test_endpoint_budget_and_none_random_h0_contract_are_preserved(condition, field, value):
    case = fixture(3)
    row = next(row for row in case[2]["records"] if row["condition"] == condition)
    row[field] = value
    with pytest.raises(PairedStatisticsError):
        analyze(case)


@pytest.mark.parametrize("field,value", [("method", "pick_best_pvalue"), ("independent_unit", "fold"),
    ("aggregation", "average_available"), ("alternative", "posthoc_greater"),
    ("confidence_level", True), ("confidence_level", 1.), ("alpha", 0.),
    ("multiple_comparison_rule", "none"), ("primary_families", []), ("unknown_option", True)])
def test_analysis_choices_are_explicit_and_no_unsupported_method_is_inferred(field, value):
    case = fixture(3)
    case[0][field] = value
    reseal(case)
    with pytest.raises(PairedStatisticsError):
        validate_analysis_plan(case[0], case[1])


@pytest.mark.parametrize("defect", ["nonzero_sum", "zero_coefficient", "one_condition", "bool_coefficient",
                                  "unplanned_condition", "duplicate_comparison", "unknown_seed",
                                  "duplicate_seed", "one_seed", "empty_family", "missing_family_member",
                                  "duplicate_family_member", "overlapping_families", "posthoc_primary"])
def test_contrast_scope_seeds_and_full_hypothesis_family_cannot_be_silently_repaired(defect):
    case = fixture(3)
    plan, protocol, _ = case
    comparison = plan["comparisons"][0]
    if defect == "nonzero_sum":
        comparison["coefficients"]["S"] = 2.
    elif defect == "zero_coefficient":
        comparison["coefficients"]["D"] = 0.
    elif defect == "one_condition":
        comparison["coefficients"] = {"S": 1.}
    elif defect == "bool_coefficient":
        comparison["coefficients"]["S"] = True
    elif defect == "unplanned_condition":
        comparison["coefficients"] = {"historical_best": 1., "none": -1.}
    elif defect == "duplicate_comparison":
        plan["comparisons"].append(deepcopy(comparison))
    elif defect == "unknown_seed":
        comparison["pretraining_seeds"] = [0, 1, 99]
    elif defect == "duplicate_seed":
        comparison["pretraining_seeds"] = [0, 0, 1]
    elif defect == "one_seed":
        comparison["pretraining_seeds"] = [0]
    elif defect == "empty_family":
        plan["families"]["main"] = []
    elif defect == "missing_family_member":
        plan["families"]["main"] = ["other"]
    elif defect == "duplicate_family_member":
        plan["families"]["main"] = ["contrast", "contrast"]
    elif defect == "overlapping_families":
        plan["families"]["another"] = ["contrast"]
    else:
        protocol["downstream"]["main_comparisons"] = ["posthoc_selected"]
    reseal(case)
    with pytest.raises(PairedStatisticsError):
        validate_analysis_plan(plan, protocol)


@pytest.mark.parametrize("section,key,value", [("bootstrap", "resamples", 0),
    ("bootstrap", "resamples", 100001), ("bootstrap", "rng_seed", True),
    ("bootstrap", "quantile_method", "choose_after_results"),
    ("sign_flip", "exact_max_seeds", 17), ("sign_flip", "exact_max_seeds", 0),
    ("sign_flip", "monte_carlo_resamples", 0), ("sign_flip", "rng_seed", -1)])
def test_resampling_methods_and_bounds_are_declared_without_automatic_fallback(section, key, value):
    case = fixture(3)
    case[0][section][key] = value
    reseal(case)
    with pytest.raises(PairedStatisticsError):
        validate_analysis_plan(case[0], case[1])


@pytest.mark.parametrize("defect", ["draft", "stale_content", "different_plan_hash", "different_records_plan_hash",
                                  "different_records_protocol_hash", "unpaired", "historical_init"])
def test_declared_plan_and_protocol_bindings_are_required_without_claiming_file_verification(defect):
    case = fixture(3)
    _, protocol, records = case
    if defect == "draft":
        protocol["state"] = "draft"
        reseal(case)
    elif defect == "stale_content":
        protocol["content_sha256"] = "c" * 64
    elif defect == "different_plan_hash":
        protocol["downstream"]["statistics"]["analysis_plan_sha256"] = "c" * 64
        protocol["content_sha256"] = sha({k: v for k, v in protocol.items() if k != "content_sha256"})
        records["protocol_content_sha256"] = protocol["content_sha256"]
    elif defect == "different_records_plan_hash":
        records["statistics_plan_sha256"] = "c" * 64
    elif defect == "different_records_protocol_hash":
        records["protocol_content_sha256"] = "c" * 64
    elif defect == "unpaired":
        protocol["downstream"]["statistics"]["paired"] = False
        reseal(case)
    else:
        protocol["pretraining"]["paired_random_initialization"]["initialization_source"] = "historical_pretrained"
        reseal(case)
    with pytest.raises(PairedStatisticsError):
        analyze(case)


def test_complete_holm_family_matches_independently_counted_six_seed_oracle():
    # Enumerating the 64 +/- assignments gives 2, 14 and 44 extreme means.
    # Holm's multipliers are 3, 2, 1, with a cumulative maximum.
    case = family_fixture({"all-positive": [1.] * 6,
                           "one-negative": [1., 1., 1., 1., 1., -1.],
                           "two-negative": [1., 1., 1., 1., -1., -1.]})
    receipt = analyze(case)
    rows = holm_by_id(receipt)
    for identifier, raw, adjusted, rank in [
        ("all-positive", .03125, .09375, 1),
        ("one-negative", .21875, .4375, 2),
        ("two-negative", .6875, .6875, 3),
    ]:
        assert rows[identifier]["p_value"] == raw
        assert rows[identifier]["holm_adjusted_p"] == adjusted
        assert rows[identifier]["rank"] == rank
        assert rows[identifier]["reject_holm"] is False
    assert receipt["families"]["main"]["family_size"] == 3
    # The smallest raw p is below alpha, but its full-family decision is not.
    assert rows["all-positive"]["p_value"] < case[0]["alpha"]


def test_holm_ties_and_family_order_do_not_change_adjusted_decisions():
    case = family_fixture({"a": [1.] * 6, "b": [1.] * 6, "zero": [0.] * 6})
    first = analyze(case)
    permuted = deepcopy(case)
    permuted[0]["comparisons"].reverse()
    permuted[0]["families"]["main"].reverse()
    permuted[2]["records"].reverse()
    reseal(permuted)
    second = analyze(permuted)
    a, b = holm_by_id(first), holm_by_id(second)
    assert a == b
    assert a["a"]["holm_adjusted_p"] == a["b"]["holm_adjusted_p"] == .09375
    assert a["zero"]["p_value"] == a["zero"]["holm_adjusted_p"] == 1.


def test_primary_families_name_comparison_union_and_secondary_family_is_still_complete():
    case = family_fixture({"a": [1.] * 6, "b": [1.] * 6, "secondary": [0.] * 6})
    case[0]["families"] = {"main": ["a", "b"], "sensitivity": ["secondary"]}
    case[1]["downstream"]["main_comparisons"] = ["a", "b"]
    reseal(case)
    receipt = analyze(case)
    assert receipt["families"]["main"]["primary"] is True
    assert receipt["families"]["sensitivity"]["primary"] is False
    assert receipt["families"]["sensitivity"]["family_size"] == 1
    assert holm_by_id(receipt, "sensitivity")["secondary"]["p_value"] == 1.


@pytest.mark.parametrize("field", ["checkpoint_sha256", "endpoint_h0_sha256"])
def test_checkpoint_and_endpoint_state_must_be_stable_across_distinct_endpoints(field):
    case = family_fixture({"first": [1.] * 3, "second": [2.] * 3})
    row = next(row for row in case[2]["records"]
               if row["endpoint"] == "endpoint-second" and row["condition"] == "S"
               and row["pretraining_seed"] == 0)
    row[field] = sha(["different checkpoint for same condition and seed", field])
    with pytest.raises(PairedStatisticsError):
        analyze(case)


def test_none_checkpoint_file_is_distinct_from_initialization_artifact_and_proofs_are_scoped():
    case = fixture(3)
    none_rows = [row for row in case[2]["records"] if row["condition"] == "none"]
    assert all(row["checkpoint_sha256"] != row["shared_initialization_sha256"] for row in none_rows)
    assert all(row["endpoint_h0_sha256"] == row["initial_h0_sha256"] for row in none_rows)
    receipt = analyze(case)
    assert receipt["may_start_formal_training"] is False
    assert receipt["model_or_evaluation_truth_independently_verified"] is False
    assert receipt["byte_bindings"]["records_sha256"] == sha(case[2])
    assert receipt["byte_bindings"]["plan_sha256"] == sha(case[0])
    assert receipt["analysis_sha256"] == sha({k: v for k, v in receipt.items() if k != "analysis_sha256"})
    assert receipt["limitations"]


def test_pretraining_seed_declaration_order_is_normalized_before_local_random_draws():
    case = fixture(6, effects=[1., 2., 3., 4., 5., 8.])
    case[0]["sign_flip"]["exact_max_seeds"] = 2
    reseal(case)
    changed = deepcopy(case)
    changed[0]["comparisons"][0]["pretraining_seeds"].reverse()
    changed[1]["pretraining"]["seeds"].reverse()
    reseal(changed)
    assert result(changed) == result(case)


def write_cli_fixture(tmp_path, case):
    """Write exact toy declaration bytes; no real data or protocol is touched."""
    input_dir = tmp_path / "inputs"
    input_dir.mkdir()
    paths = [input_dir / name for name in ("protocol.json", "plan.json", "metrics.json")]
    for path, part in zip(paths, (case[1], case[0], case[2])):
        path.write_bytes(canonical_bytes(part))
    output = tmp_path / "receipt.json"
    argv = ["--protocol", str(paths[0]), "--analysis-plan", str(paths[1]),
            "--metrics", str(paths[2]), "--output", str(output)]
    return paths, output, argv


def test_cli_consumes_actual_bytes_and_publishes_complete_scoped_receipt(tmp_path, capsys):
    from tools.phase1_paired_statistics import main

    paths, output, argv = write_cli_fixture(tmp_path, fixture(3))
    before = {path: path.read_bytes() for path in paths}
    assert main(argv) == 0
    printed = json.loads(capsys.readouterr().out)
    actual_bytes = output.read_bytes()
    receipt = json.loads(actual_bytes)
    assert printed["output_sha256"] == hashlib.sha256(actual_bytes).hexdigest()
    assert printed["output_bytes"] == len(actual_bytes)
    assert receipt["receipt_sha256"] == sha({k: v for k, v in receipt.items() if k != "receipt_sha256"})
    assert receipt["status"] == "STATISTICAL_CONSUMPTION_COMPLETE"
    assert receipt["formal_training_authorized"] is False
    comparison = receipt["analysis"]["comparisons"]["contrast"]
    assert comparison["n_independent"] == 3
    assert comparison["sign_flip"]["p_value"] == .25
    assert receipt["input_files_unchanged"] is True
    for binding in receipt["input_files"]:
        matching = next(path for path in paths if str(path.resolve()) == binding["path"])
        assert binding["sha256"] == hashlib.sha256(before[matching]).hexdigest()
        assert binding["bytes"] == len(before[matching])
    assert {path: path.read_bytes() for path in paths} == before
    assert not list(tmp_path.glob(".paired-statistics-*.pending"))


def test_cli_refuses_existing_output_and_preserves_its_bytes(tmp_path, capsys):
    from tools.phase1_paired_statistics import main

    paths, output, argv = write_cli_fixture(tmp_path, fixture(3))
    before = {path: path.read_bytes() for path in paths}
    output.write_bytes(b"existing result must be preserved\n")
    original_output = output.read_bytes()
    assert main(argv) == 2
    assert json.loads(capsys.readouterr().out)["status"] == "STATISTICAL_CONSUMPTION_FAILED"
    assert output.read_bytes() == original_output
    assert {path: path.read_bytes() for path in paths} == before
    assert not list(tmp_path.glob(".paired-statistics-*.pending"))


def test_cli_missing_metric_cell_fails_without_output_or_owned_pending_file(tmp_path, capsys):
    from tools.phase1_paired_statistics import main

    case = fixture(3)
    case[2]["records"].pop()
    paths, output, argv = write_cli_fixture(tmp_path, case)
    before = {path: path.read_bytes() for path in paths}
    assert main(argv) == 2
    assert json.loads(capsys.readouterr().out)["status"] == "STATISTICAL_CONSUMPTION_FAILED"
    assert not output.exists()
    assert {path: path.read_bytes() for path in paths} == before
    assert not list(tmp_path.glob(".paired-statistics-*.pending"))


def test_cli_exclusive_publication_preserves_concurrent_result_and_cleans_own_pending(tmp_path, capsys, monkeypatch):
    import tools.phase1_paired_statistics as cli

    paths, output, argv = write_cli_fixture(tmp_path, fixture(3))
    before = {path: path.read_bytes() for path in paths}
    winner_bytes = b"another process published first\n"
    def publish_other_result(source, destination):
        assert destination == output
        assert source.exists() and source.name.endswith(".pending")
        output.write_bytes(winner_bytes)
        raise FileExistsError("Synthetic competing publisher won exclusive creation")
    monkeypatch.setattr(cli.os, "link", publish_other_result)
    assert cli.main(argv) == 2
    assert json.loads(capsys.readouterr().out)["status"] == "STATISTICAL_CONSUMPTION_FAILED"
    assert output.read_bytes() == winner_bytes
    assert {path: path.read_bytes() for path in paths} == before
    assert not list(tmp_path.glob(".paired-statistics-*.pending"))
