"""Tests cover new population binding, decisions, and scaffold assignment only."""
import unittest
import numpy as np
from workflows.benchmark_evaluation.selection import (
    BASELINES, IncompleteComparison, align_predictions, decide_endpoint,
    paired_bootstrap, scaffold_folds, tukey_cv,
)

PROOF = {"deferred_registry_full_inventory_verified": True, "deferred_endpoint_count": 5}

def predictions(errors=(.2, .4, .6)):
    values = {}
    for model, error in zip(BASELINES, errors):
        values[model] = [
            {"evaluation_id": str(index), "y_true": float(index % 2 * 2),
             "training_mean": 1., "full_inchikey": "molecule_" + str(index // 2),
             "prediction": float(index % 2 * 2) + error}
            for index in range(80)
        ]
    return values

class SelectionTests(unittest.TestCase):
    def test_missing_baseline_cannot_make_a_decision(self):
        data = predictions(); data.pop(BASELINES[-1])
        with self.assertRaises(IncompleteComparison):
            decide_endpoint(data, n_filtered_labeled_points=100, scope_proof=PROOF)

    def test_scope_proof_is_required(self):
        with self.assertRaises(IncompleteComparison):
            decide_endpoint(predictions(), n_filtered_labeled_points=100, scope_proof={})

    def test_populations_are_not_silently_intersected(self):
        data = predictions(); data[BASELINES[1]].pop()
        with self.assertRaises(IncompleteComparison): align_predictions(data)

    def test_missing_molecular_identity_is_not_a_group(self):
        data = predictions(); data[BASELINES[0]][0]['full_inchikey'] = None
        with self.assertRaises(IncompleteComparison): align_predictions(data)

    def test_training_reference_must_be_the_same(self):
        data = predictions(); data[BASELINES[1]][0]["training_mean"] = 0.
        with self.assertRaises(IncompleteComparison): align_predictions(data)

    def test_record_order_does_not_change_pairing(self):
        data = predictions(); expected = paired_bootstrap(data)
        data[BASELINES[1]].reverse()
        self.assertEqual(expected, paired_bootstrap(data))

    def test_molecule_groups_preserve_repeated_atom_rows(self):
        result = paired_bootstrap(predictions())
        self.assertEqual(result["n_test_rows"], 80)
        self.assertEqual(result["n_test_molecules"], 40)
        self.assertAlmostEqual(result["RAE"][0], .2)
        self.assertAlmostEqual(result["paired_best_worst_bootstrap_SE"], 0.)

    def test_insufficient_signal_excludes(self):
        result = decide_endpoint(predictions((.95, 1., 1.1)),
                                 n_filtered_labeled_points=100, scope_proof=PROOF)
        self.assertEqual(result["decision"], "EXCLUDE")

    def test_insufficient_discrimination_goes_to_appendix(self):
        result = decide_endpoint(predictions((.4, .405, .41)),
                                 n_filtered_labeled_points=100, scope_proof=PROOF)
        self.assertEqual(result["decision"], "APPENDIX")

    def test_other_tasks_are_retained(self):
        result = decide_endpoint(predictions(), n_filtered_labeled_points=100, scope_proof=PROOF)
        self.assertEqual(result["decision"], "RETAIN")

    def test_too_few_filtered_points_go_to_appendix(self):
        result = decide_endpoint(predictions(), n_filtered_labeled_points=29, scope_proof=PROOF)
        self.assertEqual(result["reason"], "FEWER_THAN_30_FILTERED_LABELED_POINTS")

    def test_scaffold_cv_is_5_by_5_disjoint_and_reproducible(self):
        groups = ["scaffold_" + str(index // 3) for index in range(60)]
        first = list(scaffold_folds(groups)); second = list(scaffold_folds(groups))
        self.assertEqual(len(first), 25)
        for left, right in zip(first, second):
            rep, fold, train, test = left
            np.testing.assert_array_equal(test, right[3])
            self.assertFalse(set(np.asarray(groups)[train]) & set(np.asarray(groups)[test]))
        for rep in range(5):
            np.testing.assert_array_equal(
                np.sort(np.concatenate([row[3] for row in first if row[0] == rep])),
                np.arange(60),
            )

    def test_few_scaffolds_cannot_be_replaced_by_random_splitting(self):
        with self.assertRaises(IncompleteComparison): list(scaffold_folds(["acyclic"] * 40))

    def test_Tukey_requires_every_registered_fold(self):
        data = {name: {(0, 0): .5} for name in BASELINES}
        with self.assertRaises(IncompleteComparison): tukey_cv(data)

if __name__ == "__main__":
    unittest.main()
