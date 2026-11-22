"""Selective readers use tiny new Parquet fixtures; existing scientific scores are never accessed."""
import json,tempfile,unittest
from pathlib import Path
import pyarrow as pa
import pyarrow.parquet as pq
from workflows.benchmark_evaluation.confirmation_io import selected_predictions
from workflows.benchmark_evaluation.selection import IncompleteComparison
class SelectiveConfirmationIOTests(unittest.TestCase):
    def fixture(self,root,kind="B1"):
        (root/"manifest.json").write_text(json.dumps(dict(job="700",status="CLOSED")))
        rows=[dict(dataset="Synthetic",task=task,record_id=task+str(atom),full_inchikey="ORIGINAL-"+task,
            y_true=float(atom+1),prediction=float(atom+1)+.1,training_mean=0.,
            model="Chemprop-v2",fit_population="retained",retained=True,domain_eligible=True)
            for task in ("keep","unrelated") for atom in range(2)]
        if kind=="C1":
            rows=[{k:v for k,v in row.items() if k not in {"dataset","model","fit_population"}} for row in rows]
        pq.write_table(pa.Table.from_pylist(rows),root/"predictions.parquet")
        return rows
    def inputs(self):
        catalog=[dict(endpoint_key="synthetic::"+task,dataset="Synthetic",target=task) for task in ("keep","unrelated")]
        query=[dict(endpoint_key="synthetic::keep",dataset="Synthetic",producer_task="keep",model="Chemprop-v2")]
        return catalog,query
    def test_only_requested_task_keeps_all_original_atom_or_repeat_observations(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);self.fixture(root);catalog,query=self.inputs()
            result,source=selected_predictions(root,catalog,query,kind="B1",spec={},native_state="COMPLETED",expected_job=700)
            rows=result[("synthetic::keep","Chemprop-v2")]
            self.assertEqual(len(rows),2);self.assertEqual({r["record_id"] for r in rows},{"keep0","keep1"})
            self.assertNotIn(("synthetic::unrelated","Chemprop-v2"),result)
            self.assertFalse(source["primary_scores_recomputed"])
    def test_C1_legacy_dataset_column_uses_its_actual_producer_spec(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);self.fixture(root,"C1");catalog,query=self.inputs()
            spec=dict(dataset="Synthetic",feature_group="D",learner="TabPFN")
            result,_=selected_predictions(root,catalog,query,kind="C1",spec=spec,native_state="COMPLETED",expected_job=700)
            self.assertEqual(len(result[("synthetic::keep","D","TabPFN")]),2)
    def test_live_or_mismatched_native_source_is_rejected_before_reading_predictions(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);self.fixture(root);catalog,query=self.inputs()
            with self.assertRaises(IncompleteComparison):
                selected_predictions(root,catalog,query,kind="B1",spec={},native_state="RUNNING",expected_job=700)
            with self.assertRaises(IncompleteComparison):
                selected_predictions(root,catalog,query,kind="B1",spec={},native_state="COMPLETED",expected_job=701)
    def test_wrong_original_endpoint_cannot_be_assigned_to_a_query(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);self.fixture(root);catalog,query=self.inputs();query[0]["endpoint_key"]="synthetic::unrelated"
            with self.assertRaises(IncompleteComparison):
                selected_predictions(root,catalog,query,kind="B1",spec={},native_state="COMPLETED",expected_job=700)

    def test_each_task_keeps_only_its_registered_control_models(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);original=self.fixture(root);catalog,query=self.inputs()
            rows=[dict(row,model=model) for row in original for model in ("Chemprop-v2","RF-ECFP4","LightGBM-RDKit2D")]
            pq.write_table(pa.Table.from_pylist(rows),root/"predictions.parquet")
            query[0].pop("model");query[0]["models"]=["Chemprop-v2","RF-ECFP4"]
            query.append(dict(endpoint_key="synthetic::unrelated",dataset="Synthetic",producer_task="unrelated",models=["LightGBM-RDKit2D"]))
            result,_=selected_predictions(root,catalog,query,kind="B1",spec={},native_state="COMPLETED",expected_job=700)
            self.assertEqual(set(result),{("synthetic::keep","Chemprop-v2"),("synthetic::keep","RF-ECFP4"),("synthetic::unrelated","LightGBM-RDKit2D")})
    def test_actual_array_parent_and_element_are_required(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);self.fixture(root);catalog,query=self.inputs()
            (root/"manifest.json").write_text(json.dumps(dict(job="700",array_job="600",array_index="1")))
            with self.assertRaises(IncompleteComparison):
                selected_predictions(root,catalog,query,kind="B1",spec={},native_state="COMPLETED",expected_job=700,array_parent=600,array_index=0)

    def test_original_control_task_aliases_resolve_by_frozen_endpoint_not_another_methods_spelling(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);self.fixture(root);catalog,query=self.inputs()
            query[0]["producer_task"]="alias/keep"
            def resolve(catalog,dataset,task):return "synthetic::"+task.removeprefix("alias/")
            with patch("workflows.benchmark_evaluation.confirmation_io.resolve_endpoint",side_effect=resolve):
                result,_=selected_predictions(root,catalog,query,kind="B1",spec={},native_state="COMPLETED",expected_job=700)
            self.assertEqual(len(result[("synthetic::keep","Chemprop-v2")]),2)
