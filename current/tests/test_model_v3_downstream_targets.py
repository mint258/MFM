"""Validate only the new atomization labels and SoM report-only aggregation."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from phychem_mfm.phase1.v3_downstream_targets import (
 QM9_U0_ATOMREF_HA,PRIMARY_TASK_IDS,REPORT_ONLY_TASK_IDS,
 qm9_u0_atomization,compare_report_only_panel)
from phychem_mfm.phase1.v3_dev_evaluation import TaskSpec,TaskPrediction

class DownstreamTargetRevisionTest(unittest.TestCase):
 def test_atomization_uses_U0_column_Hartree_and_all_native_H(self):
  for z,value in QM9_U0_ATOMREF_HA.items():
   self.assertTrue(np.isclose(qm9_u0_atomization(value,[z],element_index_base=1),
    0.,atol=1e-10,rtol=1e-9))
  # H2O: sum(atomrefs)=-76.065125 Ha; fixture U0=-76.438 Ha.
  result=qm9_u0_atomization(-76.438,[8,1,1],element_index_base=1)
  self.assertTrue(np.isclose(result,-.372875,atol=1e-10,rtol=1e-9))
  for elements in ([7,0,0],[0,7,0]):
   self.assertTrue(np.isclose(qm9_u0_atomization(-76.438,elements,element_index_base=0),
    result,atol=1e-10,rtol=1e-9))
  with self.assertRaises(ValueError):qm9_u0_atomization(-76.438,[8,0],element_index_base=1)
  with self.assertRaises(ValueError):qm9_u0_atomization(-76.438,[16],element_index_base=1)

 def test_SoM_changes_reports_but_cannot_change_selection_score_or_draws(self):
  candidate,reference={},{}
  for key in PRIMARY_TASK_IDS:
   dataset=key.split('.')[0];task=TaskSpec(key,dataset,key.rsplit('.',1)[1],'graph','mae')
   def graph_prediction(value):
    return TaskPrediction(task,('mol0','mol1'),np.zeros(2),np.full(2,value),
     np.ones(2,dtype=bool),('record0','record1'))
   candidate[key]=graph_prediction(1.);reference[key]=graph_prediction(2.)
  for key in REPORT_ONLY_TASK_IDS:
   task=TaskSpec(key,'cyp_isoform',key.rsplit('.',1)[1],'atom','one_minus_hit1')
   def atom_prediction(correct):
    return TaskPrediction(task,('mol0','mol0','mol1','mol1'),
     np.array([1.,0.,1.,0.]),np.array([1.,0.,1.,0.]) if correct else np.array([0.,1.,0.,1.]),
     np.ones(4,dtype=bool),('record0','record0','record1','record1'))
   candidate[key]=atom_prediction(False);reference[key]=atom_prediction(False)
  bad=compare_report_only_panel(candidate,reference,architecture_sha256='same',
   reference_architecture_sha256='same',bootstrap_samples=32,retain_paired_samples=True)
  for key in REPORT_ONLY_TASK_IDS:
   p=candidate[key]
   candidate[key]=TaskPrediction(p.task,p.molecule_uids,p.targets,
    np.array([1.,0.,1.,0.]),p.valid,p.source_record_uids)
  good=compare_report_only_panel(candidate,reference,architecture_sha256='same',
   reference_architecture_sha256='same',bootstrap_samples=32,retain_paired_samples=True)
  self.assertEqual(bad['mean_normalized_improvement'],.5)
  self.assertEqual(good['mean_normalized_improvement'],.5)
  np.testing.assert_allclose(bad['paired_bootstrap']['values'],good['paired_bootstrap']['values'],
   atol=1e-12,rtol=1e-10)
  self.assertNotEqual(bad['report_only']['mean_normalized_improvement'],
   good['report_only']['mean_normalized_improvement'])
  self.assertFalse(good['report_only']['selection_use'])
if __name__=='__main__':unittest.main()
