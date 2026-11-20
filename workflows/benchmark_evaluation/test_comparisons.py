"""Unit tests only for new paired-comparison and second-seed policy logic."""
import unittest
import math
from workflows.benchmark_evaluation.comparisons import paired_improvement,needs_second_seed,baseline_confirmation_plan
from workflows.benchmark_evaluation.selection import IncompleteComparison

def rows(error):
    return [dict(record_id=str(i),full_inchikey="molecule_"+str(i//2),
                 y_true=float(i%2*2-1),prediction=float(i%2*2-1)+error,training_mean=0.)
            for i in range(80)]

class ComparisonTests(unittest.TestCase):
    def test_whole_molecules_are_paired_and_improvement_is_directional(self):
        actual=paired_improvement(rows(.4),rows(.1))
        self.assertEqual(actual["common_TEST_molecules"],40)
        self.assertAlmostEqual(actual["pooled_RAE_improvement"],.3)
        self.assertAlmostEqual(actual["paired_RAE_improvement_CI95_low"],.3)
        self.assertTrue(actual["significant_improvement"])
        self.assertFalse(paired_improvement(rows(.1),rows(.4))["significant_improvement"])
    def test_ordinary_missing_rows_are_not_silently_intersected(self):
        with self.assertRaises(IncompleteComparison):paired_improvement(rows(.4),rows(.1)[:-1])
    def test_declared_native_missingness_has_explicit_population_counts(self):
        data=rows(.1);data[0]["prediction"]=None
        actual=paired_improvement(rows(.4),data,allow_native_missing=True)
        self.assertEqual(actual["common_TEST_rows"],79)
        self.assertEqual(actual["candidate_rows_outside_common_available_population"],1)
    def test_each_method_retains_its_actual_TRAIN_reference(self):
        left=[dict(record_id=str(i),full_inchikey="m"+str(i),y_true=1.,prediction=1.4,training_mean=0.) for i in range(40)]
        right=[dict(r,prediction=1.1,training_mean=-1.) for r in left]
        actual=paired_improvement(left,right)
        self.assertAlmostEqual(actual["candidate_RAE"],.05)
        self.assertAlmostEqual(actual["reference_RAE"],.4)
    def test_labels_and_groups_must_match(self):
        data=rows(.1);data[0]["y_true"]=3.
        with self.assertRaises(IncompleteComparison):paired_improvement(rows(.4),data)
    def test_CV_significance_uses_every_original_fold(self):
        reference=[];candidate=[]
        for rep in range(5):
            for fold in range(5):
                for atom in range(2):
                    y=float(atom*2-1);noise=.02*math.sin(rep*5+fold)
                    base=dict(record_id=str(fold*2+atom)+"::repeat:"+str(rep),full_inchikey="m"+str(fold*2+atom),
                              y_true=y,training_mean=0.,repetition=rep,fold=fold)
                    reference.append(dict(base,prediction=y+.4+noise));candidate.append(dict(base,prediction=y+.1+noise))
        result=paired_improvement(reference,candidate,scaffold_cv=True)
        self.assertEqual(result["significance_method"],"TUKEY_HSD_25_ORIGINAL_SCAFFOLD_FOLDS")
        self.assertTrue(result["significant_improvement"])
        candidate=[r for r in candidate if (r["repetition"],r["fold"])!=(0,0)]
        with self.assertRaises(IncompleteComparison):paired_improvement(reference,candidate,allow_native_missing=True,scaffold_cv=True)
    def test_second_seed_requires_significant_final_neural_result(self):
        for learner in ("RF-ECFP4","LightGBM"):
            self.assertFalse(needs_second_seed(learner=learner,final_role="RETAIN",significant_improvement=True))
        self.assertTrue(needs_second_seed(learner="TabPFN",final_role="RETAIN",significant_improvement=True))
        self.assertFalse(needs_second_seed(learner="TabPFN",final_role="EXCLUDE",significant_improvement=True))
        self.assertFalse(needs_second_seed(learner="Chemprop-v2",final_role="RETAIN",significant_improvement=False))
        self.assertFalse(needs_second_seed(learner="TabPFN",final_role="RETAIN",significant_improvement=True,current_seed_count=2))
    def test_only_the_final_Chemprop_winner_gets_a_confirmation_plan(self):
        key="moleculeace::example.csv::y"
        predictions={key:{name:[dict(r,fit_population="retained",eligible=True) for r in rows(error)]
                            for name,error in (("RF-ECFP4",.4),("LightGBM-RDKit2D",.5),("Chemprop-v2",.1))}}
        record=dict(endpoint_key=key,dataset="MoleculeACE",target="y",status="SCREENED",
                    decision="RETAIN",best_baseline="Chemprop-v2")
        record.update({"RF-ECFP4_RAE":.4,"LightGBM-RDKit2D_RAE":.5,"Chemprop-v2_RAE":.1})
        plan,contrasts=baseline_confirmation_plan([record],predictions)
        self.assertEqual(len(plan),1)
        self.assertEqual(plan[0]["confirmation_seed"],20261026)
        self.assertFalse(plan[0]["task_roster_reselection"])
        record["best_baseline"]="RF-ECFP4"
        self.assertEqual(baseline_confirmation_plan([record],predictions),([],[]))
    def test_real_training_rollback_is_an_independent_neural_exception(self):
        self.assertTrue(needs_second_seed(learner="Chemprop-v2",final_role="UNRESOLVED",
                                         significant_improvement=False,rollback_lost_samples=True))
        self.assertFalse(needs_second_seed(learner="LightGBM",final_role="RETAIN",
                                          significant_improvement=False,rollback_lost_samples=True))

if __name__=="__main__":unittest.main()
