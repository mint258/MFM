"""New safety boundaries for finite metadata orchestration only."""
import unittest
from unittest.mock import Mock
from fullft_point_sequence_20261127 import completed,sequence


class FinitePointSequence(unittest.TestCase):
    def test_running_allocation_zero_code_is_not_completion(self):
        closed=dict(status='COMPLETE',exit_code=0,owned_descendants_exited=True,
            observer_joined=True,ended_at=1)
        self.assertFalse(completed(dict(job_id=1),closed,lambda job:'RUNNING|0:0'))
        self.assertTrue(completed(dict(job_id=1),closed,lambda job:'COMPLETED|0:0'))
        with self.assertRaises(ValueError):
            completed(dict(job_id=1),closed,lambda job:'FAILED|1:0')

    def test_wait_boundary_does_not_launch_or_cancel(self):
        control=Mock()
        row=dict(point='S_X',run='S_fit0',node='compute-0-20',gpu_uuid='GPU-x',
            mode='finetune_native',lifecycle_record='/unused')
        ticks=iter((0,61))
        result=sequence('S_X','S_handle','compute-0-20','GPU-x',
            ['S_fit'+str(i) for i in range(12)],
            load=lambda path:dict(statistics=dict(S_handle=row)),
            control=control,now=lambda:next(ticks),wait_seconds=60)
        self.assertEqual(result['status'],'FINITE_WAIT_ENDED_WITHOUT_CANCELLING_WORK')
        control.assert_not_called()

    def test_next_point_is_started_once_but_never_advanced(self):
        closed=dict(status='COMPLETE',exit_code=0,owned_descendants_exited=True,
            observer_joined=True,ended_at=1)
        row=dict(point='S_X',run='S_fit0',node='compute-0-20',gpu_uuid='GPU-x',
            mode='finetune_native',lifecycle_record='/unused')
        control=Mock(return_value=dict(status='EXPLICIT_CONTROLLER_SEQUENCE_RETURNED',
            next_controller_result=dict(point='S_Y',run='S_next')))
        result=sequence('S_X','S_handle','compute-0-20','GPU-x',
            ['S_fit'+str(i) for i in range(12)],
            load=lambda path:closed if str(path)=='/unused' else dict(statistics=dict(S_handle=row)),
            control=control)
        self.assertEqual(result['status'],'POINT_SEQUENCE_ENDED')
        self.assertEqual(control.call_count,1)


if __name__=='__main__':unittest.main()
