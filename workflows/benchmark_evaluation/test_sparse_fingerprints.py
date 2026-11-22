"""New storage-format contracts on invented fingerprints, never real model outputs."""
import unittest
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from workflows.benchmark_evaluation.sparse_fingerprints import sparse_fingerprint_matrix

def packed(active):
    values=np.zeros(2048,dtype=np.uint8);values[list(active)]=1
    return np.packbits(values,bitorder="little").tobytes()

class SparseFingerprintTests(unittest.TestCase):
    def test_original_little_endian_bit_and_row_order_is_exact(self):
        rows=[dict(ecfp4_2048_packed=packed([0,7,8,2047])),dict(ecfp4_2048_packed=packed([1,9]))]
        matrix=sparse_fingerprint_matrix(rows)
        dense=np.asarray([np.unpackbits(np.frombuffer(r["ecfp4_2048_packed"],np.uint8),bitorder="little") for r in rows],np.float32)
        np.testing.assert_array_equal(matrix.toarray(),dense)
        self.assertEqual(matrix.format,"csc")
        self.assertEqual(matrix.dtype,np.float32)
        self.assertEqual(matrix.nnz,6)
    def test_solvent_roles_and_native_gas_zero_block_are_not_conflated(self):
        rows=[dict(chrom=packed([3]),solvent=packed([]),gas=True),
              dict(chrom=packed([3]),solvent=packed([3]),gas=False)]
        matrix=sparse_fingerprint_matrix(rows,("chrom","solvent"),"gas").toarray()
        self.assertEqual(matrix.shape,(2,4097))
        self.assertEqual(matrix[0,3],1.)
        self.assertEqual(matrix[0,2048+3],0.)
        self.assertEqual(matrix[1,2048+3],1.)
        self.assertEqual(matrix[0,-1],1.)
        self.assertEqual(matrix[1,-1],0.)
    def test_malformed_native_fingerprints_are_not_padded_or_imputed(self):
        for value in (None,b"short"):
            with self.assertRaises(ValueError):sparse_fingerprint_matrix([dict(ecfp4_2048_packed=value)])
    def test_same_RF_parameters_accept_the_same_binary_values_in_both_storage_forms(self):
        rng=np.random.default_rng(20261025)
        raw=(rng.random((40,2048))<.02).astype(np.uint8)
        rows=[dict(ecfp4_2048_packed=np.packbits(r,bitorder="little").tobytes()) for r in raw]
        target=np.arange(40,dtype=float)
        parameters=dict(n_estimators=7,random_state=20261025,n_jobs=1)
        dense=RandomForestRegressor(**parameters).fit(raw,target)
        sparse=RandomForestRegressor(**parameters).fit(sparse_fingerprint_matrix(rows),target)
        self.assertEqual(dense.get_params(),sparse.get_params())
        np.testing.assert_array_equal(dense.predict(raw),sparse.predict(sparse_fingerprint_matrix(rows)))

if __name__=="__main__":unittest.main()
