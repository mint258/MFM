"""Prevent cross-condition or cross-trial gradient-clip contamination."""
import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools/model_v3'))
from v3_prepare_condition_clip_20261113 import condition_clip

class ConditionLocalClipTest(unittest.TestCase):
 def test_clip_cannot_be_borrowed_between_conditions_or_trials(self):
  recipe=dict(selected_C1='C1-0',selected_latent='none',selected_views='two',
   selected_head='H2',selected_pooling='learned',learning_rate=.0006,
   batch_size=64,schedule='wsd',samples=6000000,seed=0)
  def evidence(condition,value):
   return dict(schema='MODEL_V3_TRAIN_PRECLIP_P99_V1',
    source_policy='per_condition_and_trial',quantile=.99,method='linear',
    population='all_effective_TRAIN_updates',source_conditions=[condition],
    source_runs=[dict(condition=condition,scientific_samples=6000000,
     configuration='/actual/'+condition+'/configuration.json',output='/actual/'+condition)],
    recipe=copy.deepcopy(recipe),p99=value)
  for condition,value in (('S',2.5),('P',7.0),('SDP',19.0)):
   local=evidence(condition,value)
   self.assertEqual(condition_clip(local,condition,recipe),value)
   for other in ('S','P','SDP'):
    if other!=condition:
     with self.assertRaises(ValueError):condition_clip(local,other,recipe)
   wrong_trial=copy.deepcopy(local);wrong_trial['recipe']['learning_rate']=.0003
   with self.assertRaises(ValueError):condition_clip(wrong_trial,condition,recipe)
   duplicate=copy.deepcopy(local);duplicate['source_runs']*=2
   with self.assertRaises(ValueError):condition_clip(duplicate,condition,recipe)
  pooled=evidence('SDP',4.0);pooled['source_conditions']=['S','P']
  with self.assertRaises(ValueError):condition_clip(pooled,'SDP',recipe)
  inactive=evidence('S',2.5);inactive['recipe'].update(selected_head=None,selected_pooling=None)
  self.assertEqual(condition_clip(inactive,'S',recipe),2.5)
  active=evidence('P',7.0);active['recipe']['selected_head']='H1'
  with self.assertRaises(ValueError):condition_clip(active,'P',recipe)
if __name__=='__main__':unittest.main()
