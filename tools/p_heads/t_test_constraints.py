"""New physical head math and routing against an independent numpy FP64 solve."""
import unittest
import numpy as np
import torch
from phychem_mfm.model.p_constraint_heads import charge_equilibrium,fukui_projection,install_physical_heads

class ConstraintTests(unittest.TestCase):
    def test_charge_reference_and_sum(self):
        rng=np.random.default_rng(7)
        pos=torch.tensor(rng.normal(size=(17,3)),dtype=torch.float32)
        chi=torch.tensor(rng.normal(size=(17,1)),dtype=torch.float32,requires_grad=True)
        u=torch.tensor(rng.normal(size=(17,1)),dtype=torch.float32,requires_grad=True)
        batch=torch.tensor([0]*6+[1]*11)
        for q in (-1,0,1):
            actual=charge_equilibrium(chi,u,pos,batch,q)
            for m in (0,1):
                rows=batch==m;p=pos[rows].numpy().astype(float);n=len(p)
                matrix=14.3996/np.sqrt(((p[:,None]-p[None])**2).sum(-1)+1.)
                matrix+=np.diag(np.logaddexp(0,u.detach().numpy()[rows,0].astype(float)))
                system=np.block([[matrix,np.ones((n,1))],[np.ones((1,n)),np.zeros((1,1))]])
                expected=np.linalg.solve(system,np.r_[-chi.detach().numpy()[rows,0],q])[:n]
                np.testing.assert_allclose(actual.detach().numpy()[rows,0],expected,atol=1e-6,rtol=1e-5)
                self.assertLessEqual(abs(float(actual[rows].sum())-q),1e-6+1e-6*n)
            actual.square().sum().backward()
        self.assertTrue(torch.isfinite(chi.grad).all());self.assertTrue(torch.isfinite(u.grad).all())
    def test_fukui_sum_and_negative(self):
        torch.manual_seed(2)
        s=torch.randn(47,1,requires_grad=True);batch=torch.tensor([0]*17+[1]*30)
        value=fukui_projection(s,batch)
        for m in (0,1):self.assertLessEqual(abs(float(value[batch==m].sum())-1),1e-6)
        self.assertTrue((value<0).any());value.square().sum().backward()
        self.assertTrue(torch.isfinite(s.grad).all())
    def test_grouped_constraint_routing(self):
        from phychem_mfm.phase1.v3_contract import FieldSpec,LabelRegistry
        from phychem_mfm.model.v3_heads import V3HeadBank
        registry=LabelRegistry((FieldSpec('charge','P','charge','atom'),),'test','0'*64,'synthetic_fixture')
        bank=V3HeadBank(registry);install_physical_heads(bank,{'charge':{'kind':'charge','Q':-1}})
        bank.grouped_fields=True
        h=torch.randn(5,512);pos=torch.randn(5,3);batch=torch.tensor([0,0,1,1,1])
        out=bank(h,batch,pos,enabled_groups=('P',))['charge']
        for m in (0,1):self.assertLessEqual(abs(float(out[batch==m].sum())+1),1e-6+1e-6*int((batch==m).sum()))
if __name__=='__main__':unittest.main()
