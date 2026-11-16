"""A bad SoM report cannot veto an otherwise eligible new T1 module."""
import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from phychem_mfm.phase1.v3_downstream_targets import PRIMARY_TASK_IDS,REPORT_ONLY_TASK_IDS
from phychem_mfm.phase1.v3_reselection import t1_result
def panel(score,som):
 def boot(value,groups):return dict(samples=1000,seed=20261025,confidence=.95,values=[value]*1000,groups=groups)
 return dict(panel='v3',complete=True,SoM_selection_use=False,
  tasks={key:dict(normalized_improvement=score) for key in PRIMARY_TASK_IDS},
  mean_normalized_improvement=score,
  paired_bootstrap=boot(score,{'expansionrx':['m'],'qm9':['q']}),
  report_only=dict(complete=True,selection_use=False,
   tasks={key:dict(normalized_improvement=som) for key in REPORT_ONLY_TASK_IDS},
   mean_normalized_improvement=som,paired_bootstrap=boot(som,{'cyp_isoform':['s']})))
class T1ReportingOnlyTest(unittest.TestCase):
 def test_winning_module_survives_arbitrarily_bad_SoM_but_missing_arm_cannot_select(self):
  values={'A0':.3,'A1':.6,'A2':.7,'A3':.8,'A4':.4}
  data={arm:{c:{name:panel(value,-10. if arm in ('A1','A3') else .5)
   for name in ('R1','R2','R3','R1z','R2z')} for c in ('S','P')} for arm,value in values.items()}
  result=t1_result(data)
  self.assertEqual(result['provisional_latent'],'lite_rec')
  self.assertTrue(result['lambda_k_required'])
  self.assertFalse(result['SoM_selection_use'])
  self.assertLess(result['SoM_reporting']['A3']['delta'],0)
  self.assertFalse(result['SoM_reporting']['A3']['selection_use'])
  broken=copy.deepcopy(data);del broken['A4']['P']
  with self.assertRaises(ValueError):t1_result(broken)
 def test_unavailable_report_only_SoM_does_not_block_primary_adoption(self):
  values={'A0':.3,'A1':.6,'A2':.7,'A3':.8,'A4':.4}
  data={arm:{c:{name:panel(value,.5) for name in ('R1','R2','R3','R1z','R2z')}
   for c in ('S','P')} for arm,value in values.items()}
  for arm in ('A0','A1','A3'):
   for c in ('S','P'):
    report=data[arm][c]['R2']['report_only'];report['complete']=False
    report['mean_normalized_improvement']=None;report['paired_bootstrap']['values']=[None]*1000
  result=t1_result(data)
  self.assertEqual(result['provisional_latent'],'lite_rec')
  self.assertEqual(result['SoM_reporting']['A3']['status'],'UNAVAILABLE')
if __name__=='__main__':unittest.main()
