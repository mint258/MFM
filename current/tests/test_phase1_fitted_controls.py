"""Synthetic full-view preparation tests; no production dataset or GPU access."""
from __future__ import annotations

from argparse import Namespace
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import pickle
import socket
from types import SimpleNamespace

import lmdb
import pytest
from rdkit import Chem
import torch
from torch_geometric.data import Data

from phychem_mfm.data.descriptor_schema import GRAPH_DESCRIPTOR_NAMES
from phychem_mfm.model.normalization import train_regression_normalization
from phychem_mfm.model.phase1_specs import PHASE1_GRAPH_DESCRIPTOR_NAMES
from phychem_mfm.phase1.data import StrictManifestDataset
from phychem_mfm.phase1 import fitted_controls as preparation
from phychem_mfm.phase1.formal_runtime import load_fitted_controls
from phychem_mfm.phase1.identity import canonical_hash


def config(mode="train_affine"):
    return {"backbone": {"n_atom_types": 95}, "head": {"profile": "phase1"},
            "phase1": {"status": "controls_preparation", "atom_encoding": "zero_based",
                       "charge_definition": "MOPAC NET ATOMIC CHARGES", "topology_level": 1.,
                       "regression_output_mode": mode}}


def molecule(smiles, energy):
    mol = Chem.AddHs(Chem.MolFromSmiles(smiles))
    count = mol.GetNumAtoms()
    mask = torch.ones(count, 1, dtype=torch.bool)
    mask[0] = False
    charges = torch.linspace(-.2, .2, count).view(-1, 1)
    charges[0] = 99999.  # Real mask must exclude this value, not coerce it.
    graph_mask = torch.ones(len(GRAPH_DESCRIPTOR_NAMES), dtype=torch.bool)
    if energy == 2.:
        graph_mask[0] = False
    row = Data(x=torch.tensor([atom.GetAtomicNum() - 1 for atom in mol.GetAtoms()]).view(-1, 1),
        pos=torch.arange(count * 3).view(count, 3).float(), smiles=smiles,
        energy=float(energy), energy_unit="kcal/mol", energy_mask=torch.ones(1, dtype=torch.bool),
        y=charges, charge_mask=mask.clone(), rdkit_node_mask=mask.clone(),
        rdkit_graph_desc=torch.arange(len(GRAPH_DESCRIPTOR_NAMES)).float() + energy,
        rdkit_graph_desc_mask=graph_mask,
        rdkit_bond_index=torch.tensor([[0], [1]]), rdkit_bond_order=torch.tensor([1]),
        rdkit_node_formal_charge=torch.zeros(count, 1),
        rdkit_node_estate_index=torch.full((count, 1), energy),
        rdkit_node_donor=torch.zeros(count, 1), rdkit_node_acceptor=torch.ones(count, 1),
        rdkit_node_is_aromatic=torch.zeros(count, 1), rdkit_node_is_in_ring=torch.zeros(count, 1),
        rdkit_node_min_ring_size=torch.zeros(count, 1))
    return row


def tiny_train(tmp_path, mutate=None):
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    path = inputs / "synthetic.lmdb"
    rows = {0: molecule("CCO", 2.), 2: molecule("CCN", 4.)}
    if mutate:
        for row in rows.values():
            mutate(row)
    # Explicitly excluded upstream by this synthetic manifest. The producer
    # must never choose it as a replacement or silently broaden retained scope.
    excluded = Data(smiles="invalid structure", energy=999999., energy_unit="hartree")
    env = lmdb.open(str(path), subdir=False, map_size=8 * 1024 * 1024)
    with env.begin(write=True) as txn:
        txn.put(b"__len__", pickle.dumps(3))
        for index, row in {**rows, 1: excluded}.items():
            txn.put(f"{index:09d}".encode(), pickle.dumps(row))
    env.close()
    manifest = {"data_root": str(inputs), "kind": "train", "pool_id": "synthetic_retained_only",
                "segments": [{"shard": path.name, "start": i, "end": i, "count": 1} for i in (0, 2)],
                "unique_structure_count": 2}
    manifest["pool_hash"] = canonical_hash(manifest)
    manifest_path = inputs / "retained_train.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return StrictManifestDataset(manifest_path, atom_encoding="zero_based"), path, manifest_path


