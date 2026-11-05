"""Synthetic primary512 admission/paired-result tests; no model or target I/O."""
from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
import sys

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import export_admission as export
import run_panel_guard as guard


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True, allow_nan=False)+"\n")
    return export.binding(path)


def bundle(tmp_path):
    run = tmp_path / "source_run"; run.mkdir()
    directory = run / "candidate_h0"; directory.mkdir()
    weights = directory / "candidate.pt"
    weights.write_bytes(b"opaque synthetic weights; never torch.load in metadata tests")
    checkpoint = {**export.binding(weights), "state_key": "model_state"}
    options = {"precision": "fp32", "fused_adamw": True}
    recipe = {"backbone": {"dim": 512, "layers": 6}, "training": {"seed": 0},
        "phase1": {"performance_options": options}}
    configuration = {"input": "native_s", "smoke": False, "fixed_batches": 20, "trajectory_updates": 500,
        "seed": 0, "candidate": options, "code_sha": export.EXPORT_CODE_SHA, "source_sha256": {"source.py": "f"*64}}
    configuration["configuration_sha256"] = export.canonical(configuration)
    provenance = {"seed": 0, "code_sha": export.EXPORT_CODE_SHA,
        "source_inventory_sha256": export.canonical(configuration["source_sha256"]),
        "full_native_A_numeric_gates_passed": True, "optimizer_updates": 500,
        "formal_pretraining_complete": False, "A_resume_supported": False,
        "performance_options": options, "consumed_base_records": 1000}
    config_ref = write(directory / "model_configuration.json", recipe)
    configuration_ref = write(directory / "a_run_configuration.json", configuration)
    provenance_ref = write(directory / "provenance.json", provenance)
    ready = {"schema": "model_v3_A_H0_export_ready_v1", "status": "H0_BYTES_VERIFIED_PENDING_OUTER_JOB_TERMINAL",
        "code_sha": export.EXPORT_CODE_SHA, "optimizer_updates": 500, "consumed_base_records": 1000,
        "resume_supported": False, "generic_checkpoint_schema": "source_training_checkpoint_v1",
        "training_rng_unchanged": True, "training_rng_before": {"torch_cpu": "a"}, "training_rng_after": {"torch_cpu": "a"},
        "checkpoint": checkpoint, "model_configuration": config_ref, "a_run_configuration": configuration_ref,
        "provenance": provenance_ref, "source_inventory_sha256": provenance["source_inventory_sha256"],
        "pretraining_seed": 0, "architecture_sha256": "a"*64,
        "H0_loader_provenance": {"H0_dimension": 512, "reference_kind": "primary",
            "checkpoint_schema": "source_training_checkpoint_v1", "architecture_sha256": "a"*64,
            "checkpoint": checkpoint, "original_configuration": config_ref, "pretraining_seed": 0}}
    ready_ref = write(directory / "READY.json", ready)
    supervisor = {"job_id": "4520457", "status": "COMPLETED", "exit_code": 0, "first_failure": None,
        "remaining_recorded_processes_before_retirement": [], "private_storage_cleanup_errors": []}
    run_status = {"job_id": "4520457", "status": "PAIRED_GATES_PASS", "failure": None,
        "cleanup_errors": [], "checkpoint_export": {"ready": ready_ref}}
    summary = {"status": "PAIRED_GATES_PASS", "full_A_numeric_acceptance": True, "fixed_batch_pass": True,
        "trajectory_pass": True, "input": "native_s", "smoke": False, "code_sha": export.EXPORT_CODE_SHA,
        "consumed_trajectory_base_records": 1000}
    admission = {"schema": "model_v3_primary512_export_admission_v1", "ready": ready_ref,
        "checked_at_utc": datetime.now(timezone.utc).isoformat(), "expected_export_code_sha": export.EXPORT_CODE_SHA,
        "export_job": {"job_id": "4520457", "state": "COMPLETED", "exit_code": "0:0"},
        "supervisor": write(run / "supervisor.json", supervisor),
        "run_status": write(run / "run_status.json", run_status), "summary": write(run / "summary.json", summary)}
    admission_ref = write(tmp_path / "root_admission.json", admission)
    return ready_ref, admission_ref, ready, admission, supervisor, run_status, summary


