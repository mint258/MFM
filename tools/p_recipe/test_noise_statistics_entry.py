"""Selected original scalar rows stay stable while other runs append to scores."""
import csv
import pytest
from noise_statistics_entry import original_points
from phychem_mfm.phase1.v3_downstream_targets import PRIMARY_TASK_IDS


def inputs(tmp_path):
    path=tmp_path/"scores.csv"
    fields=["run","samples","readout","task","error","E_ref","score"]
    rows=[dict(run="bound",samples=1000000,readout="R3",task=t,error=.5,E_ref=1.,score=.5)
          for t in ("cyp.2D6","cyp.3A4")]
    with path.open("w",newline="") as stream:
        w=csv.DictWriter(stream,fieldnames=fields);w.writeheader();w.writerows(rows)
    manifest=dict(run="bound",samples=1000000,files={t+"/R3":"unopened.pt" for t in
        [*PRIMARY_TASK_IDS,"cyp.2D6","cyp.3A4"]})
    manifest["files"]["unused/R1"]="never-open-R1.pt"
    summary=dict(tasks={t:dict(error=2.,reference_error=4.,normalized_improvement=.5)
                        for t in PRIMARY_TASK_IDS})
    return path,fields,rows,manifest,summary


def test_unrelated_appends_do_not_change_selected_original_seed0_snapshot(tmp_path):
    path,fields,rows,m,s=inputs(tmp_path)
    before=original_points(m,s,path)
    with path.open("a",newline="") as stream:
        csv.DictWriter(stream,fieldnames=fields).writerow(dict(
            run="another",samples=9000000,readout="R3",task="cyp.2D6",error=99,E_ref=100,score=.01))
    assert original_points(m,s,path)==before
    for t in PRIMARY_TASK_IDS:
        assert before[0][t]==dict(error=2.,E_ref=4.,score=.5)


def test_duplicate_original_scalar_is_rejected_instead_of_changing_reference(tmp_path):
    path,fields,rows,m,s=inputs(tmp_path)
    with path.open("a",newline="") as stream:
        csv.DictWriter(stream,fieldnames=fields).writerow(rows[0])
    with pytest.raises(ValueError,match="Duplicated"):
        original_points(m,s,path)


def test_wrong_sample_checkpoint_does_not_supply_missing_original_point(tmp_path):
    path,fields,rows,m,s=inputs(tmp_path)
    m["samples"]=3000000
    with pytest.raises(ValueError,match="absent"):
        original_points(m,s,path)
