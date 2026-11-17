"""Registered threshold boundaries; no scores or training are generated here."""
import unittest
from t_decide import single,both
class DecisionTests(unittest.TestCase):
    def test_single_seed_boundaries_and_sign(self):
        self.assertEqual(single(dict(delta=.06,ci95=[.001,.1])),'win')
        self.assertEqual(single(dict(delta=.059,ci95=[.001,.1])),'seed1_required')
        self.assertEqual(single(dict(delta=-.06,ci95=[-.1,-.001])),'loss')
        self.assertEqual(single(dict(delta=.07,ci95=[0,.1])),'seed1_required')
    def test_two_seed_effect_and_paired_direction(self):
        z=dict(delta=.04,ci95=[.01,.07],reference=.475)
        o=dict(delta=.04,ci95=[.01,.07],reference=.475)
        self.assertEqual(both(z,o),'win')
        o=dict(delta=.03,ci95=[.01,.05],reference=.475)
        self.assertEqual(both(z,o),'tie')
        z=dict(delta=-.01,ci95=[-.02,-.001],reference=.475)
        o=dict(delta=-.01,ci95=[-.02,-.001],reference=.475)
        self.assertEqual(both(z,o),'loss')
if __name__=='__main__':unittest.main()
