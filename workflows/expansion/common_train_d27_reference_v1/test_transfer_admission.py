"""Tiny metadata admission/launcher routing tests; no input bodies or scheduler."""
import copy
from pathlib import Path
import unittest
from .transfer import MODULE,arguments,launcher_binding


class Admission(unittest.TestCase):
    def fixture(self):
        ref=lambda path:dict(path=path,bytes=1,sha256='a'*64)
        source,entry,planref=map(ref,('/fixture/transfer.py','/fixture/entry.py','/fixture/plan.json'))
        argv=['/fixture/python','-I','-B',entry['path'],MODULE,'--plan',planref['path'],'--startup-proof','/fixture/proof.json']
        plan=dict(execution_argv=argv,code_references=[source,entry])
        proof=dict(uid=1264,job_id='FIXTURE',boot_id='CURRENT_BOOT',request=dict(
            producer_plan_reference=planref,execution_argv=argv,source_references=[source,entry]))
        return plan,proof,planref,source,entry

    def test_old_boot_or_changed_executed_entry_cannot_bind_current_source(self):
        args=self.fixture();launcher_binding(*args,'CURRENT_BOOT','FIXTURE')
        with self.assertRaisesRegex(ValueError,'boot'):launcher_binding(*args,'OTHER_BOOT','FIXTURE')
        changed=copy.deepcopy(args);changed[1]['request']['source_references'][1]={**changed[1]['request']['source_references'][1],'sha256':'b'*64}
        with self.assertRaisesRegex(ValueError,'source pins'):launcher_binding(*changed,'CURRENT_BOOT','FIXTURE')

    def test_node_launcher_direct_close_and_existing_inventory_cli_remain_distinct(self):
        direct=arguments(['--plan','/fixture/p','--startup-proof','/fixture/s'])
        explicit=arguments(['close','--plan','/fixture/p','--startup-proof','/fixture/s'])
        self.assertEqual(vars(direct),vars(explicit));self.assertEqual(direct.action,'close')
        inventory=arguments(['inventory','--catalog','/fixture/c','--destination-root','/gfshome/alpha/f','--output','/fixture/o'])
        self.assertEqual(inventory.action,'inventory');self.assertEqual(inventory.catalog,Path('/fixture/c'))


if __name__=='__main__':unittest.main()
