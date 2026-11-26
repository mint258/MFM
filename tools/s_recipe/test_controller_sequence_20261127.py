"""State boundary tests; all actual job/model entry points remain mocked."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch,Mock
import controller_sequence_20261127 as m


class Sequence(unittest.TestCase):
    def test_partial_closed_fit_never_advances_to_another_fit(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(m,'C',Path(tmp)):
            handle='S_FT_example_attempt0'
            (Path(tmp)/(handle+'_resource_close.json')).touch()
            load=lambda p:({'statistics':{handle:dict(mode='finetune')}} if p.name=='execution.json'
                           else dict(status='OWN_RESOURCES_CLOSED',exit_code=75,handle=handle))
            control=Mock()
            result=m.advance('fullft',handle,'compute-0-20','GPU-a',control=control,load=load)
            self.assertEqual(result['status'],'WAITING_SUCCESSFUL_COMPLETE_POINT')
            self.assertEqual(control.call_count,1)

    def test_last_budget_point_launches_only_its_cpu_not_an_unregistered_gpu_point(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(m,'C',Path(tmp)):
            handle='S_final_s0_9M_readout_budget_8000000_attempt0'
            (Path(tmp)/(handle+'_resource_close.json')).touch()
            row=dict(role='budget',run='S_final_s0_9M',samples=8000000)
            load=lambda p:({'statistics':{handle:row}} if p.name=='execution.json'
                           else dict(status='OWN_RESOURCES_CLOSED',exit_code=0,handle=handle))
            control=Mock()
            result=m.advance('budget',handle,'compute-0-20','GPU-a',control=control,load=load)
            self.assertEqual(result['status'],'ALL_REGISTERED_GPU_POINTS_REQUESTED_CPU_PENDING')
            self.assertEqual(control.call_count,2)
            self.assertEqual(control.call_args_list[1].args,
                ('launch_budget_statistics_native_20261126.py','S_final_s0_9M',8000000,'compute-0-11','50'))
