from copy import deepcopy
import csv
import json
import sys
from types import SimpleNamespace

import numpy as np
import pytest
import torch

from phychem_mfm.phase1.dev_probe import (
    DEV_TARGETS,
    PreparedDevData,
    conformer_cache_metadata,
    fit_fold_target_scaler,
    grouped_fold_assignments,
    load_phase1_probe_checkpoint,
    read_train_records,
    require_train_csv,
    run_train_only_cv,
    validate_conformer_cache,
)


def test_train_source_guard_rejects_all_test_paths_before_read(tmp_path):
    forbidden = (tmp_path / "official_test.csv", tmp_path / "log_test_data.csv",
                 tmp_path / "fold_1" / "log_train_data.csv",
                 tmp_path / "fold-1" / "log_train_data.csv",
                 tmp_path / "official_test" / "log_train_data.csv")
    for path in forbidden:
        with pytest.raises(ValueError, match="global log_train_data.csv"):
            require_train_csv(path)
    assert require_train_csv(tmp_path / "log_train_data.csv").name == "log_train_data.csv"


def test_train_csv_identity_aliases_are_always_in_one_cv_fold(tmp_path):
    source = tmp_path / "log_train_data.csv"
    smiles = ("CCO", "OCC", "CCN", "CCC", "CCCl", "CCBr", "CCF")
    with source.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=("SMILES", "Molecule Name", *DEV_TARGETS))
        writer.writeheader()
        for index, value in enumerate(smiles):
            writer.writerow({"SMILES": value, "Molecule Name": f"row-{index}",
                             **{name: float(index) for name in DEV_TARGETS}})
    records, ledger, metadata = read_train_records(source, max_molecules=6, seed=12)
    assert not ledger
    assert metadata["selected_unique_molecules"] == 6
    assert records[0]["inchikey"] == records[1]["inchikey"]
    assert records[0]["fold"] == records[1]["fold"]
    keys = [row["inchikey"] for row in records]
    folds = np.asarray([row["fold"] for row in records])
    assert set(folds) == {0, 1, 2}
    for fold in range(3):
        assert not {key for key, value in zip(keys, folds) if value == fold} & {
            key for key, value in zip(keys, folds) if value != fold
        }
    np.testing.assert_array_equal(grouped_fold_assignments(keys, seed=12), folds)


def test_target_scaler_excludes_validation_values_and_missing_labels():
    labels = np.asarray([[1.0, np.nan], [3.0, 4.0], [1e9, -1e9]])
    scaler = fit_fold_target_scaler(labels, np.asarray([0, 1]))
    np.testing.assert_array_equal(scaler["counts"], [2, 1])
    np.testing.assert_allclose(scaler["mean"], [2, 4])
    np.testing.assert_allclose(scaler["std"], [1, 1])


def test_cache_contract_rejects_source_identity_recipe_and_old_cache_drift():
    rows = [{"row_identity": "row-a", "inchikey": "key-a", "fold": 0}]
    metadata = conformer_cache_metadata(rows, {"source_csv_sha256": "source-a"},
                                        seed=3, max_atoms=32, source_sha256="code-a")
    from phychem_mfm.phase1.identity import canonical_hash
    payload = {"metadata": metadata, "metadata_sha256": canonical_hash(metadata),
               "molecules": {}, "failures": {"key-a": {"reason": "excluded"}}}
    assert validate_conformer_cache(payload, metadata) is payload
    for field, value in (("source_csv_sha256", "source-b"), ("source_code_sha256", "code-b"),
                         ("row_identities", ["row-b"]), ("seed", 4), ("max_atoms", 64)):
        changed = deepcopy(metadata)
        changed[field] = value
        with pytest.raises(RuntimeError, match="contract mismatch"):
            validate_conformer_cache(payload, changed)
    changed = deepcopy(metadata)
    changed["recipe"]["atom_encoding"] = "legacy_encoding"
    with pytest.raises(RuntimeError, match="contract mismatch"):
        validate_conformer_cache(payload, changed)
    with pytest.raises(RuntimeError, match="contract mismatch"):
        validate_conformer_cache({"features": [], "split_ids": [0, 1]}, metadata)


def test_old_checkpoint_cannot_enter_phase1_probe(tmp_path):
    path = tmp_path / "old.pt"
    torch.save({"architecture_type": "shared_multitask", "model_config": {"head_config": {}}}, path)
    with pytest.raises(RuntimeError, match="new Phase 1"):
        load_phase1_probe_checkpoint(path)


