"""Synthetic optimization and restoration oracles; no final-test labels or I/O.

The identified tracker below is a test spy, not a substitute for a persisted
production W&B run. All numbers, molecule IDs and source digests are synthetic.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import random
from types import SimpleNamespace

import numpy as np
import pytest
import torch
from torch import nn
from torch.nn import functional as F
from torch_geometric.data import Data

from conftest import small_config
from phychem_mfm.factory import build_model
from phychem_mfm.phase1.downstream_readout import SourceAlignedH0Readout
from phychem_mfm.phase1.downstream_training import (
    DownstreamTrainBatch,
    DownstreamTrainer,
    DownstreamTrainingError,
    checkpoint_content_sha256,
)
from phychem_mfm.phase1.formal_runtime import backbone_state_hash
from phychem_mfm.phase1.identity import canonical_hash


class SyntheticWandbSpy:
    """Minimal, explicitly synthetic W&B-compatible identity and log cursor."""

    def __init__(self, *, next_step=0, fail_at=None):
        self.id = "synthetic-stage31"
        self.path = f"tests/synthetic/{self.id}"
        self.settings = SimpleNamespace(mode="offline")
        self.disabled = False
        self.step = next_step
        self.fail_at = fail_at
        self.rows = []

    def log(self, payload, *, step, commit=None):
        assert commit is True, "Explicit W&B step requires commit=True to advance history"
        assert step == self.step, "History cursor must not skip or rewind"
        if step == self.fail_at:
            raise RuntimeError("synthetic tracker write failed")
        self.rows.append((step, deepcopy(payload)))
        self.step += 1


class ToyBackbone(nn.Module):
    """A differentiable H0 with genuine dropout/BN, inside genuine SharedMFM."""

    def __init__(self, *, dropout=0.0, batch_norm=False):
        super().__init__()
        self.linear = nn.Linear(4, 8)
        self.norm = nn.BatchNorm1d(8) if batch_norm else nn.Identity()
        self.dropout = nn.Dropout(dropout)
        self.register_buffer("unused_marker", torch.tensor([13.0]))

    def forward(self, data):
        assert set(data.keys()) == {"x", "pos", "batch", "ptr"}
        features = torch.cat((data.x.to(torch.float32).unsqueeze(1) / 10, data.pos), dim=1)
        return self.dropout(self.norm(self.linear(features)))


def assert_nested_equal(left, right):
    if isinstance(left, torch.Tensor):
        assert isinstance(right, torch.Tensor)
        assert left.dtype == right.dtype and left.shape == right.shape
        assert torch.equal(left, right)
    elif isinstance(left, dict):
        assert isinstance(right, dict) and set(left) == set(right)
        for key in left:
            assert_nested_equal(left[key], right[key])
    elif isinstance(left, (list, tuple)):
        assert isinstance(right, type(left)) and len(left) == len(right)
        for a, b in zip(left, right):
            assert_nested_equal(a, b)
    else:
        assert left == right


def make_batch(level="atom", tasks=2, offset=0.0):
    # Two unequal graphs. Each graph's encoder order differs from native order.
    encoder = Data(
        x=torch.tensor([5, 7, 0, 5, 7], dtype=torch.long),
        pos=torch.tensor([[0., 0., 0.], [1., .2, 0.], [0., 1., 0.],
                          [.3, 1., .4], [1., 1., .1]], dtype=torch.float32),
        batch=torch.tensor([0, 0, 1, 1, 1]),
        ptr=torch.tensor([0, 2, 5]),
        # The trainer must not forward these fields to the backbone.
        y=torch.tensor([-999.]),
        unrelated_annotation="synthetic unused label",
    )
    rows = 5 if level == "atom" else 2
    target = torch.arange(rows * tasks, dtype=torch.float32).reshape(rows, tasks) / 7 + offset
    mask = torch.ones_like(target, dtype=torch.bool)
    return DownstreamTrainBatch(
        encoder_batch=encoder, sample_ids=(f"synthetic-A-{offset:g}", f"synthetic-B-{offset:g}"),
        source_atom_ids=torch.tensor([1, 0, 2, 0, 1]), targets=target,
        candidate_mask=mask.clone(), supervision_mask=mask.clone(), role="train",
    )


def make_system(*, level="atom", mode="finetune", tasks=2, total=4,
                dropout=0.0, batch_norm=False, real=False, loss="mse", seed=19,
                task_weights=None):
    # Independently repeated construction reproduces the initialization, rather
    # than copying trainer checkpoint weights into the reference optimizer.
    with torch.random.fork_rng(devices=[]):
        torch.set_rng_state(torch.Generator(device="cpu").manual_seed(712).get_state())
        architecture = small_config("expert")
        architecture["backbone"].update(dim=8, layers=1, heads=2, dropout=dropout)
        architecture["expert"]["heads"] = 2
        architecture["head"]["profile"] = "phase1"
        model = build_model(architecture)
        if not real:
            model.backbone = ToyBackbone(dropout=dropout, batch_norm=batch_norm)
        readout = SourceAlignedH0Readout(8, tasks, output_level=level, hidden_dim=8)
    normalization = {
        "kind": "identity", "means": [0.0] * tasks, "scales": [1.0] * tasks,
        "train_only": True, "train_data_sha256": "a" * 64,
        "split_manifest_sha256": "b" * 64, "fit_source_sha256": "c" * 64,
    }
    config = {
        "schema_version": "phase1_downstream_training_v1", "mode": mode,
        "total_updates": total, "seed": seed, "device": "cpu",
        "readout_config": readout.config_dict(), "tasks": [f"toy-task-{j}" for j in range(tasks)],
        "loss": loss, "reduction": "task_then_observed_label_mean",
        "task_weights": [1.0] * tasks if task_weights is None else list(task_weights),
        "normalization": normalization,
        "optimizer": {"implementation": "single_tensor_adamw_v1", "lr": .01,
                      "betas": [.8, .9], "eps": 1e-7, "weight_decay": .03, "amsgrad": False},
        "gradient_clip_norm": None,
        "caps": {"wall_seconds": 60.0, "max_sequence_batches": 8,
                 "max_graphs_per_batch": 4, "max_atoms_per_batch": 32, "max_unique_samples": 16},
        "bindings": {"train_data_sha256": "a" * 64, "split_manifest_sha256": "b" * 64,
                     "normalizer_sha256": canonical_hash(normalization), "source_sha256": "d" * 64,
                     "initial_encoder_sha256": backbone_state_hash(model)},
    }
    return model, readout, config


def make_trainer(**kwargs):
    model, readout, config = make_system(**kwargs)
    tracker = SyntheticWandbSpy()
    return DownstreamTrainer(model, readout, config, tracker=tracker), model, readout, config, tracker


def gathered_labels(batch, level):
    if level == "atom":
        native_index = batch.encoder_batch.ptr[batch.encoder_batch.batch] + batch.source_atom_ids
        return (batch.targets[native_index], batch.candidate_mask[native_index],
                batch.supervision_mask[native_index])
    return batch.targets, batch.candidate_mask, batch.supervision_mask


def independent_adamw_oracle(model, readout, config, batches, updates):
    """Direct PyTorch algorithm, independent of trainer step/checkpoint helpers."""
    model.eval()
    for parameter in model.parameters():
        parameter.requires_grad_(False)
    if config["mode"] == "finetune":
        model.backbone.train()
        for parameter in model.backbone.parameters():
            parameter.requires_grad_(True)
    readout.train()
    params = (list(model.backbone.parameters()) if config["mode"] == "finetune" else []) + list(readout.parameters())
    opt = config["optimizer"]
    optimizer = torch.optim.AdamW(params, lr=opt["lr"], betas=tuple(opt["betas"]),
                                 eps=opt["eps"], weight_decay=opt["weight_decay"],
                                 amsgrad=opt["amsgrad"], foreach=False, fused=False)
    losses = []
    with torch.random.fork_rng(devices=[]):
        torch.set_rng_state(torch.Generator(device="cpu").manual_seed(config["seed"]).get_state())
        for update in range(updates):
            batch = batches[update % len(batches)]
            data = batch.encoder_batch
            clean = Data(x=data.x, pos=data.pos, batch=data.batch, ptr=data.ptr)
            optimizer.zero_grad(set_to_none=True)
            if config["mode"] == "frozen":
                with torch.no_grad():
                    h0 = model.encode_atoms(clean)
            else:
                h0 = model.encode_atoms(clean)
            prediction = readout(h0, source_atom_ids=batch.source_atom_ids,
                                 batch=data.batch, ptr=data.ptr).predictions
            target, candidate, supervised = gathered_labels(batch, readout.output_level)
            active = candidate & supervised
            loss = prediction.sum() * 0
            for task, weight in enumerate(config["task_weights"]):
                mask = active[:, task]
                if not bool(mask.any()):
                    continue
                if config["loss"] == "mse":
                    mu = config["normalization"]["means"][task]
                    scale = config["normalization"]["scales"][task]
                    residual = prediction[mask, task] - (target[mask, task] - mu) / scale
                    raw = residual.square().mean()
                else:
                    raw = F.binary_cross_entropy_with_logits(prediction[mask, task], target[mask, task])
                loss = loss + weight * raw / sum(config["task_weights"])
            loss.backward()
            if config["gradient_clip_norm"] is not None:
                torch.nn.utils.clip_grad_norm_(params, config["gradient_clip_norm"])
            optimizer.step()
            losses.append(float(loss.detach()))
        local_rng = torch.get_rng_state().clone()
    return optimizer, local_rng, losses


@pytest.mark.parametrize("level", ["graph", "atom"])
@pytest.mark.parametrize("mode", ["frozen", "finetune"])
def test_real_shared_h0_end_to_end_updates_only_allowed_parameters(level, mode):
    trainer, model, readout, _, tracker = make_trainer(level=level, mode=mode, real=True, total=2)
    before_model = deepcopy(model.state_dict())
    before_readout = deepcopy(readout.state_dict())
    result = trainer.fit((make_batch(level),), max_updates=2)
    assert result["optimizer_updates"] == 2
    assert result["sample_exposure"] == 4 and result["atom_exposure"] == 10
    assert result["formal_eligible"] is False
    assert any(not torch.equal(value, readout.state_dict()[key])
               for key, value in before_readout.items() if isinstance(value, torch.Tensor))
    changed_backbone = False
    for key, value in before_model.items():
        if key.startswith("backbone.") and mode == "finetune":
            changed_backbone |= not torch.equal(value, model.state_dict()[key])
        else:
            assert_nested_equal(value, model.state_dict()[key])
    assert changed_backbone == (mode == "finetune")
    for name, parameter in model.named_parameters():
        if mode == "frozen" or not name.startswith("backbone."):
            assert parameter.grad is None
    assert tracker.step >= 2


def test_frozen_bn_dropout_all_buffers_and_original_heads_are_unchanged():
    trainer, model, _, _, _ = make_trainer(mode="frozen", dropout=.4, batch_norm=True)
    before = deepcopy(model.state_dict())
    trainer.fit((make_batch(),), max_updates=4)
    assert_nested_equal(before, model.state_dict())
    assert model.backbone.training is False
    assert all(parameter.grad is None for parameter in model.parameters())


@pytest.mark.parametrize("level", ["graph", "atom"])
def test_native_targets_and_both_masks_match_independent_optimizer(level):
    trainer, actual_model, actual_readout, config, _ = make_trainer(level=level, total=3, task_weights=[1., 3.])
    ref_model, ref_readout, ref_config = make_system(level=level, total=3, task_weights=[1., 3.])
    batch = make_batch(level)
    candidate, supervision = batch.candidate_mask.clone(), batch.supervision_mask.clone()
    candidate[0, 0] = False
    supervision[0, 0] = False
    supervision[-1, 1] = False
    targets = batch.targets.clone()
    targets[0, 0] = float("nan")
    targets[-1, 1] = float("nan")
    batch = replace(batch, targets=targets, candidate_mask=candidate, supervision_mask=supervision)
    reference_optimizer, reference_rng, _ = independent_adamw_oracle(ref_model, ref_readout, ref_config, (batch,), 3)
    trainer.fit((batch,), max_updates=3)
    checkpoint = trainer.checkpoint()
    assert_nested_equal(ref_model.state_dict(), actual_model.state_dict())
    assert_nested_equal(ref_readout.state_dict(), actual_readout.state_dict())
    assert_nested_equal(reference_optimizer.state_dict(), checkpoint["optimizer_state"])
    assert torch.equal(reference_rng, checkpoint["rng_state"]["cpu"])
    assert config == ref_config


@pytest.mark.parametrize("level", ["graph", "atom"])
def test_whole_missing_task_retains_fixed_weight_denominator(level):
    trainer, model, readout, config, _ = make_trainer(level=level, total=1, task_weights=[1., 3.])
    ref_model, ref_readout, ref_config = make_system(level=level, total=1, task_weights=[1., 3.])
    batch = make_batch(level)
    mask = batch.supervision_mask.clone()
    mask[:, 1] = False
    target = batch.targets.clone()
    target[:, 1] = float("nan")
    batch = replace(batch, supervision_mask=mask, targets=target)
    _, _, losses = independent_adamw_oracle(ref_model, ref_readout, ref_config, (batch,), 1)
    result = trainer.fit((batch,), max_updates=1)
    assert result["task_valid_label_exposure"] == [batch.targets.size(0), 0]
    assert_nested_equal(ref_model.state_dict(), model.state_dict())
    assert_nested_equal(ref_readout.state_dict(), readout.state_dict())
    assert losses[0] > 0  # The missing task contributes no labels but its weight remains in denominator.


@pytest.mark.parametrize("level", ["graph", "atom"])
@pytest.mark.parametrize("mode", ["frozen", "finetune"])
def test_adamw_dropout_resume_is_bitexact_against_independent_continuous_oracle(level, mode):
    trainer, model, readout, config, tracker = make_trainer(level=level, mode=mode, total=6, dropout=.35)
    reference_model, reference_readout, reference_config = make_system(level=level, mode=mode, total=6, dropout=.35)
    batches = (make_batch(level), make_batch(level, offset=.4))
    reference_optimizer, reference_rng, _ = independent_adamw_oracle(
        reference_model, reference_readout, reference_config, batches, 6)
    caller_rng = torch.get_rng_state().clone()
    trainer.fit(batches, max_updates=2)
    interrupted = trainer.checkpoint()
    assert interrupted["counters"]["optimizer_updates"] == 2
    restored_model, restored_readout, restored_config = make_system(level=level, mode=mode, total=6, dropout=.35)
    restored_tracker = SyntheticWandbSpy(next_step=interrupted["tracker"]["next_step"])
    restored = DownstreamTrainer(restored_model, restored_readout, restored_config, tracker=restored_tracker)
    restored.load_checkpoint(interrupted, batches)
    result = restored.fit(batches, max_updates=6)
    final = restored.checkpoint()
    assert result["optimizer_updates"] == 6 and result["sample_exposure"] == 12
    assert_nested_equal(reference_model.state_dict(), restored_model.state_dict())
    assert_nested_equal(reference_readout.state_dict(), restored_readout.state_dict())
    assert_nested_equal(reference_optimizer.state_dict(), final["optimizer_state"])
    assert torch.equal(reference_rng, final["rng_state"]["cpu"])
    assert torch.equal(caller_rng, torch.get_rng_state())
    assert restored_tracker.step >= tracker.step
    assert config == restored_config


@pytest.mark.parametrize("level", ["graph", "atom"])
def test_train_affine_loss_uses_raw_targets_and_training_only_scales(level):
    model, readout, config = make_system(level=level, total=2, task_weights=[1., 3.])
    reference_model, reference_readout, reference_config = make_system(level=level, total=2, task_weights=[1., 3.])
    for contract in (config, reference_config):
        contract["normalization"].update(kind="train_affine", means=[4., -3.], scales=[2., .5])
        contract["bindings"]["normalizer_sha256"] = canonical_hash(contract["normalization"])
    trainer = DownstreamTrainer(model, readout, config, tracker=SyntheticWandbSpy())
    batch = make_batch(level, offset=2.)
    _, _, losses = independent_adamw_oracle(reference_model, reference_readout, reference_config, (batch,), 2)
    result = trainer.fit((batch,), max_updates=2)
    assert result["last_step"]["loss"] == pytest.approx(losses[-1], rel=2e-6, abs=1e-7)
    assert_nested_equal(reference_model.state_dict(), model.state_dict())
    assert_nested_equal(reference_readout.state_dict(), readout.state_dict())


@pytest.mark.parametrize("level", ["graph", "atom"])
def test_bce_logits_binary_masked_training_matches_direct_torch(level):
    trainer, model, readout, config, _ = make_trainer(level=level, loss="bce_logits", total=3)
    reference_model, reference_readout, reference_config = make_system(level=level, loss="bce_logits", total=3)
    batch = make_batch(level)
    target = torch.arange(batch.targets.numel()).reshape_as(batch.targets).remainder(2).to(torch.float32)
    mask = batch.supervision_mask.clone()
    mask[0, 0] = False
    target[0, 0] = float("nan")
    batch = replace(batch, targets=target, supervision_mask=mask)
    independent_adamw_oracle(reference_model, reference_readout, reference_config, (batch,), 3)
    trainer.fit((batch,), max_updates=3)
    assert_nested_equal(reference_model.state_dict(), model.state_dict())
    assert_nested_equal(reference_readout.state_dict(), readout.state_dict())


@pytest.mark.parametrize("mutation", ["nan", "inf", "all_missing", "all_missing_later", "binary_fraction", "binary_two"])
def test_invalid_active_labels_do_not_optimize_decay_or_log(mutation):
    binary = mutation.startswith("binary")
    trainer, model, readout, _, tracker = make_trainer(loss="bce_logits" if binary else "mse")
    batch = make_batch()
    target = torch.zeros_like(batch.targets) if binary else batch.targets.clone()
    if mutation in ("all_missing", "all_missing_later"):
        batch = replace(batch, supervision_mask=torch.zeros_like(batch.supervision_mask))
    else:
        target[0, 0] = {"nan": float("nan"), "inf": float("inf"),
                        "binary_fraction": .5, "binary_two": 2.}[mutation]
        batch = replace(batch, targets=target)
    before_model, before_readout = deepcopy(model.state_dict()), deepcopy(readout.state_dict())
    rng = torch.get_rng_state().clone()
    batches = (make_batch(), batch) if mutation == "all_missing_later" else (batch,)
    with pytest.raises(DownstreamTrainingError):
        trainer.fit(batches, max_updates=1)
    assert_nested_equal(before_model, model.state_dict())
    assert_nested_equal(before_readout, readout.state_dict())
    assert tracker.rows == [] and tracker.step == 0
    assert all(parameter.grad is None for parameter in model.parameters())
    assert all(parameter.grad is None for parameter in readout.parameters())
    assert torch.equal(rng, torch.get_rng_state())


@pytest.mark.parametrize("mutation", ["negative", "oov", "padding", "float", "multi_column", "nan_pos", "inf_pos"])
def test_invalid_real_encoder_features_are_rejected_before_optimizer_or_log(mutation):
    trainer, model, readout, _, tracker = make_trainer(real=True)
    batch = make_batch()
    data = batch.encoder_batch.clone()
    if mutation == "negative":
        data.x[0] = -1
    elif mutation == "oov":
        data.x[0] = model.n_atom_types
    elif mutation == "padding":
        data.x[0] = model.pad_elem_index
    elif mutation == "float":
        data.x = data.x.to(torch.float32)
    elif mutation == "multi_column":
        data.x = torch.stack((data.x, data.x), dim=1)
    else:
        data.pos[0, 0] = float("nan") if mutation == "nan_pos" else float("inf")
    batch = replace(batch, encoder_batch=data)
    before_model, before_readout = deepcopy(model.state_dict()), deepcopy(readout.state_dict())
    with pytest.raises(DownstreamTrainingError):
        trainer.fit((batch,), max_updates=1)
    assert_nested_equal(before_model, model.state_dict())
    assert_nested_equal(before_readout, readout.state_dict())
    assert tracker.rows == [] and tracker.step == 0


@pytest.mark.parametrize("mutation", ["duplicate_native", "bad_ptr", "wrong_batch", "role", "mask_type", "target_shape"])
def test_invalid_source_alignment_partition_or_masks_are_rejected(mutation):
    trainer, model, readout, _, tracker = make_trainer()
    batch = make_batch()
    if mutation == "duplicate_native":
        ids = batch.source_atom_ids.clone()
        ids[0] = ids[1]
        batch = replace(batch, source_atom_ids=ids)
    elif mutation in ("bad_ptr", "wrong_batch"):
        data = batch.encoder_batch.clone()
        if mutation == "bad_ptr":
            data.ptr = torch.tensor([0, 1, 5])
        else:
            data.batch = torch.tensor([0, 1, 0, 1, 1])
        batch = replace(batch, encoder_batch=data)
    elif mutation == "role":
        batch = replace(batch, role="validation")
    elif mutation == "mask_type":
        batch = replace(batch, candidate_mask=batch.candidate_mask.long())
    else:
        batch = replace(batch, targets=batch.targets[:-1])
    before_model, before_readout = deepcopy(model.state_dict()), deepcopy(readout.state_dict())
    with pytest.raises(DownstreamTrainingError):
        trainer.fit((batch,), max_updates=1)
    assert_nested_equal(before_model, model.state_dict())
    assert_nested_equal(before_readout, readout.state_dict())
    assert tracker.rows == []


def test_constructor_fit_and_checkpoint_preserve_caller_rngs_and_batch_objects():
    model, readout, config = make_system(dropout=.35)
    tracker = SyntheticWandbSpy()
    batch = make_batch()
    before_batch = deepcopy(batch)
    caller_rng = torch.get_rng_state().clone()
    numpy_rng = deepcopy(np.random.get_state())
    python_rng = random.getstate()
    trainer = DownstreamTrainer(model, readout, config, tracker=tracker)
    trainer.fit((batch,), max_updates=2)
    trainer.checkpoint()
    assert torch.equal(caller_rng, torch.get_rng_state())
    after_numpy = np.random.get_state()
    assert numpy_rng[0] == after_numpy[0] and np.array_equal(numpy_rng[1], after_numpy[1])
    assert numpy_rng[2:] == after_numpy[2:]
    assert random.getstate() == python_rng
    assert set(batch.encoder_batch.keys()) == set(before_batch.encoder_batch.keys())
    for name in batch.encoder_batch.keys():
        assert_nested_equal(batch.encoder_batch[name], before_batch.encoder_batch[name])
    for name in ("sample_ids", "source_atom_ids", "targets", "candidate_mask", "supervision_mask", "role"):
        assert_nested_equal(getattr(batch, name), getattr(before_batch, name))


@pytest.mark.parametrize("tracker_kind", ["lambda", "disabled", "missing_identity", "bad_cursor"])
def test_tracker_requires_identified_active_wandb_compatible_run(tracker_kind):
    model, readout, config = make_system()
    tracker = SyntheticWandbSpy()
    if tracker_kind == "lambda":
        tracker = lambda *args, **kwargs: None
    elif tracker_kind == "disabled":
        tracker.settings.mode = "disabled"
    elif tracker_kind == "missing_identity":
        tracker.id = ""
    else:
        tracker.step = True
    with pytest.raises(DownstreamTrainingError):
        DownstreamTrainer(model, readout, config, tracker=tracker)


def test_tracker_failure_records_actual_update_but_never_claims_endpoint_or_replays():
    model, readout, config = make_system(total=3)
    tracker = SyntheticWandbSpy(fail_at=0)
    trainer = DownstreamTrainer(model, readout, config, tracker=tracker)
    batch = make_batch()
    before = deepcopy(readout.state_dict())
    with pytest.raises(DownstreamTrainingError, match="(?i)track"):
        trainer.fit((batch,), max_updates=3)
    failed = trainer.checkpoint()
    assert failed["counters"]["optimizer_updates"] == 1
    assert failed["counters"]["sample_exposure"] == 2
    assert any(not torch.equal(v, readout.state_dict()[k]) for k, v in before.items() if isinstance(v, torch.Tensor))
    assert failed["tracker"]["next_step"] == 0
    fresh_model, fresh_readout, fresh_config = make_system(total=3)
    fresh = DownstreamTrainer(fresh_model, fresh_readout, fresh_config, tracker=SyntheticWandbSpy())
    fresh_before = deepcopy(fresh_model.state_dict()), deepcopy(fresh_readout.state_dict())
    with pytest.raises(DownstreamTrainingError):
        fresh.load_checkpoint(failed, (batch,))
    assert_nested_equal(fresh_before[0], fresh_model.state_dict())
    assert_nested_equal(fresh_before[1], fresh_readout.state_dict())


def test_fixed_endpoint_is_last_update_not_a_posthoc_best_training_step():
    trainer, _, readout, _, tracker = make_trainer(total=3)
    batches = (make_batch(offset=0.), make_batch(offset=20.))
    first = trainer.fit(batches, max_updates=1)
    intermediate = deepcopy(readout.state_dict())
    final = trainer.fit(batches, max_updates=3)
    assert first["optimizer_updates"] == 1 and final["optimizer_updates"] == 3
    assert final["last_step"]["optimizer_update"] == 3
    assert final["last_step"]["batch_index"] == 0  # Fixed cycle at actual optimizer update 2.
    assert any(not torch.equal(v, readout.state_dict()[k]) for k, v in intermediate.items() if isinstance(v, torch.Tensor))
    assert trainer.checkpoint()["counters"]["optimizer_updates"] == 3
    assert len(tracker.rows) == 3


def reseal_checkpoint(payload):
    payload["checkpoint_content_sha256"] = checkpoint_content_sha256(payload)
    return payload


def partial_checkpoint_fixture():
    trainer, _, _, _, _ = make_trainer(total=4, dropout=.3)
    batches = (make_batch(), make_batch(offset=.2))
    trainer.fit(batches, max_updates=2)
    checkpoint = trainer.checkpoint()
    return checkpoint, batches


def live_resume_fixture(checkpoint):
    model, readout, config = make_system(total=4, dropout=.3)
    tracker = SyntheticWandbSpy(next_step=checkpoint["tracker"]["next_step"])
    trainer = DownstreamTrainer(model, readout, config, tracker=tracker)
    return trainer, model, readout, tracker


def snapshot_trainer_state(trainer):
    # Inspect live state for rejection atomicity; no loader/step implementation
    # is reused as an optimization oracle. A fresh receiver is not yet bound to
    # a sequence and therefore intentionally cannot produce a checkpoint.
    names = ("config", "rng_state", "optimizer_updates", "sample_exposure", "atom_exposure",
             "task_valid_label_exposure", "total_wall_seconds", "attempted_forward_steps",
             "forward_sample_exposure", "forward_atom_exposure", "train_sequence_sha256",
             "status", "last_step", "_tracker", "_specs")
    return {"optimizer": deepcopy(trainer.optimizer.state_dict()),
            "metadata": {name: deepcopy(getattr(trainer, name)) for name in names}}


@pytest.mark.parametrize("mutation", [
    "config", "source", "sequence", "cursor", "initial_encoder", "initial_readout",
    "late_model_shape", "late_model_nan", "readout_contract", "optimizer_moment_shape",
    "optimizer_moment_nan", "optimizer_step", "optimizer_step_rewind", "optimizer_missing_state", "optimizer_empty_state",
    "optimizer_backbone_missing_state", "optimizer_backbone_step_rewind", "optimizer_group", "rng", "tracker_cursor",
])
def test_resealed_resume_tampering_is_rejected_atomically(mutation):
    payload, batches = partial_checkpoint_fixture()
    trainer, model, readout, tracker = live_resume_fixture(payload)
    before = snapshot_trainer_state(trainer)
    model_before, readout_before = deepcopy(model.state_dict()), deepcopy(readout.state_dict())
    parameter_grad_modes = [(p.requires_grad, None if p.grad is None else p.grad.clone())
                            for p in list(model.parameters()) + list(readout.parameters())]
    module_modes = [(name, module.training) for name, module in model.named_modules()]
    caller_rng = torch.get_rng_state().clone()
    broken = deepcopy(payload)
    if mutation == "config":
        broken["config"]["optimizer"]["lr"] *= 2
        broken["config_sha256"] = canonical_hash(broken["config"])
    elif mutation == "source":
        broken["config"]["bindings"]["source_sha256"] = "e" * 64
        broken["config_sha256"] = canonical_hash(broken["config"])
    elif mutation == "sequence":
        broken["train_sequence_sha256"] = "e" * 64
    elif mutation == "cursor":
        broken["counters"]["optimizer_updates"] += 1
    elif mutation in ("initial_encoder", "initial_readout"):
        broken[f"{mutation}_sha256"] = "e" * 64
    elif mutation.startswith("late_model"):
        key = [k for k, v in broken["model_state"].items() if isinstance(v, torch.Tensor) and v.is_floating_point()][-1]
        if mutation.endswith("shape"):
            broken["model_state"][key] = torch.zeros(123, dtype=broken["model_state"][key].dtype)
        else:
            broken["model_state"][key].reshape(-1)[0] = float("nan")
    elif mutation == "readout_contract":
        broken["readout_state"]["_extra_state"]["source_map_contract"]["index_base"] = 1
    elif mutation.startswith("optimizer_moment"):
        state = next(iter(broken["optimizer_state"]["state"].values()))
        if mutation.endswith("shape"):
            state["exp_avg"] = torch.zeros(123)
        else:
            state["exp_avg"].reshape(-1)[0] = float("nan")
    elif mutation in ("optimizer_step", "optimizer_step_rewind"):
        states = broken["optimizer_state"]["state"]
        # Last ID is the mandatory readout output bias, used at every step.
        states[max(states)]["step"] += (1 if mutation == "optimizer_step" else -1)
    elif mutation == "optimizer_missing_state":
        states = broken["optimizer_state"]["state"]
        states.pop(max(states))
    elif mutation == "optimizer_empty_state":
        broken["optimizer_state"]["state"] = {}
    elif mutation == "optimizer_backbone_missing_state":
        states = broken["optimizer_state"]["state"]
        states.pop(min(states))  # First selected parameter is the connected H0 Linear weight.
    elif mutation == "optimizer_backbone_step_rewind":
        states = broken["optimizer_state"]["state"]
        states[min(states)]["step"] -= 1  # H0 AdamW history must not silently rewind from 2 to 1.
    elif mutation == "optimizer_group":
        broken["optimizer_state"]["param_groups"][0]["lr"] *= 2
    elif mutation == "rng":
        broken["rng_state"]["cpu"] = torch.zeros(1, dtype=torch.uint8)
    else:
        broken["tracker"]["next_step"] += 1
    reseal_checkpoint(broken)
    with pytest.raises(DownstreamTrainingError):
        trainer.load_checkpoint(broken, batches)
    assert_nested_equal(model_before, model.state_dict())
    assert_nested_equal(readout_before, readout.state_dict())
    assert_nested_equal(before, snapshot_trainer_state(trainer))
    assert module_modes == [(name, module.training) for name, module in model.named_modules()]
    for parameter, (requires_grad, gradient) in zip(list(model.parameters()) + list(readout.parameters()), parameter_grad_modes):
        assert parameter.requires_grad == requires_grad
        if gradient is None:
            assert parameter.grad is None
        else:
            assert torch.equal(gradient, parameter.grad)
    assert torch.equal(caller_rng, torch.get_rng_state())
    assert tracker.rows == []


@pytest.mark.parametrize("changed_field", ["targets", "source_atom_ids", "sample_ids", "candidate_mask", "supervision_mask", "coordinates"])
def test_resume_rejects_sequence_content_changes_without_live_mutation(changed_field):
    payload, batches = partial_checkpoint_fixture()
    trainer, model, readout, _ = live_resume_fixture(payload)
    batch = deepcopy(batches[0])
    if changed_field == "sample_ids":
        batch = replace(batch, sample_ids=("different-synthetic-A", "different-synthetic-B"))
    elif changed_field == "source_atom_ids":
        ids = batch.source_atom_ids.clone()
        ids[:2] = ids[:2].flip(0)  # Another valid, complete source permutation.
        batch = replace(batch, source_atom_ids=ids)
    elif changed_field == "coordinates":
        data = batch.encoder_batch.clone()
        data.pos[0, 0] += .1
        batch = replace(batch, encoder_batch=data)
    else:
        value = getattr(batch, changed_field).clone()
        if value.dtype == torch.bool:
            value[0, 0] = False
        else:
            value[0, 0] += .1
        batch = replace(batch, **{changed_field: value})
    before_model, before_readout = deepcopy(model.state_dict()), deepcopy(readout.state_dict())
    with pytest.raises(DownstreamTrainingError):
        trainer.load_checkpoint(payload, (batch, batches[1]))
    assert_nested_equal(before_model, model.state_dict())
    assert_nested_equal(before_readout, readout.state_dict())


def test_checkpoint_is_detached_from_live_state_and_caller_payload_is_unchanged():
    payload, batches = partial_checkpoint_fixture()
    trainer, model, readout, _ = live_resume_fixture(payload)
    original = deepcopy(payload)
    trainer.load_checkpoint(payload, batches)
    assert_nested_equal(original, payload)
    checkpoint = trainer.checkpoint()
    tensor_key = next(key for key, value in checkpoint["model_state"].items() if isinstance(value, torch.Tensor) and value.is_floating_point())
    checkpoint["model_state"][tensor_key].add_(100)
    checkpoint["config"]["tasks"][0] = "caller-mutated-copy"
    assert not torch.equal(checkpoint["model_state"][tensor_key], model.state_dict()[tensor_key])
    assert trainer.checkpoint()["config"]["tasks"][0] != "caller-mutated-copy"
    trainer.fit(batches, max_updates=3)
    assert_nested_equal(original, payload)  # AdamW moments must not alias the supplied checkpoint.


def test_cumulative_wall_budget_is_preserved_across_resume(monkeypatch):
    import phychem_mfm.phase1.downstream_training as training_module

    payload, batches = partial_checkpoint_fixture()
    # A valid declared prior duration near the original cap. This pure metadata
    # fixture does not claim that the toy run actually took a minute.
    payload["counters"]["total_wall_seconds"] = 59.9
    reseal_checkpoint(payload)
    trainer, model, readout, tracker = live_resume_fixture(payload)
    trainer.load_checkpoint(payload, batches)
    assert trainer.checkpoint()["counters"]["total_wall_seconds"] == 59.9
    before_model, before_readout = deepcopy(model.state_dict()), deepcopy(readout.state_dict())
    clock = [0.0]

    def ticking_clock():
        clock[0] += .25
        return clock[0]

    monkeypatch.setattr(training_module.time, "monotonic", ticking_clock)
    with pytest.raises(DownstreamTrainingError, match="wall"):
        trainer.fit(batches, max_updates=4)
    stopped = trainer.checkpoint()
    assert stopped["counters"]["optimizer_updates"] == 2
    assert stopped["counters"]["total_wall_seconds"] >= 60.0
    assert_nested_equal(before_model, model.state_dict())
    assert_nested_equal(before_readout, readout.state_dict())
    assert tracker.rows == []


@pytest.mark.parametrize("bad_target", [-1, True, 5])
def test_update_target_cannot_change_declared_budget_or_rewind(bad_target):
    trainer, model, readout, _, tracker = make_trainer(total=4)
    before_model, before_readout = deepcopy(model.state_dict()), deepcopy(readout.state_dict())
    with pytest.raises(DownstreamTrainingError):
        trainer.fit((make_batch(),), max_updates=bad_target)
    assert_nested_equal(before_model, model.state_dict())
    assert_nested_equal(before_readout, readout.state_dict())
    assert tracker.rows == []


def test_completed_endpoint_can_be_restored_for_view_but_never_extended():
    trainer, model, readout, _, tracker = make_trainer(total=2)
    batches = (make_batch(),)
    result = trainer.fit(batches, max_updates=2)
    assert result["status"] == "complete"
    complete = trainer.checkpoint()
    before_model, before_readout = deepcopy(model.state_dict()), deepcopy(readout.state_dict())
    before_logs = deepcopy(tracker.rows)
    with pytest.raises(DownstreamTrainingError):
        trainer.fit(batches, max_updates=3)
    assert_nested_equal(before_model, model.state_dict())
    assert_nested_equal(before_readout, readout.state_dict())
    assert tracker.rows == before_logs
    fresh_model, fresh_readout, fresh_config = make_system(total=2)
    fresh_tracker = SyntheticWandbSpy(next_step=complete["tracker"]["next_step"])
    fresh = DownstreamTrainer(fresh_model, fresh_readout, fresh_config, tracker=fresh_tracker)
    fresh.load_checkpoint(complete, batches)
    viewed = fresh.fit(batches, max_updates=2)
    assert viewed["status"] == "complete" and viewed["optimizer_updates"] == 2
    assert fresh_tracker.rows == []
    assert_nested_equal(before_model, fresh_model.state_dict())
    assert_nested_equal(before_readout, fresh_readout.state_dict())
    with pytest.raises(DownstreamTrainingError):
        fresh.fit(batches, max_updates=3)


def test_finite_stationary_loss_with_connected_zero_gradients_is_a_valid_update():
    model, readout, config = make_system(total=2, mode="finetune")
    with torch.no_grad():
        for parameter in list(model.backbone.parameters()) + list(readout.parameters()):
            parameter.zero_()
    config["bindings"]["initial_encoder_sha256"] = backbone_state_hash(model)
    trainer = DownstreamTrainer(model, readout, config, tracker=SyntheticWandbSpy())
    batch = make_batch()
    batch = replace(batch, targets=torch.zeros_like(batch.targets))
    initial_backbone = deepcopy(model.backbone.state_dict())
    result = trainer.fit((batch,), max_updates=2)
    assert result["status"] == "complete" and result["optimizer_updates"] == 2
    assert result["last_step"]["loss"] == 0.0
    assert result["last_step"]["gradient_norm"] == 0.0
    assert result["task_valid_label_exposure"] == [10, 10]
    assert all(parameter.grad is not None for parameter in model.backbone.parameters())
    assert all(bool((parameter.grad == 0).all()) for parameter in model.backbone.parameters())
    assert_nested_equal(initial_backbone, model.backbone.state_dict())
