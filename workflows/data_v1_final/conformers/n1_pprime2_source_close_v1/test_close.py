"""Pure synthetic metadata boundaries; no runtime, packet body or optimizer."""
import unittest
from . import contract as C


class TerminalCloseBoundaries(unittest.TestCase):
    def test_durable_packet_without_final_receipt(self):
        row=C.classify(dict(claim=True,dispatch=True,start=True,packet=True),claim_valid=True,dispatch_valid=True,start_valid=True,packet_valid=True,has_second=True)
        self.assertEqual(row['state'],'REAL_SECOND_SOURCE_PACKET');self.assertTrue(row['real_second']);self.assertFalse(row['automatic_retry_authorized'])

    def test_dispatch_only_is_unknown_consumed(self):
        row=C.classify(dict(claim=True,dispatch=True),claim_valid=True,dispatch_valid=True)
        self.assertTrue(row['safety_consumed']);self.assertFalse(row['science_result_observed']);self.assertNotEqual(row['state'],'PROVEN_UNSTARTED_UNCONSUMED')

    def test_missing_parent_even_without_receipt(self):
        with self.assertRaisesRegex(ValueError,'MISSING_ACTUAL_TERMINAL'):C.require_parents(['123'],{})
        with self.assertRaisesRegex(ValueError,'ACTUALLY_BE_TERMINAL'):C.require_parents(['123'],{'123':{'state':'RUNNING'}})

    def test_packet_without_claim_or_start_is_retained_unknown(self):
        row=C.classify(dict(packet=True));self.assertTrue(row['safety_consumed']);self.assertFalse(row['scientific_status_may_be_copied'])
        row=C.classify(dict(start=True,finished=True));self.assertTrue(row['safety_consumed']);self.assertFalse(row['real_second'])

    def test_invalid_sha_and_finished_conflict_cannot_copy_science(self):
        a={'path':'/literal/packet','bytes':12,'sha256':'a'*64};b=dict(a,sha256='b'*64)
        with self.assertRaisesRegex(ValueError,'MISMATCH'):C.same_sha(a,b)
        row=C.classify(dict(claim=True,dispatch=True,start=True,packet=True),claim_valid=True,dispatch_valid=True,start_valid=True,packet_valid=True,has_second=True,conflicts=['SHA mismatch'])
        self.assertTrue(row['safety_consumed']);self.assertFalse(row['scientific_status_may_be_copied']);self.assertFalse(row['real_second'])

    def test_proven_unstarted_requires_all_task_evidence_absent(self):
        row=C.classify({});self.assertEqual(row['state'],'PROVEN_UNSTARTED_UNCONSUMED');self.assertFalse(row['safety_consumed'])
        for name in C.EVIDENCE_KINDS:
            row=C.classify({name:True});self.assertTrue(row['safety_consumed'],name)
        with self.assertRaisesRegex(ValueError,'WITHOUT_ACTUAL_EVIDENCE'):C.classify({},claim_valid=True)

    def test_complete_partition_and_duplicate_rejection(self):
        roster=[{'task_key':f'{i:064x}'} for i in range(4631)];imports=roster[:32]
        union=C.union_source(roster,imports,[roster[32]]);self.assertEqual(len(union['new_keys']),4599);self.assertEqual(len(union['not_registered_or_not_closed_keys']),4598)
        with self.assertRaisesRegex(ValueError,'DUPLICATE_CLOSED'):C.union_source(roster,imports,[roster[32],roster[32]])
        with self.assertRaisesRegex(ValueError,'IMPORTED_OR_UNKNOWN'):C.union_source(roster,imports,[roster[0]])

    def test_timeout_and_failed_startup_costs_are_not_dropped(self):
        rows={'1':dict(job_id='1',state='TIMEOUT',alloc_cpus=16,elapsed_raw_seconds=7201),
            '2':dict(job_id='2',state='FAILED',alloc_cpus=16,elapsed_raw_seconds=3)}
        C.require_parents(['1','2'],rows);self.assertEqual(C.parent_cost(rows),115264)
        row=C.classify(dict(claim=True,dispatch=True,start=True,packet=True),claim_valid=True,dispatch_valid=True,start_valid=True,packet_valid=True)
        self.assertEqual(row['state'],'CONSUMED_VALID_PACKET_PENDING_SECOND');self.assertTrue(row['science_result_observed']);self.assertFalse(row['real_second'])
