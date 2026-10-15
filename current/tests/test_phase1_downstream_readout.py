"""Synthetic H0 only: no structures, labels, file access or final protocols."""
from copy import deepcopy

import pytest
import torch
from torch import nn

from phychem_mfm.phase1.downstream_readout import READOUT_SCHEMA, SourceAlignedH0Readout


def fixture_inputs():
    # Two unequal graphs; both carbon-like rows can have distinct H0. Source
    # IDs are local and deliberately differ from within-batch encoder order.
    h0 = torch.tensor([[1., 2.], [3., 4.], [10., 20.], [30., 40.], [50., 60.]])
    return h0, torch.tensor([1, 0, 2, 0, 1]), torch.tensor([0, 2, 5]), torch.tensor([0, 0, 1, 1, 1])


def identity_readout(level, *, pooling=None):
    model = SourceAlignedH0Readout(2, 2, output_level=level, hidden_dim=2, pooling=pooling)
    with torch.no_grad():
        affine = model.atom_mlp[0].net[0]
        affine.weight.copy_(torch.eye(2))
        affine.bias.zero_()
        model.output.weight.copy_(torch.eye(2))
        model.output.bias.zero_()
    return model


def test_unequal_graph_mean_isolated_and_batch_ptr_derivation_agree():
    h0, source, ptr, batch = fixture_inputs()
    model = identity_readout("graph")
    output = model(h0, source_atom_ids=source, ptr=ptr, batch=batch)
    torch.testing.assert_close(output.predictions, torch.stack((h0[:2].mean(0), h0[2:].mean(0))))
    assert output.output_level == "graph" and output.source_atom_ids is None
    assert output.graph_ids.tolist() == [0, 1] and output.ptr.tolist() == [0, 2, 5]
    assert output.contract["schema"] == READOUT_SCHEMA
    for partition in ({"ptr": ptr}, {"batch": batch}):
        torch.testing.assert_close(model(h0, source_atom_ids=source, **partition).predictions, output.predictions)
    changed = h0.clone()
    changed[2:] *= 100
    torch.testing.assert_close(model(changed, source_atom_ids=source, ptr=ptr).predictions[0], output.predictions[0])


def test_atom_rows_and_source_ids_follow_within_graph_permutation_without_pool_or_reindex():
    h0, source, ptr, batch = fixture_inputs()
    original_h0, original_source, original_ptr, original_batch = [value.clone() for value in (h0, source, ptr, batch)]
    atom = identity_readout("atom")
    before = atom(h0, source_atom_ids=source, ptr=ptr)
    assert before.predictions.shape == (5, 2)
    torch.testing.assert_close(before.predictions, h0)
    assert before.source_atom_ids.tolist() == [1, 0, 2, 0, 1]
    assert before.graph_ids.tolist() == [0, 0, 1, 1, 1]
    order = torch.tensor([1, 0, 4, 2, 3])
    after = atom(h0[order], source_atom_ids=source[order], batch=batch)
    torch.testing.assert_close(after.predictions, before.predictions[order])
    assert torch.equal(after.source_atom_ids, before.source_atom_ids[order])
    graph = identity_readout("graph")
    torch.testing.assert_close(graph(h0, source_atom_ids=source, ptr=ptr).predictions,
                               graph(h0[order], source_atom_ids=source[order], ptr=ptr).predictions)
    for current, old in zip((h0, source, ptr, batch), (original_h0, original_source, original_ptr, original_batch)):
        assert torch.equal(current, old)
    # Returned metadata owns copies; later consumer edits cannot mutate source.
    before.source_atom_ids.zero_()
    before.ptr.zero_()
    assert torch.equal(source, original_source) and torch.equal(ptr, original_ptr)


