"""Synthetic readiness mechanics only; no real Data release/labels accepted."""
from copy import deepcopy
from dataclasses import asdict, replace
import json
from pathlib import Path

import pytest
import torch

from phychem_mfm.phase1.v3_contract import (DisabledNormalization, FieldSpec, FieldTarget,
    LabelRegistry, LOSS_DISABLED_SCALE, TrainNormalization, canonical_hash)
from phychem_mfm.phase1.v3_data_adapter import (tensor6_normalization, tensor6_raw_mean_report,
    verify_release_binding, VerifiedDataRelease, make_proxy_inputs)
from phychem_mfm.phase1.v3_label_domains import tensor6_from_f64
from phychem_mfm.phase1.v3_losses import compute_v3_loss
from phychem_mfm.phase1.v3_training import ValidationAccumulator
from test_model_v3_data_adapter import metadata_case, ref, write


@pytest.fixture(autouse=True)
def one_cpu_thread():
    old = torch.get_num_threads(); torch.set_num_threads(1)
    try: yield
    finally: torch.set_num_threads(old)


def disabled(tmp_path, name="q", *, reason="ZERO", version="UNIT_FIXTURE_NOT_D3", suffix=""):
    path = tmp_path / ("actual_unit_stat" + suffix + ".json")
    body = {"UNIT_FIXTURE_ONLY": True, "n": 0 if reason == "EMPTY" else 2, "std_ddof0": None if reason == "EMPTY" else 0.}
    if path.exists():
        assert json.loads(path.read_text()) == body
        reference = ref(path)  # Preserve the actual checkpoint-era file identity/mtime.
    else:
        reference = write(path, body)
    return DisabledNormalization(name, "unit-target-" + name, reason, reference["sha256"], version,
        {"statistics_reference": reference, "statistics_pointer": [], "scope": "UNIT_SYNTHETIC_ONLY"})


def loss_case(tmp_path):
    registry = LabelRegistry((FieldSpec("q", "P", "physics", "graph", representation="symmetric_tensor6"),
                              FieldSpec("ready", "P", "physics", "graph")), "UNIT_FIXTURE_NOT_D3", "a" * 64)
    q = tensor6_from_f64(values=torch.tensor([[1., 2., 3., 4., 5., 6.], [2., 3., 4., 5., 6., 7.]], dtype=torch.float64),
        component_valid=torch.ones((2, 6), dtype=torch.bool), geometry_ids=("g0", "g1"),
        component_geometry_ids=(("g0",) * 6, ("g1",) * 6), reasons=({}, {}),
        source_ref={"path": "/unit-only/stat", "bytes": 1, "sha256": "f" * 64})
    targets = {"q": q, "ready": FieldTarget(torch.tensor([[1.], [2.]]), torch.ones(2, dtype=torch.bool))}
    predictions = {"q": torch.nn.Parameter(torch.zeros((2, 6))), "ready": torch.nn.Parameter(torch.zeros((2, 1)))}
    normalizations = {"q": disabled(tmp_path), "ready": TrainNormalization((0.,), (1.,), "b" * 64, registry.version)}
    return registry, predictions, targets, normalizations


def test_disabled_tensor_preserves_source_counts_masks_and_other_target_gradient(tmp_path):
    registry, predictions, targets, normalizations = loss_case(tmp_path)
    before_values, before_masks = targets["q"].values.clone(), targets["q"].component_valid.clone()
    loss = compute_v3_loss(predictions, targets, registry, normalizations, enabled_groups=("P",))
    assert loss.counts == {"q": 2, "ready": 2} and loss.loss_counts == {"q": 0, "ready": 2}
    assert loss.observed_fields == {"P": 1} and loss.metrics()["loss/q"] is None
    assert loss.metrics()["valid_count/q"] == 2 and loss.metrics()["loss_count/q"] == 0
    assert loss.audit_counts["q"]["source_valid_components"] == 12
    assert loss.audit_counts["q"]["pre_scale_eligible_tensors"] == 2
    assert loss.audit_counts["q"]["loss_eligible_tensors"] == 0
    loss.total.backward()
    assert predictions["q"].grad is None
    assert predictions["ready"].grad is not None and predictions["ready"].grad.abs().sum() > 0
    assert torch.equal(targets["q"].values, before_values) and torch.equal(targets["q"].component_valid, before_masks)
    assert not hasattr(normalizations["q"], "scale") and not hasattr(normalizations["q"], "transform")


