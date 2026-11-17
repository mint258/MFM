"""New decoder identity initialization and molecule isolation."""
import unittest
import torch
from phychem_mfm.model.p_heads import AtomAttentionDecoder
class DecoderTests(unittest.TestCase):
    def test_identity_and_isolation(self):
        torch.manual_seed(1)
        model=AtomAttentionDecoder()
        x=torch.randn(7,512);batch=torch.tensor([0,0,0,1,1,1,1])
        self.assertTrue(torch.equal(x,model(x,batch)))
        torch.nn.init.normal_(model.attention.out.weight,std=.02)
        first=model(x,batch)
        changed=x.clone();changed[batch==1]+=10
        second=model(changed,batch)
        torch.testing.assert_close(first[batch==0],second[batch==0],rtol=0,atol=0)
    def test_grouped_pair_atomic_feature_route(self):
        from phychem_mfm.model.v3_heads import _PairHead
        from phychem_mfm.model.v31_grouped_heads import _pairs
        torch.manual_seed(11)
        head=_PairHead(512,1,64)
        h=torch.randn(4,512);pos=torch.randn(4,3)
        index=torch.tensor([[0,1,2],[1,2,3]])
        value=_pairs([head],h,pos,[index])[0]
        torch.testing.assert_close(value,head(h,pos,index),rtol=1e-5,atol=1e-6)
    def test_failed_head_falls_back_before_grouping(self):
        from phychem_mfm.phase1.v3_contract import FieldSpec,LabelRegistry
        from phychem_mfm.model.v3_heads import V3HeadBank
        registry=LabelRegistry(tuple(FieldSpec(n,'P','charge','atom') for n in ('a','b')),'test','0'*64,'synthetic_fixture')
        bank=V3HeadBank(registry);bank.grouped_fields=True
        h=torch.randn(4,512);pos=torch.randn(4,3);batch=torch.tensor([0,0,1,1])
        baseline=bank(h,batch,pos,enabled_groups=('P',))
        class AddOne(torch.nn.Module):
            def forward(self,h,batch):return h+1
        bank.atom_decoder=AddOne();bank.atom_decoder_fields=('a',)
        actual=bank(h,batch,pos,enabled_groups=('P',))
        torch.testing.assert_close(actual['b'],baseline['b'],rtol=1e-5,atol=1e-6)
        self.assertFalse(torch.allclose(actual['a'],baseline['a']))
if __name__=='__main__':unittest.main()
