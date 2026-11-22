"""New opt-in wiring to the existing capacity wait; no scientific inputs."""
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from tools.d_recipe import resources


class CapacityGateTests(unittest.TestCase):
    def test_default_uses_existing_fail_fast_check(self):
        guard = SimpleNamespace(check=Mock(), wait=Mock())
        self.assertIs(resources.capacity_gate(guard, {}), guard.check)

    def test_explicit_switch_uses_existing_blocking_wait(self):
        guard = SimpleNamespace(check=Mock(), wait=Mock())
        self.assertIs(resources.capacity_gate(guard, {"wait_for_capacity": True}), guard.wait)

    def test_truthy_nonboolean_does_not_enable_switch(self):
        guard = SimpleNamespace(check=Mock(), wait=Mock())
        self.assertIs(resources.capacity_gate(guard, {"wait_for_capacity": "true"}), guard.check)

    def test_default_constructor_preserves_initial_check(self):
        with patch.object(resources.Guard, "__init__", return_value=None), patch.object(resources, "protection_plan", return_value={}), patch.object(resources.DJointGuard, "check") as check, patch.object(resources.DJointGuard, "wait") as wait:
            resources.DJointGuard({"output": "/target"})
            check.assert_called_once_with("/target")
            wait.assert_not_called()

    def test_opted_constructor_waits_before_starting_writer(self):
        with patch.object(resources.Guard, "__init__", return_value=None), patch.object(resources, "protection_plan", return_value={}), patch.object(resources.DJointGuard, "check") as check, patch.object(resources.DJointGuard, "wait") as wait:
            resources.DJointGuard({"output": "/target", "wait_for_capacity": True})
            check.assert_not_called()
            wait.assert_called_once_with("/target")

    def test_new_gate_preserves_actual_rechecks_and_polling(self):
        guard = object.__new__(resources.DJointGuard)
        guard.poll = 5
        inherited = sys.modules[resources.Guard.__module__]
        with patch.object(guard, "check", side_effect=[resources.DiskUnavailable("stale"), None]) as check, patch.object(inherited.time, "sleep") as sleep:
            resources.capacity_gate(guard, {"wait_for_capacity": True})("/target", 17, 2)
            self.assertEqual(check.call_count, 2)
            self.assertEqual(check.call_args_list[0], check.call_args_list[1])
            sleep.assert_called_once_with(5)


if __name__ == "__main__":
    unittest.main()
