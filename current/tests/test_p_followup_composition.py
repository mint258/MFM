import pathlib,sys,unittest
import numpy as np
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[2]/'tools/p_followup'))
from composition_statistics import ridge_oof,cev_values,cvf_values,eev_values
class CompositionStatisticsChecks(unittest.TestCase):
 def test_known_linear_signal_predicts_held_out_molecules(self):
  x=np.random.default_rng(3).normal(size=(100,3));y=x@np.array([[1.,2.],[2.,0.],[0.,4.]])+3
  predicted,_=ridge_oof(x,y)
  self.assertGreater(cev_values(y,predicted,np.ones((1,100)))[0],.999)
 def test_conformer_fraction_and_residual_fraction(self):
  h=np.array([[0.],[2.],[4.],[6.]]);owners=np.array([0,0,1,1]);prediction=np.array([[1.],[5.]])
  cvf,res=cvf_values(h,owners,prediction,np.ones((1,2)))
  self.assertAlmostEqual(cvf[0],.2);self.assertAlmostEqual(res[0],1.)
 def test_between_element_fraction_without_atom_vectors(self):
  result=eev_values(np.array([[-2.],[2.]]),np.array([4.,4.]),np.array([1.,1.]),np.array([0,1]),np.array([1,6]),np.ones((1,2)))
  self.assertAlmostEqual(result[0],1.)
if __name__=='__main__':unittest.main()