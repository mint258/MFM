"""Synthetic regression for native macro-pKa names and combined closed score reuse."""
import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from .reporting import resolve_endpoint
from .c1_reporting import C1ClosedConsumer,native_primary_row,primary_statistics
from .selection import IncompleteComparison

class PkaReportBindingTests(unittest.TestCase):
    def catalog(self):
        return [dict(dataset="pKahub",target=target,endpoint_key="pkahub::"+target,
                     level="atom" if target=="single_site_mechanism" else "molecule")
                for target in ("macro_acid","macro_base","single_site_mechanism")]
    def score(self,evaluation="SAMPL6_7_combined",n=2):
        return dict(dataset="pKahub",evaluation=evaluation,n_test_rows=str(n),n_train="10",
                    bootstrap_draws="1000",MAE="1.0",RAE="0.5",RAE_CI95_low="0.3",RAE_CI95_high="0.7")
    def raw(self,task,index=0):
        return dict(dataset="pKahub",task=task,record_id="SAMPL"+str(6+index)+"::SM1",
                    challenge="SAMPL"+str(6+index),rawdataID="raw"+str(index),
                    challenge_compound_id="SM1",full_inchikey="FULL-KEY-"+str(index),
                    y_true=float(2+index),prediction=float(1+index),training_mean=0.)
    def test_explicit_macro_aliases_preserve_canonical_and_atomic_targets(self):
        catalog=self.catalog()
        for native,target in (("acid","macro_acid"),("base","macro_base"),
                              ("macro_acid","macro_acid"),("macro_base","macro_base"),
                              ("single_site_mechanism","single_site_mechanism")):
            self.assertEqual(resolve_endpoint(catalog,"pKahub",native),"pkahub::"+target)
        for unknown in ("micro_acid","microspecies","multi_site","ACID"):
            with self.assertRaises(IncompleteComparison):resolve_endpoint(catalog,"pKahub",unknown)
    def test_aliases_are_scoped_and_cannot_select_absent_or_duplicate_endpoints(self):
        other=[dict(dataset="Other",target="acid",endpoint_key="other::acid")]
        self.assertEqual(resolve_endpoint(other,"Other","acid"),"other::acid")
        for rows in ([],self.catalog()+[dict(self.catalog()[0])],
                     [dict(dataset="pKahub",target="acid",endpoint_key="pkahub::unregistered_acid")]):
            with self.assertRaises(IncompleteComparison):resolve_endpoint(rows,"pKahub","acid")
    def test_native_prediction_keeps_task_labels_challenge_id_and_values(self):
        original=self.raw("acid");before=dict(original)
        spec=dict(dataset="pKahub",feature_group="Pprime",learner="TabPFN")
        actual=native_primary_row(original,self.catalog(),spec)
        self.assertEqual(original,before)
        for key,value in original.items():self.assertEqual(actual[key],value)
        self.assertEqual(actual["endpoint_key"],"pkahub::macro_acid")
        self.assertEqual(actual["task"],"acid")
    def test_all_six_native_arms_bind_metadata_and_predictions_without_fit(self):
        import pyarrow as pa
        import pyarrow.parquet as pq
        with tempfile.TemporaryDirectory() as temporary:
            consumer=C1ClosedConsumer(self.catalog())
            for index,(feature,learner) in enumerate((f,l) for f in ("D","Pprime","Pprime_plus_D")
                                                   for l in ("LightGBM","TabPFN")):
                job=100+index;folder=Path(temporary)/("job_"+str(job));folder.mkdir()
                (folder/"manifest.json").write_text(json.dumps(dict(job=str(job),status="CLOSED")))
                values=[self.raw(task,i) for task in ("acid","base") for i in (0,1)]
                pq.write_table(pa.Table.from_pylist(values),folder/"test_predictions.parquet")
                records=[dict(self.score(evaluation,n),task=task)
                         for task in ("acid","base")
                         for evaluation,n in (("SAMPL6_7_combined",2),("SAMPL6",1),("SAMPL7",1))]
                with (folder/"partial_results.csv").open("w",newline="") as stream:
                    writer=csv.DictWriter(stream,fieldnames=list(records[0]));writer.writeheader();writer.writerows(records)
                consumer.add_run(folder,"COMPLETED",dict(job=job,dataset="pKahub",feature_group=feature,learner=learner))
                for task,target in (("acid","macro_acid"),("base","macro_base")):
                    cell=("pkahub::"+target,feature,learner)
                    actual=consumer.predictions[cell]
                    self.assertEqual([r["record_id"] for r in actual],[self.raw(task,i)["record_id"] for i in (0,1)])
                    self.assertEqual({r["native_producer_job"] for r in actual},{str(job)})
                    self.assertEqual({r["task"] for r in actual},{task})
                    with patch("workflows.benchmark_evaluation.c1_reporting.single_model_statistics",
                               side_effect=AssertionError("closed pKa score must not be recomputed")):
                        scores=primary_statistics(actual,consumer.fit_metadata[cell])
                    self.assertEqual(scores["RAE"],.5)
                    self.assertEqual(scores["statistics_source"],"REUSED_CLOSED_CPU_PRODUCER_STATISTICS")
            self.assertEqual(len(consumer.predictions),12)
            self.assertFalse(consumer.unresolved_cells)
    def test_combined_primary_statistics_reuse_existing_value_without_bootstrap(self):
        values=[self.raw("acid",i) for i in (0,1)]
        diagnostics=[self.score("SAMPL6",1),self.score("SAMPL7",1),self.score()]
        with patch("workflows.benchmark_evaluation.c1_reporting.single_model_statistics",
                   side_effect=AssertionError("no second bootstrap")):
            actual=primary_statistics(values,diagnostics)
        self.assertEqual(actual["n_test_rows"],2)
        self.assertEqual((actual["RAE"],actual["RAE_CI95_low"],actual["RAE_CI95_high"]),(.5,.3,.7))
    def test_ambiguous_combined_or_other_official_statistics_still_fail_closed(self):
        values=[self.raw("acid",i) for i in (0,1)]
        with self.assertRaises(IncompleteComparison):primary_statistics(values,[self.score(),self.score()])
        generic=[dict(self.score(),dataset="Other"),dict(self.score(),dataset="Other")]
        with self.assertRaises(IncompleteComparison):primary_statistics(values,generic)
    def test_combined_score_must_cover_exact_native_population(self):
        values=[self.raw("acid",i) for i in (0,1)]
        with self.assertRaises(IncompleteComparison):
            primary_statistics(values,[self.score(n=3),self.score("SAMPL6",1),self.score("SAMPL7",1)])
