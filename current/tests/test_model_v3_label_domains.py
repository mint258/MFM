"""Synthetic transport tests only: never a real D1/D3/D4 acceptance."""
from dataclasses import replace

import pytest
import torch

from phychem_mfm.phase1.v3_label_domains import (
    ChannelCodebook, OrderedEntryInputs, Tensor6Inputs, collate_domain_inputs,
    collate_ordered_entries, collate_tensor6, ordered_entries_from_f64, tensor6_from_f64)

REF = {"path": "/unit-only/not-a-real-release.json", "bytes": 1, "sha256": "a" * 64}
FRAME = {"target_id": "unit-target", "condition": "unit-condition", "unit": "source-native-unit", "sign": "source-native-sign", "frame": "source-frame-assumption-recorded",
         "origin_policy": "declared-source-origin-not-COM", "joint_policy": REF}


def ordered(geometry="actual-g", values=None):
    return ordered_entries_from_f64(
        values=torch.tensor([[1.0000000596046448], [2.], [3.], [4.]], dtype=torch.float64) if values is None else values,
        source_valid=torch.tensor([True, True, True, False]),
        atom_index=torch.tensor([[0, 0, 1, 0], [0, 0, 0, 1]]),
        channel_index=torch.tensor([[0, 0, 1, 2], [1, 1, 0, 0]]), entry_ordinal=torch.arange(4),
        n_atoms=2, geometry_id=geometry, codebook=ChannelCodebook(("SIGMA", "DEL", "DELL"), REF),
        frame_binding=FRAME, reasons=({}, {}, {}, {"original_invalid_reason": 7}), source_ref=REF, geometry_ref=REF)


def tensor6(geometry="actual-g", *, partial=False, mismatch=False):
    valid = torch.ones((1, 6), dtype=torch.bool)
    if partial: valid[0, 1] = False
    ids = [geometry] * 6
    if mismatch: ids[5] = "a-different-actual-geometry"
    return tensor6_from_f64(values=torch.tensor([[1., 2., 3., 4., 5., 6.]], dtype=torch.float64),
        component_valid=valid, geometry_ids=(geometry,), component_geometry_ids=(tuple(ids),),
        reasons=({"original_component_reasons": [0, 7 if partial else 0, 0, 0, 0, 0]},), source_ref=REF)


def test_codebook_is_reversible_literal_and_does_not_merge_native_aliases():
    book = ChannelCodebook(("DEL", "DELL", "DELTA", "SIGMA"), REF)
    assert book.decode(book.encode(("DELL", "DEL", "DELL", "DELTA"))) == ("DELL", "DEL", "DELL", "DELTA")
    with pytest.raises(ValueError, match="Unknown literal"):
        book.encode(("delta",))
    with pytest.raises(ValueError, match="Unique"):
        ChannelCodebook(("DEL", "DEL"), REF)


def test_ordered_source_preserves_onsite_duplicates_direction_and_once_rounding():
    value = ordered()
    assert value.atom_index.tolist() == [[0, 0, 1, 0], [0, 0, 0, 1]]
    assert value.channel_index.tolist() == [[0, 0, 1, 2], [1, 1, 0, 0]]
    assert value.entry_ordinal.tolist() == [0, 1, 2, 3]
    assert value.values[0, 0].item() == 1.0
    assert value.valid.tolist() == [True, True, True, False]
    assert value.reasons[-1]["original_invalid_reason"] == 7
    assert value.audit_counts()["onsite_entries"] == 2
    assert value.conversions[0]["float_conversions"] == 1
    assert not hasattr(value.inputs, "entry_ordinal") and not hasattr(value.inputs, "values")


def test_converted_f32_cannot_be_used_as_authoritative_f64_sidecar():
    with pytest.raises(ValueError, match="Only authoritative F64"):
        ordered(values=ordered().values)


