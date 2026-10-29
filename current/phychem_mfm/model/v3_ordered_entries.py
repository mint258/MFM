"""Source-frame ordered-entry heads with independent endpoint channels.

r73 retains selected entries, not a complete AO matrix. This module makes no
invariant-scalar, exchange-symmetry or AO-rotation-law claim. Its coordinate
features use explicitly supplied source-frame origin and basis. Under passive
coordinate re-expression X'=XR+t, O'=OR+t, B'=BR, (X-O)B^T is unchanged. This
does not establish an active AO rotation law for the retained entry list.
Release admission remains separate; ordinals/labels are never head inputs.
"""
from __future__ import annotations

from copy import deepcopy
import json
from typing import Mapping

import torch
from torch import Tensor, nn

from ..phase1.v3_contract import require
from ..phase1.v3_label_domains import ChannelCodebook, OrderedEntryInputs


def json_metadata(value):
    """Canonical plain JSON state; tuples from the program API become lists."""
    def valid(item):
        if type(item) is dict:
            return all(type(key) is str and valid(part) for key, part in item.items())
        if type(item) in (tuple, list):
            return all(valid(part) for part in item)
        return item is None or type(item) in (str, int, float, bool)
    require(valid(value), "Plain finite JSON head metadata required")
    try:
        return json.loads(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False))
    except (TypeError, ValueError) as error:
        raise ValueError("Plain finite JSON head metadata required") from error


def decode_channel_codebook(value):
    """Accept a typed program object or exact JSON {tokens:[str],source:rawref}."""
    if isinstance(value, ChannelCodebook):
        return ChannelCodebook(value.tokens, deepcopy(value.source))
    require(type(value) is dict and set(value) == {"tokens", "source"}
            and type(value["tokens"]) is list,
            "Exact JSON channel codebook tokens/source record required")
    return ChannelCodebook(value["tokens"], json_metadata(value["source"]))


def _rawref(value):
    require(type(value) is dict and set(value) == {"path", "bytes", "sha256"}
            and type(value["path"]) is str and value["path"].startswith("/")
            and type(value["bytes"]) is int and value["bytes"] >= 0
            and type(value["sha256"]) is str and len(value["sha256"]) == 64
            and all(x in "0123456789abcdef" for x in value["sha256"]),
            "Exact source geometry/policy rawref required")


def validate_frame_binding(frame_binding):
    require(isinstance(frame_binding, Mapping)
            and all(type(frame_binding.get(key)) is str and frame_binding[key]
                for key in ("unit", "sign", "frame", "origin_policy", "target_id", "condition")),
            "Explicit target/condition/unit/sign/frame/origin declaration required")
    _rawref(frame_binding.get("joint_policy"))
    return json_metadata(dict(frame_binding))


def validate_geometry_context(batch: Tensor, graphs: int, geometry_context):
    """Check independent decoded-position identities and native memberships.

    This compares supplied identities; it never hashes live files or invents
    a source binding from the target's own metadata.
    """
    require(isinstance(geometry_context, Mapping)
            and set(geometry_context) == {"geometry_ids", "geometry_bindings", "native_atom_counts"},
            "Independent actual-geometry context required for typed-domain heads")
    ids = tuple(geometry_context["geometry_ids"])
    bindings = tuple(geometry_context["geometry_bindings"])
    counts = tuple(geometry_context["native_atom_counts"])
    require(len(ids) == len(bindings) == len(counts) == graphs
            and all(type(value) is str and value for value in ids)
            and all(type(value) is int and value > 0 for value in counts),
            "Actual geometry identities/counts differ from native graph batch")
    for value in bindings:
        _rawref(value)
    require(batch.dtype == torch.long and batch.ndim == 1
            and (len(batch) == 0 or (int(batch.min()) >= 0 and int(batch.max()) < graphs))
            and torch.bincount(batch, minlength=graphs).tolist() == list(counts),
            "Actual geometry atom membership differs from decoded native counts")
    return ids, bindings


