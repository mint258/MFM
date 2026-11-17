"""Only the new PMA switch and its unchanged default execution."""
import math
import unittest
import torch
from phychem_mfm.model.v3_latent import MaskedAttention

class UniformAttentionTests(unittest.TestCase):
    def test_uniform_padding_and_parameter_count(self):
        torch.manual_seed(0)
        layer = MaskedAttention(256,512,256)
        count = sum(p.numel() for p in layer.parameters())
        layer.uniform_weights = True
        query = torch.randn(2,8,256)
        key = torch.randn(2,5,512)
        mask = torch.tensor([[1,1,1,0,0],[1,1,1,1,1]],dtype=torch.bool)
        first = layer(query,key,key,mask)
        changed = key.clone(); changed[~mask] = 1e8
        torch.testing.assert_close(first, layer(query,changed,changed,mask),rtol=0,atol=0)
        expected = layer.out((layer.v(key)*mask[...,None]).sum(1)/mask.sum(1)[:,None])
        torch.testing.assert_close(first,expected[:,None].expand_as(first),rtol=1e-5,atol=1e-6)
        self.assertEqual(count,sum(p.numel() for p in layer.parameters()))
    def test_disabled_bitwise_original_formula(self):
        torch.manual_seed(7)
        layer = MaskedAttention(256,512,256)
        query,key = torch.randn(2,8,256),torch.randn(2,5,512)
        mask = torch.tensor([[1,1,1,0,0],[1,1,1,1,1]],dtype=torch.bool)
        def split(x): return x.reshape(2,-1,8,32).transpose(1,2)
        q,k,v = split(layer.q(query)),split(layer.k(key)),split(layer.v(key))
        logits = (q@k.transpose(-1,-2))/math.sqrt(32)
        logits = logits.masked_fill(~mask[:,None,None,:],-torch.inf)
        result = (torch.softmax(logits,dim=-1)@v).transpose(1,2).reshape(2,8,256)
        original = layer.out(result)
        self.assertTrue(torch.equal(original,layer(query,key,key,mask)))
        layer.uniform_weights = False
        self.assertTrue(torch.equal(original,layer(query,key,key,mask)))
        fresh = MaskedAttention(256,512,256)
        fresh.load_state_dict(layer.state_dict(),strict=True)
        self.assertTrue(torch.equal(original,fresh(query,key,key,mask)))
if __name__ == '__main__': unittest.main()
