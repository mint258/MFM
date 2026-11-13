"""New seven-task selection binding and inactive-before-scope production guard."""
import copy,json,sys,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from phychem_mfm.phase1.v3_downstream_targets import PRIMARY_TASK_IDS
from phychem_mfm.phase1.v3_selection import paired_difference,select_candidate,convergence_budget

class SevenTaskSelectionTest(unittest.TestCase):
 def panel(self,score):
  return dict(panel='v3',complete=True,SoM_selection_use=False,
   tasks={key:dict(normalized_improvement=score) for key in PRIMARY_TASK_IDS},
   mean_normalized_improvement=score,
   paired_bootstrap=dict(samples=1000,seed=20261025,confidence=.95,
    groups={'expansionrx':['m0','m1'],'qm9':['q0','q1']},values=[score]*1000),
   report_only={'mean_normalized_improvement':999.0,'selection_use':False})

 def test_seven_task_choice_and_budget_reject_mixed_revisions_or_total_U0(self):
  low,high=self.panel(.3),self.panel(.4)
  comparison=paired_difference({'P':high},{'P':low})
  self.assertTrue(comparison['A_wins'])
  selected=select_candidate({'registry':{'P':low},'learned':{'P':high}},
   ['registry','learned'])
  self.assertEqual(selected['selected'],'learned')
  budget=convergence_budget({1000000:low,2000000:high,4000000:self.panel(.401)})
  self.assertEqual(budget['budget'],2000000)
  total_energy=copy.deepcopy(high)
  total_energy['tasks']['qm9.U0']=total_energy['tasks'].pop('qm9.U0_atom')
  with self.assertRaises(ValueError):paired_difference({'P':total_energy},{'P':low})
  old=copy.deepcopy(low);old['panel']='v2'
  with self.assertRaises(ValueError):paired_difference({'P':high},{'P':old})
  voting_som=copy.deepcopy(high);voting_som['SoM_selection_use']=True
  with self.assertRaises(ValueError):paired_difference({'P':voting_som},{'P':low})

 def test_total_energy_prediction_cannot_hide_under_atomization_task_key(self):
  from phychem_mfm.phase1.v3_downstream_targets import compare_report_only_panel,REPORT_ONLY_TASK_IDS
  keys=tuple(PRIMARY_TASK_IDS)+tuple(REPORT_ONLY_TASK_IDS)
  candidate={key:SimpleNamespace(task=SimpleNamespace(task_id=key)) for key in keys}
  reference=copy.deepcopy(candidate)
  candidate['qm9.U0_atom'].task.task_id='qm9.U0'
  with self.assertRaisesRegex(ValueError,'relabeled'):
   compare_report_only_panel(candidate,reference,architecture_sha256='same',
    reference_architecture_sha256='same')

 def test_forward_request_does_not_implicitly_authorize_historical_reselection(self):
  from phychem_mfm.phase1.v3_downstream_targets import evaluation_scope_ready
  panel={'authority':{'retrospective_scope':'AWAITING_USER',
   'forward_evaluation_requested':True}}
  self.assertTrue(evaluation_scope_ready(panel,'forward'))
  self.assertFalse(evaluation_scope_ready(panel,'retrospective'))
  self.assertFalse(evaluation_scope_ready(panel,None))
  panel['authority']['forward_evaluation_requested']=False
  self.assertFalse(evaluation_scope_ready(panel,'forward'))

 def test_pending_scope_cannot_open_checkpoint_labels_or_start_encoding(self):
  from phychem_mfm.phase1 import v3_dev_evaluation_v3 as producer
  store_factory=Mock(side_effect=AssertionError('No source store before scope'))
  encode=Mock(side_effect=AssertionError('No GPU encoding before scope'))
  with patch.object(Path,'read_text',return_value=json.dumps(
    {'authority':{'retrospective_scope':'AWAITING_USER'}})),patch.object(
    producer.torch,'load',side_effect=AssertionError('No checkpoint read before scope')):
   with self.assertRaisesRegex(ValueError,'scope'):
    producer.evaluate(SimpleNamespace(),store_factory=store_factory,encode=encode)
  store_factory.assert_not_called();encode.assert_not_called()
if __name__=='__main__':unittest.main()
