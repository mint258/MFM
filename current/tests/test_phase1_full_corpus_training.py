"""Synthetic compact LMDB -> real tiny SharedBackbone -> optimization/resume.

No real corpus labels, final targets, GPU capacity or frozen formal experiment
are claimed by these tests. Independent known-data clocks and bitwise training
trajectories exercise the actual controller/model/AdamW, not copied reports.
"""
from copy import deepcopy
import hashlib
import json
import math
import time

import pytest
import torch

from conftest import small_config
from test_phase1_full_corpus_loader import write_fixture, open_index, dataset, seal
from phychem_mfm.factory import build_model
from phychem_mfm.phase1.downstream_training import checkpoint_content_sha256
from phychem_mfm.phase1.formal_gate import canonical_sha256 as canonical_hash
from phychem_mfm.phase1.formal_runtime import backbone_state_hash
from phychem_mfm.phase1.full_corpus_loader import (
    BlockAtomBatchSampler, collate_native_views, make_prefetch_loader, close_prefetch_iterator)
from phychem_mfm.phase1.full_corpus_training import BaseExposureCosine, FullCorpusTrainer, FullCorpusTrainingError
from phychem_mfm.phase1.objectives import GROUP_TASKS
from phychem_mfm.training.full_corpus_normalization import (
    full_train_regression_normalization, validate_full_train_regression_normalization,
    validate_full_train_moment_artifact, ESTIMATOR, STREAMS)


class OfflineSpy:
    """Identified synchronous test spy; not evidence of a real W&B backend."""
    mode, disabled = "offline", False
    def __init__(self, name):
        self.id, self.path, self.step = name, "tests/synthetic/" + name, 0
        self.rows = []
    def log(self, payload, *, step, commit):
        assert commit is True and step == self.step
        self.rows.append(deepcopy(payload))
        self.step += 1


def normalization(manifest, atoms):
    n = manifest["view"]["rows"]
    moments = {name: {"count": atoms if name in ("charge", "estate_index") else n,
                      "mean": 0.0, "m2": float(atoms if name in ("charge", "estate_index") else n)} for name in STREAMS}
    binding = {"schema_version": "phase1_full_train_normalization_binding_v1", "role": "train",
               "train_only": True, "full_coverage": True,
               "estimator": "phase1_train_only_fp64_chan_population_moments_v1",
               "train_manifest_sha256": manifest["content_sha256"],
               "train_view_sha256": manifest["view"]["sha256"],
               "base_index_sha256": manifest["base_index"]["sha256"],
               "quality_artifact_sha256": manifest["quality_and_identity_artifact_sha256"],
               "moments_file_sha256": "a" * 64, "retained_train_records": n,
               "observed_train_records": n, "observed_train_atoms": atoms}
    return full_train_regression_normalization(moments, binding)


def fixture(tmp_path, *, zero_labels=False, dropout=.1, name="fresh", shared_manifest=None):
    if shared_manifest is None:
        tmp_path.mkdir()
        def mutate(record):
            if zero_labels:
                record.energy_mask[:] = False
                record.charge_mask[:] = False
        manifest, records = write_fixture(tmp_path, mutate_record=mutate)
    else:
        manifest, records = shared_manifest
    index = open_index(manifest)
    atoms = sum(index.ref(i).native_n_atoms for i in range(len(index)))
    norm = normalization(manifest, atoms)
    model_config = small_config("light")
    model_config["backbone"].update(n_atom_types=119, dim=8, heads=2, layers=1,
                                      dropout=dropout, activation_checkpointing=True)
    model_config["expert"].update(heads=2, real_layers=2, internal_layers=0)
    model_config["head"].update(profile="phase1", geometry_head="residual",
                               regression_output_normalization=norm)
    torch.manual_seed(31)
    model = build_model(model_config)
    sampler = BlockAtomBatchSampler(index, seed=0, block_size=4, max_molecules=2,
                max_native_atoms=128, atom_bucket_width=16, max_padded_cost=100000, padded_cost_multiplier=3)
    native = dataset(index)
    batches = [collate_native_views([native[i] for i in indices]) for indices in sampler]
    tasks = {task for group in GROUP_TASKS.values() for task in group}
    config = {"schema_version": "phase1_full_corpus_training_v1", "variant": "P", "seed": 0,
        "device": "cpu", "epochs": 1, "views_per_base": 3,
        "optimizer": {"lr": .0003, "weight_decay": .01, "betas": [.9, .95]},
        "schedule": {"warmup_base_exposures": 2, "min_lr_ratio": .05}, "loss": {}, "loss_policy": {},
        "dynamic_loss": {"calibration_observations": 2, "balance_interval": 2},
        "shared_parameter_names": ["out_norm.weight", "out_norm.bias"], "gradient_clip_norm": 1.0,
        "metric_interval": 3, "bindings": {"protocol_sha256": "b" * 64, "source_sha256": "c" * 64,
        "train_manifest_sha256": manifest["content_sha256"], "routine_validation_manifest_sha256": "d" * 64,
        "full_validation_manifest_sha256": "e" * 64, "normalization_contract_sha256": norm["contract_sha256"],
        "initial_encoder_sha256": backbone_state_hash(model), "environment": {"kind": "synthetic_cpu"}},
        "validation": {"criterion": "fixed_standardized_leaf_macro_v1", "every_base_exposures": 100,
                       "task_scales": {task: 1.0 for task in tasks}},
        "caps": {"segment_wall_seconds": 30., "finalization_reserve_seconds": 1.}}
    tracker = OfflineSpy(name)
    trainer = FullCorpusTrainer(model, sampler, config, tracker=tracker)
    return trainer, batches, tracker, (manifest, records)


