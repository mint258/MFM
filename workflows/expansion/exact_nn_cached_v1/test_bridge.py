"""Small native SQL oracles for representation seams, not production samples."""
import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch
from .typed_rank import check_membership
from .compare_coverage import comparison
from .coverage import sample_membership
from ..common import reference
from .run import allocation_guard
from .sql_runtime import literal


class TypedBridgeTests(unittest.TestCase):
    def setUp(self):
        import duckdb
        self.db=duckdb.connect()

    def tearDown(self):self.db.close()

    def pool(self):
        self.db.execute('''CREATE TABLE candidates AS SELECT 1::BIGINT cid,'A' full_key,10 heavy_atoms,
            '6,8' element_combination,'ring' generic_murcko,['R'] generic_ring_systems
            UNION ALL SELECT 2,'B',12,'6,7','chain',[]''')
        self.db.execute('CREATE TABLE pool AS SELECT * FROM candidates')

    def test_full_identity_antijoins_and_structural_feature_seam(self):
        self.pool();check_membership(self.db,2)
        self.db.execute("UPDATE pool SET heavy_atoms=99 WHERE cid=2")
        with self.assertRaises(ValueError):check_membership(self.db,2)

    def test_no_missing_duplicate_or_replaced_pool_identity(self):
        self.pool();self.db.execute("UPDATE pool SET full_key='C' WHERE cid=2")
        with self.assertRaises(ValueError):check_membership(self.db,2)
        self.db.execute('DELETE FROM pool WHERE cid=2')
        with self.assertRaises(ValueError):check_membership(self.db,2)

    def coverage(self):
        self.db.execute('''CREATE TABLE before AS SELECT 0 sample_ordinal,1::BIGINT cid,'A' full_key,
            .1::DOUBLE nearest_reference_tanimoto,false reference_identity_present,false fingerprint_self_match,
            9 reference_ordinal,'X' nearest_reference_key
            UNION ALL SELECT 1,2,'B',1.0,true,true,1,'B'
            UNION ALL SELECT 2,3,'C',.5,false,false,8,'Y' ''')
        self.db.execute('CREATE TABLE after AS SELECT * FROM before')
        self.db.execute("UPDATE after SET nearest_reference_tanimoto=1.,reference_identity_present=true,fingerprint_self_match=true,reference_ordinal=20,nearest_reference_key='A' WHERE cid=1")

    def test_same_sample_monotonic_coverage_reports_self_matches(self):
        self.coverage();result=comparison(self.db,3)
        self.assertEqual(result['all_fixed_sample']['molecules'],3)
        self.assertEqual(result['all_fixed_sample']['improved'],1)
        self.assertEqual(result['all_fixed_sample']['before_identity_self'],1)
        self.assertEqual(result['all_fixed_sample']['after_identity_self'],2)
        self.assertEqual(result['identities_absent_from_both_references']['molecules'],1)

    def test_augmented_equal_score_must_keep_original_earliest_ordinal(self):
        self.coverage();self.db.execute('UPDATE after SET reference_ordinal=99 WHERE cid=3')
        with self.assertRaises(ValueError):comparison(self.db,3)

    def test_scientific_sample_jsonl_exact_membership_and_ordinal_census(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"quoted'path";path.mkdir();membership=path/'sample.parquet';projection=path/'sample.jsonl'
            self.db.execute('COPY (SELECT i sample_ordinal,i+1 cid,chr(65+i::INTEGER) full_key FROM range(3) t(i)) TO '+literal(membership)+' (FORMAT PARQUET)')
            projection.write_text(''.join(json.dumps({'cid':i+1,'full_key':chr(65+i),'extra_structure':'allowed projection field'})+'\n' for i in range(3)))
            q={'sample_membership':reference(membership)};plan={'workers':2,'parent_rss_cap_bytes':1<<30}
            sample_membership(q,projection,plan,3)
            projection.write_text(projection.read_text().replace('"B"','"Z"'))
            with self.assertRaises(ValueError):sample_membership(q,projection,plan,3)


class AllocationMetadataTests(unittest.TestCase):
    def test_missing_slurm_memory_is_not_invented_as_a_reservation(self):
        plan={'workers':16,'worker_rss_cap_bytes':1<<30,'parent_rss_cap_bytes':4<<30,'minimum_node_available_bytes':24<<30}
        with patch.dict('os.environ',{'SLURM_JOB_ID':'fixture','SLURM_CPUS_PER_TASK':'16'},clear=True), \
                patch('socket.gethostname',return_value='compute-0-21'),patch.object(Path,'read_text',return_value='MemAvailable: 83886080 kB\n'):
            result=allocation_guard(plan)
        self.assertIsNone(result['actual_finite_slurm_memory_bytes'])
        self.assertFalse(result['explicit_Slurm_memory_request_inferred'])
        self.assertEqual(result['declared_software_memory_bytes'],20<<30)

    def test_real_finite_or_physical_memory_constraints_remain(self):
        plan={'workers':16,'worker_rss_cap_bytes':1<<30,'parent_rss_cap_bytes':4<<30,'minimum_node_available_bytes':24<<30}
        with patch.dict('os.environ',{'SLURM_JOB_ID':'fixture','SLURM_CPUS_PER_TASK':'16','SLURM_MEM_PER_NODE':'16384'},clear=True), \
                patch('socket.gethostname',return_value='compute-0-21'),patch.object(Path,'read_text',return_value='MemAvailable: 83886080 kB\n'):
            with self.assertRaises(ValueError):allocation_guard(plan)
        with patch.dict('os.environ',{'SLURM_JOB_ID':'fixture','SLURM_CPUS_PER_TASK':'16'},clear=True), \
                patch('socket.gethostname',return_value='compute-0-21'),patch.object(Path,'read_text',return_value='MemAvailable: 31457280 kB\n'):
            with self.assertRaises(ValueError):allocation_guard(plan)


if __name__=='__main__':unittest.main()
