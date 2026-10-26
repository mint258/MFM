"""Real CPU dispatch tests of the observer; no CUDA acceptance is mocked."""
import pytest
import torch
from torch import nn
from precision_observer import observe


@pytest.fixture(autouse=True)
def preserve_rng_threads():
    state,threads=torch.get_rng_state(),torch.get_num_threads()
    torch.set_num_threads(1)
    try: yield
    finally:
        torch.set_rng_state(state); torch.set_num_threads(threads)


class Attention(nn.Module):
    def __init__(self,precision,*,bad_distance=False):
        super().__init__(); self.precision=precision; self.bad_distance=bad_distance; self.nheads=1; self.d_head=4
        self.dist_mlp=nn.Sequential(nn.Linear(1,1))
    def forward(self,value,pos,mask):
        difference=pos[:,:,None,:]-pos[:,None,:,:]
        squared=difference.square().sum(-1)
        self.dist_mlp(squared[...,None].float())
        q=value[:,None]
        with torch.autocast('cpu',dtype=torch.bfloat16,enabled=self.precision=='bf16'):
            score=torch.matmul(q,q.transpose(-2,-1))
        attention=torch.softmax(score.float(),-1)
        with torch.autocast('cpu',dtype=torch.bfloat16,enabled=self.precision=='bf16'):
            output=torch.matmul(attention,q)
        if self.bad_distance:
            # A normalization/distance component cast is a real contract failure.
            with torch.autocast('cpu',dtype=torch.bfloat16): self.dist_mlp(value.reshape(-1,1))
        return output[:,0].float()


class Geometry(nn.Module):
    def forward(self,value): return torch.exp(-value.square())


class Tiny(nn.Module):
    def __init__(self,precision,*,bad_distance=False,layers=1):
        super().__init__(); self.encoder=nn.Module(); self.encoder.backbone=nn.Module()
        rows=[]
        for _ in range(layers):
            layer=nn.Module(); layer.attn=Attention(precision,bad_distance=bad_distance); layer.norm=nn.LayerNorm(4); rows.append(layer)
        self.encoder.backbone.layers=nn.ModuleList(rows); self.encoder.geometry_head=Geometry()
    def forward(self,value):
        pos=value.new_zeros((value.shape[0],value.shape[1],3)); mask=torch.ones(value.shape[:2],dtype=torch.bool)
        for layer in self.encoder.backbone.layers: value=layer.norm(layer.attn(value,pos,mask))
        return self.encoder.geometry_head(value)


@pytest.mark.parametrize('precision',['fp32','bf16'])
def test_real_CPU_matmul_and_fp32_regions_observed_but_never_called_CUDA(precision):
    state=torch.get_rng_state(); model=Tiny(precision)
    try:
        with observe(model,precision,torch,device_type='cpu',expected_layers=1) as receipt:
            result=model(torch.ones(1,2,4))
        assert result.dtype==torch.float32 and receipt['status']=='OBSERVED_OPERATOR_INTERFACES'
        assert receipt['layers']['0']['QK'] and receipt['layers']['0']['AV']
        assert receipt['actual_device']=='cpu' and receipt['CUDA_acceptance'] is False
        assert all(receipt['coverage'].values())
        assert all(not module._forward_hooks and not module._forward_pre_hooks for module in model.modules())
    finally: torch.set_rng_state(state)


def test_real_wrong_distance_autocast_fails_and_hooks_close():
    model=Tiny('bf16',bad_distance=True)
    with pytest.raises(ValueError,match='left fp32'):
        with observe(model,'bf16',torch,device_type='cpu',expected_layers=1):
            model(torch.ones(1,2,4))
    assert all(not module._forward_hooks and not module._forward_pre_hooks for module in model.modules())


def test_six_layers_have_distinct_QK_softmax_AV_even_when_N_equals_head_width():
    model=Tiny('bf16',layers=6)
    with observe(model,'bf16',torch,device_type='cpu',expected_layers=6) as receipt:
        model(torch.ones(1,4,4))
    assert receipt['status']=='OBSERVED_OPERATOR_INTERFACES' and set(receipt['layers'])==set(map(str,range(6)))
    for row in receipt['layers'].values():
        assert row['QK']['inputs'][0]['shape']==[1,4,4]
        assert row['AV']['outputs'][0]['shape']==[1,4,4]
        assert row['softmax']['region']=='softmax'
        assert all(value['device']=='cpu' for value in row['QK']['inputs']+row['AV']['outputs'])


def test_missing_layers_are_NOT_OBSERVED_not_internal_precision_proof():
    model=Tiny('fp32')
    with observe(model,'fp32',torch,device_type='cpu',expected_layers=6) as receipt:
        model(torch.ones(1,2,4))
    assert receipt['status']=='NOT_OBSERVED' and receipt['CUDA_acceptance'] is False


def test_no_visible_bmm_does_not_claim_flash_internal_precision():
    model=Tiny('bf16')
    model.encoder.backbone.layers[0].attn.forward=lambda value,pos,mask:value
    with observe(model,'bf16',torch,device_type='cpu',expected_layers=1) as receipt:
        model(torch.ones(1,2,4))
    assert receipt['status']=='NOT_OBSERVED'
    assert receipt['layers']['0']['QK'] is None and receipt['layers']['0']['AV'] is None
