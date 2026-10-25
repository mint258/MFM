"""C2 sparse fitting is normalized per atom, equivariant and TRAIN-only."""
from copy import deepcopy
from dataclasses import replace

import numpy as np
import pytest
from scipy import sparse

from phychem_mfm.phase1.v3_coordinate_lookup import (CoordinateLookup, CoordinateLookupConfig,
    LookupRecord, design_matrix, evaluate_coordinate_lookup, fit_coordinate_lookup,
    matrix_capacity_estimate, radial_features)


def record(*, role="TRAIN", name="train1", elements=None, rotation=None):
    noisy = np.array([[0., 0., 0.], [1.01, .12, .18], [.17, 1.24, .31], [.23, .21, 1.59]], dtype=np.float64)
    elements = np.array([5, 7, 5, 7], dtype=np.int64) if elements is None else elements
    matrix, codes = design_matrix(elements, noisy)
    coefficients = np.zeros(matrix.shape[1]); coefficients[np.unique(codes)] = .015
    clean = noisy - np.asarray(matrix @ coefficients).reshape(-1, 3)
    if rotation is not None:
        noisy, clean = noisy @ rotation, clean @ rotation
    return LookupRecord(name, name+":molecule", role, elements.copy(), noisy, clean, "a"*64)


def fit(records, *, config=CoordinateLookupConfig(), **kwargs):
    return fit_coordinate_lookup(iter(records), config=config, expected_records=len(records),
        source_plan_sha256="b"*64, **kwargs)


def test_sparse_ridge_equals_active_column_closed_form_with_lambda_times_atoms():
    source = record(); config = CoordinateLookupConfig(ridge=.02, atol=1e-12, btol=1e-12)
    model = fit([source], config=config)
    matrix, codes = design_matrix(source.elements, source.noisy, config)
    active = np.unique(codes)
    tiny = matrix[:, active].toarray()
    target = (source.noisy - source.clean).reshape(-1)
    expected = np.linalg.solve(tiny.T @ tiny + config.ridge * len(source.elements) * np.eye(len(active)), tiny.T @ target)
    np.testing.assert_allclose(model.coefficients[active], expected, atol=1e-10, rtol=1e-8)
    assert model.fit_receipt["equivalent_damp_squared_unscaled_operator"] == .08
    wrong_three = np.linalg.solve(tiny.T @ tiny + config.ridge * 3 * len(source.elements) * np.eye(len(active)), tiny.T @ target)
    assert np.linalg.norm(expected-wrong_three) > 1e-4
    assert model.fit_receipt["solver"]["stop_code"] in (1, 2, 4, 5)


def test_dataset_duplication_does_not_change_mean_atom_ridge_solution():
    one = record(); two = replace(one, record_id="train2", molecule_id="train2:molecule")
    config = CoordinateLookupConfig(ridge=.02, atol=1e-12, btol=1e-12)
    a, b = fit([one], config=config), fit([one, two], config=config)
    np.testing.assert_allclose(a.coefficients, b.coefficients, atol=1e-10, rtol=1e-8)
    assert b.fit_receipt["TRAIN_atoms"] == 2 * a.fit_receipt["TRAIN_atoms"]


def test_geometry_features_cannot_read_clean_targets_and_ordered_element_pair_codes_are_explicit():
    source = record()
    src, dst, codes, relative = radial_features(source.elements, source.noisy)
    bins = np.floor(np.linalg.norm(relative, axis=1)/.1).astype(np.int64)
    assert np.array_equal(codes, (source.elements[src]*119+source.elements[dst])*50+bins)
    assert np.all(np.linalg.norm(relative, axis=1) < 5.)
    same_inputs = replace(source, clean=source.clean+100.)
    left, _ = design_matrix(source.elements, source.noisy)
    right, _ = design_matrix(same_inputs.elements, same_inputs.noisy)
    assert (left != right).nnz == 0
    assert np.all(src != dst)


def test_predictions_and_fitted_coefficients_are_rotation_translation_and_permutation_consistent():
    source = record(); model = fit([source])
    rotation = np.array([[0., 1., 0.], [0., 0., 1.], [1., 0., 0.]])
    before, _ = model.predict_noise(source.elements, source.noisy)
    after, _ = model.predict_noise(source.elements, source.noisy @ rotation + np.array([3., -2., .7]))
    np.testing.assert_allclose(after, before @ rotation, atol=1e-10, rtol=1e-8)
    rotated = replace(source, noisy=source.noisy @ rotation, clean=source.clean @ rotation)
    rotated_fit = fit([rotated])
    np.testing.assert_allclose(rotated_fit.coefficients, model.coefficients, atol=1e-10, rtol=1e-8)
    order = np.array([2, 0, 3, 1])
    permuted, _ = model.predict_noise(source.elements[order], source.noisy[order])
    np.testing.assert_allclose(permuted, before[order], atol=1e-10, rtol=1e-8)
    a = evaluate_coordinate_lookup(model, [replace(source, role="PRETRAIN_VAL", record_id="val", molecule_id="val:m")], expected_records=1)
    b = evaluate_coordinate_lookup(model, [replace(source, role="PRETRAIN_VAL", record_id="val", molecule_id="val:m",
        noisy=source.noisy @ rotation + 2., clean=source.clean @ rotation + 2.)], expected_records=1)
    for key in ("displacement_vector_MSE_A2", "coordinate_vector_RMSE_A", "local_pair_RMSE_A"):
        assert a[key] == pytest.approx(b[key], rel=1e-8, abs=1e-12)


