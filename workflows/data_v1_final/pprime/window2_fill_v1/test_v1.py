"""Unit tests of physical identity checks; no native call or pilot."""
import tempfile,unittest
from pathlib import Path
from .run import physical
import pyarrow as pa,pyarrow.parquet as pq
class PhysicalTests(unittest.TestCase):
    def test_physical_identity_and_convergence(self):
        with tempfile.TemporaryDirectory()as tmp:
            p=Path(tmp)/'geometry.parquet'
            pq.write_table(pa.Table.from_pylist([{'molecule_id':'A','status':'SUCCESS','converged':True,'atom_order_sha256':'old-witness','sprime_conf_idx':7,'coordinates':[[0.,0.,0.]]}]),p)
            row={'source_format':'parquet','source_path':str(p),'source_row_index':0,'molecule_id':'A','atom_order_sha256':'old-witness','original_sprime_conf_idx':7}
            self.assertEqual(physical(row)['sprime_conf_idx'],7)
            with self.assertRaisesRegex(ValueError,'GEOMETRY_ID'):physical(dict(row,molecule_id='B'))
            with self.assertRaisesRegex(ValueError,'CONFORMER_ID'):physical(dict(row,original_sprime_conf_idx=9))