"""Model-side typed contracts; synthetic coverage is not release acceptance."""
from dataclasses import asdict, replace

import pytest
import torch

from model_v3_typed_fixture import ordered_target, tensor_target
from phychem_mfm.phase1.v3_contract import FieldSpec, FieldTarget, TrainNormalization, observed_rows


def test_legacy_field_default_serialization_and_positional_construction_remain_exact():
    field = FieldSpec("p", "P", "family", "graph")
    assert asdict(field) == {"name": "p", "group": "P", "family": "family", "level": "graph",
        "kind": "regression", "representation": "scalar", "pooling": "mean", "classes": 0,
        "huber_delta": 1., "denoise_sigma": .1, "unit": "explicit_adapter_unit_required"}
    assert field.target_width == field.prediction_width == 1
    assert FieldSpec("v", "P", "family", "atom", "regression", "vector").target_width == 3


def test_tensor6_requires_graph_regression_and_exact_single_scale_zero_center():
    field = FieldSpec("q", "P", "q", "graph", representation="symmetric_tensor6")
    assert field.target_width == field.prediction_width == 6
    TrainNormalization((0.,), (2.,), "b" * 64, "synthetic").validate_for(field)
    for center, scale in (((1.,), (2.,)), ((0.,) * 6, (2.,) * 6), ((0.,), (2.,) * 6)):
        with pytest.raises(ValueError):
            TrainNormalization(center, scale, "b" * 64, "synthetic").validate_for(field)
    for changes in ({"level": "atom"}, {"kind": "binary"}, {"huber_delta": 2.}):
        with pytest.raises(ValueError): replace(field, **changes)


def test_ordered_entries_require_separate_scalar_regression_level():
    field = FieldSpec("r", "D", "r73", "ordered_entry")
    assert field.target_width == 1
    for changes in ({"representation": "vector"}, {"representation": "symmetric_tensor6"}, {"kind": "binary"}):
        with pytest.raises(ValueError): replace(field, **changes)


@pytest.mark.parametrize("domain", ["ordered", "tensor6"])
def test_observed_rows_retains_original_domains_and_rejects_generic_target_replacement(domain):
    value = ordered_target() if domain == "ordered" else tensor_target()
    field = (FieldSpec("r", "D", "r73", "ordered_entry") if domain == "ordered" else
             FieldSpec("q", "P", "r674", "graph", representation="symmetric_tensor6"))
    original_values, reasons, conversions = value.values.clone(), value.reasons, value.conversions
    masks = value.source_valid.clone() if domain == "ordered" else value.component_valid.clone()
    prediction = torch.zeros_like(value.values)
    prediction[~value.valid] = float("nan")
    selected_prediction, selected_target, count = observed_rows(field, prediction, value)
    assert count == (3 if domain == "ordered" else 1)
    assert torch.isfinite(selected_prediction).all() and torch.isfinite(selected_target).all()
    torch.testing.assert_close(value.values, original_values, equal_nan=True)
    assert value.reasons == reasons and value.conversions == conversions
    assert torch.equal(value.source_valid if domain == "ordered" else value.component_valid, masks)
    if domain == "ordered":
        assert value.entry_ordinal.tolist() == [0, 1, 2, 3]
        assert value.inputs.atom_index.tolist() == [[0, 0, 1, 0], [0, 0, 0, 1]]
    else:
        assert value.geometry_valid.tolist() == [True, True, False]
        assert value.component_geometry_ids[-1][-1] == "wrong-geometry"
    with pytest.raises(ValueError, match="typed"):
        observed_rows(field, prediction, FieldTarget(value.values, value.valid))


def test_exposure_mask_does_not_rewrite_tensor_source_masks_or_geometry():
    value = tensor_target().masked(False)
    prediction = torch.full_like(value.values, float("nan"))
    _, _, count = observed_rows(FieldSpec("q", "P", "r674", "graph", representation="symmetric_tensor6"), prediction, value)
    assert count == 0 and int(value.component_valid.sum()) == 17
    assert value.geometry_valid.tolist() == [True, True, False]


@pytest.mark.parametrize("domain", ["ordered", "tensor6"])
def test_source_labels_cannot_acquire_an_autograd_graph(domain):
    value = ordered_target() if domain == "ordered" else tensor_target()
    with pytest.raises(ValueError, match="autograd"):
        replace(value, values=value.values.clone().requires_grad_())
