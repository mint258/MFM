"""Only directive-authorized T4/T5 new-logic unit tests."""
import unittest
import torch
from phychem_mfm.model.v3_latent import MolecularLatent,LatentSpec
from phychem_mfm.model.p_heads import SimpleMolecularReadout
from phychem_mfm.model.v3_heads import V3HeadBank
from phychem_mfm.phase1.v3_contract import FieldSpec,LabelRegistry

class ReadoutTests(unittest.TestCase):
    def test_T4_gate_one_and_padding(self):
        torch.manual_seed(11);m=MolecularLatent(LatentSpec(kind='pma',n_ref=53.64145,write_back=False,reconstruction=False))
        x=torch.randn(2,5,512);mask=torch.tensor([[1,1,0,0,0],[1,1,1,1,1]],dtype=torch.bool)
        count=sum(p.numel() for p in m.parameters());m.uniform_sum_gate=True
        out=m.finish(x,mask)
        clean=torch.where(mask[...,None],x,x.new_zeros(()))
        expected=torch.where(mask[...,None],m.sum_project(m.sum_norm(clean)),x.new_zeros(())).sum(1)/53.64145
        self.assertTrue(torch.equal(out[:,512:576],expected))
        with torch.no_grad():m.sum_gate.weight.fill_(1e5);m.sum_gate.bias.fill_(-1e5)
        changed=x.clone();changed[~mask]=1e8
        self.assertTrue(torch.equal(out,m.finish(changed,mask)))
        self.assertEqual(count,sum(p.numel() for p in m.parameters()))
    def test_T5_dimension_padding_and_linear_field(self):
        torch.manual_seed(12);m=SimpleMolecularReadout()
        x=torch.randn(2,5,512);mask=torch.tensor([[1,1,0,0,0],[1,1,1,1,1]],dtype=torch.bool)
        z=m.finish(x,mask);self.assertEqual(z.shape,(2,1025))
        expected=torch.cat((x[0,:2].mean(0),x[0,:2].sum(0)/53.64145,x.new_tensor([2.]).log()))
        self.assertTrue(torch.equal(z[0],expected))
        changed=x.clone();changed[~mask]=float('inf')
        self.assertTrue(torch.equal(z,m.finish(changed,mask)))
        registry=LabelRegistry((FieldSpec('m','P','molecule','graph'),),'fixture','0'*64,'synthetic_fixture')
        bank=V3HeadBank(registry);bank.enable_p_recipe_pma(1025)
        self.assertEqual(bank.field_heads[bank.keys['m']].in_features,1025)
    def test_disabled_T4_T5_bitwise_original_finish(self):
        torch.manual_seed(13);m=MolecularLatent(LatentSpec(kind='pma',n_ref=53.64145,write_back=False,reconstruction=False))
        x=torch.randn(2,5,512);mask=torch.tensor([[1,1,0,0,0],[1,1,1,1,1]],dtype=torch.bool)
        clean=torch.where(mask[...,None],x,x.new_zeros(()));q=m.z0.unsqueeze(0).expand(2,-1,-1)
        _,q=m.layers[0](clean,q,mask);projected=m.project(q)
        n=m.sum_norm(clean);gated=torch.sigmoid(m.sum_gate(n))*m.sum_project(n)
        total=torch.where(mask[...,None],gated,gated.new_zeros(())).sum(1)/53.64145
        original=torch.cat((projected.flatten(1),total,mask.sum(1,keepdim=True).to(x.dtype).log()),-1)
        self.assertTrue(torch.equal(original,m.finish(x,mask)))
        m.uniform_sum_gate=False
        self.assertTrue(torch.equal(original,m.finish(x,mask)))
if __name__=='__main__':unittest.main()