def fit(train, cfg=None):
    return preparation.fit_full_train_controls(train, config() if cfg is None else cfg, fit_seed=17, topology_seed=23)


def validation_config(prepared, original):
    result = deepcopy(original)
    if result["phase1"]["regression_output_mode"] == "train_affine":
        result["head"]["regression_output_normalization"] = train_regression_normalization(
            prepared["controls"]["statistics"], prepared["controls"]["statistics_provenance"])
    return result


@pytest.mark.parametrize("mode", ["raw", "train_affine"])
def test_full_retained_roundtrip_preserves_source_masks_ids_and_rng(tmp_path, mode):
    train, path, _ = tiny_train(tmp_path)
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    before_row = train.raw_record(0)
    cfg, rng = config(mode), torch.random.get_rng_state().clone()
    original = deepcopy(cfg)
    prepared = fit(train, cfg)
    assert cfg == original
    assert torch.equal(torch.random.get_rng_state(), rng)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before
    after_row = train.raw_record(0)
    for name in ("y", "charge_mask", "rdkit_graph_desc", "rdkit_graph_desc_mask", "rdkit_node_mask", "rdkit_node_estate_index"):
        assert torch.equal(getattr(before_row, name), getattr(after_row, name))
    controls, ids = prepared["controls"], prepared["fit_ids"]
    assert set(controls) == {"schema_version", "statistics", "statistics_provenance", "baselines"}
    assert controls["statistics"]["muE"] == 3. and controls["statistics"]["stdE"] == 1.
    assert controls["statistics"]["graph_desc_mu"][0] == 4.
    assert controls["statistics"]["graph_desc_std"][0] == pytest.approx(.001)
    provenance = controls["statistics_provenance"]
    assert provenance["cap"] == provenance["sampled_structure_count"] == len(train)
    assert provenance["diagnostic_only"] is False
    assert provenance["valid_label_counts"]["graph_descriptor"][0] == 1
    expected_charge_labels = sum(len(train.raw_record(i).x) - 1 for i in range(len(train)))
    assert provenance["valid_label_counts"]["charge"] == expected_charge_labels
    assert controls["baselines"]["provenance"]["charge_fit_labels"] == expected_charge_labels
    assert controls["baselines"]["provenance"]["element_majority_source"] == "train_topology_actual_corrupted_target_x"
    assert controls["baselines"]["element_view"] == {"mode": "topo", "level": 1., "seed": 23, "seed_rule": "seed_plus_logical_index"}
    assert set(PHASE1_GRAPH_DESCRIPTOR_NAMES).issubset(controls["baselines"]["graph_means"])
    assert set(controls["baselines"]["node_predictions"]) == {"donor", "acceptor", "estate_index", "is_aromatic", "is_in_ring", "min_ring_size"}
    for entry in (ids["statistics"], ids["baselines"]):
        assert entry == {"logical_indices": [0, 1], "record_keys": [f"{path.name}:0", f"{path.name}:2"]}
    loaded, baseline, proof = load_fitted_controls(controls, ids, train, validation_config(prepared, cfg))
    assert loaded["muE"] == 3. and baseline.charge_counts.sum() == expected_charge_labels
    assert prepared["proof"]["formal_eligible"] is False and prepared["proof"]["state"] == "NOT_FROZEN"
    assert prepared["proof"]["all_retained_train_ids_fitted"]
    assert (proof["continuous_output_contract_sha256"] is not None) == (mode == "train_affine")


def test_repeated_fixed_seeds_produce_identical_json_artifacts(tmp_path):
    train, _, _ = tiny_train(tmp_path)
    first, second = fit(train), fit(train)
    assert first["controls"] == second["controls"]
    assert first["fit_ids"] == second["fit_ids"]


