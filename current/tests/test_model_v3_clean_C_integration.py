"""Ordinary C construction/config/restore tests; no compensation or physics acceptance."""
from copy import deepcopy
import pytest
import torch
from torch import nn
from torch_geometric.data import Data

from phychem_mfm.model.v3_architecture import (
    ArchitectureOptions,build_architecture_model,configuration_with_architecture,
    source_s_architecture_configuration)
from phychem_mfm.model.v3_distance_bias import KEY,common_parameter_mapping
from phychem_mfm.model.v3_performance import PerformanceOptions,build_performance_model,install_training_performance
from phychem_mfm.model.v3_heads import V3HeadBank
from phychem_mfm.phase1.v3_contract import FieldSpec,LabelRegistry


@pytest.fixture(autouse=True)
def ordinary_CPU():
    precision=torch.get_float32_matmul_precision();cudnn=torch.backends.cudnn.allow_tf32
    threads=torch.get_num_threads()
    with torch.random.fork_rng(devices=[]):
        torch.set_num_threads(1);torch.set_float32_matmul_precision('highest')
        torch.backends.cudnn.allow_tf32=False
        try:yield
        finally:
            torch.set_num_threads(threads)
            torch.set_float32_matmul_precision(precision);torch.backends.cudnn.allow_tf32=cudnn


def configuration(kind='C1-0',bias=None):
    cfg={'architecture':{'preset':'shared_light'},
        'backbone':{'dim':512,'layers':6,'heads':8,'ff_mult':2,'dropout':0.,
            'use_dist_bias':True,'use_radius_mask':False,'radius':8.},
        'head':{'profile':'phase1','geometry_head':'equivariant_noise',
            'geometry_hidden_dim':16,'geometry_message_layers':0}}
    if bias is not None:cfg['backbone'][KEY]=bias
    if kind!='C1-0':cfg=configuration_with_architecture(cfg,ArchitectureOptions(distance_bias=kind))
    return cfg


def seeded(cfg):
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(1742)
        model=build_architecture_model(cfg)
        after=torch.get_rng_state().clone()
    return model,after


def state_equal(a,b):
    assert set(a)==set(b)
    for key in a:
        if isinstance(a[key],torch.Tensor):assert torch.equal(a[key],b[key]),key
        else:assert a[key]==b[key],key


@pytest.fixture(scope='module',params=('C1-0','C1-a','C1-b'))
def models(request):
    a,ar=seeded(configuration(request.param));b,br=seeded(configuration(request.param,False))
    return request.param,a,b,ar,br


def test_only_exact_Dense_head_constants_are_removed_and_all_common_bytes_RNG_match(models):
    kind,a,b,ar,br=models;mapping=common_parameter_mapping(a,b)
    assert torch.equal(ar,br)
    assert mapping['removed_scalar_count']==(48 if kind=='C1-0' else 0)
    assert len(mapping['removed'])==(6 if kind=='C1-0' else 0)
    old,new=dict(a.named_parameters()),dict(b.named_parameters())
    assert set(old)-set(new)==set(mapping['removed'])
    for name in mapping['common']:assert torch.equal(old[name],new[name]),name
    for layer in b.backbone.layers:
        assert layer.attn.distance_bias_projection_bias is False
        final=layer.attn.dist_mlp[2] if kind=='C1-0' else layer.attn.pair_projection
        assert final.bias is None and 'bias' not in dict(final.named_parameters())
    if kind!='C1-0':
        assert b.backbone.pair_encoder.project[2].bias is not None
        assert torch.equal(a.backbone.pair_encoder.project[2].bias,b.backbone.pair_encoder.project[2].bias)
    assert KEY not in a.config_dict()['backbone_config'] and b.config_dict()['backbone_config'][KEY] is False


def test_plain_C_forward_H0_and_parameter_objects_are_real(models):
    kind,a,b,_,_=models
    data=Data(x=torch.tensor([[5],[0],[7]]),pos=torch.tensor([[0.,0.,0.],[.5,0.,0.],[.25,.75,0.]]),
        batch=torch.zeros(3,dtype=torch.long))
    ids={n:id(p) for n,p in b.named_parameters()};rng=torch.get_rng_state().clone()
    result=b.encode_atoms(data)
    assert result.shape==(3,512) and result.dtype==torch.float32 and torch.isfinite(result).all()
    assert ids=={n:id(p) for n,p in b.named_parameters()} and torch.equal(rng,torch.get_rng_state())
    assert b.config_dict()['backbone_config'][KEY] is False


def test_C_state_roundtrip_and_default_old_state_format_are_locked(models):
    kind,a,b,_,_=models
    restored,_=seeded(configuration(kind,False))
    restored.load_state_dict(b.state_dict(),strict=True);state_equal(restored.state_dict(),b.state_dict())
    explicit,_=seeded(configuration(kind,True))
    explicit.load_state_dict(a.state_dict(),strict=True);state_equal(explicit.state_dict(),a.state_dict())
    if kind=='C1-0':
        with pytest.raises(RuntimeError):explicit.load_state_dict(b.state_dict(),strict=True)
    else:
        assert KEY not in a.backbone.get_extra_state() and b.backbone.get_extra_state()[KEY] is False
        with pytest.raises(ValueError):explicit.load_state_dict(b.state_dict(),strict=True)
    assert restored.config_dict()['backbone_config'][KEY] is False


