"""Independent geometry/derivative oracles; source-only until Root executes."""
from copy import deepcopy

import pytest
import torch
from torch_geometric.data import Batch, Data

from phychem_mfm.model import attention as attention_module
from phychem_mfm.model import v3_architecture as architecture_module
from phychem_mfm.model.v3_architecture import (
    ArchitectureOptions, configuration_with_architecture, build_architecture_model,
    build_source_s_architecture_model, SharedGaussianPairEncoder)
from phychem_mfm.model.v3_geometry_fp32 import (
    LEGACY_GEOMETRY, RESIDUAL_GEOMETRY, GEOMETRY_TILE_ROWS,
    residual_distance_fp32, residual_pairwise_distance_fp32, require_geometry_backbone)
from phychem_mfm.model.v3_numeric_stability import (
    COMPENSATED, numeric_checkpoint_contract, load_numeric_bound_state_dict)


@pytest.fixture(autouse=True)
def strict_cpu_fp32():
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
    value = {"architecture":{"preset":"shared_light"},
        "backbone":{"dim":512,"layers":6,"heads":8,"ff_mult":2,"dropout":0.,
                    "n_atom_types":119,"numeric_mode":COMPENSATED,
                    "attention_aggregation_mode":"centered_fp32_v1",
                    "attention_projection_mode":"blocked_k64_compensated_fp32_v1"},
        "head":{"profile":"phase1","geometry_head":"equivariant_noise","geometry_hidden_dim":32,
                "geometry_message_layers":0,"numeric_mode":COMPENSATED}}
    if candidate:
        value["backbone"]["geometry_mode"] = RESIDUAL_GEOMETRY
    if distance != "C1-0":
        value = configuration_with_architecture(value,ArchitectureOptions(distance_bias=distance))
    return value


def seeded(config, *, source=True, seed=1742):
    with torch.random.fork_rng(devices=[]):
        torch.random.default_generator.manual_seed(seed)
        return (build_source_s_architecture_model if source else build_architecture_model)(config)


def graphs():
    return Batch.from_data_list([
        Data(x=torch.tensor([[5],[0],[7]]),
             pos=torch.tensor([[0.,0.,0.],[.75,.125,0.],[.125,.875,.25]])),
        Data(x=torch.tensor([[6],[5],[0],[7]]),
             pos=torch.tensor([[.25,.125,.375],[1.,.25,.5],[.375,1.125,.125],[.5,.375,1.]]))])


def test_raw_difference_tail_and_product_have_independent_exact_squared_oracle():
    left = torch.tensor([[2.**24,1.,0.]])
    right = torch.tensor([[-1.,0.,0.]])
    # Exact real square is 2^48 + 2^25 + 2. Nearest F32 is 2^48 + 2^25.
    expected = torch.tensor([2.**48 + 2.**25],dtype=torch.float32)
    actual = residual_distance_fp32(left,right,squared=True)
    naive = ((left-right).square()).sum(-1)
    assert torch.equal(actual,expected)
    assert float(actual) > float(naive)
    reference = ((left.double()-right.double()).square().sum(-1))
    assert abs(float(actual)-float(reference)) == 2.
    assert abs(float(naive)-float(reference)) == 2.**25+2


@pytest.mark.parametrize("squared",[False,True])
@pytest.mark.parametrize("power",[-60,0,60])
def test_fixed_norm_formula_and_exact_power_two_scaling_against_real_reference(squared,power):
    left = torch.tensor([[3.,4.,0.],[-.5,.25,1.]],dtype=torch.float32)*(2.**power)
    right = torch.zeros_like(left)
    delta = left.double()-right.double()
    expected = delta.square().sum(-1)
    if not squared:
        expected = expected.sqrt()
    actual = residual_distance_fp32(left,right,squared=squared)
    assert actual.dtype == torch.float32 and torch.isfinite(actual).all()
    torch.testing.assert_close(actual.double(),expected,rtol=1.3e-7,atol=0.)


