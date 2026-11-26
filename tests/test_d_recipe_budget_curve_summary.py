"""New population/trajectory joins and one-time primary score consumption."""
import csv
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools.d_recipe import budget_curve_summary as summary


class DBudgetSummaryTests(unittest.TestCase):
    def test_population_and_trajectory_are_not_interchangeable(self):
        c = dict(condition="D", arm="9M-D-final", samples=9000000, seed=0)
        self.assertEqual(summary.source_population("9M-D-final", c)[-1], 9000000)
        with self.assertRaisesRegex(ValueError, "differs"):
            summary.source_population("9M-D-R0", c)
        c.update(molecule_scaling=True, scaling_authority=summary.AUTHORITY,
                 d_explicit_molecule_selection=dict(P_arm="T5"))
        self.assertEqual(summary.source_population("D-final-P-T5", c),
                         (3000000, 6000000, 9000000))
        with self.assertRaisesRegex(ValueError, "differs"):
            summary.source_population("D-final-P-T6", c)

    def test_fixed_VAL_half_million_rows_and_subset_deltas_use_original_table(self):
        # Load the real P table function; its already-tested bootstrap algebra
        # is supplied here without NumPy because this fixture has no draws.
        module = summary.original_report()
        metrics = lambda n: {name: dict(mean=n, ci_lower=n, ci_upper=n)
                             for name in ("R1", "R3")}
        cache = dict(sources={p: dict(run=p) for p in summary.POPULATIONS}, VAL={}, points={})
        for pop in cache["sources"]:
            cache["VAL"][pop] = [dict(samples=500000, family="graph_2d", loss=.123, kind="VAL")]
        for pop, mean in (("9M-D-R0", .1), ("9M-D-final", .2), ("D-final-P-T5", .15)):
            cache["points"][pop + ":3000000"] = dict(run=pop, source_run=pop, metrics=metrics(mean))
        def delta(a, b):
            return dict(delta=a["mean"]-b["mean"], ci_lower=-.1, ci_upper=.1)
        with patch.object(module, "paired_delta", side_effect=delta):
            rows = summary.table_rows(cache, module)
        half = next(r for r in rows if r["arm"] == "9M-D-final" and r["samples"] == 500000)
        self.assertEqual(half["source_run"], "9M-D-final")
        self.assertEqual(half["VAL_loss_graph_2d"], .123)
        self.assertEqual(half["R3_mean"], "")
        full = next(r for r in rows if r["arm"] == "9M-D-final" and r["samples"] == 3000000)
        sub = next(r for r in rows if r["arm"] == "D-final-P-T5" and r["samples"] == 3000000)
        self.assertAlmostEqual(full["R3_final_minus_R0_delta"], .1)
        self.assertAlmostEqual(sub["R3_subset_minus_full_delta"], -.05)
        self.assertEqual(sub["population"], "T5")
        self.assertNotIn("R3_T2_minus_T1_delta", sub)

    def test_closed_scores_and_VAL_are_consumed_once_and_foreign_point_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo, runs = root / "repo", root / "runs"
            def put(path, value):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(value))
                return str(path)
            tasks = ["task" + str(i) for i in range(7)]
            put(repo / "configs/p_recipe/protocol.json", dict(scored_tasks=tasks))
            spec = dict(authority=summary.AUTHORITY, sources={}, scored_tasks=tasks,
                        cache=str(runs / "primary.json"), readouts=[])
            for arm in summary.NATIVE_ARMS:
                output = runs / arm
                source = dict(arm=arm, condition="D", samples=9000000, seed=0, run=arm,
                              output=str(output), d_recipe=dict(scientific_binding=dict(arm=arm)))
                spec["sources"][arm] = put(output / "configuration.json", source)
                put(output / "summary.json", dict(run=arm, samples=9000000,
                    status="COMPLETE", statistics_complete=True))
                put(output / "readout/scores.json", dict(marker=arm))
            consumed, vals = [], []
            def metrics(value):
                consumed.append(value["marker"])
                return {name: dict(included_tasks=tasks) for name in ("R1", "R3")}
            def val(c):
                vals.append(c["run"])
                return [dict(samples=n, family=f, loss=.1, kind="VAL")
                        for n in range(500000, 9000001, 500000) for f in summary.FAMILIES]
            module = SimpleNamespace(REPO="original_P", metrics=metrics, val_rows=val,
                                     table_rows=lambda c: [])
            with patch.object(summary, "REPO", repo), patch.object(summary, "RUNS", runs):
                first = summary.aggregate(spec, module=module)
                self.assertEqual(first["closed_points"], 2)
                self.assertEqual(first["status"], "IN_PROGRESS")
                self.assertEqual(len(first["missing_readouts"]), 16)
                # Scores disappear after first primary consumption: a second
                # aggregation must use its cache and never reopen them.
                for arm in summary.NATIVE_ARMS:
                    (runs / arm / "readout/scores.json").unlink()
                summary.aggregate(spec, module=module)
                self.assertCountEqual(consumed, summary.NATIVE_ARMS)
                self.assertCountEqual(vals, summary.NATIVE_ARMS)
                self.assertEqual(module.REPO, "original_P")
                bad = dict(source_run="some_3M_screening_run", samples=3000000,
                           source_training_budget=3000000, layer=6, representation="H0",
                           descriptive_only=True)
                filename = put(runs / "bad.json", bad)
                spec["readouts"] = [dict(population="9M-D-final", samples=3000000,
                                         configuration=filename)]
                with self.assertRaisesRegex(ValueError, "trajectory differs"):
                    summary.aggregate(spec, module=module)


if __name__ == "__main__":
    unittest.main()

