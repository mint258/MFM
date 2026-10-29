"""Engineering-only CP/H0 tests; actual collection and execution are Root-owned.

One module-shared 6x512 CP is produced by the real sampler/provider/trainer and
immutable saver through two real fresh CLI processes, resume and outbox.
Metadata mutations reuse that fixture without writing copied large weights.
"""
from copy import deepcopy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from model_v3_fixture_lifecycle import own_module_directory

pytest_plugins = ("model_v3_fixture_lifecycle",)
import torch
from torch_geometric.data import Batch, Data

from test_model_v3_trainer import UnitTracker
from test_model_v3_training_entry import run_cli_pair
from test_model_v3_sample_budget import fake_result_and_evidence
from test_model_v3_training import assert_tree_equal
from phychem_mfm.phase1 import v3_proxy_run as proxy
from phychem_mfm.phase1.v3_contract import canonical_hash
from phychem_mfm.phase1.v3_proxy_segments import BoundedLineageController
from phychem_mfm.phase1.v3_dev_panel import FrozenH0Cache, NativeGeometry, encoder_state_sha256
from phychem_mfm.phase1.v3_encoder_bridge import EncoderBindingError, _strict_state, load_encoder_pair
from phychem_mfm.phase1.v3_execution_checkpoint_bridge import (
    ExecutionCheckpointError, execution_checkpoint_state, validate_h0_export_capability,
    training_execution_cache_projection)
from phychem_mfm.phase1.v3_sample_budget_events import binding, read_bound, write_once
from phychem_mfm.phase1.v3_training import capture_rng_state

ROOT = Path(__file__).absolute().parents[2]
BASE = "81948e457c29fbc51687066a4f944ff5bcd5bad5"
POLICY = {
    "options": {"backbone_checkpointing": True},
    "batch_padded_cost": 10000,
    "padding": {"atom_bucket_width": 2, "max_graphs_per_chunk": 2,
                "max_padded_cost_per_chunk": 128},
}


@pytest.fixture(scope="module", autouse=True)
def fixed_cpu_context():
    threads, precision = torch.get_num_threads(), torch.get_float32_matmul_precision()
    matmul, cudnn = torch.backends.cuda.matmul.allow_tf32, torch.backends.cudnn.allow_tf32
    cudnn_deterministic, cudnn_benchmark = torch.backends.cudnn.deterministic, torch.backends.cudnn.benchmark
    deterministic = torch.are_deterministic_algorithms_enabled()
    warn_only = torch.is_deterministic_algorithms_warn_only_enabled()
    torch.set_num_threads(1)
    torch.set_float32_matmul_precision("highest")
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    torch.use_deterministic_algorithms(True)
    try:
        yield
    finally:
        torch.set_num_threads(threads)
        torch.set_float32_matmul_precision(precision)
        torch.backends.cuda.matmul.allow_tf32 = matmul
        torch.backends.cudnn.allow_tf32 = cudnn
        torch.backends.cudnn.deterministic = cudnn_deterministic
        torch.backends.cudnn.benchmark = cudnn_benchmark
        torch.use_deterministic_algorithms(deterministic, warn_only=warn_only)


@pytest.fixture(scope="module")
def committed(tmp_path_factory, fixed_cpu_context, request):
    owned = own_module_directory(request, tmp_path_factory, "execution-H0-one-real-6x512-CLI-family")
    root = owned.path
    case = run_cli_pair(root, layers=6, training_execution=deepcopy(POLICY), budget=3)
    request, configuration = case["request"], case["configuration"]
    _, plan, _ = proxy.validate_request(request, input_kind="synthetic", engineering_only=True)
    inputs = proxy.bind_inputs(request, configuration)
    # Restore the genuine producer implementation from the final CLI CP.
    # This is a saved-state numerical control, not a pre-save observation.
    experiment = proxy.build_experiment(
        request, configuration, plan, inputs, UnitTracker("execution-H0-restored-engineering"),
        output_root=root / "restored/training", lineage_root=case["lineage_root"],
        lineage=case["lineage"], device="cpu", allow_unit_tracker=True)
    event = case["event"]
    trainer_directory = case["trainer_checkpoint_directory"]
    experiment.trainer.load(trainer_directory, output_root=trainer_directory.parent)
    assert case["first_result"]["outcome"]["optimizer_updates"] > 0
    assert (case["second_result"]["outcome"]["optimizer_updates"]
            > case["first_result"]["outcome"]["optimizer_updates"])
    assert experiment.trainer.optimizer.state
    assert event["status"] == "READY" and event["data_authority_asserted"] is False
    assert experiment.trainer.clock.samples_consumed == 3
    graph = Batch.from_data_list([
        Data(x=torch.tensor([[5]]), pos=torch.tensor([[.25, .5, -.25]])),
        Data(x=torch.tensor([[5], [0], [7], [6], [5]]),
             pos=torch.tensor([[0., 0., 0.], [.7, 0., .1], [.2, .8, 0.],
                               [.1, .3, .9], [.8, .8, .4]])),
        Data(x=torch.tensor([[6], [5]]), pos=torch.tensor([[.2, .1, .2], [1., .3, .4]])),
    ])
    experiment.trainer.model.eval()
    with torch.no_grad():
        expected_h0 = experiment.trainer.model.encoder.encode_atoms(graph).clone()
    payload = torch.load(event["checkpoint"]["path"], map_location="cpu", weights_only=True)
    try:
        yield {**case, "experiment": experiment, "graph": graph,
               "expected_h0": expected_h0, "payload": payload}
    finally:
        inputs.provider.close()
        owned.fixture_closed()

