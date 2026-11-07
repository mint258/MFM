"""One scheduling/reference fixture, without census, native accounting or science."""
from pathlib import Path
import tempfile
import unittest
from . import report_pipeline as P


class Scheduling(unittest.TestCase):
    def test_exact_scientific_receipt_private_remaining_budget_and_dispatch(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sample = P.Q.write(root / 'fixed183.json', {'fixture': 'same fixed sample'})
            reference = P.Q.write(root / 'full196.json', {'fixture': 'same complete reference'})
            plan = P.Q.write(root / 'plan.json', {'baseline_receipt':sample,'reference_manifest':reference})
            startup = P.Q.write(root / 'startup.json', {'fixture': 'closed startup'})
            meta = dict(output_directory=str(root), plan_reference=plan, startup_proof_reference=startup)
            # A malformed non-SQL file proves this selector has no SQLite dependency.
            (root / 'queries.sqlite').write_bytes(b'NOT_A_SQLITE_DATABASE')
            valid = dict(schema='EXPANSION_EXACT_SCIENTIFIC_COVERAGE_V1', status='COMPLETE',
                producer_schema='CLOSED_FP_REUSE_PLUS_INVERTED_MISSING_FIXED1M_V1',
                reference_role='before', resource_plan=plan, launcher_startup_proof_reference=startup,
                queries=1000000, projection={'rows':1000000}, nearest_similarity_exact=True,
                baseline_receipt=sample, reference_manifest=reference, decontamination_applied_to_sample=False,
                candidate_pool_release_authorized=False)
            P.Q.write(root / 'attempt_cost.receipt.json', dict(valid, schema='COST_PROFILE', queries=64))
            actual = P.Q.write(root / 'attempt0.receipt.json', valid)
            self.assertEqual(P.before_receipt(meta), actual)
            P.Q.write(root / 'attempt1.receipt.json', valid)
            with self.assertRaisesRegex(ValueError, 'Exactly one'): P.before_receipt(meta)
            self.assertEqual((root / 'queries.sqlite').read_bytes(), b'NOT_A_SQLITE_DATABASE')
            inline = dict(scope_total_caps_bytes={'reports':5000000000},
                remaining_reserved_bytes_by_scope={'reports':3000000000},
                other_future_reserved_bytes_for_each_scope={'reports':100})
            self.assertEqual(P.partition({}, 'baseline-report', inline), (1500000000,1500000100))
            self.assertEqual(P.partition({}, 'rn-populations', inline), (1500000000,1500000100))
            self.assertEqual(P.partition({'private_caps_bytes':{'batch-graph-report':4000000000}},
                'batch-graph-report', inline), (3000000000,100))
            with self.assertRaises(ValueError): P.partition({'private_caps_bytes':{'baseline-report':4000000000}}, 'baseline-report', inline)
            for phase in P.PHASES:
                argv = P.launch_argv('/real/template.json', phase, '/immutable/entry.py', phase, root)
                module = argv[argv.index('--module') + 1]
                self.assertEqual(module.rsplit('.',1)[-1], 'rn_populations' if phase == 'rn-populations' else 'report')
                self.assertEqual(argv[argv.index('--template')+1], '/real/template.json')
                self.assertNotIn('sbatch', argv)


if __name__ == '__main__': unittest.main()
