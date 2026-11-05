"""Small deterministic algorithm tests; no original data or chemistry is opened."""
import unittest

from selection import conformer_orders, select_fill


def row(key, position, energy=0):
    return {"candidate_key": key, "conformer_id": key, "position": position, "energy": energy}


def distance(left, right):
    return abs(left["position"] - right["position"])


class SelectionTests(unittest.TestCase):
    def test_preserves_existing_and_threshold_boundary(self):
        selected = select_fill([row("old", 0)], [row("new", .5)], 2, distance)
        self.assertEqual([item["candidate_key"] for item in selected], ["old", "new"])
        self.assertFalse(selected[-1]["below_dedup_threshold"])

    def test_fallback_chooses_farthest_then_marks(self):
        selected = select_fill([row("old", 0)], [row("near", .1), row("far", .4)], 2, distance)
        self.assertEqual(selected[-1]["candidate_key"], "far")
        self.assertTrue(selected[-1]["below_dedup_threshold"])

    def test_each_fallback_recomputes_minimum_distance(self):
        selected = select_fill([row("old", 0)], [row("a", .4), row("b", .35), row("c", -.3)], 3, distance)
        self.assertEqual([item["candidate_key"] for item in selected], ["old", "a", "c"])

    def test_does_not_copy_when_candidates_exhausted(self):
        selected = select_fill([], [row("only", 0)], 3, distance)
        self.assertEqual(len(selected), 1)

    def test_identical_geometries_are_distinct_generated_candidates(self):
        selected = select_fill([], [row("one", 0), row("two", 0)], 2, distance)
        self.assertTrue(selected[1]["below_dedup_threshold"])
        self.assertNotEqual(selected[0]["candidate_key"], selected[1]["candidate_key"])

    def test_duplicate_candidate_identity_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "DUPLICATE_CANDIDATE_ID"):
            select_fill([row("same", 0)], [row("same", 2)], 2, distance)

    def test_nan_rmsd_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "NONFINITE_RMSD"):
            select_fill([row("old", 0)], [row("new", 1)], 2, lambda left, right: float("nan"))

    def test_orders_are_permutations_and_random_order_is_input_invariant(self):
        rows = [row("a", 0, 2), row("b", 1, 1), row("c", 2, 3)]
        orders = conformer_orders(rows, distance, "mol", "pm7", 20261025)
        reverse = conformer_orders(list(reversed(rows)), distance, "mol", "pm7", 20261025)
        self.assertEqual(orders, reverse)
        self.assertEqual(orders["energy"], ["b", "a", "c"])
        for sequence in orders.values():
            self.assertEqual(set(sequence), {"a", "b", "c"})

    def test_diversity_starts_at_lowest_energy_then_maxmin(self):
        rows = [row("low", 0, -10), row("near", 1, 0), row("far", 3, 1)]
        orders = conformer_orders(rows, distance, "mol", "uff_sprime", 1)
        self.assertEqual(orders["diversity"], ["low", "far", "near"])

    def test_order_ties_are_deterministic(self):
        rows = [row("z", 1, 0), row("a", -1, 0), row("low", 0, -1)]
        self.assertEqual(conformer_orders(rows, distance, "m", "pm7", 1)["diversity"], ["low", "a", "z"])


if __name__ == "__main__":
    unittest.main()
