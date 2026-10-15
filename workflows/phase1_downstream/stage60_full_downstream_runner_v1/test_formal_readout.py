"""Small genuine readout forwards; synthetic sources do not prove file truth."""
from copy import deepcopy
from types import SimpleNamespace
import os
import json
from pathlib import Path

import pytest
import torch

from formal_plan import FormalReadoutError, digest
from formal_readout import (observed_loss, evaluate_outer, validate_store_group,
                            train_fixed_readout, _tree_hash)


def fixture(level="graph", directory=None):
    fit = {"dataset_id": "qm7" if level == "graph" else "az_exactsom", "fold_id": "0",
        "readout": "atom_mlp64", "readout_seed": 0, "output_level": level,
        "tasks": ["target"], "endpoints": ["endpoint"], "primary_inference": [True],
        "protocol_content_sha256": "a" * 64, "units": ["synthetic-unit"]}
    norm = {"kind": "train_affine" if level == "graph" else "identity", "fit_scope": "train",
            "means": [10.] if level == "graph" else [0.], "scales": [2.] if level == "graph" else [1.], "availability": [True]}
    samples = {}
    for index, role in enumerate(("train", "train_inner_validation", "test")):
        shape = (1, 1) if level == "graph" else (2, 1)
        target = torch.full(shape, 12., dtype=torch.float32) if level == "graph" else torch.tensor([[0.], [1.]])
        samples[index] = SimpleNamespace(dataset_id=fit["dataset_id"], member_index=index, member_uid=role,
            geometry_ready=True, provenance={"synthetic_source": index}, unavailable_reason=None,
            x=torch.tensor([5, 7]), pos=torch.tensor([[0., 0., 0.], [1., 0., 0.]]), source_atom_ids=torch.arange(2),
            targets=target, candidate_mask=torch.ones(shape, dtype=torch.bool), supervision_mask=torch.ones(shape, dtype=torch.bool))
    contract = {"tasks": ["target"], "units": ["synthetic-unit"], "output_level": level, "normalization": norm,
        "protocol_content_sha256": "a" * 64, "original_inventory_count": 3,
        "ordered_members": {role: [role] for role in ("train", "train_inner_validation", "test")}}
    if directory is not None:
        from formal_readout import _make_readout, file_sha
        config = _make_readout(fit, "cpu").config_dict()
        path = Path(directory) / "readout-config.json"
        path.write_text(json.dumps(config) + "\n", encoding="utf-8")
        contract["readout_binding"] = {"main": {"config": config, "config_sha256": digest(config),
            "file": {"path": str(path.absolute()), "bytes": path.stat().st_size, "sha256": file_sha(path)},
            "config_hash_recipe": "canonical finite sorted UTF8 JSON ensure_ascii=false",
            "file_hash_recipe": "physical raw JSON file bytes including newline"}}
    class Store:
        def contract(self, dataset, fold): return deepcopy(contract)
        def view(self, dataset, fold, role): return (("train", "train_inner_validation", "test").index(role),)
        def get(self, dataset, index): return samples[index]
    class Cache:
        catalog = {"cache_sha256": "1" * 64}
        def get(self, sample):
            value = torch.zeros(2, 384)
            value[:, 0] = torch.tensor([1., 2.])
            return value
    return fit, Store(), Cache(), contract, samples


def test_fixed_task_denominator_not_observed_count():
    predictions = torch.tensor([[3., 100.]], requires_grad=True)
    batch = {"targets": torch.tensor([[1., float("nan")]]), "supervision_mask": torch.tensor([[True, False]]),
             "candidate_mask": torch.tensor([[True, True]])}
    value, rows, counts = observed_loss(predictions, batch,
        {"means": [0., 0.], "scales": [1., 1.], "availability": [True, False]}, level="graph")
    assert value.item() == 2. and rows == [4., None] and counts == [1, 0]
    value.backward()
    assert torch.equal(predictions.grad, torch.tensor([[2., 0.]]))


def test_test_role_exact_native_ties_partial_unknown_and_no_train():
    fit, store, cache, contract, samples = fixture("atom")
    from formal_readout import _make_readout
    model = _make_readout(fit, "cpu")
    with torch.no_grad():
        for parameter in model.parameters(): parameter.zero_()
    before = _tree_hash(model.state_dict())
    report = evaluate_outer(model, store, cache, fit, contract, device="cpu", encoder_binding={}, wall_check=lambda: None)
    # Equal logits choose original native atom0, so source-positive atom1 is hit
    # only at k>=2. Unknown source atom0 cannot be treated as a negative.
    assert report["metrics"]["target"]["molecule_hit_at_k"] == {"1": 0., "2": 1., "3": 1.}
    samples[2].supervision_mask[0] = False
    partial = evaluate_outer(model, store, cache, fit, contract, device="cpu", encoder_binding={}, wall_check=lambda: None)
    assert partial["metrics"]["target"]["partitions"]["partial_supervision"] == 1
    assert partial["metrics"]["target"]["molecule_hit_at_k"]["1"] is None
    assert _tree_hash(model.state_dict()) == before


def test_outer_regression_fp64_inverse_units():
    fit, store, cache, contract, _ = fixture()
    from formal_readout import _make_readout
    model = _make_readout(fit, "cpu")
    with torch.no_grad():
        for parameter in model.parameters(): parameter.zero_()
        model.output.bias.fill_(2.)
    result = evaluate_outer(model, store, cache, fit, contract, device="cpu", encoder_binding={}, wall_check=lambda: None)
    # z=2 -> raw14, actual raw target12; reporting is raw MAE2, not z error1.
    assert result["metrics"]["target"]["MAE"] == 2.
    assert result["metrics"]["target"]["RMSE"] == 2.


