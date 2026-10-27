"""One fixed FP32 projection method: engineering oracles, not C4 acceptance."""
from copy import deepcopy

import pytest
import torch
from torch_geometric.data import Batch, Data

from phychem_mfm.model import attention as attention_module
from phychem_mfm.model import v3_architecture as architecture_module
from phychem_mfm.model.v3_architecture import (
    ArchitectureOptions, build_architecture_model, configuration_with_architecture)
from phychem_mfm.model.v3_attention_projection import (
    K_BLOCK, DENSE_ROW_TILE, LEGACY_PROJECTION, BLOCKED_PROJECTION,
    blocked_linear_fp32, require_projection_backbone)
from phychem_mfm.model.v3_numeric_stability import (
    COMPENSATED, numeric_checkpoint_contract, load_numeric_bound_state_dict)
from phychem_mfm.model.v3_performance import PerformanceOptions, build_performance_model


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


def primary_configuration(distance="C1-0", *, candidate=True):
    configuration = {
        "architecture": {"preset": "shared_light"},
        "backbone": {"dim": 512, "layers": 6, "heads": 8, "ff_mult": 2,
                     "n_atom_types": 119, "dropout": 0.,
                     "numeric_mode": COMPENSATED,
                     "attention_aggregation_mode": "centered_fp32_v1"},
        "head": {"profile": "phase1", "geometry_head": "equivariant_noise",
                 "geometry_hidden_dim": 32, "geometry_message_layers": 0,
                 "geometry_pair_chunk_size": 8192, "numeric_mode": COMPENSATED}}
    if candidate:
        configuration["backbone"]["attention_projection_mode"] = BLOCKED_PROJECTION
    if distance != "C1-0":
        configuration = configuration_with_architecture(
            configuration, ArchitectureOptions(distance_bias=distance))
    return configuration


def seeded_model(configuration, seed=1742):
    # CPU-only initialization; do not mutate or queue CUDA RNG seeds.
    with torch.random.fork_rng(devices=[]):
        torch.random.default_generator.manual_seed(seed)
        return build_architecture_model(configuration)


def graphs():
    return Batch.from_data_list([
        Data(x=torch.tensor([[5], [0], [7]]),
             pos=torch.tensor([[0., 0., 0.], [.7, .1, 0.], [.1, .8, .2]])),
        Data(x=torch.tensor([[6], [5], [0], [7]]),
             pos=torch.tensor([[.2, .1, .3], [1., .2, .4], [.3, 1.1, .1], [.5, .4, 1.]])),
    ])


@pytest.mark.parametrize("bias", [None, 1.5])
def test_cross_block_cancellation_has_independent_exact_scalar_oracle_and_bias_once(bias):
    x = torch.ones(2, 3 * K_BLOCK)
    weight = torch.zeros(1, 3 * K_BLOCK)
    weight[0, 0], weight[0, K_BLOCK], weight[0, 2 * K_BLOCK] = 2.**24, 1., -(2.**24)
    offset = None if bias is None else torch.tensor([bias])
    actual = blocked_linear_fp32(x, weight, offset)
    # Exact real dot: 2^24 + 1 - 2^24 = 1; no algorithm is replayed here.
    assert torch.equal(actual, torch.full((2, 1), 1. if bias is None else 2.5))
    assert K_BLOCK == 64 and DENSE_ROW_TILE == 128


def test_noncontiguous_inputs_weights_bias_and_rows_keep_source_order_across_tiles():
    x_base = (torch.arange(257 * 256).reshape(257, 256) % 7).float() / 8
    w_base = (torch.arange(128 * 5).reshape(128, 5) % 5 - 2).float() / 16
    x, weight = x_base[:, ::2], w_base.t()
    bias_base = torch.arange(10, dtype=torch.float32) / 8
    bias = bias_base[::2]
    assert not x.is_contiguous() and not weight.is_contiguous() and not bias.is_contiguous()
    expected = (x.double().matmul(weight.double().t()) + bias.double()).float()
    actual = blocked_linear_fp32(x, weight, bias)
    assert torch.equal(actual, expected)
    permutation = torch.cat((torch.arange(256, -1, -2), torch.arange(255, -1, -2)))
    moved = blocked_linear_fp32(x[permutation], weight, bias)
    assert torch.equal(moved, actual[permutation])