def test_ready_needs_real_terminal_admission_and_preserves_original_full_configuration(tmp_path):
    ready_ref, admission_ref, ready, _, _, _, _ = bundle(tmp_path)
    before = export.binding(ready["checkpoint"]["path"])
    accepted = export.read_validated_export(ready_ref, admission_ref)
    assert accepted["checkpoint"] == ready["checkpoint"]
    assert accepted["model_configuration"] == ready["model_configuration"]
    assert accepted["export_job_id"] == "4520457" and accepted["pretraining_seed"] == 0
    assert export.binding(ready["checkpoint"]["path"]) == before
    assert accepted["ready"]["status"] == "H0_BYTES_VERIFIED_PENDING_OUTER_JOB_TERMINAL"


@pytest.mark.parametrize("drift", ("running", "supervisor", "cleanup", "acceptance", "source", "384", "stale", "rng"))
def test_export_admission_rejects_unclosed_or_foreign_export(tmp_path, drift):
    ready_ref, _, ready, admission, supervisor, run_status, summary = bundle(tmp_path)
    if drift == "running": admission["export_job"]["state"] = "RUNNING"
    elif drift == "supervisor": supervisor["status"] = "FAILED"
    elif drift == "cleanup": run_status["cleanup_errors"] = [{"component": "SDK"}]
    elif drift == "acceptance": summary["full_A_numeric_acceptance"] = False
    elif drift == "source": ready["code_sha"] = "0"*40
    elif drift == "384": ready["H0_loader_provenance"]["H0_dimension"] = 384
    elif drift == "stale": admission["checked_at_utc"] = (datetime.now(timezone.utc)-timedelta(hours=2)).isoformat()
    elif drift == "rng": ready["training_rng_after"] = {"torch_cpu": "changed"}
    with pytest.raises(ValueError):
        export.validate_receipts(ready, ready_ref, admission, supervisor, run_status, summary)


def test_export_readonly_hash_rejects_changed_weight_bytes(tmp_path):
    ready_ref, admission_ref, ready, _, _, _, _ = bundle(tmp_path)
    Path(ready["checkpoint"]["path"]).write_bytes(b"different opaque weights")
    with pytest.raises(ValueError, match="bundle SHA"):
        export.read_validated_export(ready_ref, admission_ref)


def test_same_shape_performance_recipe_drift_is_not_reconstructed_or_ignored(tmp_path):
    ready_ref, admission_ref, ready, admission, _, _, _ = bundle(tmp_path)
    path = Path(ready["model_configuration"]["path"])
    recipe = json.loads(path.read_text()); recipe["phase1"]["performance_options"]["fused_adamw"] = False
    ready["model_configuration"] = write(path, recipe)
    ready["H0_loader_provenance"]["original_configuration"] = ready["model_configuration"]
    # Rebind synthetic outer metadata intentionally. The original recipe/run
    # semantic cross-check must still detect the mismatch before any model load.
    new_ready = write(Path(ready_ref["path"]), ready)
    admission["ready"] = new_ready
    status = json.loads(Path(admission["run_status"]["path"]).read_text())
    status["checkpoint_export"]["ready"] = new_ready
    admission["run_status"] = write(Path(admission["run_status"]["path"]), status)
    new_admission = write(Path(admission_ref["path"]), admission)
    with pytest.raises(ValueError, match="runtime options"):
        export.read_validated_export(new_ready, new_admission)


def actual_frozen_request(tmp_path):
    source = Path('/share/home/zixiao/descriptor_analysis/MFM_model_v3_sa3/tools/model_v3/prepare_dev_evaluation.py')
    assert export.binding(source)['sha256'] == 'e66564d33a2430fec646528caee3d82e57d31bb5fc3fae00e24c7d04de9762ea'
    loader = importlib.util.spec_from_file_location('actual_frozen9638_request_builder', source)
    prepare = importlib.util.module_from_spec(loader); loader.loader.exec_module(prepare)
    repository = tmp_path / 'request_repo'; repository.mkdir()
    (repository / 'source.py').write_text('unit_metadata_only = True\n')
    configuration = tmp_path / 'model_configuration.json'
    configuration.write_text(json.dumps({'seed': 0, 'model': {'backbone': {'dim': 512, 'layers': 6}}}))
    checkpoint = tmp_path / 'candidate.pt'; checkpoint.write_bytes(b'opaque standard reference fixture; no model deserialization')
    panel = tmp_path / 'panel.json'; panel.write_text('{}')
    store = tmp_path / 'store.json'; store.write_text('{}')
    request = prepare.make_request(panel=panel, training_store=store, model_configuration=configuration,
        checkpoint=checkpoint, code_sha=export.EVALUATION_CODE_SHA, preregistration_sha='39cf4929299cd227a3c361183a4b26c8b1405900',
        data_version='synthetic_reference_shape_v2', pretraining_seed=0, output_root=tmp_path / 'evaluation',
        cache_root=tmp_path / 'evaluation/h0_cache', run_id='A00_short500_primary512_dev9_v1',
        source_files=['source.py'], state_key='model_state', repository_root=repository)
    checkpoint_authority = {**export.binding(checkpoint), 'state_key': 'model_state'}
    configuration_authority = export.binding(configuration)
    assert set(request['checkpoint']) == {'path', 'sha256', 'state_key'}
    assert set(request['model_configuration']) == {'path', 'sha256'}
    assert 'bytes' in checkpoint_authority and 'bytes' in configuration_authority
    return request, checkpoint_authority, configuration_authority


