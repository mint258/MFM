"""Small analytic/unit controls; no48case scientific measurement or native data."""
from copy import deepcopy
import gzip
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import torch
from torch import nn

SPEC = importlib.util.spec_from_file_location('layer_head_diagnostic_source_v1', Path(__file__).with_name('instrument_layer_heads.py'))
source = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(source)
ROTATION = torch.tensor([[0., 1., 0.], [-1., 0., 0.], [0., 0., 1.]], dtype=torch.float64)


def test_scalar_cross_linear_oracle_separates_feature_and_coordinate_effects():
    y00 = torch.tensor([[2.], [4.]], dtype=torch.float32)
    y10 = torch.tensor([[5.], [3.]], dtype=torch.float32)
    result = source.four_way(y00, y10, y00, y10, ROTATION, 'invariant')
    assert result['H0_effect']['values'] == [[3.], [-1.]]
    assert result['coordinate_effect']['maxabs'] == result['interaction']['maxabs'] == 0
    assert result['bookkeeping_residual']['maxabs'] == 0


def test_nonzero_vector_cross_oracle_uses_row_R_and_separates_interaction():
    y00 = torch.tensor([[1., 2., 3.]], dtype=torch.float64)
    deltaH = torch.tensor([[.1, .2, -.3]], dtype=torch.float64)
    deltaP = torch.tensor([[.02, -.03, .04]], dtype=torch.float64)
    interaction = torch.tensor([[.005, .006, -.007]], dtype=torch.float64)
    y10 = y00+deltaH
    y01 = y00@ROTATION+deltaP
    y11 = y10@ROTATION+deltaP+interaction
    result = source.four_way(y00, y10, y01, y11, ROTATION, 'vector')
    assert torch.allclose(torch.tensor(result['H0_effect']['values'], dtype=torch.float64), deltaH@ROTATION, atol=1e-8, rtol=0)
    assert torch.allclose(torch.tensor(result['coordinate_effect']['values'], dtype=torch.float64), deltaP, atol=1e-8, rtol=0)
    assert torch.allclose(torch.tensor(result['interaction']['values'], dtype=torch.float64), interaction, atol=1e-8, rtol=0)
    assert torch.allclose(torch.tensor(result['total']['values'], dtype=torch.float64),
        deltaH@ROTATION+deltaP+interaction, atol=1e-8, rtol=0)
    assert float((y11-y00@ROTATION.T).abs().max()) > .1  # Wrong row-vector law is discriminated.
    assert result['bookkeeping_residual']['maxabs'] < 1e-15


def test_shadow_MLP_matches_independent_dense_formula_and_preserves_weights():
    layer = nn.Sequential(nn.Linear(2, 3), nn.SiLU(), nn.Linear(3, 1)).float()
    with torch.no_grad():
        layer[0].weight.copy_(torch.tensor([[1., 2.], [-1., .5], [2., -.25]]))
        layer[0].bias.copy_(torch.tensor([.1, -.2, .3]))
        layer[2].weight.copy_(torch.tensor([[.4, -.6, .2]]))
        layer[2].bias.copy_(torch.tensor([.7]))
    before = {key: value.clone() for key, value in layer.state_dict().items()}
    x = torch.tensor([[1., -.5], [.2, .3]], dtype=torch.float64)
    z = x@before['0.weight'].double().T+before['0.bias'].double()
    expected = (z*torch.sigmoid(z))@before['2.weight'].double().T+before['2.bias'].double()
    actual = source.shadow_mlp(layer, x)
    assert torch.allclose(actual, expected, atol=1e-15, rtol=0)
    assert all(torch.equal(value, before[key]) for key, value in layer.state_dict().items())
    assert all(parameter.dtype == torch.float32 for parameter in layer.parameters())


