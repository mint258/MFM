"""Preregister tensor6 metric definitions before real D3 exists.

One complete same-actual-geometry tensor is one observation. R2 uses raw-unit
Frobenius SSE/SST; Frobenius_MAE_d9 is mean(||prediction-target||_F/3).
Source-six component MAE/RMSE keep their existing definitions. These synthetic
tests neither run real D3 nor change its acceptance threshold.
"""
from dataclasses import replace
import math

import pytest
import torch

from model_v3_typed_fixture import REF
from phychem_mfm.model.v3_rank2_targets import rotate_six, six_to_matrix
from phychem_mfm.phase1.v3_contract import FieldSpec, FieldTarget, LabelRegistry, TrainNormalization
from phychem_mfm.phase1.v3_label_domains import tensor6_from_f64
from phychem_mfm.phase1.v3_losses import compute_v3_loss
from phychem_mfm.phase1.v3_precision_experiment import PrecisionValidationAccumulator
from phychem_mfm.phase1.v3_training import ValidationAccumulator


def tensor_target(values, *, partial=(), mismatch=(), exposure=None):
    values = torch.as_tensor(values, dtype=torch.float64)
    n = len(values)
    masks = torch.ones((n, 6), dtype=torch.bool)
    for row, component in partial:
        masks[row, component] = False
    ids = tuple(f"g{i}" for i in range(n))
    component_ids = [list((identity,) * 6) for identity in ids]
    for row in mismatch:
        component_ids[row][-1] = "different-actual-geometry"
    result = tensor6_from_f64(values=values, component_valid=masks, geometry_ids=ids,
        component_geometry_ids=tuple(tuple(row) for row in component_ids), reasons=({},) * n, source_ref=REF)
    return result if exposure is None else replace(result, exposure_valid=torch.tensor(exposure, dtype=torch.bool))


def evaluate(prediction, target, *, accumulator=ValidationAccumulator):
    registry = LabelRegistry((FieldSpec("q", "P", "r674", "graph", representation="symmetric_tensor6"),),
        "synthetic-typed-metric", "a" * 64)
    predictions, targets = {"q": prediction}, {"q": target}
    norms = {"q": TrainNormalization((0.,), (1.,), "b" * 64, "synthetic")}
    loss = compute_v3_loss(predictions, targets, registry, norms, enabled_groups=("P",))
    metric = accumulator(registry, role="VAL", enabled_groups=("P",))
    metric.add(predictions, targets, loss)
    return metric.result()["fields"]["q"], loss, metric


def rotation():
    axis = torch.tensor([2., 3., 5.], dtype=torch.float64)
    axis = axis / axis.norm()
    x, y, z = axis.tolist()
    skew = torch.tensor([[0., -z, y], [z, 0., -x], [-y, x, 0.]], dtype=torch.float64)
    angle = .61
    return (math.cos(angle) * torch.eye(3, dtype=torch.float64)
        + (1 - math.cos(angle)) * axis[:, None] * axis[None, :] + math.sin(angle) * skew)


def mixed_inputs():
    values = torch.tensor([[2., 1., 0., -.5, .25, 4.], [-1., .5, 3., 2., -1., 0.],
        [0., -2., 1., .75, 1.5, -3.], [7., float("nan"), 1., 2., 3., 4.],
        [1e5] * 6, [-1e5] * 6], dtype=torch.float64)
    error = torch.tensor([[.6, -.3, .2, .8, -.5, .1], [-.7, .9, -.2, .3, .2, .8],
                          [.4, .6, -.1, -.9, .7, -.2]], dtype=torch.float64)
    prediction = torch.full((6, 6), float("nan"), dtype=torch.float32)
    prediction[:3] = (values[:3] + error).float()
    target = tensor_target(values, partial=((3, 1),), mismatch=(4,),
                           exposure=(True, True, True, True, True, False))
    return values, prediction, target


def test_tensor_r2_counts_offdiagonal_twice_while_source_component_mae_stays_unchanged():
    target = tensor_target([[0.] * 6, [2., 0., 0., 0., 0., 0.]])
    prediction = target.values.clone()
    prediction[0, 1] = 1.
    row, loss, metric = evaluate(prediction, target)
    assert row["valid_labels"] == 2 and loss.counts["q"] == 2
    assert row["Frobenius_SSE"] == 2. and row["Frobenius_SST"] == 2.
    assert row["R2"] == 0.  # Unweighted six-component R2 would incorrectly be .5.
    assert row["MAE"] == pytest.approx(1 / 12)
    assert row["Frobenius_MAE_d9"] == pytest.approx(math.sqrt(2) / 6)
    assert metric.rows["q"]["squared"] == 1.  # Original source-component SSE retained.
    assert row["valid_labels_definition"] == "eligible_complete_same_actual_geometry_tensors"
    assert "w=(1,2,1,2,2,1)" in row["R2_definition"]
    assert "raw_unit" in row["Frobenius_MAE_d9_definition"]
    assert "source6=(xx,xy,yy,xz,yz,zz)" in row["MAE_definition"]


