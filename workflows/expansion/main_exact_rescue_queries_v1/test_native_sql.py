"""Tiny real Parquet/MD5/DISTINCT/order/shard fixture; no science or NN calls."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from . import core as C
from ..alpha_runtime_v1 import common as Q


class NativeSQL(unittest.TestCase):
    def test_physical_buckets_md5_text_selected_multiplicity_and_single_column(self):
        import duckdb
        import pyarrow as pa
        import pyarrow.parquet as pq
        with tempfile.TemporaryDirectory()as directory:
            root=Path(directory);db=duckdb.connect(':memory:');db.execute('SET threads=1')
            try:
                # Deterministically locate both selected and unselected MD5
                # classes, all in the same physical0 bucket, using real hashes.
                values=[format(i,'0512x')for i in range(1,200)]
                selected=[fp for fp in values if hashlib.md5(fp.encode('ascii')).hexdigest()[0]in C.TARGETS][:3]
                other=next(fp for fp in values if hashlib.md5(fp.encode('ascii')).hexdigest()[0]not in C.TARGETS)
                source=root/'source.parquet';payload=[selected[2],other,selected[0],selected[1],selected[0]]
                pq.write_table(pa.table({'ecfp4_2048_hex':payload,'cid':[1,2,3,4,5]}),source)
                out=root/'out';out.mkdir();parts_path=root/'parts.jsonl';journal_path=root/'closed.jsonl'
                with parts_path.open('wb')as parts,journal_path.open('wb')as journal:
                    result=C.export_bucket(db,[source],'0',5,out,Q.reference,parts,journal,max_rows=2)
                self.assertEqual(result,dict(input_candidate_rows=5,selected_candidate_rows=4,distinct_fingerprints=3,part_count=2))
                refs=[json.loads(line)for line in parts_path.read_bytes().splitlines()];observed=[]
                for ref in refs:
                    self.assertEqual(ref['physical_fp_bucket'],'0');self.assertLessEqual(ref['rows'],2)
                    table=pq.read_table(Q.verify(ref));self.assertEqual(table.schema.names,['ecfp4_2048_hex'])
                    self.assertEqual(str(table.schema.field(0).type),'string');observed.extend(table.column(0).to_pylist())
                self.assertEqual(observed,sorted(set(selected)))
                self.assertTrue(all(hashlib.md5(fp.encode('ascii')).hexdigest()[0]in C.TARGETS for fp in observed))
                self.assertEqual(len(journal_path.read_bytes().splitlines()),2)
                bad=root/'bad.parquet';pq.write_table(pa.table({'ecfp4_2048_hex':['NOT512HEX']}),bad)
                with parts_path.open('ab')as parts,journal_path.open('ab')as journal:
                    with self.assertRaisesRegex(ValueError,'width/domain'):C.export_bucket(db,[bad],'0',1,out,Q.reference,parts,journal)
            finally:db.close()


if __name__=='__main__':unittest.main()