@pytest.mark.parametrize('module,input_dtype', [(nn.ReLU(), torch.float64), (nn.Linear(2, 1), torch.float32)])
def test_unknown_shadow_module_or_wrong_reference_dtype_rejects(module, input_dtype):
    with pytest.raises(ValueError):
        source.shadow_mlp(module, torch.ones(2, 2, dtype=input_dtype))


def test_FP64_pool_reference_preserves_extensive_and_mean_denominators():
    x = torch.tensor([[1., 2.], [3., 4.], [-5., 6.]], dtype=torch.float64)
    batch = torch.tensor([0, 0, 1])
    assert torch.equal(source.pool64(x, batch, 2, 'sum'), torch.tensor([[4., 6.], [-5., 6.]], dtype=torch.float64))
    assert torch.equal(source.pool64(x, batch, 2, 'mean'), torch.tensor([[2., 3.], [-5., 6.]], dtype=torch.float64))


def test_readonly_hook_preserves_output_and_is_removed():
    layer = nn.Linear(3, 4).float()
    x = torch.tensor([[.2, .3, -.1], [.4, -.5, .6]])
    before = layer(x).detach()
    capture = source.ReadOnlyCapture()
    capture.phase = 0
    capture.watch('linear', layer)
    during = layer(x)
    assert torch.equal(before, during) and torch.equal(capture.values['linear'][0][0], before)
    capture.close()
    assert not capture.handles and not layer._forward_hooks


def test_trace_argmax_locates_planted_layer_drift_and_is_JSON_serializable():
    expected = torch.ones(3, 4, dtype=torch.float32)
    actual = expected.clone()
    actual[2, 1] += .125
    result = source.compare(actual, expected)
    assert result['argmax'] == [2, 1] and result['signed_error_at_argmax'] == .125
    json.dumps(result, allow_nan=False)


def terminal_archives(tmp_path, *, change=False, bad_dtype=False):
    first, second = tmp_path/'fresh_control.npz', tmp_path/'fresh_hooked.npz'
    data = {str(i): np.array([[i+.5, i+1.25]], dtype=np.float32) for i in range(52)}
    np.savez_compressed(first, **data)
    if change:
        data['13'] = data['13'].copy()
        data['13'][0, 0] = np.nextafter(data['13'][0, 0], np.float32(np.inf))
    if bad_dtype:
        data['13'] = data['13'].astype(np.float64)
    np.savez_compressed(second, **data)
    return first, second


def test_full52_terminal_archive_control_passes(tmp_path):
    result = source.ensure_terminal_equality(*terminal_archives(tmp_path))
    assert result['archive_arrays'] == 52 and result['all_original_and_three_transformed_terminals_bitwise_equal']


@pytest.mark.parametrize('bad_dtype', [False, True])
def test_any_terminal_change_even_one_ULP_or_wrong_dtype_is_hard_failure(tmp_path, bad_dtype):
    with pytest.raises(ValueError):
        source.ensure_terminal_equality(*terminal_archives(tmp_path, change=not bad_dtype, bad_dtype=bad_dtype))


@pytest.mark.parametrize('mutation', ['missing', 'duplicate', 'reordered'])
def test_complete48_membership_rejects_incomplete_or_adaptive_case_selection(mutation):
    expected = ['case_'+str(i) for i in range(48)]
    changed = expected.copy()
    if mutation == 'missing': changed.pop()
    elif mutation == 'duplicate': changed[-1] = changed[0]
    else: changed[0], changed[1] = changed[1], changed[0]
    with pytest.raises(ValueError): source.complete_membership(changed, expected)
    source.complete_membership(expected, expected)


def test_gzip_trace_roundtrip_is_bounded_and_never_overwrites(tmp_path):
    path = tmp_path/'TRACE.json.gz'
    value = {'signed_effects': [-1.5, 2.75], 'analysis_only': True}
    result = source.save_trace(path, value)
    assert json.loads(gzip.decompress(path.read_bytes())) == value
    assert result['sha256'] == source.sha(path.read_bytes())
    with pytest.raises(ValueError): source.save_trace(path, value)


