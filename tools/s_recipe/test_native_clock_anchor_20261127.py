"""Only new clock-boundary behavior through both actual metadata guards."""
import os
import unittest
from unittest.mock import patch
from contextlib import ExitStack
import lifecycle_20261122 as life
import mixed_fullft_runtime_20261126 as ft
import readout_task_20261126 as ro
from storage_20261122 import CONTROL as C


class ClockBoundaries(unittest.TestCase):
    def sources(self,created):
        producer=vars(life.identity(os.getpid()))
        for kind in ('readout','fullft'):
            run='S_final_s0_9M' if kind=='readout' else 'S_FT_S_B0_3M_qm9_U0_atom_s0'
            handle=run+('_readout_budget_2000000_attempt99' if kind=='readout' else '_attempt99')
            c=dict(run=run,node='compute-0-20',seed=0,samples=9000000,layer=6,
                output=str(C/'training'/run),execution_backend='mixed_gpu_native_20261126')
            task=dict(handle=handle,native_handle=handle,role='budget',samples=2000000,
                configuration=str(C/(handle+'_configuration.json')),
                native_record=str(C/(handle+('_native_record.json' if kind=='readout' else '_fullft_native_record.json'))),
                handoff_request=str(C/(handle+('_handoff_request.json' if kind=='readout' else '_fullft_handoff_request.json'))),
                standby_job_id=123,producer=producer,contract=dict(uid=1278,run=run,node=c['node'],
                    role='budget',samples=2000000,created_at=created,duration_seconds=7200 if kind=='readout' else 2100))
            yield (ro.native_guard if kind=='readout' else ft.native_guard),task,c,(7200 if kind=='readout' else 2100)

    def context(self):
        stack=ExitStack()
        stack.enter_context(patch.dict(os.environ,{},clear=True))
        stack.enter_context(patch('socket.gethostname',return_value='compute-0-20'))
        stack.enter_context(patch('time.time',return_value=1000.0))
        original_guard=life.Guard
        stack.enter_context(patch.object(life,'Guard',side_effect=lambda end,closing:
            original_guard(end,closing,now=lambda:1000.0)))
        return stack

    def test_small_cross_host_skew_does_not_extend_deadline(self):
        with self.context():
            for guard,task,c,duration in self.sources(1000.5):
                self.assertEqual(guard(task,c).end_epoch,1000.0+duration)

    def test_more_than_five_seconds_in_future_is_rejected(self):
        with self.context():
            for guard,task,c,_ in self.sources(1005.01):
                with self.assertRaises(ValueError):guard(task,c)

    def test_original_staleness_limit_is_preserved(self):
        with self.context():
            for guard,task,c,_ in self.sources(939.99):
                with self.assertRaises(ValueError):guard(task,c)
