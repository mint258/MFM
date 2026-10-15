from __future__ import annotations

import json

import numpy as np
import pytest
import torch

from phychem_mfm.discovery.convergence import ConvergenceGate
from phychem_mfm.discovery.engine import budget_status, should_stop_for_maturity
from phychem_mfm.discovery.identity import recipe_hash
from phychem_mfm.discovery.domain import DomainRecord, records_to_segments
from phychem_mfm.discovery.manifests import Segment, _recipe_index_for_key, allocate_segments, validate_nested_manifests
from phychem_mfm.discovery.registry import ExperimentRegistry
from phychem_mfm.discovery.schedule import DataProgressSchedule
from phychem_mfm.factory import task_routes_from_preset
from phychem_mfm.training.data import DomainWrapperDataset, SampleTypeWrapperDataset, dataset_atom_counts


def test_hybrid_route_definitions_are_exact():
    assert task_routes_from_preset("hybrid_g").to_dict() == {
        "energy": "light",
        "charge": "light",
        "element": "light",
        "geometry": "expert",
        "bond": "light",
        "descriptor": "light",
    }
    assert task_routes_from_preset("hybrid_qg").to_dict()["charge"] == "expert"
    assert task_routes_from_preset("hybrid_qg").to_dict()["geometry"] == "expert"


def test_recipe_hash_includes_pool_identity():
    config = {"architecture": {"preset": "light"}, "training": {"seed": 0}}
    first = recipe_hash(config, train_pool_hash="pool-a", validation_pool_hash="val")
    second = recipe_hash(config, train_pool_hash="pool-b", validation_pool_hash="val")
    assert first != second
    assert first == recipe_hash(config, train_pool_hash="pool-a", validation_pool_hash="val")


def test_data_progress_schedule_is_batch_invariant():
    schedule = DataProgressSchedule("delayed", 1000, 0.25, 0.15, 0.15, 0.3)
    assert schedule.descriptor_scale(249) == 0.0
    assert schedule.descriptor_scale(250) == 0.0
    assert schedule.descriptor_scale(325) == pytest.approx(0.5)
    assert schedule.descriptor_scale(400) == 1.0
    assert schedule.stage1_scale(400) == pytest.approx(0.3)
    assert schedule.is_mature(400)


def test_nested_pool_perturbation_assignment_is_sample_identity_stable():
    boundaries = (0.625, 0.75, 0.8125, 0.9375, 1.0)
    shared = [f"principal:{index}" for index in range(100)]
    small = [_recipe_index_for_key(key, 7001, boundaries) for key in shared]
    large = [_recipe_index_for_key(key, 7001, boundaries) for key in shared + ["new"]]
    assert small == large[:len(shared)]


def test_domain_segments_are_compacted_independent_of_stratified_order():
    records = [
        DomainRecord("principal.lmdb", 1, "principal", "p1", "s1", 2),
        DomainRecord("molecule.lmdb", 8, "molecule", "m1", "s2", 2),
        DomainRecord("principal.lmdb", 2, "principal", "p2", "s3", 2),
        DomainRecord("molecule.lmdb", 9, "molecule", "m2", "s4", 2),
    ]
    assert records_to_segments(records) == [
        Segment("molecule.lmdb", 8, 2), Segment("principal.lmdb", 1, 2),
    ]


def test_wrapped_concat_dataset_preserves_atom_counts():
    left = torch.utils.data.TensorDataset(torch.arange(2))
    right = torch.utils.data.TensorDataset(torch.arange(3))
    left.atom_counts = np.asarray([2, 4])
    right.atom_counts = np.asarray([1, 3, 5])
    base = torch.utils.data.ConcatDataset([left, right])
    wrapped = DomainWrapperDataset(SampleTypeWrapperDataset(base, "clean"), 0)
    assert dataset_atom_counts(wrapped).tolist() == [2, 4, 1, 3, 5]


def test_convergence_gate_separates_fast_improvement_from_plateau():
    gate = ConvergenceGate(validation_window=4)
    plateau = [
        {"val/loss/total": value, "val/loss/raw/energy": value}
        for value in (1.0, 0.99, 0.985, 0.98)
    ]
    mature = gate.evaluate(plateau, pass_count=1, schedule_mature=True, warmup_complete=True)
    assert mature.optimization_mature
    assert mature.status == "OPTIMIZATION_MATURE"
    assert not mature.transfer_ready
    assert gate.evaluate(
        plateau, pass_count=1, schedule_mature=True, warmup_complete=True, target_adequate=True
    ).transfer_ready
    falling = [
        {"val/loss/total": value, "val/loss/raw/energy": value}
        for value in (1.0, 0.9, 0.7, 0.6)
    ]
    assert not gate.evaluate(falling, pass_count=1, schedule_mature=True, warmup_complete=True).transfer_ready


