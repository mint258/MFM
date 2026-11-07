"""Continuation inventories actual immutable attempt markers, no Native calls."""
import json
from pathlib import Path
import tempfile
import unittest
from ..alpha_runtime_v1 import common as Q
from .followup import previous


class FollowupTests(unittest.TestCase):
    def test_all_prior_attempts_need_real_matching_account_metadata(self):
        with tempfile.TemporaryDirectory()as folder:
            root=Path(folder);source={'path':'frozen-source','bytes':0,'sha256':'0'*64}
            def put(name,value):
                path=root/name;path.write_text(json.dumps(value));return Q.reference(path)
            p=put('plan.json',{'source_manifest':source,'output_directory':str(root)})
            startup=put('startup.json',{'job_id':'12'})
            marker={'original_launcher_plan_reference':p,'original_startup_proof_reference':startup}
            put('derived_runtime_plan_old.json',marker);put('derived_runtime_plan_alias.json',marker)
            account=put('account.json',{'actual_parents':[{'JobIDRaw':'12','State':'FAILED','ExitCode':'1:0'}]})
            b=previous(root,source,[account,account])
            self.assertEqual(b['output_scope_root'],str(root));self.assertEqual(len(b['previous_allocations']),1)
            self.assertEqual(b['previous_allocations'][0]['plan_reference'],p)
            with self.assertRaisesRegex(ValueError,'every old attempt'):previous(root,source,[])
            other=put('other-plan.json',{'source_manifest':{'changed':True},'output_directory':str(root)})
            put('derived_runtime_plan_wrong_source.json',{**marker,'original_launcher_plan_reference':other})
            with self.assertRaisesRegex(ValueError,'same source'):previous(root,source,[account])


if __name__=='__main__':unittest.main()