"""Analytic gradients and mode boundaries; full physical C4 matrix is separate."""
import pytest
import torch
from torch import nn
from torch_geometric.data import Batch, Data

from phychem_mfm.model.attention import DenseGeoSelfAttention
from phychem_mfm.model.v3_architecture import (
    ArchitectureOptions, SharedPairAttention, build_architecture_model,
)
from phychem_mfm.model.v3_attention_numerics import (
    LEGACY_AGGREGATION, CENTERED_FP32, centered_attention_value,
)
from phychem_mfm.model.v3_numeric_stability import (
    COMPENSATED, numeric_mode, numeric_checkpoint_contract, load_numeric_bound_state_dict,
)
from phychem_mfm.model.v3_performance import (
    PerformanceOptions, RuntimeDenseAttention, build_performance_model,
)


C1_KINDS = ("C1-0", "C1-a", "C1-b")


def configuration(mode=CENTERED_FP32):
    result = {"architecture": {"preset": "shared_light"},
        "backbone": {"n_atom_types": 119, "dim": 16, "layers": 6, "heads": 4,
                     "ff_mult": 2, "dropout": 0., "use_radius_mask": False, "radius": 8.},
        "head": {"profile": "phase1", "geometry_head": "equivariant_noise",
                 "geometry_hidden_dim": 8, "geometry_rbf_count": 8},
        "numeric_stability": {"mode": COMPENSATED}}
    if mode is not None:
        result["backbone"]["attention_aggregation_mode"] = mode
    return result


def model(kind="C1-0", mode=CENTERED_FP32):
    return build_architecture_model(configuration(mode),
        ArchitectureOptions(distance_bias=kind, pair_dim=8, pair_hidden_dim=8))


def atoms():
    return Batch.from_data_list([
        Data(x=torch.tensor([[5], [7], [0]]),
             pos=torch.tensor([[0., 0., 0.], [1.1, .2, 0.], [.2, .8, .3]])),
        Data(x=torch.tensor([[5], [8]]), pos=torch.tensor([[.1, .2, .3], [1.8, .3, .1]]))])


def operands():
    p = torch.full((1, 1, 4, 4), .25)
    v = torch.tensor([[[[2., -1.], [4., 3.], [-2., 5.], [0., 1.]]]])
    return p, v, torch.ones(1, 4, dtype=torch.bool)


def attention(kind="dense", dropout=0.):
    original = DenseGeoSelfAttention(16, 4, dropout=dropout,
                                     attention_aggregation_mode=CENTERED_FP32)
    return original if kind == "dense" else SharedPairAttention(original, 8)


def call_attention(module, x, mask):
    pos = torch.arange(x.shape[0]*x.shape[1]*3, dtype=torch.float32).reshape(*x.shape[:2], 3)/8
    if isinstance(module, SharedPairAttention):
        pair = torch.ones(x.shape[0], x.shape[1], x.shape[1], 8)
        distance = torch.zeros(x.shape[0], x.shape[1], x.shape[1])
        return module(x, pair, distance, mask)
    return module(x, pos, mask)[0]


def test_true_softmax_and_value_gradients_match_analytic_dyadic_oracle():
    # All quantities in this oracle are exactly representable binary fractions.
    logits = torch.zeros(1, 1, 4, 4, requires_grad=True)
    _, values, mask = operands()
    values.requires_grad_()
    weight = torch.tensor([[[[1., .5], [.5, -1.], [-.5, .25], [2., 1.]]]])
    result = centered_attention_value(logits.softmax(-1), values, mask)
    mean = values.detach().mean(-2, keepdim=True)
    torch.testing.assert_close(result, mean.expand_as(result), rtol=0, atol=0)
    (result*weight).sum().backward()
    expected_value_grad = (weight.sum(-2, keepdim=True)/4).expand_as(values)
    expected_logit_grad = .25*((values.detach()-mean).unsqueeze(-3)*weight.unsqueeze(-2)).sum(-1)
    torch.testing.assert_close(values.grad, expected_value_grad, rtol=0, atol=0)
    torch.testing.assert_close(logits.grad, expected_logit_grad, rtol=0, atol=0)
    assert bool((values.grad != 0).any()) and bool((logits.grad != 0).any())