def test_diagnostic_view_and_incomplete_manifest_are_rejected(tmp_path):
    train, _, manifest = tiny_train(tmp_path)
    with pytest.raises(ValueError, match="complete retained"):
        fit(StrictManifestDataset(manifest, diagnostic_limit=1))
    train.manifest["unique_structure_count"] = 3
    with pytest.raises(ValueError, match="complete retained"):
        fit(train)


@pytest.mark.parametrize("field", ["train_limit", "diagnostic_limit", "validation_manifest"])
def test_preparation_cannot_ignore_diagnostic_or_other_dataset_configuration(tmp_path, field):
    train, _, _ = tiny_train(tmp_path)
    cfg = config()
    cfg["phase1"][field] = 1
    with pytest.raises(ValueError, match="Diagnostic configuration"):
        fit(train, cfg)


def test_wrong_energy_units_are_rejected_without_mask_repair(tmp_path):
    train, path, _ = tiny_train(tmp_path, lambda row: setattr(row, "energy_unit", "hartree"))
    before = path.read_bytes()
    with pytest.raises(ValueError, match="unit must be kcal/mol"):
        fit(train)
    assert path.read_bytes() == before


@pytest.mark.parametrize("target", ["MolLogP", "estate_index", "donor"])
def test_missing_retained_baseline_targets_cannot_be_filled_with_zero(tmp_path, target):
    def missing(row):
        if target == "MolLogP":
            row.rdkit_graph_desc_mask[0] = False
        else:
            del row[f"rdkit_node_{target}"]
    train, _, _ = tiny_train(tmp_path, missing)
    with pytest.raises(ValueError, match="all 23 graph and 6 node"):
        fit(train)


@pytest.mark.parametrize("kind", ["ids", "energy_unit", "estimator_version", "baseline_vocabulary"])
def test_existing_strict_consumer_rejects_tampered_prepared_controls(tmp_path, kind):
    train, _, _ = tiny_train(tmp_path)
    prepared = fit(train)
    cfg = validation_config(prepared, config())
    controls, ids = deepcopy(prepared["controls"]), deepcopy(prepared["fit_ids"])
    if kind == "ids":
        ids["baselines"]["record_keys"][1] = "synthetic.lmdb:1"
    elif kind == "baseline_vocabulary":
        controls["baselines"]["n_atom_types"] = 94
    else:
        provenance = controls["statistics_provenance"]
        provenance[kind] = "hartree" if kind == "energy_unit" else "different_estimator"
        provenance["provenance_hash"] = canonical_hash({key: value for key, value in provenance.items() if key != "provenance_hash"})
    with pytest.raises(ValueError):
        load_fitted_controls(controls, ids, train, cfg)


def test_output_paths_refuse_source_input_and_existing_directories(tmp_path):
    repo, inputs = tmp_path / "repo", tmp_path / "inputs"
    repo.mkdir()
    inputs.mkdir()
    manifest = inputs / "manifest.json"
    manifest.write_text("{}")
    for path in (repo / "output", inputs / "output"):
        with pytest.raises(ValueError, match="outside source"):
            preparation.validate_output_directory(path, project_root=repo, input_paths=[manifest])
    with pytest.raises(FileExistsError):
        preparation.validate_output_directory(inputs, project_root=repo, input_paths=[manifest])
    assert preparation.validate_output_directory(tmp_path / "new", project_root=repo, input_paths=[manifest]) == tmp_path / "new"


def cpu_env():
    return {"SLURM_JOB_ID": "123", "SLURM_JOB_NODELIST": "compute-0-20", "SLURMD_NODENAME": "compute-0-20",
            "SLURM_CPUS_PER_TASK": "2", "SLURM_MEM_PER_NODE": "8192", "CUDA_VISIBLE_DEVICES": ""}


@pytest.mark.parametrize("change", [{"SLURM_JOB_ID": ""}, {"SLURMD_NODENAME": "login"},
                                   {"SLURM_JOB_GPUS": "0,1"}, {"CUDA_VISIBLE_DEVICES": "0"},
                                   {"SLURM_NTASKS": "2"}, {"SLURM_CPUS_PER_TASK": ""}])
