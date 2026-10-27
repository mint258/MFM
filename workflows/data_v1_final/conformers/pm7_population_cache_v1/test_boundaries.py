"""Six pure dispatch/closure membership boundaries; no real inputs."""
import unittest
from . import contract as C


class BatchBoundaries(unittest.TestCase):
    def test_whole_molecule_selection_exact_contiguous_range(self):
        self.assertEqual(C.selection({'file_group':1,'shard_index':0,'offset':100,'limit':256})['limit'],256)
        for value in ({'file_group':1,'shard_index':0,'offset':4999,'limit':2},
                      {'file_group':True,'shard_index':0,'offset':0,'limit':1}):
            with self.assertRaises(ValueError):C.selection(value)

    def test_packet_without_claim_is_never_proven_unstarted(self):
        self.assertEqual(C.classify_claim(None,None,evidence_exists=True),'UNKNOWN_ORPHAN_EVIDENCE')
        self.assertEqual(C.classify_claim(None,None),'PROVEN_UNSTARTED')

    def test_consumed_claim_requires_real_parent_even_with_packet(self):
        self.assertEqual(C.classify_claim({'job_id':'1'},None,True),'UNKNOWN_PARENT_ACCOUNTING_REQUIRED')
        self.assertEqual(C.classify_claim({'job_id':'1'},{'state':'TIMEOUT'},True),'DURABLE_PACKET_RECOVERED')

    def test_dispatch_only_is_consumed_unknown_without_retry(self):
        self.assertEqual(C.classify_claim({'job_id':'1'},{'state':'FAILED'}),'UNKNOWN_CONSUMED_NO_COMPLETE_PACKET')

    def test_count_conservation_rejects_duplicate_and_outside_molecule(self):
        self.assertEqual(C.conservation(['a','b'],[{'molecule_id':'b'}]),['a'])
        self.assertNotEqual(C.error_reason("ValueError('SOURCE_GRAPH_MISSING')"),C.error_reason("ValueError('ACTUAL_RECORD_MANIFEST_MISMATCH')"))
        self.assertEqual(C.error_reason("RuntimeError('unclassified native details')"),'RuntimeError')
        for rows in ([{'molecule_id':'a'},{'molecule_id':'a'}],[{'molecule_id':'c'}]):
            with self.assertRaises(ValueError):C.conservation(['a','b'],rows)

    def test_task_key_native_payload_and_hof_authority_are_not_interchangeable(self):
        r={'path':'/immutable/source','bytes':1,'sha256':'a'*64};h={'path':'/immutable/hof','bytes':1,'sha256':'b'*64}
        rows=[{'molecule_id':'m','record_id':'r1','record_payload_sha256':'c'*64},
              {'molecule_id':'m','record_id':'r2','record_payload_sha256':'d'*64}]
        self.assertEqual(C.task_key(r,h,rows),C.task_key(r,h,list(reversed(rows))))
        changed=[dict(rows[0],record_payload_sha256='e'*64),rows[1]]
        self.assertNotEqual(C.task_key(r,h,rows),C.task_key(r,h,changed))
        with self.assertRaises(ValueError):C.task_key(r,h,[rows[0],rows[0]])