def test_trace_budget_overflow_is_explicit_not_silently_truncated(tmp_path):
    noise = np.random.default_rng(41).bytes(600*1024).hex()
    with pytest.raises(ValueError, match='512KiB'):
        source.save_trace(tmp_path/'too_large.json.gz', {'random_hex': noise})
    assert not (tmp_path/'too_large.json.gz').exists()


def test_scoped_capture_restores_factory_pool_and_hooks_after_failure(monkeypatch):
    sentinel = nn.Linear(1, 1)
    attached = []
    class TinyTrace:
        def __init__(self, model, registry):
            self.phase = 0
            self.handle = sentinel.register_forward_hook(lambda *args: None)
            attached.append(self)
        def close(self):
            self.handle.remove()
        def record(self, name, value):
            pass
    monkeypatch.setattr(source, 'CompositionTrace', TinyTrace)
    def original_builder(spec): return object(), object()
    calls = []
    def original_pool(h, batch, graphs, mode):
        calls.append((h, mode))
        return h+3
    equation, heads = SimpleNamespace(build_composition=original_builder), SimpleNamespace(_pool=original_pool)
    x = torch.tensor([[1.]])
    with pytest.raises(RuntimeError):
        with source.capture_composition(equation, heads):
            equation.build_composition(None)
            assert torch.equal(heads._pool(x, None, 1, 'sum'), x+3)
            raise RuntimeError('planted instrumentation failure')
    assert equation.build_composition is original_builder and heads._pool is original_pool
    assert not sentinel._forward_hooks and len(calls) == 1


def test_missing_encoder_phase_is_rejected():
    trace = object.__new__(source.CompositionTrace)
    trace.phase, trace.bank_inputs, trace.bank_outputs, trace.values = 2, {}, {}, {}
    with pytest.raises(ValueError): trace.complete()


def test_synthetic_real_source_dipole_and_magnitude_have_independent_charge_parameters():
    equation, heads = source.legacy().import_equation(source.B/'MFM_model_v3_composed_equivariance')
    vector = heads._DipoleHead(2, 2, False).float()
    magnitude = heads._DipoleHead(2, 2, True).float()
    with torch.no_grad():
        for module in (vector, magnitude):
            module.charges[0].weight.copy_(torch.eye(2)); module.charges[0].bias.zero_()
            module.charges[2].bias.zero_()
        vector.charges[2].weight.copy_(torch.tensor([[1., 0.]]))
        magnitude.charges[2].weight.copy_(torch.tensor([[0., 2.]]))
    h = torch.tensor([[1., -.2], [.3, .7], [-.5, 1.1]])
    pos = torch.tensor([[.1, .2, 0.], [1.3, -.2, .3], [-.4, .8, -.1]])
    batch = torch.tensor([0, 0, 0])
    v, pv = source.fp32_dipole_parts(vector, h, pos, batch, heads._pool)
    m, pm = source.fp32_dipole_parts(magnitude, h, pos, batch, heads._pool)
    assert torch.equal(v, vector(h, pos, batch, 1)) and torch.equal(m, magnitude(h, pos, batch, 1))
    assert not torch.allclose(m, v.norm(dim=-1, keepdim=True), atol=1e-5, rtol=0)
    assert not torch.equal(pv['charges'], pm['charges'])