def test_real_entry_requires_cpu_slurm_without_broadening_visibility(change):
    env = {**cpu_env(), **change}
    before = env.copy()
    with pytest.raises(RuntimeError):
        preparation.cpu_slurm_environment(env, platform="linux", hostname="compute-0-20")
    assert env == before


def test_cpu_slurm_boundary_refuses_windows_and_returns_actual_limits():
    env = cpu_env()
    with pytest.raises(RuntimeError, match="Linux CPU Slurm"):
        preparation.cpu_slurm_environment(env, platform="win32", hostname="compute-0-20")
    assert preparation.cpu_slurm_environment(env, platform="linux", hostname="compute-0-20")["cpus_per_task"] == 2


@pytest.mark.parametrize("change", ["", "JobState=PENDING", "UserId=another(43)", "NodeList=login", "AllocTRES=cpu=2,mem=8G,node=1,gres/gpu=1"])
def test_live_cpu_allocation_observation_rejects_wrong_owner_state_node_and_gpu(change):
    fields = {"JobId": "123", "JobState": "RUNNING", "UserId": "fixture(42)", "NodeList": "compute-0-20",
              "NumNodes": "1", "NumCPUs": "2", "NumTasks": "1", "AllocTRES": "cpu=2,mem=8G,node=1"}
    if change:
        name, value = change.split("=", 1)
        fields[name] = value
    def observed(command, **kwargs):
        assert command == ["scontrol", "show", "job", "123"] and kwargs["timeout"] == 10
        return SimpleNamespace(stdout=" ".join(f"{name}={value}" for name, value in fields.items()))
    allocation = {"job_id": "123", "node": "compute-0-20", "cpus_per_task": 2}
    if change:
        with pytest.raises(RuntimeError):
            preparation.verify_cpu_slurm_job(allocation, execute=observed, uid=42)
    else:
        assert preparation.verify_cpu_slurm_job(allocation, execute=observed, uid=42)["memory_mib"] == 8192


def observe_cpu_fields(fields, *, task_cpus=2, uid=42):
    def observed(command, **kwargs):
        assert command == ["scontrol", "show", "job", fields["JobId"]] and kwargs["timeout"] == 10
        return SimpleNamespace(stdout=" ".join(f"{name}={value}" for name, value in fields.items()))
    allocation = {"job_id": fields["JobId"], "node": fields["NodeList"], "cpus_per_task": task_cpus}
    return preparation.verify_cpu_slurm_job(allocation, execute=observed, uid=uid)


def cpu_fields(**change):
    # The Slurm 22.05 CPU-only shape: TRES omits mem while the live job records
    # a per-node minimum request. This synthetic RUNNING observation is not a
    # replay of the archived FAILED production probe.
    return {"JobId": "123", "JobState": "RUNNING", "UserId": "fixture(42)", "NodeList": "compute-0-20",
            "NumNodes": "1", "NumCPUs": "2", "NumTasks": "1", "TRES": "cpu=2,node=1,billing=2",
            **change}


def test_live_slurm_2205_node_request_is_budget_evidence_without_enforcement_claim():
    observed = observe_cpu_fields(cpu_fields(MinMemoryNode="4G"))
    assert observed["memory_mib"] == 4096
    assert observed["memory_evidence_kind"] == "live_scheduler_job_request"
    assert observed["source_field"] == "MinMemoryNode"
    assert observed["memory_enforcement_verified"] is False
    with pytest.raises(RuntimeError, match="running allocation"):
        observe_cpu_fields(cpu_fields(MinMemoryNode="4G", JobState="FAILED"))


