"""Independent synthetic molecule/task ranking oracles, never final targets.

Declared masks mimic deleted ordinary H and retained isotope H only to test
transport; they do not verify a real source annotation or chemical negative.
Native-ID tie breaking and N/A are preparation semantics, not author bitwise
reproduction. Real tiny Shared H0/atom-readout training is tested separately
from the controlled score backbone, and no dataset or file I/O is required.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace

import pytest
import torch
from torch import nn
from torch_geometric.data import Data

from conftest import small_config
from phychem_mfm.factory import build_model
from phychem_mfm.phase1.downstream_readout import SourceAlignedH0Readout
from phychem_mfm.phase1.downstream_training import DownstreamTrainBatch, DownstreamTrainer
from phychem_mfm.phase1.formal_runtime import backbone_state_hash
from phychem_mfm.phase1.identity import canonical_hash
from phychem_mfm.phase1 import som_evaluation as som_module
from phychem_mfm.phase1.som_evaluation import SomEvaluationError, evaluate_som_ranking


TASKS = ("toy_cyp", "toy_human_hepatocyte")


class ScoreBackbone(nn.Module):
    """Controlled actual H0 forward within a genuine Shared model container."""

    def __init__(self):
        super().__init__()
        self.scale = nn.Parameter(torch.ones(()))
        self.register_buffer("marker", torch.tensor([17.0]))

    def forward(self, data):
        assert set(data.keys()) == {"x", "pos", "batch", "ptr"}
        return torch.cat((data.pos, data.pos.new_zeros((data.x.numel(), 5))), dim=1) * self.scale


class ObservableBackbone(nn.Module):
    """BN/dropout state test double, not a scientific representation choice."""

    def __init__(self):
        super().__init__()
        self.linear = nn.Linear(4, 8)
        self.bn = nn.BatchNorm1d(8)
        self.dropout = nn.Dropout(0.4)
        self.register_buffer("marker", torch.tensor([19.0]))

    def forward(self, data):
        assert set(data.keys()) == {"x", "pos", "batch", "ptr"}
        features = torch.cat((data.x.float().unsqueeze(1) / 10, data.pos), dim=1)
        return self.dropout(self.bn(self.linear(features)))


class SyntheticTracker:
    """Identified training spy; no persisted W&B/backend claims."""

    def __init__(self):
        self.id = "synthetic-som-training"
        self.path = "tests/synthetic/" + self.id
        self.settings = SimpleNamespace(mode="offline")
        self.disabled = False
        self.step = 0

    def log(self, payload, *, step, commit):
        assert commit is True and step == self.step
        self.step += 1


def make_system(*, backbone="scores", mode="frozen"):
    with torch.random.fork_rng(devices=[]):
        torch.set_rng_state(torch.Generator(device="cpu").manual_seed(1301).get_state())
        architecture = small_config("light")
        architecture["backbone"].update(dim=8, layers=1, heads=2, dropout=0.3)
        architecture["head"]["profile"] = "phase1"
        model = build_model(architecture)
        if backbone == "scores":
            model.backbone = ScoreBackbone()
        elif backbone == "observable":
            model.backbone = ObservableBackbone()
        else:
            assert backbone == "real"
        readout = SourceAlignedH0Readout(8, 2, output_level="atom", hidden_dim=8)
    if backbone == "scores":
        with torch.no_grad():
            for layer in readout.atom_mlp.modules():
                if isinstance(layer, nn.Linear):
                    layer.weight.copy_(torch.eye(8))
                    layer.bias.zero_()
            readout.output.weight.zero_()
            readout.output.weight[:, :2].copy_(torch.eye(2))
            readout.output.bias.zero_()
    normalization = {
        "kind": "identity", "means": [0.0, 0.0], "scales": [1.0, 1.0],
        "train_only": True, "train_data_sha256": "a" * 64,
        "split_manifest_sha256": "b" * 64, "fit_source_sha256": "c" * 64,
    }
    config = {
        "schema_version": "phase1_downstream_training_v1", "mode": mode,
        "total_updates": 2, "seed": 1303, "device": "cpu",
        "readout_config": readout.config_dict(), "tasks": list(TASKS),
        "loss": "bce_logits", "reduction": "task_then_observed_label_mean",
        "task_weights": [1.0, 3.0], "normalization": normalization,
        "optimizer": {"implementation": "single_tensor_adamw_v1", "lr": 0.005,
                      "betas": [0.8, 0.9], "eps": 1e-7, "weight_decay": 0.01, "amsgrad": False},
        "gradient_clip_norm": None,
        "caps": {"wall_seconds": 60.0, "max_sequence_batches": 8,
                 "max_graphs_per_batch": 4, "max_atoms_per_batch": 32, "max_unique_samples": 8},
        "bindings": {"train_data_sha256": "a" * 64, "split_manifest_sha256": "b" * 64,
                     "normalizer_sha256": canonical_hash(normalization), "source_sha256": "d" * 64,
                     "initial_encoder_sha256": backbone_state_hash(model)},
    }
    primary = {TASKS[0]: {"metric": "molecule_hit_at_k", "k": 1},
               TASKS[1]: {"metric": "molecule_hit_at_k", "k": 2}}
    contract = {
        "schema_version": "phase1_som_ranking_evaluation_v1", "role": "train_inner_validation",
        "ks": [1, 2, 3], "score_space": "raw_logits",
        "tie_policy": "score_desc_native_source_id_asc",
        "k_over_candidates": "clamp_to_candidate_count",
        "incomplete_supervision": "skip_instance", "no_positive_policy": "exclude_and_report",
        "label_semantics": "source_native_binary_0_1_supervision_subset_candidates_v1",
        "units": {task: "binary" for task in TASKS},
        "task_metadata": {TASKS[0]: {"dataset_id": "synthetic-cyp", "enzyme_id": "toy-enzyme",
                                     "positive_definition": "synthetic-primary-only"},
                          TASKS[1]: {"dataset_id": "synthetic-az", "enzyme_id": None,
                                     "positive_definition": "synthetic-exact-only"}},
        "primary_metric_per_task": primary, "primary_contract_sha256": canonical_hash(primary),
        "dataset_sha256": "e" * 64, "split_manifest_sha256": "b" * 64,
        "caps": {"wall_seconds": 60.0, "max_sequence_batches": 8,
                 "max_unique_samples": 8, "max_graphs_per_batch": 4, "max_atoms_per_batch": 32},
    }
    return model, readout, config, contract


def pack_graphs(graphs, *, permutations=None):
    """Native labels stay in source order while actual encoder rows permute."""
    native_x = ([5, 0, 7, 0], [5, 7], [5, 6, 7], [0])
    scores = (((1., 4.), (3., 3.), (2., 2.), (100., 100.)),
              ((2., 2.), (1., 1.)), ((1., 1.), (1., 1.), (1., 1.)), ((1., 1.),))
    labels = (((1., 0.), (0., 1.), (1., 0.), (float("nan"), float("nan"))),
              ((1., float("nan")), (0., float("nan"))),
              ((0., 0.), (0., 0.), (1., 0.)), ((float("nan"), 1.),))
    candidates = (((True, True), (True, True), (True, True), (False, False)),
                  ((True, True), (True, True)), ((True, True),) * 3, ((True, True),))
    observed = (((True, True), (True, True), (True, True), (False, False)),
                ((True, False), (True, False)), ((True, True),) * 3, ((False, True),))
    default_perms = ((3, 1, 0, 2), (1, 0), (2, 0, 1), (0,))
    x, pos, owners, source, target, candidate, supervision, ptr = [], [], [], [], [], [], [], [0]
    for owner, graph in enumerate(graphs):
        order = default_perms[graph] if permutations is None else permutations[graph]
        for native_id in order:
            x.append(native_x[graph][native_id])
            pos.append([*scores[graph][native_id], native_id * 0.1])
            owners.append(owner)
            source.append(native_id)
        target.extend(labels[graph])
        candidate.extend(candidates[graph])
        supervision.extend(observed[graph])
        ptr.append(len(x))
    data = Data(x=torch.tensor(x, dtype=torch.long), pos=torch.tensor(pos, dtype=torch.float32),
                batch=torch.tensor(owners), ptr=torch.tensor(ptr),
                y=torch.tensor([-999.0]), unrelated_annotation="not an encoder feature")
    return DownstreamTrainBatch(
        encoder_batch=data, sample_ids=tuple("synthetic-source-record-" + str(g) for g in graphs),
        source_atom_ids=torch.tensor(source), targets=torch.tensor(target, dtype=torch.float32),
        candidate_mask=torch.tensor(candidate), supervision_mask=torch.tensor(supervision),
        role="train_inner_validation",
    )


def standard_batches():
    return (pack_graphs((0, 1)), pack_graphs((2, 3)))


def evaluate(system, batches=None, *, config=None, contract=None):
    model, readout, original_config, original_contract = system
    return evaluate_som_ranking(model, readout, original_config if config is None else config,
                                standard_batches() if batches is None else batches,
                                evaluation_contract=original_contract if contract is None else contract)


def assert_nested_equal(left, right):
    if isinstance(left, torch.Tensor):
        assert isinstance(right, torch.Tensor) and left.dtype == right.dtype and left.shape == right.shape
        torch.testing.assert_close(left, right, rtol=0, atol=0, equal_nan=True)
    elif isinstance(left, dict):
        assert isinstance(right, dict) and set(left) == set(right)
        for key in left:
            assert_nested_equal(left[key], right[key])
    elif isinstance(left, (tuple, list)):
        assert isinstance(right, type(left)) and len(left) == len(right)
        for a, b in zip(left, right):
            assert_nested_equal(a, b)
    else:
        assert left == right


def snapshot(model, readout):
    modules = (model, readout)
    parameters = [p for module in modules for p in module.parameters()]
    return {"states": [deepcopy(module.state_dict()) for module in modules],
            "modes": [[child.training for child in module.modules()] for module in modules],
            "requires_grad": [p.requires_grad for p in parameters],
            "grads": [None if p.grad is None else p.grad.detach().clone() for p in parameters],
            "grad_objects": [p.grad for p in parameters], "rng": torch.get_rng_state().clone()}


def assert_preserved(before, model, readout):
    after = snapshot(model, readout)
    for field in ("states", "modes", "requires_grad", "grads", "rng"):
        assert_nested_equal(before[field], after[field])
    assert all(a is b for a, b in zip(before["grad_objects"], after["grad_objects"]))


def independent_forward_hit_counts(model, readout, batches, *, score_space="raw_logits", ks=(1, 2, 3)):
    """Actual H0 plus separate matrices/loops: never calls ranking/readout forward."""
    before = snapshot(model, readout)
    hits, denominators = [[0] * len(ks) for _ in TASKS], [0] * len(TASKS)
    try:
        model.eval()
        readout.eval()
        with torch.no_grad():
            for item in batches:
                data = item.encoder_batch
                clean = Data(x=data.x, pos=data.pos, batch=data.batch, ptr=data.ptr)
                h0 = model.encode_atoms(clean)
                # Fixture is exactly one affine hidden layer followed by ReLU.
                layer = readout.atom_mlp[0].net[0]
                hidden = torch.relu(h0 @ layer.weight.T + layer.bias)
                scores = hidden @ readout.output.weight.T + readout.output.bias
                if score_space == "sigmoid_fp32":
                    scores = torch.sigmoid(scores)
                for start, end in zip(data.ptr[:-1].tolist(), data.ptr[1:].tolist()):
                    for task in range(len(TASKS)):
                        candidates = [i for i in range(end - start) if item.candidate_mask[start + i, task]]
                        if not candidates or not all(item.supervision_mask[start + i, task] for i in candidates):
                            continue
                        positive = {i for i in candidates if float(item.targets[start + i, task]) == 1.0}
                        if not positive:
                            continue
                        # Convert encoder scores to native rows using the source permutation.
                        native_scores = {int(item.source_atom_ids[row]): float(scores[row, task])
                                         for row in range(start, end)}
                        ranking = sorted(candidates, key=lambda i: (-native_scores[i], i))
                        denominators[task] += 1
                        for index, k in enumerate(ks):
                            hits[task][index] += int(bool(positive.intersection(ranking[:min(k, len(candidates))])))
    finally:
        for module, modes in zip((model, readout), before["modes"]):
            for child, mode in zip(module.modules(), modes):
                child.training = mode
    assert_preserved(before, model, readout)
    return denominators, hits


def test_hand_molecule_task_hit_counts_are_not_atom_recall_or_batch_means():
    receipt = evaluate(make_system())
    for task, denominator, hits in zip(TASKS, (3, 2), ((1, 2, 3), (1, 2, 2))):
        metric = receipt["metrics"][task]
        assert metric["counters"]["instances"] == 4
        assert metric["counters"]["evaluable"] == denominator
        assert metric["counters"]["unknown"] == 1
        assert metric["counters"]["partial_supervision"] == 0
        for k, hit in zip((1, 2, 3), hits):
            assert metric["by_k"][str(k)] == {"hits": hit, "denominator": denominator, "hit_rate": hit / denominator}
    assert receipt["metrics"][TASKS[0]]["primary_value"] == pytest.approx(1 / 3)
    assert receipt["metrics"][TASKS[1]]["primary_value"] == 1.0
    assert receipt["metrics"][TASKS[1]]["counters"]["no_positive"] == 1
    # A has two positives, only one in its Top2: molecule hit=1, atom recall=1/2.
    a = evaluate(make_system(), (pack_graphs((0,)),))
    assert a["metrics"][TASKS[0]]["by_k"]["2"]["hit_rate"] == 1.0


def test_deleted_h_is_excluded_but_retained_isotope_h_remains_a_candidate():
    system = make_system()
    item = pack_graphs((0,))
    # Native IDs 1 and 3 are both Z=1, but only ID1 is declared retained.
    assert item.encoder_batch.x[item.source_atom_ids == 1].item() == 0
    assert item.encoder_batch.x[item.source_atom_ids == 3].item() == 0
    assert item.candidate_mask[1, 1] and not item.candidate_mask[3, 1]
    receipt = evaluate(system, (item,))
    assert receipt["metrics"][TASKS[1]]["by_k"]["1"]["hits"] == 0
    assert receipt["metrics"][TASKS[1]]["by_k"]["2"]["hits"] == 1


def test_native_id_ties_ignore_encoder_permutation_and_k_clamps_to_candidates():
    system = make_system()
    left = evaluate(system, (pack_graphs((2, 3)),))
    right = evaluate(system, (pack_graphs((2, 3), permutations=((0, 1, 2, 3), (0, 1), (1, 2, 0), (0,))),))
    assert_nested_equal(left["metrics"], right["metrics"])
    assert left["ranked_native_source_ids_sha256"] == right["ranked_native_source_ids_sha256"]
    # These genuinely equal score rows retain the same tensor hash even when
    # their source IDs permute; the sequence binding separately records IDs.
    assert left["raw_logit_score_sha256"] == right["raw_logit_score_sha256"]
    assert left["evaluation_sequence_sha256"] != right["evaluation_sequence_sha256"]
    assert [left["metrics"][TASKS[0]]["by_k"][str(k)]["hits"] for k in (1, 2, 3)] == [0, 0, 1]
    assert [left["metrics"][TASKS[1]]["by_k"][str(k)]["hits"] for k in (1, 2, 3)] == [1, 1, 1]


def test_sigmoid_saturation_is_explicit_and_can_change_native_id_tie_ranking():
    system = make_system()
    item = deepcopy(pack_graphs((1,)))
    # Raw native ID0=20, ID1=21; both sigmoid FP32 scores round to 1.
    item.encoder_batch.pos[:, 0] = torch.tensor([21., 20.])
    item.targets[:, 0] = torch.tensor([0., 1.])
    raw = evaluate(system, (item,))
    contract = deepcopy(system[3])
    contract["score_space"] = "sigmoid_fp32"
    saturated = evaluate(system, (item,), contract=contract)
    assert torch.sigmoid(torch.tensor(20., dtype=torch.float32)).item() == 1.0
    assert raw["metrics"][TASKS[0]]["by_k"]["1"]["hits"] == 1
    assert saturated["metrics"][TASKS[0]]["by_k"]["1"]["hits"] == 0
    assert raw["evaluation_contract_sha256"] != saturated["evaluation_contract_sha256"]
    assert raw["raw_logit_score_sha256"] == saturated["raw_logit_score_sha256"]
    assert raw["ranking_score_sha256"] != saturated["ranking_score_sha256"]
    assert raw["ranked_native_source_ids_sha256"] != saturated["ranked_native_source_ids_sha256"]


@pytest.mark.parametrize("partition", [((0,), (1, 2, 3)), ((0, 1, 2, 3),), ((3, 2), (1, 0))])
def test_batch_chunking_and_graph_order_preserve_pooled_counts_not_order_hash(partition):
    system = make_system()
    baseline = evaluate(system)
    actual = evaluate(system, tuple(pack_graphs(graphs) for graphs in partition))
    assert_nested_equal(actual["metrics"], baseline["metrics"])
    assert actual["sample_membership_sha256"] == baseline["sample_membership_sha256"]
    assert actual["evaluation_sequence_sha256"] != baseline["evaluation_sequence_sha256"]


@pytest.mark.parametrize("state", ["no_candidate", "unknown", "no_positive", "partial_supervision"])
def test_unavailable_instance_states_have_explicit_counters_and_none_not_zero(state):
    system = make_system()
    item = deepcopy(pack_graphs((1,)))
    item.targets[:] = float("nan")
    item.supervision_mask[:] = False
    if state == "no_candidate":
        item.candidate_mask[:] = False
    elif state == "no_positive":
        item.targets[:] = 0
        item.supervision_mask[:] = True
    elif state == "partial_supervision":
        item.targets[0, :] = 1
        item.supervision_mask[0, :] = True
    receipt = evaluate(system, (item,))
    assert receipt["status"] == "NO_EVALUABLE_INSTANCES"
    for task in TASKS:
        metric = receipt["metrics"][task]
        assert metric["counters"][state] == 1 and metric["counters"]["evaluable"] == 0
        assert metric["status"] == "NO_EVALUABLE_INSTANCES" and metric["primary_value"] is None
        for row in metric["by_k"].values():
            assert row == {"hits": 0, "denominator": 0, "hit_rate": None}


@pytest.mark.parametrize("state", ["unknown", "partial_supervision"])
def test_incomplete_reject_policy_does_not_shrink_ranking_to_observed_atoms(state):
    system = make_system()
    item = deepcopy(pack_graphs((1,)))
    item.supervision_mask[:] = False
    item.targets[:] = float("nan")
    if state == "partial_supervision":
        item.supervision_mask[0, :] = True
        item.targets[0, :] = 1
    contract = deepcopy(system[3])
    contract["incomplete_supervision"] = "reject"
    before = snapshot(*system[:2])
    with pytest.raises(SomEvaluationError):
        evaluate(system, (item,), contract=contract)
    assert_preserved(before, *system[:2])


@pytest.mark.parametrize("mode", ["frozen", "finetune"])
def test_genuine_shared_trained_atom_readout_matches_independent_raw_h0_ranking(mode):
    system = make_system(backbone="real", mode=mode)
    model, readout, config, _ = system
    batches = standard_batches()
    tracker = SyntheticTracker()
    initial = backbone_state_hash(model)
    trainer = DownstreamTrainer(model, readout, config, tracker=tracker)
    trainer.fit(tuple(replace(item, role="train") for item in batches), max_updates=2)
    assert tracker.step == 2
    assert (backbone_state_hash(model) == initial) == (mode == "frozen")
    expected_denominators, expected_hits = independent_forward_hit_counts(model, readout, batches)
    before = snapshot(model, readout)
    receipt = evaluate(system, batches)
    for index, task in enumerate(TASKS):
        for k_index, k in enumerate((1, 2, 3)):
            row = receipt["metrics"][task]["by_k"][str(k)]
            assert row["denominator"] == expected_denominators[index]
            assert row["hits"] == expected_hits[index][k_index]
    assert_preserved(before, model, readout)


@pytest.mark.parametrize("fault", ["none", "random_then_raise", "buffer", "unused_head", "readout_weight", "gradient"])
def test_full_modes_buffers_parameters_gradient_ownership_and_rng_restore(fault, monkeypatch):
    system = make_system(backbone="observable")
    model, readout = system[:2]
    model.train()
    model.backbone.bn.eval()
    readout.eval()
    readout.atom_mlp.train()
    parameters = list(model.parameters()) + list(readout.parameters())
    for index, parameter in enumerate(parameters):
        parameter.requires_grad_(index % 2 == 0)
        if index % 3 == 0:
            parameter.grad = torch.full_like(parameter, .125)
    before = snapshot(model, readout)
    versions = [parameter._version for parameter in parameters]
    original = model.backbone.forward

    def injected_forward(data):
        if fault == "random_then_raise":
            torch.rand(3)
            raise RuntimeError("synthetic failure after consuming caller RNG")
        if fault == "buffer":
            model.backbone.marker.add_(1)
        elif fault == "unused_head":
            next(model.energy_head.parameters()).add_(.5)
        elif fault == "readout_weight":
            readout.output.weight.add_(.5)
        elif fault == "gradient":
            parameters[0].grad.add_(.5)
        return original(data)

    monkeypatch.setattr(model.backbone, "forward", injected_forward)
    if fault == "none":
        evaluate(system)
        assert [parameter._version for parameter in parameters] == versions
    else:
        with pytest.raises(SomEvaluationError):
            evaluate(system)
    assert_preserved(before, model, readout)


@pytest.mark.parametrize("fault", [
    "final_test", "train", "duplicate_id", "pad_element", "oov_element", "nan_coordinates",
    "duplicate_native_id", "bad_partition", "supervised_non_candidate", "active_nan", "nonbinary", "mask_dtype",
])
def test_invalid_batches_fail_closed_and_preserve_caller_state(fault):
    system = make_system()
    batches = list(standard_batches())
    item = deepcopy(batches[0])
    if fault in ("final_test", "train"):
        item = replace(item, role=fault)
    elif fault == "duplicate_id":
        batches[1] = replace(batches[1], sample_ids=(item.sample_ids[0], "new-toy-id"))
    elif fault in ("pad_element", "oov_element"):
        item.encoder_batch.x[0] = system[0].pad_elem_index + (fault == "oov_element")
    elif fault == "nan_coordinates":
        item.encoder_batch.pos[0, 0] = float("nan")
    elif fault == "duplicate_native_id":
        item.source_atom_ids[0] = item.source_atom_ids[1]
    elif fault == "bad_partition":
        item.encoder_batch.batch[1] = 1
    elif fault == "supervised_non_candidate":
        item.candidate_mask[0, 0] = False
    elif fault == "active_nan":
        item.targets[0, 0] = float("nan")
    elif fault == "nonbinary":
        item.targets[0, 0] = .5
    else:
        item = replace(item, candidate_mask=item.candidate_mask.long())
    batches[0] = item
    before = snapshot(*system[:2])
    with pytest.raises(SomEvaluationError):
        evaluate(system, batches)
    assert_preserved(before, *system[:2])


@pytest.mark.parametrize("fault", [
    "final_test", "train", "ks_duplicate", "ks_zero", "ks_bool", "score_space", "tie_policy",
    "incomplete_policy", "no_positive_policy", "units", "metadata_missing", "primary_k", "primary_hash",
    "dataset_hash", "split_drift", "boolean_cap", "supplied_predictions",
])
def test_contract_policies_primary_binding_and_source_declarations_are_exact(fault):
    system = make_system()
    contract = deepcopy(system[3])
    if fault in ("final_test", "train"):
        contract["role"] = fault
    elif fault.startswith("ks_"):
        contract["ks"] = {"ks_duplicate": [1, 1, 2], "ks_zero": [0, 1], "ks_bool": [True, 2]}[fault]
    elif fault == "score_space":
        contract["score_space"] = "caller_predictions"
    elif fault == "tie_policy":
        contract["tie_policy"] = "all_boundary_ties_count_as_hits"
    elif fault == "incomplete_policy":
        contract["incomplete_supervision"] = "rank_observed_only"
    elif fault == "no_positive_policy":
        contract["no_positive_policy"] = "assume_negative"
    elif fault == "units":
        contract["units"][TASKS[0]] = "probability"
    elif fault == "metadata_missing":
        contract["task_metadata"][TASKS[1]].pop("enzyme_id")
    elif fault == "primary_k":
        contract["primary_metric_per_task"][TASKS[0]]["k"] = 4
        contract["primary_contract_sha256"] = canonical_hash(contract["primary_metric_per_task"])
    elif fault == "primary_hash":
        contract["primary_contract_sha256"] = "f" * 64
    elif fault == "dataset_hash":
        contract["dataset_sha256"] = "short"
    elif fault == "split_drift":
        contract["split_manifest_sha256"] = "f" * 64
    elif fault == "boolean_cap":
        contract["caps"]["max_unique_samples"] = True
    else:
        contract["supplied_predictions"] = [[1., 2.]]
    before = snapshot(*system[:2])
    with pytest.raises(SomEvaluationError):
        evaluate(system, contract=contract)
    assert_preserved(before, *system[:2])


@pytest.mark.parametrize("fault", ["loss", "normalizer_hash", "readout_config", "model_dtype"])
def test_scientific_config_or_model_dtype_drift_is_rejected(fault):
    system = make_system()
    config = deepcopy(system[2])
    if fault == "loss":
        config["loss"] = "mse"
    elif fault == "normalizer_hash":
        config["normalization"]["scales"][0] = 2
    elif fault == "readout_config":
        config["readout_config"]["hidden_dim"] = 9
    else:
        system[0].double()
    before = snapshot(*system[:2])
    with pytest.raises(SomEvaluationError):
        evaluate(system, config=config)
    assert_preserved(before, *system[:2])


@pytest.mark.parametrize("field", ["max_sequence_batches", "max_unique_samples", "max_graphs_per_batch", "max_atoms_per_batch"])
def test_actual_sequence_shape_caps_are_cooperative_and_fail_closed(field):
    system = make_system()
    contract = deepcopy(system[3])
    contract["caps"][field] = {"max_sequence_batches": 1, "max_unique_samples": 3,
                               "max_graphs_per_batch": 1, "max_atoms_per_batch": 4}[field]
    before = snapshot(*system[:2])
    with pytest.raises(SomEvaluationError):
        evaluate(system, contract=contract)
    assert_preserved(before, *system[:2])


@pytest.mark.parametrize("changed", ["target", "candidate", "supervision", "member"])
def test_actual_target_mask_membership_binding_is_separate_from_caller_dataset_hash(changed):
    system = make_system()
    baseline = evaluate(system)
    batches = list(standard_batches())
    item = deepcopy(batches[0])
    if changed == "target":
        item.targets[0, 0] = 0
    elif changed == "candidate":
        # Graph B task1 is entirely unknown: remove its candidates without
        # pretending that these unspecified targets became known negatives.
        item.candidate_mask[4:, 1] = False
    elif changed == "supervision":
        item.supervision_mask[0, 0] = False
    else:
        item = replace(item, sample_ids=("other-declared-source-record", item.sample_ids[1]))
    batches[0] = item
    actual = evaluate(system, batches)
    assert actual["evaluation_contract_sha256"] == baseline["evaluation_contract_sha256"]
    assert actual["evaluation_sequence_sha256"] != baseline["evaluation_sequence_sha256"]
    if changed in ("candidate", "supervision"):
        assert actual["label_masks_sha256"] != baseline["label_masks_sha256"]
    if changed == "member":
        assert actual["sample_membership_sha256"] != baseline["sample_membership_sha256"]
    else:
        assert actual["sample_membership_sha256"] == baseline["sample_membership_sha256"]
        assert actual["raw_logit_score_sha256"] == baseline["raw_logit_score_sha256"]


def test_actual_prediction_and_weight_hashes_change_without_caller_binding_changes():
    system = make_system()
    baseline = evaluate(system)
    with torch.no_grad():
        system[1].output.bias[0] += .25
    actual = evaluate(system)
    assert actual["training_config_sha256"] == baseline["training_config_sha256"]
    assert actual["evaluation_contract_sha256"] == baseline["evaluation_contract_sha256"]
    assert actual["raw_logit_score_sha256"] != baseline["raw_logit_score_sha256"]
    assert actual["ranking_score_sha256"] != baseline["ranking_score_sha256"]
    assert actual["actual_state_before"]["readout_state_sha256"] != baseline["actual_state_before"]["readout_state_sha256"]
    # A common within-task shift changes actual values but not ranking.
    assert actual["ranked_native_source_ids_sha256"] == baseline["ranked_native_source_ids_sha256"]
    assert_nested_equal(actual["metrics"], baseline["metrics"])


def test_task_enzyme_and_primary_are_hashed_declarations_not_frozen_or_source_truth():
    system = make_system()
    baseline = evaluate(system)
    assert baseline["state"] == "NOT_FROZEN" and baseline["formal_eligible"] is False
    assert baseline["source_dataset_role_truth_independently_verified"] is False
    assert baseline["annotation_and_candidate_truth_independently_verified"] is False
    assert baseline["checkpoint_file_sha256_independently_verified"] is False
    assert baseline["metrics"][TASKS[1]]["task_metadata"]["enzyme_id"] is None
    assert baseline["actual_state_before"] == baseline["actual_state_after"]
    assert baseline["receipt_sha256"] == canonical_hash({k: v for k, v in baseline.items() if k != "receipt_sha256"})
    contract = deepcopy(system[3])
    contract["task_metadata"][TASKS[0]]["enzyme_id"] = "another-caller-declared-enzyme"
    contract["primary_metric_per_task"][TASKS[0]]["k"] = 3
    contract["primary_contract_sha256"] = canonical_hash(contract["primary_metric_per_task"])
    actual = evaluate(system, contract=contract)
    assert actual["evaluation_contract_sha256"] != baseline["evaluation_contract_sha256"]
    assert actual["primary_contract_sha256"] != baseline["primary_contract_sha256"]
    assert actual["raw_logit_score_sha256"] == baseline["raw_logit_score_sha256"]
    assert actual["metrics"][TASKS[0]]["primary_value"] == 1.0
    assert actual["formal_eligible"] is False


def test_last_forward_input_mutation_is_rejected_instead_of_returning_stale_binding(monkeypatch):
    system = make_system()
    batches = standard_batches()
    last = batches[-1]
    original = system[0].backbone.forward
    calls = 0

    def change_last_target(data):
        nonlocal calls
        calls += 1
        if calls == len(batches):
            last.targets[0, 0] = 1  # Still a legal binary label, but no longer the bound sequence.
        return original(data)

    monkeypatch.setattr(system[0].backbone, "forward", change_last_target)
    before = snapshot(*system[:2])
    with pytest.raises(SomEvaluationError):
        evaluate(system, batches)
    assert_preserved(before, *system[:2])


def test_cooperative_wall_failure_after_forward_restores_caller_rng_and_state(monkeypatch):
    system = make_system()
    contract = deepcopy(system[3])
    contract["caps"]["wall_seconds"] = .5
    clock = [0.0]
    original = system[0].backbone.forward

    def late_forward(data):
        torch.rand(3)
        result = original(data)
        clock[0] = 1.0
        return result

    monkeypatch.setattr(som_module.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(system[0].backbone, "forward", late_forward)
    before = snapshot(*system[:2])
    with pytest.raises(SomEvaluationError):
        evaluate(system, contract=contract)
    assert_preserved(before, *system[:2])
