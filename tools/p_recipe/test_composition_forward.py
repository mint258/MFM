"""Composition cache tests: exact prefix, source identity and original CPU mean."""
import unittest
import numpy as np
from composition_forward import validate_cursor, store_batch


class ForwardTests(unittest.TestCase):
    def test_prefix_and_identity_reject_corruption(self):
        offsets=np.arange(66,dtype=np.int64)*2
        state=dict(identity={"source":1},record_cursor=32,atom_cursor=64,complete=False)
        self.assertEqual(validate_cursor(state,{"source":1},offsets),32)
        for update in [dict(record_cursor=31),dict(atom_cursor=65),dict(complete=True),
                       dict(identity={"source":2})]:
            with self.assertRaises(ValueError):validate_cursor({**state,**update},{"source":1},offsets)

    def test_original_mean_and_preserved_prefix(self):
        atoms=np.zeros((5,512),np.float32);means=np.zeros((2,512),np.float32)
        features=np.arange(3*512,dtype=np.float32).reshape(3,512).astype(np.float64)
        self.assertEqual(store_batch(atoms,means,features,[0,3],0,np.array([0,3,5])),1)
        before=atoms[:3].copy();first=means[0].copy()
        tail=np.full((2,512),2.,np.float64)
        self.assertEqual(store_batch(atoms,means,tail,[0,2],1,np.array([0,3,5])),2)
        np.testing.assert_array_equal(atoms[:3],before)
        np.testing.assert_array_equal(means[0],first)
        np.testing.assert_array_equal(first,features.mean(0).astype(np.float32))
        with self.assertRaises(ValueError):
            store_batch(atoms,means,tail,[0,2],0,np.array([0,3,5]))


if __name__=="__main__":unittest.main()
