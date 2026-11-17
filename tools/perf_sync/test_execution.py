"""Tests for newly introduced execution logic; these are not GPU acceptance."""
from copy import deepcopy

import pytest
import torch
from torch_geometric.data import Batch, Data
from torch_geometric.utils import to_dense_batch

from phychem_mfm.model.perf_sync import (prepare_layout, batch_layout, dense_batch,
    unpack_dense, finite_checks, check_finite, configure)
from phychem_mfm.model.attention import DenseGeoSelfAttention
from phychem_mfm.model.v3_latent import MaskedAttention
from phychem_mfm.phase1.perf_sync_step import StepBuffer, make_optimizer
from phychem_mfm.phase1.perf_sync_transfer import share_tensors, map_tensors


def packed():
    return Batch.from_data_list([Data(x=torch.zeros((n,1),dtype=torch.long),
        pos=torch.arange(3*n,dtype=torch.float32).reshape(n,3)) for n in (3,1,5)])


def test_reader_layout_preserves_dense_order_and_backward():
    data = prepare_layout(packed())
    old = torch.randn((9,7), requires_grad=True)
    new = old.detach().clone().requires_grad_()
    baseline, mask = to_dense_batch(old, data.batch)
    with batch_layout(data):
        actual, actual_mask = dense_batch(new, data.batch)
        assert torch.equal(baseline, actual) and torch.equal(mask, actual_mask)
        restored = unpack_dense(actual.square(), actual_mask)
    expected = baseline.square()[mask]
    assert torch.equal(expected, restored)
    expected.sum().backward()
    restored.sum().backward()
    assert torch.equal(old.grad, new.grad)


def test_invalid_reader_coordinates_rejected_before_forward():
    data = packed()
    data.pos[0,0] = float('nan')
    with pytest.raises(ValueError, match='coordinates'):
        prepare_layout(data)


def test_gpu_buffer_preserves_python_double_sums_and_resume_window():
    buffer = StepBuffer(device='cpu')
    initial = 0.12345678912345
    buffer.seed_family({'energy': (initial, 7)})
    expected = initial
    norms = [1., 1.0000001192092896, 0.99]
    rows = []
    clipped = 0
    for i in range(1000):
        loss = torch.tensor((i%11)*0.10234763)
        norm = torch.tensor(norms[i%3])
        expected += float(loss)
        clipped += int(float(norm)>1.00000001)
        buffer.add(dict(samples=(i+1)*32, updates=i+1, lr=3e-4, seconds=i/10),
                   loss, norm, 1.00000001, {'energy':loss}, [])
        if i in (499,999):
            saved, family, count = buffer.drain()
            rows.extend(saved)
            assert family['energy'] == (expected, i+8)
            assert count == clipped
            clipped = 0
    assert len(rows) == 1000
    assert rows[0]['total'] == float(torch.tensor(0.))
    assert rows[-1]['updates'] == 1000


def test_deferred_internal_nonfinite_is_not_silently_dropped():
    with finite_checks() as flags:
        assert check_finite(torch.tensor([float('nan')]))
    buffer = StepBuffer(device='cpu')
    buffer.add({}, torch.tensor(1.), torch.tensor(1.), 2., {}, flags)
    with pytest.raises(RuntimeError, match='internal activation'):
        buffer.drain()


def test_shared_transport_keeps_source_values_and_typed_batch():
    data = packed()
    source = {'data':data, 'values':[torch.arange(9),('layout',3)]}
    shared = share_tensors(source)
    assert isinstance(shared['data'], type(data))
    assert shared['data'].x.is_shared() and shared['values'][0].is_shared()
    copied = map_tensors(shared, lambda value:value.clone()+1)
    assert torch.equal(shared['values'][0], torch.arange(9))
    assert torch.equal(copied['values'][0], torch.arange(9)+1)
    assert torch.equal(source['data'].x, data.x)


@pytest.mark.parametrize('radius',[False,True])
def test_sdpa_distance_and_padding_bias_forward_backward(radius):
    torch.manual_seed(3)
    old = DenseGeoSelfAttention(16,4,use_radius_mask=radius,radius=1.2)
    new = deepcopy(old)
    new.perf_sync_sdpa = True
    x = torch.randn((2,5,16),requires_grad=True)
    y = x.detach().clone().requires_grad_()
    pos = torch.randn((2,5,3))
    mask = torch.tensor([[True]*5,[True,True,False,False,False]])
    a,_ = old(x,pos,mask)
    b,_ = new(y,pos,mask)
    torch.testing.assert_close(a,b,atol=2e-6,rtol=2e-5)
    a.square().sum().backward()
    b.square().sum().backward()
    torch.testing.assert_close(x.grad,y.grad,atol=2e-6,rtol=2e-5)
    for p,q in zip(old.parameters(),new.parameters()):
        torch.testing.assert_close(p.grad,q.grad,atol=3e-6,rtol=3e-5)
    assert old.state_dict().keys() == new.state_dict().keys()


def test_sdpa_latent_cross_attention_with_padding():
    torch.manual_seed(9)
    old = MaskedAttention(8,12,8,width=16,heads=4)
    new = deepcopy(old)
    new.perf_sync_sdpa = True
    query,key,value = torch.randn(2,3,8),torch.randn(2,5,12),torch.randn(2,5,12)
    mask = torch.tensor([[True]*5,[True,True,False,False,False]])
    torch.testing.assert_close(old(query,key,value,mask),new(query,key,value,mask),atol=2e-6,rtol=2e-5)


def test_default_configuration_does_not_touch_non_transformer_encoders():
    # Existing coordinate-free registry consumers are outside this study.
    configure(torch.nn.Linear(3,3), {})


def test_compile_preserves_aliases_checkpoint_and_dynamic_inputs(monkeypatch):
    original = torch.nn.Module.compile
    def eager(module, **kwargs):
        return original(module, backend='eager', **kwargs)
    monkeypatch.setattr(torch.nn.Module, 'compile', eager)
    class Model(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.encoder = torch.nn.Module()
            self.encoder.backbone = torch.nn.Module()
            self.encoder.backbone.layers = torch.nn.ModuleList([torch.nn.Linear(3,3)])
            self.heads = torch.nn.Linear(3,2)
    model = Model()
    before = deepcopy(model.state_dict())
    identities = [id(parameter) for parameter in model.parameters()]
    configure(model, {'compile':'encoder_heads'})
    for length in (2,7):
        x = torch.randn(length,3)
        layer = model.encoder.backbone.layers[0]
        assert torch.equal(layer(x),layer.forward(x))
        assert torch.equal(model.heads(x),model.heads.forward(x))
    assert list(before) == list(model.state_dict())
    assert identities == [id(parameter) for parameter in model.parameters()]
    model.load_state_dict(before,strict=True)
    configure(model,{})
    assert model.heads._compiled_call_impl is None


def test_optimizer_default_and_fallback_preserve_checkpoint_loading(monkeypatch):
    parameters = [torch.nn.Parameter(torch.ones(3))]
    c = dict(lr=3e-4,betas=(.9,.95),weight_decay=.01)
    baseline = make_optimizer(parameters,c)
    assert baseline.defaults['fused'] is None
    original = torch.optim.AdamW
    def unsupported(*args,**kwargs):
        if kwargs.get('fused'):raise NotImplementedError('device lacks fused kernels')
        return original(*args,**kwargs)
    monkeypatch.setattr(torch.optim,'AdamW',unsupported)
    candidate = make_optimizer(parameters,dict(c,step_overhead={'fused_optimizer':True}))
    assert candidate.perf_sync_backend == 'foreach'
    candidate.load_state_dict(baseline.state_dict())