@pytest.mark.parametrize("squared",[False,True])
def test_independent_first_and_complete_second_cross_derivatives(squared):
    left = torch.tensor([[1.,2.,3.],[-.5,.75,1.25]],requires_grad=True)
    right = torch.tensor([[.5,-.25,.125],[.25,-.5,.375]],requires_grad=True)
    coefficient = torch.tensor([.5,-1.25],requires_grad=True)
    u = torch.tensor([[.25,-.5,.125],[-.25,.125,.5]])
    v = torch.tensor([[-.125,.25,.5],[.125,-.25,.125]])
    uc = torch.tensor([.25,.125])
    actual = residual_distance_fp32(left,right,squared=squared)
    gradient = torch.autograd.grad((coefficient*actual).sum(),(left,right,coefficient),create_graph=True)
    hessian = torch.autograd.grad((gradient[0]*u).sum()+(gradient[1]*v).sum()+(gradient[2]*uc).sum(),
                                  (left,right,coefficient))
    delta, direction = left.detach().double()-right.detach().double(),(u-v).double()
    c,dc = coefficient.detach().double(),uc.double()
    if squared:
        expected_value = delta.square().sum(-1)
        dx = 2*c[:,None]*delta
        hc = 2*(delta*direction).sum(-1)
        hx = 2*c[:,None]*direction + 2*dc[:,None]*delta
        rtol,atol = 0.,0.
    else:
        norm = delta.square().sum(-1).sqrt()
        expected_value = norm
        dx = c[:,None]*delta/norm[:,None]
        projection = (delta*direction).sum(-1)
        hc = projection/norm
        hx = c[:,None]*(direction/norm[:,None]-delta*projection[:,None]/norm[:,None]**3)
        hx = hx+dc[:,None]*delta/norm[:,None]
        rtol,atol = 3e-6,3e-7
    for got,want in zip(gradient,(dx,-dx,expected_value)):
        assert got.dtype == torch.float32 and torch.isfinite(got).all()
        torch.testing.assert_close(got.double(),want,rtol=rtol,atol=atol)
    for got,want in zip(hessian,(hx,-hx,hc)):
        assert got.dtype == torch.float32 and torch.isfinite(got).all()
        torch.testing.assert_close(got.double(),want,rtol=rtol,atol=atol)
    assert sum(float(x.abs().sum()) for x in hessian)>0


def test_zero_norm_retains_explicit_finite_zero_gradient_convention():
    left = torch.zeros(2,3,requires_grad=True)
    right = torch.zeros(2,3,requires_grad=True)
    norm = residual_distance_fp32(left,right)
    first = torch.autograd.grad(norm.sum(),(left,right),create_graph=True)
    second = torch.autograd.grad((first[0]-first[1]).sum(),(left,right))
    assert torch.equal(norm,torch.zeros(2))
    assert all(torch.equal(x,torch.zeros_like(x)) for x in first+second)
    # This is the retained zero subgradient convention, not a differentiable-norm theorem at zero.


@pytest.mark.parametrize("squared",[False,True])
def test_noncontiguous_pair_order_and_fixed_tile_boundary(squared):
    source = (torch.arange(257*6).reshape(1,257,6)%23).float()/8
    left,right = source[...,::2],source[...,1::2]
    assert not left.is_contiguous() and not right.is_contiguous()
    delta = left.double()[:,:,None,:]-right.double()[:,None,:,:]
    expected = delta.square().sum(-1)
    if not squared:
        expected = expected.sqrt()
    actual = residual_pairwise_distance_fp32(left,right,squared=squared)
    torch.testing.assert_close(actual.double(),expected,rtol=1.3e-7,atol=0.)
    p,q = torch.arange(256,-1,-1),torch.roll(torch.arange(257),19)
    permuted = residual_pairwise_distance_fp32(left[:,p],right[:,q],squared=squared)
    assert torch.equal(permuted,actual[:,p][:,:,q])
    assert GEOMETRY_TILE_ROWS == 65536 and 257*257>GEOMETRY_TILE_ROWS


@pytest.mark.parametrize("shape",[(0,2,3),(1,0,3)])
def test_empty_pair_population_keeps_real_gradient_connection(shape):
    left = torch.empty(shape,requires_grad=True)
    right = torch.ones((shape[0],4,3),requires_grad=True)
    out = residual_pairwise_distance_fp32(left,right)
    gradient = torch.autograd.grad(out.sum(),(left,right))
    assert out.shape == (shape[0],shape[1],4)
    assert all(x.dtype == torch.float32 and torch.equal(x,torch.zeros_like(x)) for x in gradient)


