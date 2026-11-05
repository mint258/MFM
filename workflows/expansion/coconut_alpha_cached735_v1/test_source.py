"""Native fixtures run only in Root's actual allocated Alpha environment."""
import json
import unittest
from . import kernel as K
from .extract import extract, lexical, text_reference


class Source(unittest.TestCase):
    def test_original_native_key_object_parity(self):
        expected, errors = K.STATE['functions']['source_smiles_keys']({'original': 'CCO'})
        actual = K.keys('CCO', 'SMILES')
        self.assertEqual((actual['keys'], actual['errors']), (expected, errors))
        self.assertTrue(expected)

    def test_dummy_known_atom_bound_no_completion(self):
        value = K.parse_atoms('C*', 'SMILES')
        self.assertEqual(value['positive_known_non_H_atom_lower_bound_observation'], [[6, 1]])
        self.assertEqual(value['dummy_atom_indices'], [1])
        self.assertIsNone(value['full_non_H_composition_observation'])
        self.assertFalse(value['lower_bound_accepted_for_exclusion'])

    def test_query_atoms_never_counted_as_known(self):
        Chem = K.STATE['Chem']; mol = Chem.RWMol()
        mol.AddAtom(Chem.Atom(6))
        mol.AddAtom(Chem.AtomFromSmarts('[#7,#8]'))
        value = K.atom_evidence(mol)
        self.assertEqual(value['positive_known_non_H_atom_lower_bound_observation'], [[6, 1]])
        self.assertEqual(value['query_atom_indices'], [1])
        self.assertIsNone(value['full_non_H_composition_observation'])

    def test_mol_new_seam_and_native_key_parity(self):
        Chem = K.STATE['Chem']; text = Chem.MolToMolBlock(Chem.MolFromSmiles('CCO'))
        atoms = K.parse_atoms(text, 'MOL'); keys = K.keys(text, 'MOL')
        self.assertEqual(atoms['full_non_H_composition_observation'], [[6, 2], [8, 1]])
        self.assertFalse(atoms['recipe']['original_recipe'])
        self.assertEqual(keys['keys'], K.keys('CCO', 'SMILES')['keys'])

    def test_H_only_is_observed_without_positive_non_H_bound(self):
        value = K.parse_atoms('[H][H]', 'SMILES')
        self.assertEqual(value['atom_count'], 2)
        self.assertTrue(value['closed_explicit_atom_table'])
        self.assertIsNone(value['positive_known_non_H_atom_lower_bound_observation'])
        self.assertIsNone(value['full_non_H_composition_observation'])

    def test_mixed_CSV_whole_text_never_prefix_parsed(self):
        text = 'CCO,06-022,"NOBILETIN, 20%",,https://example.test/details'
        value = K.parse_atoms(text, 'SMILES'); original = text_reference(text)
        self.assertEqual(value['state'], 'NOT_PARSED')
        self.assertFalse(lexical(text)['prefix_or_CSV_cell_extracted'])
        self.assertEqual(text_reference(text), original)

    def test_exact_three_original_normalize_fields_and_missing_variants(self):
        names = K.STATE['norm'].FIELDS['entries']; fields = dict.fromkeys(names)
        fields.update(id='fixture', canonical_smiles='CCO', status='REJECTED', is_invalid='t')
        row = dict(source_table='entries', copy_block=1, source_row_ordinal=1,
                   source_offset=0, source_bytes=1, source_row_sha256='0' * 64,
                   identity_fields_json=json.dumps(fields))
        value = K.STATE['norm'].normalize(row, K.STATE['functions'])
        self.assertEqual(value['source'], row)
        self.assertEqual(value['missing_variants'], 2)
        self.assertEqual([v['source_field'] for v in value['variant_observations']],
                         ['canonical_smiles', 'standardized_canonical_smiles', 'parent_canonical_smiles'])
