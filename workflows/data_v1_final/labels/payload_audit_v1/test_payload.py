"""Six incremental synthetic payload checks; no real label data or old suites."""
import copy,unittest
from workflows.data_v1_final.labels import common
from workflows.data_v1_final.labels.size_cpu_v2.aggregate import pair_keys
from workflows.data_v1_final.labels.streaming_v1.support import legacy
from .payload import evaluate,layout_reviews,reference_review,quality_stop_fields

class PayloadSemantics(unittest.TestCase):
    def test_actual_array_length_and_source_immutability(self):
        good={'registry_id':1,'kind':5,'shape':[2,3],'array_f64':[1.,2.,3.,4.,5.,6.]}
        original=copy.deepcopy(good)
        self.assertEqual(common.decode_cell(good),[[1.,2.,3.],[4.,5.,6.]])
        self.assertEqual(good,original)
        with self.assertRaises(ValueError):common.decode_cell(dict(good,array_f64=[1.,2.]))
        with self.assertRaises(ValueError):common.decode_cell(dict(good,shape=[-1,3]))

    def test_pair_conflict_and_atom_coverage_are_review_only(self):
        pairs=[{'i':0,'j':1,'value':.5},{'i':1,'j':0,'value':.7}];saved=copy.deepcopy(pairs)
        self.assertIn('DUPLICATE_PAIR_KEY_CONFLICT_REVIEW',layout_reviews(pairs,'bond_orders',2,pair_keys))
        self.assertEqual(pairs,saved)
        one=[{'atom_index':0,'values':[1.,2.,3.]},{'atom_index':0,'values':[1.,2.,3.]}]
        reviews=layout_reviews(one,'enpart_one_center_eV',2,pair_keys)
        self.assertIn('COMPOUND_DUPLICATE_ATOM_ID_REVIEW',reviews);self.assertIn('ONE_CENTER_ATOM_COVERAGE_REVIEW',reviews)

    def test_unknown_basis_index_and_empty_sparse_are_not_invented_values(self):
        wrong=[{'atom_i':0,'atom_j':8,'basis_i':'s','basis_j':'p','value':1.}]
        self.assertIn('SPARSE_PAIR_ATOM_ID_RANGE_REVIEW',layout_reviews(wrong,'sigma_pi_entries',2,pair_keys))
        self.assertEqual(layout_reviews([],'bond_orders',2,pair_keys),[])
        self.assertIs(common.decode_cell({'registry_id':2,'kind':9}),common.MISSING)
        self.assertIsNone(common.decode_cell({'registry_id':2,'kind':0}))

    def test_z_and_zero_mad_do_not_mask_or_change_values(self):
        item={'field_id':0,'values_float64':[50.],'value_mask':[True],'review_reasons':[]}
        self.assertGreater(reference_review(item,{'0':{'median':0.,'MAD':1.}}),20)
        self.assertIn('ROBUST_Z_GT20_REVIEW_ONLY',item['review_reasons']);self.assertEqual(item['value_mask'],[True])
        reference_review(item,{'0':{'median':0.,'MAD':0.}})
        self.assertIn('ZERO_MAD_UNEQUAL_VALUE_REVIEW_ONLY',item['review_reasons']);self.assertEqual(item['values_float64'],[50.])
        self.assertIsNone(reference_review(item,{}))

    def test_exact_one_percent_and_old_missing_not_new_failure(self):
        stats={'0':{'newly_masked_records':10},'1':{'newly_masked_records':11},
          '2':{'new_payload_structural_invalid_records':11},'3':{'source_missing_records':900}}
        self.assertEqual(quality_stop_fields(stats,1000),['1','2'])

    def test_ea_high_value_and_null_convergence_not_guessed_failure(self):
        # Real frozen rule functions, synthetic values: no archive/QM/true corpus.
        import pathlib,json
        repo=pathlib.Path(__file__).absolute().parents[4]
        config=json.loads((repo/'configs/data_v1/labels/streaming_v1.json').read_text())
        native,masks=legacy(config)
        field={'field_key':'P.xtb_vipea.r751.value','registry_id':751,'task':'xtb_vipea','source_path':'values.EA_eV',
          'component':'value','level':'molecule','status':'enabled','field_id':0,
          'physical_range':{'lower':None,'upper':None,'lower_exclusive':False}}
        row={'status':'SUCCESS','source_status':'SUCCESS','converged':None,'total_atoms':2,'calc_type':'xtb_vipea',
          'numeric_issues':[],'values':[{'registry_id':751,'kind':1,'f64':8791.0184}],'precision_by_field_json':'{}'}
        saved=copy.deepcopy(row)
        items,obs,issues,raw,scores=evaluate(row,'xtb_vipea',[field],native,masks,pair_keys,{})
        self.assertEqual(items[0]['value_mask'],[True]);self.assertEqual(items[0]['new_reasons'],[])
        self.assertIn('SUCCESS_WITH_CONVERGENCE_EVIDENCE_UNKNOWN',items[0]['review_reasons'])
        self.assertEqual(row,saved);self.assertEqual(obs[0]['numeric_leaves'],1)

if __name__=='__main__':unittest.main()