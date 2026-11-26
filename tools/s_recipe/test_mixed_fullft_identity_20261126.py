"""New native admission/sealing boundaries; original suites stay closed."""
import copy
import os
import unittest
from unittest.mock import patch
import time
from finetune_extension_20261124 import validate,CONTROL,AUTHORITY,PROTOCOL
from mixed_fullft_runtime_20261126 import native_guard
from seal_finetune_20261124 import same_execution
from extension_output_budget_20261124 import phase_live
import lifecycle_20261122 as life


class MixedFullFTIdentity(unittest.TestCase):
    def config(self):
        return dict(invoking_authority=AUTHORITY,authority=PROTOCOL,kind='F',mode='full',
            ready=True,task='exp.LogD',seed=0,pretraining_seed=0,run='S_FT_B0_LogD_s0',
            internal_split_seed=20261112,bootstrap_seed=20261025,
            output=str(CONTROL/'finetune_20261124/S_FT_B0_LogD_s0'),
            source_binding=dict(checkpoint=str(CONTROL/'training/S_B0_s0_3M/samples_3000000.pt'),
                samples=3000000,source_training_budget=3000000,run='S_B0_s0_3M'),
            output_mount='/share',cleanup_seconds=900,peak_ram_bytes=64*1024**3,
            cpus=16,minimum_free_gpu_mib=22000,work_unit_seconds=120,node='compute-0-20',
            execution_backend='mixed_gpu_native_20261126')

    def test_mixed_nodes_require_explicit_backend_and_keep_node21_banned(self):
        c=self.config()
        self.assertIs(validate(c),c)
        with self.assertRaises(ValueError):validate(dict(c,execution_backend=None))
        with self.assertRaises(ValueError):validate(dict(c,node='compute-0-21'))

    def test_native_contract_binds_real_producer_without_a_slurm_identity(self):
        c=self.config()
        producer=dict(pid=123,uid=1278,start_ticks=456,ppid=1,state='R')
        handle=c['run']+'_attempt0'
        task=dict(contract=dict(uid=1278,run=c['run'],node=c['node'],duration_seconds=2100,created_at=time.time()),
            producer=producer,standby_job_id=12345,native_handle=handle,
            configuration=str(CONTROL/(handle+'_configuration.json')),
            native_record=str(CONTROL/(handle+'_fullft_native_record.json')),
            handoff_request=str(CONTROL/(handle+'_fullft_handoff_request.json')))
        with patch('mixed_fullft_runtime_20261126.socket.gethostname',return_value=c['node']), \
             patch('mixed_fullft_runtime_20261126.life.identity',return_value=life.Identity(**producer)):
            native_guard(task,c)
            wrong=copy.deepcopy(task)
            wrong['producer']['start_ticks']+=1
            with self.assertRaises(ValueError):native_guard(wrong,c)
            with patch.dict(os.environ,SLURM_JOB_ID='12345'):
                with self.assertRaises(ValueError):native_guard(task,c)
            wrong=copy.deepcopy(task)
            wrong['native_record']=str(CONTROL/'another_fit_native_record.json')
            with self.assertRaises(ValueError):native_guard(wrong,c)

    def test_selected_model_requires_exact_native_producer_not_none_job_equality(self):
        producer=dict(pid=123,uid=1278,start_ticks=456)
        closure=dict(job_id=None,native_handle='native1',run='fit',node='compute-0-20',producer=producer)
        execution=dict(native_handle='native1',run='fit',node='compute-0-20',producer=producer)
        summary=dict(job_id=None,native_execution=execution)
        self.assertTrue(same_execution(summary,closure))
        self.assertFalse(same_execution(dict(job_id=None),closure))
        self.assertFalse(same_execution(dict(summary,native_execution=dict(execution,native_handle='native2')),closure))
        self.assertTrue(same_execution(dict(job_id='12'),dict(job_id=12)))

    def test_native_continuation_counts_future_until_its_standby_is_settled(self):
        row=dict(mode='finetune_native',job_id=None,lifecycle_record='synthetic.json')
        closed=dict(ended_at=1,owned_descendants_exited=True,observer_joined=True,exit_code=75)
        self.assertTrue(phase_live(row,{},lambda _:closed))
        self.assertFalse(phase_live(dict(row,resource_closed=True),{},lambda _:closed))
