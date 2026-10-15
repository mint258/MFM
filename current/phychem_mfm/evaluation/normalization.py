from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Mapping

import torch
from torch import Tensor


@dataclass(frozen=True)
class TargetTransform:
    """Audited mapping between a model head and its stored target space.

    Protocol v3 distinguishes output transforms from loss scaling.  The current
    pretraining heads emit values in original target space; mean/std are used
    only to scale residuals inside ``standardized_huber``.  Consequently all
    current transforms are identity transforms.
    """

    task: str
    kind: str = "identity"
    unit: str = "dimensionless"
    mean: float | list[float] | None = None
    std: float | list[float] | None = None
    clipping: str = "none"
    transformation: str = "none"
    loss_scaling: str = "residual_divided_by_training_std"

    def inverse(self, prediction: Tensor) -> Tensor:
        if self.kind == "identity":
            return prediction
        if self.kind == "zscore":
            if self.mean is None or self.std is None:
                raise ValueError(f"zscore transform for {self.task} requires mean and std")
            mean = torch.as_tensor(self.mean, device=prediction.device, dtype=prediction.dtype)
            std = torch.as_tensor(self.std, device=prediction.device, dtype=prediction.dtype)
            return prediction * std + mean
        raise ValueError(f"Unsupported transform kind: {self.kind}")

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class TargetTransformRegistry:
    VERSION = "target-transform-v3.1"

    def __init__(self, standardizers: Mapping[str, object] | None = None):
        stats = dict(standardizers or {})
        graph_mu = stats.get("graph_desc_mu")
        graph_std = stats.get("graph_desc_std")
        if isinstance(graph_mu, Tensor):
            graph_mu = graph_mu.detach().cpu().tolist()
        if isinstance(graph_std, Tensor):
            graph_std = graph_std.detach().cpu().tolist()
        self._transforms = {
            "energy": TargetTransform("energy", unit="kcal/mol", mean=stats.get("muE"), std=stats.get("stdE")),
            "charge": TargetTransform("charge", unit="e", mean=stats.get("muQ"), std=stats.get("stdQ")),
            "geometry": TargetTransform("geometry", unit="angstrom"),
            "graph_descriptor": TargetTransform(
                "graph_descriptor", unit="descriptor-specific", mean=graph_mu, std=graph_std
            ),
            "formal_charge": TargetTransform(
                "formal_charge", unit="e", mean=stats.get("formal_charge_mu"), std=stats.get("formal_charge_std")
            ),
            "estate_index": TargetTransform(
                "estate_index", unit="descriptor-specific", mean=stats.get("estate_index_mu"), std=stats.get("estate_index_std")
            ),
        }

    def get(self, task: str) -> TargetTransform:
        key = str(task).strip().lower()
        return self._transforms.get(key, TargetTransform(key))

    def inverse_transform_prediction(self, task: str, prediction: Tensor) -> Tensor:
        return self.get(task).inverse(prediction)

    def to_dict(self) -> dict[str, object]:
        return {
            "version": self.VERSION,
            "important_semantics": (
                "Current heads output original-space values. Training mean/std scale only residuals in the loss; "
                "they are metadata and are not applied again during inverse transformation."
            ),
            "targets": {key: value.to_dict() for key, value in sorted(self._transforms.items())},
        }


def inverse_transform_prediction(
    task: str,
    prediction: Tensor,
    standardizers: Mapping[str, object] | None = None,
) -> Tensor:
    return TargetTransformRegistry(standardizers).inverse_transform_prediction(task, prediction)
