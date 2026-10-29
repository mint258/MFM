"""Source-format fixtures, not native data or scientific checkpoint acceptance.

One module-level actual 6x512 saver artifact is shared. Negative cases mutate
small metadata/in-memory views and never persist another full checkpoint.
"""
from copy import deepcopy
from dataclasses import asdict, replace
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest
from model_v3_fixture_lifecycle import own_module_directory

pytest_plugins = ("model_v3_fixture_lifecycle",)
import torch
from torch_geometric.data import Batch, Data

from phychem_mfm.model.v3_multiview import V3MultiViewModel
from phychem_mfm.model.v3_performance import PerformanceOptions, build_performance_model
from phychem_mfm.phase1.v3_contract import canonical_hash
from phychem_mfm.phase1.v3_dev_panel import canonical
from phychem_mfm.phase1.v3_encoder_bridge import EncoderBindingError, load_encoder_pair, _strict_state
from phychem_mfm.phase1.v3_native_checkpoint_bridge import (
    NATIVE_SCOPE, NativeCheckpointError, native_checkpoint_state, native_member_contract)
from phychem_mfm.phase1.v3_native_s_precision import NativeSPrecisionPlan
from phychem_mfm.phase1.v3_native_s_precision_data import source_registry
from phychem_mfm.phase1.v3_trainer import _execution_state
from phychem_mfm.phase1.v3_training import SampleClock, save_new_checkpoint, capture_rng_state, restore_rng_state

ROOT = Path(__file__).absolute().parents[2]


