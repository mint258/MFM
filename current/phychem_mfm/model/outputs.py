from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional

from torch import Tensor


@dataclass
class BondOutputs:
    existence: Tensor
    order: Tensor
    pair_index: Tensor
    pair_graph_index: Tensor
    existence_target: Tensor
    order_target: Tensor
    sampled_pair_count: int = 0
    positive_pair_count: int = 0
    valid_graph_count: int = 0


@dataclass
class PretrainOutputs:
    atom_repr: Tensor
    graph_repr: Tensor
    energy_pred: Optional[Tensor] = None
    charge_pred: Optional[Tensor] = None
    element_logits: Optional[Tensor] = None
    coordinate_pred: Optional[Tensor] = None
    bond: Optional[BondOutputs] = None
    graph_descriptor_pred: Optional[Tensor] = None
    charge_descriptor_pred: Dict[str, Tensor] = field(default_factory=dict)
    element_descriptor_pred: Dict[str, Tensor] = field(default_factory=dict)
    node_mask: Optional[Tensor] = None
    charge_mask: Optional[Tensor] = None
    task_repr: Dict[str, Tensor] = field(default_factory=dict)
    # Keep each head's original Tensor available to missing-label-aware losses.
    # Slicing a concatenation sends zero gradients to otherwise unused heads,
    # which still permits AdamW weight decay; direct tensors leave grad=None.
    graph_descriptor_by_name: Dict[str, Tensor] = field(default_factory=dict)
    noise_pred: Optional[Tensor] = None

    def detached_summary(self) -> dict[str, object]:
        def shape(value: Optional[Tensor]):
            return None if value is None else list(value.shape)

        return {
            "atom_repr": shape(self.atom_repr),
            "graph_repr": shape(self.graph_repr),
            "energy_pred": shape(self.energy_pred),
            "charge_pred": shape(self.charge_pred),
            "element_logits": shape(self.element_logits),
            "coordinate_pred": shape(self.coordinate_pred),
            "graph_descriptor_pred": shape(self.graph_descriptor_pred),
            "graph_descriptor_by_name": {key: list(value.shape) for key, value in self.graph_descriptor_by_name.items()},
            "charge_descriptor_pred": {key: list(value.shape) for key, value in self.charge_descriptor_pred.items()},
            "element_descriptor_pred": {key: list(value.shape) for key, value in self.element_descriptor_pred.items()},
            "task_repr": {key: list(value.shape) for key, value in self.task_repr.items()},
        }
