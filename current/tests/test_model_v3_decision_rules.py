"""Rule boundaries with explicit synthetic policies, never scientific choices."""
from dataclasses import replace
import math

import pytest

from phychem_mfm.phase1.v3_decision_evidence import METRIC, RunEvidence, canonical
from phychem_mfm.phase1.v3_decision_rules import (AuxiliaryMetric, LR_GRID, RulePolicy,
    Stability, Timing, choose_batch, choose_c1, choose_c3, choose_heads,
    choose_learning_rate, choose_pooling, choose_schedule, doubling_plateau, propose_b_star)


def noise(sd=.125):
    return {"schema": "model_v3_global_seed_sd_artifact_v1", "status": "COMPLETE_BOUND_EVIDENCE",
        "metric": METRIC, "ddof": 1, "seed_count": 2, "pretraining_seeds": [11, 29],
        "scores": [0., sd*math.sqrt(2.)], "sample_standard_deviation": sd,
        "registration_sha256": "a"*64, "panel_identity_sha256": "b"*64,
        "scientific_identity_sha256": "c"*64, "bootstrap_confidence_interval_used": False}


def measurement(condition, candidate, score, seed=0, *, samples=100, run_id=None, curve=None):
    run_id = run_id or condition+"/"+candidate+"/"+str(seed)
    return RunEvidence(score, seed, canonical([condition, candidate]), "b"*64,
        canonical([run_id, samples]), run_id, 100., canonical(["evidence", run_id, samples]),
        {"synthetic_only": True}, samples, curve or canonical([condition, candidate, "curve"]))


def setup(name, conditions, candidates, scores=None, **rules):
    rows = {c: {a: [measurement(c, a, (scores or {}).get((c, a), .5))] for a in candidates} for c in conditions}
    identities = {c: {a: rows[c][a][0].scientific_identity_sha256 for a in candidates} for c in conditions}
    policy = RulePolicy({name: {"scientific_identities": identities, "seed_aggregation": "equal_seed_mean",
        "pretraining_seed_roles": {"initial": 0, "repeat": 1}, **rules}}, "d"*64, "e"*40, 0)
    return rows, policy


def timing(rows, candidate, condition, seconds):
    return Timing(seconds, "GPU-synthetic-same-device", canonical([condition, candidate, "timing"]),
                  tuple(sorted(r.training_run_id for r in rows[condition][candidate])))


def auxiliary(rows, condition, candidate, *, metric="accuracy", value=.75, scope="masked_element_only"):
    return AuxiliaryMetric(value, canonical([condition, candidate, metric]), canonical([condition, "population", scope]),
        tuple(sorted(r.training_run_id for r in rows[condition][candidate])), scope)


def test_c1_fastest_must_also_pass_separate_s_and_p_safeguards():
    rows, policy = setup("C1", ("S", "P"), ("C1-0", "C1-a", "C1-b"),
        {("S", "C1-a"): .55, ("P", "C1-a"): .55, ("S", "C1-b"): .3, ("P", "C1-b"): .9},
        cross_condition_ranking="equal_mean_S_P", timing_aggregation="equal_mean_S_P_seconds_per_million_samples")
    timings = {c: {a: timing(rows, a, c, t) for a, t in (("C1-0", 3.), ("C1-a", 2.), ("C1-b", 1.))} for c in rows}
    result = choose_c1(rows, noise(), policy, timings)
    assert result["selected"] == "C1-a" and "C1-b" not in result["eligible"]
    assert not result["frozen"] and result["input_evidence"]["S"]["C1-a"][0]["evidence_sha256"]
    altered = dict(timings["S"]); altered["C1-a"] = replace(altered["C1-a"], gpu_uuid="GPU-other")
    with pytest.raises(ValueError, match="Heterogeneous"):
        choose_c1(rows, noise(), policy, {**timings, "S": altered})


def test_c1_does_not_invent_cross_condition_ranking_or_exact_tie_break():
    rows, policy = setup("C1", ("S", "P"), ("C1-0", "C1-a", "C1-b"))
    assert choose_c1(rows, noise(), policy, {})["status"] == "MISSING_EVIDENCE"
    policy.rules["C1"].update(cross_condition_ranking="equal_mean_S_P", timing_aggregation="equal_mean_S_P_seconds_per_million_samples")
    timings = {c: {a: timing(rows, a, c, 1.) for a in rows[c]} for c in rows}
    assert choose_c1(rows, noise(), policy, timings)["status"] == "MISSING_POLICY"


def c3_fixture():
    rows, policy = setup("C3", ("S", "SDP"), ("two", "three"),
        {(c, "three"): .625 for c in ("S", "SDP")}, auxiliary_regression_thresholds={
            "masked_element_accuracy": {"direction": "higher", "scope": "masked_element_only", "maximum_regression": .01},
            "bond/mae": {"direction": "lower", "scope": "clean_bond", "maximum_regression": .02}})
    aux = {c: {a: {"masked_element_accuracy": auxiliary(rows, c, a),
                  "bond/mae": auxiliary(rows, c, a, metric="bond", value=.1, scope="clean_bond")}
               for a in rows[c]} for c in rows}
    return rows, policy, aux


