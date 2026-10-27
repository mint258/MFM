"""Source-only diagnostic QA; no claim of the formal all-FP32 C4 gate."""
import math
import pytest
import torch
from torch import nn

from phychem_mfm.model.attention import DenseGeoSelfAttention
from phychem_mfm.model.v3_architecture import SharedPairAttention
from phychem_mfm.model.v3_attention_numerics import (
    LEGACY_AGGREGATION, CENTERED_FP32, CORE64_DIAGNOSTIC,
    diagnostic_core64_logits, diagnostic_core64_value,
)
from phychem_mfm.model.v3_numeric_stability import (
    COMPENSATED, numeric_mode, numeric_checkpoint_contract, load_numeric_bound_state_dict,
)
from phychem_mfm.model.v3_performance import (
    PerformanceOptions, RuntimeDenseAttention, build_performance_model,
)
from test_model_v3_attention_centering import configuration, model, atoms, call_attention

KINDS = ("C1-0", "C1-a", "C1-b")


def operands():
    return (torch.full((1, 1, 4, 4), .25, dtype=torch.float64),
            torch.tensor([[[[1., 2.], [3., 0.], [-1., 2.], [5., 4.]]]]),
            torch.ones(1, 4, dtype=torch.bool))


def attention(kind):
    original = DenseGeoSelfAttention(16, 4, attention_aggregation_mode=CORE64_DIAGNOSTIC)
    return (original if kind == "dense" else SharedPairAttention(original, 8)).eval()


def test_qk_and_backward_match_hand_computed_two_dimensional_oracle():
    q = torch.tensor([[[[1., 2.], [-1., 0.]]]], requires_grad=True)
    k = torch.tensor([[[[2., -1.], [1., 3.]]]], requires_grad=True)
    actual = diagnostic_core64_logits(q, k)
    expected = torch.tensor([[[[0., 7.], [-2., -1.]]]], dtype=torch.float64)/math.sqrt(2)
    torch.testing.assert_close(actual, expected, rtol=0, atol=0)
    assert actual.dtype == torch.float64
    actual.sum().backward()
    qgrad = (torch.tensor([3., 2.], dtype=torch.float64)/math.sqrt(2)).float()
    kgrad = (torch.tensor([0., 2.], dtype=torch.float64)/math.sqrt(2)).float()
    assert torch.equal(q.grad, qgrad.expand_as(q))
    assert torch.equal(k.grad, kgrad.expand_as(k))


def test_true_softmax_value_and_logit_gradients_match_nonzero_dyadic_oracle():
    logits = torch.zeros(1, 1, 4, 4, dtype=torch.float64, requires_grad=True)
    _, values, mask = operands()
    values.requires_grad_()
    result = diagnostic_core64_value(logits.softmax(-1), values, mask)
    assert result.dtype == torch.float32
    assert torch.equal(result, torch.full_like(result, 2.))
    (result[0, 0, 0]*torch.tensor([1., -2.])).sum().backward()
    expected_logits = torch.zeros_like(logits)
    expected_logits[0, 0, 0] = torch.tensor([-.25, 1.25, -.75, -.25], dtype=torch.float64)
    assert torch.equal(logits.grad, expected_logits)
    assert torch.equal(values.grad, torch.tensor([.25, -.5]).expand_as(values))
    assert bool(logits.grad.abs().sum() > 0) and bool(values.grad.abs().sum() > 0)


def test_first_valid_anchor_is_not_detached_in_nonunit_mass_algebra_control():
    # A primitive-only algebra control, not a different production softmax.
    # Its nonunit mass makes a detached anchor give the wrong V gradient.
    p = torch.tensor([[[[0., .125, .125, .125]]*4]], dtype=torch.float64, requires_grad=True)
    v = torch.tensor([[[[99.], [2.], [4.], [6.]]]], requires_grad=True)
    mask = torch.tensor([[False, True, True, True]])
    result = diagnostic_core64_value(p, v, mask)
    assert torch.equal(result, torch.full_like(result, 2.75))
    result[0, 0, 0, 0].backward()
    assert torch.equal(v.grad, torch.tensor([[[[0.], [.75], [.125], [.125]]]]))
    expected_p = torch.zeros_like(p)
    expected_p[0, 0, 0] = torch.tensor([97., 0., 2., 4.], dtype=torch.float64)
    assert torch.equal(p.grad, expected_p)