@pytest.mark.parametrize("fields, expected, source", [
    ({"AllocTRES": "cpu=2,mem=8G,node=1", "MinMemoryNode": "4G"}, 8192, "AllocTRES.mem"),
    ({"TRES": "cpu=2,mem=8192M,node=1", "MinMemoryNode": "4G"}, 8192, "TRES.mem"),
    ({"AllocTRES": "cpu=2,node=1", "TRES": "cpu=2,mem=8G,node=1"}, 8192, "TRES.mem"),
    ({"AllocTRES": "cpu=2,mem=8G,node=1", "TRES": "cpu=2,mem=8192M,node=1"}, 8192, "AllocTRES.mem"),
])
def test_valid_allocated_memory_accounting_is_preferred_and_may_exceed_minimum_request(fields, expected, source):
    observed = observe_cpu_fields(cpu_fields(**fields))
    assert observed["memory_mib"] == expected
    assert observed["memory_evidence_kind"] == "allocated_tres_accounting"
    assert observed["source_field"] == source
    assert observed["memory_enforcement_verified"] is False


def test_cpu_request_multiplier_uses_both_live_and_declared_cpu_counts_conservatively():
    observed = observe_cpu_fields(cpu_fields(NumCPUs="4", MinMemoryCPU="2G"), task_cpus=2)
    assert observed["num_cpus"] == 4 and observed["memory_budget_cpus"] == 2
    assert observed["memory_mib"] == 4096  # Not the 8192 MiB of all job CPUs.
    assert observed["source_field"] == "MinMemoryCPU"
    assert observed["memory_evidence_kind"] == "live_scheduler_job_request"
    assert observed["memory_enforcement_verified"] is False
    with pytest.raises(RuntimeError, match="smaller than its environment"):
        observe_cpu_fields(cpu_fields(NumCPUs="1", MinMemoryCPU="2G"), task_cpus=2)


@pytest.mark.parametrize("value", ["", "0", "None", "UNLIMITED", "-1", "4GB", "1.5G", str(2 ** 63)])
def test_invalid_explicit_accounting_never_falls_back_to_valid_minimum_request(value):
    with pytest.raises(RuntimeError, match="invalid memory evidence"):
        observe_cpu_fields(cpu_fields(AllocTRES=f"cpu=2,mem={value},node=1", MinMemoryNode="4G"))


@pytest.mark.parametrize("fields", [
    {},
    {"MinMemoryNode": "0"},
    {"MinMemoryCPU": "None"},
    {"MinMemoryNode": "4G", "MinMemoryCPU": "2G"},
    {"AllocTRES": "cpu=2,mem=8G,node=1", "TRES": "cpu=2,mem=4G,node=1"},
    {"AllocTRES": "cpu=2,mem=2G,node=1", "MinMemoryNode": "4G"},
    {"AllocTRES": "cpu=2,mem=8G,node=1", "MinMemoryNode": "UNLIMITED"},
    {"AllocTRES": "cpu=2,mem=8G,mem=8G,node=1"},
])
def test_missing_invalid_or_contradictory_job_memory_evidence_is_rejected(fields):
    with pytest.raises(RuntimeError):
        observe_cpu_fields(cpu_fields(**fields))


