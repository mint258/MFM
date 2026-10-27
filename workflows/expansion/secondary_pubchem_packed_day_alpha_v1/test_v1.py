"""Three meaningful synthetic day32 boundaries; no corpus DATA or chemistry."""
import json,tempfile,unittest
from pathlib import Path
from secondary_cpu_queue_v1 import common as Q
from secondary_pubchem_screening_alpha_v1 import source,journal
from . import contracts as C,resource as R,source_inverse as F
TEST_ROOT=None

class SyntheticBudget:
    def check(self,extra=0,drain=False):return None

class Boundaries(unittest.TestCase):
    def test_source_inverse_and_disjoint_exact_original_indices(self):
        F.proof();a={'a':{'indices':[2,7],'node':'compute-0-1','cpus':32},'b':{'indices':[4],'node':'compute-0-6','cpus':32}}
        C.selection([2,4,7],a)
        with self.assertRaises(ValueError):C.selection([2,4,7],dict(a,b={**a['b'],'indices':[4,7]}))
        with self.assertRaises(ValueError):C.selection([2,4,7],dict(a,b={**a['b'],'indices':[4,8]}))
        with self.assertRaises(ValueError):C.selection([2,4,7],dict(a,b={**a['b'],'cpus':True}))

    def test_real32_request_not_old16_and_large_data_not_small_source(self):
        argv=['/python','-B','-m',C.MODULE,'--plan','/plan','--startup-proof','/proof']
        r={'kind':'analysis','pilot':False,'cpus':32,'memory_policy':Q.POLICY,'wall_seconds':86400,'execution_argv':argv};R.request_shape(r)
        for n in (16,True,32.0):
            with self.assertRaises(ValueError):R.request_shape(dict(r,cpus=n))
        with self.assertRaises(ValueError):R.request_shape(dict(r,execution_argv=[*argv[:3],'secondary_pubchem_continuation_alpha_v3.run',*argv[4:]]))
        ref={'path':str(Q.ROOT/'control/synthetic_index.jsonl'),'bytes':16<<20,'sha256':'a'*64};C.data_ref(ref)
        with self.assertRaises(ValueError):Q.normalized(ref)
        for n in (0,True,-1):
            with self.assertRaises(ValueError):C.data_ref(dict(ref,bytes=n))

    def test_original_durable_dispatch_complete_unknown_and_parquet_close(self):
        Q.need(TEST_ROOT is not None,'ACTUAL_PARENT_SYNTHETIC_TEST_ROOT')
        with tempfile.TemporaryDirectory(prefix='day32_pure_',dir=TEST_ROOT) as name:
            root=Path(name);part=root/'source_000000.tsv';raw=b'1\tF\n';part.write_bytes(raw)
            original=source.record(raw,source.row_fact(raw,1,0,0),source.pin(part));writer=journal.Writer(root,'synthetic',SyntheticBudget())
            writer.dispatch(original);writer.complete(original,None,{'type':'SyntheticOnly','message':'retained UNKNOWN not chemical rejection'});result=writer.close()
            self.assertEqual(result['dispatched_rows'],1);self.assertEqual(result['completed_rows'],1)
            self.assertEqual(result['counts'],{'accepted':0,'chemReject':0,'technicalUnresolved':1})
            path=source.verify(result['full_dispatch_and_result_journal']);events=[json.loads(x) for x in path.read_text().splitlines()]
            self.assertEqual([r['event'] for r in events],['DISPATCH_DURABLE_BEFORE_SUBMIT','COMPLETE_RESULT_DURABLE_BEFORE_PARQUET'])
            self.assertEqual(events[1]['value']['input'],original);source.verify(result['features'])
if __name__=='__main__':unittest.main()