def test_nonzero_constant_values_have_exact_zero_logit_and_nonzero_value_gradients():
    logits = torch.zeros(1, 1, 4, 4, dtype=torch.float64, requires_grad=True)
    v = torch.tensor([1.5, -2.]).expand(1, 1, 4, 2).clone().requires_grad_()
    result = diagnostic_core64_value(logits.softmax(-1), v, torch.ones(1, 4, dtype=torch.bool))
    assert torch.equal(result, v.detach())
    result.sum().backward()
    assert torch.equal(logits.grad, torch.zeros_like(logits))
    assert torch.equal(v.grad, torch.ones_like(v))


@pytest.mark.parametrize("kind", ("dense", "shared"))
def test_real_module_keeps_external_f32_and_executes_only_core_matmuls_in_f64(kind, monkeypatch):
    module = attention(kind)
    x = torch.linspace(-.7, .9, 48).reshape(1, 3, 16).requires_grad_()
    mask = torch.tensor([[False, True, True]])
    matmul, softmax = torch.matmul, torch.softmax
    seen_matmuls, seen_softmax, seen_linear = [], [], []
    def traced_matmul(left, right, *args, **kwargs):
        if left.ndim == right.ndim == 4:
            seen_matmuls.append((left.dtype, right.dtype))
        return matmul(left, right, *args, **kwargs)
    def traced_softmax(value, *args, **kwargs):
        result = softmax(value, *args, **kwargs)
        seen_softmax.append((value.dtype, result.dtype))
        return result
    monkeypatch.setattr(torch, "matmul", traced_matmul)
    monkeypatch.setattr(torch, "softmax", traced_softmax)
    handles = []
    for name in ("qkv", "proj", "pair_projection" if kind == "shared" else "dist_mlp"):
        child = getattr(module, name)
        handles.append(child.register_forward_hook(
            lambda _, args, out, name=name: seen_linear.append((name, args[0].dtype, out.dtype))))
    state = {name: value.detach().clone() for name, value in module.named_parameters()}
    rng = torch.get_rng_state().clone()
    flags = (torch.are_deterministic_algorithms_enabled(), torch.get_float32_matmul_precision(),
             torch.backends.cuda.matmul.allow_tf32)
    try:
        out = call_attention(module, x, mask)
        assert out.dtype == torch.float32 and bool(torch.isfinite(out).all())
        out.square().sum().backward()
    finally:
        for handle in handles: handle.remove()
    assert seen_matmuls == [(torch.float64, torch.float64)]*2
    assert seen_softmax == [(torch.float64, torch.float64)]
    assert {row[0] for row in seen_linear} == {"qkv", "proj", "pair_projection" if kind == "shared" else "dist_mlp"}
    assert all(a == b == torch.float32 for _, a, b in seen_linear)
    assert x.grad is not None and x.grad.dtype == torch.float32 and bool(x.grad.abs().sum() > 0)
    assert torch.equal(rng, torch.get_rng_state())
    assert flags == (torch.are_deterministic_algorithms_enabled(), torch.get_float32_matmul_precision(),
                     torch.backends.cuda.matmul.allow_tf32)
    for name, value in module.named_parameters():
        assert value.dtype == torch.float32 and torch.equal(value, state[name])
        if value.grad is not None: assert value.grad.dtype == torch.float32 and torch.isfinite(value.grad).all()
    if kind == "dense":
        pos = torch.arange(9, dtype=torch.float32).reshape(1, 3, 3)/8
        with torch.no_grad(): _, public_weights = module(x, pos, mask)
        assert public_weights.dtype == torch.float32


@pytest.mark.parametrize("dtype", (torch.bfloat16, torch.float64))
def test_qk_rejects_non_f32_external_operands(dtype):
    q = torch.ones(1, 1, 2, 2)
    with pytest.raises(ValueError, match="FP32"):
        diagnostic_core64_logits(q.to(dtype), q)


