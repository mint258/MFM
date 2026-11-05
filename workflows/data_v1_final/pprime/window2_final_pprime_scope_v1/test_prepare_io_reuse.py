"""One memory-only fixture for decoded-publication and current-footer reuse."""
import collections,json,struct,types,unittest,zlib
from unittest.mock import patch
from . import binding as B,prepare as P

class PrepareIOReuse(unittest.TestCase):
    def test_same_file_reuse_switch_eviction_and_unchanged_physical_semantics(self):
        import pyarrow as pa,pyarrow.parquet as pq
        raw={'record_id':'opaque:record:A','molecule_id':'M','sprime_conf_idx':7,
            'source_record_id':'original:native:A','status':'SUCCESS','converged':True,
            'atomic_numbers':[6,1],'coordinates':[[1.0000000000000002,-0.0,0.],[2.,0.,0.]]}
        rows_a=[raw,dict(raw,record_id='opaque:record:A2',sprime_conf_idx=8)]
        rows_b=[dict(raw,record_id='opaque:record:B',sprime_conf_idx=9)]
        store=B.BindingStore(':memory:')
        try:
            for filename,rows in [('A',rows_a),('B',rows_b)]:
                store.db.execute('INSERT INTO bases VALUES(?,?)',(filename,zlib.compress(json.dumps(rows).encode())))
            original_decompress=zlib.decompress
            with patch.object(B.zlib,'decompress',wraps=original_decompress) as decode,patch.object(pq,'read_table',side_effect=AssertionError('CLOSED_BLOB_MUST_NOT_REREAD_SOURCE')):
                first=store.base_rows('A');self.assertIs(store.base_rows('A'),first);self.assertEqual(decode.call_count,1)
                store.base_rows('B');self.assertEqual(store._decoded_base_file,'B');self.assertEqual(decode.call_count,2)
                self.assertEqual(store._decoded_base_rows,rows_b)
                again=store.base_rows('A');self.assertIsNot(again,first);self.assertEqual(decode.call_count,3)
                self.assertEqual(again,rows_a)
                for value,expected in zip(again[0]['coordinates'][0],raw['coordinates'][0]):
                    self.assertEqual(struct.pack('<d',value),struct.pack('<d',expected))
                left=dict(again[0],positions_A=again[0]['coordinates'])
                self.assertTrue(B.same_geometry(left,left)[0])
                self.assertFalse(B.same_geometry(left,dict(left,atomic_numbers=[1,6]))[0])

            opened=collections.Counter();reads=collections.Counter();closed=collections.Counter()
            class Footer:
                def __init__(self,filename):
                    self.filename=filename;opened[filename]+=1
                    self.groups=[pa.Table.from_pylist([r]) for r in (rows_a if filename=='A' else rows_b)]
                    self.num_row_groups=len(self.groups)
                    self.metadata=types.SimpleNamespace(row_group=lambda index:types.SimpleNamespace(num_rows=self.groups[index].num_rows))
                def read_row_group(self,index):reads[(self.filename,index)]+=1;return self.groups[index]
                def close(self):closed[self.filename]+=1
            def locator(filename,index=0,mid='M'):
                return {'source_format':'parquet','source_path':filename,'source_row_index':index,'molecule_id':mid}
            P.close_parquet_layout();P.parquet_group.cache_clear()
            try:
                with patch.object(pq,'ParquetFile',side_effect=Footer):
                    self.assertEqual(P.geometry(locator('A'))['record_id'],'opaque:record:A')
                    self.assertEqual(P.geometry(locator('A',1))['sprime_conf_idx'],8)
                    self.assertEqual(P.geometry(locator('A'))['coordinates'],raw['coordinates'])
                    self.assertEqual(opened['A'],1);self.assertEqual(reads[('A',0)],1);self.assertEqual(reads[('A',1)],1)
                    with self.assertRaisesRegex(ValueError,'GEOMETRY_MID_DIFFERS'):P.geometry(locator('A',mid='wrong'))
                    with self.assertRaisesRegex(ValueError,'ACTUAL_GEOMETRY_ROW_MISSING'):P.geometry(locator('A',2))
                    self.assertEqual(P.geometry(locator('B'))['sprime_conf_idx'],9)
                    self.assertEqual(closed['A'],1);self.assertEqual(opened['B'],1)
                    self.assertEqual(P.geometry(locator('A'))['record_id'],'opaque:record:A')
                    self.assertEqual(closed['B'],1);self.assertEqual(opened['A'],2)
                    self.assertEqual(reads[('A',0)],1)
            finally:P.close_parquet_layout();P.parquet_group.cache_clear()
        finally:store.close()
