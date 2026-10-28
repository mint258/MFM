"""One fixed residual finalizer: CPU engineering controls, not C4 acceptance."""
from copy import deepcopy

import pytest
import torch
from torch_geometric.data import Batch, Data

from phychem_mfm.model import attention as attention_module
from phychem_mfm.model import v3_architecture as architecture_module
from phychem_mfm.model.v3_architecture import (
    ArchitectureOptions, build_architecture_model, configuration_with_architecture)
from phychem_mfm.model.v3_numeric_stability import (
    COMPENSATED, numeric_checkpoint_contract, load_numeric_bound_state_dict)
from phychem_mfm.model.v3_residual_accumulation import (
    LEGACY_RESIDUAL, TWO_SUM_RESIDUAL, two_sum_three_term_fp32,
    require_residual_backbone, validate_residual_accumulation_mode)
from phychem_mfm.model.v3_performance import PerformanceOptions, build_performance_model


@pytest.fixture(autouse=True)
def strict_CPU():
    threads, precision = torch.get_num_threads(), torch.get_float32_matmul_precision()
    cudnn = torch.backends.cudnn.allow_tf32
    torch.set_num_threads(1)
    torch.set_float32_matmul_precision("highest")
    torch.backends.cudnn.allow_tf32 = False
    try:
        yield
    finally:
        torch.set_num_threads(threads)
        torch.set_float32_matmul_precision(precision)
        torch.backends.cudnn.allow_tf32 = cudnn


def configuration(distance="C1-0", *, candidate=True):
    result = {"architecture": {"preset": "shared_light"},
        "backbone": {"dim": 512, "layers": 6, "heads": 8, "ff_mult": 2,
            "n_atom_types": 119, "dropout": 0., "numeric_mode": COMPENSATED,
            "attention_aggregation_mode": "centered_fp32_v1",
            "attention_projection_mode": "blocked_k64_compensated_fp32_v1",
            "ffn_projection_mode": "blocked_k64_compensated_fp32_v1",
            "geometry_mode": "residual_expansion_fp32_v1"},
        "head": {"profile": "phase1", "geometry_head": "equivariant_noise",
            "geometry_hidden_dim": 32, "geometry_message_layers": 0,
            "geometry_pair_chunk_size": 8192, "numeric_mode": COMPENSATED}}
    if candidate:
        result["backbone"]["residual_accumulation_mode"] = TWO_SUM_RESIDUAL
    if distance != "C1-0":
        result = configuration_with_architecture(result, ArchitectureOptions(distance_bias=distance))
    return result


def seeded_model(config):
    with torch.random.fork_rng(devices=[]):
        torch.random.default_generator.manual_seed(1742)
        return build_architecture_model(config)


def graphs():
    return Batch.from_data_list([
        Data(x=torch.tensor([[5], [0], [7]]),
            pos=torch.tensor([[0., 0., 0.], [.7, .1, 0.], [.1, .8, .2]])),
        Data(x=torch.tensor([[6], [5], [0], [7]]),
            pos=torch.tensor([[.2, .1, .3], [1., .2, .4], [.3, 1.1, .1], [.5, .4, 1.]]))])


@pytest.mark.parametrize("values,answer", [((2.**24, 1., -(2.**24)), 1.),
    ((-(2.**24), -1., 2.**24), -1.), ((2.**24, -(2.**24), 1.), 1.),
    ((1., 2., 3.), 6.)])
def test_cancellation_has_independent_real_sum_oracle(values, answer):
    actual = two_sum_three_term_fp32(*(torch.tensor([v]) for v in values))
    assert torch.equal(actual, torch.tensor([answer]))


def test_noncontiguous_terms_keep_shape_source_order_and_dyadic_oracle():
    storage = (torch.arange(257 * 14).reshape(257, 14) % 9 - 4).float() / 8
    x, a, b = storage[:, ::2], storage.flip(0)[:, ::2], (-storage)[:, ::2]
    assert not x.is_contiguous() and not a.is_contiguous() and not b.is_contiguous()
    expected = (x.double() + a.double() + b.double()).float()
    actual = two_sum_three_term_fp32(x, a, b)
    assert actual.shape == x.shape and torch.equal(actual, expected)
    permutation = torch.arange(256, -1, -1)
    assert torch.equal(two_sum_three_term_fp32(x[permutation], a[permutation], b[permutation]),
                       actual[permutation])


