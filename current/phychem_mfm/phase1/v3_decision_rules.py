"""Pure v3 rule proposals from bound evidence, never an admission/freeze gate.

Missing prerequisites, ambiguous rules and undefined metrics stay explicit.
Caller verifies a saved global SD with ``verify_global_seed_sd`` first. Policy
documents are fixed Git blobs and must predate every supplied actual run. These
functions do not launch jobs, inspect targets or select an SD reference config.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from functools import wraps
import math
from pathlib import Path
import hashlib

from .v3_decision_evidence import (METRIC, RunEvidence, canonical, digest,
    git_registration, require, _number)


LR_GRID = ("1e-4", "3e-4", "6e-4", "1e-3", "2e-3")


@dataclass(frozen=True)
class RulePolicy:
    rules: dict
    sha256: str
    commit: str
    commit_epoch: int
    reference: dict | None = None


def registered_policy(reference, *, expected_sha256):
    document, epoch = git_registration(reference, expected_sha256=expected_sha256)
    require(document.get("schema") == "model_v3_decision_policy_v1" and type(document.get("rules")) is dict,
            "Explicit preregistered decision policy required")
    return RulePolicy(document["rules"], expected_sha256, reference["commit"], epoch, reference)


@dataclass(frozen=True)
class AuxiliaryMetric:
    value: float | None
    source_sha256: str
    population_sha256: str
    run_ids: tuple[str, ...]
    scope: str


@dataclass(frozen=True)
class Timing:
    seconds_per_million_samples: float
    gpu_uuid: str
    source_sha256: str
    run_ids: tuple[str, ...]


@dataclass(frozen=True)
class Stability:
    diverged: bool | None
    loss_spike: bool | None
    source_sha256: str
    policy_sha256: str
    run_ids: tuple[str, ...]


def _result(status, *, selected=None, missing=(), **details):
    return {"schema": "model_v3_decision_rule_proposal_v1", "status": status,
        "frozen": False, "selected": selected, "missing": list(missing),
        "decision_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "remaining_admission_gates": ["stage-specific actual-data acceptance", "top-two repeat lineage where required",
                                      "user review before architecture/recipe/budget freeze"], **details}


def _missing(*items):
    return _result("MISSING_EVIDENCE", missing=items)


def _trace(function):
    def serializable(value):
        if is_dataclass(value): return serializable(asdict(value))
        if isinstance(value, dict): return {str(k): serializable(v) for k, v in value.items()}
        if isinstance(value, (tuple, list)): return [serializable(v) for v in value]
        return value
    @wraps(function)
    def wrapped(measurements, noise, policy, *args, **kwargs):
        result = function(measurements, noise, policy, *args, **kwargs)
        result["global_seed_sd_artifact_sha256"] = canonical(noise)
        result["policy_sha256"] = policy.sha256
        result["policy_commit"] = policy.commit
        result["policy_reference"] = policy.reference
        result["additional_evidence"] = {"positional": serializable(args), "keyword": serializable(kwargs)}
        result["input_evidence"] = {condition: {candidate: [
            {"evidence_sha256": run.evidence_sha256, "seed": run.seed,
             "scientific_identity_sha256": run.scientific_identity_sha256,
             "checkpoint_sha256": run.checkpoint_sha256, "score": run.score, "sources": run.sources} for run in runs]
            for candidate, runs in candidates.items()} for condition, candidates in measurements.items()}
        return result
    return wrapped


def _sd(noise):
    require(noise.get("schema") == "model_v3_global_seed_sd_artifact_v1"
            and noise.get("status") == "COMPLETE_BOUND_EVIDENCE" and noise.get("metric") == METRIC
            and noise.get("ddof") == 1 and noise.get("seed_count") == 2
            and noise.get("bootstrap_confidence_interval_used") is False, "Verified complete global seed-SD artifact required")
    digest(noise["registration_sha256"]); digest(noise["panel_identity_sha256"])
    digest(noise["scientific_identity_sha256"])
    seeds, scores = noise["pretraining_seeds"], noise["scores"]
    require(len(seeds) == len(scores) == 2 and all(type(s) is int and s >= 0 for s in seeds)
            and len(set(seeds)) == 2, "Exactly two distinct actual pretraining seeds required")
    expected = abs(_number(scores[0])-_number(scores[1]))/math.sqrt(2.)
    sd = _number(noise["sample_standard_deviation"])
    require(sd >= 0 and math.isclose(sd, expected, rel_tol=1e-12, abs_tol=1e-12), "Global sample SD differs")
    return sd


def _collect(measurements, noise, policy, name, conditions, candidates):
    """A bound policy ties each candidate label to its exact scientific identity."""
    sd = _sd(noise)
    require(isinstance(policy, RulePolicy), "Git-bound rule policy required")
    p = policy.rules.get(name)
    if not isinstance(p, dict):
        return None, None, sd, _missing("preregistered policy: "+name)
    if p.get("seed_aggregation") != "equal_seed_mean":
        return None, p, sd, _missing("preregistered complete-seed score aggregation: "+name)
    roles = p.get("pretraining_seed_roles", {})
    if (set(roles) != {"initial", "repeat"} or any(type(s) is not int or s < 0 for s in roles.values())
            or roles["initial"] == roles["repeat"]):
        return None, p, sd, _missing("preregistered initial/repeat pretraining seeds: "+name)
    bindings = p.get("scientific_identities")
    if not isinstance(bindings, dict):
        return None, p, sd, _missing("preregistered scientific identities: "+name)
    if set(measurements) != set(conditions) or set(bindings) != set(conditions):
        return None, p, sd, _missing("complete condition coverage: "+name)
    values, used_runs, used_checkpoints = {}, set(), set()
    for condition in conditions:
        if set(measurements[condition]) != set(candidates) or set(bindings[condition]) != set(candidates):
            return None, p, sd, _missing("complete candidate coverage: "+condition)
        values[condition] = {}
        for candidate in candidates:
            runs = measurements[condition][candidate]
            if not runs:
                return None, p, sd, _missing(condition+"/"+candidate+" actual complete panel")
            require(type(runs) in (tuple, list) and 1 <= len(runs) <= 2 and all(isinstance(r, RunEvidence) for r in runs),
                    "One/two inspected actual pretraining runs per candidate required")
            require(len({r.seed for r in runs}) == len(runs), "Candidate repeats must have distinct actual seeds")
            expected_seeds = {roles["initial"]} if len(runs) == 1 else set(roles.values())
            require({r.seed for r in runs} == expected_seeds, "Candidate's actual initial/repeat seeds differ from preregistration")
            expected = digest(bindings[condition][candidate])
            require(all(r.scientific_identity_sha256 == expected for r in runs), "Candidate's registered scientific identity differs")
            require(all(r.panel_identity_sha256 == noise["panel_identity_sha256"] for r in runs),
                    "All comparisons must use the global anchor's complete panel/membership")
            require(all(policy.commit_epoch < r.training_start_epoch for r in runs), "Rule policy must precede each actual training start")
            for run in runs:
                digest(run.evidence_sha256); digest(run.checkpoint_sha256)
                require(run.training_run_id not in used_runs and run.checkpoint_sha256 not in used_checkpoints,
                        "A training run/checkpoint cannot be reused as another candidate")
                used_runs.add(run.training_run_id); used_checkpoints.add(run.checkpoint_sha256)
            values[condition][candidate] = math.fsum(_number(r.score) for r in runs)/len(runs)
    return values, p, sd, None


def _runs(measurements, condition, candidate):
    return tuple(sorted(run.training_run_id for run in measurements[condition][candidate]))


@_trace
def choose_c1(measurements, noise, policy, timings):
    candidates = ("C1-0", "C1-a", "C1-b")
    values, p, sd, error = _collect(measurements, noise, policy, "C1", ("S", "P"), candidates)
    if error: return error
    if p.get("cross_condition_ranking") not in ("equal_mean_S_P", "worst_condition"):
        return _missing("preregistered C1 cross-condition ranking")
    if p.get("timing_aggregation") != "equal_mean_S_P_seconds_per_million_samples":
        return _missing("preregistered C1 timing aggregation")
    if set(timings) != {"S", "P"} or any(set(timings[c]) != set(candidates) for c in timings):
        return _missing("complete comparable S/P timings")
    hardware, speed = set(), {}
    for candidate in candidates:
        rows = []
        for condition in ("S", "P"):
            timing = timings[condition][candidate]
            require(isinstance(timing, Timing) and timing.run_ids == _runs(measurements, condition, candidate),
                    "Timing must bind the actual candidate runs")
            digest(timing.source_sha256)
            require(type(timing.gpu_uuid) is str and timing.gpu_uuid.startswith("GPU-")
                    and _number(timing.seconds_per_million_samples) > 0, "Actual same-GPU timing required")
            hardware.add(timing.gpu_uuid); rows.append(timing.seconds_per_million_samples)
        speed[candidate] = math.fsum(rows)/2
    require(len(hardware) == 1, "Heterogeneous GPU timings cannot choose fastest C1")
    if all(all(values[c][a] < values[c]["C1-0"]-sd for c in ("S", "P")) for a in ("C1-a", "C1-b")):
        return _result("RULE_PROPOSAL", selected="C1-0", reason="both alternatives worse by >1 SD on both conditions")
    ranking = {a: (math.fsum(values[c][a] for c in ("S", "P"))/2
                    if p["cross_condition_ranking"] == "equal_mean_S_P" else min(values[c][a] for c in ("S", "P")))
               for a in candidates}
    best = max(ranking.values())
    eligible = [a for a in candidates if ranking[a] >= best-sd
                and all(values[c][a] >= values[c]["C1-0"]-sd for c in ("S", "P"))]
    if not eligible:
        return _result("REPORT_REQUIRED", reason="no candidate satisfies both ranking and separate S/P safeguards")
    fastest = min(speed[a] for a in eligible)
    winners = [a for a in eligible if speed[a] == fastest]
    if len(winners) != 1:
        return _result("MISSING_POLICY", missing=("exact timing tie-break policy",), eligible=eligible)
    return _result("RULE_PROPOSAL", selected=winners[0], eligible=eligible, ranking=ranking, timings=speed)


@_trace
def choose_c3(measurements, noise, policy, auxiliary):
    values, p, sd, error = _collect(measurements, noise, policy, "C3", ("S", "SDP"), ("two", "three"))
    if error: return error
    thresholds = p.get("auxiliary_regression_thresholds")
    if not isinstance(thresholds, dict) or "masked_element_accuracy" not in thresholds or not any(k.startswith("bond/") for k in thresholds):
        return _missing("preregistered masked-element and clean-bond metric directions/thresholds")
    regressions = []
    for condition in ("S", "SDP"):
        for metric, rule in thresholds.items():
            if rule.get("direction") not in ("higher", "lower") or rule.get("scope") not in ("masked_element_only", "clean_bond"):
                return _missing("explicit auxiliary metric direction/population: "+metric)
            require((metric == "masked_element_accuracy") == (rule["scope"] == "masked_element_only"), "Auxiliary masking/clean-bond scope differs")
            limit = _number(rule["maximum_regression"])
            require(limit >= 0, "Nonnegative preregistered regression tolerance required")
            rows = []
            for candidate in ("two", "three"):
                row = auxiliary.get(condition, {}).get(candidate, {}).get(metric)
                if not isinstance(row, AuxiliaryMetric) or row.value is None:
                    return _missing(condition+"/"+candidate+"/"+metric+" (N/A is not evidence)")
                require(row.scope == rule["scope"] and row.run_ids == _runs(measurements, condition, candidate), "Auxiliary metric run/scope differs")
                digest(row.source_sha256); digest(row.population_sha256); _number(row.value)
                rows.append(row)
            require(rows[0].population_sha256 == rows[1].population_sha256, "Auxiliary metric populations differ")
            drop = (rows[1].value-rows[0].value)*(1 if rule["direction"] == "higher" else -1)
            if drop > limit: regressions.append(condition+"/"+metric)
    within = all(values[c]["two"] >= values[c]["three"]-sd for c in ("S", "SDP"))
    return _result("RULE_PROPOSAL", selected="two" if within and not regressions else "three",
                   within_global_one_sd=within, auxiliary_regressions=regressions)


@_trace
def choose_heads(measurements, noise, policy, group_r2):
    candidates = ("H1", "H2", "H3")
    values, p, sd, error = _collect(measurements, noise, policy, "H", ("P", "D", "SDP"), candidates)
    if error: return error
    groups, scope = p.get("field_groups"), p.get("r2_scope")
    if not isinstance(groups, dict) or not groups or not isinstance(scope, str) or not scope or set(group_r2) != set(groups):
        return _missing("registry-bound field groups and preregistered group R2 scope/evidence")
    if not isinstance(p.get("r2_conditions"), dict) or set(p["r2_conditions"]) != set(groups):
        return _missing("preregistered condition supplying each group's H1/H3 R2")
    fields = [field for names in groups.values() for field in names]
    require(all(type(names) is list and names for names in groups.values())
            and all(type(f) is str and f for f in fields) and len(set(fields)) == len(fields), "Each registry field belongs to exactly one head group")
    eligible = {c: [h for h in candidates if values[c][h] >= max(values[c].values())-sd] for c in values}
    common = [h for h in candidates if all(h in eligible[c] for c in eligible)]
    if not common:
        return _result("REPORT_REQUIRED", eligible=eligible, reason="no common within-1-SD form; field-consistent assignment needs explicit review")
    exceptions = []
    for group, metrics in group_r2.items():
        if set(metrics) != {"H1", "H3"} or any(not isinstance(m, AuxiliaryMetric) or m.value is None for m in metrics.values()):
            return _missing("defined H1/H3 R2 for group: "+group)
        a, b = metrics["H1"], metrics["H3"]
        require(a.scope == b.scope == scope and a.population_sha256 == b.population_sha256, "Group R2 scope/population differs")
        condition = p["r2_conditions"][group]
        require(condition in measurements, "Registered group-R2 condition is unavailable")
        for head, row in metrics.items():
            digest(row.source_sha256); digest(row.population_sha256); _number(row.value)
            require(row.run_ids == _runs(measurements, condition, head),
                    "Group R2 does not bind the registered condition's corresponding actual head runs")
        if a.value < .5 and b.value > .9: exceptions.append(group)
    assignment = {field: ("H2" if group in exceptions else common[0]) for group, names in groups.items() for field in names}
    return _result("RULE_PROPOSAL", selected=common[0], field_heads=assignment,
                   same_field_in_all_label_combinations=True, exception_groups=exceptions, eligible=eligible)


@_trace
def choose_pooling(measurements, noise, policy):
    values, _, sd, error = _collect(measurements, noise, policy, "pooling", ("P",), ("registry", "learned"))
    if error: return error
    gain = values["P"]["learned"]-values["P"]["registry"]
    return _result("RULE_PROPOSAL", selected="learned" if gain > sd else "registry", improvement=gain)


@_trace
def choose_learning_rate(measurements, noise, policy, stability, *, failure_exclusions=None):
    grid = LR_GRID
    failed = set()
    if failure_exclusions:
        from copy import deepcopy
        from dataclasses import replace
        from .v3_recipe_evidence import verify_failure_exclusions
        failed = verify_failure_exclusions(failure_exclusions, measurements, policy)
        grid = tuple(r for r in LR_GRID if r not in failed)
        if not grid:
            return _result("REPORT_REQUIRED", reason="all rates excluded by actual numeric failures", excluded=sorted(failed))
        measurements = {c: {r: measurements[c][r] for r in grid} for c in ("S", "P")}
        rules = deepcopy(policy.rules)
        rules["learning_rate"]["scientific_identities"] = {
            c: {r: rules["learning_rate"]["scientific_identities"][c][r] for r in grid} for c in ("S", "P")}
        policy = replace(policy, rules=rules)
    values, p, sd, error = _collect(measurements, noise, policy, "learning_rate", ("S", "P"), grid)
    if error: return error
    if not p.get("loss_spike_policy"):
        return _missing("quantitative preregistered loss-spike classification policy")
    stability_sha = canonical(p["loss_spike_policy"])
    excluded = list(failed)
    for rate in grid:
        for condition in ("S", "P"):
            row = stability.get(condition, {}).get(rate)
            if not isinstance(row, Stability) or row.diverged is None or row.loss_spike is None:
                return _missing("actual stability evidence: "+condition+"/"+rate)
            require(type(row.diverged) is type(row.loss_spike) is bool and row.policy_sha256 == stability_sha
                    and row.run_ids == _runs(measurements, condition, rate), "Stability policy/run binding differs")
            digest(row.source_sha256)
            if row.diverged or row.loss_spike: excluded.append(rate)
    allowed = [r for r in grid if r not in excluded]
    if not allowed:
        return _result("REPORT_REQUIRED", reason="all scanned rates excluded by stability", excluded=sorted(set(excluded)))
    near = {c: [r for r in allowed if values[c][r] >= max(values[c][x] for x in allowed)-sd] for c in values}
    common = [r for r in allowed if all(r in near[c] for c in near)]
    if not common:
        return _result("REPORT_REQUIRED", reason="no learning rate within 1 SD of both S and P optima", eligible=near)
    return _result("RULE_PROPOSAL", selected=min(common, key=float), eligible=near, excluded=sorted(set(excluded)))


@_trace
def choose_batch(measurements, noise, policy):
    values, _, _, error = _collect(measurements, noise, policy, "batch", ("S", "P"), ("B0", "2B0"))
    if error: return error
    regressed = [c for c in values if values[c]["2B0"] < values[c]["B0"]]
    return _result("RULE_PROPOSAL", selected="B0" if regressed else "2B0", regressed_conditions=regressed)


@_trace
def choose_schedule(measurements, noise, policy):
    values, p, sd, error = _collect(measurements, noise, policy, "schedule", ("S", "P"), ("cosine", "wsd"))
    if error: return error
    if type(p.get("wsd_decay_fraction")) not in (int, float) or not .1 <= p["wsd_decay_fraction"] <= .2:
        return _missing("exact preregistered WSD decay fraction in [0.1,0.2]")
    near = {name: all(values[c][name] >= max(values[c].values())-sd for c in values)
            for name in ("cosine", "wsd")}
    if not any(near.values()):
        return _result("REPORT_REQUIRED", reason="S/P schedule preferences conflict by more than global 1 SD")
    selected = "wsd" if near["wsd"] else "cosine"
    return _result("RULE_PROPOSAL", selected=selected, wsd_decay_fraction=p["wsd_decay_fraction"])


def doubling_plateau(points, noise, *, policy=None, condition=None, maximum_samples=64_000_000):
    """points: sorted (sample_count, RunEvidence) from ONE continuing S or P run.

    An absent exact doubling is incomplete evidence. The guide's lower-vs-upper
    endpoint ambiguity stays explicit; no silent interpretation of 'earliest'.
    """
    sd = _sd(noise)
    if not points: return _missing("complete checkpoint development curve")
    require(type(maximum_samples) is int and maximum_samples > 0, "Explicit maximum sample cap required")
    counts = [count for count, _ in points]
    require(all(type(c) is int and 0 < c <= maximum_samples for c in counts)
            and counts == sorted(set(counts)), "Strictly increasing unique sample counts required")
    runs = [run for _, run in points]
    require(all(isinstance(run, RunEvidence) and run.panel_identity_sha256 == noise["panel_identity_sha256"] for run in runs),
            "Complete, same-panel checkpoint evidence required")
    require(len({run.training_run_id for run in runs}) == len({run.seed for run in runs}) == 1,
            "Budget curve must continue one actual training run/seed")
    require(len({run.checkpoint_sha256 for run in runs}) == len(runs), "Distinct checkpoint bytes required")
    require(all(run.checkpoint_samples == count for count, run in points), "Curve x-axis differs from actual checkpoint sample cursor")
    require(len({run.curve_identity_sha256 for run in runs}) == 1, "Budget curve recipe/data/architecture differs")
    p = policy.rules.get("budget", {}) if isinstance(policy, RulePolicy) else {}
    endpoint_policy = p.get("endpoint_policy")
    if p.get("maximum_samples") != maximum_samples or condition not in ("S", "P"):
        return _missing("preregistered S/P budget cap and endpoint policy")
    if p.get("curve_identities", {}).get(condition) != runs[0].curve_identity_sha256:
        return _missing("preregistered full-data S/P curve scientific identity")
    require(all(policy.commit_epoch < run.training_start_epoch for run in runs), "Budget policy must precede actual curve start")
    table = {count: _number(run.score) for count, run in points}
    pairs = [(c, 2*c, table[2*c]-table[c]) for c in counts if 2*c in table]
    if not pairs: return _missing("at least one exact sample-count doubling")
    for lower, confirming, improvement in pairs:
        # A later pair cannot certify 'earliest' when an earlier checkpoint has
        # no confirming doubling (which might itself have met the criterion).
        if any(c < lower and 2*c not in table for c in counts):
            return _missing("earlier checkpoint's missing confirming doubling")
        if improvement < sd:
            if endpoint_policy not in ("lower", "confirming"):
                return _result("MISSING_POLICY", missing=("preregistered lower/confirming plateau endpoint",),
                    lower_samples=lower, confirming_samples=confirming, improvement=improvement)
            return _result("RULE_PROPOSAL", selected=lower if endpoint_policy == "lower" else confirming,
                lower_samples=lower, confirming_samples=confirming, improvement=improvement, endpoint_policy=endpoint_policy,
                global_sd_registration_sha256=noise["registration_sha256"], policy_sha256=policy.sha256,
                global_seed_sd_artifact_sha256=canonical(noise), policy_reference=policy.reference,
                input_evidence=[{"samples": c, "evidence_sha256": r.evidence_sha256, "sources": r.sources} for c, r in points],
                condition=condition, curve_identity_sha256=runs[0].curve_identity_sha256)
    return _result("RIGHT_CENSORED" if counts[-1] == maximum_samples else "INCOMPLETE_CURVE",
                   reason="no measured doubling meets strict improvement < global seed SD", selected=None)


def propose_b_star(s_plateau, p_plateau):
    if any(v.get("status") != "RULE_PROPOSAL" or type(v.get("selected")) is not int for v in (s_plateau, p_plateau)):
        return _missing("both S/P converged development-budget proposals (a cap is not convergence)")
    if (s_plateau.get("endpoint_policy") != p_plateau.get("endpoint_policy")
            or s_plateau.get("policy_sha256") != p_plateau.get("policy_sha256")
            or s_plateau.get("global_sd_registration_sha256") != p_plateau.get("global_sd_registration_sha256")
            or s_plateau.get("condition") != "S" or p_plateau.get("condition") != "P"):
        return _missing("the same preregistered S/P plateau endpoint interpretation")
    a, b = s_plateau["selected"], p_plateau["selected"]
    require(min(a, b) > 0, "Positive actual S/P budgets required")
    ratio = max(a, b)/min(a, b)
    return _result("REPORT_REQUIRED" if ratio > 2 else "USER_CONFIRMATION_REQUIRED",
        selected=max(a, b), s_samples=a, p_samples=b, ratio=ratio,
        input_proposals={"S": s_plateau, "P": p_plateau},
        reason="S/P budgets differ by >2x" if ratio > 2 else "concrete recipe and B* require user confirmation")
