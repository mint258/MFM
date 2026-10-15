from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import torch.nn as nn
from torch import Tensor
from torch.utils.checkpoint import checkpoint

from .expert_blocks import ETExpert


MAIN_TASKS = ("energy", "charge", "element", "geometry", "bond")
ALL_ROUTE_KEYS = (*MAIN_TASKS, "descriptor")


@dataclass(frozen=True)
class TaskRouteConfig:
    energy: str = "light"
    charge: str = "light"
    element: str = "light"
    geometry: str = "light"
    bond: str = "light"
    descriptor: str = "light"

    def __post_init__(self) -> None:
        for task in ALL_ROUTE_KEYS:
            value = str(getattr(self, task)).lower()
            if value not in {"light", "expert"}:
                raise ValueError(f"Unsupported route for {task}: {value}")
        if self.descriptor != "light":
            raise ValueError(
                "The canonical ICLR 2027 presets keep descriptor supervision direct on H0; "
                "a descriptor Expert Transformer must be introduced as a separately named experiment."
            )

    @classmethod
    def light_all(cls) -> "TaskRouteConfig":
        return cls()

    @classmethod
    def expert_main(cls) -> "TaskRouteConfig":
        return cls(
            energy="expert",
            charge="expert",
            element="expert",
            geometry="expert",
            bond="expert",
            descriptor="light",
        )

    @classmethod
    def hybrid_g(cls) -> "TaskRouteConfig":
        return cls(geometry="expert")

    @classmethod
    def hybrid_qg(cls) -> "TaskRouteConfig":
        return cls(charge="expert", geometry="expert")

    @classmethod
    def from_mapping(cls, values: Mapping[str, str]) -> "TaskRouteConfig":
        unknown = set(values).difference(ALL_ROUTE_KEYS)
        if unknown:
            raise ValueError(f"Unknown task route keys: {sorted(unknown)}")
        return cls(**{key: str(values.get(key, "light")).lower() for key in ALL_ROUTE_KEYS})

    def route_for(self, task_name: str) -> str:
        if task_name not in ALL_ROUTE_KEYS:
            raise KeyError(task_name)
        return str(getattr(self, task_name))

    def to_dict(self) -> dict[str, str]:
        return {task: self.route_for(task) for task in ALL_ROUTE_KEYS}


class TaskAdapter(nn.Module):
    route_type: str

    def forward(self, h0: Tensor, *, batch: Tensor, pos: Tensor) -> Tensor:  # pragma: no cover - interface
        raise NotImplementedError


class LightTaskAdapter(TaskAdapter):
    """No attention stack: the historical prediction head receives H0 directly."""

    route_type = "light"

    def forward(self, h0: Tensor, *, batch: Tensor, pos: Tensor) -> Tensor:
        del batch, pos
        return h0


class ExpertTransformerAdapter(TaskAdapter):
    route_type = "expert"

    def __init__(
        self,
        dim: int,
        *,
        real_layers: int = 2,
        internal_layers: int = 0,
        heads: int = 8,
        ff_mult: int = 2,
        dropout: float = 0.0,
        radius: float = 8.0,
        activation_checkpointing: bool = False,
    ) -> None:
        super().__init__()
        self.activation_checkpointing = bool(activation_checkpointing)
        self.expert = ETExpert(
            dim=dim,
            real_layers=real_layers,
            int_layers=internal_layers,
            nheads=heads,
            ff_mult=ff_mult,
            dropout=dropout,
            radius=radius,
        )

    def forward(self, h0: Tensor, *, batch: Tensor, pos: Tensor) -> Tensor:
        if self.training and self.activation_checkpointing and h0.requires_grad:
            def run_expert(features: Tensor, coordinates: Tensor, graph_batch: Tensor) -> Tensor:
                return self.expert(features, batch=graph_batch, pos=coordinates)

            # Reentrant checkpointing runs the expert forward under no-grad and
            # is materially more memory-efficient for the dense attention
            # intermediates used by ETExpert.
            return checkpoint(run_expert, h0, pos, batch, use_reentrant=True)
        return self.expert(h0, batch=batch, pos=pos)


def build_task_adapter(route: str, dim: int, expert_config: Mapping[str, object]) -> TaskAdapter:
    route = str(route).lower()
    if route == "light":
        return LightTaskAdapter()
    if route == "expert":
        return ExpertTransformerAdapter(
            dim=dim,
            real_layers=int(expert_config.get("real_layers", 2)),
            internal_layers=int(expert_config.get("internal_layers", 0)),
            heads=int(expert_config.get("heads", 8)),
            ff_mult=int(expert_config.get("ff_mult", 2)),
            dropout=float(expert_config.get("dropout", 0.0)),
            radius=float(expert_config.get("radius", 8.0)),
            activation_checkpointing=bool(expert_config.get("activation_checkpointing", False)),
        )
    raise ValueError(f"Unsupported task route: {route}")