@pytest.mark.parametrize("freeze_encoder", [True, False])
def test_caller_controls_frozen_h0_vs_finetuning_without_automatic_detach(freeze_encoder):
    encoder = nn.Linear(3, 2)
    readout = SourceAlignedH0Readout(2, 1, output_level="atom", hidden_dim=2)
    with torch.no_grad():
        for parameter in list(encoder.parameters()) + list(readout.parameters()):
            parameter.fill_(0.5)
    encoder_before = {name: value.detach().clone() for name, value in encoder.named_parameters()}
    readout_before = {name: value.detach().clone() for name, value in readout.named_parameters()}
    h0 = encoder(torch.ones(5, 3))
    h0.retain_grad()
    supplied = h0.detach() if freeze_encoder else h0
    optimizer = torch.optim.SGD(list(encoder.parameters()) + list(readout.parameters()), lr=0.01)
    result = readout(supplied, source_atom_ids=torch.tensor([1, 0, 2, 0, 1]), ptr=torch.tensor([0, 2, 5]))
    result.predictions.sum().backward()
    assert all(parameter.grad is not None for parameter in readout.parameters())
    if freeze_encoder:
        assert h0.grad is None and all(parameter.grad is None for parameter in encoder.parameters())
    else:
        assert h0.grad is not None and bool(h0.grad.abs().sum() > 0)
        assert all(parameter.grad is not None and bool(parameter.grad.abs().sum() > 0) for parameter in encoder.parameters())
    optimizer.step()
    assert any(not torch.equal(parameter, readout_before[name]) for name, parameter in readout.named_parameters())
    if freeze_encoder:
        assert all(torch.equal(parameter, encoder_before[name]) for name, parameter in encoder.named_parameters())
    else:
        assert any(not torch.equal(parameter, encoder_before[name]) for name, parameter in encoder.named_parameters())


@pytest.mark.parametrize("problem", ["missing_partition", "float_batch", "batch_shape", "negative_batch",
                                   "batch_gap", "unordered_batch", "wrong_batch_length", "float_ptr",
                                   "ptr_shape",
                                   "empty_graph", "ptr_start", "ptr_end", "inconsistent_both",
                                   "missing_source_row", "float_source", "source_shape", "duplicate_source",
                                   "int32_source", "bool_source", "one_based_source", "negative_source",
                                   "global_source_ids", "unmapped_padding"])
def test_invalid_index_partition_or_source_bijection_is_rejected(problem):
    h0, source, ptr, batch = fixture_inputs()
    kwargs = {"source_atom_ids": source, "ptr": ptr}
    if problem == "missing_partition":
        kwargs.pop("ptr")
    elif problem in {"float_batch", "batch_shape", "negative_batch", "batch_gap", "unordered_batch", "wrong_batch_length"}:
        kwargs.pop("ptr")
        kwargs["batch"] = {"float_batch": batch.float(), "batch_shape": batch[:, None],
                           "negative_batch": torch.tensor([-1, -1, 0, 0, 0]),
                           "batch_gap": torch.tensor([0, 0, 2, 2, 2]),
                           "unordered_batch": torch.tensor([0, 1, 0, 1, 1]),
                           "wrong_batch_length": batch[:-1]}[problem]
    elif problem in {"float_ptr", "ptr_shape", "empty_graph", "ptr_start", "ptr_end"}:
        kwargs["ptr"] = {"float_ptr": ptr.float(), "ptr_shape": ptr[:, None], "empty_graph": torch.tensor([0, 2, 2, 5]),
                         "ptr_start": torch.tensor([1, 2, 5]), "ptr_end": torch.tensor([0, 2, 4])}[problem]
    elif problem == "inconsistent_both":
        kwargs["batch"] = torch.tensor([0, 0, 0, 1, 1])
    elif problem == "missing_source_row":
        kwargs["source_atom_ids"] = source[:-1]
    elif problem == "float_source":
        kwargs["source_atom_ids"] = source.float()
    elif problem == "source_shape":
        kwargs["source_atom_ids"] = source[:, None]
    elif problem == "int32_source":
        kwargs["source_atom_ids"] = source.to(torch.int32)
    elif problem == "bool_source":
        kwargs["source_atom_ids"] = source.bool()
    elif problem == "duplicate_source":
        kwargs["source_atom_ids"] = torch.tensor([0, 0, 2, 0, 1])
    elif problem == "one_based_source":
        kwargs["source_atom_ids"] = source + 1
    elif problem == "negative_source":
        kwargs["source_atom_ids"] = torch.tensor([1, -1, 2, 0, 1])
    elif problem == "global_source_ids":
        kwargs["source_atom_ids"] = torch.arange(5)
    else:
        h0 = torch.cat((h0, torch.zeros(1, 2)))
        kwargs["ptr"] = torch.tensor([0, 2, 6])
        kwargs["source_atom_ids"] = torch.cat((source, torch.tensor([-1])))
    with pytest.raises(ValueError):
        identity_readout("graph")(h0, **kwargs)


