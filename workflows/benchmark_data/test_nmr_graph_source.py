import pickle
import unittest
import pandas as pd
from rdkit import Chem
from workflows.benchmark_data.nmr_graph_source import restricted_graph_load,graph_lookup


class OriginalGraphTests(unittest.TestCase):
    def test_graph_containers_preserve_ids_and_atom_order(self):
        mol=Chem.AddHs(Chem.MolFromSmiles('CCO'))
        original={'train_df':pd.DataFrame({'molecule_id':[4001],'rdmol':[mol]}),
            'test_df':pd.DataFrame({'molecule_id':[4002],'rdmol':[mol]})}
        lookup=graph_lookup(restricted_graph_load(pickle.dumps(original,protocol=4)))
        self.assertEqual(set(lookup),{4001,4002})
        self.assertEqual([a.GetAtomicNum() for a in lookup[4001][0].GetAtoms()],[6,6,8]+[1]*6)

    def test_multiple_spectra_keep_one_graph_and_all_split_provenance(self):
        mol=Chem.MolFromSmiles('CCO')
        data={'train_df':pd.DataFrame({'molecule_id':[1,1],'rdmol':[mol,mol]}),
            'test_df':pd.DataFrame({'molecule_id':[1],'rdmol':[mol]})}
        self.assertEqual(graph_lookup(data)[1][1],['train_df','train_df','test_df'])
        data['test_df']['rdmol']=[Chem.MolFromSmiles('CCN')]
        with self.assertRaises(ValueError):graph_lookup(data)

    def test_arbitrary_pickle_global_is_rejected(self):
        with self.assertRaises(pickle.UnpicklingError):restricted_graph_load(pickle.dumps(eval))

if __name__=='__main__':unittest.main()
