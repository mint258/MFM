"""Original-population binding tests avoid real outputs and mock all numeric report functions."""
import unittest
from unittest.mock import patch
from workflows.benchmark_evaluation.confirmation_consumer import summarize_confirmation
from workflows.benchmark_evaluation.selection import IncompleteComparison
class ConfirmationConsumerTests(unittest.TestCase):
    def rows(self):
        return [dict(evaluation_id="0",full_inchikey="FULL-KEY",y_true=2.,prediction=1.,training_mean=0.)]
    def test_only_candidate_second_seed_receives_new_statistics(self):
        primary=self.rows();candidate=self.rows();candidate[0]["prediction"]=1.5
        with patch("workflows.benchmark_evaluation.confirmation_consumer.single_model_statistics",
                   return_value=dict(MAE=.5,RAE=.25,n_test_rows=1)) as stats:
            with patch("workflows.benchmark_evaluation.confirmation_consumer.paired_improvement",
                       return_value=dict(significant_improvement=False)) as paired:
                result=summarize_confirmation(primary,candidate,{"CONTROL":primary},sources=[dict(job=1)])
        self.assertEqual(stats.call_args.args[0],candidate)
        self.assertEqual(stats.call_count,1);self.assertEqual(paired.call_count,1)
        self.assertFalse(result["primary_scores_recomputed"])
    def test_original_TRAIN_mean_label_or_population_changes_fail_before_statistics(self):
        for field,value in (("training_mean",1.),("y_true",3.),("evaluation_id","OTHER")):
            second=self.rows();second[0][field]=value
            with patch("workflows.benchmark_evaluation.confirmation_consumer.single_model_statistics") as stats:
                with self.assertRaises(IncompleteComparison):
                    summarize_confirmation(self.rows(),second,{},sources=[dict(job=1)])
                stats.assert_not_called()
    def test_changed_native_missingness_is_a_source_error(self):
        second=self.rows();second[0]["prediction"]=None
        with self.assertRaises(IncompleteComparison):
            summarize_confirmation(self.rows(),second,{},sources=[dict(job=1)])


class BlindConfirmationBindingTests(unittest.TestCase):
    def reference(self):
        return [dict(dataset="ASAP_Polaris2025",task="HLM",endpoint_key="asap_polaris2025::HLM",record_id=str(i),
            evaluation_id=str(i),full_inchikey="KEY-"+str(i),y_true=float(i+1),prediction=0.,training_mean=0.,
            fit_population="retained",eligible=(i!=2)) for i in range(3)]
    def native(self,job,mean=2.):
        return [dict(row,prediction=None if i==1 else 1.5,training_mean=mean,native_producer_job=job,
            primary_source_job=job,native_source_folder="/native/job_"+job,learner="TabPFN",feature_group="Pprime")
            for i,row in enumerate(self.reference()[:2])]
    def test_second_seed_and_c1_controls_bind_same_predeclared_blind_population_once(self):
        primary=self.native("100");candidate=self.native("200")
        with patch("workflows.benchmark_evaluation.confirmation_consumer.single_model_statistics",return_value=dict(MAE=.5,RAE=.25)) as stats:
            with patch("workflows.benchmark_evaluation.confirmation_consumer.paired_improvement",return_value=dict(significant_improvement=False)) as paired:
                result=summarize_confirmation(primary,candidate,
                    {"B1_LightGBM_RDKit2D":self.reference(),"D_SAME_LEARNER":self.native("300")},
                    sources=[dict(job=200)],dataset="ASAP_Polaris2025",blind_reference=self.reference())
        self.assertEqual(stats.call_count,1)
        available={row["record_id"]:row for row in stats.call_args.args[0]}
        self.assertEqual(set(available),{"0","2"});self.assertEqual(available["2"]["prediction"],2.)
        self.assertEqual(len(paired.call_args_list[1].args[0]),3)
        self.assertFalse(result["primary_scores_recomputed"])
        self.assertEqual(result["blind_fallback_binding"]["second_seed"]["blind_outside_fallback_rows_bound_by_report"],1)
        self.assertEqual(len(primary),2);self.assertEqual(len(candidate),2)
    def test_changed_actual_fit_mean_still_fails_before_new_seed_statistics(self):
        with patch("workflows.benchmark_evaluation.confirmation_consumer.single_model_statistics") as stats:
            with self.assertRaises(IncompleteComparison):
                summarize_confirmation(self.native("100"),self.native("200",3.),{},
                    sources=[dict(job=200)],dataset="ASAP_Polaris2025",blind_reference=self.reference())
        stats.assert_not_called()
