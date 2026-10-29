"""Ordered heads preserve the independent domain; no physical-law acceptance."""
from copy import deepcopy
from dataclasses import replace
import inspect
import json
import math

import pytest
import torch

from model_v3_typed_fixture import FRAME, REF, ordered_target
from phychem_mfm.model.v3_ordered_entries import OrderedEntryHead, validate_geometry_context
from phychem_mfm.phase1.v3_label_domains import ChannelCodebook, collate_domain_inputs


def inputs_and_head():
    inputs = ordered_target().inputs
    return inputs, OrderedEntryHead(4, codebook=inputs.codebook, frame_binding=inputs.frame_binding,
                                   hidden_dim=4, channel_dim=2)


def evaluate(head, inputs, *, pos=None, ids=("g0",), bindings=None):
    return head(torch.ones((2, 4)), torch.tensor([[1., 2., 3.], [4., 5., 6.]]) if pos is None else pos,
                torch.zeros(2, dtype=torch.long), inputs, actual_geometry_ids=ids,
                actual_geometry_bindings=(REF,) if bindings is None else bindings)


def test_onsite_duplicates_and_order_are_retained_and_endpoint_embeddings_are_independent():
    inputs, head = inputs_and_head()
    assert head.left_channel is not head.right_channel
    assert head.left_channel.weight.data_ptr() != head.right_channel.weight.data_ptr()
    with torch.no_grad():
        for parameter in head.parameters(): parameter.zero_()
        head.left_channel.weight[:, 0] = torch.tensor([1., 2., 3.])
        head.right_channel.weight[:, 0] = torch.tensor([7., 11., 13.])
        head.predict[0].weight[0, 8] = 1.
        head.predict[2].weight[0, 0] = 1.
    result = evaluate(head, inputs)
    assert result.shape == (4, 1) and torch.equal(result[0], result[1])
    swapped = replace(inputs, atom_index=inputs.atom_index.flip(0), channel_index=inputs.channel_index.flip(0))
    swapped_result = evaluate(head, swapped)
    assert not torch.equal(result[0], swapped_result[0])
    assert not head.get_extra_state()["exchange_symmetry_imposed"]


def test_numeric_source_frame_features_are_explicit_and_v2_contract_does_not_claim_active_ao_law():
    inputs, head = inputs_and_head()
    with torch.no_grad():
        for parameter in head.parameters(): parameter.zero_()
        head.predict[0].weight[0, -6] = 1.
        head.predict[2].weight[0, 0] = 1.
    a = evaluate(head, inputs, pos=torch.zeros((2, 3)))
    b = evaluate(head, inputs, pos=torch.ones((2, 3)))
    assert not torch.equal(a, b)
    state = head.get_extra_state()
    assert state["schema"] == "model_v3_source_frame_ordered_head_v2"
    assert state["geometry_features"] == "ordered_endpoint_source_coordinates_(pos-origin)@basis.T"
    assert state["numeric_source_origin_and_basis_required"]
    assert not state["active_retained_AO_rotation_law_verified"]


@pytest.mark.parametrize("angle", [0., .61])
def test_passive_general_so3_and_translation_with_comoving_numeric_frame_preserve_features_and_predictions(angle):
    # Pure coordinate re-expression with invariant H0; this is not active
    # rotation of a retained AO-entry list relative to its source orbitals.
    torch.manual_seed(712)
    inputs, head = inputs_and_head()
    axis = torch.tensor([2., 3., 5.], dtype=torch.float64)
    axis = axis / axis.norm()
    x, y, z = axis.tolist()
    skew = torch.tensor([[0., -z, y], [z, 0., -x], [-y, x, 0.]], dtype=torch.float64)
    rotation = (math.cos(angle) * torch.eye(3, dtype=torch.float64)
        + (1 - math.cos(angle)) * axis[:, None] * axis[None, :] + math.sin(angle) * skew).float()
    translation = torch.tensor([3., -4., 2.])
    pos = torch.tensor([[1., 2., 3.], [4., 5., 6.]])
    moved = replace(inputs, frame_origin=inputs.frame_origin @ rotation + translation,
                    frame_basis=inputs.frame_basis @ rotation)
    features = []
    handle = head.predict.register_forward_pre_hook(lambda module, args: features.append(args[0].detach().clone()))
    try:
        first = evaluate(head, inputs, pos=pos)
        second = evaluate(head, moved, pos=pos @ rotation + translation)
    finally:
        handle.remove()
    assert len(features) == 2
    torch.testing.assert_close(features[1], features[0], atol=1e-6, rtol=1e-4)
    torch.testing.assert_close(second, first, atol=1e-6, rtol=1e-4)
    relative = pos - inputs.frame_origin[0]
    source_pos = relative @ inputs.frame_basis[0].T
    torch.testing.assert_close(features[0][:, -6:-3], source_pos[inputs.atom_index[0]])
    torch.testing.assert_close(features[0][:, -3:], source_pos[inputs.atom_index[1]])


