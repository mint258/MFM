"""New finalization state contracts use synthetic scores; no scientific outputs are accessed."""
import copy,unittest
from workflows.benchmark_evaluation.finalization import finalize_c1,finalize_baseline_confirmations
from workflows.benchmark_evaluation.selection import IncompleteComparison
class FinalizationTests(unittest.TestCase):
    def fixtures(self):
        row=dict(endpoint_key="E",feature_group="D",learner="TabPFN",model_seed=20261025,
            MAE=.4,RAE=.5,completed_seeds=1,frozen_B1_role="RETAIN",status="PRIMARY_REPORTED")
        plan=dict(endpoint_key="E",feature_group="D",learner="TabPFN",frozen_B1_role="RETAIN",
            reason="FINAL_SIGNIFICANT_IMPROVEMENT",triggering_comparison="B1_LightGBM_RDKit2D")
        evidence=dict(status="COMPLETED",model_seed=20261026,split_and_statistics_seed=20261025,
            sources=[dict(job=123)],statistics=dict(MAE=.6,RAE=.7,n_test_rows=20),
            comparisons=[dict(comparison="B1_LightGBM_RDKit2D",significant_improvement=True)])
        return row,plan,evidence
    def test_both_seeds_reported_without_recomputing_or_overwriting_primary_score(self):
        row,plan,native=self.fixtures();before=copy.deepcopy(row);key=("E","D","TabPFN")
        table,comparisons=finalize_c1([row],[plan],{key:native})
        self.assertEqual(row,before);self.assertEqual([r["RAE"] for r in table],[.5,.7])
        self.assertEqual([r["model_seed"] for r in table],[20261025,20261026])
        self.assertEqual(table[0]["completed_seeds"],2)
        self.assertIn("REPRODUCED",table[0]["confirmation_status"])
    def test_second_seed_nonreplication_is_disclosed_without_changing_frozen_role(self):
        row,plan,native=self.fixtures();native["comparisons"][0]["significant_improvement"]=False
        table,_=finalize_c1([row],[plan],{("E","D","TabPFN"):native})
        self.assertEqual(table[1]["frozen_B1_role"],"RETAIN")
        self.assertEqual(table[0]["confirmation_status"],"SECOND_SEED_DID_NOT_REPRODUCE_SIGNIFICANCE")
    def test_pending_or_extra_confirmation_cannot_make_final_table(self):
        row,plan,native=self.fixtures()
        with self.assertRaises(IncompleteComparison):finalize_c1([row],[plan],{})
        with self.assertRaises(IncompleteComparison):finalize_c1([row],[],{("E","D","TabPFN"):native})
    def test_actual_native_failure_remains_explicit_unresolved(self):
        row,plan,_=self.fixtures()
        native=dict(status="UNRESOLVED",model_seed=20261026,split_and_statistics_seed=20261025,
            sources=[dict(job=123)],native_failure_reason="actual two failed fits")
        table,_=finalize_c1([row],[plan],{("E","D","TabPFN"):native})
        self.assertEqual(len(table),1);self.assertEqual(table[0]["completed_seeds"],1)
        self.assertEqual(table[0]["confirmation_status"],"SECOND_SEED_UNRESOLVED_NATIVE_FAILURE")
    def test_traditional_ML_is_never_confirmed_with_an_extra_seed(self):
        row,plan,native=self.fixtures();row["learner"]=plan["learner"]="LightGBM"
        with self.assertRaises(IncompleteComparison):
            finalize_c1([row],[plan],{("E","D","LightGBM"):native})
    def test_original_statistics_seed_cannot_change(self):
        row,plan,native=self.fixtures();native["split_and_statistics_seed"]=20261026
        with self.assertRaises(IncompleteComparison):
            finalize_c1([row],[plan],{("E","D","TabPFN"):native})
    def test_unplanned_one_seed_rows_are_copied_without_new_numeric_work(self):
        row,_,_=self.fixtures();table,_=finalize_c1([row],[],{})
        self.assertEqual(table[0]["RAE"],.5);self.assertEqual(table[0]["completed_seeds"],1)
    def test_required_baseline_sample_redo_does_not_reselect_roster(self):
        _,_,native=self.fixtures()
        plan=dict(endpoint_key="E",model="Chemprop-v2",
            reason="SOURCE_BINDING_ERROR_REQUIRED_REDO_OF_TRAINED_1H_SAMPLES")
        result=finalize_baseline_confirmations([dict(endpoint_key="E",decision="DROP")],[plan],
                                              {("E","Chemprop-v2"):native})
        self.assertEqual(result[0]["frozen_B1_decision"],"DROP")
        self.assertEqual(result[0]["completed_seeds"],2)
