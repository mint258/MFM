"""Only new descriptive aggregate/retained-pair wrapper boundaries."""
from copy import deepcopy
import unittest
from fullft_contrasts_20261127 import TASKS,contrast,provider


def primary(point,seed_mean,ensemble):
    return dict(status='COMPLETE',rows=[dict(condition=point,task=task,seed_count=3,
        scratch_improvement_seed_mean=seed_mean,ensemble_scratch_improvement=ensemble) for task in TASKS],
        retained=dict(completed_draws=1000,identity=dict(groups={'dataset':['MID']},
            bootstrap_seed=20261025,samples=1000,input_identity=dict(scratch='same',random_reference='same')),
            draws={point+'/'+task:dict(scratch_improvement=[ensemble]*1000) for task in TASKS}))


class Contrasts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.original=provider()

    def test_pair_ci_is_not_attached_to_the_seed_mean_estimand(self):
        value=contrast(primary('a',.2,.5),primary('b',.1,.1),'a','b',self.original)
        result=value['aggregate']
        self.assertAlmostEqual(result['delta_seed_mean'],.1)
        self.assertAlmostEqual(result['delta_ensemble'],.4)
        self.assertEqual([result['ensemble_ci_lower'],result['ensemble_ci_upper']],[.4,.4])
        self.assertTrue(result['E1_decision_uses_separate_seed_mean_draws'])

    def test_original_provider_rejects_nonmatching_molecular_draws(self):
        baseline=primary('b',.1,.1)
        candidate=deepcopy(primary('a',.2,.5))
        candidate['retained']['identity']['groups']={'dataset':['OTHER_MID']}
        with self.assertRaises(ValueError):contrast(candidate,baseline,'a','b',self.original)
