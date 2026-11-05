"""Non-executing guide plans preserve dependencies, repeats and cost limits."""
from dataclasses import replace
import pytest

from phychem_mfm.phase1.v3_proxy_plan import (
    Evidence, PlannedTrial, architecture_plan, recipe_plan, plan_document,
    second_seed, stage_gpu_budget)


def refs():
    return Evidence("/owned/budget.json", "1"*64), Evidence("/owned/rules.json", "2"*64)


def architecture():
    budget, rules = refs()
    return architecture_plan(sample_budget=6_000_000, batch_base_samples=512,
                             budget_evidence=budget, rules_evidence=rules)


def test_adaptive_phases_cannot_bypass_selection_dependencies():
    trials = architecture()
    assert len(trials) == 20
    first = [t for t in trials if t.name.startswith("C1_")]
    assert {(t.condition, dict(t.parameters)["distance_bias"]) for t in first} == {
        (condition, candidate) for condition in ("S", "P") for candidate in ("C1-0", "C1-a", "C1-b")}
    for trial in trials:
        if trial.name.startswith("C3_"):
            assert "C1_selection_closed" in trial.requires
        elif trial.name.startswith("H_"):
            assert {"C1_selection_closed", "C3_selection_closed"} <= set(trial.requires)
    document = plan_document(trials, public_preregistration_sha="a"*40)
    assert document["status"] == "NOT_ADMITTED"
    assert document["starts_training"] is False
    assert document["provides_data_line_authority"] is False


def test_recipe_plan_separates_lr_batch_schedule_and_confirmation_gates():
    budget, rules = refs()
    trials = recipe_plan(sample_budget=6_000_000, batch_base_samples=256,
        selected_backbone=Evidence("/owned/architecture.json", "3"*64),
        budget_evidence=budget, rules_evidence=rules)
    assert len(trials) == 19
    assert len([t for t in trials if t.name.startswith("LR_")]) == 10
    for trial in trials:
        if trial.name.startswith("B2_"):
            assert dict(trial.parameters)["batch_base_samples"] == 512
            assert "LR_first_scan_closed" in trial.requires
        elif trial.name.startswith("Schedule_"):
            assert "LR_and_batch_consensus_closed" in trial.requires
            assert "schedule_policy_preregistered" in trial.requires
    final, = [t for t in trials if t.condition == "SDP"]
    assert {"TRAIN_preclip_p99_closed", "schedule_selection_closed"} <= set(final.requires)


def test_two_seed_repeats_preserve_scientific_identity_and_do_not_hide_failures():
    trials = architecture()
    selected = [trials[0].name, trials[2].name]
    repeats = second_seed(trials, selected_names=selected,
        selection_evidence=Evidence("/owned/selected.json", "4"*64))
    for original_name, item in zip(selected, repeats):
        original = next(t for t in trials if t.name == original_name)
        raw = item["trial"]
        repeated = PlannedTrial(raw["name"], raw["stage"], raw["condition"], raw["pretraining_seed"],
            raw["sample_budget"], tuple(raw["parameters"]), tuple(raw["requires"]))
        assert repeated.pretraining_seed != original.pretraining_seed
        assert repeated.name != original.name
        assert repeated.scientific_identity == original.scientific_identity
    with pytest.raises(ValueError):
        second_seed(trials, selected_names=[selected[0], selected[0]], selection_evidence=refs()[0])
    with pytest.raises(ValueError):
        second_seed(trials, selected_names=[selected[0], "unknown"], selection_evidence=refs()[0])


def test_changed_training_budget_or_condition_is_a_different_scientific_configuration():
    trial = architecture()[0]
    assert replace(trial, sample_budget=12_000_000).scientific_identity != trial.scientific_identity
    assert replace(trial, condition="P").scientific_identity != trial.scientific_identity
    assert replace(trial, pretraining_seed=1, name="repeat").scientific_identity == trial.scientific_identity


@pytest.mark.parametrize("stage,hours,complete,expected", [
    (5, 300 + 1/3600, True, "WITHIN_LIMIT"),
    (5, 450, True, "WITHIN_LIMIT"),
    (5, 450, False, "WITHIN_LIMIT"),
    (5, 450 + 1/3600, True, "STOP_REPORT_USER"),
    (5, 450 + 1/3600, False, "STOP_REPORT_USER"),
    (6, 750, True, "WITHIN_LIMIT"),
    (6, 750, False, "WITHIN_LIMIT"),
    (6, 750 + 1/3600, False, "STOP_REPORT_USER"),
])
def test_user_v3_budget_uses_threefold_confirmation_and_report_only_accounting(stage, hours, complete, expected):
    result = stage_gpu_budget(stage=stage, allocated_gpu_job_seconds=hours*3600, all_costs_registered=complete)
    assert result["status"] == expected
    assert result["estimate_multiplier"] == 3
    assert result["confirmation_limit_seconds"] == {5:450,6:750}[stage]*3600
    assert result["user_confirmation_required"] is (expected == "STOP_REPORT_USER")
    assert result["accounting_status"] == ("COMPLETE" if complete else "PENDING_REPORT_ONLY")
    assert result["all_failed_attempts_included"] is complete
    assert result["incomplete_accounting_blocks_science"] is False
    assert result["gpu_time_is_utilization"] is False


@pytest.mark.parametrize("invalid", [-1, float("nan"), float("inf"), True])
def test_invalid_cost_cannot_admit_work(invalid):
    with pytest.raises(ValueError):
        stage_gpu_budget(stage=6, allocated_gpu_job_seconds=invalid, all_costs_registered=True)


def test_source_evidence_and_duplicate_trial_rejection():
    with pytest.raises(ValueError):
        Evidence("/owned/x", "typo")
    trials = architecture()
    with pytest.raises(ValueError):
        plan_document((trials[0], trials[0]), public_preregistration_sha="a"*40)
    with pytest.raises(ValueError):
        architecture_plan(sample_budget=0, batch_base_samples=512,
                          budget_evidence=refs()[0], rules_evidence=refs()[1])
