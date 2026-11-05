"""Scientific source-selection and mask seams; no Native trial calculation."""
import unittest,struct,math
from .projection import eligible,apply_explicit_exclusions
from . import statistics as S
from ..window2_normalization_v1 import statistics as Original
class PprimeTests(unittest.TestCase):
    def test_train_and_actual_d5_physical_key(self):
        held={('MID',9)}
        self.assertFalse(eligible('TRAIN',True,('MID',9),held)[0])
        self.assertTrue(eligible('TRAIN',True,('MID',7),held)[0])
        self.assertFalse(eligible('VAL',True,('MID',7),held)[0])
        self.assertFalse(eligible('FULL',True,('MID',7),held)[0])
        self.assertFalse(eligible('TRAIN',False,('MID',7),held)[0])
    def test_mask_override_preserves_f64_and_source_mask(self):
        x=1.2345678901234567
        e={'field_id':144,'values_float64':[x,None],'source_value_mask':[True,False],'value_mask':[True,False],'new_reasons':[]}
        before=struct.pack('<d',e['values_float64'][0]);apply_explicit_exclusions([e],{144:'TASKBOOK_EXPLICIT_RECORD_FIELD_EXCLUSION'})
        self.assertEqual(struct.pack('<d',e['values_float64'][0]),before)
        self.assertEqual(e['source_value_mask'],[True,False]);self.assertEqual(e['value_mask'],[False,False])
    def test_original_normalization_math_objects(self):
        self.assertIs(S.Original._group_pass.__code__,Original._group_pass.__code__)
        self.assertIs(S.Original.B.TSQR,Original.B.TSQR)
        self.assertIs(S.Original.B.RadixCounts,Original.B.RadixCounts)
        self.assertIs(S.Original.B.WinsorMoments,Original.B.WinsorMoments)
    def test_group_mean_is_leaf_weighted(self):
        import duckdb
        from .compare import merged_mean_sql
        db=duckdb.connect()
        db.execute('CREATE TABLE parts(molecule_id VARCHAR,field_id INTEGER,n INTEGER,"sum" DOUBLE)')
        db.execute("INSERT INTO parts VALUES('M',42,1,1),('M',42,3,9)")
        row=db.execute(merged_mean_sql('parts')).fetchone();db.close()
        self.assertEqual(row[:2],('M',42));self.assertTrue(math.isclose(row[2],2.5,rel_tol=1e-12,abs_tol=1e-12));self.assertEqual(row[3],4)
    def test_constant_correlation_remains_unknown(self):
        from .compare import finite_or_none
        self.assertIsNone(finite_or_none(float('nan')))
        self.assertIsNone(finite_or_none(float('inf')))
        self.assertEqual(finite_or_none(0.),0.)

class ActualGeometryBindingTests(unittest.TestCase):
    def test_same_mid_conf_different_geometry_cannot_fit_or_inherit_gid(self):
        import json
        from .projection import bind_selection,eligible
        raw={'source_record_id':'anchor','atomic_numbers':[6,1],'positions_A':[[0.,0.,0.],[1.,0.,0.]]}
        selected=dict(raw,positions_A=[[0.,0.,0.],[2.,0.,0.]])
        result=bind_selection(raw,('ordinary-gid','TRAIN',1,1,'FIT',json.dumps(selected)))
        self.assertIsNone(result[0]);self.assertEqual(result[3],0)
        self.assertEqual(result[4],'DIFFERENT_ACTUAL_GEOMETRY_AT_SAME_MID_CONF')
        self.assertTrue(eligible('TRAIN',True,'ordinary-gid',{'diagnostic-other-gid'})[0])
        self.assertFalse(eligible('TRAIN',True,'diagnostic-other-gid',{'diagnostic-other-gid'})[0])
    def test_original_f64_geometry_match_assigns_verified_gid(self):
        import json
        from .projection import bind_selection
        raw={'source_record_id':'anchor','atomic_numbers':[6,1],'positions_A':[[0.,0.,0.],[1.0000000000000002,0.,0.]]}
        result=bind_selection(raw,('actual-gid','TRAIN',1,1,'FIT',json.dumps(raw)))
        self.assertEqual((result[0],result[3]),('actual-gid',1))
        self.assertIn('F64',result[5])
