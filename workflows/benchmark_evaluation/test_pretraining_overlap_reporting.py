"""Synthetic final-export provenance; real closed model data are never consumed."""
import unittest
from .pretraining_overlap_reporting import annotate_overlap_status,OVERLAP_FIELDS

class PretrainingOverlapReportingTests(unittest.TestCase):
    def test_preserves_every_primary_confirmation_and_unresolved_cell(self):
        marker=object()
        rows=[dict(learner="TabPFN",model_seed=20261025,status="PRIMARY_REPORTED",RAE=marker),
              dict(learner="TabPFN",model_seed=20261026,status="SECOND_SEED_NONREPRODUCED",RAE=float("nan")),
              dict(learner="LightGBM",model_seed=20261025,status="UNRESOLVED",endpoint_key="pKa"),
              dict(learner="TabPFN",model_seed=20261025,status="UNRESOLVED",completed_seeds=0)]
        actual=annotate_overlap_status(rows)
        self.assertEqual(len(actual),len(rows))
        for original,new in zip(rows,actual):
            self.assertIsNot(original,new)
            self.assertEqual(set(new)-set(original),set(OVERLAP_FIELDS))
            for key,value in original.items():self.assertIs(new[key],value)
    def test_inputs_and_nested_native_provenance_are_not_mutated(self):
        native={"native_job":"4538163","original_fold_sources":["4537812"]}
        row=dict(learner="TabPFN",confirmation_sources=native);before=dict(row)
        result=annotate_overlap_status([row])
        self.assertEqual(row,before)
        self.assertIs(result[0]["confirmation_sources"],native)
        self.assertEqual(annotate_overlap_status([]),[])
    def test_unchecked_is_explicit_and_cannot_be_confused_with_no_overlap(self):
        tab,lgbm=annotate_overlap_status([{"learner":"TabPFN"},{"learner":"LightGBM"}])
        self.assertEqual(tab["pretraining_TEST_overlap_check"],"未检查")
        self.assertEqual(tab["pretraining_molecule_inventory_status"],"NOT_OBTAINED_IN_THIS_BENCHMARK")
        self.assertIs(tab["pretraining_overlap_exclusion_applied"],False)
        self.assertEqual(lgbm["pretraining_TEST_overlap_check"],"NOT_APPLICABLE_NO_PRETRAINING")
        self.assertIs(lgbm["pretraining_overlap_exclusion_applied"],False)
    def test_unknown_learners_and_existing_assessments_cannot_be_silently_overwritten(self):
        for row in (None,{},{"learner":"RF"},{"learner":"Chemprop-v2"},{"learner":None}):
            with self.assertRaises(ValueError):annotate_overlap_status([row])
        for field in OVERLAP_FIELDS:
            with self.assertRaises(ValueError):annotate_overlap_status([{"learner":"TabPFN",field:"EXISTING_REAL_ASSESSMENT"}])
