"""Check timer accounting without importing Torch or running training."""
import csv
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

path = Path(__file__).parents[1] / 'phychem_mfm/phase1/v31_segment_timing.py'
spec = importlib.util.spec_from_file_location('segment_timing', path)
timing = importlib.util.module_from_spec(spec)
spec.loader.exec_module(timing)


class TimerTests(unittest.TestCase):
    def test_disabled_does_not_synchronize_and_preserves_result(self):
        with timing.phase('loss'):
            value = 7
        self.assertEqual(timing.timed('loss')(lambda: value)(), 7)
        self.assertIsNone(timing._CURRENT.get())

    def test_warmup_exclusive_nested_accounting_and_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            calls = []
            timer = timing.SegmentTimer(Path(directory)/'timings', skip=1,
                                        synchronize=lambda: calls.append('sync'))
            with timing.phase('forward'):
                pass
            timer.end_step()
            self.assertEqual(calls, [])
            with patch.object(timing.time, 'perf_counter', side_effect=[0., 1., 3., 5.]):
                with timing.phase('forward'):
                    with timing.phase('collate'):
                        pass
            timer.end_step()
            timer.close()
            self.assertEqual(len(calls), 4)
            self.assertIsNone(timing._CURRENT.get())
            with (Path(directory)/'timings/segments.csv').open() as file:
                rows = list(csv.DictReader(file))
            self.assertEqual(len(rows), 1)
            self.assertEqual(float(rows[0]['forward']), 3.)
            self.assertEqual(float(rows[0]['collate']), 2.)
            self.assertEqual(float(rows[0]['total']), 5.)
            self.assertEqual(rows[0]['step'], '2')


if __name__ == '__main__':
    unittest.main()