def test_tensor_r2_and_frobenius_mae_d9_match_matrix_definition_and_general_3d_rotation():
    values, prediction, target = mixed_inputs()
    first, _, _ = evaluate(prediction, target)
    error_matrix = six_to_matrix(prediction[:3].double() - target.values[:3].double())
    matrix_target = six_to_matrix(target.values[:3].double())
    sse = float(error_matrix.square().sum())
    sst = float((matrix_target - matrix_target.mean(0)).square().sum())
    radial_absolute = float(error_matrix.square().sum((-2, -1)).sqrt().mean() / 3.)
    assert first["Frobenius_SSE"] == pytest.approx(sse, rel=1e-12)
    assert first["Frobenius_SST"] == pytest.approx(sst, rel=1e-12)
    assert first["R2"] == pytest.approx(1 - sse / sst, rel=1e-12)
    assert first["Frobenius_MAE_d9"] == pytest.approx(radial_absolute, rel=1e-12)

    # Partial observations have no rotated observation operator in D1-A.
    # Only complete eligible rows are jointly re-expressed; excluded source
    # values/masks/reasons remain retained and never enter these metrics.
    moved_values, moved_prediction = values.clone(), prediction.clone()
    moved_values[:3] = rotate_six(values[:3], rotation())
    moved_prediction[:3] = rotate_six(prediction[:3].double(), rotation()).float()
    moved_target = tensor_target(moved_values, partial=((3, 1),), mismatch=(4,),
                                 exposure=(True, True, True, True, True, False))
    moved, _, _ = evaluate(moved_prediction, moved_target)
    assert first["valid_labels"] == moved["valid_labels"] == 3
    for key in ("R2", "Frobenius_SSE", "Frobenius_SST", "Frobenius_MAE_d9"):
        assert moved[key] == pytest.approx(first[key], rel=2e-6, abs=2e-6)


def test_partial_mismatched_and_recipe_excluded_tensors_never_change_metric_population():
    values, prediction, target = mixed_inputs()
    full, loss, _ = evaluate(prediction, target)
    eligible_only, _, _ = evaluate(prediction[:3], tensor_target(values[:3]))
    assert full == eligible_only
    assert loss.counts["q"] == 3 and target.valid.tolist() == [True, True, True, False, False, False]
    assert target.component_valid.sum().item() == 35 and torch.isnan(target.values[3, 1])
    assert target.geometry_valid.tolist() == [True, True, True, True, False, True]


def test_precision_consumer_keeps_original_source_six_rmse_and_adds_explicit_frobenius_metrics():
    target = tensor_target([[0.] * 6, [2., 0., 0., 0., 0., 0.]])
    prediction = target.values.clone()
    prediction[0, 1] = 1.
    row, _, _ = evaluate(prediction, target, accumulator=PrecisionValidationAccumulator)
    assert row["squared_error_sum"] == 1. and row["component_denominator"] == 12
    assert row["RMSE"] == pytest.approx(math.sqrt(1 / 12))
    assert row["Frobenius_SSE"] == 2. and row["R2"] == 0.
    assert row["Frobenius_MAE_d9"] == pytest.approx(math.sqrt(2) / 6)


def test_constant_or_empty_tensor_metrics_do_not_fill_an_epsilon_or_fabricate_r2():
    target = tensor_target([[1., 2., 3., 4., 5., 6.]] * 2)
    constant, _, _ = evaluate(target.values.clone(), target)
    assert constant["R2"] is None and constant["Frobenius_SST"] == 0.
    assert constant["R2_unavailable_reason"] == "insufficient_or_constant_labels"
    assert constant["Frobenius_MAE_d9"] == constant["MAE"] == 0.
    empty, _, _ = evaluate(torch.full_like(target.values, float("nan")), target.masked(False))
    assert empty["valid_labels"] == 0 and empty["R2"] is empty["Frobenius_MAE_d9"] is None
    assert empty["Frobenius_SSE"] is empty["Frobenius_SST"] is None


@pytest.mark.parametrize("domain", ["scalar", "vector", "binary", "classification"])
def test_existing_field_metric_values_and_output_keys_remain_unchanged(domain):
    if domain == "vector":
        field = FieldSpec("old", "P", "legacy", "graph", representation="vector")
        prediction = torch.tensor([[0., 0., 0.], [2., 4., 6.]])
        values = torch.tensor([[0., 0., 0.], [4., 4., 4.]])
        mae, r2, accuracy = 2 / 3, 2 / 3, None
    elif domain == "classification":
        field = FieldSpec("old", "P", "legacy", "graph", kind="classification", classes=3)
        prediction, values = torch.tensor([[2., 0., 0.], [0., 0., 2.]]), torch.tensor([[0], [1]])
        mae, r2, accuracy = None, None, .5
    elif domain == "binary":
        field = FieldSpec("old", "P", "legacy", "graph", kind="binary")
        prediction, values = torch.tensor([[2.], [-2.]]), torch.tensor([[1.], [0.]])
        mae, r2, accuracy = None, None, 1.
    else:
        field = FieldSpec("old", "P", "legacy", "graph")
        prediction, values = torch.tensor([[0.], [2.]]), torch.tensor([[0.], [4.]])
        mae, r2, accuracy = 1., .5, None
    registry = LabelRegistry((field,), "synthetic-legacy-metric", "a" * 64)
    target = FieldTarget(values, torch.ones(2, dtype=torch.bool))
    norms = {"old": TrainNormalization((0.,), (1.,), "b" * 64, "synthetic")}
    loss = compute_v3_loss({"old": prediction}, {"old": target}, registry, norms, enabled_groups=("P",))
    metric = ValidationAccumulator(registry, role="VAL", enabled_groups=("P",))
    metric.add({"old": prediction}, {"old": target}, loss)
    expected = {"valid_labels": 2, "loss": float(loss.fields["old"]), "MAE": mae, "R2": r2, "accuracy": accuracy}
    if domain in ("binary", "classification"):
        expected["R2_unavailable_reason"] = "categorical_field"
    row = metric.result()["fields"]["old"]
    assert set(row) == set(expected)
    for key, value in expected.items():
        assert row[key] == (pytest.approx(value) if isinstance(value, float) else value)
    assert set(metric.rows["old"]) == {"count", "loss_sum", "absolute", "squared", "target_sum", "target_squared", "correct"}
