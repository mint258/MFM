"""The production three-column D5 list resolves Native IDs, never guesses."""
import tempfile,unittest
from pathlib import Path
from .eligibility import diagnostic_pm7_records,eligible

class D5IdentitySchema(unittest.TestCase):
    def test_production_base_identity_join_and_legacy_direct_format(self):
        import pyarrow as pa,pyarrow.parquet as pq
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary)
            def table(name,rows):
                filename=folder/name;pq.write_table(pa.Table.from_pylist(rows),filename);return {'path':str(filename)}
            base=table('diagnostic_base.parquet',[
                {'molecule_id':'M:A:17','geometry_source':'pm7','geometry_id':'opaque-geometry-b'},
                {'molecule_id':'M:B:29','geometry_source':'pm7','geometry_id':'opaque-geometry-a'},
                {'molecule_id':'M:A:17','geometry_source':'uff_sprime','geometry_id':'opaque-uff'}])
            actual=table('actual_heldout_geometry.parquet',[
                {'geometry_id':'opaque-geometry-a','molecule_id':'M:B:29','geometry_source':'pm7','native_record_id':'authoritative-native-second'},
                {'geometry_id':'opaque-uff','molecule_id':'M:A:17','geometry_source':'uff_sprime','native_record_id':None},
                {'geometry_id':'unselected-program-view','molecule_id':'M:A:17','geometry_source':'pm7','native_record_id':'must-not-exclude'},
                {'geometry_id':'opaque-geometry-b','molecule_id':'M:A:17','geometry_source':'pm7','native_record_id':'authoritative-native-first'}])
            expected={'authoritative-native-first','authoritative-native-second'}
            result=diagnostic_pm7_records({'diagnostic_base_reference':base,'actual_heldout_geometry_reference':actual})
            self.assertEqual(result,expected)
            # The unchanged fit predicate excludes by Native ID for all tasks.
            self.assertFalse(eligible('TRAIN',True,'authoritative-native-first',result)[0])
            self.assertTrue(eligible('TRAIN',True,'must-not-exclude',result)[0])
            direct=table('legacy_direct.parquet',[
                {'geometry_source':'pm7','native_record_id':'authoritative-native-first'},
                {'geometry_source':'pm7','native_record_id':'authoritative-native-second'},
                {'geometry_source':'uff_sprime','native_record_id':None}])
            self.assertEqual(diagnostic_pm7_records({'diagnostic_base_reference':direct}),expected)
