"""Synthetic E1 routing/seed-mean/selection checks only."""
import copy
import numpy as np
import pytest
from finetune_statistics import summarize,TASKS
from test_finetune_statistics import inputs
from e1_decision import compare_full,choose_k
from e1_readout_entry import make_readout
from pathlib import Path
import json

def test_e1_bootstrap_matches_seed_mean_and_rejects_unpaired_inputs():
    g,s,r,identity=inputs()
    p=summarize(g,s,r,input_identity=identity,seed_mean_draws=True)
    for row in p["rows"]:
        assert row["scratch_improvement_seed_mean_ci_lower"]==pytest.approx(2/3)
        assert row["scratch_improvement_seed_mean_ci_upper"]==pytest.approx(2/3)
        assert row["scratch_improvement_ensemble_ci_lower"]==1
    assert compare_full(p,p,"candidate","candidate")["decision"]["verdict"]=="tie"
    wrong=copy.deepcopy(p);wrong["retained"]["identity"]["groups"]["qm9"].append("unpaired")
    with pytest.raises(ValueError,match="differ"):compare_full(p,wrong,"candidate","candidate")

def test_e1_minimum_requires_both_readouts_and_confirms_selected_win():
    def row(a,b):return {"frozen_R3":{"decision":{"verdict":a}},"full":{"decision":{"verdict":b}}}
    rows={1:row("loss","win"),2:row("tie","win"),5:row("tie","tie"),10:row("tie","tie")}
    a=choose_k(rows);assert a["provisional_k_star"]==2 and a["conditional_seed1_required_for_adoption"]
    rows[2]=row("loss","tie");a=choose_k(rows);assert a["provisional_k_star"]==5 and not a["conditional_seed1_required_for_adoption"]

def test_e1_readout_uses_original_budget_layer_and_source():
    q=Path(__file__).resolve().parents[2]
    for k in (1,2,5):
        path=q/f"configs/p_recipe/E1_20261124/k{k}_managed_seed0_attempt2.json"
        source=json.loads(path.read_text())
        c=make_readout(source,path,"/synthetic/output","/synthetic/store")
        assert (c["samples"],c["layer"],c["representation"],c["readout_seed"])==(3000000,6,"H0",0)
        assert c["checkpoint"]==source["output"]+"/samples_3000000.pt"
        wrong=copy.deepcopy(source);wrong["training_configuration"]["lr"]=.0006
        with pytest.raises(ValueError,match="baseline"):make_readout(wrong,path,"/synthetic/output","/synthetic/store")
