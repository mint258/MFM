"""Mathematical and compatibility tests; no scientific matrix/real data here."""
from copy import deepcopy

import pytest
import torch
from torch_geometric.data import Batch, Data

from phychem_mfm.config import numeric_stability_configuration
from phychem_mfm.factory import build_model
from phychem_mfm.model.attention import DenseGeoSelfAttention
from phychem_mfm.model.heads import EquivariantDenoisingHead, UnifiedGraphPooling
from phychem_mfm.model.v3_architecture import ArchitectureOptions, build_architecture_model
from phychem_mfm.model.v3_heads import V3HeadBank, _DipoleHead
from phychem_mfm.model.v3_numeric_stability import (
    LEGACY, COMPENSATED, apply_numeric_mode, numeric_mode, compensated_index_add,
    compensated_pool, compensated_norm3, compensated_squared_norm3,
    compensated_pairwise_norm3, numeric_checkpoint_contract, load_numeric_bound_state_dict,
)
from phychem_mfm.phase1.v3_contract import FieldSpec, LabelRegistry


def config(mode=None):
    value = {"architecture": {"preset": "shared_light"},
        "backbone": {"n_atom_types": 119, "dim": 16, "layers": 2, "heads": 4,
                     "ff_mult": 2, "use_radius_mask": False, "radius": 8.0},
        "head": {"profile": "phase1", "geometry_head": "equivariant_noise",
                 "geometry_hidden_dim": 8, "geometry_rbf_count": 8}}
    if mode is not None:
        value["numeric_stability"] = {"mode": mode}
    return value


def atoms():
    return Batch.from_data_list([
        Data(x=torch.tensor([[5], [7], [0]]), pos=torch.tensor([[0., 0., 0.], [1.1, .2, 0.], [.2, .8, .3]])),
        Data(x=torch.tensor([[5], [8]]), pos=torch.tensor([[.1, .2, .3], [1.8, .3, .1]]))])


def registry(pooling="sum"):
    return LabelRegistry((FieldSpec("g", "P", "synthetic", "graph", pooling=pooling),
                          FieldSpec("v", "P", "synthetic", "graph", representation="vector"),
                          FieldSpec("m", "P", "synthetic", "graph", representation="magnitude"),
                          FieldSpec("a", "P", "synthetic", "atom", representation="vector"),
                          FieldSpec("p", "P", "synthetic", "pair")), "numeric_test", "1"*64)


@pytest.mark.parametrize("width", (1, 3, 17, 512))
def test_csr_unordered_indices_zero_segments_match_high_precision_oracle(width):
    generator = torch.Generator().manual_seed(1209)
    source = torch.randn(37, width, generator=generator)
    index = torch.tensor([4, 1, 4, 0, 1, 0, 4]*5 + [1, 4])
    base = torch.randn(7, width, generator=generator)
    result = compensated_index_add(base, index, source)
    oracle = base.double().index_add(0, index, source.double()).float()
    assert result.dtype == torch.float32
    torch.testing.assert_close(result, oracle, rtol=0, atol=2e-6)
    assert torch.equal(result[[2, 3, 5, 6]], base[[2, 3, 5, 6]])
    assert torch.equal(result, compensated_index_add(base, index, source))


@pytest.mark.parametrize("values", ((1e8, 1., -1e8), (-1e8, 1., 1e8), (1e8, 1., 1., -1e8)))
def test_cancellation_recovers_small_terms_without_discarding_rows(values):
    source = torch.tensor(values)[:, None]
    result = compensated_index_add(torch.zeros(1, 1), torch.zeros(len(source), dtype=torch.long), source)
    assert torch.equal(result, source.double().sum(0, keepdim=True).float())


