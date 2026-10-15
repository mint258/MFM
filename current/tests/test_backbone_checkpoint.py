from copy import deepcopy

import pytest
import torch
from torch_geometric.data import Batch, Data

from phychem_mfm.factory import build_model
from phychem_mfm.model.backbone import RealCoordTransformerBackbone


def batch():
    torch.manual_seed(731)
    return Batch.from_data_list([
        Data(x=torch.arange(n) % 12, pos=torch.randn(n, 3)) for n in (5, 11, 7)
    ])


@pytest.mark.parametrize("dropout", [0.0, 0.1])
def test_checkpoint_preserves_output_probes_optimizer_and_rng(dropout):
    torch.manual_seed(98)
    original = RealCoordTransformerBackbone(119, 32, layers=3, heads=4,
                                            ff_mult=2, dropout=dropout)
    recomputed = deepcopy(original)
    recomputed.activation_checkpointing = True
    projection = torch.randn(32, 5)
    native = batch()
    states = []
    for model in (original, recomputed):
        data = native.clone()
        data.pos.requires_grad_()
        optimizer = torch.optim.AdamW(model.parameters(), lr=3e-4, weight_decay=0.01)
        torch.manual_seed(449)
        output = model(data)
        loss = (output @ projection).square().mean()
        probe_parameters = (model.out_norm.weight, model.atom_emb.weight)
        probe = torch.autograd.grad(loss, probe_parameters, retain_graph=True)
        assert all(p.grad is None for p in model.parameters())
        loss.backward()
        gradients = {name: p.grad.clone() for name, p in model.named_parameters()}
        optimizer.step()
        states.append((output.detach(), probe, gradients, data.pos.grad.clone(),
                       deepcopy(model.state_dict()), deepcopy(optimizer.state_dict()),
                       torch.random.get_rng_state()))
    left, right = states
    torch.testing.assert_close(left[0], right[0], rtol=2e-5, atol=2e-6)
    for a, b in zip(left[1], right[1]):
        torch.testing.assert_close(a, b, rtol=2e-5, atol=2e-6)
    for a, b in ((left[2], right[2]), (left[4], right[4])):
        assert a.keys() == b.keys()
        for name in a:
            torch.testing.assert_close(a[name], b[name], rtol=2e-5, atol=2e-6)
    torch.testing.assert_close(left[3], right[3], rtol=2e-5, atol=2e-6)
    assert left[5]["param_groups"] == right[5]["param_groups"]
    for key in left[5]["state"]:
        for name, value in left[5]["state"][key].items():
            torch.testing.assert_close(value, right[5]["state"][key][name], rtol=2e-5, atol=2e-6)
    assert torch.equal(left[6], right[6])


def test_checkpoint_reduces_saved_activation_footprint():
    torch.manual_seed(102)
    baseline = RealCoordTransformerBackbone(119, 64, layers=3, heads=4, ff_mult=2)
    recomputed = deepcopy(baseline)
    recomputed.activation_checkpointing = True
    data = Batch.from_data_list([Data(x=torch.arange(48) % 12, pos=torch.randn(48, 3)) for _ in range(4)])
    footprints = []
    for model in (baseline, recomputed):
        saved = []
        def pack(tensor):
            saved.append(tensor.numel() * tensor.element_size())
            return tensor
        with torch.autograd.graph.saved_tensors_hooks(pack, lambda tensor: tensor):
            result = model(data)
        assert result.shape == (192, 64)
        footprints.append(sum(saved))
    # This counts tensors retained for backward, not actual GPU allocation.
    assert footprints[1] < footprints[0] / 2


def test_factory_enables_backbone_flag_without_new_parameters_or_rng():
    config = {"architecture": {"preset": "light"},
              "backbone": {"n_atom_types": 119, "dim": 32, "layers": 2, "heads": 4}}
    torch.manual_seed(321)
    original = build_model(config)
    original_rng = torch.random.get_rng_state()
    config["backbone"]["activation_checkpointing"] = True
    torch.manual_seed(321)
    recomputed = build_model(config)
    assert original.backbone.activation_checkpointing is False
    assert recomputed.backbone.activation_checkpointing is True
    assert torch.equal(original_rng, torch.random.get_rng_state())
    assert original.state_dict().keys() == recomputed.state_dict().keys()
    for name, value in original.state_dict().items():
        assert torch.equal(value, recomputed.state_dict()[name])


@pytest.mark.parametrize("invalid", [1, "true", None])
def test_checkpoint_config_rejects_non_boolean(invalid):
    with pytest.raises(ValueError, match="must be a boolean"):
        RealCoordTransformerBackbone(119, 32, layers=2, heads=4,
                                    activation_checkpointing=invalid)
