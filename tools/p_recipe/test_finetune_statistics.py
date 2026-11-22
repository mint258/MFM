"""Synthetic primary-statistics tests; no real completed result is replayed."""
from dataclasses import replace
import copy
import json

import numpy as np
import pytest

from finetune_statistics import summarize, paired_contrast, TASKS
from phychem_mfm.phase1.v3_dev_evaluation import TaskSpec, TaskPrediction


def prediction(task, values):
    dataset = "qm9" if task.startswith("qm9.") else "expansionrx"
    spec = TaskSpec(task, dataset, "synthetic", "graph", "mae")
    return TaskPrediction(spec, ("g0","g0","g1","g2"), np.zeros(4),
        np.broadcast_to(values, (4,)).astype(np.float64).copy(), np.ones(4,dtype=bool),
        ("r0","r1","r2","r3"))


def inputs(kind="cancelling"):
    scratch = {task:[prediction(task,2.) for _ in range(3)] for task in TASKS}
    ref = {task:prediction(task,3.) for task in TASKS}
    values = (1.,-1.,0.) if kind=="cancelling" else (np.array([0.,1.,3.,5.]),)*3
    group = {task:[prediction(task,v) for v in values] for task in TASKS}
    identity = {"scratch":"bound-scratch-inputs","random_reference":"bound-original-R3",
                "conditions":{"candidate":"bound-new-primary-predictions"}}
    return {"candidate":group}, scratch, ref, identity


def test_seed_mean_and_mean_prediction_are_not_silently_conflated():
    groups,scratch,ref,identity = inputs()
    result = summarize(groups,scratch,ref,input_identity=identity)
    for row in result["rows"]:
        assert row["mae_seed_mean"] == pytest.approx(2/3)
        assert row["mae_seed_std"] > 0
        assert row["scratch_improvement_seed_mean"] == pytest.approx(2/3)
        assert row["ensemble_mae"] == 0
        assert row["ensemble_scratch_improvement"] == 1
        assert row["scratch_improvement_ensemble_ci_lower"] == 1
        assert row["scratch_improvement_ensemble_ci_upper"] == 1
        assert row["ci_estimand"] == "score_of_mean_prediction_not_mean_of_seed_scores"


def test_bootstrap_repeats_whole_molecules_with_all_native_records():
    groups,scratch,ref,identity = inputs("heterogeneous")
    result = summarize(groups,scratch,ref,input_identity=identity)
    rng = np.random.default_rng(20261025)
    # Same dataset order as the primary producer, one common draw per dataset.
    draws = {dataset:rng.choice(["g0","g1","g2"],3,replace=True).tolist()
             for dataset in ("expansionrx","qm9")}
    rows = {"g0":[0,1],"g1":[2],"g2":[3]}
    values = np.array([0.,1.,3.,5.])
    for task in TASKS:
        dataset = "qm9" if task.startswith("qm9.") else "expansionrx"
        indices = [i for group in draws[dataset] for i in rows[group]]
        actual = result["retained"]["draws"]["candidate/"+task]["mae"][0]
        assert actual == float(values[indices].mean())


def test_resume_keeps_identical_draws_without_restarting_the_primary():
    groups,scratch,ref,identity = inputs("heterogeneous")
    direct = summarize(groups,scratch,ref,input_identity=identity)
    progress = {}
    def save(state):
        progress["state"] = json.loads(json.dumps(state))
    partial = summarize(groups,scratch,ref,input_identity=identity,
        checkpoint=save, should_stop=lambda: progress.get("state",{}).get("completed_draws",0)>=50)
    assert partial["status"] == "CONTINUATION_REQUIRED"
    assert partial["state"]["completed_draws"] == 50
    resumed = summarize(groups,scratch,ref,input_identity=identity,state=progress["state"])
    assert resumed == direct
    wrong = copy.deepcopy(identity)
    wrong["conditions"]["candidate"] = "different-source"
    with pytest.raises(ValueError,match="identity"):
        summarize(groups,scratch,ref,input_identity=wrong,state=progress["state"])


