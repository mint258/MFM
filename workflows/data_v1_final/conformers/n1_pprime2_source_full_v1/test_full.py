"""Six synthetic roster/once/physical-ID boundaries; no source body or UFF."""
import time,unittest
from . import contract as C,io as I
from .planning import row_for_task

class SourceFullBoundaries(unittest.TestCase):
    def test_full_roster_import32_and_remaining4599_conserve_without_overlap(self):
        keys=['synthetic_%05d'%i for i in range(4631)];out=C.expected_source_partition(keys,keys[17:49])
        self.assertEqual(len(out['imported_keys']),32);self.assertEqual(len(out['new_keys']),4599)
        self.assertEqual(len(out['waves']),72);self.assertEqual(len(out['waves'][-1]),55)
        self.assertFalse(set(out['new_keys'])&set(out['imported_keys']))
        self.assertEqual(set(k for wave in out['waves'] for k in wave),set(out['new_keys']))

    def test_duplicate_import_unknown_import_and_duplicate_source_are_rejected(self):
        for keys,imports in ((['a','a'],[]),(['a','b'],['a','a']),(['a'],['outside'])):
            with self.assertRaises(ValueError):C.expected_source_partition(keys,imports)
        self.assertEqual(C.expected_source_partition(['b','a'],iter(['a']))['new_keys'],['b'])

    def test_source_baseline_native_ID_preserved_and_no_dense_extra_int64(self):
        task={'meta':{'molecule_id':'synthetic'},'task_key':'k','records':[{'record_id':'native_PM7'}],
            'existing_conformers':[{'sprime_conf_idx':0}],'baseline_geometry_id':'opaque_original_baseline','baseline_row_sha256':'s'}
        row=row_for_task(task,{'path':'task'},{'path':'base'})
        self.assertEqual(row['source_record_id'],'native_PM7');self.assertEqual(row['baseline_geometry_id'],'opaque_original_baseline')
        self.assertIsNone(row['final_physical_extra_int64_id']);self.assertFalse(row['common']);self.assertFalse(row['production_membership'])

    def test_imported_consumed_task_cannot_be_resubmitted_as_new(self):
        row={'task_key':'old','state':'UNCONSUMED_NEW_ATTEMPT_NOT_AUTHORIZED_UNTIL_FINITE_ROOT_REVIEW'}
        with self.assertRaises(ValueError):C.check_batch_partition({'tasks':[row],'task_count':1},{'old'})
        row['state']='IMPORTED_ALREADY_CONSUMED_NO_RETRY'
        with self.assertRaises(ValueError):C.check_batch_partition({'tasks':[row],'task_count':1},set())

    def test_wave_count_mismatch_duplicate_and_more_than64_are_rejected(self):
        row=lambda key:{'task_key':key,'state':'UNCONSUMED_NEW_ATTEMPT_NOT_AUTHORIZED_UNTIL_FINITE_ROOT_REVIEW'}
        for batch in ({'tasks':[row('a')],'task_count':2},{'tasks':[row('a'),row('a')],'task_count':2},
            {'tasks':[row(str(i)) for i in range(65)],'task_count':65}):
            with self.assertRaises(ValueError):C.check_batch_partition(batch,set())
        self.assertEqual(C.check_batch_partition({'tasks':[row('a')],'task_count':1},set()),['a'])

    def test_unknown_once_consumption_and_pending_packet_never_become_fake_second(self):
        self.assertIs(I.claim.__globals__.get('time'),time)
        self.assertIs(I.event_checkpoint.__globals__.get('time'),time)
        self.assertTrue(callable(I.claim.__globals__['time'].time))
        self.assertTrue(callable(I.event_checkpoint.__globals__['time'].time))
        self.assertEqual(C.source_outcome(True,False,False),'UNKNOWN_CONSUMED_NO_AUTORETRY')
        self.assertEqual(C.source_outcome(False,False,False),'UNSTARTED_UNCONSUMED_NOT_RETRIED')
        self.assertEqual(C.source_outcome(True,True,False),'CONSUMED_PACKET_PENDING_SECOND_GEOMETRY')
        with self.assertRaises(ValueError):C.source_outcome(False,True,True)
        with self.assertRaises(ValueError):C.source_outcome(True,False,True)
if __name__=='__main__':unittest.main()
