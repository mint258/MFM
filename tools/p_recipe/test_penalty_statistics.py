"""Only new A3 decomposition, original-objective and saved-prefix contracts."""
import ast
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pytest
import torch
import phychem_mfm.phase1.p_recipe_training as original
from phychem_mfm.phase1.p_recipe import collapse_penalty
from penalty_statistics import (b4_terms,p_objective,validate_prefix,
                                summarize_batches,intervention_condition)


@pytest.mark.parametrize("constant",[False,True])
def test_native_terms_recompose_original_penalty_bitwise(constant):
    h=torch.randn(43,17,generator=torch.Generator().manual_seed(20261123))
    if constant:h[:,::3]=.125
    hinge,decor=b4_terms(h,.1597693323500406)
    assert torch.equal(hinge+decor,collapse_penalty(h,.1597693323500406))


def test_masked_P_fields_recompose_the_actual_original_T2_calculate():
    tree=ast.parse(Path(original.__file__).read_text())
    train=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=="train")
    calculate=next(n for n in train.body if isinstance(n,ast.FunctionDef) and n.name=="calculate")
    h=torch.randn(9,5,generator=torch.Generator().manual_seed(16))
    loss=SimpleNamespace(fields=dict(a=torch.tensor(.125),b=torch.tensor(.375),masked=torch.tensor(99.)),
                         counts=dict(a=3,b=5,masked=0),total=torch.tensor(0.))
    calls=[]
    class PD:
        encoder=None
        grouped_fields=True
        def predict(self,*args,**kwargs):calls.append("predict");return {}
        def loss(self,*args,**kwargs):return loss
    namespace=dict(original.__dict__,pd=PD(),fields=("a","b","masked"),
        families=dict(a="one",b="two",masked="one"),recipe=dict(anti_collapse=True),
        model={},gamma=.1597693323500406,encode_samples=lambda *args,**kw:(None,h))
    exec(compile(ast.Module(body=[calculate],type_ignores=[]),"<original calculate>","exec"),namespace)
    expected,_,_=namespace["calculate"]([])
    hinge,decor=b4_terms(h,namespace["gamma"])
    assert torch.equal(p_objective(loss)+.1*(hinge+decor),expected)
    assert calls==["predict"]


def records():
    fixed=list(range(48))
    return fixed,[dict(batch_index=0,molecule_indices=fixed[:32],molecules=32,
                       hinge=1.,decorrelation=2.,B4=3.,weighted_B4=.3,P_loss=2.),
                  dict(batch_index=1,molecule_indices=fixed[32:],molecules=16,
                       hinge=4.,decorrelation=2.,B4=6.,weighted_B4=.6,P_loss=8.)]


def test_saved_prefix_preserves_completed_batches_and_rejects_changed_population():
    fixed,rows=records()
    assert validate_prefix(rows[:1],fixed,32)==1
    changed=[dict(rows[0],molecule_indices=list(reversed(fixed[:32])))]
    with pytest.raises(ValueError,match="prefix"):
        validate_prefix(changed,fixed,32)
    with pytest.raises(ValueError,match="unfinished"):
        summarize_batches(rows[:1],fixed,32)


def test_partial_native_batch_and_undefined_denominator_are_not_silently_reweighted():
    fixed,rows=records();summary=summarize_batches(rows,fixed,32)
    assert summary["molecules"]==48 and summary["native_batches"]==2
    assert summary["hinge"]==2. and summary["decorrelation"]==2.
    assert summary["P_loss"]==4. and summary["weighted_B4_over_P"]==pytest.approx(.1,abs=1e-15)
    zero=[dict(r,P_loss=0.) for r in rows]
    assert summarize_batches(zero,fixed,32)["weighted_B4_over_P"] is None
    report=[dict(checkpoint_samples=n,weighted_B4_over_P=(None if n==1000000 else .2))
            for n in [1000000,3000000,6000000,9000000]]
    assert intervention_condition(report)["I2_triggered"] is None
    report[0]["weighted_B4_over_P"]=.1
    assert intervention_condition(report)["I2_triggered"] is True

@pytest.mark.parametrize("change",[None,"family_equal","field_loss_multipliers"])
def test_only_original_T2_native_branch_can_enter(change):
    from penalty_entry import validate_model_configuration
    c=dict(batch_size=32,microbatch_size=32,activation_checkpointing=False,
           mean_labels=False,source="PM7",samples=9000000,
           p_recipe=dict(anti_collapse=True),
           step_overhead=dict(grouped_fields=True,prepared_input=True))
    if change:
        c["p_recipe"][change]=({"a":2.} if change=="field_loss_multipliers" else True)
        with pytest.raises(ValueError,match="branch"):
            validate_model_configuration(c)
    else:
        assert validate_model_configuration(c)==c["p_recipe"]
