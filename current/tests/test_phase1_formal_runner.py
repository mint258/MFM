"""Frozen execution/gate/resume tests; no scheduler or GPU calls are required."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest
import torch

from phychem_mfm.data.descriptor_schema import GRAPH_DESCRIPTOR_NAMES
from phychem_mfm.model.normalization import train_regression_normalization
from phychem_mfm.phase1.formal_gate import GateIssue, GateReport
from phychem_mfm.phase1.formal_runtime import (
    FORMAL_RUN_SCHEMA, INIT_RECIPE, ORDER, BudgetClock, backbone_state_hash,
    check_atom_caps, cyclic_batch_indices, file_sha256, finalize_endpoint, frozen_execution,
    load_fitted_controls, module_manifest, single_gpu_environment,
    validate_formal_resume, verify_architecture, verify_decontamination,
    verify_identity_ledger, verify_paired_initialization, verify_source, verify_tracker_lineage,
)
from phychem_mfm.phase1.identity import canonical_hash
from phychem_mfm.phase1.objectives import PHASE1_VARIANTS, Phase1LossPolicy
from phychem_mfm.training.checkpoint import contract_hash, semantic_config
from phychem_mfm.training.losses import LossWeights
from phychem_mfm.model.phase1_specs import PHASE1_GRAPH_DESCRIPTOR_NAMES


def protocol():
    return {"pretraining": {"variants": list(PHASE1_VARIANTS), "seeds": [3, 5],
        "budget": {"optimizer_steps_per_condition": 4, "structures_per_condition": 8, "gpu_hours_per_condition": 1.},
        "checkpoint_rule": {"selection_split": "fixed_budget", "selection_metric": "fixed_budget_endpoint", "save_every_steps": 2, "keep_checkpoints": 2}},
        "compute": {"nodes_per_job": 1, "gpus_per_job": 1, "max_walltime_hours": 2.}}


def execution():
    policy = Phase1LossPolicy()
    return {"schema_version": "phase1_execution_v1", "world_size": 1, "strategy": "direct_joint", "order": deepcopy(ORDER),
        "evaluation": {"every_updates": 2, "endpoint": "full_pretrain_validation"}, "none_policy": "zero_updates_export_paired_H0",
        "config": {"architecture": {"type": "shared_multitask", "preset": "shared_light", "task_route": "light"},
            "backbone": {"n_atom_types": 10}, "expert": {}, "head": {"profile": "phase1", "geometry_head": "legacy"},
            "supervision": {"variant": "SDP"}, "loss": {name: getattr(LossWeights(), name) for name in LossWeights.__dataclass_fields__},
            "schedule": {"strategy": "direct_joint_from_step_zero", "max_steps": 4, "warmup_steps": 1, "min_lr_ratio": .05},
            "optimizer": {"lr": 3e-5, "weight_decay": .01, "betas": [.9, .95], "grad_clip_norm": 1.},
            "training": {"seed": 3, "base_molecules_per_batch": 2, "world_size": 1, "precision": "float32"},
            "phase1": {"status": "formal", "atom_encoding": "zero_based", "views": ["clean", "geom", "topo"],
                "charge_definition": "MOPAC NET ATOMIC CHARGES", "geometry_level": .2, "topology_level": .3,
                "max_atoms_per_molecule": 64, "max_atoms_per_batch": 384,
                "group_weights": dict(policy.group_weights), "task_weights": dict(policy.task_weights),
                "group_normalization": "fixed_weighted_mean_of_enabled_groups", "regression_output_mode": "raw"}}}


def test_frozen_execution_only_selects_variant_and_seed():
    document = execution()
    original = deepcopy(document)
    for variant in PHASE1_VARIANTS:
        config, policy = frozen_execution(protocol(), document, variant=variant, seed=5)
        expected = deepcopy(original["config"])
        expected["supervision"]["variant"], expected["training"]["seed"] = variant, 5
        assert config == expected
        assert policy.to_dict() == Phase1LossPolicy().to_dict()
    assert document == original


@pytest.mark.parametrize("field,value", [
    ("strategy", "staged"), ("world_size", 2), ("none_policy", "train_then_discard"),
    ("order", {**ORDER, "views": ["clean"]}), ("evaluation", {"every_updates": 2, "endpoint": "subset"}),
])
def test_unsupported_execution_cannot_silently_fall_back(field, value):
    document = execution()
    document[field] = value
    with pytest.raises(ValueError):
        frozen_execution(protocol(), document, variant="SDP", seed=3)


@pytest.mark.parametrize("change", ["diagnostic", "subset", "accumulation", "amp", "missing_task_weight", "staged", "val_best"])
def test_rejects_scientific_and_budget_overrides(change):
    document, frozen = execution(), protocol()
    config = document["config"]
    if change == "diagnostic":
        config["phase1"]["status"] = "diagnostic_only"
    elif change == "subset":
        config["phase1"]["train_limit"] = 8
    elif change == "accumulation":
        config["training"]["gradient_accumulation_steps"] = 2
    elif change == "amp":
        config["training"]["precision"] = "bf16"
    elif change == "missing_task_weight":
        config["phase1"]["task_weights"].pop("energy")
    elif change == "staged":
        config["schedule"]["strategy"] = "staged"
    elif change == "val_best":
        frozen["pretraining"]["checkpoint_rule"]["selection_metric"] = "weighted_val_best"
    with pytest.raises(ValueError):
        frozen_execution(frozen, document, variant="SDP", seed=3)


def test_three_views_do_not_triple_base_structure_budget():
    frozen = protocol()
    frozen["pretraining"]["budget"]["structures_per_condition"] *= 3
    with pytest.raises(ValueError, match="three views are not three structures"):
        frozen_execution(frozen, execution(), variant="S", seed=3)


@pytest.mark.parametrize("change", ["group", "task"])
def test_direct_joint_rejects_positive_python_weights_that_disable_fp32_supervision(change):
    document = execution()
    policy = document["config"]["phase1"]
    if change == "group":
        policy["group_weights"]["D"] = 1e-100
    else:
        policy["task_weights"]["energy"] = 1e-100
    with pytest.raises(ValueError, match="positive in the float32 loss"):
        frozen_execution(protocol(), document, variant="SDP", seed=3)


def test_cyclic_fixed_order_is_identical_across_conditions_and_resume():
    order = np.random.default_rng(3).permutation(5)
    complete = [cyclic_batch_indices(order, step, 2) for step in range(4)]
    resumed = [cyclic_batch_indices(order, step, 2) for step in range(2, 4)]
    assert resumed == complete[2:]
    for variant in PHASE1_VARIANTS[1:]:
        assert [cyclic_batch_indices(order, step, 2) for step in range(4)] == complete
    assert sum(map(len, complete)) == 8


def test_actual_three_view_atom_caps_fail_without_trimming():
    counts = [4, 4, 4, 7, 7, 7]
    check_atom_caps(counts, per_molecule=7, per_batch=33)
    with pytest.raises(RuntimeError, match="filtering"):
        check_atom_caps(counts, per_molecule=6, per_batch=33)
    with pytest.raises(RuntimeError, match="lowering batch/views"):
        check_atom_caps(counts, per_molecule=7, per_batch=32)
    assert counts == [4, 4, 4, 7, 7, 7]


@pytest.mark.parametrize("env", [{}, {"SLURM_JOB_ID": "42", "CUDA_VISIBLE_DEVICES": "0,1"},
    {"SLURM_JOB_ID": "42", "CUDA_VISIBLE_DEVICES": "0", "WORLD_SIZE": "2"},
    {"SLURM_JOB_ID": "42", "CUDA_VISIBLE_DEVICES": "0", "SLURM_NTASKS": "2"},
    {"SLURM_JOB_ID": "42", "CUDA_VISIBLE_DEVICES": "0", "LOCAL_RANK": "1"}])
def test_single_gpu_requires_allocation_and_rejects_ddp(env):
    with pytest.raises(RuntimeError):
        single_gpu_environment(protocol(), env)


def test_single_gpu_preserves_scheduler_uuid_visibility():
    env = {"SLURM_JOB_ID": "42", "CUDA_VISIBLE_DEVICES": "GPU-123456", "WORLD_SIZE": "1", "LOCAL_RANK": "0"}
    original = dict(env)
    assert single_gpu_environment(protocol(), env) == "GPU-123456"
    assert env == original


def test_budget_clock_carries_failed_attempt_compute_and_none_validation():
    frozen = protocol()
    frozen["pretraining"]["budget"]["gpu_hours_per_condition"] = 100 / 3600
    clock = BudgetClock.from_protocol(frozen, carried_wall_seconds=80., began=10.)
    assert clock.usage(now=25.)["wall_seconds"] == 95.
    assert not clock.exhausted(now=29.)
    assert clock.exhausted(now=30.)
    # No optimizer update is required for allocation-time usage (none control).
    assert clock.usage(now=30.)["gpu_hours"] == 100 / 3600


class FullTrainingView:
    kind = "train"
    diagnostic_only = False
    pool_hash, view_hash = "a" * 64, "b" * 64
    def __len__(self):
        return 2
    def record_ref(self, index):
        return "clean.lmdb", index + 10


def controls_fixture():
    train = FullTrainingView()
    config, _ = frozen_execution(protocol(), execution(), variant="SDP", seed=3)
    size = len(GRAPH_DESCRIPTOR_NAMES)
    statistics = {"muE": 0., "stdE": 1., "muQ": 0., "stdQ": 1., "estate_index_mu": 0., "estate_index_std": 1.,
        "formal_charge_mu": 0., "formal_charge_std": 1., "graph_desc_mu": [0.] * size, "graph_desc_std": [1.] * size}
    keys = ["clean.lmdb:10", "clean.lmdb:11"]
    provenance = {"estimator_version": "phase1_masked_population_std_v1", "train_only": True, "diagnostic_only": False,
        "train_pool_hash": train.pool_hash, "train_view_hash": train.view_hash, "seed": 3, "cap": 2,
        "atom_encoding": "zero_based", "energy_unit": "kcal/mol", "charge_definition": "MOPAC NET ATOMIC CHARGES", "charge_unit": "e",
        "sampled_structure_count": 2, "sampled_logical_indices": [0, 1], "sampled_record_keys_hash": canonical_hash(keys),
        "valid_label_counts": {"energy": 2, "charge": 4, "estate_index": 4, "graph_descriptor": [2] * size},
        "statistics_hash": canonical_hash(statistics)}
    provenance["provenance_hash"] = canonical_hash(provenance)
    baseline_provenance = {"train_manifest": {"role": "train", "diagnostic_only": False, "pool_hash": train.pool_hash, "view_hash": train.view_hash},
        "fit_records": 2, "element_fit_view_records": 2, "element_majority_source": "train_topology_actual_corrupted_target_x",
        "element_fit_labels": 2, "energy_fit_labels": 2, "charge_fit_labels": 4, "element_class_counts": {"5": 2}}
    controls = {"schema_version": "phase1_fitted_controls_v1", "statistics": statistics, "statistics_provenance": provenance,
        "baselines": {"n_atom_types": 10, "provenance": baseline_provenance, "energy_coefficients": [0.] * 11,
            "charge_means": [0.] * 10, "charge_counts": [4] + [0] * 9, "element_majority": 5, "bond_majority": 1,
            "graph_means": {name: 1. for name in PHASE1_GRAPH_DESCRIPTOR_NAMES},
            "node_predictions": {"estate_index": .1, "donor": 0, "acceptor": 0, "is_aromatic": 0, "is_in_ring": 0, "min_ring_size": 0},
            "element_view": {"mode": "topo", "level": .3, "seed": 3, "seed_rule": "seed_plus_logical_index"}}}
    fit_ids = {"schema_version": "phase1_fit_ids_v1", "train_pool_hash": train.pool_hash, "train_view_hash": train.view_hash,
        "statistics": {"logical_indices": [0, 1], "record_keys": keys}, "baselines": {"logical_indices": [0, 1], "record_keys": keys}}
    return controls, fit_ids, train, config


def test_controls_consume_frozen_train_only_values_without_fitting():
    controls, ids, train, config = controls_fixture()
    stats, baseline, proof = load_fitted_controls(controls, ids, train, config)
    assert stats["stdE"] == 1.
    assert baseline.element_majority == 5
    assert baseline.charge_counts.sum() == 4
    assert proof["element_view"]["mode"] == "topo"
    config["phase1"]["regression_output_mode"] = "train_affine"
    config["head"]["regression_output_normalization"] = train_regression_normalization(controls["statistics"], controls["statistics_provenance"])
    _, _, proof = load_fitted_controls(controls, ids, train, config)
    assert proof["continuous_output_contract_sha256"] == config["head"]["regression_output_normalization"]["contract_sha256"]


@pytest.mark.parametrize("defect", ["val_fitted", "diagnostic", "wrong_pool", "wrong_fit_key", "stats_changed", "legacy_element", "bad_classes", "nonfinite",
    "missing_graph", "missing_node", "charge_count", "element_count", "element_majority"])
def test_controls_reject_unfrozen_or_wrong_split_inputs(defect):
    controls, ids, train, config = controls_fixture()
    if defect == "val_fitted":
        controls["statistics_provenance"]["train_only"] = False
    elif defect == "diagnostic":
        controls["statistics_provenance"]["diagnostic_only"] = True
    elif defect == "wrong_pool":
        ids["train_pool_hash"] = "c" * 64
    elif defect == "wrong_fit_key":
        ids["statistics"]["record_keys"][1] = "other.lmdb:11"
    elif defect == "stats_changed":
        controls["statistics"]["stdE"] = 2.
    elif defect == "legacy_element":
        controls["baselines"]["provenance"]["element_majority_source"] = "legacy_clean_all_atoms_compatibility_only"
    elif defect == "bad_classes":
        controls["baselines"]["element_majority"] = 9
    elif defect == "nonfinite":
        controls["baselines"]["energy_coefficients"][0] = float("nan")
    elif defect == "missing_graph":
        controls["baselines"]["graph_means"].pop("MolLogP")
    elif defect == "missing_node":
        controls["baselines"]["node_predictions"].pop("estate_index")
    elif defect == "charge_count":
        controls["baselines"]["provenance"]["charge_fit_labels"] = 5
    elif defect == "element_count":
        controls["baselines"]["provenance"]["element_class_counts"]["5"] = 3
    elif defect == "element_majority":
        controls["baselines"]["element_majority"] = 6
    with pytest.raises(ValueError):
        load_fitted_controls(controls, ids, train, config)


@pytest.mark.parametrize("field,value", [("energy_unit", "hartree"), ("charge_unit", "dimensionless"),
    ("charge_definition", "other population analysis"), ("estimator_version", "unmasked_std_v0"),
    ("atom_encoding", "atomic_number"), ("cap", 1), ("seed", -1)])
def test_rehashed_normalizer_cannot_change_actual_estimator_or_units(field, value):
    controls, ids, train, config = controls_fixture()
    provenance = controls["statistics_provenance"]
    provenance[field] = value
    provenance["provenance_hash"] = canonical_hash({key: item for key, item in provenance.items() if key != "provenance_hash"})
    with pytest.raises(ValueError):
        load_fitted_controls(controls, ids, train, config)


def write_ledger(tmp_path, dataset, keys):
    path = tmp_path / f"{dataset.kind}.jsonl"
    rows = []
    for index, key in enumerate(keys):
        shard, real = dataset.record_ref(index)
        rows.append({"manifest_pool_hash": dataset.pool_hash, "logical_index": index, "shard": shard, "real_index": real,
            "status": "identity_ok", "inchikey": key, "source_field": "smiles", "identity_policy": "standard_full_inchikey_v1"})
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    return {"path": str(path), "sha256": file_sha256(path), "rows": len(rows)}, rows


def test_identity_ledger_requires_every_exact_active_record(tmp_path):
    train = FullTrainingView()
    key = "AAAAAAAAAAAAAA-BBBBBBBBBB-C"
    declaration, rows = write_ledger(tmp_path, train, [key, key])
    assert verify_identity_ledger(train, declaration, artifact_directory=tmp_path) == {key}
    rows[1]["real_index"] = 999
    Path(declaration["path"]).write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    declaration["sha256"] = file_sha256(declaration["path"])
    with pytest.raises(ValueError, match="exact active"):
        verify_identity_ledger(train, declaration, artifact_directory=tmp_path)


def test_partial_and_parent_ledgers_cannot_prove_complete_decontamination(tmp_path):
    train = FullTrainingView()
    declaration, _ = write_ledger(tmp_path, train, ["AAAAAAAAAAAAAA-BBBBBBBBBB-C"])
    with pytest.raises(ValueError, match="every record"):
        verify_identity_ledger(train, declaration, artifact_directory=tmp_path)
    declaration, rows = write_ledger(tmp_path, train, ["AAAAAAAAAAAAAA-BBBBBBBBBB-C"] * 2)
    rows[0]["manifest_pool_hash"] = "d" * 64
    Path(declaration["path"]).write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    declaration["sha256"] = file_sha256(declaration["path"])
    with pytest.raises(ValueError):
        verify_identity_ledger(train, declaration, artifact_directory=tmp_path)


def test_decontamination_recomputes_train_val_and_finaltest_overlap(tmp_path, monkeypatch):
    train, val = FullTrainingView(), FullTrainingView()
    val.kind, val.pool_hash = "validation", "c" * 64
    train_key, val_key = "AAAAAAAAAAAAAA-BBBBBBBBBB-C", "DDDDDDDDDDDDDD-EEEEEEEEEE-F"
    t, _ = write_ledger(tmp_path, train, [train_key] * 2)
    v, _ = write_ledger(tmp_path, val, [val_key] * 2)
    frozen = {"data": {"source_manifest_sha256": "1" * 64, "split_manifest_sha256": "2" * 64},
              "downstream": {"split_manifest_sha256": "3" * 64}}
    evidence = {"schema_version": "phase1_decontamination_v1", "identity_policy": "standard_full_inchikey_v1",
        "source_manifest_sha256": "1" * 64, "split_manifest_sha256": "2" * 64, "downstream_split_manifest_sha256": "3" * 64,
        "ledgers": {"train": t, "validation": v}}
    monkeypatch.setattr("phychem_mfm.phase1.formal_runtime.frozen_test_identities", lambda spec: ({train_key}, {}))
    with pytest.raises(ValueError, match="train_test=1"):
        verify_decontamination(frozen, evidence, train, val, {}, artifact_directory=tmp_path, downstream_directory=tmp_path)
    monkeypatch.setattr("phychem_mfm.phase1.formal_runtime.frozen_test_identities", lambda spec: (set(), {}))
    proof = verify_decontamination(frozen, evidence, train, val, {}, artifact_directory=tmp_path, downstream_directory=tmp_path)
    assert proof["overlaps"] == {"train_validation": 0, "train_test": 0, "validation_test": 0}


def resume_fixture():
    config, _ = frozen_execution(protocol(), execution(), variant="SDP", seed=3)
    manifest = {"purpose": FORMAL_RUN_SCHEMA, "protocol_sha256": "a" * 64}
    payload = {"dataset_manifest": manifest, "semantic_config": semantic_config(config), "semantic_config_sha256": contract_hash(semantic_config(config)),
        "optimizer_update_step": 2, "global_exposure_step": 2, "checkpoint_type": "periodic", "scheduler_state": {"last_epoch": 2},
        "extra": {"formal_run_schema": FORMAL_RUN_SCHEMA, "wandb_run_id": "run12345", "paired_initial_H0_sha256": "b" * 64,
                  "base_molecule_exposure": 4, "budget_usage": {"wall_seconds": 10.},
                  "tracker_next_step": 3, "tracker_run_path": "entity/project/run12345"}}
    journal = {"schema_version": FORMAL_RUN_SCHEMA, "status": "failed", "manifest_sha256": contract_hash(manifest),
        "wandb_run_id": "run12345", "paired_initial_H0_sha256": "b" * 64, "optimizer_update_step": 2,
        "base_molecule_exposure": 4, "latest_checkpoint_sha256": "c" * 64,
        "budget_usage": {"wall_seconds": 30., "gpu_hours": 30. / 3600},
        "tracker_next_step": 4, "tracker_run_path": "entity/project/run12345"}
    return payload, config, manifest, journal


def check_resume(payload, config, manifest, journal):
    return validate_formal_resume(payload, expected_manifest=manifest, expected_config=config, expected_run_id="run12345",
        expected_init_hash="b" * 64, journal=journal, checkpoint_sha256="c" * 64)


def test_resume_carries_journal_usage_beyond_last_checkpoint():
    payload, config, manifest, journal = resume_fixture()
    assert check_resume(payload, config, manifest, journal) == 30.


@pytest.mark.parametrize("defect", ["diagnostic", "changed_config", "changed_protocol", "tracker", "init", "rewind", "extra_exposure", "wall_regressed", "gpu_regressed", "completed", "active", "scheduler", "history_rewind", "tracker_path"])
def test_resume_rejects_lineage_counter_and_budget_changes(defect):
    payload, config, manifest, journal = resume_fixture()
    if defect == "diagnostic":
        payload["extra"]["formal_run_schema"] = "bounded_diagnostic_only"
    elif defect == "changed_config":
        config["optimizer"]["lr"] *= 2
    elif defect == "changed_protocol":
        manifest["protocol_sha256"] = "d" * 64
    elif defect == "tracker":
        journal["wandb_run_id"] = "another-run"
    elif defect == "init":
        journal["paired_initial_H0_sha256"] = "d" * 64
    elif defect == "rewind":
        journal["optimizer_update_step"] = 3
    elif defect == "extra_exposure":
        payload["extra"]["base_molecule_exposure"] = 12
    elif defect == "wall_regressed":
        journal["budget_usage"] = {"wall_seconds": 5., "gpu_hours": 5. / 3600}
    elif defect == "gpu_regressed":
        journal["budget_usage"]["gpu_hours"] = 0.
    elif defect == "completed":
        journal["status"] = "complete"
    elif defect == "active":
        journal["status"] = "running"
    elif defect == "scheduler":
        payload["scheduler_state"]["last_epoch"] = 1
    elif defect == "history_rewind":
        journal["tracker_next_step"] = 2
    elif defect == "tracker_path":
        journal["tracker_run_path"] = "another/entity/run12345"
    with pytest.raises(RuntimeError):
        check_resume(payload, config, manifest, journal)


def test_none_resume_refuses_any_optimizer_update_or_exposure():
    payload, config, manifest, journal = resume_fixture()
    config["supervision"]["variant"] = "none"
    payload["semantic_config"], payload["semantic_config_sha256"] = semantic_config(config), contract_hash(semantic_config(config))
    with pytest.raises(RuntimeError, match="None control"):
        check_resume(payload, config, manifest, journal)
    payload["optimizer_update_step"] = payload["global_exposure_step"] = payload["extra"]["base_molecule_exposure"] = 0
    payload["scheduler_state"]["last_epoch"] = 0
    journal["optimizer_update_step"] = journal["base_molecule_exposure"] = 0
    assert check_resume(payload, config, manifest, journal) == 30.


def test_architecture_and_paired_random_state_hash_are_checked_exactly():
    model = SimpleNamespace(backbone=torch.nn.Linear(2, 3))
    artifact = {"schema_version": "phase1_paired_init_v1", "seed": 3,
                "backbone_state_sha256": backbone_state_hash(model), "hash_recipe": INIT_RECIPE}
    assert verify_paired_initialization(model, artifact, 3) == artifact["backbone_state_sha256"]
    with torch.no_grad():
        model.backbone.weight.add_(1.)
    with pytest.raises(ValueError, match="Fresh random H0"):
        verify_paired_initialization(model, artifact, 3)
    config = execution()["config"]
    whole = torch.nn.Linear(2, 3)
    architecture = {"schema_version": "phase1_architecture_v1", "config": {key: config[key] for key in ("architecture", "backbone", "expert", "head")},
                    "module_manifest": module_manifest(whole)}
    verify_architecture(whole, config, architecture)
    architecture["module_manifest"]["parameters"]["weight"]["shape"] = [9, 9]
    with pytest.raises(ValueError, match="module manifest"):
        verify_architecture(whole, config, architecture)


def test_source_snapshot_is_exact_bytes_not_a_json_digest_assertion(tmp_path):
    path = tmp_path / "source.bin"
    path.write_bytes(b"source-file.py\0print('frozen')\n\0")
    digest = file_sha256(path)
    frozen = {"source": {"source_sha256": digest, "commit": "abc123"}}
    verify_source(frozen, {"source.source_sha256": path}, {"source_sha256": digest, "git_commit": "abc123"})
    path.write_text(json.dumps({"source_sha256": digest}), encoding="utf-8")
    with pytest.raises(ValueError, match="byte snapshot"):
        verify_source(frozen, {"source.source_sha256": path}, {"source_sha256": digest, "git_commit": "abc123"})


def tracker_fixture(*, mode="online", resumed=False, step=0):
    return SimpleNamespace(id="run12345", disabled=False, settings=SimpleNamespace(mode=mode),
                           resumed=resumed, step=step, path="entity/project/run12345")


def test_tracker_fresh_offline_and_strict_online_resume_have_explicit_boundaries():
    run = tracker_fixture(mode="offline")
    assert verify_tracker_lineage(run, run_id="run12345", mode="offline") == (0, run.path)
    with pytest.raises(RuntimeError, match="Offline W&B resume is unsupported"):
        verify_tracker_lineage(run, run_id="run12345", mode="offline", resume=True)
    resumed = tracker_fixture(resumed=True, step=4)
    assert verify_tracker_lineage(resumed, run_id="run12345", mode="online", resume=True,
        expected_next_step=4, expected_run_path=resumed.path) == (4, resumed.path)


@pytest.mark.parametrize("defect", ["not_resumed", "old_cursor", "wrong_path", "disabled"])
def test_same_tracker_id_does_not_establish_real_resume(defect):
    run = tracker_fixture(resumed=True, step=4)
    if defect == "not_resumed":
        run.resumed = False
    elif defect == "old_cursor":
        run.step = 3
    elif defect == "wrong_path":
        run.path = "different/project/run12345"
    else:
        run.disabled = True
    with pytest.raises(RuntimeError):
        verify_tracker_lineage(run, run_id="run12345", mode="online", resume=True,
            expected_next_step=4, expected_run_path="entity/project/run12345")


@pytest.mark.parametrize("failure", ["tracker", "save", "publish"])
def test_endpoint_is_revoked_for_every_finalization_error(tmp_path, failure):
    endpoint = tmp_path / "fixed_endpoint.pt"
    endpoint.write_text("candidate", encoding="utf-8")
    calls = []
    def operation(name):
        def callback():
            calls.append(name)
            if failure == name:
                raise RuntimeError(name)
        return callback
    clock = SimpleNamespace(exhausted=lambda: False)
    with pytest.raises(RuntimeError, match=failure):
        finalize_endpoint(candidate_complete=True, finish_tracker=operation("tracker"), save_endpoint=operation("save"),
            publish_endpoint=operation("publish"), revoke_endpoint=lambda: endpoint.unlink(missing_ok=True), clock=clock)
    assert not endpoint.exists()
    if failure == "tracker":
        assert calls == ["save", "tracker"]
    elif failure == "save":
        assert calls == ["save"]


def test_endpoint_publication_waits_for_tracker_and_final_checkpoint(tmp_path):
    endpoint = tmp_path / "fixed_endpoint.pt"
    calls = []
    def record(name):
        assert not endpoint.exists()
        calls.append(name)
    def publish():
        calls.append("publish")
        endpoint.write_text("committed", encoding="utf-8")
    result = finalize_endpoint(candidate_complete=True, finish_tracker=lambda: record("finish"), save_endpoint=lambda: record("save"),
        publish_endpoint=publish, revoke_endpoint=lambda: endpoint.unlink(missing_ok=True), clock=SimpleNamespace(exhausted=lambda: False))
    assert result == "complete" and endpoint.exists()
    assert calls == ["save", "finish", "publish"]


def test_finalization_budget_includes_tracker_and_checkpoint_time(tmp_path):
    endpoint = tmp_path / "fixed_endpoint.pt"
    elapsed = [0.]
    clock = SimpleNamespace(exhausted=lambda: elapsed[0] >= 10.)
    def finish():
        elapsed[0] += 5.
    def save():
        elapsed[0] += 5.
    publisher = Mock()
    result = finalize_endpoint(candidate_complete=True, finish_tracker=finish, save_endpoint=save, publish_endpoint=publisher,
        revoke_endpoint=lambda: endpoint.unlink(missing_ok=True), clock=clock)
    assert result == "budget_stop"
    publisher.assert_not_called()


def load_runner():
    path = Path(__file__).resolve().parents[1] / "scripts" / "train_phase1_formal.py"
    specification = importlib.util.spec_from_file_location("phase1_formal_runner_test", path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def test_storage_handles_actual_wandb_internal_symlink_topology(tmp_path):
    runner = load_runner()
    run_dir = tmp_path / "wandb" / "offline-run-one"
    (run_dir / "logs").mkdir(parents=True)
    log_file = run_dir / "logs" / "debug.log"
    log_file.write_bytes(b"diagnostic")
    try:
        (tmp_path / "wandb" / "latest-run").symlink_to(run_dir, target_is_directory=True)
        (tmp_path / "wandb" / "debug.log").symlink_to(log_file)
    except OSError as error:
        pytest.skip(f"Filesystem cannot create symlinks: {error}")
    assert runner._run_bytes(tmp_path) == len(b"diagnostic")
    outside = tmp_path.parent / "outside-formal-storage-test.txt"
    outside.write_bytes(b"outside")
    (tmp_path / "escape").symlink_to(outside)
    with pytest.raises(RuntimeError, match="escapes"):
        runner._run_bytes(tmp_path)


def test_live_gate_failure_stops_before_tracker_model_or_data(tmp_path, monkeypatch):
    runner = load_runner()
    frozen_path, artifact_map = tmp_path / "protocol.json", tmp_path / "artifacts.json"
    frozen_path.write_text(json.dumps(protocol()), encoding="utf-8")
    artifact_map.write_text("{}", encoding="utf-8")
    output = tmp_path / "blocked-run"
    monkeypatch.setenv("SLURM_JOB_ID", "42")
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "GPU-frozen")
    for name in ("WORLD_SIZE", "LOCAL_WORLD_SIZE", "SLURM_NTASKS", "SLURM_NPROCS", "SLURM_JOB_NUM_NODES", "RANK", "LOCAL_RANK", "SLURM_PROCID"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(runner, "live_gate", lambda *args: GateReport("BLOCKED", [GateIssue("test.blocked", "no device isolation")]))
    tracker, model, data = Mock(), Mock(), Mock()
    monkeypatch.setattr(runner.wandb, "init", tracker)
    monkeypatch.setattr(runner, "build_model", model)
    monkeypatch.setattr(runner, "StrictManifestDataset", data)
    with pytest.raises(RuntimeError, match="Formal live allocation gate blocked"):
        runner.main(["--protocol", str(frozen_path), "--artifacts", str(artifact_map), "--variant", "none", "--seed", "3", "--output-dir", str(output)])
    tracker.assert_not_called()
    model.assert_not_called()
    data.assert_not_called()
    assert not (output / ".formal_active").exists()
    failure = list((output / "attempts").glob("*/failure.json"))
    assert len(failure) == 1
    assert json.loads(failure[0].read_text())["optimizer_update_step"] == 0


def test_rejected_resume_never_deletes_a_unique_completed_endpoint(tmp_path):
    runner = load_runner()
    output = tmp_path / "completed-run"
    output.mkdir()
    (output / "latest.pt").write_bytes(b"latest")
    endpoint = output / "fixed_endpoint.pt"
    endpoint.write_bytes(b"unique-frozen-formal-result")
    with pytest.raises(RuntimeError, match="preserve the existing formal result"):
        runner.main(["--protocol", "unused.json", "--artifacts", "unused-map.json", "--variant", "none", "--seed", "3",
                     "--output-dir", str(output), "--resume", str(output / "latest.pt")])
    assert endpoint.read_bytes() == b"unique-frozen-formal-result"


def test_validated_resume_charges_tracker_init_failure_before_cuda_transfer(tmp_path, monkeypatch):
    runner = load_runner()
    frozen = protocol()
    frozen["compute"]["cpus_per_task"] = 2
    frozen.update(content_sha256="a" * 64, tracking={"provider": "wandb", "mode": "online"},
                  data={"decontamination_sha256": "1" * 64}, downstream={"split_manifest_sha256": "2" * 64})
    output = tmp_path / "existing-run"
    output.mkdir()
    (output / "latest.pt").write_bytes(b"frozen-checkpoint")
    (output / "wandb_run_id.txt").write_text("run12345", encoding="utf-8")
    payload, config, _, journal = resume_fixture()
    (output / "budget_journal.json").write_text(json.dumps(journal), encoding="utf-8")
    frozen_path, artifact_map = tmp_path / "protocol.json", tmp_path / "artifacts.json"
    frozen_path.write_text(json.dumps(frozen), encoding="utf-8")
    artifact_map.write_text("{}", encoding="utf-8")
    artifact_paths = {"data.decontamination_sha256": tmp_path / "decontam.json", "downstream.split_manifest_sha256": tmp_path / "downstream.json"}
    train = FullTrainingView()
    val = FullTrainingView()
    val.kind = "validation"
    train.summary = val.summary = lambda: {"diagnostic_only": False}
    fake_model = SimpleNamespace(to=Mock())
    docs = {"strategy.schedule_sha256": execution(), "strategy.loss_policy_sha256": Phase1LossPolicy().to_dict(),
            "tasks.target_manifest_sha256": runner.target_contract(), "tasks.label_contract_sha256": runner.label_contract(),
            "data.split_manifest_sha256": {"schema_version": "phase1_split_v1", "train": {"kind": "train"}, "validation": {"kind": "validation"}}}
    monkeypatch.setenv("SLURM_JOB_ID", "42")
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "GPU-frozen")
    monkeypatch.setattr(runner, "single_gpu_environment", lambda *args: "GPU-frozen")
    monkeypatch.setattr(runner, "live_gate", lambda *args: GateReport("PASS_LIVE_ALLOCATION"))
    monkeypatch.setattr(runner, "artifact_paths", lambda *args: artifact_paths)
    monkeypatch.setattr(runner, "read_artifact", lambda protocol, artifacts, field: docs.get(field, {}))
    monkeypatch.setattr(runner, "source_provenance", lambda *args: {})
    monkeypatch.setattr(runner, "verify_source", lambda *args: None)
    monkeypatch.setattr(runner, "StrictManifestDataset", lambda document, **kwargs: train if document["kind"] == "train" else val)
    monkeypatch.setattr(runner, "verify_decontamination", lambda *args, **kwargs: {})
    monkeypatch.setattr(runner, "load_fitted_controls", lambda *args: ({}, None, {}))
    monkeypatch.setattr(runner, "build_model", lambda *args: fake_model)
    monkeypatch.setattr(runner, "verify_architecture", lambda *args: None)
    monkeypatch.setattr(runner, "verify_paired_initialization", lambda *args: "b" * 64)
    monkeypatch.setattr(runner, "validate_formal_resume", lambda *args, **kwargs: 30.)
    monkeypatch.setattr(runner.torch, "load", lambda *args, **kwargs: payload)
    monkeypatch.setattr(runner.torch, "set_num_threads", lambda *args: None)
    monkeypatch.setattr(runner.torch.cuda, "device_count", lambda: 1)
    monkeypatch.setattr(runner.torch.cuda, "is_available", lambda: True)
    ticks = iter(range(100, 1000))
    monkeypatch.setattr(runner.time, "perf_counter", lambda: float(next(ticks)))
    monkeypatch.setattr(runner.wandb, "init", Mock(side_effect=RuntimeError("tracker initialization failed")))
    with pytest.raises(RuntimeError, match="tracker initialization failed"):
        runner.main(["--protocol", str(frozen_path), "--artifacts", str(artifact_map), "--variant", "SDP", "--seed", "3",
                     "--output-dir", str(output), "--resume", str(output / "latest.pt")])
    saved = json.loads((output / "budget_journal.json").read_text())
    assert saved["status"] == "failed"
    assert saved["budget_usage"]["wall_seconds"] > 30.
    assert saved["budget_usage"]["gpu_hours"] == saved["budget_usage"]["wall_seconds"] / 3600
    assert saved["optimizer_update_step"] == 2 and saved["base_molecule_exposure"] == 4
    fake_model.to.assert_not_called()
