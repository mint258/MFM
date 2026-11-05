"""Scientific membership and frozen-selection boundary unit tests."""
import unittest
from .run import original_membership_functions, update_member, check_nested


class PopulationTests(unittest.TestCase):
    def setUp(self):
        self.membership, self.gates = original_membership_functions()
        self.row = {'molecule_id':'n1','effective_role':'TRAIN','S_usable_conformers':1,
            'S_conformers':1,'records':1,'Sprime_status':'SUCCESS','merged_uff_count':1,
            'fill_status':None,'common_population':True,'elements_atomic_numbers':[1,6]}

    def test_registered_extra_changes_pprime_availability_not_common(self):
        result = update_member(self.row, self.membership, {'n1':{}}, {})
        self.assertTrue(result['common_population'])
        self.assertFalse(result['pprime_two_conformers_pending'])
        self.assertEqual(result['merged_uff_count'],1)
        self.assertEqual(result['available_real_Pprime_bases'],2)

    def test_unavailable_n1_remains_common_and_explicit_pending(self):
        result = update_member(self.row,self.membership,{}, {'n1':'NO_SECOND_GEOMETRY'})
        self.assertTrue(result['common_population'])
        self.assertTrue(result['pprime_two_conformers_pending'])
        self.assertEqual(result['n1_current_state'],'NO_SECOND_GEOMETRY')

    def test_unresolved_source_not_promoted(self):
        row=dict(self.row,fill_status='EXECUTION_UNRESOLVED',common_population=False)
        result=update_member(row,self.membership,{}, {})
        self.assertFalse(result['common_population'])
        self.assertIn('EXECUTION_UNRESOLVED',result['exclusion_reasons'])

    def test_source_predicate_mismatch_refused(self):
        row=dict(self.row,merged_uff_count=0)
        with self.assertRaisesRegex(ValueError,'PREDICATE_DISAGREE'):
            update_member(row,self.membership,{}, {})

    def test_role_leakage_not_admitted(self):
        row=dict(self.row,effective_role='FULL',common_population=False)
        result=update_member(row,self.membership,{}, {})
        self.assertFalse(result['common_population'])

    def test_nested_selection_rejects_changed_membership(self):
        values={'train_120000':list(range(120000)), 'train_240000':list(range(240000)),
            'train_600000':list(range(600000)), 'train_all':list(range(700000))}
        check_nested(values)
        values['train_240000'][-1]=700001
        with self.assertRaisesRegex(ValueError,'NESTED_D5'):
            check_nested(values)



class D7Tests(unittest.TestCase):
    def test_exact_threshold_is_unique(self):
        from .d7 import count_unique
        rows=[{'conformer_id':0,'x':0.0},{'conformer_id':1,'x':0.49},{'conformer_id':2,'x':0.5}]
        actual=count_unique(rows,[0,1,2],lambda left,right:abs(left['x']-right['x']))
        self.assertEqual(actual,[0,2])

    def test_duplicate_id_and_nonfinite_distance_rejected(self):
        from .d7 import count_unique
        with self.assertRaisesRegex(ValueError,'PERMUTATION'):
            count_unique([{'conformer_id':0},{'conformer_id':0}],[0,0],lambda a,b:0.0)
        with self.assertRaisesRegex(ValueError,'NONFINITE'):
            count_unique([{'conformer_id':0},{'conformer_id':1}],[0,1],lambda a,b:float('nan'))

    def test_summary_uses_full_sprime_population_and_weighted_duplicate_fraction(self):
        from .d7 import summarize
        rows=[{'molecule_id':'a','status':'COMPLETE','reused_closed_result':False,'common_population':True,
            'pm7_count':4,'pm7_unique':2,'uff_sprime_count':4,'uff_sprime_unique':3,'heavy_atoms':4,'rotatable_bonds':1},
            {'molecule_id':'b','status':'COMPLETE','reused_closed_result':True,'common_population':False,
            'pm7_count':1,'pm7_unique':1,'uff_sprime_count':1,'uff_sprime_unique':1,'heavy_atoms':2,'rotatable_bonds':0}]
        result=summarize(rows)
        self.assertAlmostEqual(result['unique_counts']['pm7']['duplicate_conformer_fraction'],0.4)
        self.assertEqual(result['unique_counts']['uff_sprime']['molecules'],2)

if __name__=='__main__':
    unittest.main()