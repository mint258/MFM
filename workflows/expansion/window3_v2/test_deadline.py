"""Synthetic subprocess tests; no UFF, geometries, or real dataset reads."""
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest

from .deadline import generate_limited, failed_packet
from .kernel import molecule_id

SOURCE = {'pubchem_version': 'deadline-test', 'cid': 1, 'full_key': 'KEY',
          'stream': 'N', 'stream_rank': 1}


@unittest.skipUnless(os.name == 'posix', 'production deadline uses POSIX sessions')
class DeadlineTests(unittest.TestCase):
    def test_native_style_busy_child_is_killed_and_next_source_can_finish(self):
        with tempfile.TemporaryDirectory() as folder:
            pid_file = str(Path(folder) / 'pid')
            busy = ("import os,time,pathlib;"
                    "pathlib.Path(%r).write_text(str(os.getpid()));"
                    "exec('while True: pass')" % pid_file)
            started = time.monotonic()
            packet = generate_limited(SOURCE, {'molecule_timeout_seconds': .3},
                command=[sys.executable, '-c', busy])
            self.assertLess(time.monotonic() - started, 4)
            self.assertEqual(packet['state'], 'UFF_TIMEOUT')
            self.assertFalse(packet['native_all_failed'])
            self.assertTrue(packet['generation_count_unknown'])
            self.assertFalse(Path('/proc/' + Path(pid_file).read_text()).exists())
            ready = {'molecule_id': molecule_id(SOURCE), 'state': 'SUCCESS',
                     'conformers': [1], 'stereo_draw_index': 0}
            command = [sys.executable, '-c',
                'import json;print(json.dumps(%r))' %
                {'event': 'result', 'packet': ready}]
            following = generate_limited(SOURCE, {'molecule_timeout_seconds': 2},
                                         command=command)
            self.assertEqual(following['conformers'], [1])
            self.assertFalse(following['molecule_timed_out'])

    def test_one_deadline_covers_multiple_draws_and_preserves_produced_d20(self):
        mid = molecule_id(SOURCE)
        event = {'event': 'checkpoint', 'metadata': {'molecule_id': mid,
                 'D20': {'values': [7]}, 'stereo_assigned': True,
                 'stereo_draw_index': 1}}
        script = ("import json,time;print(json.dumps(%r),flush=True);"
                  "time.sleep(.18);print(json.dumps(%r),flush=True);time.sleep(5)"
                  % (event, {'event': 'checkpoint', 'metadata':
                     {'molecule_id': mid, 'D20': None, 'stereo_draw_index': 2}}))
        packet = generate_limited(SOURCE, {'molecule_timeout_seconds': .35},
                                   command=[sys.executable, '-c', script])
        self.assertEqual(packet['state'], 'UFF_TIMEOUT')
        self.assertEqual(packet['D20'], {'values': [7]})
        self.assertEqual(packet['stereo_draw_index'], 2)
        self.assertEqual(packet['stereo_draws'][-1]['state'], 'UFF_TIMEOUT')
        self.assertFalse(packet['stereo_draws'][-1]['native_all_failed'])

    def test_child_failure_is_unknown_and_never_retried(self):
        packet = generate_limited(SOURCE, {'molecule_timeout_seconds': 2},
            command=[sys.executable, '-c', 'raise SystemExit(7)'])
        self.assertEqual(packet['state'], 'TECHNICAL_UNKNOWN')
        self.assertEqual(packet['native_child_exit_code'], 7)
        self.assertFalse(packet['molecule_timed_out'])

    def test_invalid_limit_and_wrong_checkpoint_identity_are_rejected(self):
        with self.assertRaises(ValueError):
            generate_limited(SOURCE, {'molecule_timeout_seconds': 3601})
        with self.assertRaises(ValueError):
            failed_packet(SOURCE, 'UFF_TIMEOUT', 'limit',
                          {'molecule_id': 'different'})

    def test_resume_keeps_finished_packet_and_applies_only_approved_interruption(self):
        import gzip
        from unittest.mock import patch
        from . import producer
        old_source = dict(SOURCE, cid=10)
        interrupted_source = dict(SOURCE, cid=11)
        next_source = dict(SOURCE, cid=12)
        old = failed_packet(old_source, 'SOURCE_INTEGRITY_HOLD', 'old saved result')
        old['worker_wall_seconds'], old['worker_CPU_seconds'] = 3.5, 3.0
        stopped = failed_packet(interrupted_source, 'UFF_TIMEOUT', 'user stop')
        stopped['molecule_timeout_seconds'] = 3600
        following = failed_packet(next_source, 'UFF_UNSUPPORTED', 'synthetic result')
        captured = []
        with tempfile.TemporaryDirectory() as folder:
            chunk = Path(folder) / 'chunk_000000'
            chunk.mkdir()
            with gzip.open(chunk / 'packets_old.jsonl.gz', 'wt') as stream:
                stream.write(json.dumps({'index': 0, 'packet': old}) + '\n')
                stream.write(json.dumps({'index': 1}) + '\n')
            override = Path(folder) / 'approved_timeout.json'
            override.write_text(json.dumps(stopped))
            config = {'output': folder, 'molecule_timeout_seconds': 3600,
                      'interrupted_timeout_overrides':
                      {molecule_id(interrupted_source): str(override)}}
            def write(packets, destination):
                captured.extend(packets)
                return [], {}
            with patch.object(producer, 'CONFIG', config), \
                 patch.object(producer, 'KERNEL', None), \
                 patch.object(producer, 'generate_limited', return_value=following) as compute, \
                 patch.object(producer, 'write_packets', side_effect=write):
                result = producer.process((0, [old_source, interrupted_source, next_source]))
                compute.assert_called_once_with(next_source, config)
                self.assertEqual(captured, [old, stopped, following])
                self.assertEqual(result['states']['UFF_TIMEOUT'], 1)
                self.assertEqual(producer.process(
                    (0, [old_source, interrupted_source, next_source])), result)
                compute.assert_called_once()


if __name__ == '__main__':
    unittest.main()
