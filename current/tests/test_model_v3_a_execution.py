from copy import deepcopy
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch


def module(monkeypatch, name):
    root = Path(__file__).absolute().parents[2] / "tools/model_v3"
    monkeypatch.syspath_prepend(str(root))
    spec = importlib.util.spec_from_file_location("model_v3_a_test_" + name, root / (name + ".py"))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def test_input_receipt_detects_same_ids_with_changed_noise_and_reset_restores(monkeypatch):
    runtime = module(monkeypatch, "a_execution_runtime")
    stream_type = module(monkeypatch, "s_input_stream").SInputStream
    stream = stream_type({}, seed=19, input_kind="synthetic")
    first = stream.next()
    receipt = runtime.corpus_receipt(first)
    first.encoder_batch.pos[0, 0] += 1
    altered = runtime.corpus_receipt(first)
    assert altered["record_keys"] == receipt["record_keys"]
    assert altered["receipt_sha256"] != receipt["receipt_sha256"]
    stream.commit(first)
    assert stream.state_dict()["committed_base_samples"] == 3
    stream.reset()
    assert runtime.corpus_receipt(stream.next()) == receipt
    assert stream.state_dict()["committed_base_samples"] == 0
    stream.close()


def test_stream_reset_refuses_live_workers_before_changing_committed_cursor(monkeypatch):
    stream_type = module(monkeypatch, "s_input_stream").SInputStream
    stream = stream_type({}, seed=19, input_kind="synthetic")
    stream.commit(stream.next())
    worker = SimpleNamespace(is_alive=lambda: True, exitcode=None)
    stream.iterator = SimpleNamespace(iterator=SimpleNamespace(_workers=[worker]), close=lambda: None)
    with pytest.raises(RuntimeError, match="workers actually exited"):
        stream.reset()
    assert stream.state_dict()["committed_base_samples"] == 3


def test_stream_adapter_passes_raw_snapshot_pin_and_keeps_reference_grouping(tmp_path, monkeypatch):
    runtime = module(monkeypatch, "a_execution_runtime")
    import s_input_stream
    received = []
    monkeypatch.setattr(s_input_stream, "SInputStream", lambda reference, **kwargs: received.append(kwargs))
    args = arguments(tmp_path, atom_bucket_width=8, exact_atom_sort=True)
    args.seed = 0
    runtime.stream_for(args, {}, candidate=False)
    runtime.stream_for(args, {}, candidate=True)
    assert received[0]["snapshot_sha256"] == received[1]["snapshot_sha256"] == "c" * 64
    assert received[0]["atom_bucket_width"] is None and not received[0]["exact_atom_sort"]
    assert received[1]["atom_bucket_width"] == 8 and received[1]["exact_atom_sort"]


def arguments(tmp_path, **overrides):
    values = dict(resume=None, code_sha="a" * 40, prereg_sha="b" * 40, workers=8,
        max_padded_cost=8_000_000, atom_bucket_width=None, exact_atom_sort=False,
        input="native_s", shard_snapshot_sha256="c" * 64, output=tmp_path / "fresh")
    return SimpleNamespace(**{**values, **overrides})


def test_paired_rejects_resume_and_regrouping_but_standalone_allows_exploration(tmp_path, monkeypatch):
    runtime = module(monkeypatch, "a_execution_runtime")
    monkeypatch.setenv("SLURM_JOB_ID", "123456")
    monkeypatch.setenv("SLURM_CPUS_PER_TASK", "16")
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "GPU-abcd-1234")
    with pytest.raises(ValueError, match="do not resume"):
        runtime.validate_arguments(arguments(tmp_path, resume=tmp_path / "old"), paired=True)
    with pytest.raises(ValueError, match="regroup optimizer batches"):
        runtime.validate_arguments(arguments(tmp_path, atom_bucket_width=8), paired=True)
    assert runtime.validate_arguments(arguments(tmp_path, atom_bucket_width=8), paired=False) == "GPU-abcd-1234"
    with pytest.raises(ValueError, match="original shard"):
        runtime.validate_arguments(arguments(tmp_path, shard_snapshot_sha256=None), paired=True)
    assert not (tmp_path / "fresh").exists()


