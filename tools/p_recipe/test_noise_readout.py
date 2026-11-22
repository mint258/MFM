"""A1 continuation preserves the original R3 numerical experiment."""
import torch
import pytest
from noise_readout import run_resumable_probe
from finetune import ContinuationRequired
from phychem_mfm.phase1.v3_dev_readouts import run_probe
from phychem_mfm.phase1.v3_dev_evaluation import TaskSpec, TaskMolecule


class History:
    disabled=False
    def __init__(self):
        self.rows=[]
    def log(self,row,*,step,commit):
        self.rows.append((step,dict(row)))


def inputs(kind='graph'):
    rng=torch.Generator().manual_seed(81)
    def rows(prefix,count):
        result=[]
        for i in range(count):
            h=torch.randn(2+i%3,6,generator=rng)
            result.append(TaskMolecule(prefix+str(i//3),h,torch.arange(len(h)),
                torch.tensor([float(i%7)/9],dtype=torch.float64) if kind=="graph" else
                    torch.tensor([1.]+[0.]*(len(h)-1),dtype=torch.float64),
                torch.ones(1 if kind=="graph" else len(h),dtype=torch.bool),
                torch.ones(1 if kind=="graph" else len(h),dtype=torch.bool),
                prefix+"source"+str(i)))
        return result
    return rows("train",72),rows("eval",9),TaskSpec("test","qm9" if kind=="graph" else "cyp_isoform","target",kind,
        "mae" if kind=="graph" else "one_minus_hit1")


@pytest.mark.parametrize("kind",["graph","atom"])
@pytest.mark.parametrize("seed",[1,4])
def test_safe_R3_checkpointing_matches_original_predictions_and_updates(tmp_path,seed,kind):
    torch.set_num_threads(1)
    train,validation,task=inputs(kind)
    original_history,actual_history=History(),History()
    reference,old=run_probe(train,validation,task,readout="R3",n_ref=3.,
        seed=seed,device="cpu",tracker=original_history,relative_std_floor=True,
        internal_epoch_selection=True)
    actual,new=run_resumable_probe(train,validation,task,readout="R3",n_ref=3.,
        seed=seed,device="cpu",tracker=actual_history,relative_std_floor=True,
        internal_epoch_selection=True,state_path=tmp_path/"state.pt",
        source_identity={"checkpoint":"bound-original"},should_stop=lambda:False)
    assert torch.equal(torch.from_numpy(actual.predictions),torch.from_numpy(reference.predictions))
    assert actual_history.rows==original_history.rows
    assert new["updates"]==old["updates"] and new["selected_epoch"]==old["selected_epoch"]
    assert all(torch.equal(new["state_dict"][k],v) for k,v in old["state_dict"].items())


@pytest.mark.parametrize("kind",["graph","atom"])
def test_resume_after_three_updates_never_repeats_an_update_or_changes_rng(tmp_path,kind):
    train,validation,task=inputs(kind)
    reference_history,first,rest=History(),History(),History()
    params=dict(readout="R3",n_ref=3.,seed=2,device="cpu",
                relative_std_floor=True,internal_epoch_selection=True)
    reference,old=run_probe(train,validation,task,tracker=reference_history,**params)
    path=tmp_path/"state.pt"
    def stop():
        return sum("readout/update" in row for step,row in first.rows)>=3
    with pytest.raises(ContinuationRequired):
        run_resumable_probe(train,validation,task,tracker=first,**params,
            state_path=path,source_identity={"checkpoint":"one"},should_stop=stop)
    saved=torch.load(path,map_location="cpu",weights_only=True)
    assert saved["updates"]==3
    actual,new=run_resumable_probe(train,validation,task,tracker=rest,**params,
        state_path=path,source_identity={"checkpoint":"one"},should_stop=lambda:False)
    assert first.rows+rest.rows==reference_history.rows
    assert torch.equal(torch.from_numpy(actual.predictions),torch.from_numpy(reference.predictions))
    assert all(torch.equal(new["state_dict"][k],v) for k,v in old["state_dict"].items())
    with pytest.raises(ValueError,match="changed"):
        run_resumable_probe(train,validation,task,tracker=History(),**params,
            state_path=path,source_identity={"checkpoint":"different"},should_stop=lambda:False)