def test_anchor_stays_in_autograd_when_finite_row_sum_is_not_one():
    # Deliberately nonnormalized algebra unit exposes a detached-anchor error.
    # Production always supplies its actual softmax, without renormalization.
    p = torch.tensor([[[[.25, .125], [.5, .25]]]], requires_grad=True)
    v = torch.tensor([[[[1., 2.], [5., 4.]]]], requires_grad=True)
    result = centered_attention_value(p, v, torch.ones(1, 2, dtype=torch.bool))
    torch.testing.assert_close(result, torch.tensor([[[[1.5, 2.25], [2., 2.5]]]]), rtol=0, atol=0)
    result.sum().backward()
    torch.testing.assert_close(v.grad, torch.tensor([[[[1.625, 1.625], [.375, .375]]]]), rtol=0, atol=0)
    torch.testing.assert_close(p.grad, torch.tensor([[[[0., 6.], [0., 6.]]]]), rtol=0, atol=0)


def test_first_valid_key_is_anchor_even_when_padded_key_zero_has_large_values():
    p = torch.tensor([[[[0., .25, .25]]*3]])
    v = torch.tensor([[[[99., -88.], [2., 4.], [6., -2.]]]])
    mask = torch.tensor([[False, True, True]])
    result = centered_attention_value(p, v, mask)
    torch.testing.assert_close(result, torch.tensor([3., 2.5]).expand_as(result), rtol=0, atol=0)


def test_nonzero_constant_values_have_zero_logit_gradient_and_nonzero_value_gradient():
    logits = torch.zeros(1, 1, 4, 4, requires_grad=True)
    v = torch.tensor([1.5, -2.]).expand(1, 1, 4, 2).clone().requires_grad_()
    result = centered_attention_value(logits.softmax(-1), v, torch.ones(1, 4, dtype=torch.bool))
    torch.testing.assert_close(result, v.detach(), rtol=0, atol=0)
    result.sum().backward()
    assert torch.equal(logits.grad, torch.zeros_like(logits))
    assert torch.equal(v.grad, torch.ones_like(v))


def test_representable_large_common_component_matches_exact_small_tensor_oracle():
    p = torch.full((1, 1, 4, 4), .25)
    v = (2**20+torch.tensor([0., .25, .5, .75])).reshape(1, 1, 4, 1)
    result = centered_attention_value(p, v, torch.ones(1, 4, dtype=torch.bool))
    assert torch.equal(result, torch.full_like(result, 2**20+.375))


@pytest.mark.parametrize("dtype", (torch.float16, torch.bfloat16, torch.float64))
@pytest.mark.parametrize("operand", ("p", "v"))
def test_helper_rejects_non_fp32_operand(dtype, operand):
    p, v, mask = operands()
    if operand == "p": p = p.to(dtype)
    else: v = v.to(dtype)
    with pytest.raises(ValueError, match="FP32"):
        centered_attention_value(p, v, mask)


@pytest.mark.parametrize("fault", ("empty_batch", "empty_nodes", "empty_heads", "empty_channels",
                                  "nonsquare", "value_shape", "mask_shape", "mask_dtype",
                                  "all_masked", "negative", "nan_p", "inf_v"))
def test_invalid_or_unsupported_population_is_rejected(fault):
    p, v, mask = operands()
    if fault == "empty_batch": p, v, mask = p[:0], v[:0], mask[:0]
    elif fault == "empty_nodes": p, v, mask = p[:, :, :0, :0], v[:, :, :0], mask[:, :0]
    elif fault == "empty_heads": p, v = p[:, :0], v[:, :0]
    elif fault == "empty_channels": v = v[..., :0]
    elif fault == "nonsquare": p = p[:, :, :3]
    elif fault == "value_shape": v = v[:, :, :3]
    elif fault == "mask_shape": mask = mask[:, :3]
    elif fault == "mask_dtype": mask = mask.int()
    elif fault == "all_masked": mask.zero_()
    elif fault == "negative": p[0, 0, 0, 0] = -.25
    elif fault == "nan_p": p[0, 0, 0, 0] = float("nan")
    elif fault == "inf_v": v[0, 0, 0, 0] = float("inf")
    with pytest.raises(ValueError): centered_attention_value(p, v, mask)


def test_helper_rejects_active_dropout_but_allows_eval_dropout():
    p, v, mask = operands()
    dropout = nn.Dropout(.25).train()
    with pytest.raises(ValueError, match="dropout"):
        centered_attention_value(p, v, mask, attention_dropout=dropout)
    dropout.eval()
    assert torch.equal(centered_attention_value(p, v, mask, attention_dropout=dropout),
                       centered_attention_value(p, v, mask))


@pytest.mark.parametrize("kind", ("dense", "pair"))
def test_real_attention_rejects_active_dropout_before_rng_consumption(kind):
    module = attention(kind, dropout=.25).train()
    x, mask = torch.ones(2, 4, 16), torch.ones(2, 4, dtype=torch.bool)
    rng = torch.get_rng_state().clone()
    with pytest.raises(ValueError, match="dropout"): call_attention(module, x, mask)
    assert torch.equal(torch.get_rng_state(), rng)
    module.eval()
    assert torch.isfinite(call_attention(module, x, mask)).all()


