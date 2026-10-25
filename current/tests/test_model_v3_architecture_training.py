"""Actual C1/C3 updates, metrics, resume and strict encoder/evaluator binding."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import random

import numpy as np
import pytest
import torch
from torch_geometric.data import Batch, Data

from test_model_v3_trainer import BoundSyntheticProvider, UnitTracker, make_trainer, scientific_record
from test_model_v3_training import assert_tree_equal
from test_model_v3_encoder_bridge import binding, json_file, checkpoint_file
from test_model_v3_experiment_tools import arguments, module
from phychem_mfm.model.v3_architecture import (ArchitectureOptions, configuration_with_architecture,
    build_architecture_model, source_s_architecture_configuration)
from phychem_mfm.model.v3_multiview import V3MultiViewModel
from phychem_mfm.phase1.v3_architecture_views import V3TwoViewModel, build_two_structural_views
from phychem_mfm.phase1.v3_architecture_training import ArchitectureStepTrainer
from phychem_mfm.phase1.v3_dev_panel import canonical
from phychem_mfm.phase1.v3_encoder_bridge import EncoderBindingError, load_encoder_pair
from phychem_mfm.phase1.v3_trainer import SampleLRScheduler
from phychem_mfm.phase1.v3_training import SampleClock, capture_rng_state


@pytest.fixture(autouse=True)
def fixed_cpu_environment():
    previous = torch.get_num_threads(); torch.set_num_threads(1)
    try:
        yield
    finally:
        torch.set_num_threads(previous)


class TwoProvider(BoundSyntheticProvider):
    def prepare(self, choices, *, role, view_config, enabled_groups, enabled_fields):
        prepared = super().prepare(choices, role=role, view_config=view_config,
            enabled_groups=enabled_groups, enabled_fields=enabled_fields)
        records = prepared.views.batch.to_data_list()
        clean = Batch.from_data_list([records[int(i)] for i in prepared.views.clean_graph_rows])
        views = build_two_structural_views(clean, ordinals=prepared.views.ordinals, config=view_config,
            include_structural="S" in enabled_groups, graph_eligibility=prepared.views.graph_eligibility)
        return replace(prepared, views=views)


def architecture_trainer(*, kind="C1-a", views="two", budget=4, layers=1, max_cost=8000000,
                         tracker_id="unit-original", configuration_sha=None):
    old = make_trainer(budget=budget, milestones=(2,), probe_interval=2)
    source = old.model.encoder
    config = {"architecture": {"preset": "shared_light"}, "backbone": {**source.backbone_config, "layers": layers},
              "head": source.head_config, "expert": source.expert_config}
    options = ArchitectureOptions(distance_bias=kind)
    sealed = source_s_architecture_configuration(config, options)
    torch.manual_seed(7)
    encoder = build_architecture_model(sealed)
    cls = V3TwoViewModel if views == "two" else V3MultiViewModel
    model = cls(encoder, old.model.pd_heads, old.model.registry, old.model.structural_binding)
    provider_cls = TwoProvider if views == "two" else BoundSyntheticProvider
    provider = provider_cls(Batch.from_data_list(old.provider.records), model.registry,
                            model.structural_binding, old.sampler.index)
    optimizer = torch.optim.AdamW(model.parameters(), lr=.003, betas=(.9, .95), weight_decay=0., foreach=False)
    scheduler = SampleLRScheduler(optimizer, sample_budget=budget)
    source_bindings = {key: old.bindings[key] for key in (
        "code_sha", "configuration_sha256", "registry_sha256", "normalization_sha256", "data_version")}
    if configuration_sha is not None:
        source_bindings["configuration_sha256"] = configuration_sha
    trainer = ArchitectureStepTrainer(model, optimizer, scheduler, old.sampler, SampleClock(budget, (2,)),
        provider, old.normalizations, old.weights, UnitTracker(tracker_id), source_bindings,
        structural_views=views, enabled_groups=old.groups, gradient_probe_interval=2,
        probe_samples=1, allow_unit_tracker=True, max_padded_cost=max_cost)
    return trainer, {"seed": 7, "model": sealed}


def test_two_view_capacity_real_s_metrics_and_sample_clocks_are_connected():
    two, _ = architecture_trainer(max_cost=700)
    three, _ = architecture_trainer(views="three", max_cost=700)
    draws = tuple(two.sampler.choice(i) for i in range(2))
    assert two._within_capacity(draws) and not three._within_capacity(draws)
    row = two.next_step(2)
    assert row["samples_consumed"] == 2 and row["optimizer_updates"] == 1
    assert row["valid_count/s_element"] == 2 and row["valid_count/s_noise"] == 24
    assert row["valid_count/s_bond"] == 22 and row["accuracy/s_element"] is not None
    assert row["MAE/s_noise"] is not None and row["R2/s_noise"] is not None
    assert row["valid_count/new_energy"] == 2 and row["valid_count/new_atom"] == 24
    assert two.contract["architecture_extension"]["physical_views_per_sample"] == 2
    assert three.contract["architecture_extension"]["physical_views_per_sample"] == 3
    assert two.model.encoder.backbone.pair_encoder.centers.grad is not None


def test_wrong_physical_layout_fails_before_optimizer_or_rng_mutation():
    trainer, _ = architecture_trainer()
    draws = tuple(trainer.sampler.choice(i) for i in range(2))
    wrong = BoundSyntheticProvider.prepare(trainer.provider, draws, role="TRAIN", view_config=trainer.view_config,
        enabled_groups=trainer.groups, enabled_fields=trainer.fields)
    state = deepcopy(trainer.model.state_dict()), deepcopy(trainer.optimizer.state_dict()), capture_rng_state()
    with pytest.raises(ValueError, match="physical view layout"):
        trainer.step(wrong)
    assert_tree_equal(state[0], trainer.model.state_dict())
    assert_tree_equal(state[1], trainer.optimizer.state_dict())
    assert_tree_equal(state[2], capture_rng_state())
    assert trainer.clock.samples_consumed == 0


@pytest.mark.parametrize("kind", ("C1-a", "C1-b"))
def test_c1_two_view_complete_resume_retains_update_data_rng_and_metric_lineage(tmp_path, kind):
    np.random.seed(17); random.seed(17)
    original, _ = architecture_trainer(kind=kind)
    original.next_step(2)
    original.validate("VAL")
    original.save(tmp_path / "seen2", output_root=tmp_path)
    before = len(original.tracker.records)
    expected = original.next_step(2)
    expected_state = deepcopy(original.model.state_dict()), deepcopy(original.optimizer.state_dict()), capture_rng_state()
    expected_logs = original.tracker.records[before:]
    resumed, _ = architecture_trainer(kind=kind, tracker_id="unit-resumed")
    resumed.load(tmp_path / "seen2", output_root=tmp_path)
    actual = resumed.next_step(2)
    assert_tree_equal(expected_state[0], resumed.model.state_dict())
    assert_tree_equal(expected_state[1], resumed.optimizer.state_dict())
    assert_tree_equal(expected_state[2], capture_rng_state())
    assert scientific_record(actual) == scientific_record(expected)
    assert [scientific_record(row) for row in resumed.tracker.records] == [scientific_record(row) for row in expected_logs]
    assert resumed.validation_state["VAL"]["completed_runs"] == 1
    assert all("shared_gradient_norm/" + group in actual for group in ("S", "D", "P"))
    wrong, _ = architecture_trainer(kind=kind, views="three")
    initial = deepcopy(wrong.model.state_dict())
    with pytest.raises(ValueError, match="binding/digest differs"):
        wrong.load(tmp_path / "seen2", output_root=tmp_path)
    assert_tree_equal(initial, wrong.model.state_dict())


@pytest.fixture(scope="module")
def real_v3_envelope(tmp_path_factory):
    root = tmp_path_factory.mktemp("c1_sample_checkpoint")
    previous = torch.get_num_threads(); torch.set_num_threads(1)
    try:
        trainer, configuration = architecture_trainer(layers=6)
        config_ref = json_file(root / "configuration.json", configuration)
        trainer.bindings["configuration_sha256"] = config_ref["sha256"]
        trainer.next_step(2)
        trainer.save(root / "checkpoint", output_root=root)
        return root, trainer, configuration, config_ref, binding(root / "checkpoint/payload.pt"), binding(root / "checkpoint/COMPLETE.json")
    finally:
        torch.set_num_threads(previous)


def test_actual_v3_sample_envelope_extracts_only_bound_encoder_with_matching_random(real_v3_envelope):
    root, trainer, configuration, config_ref, weights, completion = real_v3_envelope
    kwargs = dict(architecture_sha256=canonical(configuration["model"]), pretraining_seed=7,
                  enable_architecture_candidates=True)
    with pytest.raises(EncoderBindingError, match="COMPLETE marker"):
        load_encoder_pair(weights, config_ref, **kwargs)
    pair = load_encoder_pair(weights, config_ref, training_completion=completion, **kwargs)
    assert pair.provenance["checkpoint_schema"] == "model_v3_immutable_sample_checkpoint"
    assert pair.provenance["checkpoint_encoder_state_prefix"] == "encoder."
    assert pair.provenance["downstream_target_records_read"] == 0
    assert pair.candidate.config_dict() == pair.random_reference.config_dict() == trainer.model.encoder.config_dict()
    assert_tree_equal(pair.candidate.state_dict(), trainer.model.encoder.state_dict())
    graph = Data(x=torch.tensor([[5], [0], [7]]), pos=torch.tensor([[0., 0., 0.], [1., 0., 0.], [0., 1., 0.]]))
    with torch.no_grad():
        assert torch.equal(pair.candidate.encode_atoms(graph), trainer.model.encoder.encode_atoms(graph))
    assert not any(key.startswith("pd_heads.") for key in pair.candidate.state_dict())


def test_new_envelope_rejects_wrong_completion_source_config_and_nonencoder_keys(real_v3_envelope, tmp_path):
    root, trainer, configuration, config_ref, weights, completion = real_v3_envelope
    kwargs = dict(architecture_sha256=canonical(configuration["model"]), pretraining_seed=7,
                  enable_architecture_candidates=True)
    fake = json_file(tmp_path / "fake.json", {"schema": "model_v3_training_checkpoint_v1"})
    with pytest.raises(EncoderBindingError, match="same immutable directory"):
        load_encoder_pair(weights, config_ref, training_completion=fake, **kwargs)
    with pytest.raises(EncoderBindingError, match="candidate opt-in"):
        load_encoder_pair(weights, config_ref, training_completion=completion,
            **{key: value for key, value in kwargs.items() if key != "enable_architecture_candidates"})
    changed = deepcopy(configuration); changed["model"]["backbone"]["v3_architecture"]["rbf_max_distance"] = 9.
    config2 = json_file(tmp_path / "changed.json", changed)
    with pytest.raises(EncoderBindingError, match="encoder/trainer contract differs"):
        load_encoder_pair(weights, config2, training_completion=completion,
            **{**kwargs, "architecture_sha256": canonical(changed["model"])})
    from phychem_mfm.phase1.v3_contract import canonical_hash
    for bad_kind in ("source", "namespace", "marker"):
        target = tmp_path / bad_kind; target.mkdir()
        payload = torch.load(weights["path"], map_location="cpu", weights_only=True)
        marker = json.loads(Path(completion["path"]).read_text())
        if bad_kind == "source":
            contract = payload["extra_state"]["contract"]
            contract["architecture_extension"]["implementation_sources"]["model/v3_architecture.py"] = "0" * 64
            payload["bindings"]["trainer_configuration_sha256"] = canonical_hash(contract)
        elif bad_kind == "namespace":
            payload["model"]["unrecognized.weight"] = torch.ones(1)
        new_weights = checkpoint_file(target / "payload.pt", payload)
        marker.update(payload_sha256=new_weights["sha256"], payload_bytes=new_weights["bytes"], bindings=payload["bindings"])
        if bad_kind == "marker":
            marker["samples_consumed"] += 1
        new_completion = json_file(target / "COMPLETE.json", marker)
        with pytest.raises(EncoderBindingError, match="encoder/trainer contract differs"):
            load_encoder_pair(new_weights, config_ref, training_completion=new_completion, **kwargs)


def test_request_tools_carry_explicit_architecture_and_completion_bindings_without_changing_old_defaults(tmp_path):
    prepare = module("prepare_dev_evaluation"); args = arguments(tmp_path)
    control = prepare.make_request(**args)
    assert "enable_architecture_candidates" not in control and "training_completion" not in control
    configuration = json.loads(args["model_configuration"].read_text())
    configuration["model"]["backbone"]["v3_architecture"] = {
        "distance_bias": "C1-a", "rbf_count": 64, "pair_dim": 64, "pair_hidden_dim": 64,
        "rbf_max_distance": 8., "cutoff": None}
    args["model_configuration"].write_text(json.dumps(configuration))
    with pytest.raises(ValueError, match="explicit evaluation opt-in"):
        prepare.make_request(**args)
    complete = tmp_path / "COMPLETE.json"; complete.write_text("{}")
    request = prepare.make_request(**args, enable_architecture_candidates=True, training_completion=complete)
    assert request["enable_architecture_candidates"] is True
    assert request["training_completion"] == {key: value for key, value in binding(complete).items() if key != "bytes"}
    with pytest.raises(ValueError, match="primary evaluations only"):
        prepare.make_request(**args, enable_architecture_candidates=True, reference_kind="historical_sanity_only")