def runner():
    path = Path(__file__).resolve().parents[1] / "scripts" / "prepare_phase1_controls.py"
    spec = importlib.util.spec_from_file_location("phase1_controls_preparation_test_cli", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def cli_inputs(tmp_path, monkeypatch):
    train, path, manifest = tiny_train(tmp_path)
    config_path = manifest.parent / "config.json"
    config_path.write_text(json.dumps(config()), encoding="utf-8")
    module = runner()
    monkeypatch.setattr(module, "cpu_slurm_environment", lambda: {"job_id": "123", "node": socket.gethostname(), "cpus_per_task": 2, "cuda_visible_devices": ""})
    monkeypatch.setattr(module, "verify_cpu_slurm_job", lambda allocation: {"job_id": "123", "owner_uid": 42,
                        "node": socket.gethostname(), "num_cpus": 2, "memory_mib": 8192, "job_state": "RUNNING", "gpu_resources": 0})
    monkeypatch.setenv("SLURM_MEM_PER_NODE", "8192")
    monkeypatch.setattr(module, "source_provenance", lambda root: {"git_commit": "c" * 40, "git_dirty": False, "source_sha256": "a" * 64})
    args = Namespace(train_manifest=str(manifest), config=str(config_path), output_dir=str(tmp_path / "prepared"),
                     fit_seed=17, topology_seed=23, max_wall_seconds=60., max_memory_mib=8192, max_output_bytes=4 * 1024 * 1024)
    return module, args, train, path


def test_cli_preparation_writes_consumer_ready_artifacts_with_byte_bindings(tmp_path, monkeypatch):
    module, args, train, path = cli_inputs(tmp_path, monkeypatch)
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    summary, code = module.run_preparation(args)
    assert code == 0 and summary["complete"] and not summary["formal_eligible"]
    output = Path(args.output_dir)
    controls = json.loads((output / "controls.json").read_text())
    ids = json.loads((output / "fit_ids.json").read_text())
    prepared = {"controls": controls}
    load_fitted_controls(controls, ids, train, validation_config(prepared, config()))
    for name, binding in summary["artifacts"].items():
        assert hashlib.sha256((output / name).read_bytes()).hexdigest() == binding["sha256"]
    assert summary["inputs"]["train_manifest"]["pool_hash"] == train.pool_hash
    assert summary["statistics_fit_records"] == summary["baseline_fit_records"] == 2
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before


@pytest.mark.parametrize("environment_mib, max_memory_mib, succeeds", [(8192, 4096, True), (8192, 8192, False), (2048, 4096, False)])
def test_cli_caps_rss_by_both_environment_and_live_scheduler_request(tmp_path, monkeypatch, environment_mib, max_memory_mib, succeeds):
    module, args, _, _ = cli_inputs(tmp_path, monkeypatch)
    args.max_memory_mib = max_memory_mib
    monkeypatch.setenv("SLURM_MEM_PER_NODE", str(environment_mib))
    live = observe_cpu_fields(cpu_fields(MinMemoryNode="4G"))
    monkeypatch.setattr(module, "verify_cpu_slurm_job", lambda allocation: live)
    if not succeeds:
        monkeypatch.setattr(module, "StrictManifestDataset", lambda *args, **kwargs: pytest.fail("RSS request mismatch must fail before reading data"))
    summary, code = module.run_preparation(args)
    if not succeeds:
        assert code == 2 and not summary["complete"]
        assert "RSS bound cannot exceed" in summary["error"]
        assert not Path(args.output_dir).exists()
    else:
        assert code == 0 and summary["complete"]
        assert summary["resources"]["max_memory_mib"] == 4096
        assert summary["allocation"]["live_observation"]["memory_evidence_kind"] == "live_scheduler_job_request"
        assert summary["allocation"]["live_observation"]["memory_enforcement_verified"] is False


def test_cli_timeout_keeps_failure_evidence_without_complete_artifacts(tmp_path, monkeypatch):
    module, args, _, _ = cli_inputs(tmp_path, monkeypatch)
    def timeout(*params, **kwargs):
        kwargs["deadline_check"]("synthetic_statistics", 0)
        raise preparation.PreparationBudgetExceeded("synthetic timeout")
    monkeypatch.setattr(module, "fit_full_train_controls", timeout)
    summary, code = module.run_preparation(args)
    saved = json.loads((Path(args.output_dir) / "summary.json").read_text())
    assert code == 3 and not summary["complete"] and not saved["complete"]
    assert saved["resources"]["last_stage"] == "synthetic_statistics"
    assert not (Path(args.output_dir) / "controls.json").exists()


def test_cli_output_budget_cannot_publish_complete_controls(tmp_path, monkeypatch):
    module, args, _, _ = cli_inputs(tmp_path, monkeypatch)
    args.max_output_bytes = 4096
    summary, code = module.run_preparation(args)
    assert code == 3 and not summary["complete"]
    assert not (Path(args.output_dir) / "controls.json").exists()
    assert sum(path.stat().st_size for path in Path(args.output_dir).rglob("*") if path.is_file()) <= args.max_output_bytes


def test_oversized_startup_metadata_retains_compact_failure_within_small_total_cap(tmp_path, monkeypatch):
    module, args, _, _ = cli_inputs(tmp_path, monkeypatch)
    args.max_output_bytes = 4096
    monkeypatch.setattr(module, "_sources", lambda train: {f"synthetic_{i}": {"payload": "structure-source" * 40, "size": i, "mtime_ns": i}
                                                          for i in range(20)})
    monkeypatch.setattr(module, "fit_full_train_controls", lambda *args, **kwargs: pytest.fail("oversized startup metadata must fail before fit"))
    summary, code = module.run_preparation(args)
    output = Path(args.output_dir)
    saved = json.loads((output / "summary.json").read_text())
    actual = sum(path.stat().st_size for path in output.rglob("*") if path.is_file())
    assert code == 3 and not summary["complete"] and not saved["complete"]
    assert saved["input_bindings"]["source_sha256"] == "a" * 64
    assert saved["resources"]["last_stage"] == "before_fit"
    assert saved["output_bytes"] == actual <= args.max_output_bytes
    assert len((output / "summary.json").read_bytes()) <= module.FAILURE_EVIDENCE_RESERVE


def test_failed_payload_fsync_preserves_pending_and_previous_evidence_inside_cap(tmp_path, monkeypatch):
    module, args, _, _ = cli_inputs(tmp_path, monkeypatch)
    calls = []
    def fsync(fd):
        calls.append(fd)
        if len(calls) == 3:
            raise OSError("synthetic payload fsync failure")
    monkeypatch.setattr(module.os, "fsync", fsync)
    summary, code = module.run_preparation(args)
    output = Path(args.output_dir)
    saved = json.loads((output / "summary.json").read_text())
    assert code == 2 and not summary["complete"] and saved["error_type"] == "OSError"
    assert (output / "controls.json.pending").is_file() and (output / "fit_ids.json.pending").is_file()
    assert (output / "summary.before_failure.json").is_file()
    assert set(saved["retained_files"]) == {"controls.json.pending", "fit_ids.json.pending", "summary.before_failure.json"}
    actual = sum(path.stat().st_size for path in output.rglob("*") if path.is_file())
    assert saved["output_bytes"] == actual <= args.max_output_bytes


def test_atomic_summary_replacement_accounts_for_old_and_pending_bytes(tmp_path):
    module = runner()
    output = tmp_path / "output"
    output.mkdir()
    old = output / "summary.json"
    original = b"x" * 2500
    old.write_bytes(original)
    with pytest.raises(preparation.PreparationBudgetExceeded, match="atomic replacement"):
        module._summary_write(old, {"status": "RUNNING", "details": "y" * 2500}, max_output_bytes=6000)
    assert old.read_bytes() == original and not (output / "summary.json.pending").exists()


def test_secondary_failure_writer_error_does_not_hide_original_exit_or_error(tmp_path, monkeypatch):
    module, args, _, _ = cli_inputs(tmp_path, monkeypatch)
    def timeout(*params, **kwargs):
        raise preparation.PreparationBudgetExceeded("original synthetic timeout")
    monkeypatch.setattr(module, "fit_full_train_controls", timeout)
    def evidence_failure(*params, **kwargs):
        raise OSError("synthetic unavailable failure storage")
    monkeypatch.setattr(module, "_failure_summary_write", evidence_failure)
    summary, code = module.run_preparation(args)
    assert code == 3 and not summary["complete"] and summary["error"] == "original synthetic timeout"
    assert "unavailable failure storage" in summary["failure_evidence_write_error"]


def test_cli_allocation_rejection_precedes_any_input_read(tmp_path, monkeypatch):
    module = runner()
    def reject():
        raise RuntimeError("CPU Slurm allocation absent")
    monkeypatch.setattr(module, "cpu_slurm_environment", reject)
    monkeypatch.setattr(module, "load_experiment_config", lambda *args: pytest.fail("input read before allocation rejection"))
    args = Namespace(output_dir=str(tmp_path / "output"))
    summary, code = module.run_preparation(args)
    assert code == 2 and not summary["complete"] and not Path(args.output_dir).exists()