def test_base_is_part_of_compensation_and_empty_input_has_exact_linear_gradient():
    base = torch.tensor([[1e8], [7.]], requires_grad=True)
    source = torch.tensor([[-1e8], [3.]], requires_grad=True)
    result = compensated_index_add(base, torch.zeros(2, dtype=torch.long), source)
    assert torch.equal(result, torch.tensor([[3.], [7.]]))
    result.sum().backward()
    assert torch.equal(base.grad, torch.ones_like(base))
    assert torch.equal(source.grad, torch.ones_like(source))
    empty = source.detach()[:0].requires_grad_()
    original = base.detach().requires_grad_()
    output = compensated_index_add(original, torch.empty(0, dtype=torch.long), empty)
    assert torch.equal(output, original) and output.data_ptr() != original.data_ptr()
    output.sum().backward()
    assert empty.grad.shape == (0, 1) and torch.equal(original.grad, torch.ones_like(original))


def test_custom_backward_is_exact_gather_including_unordered_duplicates_and_second_derivative():
    base = torch.randn(5, 4, requires_grad=True)
    source = torch.randn(9, 4, requires_grad=True)
    index = torch.tensor([4, 1, 4, 1, 0, 4, 0, 1, 4])
    upstream = torch.arange(20, dtype=torch.float32).reshape(5, 4).requires_grad_()
    result = compensated_index_add(base, index, source)
    db, ds = torch.autograd.grad(result, (base, source), upstream, create_graph=True)
    assert torch.equal(db, upstream) and torch.equal(ds, upstream[index])
    second = torch.autograd.grad(ds.sum(), upstream)[0]
    expected = torch.bincount(index, minlength=5).float()[:, None].expand(5, 4)
    assert torch.equal(second, expected)


@pytest.mark.parametrize("fault", ("negative", "outside", "dtype", "shape", "fp64"))
def test_invalid_segment_inputs_fail_instead_of_dropping_rows(fault):
    base, source, index = torch.zeros(2, 3), torch.ones(2, 3), torch.tensor([0, 1])
    if fault == "negative": index[0] = -1
    elif fault == "outside": index[1] = 2
    elif fault == "dtype": index = index.int()
    elif fault == "shape": source = source[:, :2]
    else: source = source.double()
    with pytest.raises(ValueError): compensated_index_add(base, index, source)


def test_pool_denominator_includes_all_rows_and_empty_segments_are_zero():
    h = torch.tensor([[1e8, 2.], [1., 4.], [-1e8, 6.]])
    batch = torch.zeros(3, dtype=torch.long)
    total = compensated_pool(h, batch, 3, "sum")
    mean = compensated_pool(h, batch, 3, "mean")
    assert torch.equal(total, torch.tensor([[1., 12.], [0., 0.], [0., 0.]]))
    assert torch.equal(mean, total / torch.tensor([[3.], [1.], [1.]]))


def test_squared_norm_compensates_three_positive_terms_and_has_mathematical_gradient():
    value = torch.tensor([[4096., 1., 1.], [0., 0., 0.], [-3., 4., 12.]], requires_grad=True)
    result = compensated_squared_norm3(value)
    assert torch.equal(result, value.detach().double().square().sum(-1).float())
    result.sum().backward()
    assert torch.equal(value.grad, 2*value.detach())


def test_norm_zero_has_finite_zero_derivative_and_nonzero_has_euclidean_derivative():
    value = torch.tensor([[0., 0., 0.], [-3., 4., 12.]], requires_grad=True)
    result = compensated_norm3(value, keepdim=True)
    assert torch.equal(result, torch.tensor([[0.], [13.]]))
    result.sum().backward()
    assert torch.isfinite(value.grad).all()
    assert torch.equal(value.grad[0], torch.zeros(3))
    torch.testing.assert_close(value.grad[1], value.detach()[1]/13., rtol=0, atol=0)


