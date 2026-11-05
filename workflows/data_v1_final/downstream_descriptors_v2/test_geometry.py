"""New baseline-only completion and existing QM7 perception tests; no native xTB."""
import copy
import unittest
from unittest.mock import patch
from .geometry import complete_geometry, qm7_perceived_graph, graph_seed


class GeometryTests(unittest.TestCase):
    def molecule(self,smiles='CCO'):
        from rdkit import Chem
        from rdkit.Chem import AllChem
        mol=Chem.MolFromSmiles(smiles)
        full=Chem.AddHs(mol);parameters=AllChem.ETKDGv3();parameters.randomSeed=193
        self.assertGreaterEqual(AllChem.EmbedMolecule(full,parameters),0)
        xyz=full.GetConformer().GetPositions().tolist()
        return mol,full,xyz

    def test_complete_native_xyz_is_reused_even_when_smiles_graph_order_differs(self):
        mol,full,xyz=self.molecule()
        numbers=[a.GetAtomicNum() for a in full.GetAtoms()]
        # Complete native geometry does not require an artificial graph-order remapping.
        order=list(reversed(range(len(numbers))))
        source={'mol':mol,'atomic_numbers':[numbers[i] for i in order],'coordinates_A':[xyz[i] for i in order]}
        result=complete_geometry(source)
        self.assertEqual(result['coordinates_A'],source['coordinates_A'])
        self.assertEqual(result['geometry_policy'],'REUSED_COMPLETE_EXISTING_NATIVE_GEOMETRY')
        self.assertEqual(result['xtb_source_atom_ids'],list(range(len(numbers))))

    def test_h_only_completion_preserves_every_existing_native_coordinate_and_source(self):
        from rdkit import Chem
        mol,full,xyz=self.molecule()
        source={'mol':mol,'atomic_numbers':[a.GetAtomicNum() for a in mol.GetAtoms()],
            'coordinates_A':xyz[:mol.GetNumAtoms()]}
        before=copy.deepcopy(source['coordinates_A']);binary=mol.ToBinary()
        result=complete_geometry(source)
        self.assertEqual(source['coordinates_A'],before);self.assertEqual(mol.ToBinary(),binary)
        self.assertEqual(result['coordinates_A'][:mol.GetNumAtoms()],before)
        self.assertEqual(result['atomic_numbers'],[a.GetAtomicNum() for a in full.GetAtoms()])
        self.assertEqual(result['xtb_source_atom_ids'],[0,1,2]+[None]*(len(xyz)-3))
        self.assertEqual(result['geometry_mmff_status'],0)
        self.assertIn('FIXED_ALL_EXISTING_NATIVE',result['geometry_policy'])

    def test_missing_coordinates_get_one_deterministic_existing_recipe_conformer(self):
        mol,_,_=self.molecule()
        source={'mol':mol,'atomic_numbers':[a.GetAtomicNum() for a in mol.GetAtoms()],'coordinates_A':None}
        first=complete_geometry(source);second=complete_geometry(source)
        self.assertEqual(first['geometry_seed'],graph_seed(mol))
        self.assertEqual(first['coordinates_A'],second['coordinates_A'])
        self.assertEqual(first['geometry_recipe']['force_field'],'MMFF94')
        self.assertEqual(first['geometry_recipe']['fallback'],'none')
        self.assertEqual(first['geometry_recipe']['max_iterations'],500)
        self.assertIsNone(source['coordinates_A']);self.assertEqual(mol.GetNumConformers(),0)

    def test_composition_or_atom_order_mismatch_is_not_silently_reconstructed(self):
        mol,_,xyz=self.molecule()
        source={'mol':mol,'atomic_numbers':[8,6,6],'coordinates_A':xyz[:3]}
        with self.assertRaisesRegex(ValueError,'ATOM_ORDER_OR_COMPOSITION_MISMATCH'):complete_geometry(source)

    def test_original_no_fallback_embedding_failure_is_explicit(self):
        mol,_,_=self.molecule()
        source={'mol':mol,'atomic_numbers':[a.GetAtomicNum() for a in mol.GetAtoms()],'coordinates_A':None}
        with patch('rdkit.Chem.AllChem.EmbedMolecule',return_value=-1) as call:
            with self.assertRaisesRegex(ValueError,'FAILED_NO_FALLBACK'):complete_geometry(source)
            self.assertEqual(call.call_count,1)

    def test_qm7_uses_formal_existing_perception_and_preserves_native_atom_order(self):
        from rdkit import Chem
        _,full,xyz=self.molecule('C')
        numbers=[a.GetAtomicNum() for a in full.GetAtoms()]
        perceived=qm7_perceived_graph(numbers,xyz)
        self.assertEqual([a.GetAtomicNum() for a in perceived.GetAtoms()],numbers)
        self.assertEqual(Chem.GetFormalCharge(perceived),0)
        self.assertEqual(perceived.GetNumBonds(),4)
        self.assertEqual(perceived.GetConformer().GetNumAtoms(),len(numbers))


if __name__=='__main__':unittest.main()
