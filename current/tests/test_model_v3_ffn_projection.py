"""Fixed all-six-layer FFN affine candidate: CPU engineering, not C4 acceptance."""
from copy import deepcopy
import math

import pytest
import torch
from torch_geometric.data import Batch, Data

from phychem_mfm.model import attention as attention_module
from phychem_mfm.model.attention import DenseFFN
from phychem_mfm.model.v3_architecture import (
    ArchitectureOptions, build_architecture_model, configuration_with_architecture)
from phychem_mfm.model.v3_attention_projection import K_BLOCK, DENSE_ROW_TILE
from phychem_mfm.model.v3_ffn_projection import (
    LEGACY_FFN, BLOCKED_FFN, ffn_projection, require_ffn_backbone)
from phychem_mfm.model.v3_numeric_stability import (
    COMPENSATED, numeric_checkpoint_contract, load_numeric_bound_state_dict)
from phychem_mfm.model.v3_performance import (
    PerformanceOptions, RuntimeFFN, build_performance_model)


@pytest.fixture(autouse=True)
def strict_CPU():
    threads = torch.get_num_threads()
    precision = torch.get_float32_matmul_precision()
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


def seeded_ffn(mode=BLOCKED_FFN):
    with torch.random.fork_rng(devices=[]):
        torch.random.default_generator.manual_seed(1742)
        return DenseFFN(512, 2, ffn_projection_mode=mode)


def configuration(distance="C1-0", *, candidate=True):
    result = {
        "architecture": {"preset": "shared_light"},
        "backbone": {"dim": 512, "layers": 6, "heads": 8, "ff_mult": 2,
                     "n_atom_types": 119, "dropout": 0., "numeric_mode": COMPENSATED,
                     "attention_aggregation_mode": "centered_fp32_v1",
                     "attention_projection_mode": "blocked_k64_compensated_fp32_v1",
                     "geometry_mode": "residual_expansion_fp32_v1"},
        "head": {"profile": "phase1", "geometry_head": "equivariant_noise",
                 "geometry_hidden_dim": 32, "geometry_message_layers": 0,
                 "geometry_pair_chunk_size": 8192, "numeric_mode": COMPENSATED}}
    if candidate:
        result["backbone"]["ffn_projection_mode"] = BLOCKED_FFN
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
             pos=torch.tensor([[.2, .1, .3], [1., .2, .4], [.3, 1.1, .1], [.5, .4, 1.]])),
    ])


def test_both_actual_affine_sites_retain_parameter_objects_and_noncontiguous_row_order(monkeypatch):
    module = seeded_ffn()
    with torch.no_grad():
        for parameter in module.parameters():
            parameter.zero_()
        axis = torch.arange(512)
        module.net[0].weight[axis, axis] = 1.
        module.net[3].weight[axis, axis] = 1.
    ids = {name: id(value) for name, value in module.named_parameters()}
    original = attention_module.ffn_projection
    calls = []
    def observed(owner, linear, value):
        result = original(owner, linear, value)
        calls.append((linear is module.net[0], linear is module.net[3], value.dtype, result.dtype))
        return result
    monkeypatch.setattr(attention_module, "ffn_projection", observed)

    values = (((torch.arange(257 * 1024).reshape(257, 1024) % 7) - 3).float() / 16)[:, ::2]
    assert not values.is_contiguous()
    rng = torch.get_rng_state().clone()
    expected = module(values)
    assert calls == [(True, False, torch.float32, torch.float32),
                     (False, True, torch.float32, torch.float32)]
    calls.clear()
    permutation = torch.arange(256, -1, -1)
    actual = module(values[permutation])
    assert torch.equal(actual, expected[permutation])
    assert ids == {name: id(value) for name, value in module.named_parameters()}
    assert torch.equal(rng, torch.get_rng_state())
    assert K_BLOCK == 64 and DENSE_ROW_TILE == 128