@pytest.mark.parametrize("squared", (False, True))
def test_pairwise_tiling_preserves_direct_geometry_and_position_gradient(squared):
    left = torch.tensor([[[0., 0., 0.], [1., 2., 3.]]], requires_grad=True)
    right = torch.tensor([[[.2, .5, .7], [1., 2., 3.], [-1., .5, 2.]]], requires_grad=True)
    result = compensated_pairwise_norm3(left, right, squared=squared)
    difference = left.double()[:, :, None] - right.double()[:, None]
    oracle = difference.square().sum(-1)
    if not squared: oracle = oracle.sqrt()
    torch.testing.assert_close(result.double(), oracle, rtol=0, atol=1e-6)
    result.sum().backward()
    assert torch.isfinite(left.grad).all() and torch.isfinite(right.grad).all()
    direction = difference.detach() if squared else difference.detach()/oracle.detach().clamp_min(1)[..., None]
    if not squared:
        norm = oracle.detach()[..., None]
        direction = torch.where(norm > 0, difference.detach()/norm.clamp_min(1e-30), torch.zeros_like(difference))
    else: direction = 2*direction
    torch.testing.assert_close(left.grad.double(), direction.sum(2), rtol=0, atol=1e-6)
    torch.testing.assert_close(right.grad.double(), -direction.sum(1), rtol=0, atol=1e-6)


def test_pair_tile_boundary_is_not_a_new_geometric_boundary():
    generator = torch.Generator().manual_seed(612)
    pos = torch.randn(1, 257, 3, generator=generator)
    result = compensated_pairwise_norm3(pos, pos)
    assert result.shape == (1, 257, 257)
    rows = torch.tensor([0, 254, 255, 256])
    oracle = torch.linalg.vector_norm(pos.double()[0, rows] - pos.double()[0, 256], dim=-1)
    torch.testing.assert_close(result[0, rows, 256].double(), oracle, rtol=0, atol=1e-6)
    assert torch.equal(result[0].diagonal(), torch.zeros(257))


def test_production_primitives_never_create_fp64_or_change_global_backend_flags():
    from torch.utils._python_dispatch import TorchDispatchMode
    class ForbidFP64(TorchDispatchMode):
        def __torch_dispatch__(self, func, types, args=(), kwargs=None):
            output = func(*args, **(kwargs or {}))
            tensors = output if isinstance(output, (list, tuple)) else (output,)
            assert not any(isinstance(x, torch.Tensor) and x.dtype == torch.float64 for x in tensors)
            return output
    previous = (torch.are_deterministic_algorithms_enabled(), torch.get_float32_matmul_precision(),
                torch.backends.cuda.matmul.allow_tf32)
    with ForbidFP64():
        source = torch.randn(7, 3, requires_grad=True)
        result = compensated_index_add(torch.zeros(2, 3), torch.tensor([1, 0, 1, 0, 1, 1, 0]), source)
        (compensated_norm3(result).sum() + compensated_squared_norm3(result).sum()).backward()
    assert previous == (torch.are_deterministic_algorithms_enabled(), torch.get_float32_matmul_precision(),
                        torch.backends.cuda.matmul.allow_tf32)


def test_nonfinite_values_are_not_silently_replaced_by_finite_values():
    source = torch.tensor([[float("inf"), float("nan")], [1., 1.]])
    result = compensated_index_add(torch.zeros(1, 2), torch.zeros(2, dtype=torch.long), source)
    assert torch.isposinf(result[0, 0]) and torch.isnan(result[0, 1])


@pytest.mark.parametrize("fault", ("unknown", "extra", "conflict", "onesided", "null", "missing_mode"))
def test_config_mode_is_explicit_and_rejects_ambiguous_bindings(fault):
    value = config(COMPENSATED)
    if fault == "unknown": value["numeric_stability"]["mode"] = "automatic"
    elif fault == "extra": value["numeric_stability"]["implicit"] = True
    elif fault == "conflict": value["head"]["numeric_mode"] = LEGACY
    elif fault == "null": value["numeric_stability"] = None
    elif fault == "missing_mode": value["numeric_stability"] = {}
    else:
        del value["numeric_stability"]
        value["head"]["numeric_mode"] = COMPENSATED
    with pytest.raises(ValueError): build_model(value)