def pair_for(case, **overrides):
    event = case["event"]
    arguments = dict(
        architecture_sha256=event["architecture_sha256"],
        pretraining_seed=event["pretraining_seed"],
        training_completion=event["training_completion"],
        enable_architecture_candidates=True, enable_training_execution=True)
    arguments.update(overrides)
    return load_encoder_pair(event["checkpoint"], event["model_configuration"], **arguments)


def metadata_copy(case):
    # Do not duplicate optimizer/model tensors or write another large payload.
    payload = dict(case["payload"])
    payload["extra_state"] = deepcopy(payload["extra_state"])
    payload["clock"] = deepcopy(payload["clock"])
    payload["sampler"] = deepcopy(payload["sampler"])
    return payload, deepcopy(case["configuration"])


def module_from_tool(name):
    spec = importlib.util.spec_from_file_location(
        "execution_H0_unit_" + name, ROOT / "tools/model_v3" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_real_6x512_CLI_resume_checkpoint_exports_same_restored_producer_H0(committed):
    provider = committed["experiment"].trainer.provider
    before_rng, before_provider = capture_rng_state(), deepcopy(provider.state_dict())
    pair = pair_for(committed)
    with torch.no_grad():
        actual = pair.candidate.encode_atoms(committed["graph"])
    assert torch.equal(actual, committed["expected_h0"])
    assert actual.dtype == torch.float32 and actual.shape == (8, 512)
    assert pair.provenance["checkpoint_schema"] == "model_v3_immutable_sample_checkpoint"
    assert pair.provenance["training_completion"] == committed["event"]["training_completion"]
    assert pair.provenance["training_execution"]["training_capacity_reused_for_downstream_H0"] is False
    assert pair.provenance["downstream_target_records_read"] == 0
    assert_tree_equal(before_rng, capture_rng_state())
    assert_tree_equal(before_provider, provider.state_dict())


def test_candidate_and_matched_random_use_one_export_path_without_cuda_seed_side_effect(committed, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("CPU export must not mutate or queue CUDA initialization seeds")
    monkeypatch.setattr(torch.cuda, "manual_seed_all", forbidden)
    before = capture_rng_state()
    left, right = pair_for(committed), pair_for(committed)
    assert encoder_state_sha256(left.random_reference) == encoder_state_sha256(right.random_reference)
    assert encoder_state_sha256(left.candidate) != encoder_state_sha256(left.random_reference)
    assert not ({id(p) for p in left.candidate.parameters()}
                & {id(p) for p in left.random_reference.parameters()})
    assert left.candidate.config_dict() == left.random_reference.config_dict()
    assert left.provenance["random_reference_seed"] == 20261025
    assert left.candidate.training_h0_export_contract == left.random_reference.training_h0_export_contract
    for model in (left.candidate, left.random_reference):
        assert all(value.dtype == torch.float32 for value in (*model.parameters(), *model.buffers())
                   if value.is_floating_point())
    assert_tree_equal(before, capture_rng_state())


def test_capability_is_metadata_only_and_uses_the_actual_shared_adapter(committed, monkeypatch):
    from phychem_mfm.phase1 import v3_training_execution as adapter
    def forbidden(*args, **kwargs):
        raise AssertionError("Metadata capability must not construct a model")
    monkeypatch.setattr(adapter, "build_h0_export_encoder", forbidden)
    contract = committed["payload"]["extra_state"]["contract"]["training_execution"]
    result = validate_h0_export_capability(committed["configuration"]["model"], contract)
    assert result["supported"] is True and result["H0_dimension"] == 512
    assert result["training_execution_contract_sha256"] == canonical_hash(contract)
    assert result["downstream_capacity_authority"] is False and result["scientific_acceptance"] is False


def test_minimal_original_execution_request_is_normalized_by_the_one_adapter(committed):
    payload, configuration = metadata_copy(committed)
    configuration["training_execution"] = deepcopy(POLICY)
    _, _, provenance = execution_checkpoint_state(payload, configuration)
    assert provenance["training_contract"]["requested_execution"] != POLICY
    assert provenance["H0_export"]["precision"] == "fp32"


@pytest.mark.parametrize("flag", [False, 1, "true"])
def test_new_sample_checkpoint_cannot_use_a_plain_or_untyped_opt_in(committed, flag):
    with pytest.raises(EncoderBindingError):
        pair_for(committed, enable_training_execution=flag)


@pytest.mark.parametrize("case", [
    "missing_contract", "missing_saved_contract", "runtime_flags", "source_digest",
    "unknown_map", "map_precision", "wrong_model", "request_policy", "bool_seed",
    "bool_samples", "bool_milestone", "bool_saved_milestone", "clock_schema",
    "sampler_schema", "missing_sampler_sha", "sampler_cursor",
    "scheduler_cursor", "scheduler_binding", "source_budget", "source_milestones",
    "pending_log", "missing_pending_log", "log_cursor", "declared_deterministic",
])
def test_changed_or_incomplete_execution_and_committed_metadata_reject(committed, case):
    payload, configuration = metadata_copy(committed)
    extra = payload["extra_state"]
    contract = extra["contract"]["training_execution"]
    if case == "missing_contract":
        del extra["contract"]["training_execution"]
    elif case == "missing_saved_contract":
        del extra["execution"]["training_execution"]
    elif case == "runtime_flags":
        flags = extra["execution"]["resolved_checkpoint_flags"]
        path = next(iter(flags))
        key = next(iter(flags[path]))
        flags[path][key] = not flags[path][key]
    elif case == "source_digest":
        sources = contract["implementation_sha256"]
        sources[next(iter(sources))] = "0" * 64
    elif case == "unknown_map":
        contract["h0_export"]["builder"] = "unregistered.module.builder"
    elif case == "map_precision":
        contract["h0_export"]["precision"] = "bf16"
    elif case == "wrong_model":
        configuration["model"]["backbone"]["heads"] = 4
    elif case == "request_policy":
        configuration["training_execution"]["options"]["backbone_checkpointing"] = False
    elif case == "bool_seed":
        configuration["seed"] = True
    elif case == "bool_samples":
        payload["clock"]["samples_consumed"] = True
    elif case == "bool_milestone":
        payload["clock"]["milestones"] = [True]
    elif case == "bool_saved_milestone":
        payload["clock"]["saved_milestones"] = [True]
    elif case == "clock_schema":
        payload["clock"]["schema"] = "unknown_clock"
    elif case == "sampler_schema":
        payload["sampler"]["schema"] = "not_the_original_sampler"
    elif case == "missing_sampler_sha":
        del payload["sampler"]["contract_sha256"]
    elif case == "sampler_cursor":
        payload["sampler"]["samples_consumed"] += 1
    elif case == "scheduler_cursor":
        extra["scheduler"]["samples_consumed"] += 1
    elif case == "scheduler_binding":
        extra["scheduler"]["binding_sha256"] = "0" * 64
    elif case == "source_budget":
        configuration["proxy_contract"]["sample_budget"] += 1
    elif case == "source_milestones":
        configuration["proxy_contract"]["milestones"] = []
    elif case == "pending_log":
        extra["pending_log"] = {"uncommitted": True}
    elif case == "missing_pending_log":
        del extra["pending_log"]
    elif case == "log_cursor":
        extra["log_cursor"] = True
    elif case == "declared_deterministic":
        configuration["proxy_contract"]["execution"]["deterministic"] = False
    with pytest.raises(ExecutionCheckpointError):
        execution_checkpoint_state(payload, configuration)


@pytest.mark.parametrize("case", ["foreign_namespace", "empty_encoder", "wrong_dtype", "missing_tensor"])
def test_encoder_state_cannot_be_permissively_stripped_or_cast(committed, case):
    payload, configuration = metadata_copy(committed)
    payload["model"] = dict(payload["model"])
    if case == "foreign_namespace":
        payload["model"]["arbitrary.encoder.weight"] = torch.ones(1)
    elif case == "empty_encoder":
        payload["model"] = {k: v for k, v in payload["model"].items() if k.startswith("pd_heads.")}
    else:
        key = next(k for k, v in payload["model"].items()
                   if k.startswith("encoder.") and isinstance(v, torch.Tensor) and v.is_floating_point())
        if case == "wrong_dtype":
            payload["model"][key] = payload["model"][key].double()
        else:
            del payload["model"][key]
    if case in ("foreign_namespace", "empty_encoder"):
        with pytest.raises(ExecutionCheckpointError):
            execution_checkpoint_state(payload, configuration)
    else:
        state, builder, _ = execution_checkpoint_state(payload, configuration)
        model = builder(configuration["model"])
        with pytest.raises(EncoderBindingError):
            _strict_state(model, state)


def test_execution_cache_binds_original_COMPLETE_and_map_and_preserves_old_dictionary(committed, tmp_path):
    evaluator = module_from_tool("evaluate_dev_panel")
    pair = pair_for(committed)
    request = {"code_sha": BASE, "source_files": [{"path": "unit-engineering", "sha256": "a" * 64}],
               "model_configuration": committed["event"]["model_configuration"]}
    source = evaluator.h0_execution_source(request, pair.provenance)
    assert source["training_execution"] == training_execution_cache_projection(pair.provenance["training_execution"])
    assert "training_contract" not in source["training_execution"]
    assert source["training_completion"] == committed["event"]["training_completion"]
    old = dict(pair.provenance)
    del old["training_execution"]
    legacy = evaluator.h0_execution_source(request, old)
    assert set(legacy) == {"code_sha", "source_inventory_sha256", "configuration",
                           "loader_implementation", "historical_memory_implementation"}
    graph = committed["graph"].to_data_list()[1]
    geometries = [NativeGeometry("engineering", "one", 0, graph.x, graph.pos, torch.arange(5))]
    cache = FrozenH0Cache(tmp_path / "cache", repository_root=ROOT)
    keys = []
    for altered in (False, True):
        provenance = deepcopy(pair.provenance)
        if altered:
            provenance["training_completion"]["sha256"] = "0" * 64
        execution_source = evaluator.h0_execution_source(request, provenance)
        _, metadata = cache.get_or_compute(
            pair.candidate, geometries, architecture_sha256=pair.provenance["architecture_sha256"],
            membership_sha256="a" * 64, device="cpu", execution_source=execution_source, max_graphs=1)
        keys.append(metadata["cache_key"])
    assert keys[0] != keys[1]


@pytest.mark.parametrize("case", ["no_COMPLETE", "wrong_map", "nonfinite"])
def test_execution_cache_cannot_drop_or_change_checked_mapping(committed, case):
    evaluator = module_from_tool("evaluate_dev_panel")
    pair = pair_for(committed)
    provenance = deepcopy(pair.provenance)
    request = {"code_sha": BASE, "source_files": [], "model_configuration": committed["event"]["model_configuration"]}
    if case == "no_COMPLETE":
        del provenance["training_completion"]
    elif case == "wrong_map":
        provenance["training_execution"]["H0_export"]["precision"] = "bf16"
    else:
        provenance["training_execution"]["bad"] = float("nan")
    with pytest.raises(ValueError):
        evaluator.h0_execution_source(request, provenance)


def test_existing_preparer_has_explicit_execution_flag_and_keeps_old_default_shape(committed, tmp_path):
    preparer = module_from_tool("prepare_dev_evaluation")
    panel = write_once(tmp_path / "panel.json", {"engineering_metadata_only": True})
    store = write_once(tmp_path / "store.json", {"engineering_metadata_only": True})
    event = committed["event"]
    kwargs = dict(panel=panel["path"], training_store=store["path"],
                  model_configuration=event["model_configuration"]["path"],
                  checkpoint=event["checkpoint"]["path"], code_sha=BASE,
                  preregistration_sha=BASE, data_version="engineering-unit",
                  pretraining_seed=event["pretraining_seed"], output_root=tmp_path / "output",
                  cache_root=tmp_path / "output/cache", run_id="unit_execution_H0",
                  training_completion=event["training_completion"]["path"],
                  enable_architecture_candidates=True)
    with pytest.raises(ValueError, match="explicit evaluation opt-in"):
        preparer.make_request(**kwargs)
    result = preparer.make_request(**kwargs, enable_training_execution=True)
    assert result["enable_training_execution"] is True
    assert result["training_completion"]["sha256"] == event["training_completion"]["sha256"]
    with pytest.raises(ValueError):
        preparer.make_request(**kwargs, enable_training_execution=1)
    # This is a metadata-only legacy-shape check, not an assertion that a new
    # execution CP can load under the stripped configuration (the bridge refuses).
    legacy_configuration = deepcopy(committed["configuration"])
    del legacy_configuration["training_execution"]
    legacy_ref = write_once(tmp_path / "legacy-shape-only-configuration.json", legacy_configuration)
    legacy_kwargs = dict(kwargs, model_configuration=legacy_ref["path"])
    legacy = preparer.make_request(**legacy_kwargs)
    assert "enable_training_execution" not in legacy


def test_same_real_CLI_checkpoint_H0_random_enters_original_ACK_protocol(committed, tmp_path):
    # The encoders, CP, resume and H0 caches below are genuine engineering work.
    # Panel scores/outer/SDK evidence are explicitly synthetic grammar fixtures:
    # this test grants no nine-task evaluation, SDK or scientific acceptance.
    pair = pair_for(committed)
    evaluator = module_from_tool("evaluate_dev_panel")
    event = committed["event"]
    request = {"code_sha": BASE, "source_files": [], "model_configuration": event["model_configuration"]}
    source = evaluator.h0_execution_source(request, pair.provenance)
    graph = committed["graph"].to_data_list()[1]
    cache = FrozenH0Cache(tmp_path / "actual-target-free-cache", repository_root=ROOT)
    caches = {}
    for dataset in ("cyp_isoform", "expansionrx", "qm9"):
        geometry = NativeGeometry(dataset, "unit-one", 0, graph.x, graph.pos, torch.arange(5))
        for label, model in (("candidate", pair.candidate), ("reference", pair.random_reference)):
            _, metadata = cache.get_or_compute(
                model, [geometry], architecture_sha256=event["architecture_sha256"],
                membership_sha256=event["panel_binding"]["membership_sha256"][dataset],
                device="cpu", execution_source=source, max_graphs=1)
            caches[label + "/" + dataset] = metadata
    grammar_root = tmp_path / "synthetic-panel-grammar"
    grammar_root.mkdir()
    template_ref, _ = fake_result_and_evidence(grammar_root, event)
    result = read_bound(template_ref)
    result["encoder_pair"] = pair.provenance
    result["h0_caches"] = caches
    result["unit_engineering_panel_protocol_only"] = True
    result_ref = write_once(tmp_path / "actual-H0-synthetic-panel-result.json", result)
    outer_ref = write_once(tmp_path / "synthetic-panel-outer.json",
                           {"status": "COMPLETED", "exit_code": 0, "job_id": "synthetic"})
    sdk_ref = write_once(tmp_path / "synthetic-panel-sdk.json",
                         {"status": "VERIFIED", "wandb_history_independently_verified": True,
                          "inputs": {"result": result_ref}, "sdk_run_id": "synthetic",
                          "clean_eof": True, "sdk_exit_code": 0, "history_rows": 2})
    evidence_ref = write_once(tmp_path / "synthetic-panel-evidence.json",
                              {"schema": "model_v3_sample_panel_evidence_v1", "result": result_ref,
                               "outer_terminal": outer_ref, "sdk_verification": sdk_ref})
    # Reopen the actual CLI outbox; do not create a parallel fake controller.
    lineage = read_bound(binding(Path(committed["lineage_root"]) / "EXPERIMENT.json"))
    plan = lineage["contract"]["plan"]
    controller = BoundedLineageController(
        committed["lineage_root"], contract=lineage["contract"],
        max_records=plan["max_total_checkpoints"],
        maximum_bytes=committed["configuration"]["proxy_contract"]["resources"]["ledger_bytes"])
    receipt = controller.acknowledge(committed["event_ref"], result_ref, evidence_ref)
    assert receipt and event["event_id"] not in {body["event_id"] for _, body in controller.pending()}
    assert controller.acknowledge(committed["event_ref"], result_ref, evidence_ref) == receipt
    assert controller.curve()["scientific_acceptance"] is False


@pytest.mark.parametrize("drift", ["payload_digest", "configuration_digest", "detached_COMPLETE"])
def test_new_execution_branch_keeps_original_raw_byte_and_directory_boundary(committed, tmp_path, drift):
    changed = dict(committed, event=deepcopy(committed["event"]))
    if drift == "payload_digest":
        changed["event"]["checkpoint"]["sha256"] = "0" * 64
    elif drift == "configuration_digest":
        changed["event"]["model_configuration"]["sha256"] = "0" * 64
    else:
        folder = tmp_path / "different-immutable-directory"
        folder.mkdir()
        original = read_bound(changed["event"]["training_completion"])
        changed["event"]["training_completion"] = write_once(folder / "COMPLETE.json", original)
    with pytest.raises(EncoderBindingError):
        pair_for(changed)


def test_cache_projection_has_stdlib_only_import_and_preserves_full_identity(committed):
    _, _, provenance = execution_checkpoint_state(committed["payload"], committed["configuration"])
    expected = training_execution_cache_projection(provenance)
    code = """import importlib.util,json,sys
spec=importlib.util.spec_from_file_location('standalone_H0_projection',sys.argv[1])
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
assert 'torch' not in sys.modules
projected=module.training_execution_cache_projection(json.load(sys.stdin))
assert 'torch' not in sys.modules
print(json.dumps(projected,sort_keys=True,allow_nan=False))
"""
    child = subprocess.run(
        [sys.executable, "-S", "-B", "-c", code,
         str(ROOT / "current/phychem_mfm/phase1/v3_execution_checkpoint_bridge.py")],
        input=json.dumps(provenance, ensure_ascii=False, allow_nan=False),
        text=True, capture_output=True, check=True, timeout=30)
    assert json.loads(child.stdout) == expected
    assert expected["training_execution_contract_sha256"] == canonical_hash(provenance["training_contract"])
    assert expected["H0_export_sha256"] == canonical_hash(provenance["training_contract"]["h0_export"])
    assert "training_contract" not in expected


@pytest.mark.parametrize("drift", ["contract_hash", "map_hash", "runtime_hash", "missing_full_original"])
def test_compact_projection_cannot_substitute_for_its_complete_original(committed, drift):
    _, _, provenance = execution_checkpoint_state(committed["payload"], committed["configuration"])
    if drift == "contract_hash":
        provenance["training_execution_contract_sha256"] = "0" * 64
    elif drift == "map_hash":
        provenance["H0_export_sha256"] = "0" * 64
    elif drift == "runtime_hash":
        provenance["saved_runtime_execution_sha256"] = "0" * 64
    else:
        del provenance["training_contract"]
    with pytest.raises(ExecutionCheckpointError):
        training_execution_cache_projection(provenance)


def _global_precision():
    return {"precision": torch.get_float32_matmul_precision(),
            "matmul_tf32": torch.backends.cuda.matmul.allow_tf32,
            "cudnn_tf32": torch.backends.cudnn.allow_tf32,
            "deterministic": torch.are_deterministic_algorithms_enabled(),
            "warn_only": torch.is_deterministic_algorithms_warn_only_enabled(),
            "cudnn_deterministic": torch.backends.cudnn.deterministic,
            "cudnn_benchmark": torch.backends.cudnn.benchmark}


def _restore_global_precision(value):
    torch.set_float32_matmul_precision(value["precision"])
    torch.backends.cudnn.allow_tf32 = value["cudnn_tf32"]
    torch.use_deterministic_algorithms(value["deterministic"], warn_only=value["warn_only"])
    torch.backends.cudnn.deterministic = value["cudnn_deterministic"]
    torch.backends.cudnn.benchmark = value["cudnn_benchmark"]


def test_builder_preserves_globals_and_explicit_CPU_H0_context_restores_on_success_and_failure(committed):
    from phychem_mfm.phase1.v3_training_execution import h0_export_context
    original = _global_precision()
    before_rng = capture_rng_state()
    try:
        torch.set_float32_matmul_precision("medium")
        torch.backends.cudnn.allow_tf32 = True
        torch.use_deterministic_algorithms(False, warn_only=True)
        torch.backends.cudnn.deterministic = False
        torch.backends.cudnn.benchmark = True
        altered = _global_precision()
        pair = pair_for(committed)
        assert _global_precision() == altered  # construction/load is not a context setter
        contract = pair.provenance["training_execution"]["training_contract"]
        with h0_export_context(contract, device_type="cpu"):
            assert torch.get_float32_matmul_precision() == "highest"
            assert torch.backends.cuda.matmul.allow_tf32 is False
            assert torch.backends.cudnn.allow_tf32 is False
            assert torch.are_deterministic_algorithms_enabled()
            assert not torch.is_deterministic_algorithms_warn_only_enabled()
            with torch.no_grad():
                h0 = pair.candidate.encode_atoms(committed["graph"])
            assert torch.equal(h0, committed["expected_h0"])
        assert _global_precision() == altered
        with pytest.raises(RuntimeError, match="unit H0 scope failure"):
            with h0_export_context(contract, device_type="cpu"):
                raise RuntimeError("unit H0 scope failure")
        assert _global_precision() == altered
        assert_tree_equal(before_rng, capture_rng_state())
    finally:
        _restore_global_precision(original)


@pytest.fixture
def preinit_case(tmp_path):
    # Deliberately only the metadata read by this narrow pre-CUDA component.
    # This is not a valid panel/data/GPU-admission request.
    preparer = module_from_tool("prepare_dev_evaluation")
    configuration = {"schema": "model_v3_proxy_configuration_v1",
                     "training_execution": {"options": {"backbone_checkpointing": True}},
                     "proxy_contract": {"execution": {"deterministic": True}}}
    ref = write_once(tmp_path / "preinit-source-configuration.json", configuration)
    declaration = preparer.h0_preinit_declaration(ref, repository_root=ROOT)
    required = (preparer.H0_POLICY_RELATIVE, "tools/model_v3/prepare_dev_evaluation.py",
                "tools/model_v3/evaluate_dev_panel.py")
    request = {"schema": "unit_H0_preinit_metadata_only_not_GPU_admission",
               "enable_training_execution": True, "model_configuration": ref,
               "h0_preinit": declaration,
               "source_files": [{"path": path, "sha256": preparer.binding(ROOT / path)["sha256"]}
                                for path in required]}
    request_ref = write_once(tmp_path / "preinit-request.json", request)
    return {"preparer": preparer, "configuration": configuration,
            "declaration": declaration, "request": request,
            "request_ref": request_ref, "root": tmp_path}


def test_same_policy_preinit_is_before_exec_and_imports_no_Torch(preinit_case, monkeypatch):
    case = preinit_case
    script = case["preparer"].sbatch_text(
        case["request_ref"]["path"], case["request_ref"]["sha256"],
        node="compute-0-21", python_entry=sys.executable,
        gpu_uuid="GPU-00000000-0000-0000-0000-000000000001",
        log_path=case["root"] / "metadata-only.log", h0_preinit=case["declaration"])
    assert script.index("export CUBLAS_WORKSPACE_CONFIG=") < script.index("\nexec ")
    legacy_script = case["preparer"].sbatch_text(
        case["request_ref"]["path"], case["request_ref"]["sha256"],
        node="compute-0-21", python_entry=sys.executable,
        gpu_uuid="GPU-00000000-0000-0000-0000-000000000001",
        log_path=case["root"] / "metadata-only-legacy.log")
    assert "CUBLAS_WORKSPACE_CONFIG" not in legacy_script
    code = """import importlib.util,json,os,sys
spec=importlib.util.spec_from_file_location('fixed_preinit_tool',sys.argv[1])
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
assert 'torch' not in sys.modules
result=module.validate_h0_preinit_request(sys.argv[2],sys.argv[3],repository_root=sys.argv[4])
assert 'torch' not in sys.modules
assert os.environ.get('CUBLAS_WORKSPACE_CONFIG')==result['runtime_controls']['cublas_workspace_config_for_cuda']
print(json.dumps(result,sort_keys=True))
"""
    environment = dict(os.environ)
    environment.pop("CUBLAS_WORKSPACE_CONFIG", None)
    child = subprocess.run(
        [sys.executable, "-S", "-B", "-c", code,
         str(ROOT / "tools/model_v3/prepare_dev_evaluation.py"),
         case["request_ref"]["path"], case["request_ref"]["sha256"], str(ROOT)],
        env=environment, text=True, capture_output=True, check=True, timeout=30)
    assert json.loads(child.stdout) == case["declaration"]


@pytest.mark.parametrize("deterministic", [False, True])
def test_preinit_metadata_planning_uses_shared_policy_without_setting_environment(preinit_case, monkeypatch, deterministic):
    case = preinit_case
    configuration = deepcopy(case["configuration"])
    configuration["proxy_contract"]["execution"]["deterministic"] = deterministic
    config_ref = write_once(case["root"] / ("deterministic-" + str(deterministic) + ".json"), configuration)
    request = deepcopy(case["request"])
    request["model_configuration"] = config_ref
    request["h0_preinit"] = case["preparer"].h0_preinit_declaration(config_ref)
    request_ref = write_once(case["root"] / ("metadata-" + str(deterministic) + ".json"), request)
    monkeypatch.setenv("CUBLAS_WORKSPACE_CONFIG", "unit-existing-not-admitted")
    declaration = case["preparer"].validate_h0_preinit_request(
        request_ref["path"], request_ref["sha256"], apply_environment=False)
    assert declaration == request["h0_preinit"]
    assert declaration["runtime_controls"]["deterministic_algorithms"] is deterministic
    assert os.environ["CUBLAS_WORKSPACE_CONFIG"] == "unit-existing-not-admitted"
    if not deterministic:
        assert declaration["runtime_controls"]["cublas_workspace_config_for_cuda"] is None


@pytest.mark.parametrize("drift", [
    "missing_declaration", "wrong_controls", "wrong_configuration", "wrong_policy_sha",
    "wrong_policy_path", "missing_source", "bool_flag", "missing_deterministic",
])
def test_preinit_missing_or_inconsistent_source_declarations_reject_before_environment(preinit_case, monkeypatch, drift):
    case = preinit_case
    request = deepcopy(case["request"])
    if drift == "missing_declaration":
        del request["h0_preinit"]
    elif drift == "wrong_controls":
        request["h0_preinit"]["runtime_controls"]["cublas_workspace_config_for_cuda"] = ":16:8"
    elif drift == "wrong_configuration":
        request["h0_preinit"]["configuration"]["sha256"] = "0" * 64
    elif drift == "wrong_policy_sha":
        request["h0_preinit"]["policy_source"]["sha256"] = "0" * 64
    elif drift == "wrong_policy_path":
        request["h0_preinit"]["policy_source"]["path"] += ".not-the-fixed-policy"
    elif drift == "missing_source":
        request["source_files"] = request["source_files"][1:]
    elif drift == "bool_flag":
        request["enable_training_execution"] = 1
    else:
        configuration = deepcopy(case["configuration"])
        del configuration["proxy_contract"]["execution"]["deterministic"]
        config_ref = write_once(case["root"] / "missing-deterministic-source.json", configuration)
        request["model_configuration"] = config_ref
        request["h0_preinit"]["configuration"] = config_ref
    ref = write_once(case["root"] / ("bad-" + drift + ".json"), request)
    monkeypatch.delenv("CUBLAS_WORKSPACE_CONFIG", raising=False)
    with pytest.raises(ValueError):
        case["preparer"].validate_h0_preinit_request(ref["path"], ref["sha256"])
    assert "CUBLAS_WORKSPACE_CONFIG" not in os.environ
    if drift == "wrong_controls":
        with pytest.raises(ValueError):
            case["preparer"].sbatch_text(
                ref["path"], ref["sha256"], node="compute-0-21",
                python_entry=sys.executable, gpu_uuid="GPU-00000000-0000-0000-0000-000000000001",
                log_path=case["root"] / "must-not-launch.log", h0_preinit=request["h0_preinit"])


def test_preinit_simulated_already_initialized_CUDA_is_not_late_repaired(preinit_case, monkeypatch):
    case = preinit_case
    monkeypatch.setattr(torch.cuda, "is_initialized", lambda: True)
    monkeypatch.delenv("CUBLAS_WORKSPACE_CONFIG", raising=False)
    with pytest.raises(ValueError, match="precede CUDA initialization"):
        case["preparer"].validate_h0_preinit_request(
            case["request_ref"]["path"], case["request_ref"]["sha256"])
    assert "CUBLAS_WORKSPACE_CONFIG" not in os.environ


def test_preinit_conflicting_inherited_environment_is_not_silently_overridden(preinit_case, monkeypatch):
    case = preinit_case
    monkeypatch.setenv("CUBLAS_WORKSPACE_CONFIG", ":16:8")
    with pytest.raises(ValueError, match="contradicts"):
        case["preparer"].validate_h0_preinit_request(
            case["request_ref"]["path"], case["request_ref"]["sha256"])
    assert os.environ["CUBLAS_WORKSPACE_CONFIG"] == ":16:8"

# Small recursive-deletion policy tests. These use no committed/model fixture.
def _unit_module_lifecycle(tmp_path):
    from model_v3_fixture_lifecycle import _ModuleLifecycle, _OwnedDirectory
    base = tmp_path / "worker-basetemp"
    base.mkdir()
    root = base / "only-this-fixture"
    root.mkdir()
    (root / "kept.txt").write_text("owned unit fixture", encoding="utf-8")
    owned = _OwnedDirectory(base, root)
    state = _ModuleLifecycle({"unit::test"})
    state.add_directory(owned)
    return state, owned


def test_module_fixture_cleanup_waits_for_resource_close_and_final_actual_teardown(tmp_path):
    state, owned = _unit_module_lifecycle(tmp_path)
    state.record_report("unit::test", "setup", True)
    state.record_report("unit::test", "call", True)
    assert state.try_cleanup() is False and owned.path.is_dir()
    owned.fixture_closed()
    assert state.try_cleanup() is False and owned.path.is_dir()
    state.record_report("unit::test", "teardown", True)
    assert state.try_cleanup() is True and owned.path.is_dir()
    assert list(owned.path.iterdir()) == []  # Empty root stays in the same measured basetemp.
    assert state.try_cleanup() is False  # This directory contents can be retired only once.


@pytest.mark.parametrize("outcome", ["failure", "skip", "xfail", "interrupted"])
def test_module_fixture_failure_skip_xfail_or_interruption_retains_every_owned_byte(tmp_path, outcome):
    state, owned = _unit_module_lifecycle(tmp_path)
    owned.fixture_closed()
    state.record_report("unit::test", "setup", True)
    state.record_report("unit::test", "call", outcome not in ("failure", "skip"), outcome == "xfail")
    if outcome != "interrupted":
        state.record_report("unit::test", "teardown", True)
    assert state.try_cleanup() is False
    assert (owned.path / "kept.txt").read_text(encoding="utf-8") == "owned unit fixture"


@pytest.mark.parametrize("boundary", ["outside", "root_symlink", "ancestor_symlink"])
def test_module_fixture_cleanup_rejects_outside_or_symlinked_roots_before_deletion(tmp_path, boundary):
    from model_v3_fixture_lifecycle import _OwnedDirectory
    base = tmp_path / "worker-basetemp"
    base.mkdir()
    outside = tmp_path / "must-survive"
    outside.mkdir()
    (outside / "sentinel").write_bytes(b"unchanged")
    if boundary == "outside":
        root = outside
    elif boundary == "root_symlink":
        root = base / "unsafe-root"
        root.symlink_to(outside, target_is_directory=True)
    else:
        real = base / "real-root"
        real.mkdir()
        alias = tmp_path / "unsafe-basetemp-alias"
        alias.symlink_to(base, target_is_directory=True)
        base, root = alias, alias / "real-root"
    with pytest.raises(ValueError):
        _OwnedDirectory(base, root)
    assert (outside / "sentinel").read_bytes() == b"unchanged"
    assert outside.is_dir()


def test_module_fixture_cleanup_rejects_replaced_registered_inode_and_retains_both(tmp_path):
    state, owned = _unit_module_lifecycle(tmp_path)
    saved = owned.path.with_name("original-must-survive")
    owned.path.rename(saved)
    owned.path.mkdir()
    (owned.path / "replacement").write_bytes(b"not registered")
    owned.fixture_closed()
    for phase in ("setup", "call", "teardown"):
        state.record_report("unit::test", phase, True)
    with pytest.raises(ValueError, match="replaced"):
        state.try_cleanup()
    assert (saved / "kept.txt").read_text(encoding="utf-8") == "owned unit fixture"
    assert (owned.path / "replacement").read_bytes() == b"not registered"

@pytest.mark.parametrize("replacement_timing", ["before_open", "after_open"])
def test_module_fixture_cleanup_is_bound_to_actual_opened_inode_not_later_root_path(tmp_path, monkeypatch, replacement_timing):
    import model_v3_fixture_lifecycle as lifecycle
    state, owned = _unit_module_lifecycle(tmp_path)
    child = owned.path / "child-directory"
    child.mkdir()
    (child / "payload").write_bytes(b"original fixture only")
    saved = owned.path.with_name("registered-original")
    real_open, raced = lifecycle.os.open, []

    def replace_root_at_open(path, flags, mode=0o777, *, dir_fd=None):
        if dir_fd is None and Path(path) == owned.path and not raced:
            raced.append(True)
            fd = real_open(path, flags, mode) if replacement_timing == "after_open" else None
            owned.path.rename(saved)
            owned.path.mkdir()
            (owned.path / "must-survive").write_bytes(b"new unregistered inode")
            return fd if fd is not None else real_open(path, flags, mode)
        return real_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(lifecycle.os, "open", replace_root_at_open)
    owned.fixture_closed()
    for phase in ("setup", "call", "teardown"):
        state.record_report("unit::test", phase, True)
    if replacement_timing == "before_open":
        with pytest.raises(ValueError, match="Opened fixture inode"):
            state.try_cleanup()
        assert (saved / "kept.txt").is_file() and (saved / "child-directory/payload").is_file()
    else:
        assert state.try_cleanup() is True
        assert saved.is_dir() and list(saved.iterdir()) == []
    assert raced and (owned.path / "must-survive").read_bytes() == b"new unregistered inode"
