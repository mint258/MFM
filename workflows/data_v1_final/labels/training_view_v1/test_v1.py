import unittest
import numpy as np
from .run import r73_pair_targets
class ViewTests(unittest.TestCase):
    def test_r73_sum_masks_and_mixed(self):
        a={26:np.array([[1,0],[2,0],[2,1]]),31:np.array([0,0,0,1,1,2]),32:np.array([[1,2,0],[2,1,0],[3,3,0],[1,1,0],[1,1,0],[1,3,0]]),34:np.array([1.,2.,4.,5.,np.nan,7.])}
        v,c=r73_pair_targets(a,['__ABSENT__','S-SIGMA','P-SIGMA','P-PI'])
        np.testing.assert_allclose(v[:1],[[3.,4.]],atol=1e-12,rtol=1e-12)
        self.assertTrue(np.isnan(v[1:]).all());self.assertEqual(c['mixed_symmetry_entries'],1)