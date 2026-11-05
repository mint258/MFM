"""Only orchestration safety UNIT tests; no actual model or dataset authority."""
import importlib.util,pathlib,tempfile,unittest
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
 def test_native_coordinator_does_not_block_hourly_dispatch(self):
  state={'calls':{}}
  with tempfile.TemporaryDirectory() as d, patch.object(m,'CONTROL',pathlib.Path(d)), patch.object(m.subprocess,'run',side_effect=AssertionError('Synchronous wait forbidden')), patch.object(m.subprocess,'Popen') as popen:
   popen.return_value.pid=123456
   result=m.invoke('Native_slot_032',['ORIGINAL_FROZEN_ROOT'],state,{},False)
   self.assertEqual(result,'ORIGINAL_COORDINATOR_STARTED_NO_REPLAY')
   self.assertTrue(popen.call_args.kwargs['start_new_session'])
   self.assertEqual(popen.call_args.args[0],['ORIGINAL_FROZEN_ROOT'])
   self.assertEqual(state['calls']['Native_slot_032']['child_pid'],123456)
 def test_native_handoff_intent_cannot_spawn_twice(self):
  state={'calls':{'Native_slot_032':{'status':'ORIGINAL_COORDINATOR_STARTED_NO_REPLAY'}}}
  with patch.object(m.subprocess,'Popen',side_effect=AssertionError('Replay forbidden')), patch.object(m.subprocess,'run',side_effect=AssertionError('Replay forbidden')):
   self.assertEqual(m.invoke('Native_slot_032',['FORBIDDEN'],state,{},False),'ALREADY_CALLED_NO_REPLAY')
 def test_actual_root_closure_required_after_native_handoff(self):
  calls={'Native_slot_032':{'status':'ORIGINAL_COORDINATOR_STARTED_NO_REPLAY'}}
  self.assertFalse(m.prior_native_calls_closed(calls,[],33))
  self.assertFalse(m.prior_native_calls_closed(calls,[({'slot':32},{'status':'FAILED_OR_STORAGE_HOLD'})],33))
  self.assertTrue(m.prior_native_calls_closed(calls,[({'slot':32},{'status':'OUTER_C0_SEGMENT_CLOSED_SDK_PENDING'})],33))
if __name__=='__main__':unittest.main(verbosity=2)
