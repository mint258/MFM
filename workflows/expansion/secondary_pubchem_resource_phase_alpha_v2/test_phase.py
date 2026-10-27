"""Three pure resource seam boundaries; no scientific bodies or processes."""
import unittest
from . import phase as A

class Boundaries(unittest.TestCase):
    def test_source_inverse_AST_and_original_science_runtime_objects(self):
        from .inverse import proof
        self.assertEqual(proof()['status'],'EXACT_RESOURCE_PHASE_MAIN_INVERSE_AST_AND_BYTES')
    def test_all_fixtures_finish_before_Budget_and_failed_fixture_blocks_budget(self):
        events=[]
        def step(name):
            def call():events.append(name);return name
            return call
        self.assertEqual(A.startup_phase(step('old5'),step('new3'),step('Budget')),('old5','new3','Budget'))
        self.assertEqual(events,['old5','new3','Budget']);events.clear()
        def fail():events.append('fixture_fail');raise ValueError('SYNTHETIC_FIXTURE_FAILURE')
        with self.assertRaisesRegex(ValueError,'SYNTHETIC_FIXTURE_FAILURE'):A.startup_phase(fail,step('new3'),step('Budget'))
        self.assertEqual(events,['fixture_fail'])
    def test_Budget_constructor_failure_has_zero_sourceproof_DATA_pool_once_calls(self):
        events=[]
        def budget():events.append('Budget');raise FileNotFoundError(2,'SYNTHETIC_OBSERVATION_FAILURE','/synthetic-only')
        def proof():events.append('sourceproof');return None
        with self.assertRaises(FileNotFoundError):
            A.startup_phase(lambda:events.append('old5'),lambda:events.append('new3'),budget);proof()
        self.assertEqual(events,['old5','new3','Budget']);self.assertNotIn('sourceproof',events)
