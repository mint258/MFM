"""Equivalent six-field transition must preserve immutable old checkpoint bytes."""
import copy
from pathlib import Path
import tempfile
import unittest
from . import binding as B


class EquivalentBinding(unittest.TestCase):
    def test_only_backend_changes_and_original_binding_journals_scores_remain(self):
        def ref(name):return {'path':'/'+name,'bytes':1,'sha256':name}
        previous=dict(filtered_pool_reference=ref('filter209'),reference=ref('full196'),
            backend_adoption_reference=ref('old206'),assigned_hash_buckets=list('0123'),partition_id='left',scope_key='same-scope')
        current={**previous,'backend_adoption_reference':ref('native-equivalence')}
        proof=dict(previous_backend_adoption_reference=previous['backend_adoption_reference'],
            native_equivalence_reference=current['backend_adoption_reference'],reference_manifest_reference=previous['reference'],
            filtered_pool_reference=previous['filtered_pool_reference'])
        with tempfile.TemporaryDirectory()as folder:
            root=Path(folder);original=B.Q.write(root/'source_binding.json',previous)
            journal=root/'closed_files_old.jsonl';journal.write_bytes(b'original-closed-journal\n')
            (root/'scores').mkdir();score=root/'scores'/'part.parquet';score.write_bytes(b'original-closed-score')
            before={p:B.Q.reference(p)for p in (root/'source_binding.json',journal,score)}
            derived,lineage=B.establish(root,current,proof)
            self.assertNotEqual(derived['path'],original['path'])
            self.assertEqual(B.Q.load(derived['path']),current)
            self.assertEqual(B.Q.load(lineage['path'])['original_source_binding_reference'],original)
            self.assertEqual(B.establish(root,current,proof),(derived,lineage))
            self.assertEqual(before,{p:B.Q.reference(p)for p in before})
            for key in B.PRESERVED:
                changed=copy.deepcopy(current);changed[key]='different'
                with self.subTest(key=key),self.assertRaisesRegex(ValueError,'five non-backend'):
                    B.check_transition(previous,changed,proof)
            with self.assertRaisesRegex(ValueError,'old206'):
                B.check_transition(previous,current,{**proof,'previous_backend_adoption_reference':ref('other-build')})
        with tempfile.TemporaryDirectory()as folder:
            root=Path(folder);(root/'closed_files_unbound.jsonl').write_text('unbound-score\n')
            with self.assertRaisesRegex(ValueError,'unbound old cache'):B.establish(root,current,proof)

    def test_native_step_C0_is_distinct_from_parent_C0_and_worker_API_unchanged(self):
        from . import authority,workers
        from ..exact_nn_popcount_production_v1 import workers as old_workers
        with tempfile.TemporaryDirectory()as folder:
            root=Path(folder);header='JobIDRaw|UID|State|ExitCode|AllocCPUS\n'
            main=root/'main.txt';main.write_text(header+'4525827|1278|COMPLETED|0:0|16\n4525827.batch||COMPLETED|0:0|16\n')
            alpha=root/'alpha.txt';alpha.write_text(header+'1885213|1264|RUNNING|0:0|32\n1885213.0||COMPLETED|0:0|16\n')
            authority.native_completion(B.Q.reference(main),B.Q.reference(alpha))
            alpha.write_text(header+'1885213|1264|RUNNING|0:0|32\n1885213.0||RUNNING|0:0|16\n')
            with self.assertRaisesRegex(ValueError,'step C0'):
                authority.native_completion(B.Q.reference(main),B.Q.reference(alpha))
        class Reference:
            def nearest(self,raw):
                return dict(score=1/10,reference_ordinal=2,score_numerator=11,score_denominator=110,
                    evaluated_references=4,strictly_bound_pruned_references=2,reference_molecules=6,searched_popcount_groups=[11,110])
        rows=[('identity',bytes(256))]
        self.assertEqual(workers.fixed_result(Reference(),rows),old_workers.fixed_result(Reference(),rows))
        self.assertNotIn('searched_popcount_groups',workers.fixed_result(Reference(),rows)[0][2])

if __name__=='__main__':unittest.main()