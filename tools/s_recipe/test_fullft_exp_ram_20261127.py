import copy
import unittest
from fullft_ram_envelope_20261127 import GiB,read
from fullft_exp_ram_20261127 import PROOF,SCHEMA,require_proof,choose,future_exp_ram,validate_exp_contract
from storage_20261122 import CONTROL as C


class ExpRam(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.proof=require_proof()
        cls.previous=read(C/'execution.json')['statistics']['S_FT_S_N2_3M_exp_LogD_s2_attempt0']
        cls.old=read(cls.previous['configuration'])

    def config(self):
        c=copy.deepcopy(self.old)
        c.update(peak_ram_bytes=6*GiB,host_ram_envelope_source=str(PROOF),
            host_ram_runtime_python=self.proof['python'])
        return c

    def test_same_scientific_partial_can_resume_with_closed_six_GiB_estimate(self):
        from finetune_extension_20261124 import validate
        from fullft_resume_20261126 import require_resume
        c=self.config()
        validate(c)
        require_resume(self.previous,read(self.previous['lifecycle_record']),self.old,c)
        result=future_exp_ram(read(C/'execution.json'),c['providers_sha256'],python=self.proof['python'],
            task=c['task'],state=dict(future_fullft_exp_ram_policy=SCHEMA))
        self.assertEqual(result,(6*GiB,str(PROOF)))

    def test_larger_subsequent_peak_cannot_keep_smaller_envelope(self):
        p=self.proof
        self.assertIsNone(choose('exp.LogD',p['python'],p['providers_sha256'],p,6*GiB))

    def test_QM9_cannot_receive_Exp_envelope(self):
        c=self.config();c['task']='qm9.homo'
        with self.assertRaises(ValueError):validate_exp_contract(c)
        p=self.proof
        self.assertIsNone(choose(c['task'],p['python'],p['providers_sha256'],p,3*GiB))

    def test_untraced_interpreter_or_changed_provider_is_rejected(self):
        c=self.config();c['host_ram_runtime_python']='/untraced/python'
        with self.assertRaises(ValueError):validate_exp_contract(c)
        c=self.config();c['providers_sha256']={}
        with self.assertRaises(ValueError):validate_exp_contract(c)
        p=self.proof
        self.assertIsNone(choose('exp.LogD','/untraced/python',p['providers_sha256'],p,3*GiB))


if __name__=='__main__':unittest.main()