def test_validation_loss_denominator_is_separate_from_raw_unit_metrics(tmp_path):
    registry, predictions, targets, normalizations = loss_case(tmp_path)
    loss = compute_v3_loss(predictions, targets, registry, normalizations, enabled_groups=("P",))
    metric = ValidationAccumulator(registry, role="VAL", enabled_groups=("P",))
    metric.add(predictions, targets, loss)
    result = metric.result()["fields"]
    assert result["q"]["valid_labels"] == 2 and result["q"]["loss_count"] == 0
    assert result["q"]["loss"] is None and result["q"]["loss_status"] == LOSS_DISABLED_SCALE
    assert result["q"]["MAE"] > 0 and result["q"]["Frobenius_SSE"] > 0
    assert result["ready"]["loss_count"] == 2 and result["ready"]["loss"] is not None


def test_legacy_loss_result_constructor_serialization_and_metrics_have_no_new_default_keys(tmp_path):
    registry, predictions, targets, norms = loss_case(tmp_path)
    norms["q"] = TrainNormalization((0.,), (1.,), "b" * 64, registry.version)
    # asdict deep-copies tensor fields; active nonleaf autograd graphs never
    # supported that protocol. Check the legacy metadata shape in evaluation.
    with torch.no_grad():
        result = compute_v3_loss(predictions, targets, registry, norms, enabled_groups=("P",))
    assert not result.has_loss_readiness and result.loss_counts == result.counts
    assert set(asdict(result)) == {"total", "fields", "groups", "counts", "observed_fields", "enabled_groups", "audit_counts"}
    assert not any(key.startswith(("loss_count/", "loss_status/", "loss_disabled_reason/")) for key in result.metrics())


def unavailable_release(tmp_path, change):
    evidence, request, projection, interpreter = metadata_case(tmp_path)
    raw = json.loads(Path(evidence["d4_statistics"]["path"]).read_text())
    row = raw["parameters"]["q"]
    if change == "missing": row["std_ddof0"] = None
    if change == "empty": row.update(n=0, std_ddof0=None, winsor_lower=None, winsor_upper=None)
    if change == "zero": row["std_ddof0"] = 0.
    if change == "underflow": row["std_ddof0"] = 1e-300
    if change == "negative": row["std_ddof0"] = -1.
    if change == "bounds": row.update(std_ddof0=0., winsor_lower=9., winsor_upper=1.)
    if change == "boolean": row["std_ddof0"] = False
    if change == "pointer": projection["D4_bindings"]["q"]["statistics_pointer"] = ["a_typo_not_a_missing_series"]
    if change == "nonfinite":
        body = json.dumps(raw).replace('"std_ddof0": 2.0', '"std_ddof0": 1e999')
        Path(evidence["d4_statistics"]["path"]).write_text(body)
        evidence["d4_statistics"] = ref(evidence["d4_statistics"]["path"])
    else:
        evidence["d4_statistics"] = write(Path(evidence["d4_statistics"]["path"]), raw)
    projection["evidence_sha256"] = canonical_hash(evidence)
    return verify_release_binding(request, evidence=evidence, verifier=interpreter(projection))


@pytest.mark.parametrize("change,reason", [("missing", "MISSING"), ("empty", "EMPTY"), ("zero", "ZERO"), ("underflow", "ZERO"), ("nonfinite", "NONFINITE")])
def test_only_explicit_actual_statistic_unavailability_gets_typed_target_local_state(tmp_path, change, reason):
    release = unavailable_release(tmp_path, change)
    state = tensor6_normalization(release, "q", target_local=True)
    assert isinstance(state, DisabledNormalization) and state.reason == reason and state.status == LOSS_DISABLED_SCALE
    assert state.evidence["statistics_reference"] == release.evidence["d4_statistics"]
    # Existing strict API remains strict; no pre-existing test is rewritten.
    with pytest.raises(ValueError): tensor6_normalization(release, "q")