@pytest.mark.parametrize("change", ["atom", "channel", "ordinal", "source_nonfinite", "wire_overflow"])
def test_ordered_metadata_or_valid_numeric_corruption_rejected(change):
    value = ordered()
    if change == "atom":
        with pytest.raises(ValueError): replace(value.inputs, atom_index=torch.tensor([[-1, 0, 1, 0], [0, 0, 0, 1]]))
        return
    elif change == "channel":
        with pytest.raises(ValueError): replace(value.inputs, channel_index=torch.full((2, 4), 99, dtype=torch.long))
        return
    elif change == "ordinal":
        with pytest.raises(ValueError): replace(value, entry_ordinal=torch.tensor([0, 1, 1, 3]))
        return
    else:
        raw = torch.ones((4, 1), dtype=torch.float64)
        raw[0] = float("nan") if change == "source_nonfinite" else 1e300
        with pytest.raises(ValueError): ordered(values=raw)
        return



def test_ordered_collate_offsets_atoms_without_sort_dedup_or_global_ordinal_rewrite():
    a, b = ordered("g0"), ordered("g1")
    batch = collate_ordered_entries((a, b), atom_counts=(2, 3))
    assert batch.atom_index[:, :4].tolist() == a.atom_index.tolist()
    assert batch.atom_index[:, 4:].tolist() == (b.atom_index + 2).tolist()
    assert batch.entry_ordinal.tolist() == [0, 1, 2, 3, 0, 1, 2, 3]
    assert batch.entry_graph.tolist() == [0] * 4 + [1] * 4
    assert batch.values.shape == (8, 1) and len(batch.reasons) == 8
    assert batch.audit_counts()["retained_entries"] == 8
    assert batch.to("cpu").inputs.codebook.sha256 == batch.inputs.codebook.sha256


def test_ordered_collate_rejects_out_of_graph_or_changed_frame_and_book():
    value = ordered()
    with pytest.raises(ValueError): collate_ordered_entries((value,), atom_counts=(1,))
    other = replace(value, inputs=replace(value.inputs, frame_binding={**FRAME, "unit": "another-unit"}))
    with pytest.raises(ValueError): collate_ordered_entries((value, other), atom_counts=(2, 2))
    other = replace(value, inputs=replace(value.inputs, codebook=ChannelCodebook(("DEL", "SIGMA", "DELL"), REF)))
    with pytest.raises(ValueError): collate_ordered_entries((value, other), atom_counts=(2, 2))


def test_tensor_native_full6_is_not_retraced_scaled_or_centered():
    value = tensor6()
    assert value.values.tolist() == [[1., 2., 3., 4., 5., 6.]]
    assert value.values[0, [0, 2, 5]].sum().item() == 10.0  # deliberately NOT projected traceless
    assert value.valid.tolist() == [True] and value.audit_counts()["retained_components"] == 6


@pytest.mark.parametrize("partial,mismatch", [(True, False), (False, True), (True, True)])
def test_tensor_partial_and_geometry_mismatch_only_change_loss_eligibility(partial, mismatch):
    value = tensor6(partial=partial, mismatch=mismatch)
    assert value.valid.tolist() == [False]
    assert value.values.tolist() == [[1., 2., 3., 4., 5., 6.]]
    assert int(value.component_valid.sum()) == (5 if partial else 6)
    assert value.reasons[0]["original_component_reasons"][1] == (7 if partial else 0)
    assert value.audit_counts()["quality_denominator_redefined"] is False
    if partial:
        raw = torch.tensor([[1., float("nan"), 3., 4., 5., 6.]], dtype=torch.float64)
        retained = tensor6_from_f64(values=raw, component_valid=value.component_valid,
            geometry_ids=value.geometry_ids, component_geometry_ids=value.component_geometry_ids,
            reasons=value.reasons, source_ref=REF)
        assert torch.isnan(retained.values[0, 1]) and retained.valid.tolist() == [False]
        assert retained.audit_counts()["source_valid_components"] == 5
    with pytest.raises(ValueError, match="derived"):
        replace(value, geometry_valid=~value.geometry_valid)


