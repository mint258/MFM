"""Tiny real columnar exact-key anti-join and shard-preservation test."""
import tempfile
from pathlib import Path
import unittest
from . import core as C
from .storage import Storage, write_shards
from .test_core import K


class Native(unittest.TestCase):
    def test_full_and_WP5_only_Honly_allfields_closed_shards(self):
        import duckdb
        import pyarrow as pa
        import pyarrow.parquet as pq
        from ..alpha_runtime_v1 import common as Q
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary); db = duckdb.connect(':memory:')
            data = pa.Table.from_pylist([
                dict(cid=1, full_key=K, wp5_key=C.wp5(K), non_h_composition='[[6,1]]', elements=[6], heavy_atoms=1, scalar=-0.0),
                dict(cid=2, full_key='AAAAAAAAAAAAAA-CCCCCCCCCC-N', wp5_key=C.wp5(K), non_h_composition='[[7,1]]', elements=[7], heavy_atoms=1, scalar=0.12345678901234567),
                dict(cid=3, full_key='DDDDDDDDDDDDDD-EEEEEEEEEE-N', wp5_key='DDDDDDDDDDDDDD:N', non_h_composition='[]', elements=[], heavy_atoms=0, scalar=3.25),
                dict(cid=4, full_key='FFFFFFFFFFFFFF-GGGGGGGGGG-N', wp5_key='FFFFFFFFFFFFFF:N', non_h_composition='[[6,1]]', elements=[6], heavy_atoms=1, scalar=4.5),
                dict(cid=5, full_key='HHHHHHHHHHHHHH-IIIIIIIIII-N', wp5_key='HHHHHHHHHHHHHH:N', non_h_composition='[[8,1]]', elements=[8], heavy_atoms=1, scalar=5.75),
            ])
            data = data.append_column('ecfp4_2048_hex', pa.array(['0' * 512, 'a' * 512, '0' * 512, '0' * 512, 'f' * 512]))
            db.register('candidates', data)
            db.execute('CREATE TABLE keys_full(key VARCHAR)'); db.execute('CREATE TABLE keys_wp5(key VARCHAR)')
            db.execute('INSERT INTO keys_full VALUES (?)', [K]); db.execute('INSERT INTO keys_wp5 VALUES (?)', [C.wp5(K)])
            self.assertEqual(db.execute(C.candidate_census_sql()).fetchone(), (5, 5, 5, 0))
            self.assertEqual(db.execute('SELECT cid FROM (' + C.eligible_sql() + ') ORDER BY cid').fetchall(), [(3,), (4,), (5,)])
            store = Storage(out, lambda: None, Q.reference)
            try:
                refs, total, schema = write_shards(db.execute(C.eligible_sql()).fetch_record_batch(1),
                                                 out / 'parts', store, target_bytes=1, max_rows=1)
                self.assertEqual(total, 3); self.assertEqual(schema, data.schema)
                actual = pa.concat_tables([pq.read_table(r['path']) for r in refs]).sort_by('cid')
                self.assertTrue(actual.equals(data.slice(2)))
                self.assertEqual(len(refs), 3)
                self.assertEqual({r['fp_bucket'] for r in refs}, {'0', 'f'})
                self.assertTrue(all(r['rows'] == 1 and Path(r['path']).suffix == '.parquet' for r in refs))
                self.assertFalse(list((out / 'parts').glob('*.partial')))
            finally:
                store.close(); db.close()


if __name__ == '__main__':
    unittest.main()
