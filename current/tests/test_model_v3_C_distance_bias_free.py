"""C-only parameter removal: mathematical/common-state controls, no A gate or physics PASS."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path

import pytest
import torch
from torch import nn
from torch.nn import functional as F
from torch_geometric.data import Batch, Data

from phychem_mfm.model.attention import DenseGeoSelfAttention
from phychem_mfm.model.v3_architecture import (
    ArchitectureOptions, build_architecture_model, build_source_s_architecture_model,
    configuration_with_architecture, source_s_architecture_configuration)
from phychem_mfm.model.v3_distance_bias import (
    KEY, common_parameter_mapping, require_distance_bias_backbone,
    validate_distance_bias_projection_bias)
from phychem_mfm.model.v3_numeric_stability import (
    numeric_checkpoint_contract, load_numeric_bound_state_dict)
from phychem_mfm.phase1.v3_proxy_plan import Evidence, architecture_plan
from phychem_mfm.model.v3_performance import (
    PerformanceOptions, RuntimeDenseAttention, build_performance_model)


@pytest.fixture(autouse=True)
def strict_CPU():
    threads,precision = torch.get_num_threads(),torch.get_float32_matmul_precision()
    cudnn = torch.backends.cudnn.allow_tf32
    torch.set_num_threads(1);torch.set_float32_matmul_precision('highest')
    torch.backends.cudnn.allow_tf32 = False
    try: yield
    finally:
        torch.set_num_threads(threads)
        torch.set_float32_matmul_precision(precision)
        torch.backends.cudnn.allow_tf32 = cudnn


def config(distance='C1-0', *, bias=None, dim=512, layers=6, heads=8, cutoff=None):
    result={'architecture':{'preset':'shared_light'},
        'backbone':{'dim':dim,'layers':layers,'heads':heads,'ff_mult':2,'dropout':0.},
        'head':{'profile':'phase1','geometry_head':'equivariant_noise',
                'geometry_hidden_dim':16,'geometry_message_layers':0}}
    if bias is not None:result['backbone'][KEY]=bias
    if cutoff is not None:result['backbone'].update(use_radius_mask=True,radius=cutoff)
    if distance!='C1-0':
        result=configuration_with_architecture(result,ArchitectureOptions(distance_bias=distance,cutoff=cutoff))
    return result


def seeded(configuration, *, source_s=False):
    with torch.random.fork_rng(devices=[]):
        torch.random.default_generator.manual_seed(1742)
        builder=build_source_s_architecture_model if source_s else build_architecture_model
        model=builder(configuration)
        after=torch.get_rng_state().clone()
    return model,after


def graphs():
    return Batch.from_data_list([
        Data(x=torch.tensor([[5],[0],[7]]),pos=torch.tensor([[0.,0.,0.],[.5,0.,0.],[.25,.75,0.]])),
        Data(x=torch.tensor([[6],[5],[0],[7]]),
             pos=torch.tensor([[.25,0.,.5],[1.,.25,.5],[.25,1.,.25],[.5,.5,1.]]))])


@pytest.fixture(scope='module',params=['C1-0','C1-a','C1-b'])
def primary(request):
    source,source_rng=seeded(config(request.param))
    target,target_rng=seeded(config(request.param,bias=False))
    return request.param,source,target,source_rng,target_rng


def test_common_parameter_values_and_initialization_RNG_map_exactly(primary):
    distance,source,target,source_rng,target_rng=primary
    before=torch.get_rng_state().clone()
    mapping=common_parameter_mapping(source,target)
    original,current=dict(source.named_parameters()),dict(target.named_parameters())
    assert torch.equal(source_rng,target_rng)
    assert len(mapping['common'])==len(current)
    assert mapping['removed_scalar_count']==(48 if distance=='C1-0' else 0)
    assert len(mapping['removed'])==(6 if distance=='C1-0' else 0)
    assert mapping['common_raw_values_verified_by_this_mapping'] is False
    assert set(original)-set(current)==set(mapping['removed'])
    for old,new in mapping['common'].items():
        assert old==new and torch.equal(original[old],current[new])
    for layer in target.backbone.layers:
        assert layer.attn.distance_bias_projection_bias is False
        projection=layer.attn.dist_mlp[2] if distance=='C1-0' else layer.attn.pair_projection
        assert projection.bias is None and 'bias' not in dict(projection.named_parameters())
    if distance!='C1-0':
        assert target.backbone.pair_encoder.project[2].bias is not None
        assert 'backbone.pair_encoder.project.2.bias' in mapping['common']
    assert torch.equal(before,torch.get_rng_state())


def test_all_six_supported_C_layers_forward_and_common_gradient_headers(primary):
    _,source,target,_,_=primary
    target.train();target.zero_grad(set_to_none=True)
    inputs=graphs();inputs.pos.requires_grad_();before=torch.get_rng_state().clone()
    h0=target.encode_atoms(inputs)
    assert h0.shape==(7,512) and h0.dtype==torch.float32 and torch.isfinite(h0).all()
    cotangent=((torch.arange(h0.numel()).reshape_as(h0)%11)-5).float()/64
    (h0*cotangent).sum().backward()
    mapping=common_parameter_mapping(source,target)
    assert all(name not in dict(target.named_parameters()) for name in mapping['removed'])
    for index in range(6):
        layer=target.backbone.layers[index]
        projection=layer.attn.dist_mlp[2] if hasattr(layer.attn,'dist_mlp') else layer.attn.pair_projection
        for value in (layer.attn.qkv.weight,layer.attn.proj.weight,projection.weight):
            assert value.grad is not None and value.grad.dtype==value.dtype==torch.float32
            assert value.grad.shape==value.shape and torch.isfinite(value.grad).all()
        assert layer.attn.qkv.weight.grad.abs().sum()>0
    assert inputs.pos.grad is not None and torch.isfinite(inputs.pos.grad).all()
    assert torch.equal(before,torch.get_rng_state())


def test_state_keys_strict_restore_and_checkpoint_configuration_do_not_alias(primary):
    distance,source,target,_,_=primary
    before=torch.get_rng_state().clone()
    original,state=source.state_dict(),target.state_dict()
    mapping=common_parameter_mapping(source,target)
    assert set(original)-set(state)==set(mapping['removed'])
    contract=numeric_checkpoint_contract(target)
    assert contract['model_config']['backbone_config'][KEY] is False
    assert KEY not in numeric_checkpoint_contract(source)['model_config']['backbone_config']
    with pytest.raises(ValueError,match='numeric mode/model configuration'):
        load_numeric_bound_state_dict(target,original,numeric_checkpoint_contract(source))
    with pytest.raises((RuntimeError,ValueError)):
        target.load_state_dict(original,strict=True)
    if distance!='C1-0':
        assert target.backbone.get_extra_state()[KEY] is False
        assert KEY not in source.backbone.get_extra_state()
    saved=deepcopy(state);identities={name:id(value) for name,value in target.named_parameters()}
    with torch.no_grad():target.backbone.layers[0].attn.qkv.weight.add_(1.)
    load_numeric_bound_state_dict(target,saved,contract)
    assert identities=={name:id(value) for name,value in target.named_parameters()}
    for name,value in saved.items():
        other=target.state_dict()[name]
        assert torch.equal(value,other) if isinstance(value,torch.Tensor) else value==other
    assert torch.equal(before,torch.get_rng_state())


def test_common_parameter_mapping_preserves_full_model_encoder_prefix(primary):
    _,source,target,_,_=primary
    old,new=nn.Module(),nn.Module()
    old.add_module('encoder',source);new.add_module('encoder',target)
    old.register_parameter('same_readout',nn.Parameter(torch.tensor([.5,-.25])))
    new.register_parameter('same_readout',nn.Parameter(torch.tensor([.5,-.25])))
    mapping=common_parameter_mapping(old,new)
    assert mapping['common']['same_readout']=='same_readout'
    assert all(name.startswith('encoder.backbone.') for name in mapping['removed'])
    assert all(name.startswith('encoder.') or name=='same_readout' for name in mapping['common'])


def test_exact_analytic_common_logit_bias_derivative_is_null():
    # Softmax Jacobian at the exact dyadic population p=(1/4,1/2,1/4).
    # J*1=0 independently of either attention implementation or its summation error.
    p=torch.tensor([.25,.5,.25],dtype=torch.float64)
    jacobian=torch.diag(p)-p[:,None]*p[None,:]
    assert torch.equal(jacobian@torch.ones(3,dtype=torch.float64),torch.zeros(3,dtype=torch.float64))
    loss_direction=torch.tensor([2.,-1.,3.],dtype=torch.float64)
    assert float(torch.ones(3,dtype=torch.float64)@jacobian@loss_direction)==0.


def reference_attention(x,pos,parameters, *, bias):
    """Independent test-only real-formula reference, without model/helper construction."""
    qkv=F.linear(x,parameters['qkv.weight'],parameters['qkv.bias']).reshape(1,3,3,2,4)
    q,k,v=(value.transpose(1,2) for value in qkv.unbind(2))
    logits=(q@k.transpose(-2,-1))/2
    distances=(pos[:,:,None,:]-pos[:,None,:,:]).square().sum(-1)
    hidden=F.silu(F.linear(distances.unsqueeze(-1),parameters['dist_mlp.0.weight'],parameters['dist_mlp.0.bias']))
    head_bias=F.linear(hidden,parameters['dist_mlp.2.weight'],bias).permute(0,3,1,2)
    weights=torch.softmax(logits+head_bias,dim=-1)
    context=(weights@v).transpose(1,2).contiguous().reshape(1,3,8)
    return F.linear(context,parameters['proj.weight'],parameters['proj.bias'])


@pytest.mark.parametrize('constant',[(0.,0.),(.75,-.5)])
def test_actual_same_input_common_weights_gradients_against_independent_F64_reference(constant):
    # These small engineering tolerances are not the A gradient gate or C4 physics criterion.
    with torch.random.fork_rng(devices=[]):
        torch.random.default_generator.manual_seed(1742)
        source=DenseGeoSelfAttention(8,2)
        torch.random.default_generator.manual_seed(1742)
        target=DenseGeoSelfAttention(8,2,distance_bias_projection_bias=False)
    with torch.no_grad():
        for index,(name,parameter) in enumerate(source.named_parameters()):
            if name=='dist_mlp.2.bias':parameter.copy_(torch.tensor(constant))
            else:parameter.copy_(((torch.arange(parameter.numel()).reshape_as(parameter)%7)-3).float()/16)
        for name,parameter in target.named_parameters():parameter.copy_(dict(source.named_parameters())[name])
    shared_names=tuple(dict(target.named_parameters()))
    x=((torch.arange(24).reshape(1,3,8)%7)-3).float()/8
    pos=torch.tensor([[[0.,0.,0.],[.5,0.,0.],[.25,.75,0.]]])
    mask=torch.ones(1,3,dtype=torch.bool)
    tangent=((torch.arange(24).reshape(1,3,8)%5)-2).float()/8
    parameters={name:value.detach().double().requires_grad_() for name,value in source.named_parameters()}
    x64=x.double().requires_grad_();p64=pos.double().requires_grad_()
    with_bias=reference_attention(x64,p64,parameters,bias=parameters['dist_mlp.2.bias'])
    without_bias=reference_attention(x64,p64,parameters,bias=None)
    assert torch.allclose(with_bias,without_bias,atol=2e-14,rtol=0)
    reference_inputs=(x64,p64)+tuple(parameters[name] for name in shared_names)
    expected=torch.autograd.grad((without_bias*tangent.double()).sum(),reference_inputs,retain_graph=True)
    null_gradient,=torch.autograd.grad((with_bias*tangent.double()).sum(),(parameters['dist_mlp.2.bias'],))
    assert null_gradient.abs().max()<=2e-14
    for module in (source,target):
        values=x.clone().requires_grad_();positions=pos.clone().requires_grad_()
        actual,_=module(values,positions,mask)
        gradients=torch.autograd.grad((actual*tangent).sum(),
            (values,positions)+tuple(dict(module.named_parameters())[name] for name in shared_names))
        assert torch.allclose(actual.double(),without_bias.detach(),atol=2e-6,rtol=2e-5)
        assert all(torch.allclose(g.double(),e,atol=2e-6,rtol=2e-5) for g,e in zip(gradients,expected))
        assert actual.abs().sum()>0 and sum(g.abs().sum() for g in gradients)>0
        assert all(g.dtype==torch.float32 for g in gradients)
    assert target.dist_mlp[2].bias is None


@pytest.mark.parametrize('distance',['C1-0','C1-a','C1-b'])
def test_default_and_explicit_true_keep_legacy_parameters_RNG_and_bitwise_path(distance):
    source,rng_source=seeded(config(distance,dim=32,layers=1,heads=4))
    target,rng_target=seeded(config(distance,bias=True,dim=32,layers=1,heads=4))
    assert torch.equal(rng_source,rng_target)
    assert KEY not in source.config_dict()['backbone_config']
    assert target.config_dict()['backbone_config'][KEY] is True
    for name,value in source.state_dict().items():
        other=target.state_dict()[name]
        assert torch.equal(value,other) if isinstance(value,torch.Tensor) else value==other
    source.eval();target.eval();rng=torch.get_rng_state().clone()
    with torch.no_grad():assert torch.equal(source.encode_atoms(graphs()),target.encode_atoms(graphs()))
    if distance=='C1-0':assert source.backbone.layers[0].attn.dist_mlp[2].bias is not None
    assert torch.equal(rng,torch.get_rng_state())


@pytest.mark.parametrize('distance',['C1-0','C1-a','C1-b'])
def test_original_source_S_tiled_builder_keeps_supported_distance_callers(distance):
    source,source_rng=seeded(config(distance),source_s=True)
    target,target_rng=seeded(config(distance,bias=False),source_s=True)
    mapping=common_parameter_mapping(source,target)
    assert mapping['removed_scalar_count']==(48 if distance=='C1-0' else 0)
    assert torch.equal(source_rng,target_rng)
    for name in mapping['common']:assert torch.equal(dict(source.named_parameters())[name],dict(target.named_parameters())[name])
    target.eval()
    with torch.no_grad():assert target.encode_atoms(graphs()).shape==(7,512)


@pytest.mark.parametrize('distance',['C1-a','C1-b'])
def test_cutoff_feature_MLP_bias_is_retained_and_never_misidentified_as_head_constant(distance):
    source,_=seeded(config(distance,cutoff=8.))
    target,_=seeded(config(distance,bias=False,cutoff=8.))
    mapping=common_parameter_mapping(source,target)
    assert mapping['removed']==[]
    for name in ('backbone.pair_encoder.project.0.bias','backbone.pair_encoder.project.2.bias'):
        assert name in mapping['common'] and torch.equal(dict(source.named_parameters())[name],dict(target.named_parameters())[name])


@pytest.mark.parametrize('bad',[None,0,1,'false'])
def test_flag_type_is_not_coerced(bad):
    rng=torch.get_rng_state().clone()
    with pytest.raises(ValueError):validate_distance_bias_projection_bias(bad)
    assert torch.equal(rng,torch.get_rng_state())


@pytest.mark.parametrize('bad',['layers','dim','heads','disabled'])
def test_opt_in_model_scope_rejects_before_parameter_RNG(bad):
    value=config(bias=False)
    if bad=='disabled':value['backbone']['use_dist_bias']=False
    else:value['backbone'][bad]={'layers':1,'dim':256,'heads':4}[bad]
    rng=torch.get_rng_state().clone()
    with pytest.raises(ValueError):build_architecture_model(value)
    assert torch.equal(rng,torch.get_rng_state())


@pytest.mark.parametrize('kind',['fp32','bf16','compiled'])
def test_A_performance_builder_explicitly_rejects_new_C_flag_before_RNG(kind):
    rng=torch.get_rng_state().clone()
    options=PerformanceOptions(precision='bf16' if kind=='bf16' else 'fp32',compile_backbone=kind=='compiled')
    with pytest.raises(ValueError,match='Bias-free C.*unsupported'):
        build_performance_model(config(bias=False),options)
    assert torch.equal(rng,torch.get_rng_state())


def test_direct_Native_runtime_replacement_is_not_a_silent_fallback(primary):
    _,_,target,_,_=primary
    with pytest.raises(ValueError,match='Bias-free C.*unsupported'):
        RuntimeDenseAttention(target.backbone.layers[0].attn)


@pytest.mark.parametrize('bad',['config','backbone','layer','reintroduced_bias','unknown_attention'])
def test_partial_flags_or_reintroduced_redundant_parameter_reject(primary,monkeypatch,bad):
    distance,_,target,_,_=primary
    if bad=='config':monkeypatch.setitem(target.backbone_config,KEY,True)
    elif bad=='backbone':monkeypatch.setattr(target.backbone,KEY,True)
    elif bad=='layer':monkeypatch.setattr(target.backbone.layers[1].attn,KEY,True)
    elif bad=='unknown_attention':monkeypatch.setattr(target.backbone.layers[1],'attn',nn.Identity())
    else:
        projection=target.backbone.layers[1].attn.dist_mlp[2] if distance=='C1-0' else target.backbone.layers[1].attn.pair_projection
        monkeypatch.setattr(projection,'bias',nn.Parameter(torch.zeros(8)))
    rng=torch.get_rng_state().clone()
    with pytest.raises(ValueError):target.encode_atoms(graphs())
    assert torch.equal(rng,torch.get_rng_state())


@pytest.mark.parametrize('bad',['autocast','float64','compiled'])
def test_unsupported_direct_precision_or_compile_state_is_explicit(monkeypatch,bad):
    module=DenseGeoSelfAttention(8,2,distance_bias_projection_bias=False)
    x=torch.ones(1,2,8);pos=torch.zeros(1,2,3);mask=torch.ones(1,2,dtype=torch.bool)
    if bad=='compiled':monkeypatch.setattr(torch.compiler,'is_compiling',lambda:True)
    if bad=='float64':x=x.double()
    with torch.autocast('cpu',dtype=torch.bfloat16,enabled=bad=='autocast'):
        with pytest.raises(ValueError):module(x,pos,mask)
@pytest.mark.parametrize('bad',['unlisted_bias','shape','other_configuration'])
def test_common_map_rejects_any_additional_parameter_or_configuration_difference(primary,monkeypatch,bad):
    _,source,target,_,_=primary
    if bad=='unlisted_bias':monkeypatch.setattr(target.backbone.layers[0].ffn.net[0],'bias',None)
    elif bad=='shape':
        projection=target.backbone.layers[0].attn.proj
        monkeypatch.setattr(projection,'weight',nn.Parameter(projection.weight[:,:-1].detach().clone()))
    else:monkeypatch.setitem(target.backbone_config,'radius',9.)
    with pytest.raises(ValueError):common_parameter_mapping(source,target)

def test_new_registry_and_all20_architecture_trials_explicitly_bind_bias_free_identity():
    root=Path(__file__).absolute().parents[2]
    historical=json.loads((root/'configs/model_v3/architecture_candidates_v1.json').read_bytes())
    candidate=json.loads((root/'configs/model_v3/architecture_candidates_bias_free_v1.json').read_bytes())
    assert candidate['schema']=='model_v3_architecture_bias_free_implementation_candidates_v1'
    assert candidate['status']=='SOURCE_ONLY_NEW_C_BIAS_FREE_NOT_SCIENTIFIC_SELECTION'
    assert candidate['backbone']=={**historical['backbone'],KEY:False}
    assert KEY not in historical['backbone']
    assert set(candidate)==set(historical)|{'historical_registry'}
    for name in set(historical)-{'schema','status','backbone'}:
        assert candidate[name]==historical[name]
    assert candidate['historical_registry']=={
        'path':'configs/model_v3/architecture_candidates_v1.json','unchanged':True,
        'scope':'HISTORICAL_LEGACY_BIAS_POLICY_NOT_THIS_NEW_C_CANDIDATE'}
    trials=architecture_plan(sample_budget=4096,batch_base_samples=2,
        budget_evidence=Evidence('/metadata/budget.json','1'*64),
        rules_evidence=Evidence('/metadata/rules.json','2'*64))
    assert len(trials)==20 and len({trial.name for trial in trials})==20
    for trial in trials:
        assert dict(trial.parameters)[KEY] is False
        old_policy=replace(trial,parameters=tuple((name,value) for name,value in trial.parameters if name!=KEY))
        assert old_policy.scientific_identity!=trial.scientific_identity


def test_new_C_plan_parameter_maps_to_backbone_and_source_seal_keeps_false(primary):
    distance,_,target,_,_=primary
    trials=architecture_plan(sample_budget=4096,batch_base_samples=2,
        budget_evidence=Evidence('/metadata/budget.json','1'*64),
        rules_evidence=Evidence('/metadata/rules.json','2'*64))
    # The plan parameter maps to backbone, not to ArchitectureOptions fields.
    requested=config(distance,bias=dict(trials[0].parameters)[KEY])
    before=deepcopy(requested)
    sealed=source_s_architecture_configuration(requested)
    assert requested==before and sealed['backbone'][KEY] is False
    assert target.config_dict()['backbone_config'][KEY] is False
    assert KEY not in sealed['backbone'].get('v3_architecture',{})
