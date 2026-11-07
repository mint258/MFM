"""Tiny real Parquet/DuckDB/original QueryCache API fixture, no native NN calls."""
import os
from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace
import unittest
from . import run as R,catalog as C
from ..alpha_runtime_v1 import common as Q
from ..exact_nn_cached_v1.cache import QueryCache
from ..exact_nn_cached_v1.sql_runtime import literal


class NativeSQL(unittest.TestCase):
    def test_bulk_fp_join_seed_one_missing_and_all_mid_order(self):
        import duckdb
        import pyarrow as pa
        import pyarrow.parquet as pq
        with tempfile.TemporaryDirectory()as folder:
            root=Path(folder);old=root/'old';scores=old/'scores'/'0';scores.mkdir(parents=True);out=root/'new';out.mkdir()
            key=lambda i:'A'*13+chr(65+i)+'-'+'B'*10+'-N'
            fp='03'+'00'*255;absent='f0'+'00'*255;unrelated='0f'+'00'*255
            row=dict(ecfp4_2048_hex=fp,nearest_v1_key=key(3),nearest_v1_tanimoto=2/6,
                reference_ordinal=3,score_numerator=2,score_denominator=6,evaluated_references=9,
                strictly_bound_pruned_references=C.N-9,reference_molecules=C.N)
            refs=[]
            for index,value in enumerate((dict(reversed(list(row.items()))),dict(row,ecfp4_2048_hex=unrelated))):
                path=scores/('part_%d.parquet'%index);pq.write_table(pa.Table.from_pylist([value]),path,compression='zstd')
                refs.append(dict(Q.reference(path),rows=1,fp_bucket='0'))
            with(old/'closed_files_fixture.jsonl').open('wb')as stream:
                for ref in refs:stream.write(C.canonical(ref)+b'\n')
            binding=Q.write(root/'fixture_binding.json',{'fixture_only':True})
            source=dict(root=str(old),manifest={'distinct_query_fingerprints':2},binding={'fixture':True},
                original_binding_reference=binding,derived_binding_reference=binding,lineage_reference=None)
            db=duckdb.connect(':memory:');db.execute('SET threads=1');cache=None
            try:
                db.execute('CREATE TABLE sample(ordinal BIGINT,cid BIGINT,full_key VARCHAR,ecfp4_2048_hex VARCHAR)')
                db.executemany('INSERT INTO sample VALUES(?,?,?,?)',[(2,103,key(2),absent),(0,101,key(0),fp),(1,102,key(1),fp)])
                db.execute('CREATE TABLE query_fp AS SELECT ecfp4_2048_hex,min(ordinal)first_ordinal FROM sample GROUP BY ecfp4_2048_hex')
                guard=SimpleNamespace(poll=lambda *args,**kwargs:None)  # Resource observation only; actual SQL/cache APIs.
                result=R.import_hits(db,[source],out,guard,Q,pq,literal,uid=os.getuid())
                self.assertEqual(result['reused_distinct_query_fingerprints'],1)
                preserved=pq.read_table(result['reused_original9_column_results_reference']['path']).to_pylist()
                self.assertEqual(preserved,[row])
                self.assertEqual(struct.pack('<d',preserved[0]['nearest_v1_tanimoto']),struct.pack('<d',2/6))
                cache=QueryCache(out/'queries.sqlite','a'*64,C.N,sqlite_cache_bytes=1<<20)
                member=cache.source('fixture_fixed_sample');keys=b''.join((key(i)+'\n').encode()for i in range(5))
                self.assertEqual(R.seed(cache,db,member,keys,guard,Q),(1,1))
                self.assertEqual((cache.source_count(member),cache.pending_count(member)),(2,1))
                self.assertEqual(cache.db.execute('SELECT first_ordinal FROM queries WHERE fp=?',(bytes.fromhex(fp),)).fetchone()[0],0)
                pending=[entry for batch in cache.pending_batches(16,member)for entry in batch]
                self.assertEqual(len(pending),1);identity,raw=pending[0];self.assertEqual(raw.hex(),absent)
                cache.store(identity,raw,dict(score=.5,reference_ordinal=4,score_numerator=2,score_denominator=4,
                    evaluated_references=11,strictly_bound_pruned_references=C.N-11,reference_molecules=C.N))
                cache.commit();self.assertEqual(cache.pending_count(member),0)
                observed=[]
                for ordinal,cid,full_key,text in db.execute('SELECT *FROM sample ORDER BY ordinal').fetchall():
                    value=cache.lookup(bytes.fromhex(text));observed.append((ordinal,cid,value['score_numerator'],value['score_denominator'],value['reference_ordinal']))
                self.assertEqual(observed,[(0,101,2,6,3),(1,102,2,6,3),(2,103,2,4,4)])
            finally:
                if cache is not None:cache.close()
                db.close()


if __name__=='__main__':unittest.main()
