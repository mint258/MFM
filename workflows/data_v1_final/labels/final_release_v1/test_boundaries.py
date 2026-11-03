"""Three meaningful synthetic boundaries; Source/Data execution belongs to CPU."""
import copy,sqlite3,tempfile,unittest
from pathlib import Path
from . import contract as C,originals as O,mask_binding as M

class Boundaries(unittest.TestCase):
    def test_missing_actual_parents_are_nonexecutable_and_no_future_reference(self):
        d={'schema':C.SCHEMA,'status':'PENDING','reviewer':None}
        result=C.validate_directive(d)
        self.assertEqual(result['status'],'NONEXECUTABLE');self.assertFalse(result['current_parent_C0_required_for_candidate'])
        self.assertEqual(result['data_references'],[]);self.assertEqual(result['source_references'],[])
        self.assertIn('joint_policy_reference',result['missing'])
        with self.assertRaises(ValueError):C.validate_directive(d,allow_nonexecutable=False)
        for bad in (True,0,-1):
            with self.assertRaises(ValueError):C.reference({'path':'/synthetic/data','bytes':bad,'sha256':'a'*64})

    def test_exact_original_series_selection_no_RMS_epsilon_or_anisotropy(self):
        rows={'physical/q/frobenius_norm':{'n':100,'mean':4.0,'std_ddof0':2.0,'lower':1.0,'upper':9.0}}
        recipe={'series_key':'physical/q/frobenius_norm','scale':'SERIES_STD_DDOF0','centering':'FIXED_ZERO','per_head_single_scale':True}
        value=O.exact_series_recipe(rows,recipe,physical=True)
        self.assertEqual(value['center_value'],0.0);self.assertEqual(value['scale'],2.0);self.assertEqual(value['audit_series_mean'],4.0)
        self.assertEqual(rows['physical/q/frobenius_norm']['mean'],4.0)
        with self.assertRaises(ValueError):O.exact_series_recipe(rows,dict(recipe,scale='RMS_ASSERTED_WITHOUT_REAL_BUILDER'),physical=True)
        with self.assertRaises(ValueError):O.exact_series_recipe(rows,dict(recipe,centering='SUBTRACT_SERIES_MEAN'),physical=True)
        zero=copy.deepcopy(rows);zero['physical/q/frobenius_norm']['std_ddof0']=0.0
        with self.assertRaises(ValueError):O.exact_series_recipe(zero,recipe,physical=True)
        with self.assertRaises(ValueError):O.exact_series_recipe({},recipe,physical=True)

    def test_original_rho_and_field_mask_partition_preserve_leaf_causes(self):
        import pyarrow as pa,pyarrow.parquet as pq,duckdb
        registry,reduce,series,compact,masks=O.objects()
        with tempfile.TemporaryDirectory(prefix='final_label_source3_') as name:
            p=Path(name)/'synthetic.parquet'
            pq.write_table(pa.Table.from_pylist([{'field_id':0,'value':float(i),'heavy_atoms':i,'n':1} for i in range(1,8)]),p)
            db=duckdb.connect()
            try:value=reduce.rho_external(db,[str(p)],0)
            finally:db.close()
            self.assertEqual(value['pair_n'],7);self.assertEqual(value['rho'],1.0)
        e={'field_id':0,'values_float64':[1.0,None,3.0],'source_value_mask':[True,False,True],'value_mask':[True,False,True],
          'source_reasons':['SOURCE_NONFINITE_OR_NONNUMERIC'],'new_reasons':[],'review_reasons':['ROBUST_Z_GT20_REVIEW_ONLY']}
        e1={**e,'field_id':1};row=compact.encode(9,0,[e,e1]);split=M.subset(row,[0],compact)
        self.assertEqual(compact.unpack(split['in_scope_fields']),[0]);a=masks.restore(row,0,3);b=masks.restore(split,0,3)
        self.assertEqual(a['valid'].tolist(),b['valid'].tolist());self.assertEqual(a['reason'].tolist(),b['reason'].tolist())
        self.assertEqual(a['field_reason_codes'],b['field_reason_codes']);self.assertEqual(a['review_groups'],b['review_groups'])
        self.assertEqual(M.complete_counts({'0':3},{'0':3,'1':0}),{'0':3,'1':0})
        with self.assertRaises(ValueError):M.complete_counts({'0':3},{'0':3,'1':1})
        with self.assertRaises(ValueError):M.complete_counts({'0':3,'2':0},{'0':3})
        self.assertEqual(registry.family_for('P','values.heat_of_formation_kcal_mol','molecule'),'energy')
        self.assertTrue(registry.physical_semantics('P','values.heat_of_formation_kcal_mol','molecule',None)['definition_based_not_inferred_from_rho'])

if __name__=='__main__':unittest.main()
