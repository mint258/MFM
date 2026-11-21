"""Synthetic checks of primary budget-curve aggregation and the final REPORT gate."""
import copy
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import budget_curve_report as report


class BudgetCurveReportTests(unittest.TestCase):
    def scores(self, mean=.2, offset=0.):
        value = dict(complete=True, bootstrap_samples=1000, bootstrap_defined=1000,
                     mean_normalized_improvement=mean, included_tasks=["task_b", "task_a"],
                     paired_bootstrap=dict(seed=20261025,
                                           values=[offset + i/10000 for i in range(1000)]))
        return dict(R1=copy.deepcopy(value), R3=copy.deepcopy(value))

    def point(self, arm, samples, mean):
        return dict(run=arm+"_readout", source_run=arm+"_9M",
                    metrics=report.metrics(self.scores(mean)))

    def test_original_draws_are_consumed_without_modifying_scores(self):
        scores = self.scores()
        original = copy.deepcopy(scores)
        actual = report.metrics(scores)
        self.assertEqual(scores, original)
        self.assertAlmostEqual(actual["R3"]["ci_lower"], .0024975)
        self.assertAlmostEqual(actual["R3"]["ci_upper"], .0974025)
        self.assertEqual(actual["R3"]["included_tasks"], ["task_a", "task_b"])

    def test_incomplete_undefined_or_changed_bootstrap_is_rejected(self):
        for change in (lambda v: v.update(complete=False),
                       lambda v: v.update(bootstrap_defined=999),
                       lambda v: v["paired_bootstrap"].update(values=[0.]*999),
                       lambda v: v["paired_bootstrap"].update(seed=1),
                       lambda v: v["paired_bootstrap"]["values"].__setitem__(5, None)):
            scores = self.scores()
            change(scores["R3"])
            with self.assertRaises(ValueError):
                report.metrics(scores)

    def test_pairing_uses_the_same_retained_draw_indices(self):
        a = report.metrics(self.scores(.4, 1.))["R3"]
        b = report.metrics(self.scores(.2, 0.))["R3"]
        delta = report.paired_delta(a,b)
        self.assertAlmostEqual(delta["delta"], .2)
        self.assertAlmostEqual(delta["ci_lower"], 1.)
        self.assertAlmostEqual(delta["ci_upper"], 1.)
        b["included_tasks"] = ["another_task"]
        with self.assertRaises(ValueError):
            report.paired_delta(a,b)

    def test_half_million_VAL_alignment_has_blank_unmeasured_readouts(self):
        cache = dict(points={"T2:1000000":self.point("T2",1000000,.3)},
                     VAL={"T2":[dict(samples=500000,family="energy",loss=.2,kind="VAL_fixed2000"),
                                dict(samples=1000000,family="energy",loss=.1,kind="VAL_fixed2000")]})
        rows = report.table_rows(cache)
        half = next(r for r in rows if r["samples"]==500000)
        full = next(r for r in rows if r["samples"]==1000000)
        self.assertEqual(half["R3_mean"], "")
        self.assertEqual(half["VAL_loss_energy"], .2)
        self.assertEqual(full["R3_mean"], .3)
        self.assertEqual(full["source_training_budget"], 9000000)
        self.assertNotIn("VAL_total",full)

    def test_tau_uses_own_9m_and_requires_no_later_gain_over_tau(self):
        points=[dict(samples=1000000,R3=.1),dict(samples=2000000,R3=.3),
                dict(samples=3000000,R3=.31),dict(samples=9000000,R3=.32)]
        result=report.plateau(points)
        self.assertEqual(result["earliest_observed_plateau_samples"],3000000)
        self.assertEqual(result["tau"],.016)
        with self.assertRaises(ValueError):
            report.plateau(points[:-1])

    def test_report_gate_requires_all_22_original_five_endpoints_and_plot(self):
        valid=dict(authority="docs/p_recipe/USER_DIRECTIVE_20261121.md",status="COMPLETE",
                   closed_readouts=22,expected_readouts=22,missing_readouts=[],
                   closed_original_9M_arms=["T1","T2","T4","T5","T6"],plot_complete=True,
                   closed_readout_points=report.expected_points())
        self.assertEqual(report.require_complete(valid),valid)
        for update in (dict(closed_readouts=21),dict(missing_readouts=[{}]),
                       dict(plot_complete=False),dict(closed_original_9M_arms=["T2"]),
                       dict(status="IN_PROGRESS"),dict(closed_readout_points=[["T2",1000000]])):
            changed=dict(valid,**update)
            with self.assertRaises(ValueError):
                report.require_complete(changed)

    def test_R3_fall_reports_original_decreasing_families_without_a_mechanism(self):
        points=[dict(samples=1000000,R3=.4),dict(samples=2000000,R3=.3)]
        vals=[dict(samples=1000000,family="energy",loss=.2),
              dict(samples=2000000,family="energy",loss=.1),
              dict(samples=1000000,family="charge",loss=.1),
              dict(samples=2000000,family="charge",loss=.2)]
        result=report.regressions(points,vals)
        self.assertEqual(result[0]["VAL_families_still_decreasing"],["energy"])
        self.assertFalse(result[0]["all_comparable_VAL_families_decreasing"])
        self.assertFalse(result[0]["mechanism_inferred"])
        self.assertFalse(result[0]["extra_diagnostics_performed"])

    def test_first_measurement_uses_actual_completion_order_not_checkpoint_order(self):
        def point(samples, completed, seconds):
            return dict(arm="T2",samples=samples,run=str(samples),new_readout=True,
                        statistics_completed_at=completed,gpu_readout_seconds=seconds,
                        statistics_cpu_seconds=3.)
        first=report.first_timing([point(1000000,20.,40.),point(2000000,10.,30.)])
        self.assertEqual(first["samples"],2000000)
        self.assertEqual(first["measured_compute_seconds"],33.)
        self.assertEqual(first["estimate_all_22_compute_seconds"],726.)
        self.assertIsNone(report.first_timing([]))

    def test_login_GPU_and_unhealthy_nodes_cannot_run_the_aggregator(self):
        for node in ("sonmi","compute-0-5","compute-0-14","compute-0-18"):
            with patch.object(report.socket,"gethostname",return_value=node):
                with self.assertRaises(RuntimeError):
                    report.admit_statistics()


if __name__=="__main__":
    unittest.main()
