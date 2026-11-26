"""Only the new standby state/race boundaries; no cluster commands."""
import unittest
from unittest.mock import Mock
from standby_settlement_20261126 import settle


NAME = 'S_E1_k1_s0_3M_extension'
PENDING = 'zixiao|' + NAME + '|PENDING|0:0|0'
RUNNING = 'zixiao|' + NAME + '|RUNNING|0:0|1'
CANCELLED = 'zixiao|' + NAME + '|CANCELLED by 1278|0:0|0'
BEFORE = 'UserId=zixiao(1278) JobName=' + NAME + ' JobState=PENDING Reason=Resources'
HELD = 'UserId=zixiao(1278) JobName=' + NAME + ' JobState=PENDING Reason=JobHeldUser'


class Settlement(unittest.TestCase):
    def test_pending_hold_recheck_then_confirm_final(self):
        call = Mock(side_effect=[PENDING, BEFORE, '', HELD, PENDING, '', CANCELLED])
        persist = Mock()
        value = settle(7, NAME, call, persist)
        self.assertTrue(value['settled'])
        self.assertEqual(persist.call_count, 1)
        self.assertEqual(sum(c.args[0] == '/usr/bin/scancel' for c in call.call_args_list), 1)

    def test_started_standby_is_observed_only(self):
        call = Mock(return_value=RUNNING)
        persist = Mock()
        self.assertFalse(settle(7, NAME, call, persist)['settled'])
        self.assertEqual(call.call_count, 1)
        persist.assert_not_called()

    def test_race_during_hold_never_cancels(self):
        started = 'UserId=zixiao(1278) JobName=' + NAME + ' JobState=RUNNING Reason=None'
        call = Mock(side_effect=[PENDING, BEFORE, '', started, RUNNING])
        persist = Mock()
        self.assertFalse(settle(7, NAME, call, persist)['settled'])
        self.assertFalse(any(c.args[0] == '/usr/bin/scancel' for c in call.call_args_list))
        persist.assert_not_called()

    def test_async_cancel_requires_actual_terminal_without_resignalling(self):
        call = Mock(return_value=PENDING)
        persist = Mock()
        self.assertFalse(settle(7, NAME, call, persist, dict(cancel_requested=True))['settled'])
        self.assertEqual(call.call_count, 1)
        persist.assert_not_called()
        call = Mock(return_value=CANCELLED)
        self.assertTrue(settle(7, NAME, call, persist, dict(cancel_requested=True))['settled'])
        self.assertEqual(call.call_count, 1)

    def test_successful_started_standby_needs_no_cancel(self):
        call = Mock(return_value='zixiao|' + NAME + '|COMPLETED|0:0|8')
        persist = Mock()
        self.assertTrue(settle(7, NAME, call, persist)['settled'])
        self.assertEqual(call.call_count, 1)
        persist.assert_not_called()

    def test_foreign_identity_refuses_without_controls(self):
        call = Mock(return_value='other|' + NAME + '|PENDING|0:0|0')
        persist = Mock()
        with self.assertRaises(ValueError):
            settle(7, NAME, call, persist)
        self.assertEqual(call.call_count, 1)
        persist.assert_not_called()
