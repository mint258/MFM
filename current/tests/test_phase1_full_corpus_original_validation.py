"""Real tiny-H0 integration: physical-unit validation and atomic continuation.

Only synthetic CPU LMDB records and an identified test tracking spy are used.
This does not establish real-corpus learning, GPU capacity or W&B persistence.
"""
from copy import deepcopy
import math

import pytest
import torch

from phychem_mfm.factory import build_model
from phychem_mfm.phase1.downstream_training import checkpoint_content_sha256
from phychem_mfm.phase1.formal_runtime import backbone_state_hash
from phychem_mfm.phase1.full_corpus_controls import BINDING_FIELDS
from phychem_mfm.phase1.full_corpus_training import FullCorpusTrainer, FullCorpusTrainingError
from phychem_mfm.training.full_corpus_normalization import full_train_regression_normalization
from test_phase1_full_corpus_training import (fixture, validation_fixture, OfflineSpy, assert_same_tree)
from test_phase1_full_corpus_original_metrics import make_controls, _builder, _seal, _assert_builtin


def controlled_fixture(path, *, name="fresh", shared_manifest=None):
    trainer, batches, _, data = fixture(path, dropout=0., name=name, shared_manifest=shared_manifest)
    old = trainer.model.head_config["regression_output_normalization"]
    moments = deepcopy(old["full_training_moments"])
    moments["energy"].update(mean=7., m2=4. * moments["energy"]["count"])
    moments["charge"].update(mean=.3, m2=.04 * moments["charge"]["count"])
    binding = {k: old["training_provenance"][k] for k in BINDING_FIELDS}
    norm = full_train_regression_normalization(moments, binding)
    snapshot = trainer.model.config_dict()
    recipe = {"architecture": {"preset": "shared_light", "task_route_per_task": snapshot["task_route_per_task"]},
              "backbone": deepcopy(snapshot["backbone_config"]),
              "expert": deepcopy(snapshot["expert_config"]), "head": deepcopy(snapshot["head_config"])}
    recipe["head"]["regression_output_normalization"] = norm
    torch.manual_seed(31)
    model = build_model(recipe)
    with torch.no_grad():
        for parameter in model.parameters():
            parameter.zero_()
    config = deepcopy(trainer.config)
    config["original_unit_controls"] = make_controls(norm, _builder().build_validation_controls)
    config["bindings"]["normalization_contract_sha256"] = norm["contract_sha256"]
    config["bindings"]["initial_encoder_sha256"] = backbone_state_hash(model)
    spy = OfflineSpy(name)
    controlled = FullCorpusTrainer(model, trainer.sampler, config, tracker=spy)
    return controlled, batches, spy, data


def test_original_mae_rmse_use_affine_head_units_and_the_same_single_forward(tmp_path):
    with torch.random.fork_rng(devices=[]):
        trainer, _, spy, data = controlled_fixture(tmp_path / "fixture")
        sampler, batches, records = validation_fixture(trainer, data)
        calls = [0]
        actual_forward = trainer.model.forward_pretrain
        def counted(*args, **kwargs):
            calls[0] += 1
            return actual_forward(*args, **kwargs)
        trainer.model.forward_pretrain = counted
        controller, rng = trainer.controller.state_dict(), torch.get_rng_state().clone()
        trainer._remaining = lambda: 20.
        assert trainer._validate("routine", sampler, batches)
        assert calls[0] == sampler.batches_consumed
        metrics = trainer.last_validation["original_unit_metrics"]
        energy = metrics["targets"]["energy_kcal_per_mol"]["model"]
        charge = metrics["targets"]["net_atomic_charge_e"]["model"]
        differences = [abs(float(record.energy) - 7.) for record in records]
        assert energy["count"] == 5
        assert energy["mae"] == pytest.approx(sum(differences) / 5, rel=1e-6)
        assert energy["rmse"] == pytest.approx(math.sqrt(sum(v*v for v in differences) / 5), rel=1e-6)
        qdiff = [abs(float(v) - .3) for record in records for v in record.y.reshape(-1)]
        assert charge["count"] == len(qdiff)
        assert charge["mae"] == pytest.approx(sum(qdiff) / len(qdiff), rel=1e-6)
        scaled = [v / 2. for v in differences]
        huber = sum(.5 * min(v, 5.) ** 2 + 5. * max(v - 5., 0.) for v in scaled) / 5
        assert trainer.last_validation["leaf_losses"]["energy"] == pytest.approx(huber, rel=1e-6)
        assert trainer.controller.state_dict() == controller and torch.equal(torch.get_rng_state(), rng)
        assert trainer.counters["optimizer_updates"] == 0
        assert any("validation/original/energy_kcal_per_mol/model/mae" in row for row in spy.rows)
        _assert_builtin(trainer.last_validation)


