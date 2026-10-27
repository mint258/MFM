"""Six pure bounded retirement/delegation state tests; no data or scheduler."""
import unittest
from . import contract as C


class Boundaries(unittest.TestCase):
    def test_two_live_caps_not247_and_closed_size_unknown_can_retire(self):
        rows={'a':{'job_id':'1'},'b':{'job_id':'2'}}
        self.assertFalse(C.capacity(rows));self.assertEqual(C.future_bytes(rows),2*C.CAP)
        rows['a'].update(retired=True,actual_output_bytes='UNKNOWN_PENDING_CPU_INVENTORY')
        self.assertTrue(C.capacity(rows));self.assertEqual(C.future_bytes(rows),C.CAP)

    def test_only_actual_C0_plus_same_observer_closure_retires(self):
        parent={'state':'COMPLETED','exit_code':'0:0'};closure={'status':'REGISTERED_PHASE_ALL_TERMINAL_NOT_GLOBAL_TASK_COMPLETE',
            'states':[{'job_id':'1','state':'COMPLETED','exit_code':'0:0'}]}
        self.assertTrue(C.retired(parent,closure,'1'));self.assertFalse(C.retired(parent,None,'1'))
        self.assertFalse(C.retired(dict(parent,state='TIMEOUT'),closure,'1'));self.assertFalse(C.retired(parent,closure,'2'))

    def test_imported_first_shard_not_dispatched_again(self):
        result=C.next_action({'a':{'job_id':'1775','retired':True}},['a','b'])
        self.assertEqual(result,{'action':'DISPATCH','batch_id':'b'})

    def test_failed_unknown_or_partial_intent_never_automatically_retries(self):
        for kind in ('failed','unknown','ambiguous'):
            self.assertEqual(C.next_action({'a':{kind:True}},['a','b'])['action'],'HOLD')

    def test_lease_wall_envelope_and_no_fake_final_inventory(self):
        self.assertTrue(C.lease_allows(0,10000,7200));self.assertFalse(C.lease_allows(8000,10000,7200))
        self.assertFalse(C.inventory_ready({'status':'ALL247_RETIRED_PENDING_CPU_INVENTORY_AND_ROOT_REVIEW','batches':{}}))

    def test_known_geometry_pending_and_HOF_NULL_not_silent_success(self):
        row=dict(file_group=1,shard_index=0,molecules=2,records=3)
        r=dict(schema='PM7_POPULATION_CACHE_BATCH_RECEIPT_V1',status='SELECTION_DURABLY_CLOSED_ROOT_REVIEW_REQUIRED',
            selection=dict(file_group=1,shard_index=0,offset=0,limit=2),selected_molecules=2,durable_classified_molecules=2,
            selected_records=3,unstarted_molecules=0,consumed_without_validated_packet_molecules=0,error_count=0,
            common=False,full_cache_release=False,geometry_complete_molecules=1,geometry_pending_or_unresolved_molecules=1,
            selected_HOF_reader_records=3,selected_HOF_reader_valid_records=2,selected_HOF_NULL_convergence_review_records=1)
        C.receipt(r,row);self.assertFalse(r['full_cache_release'])
        with self.assertRaises(ValueError):C.receipt(dict(r,consumed_without_validated_packet_molecules=1),row)
