"""Undefined cosine regressions for denoise-only zero-weight tasks."""
import math,unittest
from profile_completed_d3_conditions_v3 import mean_defined_cosines
def rows(values):return [{'diagnostics':{'cosine_similarities':{'a/b':v}}} for v in values]
class OptionalCosineTests(unittest.TestCase):
    def test_all_defined_preserves_original_exact_average(self):
        values=[(-1)**i*i/20 for i in range(20)];means,counts=mean_defined_cosines(rows(values),{'a/b'})
        self.assertEqual(means['a/b'],math.fsum(values)/20);self.assertEqual(counts['a/b'],{'defined_batches':20,'total_batches':20})
    def test_A5_zero_weight_pair_preserves_undefined_and_zero_coverage(self):
        means,counts=mean_defined_cosines(rows([None]*20),{'a/b'})
        self.assertIsNone(means['a/b']);self.assertEqual(counts['a/b']['defined_batches'],0)
    def test_partial_definition_reports_actual_denominator(self):
        means,counts=mean_defined_cosines(rows([.5,-.5]+[None]*18),{'a/b'})
        self.assertEqual(means['a/b'],0.);self.assertEqual(counts['a/b']['defined_batches'],2)
    def test_real_zero_cosine_is_defined(self):
        means,counts=mean_defined_cosines(rows([0.]*20),{'a/b'})
        self.assertEqual(means['a/b'],0.);self.assertEqual(counts['a/b']['defined_batches'],20)
    def test_nonfinite_invalid_angle_or_incomplete_batch_set_rejected(self):
        for value in [math.nan,math.inf,-math.inf,1.01,'null']:
            with self.subTest(value=value),self.assertRaises(AssertionError):mean_defined_cosines(rows([value]+[0.]*19),{'a/b'})
        with self.assertRaises(AssertionError):mean_defined_cosines(rows([0.]*19),{'a/b'})
if __name__=='__main__':unittest.main()
