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
