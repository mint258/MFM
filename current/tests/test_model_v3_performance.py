from copy import deepcopy
from types import SimpleNamespace

import pytest
import torch

from phychem_mfm.factory import build_model
from phychem_mfm.model.attention import DenseGeoSelfAttention
from phychem_mfm.model.v3_performance import (
    PerformanceOptions, RuntimeDenseAttention, SparseRadiusAttention,
    ConfigurableDenoisingHead, ConfigurableTiledDistanceMLP, build_performance_model,
    choose_checkpointing, execution_context, make_adamw, performance_forward_pretrain,
)
from phychem_mfm.model.heads import EquivariantDenoisingHead
from phychem_mfm.phase1.v3_padding import LocallySortedAtomBatchSampler
from phychem_mfm.training.v3_performance_acceptance import (
    compare_tensors, trajectory_report, bf16_curve_report,
)


def test_sparse_radius_outputs_and_gradients_match_dense_with_padding():
    torch.manual_seed(13)
    dense = DenseGeoSelfAttention(16, 4, use_radius_mask=True, radius=1.2)
    sparse = SparseRadiusAttention(deepcopy(dense), query_chunk=2)
    x = torch.randn(2, 7, 16)
    pos = torch.randn(2, 7, 3)
    mask = torch.tensor([[True] * 7, [True] * 4 + [False] * 3])
    left = dense(x, pos, mask)[0]
    right = sparse(x, pos, mask)[0]
    assert torch.allclose(left, right, rtol=1e-5, atol=1e-6)
    left.square().sum().backward()
    right.square().sum().backward()
    for (ln, lp), (rn, rp) in zip(dense.named_parameters(), sparse.named_parameters()):
        assert ln == rn and torch.allclose(lp.grad, rp.grad, rtol=1e-4, atol=1e-6)
    assert torch.equal(right[1, 4:], torch.zeros_like(right[1, 4:]))


def test_sparse_cannot_silently_change_global_attention_or_dropout_recipe():
    with pytest.raises(ValueError, match="global"):
        SparseRadiusAttention(DenseGeoSelfAttention(8, 2, use_radius_mask=False))
    with pytest.raises(ValueError, match="RNG"):
        SparseRadiusAttention(DenseGeoSelfAttention(8, 2, use_radius_mask=True, dropout=.1))


def test_distance_and_head_checkpoint_flags_preserve_values_and_state_keys():
    torch.manual_seed(7)
    original = torch.nn.Sequential(torch.nn.Linear(1, 8), torch.nn.SiLU(), torch.nn.Linear(8, 2))
    tiled = ConfigurableTiledDistanceMLP(deepcopy(original), pair_rows=3, activation_checkpointing=False)
    value = torch.randn(2, 5, 5, 1)
    assert set(original.state_dict()) == set(tiled.state_dict())
    assert torch.allclose(original(value), tiled(value), atol=1e-7, rtol=1e-6)
    head = EquivariantDenoisingHead(16, pair_chunk_size=3, message_layers=1)
    candidate = ConfigurableDenoisingHead(deepcopy(head), activation_checkpointing=False)
    h, pos, batch = torch.randn(7, 16), torch.randn(7, 3), torch.tensor([0, 0, 0, 1, 1, 1, 1])
    assert set(head.state_dict()) == set(candidate.state_dict())
    left, right = head(h, pos, batch), candidate(h, pos, batch)
    assert torch.equal(left, right)
    left.square().sum().backward()
    right.square().sum().backward()
    assert all(torch.equal(lp.grad, rp.grad) for lp, rp in zip(head.parameters(), candidate.parameters()))


def small_config():
    return {"architecture": {"preset": "shared_light"},
            "backbone": {"dim": 32, "heads": 4, "layers": 1, "ff_mult": 2,
                         "activation_checkpointing": True},
            "head": {"profile": "phase1", "geometry_head": "equivariant_noise",
                     "geometry_rbf_count": 4, "geometry_hidden_dim": 8}}


def test_selective_bf16_preserves_geometry_normalization_h0_and_state_keys():
    from torch_geometric.data import Batch, Data
    torch.manual_seed(4)
    baseline = build_model(small_config())
    torch.manual_seed(4)
    candidate = build_performance_model(small_config(), PerformanceOptions(precision="bf16"))
    assert tuple(baseline.state_dict()) == tuple(candidate.state_dict())
    assert all(torch.equal(baseline.state_dict()[name], candidate.state_dict()[name]) for name in baseline.state_dict())
    observed_norms, observed_geometry, observed_qkv = [], [], []
    handles = []
    for module in candidate.modules():
        if isinstance(module, torch.nn.LayerNorm):
            handles.append(module.register_forward_pre_hook(lambda m, values: observed_norms.append(values[0].dtype)))
    handles.append(candidate.geometry_head.pair_mlp[0].register_forward_pre_hook(
        lambda m, values: observed_geometry.append(values[0].dtype)))
    handles.append(candidate.backbone.layers[0].attn.qkv.register_forward_hook(
        lambda m, values, result: observed_qkv.append(result.dtype)))
    batch = Batch.from_data_list([Data(x=torch.tensor([[5], [0], [0]]), pos=torch.randn(3, 3))])
    outputs = performance_forward_pretrain(candidate, batch, ["geometry"])
    assert outputs.atom_repr.dtype == outputs.noise_pred.dtype == outputs.coordinate_pred.dtype == torch.float32
    assert observed_norms and set(observed_norms) == {torch.float32}
    assert observed_geometry and set(observed_geometry) == {torch.float32}
    assert observed_qkv and set(observed_qkv) == {torch.bfloat16}
    outputs.noise_pred.square().sum().backward()
    assert any(parameter.grad is not None for parameter in candidate.backbone.parameters())
    for handle in handles:
        handle.remove()


