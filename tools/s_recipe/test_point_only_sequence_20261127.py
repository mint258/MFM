import unittest
from unittest.mock import Mock
from fullft_point_sequence_20261127 import point_only_advance


class PointOnlySequence(unittest.TestCase):
    def row(self,run):
        return dict(run=run,point='S_E1',node='compute-0-20',gpu_uuid='GPU-x',
            mode='finetune',resource_closed=True,status='COMPLETE')

    def test_explicit_same_point_next_never_uses_global_order(self):
        control=Mock(side_effect=[dict(status='OWN_RESOURCES_CLOSED',exit_code=0),{},
            dict(point='S_E1',run='next_same_point')])
        result=point_only_advance('fullft','S_handle','compute-0-20','GPU-x',point='S_E1',
            allowed_runs=['first','next_same_point'],control=control,
            load=lambda p:dict(statistics=dict(S_handle=self.row('first'))))
        self.assertEqual(result['next_controller_result']['run'],'next_same_point')
        control.assert_called_with('launch_fullft_20261124.py','compute-0-20','GPU-x','--run','next_same_point')

    def test_last_member_cannot_submit_the_next_scientific_point(self):
        control=Mock(return_value=dict(status='OWN_RESOURCES_CLOSED',exit_code=0))
        result=point_only_advance('fullft','S_handle','compute-0-20','GPU-x',point='S_E1',
            allowed_runs=['last'],control=control,
            load=lambda p:dict(statistics=dict(S_handle=self.row('last'))))
        self.assertEqual(result['next_controller_result']['status'],'NO_FOLLOWING_POINT_SUBMITTED')
        self.assertEqual(control.call_count,1)


if __name__=='__main__':unittest.main()
