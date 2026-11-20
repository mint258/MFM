import unittest
from rdkit import Chem
from workflows.benchmark_data.nmr2018_targets import labels,source_record

def molecule():
    p=Chem.SmilesParserParams();p.removeHs=False
    return Chem.MolFromSmiles('[H]C([H])([H])C(=O)O[H]',p)

class NMRTargets(unittest.TestCase):
    def test_explicit_hydrogen_indices_and_spectrum_groups_are_preserved(self):
        mol=molecule()
        result=labels(mol,[{0:1.2},{0:1.3,2:1.4}],'1H')
        self.assertEqual(result['target_source_atom_ids'],[0,0,2])
        self.assertEqual(result['target_group_indices'],[0,1,1])
        self.assertEqual(result['target_values_ppm'],[1.2,1.3,1.4])

    def test_wrong_nucleus_and_nonexistent_source_atom_rejected(self):
        with self.assertRaises(ValueError):labels(molecule(),[{0:12.0}],'13C')
        with self.assertRaises(ValueError):labels(molecule(),[{100:1.0}],'1H')

    def test_repeated_author_molecule_rows_keep_distinct_ids_and_atom_mapping(self):
        mol=molecule();row=dict(rdmol=mol,molecule_id=123,spectra_ids=[4],value=[{0:1.2}])
        first=source_record('1H','test',0,20,row,'member','archive')
        second=source_record('1H','test',1,21,row,'member','archive')
        self.assertEqual(first['official_split'],'test')
        self.assertEqual(first['original_molecule_id'],second['original_molecule_id'])
        self.assertNotEqual(first['record_id'],second['record_id'])
        self.assertEqual(first['target_source_atom_ids'],[0])
        params=Chem.SmilesParserParams();params.removeHs=False
        parsed=Chem.MolFromSmiles(first['model_smiles'],params)
        for i,source_id in enumerate(first['model_atom_to_source']):
            self.assertEqual(parsed.GetAtomWithIdx(i).GetAtomicNum(),mol.GetAtomWithIdx(source_id).GetAtomicNum())

if __name__=='__main__':unittest.main()