def test_tensor_collate_keeps_all_components_and_distinct_exposure_mask():
    a, b = tensor6("g0"), tensor6("g1", partial=True)
    batch = collate_tensor6((a.masked(False), b))
    assert batch.values.shape == (2, 6) and batch.valid.tolist() == [False, False]
    assert batch.component_valid[0].all() and not batch.component_valid[1, 1]
    assert batch.exposure_valid.tolist() == [False, True]
    assert batch.to("cpu").audit_counts()["retained_components"] == 12


def test_rank2_head_context_is_explicit_geometry_only_not_label_or_centroid():
    a = Tensor6Inputs(torch.tensor([[9., -3., 2.]]), ("g0",), (REF,), FRAME)
    b = Tensor6Inputs(torch.tensor([[-1., 7., 4.]]), ("g1",), (REF,), FRAME)
    batch = collate_domain_inputs((a, b), atom_counts=(2, 3))
    assert batch.origin.tolist() == [[9., -3., 2.], [-1., 7., 4.]]
    assert not hasattr(batch, "values") and not hasattr(batch, "entry_ordinal")
    with pytest.raises(ValueError): replace(a, origin=torch.full((1, 3), float("nan")))
    with pytest.raises(ValueError): replace(a, origin=torch.zeros((1, 2)))


def test_recipe_exposure_does_not_rewrite_original_validity():
    ordered_value = ordered().masked(False)
    assert not ordered_value.valid.any() and ordered_value.source_valid.tolist() == [True, True, True, False]
    tensor_value = tensor6().masked(False)
    assert not tensor_value.valid.any() and tensor_value.component_valid.all() and tensor_value.geometry_valid.all()


def test_ordered_explicit_numeric_frame_transport_collate_and_autocast_safety():
    import math
    audit = ordered().inputs
    assert audit.frame_origin is None and audit.frame_basis is None
    origin = torch.tensor([[.5, -1., 2.]])
    basis = torch.tensor([[[0., 1., 0.], [-1., 0., 0.], [0., 0., 1.]]])
    ready = replace(audit, frame_origin=origin, frame_basis=basis)
    moved = ready.to("cpu")
    assert torch.equal(moved.frame_origin, origin) and torch.equal(moved.frame_basis, basis)
    batch = collate_domain_inputs((ready, ready), atom_counts=(2, 2))
    assert torch.equal(batch.frame_origin, origin.repeat(2, 1))
    assert torch.equal(batch.frame_basis, basis.repeat(2, 1, 1))
    with pytest.raises(ValueError, match="Cannot mix"):
        collate_domain_inputs((audit, ready), atom_counts=(2, 2))
    c, s = math.cos(.37), math.sin(.37)
    non_dyadic_basis = torch.tensor([[[c, s, 0.], [-s, c, 0.], [0., 0., 1.]]])
    # F32 metadata validation must not accidentally become BF16 matmul.
    with torch.autocast(device_type="cpu", dtype=torch.bfloat16):
        checked = replace(ready, frame_basis=non_dyadic_basis)
        assert checked.frame_basis.dtype == torch.float32


@pytest.mark.parametrize("corruption", ["origin_only", "basis_only", "nonfinite_origin", "nonfinite_basis", "nonorthogonal", "autograd"])
def test_ordered_source_numeric_frame_rejects_incomplete_or_invalid_declarations(corruption):
    origin = torch.tensor([[.5, -1., 2.]])
    basis = torch.tensor([[[0., 1., 0.], [-1., 0., 0.], [0., 0., 1.]]])
    if corruption == "origin_only": basis = None
    if corruption == "basis_only": origin = None
    if corruption == "nonfinite_origin": origin[0, 0] = float("nan")
    if corruption == "nonfinite_basis": basis[0, 0, 0] = float("inf")
    if corruption == "nonorthogonal": basis[0, 0, 1] = 2.
    if corruption == "autograd": origin.requires_grad_(True)
    with pytest.raises(ValueError):
        replace(ordered().inputs, frame_origin=origin, frame_basis=basis)
