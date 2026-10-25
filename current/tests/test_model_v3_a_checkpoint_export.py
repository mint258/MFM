"""Real small CPU training and safe generic H0 serialization; no GPU acceptance."""
from copy import deepcopy
from dataclasses import asdict
import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch
from torch_geometric.data import Batch, Data

from phychem_mfm.model.v3_performance import PerformanceOptions, build_performance_model, make_adamw
from phychem_mfm.phase1.v3_encoder_bridge import EncoderBindingError
from phychem_mfm.training import checkpoint as standard

ROOT = Path(__file__).absolute().parents[2]


def helper(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "tools/model_v3"))
    spec = importlib.util.spec_from_file_location("model_v3_export_test", ROOT / "tools/model_v3/a_checkpoint_export.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def trained_cpu():
    model_config = deepcopy(json.loads((ROOT / "workflows/s_denoise/configs/A4_seed0_v3.json").read_text())["model"])
    model_config["backbone"].update(dim=512, layers=6, heads=8)
    model_config["expert"]["heads"] = 8
    options = PerformanceOptions(backbone_checkpointing=False)
    optimizer_config = {"lr": 3e-4, "betas": [.9, .95], "weight_decay": .01}
    batch = Batch.from_data_list([
        Data(x=torch.tensor([[5], [0], [0]]), pos=torch.tensor([[0., 0., 0.], [1., 0., 0.], [0., 1., 0.]])),
        Data(x=torch.tensor([[7], [0]]), pos=torch.tensor([[0., 0., 0.], [0., 0., 1.]]))])
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(7)
        model = build_performance_model(model_config, options).train()
        optimizer = make_adamw(model, optimizer_config, options)
        before = model.backbone.out_norm.weight.detach().clone()
        for _ in range(2):
            optimizer.zero_grad(set_to_none=True)
            h0 = model.encode_atoms(batch)
            target = torch.linspace(-.2, .2, h0.numel()).reshape_as(h0)
            loss = (h0 - target).square().mean() + .1 * h0[:, 0].mean()
            loss.backward()
            optimizer.step()
    assert not torch.equal(before, model.backbone.out_norm.weight)
    configuration = {"model": model_config, "seed": 7, "code_sha": "a" * 40, "prereg_sha": "b" * 40,
        "supervision": {"variant": "none", "fixture_loss": "CPU_H0_regression_not_native_S"},
        "loss_weights": {"fixture_H0_MSE": 1.}, "optimizer": optimizer_config,
        "schedule": {"kind": "fixed_lr_CPU_fixture"}, "candidate": asdict(options),
        "deterministic_controls": None, "input": "synthetic_CPU_fixture", "smoke": True,
        "data_version": {"input_kind": "synthetic_CPU_fixture", "base_records": 2}}
    names = ("tools/model_v3/a_checkpoint_export.py", "tools/model_v3/paired_a_acceptance.py",
        "current/phychem_mfm/training/checkpoint.py", "current/phychem_mfm/model/v3_performance.py")
    configuration["source_sha256"] = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in names}
    return model, optimizer, batch, configuration


@pytest.fixture(scope="module")
def bundle(tmp_path_factory, trained_cpu):
    # Call the serialization primitive, never fake full-native admission or READY.
    tools = ROOT / "tools/model_v3"
    spec = importlib.util.spec_from_file_location("model_v3_export_fixture", tools / "a_checkpoint_export.py")
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    root = tmp_path_factory.mktemp("a_h0_CPU_serialization_only")
    model, optimizer, batch, configuration = trained_cpu
    source_sha = module.canonical(configuration["source_sha256"])
    provenance = {"schema": "CPU_UNIT_ROUNDTRIP_NOT_A_ACCEPTANCE", "full_native_A_numeric_gates_passed": False,
        "code_sha": configuration["code_sha"], "source_inventory_sha256": source_sha,
        "consumed_base_records": 4, "optimizer_updates": 2, "A_resume_supported": False}
    source = {"git_commit": configuration["code_sha"], "git_dirty": None, "source_sha256": source_sha,
              "source_files": configuration["source_sha256"]}
    original_source = hashlib.sha256(Path(standard.__file__).read_bytes()).hexdigest()
    original_provider = standard.environment_fingerprint
    safe_globals = list(torch.serialization.get_safe_globals())
    rng = torch.get_rng_state().clone()
    refs = module.write_standard_h0_bundle(root, model=model, optimizer=optimizer,
        configuration=configuration, provenance=provenance, source_metadata=source)
    assert torch.equal(rng, torch.get_rng_state())
    assert standard.environment_fingerprint is original_provider
    assert hashlib.sha256(Path(standard.__file__).read_bytes()).hexdigest() == original_source
    assert list(torch.serialization.get_safe_globals()) == safe_globals
    assert not (root / "READY.json").exists()
    return root, module, refs, source_sha, trained_cpu


def test_real_cpu_training_weights_only_and_generic_H0_roundtrip(bundle):
    root, module, refs, source_sha, (model, optimizer, batch, configuration) = bundle
    payload = torch.load(refs["checkpoint"]["path"], map_location="cpu", weights_only=True)
    assert payload["format_version"] == 1 and type(payload["environment"]["torch"]) is str
    assert payload["optimizer_update_step"] == 2 and payload["global_exposure_step"] == 4
    assert payload["scheduler_state"]["used_during_training"] is False
    assert payload["optimizer_state"]["state"]
    assert all(float(row["step"]) == 2 for row in payload["optimizer_state"]["state"].values())
    safe_globals = list(torch.serialization.get_safe_globals())
    rng = torch.get_rng_state().clone()
    pair = module.verify_h0_bundle(refs, expected_code_sha="a" * 40, expected_source_sha256=source_sha)
    assert torch.equal(rng, torch.get_rng_state())
    assert list(torch.serialization.get_safe_globals()) == safe_globals
    assert pair.provenance["checkpoint_schema"] == "source_training_checkpoint_v1"
    assert pair.candidate.latent_dim == 512 and pair.provenance["downstream_target_records_read"] == 0
    model.eval()
    with torch.no_grad():
        expected, actual = model.encode_atoms(batch), pair.candidate.encode_atoms(batch)
    torch.testing.assert_close(actual, expected, rtol=1e-5, atol=1e-6)
    assert not (root / "READY.json").exists()  # serialization-only CPU fixture is never an accepted export


