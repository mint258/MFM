"""Actual accounting consistency, no job approval or fake Slurm execution."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import terminal as T


class TerminalTests(unittest.TestCase):
    def test_header_order_and_terminal_cancelled_steps(self):
        text='State|JobIDRaw|ExitCode\nCOMPLETED|12|0:0\nCANCELLED by 1264|12.batch|0:15\nRUNNING|999.batch|0:0\n'
        self.assertEqual(T.raw_rows(text,'12'),[('12','COMPLETED','0:0'),('12.batch','CANCELLED','0:15')])

    def check(self,text,state='COMPLETED',code='0:0',require=True):
        with tempfile.TemporaryDirectory()as folder:
            raw=Path(folder)/'sacct.txt';raw.write_text(text)
            p={'JobIDRaw':'12','State':state,'ExitCode':code,'UID':'1264'}
            account={'endpoint':T.Q.ENDPOINT,'uid':1264,'actual_parents':[p],'raw_sacct_reference':{'raw':True}}
            with patch.object(T.Q,'verify',return_value=raw),patch.object(T.Q,'load',return_value=account):
                return T.parent({'job_id':'12','uid':1264,'endpoint':T.Q.ENDPOINT},{'account':True},require)

    def test_actual_complete_parent_and_steps_not_live_or_mismatched(self):
        self.assertEqual(self.check('12|COMPLETED|0:0\n12.batch|COMPLETED|0:0\n')['State'],'COMPLETED')
        for text in ('12|COMPLETED|0:0\n12.batch|RUNNING|0:0\n',
                     '12|FAILED|1:0\n12.batch|FAILED|1:0\n','13|COMPLETED|0:0\n13.batch|COMPLETED|0:0\n'):
            with self.subTest(text=text),self.assertRaises(ValueError):self.check(text)

    def test_failed_terminal_is_resume_evidence_but_not_completed_production(self):
        raw='12|FAILED|1:0\n12.batch|FAILED|1:0\n12.extern|COMPLETED|0:0\n'
        self.assertEqual(self.check(raw,'FAILED','1:0',False)['State'],'FAILED')
        with self.assertRaisesRegex(ValueError,'producer C0'):self.check(raw,'FAILED','1:0',True)

    def test_machine_resume_uses_known_attempt_plan_startup_and_terminal_steps(self):
        from ..uff3_candidate_v1.ledger_resume import resume_authority
        from ..uff3_candidate_v1 import core as C
        import json
        with tempfile.TemporaryDirectory()as folder:
            root=Path(folder);(root/'molecules').mkdir()
            def put(name,obj):
                path=root/name;path.write_text(json.dumps(obj));return T.Q.reference(path)
            source={'path':'frozen-source-fixture','bytes':0,'sha256':'0'*64}
            old=put('old_plan.json',{'output_directory':str(root),'source_manifest':source,'recipe_sha256':C.recipe_sha()})
            proof=put('old_startup.json',{'uid':1264,'endpoint':T.Q.ENDPOINT,'job_id':'12',
                  'request':{'producer_plan_reference':old}})
            raw=root/'raw.sacct';raw.write_text('12|FAILED|1:0\n12.batch|FAILED|1:0\n')
            account=put('account.json',{'endpoint':T.Q.ENDPOINT,'uid':1264,'raw_sacct_reference':T.Q.reference(raw),
                        'actual_parents':[{'JobIDRaw':'12','UID':'1264','State':'FAILED','ExitCode':'1:0'}]})
            put('derived_runtime_plan_old.json',{'original_launcher_plan_reference':old})
            binding={'output_scope_root':str(root),'source_manifest':source,'recipe_sha256':C.recipe_sha(),
                'previous_allocations':[{'plan_reference':old,'startup_proof_reference':proof,'accounting_reference':account}]}
            plan={'source_manifest':source,'recipe_sha256':C.recipe_sha(),'resume_binding':binding}
            self.assertEqual(resume_authority(plan,root),[])
            put('derived_runtime_plan_uninventoried.json',{'original_launcher_plan_reference':{'path':'unknown','bytes':0,'sha256':'f'*64}})
            with self.assertRaisesRegex(ValueError,'All historical stage attempts'):resume_authority(plan,root)

if __name__=='__main__':unittest.main()