@pytest.mark.parametrize("site", ["first", "second"])
def test_cross_K_block_cancellation_through_each_actual_FFN_site_has_scalar_oracle(site):
    module = seeded_ffn()
    with torch.no_grad():
        for parameter in module.parameters():
            parameter.zero_()
        if site == "first":
            module.net[0].weight[0, 0] = 2.**24
            module.net[0].weight[0, 64] = 1.
            module.net[0].weight[0, 128] = -(2.**24)
            module.net[3].weight[0, 0] = 1.
            values = torch.ones(1, 512)
        else:
            module.net[0].bias[[0, 64, 128]] = 1.
            module.net[3].weight[0, 0] = 2.**24
            module.net[3].weight[0, 64] = 1.
            module.net[3].weight[0, 128] = -(2.**24)
            values = torch.zeros(1, 512)
        module.net[3].bias[0] = .5
    # In either case the real expression is SiLU(1)+.5, using cancellation across three blocks.
    expected = 1. / (1. + math.exp(-1.)) + .5
    actual = module(values)
    assert abs(float(actual[0, 0]) - expected) < 1e-7
    assert torch.count_nonzero(actual[:, 1:]) == 0


def test_complete_FFN_first_and_second_derivatives_have_independent_exact_dyadic_oracle():
    module = seeded_ffn()
    with torch.no_grad():
        for parameter in module.parameters():
            parameter.zero_()
        module.net[0].weight[0, 0] = .5
        module.net[0].weight[0, 64] = .25
        module.net[3].weight[0, 0] = .75
        module.net[3].weight[1, 0] = -.5
        module.net[3].bias[0] = .5
        module.net[3].bias[1] = -.25
    x = torch.zeros(1, 512)
    x[0, 0], x[0, 64] = 1., -2.
    x.requires_grad_()
    values = (x, module.net[0].weight, module.net[0].bias,
              module.net[3].weight, module.net[3].bias)
    directions = [torch.zeros_like(value) for value in values]
    directions[0][0, 0], directions[0][0, 64] = .125, -.25
    directions[1][0, 0], directions[1][0, 64] = -.125, .0625
    directions[2][0] = .5
    directions[3][0, 0], directions[3][1, 0] = .125, .25
    directions[4][0], directions[4][1] = -.125, .25
    y = module(x)
    assert torch.equal(y[:, :2], torch.tensor([[.5, -.25]]))
    gradients = torch.autograd.grad(.5 * y.square().sum(), values, create_graph=True)
    # z=0, SiLU(z)=0, SiLU'(0)=SiLU''(0)=1/2. Direct chain rule, no implementation replay.
    expected = [torch.zeros_like(value) for value in values]
    expected[0][0, 0], expected[0][0, 64] = .125, .0625
    expected[1][0, 0], expected[1][0, 64] = .25, -.5
    expected[2][0] = .25
    expected[4][0], expected[4][1] = .5, -.25
    for actual, oracle in zip(gradients, expected):
        assert torch.equal(actual, oracle)
    assert torch.count_nonzero(gradients[3]) == 0  # Exact zero activation; cross Hessian remains nonzero.
    first_direction = sum((g * direction).sum() for g, direction in zip(gradients, directions))
    assert float(first_direction) == -.0625
    hessian = torch.autograd.grad(first_direction, values)
    second = [torch.zeros_like(value) for value in values]
    second[0][0, 0], second[0][0, 64] = -.029296875, .0166015625
    second[1][0, 0], second[1][0, 64] = .03515625, -.0703125
    second[2][0] = .00390625
    second[3][0, 0], second[3][1, 0] = .0625, -.03125
    second[4][0], second[4][1] = -.03125, .1875
    for actual, oracle in zip(hessian, second):
        assert torch.equal(actual, oracle)
        assert actual.abs().sum() > 0
    # d2F=||dY||²+<Y,d2Y>; here <Y,d2Y>=0, independent scalar value37/1024.
    assert float(sum((h * direction).sum() for h, direction in zip(hessian, directions))) == .0361328125
    assert all(value.dtype == torch.float32 for value in (*gradients, *hessian))


def test_nonzero_SiLU_point_has_independent_input_weight_bias_first_derivatives():
    module = seeded_ffn()
    with torch.no_grad():
        for parameter in module.parameters():
            parameter.zero_()
        module.net[0].weight[0, 0] = 1.
        module.net[3].weight[0, 0] = 2.
        module.net[3].bias[0] = .5
    x = torch.zeros(1, 512)
    x[0, 0] = 1.
    x.requires_grad_()
    values = (x, module.net[0].weight, module.net[0].bias,
              module.net[3].weight, module.net[3].bias)
    result = module(x)[0, 0]
    gradients = torch.autograd.grad(result, values)
    sigma = 1. / (1. + math.exp(-1.))
    slope = sigma + sigma * (1. - sigma)
    expected = [torch.zeros_like(value) for value in values]
    expected[0][0, 0] = 2 * slope
    expected[1][0, 0] = 2 * slope
    expected[2][0] = 2 * slope
    expected[3][0, 0] = sigma
    expected[4][0] = 1.
    for actual, oracle in zip(gradients, expected):
        torch.testing.assert_close(actual, oracle, rtol=0, atol=5e-7)
    assert abs(float(result) - (2 * sigma + .5)) < 5e-7


