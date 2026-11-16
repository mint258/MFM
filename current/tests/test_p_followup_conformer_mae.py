"""Native conformer-difference identity and masking tests; no source reads."""
import importlib.util
from pathlib import Path
import numpy as np
import pytest
spec=importlib.util.spec_from_file_location('conformer_mae_math',Path(__file__).resolve().parents[2]/'tools/p_followup/conformer_mae_math.py')
math=importlib.util.module_from_spec(spec);spec.loader.exec_module(math)


def entry(pred,truth,pairs=None):
    a=np.asarray(truth,dtype=np.float64)
    return np.asarray(pred,dtype=np.float64),a,np.isfinite(a),None if pairs is None else np.asarray(pairs)


def test_reordered_directed_pairs_are_aligned_before_subtraction():
    ca=entry([[5.],[8.]],[[4.],[6.]],[[0,1],[1,0]])
    cb=entry([[2.],[3.],[100.]],[[1.],[2.],[99.]],[[1,0],[0,1],[2,2]])
    da=entry([[4.],[6.]],[[4.],[6.]],[[0,1],[1,0]])
    db=entry([[1.],[2.],[99.]],[[1.],[2.],[99.]],[[1,0],[0,1],[2,2]])
    assert math.paired_error(ca,cb,da,db)==dict(observations=2,C_absolute_error=1.,D_absolute_error=0.)
    bad=entry([[4.],[6.]],[[4.],[6.]],[[1,0],[0,1]])
    with pytest.raises(ValueError,match='endpoints differ'):math.paired_error(ca,cb,bad,db)


def test_vector_components_use_the_same_finite_mask_in_both_arms():
    ca=entry([[3.,np.nan,8.]],[[1.,np.nan,5.]])
    cb=entry([[2.,9.,4.]],[[0.,2.,3.]])
    da=entry([[1.,np.nan,np.nan]],[[1.,np.nan,5.]])
    db=entry([[0.,2.,3.]],[[0.,2.,3.]])
    assert math.paired_error(ca,cb,da,db)==dict(observations=1,C_absolute_error=0.,D_absolute_error=0.)