@pytest.mark.parametrize("change", ["negative", "bounds", "boolean", "pointer"])
def test_schema_recipe_and_binding_errors_are_not_caught_as_target_disable(tmp_path, change):
    release = unavailable_release(tmp_path, change)
    with pytest.raises(ValueError): tensor6_normalization(release, "q", target_local=True)


def test_raw_mean_report_does_not_substitute_winsor_mean_or_block_ready_scale(tmp_path):
    evidence, request, projection, interpreter = metadata_case(tmp_path)
    raw = json.loads(Path(evidence["d4_statistics"]["path"]).read_text())
    raw["parameters"]["q"]["mean"] = 999.
    evidence["d4_statistics"] = write(Path(evidence["d4_statistics"]["path"]), raw)
    projection["evidence_sha256"] = canonical_hash(evidence)
    release = verify_release_binding(request, evidence=evidence, verifier=interpreter(projection))
    assert isinstance(tensor6_normalization(release, "q", target_local=True), TrainNormalization)
    report = tensor6_raw_mean_report(release, "q")
    assert report["status"] == "RAW_MEAN_F_REPORT_PENDING" and report["raw_mean_F"] is None
    assert report["raw_mean_F_over_s"] is None


@pytest.mark.parametrize("wrong", [False, True])
def test_raw_mean_ratio_uses_only_explicit_actual_same_population_value(tmp_path, wrong):
    evidence, request, projection, interpreter = metadata_case(tmp_path)
    mean_ref = write(tmp_path / "real_unit_raw_mean.json", {"record": {"n": 2, "mean" if wrong else "raw_mean_F": 6.}})
    binding = projection["D4_bindings"]["q"]
    binding["raw_mean_F_binding"] = {"reference": mean_ref, "record_pointer": ["record"],
        "series_key": binding["series_key"], "population_sha256": binding["population_sha256"],
        "heldout_exclusion_sha256": binding["heldout_exclusion_sha256"], "statistic": "RAW_UNWINSORIZED_FROBENIUS_MEAN"}
    release = verify_release_binding(request, evidence=evidence, verifier=interpreter(projection))
    if wrong:
        with pytest.raises(ValueError, match="raw_mean_F"): tensor6_raw_mean_report(release, "q")
    else:
        report = tensor6_raw_mean_report(release, "q")
        assert report["raw_mean_F"] == 6. and report["raw_mean_F_over_s"] == 3.
        assert report["source"] == mean_ref and report["current_centering_changed"] is False


def make_trainer_with_disposition(tmp_path, *, groups=("D", "P"), reason="ZERO", suffix="", tracker_id="unit-original"):
    from test_model_v3_structural import setup_model
    from test_model_v3_trainer import BoundSyntheticProvider, UnitTracker
    from phychem_mfm.phase1.v3_sampling import ConformerRef, InMemorySamplingIndex, MoleculeEntry, UniformMoleculeSampler
    from phychem_mfm.phase1.v3_trainer import SampleLRScheduler, V3StepTrainer
    from phychem_mfm.phase1.v3_training import SampleClock
    from phychem_mfm.training.losses import LossWeights
    model, base, registry, binding, norms, _ = setup_model()
    state = disabled(tmp_path, "new_energy", reason=reason, version=BoundSyntheticProvider.data_version, suffix=suffix)
    norms["new_energy"] = state
    index = InMemorySamplingIndex(tuple(MoleculeEntry(f"m{i}",
        (ConformerRef(f"c{i}", 0, 12, (("PM7", f"unit:{i}"),)),),
        (("S", True), ("D", True), ("P", True)),
        (("structural", True), ("physics", True), ("descriptor", True))) for i in range(2)), BoundSyntheticProvider.data_version)
    sampler = UniformMoleculeSampler(index, seed=101, sample_budget=4)
    provider = BoundSyntheticProvider(base, registry, binding, index)
    optimizer = torch.optim.AdamW(model.parameters(), lr=.003, weight_decay=0., foreach=False)
    scheduler = SampleLRScheduler(optimizer, sample_budget=4)
    bindings = {"code_sha": "c" * 40, "configuration_sha256": "e" * 64, "registry_sha256": registry.source_sha256,
        "normalization_sha256": canonical_hash({k: asdict(v) for k, v in norms.items()}), "data_version": provider.data_version}
    return V3StepTrainer(model, optimizer, scheduler, sampler, SampleClock(4, (2, 4)), provider, norms, LossWeights(),
        UnitTracker(tracker_id), bindings, enabled_groups=groups, allow_unit_tracker=True)