def binding(path):
    return {"path": str(path), "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def json_file(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2)+"\n")
    return binding(path)


def common(contract):
    specific = {"seed", "precision", "input_binding", "sampler_contract_sha256", "execution"}
    return {k: v for k, v in contract.items() if k not in specific}


class UnitSampler:
    samples_consumed = 6
    def state_dict(self):
        return {"samples_consumed": 6, "contract_sha256": "d"*64}


@pytest.fixture(scope="module")
def native(tmp_path_factory, request):
    owned = own_module_directory(request, tmp_path_factory, "native_bridge_one_checkpoint")
    root = owned.path
    rng, threads = capture_rng_state(), torch.get_num_threads()
    torch.set_num_threads(1)
    try:
        cfg = deepcopy(json.loads((ROOT / "workflows/s_denoise/configs/A4_seed0_v3.json").read_text())["model"])
        cfg["backbone"].update(dim=512, layers=6, heads=8, activation_checkpointing=True, dropout=0.0)
        cfg["expert"]["heads"] = 8
        options = PerformanceOptions(precision="fp32", backbone_checkpointing=True)
        torch.manual_seed(0)
        encoder = build_performance_model(cfg, options)
        registry, structural = source_registry("e"*64)
        model = V3MultiViewModel(encoder, None, registry, structural)
        sources = {"current/phychem_mfm/"+path.relative_to(ROOT / "current/phychem_mfm").as_posix():
                   hashlib.sha256(path.read_bytes()).hexdigest()
                   for path in (ROOT / "current/phychem_mfm/model").rglob("*.py")}
        for name in ("config.py", "factory.py", "phase1/v3_native_s_precision.py",
                     "phase1/v3_native_s_precision_data.py", "phase1/v3_training.py", "phase1/v3_contract.py",
                     "data/descriptor_schema.py", "supervision.py"):
            sources["current/phychem_mfm/"+name] = hashlib.sha256((ROOT / "current/phychem_mfm" / name).read_bytes()).hexdigest()
        contract = {"plan": asdict(NativeSPrecisionPlan()), "source_files": sources,
            "code_sha": "a"*40, "prereg_sha": "b"*40, "data_version": "e"*64,
            "registry": registry.content_sha256, "model": cfg,
            "loss_weights": {},
            "loss_semantics": "V3_S_mean_of_observed_original_raw_fields; not_legacy_weighted_total",
            "schedule": {}, "runtime": {}, "Root_storage_policy": {},
            "base_options": asdict(options), "source_scope": NATIVE_SCOPE,
            "validation_role": "PRETRAIN_VAL", "validation_seed": 0, "validation_epoch": 0,
            "D5_authority": False, "TRAIN_UNSEEN_CONFORMATION": "NOT_PROVIDED",
            "seed": 0, "precision": "fp32", "input_binding": {"unit_fixture": True},
            "sampler_contract_sha256": "d"*64, "execution": _execution_state(model)}
        bindings = {"code_sha": contract["code_sha"], "configuration_sha256": canonical_hash(contract),
            "registry_sha256": registry.source_sha256, "normalization_sha256": canonical_hash({}),
            "data_version": contract["data_version"], "source_inventory_sha256": canonical_hash(sources)}
        extra = {"contract": contract, "scheduler": {}, "points": {}, "saved_updates": [2],
                 "log_cursor": 3, "input_chain": "f"*64, "tracker": {"id": "unit-only"},
                 "model_training": model.training, "dtype_observations": {}}
        clock = SampleClock(contract["plan"]["sample_budget"], (), samples_consumed=6, optimizer_updates=2)
        directory = root / "checkpoint"
        marker = save_new_checkpoint(directory, output_root=root, model=model,
            optimizer=torch.optim.AdamW(model.parameters()), sampler=UnitSampler(), clock=clock,
            bindings=bindings, extra_state=extra)
        # Actual save_new_checkpoint readback is required, with no unsafe fallback.
        payload = torch.load(directory / "payload.pt", map_location="cpu", weights_only=True)
        member = {"schema": "existing_native_S_precision_member_v1", "status": "SEGMENT_PAUSED",
            "scope": NATIVE_SCOPE, "seed": 0, "precision": "fp32", "D5_authority": False,
            "scientific_acceptance": False, "optimizer_updates": 2, "samples_consumed": 6,
            "training_input_chain_sha256": "f"*64, "member_contract": contract,
            "common_binding": common(contract), "tracker": {"id": "unit-only"}}
        config_ref = json_file(root / "member_result.json", member)
        # Exercise actual producer tuple -> original saved JSON list transport.
        member = json.loads(Path(config_ref["path"]).read_text())
        assert isinstance(payload["extra_state"]["contract"]["plan"]["checkpoint_updates"], tuple)
        assert isinstance(member["member_contract"]["plan"]["checkpoint_updates"], list)
        fixture = {"root": root, "model": model, "config": cfg, "member": member, "payload": payload,
                "marker": marker, "config_ref": config_ref, "checkpoint_ref": binding(directory / "payload.pt"),
                "complete_ref": binding(directory / "COMPLETE.json")}
    finally:
        torch.set_num_threads(threads)
        restore_rng_state(rng)
    # Preserve original setup-time RNG/thread restoration before exposing data.
    try:
        yield fixture
    finally:
        owned.fixture_closed()


def load(fixture, **kwargs):
    return load_encoder_pair(fixture["checkpoint_ref"], fixture["config_ref"],
        architecture_sha256=canonical(fixture["config"]), pretraining_seed=0,
        training_completion=fixture["complete_ref"], **kwargs)


def pieces(fixture):
    payload = dict(fixture["payload"])
    for key in ("bindings", "clock", "sampler", "extra_state"):
        payload[key] = deepcopy(payload[key])
    payload["model"] = dict(payload["model"])
    return payload, deepcopy(fixture["member"]), deepcopy(fixture["marker"])


def validate(fixture, payload, member, marker):
    return native_checkpoint_state(payload, member, marker,
                                   fixture["checkpoint_ref"], fixture["checkpoint_ref"]["bytes"])


def test_real_saver_native_bridge_source_H0_and_matched_random(native):
    rng = torch.get_rng_state().clone()
    pair = load(native, expected_state_key="model")
    assert torch.equal(torch.get_rng_state(), rng)
    data = Batch.from_data_list([
        Data(x=torch.tensor([[5], [0], [0]]), pos=torch.tensor([[0., 0., 0.], [1., 0., 0.], [0., 1., 0.]])),
        Data(x=torch.tensor([[7], [0]]), pos=torch.tensor([[0., 0., 0.], [0., 0., 1.]]))])
    with torch.inference_mode():
        source = native["model"].encoder.eval().encode_atoms(data)
        actual = pair.candidate.encode_atoms(data)
    assert actual.shape == (5, 512) and actual.dtype == torch.float32 and torch.equal(actual, source)
    assert pair.candidate.config_dict() == pair.random_reference.config_dict()
    assert pair.candidate.v3_performance_options == pair.random_reference.v3_performance_options
    assert pair.candidate.v3_performance_options == native["member"]["member_contract"]["base_options"]
    assert pair.provenance["checkpoint_schema"] == "model_v3_native_S_immutable_checkpoint"
    assert pair.provenance["checkpoint_encoder_state_sha256"] != pair.provenance["random_encoder_state_sha256"]
    assert pair.provenance["native_checkpoint"]["samples_consumed"] == 6
    assert pair.provenance["native_checkpoint"]["scientific_acceptance"] is False
    assert pair.provenance["native_checkpoint"]["pretraining_seed_SD_claimed"] is False
    assert pair.provenance["downstream_target_records_read"] == 0


def test_existing_request_entry_binds_member_result_and_COMPLETE(native, tmp_path):
    path = ROOT / "tools/model_v3/prepare_dev_evaluation.py"
    spec = importlib.util.spec_from_file_location("unit_native_prepare", path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    panel = tmp_path / "panel.json"; store = tmp_path / "store.json"
    json_file(panel, {"unit_metadata_only": True}); json_file(store, {"unit_metadata_only": True})
    request = module.make_request(panel=panel, training_store=store,
        model_configuration=native["config_ref"]["path"], checkpoint=native["checkpoint_ref"]["path"],
        training_completion=native["complete_ref"]["path"], code_sha="c"*40,
        preregistration_sha="d"*40, data_version="unit_store_not_pretraining_data", pretraining_seed=0,
        output_root=tmp_path / "result", cache_root=tmp_path / "result/cache", run_id="unit_native_S",
        state_key="model", source_files=["current/phychem_mfm/phase1/v3_encoder_bridge.py"])
    assert request["training_completion"]["sha256"] == native["complete_ref"]["sha256"]
    assert request["model_configuration"]["sha256"] == native["config_ref"]["sha256"]
    assert request["architecture_sha256"] == canonical(native["config"])
    assert request["pretraining_seed"] == 0 and "enable_architecture_candidates" not in request


def test_native_completion_is_required(native):
    with pytest.raises(EncoderBindingError):
        load_encoder_pair(native["checkpoint_ref"], native["config_ref"],
            architecture_sha256=canonical(native["config"]), pretraining_seed=0)


def test_native_completion_cannot_be_detached(native, tmp_path):
    marker = json_file(tmp_path / "COMPLETE.json", native["marker"])
    with pytest.raises(EncoderBindingError):
        load_encoder_pair(native["checkpoint_ref"], native["config_ref"],
            architecture_sha256=canonical(native["config"]), pretraining_seed=0, training_completion=marker)


@pytest.mark.parametrize("case", ["sha", "bytes", "bindings", "clock", "bool_cursor", "sampler", "input_chain",
                                   "clock_schema", "saved_updates", "tracker"])
def test_marker_payload_and_committed_cursor_rejects(native, case):
    p, m, h = pieces(native)
    if case == "sha": h["payload_sha256"] = "0"*64
    elif case == "bytes": h["payload_bytes"] += 1
    elif case == "bindings": p["bindings"]["data_version"] = "0"*64
    elif case == "clock": p["clock"]["optimizer_updates"] += 1
    elif case == "bool_cursor": h["samples_consumed"] = True
    elif case == "sampler": p["sampler"]["samples_consumed"] += 1
    elif case == "input_chain": p["extra_state"]["input_chain"] = "0"*64
    elif case == "clock_schema": p["clock"]["schema"] = "foreign_clock"
    elif case == "saved_updates": p["extra_state"]["saved_updates"] = []
    else: p["extra_state"]["tracker"] = {"id": "foreign"}
    with pytest.raises(NativeCheckpointError): validate(native, p, m, h)


@pytest.mark.parametrize("case", ["seed", "geometry", "scope", "D5", "execution_precision"])
def test_member_semantics_cannot_be_inferred_from_shapes(native, case):
    p, m, h = pieces(native)
    if case == "seed": m["seed"] = 1
    elif case == "geometry":
        m["member_contract"]["model"]["head"]["geometry_radius"] = 5.25
        m["common_binding"] = common(m["member_contract"])
    elif case == "scope": m["scope"] = "synthetic_native_fixture"
    elif case == "D5": m["D5_authority"] = True
    else:
        m["precision"] = m["member_contract"]["precision"] = "bf16"
        # Rebind legitimate metadata, but preserve the inconsistent FP32
        # training execution options. The producer cannot emit this relation.
        m["common_binding"] = common(m["member_contract"])
        p["extra_state"]["contract"] = deepcopy(m["member_contract"])
        p["bindings"]["configuration_sha256"] = canonical_hash(m["member_contract"])
        h["bindings"] = dict(p["bindings"])
    with pytest.raises(NativeCheckpointError): validate(native, p, m, h)


@pytest.mark.parametrize("case", ["namespace", "missing", "dtype", "bf16_storage", "nonfinite"])
def test_encoder_namespace_keys_and_tensor_contract_are_strict(native, case):
    p, m, h = pieces(native)
    key = next(k for k, v in p["model"].items() if isinstance(v, torch.Tensor) and v.is_floating_point())
    if case == "namespace":
        p["model"]["pd_heads.forbidden"] = torch.ones(1)
        with pytest.raises(NativeCheckpointError): validate(native, p, m, h)
        return
    if case == "missing": del p["model"][key]
    elif case == "dtype": p["model"][key] = p["model"][key].to(torch.float16)
    elif case == "bf16_storage": p["model"][key] = p["model"][key].to(torch.bfloat16)
    else:
        p["model"][key] = p["model"][key].clone(); p["model"][key].reshape(-1)[0] = float("nan")
    state, _, _ = validate(native, p, m, h)
    with pytest.raises(EncoderBindingError): _strict_state(native["model"].encoder, state)


@pytest.mark.parametrize("case", ["implementation", "performance", "base_precision"])
def test_resealed_contract_cannot_substitute_known_producer_semantics(native, case):
    p, m, h = pieces(native)
    contract = m["member_contract"]
    if case == "implementation": contract["source_files"]["current/phychem_mfm/factory.py"] = "0"*64
    elif case == "base_precision":
        contract["base_options"]["precision"] = "bf16"
    else:
        contract["base_options"]["distance_pair_rows"] += 1
        contract["execution"]["performance_options"]["encoder"]["distance_pair_rows"] += 1
    m["common_binding"] = common(contract)
    p["extra_state"]["contract"] = deepcopy(contract)
    p["bindings"]["configuration_sha256"] = canonical_hash(contract)
    p["bindings"]["source_inventory_sha256"] = canonical_hash(contract["source_files"])
    h["bindings"] = dict(p["bindings"])
    with pytest.raises(NativeCheckpointError): validate(native, p, m, h)


class UnsafeNativeFixture:
    pass


def test_native_weights_only_boundary_has_no_pickle_fallback(native, tmp_path):
    directory = tmp_path / "unsafe"; directory.mkdir()
    path = directory / "payload.pt"; torch.save({"unsafe": UnsafeNativeFixture()}, path)
    with pytest.raises(EncoderBindingError, match="weights-only"):
        load_encoder_pair(binding(path), native["config_ref"], architecture_sha256=canonical(native["config"]),
            pretraining_seed=0, training_completion=native["complete_ref"])


def test_native_payload_ref_SHA_is_checked_before_safe_load(native):
    changed = {**native["checkpoint_ref"], "sha256": "0"*64}
    with pytest.raises(EncoderBindingError, match="Source file bytes"):
        load_encoder_pair(changed, native["config_ref"], architecture_sha256=canonical(native["config"]),
            pretraining_seed=0, training_completion=native["complete_ref"])


def test_native_registry_source_cannot_be_rebound_without_the_producer(native):
    p, m, h = pieces(native)
    p["bindings"]["registry_sha256"] = "0"*64
    h["bindings"] = dict(p["bindings"])
    with pytest.raises(NativeCheckpointError):
        validate(native, p, m, h)


@pytest.fixture(scope="module")
def bf16_native(native, tmp_path_factory, request):
    """BF16 producer metadata/FP32 storage; no BF16 forward or training claim."""
    owned = own_module_directory(request, tmp_path_factory, "native_bridge_bf16_one_checkpoint")
    root = owned.path
    rng, threads = capture_rng_state(), torch.get_num_threads()
    torch.set_num_threads(1)
    try:
        contract = deepcopy(native["payload"]["extra_state"]["contract"])
        options = replace(PerformanceOptions(**contract["base_options"]), precision="bf16")
        encoder = build_performance_model(native["config"], options)
        encoder.load_state_dict(native["model"].encoder.state_dict(), strict=True)
        registry, structural = source_registry(contract["data_version"])
        model = V3MultiViewModel(encoder, None, registry, structural)
        contract.update(precision="bf16", execution=_execution_state(model))
        bindings = dict(native["marker"]["bindings"])
        bindings["configuration_sha256"] = canonical_hash(contract)
        extra = deepcopy(native["payload"]["extra_state"])
        extra["contract"] = contract
        directory = root / "checkpoint"
        save_new_checkpoint(directory, output_root=root, model=model,
            optimizer=torch.optim.AdamW(model.parameters()), sampler=UnitSampler(),
            clock=SampleClock(contract["plan"]["sample_budget"], (), samples_consumed=6, optimizer_updates=2),
            bindings=bindings, extra_state=extra)
        member = deepcopy(native["member"])
        member.update(precision="bf16", member_contract=contract, common_binding=common(contract))
        config_ref = json_file(root / "member_result.json", member)
        fixture = {"model": model, "config": native["config"], "config_ref": config_ref,
                "complete_ref": binding(directory / "COMPLETE.json"),
                "checkpoint_ref": binding(directory / "payload.pt")}
    finally:
        torch.set_num_threads(threads)
        restore_rng_state(rng)
    # Same original restoration timing; cleanup awaits every module report.
    try:
        yield fixture
    finally:
        owned.fixture_closed()


def test_bf16_source_checkpoint_exports_declared_FP32_H0_without_mutation(bf16_native, native, tmp_path):
    from phychem_mfm.phase1.v3_dev_panel import FrozenH0Cache, NativeGeometry
    before = deepcopy(bf16_native["model"].encoder.v3_performance_options)
    pair = load(bf16_native, expected_state_key="model")
    assert before["precision"] == "bf16"
    assert bf16_native["model"].encoder.v3_performance_options == before
    assert pair.candidate.v3_performance_options == pair.random_reference.v3_performance_options
    assert pair.candidate.v3_performance_options["precision"] == "fp32"
    assert all(p.dtype == torch.float32 for p in pair.candidate.parameters())
    meta = pair.provenance["native_checkpoint"]
    assert meta["pretraining_precision"] == meta["pretraining_performance_options"]["precision"] == "bf16"
    assert meta["H0_export_performance_options"]["precision"] == "fp32"
    assert meta["BF16_training_forward_bitwise_replay_claimed"] is False
    records = (NativeGeometry("synthetic", "unit:0", 0,
        torch.tensor([[5], [0], [0]]), torch.tensor([[0., 0., 0.], [1., 0., 0.], [0., 1., 0.]]),
        torch.tensor([0, 1, 2])),)
    batch = Batch.from_data_list([Data(x=r.x, pos=r.pos) for r in records])
    with torch.inference_mode():
        expected = native["model"].encoder.eval().encode_atoms(batch)
        actual = pair.candidate.encode_atoms(batch)
    assert actual.dtype == torch.float32 and torch.equal(actual, expected)
    cache = FrozenH0Cache(tmp_path / "cache", repository_root=ROOT)
    with torch.autocast("cpu", dtype=torch.bfloat16):
        rows, census = cache.get_or_compute(pair.candidate, records,
            architecture_sha256=canonical(native["config"]), membership_sha256="a"*64,
            execution_source={"loader": pair.provenance["loader_implementation"],
                              "checkpoint": pair.provenance["checkpoint"],
                              "native_checkpoint": meta}, max_graphs=1)
    assert rows[0].h0.dtype == torch.float32 and torch.equal(rows[0].h0, expected)
    assert census["binding"]["effective_runtime"]["H0_output_dtype"] == "torch.float32"


def reseal_metadata(payload, member, marker):
    contract = member["member_contract"]
    member["common_binding"] = common(contract)
    payload["extra_state"]["contract"] = deepcopy(contract)
    payload["bindings"]["configuration_sha256"] = canonical_hash(contract)
    payload["bindings"]["source_inventory_sha256"] = canonical_hash(contract["source_files"])
    marker["bindings"] = dict(payload["bindings"])


@pytest.mark.parametrize("case", ["updates", "sample_budget", "validation_grid"])
def test_resealed_plan_still_requires_the_original_native_policy(native, case):
    p, m, h = pieces(native)
    plan = m["member_contract"]["plan"]
    if case == "updates": plan["updates"] = 19000
    elif case == "sample_budget": plan["sample_budget"] += 1
    else: plan["validation_updates"] = [0, 20000]
    reseal_metadata(p, m, h)
    with pytest.raises(NativeCheckpointError): validate(native, p, m, h)


@pytest.mark.parametrize("field", ["seed", "validation_seed", "validation_epoch"])
def test_bool_cannot_impersonate_an_integer_contract_zero(native, field):
    p, m, h = pieces(native)
    m["member_contract"][field] = False
    reseal_metadata(p, m, h)
    with pytest.raises(NativeCheckpointError): validate(native, p, m, h)


@pytest.mark.parametrize("case", ["sampler_contract", "input_chain"])
def test_missing_both_sides_is_not_a_valid_SHA_match(native, case):
    p, m, h = pieces(native)
    if case == "sampler_contract":
        del p["sampler"]["contract_sha256"]
        del m["member_contract"]["sampler_contract_sha256"]
        reseal_metadata(p, m, h)
    else:
        del p["extra_state"]["input_chain"]
        del m["training_input_chain_sha256"]
    with pytest.raises(NativeCheckpointError): validate(native, p, m, h)


def test_active_common_source_cannot_be_omitted_from_resealed_inventory(native):
    p, m, h = pieces(native)
    del m["member_contract"]["source_files"]["current/phychem_mfm/model/common.py"]
    reseal_metadata(p, m, h)
    with pytest.raises(NativeCheckpointError): validate(native, p, m, h)


def evaluator_module():
    path = ROOT / "tools/model_v3/evaluate_dev_panel.py"
    spec = importlib.util.spec_from_file_location("unit_native_evaluator", path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def test_actual_cache_source_binds_helper_projection_and_complete(native, tmp_path):
    from phychem_mfm.phase1.v3_dev_panel import FrozenH0Cache, NativeGeometry
    pair = load(native)
    request = {"code_sha": "c"*40, "source_files": [{"path": "unit", "sha256": "b"*64}],
               "model_configuration": native["config_ref"]}
    module = evaluator_module()
    source = module.h0_execution_source(request, pair.provenance)
    assert source["native_checkpoint"] == pair.provenance["native_checkpoint"]
    assert source["training_completion"] == native["complete_ref"]
    records = (NativeGeometry("synthetic", "cache:0", 0, torch.tensor([[5], [0]]),
        torch.tensor([[0., 0., 0.], [1., 0., 0.]]), torch.tensor([0, 1])),)
    variants = [deepcopy(pair.provenance) for _ in range(4)]
    # Fingerprint contrast only; modified metadata is not a new accepted reader
    # or a new completed checkpoint. Admission tests above reject such forgeries.
    variants[1]["native_checkpoint"]["bridge_implementation"] = pair.provenance["loader_implementation"]
    variants[2]["native_checkpoint"]["H0_export_precision"] += "_different_mapping"
    variants[3]["training_completion"]["sha256"] = "0"*64
    cache, keys = FrozenH0Cache(tmp_path / "cache", repository_root=ROOT), []
    for provenance in variants:
        _, metadata = cache.get_or_compute(pair.candidate, records,
            architecture_sha256=canonical(native["config"]), membership_sha256="a"*64,
            execution_source=module.h0_execution_source(request, provenance), max_graphs=1)
        keys.append(metadata["cache_key"])
    assert len(set(keys)) == 4  # Distinct identities create new entries; no claimed rejection.
    legacy = dict(pair.provenance); del legacy["native_checkpoint"]
    assert "native_checkpoint" not in module.h0_execution_source(request, legacy)
    assert "training_completion" not in module.h0_execution_source(request, legacy)


@pytest.mark.parametrize("case", ["missing_COMPLETE", "noncanonical"])
def test_native_cache_source_requires_complete_and_finite_JSON(native, case):
    pair = load(native)
    request = {"code_sha": "c"*40, "source_files": [], "model_configuration": native["config_ref"]}
    provenance = deepcopy(pair.provenance)
    if case == "missing_COMPLETE": del provenance["training_completion"]
    else: provenance["native_checkpoint"]["invalid"] = float("nan")
    with pytest.raises(ValueError): evaluator_module().h0_execution_source(request, provenance)


@pytest.mark.parametrize("case", ["updates_exceed_samples", "log_cursor_behind_updates", "future_saved_update"])
def test_impossible_native_committed_ack_relationships_reject(native, case):
    p, m, h = pieces(native)
    if case == "updates_exceed_samples":
        p["clock"]["samples_consumed"] = p["sampler"]["samples_consumed"] = 1
        m["samples_consumed"] = h["samples_consumed"] = 1
    elif case == "log_cursor_behind_updates": p["extra_state"]["log_cursor"] = 1
    else: p["extra_state"]["saved_updates"] = [2, 3]
    with pytest.raises(NativeCheckpointError): validate(native, p, m, h)
