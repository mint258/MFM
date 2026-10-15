from __future__ import annotations

import json
from types import SimpleNamespace

import torch

from phychem_mfm.discovery.registry import ExperimentRegistry
from phychem_mfm.evaluation.fidelity import FidelityLevel, TargetFidelityRegistry
from phychem_mfm.evaluation.metrics import classification_metrics, regression_metrics
from phychem_mfm.evaluation.normalization import TargetTransformRegistry, inverse_transform_prediction
from phychem_mfm.evaluation.target_adequacy import formal_charges_from_smiles


def test_current_predictions_are_already_in_original_target_space():
    prediction = torch.tensor([[-80.0], [-75.0]])
    restored = inverse_transform_prediction("energy", prediction, {"muE": -100.0, "stdE": 20.0})
    assert torch.equal(restored, prediction)
    metadata = TargetTransformRegistry({"muE": -100.0, "stdE": 20.0}).to_dict()
    assert metadata["targets"]["energy"]["kind"] == "identity"
    assert metadata["targets"]["energy"]["unit"] == "kcal/mol"


def test_formal_charge_diagnostic_is_recovered_from_stored_smiles():
    batch = SimpleNamespace(canonical_smiles=["C[NH3+]", "CC(=O)[O-]", "not-smiles"])
    charges, valid = formal_charges_from_smiles(batch, 3, torch.device("cpu"))
    assert charges.tolist() == [1.0, -1.0, 0.0]
    assert valid.tolist() == [True, True, False]


def test_fidelity_registry_respects_metric_direction(tmp_path):
    path = tmp_path / "thresholds.json"
    path.write_text(json.dumps({
        "version": "test",
        "thresholds": [{
            "task": "energy", "metric": "mae", "unit": "kcal/mol",
            "high_fidelity_threshold": 1.0, "usable_threshold": 5.0,
            "higher_is_better": False, "source": "test", "source_type": "project",
            "rationale": "test", "hard_gate_or_diagnostic": "hard_gate", "version": "test",
        }],
    }))
    registry = TargetFidelityRegistry.load(path)
    assert registry.threshold("energy", "mae").classify(0.5) == FidelityLevel.HIGH_FIDELITY
    assert registry.threshold("energy", "mae").classify(3.0) == FidelityLevel.USABLE
    assert not registry.evaluate("energy", {"mae": 8.0})["pass"]


def test_metrics_report_tails_and_rare_class_macro_f1():
    regression = regression_metrics(torch.tensor([0.0, 1.0, 10.0]), torch.zeros(3))
    assert regression["p95_ae"] > regression["median_ae"]
    classification = classification_metrics(torch.tensor([0, 0, 0, 1]), torch.tensor([0, 0, 1, 1]), 2)
    assert classification["accuracy"] == 0.75
    assert classification["macro_f1"] < classification["accuracy"]


def test_checkpoint_evaluation_is_versioned_and_identity_is_preserved(tmp_path):
    path = tmp_path / "registry.json"
    registry = ExperimentRegistry(path)
    registry.register_experiment({
        "experiment_id": "run", "recipe_hash": "recipe", "train_pool_hash": "train",
        "validation_pool_hash": "val", "source_commit": "commit",
    })
    original = {
        "experiment_id": "run", "recipe_hash": "recipe", "checkpoint_sha256": "sha",
        "checkpoint_state": "pass_end", "aliases": [], "path": "/tmp/checkpoint.pt",
        "transfer_ready_status": False,
    }
    registry.register_checkpoint(original)
    registry.update_checkpoint_evaluation("sha", {
        "target_adequacy_version": "v3", "target_adequacy_status": "ADEQUATE",
        "transfer_ready_status": True,
    })
    registry.register_checkpoint(original)
    item = ExperimentRegistry(path).payload["checkpoints"]["sha"]
    assert item["transfer_ready_status"] is True
    assert item["evaluations"]["v3"]["target_adequacy_status"] == "ADEQUATE"
