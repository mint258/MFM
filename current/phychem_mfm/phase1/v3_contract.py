"""Model-side draft contracts; these are not the data line's D-1/D-2 format.

Physical storage decoding and field meanings must be supplied by a separately
versioned data-line adapter. This module only validates already decoded inputs.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
from typing import Iterable, Mapping

import torch
from torch import Tensor

GROUPS = ("S", "D", "P")
INTERFACE_STATUS = "MODEL_SIDE_DRAFT_AWAITING_D1_D2"
KINDS = ("regression", "binary", "classification", "denoise_eps_mse")
LEVELS = ("graph", "atom", "pair")
REPRESENTATIONS = ("scalar", "vector", "magnitude")


def canonical_hash(value) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"),
                     ensure_ascii=False, allow_nan=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def require(condition, message: str):
    if not condition:
        raise ValueError(message)


def selected_groups(groups: Iterable[str]) -> tuple[str, ...]:
    values = tuple(groups)
    require(len(values) == len(set(values)) and set(values) <= set(GROUPS),
            "Enable each of S/D/P at most once")
    return tuple(group for group in GROUPS if group in values)


@dataclass(frozen=True)
class FieldSpec:
    name: str
    group: str
    family: str
    level: str
    kind: str = "regression"
    representation: str = "scalar"
    pooling: str = "mean"
    classes: int = 0
    huber_delta: float = 1.0
    denoise_sigma: float = 0.1
    unit: str = "explicit_adapter_unit_required"

    def __post_init__(self):
        require(type(self.name) is str and bool(self.name) and type(self.family) is str
                and bool(self.family), "Explicit field and family IDs required")
        require(self.group in GROUPS and self.level in LEVELS and self.kind in KINDS
                and self.representation in REPRESENTATIONS, "Unknown field semantics")
        require(self.pooling in ("sum", "mean", "learned"), "Explicit scalar pooling required")
        require(type(self.classes) is int and (self.classes >= 2 if self.kind == "classification"
                                             else self.classes == 0), "Invalid class count")
        require(math.isfinite(self.huber_delta) and self.huber_delta > 0,
                "Positive finite Huber delta required")
        require(math.isfinite(self.denoise_sigma) and self.denoise_sigma > 0,
                "Positive finite denoising sigma required")
        require(self.kind in ("regression", "denoise_eps_mse") or self.representation == "scalar",
                "Categorical fields require scalar labels")
        require(self.representation != "vector" or self.level in ("graph", "atom"),
                "Pair vector fields require a new declared head")
        require(self.representation != "magnitude" or self.level == "graph",
                "Magnitude fields are graph dipole magnitudes")
        require(self.kind != "denoise_eps_mse" or (self.group == "S" and self.level == "atom"
                and self.representation == "vector"), "Denoising is an S atom vector")
        require(type(self.unit) is str and bool(self.unit), "Explicit label unit required")

    @property
    def target_width(self) -> int:
        return 3 if self.representation == "vector" else 1

    @property
    def prediction_width(self) -> int:
        return self.classes if self.kind == "classification" else self.target_width


@dataclass(frozen=True)
class LabelRegistry:
    fields: tuple[FieldSpec, ...]
    version: str
    source_sha256: str
    authority: str = "synthetic_fixture"

    def __post_init__(self):
        object.__setattr__(self, "fields", tuple(self.fields))
        require(bool(self.fields) and all(isinstance(field, FieldSpec) for field in self.fields),
                "Registry requires FieldSpec entries")
        require(len({field.name for field in self.fields}) == len(self.fields), "Duplicate field")
        require(type(self.version) is str and bool(self.version), "Registry version required")
        require(type(self.source_sha256) is str and len(self.source_sha256) == 64
                and all(c in "0123456789abcdef" for c in self.source_sha256),
                "Registry source SHA256 required")
        require(self.authority in ("synthetic_fixture", "data_line"), "Unknown registry authority")

    @property
    def content_sha256(self):
        return canonical_hash(asdict(self))

    def by_name(self) -> dict[str, FieldSpec]:
        return {field.name: field for field in self.fields}

    def enabled(self, groups, names=None) -> tuple[FieldSpec, ...]:
        groups = selected_groups(groups)
        requested = None if names is None else tuple(names)
        if requested is not None:
            require(len(set(requested)) == len(requested) and set(requested) <= set(self.by_name()),
                    "Unknown or duplicate enabled field")
        return tuple(field for field in self.fields if field.group in groups
                     and (requested is None or field.name in requested))


@dataclass(frozen=True)
class TrainNormalization:
    """A D-4-supplied affine transform. This class never fits statistics.

    Heads return original units. Both predictions and targets are transformed
    before loss, so magnitude heads retain a physically meaningful positive
    output. Any elemental reference is an explicit upstream prediction offset.
    """
    center: tuple[float, ...]
    scale: tuple[float, ...]
    source_sha256: str
    data_version: str
    fit_role: str = "TRAIN"

    def __post_init__(self):
        object.__setattr__(self, "center", tuple(float(v) for v in self.center))
        object.__setattr__(self, "scale", tuple(float(v) for v in self.scale))
        require(self.fit_role == "TRAIN", "Normalization must be fitted on TRAIN only")
        require(bool(self.scale) and len(self.center) == len(self.scale)
                and all(math.isfinite(v) for v in self.center)
                and all(math.isfinite(v) and v > 0 for v in self.scale),
                "Finite center and positive finite scale required")
        require(len(self.source_sha256) == 64
                and all(c in "0123456789abcdef" for c in self.source_sha256)
                and bool(self.data_version), "D-4 identity required")

    def validate_for(self, field: FieldSpec):
        require(len(self.scale) in (1, field.target_width), "Normalization width differs")
        if field.representation == "vector":
            require(all(value == 0 for value in self.center)
                    and all(value == self.scale[0] for value in self.scale),
                    "Equivariant vector normalization needs zero center/isotropic scale")

    def transform(self, value: Tensor) -> Tensor:
        center = value.new_tensor(self.center, dtype=torch.float32)
        scale = value.new_tensor(self.scale, dtype=torch.float32)
        return (value.float() - center) / scale


@dataclass(frozen=True)
class FieldTarget:
    """Already decoded field values with one boolean validity per observation."""
    values: Tensor
    valid: Tensor
    pair_index: Tensor | None = None


def observed_rows(field: FieldSpec, prediction: Tensor, target: FieldTarget):
    require(isinstance(prediction, Tensor) and prediction.ndim == 2
            and prediction.size(1) == field.prediction_width and prediction.is_floating_point(),
            f"{field.name}: prediction shape/dtype differs")
    require(isinstance(target.values, Tensor) and isinstance(target.valid, Tensor)
            and target.valid.dtype == torch.bool and target.valid.ndim == 1,
            f"{field.name}: explicit boolean observation mask required")
    require(prediction.device == target.values.device == target.valid.device,
            f"{field.name}: field tensors must share a device")
    require(target.values.shape == (len(prediction), field.target_width)
            and target.valid.shape == (len(prediction),), f"{field.name}: target shape differs")
    require(not target.values.requires_grad, f"{field.name}: decoded labels must be detached")
    if field.kind == "classification":
        require(target.values.dtype == torch.long, f"{field.name}: integer class IDs required")
        finite = (target.values[:, 0] >= 0) & (target.values[:, 0] < field.classes)
    else:
        require(target.values.dtype == torch.float32, f"{field.name}: decoded fp32 target required")
        finite = torch.isfinite(target.values).all(dim=-1)
        if field.kind == "binary":
            finite &= ((target.values == 0) | (target.values == 1)).all(dim=-1)
    # Missing labels are selected out BEFORE arithmetic. An explicitly valid
    # nonfinite/illegal label is an adapter error, not silently missing.
    require(bool((~target.valid | finite).all()), f"{field.name}: invalid observed label")
    mask = target.valid
    require(bool(torch.isfinite(prediction[mask]).all()), f"{field.name}: nonfinite observed prediction")
    return prediction[mask].float(), target.values[mask], int(mask.sum())


def validate_normalizations(registry: LabelRegistry, normalizations: Mapping[str, TrainNormalization]):
    names = registry.by_name()
    require(set(normalizations) <= set(names), "Normalizer for an unknown field")
    for name, normalizer in normalizations.items():
        require(isinstance(normalizer, TrainNormalization), "Typed TRAIN normalization required")
        normalizer.validate_for(names[name])
