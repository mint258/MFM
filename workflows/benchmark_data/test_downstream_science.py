import unittest
from workflows.benchmark_data.downstream_science import identities,process


class DownstreamAdapterTests(unittest.TestCase):
    def test_actual_conformers_use_source_atom_order_and_frozen_seed(self):
        from rdkit import Chem
        row=process({'model_smiles':'CCO'})
        self.assertEqual(row['molecule_id'],identities('CCO')[0])
        self.assertEqual(row['seed'],identities('CCO')[1])
        self.assertEqual(row['atomic_numbers'][:3],[6,6,8])
        self.assertEqual(row['model_atom_to_template'][:3],[0,1,2])
        self.assertEqual(row['embedding_calls'],1)
        self.assertGreaterEqual(len(row['conformers']),1)
        self.assertLessEqual(len(row['conformers']),3)
        self.assertEqual(len(row['D20']['values']),20)
        self.assertNotIn('Kappa1',row['D20']['names'])
        self.assertFalse(row['conformers'][0]['D3_issues'])
        self.assertEqual(len(row['conformers'][0]['D3']['SASA_atom_A2']),len(row['atomic_numbers']))

    def test_unspecified_stereo_keeps_d20_without_inventing_a_3d_reference(self):
        row=process({'model_smiles':'CC(O)CC'})
        self.assertEqual(row['state'],'D20_READY_STEREO_REFERENCE_UNAVAILABLE')
        self.assertIsNotNone(row['D20'])
        self.assertEqual(row['embedding_calls'],0)
        self.assertEqual(row['conformers'],[])

if __name__=='__main__':unittest.main()
