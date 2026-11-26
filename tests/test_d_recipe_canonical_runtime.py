"""New transport admission/dispatch only; no GPU, Slurm env, labels or training."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from tools.d_recipe.canonical_resources import require_admitted_job
from tools.d_recipe.canonical_runtime import (RUNS, SHARED_FLOOR, allocated_threads,
                                              guard_class, guard_plan, installed_writers)


class CanonicalRuntimeTests(unittest.TestCase):
    def config(self):
        return dict(canonical_admission=True, output_filesystem="/share",
            local_output_root="/tmp/d_recipe_fixture", output=str(RUNS / "fixture/training"),
            local_future_bytes=1100, local_storage_peak_bytes=1000, exit_root_log_future_bytes=100,
            shared_future_bytes={"/share": 5000}, local_concurrent_bytes=10**30,
            share_storage_peak_bytes=10**30, peer_storage_guard_root="/must/not/be/read")

    def resources(self):
        class FakeGuard:
            def __init__(self, plan, admit):
                self.plan, self.targets, self.calls = plan, plan["targets"], []
            def check_target(self, target, **kwargs):
                self.calls.append((target, kwargs))
        return SimpleNamespace(Guard=FakeGuard, DiskUnavailable=RuntimeError,
            allocated_local_bytes=lambda root: 300,
            admit_output=Mock(side_effect=AssertionError("Legacy peer guard must not run")),
            DJointGuard=object())

    def test_only_explicit_own_phase_budgets_and_original_floors(self):
        c = self.config()
        original = deepcopy(c)
        plan = guard_plan(c)
        self.assertEqual(c, original)
        self.assertEqual(plan["targets"][0]["peak_additional_bytes"], 1100)
        self.assertEqual(plan["targets"][1]["reserve_bytes"], SHARED_FLOOR)
        self.assertEqual(plan["targets"][1]["quota_reserve_bytes"], SHARED_FLOOR)
        self.assertTrue(all(t["concurrent_bytes"] == 0 for t in plan["targets"]))
        with self.assertRaises(ValueError):
            guard_plan(dict(c, canonical_admission=False))

    def test_runtime_checks_credit_only_owned_allocation_and_control_avoids_RAM_re_admission(self):
        resources = self.resources()
        monitor = guard_class(resources)(self.config(), admit=False)
        monitor.check(RUNS / "fixture/training")
        self.assertEqual([x[1]["bytes_needed"] for x in monitor.calls], [800, 5000])
        monitor.calls.clear()
        monitor.check_control(RUNS / "exit_control/fixture/request.json")
        self.assertEqual([x[1] for x in monitor.calls], [{}, {}])

    def test_writer_adaptation_restores_legacy_functions_after_failure(self):
        resources, c = self.resources(), self.config()
        previous = resources.admit_output, resources.DJointGuard
        with self.assertRaisesRegex(RuntimeError, "escaped"):
            with installed_writers(c, resources):
                resources.admit_output(c, RUNS / "fixture/summary.json")
                resources.admit_output(c, "/unowned/output")
        self.assertEqual((resources.admit_output, resources.DJointGuard), previous)
        previous[0].assert_not_called()

    def test_original_probe_threads_are_capped_to_actual_allocation(self):
        calls, state = [], [16]
        def setter(n):
            calls.append(n)
            state[0] = n
        fake = SimpleNamespace(set_num_threads=setter, get_num_threads=lambda: state[0])
        with allocated_threads(fake, 5):
            fake.set_num_threads(16)
            fake.set_num_threads(1)
        self.assertIs(fake.set_num_threads, setter)
        self.assertLessEqual(max(calls), 5)

    def test_prepared_actual_job_node_must_match(self):
        c = dict(node="compute-0-20", canonical_admission=True,
                 canonical_phase_admission=dict(node="compute-0-20", job_id="fixture"),
                 safe_exit_control=dict(job_id="fixture"))
        require_admitted_job(c, "compute-0-20", "fixture")
        with self.assertRaises(ValueError):
            require_admitted_job(c, "compute-0-20", "different_fixture")
        with self.assertRaises(ValueError):
            require_admitted_job(c, "compute-0-22", "fixture")


if __name__ == "__main__":
    unittest.main()