def test_three_input_VJP_and_complete_cross_Hessian_are_real_linear_sum_derivatives():
    x, a, b = [torch.tensor([[v, -v]], requires_grad=True) for v in (1., 2., 3.)]
    y = two_sum_three_term_fp32(x, a, b)
    first = torch.autograd.grad(.5 * y.square().sum(), (x, a, b), create_graph=True)
    assert all(torch.equal(g, torch.tensor([[6., -6.]])) for g in first)
    directions = [torch.tensor([[v, -v]]) for v in (.25, -.5, 1.)]
    directional = sum((g*d).sum() for g,d in zip(first,directions))
    second = torch.autograd.grad(directional, (x, a, b))
    # Hessian of .5||x+a+b||²: every block is I, so H*d=sum of the three directions.
    assert all(torch.equal(g, torch.tensor([[.75, -.75]])) for g in second)
    assert float(sum((g*d).sum() for g,d in zip(second,directions))) == 1.125


def test_nonlinear_branch_first_and_second_oracles_include_the_original_u_graph():
    x = torch.tensor([2.], requires_grad=True)
    c = torch.tensor([.5], requires_grad=True)
    attention = c*x
    u = x+attention
    feedforward = u.square()
    result = two_sum_three_term_fp32(x, attention, feedforward)
    # f=(1+c)x+((1+c)x)^2. At x=2,c=.5: f=12; Hessian=[[4.5,13],[13,8]].
    assert float(result) == 12.
    first = torch.autograd.grad(result.sum(), (x,c), create_graph=True)
    assert tuple(float(v) for v in first) == (10.5,14.)
    directional = first[0]*.25-first[1]*.5
    second = torch.autograd.grad(directional.sum(), (x,c))
    assert tuple(float(v) for v in second) == (-5.375,-.75)
    assert float(second[0]*.25-second[1]*.5) == -.96875


def test_first_rounded_u_is_not_replaced_by_an_injected_tail():
    x, attention = torch.tensor([2.**24]), torch.tensor([1.])
    u = x+attention
    assert torch.equal(u,x)  # The original FP32 branch input really lost the small term.
    feedforward = -u
    result = two_sum_three_term_fp32(x,attention,feedforward)
    assert float(result) == 1. and float(u+feedforward) == 0.
    # This is fixed-operand addition, not a theorem that nonlinear full-model error decreases.


def test_empty_rows_and_alias_inputs_have_correct_real_gradients_without_RNG():
    before = torch.get_rng_state().clone()
    terms = [torch.empty(0,512,requires_grad=True) for _ in range(3)]
    output = two_sum_three_term_fp32(*terms)
    output.sum().backward()
    assert output.shape == (0,512) and all(v.grad.shape == v.shape for v in terms)
    shared = torch.tensor([2.],requires_grad=True)
    two_sum_three_term_fp32(shared,shared,shared).sum().backward()
    assert float(shared.grad) == 3.
    assert torch.equal(before,torch.get_rng_state())


@pytest.mark.parametrize("dtype", [torch.float64,torch.bfloat16,torch.float16,torch.int64])
def test_non_FP32_terms_are_rejected_without_conversion_or_RNG(dtype):
    before = torch.get_rng_state().clone()
    with pytest.raises(ValueError,match="FP32"):
        two_sum_three_term_fp32(torch.ones(2,dtype=dtype),torch.ones(2),torch.ones(2))
    assert torch.equal(before,torch.get_rng_state())


@pytest.mark.parametrize("bad", ["shape","none","broadcast"])
def test_missing_broadcast_or_shape_mismatched_operands_are_typed_rejection(bad):
    x,a,b = torch.ones(2),torch.ones(2),torch.ones(2)
    if bad == "shape": a=torch.ones(3)
    elif bad == "none": b=None
    else: a=torch.tensor(1.)
    with pytest.raises(ValueError): two_sum_three_term_fp32(x,a,b)


