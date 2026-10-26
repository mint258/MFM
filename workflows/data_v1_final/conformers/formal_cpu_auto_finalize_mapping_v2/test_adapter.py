"""Pure source/identity/threshold boundaries, never a scientific PASS claim."""
from types import SimpleNamespace
import unittest
from . import adapter as A
from workflows.data_v1_final.conformers.formal_cpu_auto_prepare_mapping_v1 import mapping as M
from workflows.data_v1_final.conformers.formal_cpu_auto_v3.identity import append_generated


class FinalizerBoundaries(unittest.TestCase):
    def test_exact_inverse_and_reject_undeclared_quality_edit(self):
        before=A.ORIGINAL.read_bytes().decode();after=(A.HERE/'finalize.py').read_bytes().decode()
        self.assertEqual(after,A.transform(before));self.assertEqual(A.inverse(after),before)
        observed=A.verify_texts(before,after)
        self.assertTrue(observed['entire_file_inverse_equal'])
        self.assertTrue(observed['duckdb_pa_pq_direct_executable_imports_before_first_use'])
        for literal in ('    import duckdb\n','    import pyarrow as pa\n','    import pyarrow.parquet as pq\n'):
            # A comment with the same words is deliberately not an import node.
            with self.assertRaisesRegex(ValueError,'ACTUAL_DIRECT_IMPORT_BINDING'):
                A.import_bindings(after.replace(literal,'    # '+literal.strip()+'\n'))
        with self.assertRaisesRegex(ValueError,'ONLY_ENUMERATED'):
            A.verify_texts(before,after.replace('len(excluded)*50>len(mother)','len(excluded)*49>len(mother)'))

    def test_mapped_device_is_not_a_changed_source_frame(self):
        old=SimpleNamespace(st_dev=52,st_ino=10,st_size=20,st_mtime_ns=30,st_uid=1278)
        new=SimpleNamespace(**vars(old));new.st_dev=53
        self.assertEqual(M.source_frame(old),M.source_frame(new));self.assertNotEqual(M.stable_frame(old),M.stable_frame(new))

    def test_each_nondevice_identity_mutation_rejected(self):
        old=SimpleNamespace(st_dev=53,st_ino=10,st_size=20,st_mtime_ns=30,st_uid=1278)
        for field in ('st_ino','st_size','st_mtime_ns','st_uid'):
            other=SimpleNamespace(**vars(old));setattr(other,field,getattr(other,field)+1)
            self.assertNotEqual(M.source_frame(old),M.source_frame(other),field)

    def test_current_device_and_all_fields_remain_stable(self):
        old=SimpleNamespace(st_dev=53,st_ino=10,st_size=20,st_mtime_ns=30,st_uid=1278)
        for field in vars(old):
            other=SimpleNamespace(**vars(old));setattr(other,field,getattr(other,field)+1)
            self.assertNotEqual(M.stable_frame(old),M.stable_frame(other),field)

    def test_overall2percent_and_element20percent_exact_boundaries(self):
        from .finalize import exclusion_gates
        rows=[dict(effective_role='TRAIN',common_population=i>=2,elements_atomic_numbers=[6,8] if i<10 else [6]) for i in range(100)]
        self.assertTrue(exclusion_gates(rows)['passed'])
        rows[9]['elements_atomic_numbers']=[6];self.assertFalse(exclusion_gates(rows)['passed'])
        rows[9]['elements_atomic_numbers']=[6,8];rows[2]['common_population']=False
        self.assertTrue(exclusion_gates(rows)['overall_gt2_percent'])

    def test_only_se_exception_and_unknown_never_included(self):
        from .finalize import exclusion_gates,membership
        rows=[dict(effective_role='TRAIN',common_population=i>=2,elements_atomic_numbers=[6,34] if i<9 else [6]) for i in range(100)]
        self.assertTrue(exclusion_gates(rows)['passed'])
        row=dict(effective_role='VAL',S_usable_conformers=1,S_conformers=1,records=1,Sprime_status='SUCCESS',merged_uff_count=1,fill_status='EXECUTION_UNRESOLVED')
        self.assertFalse(membership(row)['common_population']);self.assertIn('EXECUTION_UNRESOLVED',membership(row)['exclusion_reasons'])

    def test_sparse_physical_append_never_compacts_failed_original_ids(self):
        rows=[dict(task_key='a'*64,seed=17,candidate_id=c) for c in (2,0)]
        added=append_generated(rows,3,7);self.assertEqual([r['sprime_conf_idx'] for r in added],[8,9]);self.assertEqual([r['candidate_id'] for r in added],[0,2])
        with self.assertRaisesRegex(ValueError,'DUPLICATE_NEW'):append_generated([rows[0],rows[0]],3,7)
        with self.assertRaisesRegex(ValueError,'OVERFLOW'):append_generated(rows,3,(1<<63)-1)

    def test_merge_preserves_original_indices_and_rejects_overwrite(self):
        from .finalize import merge_counts
        rows=[dict(origin='data_v1_fill_10N',kernel_sprime_conf_idx=i,seed=17,candidate_id=i) for i in (2,3)]
        self.assertEqual(merge_counts(2,rows,4),4)
        bad=[dict(rows[0],kernel_sprime_conf_idx=1),rows[1]]
        with self.assertRaisesRegex(ValueError,'OVERWRITES'):merge_counts(2,bad,4)
        with self.assertRaisesRegex(ValueError,'EXCEEDS'):merge_counts(2,rows,3)
