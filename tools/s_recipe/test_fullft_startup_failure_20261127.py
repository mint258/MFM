import copy
import json
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
from fullft_startup_failure_20261127 import (C,STATUS,validate_failure,require_pending,
    retire_entries,verify_receipt,validate_wait_exit,standby_terminal_action)
from fullft_startup_failure_20261127 import POLICY,digest,require_cold_origin,require_wait_accounting


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

    def wait_record(self):
        return dict(run=self.row['run'],job_id=self.row['standby_job_id'],node=self.row['node'],
            status='WAITING_CONTINUATION_REQUIRED',producer=dict(pid=55,uid=1278,start_ticks=789),
            started_at=1002.,ended_at=1100.,owned_descendants_exited=True)

    def test_closed_unknown_native_exits_wait_without_replaying_fit(self):
        self.assertEqual(standby_terminal_action(self.closure),'STOP_UNKNOWN_EXIT')
        self.assertEqual(standby_terminal_action(dict(self.closure,status='COMPLETE',exit_code=0)),'NO_REPLAY')
        self.assertEqual(standby_terminal_action(dict(self.closure,status='CONTINUATION_REQUIRED',exit_code=75)),'RESUME')
        for key,value in (('ended_at',None),('owned_descendants_exited',False),('observer_joined',False)):
            with self.assertRaises(ValueError):standby_terminal_action(dict(self.closure,**{key:value}))
        with self.assertRaises(ValueError):standby_terminal_action(dict(self.closure,exit_code=1))

    def test_wait_only_exit_requires_exact_task_owner_and_actual_code(self):
        wait=self.wait_record()
        validate_wait_exit(self.h,self.row,wait,'FAILED|75:0|100')
        validate_wait_exit(self.h,self.row,dict(wait,status='NATIVE_UNKNOWN_EXIT_NO_FIT_REPLAY'),'FAILED|1:0|0')
        for key,value in (('job_id',4540892),('run','S_other'),('node','compute-0-22'),
                ('owned_descendants_exited',False),('ended_at',999.)):
            with self.assertRaises(ValueError):validate_wait_exit(self.h,self.row,dict(wait,**{key:value}),'FAILED|75:0|100')
        for key,value in (('uid',1283),('pid',None),('start_ticks',None)):
            changed=copy.deepcopy(wait);changed['producer'][key]=value
            with self.assertRaises(ValueError):validate_wait_exit(self.h,self.row,changed,'FAILED|75:0|100')

    def test_wait_only_exit_rejects_running_success_or_fit_takeover(self):
        wait=self.wait_record()
        for actual in ('RUNNING|0:0|100','COMPLETED|0:0|100','FAILED|1:0|100','FAILED|75:0|bad'):
            with self.assertRaises(ValueError):validate_wait_exit(self.h,self.row,wait,actual)
        for status in ('NATIVE_CLOSED_READY_FOR_ACTUAL_SLURM_FIT','NATIVE_ALREADY_COMPLETE_NO_FIT_REPLAY'):
            with self.assertRaises(ValueError):validate_wait_exit(self.h,self.row,dict(wait,status=status),'FAILED|75:0|100')

    def test_wait_only_receipt_binds_closed_wait_and_verified_absence(self):
        row=dict(self.row,status=STATUS,resource_closed=True)
        proof=validate_wait_exit(self.h,row,self.wait_record(),'FAILED|75:0|100')
        receipt=dict(self.valid(),**proof,status='FAILED_STARTUP_OWN_RESOURCES_CLOSED',
            native_producer_verified_gone=True,standby_wait_producer_verified_gone=True)
        self.assertTrue(verify_receipt(row,self.closure,self.cfg,self.task,self.files,receipt))
        for key,value in (('standby_wait_digest','bad'),('standby_wait_producer_verified_gone',False)):
            with self.assertRaises(ValueError):verify_receipt(row,self.closure,self.cfg,self.task,self.files,dict(receipt,**{key:value}))
        changed=copy.deepcopy(receipt);changed['standby_wait_record']['producer']['start_ticks']=790
        with self.assertRaises(ValueError):verify_receipt(row,self.closure,self.cfg,self.task,self.files,changed)

    def absent_output(self):
        output=Path(self.cfg['output'])
        return {'absent_output':dict(path=str(output),absent=True,parent=dict(
            path=str(output.parent),uid=1278,ino=99,dev=2049,directory=True))}

    def cold_first(self):
        self.h=self.cfg['run']+'_attempt0'
        self.row['configuration']=str(C/(self.h+'_configuration.json'))
        self.task.update(native_handle=self.h,configuration=self.row['configuration'])
        self.closure['native_handle']=self.h

    def test_zero_science_absence_has_explicit_fresh_retry_not_fake_checkpoint(self):
        self.cold_first()
        absent=self.absent_output()
        value=validate_failure(self.h,self.row,self.closure,self.cfg,self.task,absent)
        self.assertEqual(value['resume_kind'],'FRESH_AFTER_ZERO_SCIENCE_STARTUP')
        self.assertIsNone(value['actual_native_exit_code'])
        self.assertEqual(value['files'],absent)
        self.assertNotIn('complete_state.pt',value['files'])

    def test_cold_receipt_rejects_changed_absence_owner_or_existing_partial(self):
        self.cold_first()
        absent=self.absent_output()
        row=dict(self.row,status=STATUS,resource_closed=True)
        value=validate_failure(self.h,row,self.closure,self.cfg,self.task,absent)
        receipt=dict(value,status='FAILED_STARTUP_OWN_RESOURCES_CLOSED',
            native_producer_verified_gone=True,standby_actual='CANCELLED by 1278|0:0|0')
        self.assertTrue(verify_receipt(row,self.closure,self.cfg,self.task,absent,receipt))
        with self.assertRaises(ValueError):verify_receipt(row,self.closure,self.cfg,self.task,self.files,receipt)
        for key,wrong in (('path','/other/output'),('absent',False)):
            bad=copy.deepcopy(absent);bad['absent_output'][key]=wrong
            with self.assertRaises(ValueError):validate_failure(self.h,row,self.closure,self.cfg,self.task,bad)
        bad=copy.deepcopy(absent);bad['absent_output']['parent']['uid']=1283
        with self.assertRaises(ValueError):validate_failure(self.h,row,self.closure,self.cfg,self.task,bad)

    def test_absence_snapshot_never_mistakes_partial_or_dangling_link_for_fresh(self):
        from fullft_startup_failure_20261127 import snapshots
        with tempfile.TemporaryDirectory(prefix='S_startup_absence_') as directory:
            output=Path(directory)/'fit';cfg=dict(output=str(output))
            self.assertEqual(snapshots(cfg)['absent_output']['path'],str(output))
            output.mkdir();(output/'complete_state.pt').write_bytes(b'partial')
            with self.assertRaises(FileNotFoundError):snapshots(cfg)
            (output/'complete_state.pt').unlink();output.rmdir()
            output.symlink_to(Path(directory)/'nonexistent_target',target_is_directory=True)
            with self.assertRaises(FileNotFoundError):snapshots(cfg)

    def test_missing_partial_cannot_be_reset_through_a_cold_retry_chain(self):
        with self.assertRaises(ValueError):require_cold_origin(self.h,self.cfg)
        with tempfile.TemporaryDirectory(prefix='S_startup_chain_') as directory:
            control=Path(directory);previous=self.cfg['run']+'_attempt0'
            path=control/(previous+'_startup_failure_settlement.json')
            prior=dict(policy=POLICY,handle=previous,run=self.cfg['run'],
                status='FAILED_STARTUP_OWN_RESOURCES_CLOSED',resume_kind='FRESH_AFTER_ZERO_SCIENCE_STARTUP',
                native_producer_verified_gone=True,actual_native_exit_code=None,exit_code_observed=False,
                files=self.absent_output())
            path.write_text(json.dumps(prior))
            cfg=dict(self.cfg,zero_science_retry_origin=dict(receipt=str(path),digest=digest(prior)))
            self.assertTrue(require_cold_origin(self.h,cfg,control))
            prior['resume_kind']='PARTIAL_STATE';path.write_text(json.dumps(prior))
            cfg['zero_science_retry_origin']['digest']=digest(prior)
            with self.assertRaises(ValueError):require_cold_origin(self.h,cfg,control)

    def test_persistent_accounting_keeps_exact_owner_and_job_after_live_cache_expiry(self):
        actual='FAILED|1:0|1'
        info=dict(JobIDRaw='4540891',UID='1278',JobName=self.h,NodeList=self.row['node'],
            State='FAILED',ExitCode='1:0',ElapsedRaw='1')
        require_wait_accounting(info,actual,self.h,4540891,self.row['node'])
        for key,value in (('JobIDRaw','4540892'),('UID','1283'),('JobName','S_other'),
                ('NodeList','compute-0-22'),('State','RUNNING'),('ExitCode','75:0'),('ElapsedRaw','2')):
            with self.assertRaises(ValueError):require_wait_accounting(dict(info,**{key:value}),
                actual,self.h,4540891,self.row['node'])


if __name__=='__main__':unittest.main()
