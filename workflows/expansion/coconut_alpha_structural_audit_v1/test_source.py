"""One semantic boundary fixture: fixed atoms with uncertain bonds remain candidates."""
import copy
import unittest
from .core import variant,partition


class Source(unittest.TestCase):
    def test_missing_key_query_bonds_do_not_erase_fixed_atom_composition(self):
        value=dict(variant_id='fixture',representation='MOL',text_reference={'sha256':'fixture'},
            key_observation={'keys':[],'state':'NO_VALID_FULL_KEY'},unsanitized_atom_observation=dict(
            atom_count=2,atoms_in_parser_order=[dict(index=0,atomic_number=6,has_query=False),
                dict(index=1,atomic_number=8,has_query=False)],query_atom_indices=[],dummy_atom_indices=[],
            query_bond_indices=[0],closed_explicit_atom_table=False,full_non_H_composition_observation=None))
        fixed=variant(value,'M  END\n')
        self.assertEqual(fixed['fixed_atom_non_H_composition_observation'],[[6,1],[8,1]])
        self.assertTrue(fixed['fixed_atoms_query_bonds_only'])
        self.assertEqual(partition([fixed]),'INSUFFICIENT_EVIDENCE')
        dummy=copy.deepcopy(value);dummy['unsanitized_atom_observation']['atoms_in_parser_order'][0]['atomic_number']=0
        dummy['unsanitized_atom_observation']['dummy_atom_indices']=[0]
        incomplete=variant(dummy,'M  END\n')
        self.assertFalse(incomplete['fixed_explicit_atom_composition_candidate'])
        self.assertEqual(partition([incomplete]),'SUPPLIED_REPRESENTATIONS_UNDERSPECIFIED_QUERY_DUMMY_OR_VARIABLE')
        self.assertEqual(partition([incomplete,fixed]),'INSUFFICIENT_EVIDENCE')
        queried=copy.deepcopy(value);queried['unsanitized_atom_observation']['atoms_in_parser_order'][0]['has_query']=True
        queried['unsanitized_atom_observation']['query_atom_indices']=[0]
        self.assertFalse(variant(queried,'M  END\n')['fixed_explicit_atom_composition_candidate'])
        self.assertFalse(variant(value,'M  STY  1   1 SRU\nM  END\n')['fixed_explicit_atom_composition_candidate'])
        malformed=copy.deepcopy(value);malformed['unsanitized_atom_observation']['atom_count']=3
        self.assertFalse(variant(malformed,'M  END\n')['complete_atom_record_table'])
        self.assertFalse(fixed['exact_composition_or_graph_accepted'] or fixed['world_nonexistence_inferred'])


if __name__=='__main__':unittest.main()
