"""New population/traversal seams; original statistics are not re-regressed."""
import unittest
from .eligibility import eligible
from .reader import effective_owner
from .statistics import exact_tails


class NormalizationSeams(unittest.TestCase):
    def test_only_final_common_train_nonheld_conformer_fits(self):
        held={'held'}
        self.assertEqual(eligible('TRAIN',True,'ordinary',held),(True,'COMMON_TRAIN_NOT_D5'))
        self.assertFalse(eligible('VAL',True,'ordinary',held)[0])
        self.assertFalse(eligible('FULL',True,'ordinary',held)[0])
        self.assertFalse(eligible('TRAIN',False,'ordinary',held)[0])
        self.assertFalse(eligible('TRAIN',True,'held',held)[0])

    def test_original_record_owner_matches_eligibility(self):
        owner={'record_id':'r','molecule_id':'m','job_id':'j','new_role':'TRAIN'}
        side=('r','m','j','TRAIN','TRAIN',1,None,None,1,'COMMON_TRAIN_NOT_D5')
        self.assertTrue(effective_owner(owner,side)['fit_eligible'])
        with self.assertRaisesRegex(ValueError,'OWNER_ALIGNMENT'):
            effective_owner(dict(owner,molecule_id='other'),side)

    def test_exact_tail_count_and_order_are_preserved(self):
        finished={'lower':[{'field_id':0,'n':5,'value':1.0}], 'upper':[{'field_id':0,'n':5,'value':9.0}]}
        result=exact_tails([{'field_id':0}],finished)['0']
        self.assertEqual((result['lower'],result['upper'],result['n']),(1.0,9.0,5))
        finished['upper'][0]['n']=4
        with self.assertRaisesRegex(ValueError,'MASS_AND_ORDER'):exact_tails([{'field_id':0}],finished)


if __name__=='__main__':unittest.main()
