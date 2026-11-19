from types import SimpleNamespace
import unittest
import numpy as np
from workflows.benchmark_data.nmr_reference import rows,restricted_load


class ReferenceTests(unittest.TestCase):
    def test_author_defaultdict_container_loads_but_unapproved_globals_do_not(self):
        from collections import defaultdict
        import io,pickle,torch
        from torch_geometric.data import Data
        data=Data(R=torch.zeros((1,3)),Z=torch.tensor([6]))
        stream=io.BytesIO();torch.save((data,defaultdict(dict,{'R':torch.tensor([0,1])})),stream)
        loaded,slices=restricted_load(stream.getvalue())
        self.assertEqual(loaded.Z.tolist(),[6])
        self.assertEqual(slices['R'].tolist(),[0,1])
        stream=io.BytesIO();torch.save(eval,stream)
        with self.assertRaises(pickle.UnpicklingError):restricted_load(stream.getvalue())

    def test_source_atom_indices_and_masked_labels_are_retained(self):
        data=SimpleNamespace(R=np.array([[1,2,3],[4,5,6],[7,8,9]],dtype=np.float32),
            Z=np.array([6,1,8]),atom_y=np.array([12.5,0,3.25],dtype=np.float32),
            mask=np.array([1,0,1],dtype=np.float32),molecule_id=np.array([17,29]))
        slices={k:[0,2,3] for k in ('R','Z','atom_y','mask')}
        slices['molecule_id']=[0,1,2]
        result=list(rows(data,slices,'13C'))
        self.assertEqual(result[0]['source_atom_indices'],[0,1])
        self.assertEqual(result[0]['source_mask'],[1,0])
        self.assertEqual(result[1]['coordinates_A'],[[7,8,9]])
        self.assertEqual(result[1]['molecule_id'],'[29]')

if __name__=='__main__':unittest.main()
