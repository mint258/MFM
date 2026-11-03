"""Counted-table transformations; no chemistry, database or production bodies."""
import unittest
from .population_figures_v1 import display_bounds, scaffold_ranks


class CountedFigureTransformTests(unittest.TestCase):
    def test_original_bin_quantiles_include_underflow_and_overflow_without_rebinning(self):
        # Four finite edges, two ordinary bins plus terminal finite bin.
        # Nonzero outside tails intentionally push both display bounds outward.
        hist = [dict(right=edge, count=n) for edge, n in zip((0, 1, 2, 4, float('inf')), (6, 200, 588, 200, 6))]
        self.assertEqual(display_bounds(hist), (0, 4))
        # Original algorithm uses the right edge of the .995 crossing bin;
        # selecting observed values or interpolating quantiles would change it.
        hist = [dict(right=edge, count=n) for edge, n in zip((0, 1, 2, 4, float('inf')), (0, 4, 992, 4, 0))]
        self.assertEqual(display_bounds(hist), (1, 2))
        self.assertEqual(sum(r['count'] for r in hist), 1000)

    def test_top_rank_curve_equals_full_scaffold_multiset_with_boundary_ties(self):
        spectrum = [dict(molecules_per_scaffold='1', number_of_scaffolds='19000'),
                    dict(molecules_per_scaffold='15', number_of_scaffolds='7'),
                    dict(molecules_per_scaffold='2', number_of_scaffolds='10003')]
        full = sorted([1] * 19000 + [15] * 7 + [2] * 10003, reverse=True)
        self.assertEqual(scaffold_ranks(spectrum), full[:10000])
        self.assertEqual(scaffold_ranks(spectrum, limit=8), [15] * 7 + [2])
        self.assertEqual(scaffold_ranks(spectrum, limit=40000), full)


if __name__ == '__main__':
    unittest.main()