def affine_case():
    x = (torch.arange(2 * 128).reshape(2, 128) % 5 - 2).float() / 16
    weight = (torch.arange(3 * 128).reshape(3, 128) % 7 - 3).float() / 32
    bias = torch.tensor([.125, -.25, .375])
    return tuple(value.requires_grad_() for value in (x, weight, bias))


def test_independent_analytic_input_weight_and_bias_gradients():
    x, weight, bias = affine_case()
    cotangent = torch.tensor([[.25, -.5, .125], [-.125, .75, .5]])
    actual = blocked_linear_fp32(x, weight, bias)
    gx, gw, gb = torch.autograd.grad((actual * cotangent).sum(), (x, weight, bias), create_graph=True)
    # Derivatives of sum_mo G_mo(sum_k X_mk W_ok + b_o).
    expected_x = cotangent.double() @ weight.detach().double()
    expected_w = cotangent.double().t() @ x.detach().double()
    expected_b = cotangent.double().sum(0)
    assert torch.equal(gx, expected_x.float())
    assert torch.equal(gw, expected_w.float())
    assert torch.equal(gb, expected_b.float())
    assert gx.abs().sum() > 0 and gw.abs().sum() > 0 and gb.abs().sum() > 0


def test_complete_second_order_cross_direction_has_independent_polynomial_oracle():
    x, weight, bias = affine_case()
    u = ((torch.arange(x.numel()).reshape_as(x) % 3) - 1).float() / 32
    v = ((torch.arange(weight.numel()).reshape_as(weight) % 5) - 2).float() / 64
    c = torch.tensor([.25, -.125, .5])
    output = blocked_linear_fp32(x, weight, bias)
    gradients = torch.autograd.grad(.5 * output.square().sum(), (x, weight, bias), create_graph=True)
    first_direction = sum((g * d).sum() for g, d in zip(gradients, (u, v, c)))
    second = torch.autograd.grad(first_direction, (x, weight, bias), create_graph=True)
    actual_second_direction = sum((g * d).sum() for g, d in zip(second, (u, v, c)))
    xd, wd, bd, ud, vd, cd = [t.detach().double() for t in (x, weight, bias, u, v, c)]
    y = xd @ wd.t() + bd
    dy = ud @ wd.t() + xd @ vd.t() + cd
    # F=.5||XW^T+b||²: d²F=||dY||² + 2<Y,U V^T>.
    expected_first = (y * dy).sum()
    expected_second = dy.square().sum() + 2 * (y * (ud @ vd.t())).sum()
    # Check every Hessian-vector output block as well as their contraction.
    expected_blocks = (dy @ wd + y @ vd, dy.t() @ xd + y.t() @ ud, dy.sum(0))
    for actual_block, expected_block in zip(second, expected_blocks):
        torch.testing.assert_close(actual_block.double(), expected_block, rtol=0, atol=1e-6)
    torch.testing.assert_close(first_direction.double(), expected_first, rtol=0, atol=1e-6)
    torch.testing.assert_close(actual_second_direction.double(), expected_second, rtol=0, atol=1e-6)
    assert actual_second_direction.abs() > 0
    assert all(torch.isfinite(value).all() for value in second)


@pytest.mark.parametrize("has_bias", [False, True])
def test_empty_rows_have_correct_shape_and_real_zero_gradients(has_bias):
    x = torch.empty(0, 128, requires_grad=True)
    weight = torch.ones(3, 128, requires_grad=True)
    bias = torch.ones(3, requires_grad=True) if has_bias else None
    result = blocked_linear_fp32(x, weight, bias)
    assert result.shape == (0, 3) and result.dtype == torch.float32
    result.sum().backward()
    assert x.grad.shape == x.shape and torch.count_nonzero(weight.grad) == 0
    if has_bias:
        assert torch.count_nonzero(bias.grad) == 0