def test_a_reference_bindings_include_actual_entry_loss_config_and_options(tmp_path, monkeypatch):
    runtime = module(monkeypatch, "a_execution_runtime")
    monkeypatch.setenv("SLURM_JOB_ID", "123456")
    args = arguments(tmp_path)
    args.reference_config = runtime.REPO / "workflows/sprime_s/formal_s/B1_seed0_v2.json"
    args.candidate_options = runtime.REPO / "current/configs/model_v3/performance/a00_control.json"
    args.seed = 0
    reference, a4, config, binding = runtime.load_references(args)
    assert config["backbone"]["dim"] == 512 and config["backbone"]["layers"] == 6
    assert binding["loss_weights"]["denoise_sigma"] == .1
    assert binding["supervision"]["objectives"] == ["bond", "element", "geometry"]
    assert binding["reference_configuration"]["sha256"] == runtime.digest(args.reference_config)
    assert {"tools/model_v3/paired_a_acceptance.py", "tools/model_v3/single_a_benchmark.py",
            "tools/model_v3/a_speed_report.py", "tools/model_v3/s_input_stream.py"} <= set(binding["source_sha256"])
    assert binding["candidate_options_sha256"] == runtime.digest(args.candidate_options)


def members_fixture(runtime):
    members = []
    for position, seconds in enumerate((2., 1., 1., 2.), 1):
        config = {key: {} for key in ("model", "optimizer", "loss_policy", "loss_weights", "supervision",
            "schedule", "reference_configuration", "a4_configuration", "data_version")}
        config.update(original_shard_snapshot_prejob_sha256="c" * 64, job_id=str(position))
        config["configuration_sha256"] = runtime.canonical_sha(config)
        summary = dict(series_id="series", code_sha="a" * 40, prereg_sha="b" * 40,
            gpu_uuid="GPU-1234", gpu_name="RTX4090", seed=0, input="native_s", smoke=False,
            measured_updates=20, warmup_updates=2, candidate_options_sha256="d" * 64,
            role=("reference", "candidate", "candidate", "reference")[position - 1], abba_position=position,
            status="STANDALONE_TIMING_COMPLETED", elapsed_window_seconds=seconds,
            measured_base_records=60, measured_native_atoms=600,
            input_receipts_sha256="e" * 64, padding_exploration=False, foreign_gpu_risk_observed=False,
            configuration_sha256=config["configuration_sha256"])
        members.append({"summary": summary, "configuration": config,
            "run_status": {"status": summary["status"], "failure": None, "cleanup_errors": [],
                           "stream_cleanup": {"input_descriptors_closed": True}},
            "supervisor": {"status": "COMPLETED", "exit_code": 0, "first_failure": None,
                           "gpu_uuid": summary["gpu_uuid"], "job_id": str(position)}})
    return members


def test_abba_speed_never_substitutes_for_numeric_gate_and_rejects_wrong_identity(monkeypatch):
    report = module(monkeypatch, "a_speed_report")
    runtime = module(monkeypatch, "a_execution_runtime")
    members = members_fixture(runtime)
    result = report.summarize_abba(members)
    assert result["speedup_candidate_over_reference"] == 2.
    assert not result["has_matched_A_numeric_acceptance"] and not result["scientific_speed_comparison"]
    members[2]["summary"]["gpu_uuid"] = "GPU-OTHER"
    with pytest.raises(ValueError, match="bindings differ"):
        report.summarize_abba(members)


@pytest.mark.parametrize("change", ["cleanup_failure", "configuration_changed", "partial", "order"])
def test_abba_rejects_nonterminal_or_changed_member_evidence(monkeypatch, change):
    report = module(monkeypatch, "a_speed_report")
    runtime = module(monkeypatch, "a_execution_runtime")
    members = members_fixture(runtime)
    if change == "cleanup_failure":
        members[1]["run_status"]["cleanup_errors"] = ["SDK finish failed"]
    elif change == "configuration_changed":
        members[1]["configuration"]["model"] = {"dim": 1024}
    elif change == "partial":
        members[1]["supervisor"]["status"] = "FAILED"
    else:
        members[1]["summary"]["abba_position"] = 3
    with pytest.raises(ValueError):
        report.summarize_abba(members)