def test_other_target_really_updates_while_disabled_head_has_no_gradient_and_resume_binds_state(tmp_path):
    from test_model_v3_training import assert_tree_equal
    original = make_trainer_with_disposition(tmp_path)
    energy_head = original.model.pd_heads.field_heads[original.model.pd_heads.keys["new_energy"]]
    head_before = {k: v.clone() for k, v in energy_head.state_dict().items() if isinstance(v, torch.Tensor)}
    trainable_before = {k: v.clone() for k, v in original.model.state_dict().items() if "new_energy" not in k and isinstance(v, torch.Tensor)}
    row = original.next_step(2)
    assert row["optimizer_updated"] is True and row["valid_count/new_energy"] == 2
    assert row["loss_count/new_energy"] == 0 and row["loss/new_energy"] is None
    energy_parameters = tuple(energy_head.parameters())
    assert energy_parameters and all(p.grad is None for p in energy_parameters)
    assert head_before and all(torch.equal(energy_head.state_dict()[k], v) for k, v in head_before.items())
    assert any(not torch.equal(original.model.state_dict()[k], v) for k, v in trainable_before.items())
    original.save(tmp_path / "cp2", output_root=tmp_path)
    original.next_step(2)
    expected_model, expected_optimizer = deepcopy(original.model.state_dict()), deepcopy(original.optimizer.state_dict())
    restored = make_trainer_with_disposition(tmp_path, tracker_id="unit-resumed")
    restored.load(tmp_path / "cp2", output_root=tmp_path)
    restored.next_step(2)
    assert_tree_equal(expected_model, restored.model.state_dict())
    assert_tree_equal(expected_optimizer, restored.optimizer.state_dict())
    assert restored.clock.optimizer_updates == 2 and restored.clock.samples_consumed == 4
    changed = make_trainer_with_disposition(tmp_path, reason="EMPTY", suffix="_changed")
    before = deepcopy(changed.model.state_dict())
    assert changed.contract["normalization_projection"] != restored.contract["normalization_projection"]
    with pytest.raises(ValueError, match="binding|configuration"):
        changed.load(tmp_path / "cp2", output_root=tmp_path)
    assert_tree_equal(before, changed.model.state_dict())


def test_all_disabled_has_source_observations_but_no_optimizer_update(tmp_path):
    trainer = make_trainer_with_disposition(tmp_path, groups=("P",))
    row = trainer.next_step(2)
    assert row["valid_count/new_energy"] == 2 and row["loss_count/new_energy"] == 0
    assert row["optimizer_updated"] is False and row["gradient_norm_before_clip"] is None
    assert row["loss/total"] is None and trainer.clock.optimizer_updates == 0
    assert trainer.clock.samples_consumed == 2 and all(p.grad is None for p in trainer.model.parameters())


def test_structural_targets_keep_their_loss_population_with_a_disabled_physical_target(tmp_path):
    trainer = make_trainer_with_disposition(tmp_path, groups=("S", "D", "P"))
    row = trainer.next_step(2)
    assert row["optimizer_updated"] is True and row["loss_count/new_energy"] == 0
    for name in ("s_element", "s_noise", "s_bond", "new_atom"):
        assert row["valid_count/" + name] > 0
        assert row["loss_count/" + name] == row["valid_count/" + name]
        assert row["loss/" + name] is not None

