"""Approved fixed-native H route: preserve original chemistry failure masks."""
import unittest
from unittest.mock import Mock

from .development_geometry import H_COMPLETION_UNAVAILABLE, UnavailableD3, structure


class FixedNativeHFailureTests(unittest.TestCase):
    def test_original_chemistry_failures_remain_explicit_member_unavailability(self):
        for reason in H_COMPLETION_UNAVAILABLE:
            with self.subTest(reason=reason):
                complete = Mock(side_effect=ValueError(reason))
                with self.assertRaises(UnavailableD3) as caught:
                    structure("CO", [6, 8], [[0., 0., 0.], [1.4, 0., 0.]],
                              hydrogen_policy="B6_fixed_native_H", complete=complete)
                self.assertEqual(str(caught.exception), reason)
                complete.assert_called_once()

    def test_unexpected_and_coordinate_invariant_errors_are_not_masked(self):
        for reason in ("unexpected code failure",
                       "BASELINE_H_COMPLETION_MOVED_EXISTING_NATIVE_COORDINATES"):
            with self.subTest(reason=reason):
                complete = Mock(side_effect=ValueError(reason))
                with self.assertRaises(ValueError) as caught:
                    structure("CO", [6, 8], [[0., 0., 0.], [1.4, 0., 0.]],
                              hydrogen_policy="B6_fixed_native_H", complete=complete)
                self.assertNotIsInstance(caught.exception, UnavailableD3)
