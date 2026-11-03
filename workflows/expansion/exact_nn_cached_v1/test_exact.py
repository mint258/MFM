"""Actual RDKit oracle tests; run on Linux in the pinned scientific env."""
import random
import struct
import tempfile
import unittest
from pathlib import Path
from .engine import CachedReference,modules,upper_bound,strict_below,WIDTH
from .cache import QueryCache

CAP=2<<30


def raw(bits):
    out=bytearray(WIDTH)
    for bit in bits:out[bit//8]|=1<<(bit%8)
    return bytes(out)


def integer_oracle(query,references):
    q=int.from_bytes(query,'little');best=-1.;index=-1
    for ordinal,value in enumerate(references):
        r=int.from_bytes(value,'little');union=(q|r).bit_count()
        score=(q&r).bit_count()/union if union else 0.
        if score>best:best,index=score,ordinal
    return best,index


class ExactTests(unittest.TestCase):
    def assert_oracle(self,queries,references):
        ds=modules();cache=CachedReference(references,worker_rss_cap_bytes=CAP)
        decoded=[ds.CreateFromBinaryText(r) for r in references]
        for query in queries:
            result=cache.nearest(query);expected,index=integer_oracle(query,references)
            native=ds.BulkTanimotoSimilarity(ds.CreateFromBinaryText(query),decoded)
            self.assertEqual(struct.pack('<d',result['score']),struct.pack('<d',expected))
            self.assertEqual(struct.pack('<d',result['score']),struct.pack('<d',max(native)))
            self.assertEqual(result['reference_ordinal'],index)
            self.assertEqual(index,native.index(max(native)))
            self.assertEqual(result['evaluated_references']+result['strictly_bound_pruned_references'],len(references))
        self.assertEqual(cache.decode_calls,len(references))
        return cache

    def test_exhaustive_six_bit_space_and_original_ties(self):
        values=[raw(i for i in range(6) if mask&(1<<i)) for mask in range(64)]
        shuffled=list(values);random.Random(7103).shuffle(shuffled)
        for refs in (values,values[::3],shuffled[:29],shuffled+shuffled[:7]):
            self.assert_oracle(values,refs)

    def test_zero_zero_native_is_zero_and_earliest_reference(self):
        self.assert_oracle([raw([])],[raw([1]),raw([]),raw([2])])
        result=CachedReference([raw([])],worker_rss_cap_bytes=CAP).nearest(raw([]))
        self.assertEqual(result['score'],0.)

    def test_equal_bound_group_and_earliest_ordinal(self):
        query=raw([0,1]);refs=[raw(range(6)),raw([0,7])]
        cache=self.assert_oracle([query],refs)
        self.assertEqual(cache.nearest(query)['reference_ordinal'],0)

    def test_rounded_up_point_one_cannot_prune_exact_equality(self):
        query=raw(range(11));refs=[raw(range(110)),raw([0,1,*range(200,209)])]
        cache=self.assert_oracle([query],refs);result=cache.nearest(query)
        self.assertEqual(result['score'],.1);self.assertEqual(result['reference_ordinal'],0)
        self.assertIn(110,result['searched_popcount_groups'])
        self.assertFalse(strict_below(11,110,2,20))

    def test_strict_pruning_keeps_accounting_and_all_references(self):
        query=raw([0,1]);refs=[query,raw([0]),raw(range(10)),query]
        result=self.assert_oracle([query]*12,refs).nearest(query)
        self.assertEqual(result['reference_ordinal'],0)
        self.assertEqual(result['evaluated_references'],2)
        self.assertEqual(result['strictly_bound_pruned_references'],2)

    def test_invalid_width_empty_and_declared_rss(self):
        for refs in ([],[b'x']):
            with self.assertRaises(ValueError):CachedReference(refs,worker_rss_cap_bytes=CAP)
        with self.assertRaises(RuntimeError):CachedReference([raw([0])],worker_rss_cap_bytes=1)
        self.assertEqual(upper_bound(0,0),(0,1))

    def test_spawn_workers_decode_once_and_preserve_batch_results(self):
        from .workers import exact_batches
        references=[raw(i for i in range(6) if mask&(1<<i)) for mask in range(0,64,3)]
        queries=[raw(i for i in range(6) if mask&(1<<i)) for mask in range(32)]
        ready=[];observed={}
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'references.bin';path.write_bytes(b''.join(references))
            batches=([ (i,q) for i,q in enumerate(queries) ][start:start+3] for start in range(0,len(queries),3))
            for batch in exact_batches(path,len(references),batches,workers=2,
                    worker_rss_cap_bytes=CAP,ready_callback=ready.append):
                self.assertEqual(batch['reference_decode_calls'],len(references))
                for identity,query,result in batch['results']:
                    expected,index=integer_oracle(query,references)
                    self.assertEqual(struct.pack('<d',result['score']),struct.pack('<d',expected))
                    self.assertEqual(result['reference_ordinal'],index);observed[identity]=True
        self.assertEqual(len({r['worker_pid'] for r in ready}),2)
        self.assertTrue(all(r['reference_decode_calls']==len(references) for r in ready))
        self.assertEqual(len(observed),len(queries))


class CacheTests(unittest.TestCase):
    def test_disk_dedup_source_membership_and_binary64(self):
        with tempfile.TemporaryDirectory() as folder:
            cache=QueryCache(Path(folder)/'q.sqlite','a'*64,2)
            full=cache.source('full');small=cache.source('small')
            q=raw([0]);other=raw([1]);identity=cache.add(q,0,full)
            self.assertEqual(cache.add(q,99,small),identity)
            cache.add(other,1,full);cache.commit()
            self.assertEqual(cache.count(),2);self.assertEqual(cache.source_count(small),1)
            result=CachedReference([raw(range(10)),other],worker_rss_cap_bytes=CAP).nearest(q)
            cache.store(identity,q,result);cache.commit()
            self.assertEqual(struct.pack('<d',cache.lookup(q)['score']),struct.pack('<d',.1))
            self.assertEqual(cache.pending_count(small),0);self.assertEqual(cache.pending_count(full),1)
            self.assertEqual(list(cache.pending_batches(2,small)),[])
            cache.close();cache=QueryCache(Path(folder)/'q.sqlite','a'*64,2)
            self.assertEqual(cache.lookup(q)['reference_ordinal'],0)
            cache.db.execute('UPDATE queries SET numerator=2 WHERE id=?',(identity,))
            with self.assertRaises(ValueError):cache.lookup(q)
            cache.close()

    def test_cache_scope_and_conflicting_result(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'q.sqlite';cache=QueryCache(path,'a'*64,2)
            q=raw([0]);identity=cache.add(q,0)
            with self.assertRaises(ValueError):cache.lookup(q)
            result=CachedReference([q,q],worker_rss_cap_bytes=CAP).nearest(q)
            cache.store(identity,q,result);cache.store(identity,q,result)
            result['reference_ordinal']=1
            with self.assertRaises(ValueError):cache.store(identity,q,result)
            cache.close()
            with self.assertRaises(ValueError):QueryCache(path,'b'*64,2)


if __name__=='__main__':unittest.main()
