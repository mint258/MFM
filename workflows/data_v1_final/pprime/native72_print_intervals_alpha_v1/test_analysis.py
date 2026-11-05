"""Three exact interval hypotheses; no data or method/tolerance changes."""
import unittest
from fractions import Fraction as F
from . import analysis as A
class IntervalBoundaries(unittest.TestCase):
    def test_signed_zero_crossing_D_E_halfstep_and_exact_square(self):
        value,step,half=A.P.token_interval('-0.00D+00');self.assertEqual(F(half),F(1,200))
        self.assertEqual(A.interval_square((-F(1,200),F(1,200))),(F(),F(1,40000)))
        self.assertEqual(A.interval_multiply((-F(2),F(1)),(-F(3),F(4))),(-F(8),F(6)))
        self.assertTrue(A.intersects((F(),F(1)),(F(1),F(2))))
        self.assertEqual(A.P.token_interval('1.250E+02')[2],A.P.token_interval('1.250D+02')[2])
    def test_proper_rotation_can_overlap_but_cannot_create_scientific_PASS(self):
        w=F(1,1000000)
        box=lambda rows:[[(F(x)-w,F(x)+w) for x in row] for row in rows]
        result=A.compare_intervals(box([[1,2,3],[0,1,1]]),box([[-2,1,3],[-1,0,1]]))
        self.assertFalse(result['rotation_only_plus_native_print_rounding_hypothesis_excluded'])
        self.assertFalse(result['scientific_PASS']);self.assertFalse(result['interval_overlap_proves_common_frame'])
    def test_equal_norms_can_have_disjoint_Gram_and_wrong_unit_arm_stays_unfitted(self):
        point=lambda rows:[[(F(x),F(x)) for x in row] for row in rows]
        result=A.compare_intervals(point([[1,0,0],[0,1,0]]),point([[1,0,0],[1,0,0]]))
        self.assertEqual(result['disjoint_row_norm_intervals'],0);self.assertEqual(result['disjoint_Gram_entries'],2)
        self.assertTrue(result['rotation_only_plus_native_print_rounding_hypothesis_excluded']);self.assertFalse(result['fitted_axes_scale_or_permutation'])
        scaled=A.compare_intervals(point([[1,0,0]]),point([[2,0,0]]))
        self.assertTrue(scaled['total_squared_norm_intervals_disjoint']);self.assertFalse(scaled['physical_or_SCF_cause_proven'])