def actual_schema_fixture(tmp_path, monkeypatch):
    """Only temporary metadata; never claims an actual job or Data authority."""
    import phychem_mfm.phase1.v3_data_adapter as adapter
    publication = tmp_path / "published"
    monkeypatch.setattr(adapter, "DATA_RELEASE_ROOT", publication)
    evidence = {key: write(tmp_path / ("evidence_" + key + ".json"), {"UNIT_FIXTURE_ONLY": True})
                for key in adapter.REQUIRED_EVIDENCE}
    base = write(tmp_path / "base_registry.json", {"UNIT_FIXTURE_ONLY": True})
    input_map = write(tmp_path / "input_map.json", {"UNIT_FIXTURE_ONLY": True})
    acknowledgement = write(tmp_path / "unit_ack.json", {"UNIT_FIXTURE_ONLY_NOT_A_SIGNATURE": True})
    joint = {"schema": "ROOT_MODEL_JOINT_FINAL_LABEL_POLICY_V1", "status": "JOINTLY_FROZEN",
        "root_review_reference": acknowledgement, "model_ack_reference": acknowledgement, "contract_reference": acknowledgement,
        "registry_source_reference": base, "mapping_source_reference": input_map}
    for key in ("actual_final_Model_ack_not_conditional", "root_signoff", "model_signoff", "partial_mask_policy_explicit",
                "r73_pair_dependent_double_basis_onsite_ordinal_explicit", "r674_native_symmetric6_no_trace_projection",
                "actual_child_coordinate_frames_explicit"): joint[key] = True
    evidence["joint_contract"] = write(tmp_path / "joint.json", joint)
    evidence["registry"] = write(tmp_path / "registry.json", {"status": "FROZEN_ACTUAL_DEFINITIONS_FAMILIES_AND_SCOPED_STATISTICS",
        "physical_joint_policy_reference": evidence["joint_contract"]})
    evidence["physical_mapping"] = write(tmp_path / "mapping.json", {"status": "FROZEN",
        "joint_policy_reference": evidence["joint_contract"], "registry_sha256": evidence["registry"]["sha256"]})
    row = {"target_id": "unit_q", "source_series_key": "physical/674/xtb_singlepoint/frobenius_norm",
        "n": 2, "std_ddof0": 2., "lower": 1., "upper": 5., "centering": "FIXED_ZERO", "center_value": 0.,
        "per_head_single_scale": True, "scale_rule": "SERIES_STD_DDOF0", "scale": 2.,
        "winsorization_only_statistical_copies": True, "original_training_labels_modified": False}
    evidence["d4_statistics"] = write(tmp_path / "norm.json", {"schema": "FINAL_TRAIN_TARGET_NORMALIZATION_CANDIDATE_V1",
        "status": "ACTUAL_SERIES_EXACT_JOINT_RECIPE_BOUND", "policy_reference": evidence["joint_contract"], "targets": {"unit_q": row}})
    outputs = {"registry_reference": evidence["registry"], "mapping_reference": evidence["physical_mapping"],
        "normalization_reference": evidence["d4_statistics"], "mask_release_reference": evidence["geometry"], "size_rho_reference": evidence["codebook"]}
    family = tmp_path / "family"; family.mkdir()
    request_body = {"scope_key": "family_export_day_v1", "cpus": 16, "wall_seconds": 86400,
                    "scope_parameters": {"output_directory": str(family)}}
    request_ref = write(tmp_path / "parent_request.json", request_body)
    startup = write(tmp_path / "startup.json", {"job_id": "990001", "request": request_body, "request_reference": request_ref})
    scope = "BOUNDED_D3_50K_TRAIN_5K_ROUTINE_VAL"
    directive = write(tmp_path / "directive.json", {"schema": "ROOT_FINAL_LABEL_RELEASE_DIRECTIVE_V1",
        "release_id": "unit_release", "release_scope": scope,
        "status": "ROOT_REVIEWED_ACTUAL_D4_AND_JOINT_POLICY_INPUTS", "reviewer": "root",
        "joint_policy_reference": evidence["joint_contract"], "base_registry_reference": base, "mapping_reference": input_map,
        "root_actual_d4_acceptance_reference": acknowledgement, "d4_closure_reference": acknowledgement})
    candidate = write(family / "candidate.json", {"schema": "FINAL_LABEL_RELEASE_CANDIDATE_V1",
        "release_id": "unit_release", "release_scope": scope,
        "status": "COMPLETE_EXACT_FINAL_CANDIDATE_REQUIRES_ACTUAL_PARENT_C0_AND_ROOT_SEAL",
        "current_actual_parent_job_id": "990001", "current_startup_proof_reference": startup,
        "current_parent_C0_claimed": False, "joint_policy_reference": evidence["joint_contract"],
        "root_reviewed_directive_reference": directive, **outputs})
    raw_path = tmp_path / "sacct.txt"
    raw_path.write_text("JobIDRaw|UID|State|ExitCode|AllocCPUS\n990001|1278|COMPLETED|0:0|16\n")
    raw = ref(raw_path)
    accounting = write(tmp_path / "accounting.json", {"schema": "DATA_V1_PARENT_ACCOUNTING_CLOSURE_V1",
        "status": "ACTUAL_PARENT_ACCOUNTING_CLOSED", "endpoint": "202.38.247.57:22", "uid": 1278,
        "query_returncode": 0, "raw_sacct_reference": raw,
        "parents": [{"job_id": "990001", "state": "COMPLETED", "exit_code": "0:0", "alloc_cpus": 16}]})
    parents = {"candidate": candidate, "startup_proof": startup, "accounting": accounting, "raw": raw}
    before = write(tmp_path / "before_review.json", {"schema": "FINAL_LABEL_POST_C0_ROOT_REVIEW_CANDIDATE_V1",
        "status": "PENDING_INDEPENDENT_ROOT_FINAL_REVIEW", "release_id": "unit_release", "release_scope": scope,
        "root_reviewed_directive_reference": directive,
        "actual_parent_references": parents, "exact_outputs": outputs, "joint_policy_reference": evidence["joint_contract"]})
    review = write(tmp_path / "review.json", {"schema": "ROOT_FINAL_LABEL_PUBLICATION_REVIEW_V1",
        "status": "APPROVED_EXACT_ACTUAL_C0_RELEASE", "reviewer": "root", "joint_policy_reference": evidence["joint_contract"],
        "exact_outputs": outputs, "candidate_reference": before})
    scope = "BOUNDED_D3_50K_TRAIN_5K_ROUTINE_VAL"
    publication = publication / "unit_release"; publication.mkdir(parents=True)
    wrappers = {}
    filenames = {"registry_reference": "label_registry_v3.json", "mapping_reference": "physical_target_mapping_v3.json",
                 "normalization_reference": "normalization_v1.json", "mask_release_reference": "validity_masks_v1.json",
                 "size_rho_reference": "size_families_v1.json"}
    for key, output in outputs.items():
        wrappers[key] = write(publication / filenames[key], {"schema": "FINAL_LABEL_CONFIGURATION_REFERENCE_V1",
            "status": "FROZEN_BOUNDED_DIAGNOSTIC_P_D_SCOPE", "configuration_kind": key, "configuration_reference": output,
            "release_scope": scope, "actual_parent_references": parents, "joint_policy_reference": evidence["joint_contract"],
            "root_publication_review_reference": review})
    release = {"schema": "ROOT_FINAL_LABEL_RELEASE_V1", "status": "BOUNDED_DIAGNOSTIC_P_D_RELEASE_NOT_FULL_V1",
        "release_scope": scope, "release_id": "unit_release", "final_consumer_release": True,
        "D2_published": True, "D4_P_D_published": True, "training_ready": False, "D4_published": False,
        "independent_Pprime_published": False, "joint_policy_reference": evidence["joint_contract"],
        "root_publication_review_reference": review, "actual_parent_references": parents,
        "candidate_reference": candidate, "configurations": wrappers, "UNIT_FIXTURE_ONLY_NOT_A_REAL_RELEASE": True, **outputs}
    evidence["release"] = write(publication / "release.json", release)
    documents = {key: json.loads(Path(value["path"]).read_text()) for key, value in evidence.items()}
    return adapter, evidence, documents, {"mode": "authoritative_pilot"}


