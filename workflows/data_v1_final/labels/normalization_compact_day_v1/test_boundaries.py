"""Three day-only boundaries: original partitions, route gate and large DATA IO."""
import hashlib,os,tempfile,unittest
from pathlib import Path
from . import contract as C,io as I,source_inverse as F

class Boundaries(unittest.TestCase):
    def test_full_prefix_inverse_original171_order_and_committed_cursors(self):
        F.proof()
        groups=[{'group_index':i,'source_job_id':str(i),'label_files':[]} for i in range(171)];C.exact_logical_groups(groups)
        with self.assertRaises(ValueError):C.exact_logical_groups(list(reversed(groups)))
        sources=[{'file_id':0,'rows':20},{'file_id':1,'rows':5}]
        w=[{'file_id':0,'lo':4,'hi':20,'all_part_reopen_bits_verified':True},{'file_id':1,'lo':0,'hi':5,'all_part_reopen_bits_verified':True}]
        self.assertEqual(C.advance(sources,{'0':4},w),{'0':20,'1':5})
        with self.assertRaises(ValueError):C.advance(sources,{'0':4},[dict(w[0],lo=5)])
        with self.assertRaises(ValueError):C.advance(sources,{'0':4},[dict(w[0],all_part_reopen_bits_verified=False)])

    def test_phase_never_advances_without_exact_original_numeric_output(self):
        from .run import next_route
        with self.assertRaises(ValueError):C.plan({'execution_mode':'FINAL_COMMON_STATS'})
        query={'path':'/synthetic/query.json','bytes':1,'sha256':'a'*64}
        self.assertEqual(next_route(1,{'statistics_purpose':'normalization_quantiles','next_query_stage':query}),(1,query))
        with self.assertRaises(ValueError):next_route(1,{'statistics_purpose':'normalization_quantiles','next_query_stage':None,'exact_tail_reference':None})
        self.assertEqual(next_route(1,{'statistics_purpose':'normalization_quantiles','next_query_stage':None,'exact_tail_reference':query}),(2,None))
        with self.assertRaises(ValueError):next_route(0,{'statistics_purpose':'normalization_moments','next_query_stage':None})
        C.reference({'path':'/synthetic/large.parquet','bytes':512<<20,'sha256':'a'*64})
        for n in (True,0,-1):
            with self.assertRaises(ValueError):C.reference({'path':'/synthetic/large.parquet','bytes':n,'sha256':'a'*64})

    def test_cpu_three_mib_whole_fd_sha_and_no_symlink_or_mutation(self):
        with tempfile.TemporaryDirectory(prefix='compact_day_pure_',dir='/tmp') as tmp:
            p=Path(tmp)/'synthetic.bin';p.write_bytes(b'a'*(3<<20));ref=I.pin(p)
            self.assertEqual(I.require(ref),p)
            with p.open('r+b') as f:f.write(b'b')
            with self.assertRaises(ValueError):I.require(ref)
            alias=Path(tmp)/'link.bin';alias.symlink_to(p)
            with self.assertRaises(ValueError):I.require(dict(I.pin(p),path=str(alias)))
if __name__=='__main__':unittest.main()