def test_convergence_gate_distinguishes_multitask_learning_from_catastrophic_worsening():
    gate = ConvergenceGate(validation_window=4)
    noisy_total_but_charge_learning = [
        {"val/loss/total": total, "val/loss/raw/charge": charge}
        for total, charge in zip((2.5, 1.7, 1.6, 3.8, 1.3, 1.6, 1.65, 1.57), (1.0, .9, .8, .7, .6, .5, .4, .3))
    ]
    decision = gate.evaluate(
        noisy_total_but_charge_learning, pass_count=1, schedule_mature=True, warmup_complete=True
    )
    assert decision.status == "STILL_IMPROVING"
    catastrophic = [
        {"val/loss/total": value, "val/loss/raw/charge": value}
        for value in (0.30, 0.29, 0.88, 0.86)
    ]
    assert gate.evaluate(catastrophic, pass_count=6, schedule_mature=True, warmup_complete=True).status == "DIVERGED"


def test_budget_limit_does_not_replace_optimization_status():
    assert budget_status(completed_passes=7, max_passes=8, optimization_status="STILL_IMPROVING") == "WITHIN_BUDGET"
    assert budget_status(completed_passes=8, max_passes=8, optimization_status="STILL_IMPROVING") == "BUDGET_LIMIT_REACHED"
    assert budget_status(completed_passes=8, max_passes=8, optimization_status="OPTIMIZATION_MATURE") == "WITHIN_BUDGET"


def test_optimization_maturity_stops_for_transfer_or_diagnosis():
    class Decision:
        def __init__(self, mature):
            self.optimization_mature = mature

    assert not should_stop_for_maturity(Decision(False))
    assert should_stop_for_maturity(Decision(True))


def test_registry_reuse_and_immutable_identity(tmp_path):
    registry = ExperimentRegistry(tmp_path / "registry.json")
    registry.register_experiment(
        {
            "experiment_id": "run-a",
            "recipe_hash": "abc",
            "train_pool_hash": "train",
            "validation_pool_hash": "val",
            "source_commit": "commit",
        }
    )
    registry.register_checkpoint(
        {
            "experiment_id": "run-a",
            "recipe_hash": "abc",
            "checkpoint_sha256": "deadbeef",
            "checkpoint_state": "transfer_ready",
            "aliases": ["first_pass", "transfer_ready"],
            "path": "/checkpoint.pt",
        }
    )
    assert registry.query_reusable("abc", "first_pass")[0]["path"] == "/checkpoint.pt"
    with pytest.raises(RuntimeError, match="EXACT_REUSABLE"):
        registry.assert_submit_allowed("abc", "transfer_ready")
    assert json.loads((tmp_path / "registry.json").read_text())["format_version"] == 1


def test_registry_instances_merge_instead_of_clobbering(tmp_path):
    path = tmp_path / "registry.json"
    first = ExperimentRegistry(path)
    second = ExperimentRegistry(path)
    first.register_experiment(
        {
            "experiment_id": "run-a",
            "recipe_hash": "a",
            "train_pool_hash": "train",
            "validation_pool_hash": "val",
            "source_commit": "commit",
        }
    )
    second.register_experiment(
        {
            "experiment_id": "run-b",
            "recipe_hash": "b",
            "train_pool_hash": "train",
            "validation_pool_hash": "val",
            "source_commit": "commit",
        }
    )
    assert set(ExperimentRegistry(path).payload["experiments"]) == {"run-a", "run-b"}
    first.update_experiment("run-a", {"downstream_results": {"expansionrx": {"score": 1.0}}})
    second.update_experiment("run-a", {"downstream_results": {"qm9": {"score": 2.0}}})
    merged = ExperimentRegistry(path).payload["experiments"]["run-a"]["downstream_results"]
    assert set(merged) == {"expansionrx", "qm9"}


def test_registry_preserves_results_across_source_only_resume(tmp_path):
    path = tmp_path / "registry.json"
    registry = ExperimentRegistry(path)
    base = {
        "experiment_id": "run-a",
        "recipe_hash": "same-science",
        "train_pool_hash": "train",
        "validation_pool_hash": "val",
        "source_commit": "commit-a",
        "downstream_results": {"qm7": {"score": 1.0}},
        "result_paths": {"frozen_h0_qm7": "/qm7.json"},
    }
    registry.register_experiment(base)
    registry.register_experiment(
        {
            **base,
            "source_commit": "commit-b",
            "downstream_results": {},
            "result_paths": {"summary": "/summary.json"},
        }
    )
    merged = ExperimentRegistry(path).payload["experiments"]["run-a"]
    assert merged["source_commit"] == "commit-a"
    assert merged["current_source_commit"] == "commit-b"
    assert merged["source_commits"] == ["commit-a", "commit-b"]
    assert merged["downstream_results"]["qm7"]["score"] == 1.0
    assert merged["result_paths"] == {"frozen_h0_qm7": "/qm7.json", "summary": "/summary.json"}


def test_segment_allocation_and_nesting():
    inventory = [("a", 4), ("b", 4)]
    assert allocate_segments(inventory, count=6) == [Segment("a", 0, 4), Segment("b", 0, 2)]
    manifests = [
        {"pool_id": "small", "unique_structure_count": 3, "segments": [{"shard": "a", "start": 0, "end": 2}]},
        {
            "pool_id": "large",
            "unique_structure_count": 6,
            "segments": [
                {"shard": "a", "start": 0, "end": 3},
                {"shard": "b", "start": 0, "end": 1},
            ],
        },
    ]
    validate_nested_manifests(manifests)
