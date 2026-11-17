"""Analytic tests for the new H feature transforms and registered decisions."""
import unittest
import numpy as np
import torch
from h_atom_targets import explained
from h_geometry import prediction_verdict
from h_sources import whiten_table
from h_attention import attention_weights,enrichment_statistics
from phychem_mfm.model.v3_latent import MaskedAttention

class NewHLogic(unittest.TestCase):
 def test_element_variance(self):
  self.assertEqual(explained({1:[2,2,2],6:[2,6,18]})['element_explained_fraction'],1)
  self.assertEqual(explained({1:[2,2,4],6:[2,2,4]})['element_explained_fraction'],0)
 def test_preregistered_effect_decision(self):
  x=np.ones(1001)
  self.assertEqual(prediction_verdict(x*.1,x*.001,x*.1)['verdict'],'SUPPORT')
  self.assertEqual(prediction_verdict(-x,-x,-x)['verdict'],'NOT_SUPPORT')
  self.assertEqual(prediction_verdict(x*.049,x*.001,x*.1)['verdict'],'PARTIAL_SUPPORT')
 def test_whitening_rare_and_constant(self):
  out=whiten_table({'1':dict(count=50,sum=[50.,0.],square=[100.,0.]),'6':dict(count=49,sum=[49.,0.],square=[98.,0.])})
  self.assertEqual(set(out),{1});np.testing.assert_allclose(out[1][0],[1.,0.]);np.testing.assert_allclose(out[1][1],[1.,1.])
 def test_attention_uniform_mask(self):
  m=MaskedAttention(256,512,256)
  a=attention_weights(m,torch.zeros(1,8,256),torch.zeros(1,3,512),torch.zeros(1,3,512),torch.tensor([[True,True,False]]))
  self.assertTrue(torch.equal(a[...,-1],torch.zeros_like(a[...,-1])))
  self.assertTrue(torch.equal(a[...,:2],torch.full_like(a[...,:2],.5)))
 def test_uniform_attention_prediction(self):
  rows=[dict(enrichments={'all':np.ones(8)},head_enrichments={'all':np.ones((8,8))},entropy=np.ones(8)) for _ in range(4)]
  result=enrichment_statistics(rows,repeats=10)
  self.assertEqual(result['verdict'],'NOT_SUPPORT');self.assertEqual(result['qualifying_queries'],[])

if __name__=='__main__':unittest.main()