def test_empty_rows_have_real_zero_parameter_gradients_and_no_RNG_draw():
    module = seeded_ffn()
    x = torch.empty(0, 512, requires_grad=True)
    before = torch.get_rng_state().clone()
    output = module(x)
    output.sum().backward()
    assert output.shape == (0, 512) and x.grad.shape == x.shape
    assert all(parameter.grad is not None and torch.count_nonzero(parameter.grad) == 0
               for parameter in module.parameters())
    assert torch.equal(before, torch.get_rng_state())


@pytest.mark.parametrize("dtype", [torch.float64, torch.bfloat16, torch.float16])
def test_non_FP32_parameters_or_inputs_are_rejected_without_conversion(dtype):
    module = seeded_ffn()
    before = torch.get_rng_state().clone()
    with pytest.raises(ValueError, match="FP32"):
        module(torch.ones(1, 512, dtype=dtype))
    module.to(dtype=dtype)
    with pytest.raises(ValueError, match="FP32"):
        module(torch.ones(1, 512))
    assert torch.equal(before, torch.get_rng_state())


def test_CPU_autocast_rejects_before_any_candidate_affine_RNG():
    module = seeded_ffn()
    before = torch.get_rng_state().clone()
    with torch.autocast("cpu", dtype=torch.bfloat16):
        with pytest.raises(ValueError, match="autocast"):
            module(torch.ones(1, 512))
    assert torch.equal(before, torch.get_rng_state())


@pytest.mark.parametrize("bad", ["precision", "cudnn_TF32", "unreadable"])
def test_precision_controls_are_rejected_not_mutated(monkeypatch, bad):
    module = seeded_ffn()
    if bad == "precision":
        monkeypatch.setattr(torch, "get_float32_matmul_precision", lambda: "high")
    elif bad == "cudnn_TF32":
        monkeypatch.setattr(torch.backends.cudnn, "allow_tf32", True)
    else:
        def invalid():
            raise RuntimeError("unit mixed precision state")
        monkeypatch.setattr(torch, "get_float32_matmul_precision", invalid)
    before = torch.get_rng_state().clone()
    with pytest.raises(ValueError):
        module(torch.ones(1, 512))
    assert torch.equal(before, torch.get_rng_state())


@pytest.mark.parametrize("bad", ["dim", "ff_mult", "dropout", "mode"])
def test_standalone_constructor_rejects_unsupported_scope_before_RNG(bad):
    kwargs = dict(dim=512, ff_mult=2, ffn_projection_mode=BLOCKED_FFN)
    kwargs.update({"dim": 256} if bad == "dim" else {"ff_mult": 4} if bad == "ff_mult"
                  else {"dropout": .1} if bad == "dropout" else {"ffn_projection_mode": "unknown"})
    before = torch.get_rng_state().clone()
    with pytest.raises(ValueError):
        DenseFFN(**kwargs)
    assert torch.equal(before, torch.get_rng_state())

@pytest.fixture(scope="module", params=["C1-0", "C1-a", "C1-b"])
def primary(request):
    config = configuration(request.param)
    model = seeded_model(config)
    yield config, model
    del model


def test_six_real_layers_train_through_all_twelve_FFN_affines(primary, monkeypatch):
    _, model = primary
    model.train()
    model.zero_grad(set_to_none=True)
    batch = graphs()
    batch.pos.requires_grad_()
    original = attention_module.ffn_projection
    sites = {(id(layer.ffn), id(linear)): (i, name)
             for i, layer in enumerate(model.backbone.layers)
             for name, linear in (("in", layer.ffn.net[0]), ("out", layer.ffn.net[3]))}
    calls = []
    def observed(owner, linear, values):
        result = original(owner, linear, values)
        calls.append(sites[id(owner), id(linear)])
        assert values.dtype == result.dtype == torch.float32
        return result
    monkeypatch.setattr(attention_module, "ffn_projection", observed)
    before = torch.get_rng_state().clone()
    h0 = model.encode_atoms(batch)
    cotangent = ((torch.arange(h0.numel()).reshape_as(h0) % 13) - 6).float() / 128
    (h0 * cotangent).sum().backward()
    assert calls == [(layer, name) for layer in range(6) for name in ("in", "out")]
    assert h0.shape == (7, 512) and h0.dtype == torch.float32
    require_ffn_backbone(model.backbone, expected_mode=BLOCKED_FFN)
    for layer in model.backbone.layers:
        assert layer.ffn.ffn_projection_mode == BLOCKED_FFN
        for linear in (layer.ffn.net[0], layer.ffn.net[3]):
            for parameter in linear.parameters():
                assert parameter.grad is not None and torch.isfinite(parameter.grad).all()
                assert parameter.grad.abs().sum() > 0
    assert batch.pos.grad is not None and torch.isfinite(batch.pos.grad).all()
    assert torch.equal(before, torch.get_rng_state())


