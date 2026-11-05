"""Native checks retain stops while small checkpoints share one bounded cadence."""
import unittest
from unittest.mock import patch
from pathlib import Path
from .run import ShardGuard
class Cadence(unittest.TestCase):
    def test_slow_native_check_cannot_retrigger_until_complete_plus_thirty(self):
        clock=[0.0];calls=[]
        def native(guard,force=False,reserve=0):
            calls.append((clock[0],force,reserve));clock[0]+=45;guard.last=clock[0]-45
        guard=ShardGuard.__new__(ShardGuard);guard.last=0
        with patch('workflows.expansion.alpha_sharded_novelty_v1.run.time.monotonic',side_effect=lambda:clock[0]),patch('workflows.expansion.exact_nn_cached_v1.run.Guard.poll',new=native):
            guard.poll(force=True);self.assertEqual(guard.last,45)
            for now in (45,60,74.999):clock[0]=now;guard.poll()
            self.assertEqual(len(calls),1)
            clock[0]=75;guard.poll();self.assertEqual(len(calls),2)
            guard.poll(force=True,reserve=123);self.assertEqual(calls[-1][1:],(True,123))
    def test_native_quota_stop_propagates_without_freshening_success_clock(self):
        guard=ShardGuard.__new__(ShardGuard);guard.last=12
        with patch('workflows.expansion.alpha_sharded_novelty_v1.run.time.monotonic',return_value=43),patch('workflows.expansion.exact_nn_cached_v1.run.Guard.poll',side_effect=RuntimeError('actual quota failed')):
            with self.assertRaisesRegex(RuntimeError,'actual quota failed'):guard.poll()
        self.assertEqual(guard.last,12)
if __name__=='__main__':unittest.main()