@pytest.mark.parametrize("dtype", [torch.float64, torch.bfloat16, torch.float16])
def test_non_FP32_is_rejected_without_cast_or_RNG_change(dtype):
    x, weight = torch.ones(2, 128, dtype=dtype), torch.ones(3, 128, dtype=dtype)
    before = torch.get_rng_state().clone()
    with pytest.raises(ValueError, match="already be FP32"):
        blocked_linear_fp32(x, weight)
    assert torch.equal(before, torch.get_rng_state())


def test_active_CPU_autocast_rejected_even_when_arguments_are_FP32():
    with torch.autocast("cpu", dtype=torch.bfloat16):
        with pytest.raises(ValueError, match="autocast"):
            blocked_linear_fp32(torch.ones(2, 128), torch.ones(3, 128))


def test_TF32_or_unreadable_precision_control_is_typed_rejection(monkeypatch):
    x, weight = torch.ones(2, 128), torch.ones(3, 128)
    monkeypatch.setattr(torch, "get_float32_matmul_precision", lambda: "high")
    with pytest.raises(ValueError, match="highest FP32"):
        blocked_linear_fp32(x, weight)
    def mixed():
        raise RuntimeError("unit simulated mixed precision API")
    monkeypatch.setattr(torch, "get_float32_matmul_precision", mixed)
    with pytest.raises(ValueError, match="mixed precision-control"):
        blocked_linear_fp32(x, weight)


@pytest.mark.parametrize("kind", ["K_not_multiple", "mismatch", "bias_width"])
def test_unsupported_linear_shapes_reject(kind):
    x, weight, bias = torch.ones(2, 128), torch.ones(3, 128), torch.ones(3)
    if kind == "K_not_multiple":
        x, weight = torch.ones(2, 65), torch.ones(3, 65)
    elif kind == "mismatch":
        weight = torch.ones(3, 64)
    else:
        bias = torch.ones(4)
    with pytest.raises(ValueError):
        blocked_linear_fp32(x, weight, bias)


@pytest.fixture(scope="module", params=["C1-0", "C1-a", "C1-b"])
def primary(request):
    configuration = primary_configuration(request.param)
    model = seeded_model(configuration)
    yield configuration, model
    del model


def test_real_six_layer_model_trains_through_all_twelve_projections(primary):
    configuration, model = primary
    model.train()
    model.zero_grad(set_to_none=True)
    batch = graphs()
    batch.pos.requires_grad_()
    before_rng = torch.get_rng_state().clone()
    result = model.encode_atoms(batch)
    cotangent = ((torch.arange(result.numel()).reshape_as(result) % 13) - 6).float() / 128
    (result * cotangent).sum().backward()
    assert result.shape == (7, 512) and result.dtype == torch.float32
    require_projection_backbone(model.backbone, expected_mode=BLOCKED_PROJECTION)
    for layer in model.backbone.layers:
        assert layer.attn.attention_projection_mode == BLOCKED_PROJECTION
        for projection in (layer.attn.qkv, layer.attn.proj):
            assert projection.weight.grad is not None
            assert torch.isfinite(projection.weight.grad).all() and projection.weight.grad.abs().sum() > 0
    assert batch.pos.grad is not None and torch.isfinite(batch.pos.grad).all()
    assert torch.equal(before_rng, torch.get_rng_state())


def test_explicit_configuration_state_identity_and_initial_parameters_are_unchanged(primary):
    configuration, model = primary
    control_configuration = primary_configuration(
        configuration["backbone"].get("v3_architecture", {}).get("distance_bias", "C1-0"), candidate=False)
    control = seeded_model(control_configuration)
    left, right = model.state_dict(), control.state_dict()
    assert set(left) == set(right)
    for key in left:
        if isinstance(left[key], torch.Tensor):
            assert torch.equal(left[key], right[key])
    assert numeric_checkpoint_contract(model) != numeric_checkpoint_contract(control)
    with pytest.raises(ValueError, match="numeric mode/model configuration"):
        load_numeric_bound_state_dict(model, right, numeric_checkpoint_contract(control))
    if hasattr(model.backbone, "pair_encoder"):
        assert model.backbone.get_extra_state()["attention_projection_mode"] == BLOCKED_PROJECTION
        assert "attention_projection_mode" not in control.backbone.get_extra_state()
    assert configuration["backbone"]["attention_projection_mode"] == BLOCKED_PROJECTION