def test_compile_wraps_forward_without_state_key_changes(monkeypatch):
    seen = []
    def compile_stub(function, **kwargs):
        seen.append(kwargs)
        return function
    monkeypatch.setattr(torch, "compile", compile_stub)
    baseline = build_model(small_config())
    candidate = build_performance_model(small_config(), PerformanceOptions(compile_backbone=True))
    assert tuple(candidate.state_dict()) == tuple(baseline.state_dict())
    assert seen == [{"dynamic": True, "fullgraph": False}]


def test_standard_adamw_retains_original_automatic_dispatch_defaults():
    reference_model = torch.nn.Linear(3, 2)
    candidate_model = deepcopy(reference_model)
    configuration = {"lr": 3e-4, "betas": (.9, .95), "weight_decay": .01}
    original_configuration = deepcopy(configuration)
    reference = torch.optim.AdamW(reference_model.parameters(), **configuration)
    candidate = make_adamw(candidate_model, configuration, PerformanceOptions())
    assert reference.defaults["fused"] is None and reference.defaults["foreach"] is None
    assert candidate.defaults == reference.defaults
    assert candidate.param_groups[0]["fused"] is None
    assert candidate.param_groups[0]["foreach"] is None
    assert configuration == original_configuration


def test_adamw_explicit_execution_remains_guarded_on_cpu():
    model = torch.nn.Linear(3, 2)
    configuration = {"lr": 3e-4, "betas": (.9, .95), "weight_decay": .01}
    with pytest.raises(ValueError, match="explicit performance options"):
        make_adamw(model, {**configuration, "fused": False}, PerformanceOptions())
    with pytest.raises(ValueError, match="measured CUDA"):
        make_adamw(model, configuration, PerformanceOptions(fused_adamw=True))


def test_automatic_checkpoint_selection_requires_matching_all_off_evidence():
    request = dict(gpu_name="example", total_memory_bytes=1000, free_memory_bytes=950,
                   padded_cost=100, model_configuration_sha256="b" * 64)
    assert choose_checkpointing(**request)["backbone_checkpointing"]
    evidence = dict(gpu_name="example", total_memory_bytes=1000, padded_cost=110,
                    peak_allocated_bytes=800, model_configuration_sha256="b" * 64,
                    measurement_sha256="a" * 64, checkpoint_mode="all_off")
    assert not choose_checkpointing(**request, measured_capacity=evidence)["backbone_checkpointing"]
    assert choose_checkpointing(**{**request, "padded_cost": 111}, measured_capacity=evidence)["head_checkpointing"]
    with pytest.raises(ValueError, match="all-off"):
        choose_checkpointing(**request, measured_capacity={**evidence, "checkpoint_mode": "all_on"})


def test_exact_sort_keeps_singletons_tails_resume_and_declares_new_order():
    counts = (12, 5, 11, 9, 3, 23, 2)
    index = SimpleNamespace(content_sha256="c" * 64)
    class Index:
        content_sha256 = index.content_sha256
        def __len__(self): return len(counts)
        def ref(self, i): return SimpleNamespace(native_n_atoms=counts[i])
    sampler = LocallySortedAtomBatchSampler(Index(), exact_atom_sort=True, seed=4,
        block_size=7, max_molecules=3, max_native_atoms=20, max_padded_cost=10000,
        padded_cost_multiplier=3, atom_bucket_width=4)
    batches = list(sampler)
    assert sorted(i for batch in batches for i in batch) == list(range(7))
    assert [5] in batches
    sampler.commit_batch(batches[0])
    restored = LocallySortedAtomBatchSampler(Index(), exact_atom_sort=True, seed=4,
        block_size=7, max_molecules=3, max_native_atoms=20, max_padded_cost=10000,
        padded_cost_multiplier=3, atom_bucket_width=4)
    restored.load_state_dict(sampler.state_dict())
    assert list(restored) == batches[1:]
    assert sampler.contract["schema_version"] == "model_v3_exact_local_atom_sort_v1"


def test_gates_reject_missing_gradients_and_incomplete_or_out_of_envelope_curves():
    assert not compare_tensors({"a": None}, {"a": torch.zeros(1)}, tolerance=1e-4)["pass"]
    assert not compare_tensors({"a": torch.zeros(1)}, {"a": torch.ones(1)}, tolerance=1e-5)["pass"]
    with pytest.raises(ValueError, match="every"):
        trajectory_report({1: 1.}, {1: 1.})
    fp32 = [{"seed": seed, "optimizer_updates": 20000,
             "validation": {20000: {"rmse": value, "accuracy": value}}} for seed, value in ((0, .1), (1, .11))]
    bf16 = deepcopy(fp32)
    assert bf16_curve_report(fp32, bf16, validation_updates=[20000], denoise_metric="rmse")["pass"]
    for row in bf16:
        row["validation"][20000] = {"rmse": .101 if row["seed"] == 0 else .109, "accuracy": .105}
    assert bf16_curve_report(fp32, bf16, validation_updates=[20000], denoise_metric="rmse")["pass"]
    bf16[0]["validation"][20000]["accuracy"] = .111
    assert not bf16_curve_report(fp32, bf16, validation_updates=[20000], denoise_metric="rmse")["pass"]
