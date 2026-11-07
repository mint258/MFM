"""Three synthetic methods only; no original DATA, monitor, key generation or QM."""
import unittest
from . import contracts as C,projection as P


class Boundaries(unittest.TestCase):
    Chem=None;functions=None

    def test_entire_string_boundaries_no_prefix_trim_or_repair(self):
        class NeverParse:
            def SmilesParserParams(self):raise AssertionError('INVALID_WHOLE_STRING_MUST_NOT_REACH_PARSER')
        for text in ('',' C','C ','C name','C\nN','C\rN','C\tN','C\x00N','C\u00a0N','C\x7f'):
            self.assertEqual(P.atoms_only(text,NeverParse())['state'],'UNKNOWN_NO_COMPOSITION')
        for text in ('C1CC','C('):self.assertEqual(P.atoms_only(text,self.Chem)['state'],'UNKNOWN_NO_COMPOSITION')

    def test_unsanitized_atoms_are_composition_only_original_UNKNOWN(self):
        value=P.composition('CN(C)(C)C',self.Chem,self.functions)
        self.assertEqual(value['composition'],[[6,4],[7,1]])
        self.assertEqual(value['original_identity_state'],'ORIGINAL_SMILES_UNRESOLVED');self.assertEqual(value['full_keys'],[])
        self.assertEqual(value['graph_charge_stereo'],'UNKNOWN');self.assertFalse(value['automatic_fallback_policy_accepted'])
        self.assertEqual(value['parser_params'],C.PARAMS);self.assertFalse(value['skipCleanup_requested'])

    def test_explicit_H_isotope_all_fragments_and_dummy_query_unknown(self):
        value=P.composition('[13CH3][H].[Na+].[Cl-]',self.Chem,self.functions)
        self.assertEqual(value['composition'],[[6,1],[11,1],[17,1]])
        self.assertEqual(value['atomic_numbers_in_original_parser_order'],[6,1,11,17]);self.assertTrue(value['all_fragments_retained'])
        for text in ('*','C~C','[H]'):
            value=P.composition(text,self.Chem,self.functions);self.assertIsNone(value['composition'])