def test_missing_numeric_frame_and_nonorthogonal_basis_are_rejected_without_defaults():
    inputs, head = inputs_and_head()
    no_frame = replace(inputs, frame_origin=None, frame_basis=None)
    with pytest.raises(ValueError, match="numeric source-frame"):
        evaluate(head, no_frame)
    with pytest.raises(ValueError):
        evaluate(head, replace(inputs, frame_origin=None))
    with pytest.raises(ValueError, match="orthogon"):
        evaluate(head, replace(inputs, frame_basis=2 * inputs.frame_basis))


def test_packed_source_frames_retain_per_geometry_membership_and_reject_mixed_geometry_entries():
    inputs, head = inputs_and_head()
    other_ref = {**REF, "sha256": "b" * 64}
    second = replace(inputs, geometry_ids=("g1",), geometry_bindings=(other_ref,),
                     frame_origin=inputs.frame_origin + 2.)
    packed = collate_domain_inputs((inputs, second), atom_counts=(2, 2))
    batch = torch.tensor([0, 0, 1, 1])
    h0, pos = torch.ones(4, 4), torch.arange(12, dtype=torch.float32).reshape(4, 3)
    output = head(h0, pos, batch, packed, actual_geometry_ids=("g0", "g1"),
                  actual_geometry_bindings=(REF, other_ref))
    assert output.shape == (8, 1)
    assert torch.equal(packed.frame_origin, torch.cat((inputs.frame_origin, second.frame_origin)))
    mixed_graph = packed.entry_graph.clone()
    mixed_graph[0] = 1
    with pytest.raises(ValueError, match="endpoints"):
        head(h0, pos, batch, replace(packed, entry_graph=mixed_graph), actual_geometry_ids=("g0", "g1"),
             actual_geometry_bindings=(REF, other_ref))
    with pytest.raises(ValueError, match="actual decoded"):
        head(h0, pos, batch, packed, actual_geometry_ids=("g1", "g0"),
             actual_geometry_bindings=(REF, other_ref))


def test_ordinal_labels_masks_and_reasons_are_absent_from_head_input_interface():
    inputs, head = inputs_and_head()
    names = set(inspect.signature(head.forward).parameters)
    assert not names & {"entry_ordinal", "values", "valid", "source_valid", "reasons", "targets"}
    assert not any(hasattr(inputs, name) for name in ("entry_ordinal", "values", "valid", "reasons"))
    value = ordered_target()
    changed = replace(value, entry_ordinal=value.entry_ordinal + 10)
    torch.testing.assert_close(evaluate(head, value.inputs), evaluate(head, changed.inputs))


def test_head_rejects_unbound_or_different_actual_geometry_frame_and_codebook():
    inputs, head = inputs_and_head()
    with pytest.raises(ValueError, match="actual decoded"):
        evaluate(head, inputs, ids=("another-actual-geometry",))
    with pytest.raises(ValueError, match="actual decoded"):
        evaluate(head, inputs, bindings=({**REF, "sha256": "b" * 64},))
    with pytest.raises(ValueError, match="codebook/source frame"):
        evaluate(head, replace(inputs, frame_binding={**FRAME, "frame": "another-frame"}))
    with pytest.raises(ValueError, match="codebook/source frame"):
        evaluate(head, replace(inputs, codebook=ChannelCodebook(("DEL", "SIGMA", "DELL"), REF)))
    with pytest.raises(ValueError, match="outside"):
        evaluate(head, replace(inputs, atom_index=inputs.atom_index + 2))


