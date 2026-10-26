"""Four synthetic checks only; no retained science, QM or network calls."""
import json,pathlib,unittest
from decimal import Decimal
from precision import token_interval,propagate_native,geometry_orbit,exact_decimal
from fractions import Fraction
from tokens import json_dipole_entries
FLOAT=r'[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[EeDd][-+]?\d+)?'


class NativePrecisionFixtures(unittest.TestCase):
    def test_scientific_E_D_halfstep_and_unique_native_token_selection(self):
        self.assertEqual(token_interval('1.230D+02'),(Decimal('123.0'),Decimal('.1'),Decimal('.05')))
        self.assertEqual(token_interval('-2.500e-03'),(Decimal('-.002500'),Decimal('.000001'),Decimal('.0000005')))
        self.assertEqual(token_interval('0.000'),(Decimal('0.000'),Decimal('.001'),Decimal('.0005')))
        text='{"dipole / a.u.": [1.230e2, -2.500e-3, 0.000]}'
        self.assertEqual([row['token'] for row in json_dipole_entries(text,FLOAT)],['1.230e2','-2.500e-3','0.000'])
        with self.assertRaisesRegex(ValueError,'DUPLICATE_JSON_KEY'):
            json_dipole_entries('{"dipole / a.u.":[1,2,3],"dipole / a.u.":[1,2,3]}',FLOAT)
    def test_large_component_quantization_propagates_into_small_rotated_component(self):
        rotation=[[.6,-.8,0.],[.8,.6,0.],[0.,0.,1.]]
        base=[{'token':value} for value in ('1000.000','750.000','0.000')]
        variant=[{'token':value} for value in ('0.001','1250.000','0.000')]
        result=propagate_native(base,variant,1.,rotation,[1000.,750.,0.],[.001,1250.,0.])
        self.assertGreater(Decimal(result[0]['native_print_propagation_bound']),Decimal('.001'))
        self.assertTrue(result[0]['native_centers_within_print_bound'])
        self.assertTrue(result[0]['parser_float_centers_within_print_bound'])
        self.assertNotIn('atol',result[0]);self.assertNotIn('rtol',result[0])
    def test_reperturbed_lab_geometry_is_not_same_orbit_and_P_must_be_explicit(self):
        import numpy as np
        rotation=np.asarray([[0.,-1.,0.],[1.,0.,0.],[0.,0.,1.]])
        clean=np.asarray([[0.,0.,0.],[1.,0.,0.]]);noise=np.asarray([[.1,.2,.3],[-.1,.1,.2]])
        base=clean+noise;rotated=base@rotation.T;lab=clean@rotation.T+noise
        self.assertTrue(geometry_orbit(base,rotated,rotation)['same_geometry_orbit_within_predeclared_coordinate_atol'])
        self.assertFalse(geometry_orbit(base,lab,rotation)['same_geometry_orbit_within_predeclared_coordinate_atol'])
        permuted=rotated[[1,0]]
        self.assertFalse(geometry_orbit(base,permuted,rotation)['same_geometry_orbit_within_predeclared_coordinate_atol'])
        self.assertTrue(geometry_orbit(base,permuted,rotation,permutation_variant_to_base=[1,0])['same_geometry_orbit_within_predeclared_coordinate_atol'])
    def test_fraction_large_exponent_cancellation_and_small_component_boundary(self):
        # More than 100 significant digits are required before cancellation.
        # Both frozen parser floats coincide; original decimal centers do not.
        c=2.**-.5;rotation=[[c,-c,0.],[c,c,0.],[0.,0.,1.]]
        left='1.'+'0'*109+'2E+250';right='1.'+'0'*110+'E+250'
        base=[{'token':value} for value in (left,right,'0.000')]
        variant=[{'token':value} for value in ('0.000','1.414213562373095E+250','0.000')]
        first=propagate_native(base,variant,1.,rotation,
            [float(Decimal(left)),float(Decimal(right)),0.],[0.,1.414213562373095e250,0.])[0]
        expected=Fraction.from_float(c)*2*10**140
        self.assertEqual(Fraction(Decimal(first['residual_exact_native_token_centers'])),expected)
        self.assertEqual(Fraction(Decimal(exact_decimal(expected))),expected)
        self.assertFalse(first['native_centers_within_print_bound'])
        self.assertTrue(first['parser_float_centers_within_print_bound'])
        # A small rotated component is just inside/outside an exact .0505
        # hypothesis bound. No atol/rtol or an ambient Decimal context decides it.
        rotation=[[0.,-1.,0.],[1.,0.,0.],[0.,0.,1.]]
        base=[{'token':value} for value in ('0.0','0.000','0.000')]
        for token,inside in (('0.050',True),('0.051',False)):
            with self.subTest(small_component_token=token):
                variant=[{'token':value} for value in ('0.000',token,'0.000')]
                row=propagate_native(base,variant,1.,rotation,[0.,0.,0.],[0.,float(token),0.])[1]
                self.assertEqual(Fraction(Decimal(row['native_print_propagation_bound'])),Fraction(101,2000))
                self.assertEqual(row['native_centers_within_print_bound'],inside)
                self.assertEqual(row['parser_float_centers_within_print_bound'],inside)
if __name__=='__main__':unittest.main()