@pytest.mark.parametrize("dtype",[torch.float16,torch.bfloat16,torch.float64])
def test_non_FP32_inputs_reject_without_cast_or_RNG_change(dtype):
    x = torch.ones(2,3,dtype=dtype)
    before = torch.get_rng_state().clone()
    with pytest.raises(ValueError,match="FP32"):
        residual_distance_fp32(x,x)
    assert torch.equal(before,torch.get_rng_state())


def test_AMP_rejects_even_with_FP32_raw_inputs():
    x = torch.ones(2,3)
    with torch.autocast(device_type="cpu",dtype=torch.bfloat16):
        with pytest.raises(ValueError,match="AMP"):
            residual_distance_fp32(x,x)


@pytest.mark.parametrize("kind",["nan","difference_overflow","squared_overflow","bad_shape","bad_switch"])
def test_invalid_domain_or_shape_is_explicit(kind):
    x,y = torch.ones(2,3),torch.zeros(2,3)
    kwargs={}
    if kind=="nan":
        x[0,0]=float("nan")
    elif kind=="difference_overflow":
        x.fill_(torch.finfo(torch.float32).max);y=-x
    elif kind=="squared_overflow":
        x.fill_(2.**80);kwargs["squared"]=True
    elif kind=="bad_shape":
        y=y[:,:2]
    else:
        kwargs["squared"]=1
    with pytest.raises(ValueError):
        residual_distance_fp32(x,y,**kwargs)
def test_actual_forward_and_two_derivative_orders_observe_only_FP32_floats():
    from torch.overrides import TorchFunctionMode
    class OnlyF32(TorchFunctionMode):
        def __init__(self):
            super().__init__();self.observed=0
        def inspect(self,value):
            if isinstance(value,torch.Tensor):
                if value.dtype.is_floating_point or value.dtype.is_complex:
                    assert value.dtype == torch.float32
                    self.observed+=1
            elif isinstance(value,(tuple,list)):
                for item in value:self.inspect(item)
            elif isinstance(value,dict):
                for item in value.values():self.inspect(item)
        def __torch_function__(self,func,types,args=(),kwargs=None):
            kwargs={} if kwargs is None else kwargs
            self.inspect(args);self.inspect(kwargs)
            out=func(*args,**kwargs);self.inspect(out)
            return out
    x=torch.tensor([[1.,2.,3.],[-.5,.25,1.]],requires_grad=True)
    y=torch.zeros_like(x,requires_grad=True)
    watcher=OnlyF32()
    with watcher:
        out=residual_distance_fp32(x,y)
        first=torch.autograd.grad(out.sum(),(x,y),create_graph=True)
        second=torch.autograd.grad((first[0]*torch.tensor([[.25,.5,1.],[1.,-.5,.25]])).sum(),(x,y))
    assert watcher.observed>100
    assert all(torch.isfinite(v).all() for v in first+second)


@pytest.fixture(scope="module",params=["C1-0","C1-a","C1-b"])
def primary(request):
    config=configuration(request.param)
    return config,seeded(config)


def test_actual_six_layer_source_S_backbone_trains_with_all_geometry_ports(primary):
    config,model=primary
    model.train();model.zero_grad(set_to_none=True)
    batch=graphs();batch.pos.requires_grad_(True)
    seen=[];handles=[]
    if hasattr(model.backbone,"pair_encoder"):
        handles.append(model.backbone.pair_encoder.register_forward_hook(
            lambda module,args,out:seen.append((out[1].dtype,tuple(out[1].shape)))))
    else:
        assert all(type(layer.attn.dist_mlp).__name__=="TiledDistanceMLP" for layer in model.backbone.layers)
        for layer in model.backbone.layers:
            handles.append(layer.attn.dist_mlp.register_forward_pre_hook(
                lambda module,args:seen.append((args[0].dtype,tuple(args[0].shape)))))
    before=torch.get_rng_state().clone()
    try:
        h0=model.encode_atoms(batch)
        assert h0.shape==(7,512) and h0.dtype==torch.float32
        loss=h0[:,7].square().mean()+h0[:,8].sum()/16
        loss.backward()
    finally:
        for handle in handles:handle.remove()
    assert len(seen)==(1 if hasattr(model.backbone,"pair_encoder") else 6)
    assert all(dtype==torch.float32 for dtype,_ in seen)
    assert batch.pos.grad is not None and torch.isfinite(batch.pos.grad).all() and batch.pos.grad.abs().sum()>0
    for layer in model.backbone.layers:
        for projection in (layer.attn.qkv,layer.attn.proj):
            assert projection.weight.grad is not None and torch.isfinite(projection.weight.grad).all()
            assert projection.weight.grad.abs().sum()>0
    assert torch.equal(before,torch.get_rng_state())
    require_geometry_backbone(model.backbone)


