"""Label-free readouts of already computed H0, preserving native atom IDs.

No data, coordinates, labels, checkpoints or training protocol are consumed.
The caller chooses geometry and freezes or fine-tunes its encoder. Every flat
encoder row must correspond to one native source atom; added/unmapped atoms and
padded rows require another independently proved loader contract.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
import json

import torch
from torch import Tensor, nn

from ..model.common import Linear, MLP
from ..model.heads import UnifiedGraphPooling


READOUT_SCHEMA = "phase1_source_aligned_h0_readout_v1"
LINEAR_GRAPH_READOUT_SCHEMA = "phase1_source_aligned_linear_graph_readout_v1"
SOURCE_MAP_CONTRACT = {
    "schema_version": 1,
    "source_atom_order_contract": "source_atom_order_v1",
    "direction": "encoder_row_to_native_source_local_atom_id",
    "index_base": 0,
    "coverage": "complete_per_graph_permutation_0_to_n_minus_1",
    "encoder_atom_scope": "native_source_atoms_only",
    "additional_or_unmapped_encoder_atoms": "unsupported",
    "label_numbering_conversion": "none; caller must declare and apply its source convention",
}


@dataclass(frozen=True)
class H0ReadoutOutput:
    predictions: Tensor
    output_level: str
    graph_ids: Tensor  # One graph ID per prediction row.
    source_atom_ids: Tensor | None  # Atom output only; encoder row order.
    ptr: Tensor  # Flat H0 graph boundaries, not prediction boundaries.
    contract: dict


def _positive_integer(value, name):
    if type(value) is not int or value <= 0:
        raise ValueError(f"{name} must be an explicit positive integer")
    return value


def _same_contract(left, right):
    try:
        return json.dumps(left, sort_keys=True, allow_nan=False) == json.dumps(right, sort_keys=True, allow_nan=False)
    except (TypeError, ValueError):
        return False


def _index_vector(value, name, device):
    if not isinstance(value, Tensor) or value.ndim != 1 or value.dtype != torch.long:
        raise ValueError(f"{name} must be a one-dimensional torch.long tensor")
    if value.device != device:
        raise ValueError(f"{name} must be on the H0 device")


def _partition(h0, batch, ptr):
    """Validate ordered, nonempty graphs without sorting or guessing padding."""
    n_atoms = h0.size(0)
    if batch is None and ptr is None:
        raise ValueError("An explicit batch or ptr is required")
    if batch is not None:
        _index_vector(batch, "batch", h0.device)
        if batch.numel() != n_atoms:
            raise ValueError("batch must cover every flat H0 row exactly")
    if ptr is None:
        if (batch[0].item() != 0 or batch[-1].item() >= n_atoms
                or bool((batch < 0).any()) or bool((batch[1:] < batch[:-1]).any())):
            raise ValueError("batch must contain ordered contiguous graph IDs starting at zero")
        counts = torch.bincount(batch)
        if bool((counts == 0).any()):
            raise ValueError("Empty or missing graph IDs are unsupported")
        ptr = torch.cat((counts.new_zeros(1), counts.cumsum(0)))
    else:
        _index_vector(ptr, "ptr", h0.device)
        if (not 2 <= ptr.numel() <= n_atoms + 1 or ptr[0].item() != 0
                or ptr[-1].item() != n_atoms or bool((ptr[1:] <= ptr[:-1]).any())):
            raise ValueError("ptr must exactly cover flat H0 with nonempty graph segments")
    derived = torch.repeat_interleave(torch.arange(ptr.numel() - 1, device=h0.device), ptr[1:] - ptr[:-1])
    if batch is not None and not torch.equal(batch, derived):
        raise ValueError("batch and ptr disagree or contain noncontiguous graph rows")
    return derived, ptr


class SourceAlignedH0Readout(nn.Module):
    """Atom MLP, then source-aligned atom output or unified graph pooling.

    Defaults have the DEV FixedAtomReadout's single affine-64/ReLU capacity and
    mean graph pooling. Initialization uses existing common.Linear's Xavier
    policy, not an assertion of paired parameters with historical DEV weights.
    """

    def __init__(self, input_dim, output_dim, *, output_level, hidden_dim=64,
                 atom_layers=1, pooling=None):
        super().__init__()
        self.input_dim = _positive_integer(input_dim, "input_dim")
        self.output_dim = _positive_integer(output_dim, "output_dim")
        self.hidden_dim = _positive_integer(hidden_dim, "hidden_dim")
        self.atom_layers = _positive_integer(atom_layers, "atom_layers")
        if output_level not in ("graph", "atom"):
            raise ValueError("output_level must explicitly be graph or atom")
        if output_level == "atom" and pooling is not None:
            raise ValueError("Atom predictions cannot be pooled")
        self.output_level = output_level
        self.pooling = ("mean" if pooling is None else pooling) if output_level == "graph" else None
        if self.pooling is not None and self.pooling not in UnifiedGraphPooling.SUPPORTED:
            raise ValueError("Unsupported explicit graph pooling")
        modules, dim = [], self.input_dim
        for _ in range(self.atom_layers):
            modules.extend((MLP(dim, self.hidden_dim, self.hidden_dim, num_layers=1), nn.ReLU()))
            dim = self.hidden_dim
        self.atom_mlp = nn.Sequential(*modules)
        self.graph_pool = UnifiedGraphPooling(self.hidden_dim)
        pooled_dim = self.graph_pool.output_dim(self.pooling) if output_level == "graph" else self.hidden_dim
        self.output = Linear(pooled_dim, self.output_dim)

    def config_dict(self):
        return {"schema": READOUT_SCHEMA, "input_dim": self.input_dim, "output_dim": self.output_dim,
                "hidden_dim": self.hidden_dim, "atom_layers": self.atom_layers,
                "output_level": self.output_level, "pooling": self.pooling,
                "activation": "ReLU", "initializer": "common.Linear/xavier_uniform; zero_bias",
                "representation": "SharedBackboneMFM.encode_atoms/H0",
                "source_map_contract": deepcopy(SOURCE_MAP_CONTRACT)}

    @classmethod
    def from_config(cls, config):
        required = {"schema", "input_dim", "output_dim", "hidden_dim", "atom_layers", "output_level", "pooling",
                    "activation", "initializer", "representation", "source_map_contract"}
        if not isinstance(config, Mapping) or set(config) != required:
            raise ValueError("Readout config must contain exactly its versioned contract fields")
        fixed = {"schema": READOUT_SCHEMA, "activation": "ReLU",
                 "initializer": "common.Linear/xavier_uniform; zero_bias",
                 "representation": "SharedBackboneMFM.encode_atoms/H0", "source_map_contract": SOURCE_MAP_CONTRACT}
        if not _same_contract({name: config[name] for name in fixed}, fixed):
            raise ValueError("Readout config changes the H0/source/activation/initialization contract")
        if config["output_level"] == "graph" and config["pooling"] is None:
            raise ValueError("Serialized graph pooling must be explicit")
        model = cls(config["input_dim"], config["output_dim"], output_level=config["output_level"],
                    hidden_dim=config["hidden_dim"], atom_layers=config["atom_layers"], pooling=config["pooling"])
        if not _same_contract(model.config_dict(), dict(config)):
            raise ValueError("Readout config does not roundtrip exactly")
        return model

    def get_extra_state(self):
        return self.config_dict()

    def set_extra_state(self, state):
        if not isinstance(state, Mapping) or not _same_contract(dict(state), self.config_dict()):
            raise ValueError("Readout state has another layer/level/pooling/source contract")

    def load_state_dict(self, state_dict, strict=True, assign=False):
        # Validate semantics before copying parameters; same shapes alone cannot
        # distinguish atom vs graph or mean vs sum output.
        if strict is not True or not isinstance(state_dict, Mapping):
            raise ValueError("Readout state requires strict loading of its complete contract")
        self.set_extra_state(state_dict.get("_extra_state"))
        return super().load_state_dict(state_dict, strict=True, assign=assign)

    def forward(self, h0, *, source_atom_ids, batch=None, ptr=None):
        if (not isinstance(h0, Tensor) or h0.ndim != 2 or not h0.is_floating_point()
                or h0.size(0) == 0 or h0.size(1) != self.input_dim or not bool(torch.isfinite(h0).all())):
            raise ValueError("H0 must be finite floating [N, input_dim] with nonzero N")
        graph_ids, boundaries = _partition(h0, batch, ptr)
        _index_vector(source_atom_ids, "source_atom_ids", h0.device)
        if source_atom_ids.numel() != h0.size(0):
            raise ValueError("source_atom_ids must map every encoder row")
        for start, end in zip(boundaries[:-1].tolist(), boundaries[1:].tolist()):
            expected = torch.arange(end - start, device=h0.device)
            if not torch.equal(torch.sort(source_atom_ids[start:end]).values, expected):
                raise ValueError("Each graph requires a complete zero-based native source atom permutation")
        hidden = self.atom_mlp(h0)  # No detach: frozen vs fine-tuned belongs to the caller.
        if self.output_level == "graph":
            hidden = self.graph_pool(hidden, graph_ids, pooling=self.pooling)
            output_graph_ids = torch.arange(boundaries.numel() - 1, device=h0.device)
            output_source_ids = None
        else:
            output_graph_ids, output_source_ids = graph_ids.clone(), source_atom_ids.clone()
        predictions = self.output(hidden)
        if not bool(torch.isfinite(predictions).all()):
            raise ValueError("Readout produced nonfinite predictions")
        return H0ReadoutOutput(predictions, self.output_level, output_graph_ids, output_source_ids,
                               boundaries.clone(), self.config_dict())


class SourceAlignedLinearGraphReadout(nn.Module):
    """Explicit mean/sum of raw H0 followed by one affine graph readout.

    Pooling precedes the Linear, so its bias is applied once per graph, including
    for sum pooling. There is no atom MLP, activation or learned fusion. This is
    a separate representation/readout contract; it does not change the existing
    SourceAlignedH0Readout or select a downstream protocol for the caller.
    """

    def __init__(self, input_dim, output_dim, *, pooling):
        super().__init__()
        self.input_dim = _positive_integer(input_dim, "input_dim")
        self.output_dim = _positive_integer(output_dim, "output_dim")
        if pooling not in ("mean", "sum"):
            raise ValueError("Linear graph pooling must explicitly be mean or sum")
        self.output_level = "graph"
        self.pooling = pooling
        self.graph_pool = UnifiedGraphPooling(self.input_dim)
        self.output = Linear(self.input_dim, self.output_dim, bias=True)

    def config_dict(self):
        return {"schema": LINEAR_GRAPH_READOUT_SCHEMA,
                "input_dim": self.input_dim, "output_dim": self.output_dim,
                "output_level": self.output_level, "pooling": self.pooling,
                "operation": "raw_H0_graph_pool_then_single_linear", "bias": True,
                "activation": "none", "initializer": "common.Linear/xavier_uniform; zero_bias",
                "representation": "SharedBackboneMFM.encode_atoms/H0",
                "source_map_contract": deepcopy(SOURCE_MAP_CONTRACT)}

    @classmethod
    def from_config(cls, config):
        required = {"schema", "input_dim", "output_dim", "output_level", "pooling",
                    "operation", "bias", "activation", "initializer", "representation",
                    "source_map_contract"}
        if not isinstance(config, Mapping) or set(config) != required:
            raise ValueError("Linear graph config requires exactly its versioned contract fields")
        fixed = {"schema": LINEAR_GRAPH_READOUT_SCHEMA, "output_level": "graph",
                 "operation": "raw_H0_graph_pool_then_single_linear", "bias": True,
                 "activation": "none", "initializer": "common.Linear/xavier_uniform; zero_bias",
                 "representation": "SharedBackboneMFM.encode_atoms/H0",
                 "source_map_contract": SOURCE_MAP_CONTRACT}
        if not _same_contract({name: config[name] for name in fixed}, fixed):
            raise ValueError("Linear graph config changes the H0/source/affine contract")
        model = cls(config["input_dim"], config["output_dim"], pooling=config["pooling"])
        if not _same_contract(model.config_dict(), dict(config)):
            raise ValueError("Linear graph config does not roundtrip exactly")
        return model

    def get_extra_state(self):
        return self.config_dict()

    def set_extra_state(self, state):
        if not isinstance(state, Mapping) or not _same_contract(dict(state), self.config_dict()):
            raise ValueError("Linear graph state has another pooling/source/affine contract")

    def load_state_dict(self, state_dict, strict=True, assign=False):
        # A mean and a sum readout have identical parameter shapes. Check the
        # serialized scientific contract before allowing any parameter copying.
        if strict is not True or not isinstance(state_dict, Mapping):
            raise ValueError("Linear graph state requires strict complete-contract loading")
        self.set_extra_state(state_dict.get("_extra_state"))
        return super().load_state_dict(state_dict, strict=True, assign=assign)

    def forward(self, h0, *, source_atom_ids, batch=None, ptr=None):
        if (not isinstance(h0, Tensor) or h0.ndim != 2 or not h0.is_floating_point()
                or h0.size(0) == 0 or h0.size(1) != self.input_dim or not bool(torch.isfinite(h0).all())):
            raise ValueError("H0 must be finite floating [N, input_dim] with nonzero N")
        graph_ids, boundaries = _partition(h0, batch, ptr)
        _index_vector(source_atom_ids, "source_atom_ids", h0.device)
        if source_atom_ids.numel() != h0.size(0):
            raise ValueError("source_atom_ids must map every encoder row")
        for start, end in zip(boundaries[:-1].tolist(), boundaries[1:].tolist()):
            expected = torch.arange(end - start, device=h0.device)
            if not torch.equal(torch.sort(source_atom_ids[start:end]).values, expected):
                raise ValueError("Each graph requires a complete zero-based native source atom permutation")
        # No detach: ownership of frozen versus fine-tuned H0 is the caller's.
        pooled = self.graph_pool(h0, graph_ids, pooling=self.pooling)
        predictions = self.output(pooled)
        if not bool(torch.isfinite(predictions).all()):
            raise ValueError("Linear graph readout produced nonfinite predictions")
        return H0ReadoutOutput(predictions, "graph",
                               torch.arange(boundaries.numel() - 1, device=h0.device),
                               None, boundaries.clone(), self.config_dict())