def test_initial_parameters_state_keys_and_RNG_match_geometry_base_and_bound_restore(primary):
    config, model = primary
    distance = config["backbone"].get("v3_architecture", {}).get("distance_bias", "C1-0")
    rng = torch.get_rng_state().clone()
    control_config = configuration(distance, candidate=False)
    control = seeded_model(control_config)
    assert torch.equal(rng, torch.get_rng_state())
    candidate_state, control_state = model.state_dict(), control.state_dict()
    assert set(candidate_state) == set(control_state)
    for key, value in candidate_state.items():
        if isinstance(value, torch.Tensor):
            assert torch.equal(value, control_state[key])
    contract = numeric_checkpoint_contract(model)
    assert contract["model_config"]["backbone_config"]["ffn_projection_mode"] == BLOCKED_FFN
    assert "ffn_projection_mode" not in control.config_dict()["backbone_config"]
    assert contract != numeric_checkpoint_contract(control)
    with pytest.raises(ValueError, match="numeric mode/model configuration"):
        load_numeric_bound_state_dict(model, control_state, numeric_checkpoint_contract(control))
    if hasattr(model.backbone, "pair_encoder"):
        assert model.backbone.get_extra_state()["ffn_projection_mode"] == BLOCKED_FFN
        assert "ffn_projection_mode" not in control.backbone.get_extra_state()
        with pytest.raises(ValueError, match="checkpoint/options"):
            model.backbone.set_extra_state(control.backbone.get_extra_state())
    saved = deepcopy(candidate_state)
    identities = {name: id(value) for name, value in model.named_parameters()}
    with torch.no_grad():
        model.backbone.layers[0].ffn.net[0].weight.add_(1.)
    load_numeric_bound_state_dict(model, saved, contract)
    for key, value in saved.items():
        if isinstance(value, torch.Tensor):
            assert torch.equal(model.state_dict()[key], value)
    assert identities == {name: id(value) for name, value in model.named_parameters()}
    assert torch.equal(rng, torch.get_rng_state())


@pytest.mark.parametrize("corruption", ["one_mode", "backbone_mode", "config_mode", "unknown_ffn", "dropout", "compiled"])
def test_model_refuses_partial_fallback_replacement_or_dropout_before_RNG(primary, monkeypatch, corruption):
    _, model = primary
    if corruption == "one_mode":
        monkeypatch.setattr(model.backbone.layers[3].ffn, "ffn_projection_mode", LEGACY_FFN)
    elif corruption == "backbone_mode":
        monkeypatch.setattr(model.backbone, "ffn_projection_mode", LEGACY_FFN)
    elif corruption == "config_mode":
        monkeypatch.setitem(model.backbone_config, "ffn_projection_mode", LEGACY_FFN)
    elif corruption == "unknown_ffn":
        monkeypatch.setattr(model.backbone.layers[0], "ffn", torch.nn.Identity())
    elif corruption == "dropout":
        monkeypatch.setitem(model.backbone.layers[0].ffn.net._modules, "2", torch.nn.Dropout(.2))
    else:
        # Metadata boundary for a replaced/compiled forward: no compiler execution in this test.
        monkeypatch.setitem(model.backbone.__dict__, "forward", lambda data: data.pos)
    rng = torch.get_rng_state().clone()
    with pytest.raises(ValueError):
        model.encode_atoms(graphs())
    assert torch.equal(rng, torch.get_rng_state())