def test_c3_inclusive_one_sd_requires_both_auxiliary_metrics():
    rows, policy, aux = c3_fixture()
    assert choose_c3(rows, noise(), policy, aux)["selected"] == "two"
    aux["S"]["two"]["masked_element_accuracy"] = replace(aux["S"]["two"]["masked_element_accuracy"], value=.7)
    assert choose_c3(rows, noise(), policy, aux)["selected"] == "three"
    aux["S"]["two"]["masked_element_accuracy"] = replace(aux["S"]["two"]["masked_element_accuracy"], value=None)
    assert choose_c3(rows, noise(), policy, aux)["status"] == "MISSING_EVIDENCE"


def test_c3_missing_preregistered_threshold_and_different_metric_population_rejected():
    rows, policy, aux = c3_fixture()
    policy.rules["C3"].pop("auxiliary_regression_thresholds")
    assert choose_c3(rows, noise(), policy, aux)["status"] == "MISSING_EVIDENCE"
    rows, policy, aux = c3_fixture()
    aux["S"]["two"]["bond/mae"] = replace(aux["S"]["two"]["bond/mae"], population_sha256="f"*64)
    with pytest.raises(ValueError, match="populations differ"):
        choose_c3(rows, noise(), policy, aux)


def test_heads_use_one_form_per_field_and_strict_group_r2_exception():
    rows, policy = setup("H", ("P", "D", "SDP"), ("H1", "H2", "H3"),
                         field_groups={"g": ["field_a", "field_b"]}, r2_scope="synthetic_preregistered_scope", r2_conditions={"g": "P"})
    def groups(a, b):
        return {"g": {h: auxiliary(rows, "P", h, value=v, scope="synthetic_preregistered_scope") for h, v in (("H1", a), ("H3", b))}}
    assert choose_heads(rows, noise(), policy, groups(.4, .95))["field_heads"] == {"field_a": "H2", "field_b": "H2"}
    assert choose_heads(rows, noise(), policy, groups(.5, .95))["field_heads"] == {"field_a": "H1", "field_b": "H1"}
    assert choose_heads(rows, noise(), policy, groups(.4, .9))["selected"] == "H1"
    assert choose_heads(rows, noise(), policy, {})["status"] == "MISSING_EVIDENCE"


def test_heads_do_not_assign_conflicting_forms_across_label_combinations():
    scores = {(c, h): .0 for c in ("P", "D", "SDP") for h in ("H1", "H2", "H3")}
    scores.update({("P", "H1"): .9, ("D", "H3"): .9, ("SDP", "H2"): .9})
    rows, policy = setup("H", ("P", "D", "SDP"), ("H1", "H2", "H3"), scores,
                         field_groups={"g": ["field"]}, r2_scope="synthetic_scope", r2_conditions={"g": "P"})
    result = choose_heads(rows, noise(), policy, {"g": {}})
    assert result["status"] == "REPORT_REQUIRED" and result["selected"] is None


def test_pooling_requires_strictly_more_than_the_global_sd():
    rows, policy = setup("pooling", ("P",), ("registry", "learned"), {("P", "learned"): .625})
    assert choose_pooling(rows, noise(), policy)["selected"] == "registry"
    rows["P"]["learned"] = [replace(rows["P"]["learned"][0], score=.626)]
    assert choose_pooling(rows, noise(), policy)["selected"] == "learned"


def lr_fixture(scores=None):
    rows, policy = setup("learning_rate", ("S", "P"), LR_GRID, scores,
        loss_spike_policy={"SYNTHETIC_EXAMPLE_ONLY": "external fixed numeric classifier"})
    policy_sha = canonical(policy.rules["learning_rate"]["loss_spike_policy"])
    verdicts = {c: {a: Stability(False, False, canonical([c, a, "stability"]), policy_sha,
        tuple(r.training_run_id for r in rows[c][a])) for a in LR_GRID} for c in rows}
    return rows, policy, verdicts


def test_lr_intersection_smaller_rate_tie_and_stability_exclusion():
    rows, policy, verdicts = lr_fixture({(c, "1e-4"): .75 for c in ("S", "P")} | {(c, "3e-4"): .875 for c in ("S", "P")})
    assert choose_learning_rate(rows, noise(), policy, verdicts)["selected"] == "1e-4"
    verdicts["S"]["1e-4"] = replace(verdicts["S"]["1e-4"], loss_spike=True)
    result = choose_learning_rate(rows, noise(), policy, verdicts)
    assert result["selected"] == "3e-4" and "1e-4" in result["excluded"]


def test_lr_reports_empty_s_p_intersection_and_missing_stability():
    rows, policy, verdicts = lr_fixture({("S", "1e-4"): .9, ("P", "2e-3"): .9})
    assert choose_learning_rate(rows, noise(), policy, verdicts)["status"] == "REPORT_REQUIRED"
    verdicts["S"]["1e-4"] = replace(verdicts["S"]["1e-4"], loss_spike=None)
    assert choose_learning_rate(rows, noise(), policy, verdicts)["status"] == "MISSING_EVIDENCE"


