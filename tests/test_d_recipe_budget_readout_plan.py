"""New D endpoint constraints and reversible use of the existing P builder."""
from pathlib import Path
from types import SimpleNamespace
import unittest

from tools.d_recipe.budget_readout_plan import AUTHORITY, make_readout, points


class DBudgetReadoutPlanTests(unittest.TestCase):
    def inputs(self):
        source = dict(condition="D", arm="9M-D-final", seed=0, samples=9000000,
                      run="D_final_9M", readout_store="original_native_store",
                      study_revision="d_recipe_20261120", reference_manifest="original_reference",
                      d_recipe=dict(scientific_binding=dict(samples=9000000)))
        closed = {arm: dict(arm=arm, seed=0, samples=9000000, run=arm,
                           status="COMPLETE", statistics_complete=True)
                  for arm in ("9M-D-R0", "9M-D-final")}
        summary = dict(run=source["run"], samples=9000000, status="COMPLETE", statistics_complete=True)
        closed["9M-D-final"]["run"] = source["run"]
        return source, closed, summary

    def test_native_and_molecule_points_exclude_original_endpoint(self):
        source, _, _ = self.inputs()
        self.assertEqual(points(source), tuple(n * 1000000 for n in range(1, 9)))
        source.update(molecule_scaling=True, scaling_authority=AUTHORITY,
                      d_explicit_molecule_selection=dict(P_arm="T5"))
        self.assertEqual(points(source), (3000000, 6000000))

    def test_actual_complete_sources_and_reversible_original_builder(self):
        source, closed, summary = self.inputs()
        original = lambda: [("T2", 1000000)]
        module = SimpleNamespace(expected_points=original, AUTHORITY="P", STORE=Path("P_store"))
        def builder(s, row, *, output_root, resolver):
            self.assertEqual(module.expected_points(), [(s["arm"], n) for n in points(s)])
            self.assertEqual(module.AUTHORITY, AUTHORITY)
            return dict(checkpoint=str(resolver(s, row["samples"])), samples=row["samples"],
                        source_training_budget=s["samples"], source_run=s["run"])
        module.make_configuration = builder
        kwargs = dict(closed_confirmations=closed, source_summary=summary,
                      source_configuration="original9M.json", output_root="/owned/readouts",
                      resolver=lambda c, n: "/actual/samples_" + str(n) + ".pt", module=module)
        c = make_readout(source, 3000000, **kwargs)
        self.assertEqual(c["source_training_budget"], 9000000)
        self.assertFalse(c["persist_features"])
        self.assertEqual(c["statistics_backend"], "ssh_cpu")
        self.assertIs(module.expected_points, original)
        self.assertEqual(module.AUTHORITY, "P")
        with self.assertRaisesRegex(ValueError, "reuse"):
            make_readout(source, 9000000, **kwargs)
        closed["9M-D-R0"]["status"] = "RUNNING"
        with self.assertRaisesRegex(ValueError, "finish first"):
            make_readout(source, 1000000, **kwargs)


if __name__ == "__main__":
    unittest.main()