def test_actual_producer_schema_joins_all_metadata_without_granting_fixture_authority(tmp_path, monkeypatch):
    adapter, evidence, documents, request = actual_schema_fixture(tmp_path, monkeypatch)
    adapter._actual_final_release(documents, evidence, request)  # Structural fixture check, not a job closure.
    # Public admission must refuse the explicit synthetic marker even though
    # this private schema fixture is internally joined and byte-bound.
    with pytest.raises(ValueError, match="Synthetic fixtures"):
        adapter.verify_release_binding(request, evidence=evidence, verifier=evidence["codebook"])


@pytest.mark.parametrize("corruption", ["ack", "mapping", "parent", "wrapper", "wrapper_path", "release_id", "bounded_as_full"])
def test_actual_data_header_does_not_replace_exact_ack_mapping_parent_and_wrapper_bindings(tmp_path, monkeypatch, corruption):
    adapter, evidence, documents, request = actual_schema_fixture(tmp_path, monkeypatch)
    if corruption == "ack": documents["joint_contract"]["actual_final_Model_ack_not_conditional"] = False
    if corruption == "mapping": documents["physical_mapping"]["registry_sha256"] = "f" * 64
    if corruption == "parent":
        release = documents["release"]
        accounting = json.loads(Path(release["actual_parent_references"]["accounting"]["path"]).read_text())
        accounting["parents"][0]["state"] = "FAILED"
        release["actual_parent_references"]["accounting"] = write(tmp_path / "wrong_accounting.json", accounting)
    if corruption == "wrapper":
        release = documents["release"]
        key = "normalization_reference"
        body = json.loads(Path(release["configurations"][key]["path"]).read_text())
        body["configuration_reference"] = evidence["codebook"]
        release["configurations"][key] = write(Path(release["configurations"][key]["path"]), body)
    if corruption == "wrapper_path":
        release = documents["release"]; key = "normalization_reference"
        body = json.loads(Path(release["configurations"][key]["path"]).read_text())
        release["configurations"][key] = write(tmp_path / "wrong_wrapper_path.json", body)
    if corruption == "release_id": documents["release"]["release_id"] = "x" * 81
    if corruption == "bounded_as_full": request["mode"] = "authoritative_full_train"
    with pytest.raises(ValueError): adapter._actual_final_release(documents, evidence, request)


