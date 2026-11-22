"""Policy tests for infrastructure-only clipping continuation."""
import types
import unittest

from tools.d_recipe.clipping_managed import (
    original_worker, require_joint_local_reserve)


class ClippingManagedTests(unittest.TestCase):
    def test_original_configuration_and_report_arguments_are_preserved(self):
        args = ["/registered/native_D20.json", "/original/closed", "/original/report"]
        self.assertEqual(original_worker(*args)[-3:], args)

    def test_joint_local_future_is_added_to_the_system_reserve(self):
        facts = types.SimpleNamespace(
            f_blocks=100 * 2**30, f_frsize=1,
            f_bavail=20 * 2**30, f_favail=10001)
        require_joint_local_reserve(facts, 10 * 2**30)
        with self.assertRaises(RuntimeError):
            require_joint_local_reserve(facts, 10 * 2**30 + 1)
        with self.assertRaises(ValueError):
            require_joint_local_reserve(facts, 0)


if __name__ == "__main__":
    unittest.main()