def test_seeded_tensor_state_and_H0_contract_preserve_parameters_but_bind_mode(primary):
    config,model=primary
    distance=config["backbone"].get("v3_architecture",{}).get("distance_bias","C1-0")
    control=seeded(configuration(distance,candidate=False))
    left,right=model.state_dict(),control.state_dict()
    assert set(left)==set(right)
    for key,value in left.items():
        if isinstance(value,torch.Tensor):
            assert torch.equal(value,right[key])
    assert model.config_dict()["backbone_config"]["geometry_mode"]==RESIDUAL_GEOMETRY
    assert "geometry_mode" not in control.config_dict()["backbone_config"]
    with pytest.raises(ValueError,match="numeric mode/model configuration"):
        load_numeric_bound_state_dict(model,right,numeric_checkpoint_contract(control))
    if hasattr(model.backbone,"pair_encoder"):
        assert model.backbone.get_extra_state()["geometry_mode"]==RESIDUAL_GEOMETRY
        assert "geometry_mode" not in control.backbone.get_extra_state()
        with pytest.raises(ValueError,match="checkpoint/options"):
            model.backbone.set_extra_state(control.backbone.get_extra_state())


@pytest.mark.parametrize("corruption",["one_layer","backbone_mode","configuration","foreign_attention","shared_pair_mode"])
def test_mixed_or_replaced_geometry_refuses_before_forward_RNG(primary,monkeypatch,corruption):
    _,model=primary
    if corruption=="one_layer":
        monkeypatch.setattr(model.backbone.layers[2].attn,"geometry_mode",LEGACY_GEOMETRY)
    elif corruption=="backbone_mode":
        monkeypatch.setattr(model.backbone,"geometry_mode",LEGACY_GEOMETRY)
    elif corruption=="configuration":
        monkeypatch.setitem(model.backbone_config,"geometry_mode",LEGACY_GEOMETRY)
    elif corruption=="foreign_attention":
        monkeypatch.setattr(model.backbone.layers[2],"attn",torch.nn.Identity())
    elif hasattr(model.backbone,"pair_encoder"):
        monkeypatch.setattr(model.backbone.pair_encoder,"geometry_mode",LEGACY_GEOMETRY)
    else:
        # Same strict mode check at a different layer; no skip or fabricated Native constructor.
        monkeypatch.setattr(model.backbone.layers[5].attn,"geometry_mode",LEGACY_GEOMETRY)
    before=torch.get_rng_state().clone()
    with pytest.raises(ValueError,match="geometry"):
        model.encode_atoms(graphs())
    assert torch.equal(before,torch.get_rng_state())


@pytest.mark.parametrize("bad",["unknown_mode","layers","dimension","heads","aggregation","projection","numeric","dropout"])
def test_invalid_constructor_refuses_before_parameter_RNG(bad):
    config=configuration();b=config["backbone"]
    if bad=="unknown_mode":b["geometry_mode"]="unknown"
    elif bad=="layers":b["layers"]=1
    elif bad=="dimension":b["dim"]=256
    elif bad=="heads":b["heads"]=4
    elif bad=="aggregation":b["attention_aggregation_mode"]="legacy"
    elif bad=="projection":b["attention_projection_mode"]="legacy"
    elif bad=="numeric":b["numeric_mode"]=config["head"]["numeric_mode"]="legacy"
    else:b["dropout"]=.1
    before=torch.get_rng_state().clone()
    with pytest.raises(ValueError):
        build_architecture_model(config)
    assert torch.equal(before,torch.get_rng_state())


