"""One scheduling-only fixture: frozen sample, real dispatch and resource partition."""
from pathlib import Path
import tempfile
import unittest
from . import prepare_pipeline as P


class Scheduling(unittest.TestCase):
    def test_before_sample_preserved_and_after_native_dispatch_has_no_submitter(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            before_ref = P.Q.write(folder / 'reference196.json', {'fixture': 'closed196'})
            baseline_ref = P.Q.write(folder / 'baseline183.json', {'fixture': 'same1M'})
            adoption = P.Q.write(folder / 'adoption206.json', {'fixture': 'sameCPP'})
            resources = P.Q.write(folder / 'resources.json', dict(endpoint=P.Q.ENDPOINT, uid=P.Q.UID,
                minimum_free_bytes=200000000000, minimum_node_available_bytes=24 << 30))
            old = dict(schema='PUBCHEM_EXACT_SCIENTIFIC_COVERAGE_PLAN_V1', reference_role='before',
                reference_manifest=before_ref, baseline_receipt=baseline_ref, query_batch=128,
                output_directory=str(P.EXACT / 'corrected_fixed1M_exact_before_v1_job_1885201'),
                execution_argv=['old201', 'must not leak to new launcher'])
            old_ref = P.Q.write(folder / 'before_plan.json', old)
            deployment = P.Q.write(folder / 'deployment.json', {'code_references': [P.Q.reference(P.__file__)]})
            config = dict(resources_reference=resources, coverage_template_reference=old_ref,
                          deployment_reference=deployment, before_reference_manifest=before_ref,
                          backend_adoption_reference=adoption)
            pack = P.resource_plan(config, 'pack-after', 'after_pack')
            after = P.resource_plan(config, 'coverage-after', 'after_coverage')
            self.assertEqual(pack['base_reference_manifest'], before_ref)
            self.assertNotIn('input_manifest', pack)  # Only a real closed source can supply it.
            self.assertNotIn('reference_manifest', after)  # Only actual completed pack output supplies it.
            self.assertEqual(after['baseline_receipt'], baseline_ref)
            self.assertEqual(after['query_batch'], old['query_batch'])
            self.assertEqual(after['reference_role'], 'after')
            self.assertEqual(after['backend_adoption_reference'], adoption)
            self.assertEqual(P.Q.load(P.Q.verify(old_ref)), old)
            for plan in (pack, after):
                self.assertEqual((plan['workers'], plan['worker_rss_cap_bytes'], plan['parent_rss_cap_bytes'],
                    plan['software_rss_budget_bytes'], plan['output_cap_bytes'], plan['sqlite_cache_bytes']),
                    (16, 2 << 30, 8 << 30, 48 << 30, 4000000000, 256 << 20))
                self.assertIn(old['output_directory'], plan['background_scope_exclusions'])
                self.assertNotEqual(plan['output_scope_root'], str(P.EXACT))
                self.assertNotIn('execution_argv', plan)
            for phase, module in [('pack-after', 'workflows.expansion.exact_nn_cached_v1.pack_reference'),
                    ('coverage-after', 'workflows.expansion.expansion_coverage_followup_v1.coverage')]:
                argv = P.launch_argv('/closed/input_plan.json', phase, '/immutable/layer_entry.py', phase, folder)
                self.assertEqual(argv[argv.index('--module') + 1], module)
                self.assertEqual(argv[argv.index('--template') + 1], '/closed/input_plan.json')
                self.assertNotIn('sbatch', argv)
            self.assertEqual(P.ACCOUNT, ['ssh','-n','-o','BatchMode=yes','-o','ConnectTimeout=5','218.192.171.238','sacct'])
            with self.assertRaises(ValueError): P.literal('217', '../wrong_source')


if __name__ == '__main__': unittest.main()