@pytest.mark.parametrize("kind", ("dense", "pair"))
def test_real_attention_rejects_all_masked_before_qkv(kind):
    module = attention(kind).eval()
    calls = []
    handle = module.qkv.register_forward_pre_hook(lambda *_: calls.append(True))
    try:
        with pytest.raises(ValueError, match="all-masked"):
            call_attention(module, torch.ones(2, 4, 16), torch.zeros(2, 4, dtype=torch.bool))
    finally: handle.remove()
    assert calls == []


def test_helper_and_real_attention_reject_autocast_even_with_fp32_inputs():
    p, v, mask = operands()
    module = attention().eval()
    with torch.autocast("cpu", dtype=torch.bfloat16):
        with pytest.raises(ValueError, match="autocast"): centered_attention_value(p, v, mask)
        with pytest.raises(ValueError, match="autocast"):
            call_attention(module, torch.ones(1, 4, 16), mask)


@pytest.mark.parametrize("kind", C1_KINDS)
def test_full_c1_keeps_all_layer_modes_parameters_state_keys_rng_and_meaningful_gradients(kind):
    torch.manual_seed(800)
    old = model(kind, LEGACY_AGGREGATION)
    old_rng = torch.get_rng_state().clone()
    torch.manual_seed(800)
    candidate = model(kind)
    assert torch.equal(torch.get_rng_state(), old_rng)
    assert set(old.state_dict()) == set(candidate.state_dict())
    for name, value in old.state_dict().items():
        if isinstance(value, torch.Tensor): assert torch.equal(value, candidate.state_dict()[name]), name
    assert candidate.attention_aggregation_mode == candidate.backbone.attention_aggregation_mode == CENTERED_FP32
    assert numeric_mode(candidate) == numeric_mode(candidate.backbone) == COMPENSATED
    assert all(layer.attn.attention_aggregation_mode == CENTERED_FP32 for layer in candidate.backbone.layers)
    expected_class = DenseGeoSelfAttention if kind == "C1-0" else SharedPairAttention
    assert all(type(layer.attn) is expected_class for layer in candidate.backbone.layers)
    if kind != "C1-0": assert numeric_mode(candidate.backbone.pair_encoder) == COMPENSATED
    result = candidate.encode_atoms(atoms())
    assert result.shape == (5, 16) and result.dtype == torch.float32 and torch.isfinite(result).all()
    (result*torch.linspace(-1., 2., result.numel()).reshape_as(result)).sum().backward()
    gradients = [candidate.backbone.atom_emb.weight.grad,
                 candidate.backbone.layers[0].attn.qkv.weight.grad,
                 candidate.backbone.layers[-1].attn.proj.weight.grad]
    assert all(value is not None and torch.isfinite(value).all() and bool((value != 0).any()) for value in gradients)


@pytest.mark.parametrize("kind", C1_KINDS)
def test_missing_and_explicit_legacy_keep_bitwise_forward_and_omit_default_config_insertion(kind):
    torch.manual_seed(151); absent = model(kind, None).eval()
    rng = torch.get_rng_state().clone()
    torch.manual_seed(151); explicit = model(kind, LEGACY_AGGREGATION).eval()
    assert torch.equal(torch.get_rng_state(), rng)
    assert "attention_aggregation_mode" not in absent.backbone_config
    assert explicit.backbone_config["attention_aggregation_mode"] == LEGACY_AGGREGATION
    with torch.no_grad(): assert torch.equal(absent.encode_atoms(atoms()), explicit.encode_atoms(atoms()))
    assert set(absent.state_dict()) == set(explicit.state_dict())
    for name, value in absent.state_dict().items():
        other = explicit.state_dict()[name]
        assert torch.equal(value, other) if isinstance(value, torch.Tensor) else value == other
    if kind != "C1-0": assert "attention_aggregation_mode" not in absent.backbone.get_extra_state()


@pytest.mark.parametrize("kind", C1_KINDS)
def test_checkpoint_full_config_binds_attention_mode_without_new_tensor_keys(kind):
    torch.manual_seed(44); candidate = model(kind)
    contract = numeric_checkpoint_contract(candidate)
    assert contract["model_config"]["backbone_config"]["attention_aggregation_mode"] == CENTERED_FP32
    other = model(kind)
    load_numeric_bound_state_dict(other, candidate.state_dict(), contract)
    legacy = model(kind, None)
    with pytest.raises(ValueError, match="configuration differs"):
        load_numeric_bound_state_dict(legacy, candidate.state_dict(), contract)
    with pytest.raises(ValueError, match="configuration differs"):
        load_numeric_bound_state_dict(candidate, legacy.state_dict(), numeric_checkpoint_contract(legacy))
    if kind != "C1-0":
        assert candidate.backbone.get_extra_state()["attention_aggregation_mode"] == CENTERED_FP32
        with pytest.raises(ValueError, match="checkpoint/options"):
            legacy.backbone.load_state_dict(candidate.backbone.state_dict())


