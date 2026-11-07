"""Three meaningful boundaries before any original Budget thread starts."""
import unittest
from . import contracts as A

class Boundaries(unittest.TestCase):
    def test_main_guard_inverse_and_original_science_runtime_objects(self):
        self.assertTrue(A.source_inverse_proof()['science_runtime_objects_direct'])
    def test_all_new_fixture_cleanup_precedes_Budget_and_failure_blocks_Budget(self):
        events=[]
        def extra():events.extend(('v2new3','v3new3','cleanup_complete'));return 'all6'
        A.startup_phase(lambda:events.append('old5'),extra,lambda:events.append('Budget'))
        self.assertEqual(events,['old5','v2new3','v3new3','cleanup_complete','Budget']);events.clear()
        def fail():events.append('v3_fixture_failed');raise ValueError('PURE_FAILURE')
        with self.assertRaises(ValueError):A.startup_phase(lambda:events.append('old5'),fail,lambda:events.append('Budget'))
        self.assertEqual(events,['old5','v3_fixture_failed'])
    def test_wrong_range_and_wrong_honest_phase_are_not_51_aliases(self):
        with self.assertRaises(ValueError):A.phase({'mode':'full_shard','resource_phase':'FULL_SHARD'})
        plan={'mode':'full_shard','resource_phase':'CONTINUATION52_499','first_part':52,'last_part':52,'first_ordinal':13000001,'last_ordinal':13250000}
        p=A.parameters(plan);self.assertEqual(p['first_part'],52);self.assertEqual(p['first_ordinal'],13000001)
        self.assertTrue(p['all11_before_Budget']);self.assertEqual(p['extra_pure_fixture_methods'],6)
