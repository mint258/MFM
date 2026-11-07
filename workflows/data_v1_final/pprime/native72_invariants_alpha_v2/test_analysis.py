"""Four derived mathematical/identity boundaries; no retained data or programs."""
import unittest
from . import analysis as A


class InvariantBoundaries(unittest.TestCase):
    def test_exact_proper_rotation_preserves_norm_and_gram(self):
        r=[[0.,-1.,0.],[1.,0.,0.],[0.,0.,1.]]
        x=A.matrix([[1.,2.,3.],[0.,1.,1.]],'xtb_gradient_Eh_bohr')
        y=A.matrix([[-2.,1.,3.],[-1.,0.,1.]],'xtb_gradient_Eh_bohr')
        v=A.pair_metrics(x,y,r)
        self.assertEqual(v['max_abs_declared_R_residual_exact'],'0')
        self.assertEqual(v['gram_max_abs_difference_exact'],'0')
        self.assertTrue(v['recorded_gram_exactly_equal']);self.assertFalse(v['any_new_scientific_tolerance_or_PASS'])

    def test_equal_row_norms_do_not_certify_common_frame(self):
        x=A.matrix([[1.,0.,0.],[0.,1.,0.]],'xtb_gradient_Eh_bohr')
        y=A.matrix([[1.,0.,0.],[1.,0.,0.]],'xtb_gradient_Eh_bohr')
        v=A.pair_metrics(x,y,[[1.,0.,0.],[0.,1.,0.],[0.,0.,1.]])
        self.assertEqual(v['max_abs_row_squared_norm_difference_exact'],'0')
        self.assertEqual(v['sum_squared_norm_difference_exact'],'0')
        self.assertEqual(v['gram_max_abs_difference_exact'],'1')
        self.assertFalse(v['recorded_gram_exactly_equal'])

    def test_nonfinite_oversize_and_wrong_vector_shape_are_rejected(self):
        for value,field in (([[1.,2.]],'xtb_gradient_Eh_bohr'),([float('nan'),0.,1.],'xtb_dipole_Debye'),
                ([[0.,0.,0.]]*81,'pm7_gradient_kcal_mol_A')):
            with self.assertRaises(ValueError):A.matrix(value,field)

    def test_native_index_and_parser_float_identity_are_required(self):
        tokens=['1.250D+02','-2.5','0.00']
        endpoint={'status':'EXACT_NATIVE_VALUES_AND_UNITS_VERIFIED',
            'native_selection':{'status':'UNIQUE_NATIVE_TOKEN_SELECTION','factor_from_frozen_parser':1.},
            'native_token_details':[{'token':t,'selected_token_index':i,'frozen_parser_conversion_factor_hex':float(1.).hex(),
                'parsed_value_field_units':float(t.replace('D','E'))} for i,t in enumerate(tokens)]}
        self.assertEqual(A.native_values(endpoint,'pm7_dipole_Debye')['native'][0][0],125)
        endpoint['native_token_details'][1]['selected_token_index']=0
        with self.assertRaisesRegex(ValueError,'TOKEN_INDEX'):A.native_values(endpoint,'pm7_dipole_Debye')
        endpoint['native_token_details'][1]['selected_token_index']=1
        endpoint['native_token_details'][1]['parsed_value_field_units']=-2.
        with self.assertRaisesRegex(ValueError,'BINARY64_BINDING'):A.native_values(endpoint,'pm7_dipole_Debye')