class OrderedEntryHead(nn.Module):
    """Predict each entry from ordered H0/channels and explicit source coordinates.

    The two embedding tables are independent. Onsite and duplicate entries
    are legal; (atom,channel) endpoint exchange is never imposed. Checkpoint
    state binds the literal codebook and the explicitly supplied frame policy.
    """
    def __init__(self, dim: int, *, codebook: ChannelCodebook | Mapping, frame_binding: Mapping,
                 hidden_dim: int = 64, channel_dim: int = 16):
        super().__init__()
        require(type(dim) is int and dim > 0 and type(hidden_dim) is int and hidden_dim >= 2
                and type(channel_dim) is int and channel_dim > 0, "Explicit ordered-head dimensions required")
        require(isinstance(frame_binding, Mapping), "Explicit source frame binding required")
        codebook = decode_channel_codebook(codebook)
        self.dim, self.hidden_dim, self.channel_dim = dim, hidden_dim, channel_dim
        self.codebook = ChannelCodebook(codebook.tokens, deepcopy(codebook.source))
        self.frame_binding = validate_frame_binding(frame_binding)
        self.left_channel = nn.Embedding(len(codebook.tokens), channel_dim)
        self.right_channel = nn.Embedding(len(codebook.tokens), channel_dim)
        self.predict = nn.Sequential(nn.Linear(2*dim + 2*channel_dim + 6, hidden_dim),
                                     nn.SiLU(), nn.Linear(hidden_dim, 1))

    def get_extra_state(self):
        return {"schema": "model_v3_source_frame_ordered_head_v2", "dim": self.dim,
                "hidden_dim": self.hidden_dim, "channel_dim": self.channel_dim,
                "codebook_tokens": list(self.codebook.tokens), "codebook_source": deepcopy(self.codebook.source),
                "codebook_sha256": self.codebook.sha256, "frame_binding": deepcopy(self.frame_binding),
                "geometry_features": "ordered_endpoint_source_coordinates_(pos-origin)@basis.T",
                "numeric_source_origin_and_basis_required": True,
                "coordinate_reexpression": "X'=XR+t; O'=OR+t; B'=BR; passive_only",
                "active_retained_AO_rotation_law_verified": False,
                "ordinal_is_learning_input": False, "exchange_symmetry_imposed": False}

    def set_extra_state(self, state):
        require(json_metadata(state) == self.get_extra_state(), "Ordered head codebook/frame/architecture differ from checkpoint")

    def forward(self, h0: Tensor, pos: Tensor, batch: Tensor, inputs: OrderedEntryInputs, *,
                actual_geometry_ids, actual_geometry_bindings):
        require(isinstance(inputs, OrderedEntryInputs), "Typed ordered-entry head inputs required")
        inputs.__post_init__()
        dtype = self.predict[0].weight.dtype
        require(dtype in (torch.float32, torch.float64) and h0.ndim == 2 and h0.shape[1] == self.dim
                and pos.shape == (len(h0), 3) and pos.dtype == dtype
                and (h0.dtype == dtype or (h0.dtype == torch.bfloat16 and dtype == torch.float32)),
                "Ordered head must use original source coordinates in the declared floating precision")
        require(batch.dtype == torch.long and batch.shape == (len(h0),)
                and h0.device == pos.device == batch.device == inputs.atom_index.device
                == inputs.channel_index.device == inputs.entry_graph.device
                and bool(torch.isfinite(h0).all()) and bool(torch.isfinite(pos).all()),
                "Finite same-device native H0/coordinates/ordered indices required")
        require(inputs.codebook.sha256 == self.codebook.sha256 and inputs.frame_binding == self.frame_binding,
                "Ordered codebook/source frame differs from declared head policy")
        require(tuple(actual_geometry_ids) == inputs.geometry_ids
                and tuple(actual_geometry_bindings) == inputs.geometry_bindings,
                "Ordered entries are not bound to the actual decoded-position geometry")
        graphs = len(inputs.geometry_ids)
        origin, basis = inputs.frame_origin, inputs.frame_basis
        require(isinstance(origin, Tensor) and isinstance(basis, Tensor),
                "Explicit numeric source-frame origin and basis are required; no inferred frame")
        require(origin.shape == (graphs, 3) and basis.shape == (graphs, 3, 3)
                and origin.dtype == basis.dtype == dtype and origin.device == basis.device == pos.device
                and not origin.requires_grad and not basis.requires_grad
                and bool(torch.isfinite(origin).all()) and bool(torch.isfinite(basis).all()),
                "Finite detached same-geometry source-frame origin[G,3]/basis[G,3,3] required")
        identity = torch.eye(3, dtype=dtype, device=pos.device).expand(graphs, 3, 3)
        with torch.autocast(device_type=pos.device.type, enabled=False):
            require(torch.allclose(basis @ basis.transpose(-1, -2), identity, rtol=0.,
                                   atol=1e-6 if dtype == torch.float32 else 32 * torch.finfo(dtype).eps),
                    "Source-frame basis must be orthogonal within native arithmetic roundoff")
        require((len(batch) == 0 and graphs == 0) or (len(batch) > 0 and graphs > 0
                and int(batch.min()) >= 0 and int(batch.max()) < graphs
                and bool((torch.bincount(batch, minlength=graphs) > 0).all())),
                "Ordered native graph membership differs")
        index = inputs.atom_index
        require(bool((index < len(h0)).all()), "Ordered atom endpoint outside actual packed geometry")
        require(bool((batch[index[0]] == inputs.entry_graph).all())
                and bool((batch[index[1]] == inputs.entry_graph).all()),
                "Ordered endpoints must belong to their explicitly bound actual geometry")
        if not index.size(1):
            return h0.new_zeros((0, 1), dtype=dtype)
        with torch.autocast(device_type=h0.device.type, enabled=False):
            src, dst = index
            relative = pos - origin[batch]
            source_pos = torch.bmm(relative[:, None, :], basis[batch].transpose(-1, -2)).squeeze(1)
            feature = torch.cat((h0[src].to(dtype), h0[dst].to(dtype),
                self.left_channel(inputs.channel_index[0]), self.right_channel(inputs.channel_index[1]),
                source_pos[src], source_pos[dst]), dim=-1)
            return self.predict(feature)