@pytest.mark.parametrize("bad",["autocast","half_parameters"])
def test_standalone_shared_pair_encoder_rejects_before_silent_cast(bad):
    pair=SharedGaussianPairEncoder(ArchitectureOptions(distance_bias="C1-a"),119,geometry_mode=RESIDUAL_GEOMETRY)
    pos=torch.tensor([[[0.,0.,0.],[.5,.25,0.]]])
    elements=torch.zeros((1,2),dtype=torch.long);mask=torch.ones((1,2),dtype=torch.bool)
    if bad=="autocast":
        with torch.autocast(device_type="cpu",dtype=torch.bfloat16):
            with pytest.raises(ValueError,match="autocast"):
                pair(pos,elements,mask)
    else:
        pair.half()
        with pytest.raises(ValueError,match="FP32"):
            pair(pos,elements,mask)


@pytest.mark.parametrize("distance",["C1-0","C1-a","C1-b"])
def test_absent_and_explicit_legacy_keep_original_path_bits_and_RNG(distance,monkeypatch):
    config={"architecture":{"preset":"shared_light"},
        "backbone":{"dim":16,"layers":1,"heads":4,"ff_mult":1,"dropout":0.},
        "head":{"profile":"phase1","geometry_head":"equivariant_noise",
                "geometry_hidden_dim":8,"geometry_message_layers":0}}
    if distance!="C1-0":
        config=configuration_with_architecture(config,ArchitectureOptions(distance_bias=distance))
    explicit=deepcopy(config);explicit["backbone"]["geometry_mode"]=LEGACY_GEOMETRY
    before=torch.get_rng_state().clone()
    default,declared=seeded(config,source=False),seeded(explicit,source=False)
    assert torch.equal(before,torch.get_rng_state())
    for key,value in default.state_dict().items():
        other=declared.state_dict()[key]
        assert torch.equal(value,other) if isinstance(value,torch.Tensor) else value==other
    def forbidden(*args,**kwargs):
        raise AssertionError("Legacy geometry must use the unchanged original path")
    monkeypatch.setattr(attention_module,"residual_pairwise_distance_fp32",forbidden)
    monkeypatch.setattr(architecture_module,"residual_pairwise_distance_fp32",forbidden)
    default.eval();declared.eval()
    with torch.no_grad():
        assert torch.equal(default.encode_atoms(graphs()),declared.encode_atoms(graphs()))
    assert torch.equal(before,torch.get_rng_state())


@pytest.mark.parametrize("kind",["compile","trace"])
def test_unimplemented_fusion_or_trace_is_typed_rejection_without_backend_mutation(monkeypatch,kind):
    if kind=="compile":
        monkeypatch.setattr(torch.compiler,"is_compiling",lambda:True)
    else:
        monkeypatch.setattr(torch.jit,"is_tracing",lambda:True)
    x=torch.ones(2,3);before=torch.get_rng_state().clone()
    with pytest.raises(ValueError,match="eager"):
        residual_distance_fp32(x,x)
    assert torch.equal(before,torch.get_rng_state())


@pytest.mark.parametrize("pairwise",[False,True])
def test_unsupported_meta_device_is_typed_rejection(pairwise):
    x=torch.empty((1,2,3) if pairwise else (2,3),device="meta",dtype=torch.float32)
    with pytest.raises(ValueError,match="FP32"):
        (residual_pairwise_distance_fp32 if pairwise else residual_distance_fp32)(x,x)


def test_legacy_declared_configuration_cannot_silently_run_one_residual_geometry_layer(monkeypatch):
    config={"architecture":{"preset":"shared_light"},
        "backbone":{"dim":16,"layers":1,"heads":4,"ff_mult":1,"dropout":0.},
        "head":{"profile":"phase1","geometry_head":"equivariant_noise","geometry_hidden_dim":8,
                "geometry_message_layers":0}}
    model=seeded(config,source=False)
    monkeypatch.setattr(model.backbone.layers[0].attn,"geometry_mode",RESIDUAL_GEOMETRY)
    before=torch.get_rng_state().clone()
    with pytest.raises(ValueError,match="geometry mode bindings"):
        model.encode_atoms(graphs())
    assert torch.equal(before,torch.get_rng_state())