@pytest.mark.parametrize("reason", ["regrouped", "foreign"])
def test_abba_keeps_risky_or_regrouped_measurements_exploratory(monkeypatch, reason):
    report = module(monkeypatch, "a_speed_report")
    runtime = module(monkeypatch, "a_execution_runtime")
    members = members_fixture(runtime)
    if reason == "regrouped":
        members[1]["summary"].update(input_receipts_sha256="different", padding_exploration=True)
    else:
        members[1]["summary"]["foreign_gpu_risk_observed"] = True
    result = report.summarize_abba(members)
    assert result["speedup_candidate_over_reference"] is None
    assert not result["scientific_speed_comparison"]


def test_abba_requires_complete_numeric_gate_and_matching_native_stream(monkeypatch):
    report = module(monkeypatch, "a_speed_report")
    runtime = module(monkeypatch, "a_execution_runtime")
    members = members_fixture(runtime)
    gate = {"configuration": deepcopy(members[0]["configuration"]),
        "summary": {"full_A_numeric_acceptance": True, "status": "PAIRED_GATES_PASS",
            "candidate_options_sha256": "d" * 64, "code_sha": "a" * 40, "gpu_uuid": "GPU-1234",
            "configuration_sha256": members[0]["configuration"]["configuration_sha256"]},
        "run_status": {"status": "PAIRED_GATES_PASS", "failure": None, "cleanup_errors": [],
            "stream_cleanup": {"input_descriptors_closed": True}},
        "fixed_batch_gate": {"pass": True, "batches": 20, "results": [{"pass": True}] * 20},
        "trajectory_gate": {"pass": True, "updates": 500, "results": [{"pass": True}] * 500}}
    assert report.summarize_abba(members, numeric_gate=gate)["scientific_speed_comparison"]
    gate["trajectory_gate"]["results"].pop()
    with pytest.raises(ValueError, match="Complete20batch"):
        report.summarize_abba(members, numeric_gate=gate)


def test_abba_rejects_mixed_deterministic_control_evidence(monkeypatch):
    report = module(monkeypatch, "a_speed_report")
    runtime = module(monkeypatch, "a_execution_runtime")
    members = members_fixture(runtime)
    for item in members:
        receipt = {"requested": False, "actual": {"deterministic_algorithms": False},
            "torch_imported_before_binding": False, "cuda_initialized_before_apply": False}
        receipt["execution_sha256"] = runtime.canonical_sha({"requested": False, "actual": receipt["actual"],
            "preimport_binding_satisfied": True, "cuda_uninitialized_before_apply": True})
        item["configuration"]["deterministic_controls"] = receipt
        item["configuration"]["configuration_sha256"] = runtime.canonical_sha({key: value for key, value in
            item["configuration"].items() if key != "configuration_sha256"})
        item["summary"]["configuration_sha256"] = item["configuration"]["configuration_sha256"]
    assert report.summarize_abba(members)["speedup_candidate_over_reference"] == 2.
    receipt = members[1]["configuration"]["deterministic_controls"]
    receipt["actual"]["deterministic_algorithms"] = True
    receipt["execution_sha256"] = runtime.canonical_sha({"requested": False, "actual": receipt["actual"],
        "preimport_binding_satisfied": True, "cuda_uninitialized_before_apply": True})
    members[1]["configuration"]["configuration_sha256"] = runtime.canonical_sha({key: value for key, value in
        members[1]["configuration"].items() if key != "configuration_sha256"})
    members[1]["summary"]["configuration_sha256"] = members[1]["configuration"]["configuration_sha256"]
    with pytest.raises(ValueError, match="deterministic controls differ"):
        report.summarize_abba(members)