@pytest.mark.parametrize("bad", ["layers", "dim", "heads", "ff_mult", "dropout", "numeric", "aggregation", "attention_projection", "geometry", "unknown_mode"])
def test_full_constructor_scope_rejects_before_parameter_RNG(bad):
    config = configuration()
    backbone = config["backbone"]
    if bad in {"layers", "dim", "heads", "ff_mult"}:
        backbone[bad] = {"layers": 1, "dim": 256, "heads": 4, "ff_mult": 4}[bad]
    elif bad == "dropout":
        backbone["dropout"] = .2
    elif bad == "numeric":
        backbone["numeric_mode"] = config["head"]["numeric_mode"] = "legacy"
    else:
        key = {"aggregation": "attention_aggregation_mode", "attention_projection": "attention_projection_mode",
               "geometry": "geometry_mode", "unknown_mode": "ffn_projection_mode"}[bad]
        backbone[key] = "legacy" if bad != "unknown_mode" else "unknown"
    rng = torch.get_rng_state().clone()
    with pytest.raises(ValueError):
        build_architecture_model(config)
    assert torch.equal(rng, torch.get_rng_state())


@pytest.mark.parametrize("kind", ["fp32", "bf16", "compiled"])
def test_performance_Native_or_compiled_builder_cannot_silently_replace_FFN(kind):
    options = PerformanceOptions(precision="bf16" if kind == "bf16" else "fp32",
                                 compile_backbone=kind == "compiled")
    before = torch.get_rng_state().clone()
    with pytest.raises(ValueError, match="FFN.*unsupported"):
        build_performance_model(configuration(), options)
    assert torch.equal(before, torch.get_rng_state())


@pytest.mark.parametrize("precision", ["fp32", "bf16"])
def test_direct_RuntimeFFN_constructor_rejects_candidate(precision):
    original = seeded_ffn()
    before = torch.get_rng_state().clone()
    with pytest.raises(ValueError, match="FFN.*unsupported"):
        RuntimeFFN(original, precision=precision)
    assert torch.equal(before, torch.get_rng_state())


@pytest.mark.parametrize("distance", ["C1-0", "C1-a"])
def test_absent_and_explicit_legacy_keep_original_net_output_config_state_and_RNG(distance, monkeypatch):
    config = {"architecture": {"preset": "shared_light"},
              "backbone": {"dim": 32, "layers": 1, "heads": 4, "ff_mult": 1, "dropout": 0.},
              "head": {"profile": "phase1", "geometry_head": "equivariant_noise",
                       "geometry_hidden_dim": 16, "geometry_message_layers": 0}}
    if distance != "C1-0":
        config = configuration_with_architecture(config, ArchitectureOptions(distance_bias=distance))
    explicit = deepcopy(config)
    explicit["backbone"]["ffn_projection_mode"] = LEGACY_FFN
    before = torch.get_rng_state().clone()
    default_model, explicit_model = seeded_model(config), seeded_model(explicit)
    for key, value in default_model.state_dict().items():
        other = explicit_model.state_dict()[key]
        assert torch.equal(value, other) if isinstance(value, torch.Tensor) else value == other
    assert "ffn_projection_mode" not in default_model.config_dict()["backbone_config"]
    assert explicit_model.config_dict()["backbone_config"]["ffn_projection_mode"] == LEGACY_FFN
    def forbidden(*args, **kwargs):
        raise AssertionError("Legacy FFN must execute original net directly")
    monkeypatch.setattr(attention_module, "ffn_projection", forbidden)
    default_model.eval(); explicit_model.eval()
    with torch.no_grad():
        assert torch.equal(default_model.encode_atoms(graphs()), explicit_model.encode_atoms(graphs()))
    assert torch.equal(before, torch.get_rng_state())


def test_wrong_site_rejects_and_legacy_net_still_supports_ordinary_training():
    candidate = seeded_ffn()
    with pytest.raises(ValueError, match="two declared"):
        ffn_projection(candidate, candidate.net[1], torch.ones(1, 512))
    legacy = seeded_ffn(LEGACY_FFN)
    x = torch.ones(2, 512, requires_grad=True)
    legacy(x).square().sum().backward()
    assert x.grad is not None and all(parameter.grad is not None for parameter in legacy.parameters())


def test_empty_packed_model_input_is_typed_rejection_without_RNG(primary):
    _, model = primary
    empty = Data(x=torch.empty((0, 1), dtype=torch.long), pos=torch.empty((0, 3)))
    before = torch.get_rng_state().clone()
    with pytest.raises(ValueError):
        model.encode_atoms(empty)
    assert torch.equal(before, torch.get_rng_state())
