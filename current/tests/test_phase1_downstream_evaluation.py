"""Independent synthetic raw-unit evaluation oracles, never final-test data.

Real tiny SharedBackboneMFM forwards are used for both graph readouts. The
separate BN/dropout backbone is only a state-preservation test double. No
dataset, annotation, checkpoint-file or W&B backend provenance is asserted.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import math
from types import SimpleNamespace

import pytest
import torch
from torch import nn
from torch_geometric.data import Data

from conftest import small_config
from phychem_mfm.factory import build_model
from phychem_mfm.phase1.downstream_evaluation import (
    DownstreamEvaluationError,
    evaluate_graph_regression,
)
from phychem_mfm.phase1.downstream_readout import (
    SourceAlignedH0Readout,
    SourceAlignedLinearGraphReadout,
)
from phychem_mfm.phase1.downstream_training import DownstreamTrainBatch, DownstreamTrainer
from phychem_mfm.phase1.formal_runtime import backbone_state_hash
from phychem_mfm.phase1.identity import canonical_hash


TASKS = ("toy_energy", "toy_charge", "toy_missing")
MEANS = (10.0, 100.0, -7.0)
SCALES = (2.0, 5.0, 0.25)


class ObservableBackbone(nn.Module):
    """A BN/dropout H0 within a genuine Shared model, not a new architecture."""

    def __init__(self):
        super().__init__()
        self.linear = nn.Linear(4, 8)
        self.bn = nn.BatchNorm1d(8)
        self.dropout = nn.Dropout(0.4)
        self.register_buffer("marker", torch.tensor([31.0]))

    def forward(self, data):
        assert set(data.keys()) == {"x", "pos", "batch", "ptr"}
        features = torch.cat((data.x.float().unsqueeze(1) / 10, data.pos), dim=1)
        return self.dropout(self.bn(self.linear(features)))


class IdentifiedSyntheticTracker:
    """An explicit optimizer-test spy, not a persisted training manager."""

    def __init__(self):
        self.id = "synthetic-evaluation-training"
        self.path = "tests/synthetic/" + self.id
        self.settings = SimpleNamespace(mode="offline")
        self.disabled = False
        self.step = 0

    def log(self, payload, *, step, commit):
        assert commit is True and step == self.step
        self.step += 1


def make_system(kind="main", *, observable=False, constant=True, mode="frozen"):
    with torch.random.fork_rng(devices=[]):
        torch.set_rng_state(torch.Generator(device="cpu").manual_seed(903).get_state())
        architecture = small_config("light")
        architecture["backbone"].update(dim=8, layers=1, heads=2, dropout=0.3)
        architecture["head"]["profile"] = "phase1"
        model = build_model(architecture)
        if observable:
            model.backbone = ObservableBackbone()
        if kind == "main":
            readout = SourceAlignedH0Readout(8, 3, output_level="graph", hidden_dim=8, pooling="mean")
        else:
            readout = SourceAlignedLinearGraphReadout(8, 3, pooling=kind.removeprefix("linear_"))
    if constant:
        with torch.no_grad():
            readout.output.weight.zero_()
            readout.output.bias.copy_(torch.tensor([1.0, -2.0, 0.5]))
    normalization = {
        "kind": "train_affine", "means": list(MEANS), "scales": list(SCALES),
        "train_only": True, "train_data_sha256": "a" * 64,
        "split_manifest_sha256": "b" * 64, "fit_source_sha256": "c" * 64,
    }
    config = {
        "schema_version": "phase1_downstream_training_v1", "mode": mode,
        "total_updates": 2, "seed": 907, "device": "cpu",
        "readout_config": readout.config_dict(), "tasks": list(TASKS),
        "loss": "mse", "reduction": "task_then_observed_label_mean",
        "task_weights": [1.0, 3.0, 2.0], "normalization": normalization,
        "optimizer": {"implementation": "single_tensor_adamw_v1", "lr": 0.005,
                      "betas": [0.8, 0.9], "eps": 1e-7, "weight_decay": 0.01, "amsgrad": False},
        "gradient_clip_norm": None,
        "caps": {"wall_seconds": 60.0, "max_sequence_batches": 8,
                 "max_graphs_per_batch": 4, "max_atoms_per_batch": 32, "max_unique_samples": 8},
        "bindings": {"train_data_sha256": "a" * 64, "split_manifest_sha256": "b" * 64,
                     "normalizer_sha256": canonical_hash(normalization), "source_sha256": "d" * 64,
                     "initial_encoder_sha256": backbone_state_hash(model)},
    }
    contract = {
        "schema_version": "phase1_graph_regression_evaluation_v1", "role": "train_inner_validation",
        "units": dict(zip(TASKS, ("kcal/mol", "e", "angstrom"))),
        "primary_metric_per_task": dict(zip(TASKS, ("MAE", "RMSE", "MAE"))),
        "dataset_sha256": "e" * 64, "split_manifest_sha256": "b" * 64,
        "caps": {"wall_seconds": 60.0, "max_sequence_batches": 8,
                 "max_unique_samples": 8, "max_graphs_per_batch": 4, "max_atoms_per_batch": 32},
    }
    return model, readout, config, contract


def pack_graphs(graph_ids):
    """Three unequal synthetic native graphs with a fixed missing-label oracle."""
    nodes = ([5, 7], [0, 5, 6], [7])
    positions = (
        [[0.0, 0.0, 0.0], [1.0, 0.2, 0.0]],
        [[0.0, 0.0, 0.0], [0.2, 1.0, 0.0], [0.1, 0.0, 1.0]],
        [[0.2, 0.3, 0.4]],
    )
    native_ids = ([1, 0], [2, 0, 1], [0])
    targets = ([11.0, 88.0, float("nan")],
               [9.0, float("nan"), float("nan")],
               [7.0, 82.0, float("nan")])
    observed = ([True, True, False], [True, False, False], [True, True, False])
    x, pos, owners, source_ids, ptr = [], [], [], [], [0]
    for owner, graph in enumerate(graph_ids):
        x.extend(nodes[graph])
        pos.extend(positions[graph])
        owners.extend([owner] * len(nodes[graph]))
        source_ids.extend(native_ids[graph])
        ptr.append(len(x))
    data = Data(x=torch.tensor(x, dtype=torch.long), pos=torch.tensor(pos, dtype=torch.float32),
                batch=torch.tensor(owners), ptr=torch.tensor(ptr),
                y=torch.tensor([-999.0]), unrelated_annotation="never forwarded")
    target = torch.tensor([targets[graph] for graph in graph_ids], dtype=torch.float32)
    return DownstreamTrainBatch(
        encoder_batch=data, sample_ids=tuple("toy-" + str(graph) for graph in graph_ids),
        source_atom_ids=torch.tensor(source_ids), targets=target,
        candidate_mask=torch.ones_like(target, dtype=torch.bool),
        supervision_mask=torch.tensor([observed[graph] for graph in graph_ids]),
        role="train_inner_validation",
    )


def standard_batches():
    return (pack_graphs((0,)), pack_graphs((1, 2)))


def evaluate(system, batches=None, *, config=None, contract=None):
    model, readout, original_config, original_contract = system
    return evaluate_graph_regression(
        model, readout, original_config if config is None else config,
        standard_batches() if batches is None else batches,
        evaluation_contract=original_contract if contract is None else contract,
    )


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
    return {
        "states": [deepcopy(module.state_dict()) for module in modules],
        "modes": [[child.training for child in module.modules()] for module in modules],
        "requires_grad": [p.requires_grad for p in parameters],
        "grads": [None if p.grad is None else p.grad.detach().clone() for p in parameters],
        "grad_objects": [p.grad for p in parameters],
        "rng": torch.get_rng_state().clone(),
    }


def assert_preserved(before, model, readout):
    after = snapshot(model, readout)
    for field in ("states", "modes", "requires_grad", "grads", "rng"):
        assert_nested_equal(before[field], after[field])
    assert all(a is b for a, b in zip(before["grad_objects"], after["grad_objects"]))


def independent_linear_metrics(model, readout, config, batches):
    """Manual raw-H0 pool/matmul and scalar observed-error oracle, no eval helper."""
    before = snapshot(model, readout)
    errors = [[] for _ in TASKS]
    try:
        model.eval()
        readout.eval()
        with torch.no_grad():
            for item in batches:
                data = item.encoder_batch
                clean = Data(x=data.x, pos=data.pos, batch=data.batch, ptr=data.ptr)
                h0 = model.encode_atoms(clean)
                pooled = []
                for start, end in zip(data.ptr[:-1].tolist(), data.ptr[1:].tolist()):
                    values = h0[start:end]
                    pooled.append(values.mean(0) if readout.pooling == "mean" else values.sum(0))
                z = torch.stack(pooled) @ readout.output.weight.T + readout.output.bias
                raw = z.double() * torch.tensor(SCALES, dtype=torch.float64) + torch.tensor(MEANS, dtype=torch.float64)
                for row in range(raw.size(0)):
                    for task in range(len(TASKS)):
                        if bool(item.supervision_mask[row, task]):
                            errors[task].append(float(raw[row, task]) - float(item.targets[row, task]))
    finally:
        for module, modes in zip((model, readout), before["modes"]):
            for child, mode in zip(module.modules(), modes):
                child.training = mode
    assert_preserved(before, model, readout)
    return [(len(items), math.fsum(abs(x) for x in items) / len(items),
             math.sqrt(math.fsum(x * x for x in items) / len(items))) if items else (0, None, None)
            for items in errors]


@pytest.mark.parametrize("kind", ["main", "linear_mean", "linear_sum"])
def test_real_shared_forwards_match_hand_raw_unit_oracle_and_missing_is_not_zero(kind, monkeypatch):
    system = make_system(kind)
    model = system[0]
    original_encode = model.encode_atoms

    def target_free_encode(data):
        assert set(data.keys()) == {"x", "pos", "batch", "ptr"}
        return original_encode(data)

    monkeypatch.setattr(model, "encode_atoms", target_free_encode)
    result = evaluate(system)
    energy, charge, missing = (result["metrics"][task] for task in TASKS)
    # Raw predictions are exactly [12,90,-6.875]; observed errors are 1,3,5 and 2,8.
    assert energy["n_valid"] == 3 and energy["unit"] == "kcal/mol"
    assert energy["MAE"] == pytest.approx(3.0)
    assert energy["RMSE"] == pytest.approx(math.sqrt(35.0 / 3))
    assert energy["MAE"] != pytest.approx((1.0 + 4.0) / 2)  # Wrong mean of batch means.
    assert charge["n_valid"] == 2 and charge["unit"] == "e"
    assert charge["MAE"] == pytest.approx(5.0) and charge["RMSE"] == pytest.approx(math.sqrt(34.0))
    assert energy["primary_value"] == energy["MAE"] and charge["primary_value"] == charge["RMSE"]
    assert missing["n_valid"] == 0 and missing["status"] == "NO_VALID_LABELS"
    assert missing["MAE"] is missing["RMSE"] is missing["primary_value"] is None
    assert result["status"] == "PARTIAL_NO_VALID_LABELS"
    assert result["batches"] == 2 and result["samples"] == 3 and result["atoms"] == 6
    assert result["state"] == "NOT_FROZEN" and result["formal_eligible"] is False
    assert result["source_dataset_role_truth_independently_verified"] is False
    assert result["checkpoint_file_sha256_independently_verified"] is False
    assert result["actual_state_before"] == result["actual_state_after"]
    assert result["computation_recipe"] == "fp32_h0_readout_fp64_affine_errors_observed_label_sums_v1"
    assert "predictions" not in result and "overall_MAE" not in result and "overall_RMSE" not in result


@pytest.mark.parametrize("pooling", ["mean", "sum"])
def test_nonconstant_linear_graph_metrics_match_independent_raw_h0_matmul_oracle(pooling):
    system = make_system("linear_" + pooling, constant=False)
    with torch.no_grad():
        system[1].output.weight.copy_(torch.arange(24, dtype=torch.float32).reshape(3, 8) / 17 - 0.5)
    expected = independent_linear_metrics(system[0], system[1], system[2], standard_batches())
    result = evaluate(system)
    for task, (count, mae, rmse) in zip(TASKS, expected):
        metric = result["metrics"][task]
        assert metric["n_valid"] == count
        if mae is None:
            assert metric["MAE"] is metric["RMSE"] is None
        else:
            assert metric["MAE"] == pytest.approx(mae, rel=2e-5, abs=2e-6)
            assert metric["RMSE"] == pytest.approx(rmse, rel=2e-5, abs=2e-6)


@pytest.mark.parametrize("kind", ["main", "linear_mean"])
def test_chunking_and_graph_permutation_preserve_metrics_but_hashes_describe_actual_frames(kind):
    system = make_system(kind)
    original = evaluate(system)
    rechunked = evaluate(system, (pack_graphs((0, 1, 2)),))
    reversed_order = evaluate(system, (pack_graphs((2,)), pack_graphs((1, 0))))
    for other in (rechunked, reversed_order):
        assert other["metrics"] == original["metrics"]
        assert other["sample_membership_sha256"] == original["sample_membership_sha256"]
        assert other["evaluation_sequence_sha256"] != original["evaluation_sequence_sha256"]
        assert other["raw_prediction_sha256"] != original["raw_prediction_sha256"]
        assert other["normalized_prediction_sha256"] != original["normalized_prediction_sha256"]


@pytest.mark.parametrize("kind", ["main", "linear_mean"])
def test_no_observed_task_is_explicit_na_without_zero_metrics(kind):
    system = make_system(kind)
    batches = tuple(replace(item, supervision_mask=torch.zeros_like(item.supervision_mask),
                            targets=torch.full_like(item.targets, float("nan"))) for item in standard_batches())
    result = evaluate(system, batches)
    assert result["status"] == "NO_VALID_LABELS"
    for metric in result["metrics"].values():
        assert metric["status"] == "NO_VALID_LABELS" and metric["n_valid"] == 0
        assert metric["MAE"] is metric["RMSE"] is metric["primary_value"] is None


@pytest.mark.parametrize("mode", ["frozen", "finetune"])
def test_current_trained_state_can_be_evaluated_without_requiring_random_initial_encoder(mode):
    system = make_system("main", constant=False, mode=mode)
    model, readout, config, _ = system
    initial_encoder = backbone_state_hash(model)
    initial_readout = deepcopy(readout.state_dict())
    trainer = DownstreamTrainer(model, readout, config, tracker=IdentifiedSyntheticTracker())
    trainer.fit(tuple(replace(item, role="train") for item in standard_batches()), max_updates=2)
    assert any(not torch.equal(value, readout.state_dict()[name]) for name, value in initial_readout.items()
               if isinstance(value, torch.Tensor))
    assert (backbone_state_hash(model) == initial_encoder) == (mode == "frozen")
    before = snapshot(model, readout)
    result = evaluate(system)
    assert result["actual_state_before"]["encoder_state_sha256"] == backbone_state_hash(model)
    assert result["actual_state_before"] == result["actual_state_after"]
    assert_preserved(before, model, readout)


@pytest.mark.parametrize("fault", ["none", "random_then_raise", "buffer", "unused_head", "readout_weight"])
def test_all_modes_states_existing_gradients_and_cpu_rng_survive_success_and_exceptions(fault, monkeypatch):
    system = make_system(observable=True, constant=False)
    model, readout = system[:2]
    model.train()
    model.backbone.bn.eval()  # Heterogeneous child modes must be restored individually.
    readout.eval()
    readout.atom_mlp.train()
    for index, parameter in enumerate(list(model.parameters()) + list(readout.parameters())):
        parameter.requires_grad_(index % 2 == 0)
        if index % 3 == 0:
            parameter.grad = torch.full_like(parameter, 0.125)
    before = snapshot(model, readout)
    original = model.backbone.forward

    def injected_forward(data):
        if fault == "random_then_raise":
            torch.rand(3)
            raise RuntimeError("synthetic forward failure after consuming caller RNG")
        if fault == "buffer":
            model.backbone.marker.add_(1)
        elif fault == "unused_head":
            next(model.energy_head.parameters()).add_(0.5)
        elif fault == "readout_weight":
            readout.output.weight.add_(0.5)
        return original(data)

    monkeypatch.setattr(model.backbone, "forward", injected_forward)
    if fault == "none":
        evaluate(system)
    else:
        with pytest.raises(DownstreamEvaluationError):
            evaluate(system)
    assert_preserved(before, model, readout)


@pytest.mark.parametrize("fault", [
    "final_test", "train", "duplicate_global_id", "negative_element", "oov_element", "pad_element",
    "nan_coordinates", "inf_coordinates", "duplicate_native_id", "bad_partition", "bad_mask_dtype",
    "supervised_non_candidate", "active_nan", "active_inf", "target_shape", "float_atom_ids", "float_source_ids",
])
def test_invalid_inner_validation_batches_are_rejected_without_model_or_rng_mutation(fault):
    system = make_system()
    batches = list(standard_batches())
    item = deepcopy(batches[0])
    if fault in ("final_test", "train"):
        item = replace(item, role=fault)
    elif fault == "duplicate_global_id":
        batches[1] = replace(batches[1], sample_ids=("toy-0", "toy-2"))
    elif fault.endswith("element"):
        item.encoder_batch.x[0] = {"negative_element": -1, "oov_element": system[0].n_atom_types,
                                  "pad_element": system[0].pad_elem_index}[fault]
    elif fault.endswith("coordinates"):
        item.encoder_batch.pos[0, 0] = float("nan") if fault == "nan_coordinates" else float("inf")
    elif fault == "duplicate_native_id":
        item.source_atom_ids[0] = item.source_atom_ids[1]
    elif fault == "bad_partition":
        item.encoder_batch.batch[1] = 1
    elif fault == "bad_mask_dtype":
        item = replace(item, supervision_mask=item.supervision_mask.long())
    elif fault == "supervised_non_candidate":
        item.candidate_mask[0, 0] = False
    elif fault.startswith("active_"):
        item.targets[0, 0] = float("nan") if fault == "active_nan" else float("inf")
    elif fault == "target_shape":
        item = replace(item, targets=item.targets[:, :2])
    elif fault == "float_atom_ids":
        item.encoder_batch.x = item.encoder_batch.x.float()
    else:
        item = replace(item, source_atom_ids=item.source_atom_ids.float())
    batches[0] = item
    before = snapshot(*system[:2])
    with pytest.raises(DownstreamEvaluationError):
        evaluate(system, batches)
    assert_preserved(before, *system[:2])


@pytest.mark.parametrize("fault", [
    "role_final_test", "role_train", "units_missing", "units_extra", "units_empty", "units_type",
    "primary_unknown", "primary_missing", "dataset_hash", "split_drift", "wall_zero", "boolean_cap", "supplied_predictions",
])
def test_evaluation_contract_and_units_are_explicit_and_exact(fault):
    system = make_system()
    contract = deepcopy(system[3])
    if fault.startswith("role_"):
        contract["role"] = fault.removeprefix("role_")
    elif fault == "units_missing":
        contract["units"].pop(TASKS[0])
    elif fault == "units_extra":
        contract["units"]["unknown_task"] = "eV"
    elif fault == "units_empty":
        contract["units"][TASKS[0]] = ""
    elif fault == "units_type":
        contract["units"][TASKS[0]] = None
    elif fault == "primary_unknown":
        contract["primary_metric_per_task"][TASKS[0]] = "AUC"
    elif fault == "primary_missing":
        contract["primary_metric_per_task"].pop(TASKS[0])
    elif fault == "dataset_hash":
        contract["dataset_sha256"] = "short"
    elif fault == "split_drift":
        contract["split_manifest_sha256"] = "f" * 64
    elif fault == "wall_zero":
        contract["caps"]["wall_seconds"] = 0
    elif fault == "boolean_cap":
        contract["caps"]["max_unique_samples"] = True
    else:
        contract["supplied_predictions"] = [[12.0, 90.0, -6.875]]
    before = snapshot(*system[:2])
    with pytest.raises(DownstreamEvaluationError):
        evaluate(system, contract=contract)
    assert_preserved(before, *system[:2])


@pytest.mark.parametrize("fault", ["readout_config", "normalizer_hash", "train_only", "loss", "optimizer", "seed", "model_dtype"])
def test_drifted_training_config_or_current_model_dtype_is_rejected(fault):
    system = make_system()
    config = deepcopy(system[2])
    if fault == "readout_config":
        config["readout_config"]["pooling"] = "sum"
    elif fault == "normalizer_hash":
        config["normalization"]["means"][0] += 1
    elif fault == "train_only":
        config["normalization"]["train_only"] = False
        config["bindings"]["normalizer_sha256"] = canonical_hash(config["normalization"])
    elif fault == "loss":
        config["loss"] = "bce_logits"
    elif fault == "optimizer":
        config["optimizer"]["betas"][0] = 1.5
    elif fault == "seed":
        config["seed"] = True
    else:
        system[0].double()
    before = snapshot(*system[:2])
    with pytest.raises(DownstreamEvaluationError):
        evaluate(system, config=config)
    assert_preserved(before, *system[:2])


@pytest.mark.parametrize("field", ["max_sequence_batches", "max_unique_samples", "max_graphs_per_batch", "max_atoms_per_batch"])
def test_actual_evaluation_shape_caps_are_checked(field):
    system = make_system()
    contract = deepcopy(system[3])
    contract["caps"][field] = {"max_sequence_batches": 1, "max_unique_samples": 2,
                               "max_graphs_per_batch": 1, "max_atoms_per_batch": 3}[field]
    before = snapshot(*system[:2])
    with pytest.raises(DownstreamEvaluationError):
        evaluate(system, contract=contract)
    assert_preserved(before, *system[:2])


@pytest.mark.parametrize("changed", ["target", "supervision", "candidate", "member"])
def test_actual_labels_masks_and_members_are_bound_independently_of_caller_dataset_digest(changed):
    system = make_system()
    baseline = evaluate(system)
    batches = list(standard_batches())
    item = deepcopy(batches[0] if changed != "candidate" else batches[1])
    if changed == "target":
        item.targets[0, 0] += 0.5
    elif changed == "supervision":
        item.supervision_mask[0, 1] = False
    elif changed == "candidate":
        item.candidate_mask[0, 1] = False  # Already unobserved on graph 1; metrics stay fixed.
    else:
        item = replace(item, sample_ids=("other-synthetic-member",))
    batches[1 if changed == "candidate" else 0] = item
    actual = evaluate(system, batches)
    assert actual["evaluation_contract_sha256"] == baseline["evaluation_contract_sha256"]
    assert actual["evaluation_sequence_sha256"] != baseline["evaluation_sequence_sha256"]
    if changed in ("supervision", "candidate"):
        assert actual["label_masks_sha256"] != baseline["label_masks_sha256"]
    if changed == "member":
        assert actual["sample_membership_sha256"] != baseline["sample_membership_sha256"]
    elif changed != "target":
        assert actual["sample_membership_sha256"] == baseline["sample_membership_sha256"]


def test_changed_units_are_bound_as_declarations_not_silently_pooled_or_verified_truth():
    system = make_system()
    baseline = evaluate(system)
    contract = deepcopy(system[3])
    contract["units"][TASKS[1]] = "declared_alternative_unit"
    actual = evaluate(system, contract=contract)
    assert actual["evaluation_contract_sha256"] != baseline["evaluation_contract_sha256"]
    assert actual["raw_prediction_sha256"] == baseline["raw_prediction_sha256"]
    assert actual["metrics"][TASKS[1]]["unit"] == "declared_alternative_unit"
    assert actual["source_dataset_role_truth_independently_verified"] is False


def test_prediction_hash_changes_with_actual_readout_values_even_if_caller_binding_is_unchanged():
    system = make_system()
    baseline = evaluate(system)
    with torch.no_grad():
        system[1].output.bias[0] += 0.25
    actual = evaluate(system)
    assert actual["training_config_sha256"] == baseline["training_config_sha256"]
    assert actual["raw_prediction_sha256"] != baseline["raw_prediction_sha256"]
    assert actual["normalized_prediction_sha256"] != baseline["normalized_prediction_sha256"]
    assert actual["actual_state_before"]["readout_state_sha256"] != baseline["actual_state_before"]["readout_state_sha256"]
    assert actual["metrics"][TASKS[0]]["MAE"] == pytest.approx(3.5)


def test_current_weight_hash_is_actual_state_even_when_constant_readout_hides_encoder_change():
    system = make_system()
    baseline = evaluate(system)
    with torch.no_grad():
        system[0].backbone.out_norm.bias.add_(0.25)
    actual = evaluate(system)
    assert actual["training_config_sha256"] == baseline["training_config_sha256"]
    assert actual["actual_state_before"]["encoder_state_sha256"] != baseline["actual_state_before"]["encoder_state_sha256"]
    assert actual["raw_prediction_sha256"] == baseline["raw_prediction_sha256"]
    assert actual["metrics"] == baseline["metrics"]


def test_cooperative_wall_failure_after_forward_restores_state_and_rng(monkeypatch):
    import phychem_mfm.phase1.downstream_evaluation as evaluation_module

    system = make_system(observable=True)
    model = system[0]
    clock = [0.0]
    original = model.backbone.forward

    def forward_then_exhaust_clock(data):
        result = original(data)
        torch.rand(2)
        clock[0] = 61.0
        return result

    monkeypatch.setattr(evaluation_module.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(model.backbone, "forward", forward_then_exhaust_clock)
    before = snapshot(*system[:2])
    with pytest.raises(DownstreamEvaluationError, match="wall"):
        evaluate(system)
    assert_preserved(before, *system[:2])


def test_receipt_and_supplied_batches_are_detached_and_preserved():
    system = make_system()
    batches = standard_batches()
    original_config, original_contract = deepcopy(system[2]), deepcopy(system[3])
    original_batches = deepcopy(batches)
    before = snapshot(*system[:2])
    parameters = list(system[0].parameters()) + list(system[1].parameters())
    versions = [parameter._version for parameter in parameters]
    result = evaluate(system, batches)
    assert_preserved(before, *system[:2])
    assert [parameter._version for parameter in parameters] == versions
    assert_nested_equal(original_config, system[2])
    assert_nested_equal(original_contract, system[3])
    for original, item in zip(original_batches, batches):
        assert set(original.encoder_batch.keys()) == set(item.encoder_batch.keys())
        for name in original.encoder_batch.keys():
            assert_nested_equal(original.encoder_batch[name], item.encoder_batch[name])
        for name in ("sample_ids", "source_atom_ids", "targets", "candidate_mask", "supervision_mask", "role"):
            assert_nested_equal(getattr(original, name), getattr(item, name))
    assert result["receipt_sha256"] == canonical_hash({key: value for key, value in result.items() if key != "receipt_sha256"})
    result["evaluation_contract"]["units"][TASKS[0]] = "caller-mutated-receipt"
    assert system[3]["units"][TASKS[0]] == "kcal/mol"
