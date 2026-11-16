import unittest
from types import SimpleNamespace as NS
import numpy as np
from stage3_information import distance,statistics
class InformationChecks(unittest.TestCase):
 def test_pair_endpoints_not_row_order(self):
  a=NS(raw=np.array([[1.],[9.],[6.]]),pair_index=np.array([[0,1],[2,0],[1,2]]),representation='scalar',level='pair')
  b=NS(raw=np.array([[8.],[3.]]),pair_index=np.array([[1,2],[0,1]]),representation='scalar',level='pair')
  d,n,total=distance(a,b,None,None,{})
  self.assertEqual((d,n,total),(2.,2,2))
 def test_missing_is_unknown_and_groups_equal_weight(self):
  a=NS(raw=np.array([[np.nan]]),pair_index=None,representation='scalar',level='molecule')
  self.assertIsNone(distance(a,a,None,None,{})[0])
  s=statistics([0.,0.,0.,10.],['a','a','a','b'])
  self.assertEqual(s['median'],5.)
 def test_split_vector_components_reassemble_before_rotation(self):
  from phychem_mfm.phase1.v31_loader import V31Target
  pos=np.array([[0.,0.,0.],[1.,0.,0.],[0.,2.,0.],[0.,0.,3.]])
  r=np.array([[0.,-1.,0.],[1.,0.,0.],[0.,0.,1.]])
  vector=np.array([1.,2.,3.]);other=vector@r;prefix='P.pm7_B.r52'
  def targets(v):
   return {prefix+'.'+axis:V31Target(np.array([[v[i]]]),np.array([[v[i]]]),np.array([[True]]),'P','multipole','molecule_vector','vector',True) for i,axis in enumerate('xyz')}
  a,b=targets(vector),targets(other);sa=dict(Z=np.array([6]*4),pos=pos,targets=a);sb=dict(Z=np.array([6]*4),pos=pos@r+2,targets=b)
  d,_,_=distance(a[prefix+'.x'],b[prefix+'.x'],sa,sb,dict(field_key=prefix+'.x',actual_task_charge=0,geometry_route='native_original_PM7'))
  self.assertLess(d,1e-12)
if __name__=='__main__':unittest.main()