def test_real_readout_checkpoint_resume_preserves_fixed_endpoint(tmp_path):
    fit, store, cache, contract, _ = fixture(directory=tmp_path)
    protocol = {"content_sha256": "a" * 64, "downstream": {"optimization_policy": {"optimizer": {
        "implementation": "single_tensor_adamw_v1", "lr": .001, "betas": [.9, .999], "eps": 1e-8,
        "weight_decay": .01, "amsgrad": False}}}}
    contract["optimizer"] = deepcopy(protocol["downstream"]["optimization_policy"])
    class Tracker:
        def __init__(self, name): self.run = SimpleNamespace(id=name, path="synthetic/" + name); self.rows = 0
        def log(self, payload): self.rows += 1
    reference = tmp_path / "reference"
    reference.mkdir()
    rng = torch.get_rng_state().clone()
    _, ref = train_fixed_readout(store, cache, fit, contract, protocol=protocol, encoder_binding={},
        tracker=Tracker("ref"), directory=reference, device="cpu", wall_check=lambda: None)
    partial = tmp_path / "partial"
    partial.mkdir()
    calls = 0
    def stop():
        nonlocal calls
        calls += 1
        if calls == 3: raise FormalReadoutError("synthetic finite attempt")
    with pytest.raises(FormalReadoutError, match="finite attempt"):
        train_fixed_readout(store, cache, fit, contract, protocol=protocol, encoder_binding={},
            tracker=Tracker("first"), directory=partial, device="cpu", wall_check=stop)
    checkpoint = partial / "latest.pt"
    from formal_readout import file_sha
    resumed = tmp_path / "resumed"
    resumed.mkdir()
    _, actual = train_fixed_readout(store, cache, fit, contract, protocol=protocol, encoder_binding={},
        tracker=Tracker("next"), directory=resumed, device="cpu", wall_check=lambda: None,
        resume_ref={"path": str(checkpoint), "bytes": checkpoint.stat().st_size, "sha256": file_sha(checkpoint)})
    assert actual["counters"] == ref["counters"]
    assert actual["actual_final_readout_state_sha256"] == ref["actual_final_readout_state_sha256"]
    assert actual["counters"]["optimizer_updates"] == 20
    assert actual["counters"]["sample_exposures"] == 20
    assert torch.equal(rng, torch.get_rng_state())


def test_genuine_native119_shared_h0_cache_and_input_drift(tmp_path):
    from phychem_mfm.factory import build_model
    from formal_readout import prepare_h0_cache, NativeH0Cache
    protocol = json.loads(Path(os.environ["PHASE1_FORMAL_PROTOCOL_PATH"]).read_bytes())
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(0)
        model = build_model(deepcopy(protocol["model"]))
    fit, store, _, _, samples = fixture()
    # This test's three native sources are deliberately a synthetic projection.
    # The real CLI requires the complete inventory; only the cache algorithm is
    # exercised below without pretending a three-member dataset is formal.
    import formal_readout
    original_count = formal_readout.INVENTORY_COUNTS["qm7"]
    formal_readout.INVENTORY_COUNTS["qm7"] = 3
    samples[0].x[0] = 117  # native118 is a real embedding class, not the padding119th row
    directory = tmp_path / "cache"
    try:
        ref = prepare_h0_cache(model, store, fit, encoder_binding={"fixture": "real_shared119"},
            store_binding={"fixture": "synthetic_native_inputs"}, directory=directory,
            cache_cap_bytes=4 << 20, max_atoms_per_forward=16, wall_check=lambda: None)
        cache = NativeH0Cache(directory, expected_catalog_sha256=ref["catalog_sha256"],
            encoder_binding={"fixture": "real_shared119"}, store_binding={"fixture": "synthetic_native_inputs"}, dataset_id="qm7")
    finally:
        formal_readout.INVENTORY_COUNTS["qm7"] = original_count
    try:
        assert cache.get(samples[0]).shape == (2, 384)
        assert cache.get(samples[0]).dtype == torch.float32
        samples[0].pos[0, 0] = 1.
        with pytest.raises(FormalReadoutError, match="drift"):
            cache.get(samples[0])
    finally:
        cache.close()


def test_actual_physical_readout_config_and_protocol_bindings_are_required(tmp_path):
    from formal_readout import _make_readout, validate_readout_binding
    fit, store, _, contract, _ = fixture(directory=tmp_path)
    readout = _make_readout(fit, "cpu")
    assert validate_readout_binding(contract, fit, readout)["config_sha256"] == digest(readout.config_dict())
    bad = deepcopy(contract)
    bad["readout_binding"]["main"]["config"]["input_dim"] = 512
    with pytest.raises(FormalReadoutError, match="configuration"):
        validate_readout_binding(bad, fit, readout)
    # Preserve the original complete inventory requirement and assert the
    # protocol guard before a synthetic three-member cardinality is examined.
    bad = deepcopy(contract); bad["protocol_content_sha256"] = "b" * 64
    store.contract = lambda dataset, fold: deepcopy(bad)
    with pytest.raises(FormalReadoutError, match="protocol"):
        validate_store_group(store, fit)


def test_cached_batches_do_not_rebuild_large_original_role_views():
    from formal_readout import role_members, cached_batch
    fit, store, cache, contract, _ = fixture()
    calls = 0
    original = store.view
    def view(dataset, fold, role):
        nonlocal calls
        calls += 1
        return original(dataset, fold, role)
    store.view = view
    indices, lookup = role_members(store, fit, contract, "train")
    for _ in range(4):
        batch = cached_batch(store, cache, fit, indices, role="train", role_uid_lookup=lookup, device="cpu")
        assert batch["member_uids"] == ("train",)
    assert calls == 1