def test_active_CPU_autocast_rejects_even_with_actual_FP32_operands():
    with torch.autocast("cpu",dtype=torch.bfloat16):
        with pytest.raises(ValueError,match="autocast"):
            two_sum_three_term_fp32(*(torch.ones(2) for _ in range(3)))


@pytest.mark.parametrize("bad", ["precision","TF32","unreadable"])
def test_precision_controls_reject_without_setting_globals(monkeypatch,bad):
    if bad == "precision": monkeypatch.setattr(torch,"get_float32_matmul_precision",lambda:"high")
    elif bad == "TF32": monkeypatch.setattr(torch.backends.cudnn,"allow_tf32",True)
    else:
        def invalid(): raise RuntimeError("unit mixed control state")
        monkeypatch.setattr(torch,"get_float32_matmul_precision",invalid)
    with pytest.raises(ValueError): two_sum_three_term_fp32(*(torch.ones(2) for _ in range(3)))


@pytest.mark.parametrize("value", [None,True,1,"unknown"])
def test_mode_enum_is_exact(value):
    with pytest.raises(ValueError): validate_residual_accumulation_mode(value)


def test_both_nonlinear_branches_have_independent_dyadic_first_and_second_derivatives():
    x=torch.tensor([.5],requires_grad=True)
    attention=x.square()
    u=x+attention
    feedforward=u.square()
    result=two_sum_three_term_fp32(x,attention,feedforward)
    first,=torch.autograd.grad(result.sum(),(x,),create_graph=True)
    second,=torch.autograd.grad(first.sum(),(x,))
    assert float(result)==21/16 and float(first)==5. and float(second)==13.


@pytest.mark.parametrize("kind", ["input_nonfinite","first_overflow","second_overflow"])
def test_finite_operand_and_every_TwoSum_intermediate_domain_is_explicit(kind):
    maximum=torch.finfo(torch.float32).max
    if kind=="input_nonfinite": values=(float('nan'),0.,0.)
    elif kind=="first_overflow": values=(maximum,maximum,-maximum)
    else: values=(maximum,0.,maximum)
    before=torch.get_rng_state().clone()
    with pytest.raises(ValueError,match="finite|overflow"):
        two_sum_three_term_fp32(*(torch.tensor([v]) for v in values))
    assert torch.equal(before,torch.get_rng_state())


def test_zero_and_smallest_normal_operands_are_not_repaired_or_rescaled():
    zeros=[torch.zeros(2) for _ in range(3)]
    assert torch.equal(two_sum_three_term_fp32(*zeros),torch.zeros(2))
    small=torch.tensor([torch.finfo(torch.float32).tiny])
    assert torch.equal(two_sum_three_term_fp32(small,small,-small),small)


@pytest.fixture(scope="module",params=["C1-0","C1-a","C1-b"])
def primary(request):
    config=configuration(request.param)
    model=seeded_model(config)
    yield config,model
    del model