def test_batch_doubling_any_measured_regression_retains_b0():
    rows, policy = setup("batch", ("S", "P"), ("B0", "2B0"))
    assert choose_batch(rows, noise(), policy)["selected"] == "2B0"
    rows["P"]["2B0"] = [replace(rows["P"]["2B0"][0], score=.499)]
    assert choose_batch(rows, noise(), policy)["selected"] == "B0"


def test_schedule_prefers_wsd_within_sd_but_does_not_resolve_conflicting_tasks():
    rows, policy = setup("schedule", ("S", "P"), ("cosine", "wsd"), {(c, "wsd"): .375 for c in ("S", "P")}, wsd_decay_fraction=.15)
    assert choose_schedule(rows, noise(), policy)["selected"] == "wsd"
    rows["S"]["wsd"] = [replace(rows["S"]["wsd"][0], score=.9)]
    rows["P"]["wsd"] = [replace(rows["P"]["wsd"][0], score=.1)]
    assert choose_schedule(rows, noise(), policy)["status"] == "REPORT_REQUIRED"
    policy.rules["schedule"].pop("wsd_decay_fraction")
    assert choose_schedule(rows, noise(), policy)["status"] == "MISSING_EVIDENCE"


def test_comparisons_reject_panel_identity_science_drift_and_duplicate_repeat_seeds():
    rows, policy = setup("pooling", ("P",), ("registry", "learned"))
    original = rows["P"]["learned"][0]
    for changes, message in (({"panel_identity_sha256": "f"*64}, "panel/membership"),
                             ({"scientific_identity_sha256": "f"*64}, "scientific identity")):
        rows["P"]["learned"] = [replace(original, **changes)]
        with pytest.raises(ValueError, match=message): choose_pooling(rows, noise(), policy)
    rows["P"]["learned"] = [original, original]
    with pytest.raises(ValueError, match="distinct actual seeds"): choose_pooling(rows, noise(), policy)
    rows["P"]["learned"] = []
    assert choose_pooling(rows, noise(), policy)["status"] == "MISSING_EVIDENCE"


def curve(condition, pairs, *, endpoint="confirming", cap=64_000_000):
    identity = canonical([condition, "full-data-fixed-recipe"])
    points = [(count, measurement(condition, "curve", score, samples=count,
        run_id=condition+"-single-training-run", curve=identity)) for count, score in pairs]
    policy = RulePolicy({"budget": {"endpoint_policy": endpoint, "maximum_samples": cap,
        "curve_identities": {"S": canonical(["S", "full-data-fixed-recipe"]),
                             "P": canonical(["P", "full-data-fixed-recipe"])}}}, "d"*64, "e"*40, 0)
    return points, policy


def test_budget_strict_doubling_and_explicit_lower_vs_confirming_endpoint():
    points, policy = curve("S", [(1_000_000, .0), (2_000_000, .125), (4_000_000, .2)])
    result = doubling_plateau(points, noise(), policy=policy, condition="S")
    assert result["selected"] == 4_000_000 and result["lower_samples"] == 2_000_000
    policy.rules["budget"]["endpoint_policy"] = "lower"
    assert doubling_plateau(points, noise(), policy=policy, condition="S")["selected"] == 2_000_000
    policy.rules["budget"].pop("endpoint_policy")
    assert doubling_plateau(points, noise(), policy=policy, condition="S")["status"] == "MISSING_POLICY"
    points[1] = (3_000_000, points[1][1])
    with pytest.raises(ValueError, match="sample cursor"): doubling_plateau(points, noise(), policy=policy, condition="S")


def test_budget_missing_doubling_and_64m_cap_are_not_convergence():
    points, policy = curve("S", [(1_000_000, .0), (4_000_000, .25), (8_000_000, .3)])
    assert doubling_plateau(points, noise(), policy=policy, condition="S")["status"] == "MISSING_EVIDENCE"
    points, policy = curve("S", [(32_000_000, .0), (64_000_000, .25)])
    capped = doubling_plateau(points, noise(), policy=policy, condition="S")
    assert capped["status"] == "RIGHT_CENSORED" and capped["selected"] is None
    assert propose_b_star(capped, capped)["status"] == "MISSING_EVIDENCE"


@pytest.mark.parametrize("p_lower,expected", [(2_000_000, "USER_CONFIRMATION_REQUIRED"), (4_000_000, "REPORT_REQUIRED")])
def test_b_star_larger_budget_exact_2x_boundary_and_never_freezes(p_lower, expected):
    sp, policy = curve("S", [(1_000_000, .0), (2_000_000, .01)])
    pp, _ = curve("P", [(p_lower, .0), (2*p_lower, .01)])
    s = doubling_plateau(sp, noise(), policy=policy, condition="S")
    p = doubling_plateau(pp, noise(), policy=policy, condition="P")
    result = propose_b_star(s, p)
    assert result["selected"] == 2*p_lower and result["status"] == expected and not result["frozen"]
