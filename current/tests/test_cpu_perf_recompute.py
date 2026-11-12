"""Recomputation removal preserves head values, derivatives, RNG and state keys."""
from copy import deepcopy
import torch
from phychem_mfm.model.heads import EquivariantDenoisingHead


def test_checkpoint_policy_preserves_function_gradients_rng_and_state():
    torch.manual_seed(17)
    old=EquivariantDenoisingHead(4,hidden_dim=8,pair_chunk_size=3,message_layers=1)
    new=deepcopy(old);new.activation_checkpointing=False
    assert list(old.state_dict())==list(new.state_dict())
    a=torch.randn(5,4,requires_grad=True);b=a.detach().clone().requires_grad_()
    pos=torch.randn(5,3);batch=torch.tensor([0,0,0,1,1])
    rng=torch.get_rng_state().clone()
    first=old(a,pos,batch);first.square().sum().backward()
    assert torch.equal(torch.get_rng_state(),rng)
    second=new(b,pos,batch);second.square().sum().backward()
    torch.testing.assert_close(first,second,rtol=0,atol=0)
    torch.testing.assert_close(a.grad,b.grad,rtol=1e-6,atol=1e-7)
    for (name,p),(other,q) in zip(old.named_parameters(),new.named_parameters()):
        assert name==other
        torch.testing.assert_close(p.grad,q.grad,rtol=1e-6,atol=1e-7)
    assert torch.equal(torch.get_rng_state(),rng)