@pytest.mark.parametrize("kind", C1_KINDS)
@pytest.mark.parametrize("entry", ("encode_atoms", "encode_graph", "backbone", "forward_pretrain"))
def test_empty_packed_data_rejected_explicitly_before_pyg_densification(kind, entry):
    candidate = model(kind)
    empty = Data(x=torch.empty(0, 1, dtype=torch.long), pos=torch.empty(0, 3),
                 batch=torch.empty(0, dtype=torch.long))
    with pytest.raises(ValueError, match="empty"):
        if entry == "forward_pretrain": candidate.forward_pretrain(empty, ())
        else: getattr(candidate, entry)(empty)


@pytest.mark.parametrize("kind", C1_KINDS)
@pytest.mark.parametrize("fault", ("positions_fp64", "parameters_fp64", "autocast"))
def test_full_backbone_rejects_unsupported_precision_before_packing(kind, fault):
    candidate, batch = model(kind), atoms()
    if fault == "positions_fp64": batch.pos = batch.pos.double()
    elif fault == "parameters_fp64": candidate.backbone.double()
    if fault == "autocast":
        with torch.autocast("cpu", dtype=torch.bfloat16), pytest.raises(ValueError, match="autocast"):
            candidate.encode_atoms(batch)
    else:
        with pytest.raises(ValueError, match="FP32"): candidate.encode_atoms(batch)


@pytest.mark.parametrize("precision", ("fp32", "bf16"))
def test_performance_builder_and_direct_runtime_constructor_cannot_silently_drop_mode(precision):
    rng = torch.get_rng_state().clone()
    with pytest.raises(ValueError, match="unsupported"):
        build_performance_model(configuration(), PerformanceOptions(precision=precision))
    assert torch.equal(torch.get_rng_state(), rng)
    with pytest.raises(ValueError, match="unsupported"):
        RuntimeDenseAttention(attention(), precision=precision)


@pytest.mark.parametrize("kind", C1_KINDS)
@pytest.mark.parametrize("entry", ("encode_atoms", "backbone"))
def test_replaced_runtime_backend_rejected_by_actual_class_guard(kind, entry):
    # This is the actual available RuntimeDense class, not an invented test of
    # an external NativeRuntimeDense constructor absent from this source base.
    candidate = model(kind)
    replacement = RuntimeDenseAttention(DenseGeoSelfAttention(16, 4))
    candidate.backbone.layers[0].attn = replacement
    called = []
    handle = replacement.register_forward_pre_hook(lambda *_: called.append(True))
    try:
        with pytest.raises(ValueError, match="replaced/NativeRuntimeDense/bf16"):
            getattr(candidate, entry)(atoms())
    finally: handle.remove()
    assert called == []


@pytest.mark.parametrize("value", ("unknown", "", None, 0, True))
def test_invalid_explicit_configuration_mode_rejected(value):
    bad = configuration()
    bad["backbone"]["attention_aggregation_mode"] = value
    with pytest.raises(ValueError, match="attention_aggregation_mode"):
        build_architecture_model(bad)


def test_helper_forward_backward_never_creates_fp64_or_changes_rng_or_backend_flags():
    from torch.utils._python_dispatch import TorchDispatchMode
    class ForbidFP64(TorchDispatchMode):
        def __torch_dispatch__(self, func, types, args=(), kwargs=None):
            output = func(*args, **(kwargs or {}))
            tensors = output if isinstance(output, (tuple, list)) else (output,)
            assert not any(isinstance(item, torch.Tensor) and item.dtype == torch.float64 for item in tensors)
            return output
    p, v, mask = operands()
    p.requires_grad_(); v.requires_grad_()
    before = (torch.are_deterministic_algorithms_enabled(), torch.get_float32_matmul_precision(),
              torch.backends.cuda.matmul.allow_tf32)
    rng = torch.get_rng_state().clone()
    with ForbidFP64(): centered_attention_value(p, v, mask).square().sum().backward()
    assert before == (torch.are_deterministic_algorithms_enabled(), torch.get_float32_matmul_precision(),
                      torch.backends.cuda.matmul.allow_tf32)
    assert torch.equal(torch.get_rng_state(), rng)
    assert p.grad is not None and v.grad is not None