@pytest.mark.parametrize("fault", ("p32", "v64", "v_bf16", "all_masked", "empty",
                                  "mask_type", "negative", "nan", "infinite_v", "nonsquare"))
def test_value_primitive_rejects_unsupported_or_nonfinite_inputs_without_rng(fault):
    p, v, mask = operands()
    if fault == "p32": p = p.float()
    elif fault == "v64": v = v.double()
    elif fault == "v_bf16": v = v.bfloat16()
    elif fault == "all_masked": mask.zero_()
    elif fault == "empty": p, v, mask = p[:0], v[:0], mask[:0]
    elif fault == "mask_type": mask = mask.long()
    elif fault == "negative": p[0, 0, 0, 0] = -.25
    elif fault == "nan": p[0, 0, 0, 0] = float("nan")
    elif fault == "infinite_v": v[0, 0, 0, 0] = float("inf")
    else: p = p[:, :, :3]
    rng = torch.get_rng_state().clone()
    with pytest.raises(ValueError): diagnostic_core64_value(p, v, mask)
    assert torch.equal(rng, torch.get_rng_state())


@pytest.mark.parametrize("kind", ("dense", "shared"))
def test_module_refuses_training_active_dropout_and_autocast_before_qkv(kind):
    module = attention(kind)
    x = torch.ones(1, 3, 16); mask = torch.ones(1, 3, dtype=torch.bool)
    calls = []
    handle = module.qkv.register_forward_pre_hook(lambda *_: calls.append(True))
    rng = torch.get_rng_state().clone()
    try:
        module.train()
        with pytest.raises(ValueError, match="diagnostic"): call_attention(module, x, mask)
        module.eval()
        module.attn_drop = nn.Dropout(.2).train()
        with pytest.raises(ValueError, match="dropout"): call_attention(module, x, mask)
        module.attn_drop = nn.Identity()
        with torch.autocast("cpu", dtype=torch.bfloat16), pytest.raises(ValueError, match="autocast"):
            call_attention(module, x, mask)
    finally: handle.remove()
    assert calls == [] and torch.equal(rng, torch.get_rng_state())


@pytest.mark.parametrize("kind", KINDS)
def test_six_layer_model_preserves_tensor_identity_rng_config_and_checkpoint_binding(kind):
    with torch.random.fork_rng(devices=[]):
        torch.random.default_generator.manual_seed(771)
        diagnostic = model(kind, CORE64_DIAGNOSTIC).eval()
        rng = torch.get_rng_state().clone()
        torch.random.default_generator.manual_seed(771)
        base = model(kind, CENTERED_FP32).eval()
        assert torch.equal(rng, torch.get_rng_state())
    assert len(diagnostic.backbone.layers) == 6
    assert all(layer.attn.attention_aggregation_mode == CORE64_DIAGNOSTIC for layer in diagnostic.backbone.layers)
    assert numeric_mode(diagnostic) == numeric_mode(base) == COMPENSATED
    left, right = diagnostic.state_dict(), base.state_dict()
    assert set(left) == set(right)
    for key, value in left.items():
        if isinstance(value, torch.Tensor):
            assert torch.equal(value, right[key]) and value.dtype == right[key].dtype
            if value.is_floating_point(): assert value.dtype == torch.float32
    result = diagnostic.encode_atoms(atoms())
    assert result.shape == (5, 16) and result.dtype == torch.float32 and torch.isfinite(result).all()
    (result*torch.linspace(-1., 2., result.numel()).reshape_as(result)).sum().backward()
    assert diagnostic.backbone.layers[0].attn.qkv.weight.grad.dtype == torch.float32
    assert bool(diagnostic.backbone.layers[0].attn.qkv.weight.grad.abs().sum() > 0)
    contract = numeric_checkpoint_contract(diagnostic)
    assert contract["model_config"]["backbone_config"]["attention_aggregation_mode"] == CORE64_DIAGNOSTIC
    copy = model(kind, CORE64_DIAGNOSTIC).eval()
    load_numeric_bound_state_dict(copy, diagnostic.state_dict(), contract)
    with pytest.raises(ValueError, match="configuration differs"):
        load_numeric_bound_state_dict(base, diagnostic.state_dict(), contract)
    if kind != "C1-0":
        assert diagnostic.backbone.get_extra_state()["attention_aggregation_mode"] == CORE64_DIAGNOSTIC
        with pytest.raises(ValueError, match="checkpoint/options"):
            base.backbone.load_state_dict(diagnostic.backbone.state_dict())


