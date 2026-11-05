"""Synthetic safety tests plus one real, tiny, offline W&B SDK round-trip."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import io
import importlib.util
import json
import os
from pathlib import Path
import sys
import time

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import verify_native_history as verify
import make_primary512_report as report
import primary512_scope as scope


def sample_rows():
    return [
        {"step": 0, "reference/cyp.3A4@ridge/validation_error": .5},
        {"step": 1, "candidate/qm9.U0@linear64_relu/readout/loss": .75,
         "candidate/qm9.U0@linear64_relu/readout/epoch": 0,
         "candidate/qm9.U0@linear64_relu/readout/observed_labels": 2,
         "candidate/qm9.U0@linear64_relu/readout/update": 0},
    ]


def records(rows=None, *, exit_code=0):
    from wandb.proto import wandb_internal_pb2 as pb
    first = pb.Record()
    first.run.run_id = "sa3audit"
    first.run.display_name = scope.RUN_NAME
    first.run.config.update.add(key="readout_seed", value_json="0")
    items = [first]
    for row in (sample_rows() if rows is None else rows):
        item = pb.Record()
        for key, value in row.items():
            item.history.item.add(key="_step" if key == "step" else key, value_json=json.dumps(value))
        item.history.item.add(key="_runtime", value_json="0.125")
        items.append(item)
    item = pb.Record()
    item.summary.update.add(key="evaluation_status", value_json='"COMPLETED"')
    items.append(item)
    item = pb.Record()
    item.exit.exit_code = exit_code
    items.append(item)
    return items


def compare(native, *, destination=None, rows=None, **kwargs):
    return verify.compare_records(native, sample_rows() if rows is None else rows,
        destination or io.BytesIO(), expected_run_id="sa3audit", expected_config={"readout_seed": 0},
        expected_summary={"evaluation_status": "COMPLETED"}, expected_rows=2, expected_display_name=scope.RUN_NAME, **kwargs)


def test_real_offline_sdk_round_trip(tmp_path, monkeypatch):
    # This is the actual installed SDK, not a fake DataStore/log method.
    monkeypatch.setenv("WANDB_MODE", "offline")
    monkeypatch.setenv("WANDB_DIR", str(tmp_path))
    monkeypatch.setenv("WANDB_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("WANDB_DATA_DIR", str(tmp_path / "wandb_data"))
    import wandb
    from wandb.proto import wandb_internal_pb2 as pb
    from wandb.sdk.internal.datastore import DataStore
    run = wandb.init(project="model-v3-readonly-verifier-unit", id="sa3audit", mode="offline",
        dir=str(tmp_path), name=scope.RUN_NAME, config={"readout_seed": 0})
    try:
        for row in sample_rows():
            run.log({key: value for key, value in row.items() if key != "step"}, step=row["step"], commit=True)
        run.summary["evaluation_status"] = "COMPLETED"
    finally:
        run.finish(exit_code=0)
    paths = list((tmp_path / "wandb").glob("offline-run-*/run-sa3audit.wandb"))
    assert len(paths) == 1
    before = verify.binding(paths[0])
    data = DataStore()
    destination = io.BytesIO()
    try:
        data.open_for_scan(str(paths[0]))
        result = compare(verify.scan_records(data, pb.Record, deadline=time.monotonic()+30), destination=destination)
    finally:
        data.close()
    assert result["clean_eof"] and result["history_rows"] == 2 and result["sdk_exit_code"] == 0
    assert verify.binding(paths[0]) == before
    assert [json.loads(line) for line in destination.getvalue().splitlines()] == sample_rows()


@pytest.mark.parametrize("corruption", ("loss", "step", "extra_key", "missing_row", "exit", "config", "run"))
def test_independent_comparison_rejects_drift(corruption):
    native = records()
    if corruption == "loss":
        native[2].history.item[1].value_json = "0.8"
    elif corruption == "step":
        native[2].history.item[0].value_json = "2"
    elif corruption == "extra_key":
        native[2].history.item.add(key="member_predictions", value_json="[0.1,0.2]")
    elif corruption == "missing_row":
        native.pop(2)
    elif corruption == "exit":
        native[-1].exit.exit_code = 1
    elif corruption == "config":
        native[0].run.config.update[0].value_json = "99"
    elif corruption == "run":
        native[0].run.run_id = "otherid0"
    with pytest.raises(ValueError):
        compare(native)


def test_export_budget_and_journal_framing():
    with pytest.raises(ValueError, match="byte budget"):
        compare(records(), budget_bytes=10)
    with pytest.raises(ValueError, match="Truncated"):
        list(verify.journal_rows(io.BytesIO(json.dumps(sample_rows()[0]).encode())))
    with pytest.raises(ValueError, match="Duplicate JSON"):
        verify.strict_json('{"step":0,"step":1}')
    bad = deepcopy(sample_rows()[1]); bad["candidate/qm9.U0@linear64_relu/readout/update"] = 1.5
    with pytest.raises(ValueError, match="integers"):
        verify.normalized(bad, 1)


def test_native_record_cap_rejects_stream_without_eof(monkeypatch):
    from wandb.proto import wandb_internal_pb2 as pb
    monkeypatch.setattr(verify, "MAX_NATIVE_RECORDS", 1)
    class NotAtEof:
        def scan_data(self):
            return records()[0].SerializeToString()
    with pytest.raises(ValueError, match="total-record budget"):
        list(verify.scan_records(NotAtEof(), pb.Record, deadline=time.monotonic()+1))


@pytest.mark.parametrize("native_limit", (8, 7))
def test_native_metric_ancillary_records_do_not_consume_history_quota_but_obey_total_cap(monkeypatch, native_limit):
    from wandb.proto import wandb_internal_pb2 as pb
    metric = pb.Record()
    metric.metric.name = "candidate/qm9.U0@linear64_relu/readout/loss"
    base = records()
    # Eight native records, with exactly two scientific history rows. Metric
    # definitions remain native ancillary records; they are not journal rows.
    native = [base[0], metric, base[1], metric, base[2], metric, *base[3:]]
    assert len(native) == 8
    monkeypatch.setattr(verify, "MAX_NATIVE_RECORDS", native_limit)
    monkeypatch.setattr(verify, "MAX_HISTORY_ROWS", 2)
    class SerializedStream:
        def __init__(self):
            self.rows = iter(row.SerializeToString() for row in native)
        def scan_data(self):
            return next(self.rows, None)
    stream = verify.scan_records(SerializedStream(), pb.Record, deadline=time.monotonic()+2)
    source = io.BytesIO(b"".join(verify.encoded(row) for row in sample_rows()))
    if native_limit == 7:
        with pytest.raises(ValueError, match="total-record budget"):
            compare(stream, rows=verify.journal_rows(source))
    else:
        result = compare(stream, rows=verify.journal_rows(source))
        assert result["native_records"] == 8 and result["record_types"]["metric"] == 3
        assert result["history_rows"] == 2 and result["clean_eof"]


def test_history_cap_still_rejects_extra_history_with_room_in_native_budget(monkeypatch):
    monkeypatch.setattr(verify, "MAX_HISTORY_ROWS", 1)
    assert verify.MAX_NATIVE_RECORDS == 500000
    with pytest.raises(ValueError, match="history-row budget"):
        compare(records())


def test_readonly_binding_rejects_symlink_and_raw_sha_drift(tmp_path):
    original = tmp_path / "original.json"
    original.write_text('{"status":"ok"}')
    with pytest.raises(ValueError, match="bytes differ"):
        verify.bound_json(original, "0"*64)
    link = tmp_path / "link.json"
    link.symlink_to(original)
    with pytest.raises(ValueError, match="physical"):
        verify.binding(link)


def test_admission_requires_successful_terminal_receipt_and_quota():
    admission = {"schema": "model_v3_primary512_metadata_admission_v1",
        "evaluation_job": {"job_id": "synthetic", "state": "COMPLETED", "exit_code": "0:0", "elapsed_seconds": 600},
        "evaluation_supervisor": {}, "launch_spec": {},
        "verification_admission": {"network_access": False, "gpu_requested": False,
            "max_output_bytes": verify.MAX_OUTPUT_BYTES, "max_source_bytes": verify.MAX_SOURCE_BYTES,
            "max_native_records": verify.MAX_NATIVE_RECORDS, "max_history_rows": verify.MAX_HISTORY_ROWS,
            "max_wall_seconds": verify.MAX_WALL_SECONDS,
            "quota": {"free_bytes": 40 << 30, "reserved_headroom_bytes": 32 << 30,
                "active_job_reserved_bytes": 0, "observed_at_utc": datetime.now(timezone.utc).isoformat()}}}
    verify.check_admission(admission, {"job_id": "synthetic"})
    admission["evaluation_job"]["state"] = "RUNNING"
    with pytest.raises(ValueError, match="terminal"):
        verify.check_admission(admission, {"job_id": "synthetic"})
    admission["evaluation_job"]["state"] = "COMPLETED"
    admission["verification_admission"]["quota"]["free_bytes"] = 32 << 30
    with pytest.raises(ValueError, match="Quota headroom"):
        verify.check_admission(admission, {"job_id": "synthetic"})


def panel_fixture():
    architecture, state, random_state = "a"*64, "b"*64, "c"*64
    tasks = [{"task_id": task, "error_metric": "one_minus_hit1" if task.startswith("cyp.") else "mae",
        "unit": "binary" if task.startswith("cyp.") else "source_unit"} for task in sorted(verify.TASKS)]
    panel = {"tasks": tasks, "uncertainty": {"bootstrap_samples": 1000, "confidence": .95,
        "paired": True, "same_draw_across_tasks_and_readouts_within_dataset": True, "seed": 20261025},
        "readouts": {"linear64_relu": {"epochs": 20, "batch_graphs": 32, "seed": 0}}}
    checkpoint = {"path": "/fixture/model.pt", "sha256": "d"*64, "state_key": "model_state"}
    request = {"reference_kind": "primary", "architecture_sha256": architecture,
        "preregistration_sha": verify.PREREGISTRATION, "checkpoint": checkpoint, "pretraining_seed": 0,
        "model_configuration": {"path": "/fixture/A00.json", "sha256": "f"*64}}
    result = {"status": "COMPLETED", "reference_kind": "primary", "architecture_sha256": architecture,
        "preregistration_sha": verify.PREREGISTRATION, "random_reference_initialization_seed": 20261025,
        "pretraining_seed": 0, "readout_seed": 0, "membership_sha256": {d: "m"*64 for d in report.DATASETS},
        "h0_packing_plan_sha256": {d: "p"*64 for d in report.DATASETS}, "h0_packing_budget_sha256": "q"*64,
        "h0_effective_runtime_sha256": "r"*64, "h0_caches": {}, "summaries": {},
        "encoder_pair": {"reference_kind": "primary", "H0_dimension": 512,
            "architecture_sha256": architecture, "checkpoint": checkpoint, "random_reference_seed": 20261025,
            "original_configuration": request["model_configuration"],
            "pretraining_seed": 0, "checkpoint_encoder_state_sha256": state, "random_encoder_state_sha256": random_state,
            "historical_memory_implementation": None, "historical_reference": None,
            "checkpoint_schema": "source_training_checkpoint_v1"},
        "job_id": "fixture", "elapsed_seconds": 123., "gpu_peak_allocated_bytes": 200000,
        "wandb_history_independently_verified": False, "code_sha": "e"*40}
    for label in ("candidate", "reference"):
        for dataset in report.DATASETS:
            result["h0_caches"][label+"/"+dataset] = {"targets_cached": False, "molecules": 2, "atoms": 10,
                "DO_NOT_EXPORT_MEMBER_ID": "PRIVATE_NATIVE_UID", "binding": {"dimension": 512,
                    "architecture_sha256": architecture, "membership_sha256": "m"*64, "geometry_sha256": "g"*64,
                    "packing_budget_sha256": "q"*64, "packing_plan_sha256": "p"*64,
                    "effective_runtime_sha256": "r"*64, "encoder_sha256": state if label == "candidate" else random_state}}
    all_tasks = {}
    for method in sorted(verify.READOUTS):
        cells = {}
        for task in sorted(verify.TASKS):
            error = 1.2 if task in ("cyp.2D6", "qm9.U0", "qm9.alpha") and method == "ridge" else .8
            score = 1-error
            cells[task+"@"+method] = {"error": error, "reference_error": 1., "normalized_improvement": score,
                "bootstrap_ci": [score-.1, score+.1], "bootstrap_defined": 1000,
                "observed_labels": 50, "observed_molecules": 2}
        result["summaries"][method] = {"architecture_sha256": architecture, "complete": True,
            "bootstrap_samples": 1000, "bootstrap_defined": 1000, "bootstrap_unit": "molecule",
            "bootstrap_seed": 20261025, "bootstrap_ci": [-.1, .3], "tasks": cells,
            "mean_normalized_improvement": sum(c["normalized_improvement"] for c in cells.values())/9}
        all_tasks.update(cells)
    result["summaries"]["primary_18_cells"] = {**deepcopy(result["summaries"]["ridge"]), "tasks": deepcopy(all_tasks),
        "mean_normalized_improvement": sum(c["normalized_improvement"] for c in all_tasks.values())/18}
    guard = {"status": "COMPLETED", "child_returncode": 0, "preregistration_sha": verify.PREREGISTRATION,
        "inclusive_panel_wall_seconds": 124., "inclusive_one_GPU_hour_target_met": True}
    return result, guard, request, panel


def test_report_keeps_eighteen_cells_negative_ridge_and_memory_scope():
    result, guard, request, panel = panel_fixture()
    rows = report.validate_panel(result, guard, request, panel)
    assert len(rows) == 18
    assert len([row for row in rows if row["normalized_improvement"] < 0]) == 3
    text = report.make_markdown(result, guard, rows, {"status": "PENDING"})
    assert "qm9.U0@ridge" in text and "qm9.alpha@ridge" in text and "cyp.2D6@ridge" in text
    assert "not device-global" in text and "512-dimensional" in text and "single pretraining seed" in text
    assert "PRIVATE_NATIVE_UID" not in text and "PRIVATE_NATIVE_UID" not in json.dumps(rows)
    assert result["wandb_history_independently_verified"] is False


def test_single_run_csv_passes_existing_typed_summary_checker(tmp_path):
    result, guard, request, _ = panel_fixture()
    request["run_id"] = "primary512_fixture"
    result.update(data_version="selectedTRAIN-fixture", gpu_model="NVIDIA RTX 5090",
        gpu_uuid="GPU-12345678-1234-1234-1234-123456789abc")
    row = report.run_summary(result, guard, request, {"sha256": "f"*64}, {"independently_verified": False})
    destination = tmp_path / "run_summary.csv"
    report.write_csv(destination, [row])
    checker = Path(os.environ.get("SA3_REPOSITORY_CHECKER", str(Path(__file__).resolve().parents[3]
        / "MFM_model_v3_sa3/tools/check_repository.py")))
    spec = importlib.util.spec_from_file_location("readonly_existing_typed_csv_checker", checker)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    assert module.model_summary_csv("docs/model_v3/results/primary512_fixture.csv", destination.read_bytes())
    assert "member" not in destination.read_text().lower()


@pytest.mark.parametrize("drift", ("random_membership", "random_geometry", "random_state", "dimension", "bootstrap", "cell"))
def test_report_rejects_unmatched_or_incomplete_panel(drift):
    result, guard, request, panel = panel_fixture()
    cache = result["h0_caches"]["reference/qm9"]["binding"]
    if drift == "random_membership": cache["membership_sha256"] = "other"
    elif drift == "random_geometry": cache["geometry_sha256"] = "other"
    elif drift == "random_state": cache["encoder_sha256"] = "other"
    elif drift == "dimension": result["encoder_pair"]["H0_dimension"] = 384
    elif drift == "bootstrap": result["summaries"]["ridge"]["bootstrap_samples"] = 999
    elif drift == "cell": result["summaries"]["ridge"]["tasks"].pop("qm9.U0@ridge")
    with pytest.raises(ValueError):
        report.validate_panel(result, guard, request, panel)


def test_core_false_flag_needs_separate_successful_matching_certificate():
    result = {"wandb_history_independently_verified": False, "wandb_run_id": "fixture", "journal_records": 2}
    refs = {key: {"path": "/fixture/"+key, "sha256": key} for key in ("result", "guard", "request", "launch_spec", "admission")}
    assert report.verification_state(None, None, refs, result)["independently_verified"] is False
    cert = {"schema": "model_v3_primary512_native_history_verification_v1", "status": "VERIFIED",
        "wandb_history_independently_verified": True, "inputs": refs, "sdk_run_id": "fixture",
        "history_rows": 2, "native_records": 10, "sdk_exit_code": 0, "clean_eof": True,
        "reference_kind": "primary", "H0_dimension": 512, "layers": 6, "run_name": scope.RUN_NAME,
        "source_scope": {"export_job_id": "4520486"}, "formal_pretraining_complete": False, "architecture_selection_claimed": False}
    state = report.verification_state(cert, {"path": "/fixture/certificate"}, refs, result)
    assert state["independently_verified"] is True and result["wandb_history_independently_verified"] is False
    cert["inputs"] = deepcopy(refs); cert["inputs"]["request"]["sha256"] = "wrong"
    with pytest.raises(ValueError, match="another input"):
        report.verification_state(cert, {}, refs, result)


def primary_scope_fixture():
    result, guard, request, _ = panel_fixture()
    request.update(run_id=scope.RUN_NAME, code_sha=scope.EVALUATOR_CODE)
    result['code_sha'] = guard['code_sha'] = scope.EVALUATOR_CODE
    guard['cache_started_cold'] = True
    configuration = {'backbone': {'dim': 512, 'layers': 6}}
    exported = {'export_job_id': '4520486', 'export_code_sha': scope.EXPORT_CODE,
        'ready': {'optimizer_updates': 500}, 'checkpoint': {**request['checkpoint'], 'bytes': 10},
        'model_configuration': {**request['model_configuration'], 'bytes': 20},
        'architecture_sha256': request['architecture_sha256'], 'pretraining_seed': 0,
        'configuration': {'candidate': {'precision': 'fp32', 'fused_adamw': False}}}
    spec = {'schema': 'model_v3_primary512_dev9_external_launch_v2', 'reference_kind': 'primary',
        'code_sha': scope.EVALUATOR_CODE, 'H0_dimension': 512, 'export_job_id': '4520486', 'export_code_sha': scope.EXPORT_CODE,
        'architecture_selection_claimed': False, 'formal_pretraining_complete': False,
        'fresh_cache_required': True, 'native_fields_units_masks_atom_ids_changed': False,
        'counts': {'cyp_isoform': 1803, 'expansionrx': 5326, 'qm9': 10473}, 'expected_tasks': 9,
        'expected_comparison_cells': 18, 'readouts': ['ridge', 'linear64_relu'],
        'source_checkpoint': exported['checkpoint'], 'original_configuration': exported['model_configuration']}
    return result, guard, request, spec, configuration, exported


def test_primary_scope_accepts_compact_request_refs_and_full_byte_authority():
    scope.validate_primary_scope(*primary_scope_fixture())


@pytest.mark.parametrize('drift', ('historical384', 'layers', 'run_name', 'export457', 'fusedA06', 'no_cold_cache', 'architecture_winner', 'member_count'))
def test_primary_scope_rejects_wrong_checkpoint_lineage_and_scientific_overclaim(drift):
    result, guard, request, spec, configuration, exported = primary_scope_fixture()
    if drift == 'historical384': result['encoder_pair']['H0_dimension'] = 384
    elif drift == 'layers': configuration['backbone']['layers'] = 4
    elif drift == 'run_name': request['run_id'] = 'A06_short500_primary512_dev9_v1'
    elif drift == 'export457': exported['export_job_id'] = '4520457'
    elif drift == 'fusedA06': exported['configuration']['candidate']['fused_adamw'] = True
    elif drift == 'no_cold_cache': guard['cache_started_cold'] = False
    elif drift == 'architecture_winner': spec['architecture_selection_claimed'] = True
    elif drift == 'member_count': spec['counts']['qm9'] += 1
    with pytest.raises(ValueError):
        scope.validate_primary_scope(result, guard, request, spec, configuration, exported)


def test_native_sdk_run_name_is_verified_in_addition_to_random_sdk_id():
    native = records(); native[0].run.display_name = 'wrong_producer_name'
    with pytest.raises(ValueError, match='run name'):
        compare(native)


def test_successful_supervisor_requires_no_live_descendants_or_storage_failure():
    value = {'status': 'COMPLETED', 'exit_code': 0, 'job_id': 'unit', 'first_failure': None,
        'remaining': [], 'private_storage': {'first_sampling_failure': None}}
    scope.successful_supervisor(value, 'unit')
    value['remaining'] = [{'pid': 123}]
    with pytest.raises(ValueError, match='descendants'):
        scope.successful_supervisor(value, 'unit')
    value['remaining'] = []; value['private_storage']['first_sampling_failure'] = 'failed'
    with pytest.raises(ValueError, match='storage'):
        scope.successful_supervisor(value, 'unit')


def test_one_gpu_hour_claim_needs_both_actual_guard_and_outer_allocation_observations():
    guard = {'inclusive_panel_wall_seconds': 500., 'inclusive_one_GPU_hour_target_met': True}
    admission = {'evaluation_job': {'elapsed_seconds': 3700}}
    assert scope.timing_observation(guard, admission)['inclusive_one_gpu_hour_observed'] is False
    admission['evaluation_job']['elapsed_seconds'] = 600
    assert scope.timing_observation(guard, admission)['inclusive_one_gpu_hour_observed'] is True
    guard['inclusive_panel_wall_seconds'] = 3601.
    assert scope.timing_observation(guard, admission)['inclusive_one_gpu_hour_observed'] is False


def test_source_chain_uses_actual_frozen_admission_reader_and_rehashes_opaque_bundle(tmp_path):
    # A fully synthetic file bundle, consumed by the actual source-admission
    # implementation. This does not assert a real SDK, terminal job or A gate.
    import importlib.util
    helper_ref = verify.binding(scope.HELPER_PATH)
    loader = importlib.util.spec_from_file_location('frozen_primary_admission_fixture', scope.HELPER_PATH)
    helper = importlib.util.module_from_spec(loader); loader.loader.exec_module(helper)
    def write(name, value):
        path = tmp_path / name; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(verify.encoded(value)); return verify.binding(path)
    result, guard, request, spec, _, _ = primary_scope_fixture()
    options = {'precision': 'fp32', 'fused_adamw': False}
    recipe = {'backbone': {'dim': 512, 'layers': 6}, 'training': {'seed': 0}, 'phase1': {'performance_options': options}}
    recipe_ref = write('source/candidate_h0/model_configuration.json', recipe)
    run = {'input': 'native_s', 'smoke': False, 'fixed_batches': 20, 'trajectory_updates': 500,
        'seed': 0, 'code_sha': scope.EXPORT_CODE, 'candidate': options, 'source_sha256': {'unit.py': 'f'*64}}
    run['configuration_sha256'] = helper.canonical(run)
    run_ref = write('source/candidate_h0/a_run_configuration.json', run)
    provenance = {'seed': 0, 'code_sha': scope.EXPORT_CODE, 'source_inventory_sha256': helper.canonical(run['source_sha256']),
        'full_native_A_numeric_gates_passed': True, 'optimizer_updates': 500, 'formal_pretraining_complete': False,
        'A_resume_supported': False, 'consumed_base_records': 1000, 'performance_options': options}
    provenance_ref = write('source/candidate_h0/provenance.json', provenance)
    weights = tmp_path / 'source/candidate_h0/candidate.pt'; weights.write_bytes(b'opaque synthetic checkpoint; never torch.load')
    checkpoint = {**verify.binding(weights), 'state_key': 'model_state'}
    ready = {'schema': 'model_v3_A_H0_export_ready_v1', 'status': 'H0_BYTES_VERIFIED_PENDING_OUTER_JOB_TERMINAL',
        'code_sha': scope.EXPORT_CODE, 'optimizer_updates': 500, 'consumed_base_records': 1000,
        'resume_supported': False, 'generic_checkpoint_schema': 'source_training_checkpoint_v1',
        'training_rng_unchanged': True, 'training_rng_before': {'unit': 'same'}, 'training_rng_after': {'unit': 'same'},
        'checkpoint': checkpoint, 'model_configuration': recipe_ref, 'a_run_configuration': run_ref, 'provenance': provenance_ref,
        'source_inventory_sha256': provenance['source_inventory_sha256'], 'pretraining_seed': 0,
        'architecture_sha256': result['architecture_sha256'], 'H0_loader_provenance': {
            'H0_dimension': 512, 'reference_kind': 'primary', 'checkpoint_schema': 'source_training_checkpoint_v1',
            'architecture_sha256': result['architecture_sha256'], 'checkpoint': checkpoint,
            'original_configuration': recipe_ref, 'pretraining_seed': 0}}
    ready_ref = write('source/candidate_h0/READY.json', ready)
    supervisor_ref = write('source/supervisor.json', {'job_id': '4520486', 'status': 'COMPLETED', 'exit_code': 0,
        'first_failure': None, 'remaining_recorded_processes_before_retirement': [], 'private_storage_cleanup_errors': []})
    status_ref = write('source/run_status.json', {'job_id': '4520486', 'status': 'PAIRED_GATES_PASS',
        'failure': None, 'cleanup_errors': [], 'checkpoint_export': {'ready': ready_ref}})
    summary_ref = write('source/summary.json', {'status': 'PAIRED_GATES_PASS', 'full_A_numeric_acceptance': True,
        'fixed_batch_pass': True, 'trajectory_pass': True, 'input': 'native_s', 'smoke': False,
        'code_sha': scope.EXPORT_CODE, 'consumed_trajectory_base_records': 1000})
    export_admission = {'schema': 'model_v3_primary512_export_admission_v1', 'ready': ready_ref,
        'expected_export_code_sha': scope.EXPORT_CODE, 'export_job': {'job_id': '4520486', 'state': 'COMPLETED', 'exit_code': '0:0'},
        'supervisor': supervisor_ref, 'run_status': status_ref, 'summary': summary_ref}
    admission_ref = write('source/export_admission.json', export_admission)
    request.update(checkpoint={key: checkpoint[key] for key in ('path', 'sha256', 'state_key')},
        model_configuration={key: recipe_ref[key] for key in ('path', 'sha256')})
    result['encoder_pair'].update(checkpoint=request['checkpoint'], original_configuration=request['model_configuration'])
    request_ref = write('request.json', request)
    guard_ref = write('source/guard_code.json', {'source': 'fixture'})
    spec.update(request=request_ref, export_ready=ready_ref, export_terminal_admission=admission_ref,
        export_admission_implementation=helper_ref, source_checkpoint=checkpoint, original_configuration=recipe_ref, external_guard=guard_ref)
    spec_ref = write('launch_spec.json', spec)
    guard.update(spec_sha256=spec_ref['sha256'], guard_implementation=guard_ref)
    result['job_id'] = 'unit_eval'
    eval_supervisor = write('eval_supervisor.json', {'status': 'COMPLETED', 'exit_code': 0,
        'job_id': 'unit_eval', 'first_failure': None, 'remaining': [], 'private_storage': {'first_sampling_failure': None}})
    root_admission = {'evaluation_supervisor': eval_supervisor, 'launch_spec': spec_ref}
    refs = {'request': request_ref, 'launch_spec': spec_ref}
    source = scope.read_source_chain(result, guard, request, spec, root_admission, refs,
        binding=verify.binding, bound_json=verify.bound_json)
    assert source['export_job_id'] == '4520486' and source['export_bytes_rehashed_without_deserialization'] is True
    assert refs['export_checkpoint'] == verify.binding(weights)
    assert refs['export_model_configuration'] == recipe_ref