@pytest.mark.parametrize('form,pooling', [('H1', 'sum'), ('H2', 'mean'), ('H3', 'learned')])
def test_functional_graph_shadow_matches_dense_manual_oracle(form, pooling):
    field = SimpleNamespace(name='scalar', group='P', level='graph', representation='scalar', pooling=pooling)
    linear = nn.Linear(2, 1).float()
    projector = nn.Sequential(nn.Linear(2, 2), nn.SiLU()).float()
    nonlinear = nn.Sequential(nn.Linear(2, 2), nn.SiLU(), nn.Linear(2, 1)).float()
    with torch.no_grad():
        for layer in (linear, nonlinear[2]):
            layer.weight.copy_(torch.tensor([[.75, -.5]])); layer.bias.copy_(torch.tensor([.2]))
        for layer in (projector[0], nonlinear[0]):
            layer.weight.copy_(torch.tensor([[1., .3], [-.2, .7]])); layer.bias.copy_(torch.tensor([.1, -.3]))
    mixer = SimpleNamespace(logits=torch.tensor([-.7, .4]))
    bank = SimpleNamespace(keys={'scalar': 'key'}, field_heads={'key': nonlinear if form == 'H3' else linear},
        pooling_mixers={'key': mixer}, forms={'scalar': form}, group_projectors={'P': projector})
    h = torch.tensor([[1., -.2], [.3, .7], [-.5, 1.1]])
    batch = torch.tensor([0, 0, 1])
    pos = torch.zeros(3, 3)
    summed = torch.stack((h[:2].double().sum(0), h[2].double()))
    mean = torch.stack((h[:2].double().mean(0), h[2].double()))
    if pooling == 'learned':
        probability = mixer.logits.double().exp(); probability = probability/probability.sum()
        pooled = probability[0]*summed+probability[1]*mean
    else:
        pooled = summed if pooling == 'sum' else mean
    feature = pooled
    if form != 'H1':
        first = projector[0] if form == 'H2' else nonlinear[0]
        z = feature@first.weight.detach().double().T+first.bias.detach().double()
        feature = z*torch.sigmoid(z)
    expected = feature@linear.weight.detach().double().T+linear.bias.detach().double()
    actual, details = source.shadow_head(bank, field, h, pos, batch)
    assert actual.dtype == torch.float64 and torch.allclose(actual, expected, atol=1e-14, rtol=0)
    assert torch.allclose(details['pool'], pooled, atol=1e-14, rtol=0)


def test_functional_dipole_shadow_matches_same_parameters_direct64_geometry():
    unused, heads = source.legacy().import_equation(source.B/'MFM_model_v3_composed_equivariance')
    head = heads._DipoleHead(2, 2, True).float()
    with torch.no_grad():
        head.charges[0].weight.copy_(torch.eye(2)); head.charges[0].bias.zero_()
        head.charges[2].weight.copy_(torch.tensor([[.7, -.4]])); head.charges[2].bias.zero_()
    field = SimpleNamespace(name='magnitude', representation='magnitude')
    bank = SimpleNamespace(keys={'magnitude': 'key'}, field_heads={'key': head})
    h = torch.tensor([[1., -.2], [.3, .7], [-.5, 1.1]])
    pos = torch.tensor([[.1, .2, 0.], [1.3, -.2, .3], [-.4, .8, -.1]])
    batch = torch.tensor([0, 0, 0])
    q = ((h.double()*torch.sigmoid(h.double()))*torch.tensor([.7, -.4]).double()).sum(-1, keepdim=True)
    centered = pos.double()-pos.double().mean(0)
    vector = (q*centered).sum(0, keepdim=True)
    actual, details = source.shadow_head(bank, field, h, pos, batch)
    assert torch.allclose(details['vector'], vector, atol=1e-14, rtol=0)
    assert torch.allclose(actual, vector.norm(dim=-1, keepdim=True), atol=1e-14, rtol=0)


def test_JSON_FP64_roundtrip_does_not_quantize_through_default_FP32():
    values = [[-.3, 1.0000000000000002, 2.**-40]]
    decoded = json.loads(json.dumps({'values': values}))['values']
    expected = torch.tensor(values, dtype=torch.float64)
    restored = torch.tensor(decoded, dtype=torch.float64)
    lossy = torch.tensor(decoded, dtype=torch.float32).double()
    assert torch.equal(restored, expected)
    assert not torch.equal(lossy, expected)
    assert float((restored-expected).abs().max()) == 0.
    assert float((lossy-expected).abs().max()) > 1e-8
