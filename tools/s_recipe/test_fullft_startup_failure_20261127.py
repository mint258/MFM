import copy
import unittest
from unittest.mock import patch
from fullft_startup_failure_20261127 import (C,STATUS,validate_failure,require_pending,
    retire_entries,verify_receipt)


class StartupFailure(unittest.TestCase):
    def setUp(self):
        self.h='S_FT_example_attempt1'
        self.cfg=dict(run='S_FT_example',output=str(C/'finetune_20261124/S_FT_example'),
            node='compute-0-20',gpu_uuid='GPU-example')
        self.row=dict(run=self.cfg['run'],mode='finetune_native',job_id=None,standby_job_id=4540891,
            configuration=str(C/(self.h+'_configuration.json')),node=self.cfg['node'],
            gpu_uuid=self.cfg['gpu_uuid'])
        self.producer=dict(pid=42,uid=1278,start_ticks=123)
        self.task=dict(native_handle=self.h,standby_job_id=4540891,
            configuration=self.row['configuration'],producer=self.producer)
        self.closure=dict(run=self.cfg['run'],node=self.cfg['node'],gpu_uuid=self.cfg['gpu_uuid'],
            native_handle=self.h,standby_job_id=4540891,producer=self.producer,
            status='FAILED',error='AdmissionRefused: REFUSED insufficient node_ram: values',
            started_at=1000.,ended_at=1001.,peak_RSS_bytes=34*1024**2,
            owned_descendants_exited=True,observer_joined=True)
        self.files={n:dict(path=self.cfg['output']+'/'+n,uid=1278,size=500,ino=i,dev=2,
            mtime_ns=900000000000,ctime_ns=900000000000,regular=True)
            for i,n in enumerate(('complete_state.pt','history.jsonl'))}

    def valid(self):return validate_failure(self.h,self.row,self.closure,self.cfg,self.task,self.files)

    def test_preserves_unobserved_exit_and_saved_state(self):
        before=copy.deepcopy((self.closure,self.files))
        value=self.valid()
        self.assertIsNone(value['actual_native_exit_code'])
        self.assertFalse(value['exit_code_observed'])
        self.assertEqual(before,(self.closure,self.files))

    def test_exact_producer_owner_and_task_binding(self):
        for key,value in (('uid',1283),('pid',43),('start_ticks',124)):
            with self.subTest(key=key):
                task=copy.deepcopy(self.task);task['producer'][key]=value
                with self.assertRaises(ValueError):validate_failure(self.h,self.row,self.closure,self.cfg,task,self.files)
        task=copy.deepcopy(self.task);task['standby_job_id']=4540892
        with self.assertRaises(ValueError):validate_failure(self.h,self.row,self.closure,self.cfg,task,self.files)
        row=dict(self.row,node='compute-0-21')
        with self.assertRaises(ValueError):validate_failure(self.h,row,self.closure,self.cfg,self.task,self.files)

    def test_rejects_changed_missing_or_linked_scientific_state(self):
        for key,value in (('mtime_ns',1000000000000),('regular',False),('uid',1283),('size',0)):
            with self.subTest(key=key):
                files=copy.deepcopy(self.files);files['complete_state.pt'][key]=value
                with self.assertRaises(ValueError):validate_failure(self.h,self.row,self.closure,self.cfg,self.task,files)
        with self.assertRaises(ValueError):validate_failure(self.h,self.row,self.closure,self.cfg,self.task,{})

    def test_rejects_other_failure_or_unclosed_tree(self):
        for key,value in (('error','DataAlignmentError'),('status','CONTINUATION_REQUIRED'),
                ('exit_code',75),('owned_descendants_exited',False),('observer_joined',False),
                ('peak_RSS_bytes',1024**3)):
            with self.subTest(key=key):
                closure=copy.deepcopy(self.closure);closure[key]=value
                with self.assertRaises(ValueError):validate_failure(self.h,self.row,closure,self.cfg,self.task,self.files)

    def test_cancel_only_exact_zero_work_pending_owner(self):
        info=dict(JobId='4540891',UserId='zixiao(1278)',JobName=self.h,JobState='PENDING',Reason='JobHeldUser')
        require_pending(info,'PENDING|0:0|0',self.h,4540891,held=True)
        for key,value in (('UserId','other(1283)'),('JobState','RUNNING'),('JobName','S_other'),('Reason','Resources')):
            changed=dict(info,**{key:value})
            with self.assertRaises(ValueError):require_pending(changed,'PENDING|0:0|0',self.h,4540891,held=True)
        with self.assertRaises(ValueError):require_pending(info,'PENDING|0:0|1',self.h,4540891)

    def test_retirement_is_exact_and_preserves_other_writers(self):
        wanted=[dict(id='own_ram',bytes=8),dict(id='own_disk',bytes=32)]
        peer=dict(id='other',bytes=64)
        self.assertEqual(retire_entries(wanted+[peer],wanted),[peer])
        self.assertEqual(retire_entries([peer],wanted,allow_absent=True),[peer])
        for rows in ([wanted[0],peer],[dict(id='own_ram',bytes=7),wanted[1],peer],[peer]):
            with self.assertRaises(ValueError):retire_entries(rows,wanted)

    def test_settlement_receipt_binds_every_snapshot_and_actual_cancel(self):
        row=dict(self.row,status=STATUS,resource_closed=True)
        receipt=dict(self.valid(),status='FAILED_STARTUP_OWN_RESOURCES_CLOSED',
            native_producer_verified_gone=True,standby_actual='CANCELLED by 1278|0:0|0')
        self.assertTrue(verify_receipt(row,self.closure,self.cfg,self.task,self.files,receipt))
        for key,value in (('closure_digest','bad'),('configuration_digest','bad'),
                ('native_producer_verified_gone',False),('standby_actual','COMPLETED|0:0|0')):
            with self.assertRaises(ValueError):verify_receipt(row,self.closure,self.cfg,self.task,self.files,dict(receipt,**{key:value}))
        changed=copy.deepcopy(self.files);changed['complete_state.pt']['ino']=999
        with self.assertRaises(ValueError):verify_receipt(row,self.closure,self.cfg,self.task,changed,receipt)

    def test_new_recovery_still_requires_identical_scientific_inputs(self):
        from fullft_resume_20261126 import require_resume
        keys=('run','output','task','seed','pretraining_seed','internal_split_seed','bootstrap_seed',
            'source_binding','store','providers_sha256','authority','invoking_authority','kind','mode')
        old={key:key for key in keys};old['run']=self.row['run']
        previous=dict(self.row,status=STATUS,resource_closed=True)
        with patch('fullft_startup_failure_20261127.require_retired_startup',return_value={}):
            require_resume(previous,self.closure,old,dict(old))
            for key in keys:
                with self.subTest(key=key):
                    changed=dict(old);changed[key]='changed'
                    with self.assertRaises(ValueError):require_resume(previous,self.closure,old,changed)


if __name__=='__main__':unittest.main()
