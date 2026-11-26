"""New final-report adapter: reuse closed frozen comparisons, never rescore."""
from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch
from test_e1_reporting_20261126 import cell
from e1_reporting_20261126 import KS,AUTHORITY,apply_s_verdict,decide,original_p_algebra


class CachedComponents(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.algebra=original_p_algebra(Path(__file__).resolve().parents[3]/'MFM_p_recipe')

    def fixture(self):
        cells={k:cell(k) for k in KS}
        closed={k:{name:apply_s_verdict(self.algebra.compare_frozen(cells[k]['frozen'],
            cells[10]['frozen'],name)) for name in ('R1','R3')} for k in KS}
        for value in cells.values():
            value['frozen_means']={name:value['frozen'][name]['mean_normalized_improvement'] for name in ('R1','R3')}
            value.pop('frozen')
        return cells,closed

    def test_final_choice_needs_no_frozen_raw_draw_arrays(self):
        cells,closed=self.fixture()
        with patch.object(self.algebra,'compare_frozen',side_effect=AssertionError('Closed component must be reused')):
            result=decide(dict(ready=True,authority=AUTHORITY),cells,self.algebra,
                closed_frozen_comparisons=closed)
        self.assertEqual(result['k_star'],1)
        self.assertTrue(result['frozen_components_reused_from_delivery'])
        self.assertEqual(result['new_bootstrap_draws'],0)

    def test_wrong_delivered_point_mean_is_rejected(self):
        cells,closed=self.fixture()
        cells=deepcopy(cells)
        cells[1]['frozen_means']['R3']+=.1
        with self.assertRaises(ValueError):
            decide(dict(ready=True,authority=AUTHORITY),cells,self.algebra,
                closed_frozen_comparisons=closed)