def test_legacy_engineering_header_cannot_supply_real_release_acceptance(tmp_path):
    evidence, request, projection, interpreter = metadata_case(tmp_path)
    release = verify_release_binding(request, evidence=evidence, verifier=interpreter(projection))
    assert release.authority_family == "model_protocol_fixture_only" and not release.is_actual_data_release
    del request["UNIT_FIXTURE_ONLY_NOT_A_REAL_REQUEST"]
    with pytest.raises(ValueError, match="engineering-only"):
        verify_release_binding(request, evidence=evidence, verifier=interpreter(projection))


@pytest.mark.parametrize("bad_scale", [False, True])
def test_published_normalizer_fields_are_consumed_without_relabeling_raw_source_schema(tmp_path, bad_scale):
    evidence, request, projection, interpreter = metadata_case(tmp_path)
    row = {"target_id": "unit_q", "source_series_key": "physical/674/xtb_singlepoint/frobenius_norm",
        "n": 2, "std_ddof0": 2., "lower": 1., "upper": 5., "centering": "FIXED_ZERO", "center_value": 0.,
        "per_head_single_scale": True, "scale_rule": "SERIES_STD_DDOF0", "scale": 99. if bad_scale else 2.,
        "winsorization_only_statistical_copies": True, "original_training_labels_modified": False}
    evidence["d4_statistics"] = write(tmp_path / "published_norm_unit.json", {
        "schema": "FINAL_TRAIN_TARGET_NORMALIZATION_CANDIDATE_V1", "status": "ACTUAL_SERIES_EXACT_JOINT_RECIPE_BOUND",
        "targets": {"unit_q": row}, "policy_reference": evidence["joint_contract"]})
    projection["D4_bindings"]["q"]["statistics_pointer"] = ["targets", "unit_q"]
    projection["evidence_sha256"] = canonical_hash(evidence)
    release = verify_release_binding(request, evidence=evidence, verifier=interpreter(projection))
    if bad_scale:
        with pytest.raises(ValueError, match="scale"): tensor6_normalization(release, "q", target_local=True)
    else:
        norm = tensor6_normalization(release, "q", target_local=True)
        assert isinstance(norm, TrainNormalization) and norm.scale == (2.,)
        assert "winsor_lower" not in row and "lower" in row