def test_cross_batch_contrast_reuses_matched_retained_values_and_baselines():
    groups,scratch,ref,identity = inputs()
    first = summarize(groups,scratch,ref,input_identity=identity)
    second_groups = {"other":{task:[prediction(task,2.) for _ in range(3)] for task in TASKS}}
    other_identity = dict(identity,conditions={"other":"other-primary"})
    second = summarize(second_groups,scratch,ref,input_identity=other_identity)
    contrast = paired_contrast(first,"candidate","other","exp.LogD",right_primary=second)
    assert contrast["delta_seed_mean"] == pytest.approx(2/3)
    assert contrast["delta_ensemble"] == 1
    assert contrast["ensemble_ci_lower"] == contrast["ensemble_ci_upper"] == 1
    changed = copy.deepcopy(second)
    changed["retained"]["identity"]["input_identity"]["scratch"]="different-scratch"
    with pytest.raises(ValueError,match="bindings"):
        paired_contrast(first,"candidate","other","exp.LogD",right_primary=changed)


def test_different_native_masks_refuse_paired_statistics():
    groups,scratch,ref,identity = inputs()
    value = groups["candidate"]["exp.LogD"][0]
    groups["candidate"]["exp.LogD"][0] = replace(value,valid=np.array([True,False,True,True]))
    with pytest.raises(ValueError,match="masks"):
        summarize(groups,scratch,ref,input_identity=identity)

def test_common_scratch_mean_preserves_three_seed_mean_mae_ranking():
    # Paired per-seed ratios would rank A above B despite A's larger mean MAE.
    scratch = {task:[prediction(task,v) for v in (1.,10.,10.)] for task in TASKS}
    ref = {task:prediction(task,20.) for task in TASKS}
    groups = {
        "A":{task:[prediction(task,v) for v in (0.,6.,6.)] for task in TASKS},
        "B":{task:[prediction(task,2.) for _ in range(3)] for task in TASKS}}
    identity = {"scratch":"unequal-errors","random_reference":"fixed",
                "conditions":{"A":"a","B":"b"}}
    result = summarize(groups,scratch,ref,input_identity=identity)
    rows = {(r["condition"],r["task"]):r for r in result["rows"]}
    for task in TASKS:
        a,b = rows[("A",task)],rows[("B",task)]
        assert a["mae_seed_mean"] == 4.
        assert b["mae_seed_mean"] == 2.
        assert a["scratch_improvement_seed_mean"] == pytest.approx(3/7)
        assert b["scratch_improvement_seed_mean"] == pytest.approx(5/7)
        assert a["scratch_baseline_mae_seed_mean"] == 7.
        assert b["scratch_improvement_seed_mean"] > a["scratch_improvement_seed_mean"]


def test_frozen_reuse_keeps_one_real_seed_without_invented_variability():
    groups,scratch,ref,identity = inputs()
    frozen = {"original_R3":{task:prediction(task,1.) for task in TASKS}}
    identity["conditions"]["original_R3"] = "original-seed0-files"
    result = summarize(groups,scratch,ref,input_identity=identity,frozen=frozen)
    rows = [r for r in result["rows"] if r["condition"]=="original_R3"]
    assert len(rows) == 4
    for row in rows:
        assert row["seed_count"] == 1
        assert row["seed0_mae"] == 1.
        assert row["seed1_mae"] is None and row["seed2_mae"] is None
        assert row["mae_seed_std"] is None
        assert row["scratch_improvement_seed_std"] is None
        assert row["frozen_reference_score_seed_std"] is None
        assert row["scratch_improvement_seed_mean"] == .5
        assert row["scratch_improvement_ensemble_ci_lower"] == .5
        assert row["seed_policy"] == "original_frozen_R3_seed0_reused"
        assert row["frozen_training_disclosure"] == "existing_R3_30epochs_constant_lr"


def test_shared_scratch_baseline_allows_one_perfect_seed_but_refuses_zero_mean():
    groups,scratch,ref,identity = inputs()
    scratch = {task:[prediction(task,v) for v in (0.,2.,4.)] for task in TASKS}
    result = summarize(groups,scratch,ref,input_identity=identity)
    assert all(r["scratch_baseline_mae_seed_mean"]==2. for r in result["rows"])
    scratch = {task:[prediction(task,0.) for _ in range(3)] for task in TASKS}
    with pytest.raises(ValueError,match="denominator"):
        summarize(groups,scratch,ref,input_identity=identity)
