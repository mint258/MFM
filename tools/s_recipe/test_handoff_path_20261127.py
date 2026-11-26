"""Exercise the two real standby entry functions with string task-file paths."""
import contextlib
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch,Mock
import readout_execution_20261126 as reader
import fullft_native_execution_20261126 as fullft


class Guard:
    def __init__(self,*args):self.phase='test'
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def stopping(self):return False


OWNER=dict(pid=77,uid=1278,start_ticks=99,ppid=1,state='R')


class HandoffPath(unittest.TestCase):
    def test_readout_string_request_is_published_and_complete_work_is_not_replayed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            record=root/'native.json'
            record.write_text(json.dumps(dict(exit_code=0,status='GPU_TERMINAL_COMPLETE_WAITING_CPU')))
            task=dict(handle='test_reader',standby_job_id=7,producer=OWNER,
                handoff_request=str(root/'request.json'),native_record=str(record))
            with contextlib.ExitStack() as stack:
                stack.enter_context(patch.dict(os.environ,SLURM_JOB_ID='7'))
                stack.enter_context(patch.object(reader,'load_task',return_value=(task,{})))
                stack.enter_context(patch.object(reader,'actual_guard',return_value=Guard()))
                stack.enter_context(patch.object(reader,'native_closed',return_value=True))
                stack.enter_context(patch.object(reader.life,'identity',return_value=None))
                stack.enter_context(patch.object(reader.life,'enable_subreaper'))
                stack.enter_context(patch.object(reader.life,'close_children'))
                gpu=stack.enter_context(patch.object(reader,'gpu',side_effect=AssertionError('No replay')))
                self.assertEqual(reader.standby('synthetic-task'),0)
                gpu.assert_not_called()
            request=json.loads((root/'request.json').read_text())
            self.assertEqual(request,dict(handle='test_reader',job_id=7,producer=OWNER))

    def test_fullft_string_request_is_published_and_complete_fit_is_not_replayed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            record=root/'native.json'
            record.write_text(json.dumps(dict(exit_code=0,status='COMPLETE',producer=OWNER,
                ended_at=1,owned_descendants_exited=True,observer_joined=True)))
            task=dict(native_handle='test_fit',standby_job_id=7,producer=OWNER,
                handoff_request=str(root/'request.json'),native_record=str(record))
            cfg=dict(run='test_fit',node='compute-0-20',cpus=16)
            actual='JobId=7 UserId=zixiao(1278) JobState=RUNNING NodeList=compute-0-20 TimeLimit=00:35:00 EndTime=2099-01-01T00:00:00'
            identity=lambda pid:None if pid==77 else SimpleNamespace(pid=pid,uid=1278,start_ticks=1,ppid=1,state='R')
            with contextlib.ExitStack() as stack:
                stack.enter_context(patch.dict(os.environ,SLURM_JOB_ID='7',SLURM_CPUS_PER_TASK='16'))
                stack.enter_context(patch.object(fullft,'C',root))
                stack.enter_context(patch.object(fullft,'task_from_path',return_value=(task,cfg)))
                stack.enter_context(patch.object(fullft,'query',return_value=actual))
                stack.enter_context(patch.object(fullft.life,'Guard',Guard))
                stack.enter_context(patch.object(fullft.life,'identity',side_effect=identity))
                stack.enter_context(patch.object(fullft.life,'enable_subreaper'))
                stack.enter_context(patch.object(fullft.life,'close_children'))
                fit=stack.enter_context(patch.object(fullft,'fit',side_effect=AssertionError('No replay')))
                self.assertEqual(fullft.standby('synthetic-task'),0)
                fit.assert_not_called()
            request=json.loads((root/'request.json').read_text())
            self.assertEqual(request['producer'],OWNER)
            self.assertEqual(request['standby_job_id'],7)
            self.assertEqual(json.loads((root/'test_fit_standby_wait_7.json').read_text())['status'],
                'NATIVE_ALREADY_COMPLETE_NO_FIT_REPLAY')