def test_absent_and_explicit_legacy_are_bitwise_identical_with_unchanged_config_identity():
    original = config()
    assert numeric_stability_configuration(original) == original
    torch.manual_seed(801); implicit = build_model(original).eval()
    rng = torch.get_rng_state().clone()
    torch.manual_seed(801); explicit = build_model(config(LEGACY)).eval()
    assert torch.equal(torch.get_rng_state(), rng)
    assert implicit.config_dict() == explicit.config_dict()
    assert torch.equal(implicit.encode_atoms(atoms()), explicit.encode_atoms(atoms()))
    assert torch.equal(implicit.encode_graph(atoms()), explicit.encode_graph(atoms()))
    assert not hasattr(implicit, "numeric_mode")


@pytest.mark.parametrize("kind", ("C1-0", "C1-a", "C1-b"))
def test_candidate_preserves_every_parameter_state_key_rng_and_binds_config(kind):
    option = ArchitectureOptions(distance_bias=kind, pair_dim=8, pair_hidden_dim=8)
    torch.manual_seed(800); legacy = build_architecture_model(config(), option).eval()
    rng = torch.get_rng_state().clone()
    torch.manual_seed(800); candidate = build_architecture_model(config(COMPENSATED), option).eval()
    assert torch.equal(torch.get_rng_state(), rng)
    assert set(legacy.state_dict()) == set(candidate.state_dict())
    for name, value in legacy.state_dict().items():
        if isinstance(value, torch.Tensor): assert torch.equal(value, candidate.state_dict()[name]), name
    assert numeric_mode(candidate) == numeric_mode(candidate.backbone) == COMPENSATED
    if kind != "C1-0": assert numeric_mode(candidate.backbone.pair_encoder) == COMPENSATED
    contract = numeric_checkpoint_contract(candidate)
    assert contract["model_config"]["backbone_config"]["numeric_mode"] == COMPENSATED
    assert contract["model_config"]["head_config"]["numeric_mode"] == COMPENSATED
    output = candidate.encode_atoms(atoms())
    assert output.shape == (5, 16) and output.dtype == torch.float32 and torch.isfinite(output).all()
    output.square().sum().backward()
    assert candidate.backbone.atom_emb.weight.grad is not None
    assert torch.isfinite(candidate.backbone.atom_emb.weight.grad).all()
    load_numeric_bound_state_dict(candidate, candidate.state_dict(), contract)
    with pytest.raises(ValueError, match="numeric mode/model"):
        load_numeric_bound_state_dict(legacy, candidate.state_dict(), contract)


def test_legacy_attention_matches_independent_original_expression_bitwise():
    torch.manual_seed(121)
    attention = DenseGeoSelfAttention(16, 4, use_radius_mask=False).eval()
    h, pos, mask = torch.randn(2, 7, 16), torch.randn(2, 7, 3), torch.ones(2, 7, dtype=torch.bool)
    q, k, v = attention.qkv(h).view(2, 7, 3, 4, 4).unbind(2)
    q, k, v = (x.transpose(1, 2) for x in (q, k, v))
    logits = torch.matmul(q, k.transpose(-2, -1))/2.
    difference = pos[:, :, None, :] - pos[:, None, :, :]
    distances = (difference*difference).sum(-1)
    logits = logits + attention.dist_mlp(distances.unsqueeze(-1)).permute(0, 3, 1, 2).contiguous()
    logits = logits.masked_fill(~mask[:, None, None, :], -1e9)
    weights = attention.attn_drop(torch.softmax(logits, dim=-1))
    expected = attention.proj(torch.matmul(weights, v).transpose(1, 2).contiguous().view(2, 7, 16))*mask[..., None]
    actual, actual_weights = attention(h, pos, mask)
    assert torch.equal(actual, expected) and torch.equal(actual_weights, weights)


