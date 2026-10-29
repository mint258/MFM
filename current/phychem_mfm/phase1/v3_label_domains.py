"""Explicit D1 ordered-entry and full symmetric-six transports.

These types describe retained source observations, not a new Data release.
Only source float64 -> model float32 conversion is performed here.  No labels
are centered, clipped, projected, symmetrized, sorted, deduplicated or imputed.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, replace
import hashlib
import json
from typing import Sequence

import torch
from torch import Tensor

TENSOR6_COMPONENTS = ("xx", "xy", "yy", "xz", "yz", "zz")


def _require(ok, message):
    if not ok:
        raise ValueError(message)


def _json(value):
    return json.loads(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False))


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _rawref(value):
    _require(type(value) is dict and set(value) == {"path", "bytes", "sha256"}, "Exact source rawref required")
    _require(type(value["path"]) is str and value["path"].startswith("/")
             and type(value["bytes"]) is int and value["bytes"] >= 0
             and type(value["sha256"]) is str and len(value["sha256"]) == 64
             and all(x in "0123456789abcdef" for x in value["sha256"]), "Invalid source rawref")
    return _json(value)


def validate_source_reference(value):
    """Validate a descriptor only; science-file bodies are not opened here."""
    return _rawref(value)


def _tensor(value, dtype, shape, message):
    _require(isinstance(value, Tensor) and value.dtype == dtype and tuple(value.shape) == tuple(shape), message)
    _require(not value.requires_grad, "Targets and domain inputs must not carry an autograd graph")


def _reasons(values, n):
    _require(type(values) in (tuple, list) and len(values) == n, "One retained reason object per observation required")
    return tuple(_json(x) for x in values)


def _geometry_ids(values, n):
    _require(type(values) in (tuple, list), "Geometry IDs must be an explicit sequence, not a string")
    values = tuple(values)
    _require(len(values) == n and all(type(x) is str and bool(x) for x in values), "Explicit actual geometry IDs required")
    return values


def _frame(value):
    value = _json(value)
    _require(type(value) is dict and all(type(value.get(k)) is str and value[k]
             for k in ("target_id", "condition", "unit", "sign", "frame", "origin_policy")), "Explicit unit/sign/frame/origin policy required")
    _rawref(value.get("joint_policy"))
    return value


@dataclass(frozen=True)
class ChannelCodebook:
    """Reversible literal strings; DEL, DELL and DELTA stay distinct."""
    tokens: tuple[str, ...]
    source: dict

    def __post_init__(self):
        _require(type(self.tokens) in (tuple, list), "Explicit channel token sequence required")
        object.__setattr__(self, "tokens", tuple(self.tokens))
        _require(bool(self.tokens) and all(type(x) is str and x for x in self.tokens)
                 and len(set(self.tokens)) == len(self.tokens), "Unique nonempty literal channel strings required")
        object.__setattr__(self, "source", _rawref(self.source))

    @property
    def sha256(self):
        return _hash({"tokens": self.tokens, "source": self.source})

    def encode(self, tokens):
        lookup = {value: i for i, value in enumerate(self.tokens)}
        tokens = tuple(tokens)
        _require(all(type(x) is str and x in lookup for x in tokens), "Unknown literal r73 channel")
        return tuple(lookup[x] for x in tokens)

    def decode(self, ids):
        ids = tuple(ids)
        _require(all(type(x) is int and 0 <= x < len(self.tokens) for x in ids), "Invalid literal channel code")
        return tuple(self.tokens[x] for x in ids)


def _conversion(values_f64, valid, source):
    _require(values_f64.device.type == valid.device.type == "cpu", "Authoritative source conversion belongs in CPU reader")
    _require(values_f64.dtype == torch.float64 and not values_f64.requires_grad, "Only authoritative F64 source may cross conversion boundary")
    _require(bool(torch.isfinite(values_f64[valid]).all()), "Nonfinite source-valid F64 observation")
    wire = values_f64.to(dtype=torch.float32)
    _require(bool(torch.isfinite(wire[valid]).all()), "Source-valid observation cannot be represented as finite F32")
    # This is a raw-array binding, not another numeric conversion or a file SHA.
    source_array_sha = hashlib.sha256(values_f64.contiguous().numpy().tobytes()).hexdigest()
    wire_array_sha = hashlib.sha256(wire.contiguous().numpy().tobytes()).hexdigest()
    return wire, {"source": _rawref(source), "source_array_sha256": source_array_sha,
                  "wire_array_sha256": wire_array_sha, "source_dtype": "float64", "wire_dtype": "float32",
                  "float_conversions": 1, "labels_centered_clipped_projected_or_imputed": False}


def _conversion_records(values):
    values = tuple(_json(x) for x in values)
    _require(bool(values), "Source conversion provenance required")
    for value in values:
        _require(value.get("source_dtype") == "float64" and value.get("wire_dtype") == "float32"
                 and type(value.get("float_conversions")) is int and value["float_conversions"] == 1
                 and value.get("labels_centered_clipped_projected_or_imputed") is False,
                 "Exactly one authoritative F64-to-F32 conversion required")
        _rawref(value.get("source"))
        for key in ("source_array_sha256", "wire_array_sha256"):
            _require(type(value.get(key)) is str and len(value[key]) == 64
                     and all(x in "0123456789abcdef" for x in value[key]), "Conversion array binding required")
    return values


@dataclass(frozen=True, eq=False)
class OrderedEntryInputs:
    atom_index: Tensor                  # long[2,E]; direction and onsite retained
    channel_index: Tensor               # long[2,E]; independent endpoint channels
    entry_graph: Tensor                 # long[E]
    codebook: ChannelCodebook
    geometry_ids: tuple[str, ...]
    frame_binding: dict
    geometry_bindings: tuple[dict, ...]
    frame_origin: Tensor | None = None
    frame_basis: Tensor | None = None

    def __post_init__(self):
        e = self.atom_index.shape[1] if self.atom_index.ndim == 2 else -1
        _tensor(self.atom_index, torch.long, (2, e), "Ordered atom endpoints must be long[2,E]")
        _tensor(self.channel_index, torch.long, (2, e), "Ordered channel endpoints must be long[2,E]")
        _tensor(self.entry_graph, torch.long, (e,), "Explicit entry-to-graph map required")
        _require(isinstance(self.codebook, ChannelCodebook), "Typed reversible channel codebook required")
        _require(bool((self.atom_index >= 0).all()) and bool(((self.channel_index >= 0)
                 & (self.channel_index < len(self.codebook.tokens))).all()), "Invalid ordered endpoint/channel")
        ids = _geometry_ids(self.geometry_ids, len(self.geometry_ids))
        _require(bool(ids) and bool(((self.entry_graph >= 0) & (self.entry_graph < len(ids))).all()), "Entry graph outside geometry batch")
        object.__setattr__(self, "geometry_ids", ids)
        _require(len(self.geometry_bindings) == len(ids), "Each ordered graph needs bound source geometry metadata")
        object.__setattr__(self, "geometry_bindings", tuple(_rawref(x) for x in self.geometry_bindings))
        _require((self.frame_origin is None) == (self.frame_basis is None), "Source frame origin/basis must both be present or both None")
        if self.frame_origin is not None:
            _tensor(self.frame_origin, torch.float32, (len(ids), 3), "Detached F32 source-frame origin[G,3] required")
            _tensor(self.frame_basis, torch.float32, (len(ids), 3, 3), "Detached F32 source-frame basis[G,3,3] required")
            _require(self.frame_origin.device == self.frame_basis.device == self.atom_index.device
                     and bool(torch.isfinite(self.frame_origin).all()) and bool(torch.isfinite(self.frame_basis).all()),
                     "Finite source-frame tensors on the domain-input device required")
            with torch.autocast(device_type=self.frame_basis.device.type, enabled=False):
                gram = self.frame_basis @ self.frame_basis.transpose(-1, -2)
                eye = torch.eye(3, dtype=torch.float32, device=gram.device).expand_as(gram)
            _require(torch.allclose(gram, eye, atol=1e-6, rtol=0.), "Source-frame basis must be orthogonal (F32 metadata atol1e-6, rtol0)")
        object.__setattr__(self, "frame_binding", _frame(self.frame_binding))

    def to(self, device, *, non_blocking=False):
        return replace(self, atom_index=self.atom_index.to(device, non_blocking=non_blocking),
                       channel_index=self.channel_index.to(device, non_blocking=non_blocking),
                       entry_graph=self.entry_graph.to(device, non_blocking=non_blocking),
                       frame_origin=None if self.frame_origin is None else self.frame_origin.to(device, non_blocking=non_blocking),
                       frame_basis=None if self.frame_basis is None else self.frame_basis.to(device, non_blocking=non_blocking))

    def pin_memory(self):
        return replace(self, atom_index=self.atom_index.pin_memory(), channel_index=self.channel_index.pin_memory(),
                       entry_graph=self.entry_graph.pin_memory(),
                       frame_origin=None if self.frame_origin is None else self.frame_origin.pin_memory(),
                       frame_basis=None if self.frame_basis is None else self.frame_basis.pin_memory())


@dataclass(frozen=True, eq=False)
class Tensor6Inputs:
    origin: Tensor                      # explicit bound source-origin, NOT centroid or label values
    geometry_ids: tuple[str, ...]
    origin_bindings: tuple[dict, ...]
    frame_binding: dict

    def __post_init__(self):
        n = len(self.geometry_ids)
        object.__setattr__(self, "geometry_ids", _geometry_ids(self.geometry_ids, n))
        _tensor(self.origin, torch.float32, (n, 3), "Explicit F32 origin[graphs,3] required")
        _require(bool(torch.isfinite(self.origin).all()), "Finite declared source-origin required")
        _require(len(self.origin_bindings) == n, "Each source-origin must bind its physical metadata")
        object.__setattr__(self, "origin_bindings", tuple(_rawref(x) for x in self.origin_bindings))
        object.__setattr__(self, "frame_binding", _frame(self.frame_binding))

    def to(self, device, *, non_blocking=False):
        return replace(self, origin=self.origin.to(device, non_blocking=non_blocking))

    def pin_memory(self):
        return replace(self, origin=self.origin.pin_memory())


@dataclass(frozen=True, eq=False)
class OrderedEntryTarget:
    values: Tensor                      # raw/wire F32[E,1], not normalized
    valid: Tensor                       # loss mask, separate from source validity
    source_valid: Tensor
    inputs: OrderedEntryInputs
    entry_ordinal: Tensor               # alignment/recovery only; absent from head inputs
    reasons: tuple
    conversions: tuple[dict, ...]

    def __post_init__(self):
        _require(isinstance(self.inputs, OrderedEntryInputs), "OrderedEntryInputs required")
        e = self.inputs.atom_index.size(1)
        _tensor(self.values, torch.float32, (e, 1), "Ordered wire values must be F32[E,1]")
        _tensor(self.valid, torch.bool, (e,), "Ordered loss-valid mask required")
        _tensor(self.source_valid, torch.bool, (e,), "Original ordered source-valid mask required")
        _tensor(self.entry_ordinal, torch.long, (e,), "Retained-list ordinals required")
        _require(bool((self.entry_ordinal >= 0).all()) and bool((~self.valid | self.source_valid).all()), "Loss mask cannot manufacture source validity")
        _require(bool(torch.isfinite(self.values[self.source_valid]).all()), "Nonfinite source-valid ordered wire value")
        object.__setattr__(self, "reasons", _reasons(self.reasons, e))
        object.__setattr__(self, "conversions", _conversion_records(self.conversions))
        for graph in range(len(self.inputs.geometry_ids)):
            ordinal = self.entry_ordinal[self.inputs.entry_graph == graph]
            _require(len(ordinal) < 2 or bool((ordinal[1:] > ordinal[:-1]).all()), "Retained entry order/ordinal changed")

    @property
    def atom_index(self): return self.inputs.atom_index
    @property
    def channel_index(self): return self.inputs.channel_index
    @property
    def entry_graph(self): return self.inputs.entry_graph
    @property
    def pair_index(self): return self.atom_index

    def masked(self, active):
        _require(type(active) is bool, "Explicit recipe exposure bool required")
        return replace(self, valid=self.valid & active)

    def to(self, device, *, non_blocking=False):
        return replace(self, values=self.values.to(device, non_blocking=non_blocking),
                       valid=self.valid.to(device, non_blocking=non_blocking),
                       source_valid=self.source_valid.to(device, non_blocking=non_blocking),
                       inputs=self.inputs.to(device, non_blocking=non_blocking),
                       entry_ordinal=self.entry_ordinal.to(device, non_blocking=non_blocking))

    def pin_memory(self):
        return replace(self, values=self.values.pin_memory(), valid=self.valid.pin_memory(), source_valid=self.source_valid.pin_memory(),
                       inputs=self.inputs.pin_memory(), entry_ordinal=self.entry_ordinal.pin_memory())

    def audit_counts(self):
        return {"retained_entries": len(self.values), "source_valid_entries": int(self.source_valid.sum()),
                "loss_eligible_entries": int(self.valid.sum()), "onsite_entries": int((self.atom_index[0] == self.atom_index[1]).sum()),
                "entries_deduplicated_or_reordered": False, "ordinal_is_learning_input": False}


@dataclass(frozen=True, eq=False)
class Tensor6Target:
    values: Tensor                      # raw/wire F32[B,6], native full6 order
    component_valid: Tensor             # original bool[B,6], never overwritten by eligibility
    geometry_valid: Tensor              # same actual geometry for ALL six components
    geometry_ids: tuple[str, ...]
    component_geometry_ids: tuple[tuple[str, ...], ...]
    reasons: tuple
    conversions: tuple[dict, ...]
    exposure_valid: Tensor | None = None

    def __post_init__(self):
        n = len(self.geometry_ids)
        object.__setattr__(self, "geometry_ids", _geometry_ids(self.geometry_ids, n))
        _tensor(self.values, torch.float32, (n, 6), "Native tensor wire values must be F32[B,6]")
        _tensor(self.component_valid, torch.bool, (n, 6), "Original six component masks required")
        _tensor(self.geometry_valid, torch.bool, (n,), "Same-actual-geometry qualification required")
        cg = tuple(_geometry_ids(row, 6) for row in self.component_geometry_ids)
        _require(len(cg) == n, "Six explicit component geometry IDs required per tensor")
        expected = torch.tensor([all(x == actual for x in row) for row, actual in zip(cg, self.geometry_ids)],
                                dtype=torch.bool, device=self.geometry_valid.device)
        _require(torch.equal(self.geometry_valid, expected), "Geometry eligibility must be derived from all six actual IDs")
        object.__setattr__(self, "component_geometry_ids", cg)
        _require(bool(torch.isfinite(self.values[self.component_valid]).all()), "Nonfinite source-valid tensor component")
        object.__setattr__(self, "reasons", _reasons(self.reasons, n))
        object.__setattr__(self, "conversions", _conversion_records(self.conversions))
        if self.exposure_valid is not None:
            _tensor(self.exposure_valid, torch.bool, (n,), "Separate recipe exposure mask required")

    @property
    def valid(self):
        valid = self.component_valid.all(dim=1) & self.geometry_valid
        return valid if self.exposure_valid is None else valid & self.exposure_valid

    @property
    def pair_index(self): return None

    def masked(self, active):
        _require(type(active) is bool, "Explicit recipe exposure bool required")
        mask = torch.full_like(self.geometry_valid, active)
        return replace(self, exposure_valid=mask if self.exposure_valid is None else self.exposure_valid & mask)

    def to(self, device, *, non_blocking=False):
        return replace(self, values=self.values.to(device, non_blocking=non_blocking),
                       component_valid=self.component_valid.to(device, non_blocking=non_blocking),
                       geometry_valid=self.geometry_valid.to(device, non_blocking=non_blocking),
                       exposure_valid=None if self.exposure_valid is None else self.exposure_valid.to(device, non_blocking=non_blocking))

    def pin_memory(self):
        return replace(self, values=self.values.pin_memory(), component_valid=self.component_valid.pin_memory(),
                       geometry_valid=self.geometry_valid.pin_memory(),
                       exposure_valid=None if self.exposure_valid is None else self.exposure_valid.pin_memory())

    def audit_counts(self):
        return {"retained_tensors": len(self.values), "retained_components": self.values.numel(),
                "source_valid_components": int(self.component_valid.sum()),
                "complete_source_tensors": int(self.component_valid.all(dim=1).sum()),
                "same_geometry_tensors": int(self.geometry_valid.sum()), "loss_eligible_tensors": int(self.valid.sum()),
                "loss_excluded_tensors": int((~self.valid).sum()), "quality_denominator_redefined": False}


def ordered_entries_from_f64(*, values, source_valid, atom_index, channel_index, entry_ordinal,
                             n_atoms, geometry_id, codebook, frame_binding, reasons, source_ref, geometry_ref,
                             frame_origin=None, frame_basis=None):
    """CPU source boundary. Passing a previously converted F32 tensor is rejected."""
    _require(type(n_atoms) is int and n_atoms > 0, "Native atom count required")
    _require(isinstance(values, Tensor) and values.ndim == 2 and values.size(1) == 1, "F64[E,1] sidecar required")
    e = len(values)
    _tensor(source_valid, torch.bool, (e,), "Source entry mask required")
    _tensor(atom_index, torch.long, (2, e), "Two ordered atom endpoints required")
    _require(bool(((atom_index >= 0) & (atom_index < n_atoms)).all()), "Ordered atom endpoint outside actual geometry")
    wire, conversion = _conversion(values, source_valid, source_ref)
    inputs = OrderedEntryInputs(atom_index.clone(), channel_index.clone(), torch.zeros(e, dtype=torch.long),
                                codebook, (geometry_id,), frame_binding, (_rawref(geometry_ref),), frame_origin, frame_basis)
    return OrderedEntryTarget(wire, source_valid.clone(), source_valid.clone(), inputs, entry_ordinal.clone(),
                              reasons, (conversion,))


def tensor6_from_f64(*, values, component_valid, geometry_ids, component_geometry_ids, reasons, source_ref):
    _require(isinstance(values, Tensor) and values.ndim == 2 and values.size(1) == 6, "F64[B,6] authoritative full6 required")
    _tensor(component_valid, torch.bool, tuple(values.shape), "Original six component masks required")
    wire, conversion = _conversion(values, component_valid, source_ref)
    ids = _geometry_ids(geometry_ids, len(values))
    cg = tuple(_geometry_ids(row, 6) for row in component_geometry_ids)
    _require(len(cg) == len(ids), "Component/actual geometry batch differs")
    geometry_valid = torch.tensor([all(x == actual for x in row) for row, actual in zip(cg, ids)], dtype=torch.bool)
    return Tensor6Target(wire, component_valid.clone(), geometry_valid, ids, cg, reasons, (conversion,))


def collate_domain_inputs(inputs: Sequence, *, atom_counts: Sequence[int]):
    inputs, counts = tuple(inputs), tuple(atom_counts)
    _require(bool(inputs) and len(inputs) == len(counts) and all(type(n) is int and n > 0 for n in counts), "One domain input per native graph required")
    if all(isinstance(x, OrderedEntryInputs) for x in inputs):
        _require(all(len(x.geometry_ids) == 1 and x.codebook.sha256 == inputs[0].codebook.sha256
                     and x.frame_binding == inputs[0].frame_binding for x in inputs), "Ordered codebook/frame binding changed across batch")
        has_frame = tuple(x.frame_origin is not None for x in inputs)
        _require(all(has_frame) or not any(has_frame), "Cannot mix audit-only and head-ready source frames")
        atoms, channels, graphs, offset = [], [], [], 0
        for graph, (value, n) in enumerate(zip(inputs, counts)):
            value.__post_init__()
            _require(bool((value.atom_index < n).all()), "Local ordered atom endpoint outside graph")
            atoms.append(value.atom_index + offset); channels.append(value.channel_index)
            graphs.append(torch.full_like(value.entry_graph, graph)); offset += n
        return OrderedEntryInputs(torch.cat(atoms, dim=1), torch.cat(channels, dim=1), torch.cat(graphs),
                                  inputs[0].codebook, tuple(x.geometry_ids[0] for x in inputs), inputs[0].frame_binding,
                                  tuple(x.geometry_bindings[0] for x in inputs),
                                  torch.cat([x.frame_origin for x in inputs]) if all(has_frame) else None,
                                  torch.cat([x.frame_basis for x in inputs]) if all(has_frame) else None)
    _require(all(isinstance(x, Tensor6Inputs) and len(x.geometry_ids) == 1 for x in inputs), "Mixed or unbatched domain input types")
    _require(all(x.frame_binding == inputs[0].frame_binding for x in inputs), "Tensor source frame policies differ")
    return Tensor6Inputs(torch.cat([x.origin for x in inputs]), tuple(x.geometry_ids[0] for x in inputs),
                         tuple(x.origin_bindings[0] for x in inputs), inputs[0].frame_binding)


def collate_ordered_entries(targets: Sequence[OrderedEntryTarget], *, atom_counts: Sequence[int]):
    targets = tuple(targets)
    _require(bool(targets) and all(isinstance(x, OrderedEntryTarget) for x in targets), "Explicit ordered target per graph required")
    inputs = collate_domain_inputs([x.inputs for x in targets], atom_counts=atom_counts)
    return OrderedEntryTarget(torch.cat([x.values for x in targets]), torch.cat([x.valid for x in targets]),
                              torch.cat([x.source_valid for x in targets]), inputs, torch.cat([x.entry_ordinal for x in targets]),
                              tuple(reason for x in targets for reason in x.reasons), tuple(c for x in targets for c in x.conversions))


def collate_tensor6(targets: Sequence[Tensor6Target]):
    targets = tuple(targets)
    _require(bool(targets) and all(isinstance(x, Tensor6Target) and len(x.values) == 1 for x in targets), "One explicit full6 observation per graph required")
    return Tensor6Target(torch.cat([x.values for x in targets]), torch.cat([x.component_valid for x in targets]),
                         torch.cat([x.geometry_valid for x in targets]), tuple(x.geometry_ids[0] for x in targets),
                         tuple(x.component_geometry_ids[0] for x in targets), tuple(x.reasons[0] for x in targets),
                         tuple(c for x in targets for c in x.conversions),
                         torch.cat([torch.ones_like(x.geometry_valid) if x.exposure_valid is None else x.exposure_valid for x in targets]))
