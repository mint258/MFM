"""Reference loader tests use synthetic tables; no chemistry or QM reruns."""
import tempfile
import unittest
from pathlib import Path
import pyarrow as pa
import pyarrow.parquet as pq
from .reference_d3 import frames


class ReferenceFrames(unittest.TestCase):
    def test_nmr_repeated_source_ids_bind_by_row_and_keep_source_order(self):
        with tempfile.TemporaryDirectory(prefix='b0-ref-loader-') as folder:
            root=Path(folder)
            pq.write_table(pa.Table.from_pylist([
                {'record_id':'spectrum-a','source_row':3,'model_smiles':'CCC','domain_eligible':True},
                {'record_id':'spectrum-b','source_row':7,'model_smiles':'CCC','domain_eligible':True},
                {'record_id':'excluded','source_row':8,'model_smiles':'C','domain_eligible':False},
            ]),root/'domain.parquet')
            pq.write_table(pa.Table.from_pylist([
                {'source_row':7,'atomic_numbers':[6,1],'coordinates_A':[[7.,0.,0.],[1.,0.,0.]]},
                {'source_row':3,'atomic_numbers':[6,1],'coordinates_A':[[3.,0.,0.],[1.,0.,0.]]},
            ]),root/'reference.parquet')
            out=list(frames(root/'domain.parquet',root/'reference.parquet',root/'absent.parquet','NMRShiftDB2_13C'))
            self.assertEqual([r['record_id'] for r in out],['spectrum-b','spectrum-a'])
            self.assertEqual(out[0]['coordinates_A'][0],[7.,0.,0.])
            self.assertEqual([r['source_reference_row'] for r in out],[0,1])
            self.assertIsNone(out[0]['D20'])

    def test_missing_eligible_reference_is_explicit_failure(self):
        with tempfile.TemporaryDirectory(prefix='b0-ref-loader-') as folder:
            root=Path(folder)
            pq.write_table(pa.Table.from_pylist([
                {'record_id':'a','source_row':0,'model_smiles':'CCC','domain_eligible':True},
            ]),root/'domain.parquet')
            pq.write_table(pa.Table.from_pylist([
                {'record_id':'other','atomic_numbers':[6],'coordinates_A':[[0.,0.,0.]]},
            ]),root/'reference.parquet')
            with self.assertRaisesRegex(ValueError,'missing reference'):
                list(frames(root/'domain.parquet',root/'reference.parquet',root/'absent.parquet','C7H10O2'))


if __name__=='__main__':unittest.main()