def assert_same_tree(left, right):
    if isinstance(left, torch.Tensor):
        assert isinstance(right, torch.Tensor) and left.dtype == right.dtype and left.shape == right.shape
        assert torch.equal(left, right)
    elif isinstance(left, dict):
        assert left.keys() == right.keys()
        for key in left:
            assert_same_tree(left[key], right[key])
    elif isinstance(left, (tuple, list)):
        assert type(left) is type(right) and len(left) == len(right)
        for a, b in zip(left, right):
            assert_same_tree(a, b)
    else:
        assert left == right


def test_variable_size_base_exposure_lr_has_a_hand_known_cosine_clock():
    parameter = torch.nn.Parameter(torch.tensor(1.))
    optimizer = torch.optim.AdamW([parameter], lr=2.)
    schedule = BaseExposureCosine(optimizer, total_base_exposures=10, warmup_base_exposures=4, min_lr_ratio=.2)
    assert optimizer.param_groups[0]["lr"] == .5
    schedule.set_consumed(3)
    assert optimizer.param_groups[0]["lr"] == 2.
    schedule.set_consumed(7)
    assert optimizer.param_groups[0]["lr"] == pytest.approx(1.2)
    schedule.set_consumed(10)
    assert optimizer.param_groups[0]["lr"] == pytest.approx(.4)
    assert schedule.state_dict()["consumed_base_exposures"] == 10


def test_full_train_moments_are_population_std_and_do_not_materialize_sample_indices(tmp_path):
    trainer, _, _, (manifest, _) = fixture(tmp_path / "fixture")
    contract = trainer.model.head_config["regression_output_normalization"]
    moments = deepcopy(contract["full_training_moments"])
    moments["energy"] = {"count": 5, "mean": 3., "m2": 20.}
    binding = {k: v for k, v in contract["training_provenance"].items() if k not in {
        "valid_label_counts", "moment_snapshot_sha256", "statistics_hash", "provenance_hash", "sampled_logical_indices_materialized"}}
    rebuilt = full_train_regression_normalization(moments, binding)
    assert rebuilt["targets"]["energy"] == {"count": 5, "mean": 3., "std": 2.}
    assert "sampled_logical_indices" not in rebuilt["training_provenance"]
    assert rebuilt["training_provenance"]["full_coverage"] is True
    assert validate_full_train_regression_normalization(rebuilt) == rebuilt