def test_partial_validation_safe_checkpoint_continues_metrics_without_recounting(tmp_path):
    with torch.random.fork_rng(devices=[]):
        trained, _, _, data = controlled_fixture(tmp_path / "fixture", name="trained")
        sampler, batches, _ = validation_fixture(trained, data)
        remaining = iter((20., 0.))
        trained._remaining = lambda: next(remaining)
        assert not trained._validate("routine", sampler, batches)
        state = trained.validation_state["original_unit_meter_state"]
        first_count = next(row["count"] for row in state["meters"] if row["target"] == "energy_kcal_per_mol" and row["estimate"] == "model")
        assert 0 < first_count == sampler.samples_consumed < 5
        archive = tmp_path / "partial.pt"
        torch.save(trained.checkpoint(), archive)
        payload = torch.load(archive, map_location="cpu", weights_only=True)
        receiver, _, _, _ = controlled_fixture(tmp_path / "unused", name="receiver", shared_manifest=data)
        valid, _, _ = validation_fixture(receiver, data)
        receiver.load_checkpoint(payload, checkpoint_file_sha256="f" * 64,
                                 validation_sampler_factory=lambda scope: valid)
        for trainer in (trained, receiver):
            sample, rest, _ = validation_fixture(trainer, data)
            trainer._remaining = lambda: 20.
            assert trainer._validate("routine", sample, rest)
        assert receiver.last_validation == trained.last_validation
        assert receiver.last_validation["original_unit_metrics"]["targets"]["energy_kcal_per_mol"]["model"]["count"] == 5
        assert receiver.validation_state is None


@pytest.mark.parametrize("where", ("pending", "closed"))
def test_resealed_invalid_meter_state_rejects_before_live_model_optimizer_rng_or_cursor(tmp_path, where):
    with torch.random.fork_rng(devices=[]):
        trained, _, _, data = controlled_fixture(tmp_path / "fixture", name="trained")
        sample, batches, _ = validation_fixture(trained, data)
        if where == "pending":
            remaining = iter((20., 0.))
            trained._remaining = lambda: next(remaining)
            assert not trained._validate("routine", sample, batches)
        else:
            trained._remaining = lambda: 20.
            assert trained._validate("routine", sample, batches)
        bad = trained.checkpoint()
        row = bad["validation_state"] if where == "pending" else bad["last_validation"]
        meter = row["original_unit_meter_state"]
        next(v for v in meter["meters"] if v["kind"] == "regression")["squared"] = -1.
        _seal(meter, "state_sha256")
        bad["checkpoint_content_sha256"] = checkpoint_content_sha256(bad)
        receiver, _, _, _ = controlled_fixture(tmp_path / "unused", name="receiver", shared_manifest=data)
        val, _, _ = validation_fixture(receiver, data)
        model, optimizer, rng = deepcopy(receiver.model.state_dict()), deepcopy(receiver.optimizer.state_dict()), torch.get_rng_state().clone()
        controller, cursor, tracking = receiver.controller.state_dict(), receiver.sampler.state_dict(), deepcopy(receiver.tracking)
        with pytest.raises(FullCorpusTrainingError, match="original-unit"):
            receiver.load_checkpoint(bad, checkpoint_file_sha256="f" * 64,
                                     validation_sampler_factory=lambda scope: val)
        assert_same_tree(receiver.model.state_dict(), model)
        assert_same_tree(receiver.optimizer.state_dict(), optimizer)
        assert receiver.controller.state_dict() == controller and receiver.sampler.state_dict() == cursor
        assert receiver.tracking == tracking and torch.equal(torch.get_rng_state(), rng)
        assert receiver.validation_state is receiver.last_validation is None


def test_complete_original_unit_report_is_checked_and_remains_safe_loadable(tmp_path):
    with torch.random.fork_rng(devices=[]):
        trained, batches, _, data = controlled_fixture(tmp_path / "fixture", name="trained")
        full, val_batches, _ = validation_fixture(trained, data)
        trained.config["bindings"]["full_validation_manifest_sha256"] = full.index.content_sha256
        for batch in batches:
            trained._consume(batch)
        assert trained.fit((), validation_factory=lambda scope: (full, val_batches))["status"] == "complete"
        receiver, _, _, _ = controlled_fixture(tmp_path / "unused", name="receiver", shared_manifest=data)
        val, _, _ = validation_fixture(receiver, data)
        receiver.config["bindings"]["full_validation_manifest_sha256"] = val.index.content_sha256
        payload = trained.checkpoint()
        wrong = deepcopy(payload)
        wrong["last_validation"]["original_unit_metrics"]["targets"]["energy_kcal_per_mol"]["model"]["mae"] += 1.
        wrong["checkpoint_content_sha256"] = checkpoint_content_sha256(wrong)
        before, rng = deepcopy(receiver.model.state_dict()), torch.get_rng_state().clone()
        with pytest.raises(FullCorpusTrainingError, match="differs from its accumulators"):
            receiver.load_checkpoint(wrong, checkpoint_file_sha256="f" * 64,
                                     validation_sampler_factory=lambda scope: val)
        assert_same_tree(receiver.model.state_dict(), before)
        assert torch.equal(torch.get_rng_state(), rng) and receiver.sampler.samples_consumed == 0
        archive = tmp_path / "complete.pt"
        torch.save(payload, archive)
        receiver.load_checkpoint(torch.load(archive, map_location="cpu", weights_only=True),
                                 checkpoint_file_sha256="f" * 64, validation_sampler_factory=lambda scope: val)
        assert receiver.status == "complete" and receiver.last_validation == trained.last_validation
