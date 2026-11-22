"""Unit tests for the newly written final reporting/binding logic only."""
import unittest
from workflows.benchmark_evaluation.reporting import (
    resolve_endpoint, normalize_prediction, primary_rows, fold_presence,
    filtered_labeled_count, close_endpoint, diagnostic_metrics, ClosedPredictionConsumer, resolve_array_run,
)
from workflows.benchmark_evaluation.selection import BASELINES, IncompleteComparison

class ReportingTests(unittest.TestCase):
    def candidate(self, dataset="Biogen_ADME"):
        return {"dataset": dataset, "endpoint_key": dataset.lower()+"::test", "target": "test"}
    def predictions(self, dataset="Biogen_ADME"):
        return {model: [
            {"evaluation_id": str(i), "record_id": str(i), "dataset": dataset,
             "y_true": float(i%2*2), "prediction": float(i%2*2)+error,
             "training_mean": 1., "full_inchikey": "molecule_"+str(i//2),
             "eligible": True, "fit_population": population}
            for population in ("retained", "full") for i in range(40)]
            for model,error in zip(BASELINES,(.2,.4,.6))}
    def test_source_path_is_bound_against_exact_active_catalog(self):
        rows=[{"dataset":"MoleculeACE","endpoint_key":"moleculeace::task.csv::y","target":"y"}]
        self.assertEqual(resolve_endpoint(rows,"MoleculeACE","raw/task.csv"),rows[0]["endpoint_key"])
        with self.assertRaises(IncompleteComparison):resolve_endpoint(rows,"MoleculeACE","raw/other.csv")
    def test_tdc_original_files_and_endpoint_name_share_original_identity(self):
        rows=[{"dataset":"TDC_ADMET","endpoint_key":"tdc_admet::example::Y","target":"Y"}]
        self.assertEqual(resolve_endpoint(rows,"TDC_ADMET","example"),rows[0]["endpoint_key"])
    def test_appendix_role_cannot_be_promoted_by_good_results(self):
        proof={"deferred_registry_full_inventory_verified":True,"deferred_endpoint_count":5}
        result,impact,tukey=close_endpoint(self.candidate(),self.predictions(),100,proof)
        self.assertEqual(result["registered_rule_decision"],"RETAIN")
        self.assertEqual(result["decision"],"APPENDIX")
        self.assertEqual(len(impact),12)
    def test_missing_full_fit_diagnostics_cannot_finalize_endpoint(self):
        values=self.predictions()
        values[BASELINES[1]]=[r for r in values[BASELINES[1]] if r["fit_population"]=="retained"]
        with self.assertRaises(IncompleteComparison):
            close_endpoint(self.candidate(),values,100,
                           {"deferred_registry_full_inventory_verified":True,"deferred_endpoint_count":5})
    def test_blind_outside_points_are_not_dropped(self):
        rows=[{"fit_population":"retained","eligible":False,"prediction":2.,"training_mean":2.}]
        self.assertEqual(len(primary_rows("ExpansionRx",rows)),1)
        rows[0]["prediction"]=1.
        with self.assertRaises(IncompleteComparison):primary_rows("ExpansionRx",rows)
    def test_cv_requires_all_original_fold_keys(self):
        with self.assertRaises(IncompleteComparison):fold_presence([{"repetition":0,"fold":0}])
        fold_presence([{"repetition":r,"fold":f} for r in range(5) for f in range(5)])
    def test_cv_repetition_cannot_be_lost_from_evaluation_id(self):
        catalog=[{"dataset":"Joung2020","target":"target","endpoint_key":"joung::target"}]
        row={"model":BASELINES[0],"record_id":"observation","dataset":"Joung2020","task":"target",
             "retained":True,"domain_eligible":True,"repetition":0,"fold":0}
        with self.assertRaises(IncompleteComparison):normalize_prediction(row,catalog)
        row["record_id"]+="::repeat:0"
        self.assertEqual(normalize_prediction(row,catalog)["evaluation_id"],row["record_id"])
    def test_filtered_count_uses_labeled_points_after_binding(self):
        self.assertEqual(filtered_labeled_count({"eligible_train":20,"eligible_test":9}),29)
        self.assertEqual(filtered_labeled_count({"filtered_total_labeled_points":31}),31)
        with self.assertRaises(IncompleteComparison):filtered_labeled_count({"n_retained_rows":400})
    def test_missing_prediction_cannot_shrink_metrics(self):
        with self.assertRaises(IncompleteComparison):
            diagnostic_metrics([{"y_true":1.,"prediction":float("nan"),"training_mean":0.,"full_inchikey":"A"}])
    def test_live_native_producer_cannot_be_read(self):
        with self.assertRaises(IncompleteComparison):
            ClosedPredictionConsumer([]).add_run("/does/not/exist","RUNNING")
    def test_C1_cannot_enter_screen_population(self):
        with self.assertRaises(IncompleteComparison):
            normalize_prediction({"model":"C1-LightGBM-D"},[])
    def test_unfinished_baseline_cannot_silently_freeze_an_UNRESOLVED_roster(self):
        catalog=[dict(endpoint_key="synthetic::"+str(i),dataset="Synthetic",target=str(i),
                      level="molecule",split_policy="OFFICIAL") for i in range(96)]
        with self.assertRaises(IncompleteComparison):
            ClosedPredictionConsumer(catalog).screen_once({})
    def test_explicit_final_failure_reason_is_required_for_an_UNRESOLVED_endpoint(self):
        catalog=[dict(endpoint_key="synthetic::"+str(i),dataset="Synthetic",target=str(i),
                      level="molecule",split_policy="OFFICIAL") for i in range(96)]
        reasons={row["endpoint_key"]:"TWO_CONSECUTIVE_NATIVE_FAILURES" for row in catalog}
        screen,impact,tukey=ClosedPredictionConsumer(catalog).screen_once({},reasons)
        self.assertEqual(len(screen),96)
        self.assertTrue(all(row["decision"]=="UNRESOLVED" for row in screen))
    def test_array_source_uses_original_array_index_and_actual_child_job(self):
        records=[("/a/job_200",dict(job="200",array_job="100",array_index="0")),
                 ("/a/job_201",dict(job="201",array_job="100",array_index="1"))]
        self.assertEqual(str(resolve_array_run(records,100,1)).replace(chr(92),"/"),"/a/job_201")
    def test_duplicate_array_metadata_cannot_double_count_a_repetition(self):
        record=("/a/job_200",dict(job="200",array_job="100",array_index="0"))
        with self.assertRaises(IncompleteComparison):resolve_array_run([record,record],100,0)
    def test_complete_active_catalog_is_required_for_final_screen(self):
        with self.assertRaises(IncompleteComparison):
            ClosedPredictionConsumer([]).screen_once({})

if __name__ == "__main__":
    unittest.main()

class NativePlanSourceTests(unittest.TestCase):
    def test_original_array_children_bind_one_parent_without_changing_labels(self):
        from workflows.benchmark_evaluation.reporting import bind_native_origin,source_identity
        original=dict(y_true=3.0,record_id="ORIGINAL",full_inchikey="ORIGINAL-KEY")
        first=bind_native_origin(original,701,"/runs/job_701",700)
        second=bind_native_origin(original,702,"/runs/job_702",700)
        source=source_identity([first,second])
        self.assertEqual(source["primary_source_job"],"700")
        self.assertEqual(source["primary_native_jobs"],["701","702"])
        self.assertEqual(original,dict(y_true=3.0,record_id="ORIGINAL",full_inchikey="ORIGINAL-KEY"))
    def test_absent_or_conflicting_native_origins_cannot_prepare_a_conditional_plan(self):
        from workflows.benchmark_evaluation.reporting import bind_native_origin,source_identity
        with self.assertRaises(IncompleteComparison):source_identity([dict(y_true=1.)])
        rows=[bind_native_origin({},job,"/runs/"+str(job)) for job in (701,702)]
        with self.assertRaises(IncompleteComparison):source_identity(rows)
    def test_missing_actual_native_job_identity_is_rejected(self):
        from workflows.benchmark_evaluation.reporting import bind_native_origin
        with self.assertRaises(IncompleteComparison):bind_native_origin({},None,"/runs/unknown")
