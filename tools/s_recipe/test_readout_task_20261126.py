"""Three new task/producer cases; no original numerical readout is repeated."""
import copy
import os
import time
import unittest
from unittest.mock import patch
from readout_task_20261126 import binding,native_guard,native_closed,CONTROL
from extension_output_budget_20261124 import phase_live
import lifecycle_20261122 as life


class ReadoutTask(unittest.TestCase):
    def fixture(self,role='budget'):
        run='S_B0_s0_9M' if role=='budget' else 'S_E1_k1_s0_3M'
        budget=9000000 if role=='budget' else 3000000
        samples=1000000 if role=='budget' else 3000000
        handle=run+'_readout_'+role+'_'+str(samples)+'_attempt0'
        c=dict(run=run,samples=budget,seed=0,node='compute-0-20',
            output=str(CONTROL/'training'/run),evaluation_samples=[budget])
        producer=dict(pid=123,uid=1278,start_ticks=456,ppid=1,state='R')
        task=dict(run=run,handle=handle,role=role,samples=samples,producer=producer,standby_job_id=12345,
            configuration=str(CONTROL/(handle+'_configuration.json')),
            native_record=str(CONTROL/(handle+'_native_record.json')),
            handoff_request=str(CONTROL/(handle+'_handoff_request.json')),
            contract=dict(uid=1278,run=run,node=c['node'],role=role,samples=samples,
                created_at=time.time(),duration_seconds=7200))
        return task,c

    def test_only_original_trajectory_points_and_registered_extension_endpoints(self):
        task,c=self.fixture()
        output,filename=binding(task,c)
        self.assertEqual(output.name,'readout_1000000')
        self.assertEqual(filename,'snapshot_gpu_status.json')
        for count in (2500000,9000000):
            with self.assertRaises(ValueError):binding(dict(task,samples=count),c)
        with self.assertRaises(ValueError):binding(task,dict(c,layer=3))
        with self.assertRaises(ValueError):binding(task,dict(c,seed=False))
        task,c=self.fixture('terminal')
        self.assertEqual(binding(task,c)[0].name,'readout')
        with self.assertRaises(ValueError):binding(task,dict(c,run='S_R1_s0_3M'))
        with self.assertRaises(ValueError):binding(task,dict(c,evaluation_samples=[1000000,3000000]))

    def test_native_guard_requires_actual_identity_and_exact_files(self):
        task,c=self.fixture()
        with patch('readout_task_20261126.socket.gethostname',return_value=c['node']), \
             patch('readout_task_20261126.life.identity',return_value=life.Identity(**task['producer'])):
            native_guard(task,c)
            bad=copy.deepcopy(task)
            bad['producer']['start_ticks']+=1
            with self.assertRaises(ValueError):native_guard(bad,c)
            with self.assertRaises(ValueError):native_guard(dict(task,native_record=str(CONTROL/'another.json')),c)
            with patch.dict(os.environ,SLURM_JOB_ID='12345'):
                with self.assertRaises(ValueError):native_guard(task,c)

    def test_owned_phase_closure_is_not_a_job_number_or_reused_pid(self):
        task,c=self.fixture()
        value=dict(run=task['run'],samples=task['samples'],role=task['role'],resource_handle=task['handle'],
            producer=task['producer'],ended_at=1,owned_descendants_exited=True,observer_joined=True,exit_code=0)
        actual=life.Identity(**task['producer'])
        self.assertFalse(native_closed(task,value,actual))
        self.assertTrue(native_closed(task,value,None))
        self.assertTrue(native_closed(task,value,life.Identity(**dict(task['producer'],start_ticks=457))))
        with self.assertRaises(ValueError):native_closed(task,dict(value,samples=2000000),None)
        self.assertFalse(native_closed(task,dict(value,observer_joined=False),None))
        row=dict(job_id=None,mode='gpu_native',lifecycle_record='synthetic')
        paused=dict(value,exit_code=75)
        self.assertTrue(phase_live(row,{},lambda _:paused))
        self.assertFalse(phase_live(dict(row,resource_closed=True),{},lambda _:paused))
