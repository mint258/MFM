import unittest
import numpy as np
from stage5_retention import atom_mapping,remap
from phychem_mfm.phase1.v31_loader import V31Target
class RetentionChecks(unittest.TestCase):
 def test_source_permutations_and_directed_endpoints(self):
  p=atom_mapping({'maps':{'g':(2,0,1)}},{'maps':{'g':(1,2,0)}},3)
  self.assertEqual(p.tolist(),[2,0,1])
  raw=np.array([[10.],[20.],[30.]]);t=V31Target(raw,raw.copy(),np.ones_like(raw,dtype=bool),'P','bonding','pair','scalar',True,np.array([[2,1],[0,2],[1,0]]))
  pos=np.arange(9).reshape(3,3);s=dict(Z=np.array([6,7,8]),pos=pos,pos_perturbed=pos,targets={'pair':t})
  mapped=remap(s,p)
  self.assertEqual(mapped['Z'].tolist(),[8,6,7]);self.assertEqual(mapped['targets']['pair'].pair_index.tolist(),[[0,2],[1,0],[2,1]])
 def test_conflicting_source_maps_stay_unknown(self):
  self.assertIsNone(atom_mapping({'maps':{'g':(0,1),'h':(0,1)}},{'maps':{'g':(0,1),'h':(1,0)}},2))
if __name__=='__main__':unittest.main()
