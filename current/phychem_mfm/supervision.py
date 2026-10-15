from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import FrozenSet, Iterable


class Objective(str, Enum):
    ENERGY = "energy"
    CHARGE = "charge"
    ELEMENT = "element"
    GEOMETRY = "geometry"
    BOND = "bond"
    GRAPH_DESCRIPTOR = "graph_descriptor"
    CHARGE_DESCRIPTOR = "charge_descriptor"
    ELEMENT_DESCRIPTOR = "element_descriptor"


STRUCTURAL_OBJECTIVES = frozenset({Objective.ELEMENT, Objective.GEOMETRY, Objective.BOND})
PHYSICS_OBJECTIVES = frozenset({Objective.ENERGY, Objective.CHARGE})
DESCRIPTOR_OBJECTIVES = frozenset(
    {Objective.GRAPH_DESCRIPTOR, Objective.CHARGE_DESCRIPTOR, Objective.ELEMENT_DESCRIPTOR}
)


class SupervisionVariant(str, Enum):
    NONE = "none"
    S = "S"
    P = "P"
    D = "D"
    SP = "SP"
    SD = "SD"
    DP = "DP"
    SDP = "SDP"
    # Keep the literal historical token readable by existing checkpoints.
    SPD = "SPD"

    @classmethod
    def parse(cls, value: str | "SupervisionVariant") -> "SupervisionVariant":
        if isinstance(value, cls):
            return value
        token = str(value).strip()
        return cls.NONE if token.lower() == "none" else cls(token.upper())

    @property
    def canonical_value(self) -> str:
        return "SDP" if self is SupervisionVariant.SPD else self.value


@dataclass(frozen=True)
class SupervisionConfig:
    variant: SupervisionVariant
    structural: bool
    physics: bool
    descriptor: bool

    @classmethod
    def from_variant(cls, variant: str | SupervisionVariant) -> "SupervisionConfig":
        resolved = SupervisionVariant.parse(variant)
        token = resolved.value
        return cls(
            variant=resolved,
            structural="S" in token,
            physics="P" in token,
            descriptor="D" in token,
        )

    @property
    def objectives(self) -> FrozenSet[Objective]:
        active: set[Objective] = set()
        if self.structural:
            active.update(STRUCTURAL_OBJECTIVES)
        if self.physics:
            active.update(PHYSICS_OBJECTIVES)
        if self.descriptor:
            active.update(DESCRIPTOR_OBJECTIVES)
        return frozenset(active)

    def objectives_at_descriptor_scale(self, descriptor_scale: float) -> FrozenSet[Objective]:
        if descriptor_scale > 0.0:
            return self.objectives
        return frozenset(self.objectives.difference(DESCRIPTOR_OBJECTIVES))

    def is_active(self, objective: Objective | str, *, descriptor_scale: float = 1.0) -> bool:
        resolved = objective if isinstance(objective, Objective) else Objective(str(objective))
        return resolved in self.objectives_at_descriptor_scale(descriptor_scale)

    def to_dict(self) -> dict[str, object]:
        return {
            "variant": self.variant.value,
            "structural": self.structural,
            "physics": self.physics,
            "descriptor": self.descriptor,
            "objectives": sorted(item.value for item in self.objectives),
        }


def normalize_objectives(values: Iterable[Objective | str]) -> FrozenSet[Objective]:
    return frozenset(item if isinstance(item, Objective) else Objective(str(item)) for item in values)