def test_default_and_failed_admission_create_no_export_directory(tmp_path, trained_cpu, monkeypatch):
    module = helper(monkeypatch)
    assert module.export_candidate_checkpoint(None, output_root=tmp_path) is None
    assert list(tmp_path.iterdir()) == []
    model, optimizer, _batch, configuration = trained_cpu
    destination = tmp_path / "not_accepted"
    with pytest.raises(ValueError, match="full native-S"):
        module.export_candidate_checkpoint(destination, output_root=tmp_path, repository_root=ROOT,
            model=model, optimizer=optimizer, configuration=configuration,
            fixed_gate={}, trajectory_gate={}, consumed_samples=4, stream_state={"committed_base_samples": 4})
    assert not destination.exists()
    native_metadata = {**configuration, "input": "native_s", "smoke": False,
                       "fixed_batches": 20, "trajectory_updates": 500}
    with pytest.raises(ValueError, match="Fixed20-batch gate not complete/pass"):
        module.export_candidate_checkpoint(destination, output_root=tmp_path, repository_root=ROOT,
            model=model, optimizer=optimizer, configuration=native_metadata,
            fixed_gate={"pass": False}, trajectory_gate={}, consumed_samples=4,
            stream_state={"committed_base_samples": 4})
    assert not destination.exists()


def test_export_rejects_changed_code_source_and_config_bytes(bundle, tmp_path, monkeypatch):
    _root, module, refs, source_sha, trained = bundle
    with pytest.raises(ValueError, match="code/source provenance"):
        module.verify_h0_bundle(refs, expected_code_sha="0" * 40, expected_source_sha256=source_sha)
    with pytest.raises(ValueError, match="code/source provenance"):
        module.verify_h0_bundle(refs, expected_code_sha="a" * 40, expected_source_sha256="0" * 64)
    changed = deepcopy(trained[3])
    changed["source_sha256"]["current/phychem_mfm/training/checkpoint.py"] = "0" * 64
    with pytest.raises(ValueError, match="source bytes changed"):
        module.verify_source_inventory(changed, ROOT)
    wrong = {**refs, "model_configuration": {**refs["model_configuration"], "sha256": "0" * 64}}
    with pytest.raises(ValueError, match="source file bytes differ"):
        module.verify_h0_bundle(wrong, expected_code_sha="a" * 40, expected_source_sha256=source_sha)


def test_generic_bridge_rejects_same_shape_semantics_and_wrong_tensor_shape(bundle, tmp_path):
    _root, module, refs, source_sha, _trained = bundle
    configuration = json.loads(Path(refs["model_configuration"]["path"]).read_text())
    configuration["backbone"]["radius"] += .25
    changed = tmp_path / "wrong_recipe.json"
    module.write_json(changed, configuration)
    with pytest.raises(EncoderBindingError, match="semantic configuration differs"):
        module.verify_h0_bundle({**refs, "model_configuration": module.file_ref(changed)},
            expected_code_sha="a" * 40, expected_source_sha256=source_sha)
    payload = torch.load(refs["checkpoint"]["path"], map_location="cpu", weights_only=True)
    state = dict(payload["model_state"])
    key = next(name for name, value in state.items() if value.ndim == 2 and value.shape[0] > 1)
    state[key] = state[key][:-1].clone()
    payload["model_state"], payload["optimizer_state"] = state, {}
    bad = tmp_path / "wrong_shape.pt"
    torch.save(payload, bad)
    with pytest.raises(EncoderBindingError, match="shape/dtype/finiteness"):
        module.verify_h0_bundle({**refs, "checkpoint": {**module.file_ref(bad), "state_key": "model_state"}},
            expected_code_sha="a" * 40, expected_source_sha256=source_sha)


def test_new_adapter_retains_standard_v1_field_structure(bundle, monkeypatch):
    _root, module, refs, _source_sha, (model, optimizer, _batch, configuration) = bundle
    actual = torch.load(refs["checkpoint"]["path"], map_location="cpu", weights_only=True)
    captured = {}
    monkeypatch.setattr(standard, "_atomic_torch_save", lambda payload, destination: captured.update(payload))
    scheduler = SimpleNamespace(state_dict=lambda: {"kind": "none_fixed_lr_diagnostic",
        "used_during_training": False, "resume_supported": False})
    standard.save_training_checkpoint(Path(refs["checkpoint"]["path"]).parent / "never_written.pt",
        model=model, optimizer=optimizer, scheduler=scheduler, config=module.h0_training_recipe(configuration),
        supervision=configuration["supervision"], dataset_manifest=configuration["data_version"],
        exposure_step=4, optimizer_update_step=2, checkpoint_type=actual["checkpoint_type"],
        project_root=ROOT, source_metadata=actual["source"], extra=actual["extra"])
    assert set(actual) == set(captured)
    for key in ("format_version", "model_config", "backbone_config", "semantic_config", "semantic_config_sha256",
                "dataset_manifest", "dataset_manifest_sha256", "seed", "scheduler_state", "source", "extra"):
        assert actual[key] == captured[key]
    assert str(actual["environment"]["torch"]) == str(captured["environment"]["torch"])