@pytest.mark.parametrize("change", ("self_seal", "estimator", "train_only", "records", "atoms", "moments"))
def test_sufficient_statistics_artifact_seal_role_and_complete_counts_are_checked(tmp_path, change):
    trainer, _, _, _ = fixture(tmp_path / "fixture")
    contract = trainer.model.head_config["regression_output_normalization"]
    provenance = contract["training_provenance"]
    artifact = {"schema_version": ESTIMATOR, "train_only": True,
                "observed_train_records": provenance["observed_train_records"],
                "observed_train_atoms": provenance["observed_train_atoms"],
                "moments": deepcopy(contract["full_training_moments"])}
    def reseal(value):
        unsigned = {key: item for key, item in value.items() if key != "statistics_sha256"}
        value["statistics_sha256"] = hashlib.sha256(json.dumps(unsigned, sort_keys=True,
            separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("ascii")).hexdigest()
    reseal(artifact)
    validate_full_train_moment_artifact(contract, artifact)
    if change == "self_seal": artifact["statistics_sha256"] = "0" * 64
    elif change == "estimator": artifact["schema_version"] = "foreign_estimator"
    elif change == "train_only": artifact["train_only"] = False
    elif change == "records": artifact["observed_train_records"] += 1
    elif change == "atoms": artifact["observed_train_atoms"] += 1
    else: artifact["moments"]["energy"]["mean"] += 1
    if change != "self_seal": reseal(artifact)
    with pytest.raises(ValueError):
        validate_full_train_moment_artifact(contract, artifact)


@pytest.mark.parametrize("field", ("train_view_sha256", "base_index_sha256", "quality_artifact_sha256"))
def test_resealed_affine_contract_cannot_name_other_actual_training_compact_bytes(tmp_path, field):
    with torch.random.fork_rng(devices=[]):
        trainer, _, _, _ = fixture(tmp_path / "fixture")
        contract = trainer.model.head_config["regression_output_normalization"]
        binding = {key: value for key, value in contract["training_provenance"].items() if key not in {
            "valid_label_counts", "moment_snapshot_sha256", "statistics_hash", "provenance_hash", "sampled_logical_indices_materialized"}}
        binding[field] = "f" * 64
        forged = full_train_regression_normalization(contract["full_training_moments"], binding)
        snapshot = trainer.model.config_dict()
        recipe = {"architecture": {"preset": "shared_light", "task_route_per_task": snapshot["task_route_per_task"]},
                  "backbone": deepcopy(snapshot["backbone_config"]),
                  "expert": deepcopy(snapshot["expert_config"]), "head": deepcopy(snapshot["head_config"])}
        recipe["head"]["regression_output_normalization"] = forged
        model = build_model(recipe)
        cfg = deepcopy(trainer.config)
        cfg["bindings"]["normalization_contract_sha256"] = forged["contract_sha256"]
        cfg["bindings"]["initial_encoder_sha256"] = backbone_state_hash(model)
        spy = OfflineSpy("receiver")
        with pytest.raises(FullCorpusTrainingError, match="compact view/index/quality bytes"):
            FullCorpusTrainer(model, trainer.sampler, cfg, tracker=spy)
        assert spy.step == 0 and trainer.sampler.samples_consumed == 0


def test_real_five_native_records_partial_batch_are_consumed_once_with_three_views(tmp_path):
    with torch.random.fork_rng(devices=[]):
        trainer, batches, tracker, _ = fixture(tmp_path / "fixture")
        before = backbone_state_hash(trainer.model)
        actual = []
        for batch in batches:
            actual.extend(batch.logical_indices)
            trainer._consume(batch)
        assert sorted(actual) == [0, 1, 2, 3, 4] and len(actual) == len(set(actual))
        assert any(len(batch.logical_indices) == 1 for batch in batches)
        assert trainer.counters["consumed_base_exposures"] == 5
        assert trainer.counters["consumed_view_exposures"] == 15
        assert trainer.counters["optimizer_updates"] == len(batches)
        assert trainer.controller.next_update == len(batches)
        assert trainer.scheduler.consumed == 5 and trainer.sampler.samples_consumed == 5
        assert backbone_state_hash(trainer.model) != before
        assert tracker.step == len(batches)
        for row in tracker.rows:
            seal = row.pop("tracking/payload_sha256")
            assert seal == canonical_hash(row)


def test_zero_label_batches_keep_full_coverage_without_adamw_or_controller_updates(tmp_path):
    with torch.random.fork_rng(devices=[]):
        trainer, batches, tracker, _ = fixture(tmp_path / "fixture", zero_labels=True)
        model, controller = deepcopy(trainer.model.state_dict()), trainer.controller.state_dict()
        for batch in batches:
            trainer._consume(batch)
        assert_same_tree(model, trainer.model.state_dict())
        assert trainer.controller.state_dict() == controller
        assert trainer.optimizer.state_dict()["state"] == {}
        assert trainer.counters["optimizer_updates"] == 0
        assert trainer.counters["zero_label_batches"] == len(batches)
        assert trainer.counters["consumed_base_exposures"] == trainer.scheduler.consumed == 5
        assert trainer.counters["consumed_view_exposures"] == 15
        assert all(row["train/zero_label_batch"] == 1 for row in tracker.rows)


def test_true_adamw_dropout_resume_equals_uninterrupted_model_moments_controller_and_rng(tmp_path):
    with torch.random.fork_rng(devices=[]):
        reference, batches, _, data = fixture(tmp_path / "fixture", name="reference")
        initial_rng = torch.get_rng_state().clone()
        for batch in batches:
            reference._consume(batch)
        expected_model = deepcopy(reference.model.state_dict())
        expected_optimizer = deepcopy(reference.optimizer.state_dict())
        expected_controller, expected_rng = reference.controller.state_dict(), torch.get_rng_state().clone()
        interrupted, same, _, _ = fixture(tmp_path / "unused", name="interrupted", shared_manifest=data)
        torch.set_rng_state(initial_rng)
        interrupted._consume(same[0])
        checkpoint = interrupted.checkpoint()
        resumed, _, spy, _ = fixture(tmp_path / "unused2", name="resumed", shared_manifest=data)
        resumed.load_checkpoint(checkpoint, checkpoint_file_sha256="f" * 64)
        for batch in same[1:]:
            resumed._consume(batch)
        assert_same_tree(expected_model, resumed.model.state_dict())
        assert_same_tree(expected_optimizer, resumed.optimizer.state_dict())
        assert resumed.controller.state_dict() == expected_controller
        assert torch.equal(torch.get_rng_state(), expected_rng)
        assert resumed.sampler.state_dict() == reference.sampler.state_dict()
        assert resumed.scheduler.state_dict() == reference.scheduler.state_dict()
        assert resumed.tracking["parent_run_id"] == "interrupted"
        assert spy.id != "interrupted" and spy.step == len(batches) - 1


def test_partial_spawn_prefetch_closes_workers_and_resumes_only_committed_dropout_controller_updates(tmp_path):
    """Real worker queues may read ahead; their reads are never committed exposure."""
    class CapturedLoader:
        def __init__(self, actual):
            self.actual, self.iterator, self.workers = actual, None, []
        def __iter__(self):
            self.iterator = iter(self.actual)
            self.workers = list(self.iterator._workers)
            return self.iterator
    def prefetch(trainer):
        return CapturedLoader(make_prefetch_loader(dataset(trainer.sampler.index), trainer.sampler,
            num_workers=2, prefetch_factor=2, pin_memory=False, persistent_workers=False,
            worker_timeout_seconds=30.))
    with torch.random.fork_rng(devices=[]):
        reference, _, _, data = fixture(tmp_path / "fixture", name="reference")
        initial_rng = torch.get_rng_state().clone()
        whole = prefetch(reference)
        iterator = iter(whole)
        try:
            for batch in iterator:
                reference._consume(batch)
        finally:
            close_prefetch_iterator(iterator)
        assert all(not worker.is_alive() for worker in whole.workers)
        expected_model = deepcopy(reference.model.state_dict())
        expected_optimizer = deepcopy(reference.optimizer.state_dict())
        expected_controller = reference.controller.state_dict()
        expected_rng = torch.get_rng_state().clone()

        interrupted, _, _, _ = fixture(tmp_path / "unused", name="interrupted", shared_manifest=data)
        interrupted.next_validation_exposure = 100
        torch.set_rng_state(initial_rng)
        partial = prefetch(interrupted)
        remaining = iter((20., 20., 0.))  # outer guard, first real batch, next prefetched batch
        interrupted._remaining = lambda: next(remaining)
        def no_validation(scope):
            raise AssertionError("The partial training segment has no validation due")
        result = interrupted.fit(partial, validation_factory=no_validation)
        assert result["status"] == "partial" and interrupted.counters["consumed_batches"] == 1
        assert interrupted.sampler.samples_consumed < len(interrupted.sampler.index)
        assert all(not worker.is_alive() for worker in partial.workers)
        payload = interrupted.checkpoint()
        assert payload["sampler_state"]["samples_consumed"] == interrupted.counters["consumed_base_exposures"]

        resumed, _, _, _ = fixture(tmp_path / "unused2", name="resumed", shared_manifest=data)
        resumed.load_checkpoint(payload, checkpoint_file_sha256="f" * 64)
        rest = prefetch(resumed)
        iterator = iter(rest)
        try:
            for batch in iterator:
                resumed._consume(batch)
        finally:
            close_prefetch_iterator(iterator)
        assert all(not worker.is_alive() for worker in rest.workers)
        assert_same_tree(expected_model, resumed.model.state_dict())
        assert_same_tree(expected_optimizer, resumed.optimizer.state_dict())
        assert resumed.controller.state_dict() == expected_controller
        assert resumed.sampler.state_dict() == reference.sampler.state_dict()
        assert resumed.scheduler.state_dict() == reference.scheduler.state_dict()
        assert resumed.counters["consumed_base_exposures"] == 5
        assert torch.equal(torch.get_rng_state(), expected_rng)


@pytest.mark.parametrize("change", ("late_shape", "missing_moment", "rewind_step", "rng", "controller", "cursor", "source", "premature_complete"))
def test_resealed_late_resume_errors_leave_live_weights_optimizer_rng_and_cursor_unchanged(tmp_path, change):
    with torch.random.fork_rng(devices=[]):
        trained, batches, _, data = fixture(tmp_path / "fixture", name="trained")
        trained._consume(batches[0])
        payload = trained.checkpoint()
        receiver, _, _, _ = fixture(tmp_path / "unused", name="receiver", shared_manifest=data)
        if change in {"late_shape", "missing_moment", "rewind_step"}:
            ident = next(iter(payload["optimizer_state"]["state"]))
            if change == "late_shape": payload["optimizer_state"]["state"][ident]["exp_avg"] = torch.zeros(1)
            elif change == "missing_moment": del payload["optimizer_state"]["state"][ident]
            else: payload["optimizer_state"]["state"][ident]["step"] -= 1
        elif change == "rng": payload["rng_state"]["cpu"] = torch.zeros(3, dtype=torch.uint8)
        elif change == "controller": payload["controller_state"]["next_update"] += 1
        elif change == "cursor": payload["counters"]["consumed_base_exposures"] += 1
        elif change == "premature_complete": payload["status"] = "complete"
        else: payload["config"]["bindings"]["source_sha256"] = "0" * 64
        payload["checkpoint_content_sha256"] = checkpoint_content_sha256(payload)
        state, opt, cursor = deepcopy(receiver.model.state_dict()), deepcopy(receiver.optimizer.state_dict()), receiver.sampler.state_dict()
        rng, control, counters = torch.get_rng_state().clone(), receiver.controller.state_dict(), deepcopy(receiver.counters)
        with pytest.raises((FullCorpusTrainingError, ValueError, RuntimeError)):
            receiver.load_checkpoint(payload, checkpoint_file_sha256="f" * 64)
        assert_same_tree(state, receiver.model.state_dict())
        assert_same_tree(opt, receiver.optimizer.state_dict())
        assert receiver.sampler.state_dict() == cursor and receiver.controller.state_dict() == control
        assert receiver.counters == counters and torch.equal(torch.get_rng_state(), rng)


def test_actual_probe_is_logged_even_when_metric_interval_is_not_a_probe_multiple(tmp_path):
    with torch.random.fork_rng(devices=[]):
        trainer, batches, tracker, _ = fixture(tmp_path / "fixture")
        for batch in batches:
            trainer._consume(batch)
        # Third real update has index2: interval2 probe, metric cadence3.
        last = tracker.rows[-1]
        assert last["balance/probe_performed"] == 1
        assert "balance/scale/energy" in last and "balance/observations/charge" in last
        assert "balance/measured_group_gradient_norms/P" in last


def validation_fixture(trainer, data):
    manifest, records = data
    view = deepcopy(manifest)
    view["view"]["role"] = "validation"
    view = seal(view)
    trainer.config["bindings"]["routine_validation_manifest_sha256"] = view["content_sha256"]
    index = open_index(view)
    sampler = BlockAtomBatchSampler(index, seed=19, block_size=4, max_molecules=2,
                max_native_atoms=128, atom_bucket_width=16, max_padded_cost=100000, padded_cost_multiplier=3)
    native = dataset(index)
    class LazyNativeBatches:
        def __iter__(self):
            for indices in sampler:
                yield collate_native_views([native[i] for i in indices])
    return sampler, LazyNativeBatches(), records


def test_validation_fixed_known_huber_macro_uses_observed_counts_and_keeps_controller_rng_modes(tmp_path):
    with torch.random.fork_rng(devices=[]):
        trainer, _, _, data = fixture(tmp_path / "fixture")
        with torch.no_grad():
            for parameter in trainer.model.parameters():
                parameter.zero_()
        sampler, batches, records = validation_fixture(trainer, data)
        trainer.model.energy_head.eval()
        modes = [module.training for module in trainer.model.modules()]
        grad_parameter = next(trainer.model.parameters())
        grad_parameter.grad = torch.ones_like(grad_parameter)
        gradients = grad_parameter.grad.clone()
        controller, rng = trainer.controller.state_dict(), torch.get_rng_state().clone()
        trainer._clock_started = time.monotonic()
        assert trainer._validate("routine", sampler, batches)
        # Predictions are exactly zero; independent standardized Huber delta5.
        energy = sum(5 * record.energy - 12.5 for record in records) / len(records)
        charges = [float(value) for record in records for value in record.y.reshape(-1)]
        charge = sum(.5 * min(abs(value), 5.) ** 2 + 5. * max(abs(value) - 5., 0.)
                     for value in charges) / len(charges)
        assert trainer.last_validation["leaf_losses"]["energy"] == pytest.approx(energy, rel=1e-6)
        assert trainer.last_validation["leaf_losses"]["charge"] == pytest.approx(charge, rel=1e-6)
        assert trainer.last_validation["criterion_value"] == pytest.approx((energy + charge) / 2, rel=1e-6)
        assert trainer.last_validation["valid_labels"] == {"energy": 5, "charge": len(charges)}
        assert [module.training for module in trainer.model.modules()] == modes
        assert torch.equal(torch.get_rng_state(), rng) and torch.equal(grad_parameter.grad, gradients)
        assert trainer.controller.state_dict() == controller and trainer.counters["optimizer_updates"] == 0


def test_all_missing_validation_reports_unavailable_without_zero_best_or_controller_observations(tmp_path):
    with torch.random.fork_rng(devices=[]):
        trainer, _, _, data = fixture(tmp_path / "fixture", zero_labels=True)
        sampler, batches, _ = validation_fixture(trainer, data)
        before = trainer.controller.state_dict()
        trainer._clock_started = time.monotonic()
        assert trainer._validate("routine", sampler, batches)
        assert trainer.last_validation["criterion_value"] is None and trainer.best_validation is None
        assert trainer.last_validation["leaf_losses"] == {"energy": None, "charge": None}
        assert trainer.last_validation["status"] == "COMPLETE_WITH_UNAVAILABLE_TASKS"
        assert trainer.controller.state_dict() == before


def test_partial_validation_cursor_continues_exact_native_coverage_without_restarting_model(tmp_path):
    with torch.random.fork_rng(devices=[]):
        trainer, _, _, data = fixture(tmp_path / "fixture")
        sampler, batches, _ = validation_fixture(trainer, data)
        remaining = iter((20., 0.))
        trainer._remaining = lambda: next(remaining)
        before = backbone_state_hash(trainer.model)
        assert not trainer._validate("routine", sampler, batches)
        assert trainer.validation_state is not None and 0 < sampler.samples_consumed < 5
        count = sampler.samples_consumed
        new_sampler, new_batches, _ = validation_fixture(trainer, data)
        trainer._remaining = lambda: 20.
        assert trainer._validate("routine", new_sampler, new_batches)
        assert new_sampler.samples_consumed == 5 and trainer.last_validation["valid_labels"]["energy"] == 5
        assert count < new_sampler.samples_consumed and trainer.validation_state is None
        assert trainer.last_validation["consumed_bases"] == 5 and backbone_state_hash(trainer.model) == before


def test_pending_validation_resume_checks_its_real_view_cursor_before_live_commit(tmp_path):
    with torch.random.fork_rng(devices=[]):
        trained, _, _, data = fixture(tmp_path / "fixture", name="trained")
        sampler, batches, _ = validation_fixture(trained, data)
        remaining = iter((20., 0.))
        trained._remaining = lambda: next(remaining)
        assert not trained._validate("routine", sampler, batches)
        payload = trained.checkpoint()
        receiver, _, _, _ = fixture(tmp_path / "unused", name="receiver", shared_manifest=data)
        valid_sampler, _, _ = validation_fixture(receiver, data)
        bad = deepcopy(payload)
        bad["validation_state"]["sampler"]["samples_consumed"] += 1
        bad["validation_state"]["sampler"]["content_sha256"] = canonical_hash({
            k: v for k, v in bad["validation_state"]["sampler"].items() if k != "content_sha256"})
        bad["checkpoint_content_sha256"] = checkpoint_content_sha256(bad)
        model, optimizer, rng = deepcopy(receiver.model.state_dict()), deepcopy(receiver.optimizer.state_dict()), torch.get_rng_state().clone()
        with pytest.raises((FullCorpusTrainingError, ValueError, RuntimeError)):
            receiver.load_checkpoint(bad, checkpoint_file_sha256="f" * 64,
                                     validation_sampler_factory=lambda scope: valid_sampler)
        assert_same_tree(model, receiver.model.state_dict())
        assert_same_tree(optimizer, receiver.optimizer.state_dict())
        assert receiver.validation_state is None and torch.equal(torch.get_rng_state(), rng)
        receiver.load_checkpoint(payload, checkpoint_file_sha256="f" * 64,
                                 validation_sampler_factory=lambda scope: valid_sampler)
        new_sampler, rest, _ = validation_fixture(receiver, data)
        receiver._remaining = lambda: 20.
        assert receiver._validate("routine", new_sampler, rest)
        assert new_sampler.samples_consumed == 5 and receiver.last_validation["valid_labels"]["energy"] == 5


def test_complete_resume_requires_real_full_validation_after_exact_training_coverage(tmp_path):
    with torch.random.fork_rng(devices=[]):
        trained, batches, _, data = fixture(tmp_path / "fixture", name="trained")
        full_sampler, full_batches, _ = validation_fixture(trained, data)
        trained.config["bindings"]["full_validation_manifest_sha256"] = full_sampler.index.content_sha256
        for batch in batches:
            trained._consume(batch)
        assert trained.sampler.samples_consumed == 5
        receiver, _, _, _ = fixture(tmp_path / "unused", name="receiver", shared_manifest=data)
        receiver_validation, _, _ = validation_fixture(receiver, data)
        receiver.config["bindings"]["full_validation_manifest_sha256"] = receiver_validation.index.content_sha256
        forged = trained.checkpoint()
        forged["status"] = "complete"
        forged["checkpoint_content_sha256"] = checkpoint_content_sha256(forged)
        before, rng = deepcopy(receiver.model.state_dict()), torch.get_rng_state().clone()
        with pytest.raises(FullCorpusTrainingError, match="closed full-validation"):
            receiver.load_checkpoint(forged, checkpoint_file_sha256="f" * 64,
                                     validation_sampler_factory=lambda scope: receiver_validation)
        assert_same_tree(before, receiver.model.state_dict())
        assert receiver.sampler.samples_consumed == 0 and torch.equal(torch.get_rng_state(), rng)
        result = trained.fit((), validation_factory=lambda scope: (full_sampler, full_batches))
        assert result["status"] == "complete" and result["last_validation"]["scope"] == "full"
        assert result["last_validation"]["consumed_bases"] == 5
        payload = trained.checkpoint()
        receiver.load_checkpoint(payload, checkpoint_file_sha256="f" * 64,
                                 validation_sampler_factory=lambda scope: receiver_validation)
        assert receiver.status == "complete" and receiver.sampler.samples_consumed == 5
        assert_same_tree(trained.model.state_dict(), receiver.model.state_dict())
        assert_same_tree(trained.optimizer.state_dict(), receiver.optimizer.state_dict())
        assert receiver.last_validation == trained.last_validation


def test_tracking_failure_after_actual_update_never_exports_a_resumable_success(tmp_path):
    with torch.random.fork_rng(devices=[]):
        trainer, batches, tracker, _ = fixture(tmp_path / "fixture")
        def fail(*args, **kwargs):
            raise OSError("Synthetic offline writer failure")
        tracker.log = fail
        with pytest.raises(OSError):
            trainer._consume(batches[0])
        assert trainer.counters["optimizer_updates"] == 1 and trainer.sampler.samples_consumed == 0
        with pytest.raises(FullCorpusTrainingError):
            trainer.checkpoint()