def primary_result(tmp_path):
    request, checkpoint, configuration = actual_frozen_request(tmp_path)
    architecture = request['architecture_sha256']
    spec = {"request": {"sha256": "d"*64}, "source_checkpoint": checkpoint, "original_configuration": configuration,
        "code_sha": export.EVALUATION_CODE_SHA}
    tasks = {"cyp.3A4", "cyp.2D6", "exp.LogD", "exp.LogS", "exp.Log_HLM_CLint", "qm9.U0", "qm9.homo", "qm9.lumo", "qm9.alpha"}
    result = {"status": "COMPLETED", "reference_kind": "primary", "request_sha256": "d"*64,
        "code_sha": export.EVALUATION_CODE_SHA, "architecture_sha256": architecture,
        "pretraining_seed": 0, "random_reference_initialization_seed": 20261025, "readout_seed": 0,
        "encoder_pair": {"H0_dimension": 512, "reference_kind": "primary", "checkpoint_schema": "source_training_checkpoint_v1",
            "checkpoint": request['checkpoint'], "original_configuration": request['model_configuration'], "architecture_sha256": architecture,
            "random_reference_seed": 20261025, "pretraining_seed": 0,
            "checkpoint_encoder_state_sha256": "e"*64, "random_encoder_state_sha256": "f"*64},
        "summaries": {}, "h0_caches": {}}
    for name in ("primary_18_cells", "ridge", "linear64_relu"):
        methods = ("ridge", "linear64_relu") if name == "primary_18_cells" else (name,)
        result["summaries"][name] = {"complete": True, "tasks": {task+"@"+method: {} for task in tasks for method in methods},
            "bootstrap_samples": 1000, "bootstrap_defined": 1000}
    for dataset in ("cyp_isoform", "expansionrx", "qm9"):
        for label in ("candidate", "reference"):
            result["h0_caches"][label+"/"+dataset] = {"targets_cached": False, "atoms": 10, "molecules": 2,
                "binding": {"architecture_sha256": architecture, "membership_sha256": "m"*64,
                    "geometry_sha256": "g"*64, "dimension": 512, "packing_plan_sha256": "p"*64,
                    "packing_budget_sha256": "q"*64, "effective_runtime_sha256": "r"*64,
                    "encoder_sha256": "e"*64 if label == "candidate" else "f"*64}}
    return spec, request, result


def test_primary_result_requires_both_matching512_encoders_all18cells_and1000draws(tmp_path):
    spec, request, result = primary_result(tmp_path)
    guard.verify_primary_result(spec, request, result)


@pytest.mark.parametrize("drift", ("historical", "dimension", "checkpoint", "random_geometry", "same_weights", "cell", "bootstrap"))
def test_primary_result_rejects_historical_or_mismatched_evidence(drift, tmp_path):
    spec, request, result = primary_result(tmp_path)
    if drift == "historical": result["reference_kind"] = "historical_sanity_only"
    elif drift == "dimension": result["encoder_pair"]["H0_dimension"] = 384
    elif drift == "checkpoint": result["encoder_pair"]["checkpoint"] = {"path": "/foreign/model.pt"}
    elif drift == "random_geometry": result["h0_caches"]["reference/qm9"]["binding"]["geometry_sha256"] = "foreign"
    elif drift == "same_weights": result["encoder_pair"]["random_encoder_state_sha256"] = "e"*64
    elif drift == "cell": result["summaries"]["ridge"]["tasks"].pop("qm9.U0@ridge")
    elif drift == "bootstrap": result["summaries"]["primary_18_cells"]["bootstrap_defined"] = 999
    with pytest.raises(RuntimeError):
        guard.verify_primary_result(spec, request, result)


