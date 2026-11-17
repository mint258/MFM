"""The single regression for preserving the original Fukui MLP body."""
import unittest
import torch
from phychem_mfm.model.v3_heads import V3HeadBank
from phychem_mfm.model.p_constraint_heads import install_physical_heads,fukui_projection
from phychem_mfm.phase1.v3_contract import FieldSpec,LabelRegistry

class OriginalFukuiMLPTest(unittest.TestCase):
    def test_original_module_parameters_and_projected_output(self):
        torch.manual_seed(0)
        registry=LabelRegistry((FieldSpec('fukui','P','reactivity','atom'),),'fixture','0'*64,'synthetic_fixture')
        bank=V3HeadBank(registry)
        original=bank.field_heads[bank.keys['fukui']]
        parameters=list(original.parameters());initial=[p.detach().clone() for p in parameters]
        h=torch.randn(7,512);pos=torch.randn(7,3);batch=torch.tensor([0,0,0,1,1,1,1])
        expected=fukui_projection(original(h),batch)
        install_physical_heads(bank,{'fukui':{'kind':'fukui','Q':1}})
        head=bank.field_heads[bank.keys['fukui']]
        self.assertIs(head.predict,original)
        self.assertTrue(all(p is q for p,q in zip(parameters,head.parameters())))
        self.assertTrue(all(torch.equal(p.detach(),saved) for p,saved in zip(parameters,initial)))
        self.assertTrue(torch.equal(head(h,pos,batch),expected))
if __name__=='__main__':unittest.main()