def test_all_six_real_layers_keep_original_u_once_and_train_all_connected_branches(primary,monkeypatch):
    _,model=primary
    model.train();model.zero_grad(set_to_none=True)
    reference={index:{} for index in range(6)};handles=[];calls=[]
    original=attention_module.residual_accumulation
    assert architecture_module.residual_accumulation is original
    mapping={id(layer):index for index,layer in enumerate(model.backbone.layers)}
    def observe(layer,x,a,b):
        index=mapping[id(layer)];row=reference[index]
        assert x is row['x'] and a is row['a'] and b is row['b']
        calls.append(index)
        return original(layer,x,a,b)
    monkeypatch.setattr(attention_module,'residual_accumulation',observe)
    monkeypatch.setattr(architecture_module,'residual_accumulation',observe)
    for index,layer in enumerate(model.backbone.layers):
        def layer_input(owner,args,index=index): reference[index]['x']=args[0]
        def attention_output(owner,args,output,index=index):
            reference[index]['a']=output[0] if isinstance(output,tuple) else output
        def norm_input(owner,args,index=index): reference[index]['u']=args[0]
        def ffn_output(owner,args,output,index=index): reference[index]['b']=output
        handles.extend((layer.register_forward_pre_hook(layer_input),
            layer.attn.register_forward_hook(attention_output),
            layer.norm2.register_forward_pre_hook(norm_input),layer.ffn.register_forward_hook(ffn_output)))
    batch=graphs();batch.pos.requires_grad_();rng=torch.get_rng_state().clone()
    try: h0=model.encode_atoms(batch)
    finally:
        for handle in handles:handle.remove()
    assert calls==list(range(6)) and h0.shape==(7,512) and h0.dtype==torch.float32
    for row in reference.values():
        assert torch.equal(row['u'],row['x']+row['a'])
        assert all(value.dtype==torch.float32 for value in row.values())
    cotangent=((torch.arange(h0.numel()).reshape_as(h0)%13)-6).float()/128
    (h0*cotangent).sum().backward()
    for layer in model.backbone.layers:
        for linear in (layer.attn.qkv,layer.attn.proj,layer.ffn.net[0],layer.ffn.net[3]):
            assert linear.weight.grad is not None and torch.isfinite(linear.weight.grad).all()
            assert linear.weight.grad.abs().sum()>0
    assert batch.pos.grad is not None and torch.isfinite(batch.pos.grad).all()
    require_residual_backbone(model.backbone,expected_mode=TWO_SUM_RESIDUAL)
    assert torch.equal(rng,torch.get_rng_state())


def test_original_parameter_state_keys_RNG_and_bound_checkpoint_restore(primary):
    config,model=primary
    distance=config['backbone'].get('v3_architecture',{}).get('distance_bias','C1-0')
    before=torch.get_rng_state().clone();control=seeded_model(configuration(distance,candidate=False))
    current,old=model.state_dict(),control.state_dict()
    assert set(current)==set(old)
    for key,value in current.items():
        if isinstance(value,torch.Tensor):assert torch.equal(value,old[key])
    contract=numeric_checkpoint_contract(model)
    assert contract['model_config']['backbone_config']['residual_accumulation_mode']==TWO_SUM_RESIDUAL
    assert 'residual_accumulation_mode' not in control.config_dict()['backbone_config']
    with pytest.raises(ValueError,match='numeric mode/model configuration'):
        load_numeric_bound_state_dict(model,old,numeric_checkpoint_contract(control))
    if hasattr(model.backbone,'pair_encoder'):
        assert model.backbone.get_extra_state()['residual_accumulation_mode']==TWO_SUM_RESIDUAL
        assert 'residual_accumulation_mode' not in control.backbone.get_extra_state()
        with pytest.raises(ValueError,match='checkpoint/options'):
            model.backbone.set_extra_state(control.backbone.get_extra_state())
    saved=deepcopy(current);identities={name:id(value) for name,value in model.named_parameters()}
    with torch.no_grad():model.backbone.layers[0].attn.qkv.weight.add_(1.)
    load_numeric_bound_state_dict(model,saved,contract)
    assert identities=={name:id(value) for name,value in model.named_parameters()}
    for key,value in saved.items():
        if isinstance(value,torch.Tensor):assert torch.equal(value,model.state_dict()[key])
    assert torch.equal(before,torch.get_rng_state())


@pytest.mark.parametrize('bad',['layer_mode','backbone_mode','config_mode','foreign_layer','forward','norm','attention'])
def test_partial_mode_or_unsupported_runtime_rejects_before_RNG(primary,monkeypatch,bad):
    _,model=primary
    if bad=='layer_mode':monkeypatch.setattr(model.backbone.layers[1],'residual_accumulation_mode',LEGACY_RESIDUAL)
    elif bad=='backbone_mode':monkeypatch.setattr(model.backbone,'residual_accumulation_mode',LEGACY_RESIDUAL)
    elif bad=='config_mode':monkeypatch.setitem(model.backbone_config,'residual_accumulation_mode',LEGACY_RESIDUAL)
    elif bad=='foreign_layer':monkeypatch.setitem(model.backbone.layers._modules,'1',torch.nn.Identity())
    elif bad=='forward':monkeypatch.setitem(model.backbone.layers[1].__dict__,'forward',lambda *args:args[0])
    elif bad=='norm':monkeypatch.setattr(model.backbone.layers[1],'norm2',torch.nn.Identity())
    else:monkeypatch.setattr(model.backbone.layers[1],'attn',torch.nn.Identity())
    rng=torch.get_rng_state().clone()
    with pytest.raises(ValueError):model.encode_atoms(graphs())
    assert torch.equal(rng,torch.get_rng_state())


