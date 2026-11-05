"""Three pure CPU13 adoption boundaries. Synthetic references are never opened."""
import copy,unittest
from . import binding as B


def sample():
    refs={k:{'path':'/share/home/zixiao/descriptor_analysis/SYNTHETIC_ONLY/'+k,'bytes':1,'sha256':'0'*64}
      for k in ('receipt','proof','submission','accounting','raw')}
    receipt={'schema':'LABELS_FULL_TIMEOUT_READONLY_INVENTORY_RECEIPT_V1','status':'PARTIAL_TIMEOUT_EVIDENCE_NOT_OLD_C0',
      'job_id':'999901','node':'compute-0-13','uid':1278,'original_parent_c0':False,
      'inventory_verification_complete':True,'all_old_member_frames_unchanged':True,'errors':[],
      'quality_hold_fields_verified_windows':[],
      'original_parent':{'original_parent_state':'TIMEOUT','original_parent_c0':False,'allocated_core_seconds':230592},
      'resource_adapter':{'schema':B.IA.ADAPTER,'current_node':'compute-0-13','historical_node':'compute-0-17','historical_job_id':'4521904'}}
    review={'schema':B.REVIEW,'status':'ROOT_APPROVED_EXACT_ACTUAL_CPU13_INVENTORY_FOR_NEW_BOOK','reviewer':'root',
      'reason':'SYNTHETIC ONLY: not existing or future actual authority','endpoint':'202.38.247.57:22','uid':1278,
      'inventory_node':'compute-0-13','inventory_module':B.INVENTORY_MODULE,'inventory_actual_references':refs,
      'inventory_job_id':'999901','original_job_id':'4521904','original_node':'compute-0-17',
      'original_parent_state':'TIMEOUT','original_parent_c0':False,'old2748_promoted_to_C0':False,
      'original_allocated_core_seconds':230592,'complete_window_part_and_original_quality_evidence_accepted':True,
      'original_science_thresholds_unchanged':True}
    return review,refs,receipt


class Boundaries(unittest.TestCase):
    def test_C0_alone_incomplete_unknown_or_quality_never_adopted(self):
        review,refs,receipt=sample();B.adoption_shape(review,refs,receipt)
        for key,value in (('inventory_verification_complete',False),('all_old_member_frames_unchanged',False),
          ('errors',['unknown']),('quality_hold_fields_verified_windows',[9]),('original_parent_c0',True)):
            bad=copy.deepcopy(receipt);bad[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):B.adoption_shape(review,refs,bad)
        bad=copy.deepcopy(review);bad['complete_window_part_and_original_quality_evidence_accepted']=False
        with self.assertRaises(ValueError):B.adoption_shape(bad,refs,receipt)

    def test_actual13_chain_not_legacy2748_or_fake17_or_rebound_reference(self):
        review,refs,receipt=sample()
        for key,value in (('inventory_node','compute-0-17'),('uid',1264),('original_parent_state','COMPLETED'),('old2748_promoted_to_C0',True)):
            bad=copy.deepcopy(review);bad[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):B.adoption_shape(bad,refs,receipt)
        bad=copy.deepcopy(review);old=copy.deepcopy(receipt);bad['inventory_job_id']=old['job_id']='4522748'
        with self.assertRaises(ValueError):B.adoption_shape(bad,refs,old)
        wrong=copy.deepcopy(refs);wrong['proof']['path']+='changed'
        with self.assertRaises(ValueError):B.adoption_shape(review,wrong,receipt)
        with self.assertRaises(ValueError):B.actual({},'workflows.data_v1_final.labels.full_timeout_inventory_v1.run')

    def test_resource_only_inverse_original_book_readers_masks_constants(self):
        from . import coverage,seed
        from workflows.data_v1_final.labels.full_recovery_book_v1 import io as old
        from workflows.data_v1_final.labels.full_recovery_book_v1.book import Book
        self.assertIs(seed.Book,Book);self.assertIs(B.reader,old.reader);self.assertIs(B.data_ref,old.data_ref)
        self.assertEqual(coverage.source_inverse()['cpu13_binding_inverse'],
          'EXACT_COORDINATOR_BYTES_AST_WITH_EXPLICIT_RESOURCE_IO_BINDING')
