"""Eight small synthetic checks; no real corpus or production guard invocation."""
from __future__ import annotations
import json, multiprocessing, sqlite3, tempfile, unittest
from pathlib import Path
from . import scan
from .prepare import make_shards
from .reduce import consume_coverage
from .support import (BOUNDARY, RECORD_COLUMNS, TASKS, TASK_FAMILIES, classify_owner,
    declared_shape, lookup_batch, ref, report_flags, sqlite_ro)

class AuditSemantics(unittest.TestCase):
    def test_14_slots_12_quantum_11_families(self):
        self.assertEqual((len(TASKS),len(TASKS)-2,len(set(TASK_FAMILIES.values()))),(14,12,11))
        self.assertEqual(set(TASKS),set(TASK_FAMILIES))
        self.assertEqual(TASK_FAMILIES['pm7_anion'],TASK_FAMILIES['pm7_cation'])

    def test_full_file_partition_preserves_shadow_mass(self):
        files=[{'path':str(i),'rows':20+i,'latest_rows':19+i,'bytes':100+i} for i in range(32)]
        shards=make_shards(files,2)
        self.assertEqual(sorted(r['path'] for s in shards for r in s['files']),sorted(r['path'] for r in files))
        self.assertEqual(sum(s['physical_rows']-s['canonical_rows'] for s in shards),32)
        with self.assertRaises(ValueError):make_shards(files,3)

    def test_latest_owner_and_exact_lane_atoms(self):
        owner={'record_id':'r','molecule_id':'m','attempt_id':1,'job_id':7,'task_id':'t','lane':18,'total_atoms':3}
        self.assertEqual(classify_owner(owner,owner,True),'CANONICAL')
        self.assertEqual(classify_owner(dict(owner,attempt_id=0),owner,True),'NONLATEST_OWNER_TUPLE')
        self.assertEqual(classify_owner(owner,None,True),'RECORD_NOT_IN_AUTHORITY')
        with self.assertRaises(ValueError):classify_owner(dict(owner,total_atoms=4),owner,True)

    def test_declared_shape_never_proves_json_array_payload(self):
        self.assertEqual(declared_shape({'kind':8},5),'UNOBSERVED_JSON_PAYLOAD')
        self.assertIn('PAYLOAD_LENGTH_UNOBSERVED',declared_shape({'kind':5,'shape':[5,3]},5))
        self.assertEqual(declared_shape({'kind':5,'shape':[-1]},5),'INVALID_DECLARED_SHAPE')
        self.assertEqual(declared_shape({'kind':9},5),'ABSENT')
        self.assertEqual(declared_shape({'kind':0},5),'NULL')

    def test_null_and_precision_metadata_are_review_only(self):
        self.assertEqual(report_flags({'status':'SUCCESS','converged':None,'scf_iterations':None}),3)
        self.assertFalse(BOUNDARY['new_masks_created']);self.assertFalse(BOUNDARY['native_program_print_precision_verified'])
        state,claim,digest=scan.precision_metadata('{"EA_eV":{"decimals":4}}')
        self.assertEqual(state,'DECLARED_SOURCE_METADATA');self.assertEqual(claim['EA_eV']['decimals'],4)
        self.assertEqual(len(digest),64)
        self.assertEqual(scan.precision_metadata('[')[0],'MALFORMED_JSON')

    def test_sqlite_batch_lookup_not_whole_owner_loading(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'index.sqlite';db=sqlite3.connect(path)
            db.execute('CREATE TABLE records(record_ordinal,record_id TEXT PRIMARY KEY,molecule_id,attempt_id,job_id,task_id,lane,total_atoms,new_role)')
            db.executemany('INSERT INTO records VALUES(?,?,?,?,?,?,?,?,?)',[(i,'r'+str(i),'m',0,7,'t',18,3,'TRAIN') for i in range(700)])
            db.commit();db.close();ro=sqlite_ro(path)
            try:result=lookup_batch(ro,['r'+str(i) for i in range(600)]+['absent','r0'])
            finally:ro.close()
            self.assertEqual(len(result),600);self.assertNotIn('r699',result);self.assertEqual(result['r599']['record_ordinal'],599)

    def test_coverage_duplicate_role_and_absent_slots(self):
        import numpy as np
        import pyarrow as pa
        seen=np.zeros((14,3),dtype=np.uint8);expected=np.array([0,1,2],dtype=np.uint8)
        def batch(ordinals,roles):
            return pa.record_batch([pa.array(ordinals,type=pa.uint64()),pa.array([0]*len(ordinals),type=pa.uint8()),
                pa.array(roles,type=pa.uint8()),pa.array([3]*len(ordinals),type=pa.uint16())],names=['record_ordinal','task_code','role_code','review_flags'])
        with self.assertRaises(ValueError):consume_coverage(batch([0,0],[0,0]),seen,expected,3)
        with self.assertRaises(ValueError):consume_coverage(batch([1],[0]),seen,expected,3)
        self.assertEqual(int(seen.sum()),0)
        self.assertEqual(consume_coverage(batch([0,2],[0,2]),seen,expected,3),2)
        with self.assertRaises(ValueError):consume_coverage(batch([0],[0]),seen,expected,3)
        self.assertEqual(int(seen.sum()),2);self.assertEqual(int(seen[0,1]),0)

    def test_real_arrow_projection_and_one_open_close(self):
        import pyarrow as pa
        import pyarrow.parquet as pq
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);index=base/'index.sqlite';db=sqlite3.connect(index)
            db.execute('CREATE TABLE records(record_ordinal,record_id TEXT PRIMARY KEY,molecule_id,attempt_id,job_id,task_id,lane,total_atoms,new_role)')
            db.execute('INSERT INTO records VALUES(0,\'r\',\'m\',1,7,\'t\',18,3,\'TRAIN\')');db.commit();db.close()
            cell=pa.struct([('registry_id',pa.int16()),('kind',pa.int8()),('f64',pa.float64()),('text',pa.large_string()),
                ('array_f64',pa.large_list(pa.float64())),('shape',pa.list_(pa.int32()))])
            schema=pa.schema([('record_id',pa.string()),('molecule_id',pa.string()),('attempt_id',pa.int8()),('job_id',pa.int64()),('task_id',pa.string()),
              ('status',pa.string()),('calc_type',pa.string()),('lane',pa.int16()),('total_atoms',pa.int32()),('source_status',pa.string()),('failure_code',pa.string()),
              ('converged',pa.bool_()),('scf_iterations',pa.int32()),('software_version_id',pa.int16()),('numeric_issues',pa.list_(pa.int16())),
              ('precision_by_field_json',pa.large_string()),('raw_audit_selected',pa.bool_()),('raw_output_locator_json',pa.large_string()),
              ('reproduction_package_sha256',pa.string()),('values',pa.large_list(cell))])
            row={'record_id':'r','molecule_id':'m','attempt_id':1,'job_id':7,'task_id':'t','status':'SUCCESS','calc_type':'pm7_B','lane':18,'total_atoms':3,
              'source_status':'SUCCESS','failure_code':None,'converged':None,'scf_iterations':None,'software_version_id':0,'numeric_issues':[],
              'precision_by_field_json':'{}','raw_audit_selected':False,'raw_output_locator_json':None,'reproduction_package_sha256':None,
              'values':[{'registry_id':39,'kind':5,'f64':None,'text':None,'array_f64':[1.0]*300,'shape':[3,100]}]}
            path=base/'source.parquet';pq.write_table(pa.Table.from_pylist([row,dict(row,attempt_id=0)],schema=schema),path,row_group_size=1)
            source=dict(ref(path),family='pm7_neutral',rows=2,latest_rows=1)
            handle=pq.ParquetFile(path)
            try:
                projected=next(handle.iter_batches(columns=scan.metadata_projection(handle,source))).to_pylist()[0]['values'][0]
                self.assertEqual(set(projected),{'registry_id','kind','shape'});self.assertNotIn('array_f64',projected)
            finally:handle.close()
            ctx=multiprocessing.get_context('spawn');stop=ctx.Event()
            scan.initialize({'worker_rss_stop_bytes':3<<30,'batch_records':1,'examples_per_file':8,'precision_variants_per_file':4},str(index),
                {39:{'task':'pm7_B','source_path':'values.atomic_shell_population_e'}},[],stop,ctx.Barrier(16))
            result=scan.scan_file((0,source,str(base),False))
            report=json.loads(Path(result['report']['path']).read_text())
            self.assertEqual((report['physical_rows'],report['canonical_rows']),(2,1))
            self.assertEqual(report['noncanonical_physical_rows'],{'NONLATEST_OWNER_TUPLE':1})
            self.assertEqual((report['io_handles_opened'],report['io_handles_closed']),(1,1))
            self.assertEqual(report['review_flags_counts'],{'3':1});self.assertFalse(report['new_masks_created'])
            self.assertEqual(pq.read_table(result['coverage']['path']).num_rows,1)

if __name__=='__main__':unittest.main()