def test_actual_frozen_reference_shapes_are_admitted_with_independently_measured_ready_bytes(tmp_path):
    request, checkpoint, configuration = actual_frozen_request(tmp_path)
    assert request['checkpoint'] != checkpoint and request['model_configuration'] != configuration
    assert export.require_same_reference(request['checkpoint'], checkpoint, state_key='model_state')
    assert export.require_same_reference(request['model_configuration'], configuration)
    # Also exercises exactly the adapter used by the guard before/after execution.
    guard.checked_reference(request['checkpoint'], checkpoint, state_key='model_state')
    guard.checked_reference(request['model_configuration'], configuration)


@pytest.mark.parametrize('drift', ('path', 'sha', 'state_key', 'candidate_bytes', 'authority_bytes', 'physical_bytes', 'missing_authority_bytes'))
def test_reference_shape_adapter_rejects_path_hash_state_key_and_any_byte_drift(tmp_path, drift):
    request, authority, _ = actual_frozen_request(tmp_path)
    candidate = dict(request['checkpoint']); authority = dict(authority)
    if drift == 'path':
        alternate = tmp_path / 'alternate.pt'; alternate.write_bytes(Path(candidate['path']).read_bytes())
        candidate['path'] = str(alternate)
    elif drift == 'sha': candidate['sha256'] = '0'*64
    elif drift == 'state_key': candidate['state_key'] = 'model'
    elif drift == 'candidate_bytes': candidate['bytes'] = authority['bytes']+1
    elif drift == 'authority_bytes': authority['bytes'] += 1
    elif drift == 'physical_bytes': Path(authority['path']).write_bytes(b'changed actual bytes')
    elif drift == 'missing_authority_bytes': authority.pop('bytes')
    with pytest.raises(ValueError):
        export.require_same_reference(candidate, authority, state_key='model_state')
    with pytest.raises(RuntimeError):
        guard.checked_reference(candidate, authority, state_key='model_state')


@pytest.mark.parametrize("nested_cache", (True, False))
def test_reuses_fixed_output_counter_without_nested_double_charge(tmp_path, nested_cache):
    reference = guard.binding(guard.FIXED_RUNTIME_MONITOR)
    monitor = guard.accounting_module(reference)
    output = tmp_path / "evaluation"; output.mkdir()
    cache = output / "h0_cache" if nested_cache else tmp_path / "separate_cache"; cache.mkdir()
    (cache / "opaque_h0").write_bytes(b"sizing fixture")
    supervision = tmp_path / "guard"; supervision.mkdir(); (supervision / "log").write_bytes(b"guard")
    sdk = output / "wandb" / "offline-run-20261025_120000-abcdefgh"; logs = sdk / "logs"; logs.mkdir(parents=True)
    for name in ("debug.log", "debug-internal.log"):
        (logs / name).write_bytes(b"SDK-shape fixture")
        (output / "wandb" / name).symlink_to(Path(sdk.name) / "logs" / name)
    (output / "wandb" / "latest-run").symlink_to(sdk.name, target_is_directory=True)
    core = output / "cache" / "wandb" / "logs" / "core-debug-20261025_120000.log"; core.parent.mkdir(parents=True); core.write_bytes(b"core")
    (logs / "debug-core.log").symlink_to(core)
    request = {"output_root": str(output), "cache_root": str(cache)}
    expected = monitor.owned_output_bytes(output)+monitor.owned_output_bytes(supervision)
    if not nested_cache: expected += monitor.owned_output_bytes(cache)
    assert guard.output_bytes(request, supervision, reference) == expected


def test_fixed_counter_rejects_arbitrary_link(tmp_path):
    output = tmp_path / "evaluation"; output.mkdir()
    cache = output / "h0_cache"; cache.mkdir()
    foreign = tmp_path / "foreign"; foreign.write_bytes(b"outside")
    (cache / "foreign").symlink_to(foreign)
    supervision = tmp_path / "guard"; supervision.mkdir()
    with pytest.raises(ValueError):
        guard.output_bytes({"output_root": str(output), "cache_root": str(cache)}, supervision,
            guard.binding(guard.FIXED_RUNTIME_MONITOR))
