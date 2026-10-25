"""Small actual math/operator checks. No original NPZ or model matrix run."""
from copy import deepcopy
import importlib

import pytest
import torch

import diagnose_aggregation as diagnostic

equation = importlib.import_module("phychem_mfm.phase1.v3_composed_equivariance")
heads = importlib.import_module("phychem_mfm.model.v3_heads")


def fixture_values(dtype=torch.float64):
    pos = torch.tensor([[.2, -.3, .7], [1.3, .8, -.1], [-.6, .1, .4],
                        [2., -.7, .2], [2.8, -.2, .9]], dtype=dtype)
    q = torch.tensor([[2.3], [1.8], [2.1], [-.7], [.4]], dtype=dtype)
    batch = torch.tensor([0, 0, 0, 1, 1], dtype=torch.long)
    return q, pos, batch


def test_charge_centering_is_exact_real_identity_with_double_math_oracle():
    q, pos, batch = fixture_values()
    center = heads._pool(pos, batch, 2, "mean")
    original = pos.new_zeros((2, 3)).index_add(0, batch, q*(pos-center[batch]))
    centered = diagnostic.centered_vector(q, pos, batch, 2, heads._pool)
    torch.testing.assert_close(original, centered, atol=1e-12, rtol=0)
    assert float(centered.norm()) > .1
    moved = pos @ equation.transforms()[0].rotation + equation.transforms()[2].translation
    expected = centered @ equation.transforms()[0].rotation
    actual = diagnostic.centered_vector(q, moved, batch, 2, heads._pool)
    torch.testing.assert_close(actual, expected, atol=1e-12, rtol=0)


def test_cdist_patch_forces_only_euclidean_direct_and_restores_actual_function():
    original = torch.cdist
    generator = torch.Generator().manual_seed(31)
    positions = torch.randn(32, 3, generator=generator)
    direct = original(positions, positions, p=2, compute_mode="donot_use_mm_for_euclid_dist")
    manhattan = original(positions, positions, p=1)
    with diagnostic.intervention(equation, heads, "cdist_direct_only") as counts:
        assert torch.equal(torch.cdist(positions, positions), direct)
        assert torch.equal(torch.cdist(positions, positions, p=1), manhattan)
        assert counts["cdist_p2_direct_calls"] == 1
    assert torch.cdist is original


@pytest.mark.parametrize("magnitude", (False, True))
def test_charge_patch_keeps_actual_head_parameters_dtype_and_nonzero_output(magnitude):
    with torch.random.fork_rng(devices=[]):
        torch.random.default_generator.manual_seed(123)
        head = heads._DipoleHead(8, 8, magnitude).eval()
    h = torch.linspace(-1., 1., 40).reshape(5, 8)
    q, pos, batch = fixture_values(torch.float32)
    before = {n: p.detach().clone() for n, p in head.named_parameters()}
    expected = diagnostic.centered_vector(head.charges(h), pos, batch, 2, heads._pool)
    if magnitude: expected = expected.norm(dim=-1, keepdim=True)
    with diagnostic.intervention(equation, heads, "charge_center_only") as counts:
        actual = head(h, pos, batch, 2)
        assert torch.equal(actual, expected) and actual.dtype == torch.float32
        assert float(actual.norm()) > 1e-8 and counts["charge_center_calls"] == 1
    assert all(torch.equal(before[n], p) for n, p in head.named_parameters())


def test_FP64_reference_changes_only_graph512_feature_reduction_not_geometry():
    original = heads._pool
    values = torch.tensor([1e8, 1., -1e8])[:, None].expand(-1, 512)
    positions = torch.tensor([[1e8, 0., 1.], [1., 1., 0.], [-1e8, 2., 1.]])
    batch = torch.zeros(3, dtype=torch.long)
    original_position_center = original(positions, batch, 1, "mean")
    expected = original(values.double(), batch, 1, "sum").float()
    with diagnostic.intervention(equation, heads, "pool_fp64_reference_only") as counts:
        assert torch.equal(heads._pool(values, batch, 1, "sum"), expected)
        assert torch.equal(heads._pool(positions, batch, 1, "mean"), original_position_center)
        assert counts["fp64_graph_feature_pool_calls"] == 1
    assert heads._pool is original and expected.dtype == torch.float32
    assert not torch.equal(expected, original(values, batch, 1, "sum"))


def test_two_interventions_restore_every_global_callable_even_on_exception():
    originals = torch.cdist, heads._pool, heads._DipoleHead.forward
    with pytest.raises(RuntimeError, match="controlled"):
        with diagnostic.intervention(equation, heads, "charge_center_and_pool_fp64_reference"):
            assert heads._pool is not originals[1] and heads._DipoleHead.forward is not originals[2]
            raise RuntimeError("controlled")
    assert torch.cdist is originals[0] and heads._pool is originals[1] and heads._DipoleHead.forward is originals[2]


@pytest.mark.parametrize("drift", ("weight_summary", "fixture_geometry_sha256", "original_view_identity_sha256"))
def test_identity_guard_rejects_changed_weights_or_inputs(drift):
    original = {key: "synthetic_unchanged" for key in ("case_id", "case", "weight_summary", "fixture_geometry_sha256",
        "original_physical_geometry_sha256", "original_view_identity_sha256", "encoder_configuration", "registry_sha256")}
    diagnostic.unchanged_case_identity(deepcopy(original), original)
    changed = deepcopy(original); changed[drift] = "changed"
    with pytest.raises(ValueError, match="drift"): diagnostic.unchanged_case_identity(changed, original)


def test_matrix_is_all_original_cases_and_seven_predeclared_variants_no_triple():
    assert len(equation.CASE_SPECS) == 48 and len(diagnostic.VARIANTS) == 7
    assert all(len(operations) <= 2 for operations in diagnostic.VARIANTS.values())
    assert diagnostic.VARIANTS["original_formula_replay"] == ()
    assert diagnostic.PER_VARIANT_CAP == 32*1024**2 and diagnostic.TOTAL_CAP == 2*1024**3
