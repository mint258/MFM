"""Synthetic retained-byte fixtures only; no actual jobs/model/data are run."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import random

import pytest

from phychem_mfm.phase1 import formal_gate as gate
from phychem_mfm.phase1 import trial_source_bridge as bridge_module
from test_phase1_formal_gate import case as legacy_gate_case


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return digest(json.dumps(value, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=False, allow_nan=False).encode())


def put(root, name, value):
    raw = value if isinstance(value, bytes) else (json.dumps(value, sort_keys=True) + "\n").encode()
    path = root / name
    path.write_bytes(raw)
    return {"path": str(path), "bytes": len(raw), "sha256": digest(raw)}


def snapshot(files):
    return b"".join(name.encode() + b"\0" + files[name] + b"\0" for name in sorted(files))


def differences(before, after):
    return [{"path": name, "producer_sha256": digest(before[name]) if name in before else None,
             "consumer_sha256": digest(after[name]) if name in after else None}
            for name in sorted(set(before) | set(after)) if before.get(name) != after.get(name)]


@pytest.fixture
def fixture(tmp_path):
    core_files = {f"phychem_mfm/model/core_{i:03}.py": f"CORE_{i}\n".encode() for i in range(120)}
    producer_files = {**core_files, "phychem_mfm/phase1/formal_gate.py": b"OLD_GATE\n",
                      "phychem_mfm/phase1/formal_runtime.py": b"OLD_RUNTIME\n"}
    prior_files = {**producer_files, "phychem_mfm/phase1/formal_gate.py": b"PRIOR_GATE\n",
                   "phychem_mfm/phase1/formal_runtime.py": b"PRIOR_RUNTIME\n",
                   "phychem_mfm/phase1/decontamination_v2.py": b"PRIOR_VALIDATOR\n",
                   "tests/test_phase1_runtime_compatibility.py": b"PRIOR_TEST\n"}
    consumer_files = {**prior_files, "phychem_mfm/phase1/formal_gate.py": b"BRIDGE_GATE\n",
                      "phychem_mfm/phase1/trial_source_bridge.py": b"BRIDGE_VALIDATOR\n",
                      "tests/test_phase1_trial_source_bridge.py": b"BRIDGE_TEST\n"}
    versions = {}
    for name, files, commit in (("producer", producer_files, "a" * 40),
                                ("prior_interface_source", prior_files, "b" * 40),
                                ("consumer", consumer_files, "c" * 40)):
        ref = put(tmp_path, name + ".bin", snapshot(files))
        versions[name] = {"commit": commit, "source_sha256": ref["sha256"], "snapshot": ref}
    table = [{"path": name, "bytes": len(raw), "sha256": digest(raw)} for name, raw in sorted(core_files.items())]
    prior_core = {"schema_version": "phase1_lf_archive_core_byte_compatibility_v1",
                  "baseline_archive_source_digest": {"sha256": versions["producer"]["source_sha256"]},
                  "candidate_archive_source_digest": {"sha256": versions["prior_interface_source"]["source_sha256"]},
                  "scientific_files_checked": 120, "unchanged_scientific_files": table}
    prior_ref = put(tmp_path, "prior_core.json", prior_core)
    new_core = {"schema_version": "phase1_trial_bridge_core_bytes_v1",
                "producer_source_sha256": versions["producer"]["source_sha256"],
                "prior_interface_source_sha256": versions["prior_interface_source"]["source_sha256"],
                "consumer_source_sha256": versions["consumer"]["source_sha256"],
                "scientific_files": table, "interface_differences": differences(producer_files, consumer_files)}
    data = {"source_manifest": put(tmp_path, "train.json", {"kind": "train", "member_order": [3, 7]}),
            "validation_manifest": put(tmp_path, "validation.json", {"kind": "validation", "member_order": [1]}),
            "normalization": put(tmp_path, "controls.json", {"synthetic_controls": True}),
            "normalization_train_ids": put(tmp_path, "fit_ids.json", {"train_ids": [3, 7]})}
    split = put(tmp_path, "split.json", {"schema_version": "phase1_split_v1",
                "train": json.loads(Path(data["source_manifest"]["path"]).read_bytes()),
                "validation": json.loads(Path(data["validation_manifest"]["path"]).read_bytes())})
    science = {"schema_version": "phase1_scientific_protocol_v1", "state": "frozen",
               "scientific_choices_complete": True,
               "source": {"producer_commit": versions["producer"]["commit"],
                          "producer_source_sha256": versions["producer"]["source_sha256"],
                          "core_byte_compatibility": prior_ref},
               "data": {key: data[name] for name, key in (("source_manifest", "train_manifest"),
                        ("validation_manifest", "validation_manifest"), ("normalization", "fitted_controls"),
                        ("normalization_train_ids", "normalization_fit_ids"))}}
    science["content_sha256"] = canonical(science)
    trial = {"status": "CLOSED_BOUNDED_FULL_FIT_COST_VERIFIED", "last_child_exitcode": 0,
             "source": {"git_commit": versions["producer"]["commit"],
                        "source_sha256": versions["producer"]["source_sha256"]},
             "input_sha256": {ref["path"]: ref["sha256"] for name, ref in data.items() if name != "validation_manifest"}}
    trial_refs = {"summary": put(tmp_path, "original_trial.json", trial),
                  "training_log": put(tmp_path, "original_steps.jsonl", b'{"synthetic_update":1}\n'),
                  "gradient_checks": put(tmp_path, "original_gradients.json", {"synthetic_gradient_scope": "one batch"}),
                  "tracking": put(tmp_path, "original_tracking.json", {"synthetic_persisted_history": True})}
    interface = {"schema_version": "phase1_actual_v2_metadata_consumer_verification_v1",
                 "status": "COMPLETE_ACTUAL_KNOWN_AND_UNRESOLVED_NON_H_METADATA_PROOF",
                 "complete": True, "process_exitcode": 0, "job_id": "4511947",
                 "source_before": {"source_sha256": versions["prior_interface_source"]["source_sha256"], "git_commit": "unavailable"},
                 "source_after": {"source_sha256": versions["prior_interface_source"]["source_sha256"], "git_commit": "unavailable"},
                 "producer_source": {"actual_source_sha256": versions["producer"]["source_sha256"]},
                 "unchanged_core_files_verified": 120, "actual_train_records": 49993, "actual_validation_records": 7996,
                 "molecular_perception_or_fit_or_model_or_target_values_run": False}
    execution = {"summary": put(tmp_path, "interface.json", interface),
                 "child_exitcode": put(tmp_path, "child.exit", b"0\n"),
                 "console_exitcode": put(tmp_path, "console.exit", b"0\n"),
                 "accounting": put(tmp_path, "accounting.txt", b"4511947|zixiao|compute-0-20|2|COMPLETED|0:0\n"),
                 "accounting_exitcode": put(tmp_path, "accounting.exit", b"0\n")}
    document = {"schema_version": bridge_module.BRIDGE_SCHEMA,
                "scientific_authority": put(tmp_path, "science.json", science), **versions,
                "data_bindings": data, "trial_raw_artifacts": trial_refs,
                "prior_core_compatibility": prior_ref, "core_compatibility": put(tmp_path, "new_core.json", new_core),
                "interface_consumer_execution": execution, "old_optimizer_executed_on_consumer_source": False}
    protocol = {"source": {"commit": versions["consumer"]["commit"], "source_sha256": versions["consumer"]["source_sha256"]},
                "data": {"source_manifest_sha256": data["source_manifest"]["sha256"],
                         "split_manifest_sha256": split["sha256"], "normalization_sha256": data["normalization"]["sha256"],
                         "normalization_train_ids_sha256": data["normalization_train_ids"]["sha256"]},
                "trial_evidence": {"source_sha256": versions["producer"]["source_sha256"],
                                   "data_sha256": data["source_manifest"]["sha256"],
                                   **{name + "_sha256": ref["sha256"] for name, ref in trial_refs.items()}}}
    state = {"root": tmp_path, "bridge": document, "protocol": protocol,
             "artifacts": {"data.split_manifest_sha256": Path(split["path"])}, "consumer_files": consumer_files,
             "producer_files": producer_files,
             "new_core": new_core, "interface": interface, "trial": trial}
    reseal(state)
    return state


def reseal(state):
    ref = put(state["root"], "bridge.json", state["bridge"])
    state["protocol"]["trial_evidence"]["producer_consumer_bridge_sha256"] = ref["sha256"]
    state["artifacts"][bridge_module.BRIDGE_FIELD] = Path(ref["path"])


def verify(state):
    return bridge_module.verify_trial_producer_consumer_bridge(state["protocol"], state["artifacts"])


def test_three_actual_snapshots_and_original_evidence_are_checked_without_replay_or_writes(fixture):
    before = {p.name: digest(p.read_bytes()) for p in fixture["root"].iterdir()}
    rng = random.getstate()
    proof = verify(fixture)
    assert proof["actual_scientific_core_files_checked"] == 120
    assert proof["producer_source_sha256"] != proof["consumer_source_sha256"]
    assert proof["old_optimizer_executed_on_consumer_source"] is False
    assert proof["interface_consumer_job_id"] == "4511947"
    assert random.getstate() == rng
    assert {p.name: digest(p.read_bytes()) for p in fixture["root"].iterdir()} == before


@pytest.mark.parametrize("defect", ["changed_core_bytes", "new_candidate_is_prior", "scope119", "duplicate_core",
                                     "core_bytecount_bool", "undocumented_interface", "changed_model_module", "false_diff_list"])
def test_resealed_source_or_core_tampering_is_rejected(fixture, defect):
    doc, core = fixture["bridge"], deepcopy(fixture["new_core"])
    if defect in {"changed_core_bytes", "changed_model_module", "undocumented_interface"}:
        files = dict(fixture["consumer_files"])
        name = {"changed_core_bytes": "phychem_mfm/model/core_000.py",
                "changed_model_module": "phychem_mfm/model/new_model.py",
                "undocumented_interface": "tools/unknown_override.py"}[defect]
        files[name] = b"CHANGED\n"
        ref = put(fixture["root"], "consumer.bin", snapshot(files))
        doc["consumer"]["snapshot"], doc["consumer"]["source_sha256"] = ref, ref["sha256"]
        fixture["protocol"]["source"]["source_sha256"] = ref["sha256"]
        core["consumer_source_sha256"] = ref["sha256"]
        core["interface_differences"] = differences(fixture["producer_files"], files)
    elif defect == "new_candidate_is_prior":
        core["consumer_source_sha256"] = doc["prior_interface_source"]["source_sha256"]
    elif defect == "scope119":
        core["scientific_files"] = core["scientific_files"][:-1]
    elif defect == "duplicate_core":
        core["scientific_files"][-1] = deepcopy(core["scientific_files"][0])
    elif defect == "core_bytecount_bool":
        core["scientific_files"][0]["bytes"] = True
    else:
        core["interface_differences"] = []
    doc["core_compatibility"] = put(fixture["root"], "new_core.json", core)
    reseal(fixture)
    with pytest.raises(bridge_module.TrialSourceBridgeError):
        verify(fixture)


@pytest.mark.parametrize("field,value", [("complete", False), ("process_exitcode", 1), ("process_exitcode", False),
                                         ("unchanged_core_files_verified", 119), ("job_id", "4511945"),
                                         ("molecular_perception_or_fit_or_model_or_target_values_run", True)])
def test_resealed_prior_execution_does_not_become_a_new_actual_trial(fixture, field, value):
    interface = deepcopy(fixture["interface"])
    interface[field] = value
    fixture["bridge"]["interface_consumer_execution"]["summary"] = put(fixture["root"], "interface.json", interface)
    reseal(fixture)
    with pytest.raises(bridge_module.TrialSourceBridgeError):
        verify(fixture)


@pytest.mark.parametrize("slot,raw", [("child_exitcode", b"1\n"), ("console_exitcode", b"142\n"),
                                     ("accounting_exitcode", b"1\n"),
                                     ("accounting", b"4511947|zixiao|compute-0-20|2|FAILED|1:0\n"),
                                     ("accounting", b"4511947|another_user|compute-0-20|2|COMPLETED|0:0\n")])
def test_closed_exit_and_owner_accounting_are_not_replaced_by_complete_true(fixture, slot, raw):
    fixture["bridge"]["interface_consumer_execution"][slot] = put(fixture["root"], "changed_execution.txt", raw)
    reseal(fixture)
    with pytest.raises(bridge_module.TrialSourceBridgeError):
        verify(fixture)


@pytest.mark.parametrize("defect", ["old_optimizer_reran", "trial_source_changed", "trial_data_changed",
                                     "ref_length_bool", "raw_slot_replaced", "split_member_order_changed"])
def test_original_source_data_and_raw_trial_domains_remain_distinct(fixture, defect):
    doc = fixture["bridge"]
    if defect == "old_optimizer_reran":
        doc["old_optimizer_executed_on_consumer_source"] = True
    elif defect == "trial_source_changed":
        fixture["protocol"]["trial_evidence"]["source_sha256"] = doc["consumer"]["source_sha256"]
    elif defect == "trial_data_changed":
        fixture["protocol"]["trial_evidence"]["data_sha256"] = "f" * 64
    elif defect == "ref_length_bool":
        doc["producer"]["snapshot"]["bytes"] = True
    elif defect == "raw_slot_replaced":
        doc["trial_raw_artifacts"]["training_log"] = put(fixture["root"], "new_fake_log.json", {"fake": True})
    else:
        ref = put(fixture["root"], "split.json", {"schema_version": "phase1_split_v1",
                  "train": {"kind": "train", "member_order": [7, 3]},
                  "validation": {"kind": "validation", "member_order": [1]}})
        fixture["protocol"]["data"]["split_manifest_sha256"] = ref["sha256"]
    reseal(fixture)
    with pytest.raises(bridge_module.TrialSourceBridgeError):
        verify(fixture)


@pytest.mark.parametrize("raw", [b'{"schema_version":"x","schema_version":"y"}', b'{"invalid":NaN}', b'{"invalid":1e999}'])
def test_actual_bridge_hash_cannot_make_ambiguous_or_nonfinite_json_valid(fixture, raw):
    ref = put(fixture["root"], "bridge.json", raw)
    fixture["protocol"]["trial_evidence"]["producer_consumer_bridge_sha256"] = ref["sha256"]
    with pytest.raises(bridge_module.TrialSourceBridgeError):
        verify(fixture)


def test_legacy_equal_source_gate_path_is_unchanged(tmp_path):
    case = legacy_gate_case.__wrapped__(tmp_path)
    report = gate.check_formal_gate(**case)
    assert report.status == "REVIEW_ONLY" and not report.issues
    case["protocol"]["trial_evidence"]["source_sha256"] = "f" * 64
    case["protocol"]["content_sha256"] = gate.canonical_sha256(case["protocol"], omit_content_hash=True)
    assert "protocol.trial_source" in {i.code for i in gate.check_formal_gate(**case).issues}


def test_gate_source_exception_requires_actual_bridge_not_just_an_optional_hash(fixture, tmp_path):
    legacy_root = tmp_path / "legacy"
    legacy_root.mkdir()
    case = legacy_gate_case.__wrapped__(legacy_root)
    partial = fixture["protocol"]
    for section in ("source", "data", "trial_evidence"):
        case["protocol"][section].update(partial[section])
    for name, ref in fixture["bridge"]["trial_raw_artifacts"].items():
        case["artifacts"][bridge_module.TRIAL_FIELDS[name]] = Path(ref["path"])
    for name, field in bridge_module.DATA_FIELDS.items():
        case["artifacts"][field] = Path(fixture["bridge"]["data_bindings"][name]["path"])
    case["artifacts"]["source.source_sha256"] = Path(fixture["bridge"]["consumer"]["snapshot"]["path"])
    case["artifacts"].update(fixture["artifacts"])
    case["protocol"]["content_sha256"] = gate.canonical_sha256(case["protocol"], omit_content_hash=True)
    report = gate.check_formal_gate(**case)
    assert report.status == "REVIEW_ONLY" and not report.issues
    assert not report.may_start_formal_training
    fixture["bridge"]["old_optimizer_executed_on_consumer_source"] = True
    reseal(fixture)
    case["protocol"]["trial_evidence"]["producer_consumer_bridge_sha256"] = fixture["protocol"]["trial_evidence"]["producer_consumer_bridge_sha256"]
    case["protocol"]["content_sha256"] = gate.canonical_sha256(case["protocol"], omit_content_hash=True)
    assert "artifact.trial_source_bridge" in {i.code for i in gate.check_formal_gate(**case).issues}
    del case["artifacts"][bridge_module.BRIDGE_FIELD]
    assert "artifact.unverified" in {i.code for i in gate.check_formal_gate(**case).issues}
