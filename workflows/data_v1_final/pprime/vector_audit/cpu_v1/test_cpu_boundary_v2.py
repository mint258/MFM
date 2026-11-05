"""Three incremental CPU-control boundaries; no repeat of original numeric tests."""
import argparse,json,pathlib,unittest
from runtime_control_v2 import checkpoint_iter,source_lineage
from verify_source_delta_v2 import verify
from workflows.data_v1_final.execution.cpu_analysis_v1 import runtime_v2 as cpu_runtime

class Boundaries(unittest.TestCase):
    def test_original_scientific_functions_and_explicit_inverse_are_exact(self):
        r=verify(pathlib.Path(__file__).parent)
        self.assertEqual(r['status'],'PASS');self.assertTrue(r['inverse_full_file_bytes_equal'])
        self.assertEqual([v['name'] for v in r['science_functions']],['load_audit','choose_pairs','make_cases','render'])
    def test_native_shard_and_legacy_engine_group_are_distinct_and_source_unmodified(self):
        source={'shard_id':6,'file_group':5,'native_record_id':'r'};before=dict(source)
        self.assertEqual(source_lineage(source),{'source_shard_id':6,'source_shard_id_status':'PRESENT_NATIVE_SHARD_ID','legacy_engine_file_group':5})
        self.assertEqual(source,before)
        self.assertIsNone(source_lineage({'file_group':5})['source_shard_id'])
        self.assertEqual(source_lineage({'file_group':5})['source_shard_id_status'],'UNAVAILABLE_IN_PREPARED_SOURCE')
        self.assertEqual(source_lineage({'shard_id':None,'file_group':5})['source_shard_id_status'],'UNAVAILABLE_IN_PREPARED_SOURCE')
    def test_stop_is_checked_before_first_and_between_next_without_copy_or_reorder(self):
        events=[]
        def items():
            events.append('read');yield object()
        def deny():events.append('stop');raise RuntimeError('STOP')
        it=checkpoint_iter(items(),deny)
        with self.assertRaisesRegex(RuntimeError,'STOP'):next(it)
        self.assertEqual(events,['stop'])
        values=[object(),object(),object()];count=[0]
        def once():
            count[0]+=1
            if count[0]>1:raise RuntimeError('STOP')
        it=checkpoint_iter(values,once);self.assertIs(next(it),values[0])
        with self.assertRaisesRegex(RuntimeError,'STOP'):next(it)
        self.assertEqual(list(checkpoint_iter(values,lambda:None)),values)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root-preflight',type=pathlib.Path,required=True);p.add_argument('--output',type=pathlib.Path,required=True);a=p.parse_args()
    cpu_runtime.root_guard(a.root_preflight,pathlib.Path(__file__),64*1024**2,wall_limit=3600)
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Boundaries))
    payload={'schema':'VECTOR_CPU_INCREMENTAL_BOUNDARIES_V1','status':'PASS' if result.wasSuccessful() else 'FAIL','tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'original_numeric_fixture_suite_repeated':False,'scientific_data_bodies_read':False,'QM_calls':0}
    with a.output.open('x') as f:json.dump(payload,f,indent=2);f.write('\n')
    if not result.wasSuccessful():raise SystemExit(1)
if __name__=='__main__':main()
