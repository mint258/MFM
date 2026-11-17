"""One-time analytic tests for H7's new gate summaries."""
import unittest
import numpy as np
import torch
from h_gates import gate_row,gate_statistics,scalar_gate


class GateLogic(unittest.TestCase):
 def test_category_mass_and_variance_decomposition(self):
  row=gate_row([.25,.75],{'low':[0],'all':[0,1]});stats=gate_statistics([row,row],repeats=10)
  found={r['category']:r for r in stats['scalar_gate_enrichments']}
  self.assertEqual(found['low']['enrichment'],.5);self.assertEqual(found['all']['enrichment'],1.)
  self.assertEqual(found['low']['ci95'],[.5,.5]);self.assertEqual(stats['distribution']['within_molecule_atom_variance_fraction'],1.)
  self.assertEqual(stats['distribution']['mean'],.5);self.assertEqual(stats['distribution']['std'],.25)
 def test_constant_and_between_molecule_variance(self):
  constant=gate_statistics([gate_row([.5,.5],{'all':[0,1]})],repeats=10)
  self.assertIsNone(constant['distribution']['within_molecule_atom_variance_fraction'])
  between=gate_statistics([gate_row([.25,.25],{}),gate_row([.75,.75],{})],repeats=10)
  self.assertEqual(between['distribution']['within_molecule_atom_variance_fraction'],0.)
 def test_actual_shared_gate_and_padding_exclusion(self):
  class Pma:
   sum_norm=torch.nn.Identity()
   sum_gate=torch.nn.Linear(2,1,bias=False)
  p=Pma();p.sum_gate.weight.data.zero_();g=scalar_gate(p,torch.ones(1,3,2)).detach().numpy()
  self.assertEqual(g.shape,(1,3,1));row=gate_row(g[0,:2,0],{'all':[0,1]})
  self.assertEqual(row['atoms'],2);self.assertEqual(row['sum'],1.)


if __name__=='__main__':unittest.main()
