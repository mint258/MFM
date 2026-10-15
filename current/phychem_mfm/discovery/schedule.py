from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class DataProgressSchedule:
    """Descriptor curriculum indexed by structure exposure, never batch count."""

    name: str
    structures_per_pass: int
    descriptor_start_fraction_of_pass: float
    descriptor_ramp_fraction_of_pass: float
    stage1_decay_fraction_of_pass: float
    stage1_floor: float = 0.3

    def __post_init__(self) -> None:
        if self.structures_per_pass <= 0:
            raise ValueError("structures_per_pass must be positive")
        for field_name in (
            "descriptor_start_fraction_of_pass",
            "descriptor_ramp_fraction_of_pass",
            "stage1_decay_fraction_of_pass",
        ):
            if float(getattr(self, field_name)) < 0:
                raise ValueError(f"{field_name} cannot be negative")
        if not 0.0 <= float(self.stage1_floor) <= 1.0:
            raise ValueError("stage1_floor must be in [0, 1]")

    @classmethod
    def from_mapping(cls, values: Mapping[str, object], *, structures_per_pass: int) -> "DataProgressSchedule":
        return cls(
            name=str(values["name"]),
            structures_per_pass=int(structures_per_pass),
            descriptor_start_fraction_of_pass=float(values["descriptor_start_fraction_of_pass"]),
            descriptor_ramp_fraction_of_pass=float(values["descriptor_ramp_fraction_of_pass"]),
            stage1_decay_fraction_of_pass=float(values.get("stage1_decay_fraction_of_pass", 0.0)),
            stage1_floor=float(values.get("stage1_floor", 0.3)),
        )

    @property
    def descriptor_start_exposure(self) -> int:
        return round(self.structures_per_pass * self.descriptor_start_fraction_of_pass)

    @property
    def descriptor_ramp_exposure(self) -> int:
        return round(self.structures_per_pass * self.descriptor_ramp_fraction_of_pass)

    @property
    def stage1_decay_exposure(self) -> int:
        return round(self.structures_per_pass * self.stage1_decay_fraction_of_pass)

    def descriptor_scale(self, structure_exposure: int) -> float:
        if structure_exposure < self.descriptor_start_exposure:
            return 0.0
        ramp = self.descriptor_ramp_exposure
        if ramp <= 0:
            return 1.0
        progress = (int(structure_exposure) - self.descriptor_start_exposure) / ramp
        return float(min(1.0, max(0.0, progress)))

    def stage1_scale(self, structure_exposure: int) -> float:
        if structure_exposure < self.descriptor_start_exposure:
            return 1.0
        decay = self.stage1_decay_exposure
        if decay <= 0:
            return float(self.stage1_floor)
        progress = (int(structure_exposure) - self.descriptor_start_exposure) / decay
        return float(1.0 - min(1.0, max(0.0, progress)) * (1.0 - self.stage1_floor))

    def is_mature(self, structure_exposure: int) -> bool:
        descriptor_end = self.descriptor_start_exposure + self.descriptor_ramp_exposure
        stage1_end = self.descriptor_start_exposure + self.stage1_decay_exposure
        return int(structure_exposure) >= max(descriptor_end, stage1_end)

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "index_unit": "structure_exposure",
            "structures_per_pass": self.structures_per_pass,
            "descriptor_start_fraction_of_pass": self.descriptor_start_fraction_of_pass,
            "descriptor_ramp_fraction_of_pass": self.descriptor_ramp_fraction_of_pass,
            "stage1_decay_fraction_of_pass": self.stage1_decay_fraction_of_pass,
            "stage1_floor": self.stage1_floor,
            "descriptor_start_exposure": self.descriptor_start_exposure,
            "descriptor_ramp_exposure": self.descriptor_ramp_exposure,
            "stage1_decay_exposure": self.stage1_decay_exposure,
        }
