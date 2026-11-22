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