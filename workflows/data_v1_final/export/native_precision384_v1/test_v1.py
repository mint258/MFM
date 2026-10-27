"""Three synthetic lexical/arithmetic/absence boundaries; no native or DATA IO."""
import hashlib,unittest
from . import precision as P


class Boundaries(unittest.TestCase):
    def test_conditional_printing_and_exact_binary64_decomposition(self):
        value,quantum=P.decimal_token('1.230D-2')
        self.assertEqual(value,P.F(123,10000));self.assertEqual(quantum,P.F(1,100000))
        factor=0.529177210903
        observed=P.conditional_residual('0.100000000000','0.2000000000000000','0.529177210903',factor,0.1,0.2*factor)
        def f(key):return P.F(int(observed[key]['numerator']),int(observed[key]['denominator']))
        self.assertEqual(f('binary64_direct_difference_exact_rational'),P.F.from_float(0.2*factor)-P.F.from_float(0.1))
        self.assertEqual(f('binary64_direct_difference_exact_rational')+f('binary64_subtraction_round_error'),P.F.from_float(0.2*factor-0.1))
        self.assertLess(f('conditional_nearest_printing_lower'),f('conditional_nearest_printing_upper'))
        self.assertFalse(observed['conditional_interval_contains_zero']);self.assertFalse(observed['physical_or_QC_pass'])
        self.assertNotEqual(f('conversion_factor_binary64_representation_error'),0)
        signed=P.conditional_residual('-0.000000000000','-0.000','1',1.0,-0.0,-0.0)
        self.assertEqual(signed['native_parse_float64_hex'],'-0x0.0p+0')
        self.assertEqual(signed['input_float64_hex'],'-0x0.0p+0');self.assertTrue(signed['conditional_interval_contains_zero'])
        for bad in ('NaN','1e1001','1.0 broken'):
            with self.assertRaises(ValueError):P.decimal_token(bad)

    def test_six_components_decimal_trace_preserved_and_bound_conditional(self):
        def tokens(zz):return [{'component':k,'native_numeric_token':v} for k,v in zip(P.ORDER,('1.000','2.345','2.000','-2.345','0.111',zz))]
        nonzero=tokens('-2.999');before=[dict(r) for r in nonzero];q=P.trace(nonzero)
        self.assertEqual(q['native_decimal_trace'],P.rational(P.F(1,1000)))
        self.assertFalse(q['exactly_zero']);self.assertTrue(q['within_conditional_f12_3_trace_envelope'])
        self.assertEqual(nonzero,before);self.assertFalse(q['trace_projected_or_original_values_modified']);self.assertFalse(q['QC_authorized'])
        self.assertTrue(P.trace(tokens('-3.000'))['exactly_zero'])
        self.assertFalse(P.trace(tokens('-2.998'))['within_conditional_f12_3_trace_envelope'])
        self.assertIsNone(P.trace(tokens('-2.999D+0'))['within_conditional_f12_3_trace_envelope'])
        bad=tokens('-3.000');bad[1],bad[2]=bad[2],bad[1]
        with self.assertRaises(ValueError):P.trace(bad)

    def test_exact_coordinate_grammar_and_missing_call_context_remains_unknown(self):
        symbols=['H','C'];xyz=b'2\nopaque comment\nH -0.000000000000 1.000000000000 2.000000000000\nC 3.000000000000 4.000000000000 5.000000000000\n'
        mop=b'PM7 THREADS=1\ntitle\n\nH -0.000000000000 1 1.000000000000 1 2.000000000000 1\nC 3.000000000000 1 4.000000000000 1 5.000000000000 1\n'
        self.assertEqual(P.input_tokens(xyz,'input.xyz',symbols),P.input_tokens(mop,'input.mop',symbols))
        with self.assertRaises(ValueError):P.input_tokens(xyz,'input.xyz',list(reversed(symbols)))
        aux='ATOM_EL[2]= H C\nATOM_X_OPT:ANGSTROMS[6]= -0.000 1.000 2.000\n3.000 4.000 5.000\nDIP_VEC:DEBYE[3]= 0.0 0.0 0.0\n'
        self.assertEqual(P.aux_tokens(aux,2)[0],['-0.000','1.000','2.000'])
        self.assertIsNone(P.aux_tokens('TOTAL_ENERGY= -1.0\n',2))
        with self.assertRaises(ValueError):P.aux_tokens(aux+aux,2)
        grad='$grad\n-0.0 1.0 2.0 h\n3.0 4.0 5.0 c\n0.0 0.0 0.0\n0.0 0.0 0.0\n$end\n'
        self.assertEqual(P.gradient_tokens(grad,symbols)[1],['3.0','4.0','5.0'])
        with self.assertRaises(ValueError):P.gradient_tokens(grad+grad,symbols)
        body=b'$write\n json=true\n$end\n'
        observed=P.controls({'keywords':['--gfn','2'],'command_line':'xtb input.xyz --gfn 2'},[{'name':'native.inp','sha256':hashlib.sha256(body).hexdigest(),'data':body}],[])
        self.assertEqual(observed['retained_full_process_argv_candidates'],[])
        self.assertEqual(len(observed['retained_control_members']),1)
        self.assertTrue(observed['recipe_keywords_are_not_full_executed_argv'])
        self.assertEqual(len(observed['retained_opaque_command_fields']),1)
        self.assertFalse(observed['retained_opaque_command_fields'][0]['split_or_interpreted_as_argv'])
        self.assertEqual(observed['global_or_unretained_rc_absence'],'UNKNOWN_NOT_PROVED_BY_BUNDLE_OMISSION')
        self.assertFalse(observed['current_HOME_rc_or_environment_read'])


if __name__=='__main__':unittest.main()