@pytest.mark.parametrize("form,pooling", (("H1", "sum"), ("H1", "learned"), ("H2", "mean"), ("H3", "sum")))
def test_head_bank_mode_binds_existing_extra_state_without_new_keys_and_all_terminals_nonzero(form, pooling):
    torch.manual_seed(319); legacy = V3HeadBank(registry(pooling), dim=16, forms=form, hidden_dim=8)
    rng = torch.get_rng_state().clone()
    torch.manual_seed(319); candidate = V3HeadBank(registry(pooling), dim=16, forms=form, hidden_dim=8,
                                               numeric_mode=COMPENSATED)
    assert torch.equal(torch.get_rng_state(), rng)
    assert set(legacy.state_dict()) == set(candidate.state_dict())
    for name, value in legacy.state_dict().items():
        if isinstance(value, torch.Tensor): assert torch.equal(value, candidate.state_dict()[name])
    assert "numeric_mode" not in legacy.get_extra_state()
    assert candidate.get_extra_state()["numeric_mode"] == COMPENSATED
    with pytest.raises(ValueError): legacy.load_state_dict(candidate.state_dict())
    batch = atoms()
    h = torch.randn(5, 16, requires_grad=True)
    prediction = candidate(h, batch.batch, batch.pos, enabled_groups=("P",), pair_indices={"p": torch.tensor([[0, 3], [1, 4]])})
    assert set(prediction) == {"g", "v", "m", "a", "p"}
    assert all(value.dtype == torch.float32 and torch.isfinite(value).all() for value in prediction.values())
    assert all(float(prediction[name].abs().max()) > 1e-8 for name in ("v", "m", "a"))
    sum(value.square().sum() for value in prediction.values()).backward()
    assert h.grad is not None and torch.isfinite(h.grad).all() and bool((h.grad != 0).any())


def test_geometry_messages_and_noise_use_finite_mathematical_backward_with_permuted_atoms():
    torch.manual_seed(327)
    head = apply_numeric_mode(EquivariantDenoisingHead(8, hidden_dim=8, rbf_count=8,
                              message_layers=1, pair_chunk_size=3), COMPENSATED)
    batch = atoms()
    order = torch.tensor([3, 0, 4, 2, 1])
    pos = batch.pos[order].clone().requires_grad_()
    h = torch.randn(5, 8, requires_grad=True)
    output = head(h, pos, batch.batch[order])
    assert output.shape == (5, 3) and float(output.abs().max()) > 1e-8
    output.square().sum().backward()
    assert torch.isfinite(pos.grad).all() and torch.isfinite(h.grad).all()
    assert head.messages[0][0].weight.grad is not None
    assert bool((head.pair_mlp[0].weight.grad != 0).any())


def test_isolated_geometry_and_compensated_pool_keep_zero_rows_without_nan():
    head = apply_numeric_mode(EquivariantDenoisingHead(8, hidden_dim=8, rbf_count=8), COMPENSATED)
    assert torch.equal(head(torch.randn(1, 8), torch.zeros(1, 3), torch.zeros(1, dtype=torch.long)), torch.zeros(1, 3))
    pool = apply_numeric_mode(UnifiedGraphPooling(3), COMPENSATED)
    h = torch.tensor([[1e8, 1., 2.], [1., 3., 4.], [-1e8, 5., 6.]])
    batch = torch.zeros(3, dtype=torch.long)
    assert torch.equal(pool(h, batch, "sum"), torch.tensor([[1., 9., 12.]]))


def test_norm_backward_preserves_nonzero_hessian_for_force_gradient_losses():
    value = torch.tensor([[3., 4., 12.]], requires_grad=True)
    direction = torch.tensor([[.3, -.7, 1.2]])
    first = torch.autograd.grad(compensated_norm3(value).sum(), value, create_graph=True)[0]
    hessian_vector = torch.autograd.grad((first*direction).sum(), value)[0]
    expected = direction/13. - value.detach()*(value.detach()*direction).sum(-1, keepdim=True)/(13.**3)
    torch.testing.assert_close(hessian_vector, expected, rtol=0, atol=1e-8)


