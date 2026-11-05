"""Profiler correctness: labels cannot silently change the measured model."""
from copy import deepcopy
import importlib.util
from importlib.machinery import ModuleSpec
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

import pytest
import torch

from phychem_mfm.model.attention import DenseGeoSelfAttention
from phychem_mfm.model.v3_profiling import instrument_model, padding_statistics


def test_profiler_labels_preserve_dense_outputs_gradients_keys_and_restore():
    torch.manual_seed(71)
    original = DenseGeoSelfAttention(16, 4, use_radius_mask=True, radius=2.)
    candidate = deepcopy(original)
    # A container provides the same named_modules interface as a complete model.
    container = torch.nn.Module()
    container.add_module("attention", candidate)
    x = torch.randn(2, 5, 16, requires_grad=True)
    pos = torch.randn(2, 5, 3)
    mask = torch.tensor([[1, 1, 1, 1, 1], [1, 1, 1, 0, 0]], dtype=torch.bool)
    expected = original(x, pos, mask)
    sum(value.square().sum() for value in expected).backward()
    keys = tuple(container.state_dict())
    forward_before = candidate.forward
    with instrument_model(container):
        actual = candidate(x.detach().clone().requires_grad_(), pos, mask)
        sum(value.square().sum() for value in actual).backward()
        assert tuple(container.state_dict()) == keys
    assert candidate.forward == forward_before
    for lhs, rhs in zip(expected, actual):
        assert torch.equal(lhs, rhs)
    for lhs, rhs in zip(original.parameters(), candidate.parameters()):
        assert torch.equal(lhs.grad, rhs.grad)


def test_instrumentation_restores_after_exception():
    model = torch.nn.Module()
    model.add_module("attention", DenseGeoSelfAttention(8, 2))
    old = model.attention.forward
    with pytest.raises(RuntimeError):
        with instrument_model(model):
            raise RuntimeError("intentional")
    assert model.attention.forward == old


def test_padding_counts_are_weighted_by_atoms_and_pairs():
    row = padding_statistics((4, 2), views=3)
    assert row["base_atoms"] == 6 and row["encoder_atoms"] == 18
    assert row["native_atom_fraction"] == .75
    assert row["native_pair_fraction"] == .625
    assert row["native_pairs_including_diagonal"] == 60
    assert row["padded_pairs_including_diagonal"] == 96
    with pytest.raises(ValueError):
        padding_statistics((0,))


def test_synthetic_smoke_has_actual_labels_for_all_s_tasks():
    from phychem_mfm.factory import build_model
    from phychem_mfm.phase1.objectives import compute_phase1_loss, Phase1LossPolicy
    from phychem_mfm.supervision import SupervisionConfig
    from phychem_mfm.training.losses import LossWeights
    path = Path(__file__).absolute().parents[2] / "tools/model_v3/profile_s_baseline.py"
    spec = importlib.util.spec_from_file_location("model_v3_profile_fixture", path)
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    batch = fixture.synthetic_corpus(0, 0).encoder_batch
    config = {"architecture": {"preset": "shared_light"},
              "backbone": {"dim": 32, "heads": 4, "layers": 1, "ff_mult": 2},
              "head": {"profile": "phase1", "geometry_head": "equivariant_noise",
                       "geometry_hidden_dim": 8, "geometry_rbf_count": 4}}
    model = build_model(config)
    supervision = SupervisionConfig.from_variant("S")
    policy = Phase1LossPolicy.from_mapping({"geometry_task": "denoise_eps_mse"})
    outputs = model.forward_pretrain(batch, supervision.objectives)
    result = compute_phase1_loss(outputs, batch, None, supervision, LossWeights(), None, 0, policy=policy)
    assert torch.isfinite(result.total)
    assert all(result.counts[name] > 0 for name in ("element", "bond_order", "denoise_eps_mse"))
    result.total.backward()
    assert any(parameter.grad is not None for parameter in model.backbone.parameters())


def profiler_fixture():
    path = Path(__file__).absolute().parents[2] / "tools/model_v3/profile_s_baseline.py"
    spec = importlib.util.spec_from_file_location("model_v3_source_binding_fixture", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def prepare_explicit_sources(module, root, *, omit=None):
    for name in module.EXPLICIT_SOURCES:
        if name != omit:
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("# bound ordinary source: " + name + "\n")


def test_source_bindings_skip_dynamic_torch_paths_and_keep_real_repo_sources(tmp_path, monkeypatch):
    module = profiler_fixture()
    root = tmp_path / "repo"
    prepare_explicit_sources(module, root)
    real = root / "loaded_real_source.py"
    real.write_text("value = 1\n")
    external = tmp_path / "third_party.py"
    external.write_text("value = 2\n")
    valid = ModuleType("real_repo_module")
    valid.__spec__ = ModuleSpec(valid.__name__, None, origin=str(real))
    valid.__file__ = "relative_alias.py"
    relative = ModuleType("torch_relative_pseudo")
    relative.__file__ = "_classes.py"
    relative.__spec__ = ModuleSpec(relative.__name__, None, origin="_classes.py")
    outside = ModuleType("third_party_absolute")
    outside.__file__ = str(external)
    missing = ModuleType("missing_dynamic_source")
    missing.__file__ = str(root / "absent_dynamic.py")
    class DynamicModule(ModuleType):
        def __getattr__(self, name):
            raise AssertionError("Dynamic module attribute lookup is forbidden: " + name)
    dynamic = DynamicModule("torch_dynamic_module")
    monkeypatch.setattr(module, "REPO", root)
    monkeypatch.setattr(module, "sys", SimpleNamespace(modules={
        "valid": valid, "relative": relative, "outside": outside, "missing": missing, "dynamic": dynamic}))
    monkeypatch.chdir(root)
    bound = module.source_bindings()
    assert set(module.EXPLICIT_SOURCES) <= set(bound)
    assert bound["loaded_real_source.py"] == module.digest(real)
    assert "_classes.py" not in bound and "relative_alias.py" not in bound
    assert "absent_dynamic.py" not in bound and "third_party.py" not in bound


def test_source_bindings_reject_missing_explicit_source(tmp_path, monkeypatch):
    module = profiler_fixture()
    root = tmp_path / "repo"
    missing = module.EXPLICIT_SOURCES[-1]
    prepare_explicit_sources(module, root, omit=missing)
    monkeypatch.setattr(module, "REPO", root)
    monkeypatch.setattr(module, "sys", SimpleNamespace(modules={}))
    with pytest.raises(FileNotFoundError, match="Required ordinary repository source is missing"):
        module.source_bindings()