@pytest.mark.parametrize("construction", ["replace", "constructor"])
@pytest.mark.parametrize("entrypoint", ["reverify", "make_proxy_inputs"])
def test_unit_release_cannot_promote_itself_to_actual_authority(tmp_path, construction, entrypoint):
    evidence, request, projection, interpreter = metadata_case(tmp_path)
    legitimate = verify_release_binding(request, evidence=evidence, verifier=interpreter(projection))
    if construction == "replace":
        forged = replace(legitimate, authority_family="actual_final_release_v1")
    else:
        forged = VerifiedDataRelease(legitimate.request_sha256, legitimate.evidence, legitimate.verifier,
            legitimate.projection, "actual_final_release_v1", request=legitimate.request)
    # A newly computed local seal cannot replace the original authority gate.
    assert forged.sha256 == forged._seal
    with pytest.raises(ValueError, match="authority"):
        if entrypoint == "reverify":
            forged.reverify()
        else:
            make_proxy_inputs(request, forged, indexes={}, registry=None, reader_factory=None,
                structural_binding=None, normalizations={}, validation_choices={})


@pytest.mark.parametrize("change", ["normalization", "target", "role_index"])
def test_resealed_projection_must_match_the_pinned_interpreter_again(tmp_path, change):
    evidence, request, projection, interpreter = metadata_case(tmp_path)
    legitimate = verify_release_binding(request, evidence=evidence, verifier=interpreter(projection))
    altered = deepcopy(legitimate.projection)
    if change == "normalization": altered["normalization_sha256"] = "f" * 64
    if change == "target": altered["targets"]["q"]["condition"] = "caller_substituted_condition"
    if change == "role_index": altered["role_index_sha256"]["TRAIN"] = "f" * 64
    forged = replace(legitimate, projection=altered)
    assert forged.sha256 == forged._seal
    with pytest.raises(ValueError, match="projection authority"):
        forged.reverify()


def test_constructor_without_bound_request_cannot_reverify_authority(tmp_path):
    evidence, request, projection, interpreter = metadata_case(tmp_path)
    legitimate = verify_release_binding(request, evidence=evidence, verifier=interpreter(projection))
    incomplete = VerifiedDataRelease(legitimate.request_sha256, legitimate.evidence,
        legitimate.verifier, legitimate.projection, legitimate.authority_family)
    with pytest.raises(ValueError, match="Bound request"):
        incomplete.reverify()


def test_legitimate_bound_projection_reverifies_without_granting_actual_authority(tmp_path):
    evidence, request, projection, interpreter = metadata_case(tmp_path)
    legitimate = verify_release_binding(request, evidence=evidence, verifier=interpreter(projection))
    identity = legitimate.sha256
    legitimate.reverify()
    assert legitimate.sha256 == identity and legitimate.request == request
    assert legitimate.authority_family == "model_protocol_fixture_only" and not legitimate.is_actual_data_release
    # Request transport is copied, not an alias whose changes silently grant scope.
    request["mode"] = "authoritative_full_train"
    legitimate.reverify()
    assert legitimate.request["mode"] == "authoritative_proxy"