def test_unknown_bins_and_isolated_atoms_have_full_zero_correction_denominators():
    model = fit([record()])
    source = record(role="PRETRAIN_VAL", name="val", elements=np.array([8, 8, 8, 8]))
    source = replace(source, clean=source.noisy-np.array([.1, .2, .3]))
    prediction, coverage = model.predict_noise(source.elements, source.noisy)
    assert np.array_equal(prediction, np.zeros((4, 3)))
    assert coverage["unknown_directed_edges"] == coverage["directed_edges"] == 12
    isolated = LookupRecord("one", "one:molecule", "PRETRAIN_VAL", np.array([8]),
        np.zeros((1, 3)), np.array([[.1, .2, .3]]), "c"*64)
    result = evaluate_coordinate_lookup(model, [source, isolated], expected_records=2)
    assert result["atoms"] == 5 and result["records"] == 2
    assert result["displacement_vector_MSE_A2"] == pytest.approx(.14)
    assert result["coordinate_vector_RMSE_A"] == pytest.approx(np.sqrt(.14))
    assert result["coordinate_component_RMSE_A"] == pytest.approx(np.sqrt(.14/3))
    assert result["explicit_sigma_normalized_component_MSE"] == pytest.approx(.14/.03)
    assert result["local_pair_RMSE_A"] == pytest.approx(0., abs=1e-14)
    assert result["all_atoms_in_coordinate_denominator"] is True


def test_coincident_atoms_have_no_undefined_direction_and_no_edges_still_fit_unique_zero_table():
    source = record(); source = replace(source, noisy=np.zeros_like(source.noisy), clean=np.ones_like(source.clean))
    model = fit([source])
    assert model.fit_receipt["TRAIN_atoms"] == 4 and model.fit_receipt["TRAIN_directed_edges"] == 0
    assert np.array_equal(model.coefficients, np.zeros_like(model.coefficients))
    assert model.fit_receipt["solver"]["stop_code"] == 0


def test_no_dense_gram_or_dense_sparse_matrix_conversion_occurs_during_fit(monkeypatch):
    original = sparse.csr_matrix.__matmul__
    def matmul(self, other):
        assert not sparse.issparse(other), "A Gram construction was attempted"
        return original(self, other)
    def dense_forbidden(*args, **kwargs):
        raise AssertionError("Dense sparse-matrix conversion was attempted")
    monkeypatch.setattr(sparse.csr_matrix, "__matmul__", matmul)
    monkeypatch.setattr(sparse.csr_matrix, "toarray", dense_forbidden)
    model = fit([record()])
    assert model.fit_receipt["dense_gram_constructed"] is False
    estimate = matrix_capacity_estimate(atoms=100, directed_edges=500, columns=708050)
    bigger = matrix_capacity_estimate(atoms=100, directed_edges=500, columns=1416100)
    assert bigger["numeric_upper_bytes"]-estimate["numeric_upper_bytes"] == 8*8*708050


def test_only_training_may_fit_and_pretrain_validation_may_evaluate_and_groups_do_not_overlap():
    with pytest.raises(ValueError, match="Only TRAIN"):
        fit([record(role="PRETRAIN_VAL")])
    with pytest.raises(ValueError, match="Duplicate TRAIN"):
        fit([record(), record()])
    model = fit([record()])
    with pytest.raises(ValueError, match="pretraining validation role"):
        evaluate_coordinate_lookup(model, [record()], expected_records=1)
    with pytest.raises(ValueError, match="overlap"):
        evaluate_coordinate_lookup(model, [record(role="PRETRAIN_VAL")], expected_records=1)
    bad = replace(record(role="PRETRAIN_VAL", name="val"), molecule_id="train1:molecule")
    with pytest.raises(ValueError, match="overlap"):
        evaluate_coordinate_lookup(model, [bad], expected_records=1)
    with pytest.raises(ValueError, match="Only TRAIN"):
        fit([replace(record(), role="test")])


def test_resource_bounds_and_exact_population_fail_without_adaptive_sample_dropping():
    with pytest.raises(ValueError, match="resource budget exceeded"):
        fit([record()], config=CoordinateLookupConfig(max_train_atoms=1))
    with pytest.raises(ValueError, match="ended before"):
        fit_coordinate_lookup([], expected_records=1, source_plan_sha256="b"*64)
    with pytest.raises(ValueError, match="exceeded its declared"):
        fit_coordinate_lookup([record(), record(name="extra")], expected_records=1, source_plan_sha256="b"*64)
    def timeout():
        raise TimeoutError("owned resource guard")
    with pytest.raises(TimeoutError, match="owned resource guard"):
        fit([record()], check=timeout)


def test_serialized_table_binds_method_source_and_keeps_unknown_zero_fallback():
    model = fit([record()]); document = model.document()
    recovered = CoordinateLookup.from_document(document)
    assert np.array_equal(recovered.coefficients, model.coefficients)
    assert np.array_equal(recovered.train_edge_counts, model.train_edge_counts)
    for key in ("source", "codes", "fit_receipt"):
        altered = deepcopy(document)
        if key == "source":
            altered[key]["sha256"] = "0"*64
        elif key == "codes":
            altered[key][0] += .5
        else:
            altered[key]["fit_role"] = "PRETRAIN_VAL"
        with pytest.raises(ValueError):
            CoordinateLookup.from_document(altered)
