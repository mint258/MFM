import unittest
import numpy as np
from stage1_geometry import rmsd,angle,local_setup,local_difference
class GeometryChecks(unittest.TestCase):
 def test_proper_rotation_and_translation(self):
  a=np.array([[0.,0.,0.],[1.,0.,0.],[0.,2.,0.],[0.,0.,3.]])
  r=np.array([[0.,-1.,0.],[1.,0.,0.],[0.,0.,1.]])
  self.assertLess(rmsd(a,a@r+4,np.ones(4,dtype=bool)),1e-12)
  b=a.copy();b[:,0]*=-1
  self.assertGreater(rmsd(a,b,np.ones(4,dtype=bool)),.1)
 def test_graph_distance_contacts_and_dihedral(self):
  m={1:np.array([6]*4),2:np.array([[0,1],[1,2],[2,3]]),3:np.array([1,1,1])}
  pairs,torsions=local_setup(m,'TRAIN','test')
  self.assertEqual(pairs,[(0,3)]);self.assertEqual(torsions,[(0,1,2,3)])
  a=np.array([[0.,1.,0.],[0.,0.,0.],[1.,0.,0.],[1.,1.,1.]])
  result=local_difference(a,a+3,pairs,torsions)
  self.assertLess(result['contact_distance_rms'],1e-12);self.assertLess(result['dihedral_change_max_deg'],1e-12)
if __name__=='__main__':unittest.main()