@pytest.mark.parametrize("fault", ("autocast", "parameters", "coordinates"))
def test_candidate_explicitly_rejects_amp_or_non_fp32_model_inputs(fault):
    model = build_model(config(COMPENSATED)).eval()
    batch = atoms()
    if fault == "parameters": model.half()
    elif fault == "coordinates": batch.pos = batch.pos.double()
    if fault == "autocast":
        with torch.autocast("cpu", dtype=torch.bfloat16), pytest.raises(ValueError, match="autocast"):
            model.encode_atoms(batch)
    else:
        with pytest.raises(ValueError, match="FP32"):
            model.encode_atoms(batch)


def test_empty_pair_domain_retains_zero_gradients_to_both_coordinate_inputs():
    left = torch.empty(1, 0, 3, requires_grad=True)
    right = torch.ones(1, 2, 3, requires_grad=True)
    output = compensated_pairwise_norm3(left, right)
    assert output.shape == (1, 0, 2) and output.dtype == torch.float32
    output.sum().backward()
    assert left.grad.shape == left.shape and torch.equal(right.grad, torch.zeros_like(right))


@pytest.mark.parametrize("magnitude", (False, True))
def test_legacy_dipole_is_bitwise_equal_to_original_centroid_moment_expression(magnitude):
    torch.manual_seed(623)
    head = _DipoleHead(8, 8, magnitude).eval()
    h, pos = torch.randn(13, 8), torch.randn(13, 3)
    batch = torch.tensor([0]*9 + [1]*4)
    center = pos.new_zeros((2, 3)).index_add(0, batch, pos)
    center = center / torch.bincount(batch, minlength=2).to(pos.dtype).clamp_min(1)[:, None]
    vector = pos.new_zeros((2, 3)).index_add(0, batch, head.charges(h)*(pos-center[batch]))
    expected = vector.norm(dim=-1, keepdim=True) if magnitude else vector
    assert torch.equal(head(h, pos, batch, 2), expected)


def test_legacy_geometry_is_bitwise_equal_to_original_chunked_index_add_expression():
    torch.manual_seed(624)
    head = EquivariantDenoisingHead(8, hidden_dim=8, rbf_count=8, message_layers=1,
                                    pair_chunk_size=3, normalization="sqrt_neighbors").eval()
    batch = atoms()
    h, pos = torch.randn(5, 8), batch.pos
    src, dst = head._edges(pos, batch.batch)
    degree = torch.bincount(src, minlength=len(pos)).clamp_min(1).to(pos.dtype).sqrt()[:, None]
    def original_features(features, i, j):
        relative = pos[i]-pos[j]
        distance = relative.norm(dim=-1).clamp_min(1e-8)
        rbf = torch.exp(-head.rbf_gamma*(distance[:, None]-head.rbf_centers)**2)
        rbf = rbf*(.5*(1.+torch.cos(torch.pi*distance/head.radius)))[:, None]
        return torch.cat((features[i], features[j], rbf.to(features.dtype)), dim=-1), relative/distance[:, None]
    with torch.no_grad():
        working = h
        for layer in head.messages:
            aggregated = torch.zeros_like(working)
            for start in range(0, len(src), 3):
                i, j = src[start:start+3], dst[start:start+3]
                aggregated = aggregated.index_add(0, i, layer(original_features(working, i, j)[0]))
            working = working + aggregated/degree.to(working.dtype)
        expected = torch.zeros_like(pos)
        for start in range(0, len(src), 3):
            i, j = src[start:start+3], dst[start:start+3]
            feature, direction = original_features(working, i, j)
            expected = expected.index_add(0, i, (head.pair_mlp(feature)*direction).to(pos.dtype))
        expected = expected/degree
        assert torch.equal(head(h, pos, batch.batch), expected)
