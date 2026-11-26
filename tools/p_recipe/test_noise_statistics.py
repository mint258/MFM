"""A1 reuses seven old intervals and computes only missing CYP seed0 intervals."""
from dataclasses import replace
import copy
import json
import numpy as np
import pytest
import noise_statistics as core
from phychem_mfm.phase1.v3_dev_evaluation import TaskSpec,TaskPrediction,error,compare_panel
from phychem_mfm.phase1.v3_downstream_targets import PRIMARY_TASK_IDS


def graph(task,value):
    spec=TaskSpec(task,"qm9" if task.startswith("qm9.") else "expansionrx","target","graph","mae")
    return TaskPrediction(spec,("g0","g0","g1","g2"),np.zeros(4),
        np.full(4,value,dtype=np.float64),np.ones(4,dtype=bool),("r0","r1","r2","r3"))


def atom(task,hits):
    spec=TaskSpec(task,"cyp_isoform","target","atom","one_minus_hit1")
    return TaskPrediction(spec,tuple(uid for uid in ("g0","g0","g1","g2") for _ in range(2)),
        np.array([1.,0.]*4),np.array([v for hit in hits for v in
        ([2.,1.] if hit else [1.,2.])]),np.ones(8,dtype=bool),
        tuple(uid for uid in ("r0","r1","r2","r3") for _ in range(2)))


def inputs():
    predictions={t:[graph(t,v) for v in (2.,1.,2.,3.,4.)] for t in PRIMARY_TASK_IDS}
    reference={t:graph(t,4.) for t in PRIMARY_TASK_IDS}
    for task in ("cyp.2D6","cyp.3A4"):
        predictions[task]=[atom(task,v) for v in [
            [True,False,True,False],[True,True,True,False],[False]*4,[True]*4,[True,True,False,False]]]
        reference[task]=atom(task,[True,True,False,False])
    points={t:dict(error=error(p[0]),E_ref=error(reference[t]),
                   score=(error(reference[t])-error(p[0]))/error(reference[t]))
            for t,p in predictions.items()}
    summary=dict(included_tasks=list(PRIMARY_TASK_IDS),
        mean_normalized_improvement=.5,bootstrap_ci=[.3,.7],
        bootstrap_samples=1000,bootstrap_seed=20261025,bootstrap_unit="molecule",
        bootstrap_defined=1000,
        tasks={t:dict(bootstrap_ci=[.3,.7],bootstrap_defined=1000) for t in PRIMARY_TASK_IDS})
    return predictions,reference,points,summary


def test_primary_seed0_points_and_intervals_are_not_recomputed(monkeypatch):
    p,r,s,old=inputs()
    original_error=core.error
    forbidden={id(p[t][0]) for t in PRIMARY_TASK_IDS}|{id(r[t]) for t in PRIMARY_TASK_IDS}
    def spy(prediction,*args):
        assert id(prediction) not in forbidden
        return original_error(prediction,*args)
    monkeypatch.setattr(core,"error",spy)
    result=core.summarize_noise(p,r,s,old,input_identity={"source":"same"})
    assert result["status"]=="COMPLETE"
    rows={v["task"]:v for v in result["rows"]}
    expected=np.std([.5,.75,.5,.25,0.],ddof=1)
    for t in [*PRIMARY_TASK_IDS,"PRIMARY7_MEAN"]:
        assert rows[t]["score_seed_mean"]==pytest.approx(.4)
        assert rows[t]["score_seed_std"]==pytest.approx(expected)
        assert rows[t]["bootstrap_halfwidth_seed0"]==pytest.approx(.2)
        assert rows[t]["std_over_seed0_bootstrap_halfwidth"]==pytest.approx(expected/.2)
        assert rows[t]["bootstrap_halfwidth_origin"]=="existing_original_seed0_primary"
    assert rows["PRIMARY7_MEAN"]["propose_multiseed_readout"]
    assert rows["PRIMARY7_MEAN"]["tau_half_original_seed0_primary"]==.0125


def test_first_CYP_intervals_match_original_molecular_bootstrap_with_repeated_records():
    p,r,s,old=inputs()
    tasks=["cyp.2D6","cyp.3A4"]
    original=compare_panel({t:p[t][0] for t in tasks},{t:r[t] for t in tasks},
        architecture_sha256="same",reference_architecture_sha256="same",
        retain_paired_samples=True,retain_task_samples=True)
    result=core.summarize_noise(p,r,s,old,input_identity={"source":"same"})
    rows={v["task"]:v for v in result["rows"]}
    for t in tasks:
        assert result["retained_new_CYP_seed0"]["draws"][t]==original["paired_bootstrap"]["task_values"][t]
        assert rows[t]["bootstrap_seed0_ci_lower"]==original["tasks"][t]["bootstrap_ci"][0]
        assert rows[t]["bootstrap_seed0_ci_upper"]==original["tasks"][t]["bootstrap_ci"][1]
        assert rows[t]["bootstrap_defined"]<1000
        assert not rows[t]["included_in_primary_mean"]


def test_resume_after50_new_draws_preserves_RNG_and_refuses_changed_input():
    p,r,s,old=inputs()
    direct=core.summarize_noise(p,r,s,old,input_identity={"source":"same"})
    saved={}
    def checkpoint(state):
        saved["state"]=json.loads(json.dumps(state))
    partial=core.summarize_noise(p,r,s,old,input_identity={"source":"same"},
        checkpoint=checkpoint,should_stop=lambda:saved.get("state",{}).get("completed_draws",0)>=50)
    assert partial["status"]=="CONTINUATION_REQUIRED"
    assert saved["state"]["completed_draws"]==50
    resumed=core.summarize_noise(p,r,s,old,input_identity={"source":"same"},state=saved["state"])
    assert resumed==direct
    with pytest.raises(ValueError,match="identity changed"):
        core.summarize_noise(p,r,s,old,input_identity={"source":"different"},state=saved["state"])


def test_missing_readout_seed_and_wrong_native_task_are_rejected():
    p,r,s,old=inputs()
    task=next(iter(PRIMARY_TASK_IDS))
    p[task]=p[task][:-1]
    with pytest.raises(ValueError,match="seed0"):
        core.summarize_noise(p,r,s,old,input_identity={"source":"same"})
    p,r,s,old=inputs()
    r[task]=replace(r[task],task=replace(r[task].task,task_id="different"))
    with pytest.raises(ValueError,match="identity differs"):
        core.summarize_noise(p,r,s,old,input_identity={"source":"same"})
