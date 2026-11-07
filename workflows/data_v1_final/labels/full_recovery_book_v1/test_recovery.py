"""Six pure boundaries, before any real state/window/part DATA."""
import copy,unittest
from . import contract as C


class Boundaries(unittest.TestCase):
    def test_timeout_is_not_inventory_or_producer_C0(self):
        bad={'schema':'LABELS_FULL_TIMEOUT_READONLY_INVENTORY_RECEIPT_V1','status':'PARTIAL_TIMEOUT_EVIDENCE_NOT_OLD_C0',
          'job_id':'4522748','uid':1278,'original_parent_c0':False,'inventory_verification_complete':False,
          'all_old_member_frames_unchanged':True,'errors':[],'quality_hold_fields_verified_windows':[],
          'original_parent':{'original_parent_state':'TIMEOUT','original_parent_c0':False,'allocated_core_seconds':230592}}
        with self.assertRaises(ValueError):C.inventory_gate(bad)
        good=dict(bad,inventory_verification_complete=True);C.inventory_gate(good)
        good['original_parent']['original_parent_state']='COMPLETED'
        with self.assertRaises(ValueError):C.inventory_gate(good)

    def sample(self):
        expected=[{'range_id':'r','file_id':7,'physical_row_lo':0,'physical_row_hi':10}]
        ranges=[{'range_id':'r','cursor':4,'stop':10}]
        windows=[{'range_id':'r','lo':0,'hi':2,'receipt':{'x':1}},{'range_id':'r','lo':2,'hi':4,'receipt':{'x':2}}]
        verified={('r',w['lo']):{'status':'VERIFIED_COMMITTED_WINDOW','window':w} for w in windows}
        return expected,ranges,windows,verified

    def test_all_verified_prefix_can_continue_but_unknown_ticket_holds(self):
        e,r,w,v=self.sample();chosen,cursor,hold,history=C.prefixes(e,r,[],w,v,[{'file_id':7,'end_physical_row':4}],set())
        self.assertEqual(cursor,{7:4});self.assertFalse(hold);self.assertEqual(len(chosen),2)
        _,_,hold,_=C.prefixes(e,r,[{'range_id':'r','status':'RESERVED'}],w,v,[{'file_id':7,'end_physical_row':4}],set())
        self.assertIn(7,hold)

    def test_unadopted_consumed_and_orphan_are_never_unstarted(self):
        e,r,w,v=self.sample();_,cursor,hold,history=C.prefixes(e,r,[],w,v,[{'file_id':7,'end_physical_row':2}],set())
        self.assertEqual(cursor[7],2);self.assertIn(7,hold);self.assertFalse(history[-1]['adopted'])
        self.assertIn(7,C.prefixes(e,r,[],w,v,[{'file_id':7,'end_physical_row':4}],{7})[2])

    def test_missing_part_window_gap_overlap_and_midwindow_selection_fail(self):
        e,r,w,v=self.sample();bad=copy.deepcopy(v);bad['r',2]['status']='UNKNOWN_MISSING_PART'
        with self.assertRaises(ValueError):C.prefixes(e,r,[],w,bad,[{'file_id':7,'end_physical_row':4}],set())
        for lo in (1,3):
            bad=copy.deepcopy(w);bad[1]['lo']=lo
            with self.assertRaises(ValueError):C.prefixes(e,r,[],bad,v,[{'file_id':7,'end_physical_row':4}],set())
        with self.assertRaises(ValueError):C.prefixes(e,r,[],w,v,[{'file_id':7,'end_physical_row':3}],set())

    def test_budget_separates_retained_and_future_and_quality_cannot_be_diluted(self):
        meta={'cap':20,'recovery_budget':{'retained':32<<30,'production':20}}
        self.assertEqual(C.remaining(meta,[{'state':'ACTUAL_C0_CLOSED','charged_bytes':8}]),12)
        self.assertEqual(meta['recovery_budget']['retained'],32<<30)
        with self.assertRaises(ValueError):C.remaining(meta,[{'state':'ACTUAL_C0_CLOSED','charged_bytes':21}])
        self.assertEqual(C.hold_fields({'0':{'records':100,'newly_masked_fields':2,'new_payload_structural_invalid_records':0}}),['0'])

    def test_frozen_science_objects_and_origin_resolver_inverse(self):
        from .coverage import source_inverse
        from workflows.data_v1_final.labels.full_projection_v1 import run as F
        from workflows.data_v1_final.labels.bounded_projection_v1 import run as B
        self.assertIs(F.worker,B.worker);self.assertIs(F.initialize,B.initialize)
        self.assertEqual(source_inverse()['status'],'EXACT_RESOLVER_AND_ORIGIN_ONLY_BYTES_AST_INVERSE')