@pytest.mark.parametrize("kind", KINDS)
def test_whole_model_training_even_with_eval_backbone_and_mixed_layers_refuse(kind):
    candidate = model(kind, CORE64_DIAGNOSTIC)
    candidate.backbone.eval()
    with pytest.raises(ValueError, match="diagnostic"): candidate.encode_atoms(atoms())
    candidate.eval()
    candidate.backbone.layers[0].attn.attention_aggregation_mode = CENTERED_FP32
    with pytest.raises(ValueError, match="unsupported"): candidate.encode_atoms(atoms())


@pytest.mark.parametrize("fault", ("not_six", "empty", "f64_pos", "f64_parameters", "replaced"))
def test_whole_backbone_refuses_invalid_scope_before_execution(fault):
    candidate = model("C1-0", CORE64_DIAGNOSTIC).eval(); batch = atoms()
    if fault == "not_six": candidate.backbone.layers = nn.ModuleList(list(candidate.backbone.layers)[:5])
    elif fault == "empty":
        batch = batch.__class__(x=torch.empty(0, 1, dtype=torch.long), pos=torch.empty(0, 3),
                                batch=torch.empty(0, dtype=torch.long))
    elif fault == "f64_pos": batch.pos = batch.pos.double()
    elif fault == "f64_parameters": candidate.backbone.double()
    else: candidate.backbone.layers[0].attn = RuntimeDenseAttention(DenseGeoSelfAttention(16, 4))
    rng = torch.get_rng_state().clone()
    with pytest.raises(ValueError): candidate.encode_atoms(batch)
    assert torch.equal(rng, torch.get_rng_state())


@pytest.mark.parametrize("precision", ("fp32", "bf16"))
def test_performance_backend_cannot_silently_accept_diagnostic_mode(precision):
    original = attention("dense")
    rng = torch.get_rng_state().clone()
    with pytest.raises(ValueError, match="unsupported"):
        build_performance_model(configuration(CORE64_DIAGNOSTIC), PerformanceOptions(precision=precision))
    with pytest.raises(ValueError, match="unsupported"):
        RuntimeDenseAttention(original, precision=precision)
    assert torch.equal(rng, torch.get_rng_state())


@pytest.mark.parametrize("mode", (None, LEGACY_AGGREGATION, CENTERED_FP32))
def test_old_modes_do_not_enter_diagnostic_helpers_or_create_f64(mode, monkeypatch):
    from torch.utils._python_dispatch import TorchDispatchMode
    import phychem_mfm.model.attention as implementation
    def forbidden(*_, **__): raise AssertionError("Old mode entered diagnostic helper")
    monkeypatch.setattr(implementation, "diagnostic_core64_logits", forbidden)
    monkeypatch.setattr(implementation, "diagnostic_core64_value", forbidden)
    class NoFP64(TorchDispatchMode):
        def __torch_dispatch__(self, func, types, args=(), kwargs=None):
            result = func(*args, **(kwargs or {}))
            leaves = result if isinstance(result, (tuple, list)) else (result,)
            assert not any(isinstance(value, torch.Tensor) and value.dtype == torch.float64 for value in leaves)
            return result
    with torch.random.fork_rng(devices=[]):
        torch.random.default_generator.manual_seed(92); first = model("C1-0", mode).eval()
        torch.random.default_generator.manual_seed(92); second = model("C1-0", mode).eval()
    with NoFP64():
        result = first.encode_atoms(atoms())
        assert torch.equal(result, second.encode_atoms(atoms()))
    assert ("attention_aggregation_mode" in first.backbone_config) is (mode is not None)