def _tracked_fake_run(monkeypatch, tmp_path, events):
    class Run:
        id = "test-unique-run"
        dir = str(tmp_path)
        disabled = False
        summary = {}

        def log(self, values, *, step):
            events.append(("log", values, step))

        def finish(self, *, exit_code):
            events.append(("finish", exit_code))

    def initialize(**kwargs):
        assert kwargs["mode"] == "offline"
        assert kwargs["id"].startswith("dev-")
        events.append(("init", kwargs))
        run = Run()
        run.id = kwargs["id"]
        return run

    monkeypatch.setitem(sys.modules, "wandb", SimpleNamespace(init=initialize))


def test_cv_tracks_before_encoding_freezes_h0_and_reports_original_units(monkeypatch, tmp_path):
    from phychem_mfm.phase1 import dev_probe

    events = []
    _tracked_fake_run(monkeypatch, tmp_path, events)
    molecules = {
        key: {"x": torch.tensor([[index], [index + 1]], dtype=torch.long),
              "pos": torch.zeros(2, 3)}
        for index, key in enumerate(("a", "b", "c", "d", "e", "f"))
    }
    records = [{"inchikey": key, "fold": index % 3} for index, key in enumerate(molecules)]
    labels = np.asarray([[float(index + target) for target in range(len(DEV_TARGETS))]
                         for index in range(len(records))], dtype=np.float32)
    prepared = PreparedDevData(records, molecules, labels, np.asarray([row["fold"] for row in records]),
                               [], {"retained_unique_molecules": 6})
    monkeypatch.setattr(dev_probe, "prepare_train_only_data", lambda *args, **kwargs: prepared)

    class Encoder(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.scale = torch.nn.Parameter(torch.tensor(2.0))

        def encode_atoms(self, batch):
            assert events[0][0] == "init"
            assert not self.training and not self.scale.requires_grad
            assert not torch.is_grad_enabled()
            assert getattr(batch, "target_pos", None) is None
            events.append(("encode",))
            return torch.cat((batch.x.float() * self.scale, batch.pos), dim=-1)

    encoder = Encoder()
    original = encoder.scale.detach().clone()
    summary = run_train_only_cv(encoder, train_csv=tmp_path / "log_train_data.csv",
                                output_dir=tmp_path / "output", source_sha256="a" * 64,
                                epochs=1, max_molecules=6, batch_size=3, seed=7)
    assert summary["scope"].startswith("DEV ONLY") and summary["status"] == "complete"
    assert len(summary["folds"]) == 3
    assert all(fold["identity_overlap"] == 0 for fold in summary["folds"])
    epoch_logs = [event for event in events if event[0] == "log" and "dev/epoch" in event[1]]
    assert len(epoch_logs) == 3
    for _, values, _ in epoch_logs:
        assert any("/train/LogD/mae_original_log_units" in key for key in values)
        assert any("/validation/LogD/mae_original_log_units" in key for key in values)
    assert encoder.training and encoder.scale.requires_grad and encoder.scale.grad is None
    torch.testing.assert_close(encoder.scale, original, rtol=0, atol=0)
    assert events[-1] == ("finish", 0)
    assert json.loads((tmp_path / "output" / "summary.json").read_text())["scope"].startswith("DEV ONLY")


def test_failed_cv_records_failure_and_closes_tracking_without_training(monkeypatch, tmp_path):
    from phychem_mfm.phase1 import dev_probe

    events = []
    _tracked_fake_run(monkeypatch, tmp_path, events)

    def fail_preparation(*args, **kwargs):
        raise RuntimeError("synthetic source defect")

    monkeypatch.setattr(dev_probe, "prepare_train_only_data", fail_preparation)
    encoder = torch.nn.Linear(2, 2)
    with pytest.raises(RuntimeError, match="synthetic source defect"):
        run_train_only_cv(encoder, train_csv=tmp_path / "log_train_data.csv",
                          output_dir=tmp_path / "output", source_sha256="a" * 64, epochs=1)
    assert events[0][0] == "init" and events[-1] == ("finish", 1)
    assert encoder.training and all(parameter.requires_grad for parameter in encoder.parameters())
    failure = json.loads((tmp_path / "output" / "failure.json").read_text())
    assert failure["status"] == "failed" and failure["error"] == "synthetic source defect"