def test_actual_geometry_context_checks_native_membership_and_exact_source_bindings():
    context = {"geometry_ids": ("g0",), "geometry_bindings": (REF,), "native_atom_counts": (2,)}
    ids, bindings = validate_geometry_context(torch.zeros(2, dtype=torch.long), 1, context)
    assert ids == ("g0",) and bindings == (REF,)
    for changed in ({}, {**context, "native_atom_counts": (3,)},
                    {**context, "geometry_bindings": ({"sha256": "a" * 64},)}):
        with pytest.raises(ValueError): validate_geometry_context(torch.zeros(2, dtype=torch.long), 1, changed)


def test_checkpoint_binds_reversible_codebook_and_explicit_frame_policy():
    inputs, head = inputs_and_head()
    other = OrderedEntryHead(4, codebook=inputs.codebook, frame_binding=inputs.frame_binding,
                             hidden_dim=4, channel_dim=2)
    other.load_state_dict(deepcopy(head.state_dict()))
    torch.testing.assert_close(evaluate(head, inputs), evaluate(other, inputs))
    different = OrderedEntryHead(4, codebook=inputs.codebook, frame_binding={**FRAME, "condition": "another"},
                                 hidden_dim=4, channel_dim=2)
    with pytest.raises(ValueError, match="checkpoint"):
        different.load_state_dict(deepcopy(head.state_dict()))
    obsolete_absolute_feature_state = deepcopy(head.get_extra_state())
    obsolete_absolute_feature_state["schema"] = "model_v3_source_frame_ordered_head_v1"
    with pytest.raises(ValueError, match="checkpoint"):
        head.set_extra_state(obsolete_absolute_feature_state)


def test_empty_entry_domain_never_connects_head_parameters():
    inputs, head = inputs_and_head()
    empty = replace(inputs, atom_index=inputs.atom_index[:, :0], channel_index=inputs.channel_index[:, :0],
                    entry_graph=inputs.entry_graph[:0])
    output = evaluate(head, empty)
    assert output.shape == (0, 1) and not output.requires_grad
    assert all(parameter.grad is None for parameter in head.parameters())


def test_strict_json_codebook_config_matches_typed_program_api_and_plain_json_state():
    inputs, typed_head = inputs_and_head()
    codebook = {"tokens": list(inputs.codebook.tokens), "source": REF}
    from_json = OrderedEntryHead(4, codebook=json.loads(json.dumps(codebook)), frame_binding=FRAME,
                                hidden_dim=4, channel_dim=2)
    from_json.load_state_dict(deepcopy(typed_head.state_dict()), strict=True)
    torch.testing.assert_close(evaluate(from_json, inputs), evaluate(typed_head, inputs))
    assert json.loads(json.dumps(from_json.get_extra_state(), allow_nan=False)) == from_json.get_extra_state()
    # Accept tuple token metadata through the v2 typed program interface.
    old_state = deepcopy(typed_head.get_extra_state())
    old_state["codebook_tokens"] = tuple(old_state["codebook_tokens"])
    from_json.set_extra_state(old_state)


@pytest.mark.parametrize("codebook", [
    {"tokens": ("SIGMA", "DEL", "DELL"), "source": REF},
    {"tokens": ["SIGMA", "DEL", "DELL"], "source": REF, "entry_ordinal": [0, 1]},
    {"tokens": ["SIGMA", "DEL", "DELL"], "source": REF, "values": [1.]},
    {"tokens": ["DEL", "DEL"], "source": REF},
])
def test_json_codebook_config_rejects_ambiguous_records_labels_and_ordinals(codebook):
    with pytest.raises(ValueError):
        OrderedEntryHead(4, codebook=codebook, frame_binding=FRAME)
