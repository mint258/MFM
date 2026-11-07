"""Bounded real metadata/SQL boundaries; never compile or search scientific DATA."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from . import common as C


class Metadata(unittest.TestCase):
    def test_step_C0_does_not_claim_parent_C0_and_wrong_step_rejected(self):
        with tempfile.TemporaryDirectory()as folder:
            path=Path(folder)/'sacct.txt'
            path.write_text('JobIDRaw|UID|State|ExitCode|\n232|1264|RUNNING|0:0|\n232.7||COMPLETED|0:0|\n')
            actual=dict(job_id='232',uid=1264,step_id='7')
            C.native_closed(actual,C.reference(path),1264,parent_required=False)
            with self.assertRaises(ValueError):C.native_closed(actual,C.reference(path),1264,parent_required=True)
            with self.assertRaises(ValueError):C.native_closed(dict(actual,step_id='8'),C.reference(path),1264,parent_required=False)

    def test_actual_replica_mapping_and_mutation_are_checked(self):
        with tempfile.TemporaryDirectory()as folder:
            root=Path(folder);file=root/'replica';file.write_bytes(b'original')
            origin=dict(C.reference(file),path='/origin/alpha/file')
            descriptor=root/'transport.json'
            C.write_new(descriptor,dict(schema='EXACT_RESCUE_TRANSPORT_V1',source_endpoint=C.ALPHA,source_uid=1264,
                destination_endpoint=C.MAIN,destination_uid=os.getuid(),files=[dict(origin=origin,replica=C.reference(file))]))
            transport=C.Transport(C.reference(descriptor),C.ALPHA,C.MAIN,os.getuid())
            self.assertEqual(transport.resolve(origin)['path'],str(file))
            with self.assertRaises(ValueError):transport.resolve(dict(origin,sha256='0'*64))
            file.write_bytes(b'mutated!')
            with self.assertRaises(ValueError):transport.finish()

    def test_external_catalog_EOF_duplicate_and_complete_16_bucket_mass(self):
        with tempfile.TemporaryDirectory()as folder:
            root=Path(folder);catalog=root/'parts.jsonl'
            part=dict(path='/alpha/origin/part.parquet',bytes=50,sha256='1'*64,rows=2,physical_fp_bucket='a')
            class Local:
                @staticmethod
                def resolve(ref):return ref
            def manifest():return dict(schema='ALPHA_EXACT_FP_RESCUE_EXPORT_V1',status='COMPLETE',endpoint=C.ALPHA,uid=1264,
                md5_hex_text_prefixes=C.PREFIXES,parts_catalog_reference=C.reference(catalog),part_count=1,
                per_bucket_counts={b:(2 if b=='a'else 0)for b in '0123456789abcdef'},distinct_fingerprints=2)
            catalog.write_bytes(json.dumps(part).encode()+b'\n')
            self.assertEqual(C.exported_parts(manifest(),Local()),[part])
            catalog.write_bytes(json.dumps(part).encode())
            with self.assertRaises(ValueError):C.exported_parts(manifest(),Local())
            catalog.write_bytes((json.dumps(part)+'\n') .encode()*2)
            with self.assertRaises(ValueError):C.exported_parts(manifest(),Local())


class SQL(unittest.TestCase):
    def test_anti_join_overlap_all_nine_columns_and_F64(self):
        import duckdb
        import pyarrow as pa
        from .importer import validate_rows,mismatch_sql
        text=next(('%0512x'%i)for i in range(100)if hashlib.md5(('%0512x'%i).encode()).hexdigest()[0]in C.PREFIXES)
        row=dict(ecfp4_2048_hex=text,nearest_v1_key='A'*27,nearest_v1_tanimoto=1/3,reference_ordinal=0,
            score_numerator=1,score_denominator=3,evaluated_references=4,strictly_bound_pruned_references=C.N-4,reference_molecules=C.N)
        db=duckdb.connect();db.execute('SET threads=1')
        try:
            db.register('_main',pa.Table.from_pylist([row]));db.execute('CREATE TABLE main_scores AS SELECT *FROM _main')
            db.execute('CREATE TABLE ref_keys(ordinal BIGINT,full_key VARCHAR)');db.execute('INSERT INTO ref_keys VALUES(0,?)',['A'*27])
            validate_rows(db)
            db.execute('CREATE TABLE existing AS SELECT *FROM main_scores')
            self.assertEqual(db.execute(mismatch_sql()).fetchone()[0],0)
            self.assertEqual(db.execute('SELECT count(*)FROM main_scores ANTI JOIN existing USING(ecfp4_2048_hex)').fetchone()[0],0)
            db.execute('UPDATE existing SET evaluated_references=evaluated_references+1')
            self.assertEqual(db.execute(mismatch_sql()).fetchone()[0],1)
            db.execute('UPDATE existing SET evaluated_references=evaluated_references-1,nearest_v1_tanimoto=0.33333333333333326')
            self.assertEqual(db.execute(mismatch_sql()).fetchone()[0],1)
            db.execute('UPDATE main_scores SET nearest_v1_tanimoto=0.33333333333333326')
            db.remove_function('rescue_f64_bits')  # Re-register for this independent corrupted-row validation.
            with self.assertRaises(ValueError):validate_rows(db)
        finally:db.close()

    def test_real_FP_parquet_sorted_distinct_tail_and_EOF(self):
        import pyarrow as pa
        import pyarrow.parquet as pq
        from .run import query_batches
        values=sorted(('%0512x'%i)for i in range(100)if hashlib.md5(('%0512x'%i).encode()).hexdigest()[0]in C.PREFIXES)[:3]
        class Local:
            @staticmethod
            def resolve(ref):return ref
        class Guard:
            def check(self):pass
        with tempfile.TemporaryDirectory()as folder:
            path=Path(folder)/'part.parquet';pq.write_table(pa.table({'ecfp4_2048_hex':values}),path)
            part=dict(C.reference(path),rows=3,physical_fp_bucket='0');counts={b:0 for b in '0123456789abcdef'}
            self.assertEqual(sum(list(query_batches([part],Local(),dict(query_batch=2),Guard(),counts)),[]),values)
            self.assertEqual(counts['0'],3)
            with self.assertRaises(ValueError):list(query_batches([part,part],Local(),dict(query_batch=2),Guard(),counts))
            with self.assertRaises(ValueError):list(query_batches([dict(part,rows=4)],Local(),dict(query_batch=2),Guard(),counts))


if __name__=='__main__':unittest.main()
