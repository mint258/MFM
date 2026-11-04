"""Metadata boundary fixtures; mocked admission/runner are not actual job proof."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
from ..alpha_runtime_v1 import common as Q
from . import alpha_full_pool_entry as E


class FullPoolEntryBoundary(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.plan_path = self.root / 'plan.json'; self.proof_path = self.root / 'startup.json'
        self.guarded = self.root / 'guarded_entry.py'; self.guarded.write_text('# metadata fixture only\n')
        self.query_path = self.root / 'query.json'
        self.query = dict(schema='EXPANSION_TYPED_DECONTAMINATED_QUERY_PROJECTION_V1',
            status='COMPLETE', projection=dict(rows=10000001, path='/not-read-fixture-only.jsonl'))
        Q.write(self.query_path, self.query)
        refs = [Q.reference(p) for p in (E.__file__, E.scientific.__file__, self.guarded)]
        self.argv = [sys.executable, '-I', '-B', str(self.guarded), E.MODULE,
            '--plan', str(self.plan_path), '--startup-proof', str(self.proof_path)]
        self.plan = dict(schema='PUBCHEM_EXACT_CACHED_NN_PLAN_V1', endpoint=Q.ENDPOINT, uid=1264,
            scope_key='fixture_full_pool', execution_argv=self.argv, code_references=refs,
            query_manifest=Q.reference(self.query_path))
        self.native = dict(uid=1264, endpoint=Q.ENDPOINT, job_id='fixture-job', boot_id='fixture-boot')
        self.actual = dict(uid=1264, endpoint=Q.ENDPOINT, job_id='fixture-job')
        self.proof = dict(uid=1264, endpoint=Q.ENDPOINT, job_id='fixture-job', boot_id='fixture-boot',
            request=dict(scope_key=self.plan['scope_key'], source_references=refs,
                execution_argv=self.argv))

    def write(self, plan=None, proof=None):
        plan = copy.deepcopy(self.plan if plan is None else plan)
        proof = copy.deepcopy(self.proof if proof is None else proof)
        Q.write(self.plan_path, plan, replace=True)
        proof['request'].setdefault('producer_plan_reference', Q.reference(self.plan_path))
        Q.write(self.proof_path, proof, replace=True)

    def execute(self, expected=True):
        result = object(); runner = Mock(return_value=result)
        with patch.object(E.profile, 'admit', return_value=self.actual) as admit, \
             patch.object(E, 'identity', return_value=self.native), \
             patch.object(E.scientific, 'run', runner), \
             patch.object(sys, 'argv', [E.__file__, *self.argv[5:]]):
            if expected:
                self.assertIs(E.execute(self.plan_path, self.proof_path), result)
                runner.assert_called_once_with(self.plan_path)
                admit.assert_called_once_with(Q.load(self.plan_path), minimum_workers=16)
            else:
                with self.assertRaises((ValueError, KeyError)):
                    E.execute(self.plan_path, self.proof_path)
                runner.assert_not_called()

    def test_exact_launcher_dispatches_original_runner_once_without_projection_read(self):
        self.write(); self.execute()

    def test_wrong_native_proof_and_original_source_pin_rejected_before_dispatch(self):
        changes = [lambda p: p.update(uid=1278), lambda p: p.update(endpoint='Main-fixture'),
            lambda p: p.update(job_id='wrong-job'), lambda p: p.update(boot_id='wrong-boot'),
            lambda p: p['request'].update(scope_key='wrong-scope'),
            lambda p: p['request'].update(producer_plan_reference=dict(path=str(self.plan_path), bytes=1, sha256='0'*64)),
            lambda p: p['request'].update(execution_argv=['wrong-command']),
            lambda p: p['request'].update(source_references=[Q.reference(E.__file__), Q.reference(self.guarded)]),
            lambda p: p['request'].update(source_references=[Q.reference(E.scientific.__file__), Q.reference(self.guarded)])]
        for index, change in enumerate(changes):
            with self.subTest(index=index):
                proof = copy.deepcopy(self.proof); change(proof)
                self.write(proof=proof); self.execute(expected=False)

    def test_partial_cost_manifest_schema_and_consistent_wrong_module_rejected(self):
        for value in (1, 10000001, None):
            with self.subTest(max_queries=value):
                plan = copy.deepcopy(self.plan); plan['max_queries'] = value
                self.write(plan=plan); self.execute(expected=False)
        for schema, status, count in [('expansion_exact_query_cost_pilot_v1', 'COMPLETE', 64),
                (self.query['schema'], 'PENDING', 10000001), (self.query['schema'], 'COMPLETE', True)]:
            with self.subTest(schema=schema, status=status, rows=count):
                Q.write(self.query_path, dict(schema=schema, status=status, projection=dict(rows=count)), replace=True)
                plan = copy.deepcopy(self.plan); plan['query_manifest'] = Q.reference(self.query_path)
                self.write(plan=plan); self.execute(expected=False)
        plan = copy.deepcopy(self.plan); proof = copy.deepcopy(self.proof)
        plan['execution_argv'][4] = 'workflows.expansion.exact_nn_cached_v1.run'
        proof['request']['execution_argv'] = plan['execution_argv']
        self.write(plan=plan, proof=proof); self.execute(expected=False)


if __name__ == '__main__':
    unittest.main()
