"""Scientific contracts for the opt-in S denoising repair."""
import copy
import pickle

import pytest
import torch
from torch_geometric.data import Batch, Data

from phychem_mfm.factory import build_model
from phychem_mfm.model.heads import EquivariantDenoisingHead
from phychem_mfm.phase1.full_corpus_loader import FullCorpusViewsDataset
from phychem_mfm.phase1.objectives import denoise_eps_mse


def inputs():
    torch.manual_seed(618)
    return torch.randn(12, 16), torch.randn(12, 3), torch.tensor([0] * 7 + [1] * 5)


def test_equivariance_rotation_translation():
    h, pos, batch = inputs()
    head = EquivariantDenoisingHead(16, pair_chunk_size=9)
    q, _ = torch.linalg.qr(torch.randn(3, 3))
    translation = torch.tensor([2.5, -3.0, 0.75])
    original = head(h, pos, batch)
    transformed = head(h, pos @ q + translation, batch)
    assert (transformed - original @ q).abs().max() < 1e-5


@pytest.mark.parametrize("message_layers", [0, 1, 2])
def test_atom_permutation_and_molecule_isolation(message_layers):
    h, pos, batch = inputs()
    head = EquivariantDenoisingHead(16, message_layers=message_layers, pair_chunk_size=9)
    output = head(h, pos, batch)
    permutation = torch.randperm(len(pos))
    assert torch.allclose(head(h[permutation], pos[permutation], batch[permutation]), output[permutation], atol=1e-5)
    isolated = head(h[:7], pos[:7], torch.zeros(7, dtype=torch.long))
    assert torch.allclose(output[:7], isolated, atol=1e-5)
    changed = pos.clone()
    changed[7:] += 100.0
    assert torch.equal(head(h, changed, batch)[:7], output[:7])
    # Packed interface has no padding atoms; ragged dense buffers are masked.
    large = torch.cat((h, torch.randn(21, 16)))
    coords = torch.cat((pos, torch.randn(21, 3)))
    labels = torch.cat((batch, torch.full((21,), 2)))
    assert torch.allclose(head(large, coords, labels)[:7], isolated, atol=1e-5)


def test_noise_loss_zero_and_unit_baseline():
    generator = torch.Generator().manual_seed(22)
    target = torch.randn(100000, 3, generator=generator)
    eps = 0.1 * torch.randn(100000, 3, generator=generator)
    noisy = target + eps
    actual = noisy - target
    mask = torch.ones(len(target), dtype=torch.bool)
    assert denoise_eps_mse(actual, noisy, target, mask).item() == 0.0
    assert abs(denoise_eps_mse(torch.zeros_like(eps), noisy, target, mask).item() - 1.0) < 0.01
    with pytest.raises(ValueError, match="Gaussian"):
        denoise_eps_mse(actual, noisy, target, mask, geom_angle_std_deg=1.0)
    with pytest.raises(ValueError, match="Gaussian"):
        denoise_eps_mse(actual, noisy, target, mask, geom_bond_scale_std=0.01)


def test_denoise_gradient_reaches_backbone():
    torch.manual_seed(42)
    config = {
        "architecture": {"preset": "shared_light"},
        "backbone": {"dim": 24, "layers": 1, "heads": 3, "n_atom_types": 119,
                     "dropout": 0.0, "activation_checkpointing": True},
        "head": {"profile": "phase1", "geometry_head": "equivariant_noise", "geometry_pair_chunk_size": 7},
    }
    model = build_model(config)
    data = Batch.from_data_list([Data(x=torch.tensor([[5], [6], [0], [0]]), pos=torch.randn(4, 3))])
    output = model.forward_pretrain(data, ["geometry"])
    loss = denoise_eps_mse(output.noise_pred[0], data.pos, data.pos - 0.1, torch.ones(4, dtype=torch.bool))
    loss.backward()
    norm = sum(float(p.grad.square().sum()) for p in model.backbone.parameters() if p.grad is not None)
    assert norm > 0 and torch.isfinite(torch.tensor(norm))


def test_epoch_seed_deterministic_read_and_serialized_resume():
    # The same method is used before each degrade_once call, including workers.
    dataset = object.__new__(FullCorpusViewsDataset)
    dataset.seed, dataset.noise_seed_includes_epoch = 23, True
    dataset.set_epoch(0)
    a = dataset.noise_seed(100)
    dataset.set_epoch(1)
    b = dataset.noise_seed(100)
    assert a != b
    assert dataset.noise_seed(100) == b
    restored = object.__new__(FullCorpusViewsDataset)
    restored.seed, restored.noise_seed_includes_epoch = dataset.seed, True
    restored.set_epoch(dataset.epoch)
    noise = lambda seed: torch.randn(12, 3, generator=torch.Generator().manual_seed(seed))
    assert torch.equal(noise(b), noise(restored.noise_seed(100)))
    dataset.noise_seed_includes_epoch = False
    assert dataset.noise_seed(100) == 123


def test_new_policy_preserves_distance_as_monitor_only():
    from phychem_mfm.phase1.objectives import Phase1LossPolicy
    policy = Phase1LossPolicy.from_mapping({"geometry_task": "denoise_eps_mse"})
    assert policy.geometry_task == "denoise_eps_mse"
    assert "denoise_eps_mse" in policy.task_weights
    assert Phase1LossPolicy().to_dict().get("geometry_task") is None
    defaults = Phase1LossPolicy()
    positional = Phase1LossPolicy(dict(defaults.group_weights), dict(defaults.task_weights))
    assert positional.to_dict() == defaults.to_dict()