@pytest.mark.parametrize("corruption", ["one_layer", "backbone_mode", "foreign_attention", "real_dropout"])
def test_model_refuses_missing_mode_replacement_or_new_dropout_before_RNG(primary, monkeypatch, corruption):
    _, model = primary
    if corruption == "one_layer":
        monkeypatch.setattr(model.backbone.layers[2].attn, "attention_projection_mode", LEGACY_PROJECTION)
    elif corruption == "backbone_mode":
        monkeypatch.setattr(model.backbone, "attention_projection_mode", LEGACY_PROJECTION)
    elif corruption == "foreign_attention":
        replacement = torch.nn.Identity()
        monkeypatch.setattr(model.backbone.layers[2], "attn", replacement)
    else:
        monkeypatch.setitem(model.backbone.layers[0].ffn.net._modules, "2", torch.nn.Dropout(.2))
    before = torch.get_rng_state().clone()
    with pytest.raises(ValueError):
        model.encode_atoms(graphs())
    assert torch.equal(before, torch.get_rng_state())


@pytest.mark.parametrize("precision", ["fp32", "bf16"])
def test_performance_Native_replacement_is_explicitly_unsupported(precision):
    with pytest.raises(ValueError, match="unsupported"):
        build_performance_model(primary_configuration(), PerformanceOptions(precision=precision))


@pytest.mark.parametrize("bad", ["layers", "dim", "heads", "aggregation", "numeric", "dropout", "unknown_mode"])
def test_constructor_scope_rejects_before_parameter_RNG(bad):
    configuration = primary_configuration()
    backbone = configuration["backbone"]
    if bad == "layers":
        backbone["layers"] = 1
    elif bad == "dim":
        backbone["dim"] = 256
    elif bad == "heads":
        backbone["heads"] = 4
    elif bad == "aggregation":
        backbone["attention_aggregation_mode"] = "legacy"
    elif bad == "numeric":
        backbone["numeric_mode"] = configuration["head"]["numeric_mode"] = "legacy"
    elif bad == "dropout":
        backbone["dropout"] = .1
    else:
        backbone["attention_projection_mode"] = "unknown_projection"
    before = torch.get_rng_state().clone()
    with pytest.raises(ValueError):
        build_architecture_model(configuration)
    assert torch.equal(before, torch.get_rng_state())


@pytest.mark.parametrize("distance", ["C1-0", "C1-a"])
def test_absent_and_explicit_legacy_use_original_Linear_bitwise(distance, monkeypatch):
    configuration = {"architecture": {"preset": "shared_light"},
        "backbone": {"dim": 32, "layers": 1, "heads": 4, "ff_mult": 1, "dropout": 0.},
        "head": {"profile": "phase1", "geometry_head": "equivariant_noise",
                 "geometry_hidden_dim": 16, "geometry_message_layers": 0}}
    if distance != "C1-0":
        configuration = configuration_with_architecture(configuration, ArchitectureOptions(distance_bias=distance))
    explicit = deepcopy(configuration)
    explicit["backbone"]["attention_projection_mode"] = LEGACY_PROJECTION
    before = torch.get_rng_state().clone()
    default_model, legacy_model = seeded_model(configuration), seeded_model(explicit)
    assert torch.equal(before, torch.get_rng_state())
    for key, value in default_model.state_dict().items():
        actual = legacy_model.state_dict()[key]
        assert torch.equal(value, actual) if isinstance(value, torch.Tensor) else value == actual
    def forbidden(*args, **kwargs):
        raise AssertionError("Legacy mode must call original Linear directly")
    monkeypatch.setattr(attention_module, "attention_projection", forbidden)
    monkeypatch.setattr(architecture_module, "attention_projection", forbidden)
    default_model.eval(); legacy_model.eval()
    with torch.no_grad():
        assert torch.equal(default_model.encode_atoms(graphs()), legacy_model.encode_atoms(graphs()))