def test_sealer_preserves_explicit_false_without_changing_old_registry_defaults(models):
    kind,a,b,_,_=models
    cfg=configuration(kind,False)
    sealed=source_s_architecture_configuration(cfg,ArchitectureOptions(distance_bias=kind))
    assert sealed['backbone'][KEY] is False
    assert cfg==configuration(kind,False)
    old=source_s_architecture_configuration(configuration(kind),ArchitectureOptions(distance_bias=kind))
    assert KEY not in old['backbone']


def test_unsupported_optimized_C_refuses_before_replacing_any_original_parameters(models):
    _,_,b,_,_=models;ids={n:id(p) for n,p in b.named_parameters()}
    with pytest.raises(ValueError,match='unsupported'):
        install_training_performance(b,PerformanceOptions())
    assert ids=={n:id(p) for n,p in b.named_parameters()}
    with pytest.raises(ValueError,match='unsupported'):build_performance_model(configuration(b.backbone.options.distance_bias if hasattr(b.backbone,'options') else 'C1-0',False))


@pytest.mark.parametrize('bad',(None,1,'false'))
def test_C_bias_flag_is_not_coerced(bad):
    cfg=configuration();cfg['backbone'][KEY]=bad;rng=torch.get_rng_state().clone()
    with pytest.raises(ValueError):build_architecture_model(cfg)
    assert torch.equal(rng,torch.get_rng_state())


def test_head_constant_softmax_equivalence_is_real_math_not_a_new_F32_gate():
    logits=torch.tensor([[[1.,-2.,.5],[.25,.75,-1.]]],dtype=torch.float64)
    common=torch.tensor([[[3.25],[-2.5]]],dtype=torch.float64)
    torch.testing.assert_close(logits.softmax(-1),(logits+common).softmax(-1),atol=3e-16,rtol=0)


def registry():
    return LabelRegistry((FieldSpec('g','P','synthetic','graph',pooling='sum'),
        FieldSpec('v','P','synthetic','graph',representation='vector')),
        'C_pooling_metadata_unit','1'*64)


def test_pooling_default_state_extra_and_RNG_are_original_compatible():
    torch.manual_seed(44);a=V3HeadBank(registry(),dim=4,hidden_dim=4);rng=torch.get_rng_state().clone()
    torch.manual_seed(44);b=V3HeadBank(registry(),dim=4,hidden_dim=4,pooling_overrides={})
    assert torch.equal(rng,torch.get_rng_state());state_equal(a.state_dict(),b.state_dict())
    assert a.get_extra_state()==dict(schema='model_v3_head_bank_v1',registry_sha256=registry().content_sha256,
        dim=4,hidden_dim=4,forms=dict(a.forms))
    b.load_state_dict(a.state_dict(),strict=True)


def test_explicit_pooling_uses_actual_mixer_without_registry_or_label_mutation():
    reg=registry();before=reg.content_sha256
    bank=V3HeadBank(reg,dim=4,hidden_dim=4,pooling_overrides={'g':'learned'})
    with torch.no_grad():
        head=bank.field_heads[bank.keys['g']];head.weight.zero_();head.weight[0,0]=1.;head.bias.zero_()
    h=torch.tensor([[2.,0.,0.,0.],[6.,0.,0.,0.],[1.,0.,0.,0.]])
    prediction=bank(h,torch.tensor([0,0,1]),torch.zeros((3,3)),enabled_groups=('P',),enabled_fields=('g',))['g']
    assert torch.equal(prediction,torch.tensor([[6.],[1.]]))
    prediction.sum().backward()
    assert torch.equal(bank.pooling_mixers[bank.keys['g']].logits.grad,torch.tensor([1.,-1.]))
    assert reg.content_sha256==before and reg.by_name()['g'].pooling=='sum'
    assert bank.get_extra_state()['pooling_overrides']=={'g':'learned'}
    same=V3HeadBank(reg,dim=4,hidden_dim=4,pooling_overrides={'g':'learned'})
    same.load_state_dict(bank.state_dict(),strict=True)
    with pytest.raises(ValueError):V3HeadBank(reg,dim=4,hidden_dim=4).load_state_dict(bank.state_dict(),strict=True)


@pytest.mark.parametrize('value',({'v':'learned'},{'unknown':'registry'},{'g':True},{'g':'mean'}))
def test_unknown_pooling_or_non_graph_scalar_field_is_rejected(value):
    with pytest.raises(ValueError):V3HeadBank(registry(),dim=4,hidden_dim=4,pooling_overrides=value)


def test_real_C_attention_rejects_nonF32_and_AMP_before_any_math(models):
    kind,_,b,_,_=models;attn=b.backbone.layers[0].attn
    x=torch.zeros((1,2,512));mask=torch.ones((1,2),dtype=torch.bool)
    if kind=='C1-0':
        def invoke(dtype):
            return attn(x.to(dtype),torch.zeros((1,2,3),dtype=dtype),mask)
    else:
        def invoke(dtype):
            return attn(x.to(dtype),torch.zeros((1,2,2,64),dtype=dtype),
                torch.zeros((1,2,2),dtype=dtype),mask)
    for dtype in (torch.float64,torch.bfloat16):
        with pytest.raises(ValueError,match='FP32'):invoke(dtype)
    with torch.autocast('cpu',dtype=torch.bfloat16):
        with pytest.raises(ValueError,match='AMP'):invoke(torch.float32)
