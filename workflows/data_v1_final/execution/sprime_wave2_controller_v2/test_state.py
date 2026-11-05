"""Eight synthetic state tests; no scheduler, body or subprocess access."""
import unittest
from . import contract as C


class ControllerBoundaries(unittest.TestCase):
    def test_timeout_science_requires_independent_close(self):
        self.assertEqual(C.next_stage({'run':dict(terminal=True,state='TIMEOUT',exit_code='0:15')})['action'],'close')
        self.assertEqual(C.next_stage({'run':dict(terminal=True,state='FAILED',exit_code='1:0')})['action'],'close')

    def test_prepare_needs_actual_c0(self):
        self.assertEqual(C.next_stage({'prepare':dict(terminal=True,state='FAILED',exit_code='3:0')})['action'],'HOLD')
        self.assertEqual(C.next_stage({'prepare':dict(terminal=True,state='COMPLETED',exit_code='0:0')})['action'],'run')

    def test_bad_or_empty_closure_holds(self):
        report=dict(schema='SPRIME_FORMAL_CPU_CLOSED_BATCH_V3',status='ACTUAL_TERMINAL_BATCH_CLASSIFIED',valid_packets=0)
        self.assertEqual(C.close_hold(report),'NO_VALIDATED_PACKETS');report.update(valid_packets=500,errors=[{'error':'SHA'}])
        self.assertEqual(C.close_hold(report),'CLOSURE_ERRORS_OR_EXTERNAL_CONSUMPTION')
        self.assertEqual(C.close_hold({'status':'planned'}),'INVALID_CLOSURE_CHAIN')

    def test_valid_failed_science_packet_does_not_invent_success(self):
        report=dict(schema='SPRIME_FORMAL_CPU_CLOSED_BATCH_V3',status='ACTUAL_TERMINAL_BATCH_CLASSIFIED',valid_packets=4,errors=[],execution_unresolved=0,unstarted_count=0)
        result=C.next_stage({'close':dict(terminal=True,state='COMPLETED',exit_code='0:0',report=report)})
        self.assertEqual(result,{'action':'DONE'});self.assertNotIn('scientific_status',result)

    def test_unknown_and_unstarted_never_automatically_retry(self):
        report=dict(schema='SPRIME_FORMAL_CPU_CLOSED_BATCH_V3',status='ACTUAL_TERMINAL_BATCH_CLASSIFIED',valid_packets=4,execution_unresolved=1)
        self.assertEqual(C.close_hold(report),'CONSUMED_UNKNOWN_NO_RETRY');report.update(execution_unresolved=0,unstarted_count=1)
        self.assertEqual(C.close_hold(report),'UNSTARTED_REQUIRES_NEW_ROOT_CONTINUATION')

    def test_capacity_counts_pending_as_nonterminal(self):
        self.assertFalse(C.capacity('run',nonterminal_science=2,nonterminal_aux=0,owned_run_pending=2))
        self.assertFalse(C.capacity('prepare',nonterminal_science=0,nonterminal_aux=1,owned_run_pending=1))
        self.assertFalse(C.capacity('close',nonterminal_science=0,nonterminal_aux=0,owned_run_pending=4))
        self.assertTrue(C.capacity('close',nonterminal_science=2,nonterminal_aux=0,owned_run_pending=3))

    def test_partial_submission_and_failed_intent_cannot_be_reissued(self):
        self.assertEqual(C.submission_resolution(False,False,None,False),'NEW_NOT_SUBMITTED')
        for intent,request in ((True,False),(False,True),(True,True)):
            self.assertIn('HOLD',C.submission_resolution(intent,request,None,False))
        self.assertIn('HOLD',C.submission_resolution(True,True,dict(job_id='12',sbatch_returncode=0),False))
        self.assertEqual(C.submission_resolution(True,True,dict(job_id='12',sbatch_returncode=0),True),'REGISTERED')

    def test_closer_priority_and_ambiguous_resume(self):
        rows=[dict(batch_id='batch-00001',stage='prepare'),dict(batch_id='batch-00003',stage='close'),dict(batch_id='batch-00002',stage='run')]
        self.assertEqual(C.choose(rows)['stage'],'close')
        self.assertEqual(C.next_stage({'prepare':dict(ambiguous=True)})['action'],'HOLD')
