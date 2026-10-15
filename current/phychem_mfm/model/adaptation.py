from __future__ import annotations

from enum import Enum

import torch.nn as nn


class AdaptationMode(str, Enum):
    FROZEN = "frozen"
    LAST1 = "last1"
    LAST2 = "last2"
    FULL = "full"


def _set_trainable(module: nn.Module, value: bool) -> None:
    for parameter in module.parameters():
        parameter.requires_grad = value


def set_backbone_adaptation(model: nn.Module, mode: AdaptationMode | str) -> dict[str, object]:
    resolved = mode if isinstance(mode, AdaptationMode) else AdaptationMode(str(mode).lower())
    backbone = getattr(model, "backbone", None)
    if backbone is None or not hasattr(backbone, "layers"):
        raise TypeError("Model does not expose backbone.layers")

    _set_trainable(backbone, False)
    if resolved == AdaptationMode.FULL:
        _set_trainable(backbone, True)
    elif resolved in {AdaptationMode.LAST1, AdaptationMode.LAST2}:
        count = 1 if resolved == AdaptationMode.LAST1 else 2
        for layer in list(backbone.layers)[-count:]:
            _set_trainable(layer, True)
        _set_trainable(backbone.out_norm, True)

    trainable_names = [name for name, parameter in backbone.named_parameters() if parameter.requires_grad]
    trainable_count = sum(parameter.numel() for parameter in backbone.parameters() if parameter.requires_grad)
    total_count = sum(parameter.numel() for parameter in backbone.parameters())
    return {
        "mode": resolved.value,
        "trainable_parameter_count": trainable_count,
        "total_parameter_count": total_count,
        "trainable_names": trainable_names,
    }


def semantic_parameter_groups(model: nn.Module, downstream_head: nn.Module | None = None) -> dict[str, list[nn.Parameter]]:
    groups = {
        "backbone": list(model.backbone.parameters()),
        "experts_adapters": list(model.task_adapters.parameters()),
        "pretraining_heads": list(model.pretraining_head_parameters()),
        "downstream_head": [] if downstream_head is None else list(downstream_head.parameters()),
    }
    seen: set[int] = set()
    for group_name, parameters in groups.items():
        for parameter in parameters:
            identity = id(parameter)
            if identity in seen:
                raise RuntimeError(f"Parameter appears in more than one semantic group: {group_name}")
            seen.add(identity)
    return groups
