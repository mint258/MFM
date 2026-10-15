"""Independent raw-H0 affine and optimizer oracles, using synthetic labels only."""
from copy import deepcopy
from dataclasses import replace

import pytest
import torch
from torch import nn

from phychem_mfm.phase1.downstream_readout import (
    LINEAR_GRAPH_READOUT_SCHEMA,
    SourceAlignedH0Readout,
    SourceAlignedLinearGraphReadout,
)
from phychem_mfm.phase1.downstream_training import (
    DownstreamTrainer,
    DownstreamTrainingError,
    validate_downstream_batch,
)
from phychem_mfm.phase1.formal_runtime import backbone_state_hash
from test_phase1_downstream_training import (
    SyntheticWandbSpy,
    assert_nested_equal,
    make_batch,
    make_system,
)


def fixture_h0():
    # Unequal two/three-atom graphs and negative coordinates detect hidden ReLU.
    h0 = torch.tensor([[-2., 1., 3.], [4., -3., 1.], [1., 2., -4.],
                       [-3., 4., 2.], [2., -1., 5.]])
    return h0, torch.tensor([0, 0, 1, 1, 1]), torch.tensor([0, 2, 5]), torch.tensor([1, 0, 2, 0, 1])


def fixed_readout(pooling):
    readout = SourceAlignedLinearGraphReadout(3, 2, pooling=pooling)
    with torch.no_grad():
        readout.output.weight.copy_(torch.tensor([[2., -1., .5], [-.25, 3., -2.]]))
        readout.output.bias.copy_(torch.tensor([7., -5.]))
    return readout


@pytest.mark.parametrize("pooling", ["mean", "sum"])
def test_raw_affine_pooling_has_one_bias_per_graph_and_no_atom_nonlinearity(pooling):
    h0, batch, ptr, source = fixture_h0()
    readout = fixed_readout(pooling)
    output = readout(h0, source_atom_ids=source, batch=batch, ptr=ptr)
    raw = torch.stack([h0[:2].sum(0), h0[2:].sum(0)])
    if pooling == "mean":
        raw = raw / torch.tensor([[2.], [3.]])
    expected = raw @ readout.output.weight.T + readout.output.bias
    torch.testing.assert_close(output.predictions, expected)
    assert output.output_level == "graph" and output.source_atom_ids is None
    assert torch.equal(output.graph_ids, torch.tensor([0, 1]))
    assert torch.equal(output.ptr, ptr) and output.ptr.data_ptr() != ptr.data_ptr()
    assert set(dict(readout.named_parameters())) == {"output.weight", "output.bias"}
    assert sum(p.numel() for p in readout.parameters()) == 8
    assert not any(isinstance(m, (nn.ReLU, nn.GELU)) for m in readout.modules())
    assert output.contract["schema"] == LINEAR_GRAPH_READOUT_SCHEMA
    if pooling == "sum":
        wrong_atom_bias = torch.stack([(h0[:2] @ readout.output.weight.T + readout.output.bias).sum(0),
                                       (h0[2:] @ readout.output.weight.T + readout.output.bias).sum(0)])
        assert not torch.equal(output.predictions, wrong_atom_bias)


@pytest.mark.parametrize("pooling", ["mean", "sum"])
def test_graph_isolation_native_permutation_and_explicit_partition_equivalence(pooling):
    h0, batch, ptr, source = fixture_h0()
    readout = fixed_readout(pooling)
    original = readout(h0, source_atom_ids=source, batch=batch, ptr=ptr).predictions
    for kwargs in ({"batch": batch}, {"ptr": ptr}):
        torch.testing.assert_close(readout(h0, source_atom_ids=source, **kwargs).predictions, original)
    permutation = torch.tensor([1, 0, 4, 2, 3])
    torch.testing.assert_close(readout(h0[permutation], source_atom_ids=source[permutation],
                                     batch=batch, ptr=ptr).predictions, original)
    changed = h0.clone()
    changed[2:] += 100.
    modified = readout(changed, source_atom_ids=source, batch=batch, ptr=ptr).predictions
    torch.testing.assert_close(modified[0], original[0])
    assert not torch.equal(modified[1], original[1])


@pytest.mark.parametrize("pooling", ["mean", "sum"])
def test_h0_gradient_matches_affine_derivative_and_graph_size(pooling):
    h0, batch, ptr, source = fixture_h0()
    h0.requires_grad_()
    readout = fixed_readout(pooling)
    readout(h0, source_atom_ids=source, batch=batch, ptr=ptr).predictions[0].sum().backward()
    derivative = readout.output.weight.detach().sum(0)
    if pooling == "mean":
        derivative = derivative / 2
    torch.testing.assert_close(h0.grad[:2], derivative.expand(2, -1))
    assert torch.count_nonzero(h0.grad[2:]) == 0


@pytest.mark.parametrize("pooling", [None, "max", "summary", "MEAN", True])
def test_linear_pooling_requires_explicit_supported_value(pooling):
    with pytest.raises(ValueError):
        SourceAlignedLinearGraphReadout(3, 2, pooling=pooling)


def test_missing_pooling_has_no_implicit_default():
    with pytest.raises(TypeError):
        SourceAlignedLinearGraphReadout(3, 2)


@pytest.mark.parametrize("field,value", [("bias", False), ("activation", "relu"),
    ("operation", "linear_then_pool"), ("representation", "fusion"),
    ("output_level", "atom"), ("schema", "unknown"), ("pooling", "max")])
