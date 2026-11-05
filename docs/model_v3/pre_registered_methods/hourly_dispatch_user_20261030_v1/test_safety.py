"""Only orchestration safety UNIT tests; no actual model or dataset authority."""
import importlib.util,pathlib,unittest
from unittest.mock import patch
p=pathlib.Path(__file__).parent/'hourly_dispatch.py'
spec=importlib.util.spec_from_file_location('hourly_dispatch_UNIT',p)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Safety(unittest.TestCase):
 def row(self,**k):
  r=dict(free_cpus=16,mem_available_bytes=128<<30,real_memory_bytes=120000<<20,occupied=False,uuid='GPU-22e21021-e572-4562-fc51-cd8c83e74141');r.update(k);return r
 def test_idle_original_target_is_eligible(self):self.assertTrue(m.eligible(self.row(),64<<30,set()))
 def test_busy_gpu_never_eligible(self):self.assertFalse(m.eligible(self.row(occupied=True),32<<30,set()))
 def test_looping_job_gap_remains_occupied(self):self.assertFalse(m.eligible(self.row(),32<<30,{'4525142'}))
 def test_requires_sixteen_free_cpus(self):self.assertFalse(m.eligible(self.row(free_cpus=15),32<<30,set()))
 def test_exact_physical_memory_reserve_boundary(self):
  lower=(64<<30)+(120000<<20)*15//100
  self.assertFalse(m.eligible(self.row(mem_available_bytes=lower-1),64<<30,set()))
  self.assertTrue(m.eligible(self.row(mem_available_bytes=lower),64<<30,set()))
 def test_original_distinct_software_budgets_remain(self):
  self.assertTrue(m.eligible(self.row(mem_available_bytes=60<<30),32<<30,set()))
  self.assertFalse(m.eligible(self.row(mem_available_bytes=60<<30),64<<30,set()))
 def test_new_failed_native_attempt_is_never_retried(self):
  with self.assertRaises(RuntimeError):m.last_attempt_requires_retry([({'slot':32},{'status':'FAILED_OR_STORAGE_HOLD'})])
 def test_only_explicit_reconciled_old31_can_request_retry(self):
  self.assertTrue(m.last_attempt_requires_retry([({'slot':31},{'status':'FAILED_OR_STORAGE_HOLD'})]))
 def test_historical_failure_does_not_replay_completed_attempt(self):
  self.assertFalse(m.last_attempt_requires_retry([({'slot':1},{'status':'FAILED_OR_STORAGE_HOLD'}),({'slot':32},{'status':'OUTER_C0_SEGMENT_CLOSED_SDK_PENDING'})]))
 def test_ambiguous_call_intent_is_never_replayed(self):
  with patch.object(m.subprocess,'run',side_effect=AssertionError('No child allowed')):
   self.assertEqual(m.invoke('A438',['forbidden'],{'calls':{'A438':{'status':'INTENT_NO_AUTOMATIC_REPLAY'}}},{},False),'ALREADY_CALLED_NO_REPLAY')
 def test_check_only_cannot_write_intent_or_start_child(self):
  state={'calls':{}}
  with patch.object(m.subprocess,'run',side_effect=AssertionError('No child allowed')):
   self.assertEqual(m.invoke('A438',['forbidden'],state,{},True)['status'],'WOULD_CALL_FROZEN_ROOT')
  self.assertEqual(state,{'calls':{}})
if __name__=='__main__':unittest.main(verbosity=2)
