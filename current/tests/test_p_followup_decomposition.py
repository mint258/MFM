import importlib.util
from pathlib import Path
import numpy as np

p=Path(__file__).resolve().parents[2]/'tools/p_followup/decomposition_math.py'
s=importlib.util.spec_from_file_location('followup_decomposition_math',p)
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)

def test_means_with_masks_and_singletons():
    mu,n,within=m.molecular_moments(np.array([[1.,10.,np.nan],[3.,np.nan,np.nan]]))
    np.testing.assert_allclose(mu[:2],[2.,10.]);assert np.isnan(mu[2])
    np.testing.assert_array_equal(n,[2,1,0]);np.testing.assert_allclose(within,[2.,0.,0.])

def test_train_moments_population_scales_and_selection():
    fit=m.TrainMoments(2)
    for a in [np.array([[0.,5.],[2.,5.]]),np.array([[2.,7.],[4.,np.nan]])]:
        mu,n,within=m.molecular_moments(a);fit.add(mu[None,:],n[None,:],within[None,:])
    result=fit.result(2,{'a':0.,'b':0.},['a','b'])
    assert result['a']['c1']==2.;assert result['a']['s1']==1.;assert result['a']['s2']==1.
    assert result['a']['selected'];assert not result['b']['selected']