@pytest.mark.parametrize('bad',['layers','dim','heads','ff_mult','dropout','numeric','aggregation','projection','geometry','ffn','mode'])
def test_constructor_scope_rejects_before_parameter_RNG(bad):
    config=configuration();backbone=config['backbone']
    if bad in {'layers','dim','heads','ff_mult'}:
        backbone[bad]={'layers':1,'dim':256,'heads':4,'ff_mult':4}[bad]
    elif bad=='dropout':backbone['dropout']=.2
    elif bad=='numeric':backbone['numeric_mode']=config['head']['numeric_mode']='legacy'
    else:
        key={'aggregation':'attention_aggregation_mode','projection':'attention_projection_mode',
             'geometry':'geometry_mode','ffn':'ffn_projection_mode','mode':'residual_accumulation_mode'}[bad]
        backbone[key]='unknown' if bad=='mode' else 'legacy'
    rng=torch.get_rng_state().clone()
    with pytest.raises(ValueError):build_architecture_model(config)
    assert torch.equal(rng,torch.get_rng_state())


@pytest.mark.parametrize('kind',['fp32','bf16','compiled'])
def test_performance_Native_and_compile_builder_are_explicitly_unsupported(kind):
    options=PerformanceOptions(precision='bf16' if kind=='bf16' else 'fp32',compile_backbone=kind=='compiled')
    rng=torch.get_rng_state().clone()
    with pytest.raises(ValueError,match='Residual.*unsupported'):
        build_performance_model(configuration(),options)
    assert torch.equal(rng,torch.get_rng_state())


@pytest.mark.parametrize('distance',['C1-0','C1-a'])
def test_absent_and_explicit_legacy_are_original_bitwise_paths_without_new_default_key(distance,monkeypatch):
    config={'architecture':{'preset':'shared_light'},
        'backbone':{'dim':32,'layers':1,'heads':4,'ff_mult':1,'dropout':0.},
        'head':{'profile':'phase1','geometry_head':'equivariant_noise','geometry_hidden_dim':16,'geometry_message_layers':0}}
    if distance!='C1-0':config=configuration_with_architecture(config,ArchitectureOptions(distance_bias=distance))
    explicit=deepcopy(config);explicit['backbone']['residual_accumulation_mode']=LEGACY_RESIDUAL
    before=torch.get_rng_state().clone();default,legacy=seeded_model(config),seeded_model(explicit)
    for key,value in default.state_dict().items():
        other=legacy.state_dict()[key]
        assert torch.equal(value,other) if isinstance(value,torch.Tensor) else value==other
    assert 'residual_accumulation_mode' not in default.config_dict()['backbone_config']
    def forbidden(*args,**kwargs):raise AssertionError('Legacy must retain original two additions')
    monkeypatch.setattr(attention_module,'residual_accumulation',forbidden)
    monkeypatch.setattr(architecture_module,'residual_accumulation',forbidden)
    default.eval();legacy.eval()
    with torch.no_grad():assert torch.equal(default.encode_atoms(graphs()),legacy.encode_atoms(graphs()))
    assert torch.equal(before,torch.get_rng_state())


def test_compilation_state_is_rejected_without_running_a_compiler(monkeypatch):
    monkeypatch.setattr(torch.compiler,'is_compiling',lambda:True)
    with pytest.raises(ValueError,match='compiled'):
        two_sum_three_term_fp32(*(torch.ones(2) for _ in range(3)))
