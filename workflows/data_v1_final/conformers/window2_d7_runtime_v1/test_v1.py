import unittest
from .run import same_inputs
class Resume(unittest.TestCase):
    def test_cpu_only_change_keeps_the_scientific_checkpoint(self):
        p={'workers':16,'seed':20261025,'common':'same','threshold':.5}
        self.assertTrue(same_inputs(p,dict(p,workers=64)))
        self.assertFalse(same_inputs(p,dict(p,seed=20261026)))
        self.assertFalse(same_inputs(p,dict(p,threshold=.4)))
        self.assertFalse(same_inputs(p,dict(p,common='other')))
    def test_only_identical_directed_calls_are_reused(self):
        from . import run as runtime
        calls=[]
        def exact(mol, left, right):
            calls.append((mol,left,right))
            return 0.49999999999999994 if left[0] < right[0] else 0.5000000000000001
        runtime.RAW_RMSD=exact
        runtime.DISTANCES.clear()
        mol=object();left=[1];right=[2]
        first=runtime.cached_rmsd(mol,left,right)
        self.assertEqual(first,0.49999999999999994)
        self.assertEqual(runtime.cached_rmsd(mol,left,right),first)
        self.assertEqual(runtime.cached_rmsd(mol,right,left),0.5000000000000001)
        self.assertEqual(len(calls),2)
        runtime.DISTANCES.clear()
        self.assertEqual(runtime.cached_rmsd(mol,left,right),first)
        self.assertEqual(len(calls),3)