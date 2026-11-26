from copy import deepcopy
from unittest.mock import patch
import unittest
from fullft_ram_envelope_20261127 import C,GiB,read,future_ram
from fullft_physical_ram_20261127 import SCHEMA,PROOF,require_physical_proof


class PhysicalIntegration(unittest.TestCase):
    def test_closed_partial_can_change_only_host_resources_and_resume_same_science(self):
        from finetune_extension_20261124 import validate
        from fullft_resume_20261126 import require_resume
        previous=read(C/'execution.json')['statistics']['S_FT_S_N1_3M_qm9_homo_s1_attempt0']
        old=read(previous['configuration']);new=deepcopy(old)
        proof=require_physical_proof()
        new.update(peak_ram_bytes=8*GiB,host_ram_envelope_source=str(PROOF),host_ram_runtime_python=proof['python'])
        validate(new)
        require_resume(previous,read(previous['lifecycle_record']),old,new)
        bad=deepcopy(new);bad['host_ram_runtime_python']='/untraced'
        with self.assertRaises(ValueError):validate(bad)

    def test_an_untraced_interpreter_never_receives_eight_gib(self):
        ledger=read(C/'execution.json');proof=require_physical_proof()
        original_read=read
        def replacement(path):
            if path==C/'current_state.json':return dict(future_fullft_ram_policy=SCHEMA)
            return original_read(path)
        with patch('fullft_ram_envelope_20261127.read',side_effect=replacement):
            ram,source=future_ram(ledger,proof['providers_sha256'],python=proof['python'])
            self.assertEqual(ram,8*GiB);self.assertEqual(source,str(PROOF))
            ram,_=future_ram(ledger,proof['providers_sha256'],python='/untraced')
            self.assertGreaterEqual(ram,16*GiB)


if __name__=='__main__':unittest.main()