def test_config_rejects_scientific_contract_changes(field, value):
    config = fixed_readout("mean").config_dict()
    config[field] = value
    with pytest.raises(ValueError):
        SourceAlignedLinearGraphReadout.from_config(config)


def test_config_and_state_roundtrip_do_not_alias_or_change_original_mlp():
    readout = fixed_readout("mean")
    config = readout.config_dict()
    cloned = SourceAlignedLinearGraphReadout.from_config(config)
    cloned.load_state_dict(deepcopy(readout.state_dict()))
    assert_nested_equal(cloned.state_dict(), readout.state_dict())
    config["source_map_contract"]["index_base"] = 1
    assert readout.config_dict()["source_map_contract"]["index_base"] == 0
    original = SourceAlignedH0Readout(3, 2, output_level="graph")
    assert original.config_dict()["schema"] != LINEAR_GRAPH_READOUT_SCHEMA
    assert original.config_dict()["activation"] == "ReLU"


@pytest.mark.parametrize("strict", [True, False])
def test_same_shaped_other_pooling_is_rejected_before_any_weight_copy(strict):
    receiver = fixed_readout("mean")
    source = fixed_readout("sum")
    with torch.no_grad():
        source.output.weight.add_(17.)
    before = deepcopy(receiver.state_dict())
    with pytest.raises(ValueError):
        receiver.load_state_dict(source.state_dict(), strict=strict)
    assert_nested_equal(receiver.state_dict(), before)


@pytest.mark.parametrize("case", ["duplicate_native", "negative_native", "one_based_native", "short_native",
    "native_float", "missing_partition", "unordered_batch", "missing_graph", "empty_ptr",
    "ptr_mismatch", "nonfinite_h0", "wrong_width", "empty_h0"])
def test_rejects_unproved_native_rows_and_graph_partition(case):
    h0, batch, ptr, source = fixture_h0()
    if case == "duplicate_native": source[0] = source[1]
    elif case == "negative_native": source[0] = -1
    elif case == "one_based_native": source += 1
    elif case == "short_native": source = source[:-1]
    elif case == "native_float": source = source.float()
    elif case == "missing_partition": batch = ptr = None
    elif case == "unordered_batch": batch = torch.tensor([0, 1, 0, 1, 1])
    elif case == "missing_graph": batch, ptr = torch.tensor([0, 0, 2, 2, 2]), None
    elif case == "empty_ptr": ptr = torch.tensor([0, 2, 2, 5])
    elif case == "ptr_mismatch": ptr = torch.tensor([0, 3, 5])
    elif case == "nonfinite_h0": h0[0, 0] = float("nan")
    elif case == "wrong_width": h0 = h0[:, :2]
    elif case == "empty_h0": h0 = h0[:0]
    with pytest.raises(ValueError):
        fixed_readout("mean")(h0, source_atom_ids=source, batch=batch, ptr=ptr)


def linear_system(pooling, mode):
    model, _, config = make_system(level="graph", mode=mode, real=True, dropout=.2, total=4)
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(932)
        readout = SourceAlignedLinearGraphReadout(8, 2, pooling=pooling)
    config["readout_config"] = readout.config_dict()
    return model, readout, config


@pytest.mark.parametrize("pooling,mode", [("mean", "frozen"), ("sum", "frozen"),
                                         ("mean", "finetune"), ("sum", "finetune")])
def test_actual_shared_backbone_optimizer_and_resume_match_uninterrupted(pooling, mode):
    sequence = (make_batch("graph"), make_batch("graph", offset=.25))
    model, readout, config = linear_system(pooling, mode)
    initial_h0 = backbone_state_hash(model)
    full = DownstreamTrainer(model, readout, config, tracker=SyntheticWandbSpy())
    full.fit(sequence, max_updates=4)
    model2, readout2, config2 = linear_system(pooling, mode)
    split = DownstreamTrainer(model2, readout2, config2, tracker=SyntheticWandbSpy())
    split.fit(sequence, max_updates=2)
    checkpoint = split.checkpoint()
    model3, readout3, config3 = linear_system(pooling, mode)
    continued = DownstreamTrainer(model3, readout3, config3, tracker=SyntheticWandbSpy(next_step=2))
    continued.load_checkpoint(checkpoint, sequence)
    continued.fit(sequence, max_updates=4)
    assert_nested_equal(model.state_dict(), model3.state_dict())
    assert_nested_equal(readout.state_dict(), readout3.state_dict())
    left, right = full.checkpoint(), continued.checkpoint()
    assert_nested_equal(left["optimizer_state"], right["optimizer_state"])
    assert_nested_equal(left["rng_state"], right["rng_state"])
    assert_nested_equal({k: v for k, v in left["counters"].items() if k != "total_wall_seconds"},
                        {k: v for k, v in right["counters"].items() if k != "total_wall_seconds"})
    assert (backbone_state_hash(model) == initial_h0) == (mode == "frozen")


def test_public_validation_allows_zero_labels_only_for_explicit_requested_scope():
    model, _, config = linear_system("mean", "frozen")
    batch = make_batch("graph")
    batch.supervision_mask.zero_()
    inner = replace(batch, role="train_inner_validation")
    spec = validate_downstream_batch(inner, config, model,
                                    expected_role="train_inner_validation", require_observed=False)
    assert spec["valid"] == [0, 0] and spec["samples"] == 2 and spec["atoms"] == 5
    for item, role, observed in ((inner, "train", True), (batch, "train", True),
                               (inner, "final_test", False), (inner, "train_inner_validation", 0)):
        with pytest.raises(DownstreamTrainingError):
            validate_downstream_batch(item, config, model, expected_role=role, require_observed=observed)
