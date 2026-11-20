"""Opt-in D-taskbook block reduction and D-K1 masking.

Inputs are standardized scalar targets/predictions with shape (molecule, item).
For atom SASA, items are source-aligned padded atoms with a validity mask. The
caller preserves original atom IDs when creating that padded view. This module
does not define or fit normalizations, change heads, or select block weights.
"""
from dataclasses import dataclass
from typing import Callable, Mapping

import torch
import torch.nn.functional as F


BLOCKS = ("graph_2d", "molecule_3d", "atom_sasa")
D_K1_DROP_PROBABILITY = 0.85


@dataclass(frozen=True)
class DBlockWeights:
    """Frozen D-R0 total weights, supplied from the preregistered anchor."""

    graph_2d: float
    molecule_3d: float
    atom_sasa: float


@dataclass(frozen=True)
class DMask:
    # True means observed in the original source; never mutated by D-K1.
    observed_valid: torch.Tensor
    # True means randomly suppressed; always False on source-missing items.
    random_dropped: torch.Tensor
    effective_valid: torch.Tensor


@dataclass(frozen=True)
class DLossResult:
    total: torch.Tensor
    per_sample: torch.Tensor
    block_means: Mapping[str, torch.Tensor]
    masks: Mapping[str, DMask]


def mask_graph_targets(valid, *, enabled=False, generator=None):
    """D-K1's single fixed 85% drop rate; default consumes no random state.

    An enabled call requires a dedicated checkpointed target-mask RNG, separate
    from the molecule/conformer sampler so D-K1 preserves its sampling order.
    Missingness and random masking remain distinct in the returned masks.
    """
    if not enabled:
        return DMask(valid, torch.zeros_like(valid), valid)
    if generator is None:
        raise ValueError("D-K1 requires an explicit checkpointed generator")
    dropped = torch.zeros_like(valid)
    dropped[valid] = torch.rand(int(valid.sum()), generator=generator,
                               device=valid.device) < D_K1_DROP_PROBABILITY
    return DMask(valid, dropped, valid & ~dropped)


def loss_targets(targets, *, enabled=False):
    """Clip standardized loss targets only in D mode; storage stays unchanged."""
    return targets.clamp(-6.0, 6.0) if enabled else targets


def compute_d_loss(predictions, standardized_targets, source_valid, weights, *,
                   enabled=False, legacy_loss: Callable | None = None,
                   graph_mask_enabled=False, generator=None, include_3d=True,
                   huber_delta=1.0):
    """Default: return the original loss object without inspecting D inputs.

    Opt-in: Huber loss after target-only +/-6 clipping; reduce actual observed,
    unmasked items within each molecule/block, then apply the three frozen
    D-R0 weights, and mean over molecules. Empty blocks contribute exactly zero.
    Deleting D3 does not redistribute any of its weight. `huber_delta` must be
    the existing registered value (this API does not choose/tune it).
    """
    if not enabled:
        if legacy_loss is None:
            raise ValueError("Disabled D mode requires the unchanged legacy loss")
        return legacy_loss()
    masks = {
        "graph_2d": mask_graph_targets(source_valid["graph_2d"],
            enabled=graph_mask_enabled, generator=generator)
    }
    for name in BLOCKS[1:]:
        masks[name] = mask_graph_targets(source_valid[name])
    means = {}
    for name in BLOCKS:
        prediction = predictions[name]
        valid = masks[name].effective_valid
        if name != "graph_2d" and not include_3d:
            means[name] = prediction.new_zeros(prediction.shape[0])
            continue
        # Exclude missing NaNs before arithmetic, so their gradients stay zero.
        prediction = torch.where(valid, prediction, 0.0)
        target = torch.where(valid, standardized_targets[name], 0.0)
        target = loss_targets(target, enabled=True)
        items = F.huber_loss(prediction, target, delta=huber_delta, reduction="none")
        counts = valid.sum(dim=1)
        means[name] = torch.where(valid, items, 0.0).sum(dim=1) / counts.clamp_min(1)
    per_sample = sum(getattr(weights, name) * means[name] for name in BLOCKS)
    return DLossResult(per_sample.mean(), per_sample, means, masks)