@pytest.mark.parametrize("h0", [torch.zeros(0, 2), torch.ones(5, 3), torch.ones(5, 2, 1),
                                torch.ones(5, 2, dtype=torch.long), torch.full((5, 2), float("nan")),
                                torch.full((5, 2), float("inf"))])
def test_invalid_or_nonfinite_h0_is_rejected(h0):
    with pytest.raises(ValueError, match="H0 must"):
        identity_readout("atom")(h0, source_atom_ids=torch.tensor([1, 0, 2, 0, 1]), ptr=torch.tensor([0, 2, 5]))


@pytest.mark.parametrize("level,pooling", [("atom", None), ("graph", "mean"), ("graph", "sum"),
                                          ("graph", "max"), ("graph", "summary")])
def test_full_config_and_state_roundtrip_keeps_predictions_and_source_contract(level, pooling):
    h0, source, ptr, _ = fixture_inputs()
    model = SourceAlignedH0Readout(2, 2, output_level=level, hidden_dim=4, atom_layers=2, pooling=pooling)
    config = model.config_dict()
    restored = SourceAlignedH0Readout.from_config(config)
    restored.load_state_dict(model.state_dict(), strict=True)
    assert restored.config_dict() == config
    torch.testing.assert_close(restored(h0, source_atom_ids=source, ptr=ptr).predictions,
                               model(h0, source_atom_ids=source, ptr=ptr).predictions)
    returned = model.config_dict()
    returned["source_map_contract"]["index_base"] = 1
    assert model.config_dict()["source_map_contract"]["index_base"] == 0


@pytest.mark.parametrize("change", ["unknown", "missing", "level", "pooling", "schema", "source",
                                   "source_bool", "activation", "representation", "dimension_bool"])
def test_config_rejects_unknown_or_changed_scientific_semantics(change):
    config = SourceAlignedH0Readout(2, 1, output_level="graph").config_dict()
    if change == "unknown":
        config["extra"] = True
    elif change == "missing":
        config.pop("source_map_contract")
    elif change == "source":
        config["source_map_contract"]["index_base"] = 1
    elif change == "source_bool":
        config["source_map_contract"]["index_base"] = False
    elif change == "dimension_bool":
        config["output_dim"] = True
    else:
        field, value = {"level": ("output_level", "atom"), "pooling": ("pooling", None),
                        "schema": ("schema", "unversioned"), "activation": ("activation", "SiLU"),
                        "representation": ("representation", "task_adapter")}[change]
        config[field] = value
    with pytest.raises(ValueError):
        SourceAlignedH0Readout.from_config(config)


@pytest.mark.parametrize("destination", ["atom", "sum"])
def test_same_shape_state_cannot_change_level_or_pooling_and_rejection_precedes_parameter_copy(destination):
    origin = SourceAlignedH0Readout(2, 1, output_level="graph", hidden_dim=2)
    target = SourceAlignedH0Readout(2, 1, output_level="atom" if destination == "atom" else "graph",
                                   hidden_dim=2, pooling="sum" if destination == "sum" else None)
    before = {name: value.detach().clone() for name, value in target.named_parameters()}
    with pytest.raises(ValueError, match="another layer/level/pooling/source"):
        target.load_state_dict(origin.state_dict())
    assert all(torch.equal(parameter, before[name]) for name, parameter in target.named_parameters())
    state = deepcopy(target.state_dict())
    state.pop("_extra_state")
    with pytest.raises(ValueError):
        target.load_state_dict(state)
    state = deepcopy(target.state_dict())
    state["_extra_state"]["source_map_contract"]["index_base"] = 1
    with pytest.raises(ValueError):
        target.load_state_dict(state)
    with pytest.raises(ValueError, match="strict loading"):
        target.load_state_dict(target.state_dict(), strict=False)


@pytest.mark.parametrize("kwargs", [{"output_level": "node"}, {"output_level": "atom", "pooling": "mean"},
                                    {"output_level": "graph", "pooling": "learned"},
                                    {"output_level": "graph", "hidden_dim": 0},
                                    {"output_level": "graph", "atom_layers": True}])
def test_constructor_rejects_ambiguous_or_invalid_architecture(kwargs):
    with pytest.raises(ValueError):
        SourceAlignedH0Readout(2, 1, **kwargs)
