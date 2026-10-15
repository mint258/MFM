"""Paired-seed inference from already scored, protocol-bound metric metadata.

No targets, checkpoints, files, scheduler or model are read. Byte bindings and
model-state hashes are supplied by the caller/metric producer; their internal
consistency is not independent verification of actual weights or evaluations.
Folds and readout seeds are fixed cells, never independent pretraining repeats.
Dimensions/draws and temporary sampling arrays are bounded below. The caller
must also enforce its declared CPU wall/RSS and output-byte budgets; maximal
plans are not a promise of completion within any particular job allocation.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import math
import re

import numpy as np

from .strategy_contract import validated_contrasts


PLAN_SCHEMA = "phase1_paired_statistics_plan_v1"
RECORDS_SCHEMA = "phase1_downstream_metric_records_v1"
RESULT_SCHEMA = "phase1_paired_statistics_result_v1"
METHOD = "paired_seed_contrast_sign_flip_bootstrap_v1"
VARIANTS = ("none", "S", "D", "P", "SD", "SP", "DP", "SDP")
MAX_SEEDS, MAX_COMPARISONS, MAX_ENDPOINTS, MAX_CELLS = 64, 128, 32, 2048
MAX_RESAMPLES, MAX_RECORDS = 100000, 2000000
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_EPS = np.finfo(np.float64).eps


class PairedStatisticsError(ValueError):
    """A complete, declared paired analysis cannot be computed safely."""


def _require(condition, message):
    if not condition:
        raise PairedStatisticsError(message)


def _canonical_hash(value):
    try:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, OverflowError) as exc:
        raise PairedStatisticsError("Analysis contracts must contain finite JSON values") from exc
    return hashlib.sha256(encoded).hexdigest()


def _exact(value, fields, name):
    _require(type(value) is dict and set(value) == set(fields), name + " has missing or unexpected fields")


def _text(value, name):
    _require(isinstance(value, str) and bool(value) and value.strip() == value
             and len(value) <= 256, name + " must be a nonempty explicit string")
    return value


def _sha(value, name):
    _require(isinstance(value, str) and bool(_SHA.fullmatch(value)), name + " must be SHA256")
    return value


def _integer(value, name, *, minimum=0, maximum=None):
    _require(type(value) is int and value >= minimum
             and (maximum is None or value <= maximum), name + " is outside its integer bounds")
    return value


def _finite(value, name, *, positive=False):
    _require(type(value) in (int, float), name + " must be a finite real number, not bool")
    try:
        result = float(value)
    except (ValueError, OverflowError) as exc:
        raise PairedStatisticsError(name + " is not a finite float64 value") from exc
    _require(math.isfinite(result) and (not positive or result > 0), name + " is not finite/positive")
    return result


def _strings(value, name, *, maximum=MAX_COMPARISONS):
    _require(type(value) is list and 1 <= len(value) <= maximum, name + " must be a bounded nonempty list")
    for item in value:
        _text(item, name)
    _require(len(set(value)) == len(value), name + " contains duplicate IDs")
    return list(value)


def _seeds(value, name, *, minimum=1, maximum=MAX_SEEDS):
    _require(type(value) is list and minimum <= len(value) <= maximum, name + " has invalid repeat count")
    for seed in value:
        _integer(seed, name)
    _require(len(set(value)) == len(value), name + " contains duplicate seeds")
    return sorted(value)


def _protocol(protocol):
    _require(type(protocol) is dict and protocol.get("schema_version") == "phase1_formal_protocol_v1"
             and protocol.get("state") == "frozen", "A frozen Phase 1 protocol is required")
    try:
        stamp = datetime.fromisoformat(protocol["frozen_at"].replace("Z", "+00:00"))
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise PairedStatisticsError("Protocol frozen_at must be timezone-aware ISO text") from exc
    _require(stamp.utcoffset() is not None, "Protocol frozen_at must be timezone-aware")
    _require(stamp <= datetime.now(timezone.utc), "Protocol frozen_at cannot be in the future")
    content = _sha(protocol.get("content_sha256"), "Protocol content hash")
    _require(content == _canonical_hash({key: value for key, value in protocol.items()
                                       if key != "content_sha256"}), "Protocol canonical content hash differs")
    try:
        pre, downstream = protocol["pretraining"], protocol["downstream"]
        _require(type(pre) is dict and type(downstream) is dict, "Protocol training scopes must be mappings")
        _require(pre["variants"] == list(VARIANTS), "Protocol must preserve the canonical eight main conditions")
        seeds = _seeds(pre["seeds"], "Protocol pretraining seeds")
        init = pre["paired_random_initialization"]
        _require(type(init) is dict and init.get("enabled") is True
                 and init.get("same_seed_per_condition") is True
                 and init.get("initialization_source") == "random", "Paired random initialization is required")
        hashes = init["encoder_sha256_by_seed"]
        _require(type(hashes) is dict and set(hashes) == {str(seed) for seed in seeds},
                 "Every main pretraining seed requires its initialization artifact hash")
        for value in hashes.values():
            _sha(value, "Initialization artifact hash")
        updates = _integer(pre["budget"]["optimizer_steps_per_condition"], "Fixed pretraining updates", minimum=1)
        readout_seeds = _seeds(downstream["seeds"], "Protocol readout seeds", maximum=MAX_CELLS)
        datasets = _strings(downstream["datasets"], "Protocol datasets", maximum=MAX_ENDPOINTS)
        modes = _strings(downstream["modes"], "Protocol modes")
        primary = _strings(downstream["main_comparisons"], "Protocol primary comparison IDs")
        stat = downstream["statistics"]
        _require(type(stat) is dict and stat.get("method") == METHOD and stat.get("paired") is True
                 and stat.get("primary_metric") == "per_endpoint_declared"
                 and stat.get("multiple_comparison_rule") == "Holm", "Protocol statistics contract differs")
        _sha(stat.get("analysis_plan_sha256"), "Protocol analysis-plan artifact hash")
        confidence = _finite(stat["confidence_level"], "Protocol confidence level")
        _require(0 < confidence < 1, "Protocol confidence level must lie in (0,1)")
        try:
            contrasts = validated_contrasts(protocol)
        except ValueError as exc:
            raise PairedStatisticsError("Invalid declared strategy comparison scope") from exc
        _require(len(contrasts) <= MAX_COMPARISONS, "Too many declared strategy contrasts")
    except (KeyError, TypeError) as exc:
        raise PairedStatisticsError("Missing/invalid required statistics protocol field: " + str(exc)) from exc
    return {"seeds": seeds, "initialization": hashes, "updates": updates,
            "readout_seeds": readout_seeds, "datasets": datasets, "modes": modes,
            "primary": primary, "statistics": stat, "contrasts": contrasts}


def _cell_weights(endpoint):
    weights = [cell["weight"] for cell in endpoint["cells"]]
    scale = max(weights)
    scaled = [value / scale for value in weights]
    _require(all(value > 0 for value in scaled), "Cell weights lose positive support in float64")
    total = math.fsum(scaled)
    normalized = [value / total for value in scaled]
    _require(all(value > 0 for value in normalized), "Normalized cell weight underflow")
    return normalized


def validate_analysis_plan(plan, protocol) -> dict:
    """Validate and detach a plan; does not verify its raw file bytes or GPU gate."""
    context = _protocol(protocol)
    fields = ("schema_version", "method", "independent_unit", "aggregation", "alternative",
              "confidence_level", "alpha", "bootstrap", "sign_flip", "multiple_comparison_rule",
              "endpoints", "comparisons", "families", "primary_families")
    _exact(plan, fields, "Analysis plan")
    fixed = {"schema_version": PLAN_SCHEMA, "method": METHOD, "independent_unit": "pretraining_seed",
             "aggregation": "fixed_cell_weighted_mean_v1", "alternative": "two_sided",
             "multiple_comparison_rule": "Holm"}
    _require(all(plan[name] == value for name, value in fixed.items()), "Unsupported statistics method/aggregation")
    result = deepcopy(plan)
    for name in ("confidence_level", "alpha"):
        result[name] = _finite(plan[name], name)
        _require(0 < result[name] < 1, name + " must lie in (0,1)")
    _require(result["confidence_level"] == context["statistics"]["confidence_level"],
             "Plan confidence level differs from frozen protocol")
    _exact(plan["bootstrap"], ("resamples", "rng_seed", "quantile_method"), "Bootstrap plan")
    _integer(plan["bootstrap"]["resamples"], "Bootstrap resamples", minimum=1, maximum=MAX_RESAMPLES)
    _integer(plan["bootstrap"]["rng_seed"], "Bootstrap RNG seed")
    _require(plan["bootstrap"]["quantile_method"] == "linear", "Bootstrap quantile method must be linear")
    _exact(plan["sign_flip"], ("exact_max_seeds", "monte_carlo_resamples", "rng_seed"), "Sign-flip plan")
    _integer(plan["sign_flip"]["exact_max_seeds"], "Exact sign-flip threshold", minimum=1, maximum=16)
    _integer(plan["sign_flip"]["monte_carlo_resamples"], "Monte Carlo resamples", minimum=1, maximum=MAX_RESAMPLES)
    _integer(plan["sign_flip"]["rng_seed"], "Sign-flip RNG seed")
    endpoints = result["endpoints"]
    _require(type(endpoints) is dict and 1 <= len(endpoints) <= MAX_ENDPOINTS, "Invalid endpoint map size")
    cell_count = 0
    for name, endpoint in endpoints.items():
        _text(name, "Endpoint ID")
        _exact(endpoint, ("dataset", "metric", "units", "direction", "mode", "readout_config_sha256",
                          "split_manifest_sha256", "cells"), "Endpoint")
        for key in ("dataset", "metric", "units", "mode"):
            _text(endpoint[key], "Endpoint " + key)
        _require(endpoint["dataset"] in context["datasets"] and endpoint["mode"] in context["modes"],
                 "Endpoint dataset/mode is outside the frozen protocol")
        _require(endpoint["direction"] in ("lower", "higher"), "Endpoint direction must be lower/higher")
        for key in ("readout_config_sha256", "split_manifest_sha256"):
            _sha(endpoint[key], key)
        cells = endpoint["cells"]
        _require(type(cells) is list and 1 <= len(cells) <= MAX_CELLS, "Invalid endpoint cell count")
        seen = set()
        for cell in cells:
            _exact(cell, ("fold_id", "readout_seed", "weight", "sample_set_sha256", "label_mask_sha256"), "Endpoint cell")
            _text(cell["fold_id"], "Fold ID")
            _integer(cell["readout_seed"], "Readout seed")
            _require(cell["readout_seed"] in context["readout_seeds"], "Undeclared readout seed")
            pair = cell["fold_id"], cell["readout_seed"]
            _require(pair not in seen, "Duplicate endpoint cell")
            seen.add(pair)
            cell["weight"] = _finite(cell["weight"], "Cell weight", positive=True)
            _sha(cell["sample_set_sha256"], "Cell sample-set hash")
            _sha(cell["label_mask_sha256"], "Cell label-mask hash")
        _cell_weights(endpoint)
        cell_count += len(cells)
    _require(cell_count <= MAX_CELLS, "Total planned cells exceed the bound")
    comparisons = result["comparisons"]
    _require(type(comparisons) is list and 1 <= len(comparisons) <= MAX_COMPARISONS, "Invalid comparison count")
    ids, used_endpoints = set(), set()
    for comparison in comparisons:
        _exact(comparison, ("id", "endpoint", "coefficients", "pretraining_seeds"), "Comparison")
        name = _text(comparison["id"], "Comparison ID")
        _require(name not in ids, "Duplicate comparison ID")
        ids.add(name)
        endpoint = comparison["endpoint"]
        _require(type(endpoint) is str and endpoint in endpoints, "Comparison has undeclared endpoint")
        used_endpoints.add(endpoint)
        seeds = _seeds(comparison["pretraining_seeds"], "Comparison seeds", minimum=2)
        _require(set(seeds) <= set(context["seeds"]), "Comparison includes undeclared pretraining seeds")
        comparison["pretraining_seeds"] = seeds
        coefficients = comparison["coefficients"]
        _require(type(coefficients) is dict and 2 <= len(coefficients) <= len(VARIANTS) + len(context["contrasts"]),
                 "Comparison requires at least two declared nonzero coefficients")
        for condition, coefficient in coefficients.items():
            _text(condition, "Condition ID")
            coefficients[condition] = _finite(coefficient, "Contrast coefficient")
            _require(coefficients[condition] != 0, "Zero contrast coefficients must be omitted")
            if condition not in VARIANTS:
                _require(condition.startswith("contrast.") and condition[9:] in context["contrasts"], "Undeclared condition")
                _require(set(seeds) <= set(context["contrasts"][condition[9:]]["seeds"]), "Strategy contrast lacks selected seeds")
        scale = max(abs(value) for value in coefficients.values())
        scaled = [value / scale for value in coefficients.values()]
        _require(all(value != 0 for value in scaled), "Coefficient support underflows in float64")
        _require(abs(math.fsum(scaled)) <= 8 * _EPS * math.fsum(abs(value) for value in scaled),
                 "Linear contrast coefficients must sum to zero")
    _require(used_endpoints == set(endpoints), "Unused endpoints cannot masquerade as analyzed scope")
    families = result["families"]
    _require(type(families) is dict and 1 <= len(families) <= MAX_COMPARISONS, "Invalid family map")
    membership = []
    for name, members in families.items():
        _text(name, "Family ID")
        membership.extend(_strings(members, "Family comparison IDs"))
    _require(len(membership) == len(ids) and set(membership) == ids, "Families must exactly partition all comparisons")
    primary = _strings(result["primary_families"], "Primary family IDs")
    _require(set(primary) <= set(families), "Unknown primary family ID")
    declared_primary = {name for family in primary for name in families[family]}
    _require(declared_primary == set(context["primary"]), "Primary-family comparison IDs differ from protocol")
    # Bound the union grid before allocating record keys. Comparisons may share
    # the same condition/seed/endpoint cells, which are counted once.
    scopes = {}
    for comparison in comparisons:
        for condition in comparison["coefficients"]:
            scopes.setdefault((condition, comparison["endpoint"]), set()).update(comparison["pretraining_seeds"])
    required_rows = sum(len(seeds) * len(endpoints[endpoint]["cells"])
                        for (_, endpoint), seeds in scopes.items())
    _require(required_rows <= MAX_RECORDS, "Required metric grid exceeds the record bound")
    _canonical_hash(result)
    return result


def _grid(plan):
    scopes = {}
    for comparison in plan["comparisons"]:
        for condition in comparison["coefficients"]:
            scopes.setdefault((condition, comparison["endpoint"]), set()).update(comparison["pretraining_seeds"])
    expected = set()
    for (condition, endpoint), seeds in scopes.items():
        for seed in seeds:
            for cell in plan["endpoints"][endpoint]["cells"]:
                expected.add((condition, seed, endpoint, cell["fold_id"], cell["readout_seed"]))
                _require(len(expected) <= MAX_RECORDS, "Required metric grid exceeds the record bound")
    return expected


def _validated_records(plan, envelope, protocol, plan_sha256):
    _exact(envelope, ("schema_version", "protocol_content_sha256", "statistics_plan_sha256", "records"), "Metric envelope")
    _require(envelope["schema_version"] == RECORDS_SCHEMA
             and envelope["protocol_content_sha256"] == protocol["content_sha256"]
             and envelope["statistics_plan_sha256"] == plan_sha256, "Metric envelope protocol/plan bindings differ")
    rows = envelope["records"]
    expected = _grid(plan)
    _require(type(rows) is list and len(rows) == len(expected), "Metric grid is missing/extra/partial")
    fields = ("condition", "pretraining_seed", "endpoint", "fold_id", "readout_seed", "metric_value",
              "checkpoint_sha256", "shared_initialization_sha256", "initial_h0_sha256", "endpoint_h0_sha256",
              "pretraining_updates", "sample_set_sha256", "label_mask_sha256", "readout_config_sha256", "split_manifest_sha256")
    cells = {name: {(cell["fold_id"], cell["readout_seed"]): cell for cell in endpoint["cells"]}
             for name, endpoint in plan["endpoints"].items()}
    hashes = protocol["pretraining"]["paired_random_initialization"]["encoder_sha256_by_seed"]
    updates = protocol["pretraining"]["budget"]["optimizer_steps_per_condition"]
    values, checkpoint_bindings, initial_states = {}, {}, {}
    for row in rows:
        _exact(row, fields, "Metric record")
        for key in ("condition", "endpoint", "fold_id"):
            _text(row[key], key)
        _integer(row["pretraining_seed"], "Record pretraining seed")
        _integer(row["readout_seed"], "Record readout seed")
        key = tuple(row[field] for field in ("condition", "pretraining_seed", "endpoint", "fold_id", "readout_seed"))
        _require(key in expected and key not in values, "Metric record is duplicate or outside the declared grid")
        endpoint, cell = plan["endpoints"][row["endpoint"]], cells[row["endpoint"]][(row["fold_id"], row["readout_seed"])]
        for field in ("sample_set_sha256", "label_mask_sha256"):
            _require(row[field] == cell[field], "Record sample/mask hashes differ from frozen cell")
        for field in ("readout_config_sha256", "split_manifest_sha256"):
            _require(row[field] == endpoint[field], "Record setup hash differs from frozen endpoint")
        for field in ("checkpoint_sha256", "shared_initialization_sha256", "initial_h0_sha256", "endpoint_h0_sha256"):
            _sha(row[field], field)
        seed, condition = row["pretraining_seed"], row["condition"]
        _require(row["shared_initialization_sha256"] == hashes[str(seed)], "Shared initialization artifact differs")
        _integer(row["pretraining_updates"], "Record pretraining updates")
        _require(row["pretraining_updates"] == (0 if condition == "none" else updates), "Fixed pretraining endpoint updates differ")
        if condition == "none":
            _require(row["endpoint_h0_sha256"] == row["initial_h0_sha256"], "None endpoint H0 differs from paired initial H0")
        _require(initial_states.get(seed, row["initial_h0_sha256"]) == row["initial_h0_sha256"], "Initial H0 state is unpaired across conditions")
        initial_states[seed] = row["initial_h0_sha256"]
        binding = {field: row[field] for field in ("checkpoint_sha256", "shared_initialization_sha256",
                   "initial_h0_sha256", "endpoint_h0_sha256", "pretraining_updates")}
        pair = condition, seed
        _require(checkpoint_bindings.get(pair, binding) == binding, "Condition/seed checkpoint or H0 state changes across cells/endpoints")
        checkpoint_bindings[pair] = binding
        values[key] = _finite(row["metric_value"], "Scored metric value")
    _require(set(values) == expected, "Complete paired-grid coverage is required")
    bindings = [{"condition": condition, "pretraining_seed": seed, **value}
                for (condition, seed), value in sorted(checkpoint_bindings.items())]
    return values, bindings


def _chunk_size(n):
    return max(1, min(4096, 65536 // n))


def _sign_flip(effects, specification):
    n = len(effects)
    scale = float(np.max(np.abs(effects)))
    scaled = effects / scale if scale else np.zeros(n, dtype=np.float64)
    observed = abs(math.fsum(scaled.tolist()) / n)
    tolerance = 64 * _EPS * max(1.0, math.fsum(np.abs(scaled).tolist()) / n)
    exact = n <= specification["exact_max_seeds"]
    draws = 2 ** n if exact else specification["monte_carlo_resamples"]
    rng = np.random.default_rng(specification["rng_seed"])
    extreme, maximum_ties = 0, 0
    maximum_statistic = math.fsum(np.abs(scaled).tolist()) / n
    for start in range(0, draws, _chunk_size(n)):
        count = min(_chunk_size(n), draws - start)
        if exact:
            bits = (np.arange(start, start + count, dtype=np.uint32)[:, None]
                    >> np.arange(n, dtype=np.uint32)[None, :]) & 1
            signs = bits.astype(np.float64) * 2 - 1
        else:
            signs = rng.integers(0, 2, size=(count, n), dtype=np.int8).astype(np.float64) * 2 - 1
        statistics = np.abs((signs * scaled).sum(axis=1) / n)
        extreme += int(np.count_nonzero(statistics >= observed - tolerance))
        if exact:
            maximum_ties += int(np.count_nonzero(statistics >= maximum_statistic - tolerance))
    p = extreme / draws if exact else (extreme + 1) / (draws + 1)
    return {"method": "exact" if exact else "monte_carlo", "alternative": "two_sided",
            "n_independent": n, "draws": draws, "extreme_count": extreme, "p_value": p,
            "rng_seed": specification["rng_seed"], "exact_max_seeds": specification["exact_max_seeds"],
            "minimum_attainable_p": maximum_ties / draws if exact else (1.0 if scale == 0 else 1 / (draws + 1)),
            "nominal_two_sided_grid_resolution": 2 / draws if exact else None,
            "zero_effect_vector": scale == 0, "observed_absolute_scaled_mean": observed,
            "tie_tolerance_scaled": tolerance, "monte_carlo_plus_one_correction": not exact}


def _bootstrap(effects, specification, confidence, direction):
    n, draws = len(effects), specification["resamples"]
    scale = float(np.max(np.abs(effects)))
    scaled = effects / scale if scale else np.zeros(n, dtype=np.float64)
    rng = np.random.default_rng(specification["rng_seed"])
    means = np.empty(draws, dtype=np.float64)
    for start in range(0, draws, _chunk_size(n)):
        count = min(_chunk_size(n), draws - start)
        indices = rng.integers(0, n, size=(count, n))
        means[start:start + count] = scaled[indices].mean(axis=1)
    tail = (1 - confidence) / 2
    interval = np.quantile(means, [tail, 1 - tail], method="linear") * scale
    _require(bool(np.isfinite(interval).all()), "Bootstrap interval overflow")
    raw = interval.tolist()
    benefit = [-raw[1], -raw[0]] if direction == "lower" else list(raw)
    return {"method": "paired_pretraining_seed_percentile_v1", "resamples": draws,
            "rng_seed": specification["rng_seed"], "quantile_method": "linear",
            "confidence_level": confidence, "raw_ci": raw, "benefit_ci": benefit,
            "degenerate": raw[0] == raw[1], "resampling_unit": "whole_pretraining_seed_contrast"}


def analyze_paired_statistics(plan, records, protocol, *, plan_sha256, records_sha256) -> dict:
    """Compute frozen contrasts from a complete grid; no refitting or test selection."""
    normalized = validate_analysis_plan(plan, protocol)
    _sha(plan_sha256, "Caller plan file hash")
    _sha(records_sha256, "Caller records file hash")
    _require(plan_sha256 == protocol["downstream"]["statistics"]["analysis_plan_sha256"], "Plan artifact hash differs from protocol")
    values, bindings = _validated_records(normalized, records, protocol, plan_sha256)
    comparisons = {}
    for entry in normalized["comparisons"]:
        endpoint = normalized["endpoints"][entry["endpoint"]]
        weights = _cell_weights(endpoint)
        seed_effects, raw_effects = [], []
        for seed in entry["pretraining_seeds"]:
            means = {}
            for condition in entry["coefficients"]:
                observations = [values[(condition, seed, entry["endpoint"], cell["fold_id"], cell["readout_seed"])]
                                for cell in endpoint["cells"]]
                scale = max(abs(value) for value in observations)
                means[condition] = math.fsum((value / scale) * weight for value, weight in zip(observations, weights)) * scale if scale else 0.0
            try:
                effect = math.fsum(entry["coefficients"][condition] * value for condition, value in means.items())
            except (OverflowError, ValueError) as exc:
                raise PairedStatisticsError("Linear contrast overflows float64") from exc
            _require(math.isfinite(effect), "Linear contrast is nonfinite")
            benefit = -effect if endpoint["direction"] == "lower" else effect
            raw_effects.append(effect)
            seed_effects.append({"pretraining_seed": seed, "condition_means": means,
                                 "raw_effect": effect, "benefit_effect": benefit})
        effects = np.asarray(raw_effects, dtype=np.float64)
        scale = float(np.max(np.abs(effects)))
        mean = math.fsum((effects / scale).tolist()) / len(effects) * scale if scale else 0.0
        comparisons[entry["id"]] = {"endpoint": entry["endpoint"], "dataset": endpoint["dataset"],
            "metric": endpoint["metric"], "units": endpoint["units"], "direction": endpoint["direction"],
            "coefficients": dict(entry["coefficients"]), "pretraining_seeds": entry["pretraining_seeds"],
            "n_independent": len(effects), "seed_effects": seed_effects, "raw_mean_effect": mean,
            "benefit_mean_effect": -mean if endpoint["direction"] == "lower" else mean,
            "fixed_normalized_cell_weights": weights,
            "bootstrap": _bootstrap(effects, normalized["bootstrap"], normalized["confidence_level"], endpoint["direction"]),
            "sign_flip": _sign_flip(effects, normalized["sign_flip"])}
    families = {}
    for name, members in normalized["families"].items():
        ordered = sorted(members, key=lambda identifier: (comparisons[identifier]["sign_flip"]["p_value"], identifier))
        previous, rows = 0.0, []
        for rank, identifier in enumerate(ordered, 1):
            p = comparisons[identifier]["sign_flip"]["p_value"]
            adjusted = max(previous, min(1.0, (len(members) - rank + 1) * p))
            previous = adjusted
            rows.append({"comparison_id": identifier, "p_value": p, "holm_adjusted_p": adjusted,
                         "reject_holm": adjusted <= normalized["alpha"], "rank": rank})
        families[name] = {"comparison_ids": list(members), "primary": name in normalized["primary_families"],
                          "family_size": len(members), "alpha": normalized["alpha"], "holm": rows}
    result = {"schema_version": RESULT_SCHEMA, "method": METHOD, "status": "ANALYSIS_COMPLETE",
        "independent_unit": "pretraining_seed", "analysis_plan": normalized,
        "byte_bindings": {"protocol_content_sha256": protocol["content_sha256"], "plan_sha256": plan_sha256,
                          "records_sha256": records_sha256, "verification": "caller_declared_raw_byte_bindings; pure_function_does_not_read_files"},
        "normalized_plan_content_sha256": _canonical_hash(normalized), "record_count": len(values),
        "producer_declared_checkpoint_bindings": bindings, "comparisons": comparisons, "families": families,
        "computation_bounds": {"max_pretraining_seeds": MAX_SEEDS, "max_comparisons": MAX_COMPARISONS,
            "max_endpoints": MAX_ENDPOINTS, "max_total_cells": MAX_CELLS, "max_records": MAX_RECORDS,
            "max_resamples_per_comparison": MAX_RESAMPLES, "max_exact_sign_flip_seeds": 16,
            "max_sampling_array_elements": 65536, "caller_wall_rss_output_budget_required": True},
        "may_start_formal_training": False, "model_or_evaluation_truth_independently_verified": False,
        "limitations": ["Inference is conditional on the fixed benchmark, fold cells and readout settings; cells are not independent repeats.",
            "Sign-flip inference requires independent seed contrasts with null sign symmetry/exchangeability; shared initialization alone does not establish it.",
            "Small seed counts yield coarse attainable p-values; zero contrasts and degenerate percentile intervals are reported, not convergence evidence.",
            "Percentile intervals are marginal, not simultaneous Holm intervals; exclusion of zero is not the family significance decision.",
            "Distinct endpoint units/effects are never pooled. Family correction covers all declared comparisons, with no missing-cell reduction.",
            "Metric, checkpoint, state and evaluation provenance is producer-declared metadata; paired consistency is not independent verification of actual model results."]}
    result["analysis_sha256"] = _canonical_hash(result)
    return result
