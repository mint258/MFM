"""Three synthetic parser/orbit/JSON-selection boundaries before actual DATA."""
import importlib,unittest
from . import geometry as G,json_selection as J


def xyz(points):return (str(len(points))+'\nsynthetic\n'+''.join('C '+' '.join(format(float(v),'.12f') for v in row)+'\n' for row in points)).encode()
def parsed(points):return G.coordinates({'input.xyz':xyz(points)},['C']*len(points))


class Boundaries(unittest.TestCase):
    def test_actual_T_arrays_and_exact_P90_native_tokens(self):
        from workflows.data_v1_final.pprime.causal15_main_v1 import render as T,contract as C
        points=[[.3,.6,.9],[1.2,-.6,-0.0],[-.9,.3,-.6]];original=xyz(points);rotated=T.p90(original,'input.xyz')
        a=G.coordinates({'input.xyz':original},['C']*3);b=G.coordinates({'input.xyz':rotated},['C']*3);r=G.compare(a,b,C.P90)
        self.assertEqual(r['coordinate_components_outside_native_token_bound'],0)
        self.assertEqual(r['worst_coordinate']['absolute_exact_residual_A']['numerator'],'0')
        self.assertEqual(r['centered_Gram']['outside_propagated_native_token_bound'],0)
        self.assertEqual(r['pair_distances']['nonoverlapping_distance_token_intervals'],0)
        self.assertEqual(a['tokens'][0],['0.300000000000','0.600000000000','0.900000000000'])
        self.assertEqual(a['tokens'][1][2],'-0.000000000000')
    def test_general_R_rounding_and_different_geometry_are_distinguished(self):
        from math_v1 import ROTATION
        from fractions import Fraction as F
        a=parsed([[.3,.6,.9],[1.2,-.6,.3],[-.9,.3,-.6]])
        transformed=G.transform(a['values'],[[G.fp(v) for v in row] for row in ROTATION]);b=parsed(transformed)
        same=G.compare(a,b,ROTATION);self.assertEqual(same['coordinate_components_outside_native_token_bound'],0)
        self.assertEqual(same['pair_distances']['outside_squared_distance_token_bound'],0)
        transformed[0][0]+=F(1,100);changed=G.compare(a,parsed(transformed),ROTATION)
        self.assertGreater(changed['coordinate_components_outside_native_token_bound'],0)
        self.assertGreater(changed['centered_Gram']['outside_propagated_native_token_bound'],0)
        self.assertGreater(changed['pair_distances']['nonoverlapping_distance_token_intervals'],0)
    def test_original_JSON_regex_scope_and_last_duplicate_selection_observed(self):
        parser=importlib.import_module('read_outputs_v1')
        text='{"nested":{"dipole / a.u.":[1.0,2.0,3.0]},"dipole / a.u.":[7.0,8.0,9.0],"dipole / a.u.":[4.0,5.0,6.0]}'
        result=J.observe(text,parser)
        self.assertEqual(result['target_key_assignments_all_scopes'],3);self.assertEqual(result['top_level_target_key_assignments'],2)
        self.assertEqual(result['JSON_duplicate_key_extra_assignments_all_scopes'],1)
        self.assertEqual(result['first_regex_number_tokens'],['1.0','2.0','3.0']);self.assertEqual(result['json_default_top_level_last_assignment_tokens'],['4.0','5.0','6.0'])
        self.assertFalse(result['regex_first_and_top_last_binary64_equal']);self.assertTrue(result['original_parser_equal_first_regex_binary64'])
        normal=J.observe('{"dipole / a.u.":[1.1,2.2,3.3]}',parser);self.assertTrue(normal['regex_first_and_top_last_exact_tokens_equal'])
