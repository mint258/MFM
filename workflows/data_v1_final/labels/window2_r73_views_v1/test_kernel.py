import unittest,math
from .kernel import derive_entries,derived_fields
class R73Tests(unittest.TestCase):
    def entry(self,values,mask=None):
        field={'field_id':72,'field_key':'P.pm7_B.r73.value','registry_id':73,'source_path':'values.sigma_pi_entries','level':'sparse_atom_pair','element_reference_eligible':False}
        return {'field':field,'values_float64':values,'source_value_mask':[True]*len(values),'value_mask':mask or[True]*len(values),'source_reasons':[],'new_reasons':[],'review_reasons':[]}
    def test_directed_duplicate_block_and_mask(self):
        rows=[{'atom_i':1,'atom_j':0,'basis_i':a,'basis_j':b,'value':v}for a,b,v in[('S-SIGMA','P-SIGMA',1.),('P-SIGMA','S-SIGMA',2.),('P-PI','P-PI',4.),('S-SIGMA','P-PI',99.),('D-DELL','D-DELL',100.)]]
        out=derive_entries(rows,self.entry([1.,2.,4.,99.,100.],[True,True,False,True,True]))
        self.assertTrue(math.isclose(out[0]['values_float64'][0],3.,rel_tol=1e-12,abs_tol=1e-12));self.assertEqual(out[0]['pair_indices'],[[1,0]])
        self.assertTrue(out[0]['value_mask'][0]);self.assertFalse(out[1]['value_mask'][0])
    def test_no_pure_block_is_missing_not_zero(self):
        rows=[{'atom_i':0,'atom_j':1,'basis_i':'S-SIGMA','basis_j':'P-PI','value':9.}]
        for entry in derive_entries(rows,self.entry([9.])):self.assertIsNone(entry['values_float64'][0]);self.assertFalse(entry['value_mask'][0])
    def test_view_map_does_not_renumber_original_field(self):
        original=self.entry([])['field'];before=dict(original);out=derived_fields([original])
        self.assertEqual(original,before);self.assertEqual([f['field_id']for f in out],[146,147]);self.assertEqual([f['field_key']for f in out],['P.pm7_B.r73.value.sigma','P.pm7_B.r73.value.pi'])