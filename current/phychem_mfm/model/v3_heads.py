"""Registry-driven v3 heads, leaving SharedBackboneMFM's H0 path intact."""
from __future__ import annotations

import hashlib
from copy import deepcopy
from typing import Mapping

import torch
from torch import Tensor, nn

from ..phase1.v3_contract import LabelRegistry, require
from ..phase1.v3_label_domains import OrderedEntryInputs, Tensor6Inputs
from .common import Linear, ensure_batch_attr
from .heads import EquivariantDenoisingHead
from .v3_ordered_entries import OrderedEntryHead, json_metadata, validate_frame_binding, validate_geometry_context
from .v3_rank2_targets import SymmetricTensor6Head


def _pool(h: Tensor, batch: Tensor, graphs: int, mode: str):
    result = h.new_zeros((graphs, h.size(-1))).index_add(0, batch, h)
    if mode == "mean":
        result = result / torch.bincount(batch, minlength=graphs).to(h.dtype).clamp_min(1)[:, None]
    return result


def _mlp(dim, output, hidden):
    return nn.Sequential(Linear(dim, hidden), nn.SiLU(), Linear(hidden, output))


class _PoolingMixer(nn.Module):
    def __init__(self):
        super().__init__()
        self.logits = nn.Parameter(torch.zeros(2))

    def forward(self, h, batch, graphs):
        values = torch.stack((_pool(h, batch, graphs, "sum"), _pool(h, batch, graphs, "mean")), dim=1)
        return (values * self.logits.softmax(0)[None, :, None]).sum(1)


class _PairHead(nn.Module):
    def __init__(self, dim, output, hidden, radius=8.0, rbf_count=64):
        super().__init__()
        self.radius, self.gamma = float(radius), ((rbf_count - 1) / radius) ** 2
        self.register_buffer("centers", torch.linspace(0., self.radius, rbf_count))
        self.predict = _mlp(2 * dim + rbf_count, output, hidden)

    def forward(self, h, pos, pairs):
        if not pairs.size(1):
            return h.new_zeros((0, self.predict[-1].out_features))
        src, dst = pairs
        with torch.autocast(device_type=pos.device.type, enabled=False):
            distance = (pos[src].float() - pos[dst].float()).norm(dim=-1)
            rbf = torch.exp(-self.gamma * (distance[:, None] - self.centers.float()) ** 2)
            envelope = torch.where(distance < self.radius,
                                   0.5 * (1 + torch.cos(torch.pi * distance / self.radius)),
                                   torch.zeros_like(distance))
            rbf = rbf * envelope[:, None]
        feature = torch.cat((h[src] + h[dst], (h[src] - h[dst]).abs(), rbf.to(h.dtype)), dim=-1)
        return self.predict(feature)


class _DipoleHead(nn.Module):
    def __init__(self, dim, hidden, magnitude):
        super().__init__()
        self.charges = _mlp(dim, 1, hidden)
        self.magnitude = magnitude

    def forward(self, h, pos, batch, graphs):
        with torch.autocast(device_type=h.device.type, enabled=False):
            center = _pool(pos.float(), batch, graphs, "mean")
            charges = self.charges(h.float())
            vector = pos.float().new_zeros((graphs, 3)).index_add(
                0, batch, charges * (pos.float() - center[batch]))
            return vector.norm(dim=-1, keepdim=True) if self.magnitude else vector


class V3HeadBank(nn.Module):
    """Independent heads reading invariant H0; no targets enter this module.

    H1/H2/H3 apply to graph scalar fields. H2 shares one projector per S/D/P
    group and keeps each field's output layer independent. A fixed bank is
    used for all enabled-label combinations; switches only select execution.
    """
    def __init__(self, registry: LabelRegistry, *, dim=512,
                 forms: str | Mapping[str, str] = "H1", hidden_dim=64,
                 vector_radius=5.0, vector_rbf_count=32, pair_chunk_size=8192,
                 pooling_overrides: Mapping[str,str] | None = None,
                 domain_head_configs: Mapping[str, Mapping] | None = None):
        super().__init__()
        require(type(dim) is int and dim > 0 and type(hidden_dim) is int and hidden_dim >= 2,
                "Valid H0/head dimensions required")
        require(pooling_overrides is None or isinstance(pooling_overrides,Mapping),
                'Explicit graph-scalar pooling overrides required')
        overrides=dict(pooling_overrides or {})
        graph_scalars={f.name for f in registry.fields if f.level=='graph' and f.representation=='scalar'}
        require(set(overrides)<=graph_scalars and all(type(v) is str and v in ('registry','learned')
                for v in overrides.values()),'Only registry/learned graph-scalar pooling overrides are supported')
        self.pooling_overrides=overrides
        self.registry, self.dim, self.hidden_dim = registry, dim, hidden_dim
        typed_fields = {field.name for field in registry.fields
                        if field.level == "ordered_entry" or field.representation == "symmetric_tensor6"}
        require(domain_head_configs is None or isinstance(domain_head_configs, Mapping),
                "Explicit typed-domain head configuration required")
        domain_configs = dict(domain_head_configs or {})
        require(set(domain_configs) == typed_fields and all(isinstance(value, Mapping) for value in domain_configs.values()),
                "Every typed domain requires its own explicit codebook/frame/origin configuration")
        self.domain_head_bindings = {}
        if isinstance(forms, str):
            self.forms = {field.name: forms for field in registry.fields}
        else:
            require(set(forms) == set(registry.by_name()), "Every field needs a fixed head form")
            self.forms = dict(forms)
        require(set(self.forms.values()) <= {"H1", "H2", "H3"}, "Unknown graph head form")
        self.keys = {field.name: "f_" + hashlib.sha256(field.name.encode()).hexdigest()[:24]
                     for field in registry.fields}
        require(len(set(self.keys.values())) == len(self.keys), "Head key hash collision")
        self.field_heads, self.pooling_mixers, self.group_projectors = nn.ModuleDict(), nn.ModuleDict(), nn.ModuleDict()
        for field in registry.fields:
            key = self.keys[field.name]
            if field.level == "ordered_entry":
                config = dict(domain_configs[field.name])
                require({"codebook", "frame_binding"} <= set(config)
                        and set(config) <= {"codebook", "frame_binding", "channel_dim"},
                        "Ordered head needs explicit codebook/frame and optional channel dimension")
                head = OrderedEntryHead(dim, hidden_dim=hidden_dim, **config)
                self.field_heads[key] = head
                self.domain_head_bindings[field.name] = head.get_extra_state()
            elif field.representation == "symmetric_tensor6":
                config = dict(domain_configs[field.name])
                require(set(config) == {"origin_policy", "frame_binding"},
                        "Tensor6 head requires explicit comoving-origin and source-frame bindings")
                frame_binding = validate_frame_binding(config["frame_binding"])
                self.field_heads[key] = SymmetricTensor6Head(dim, hidden_dim,
                    origin_policy=config["origin_policy"])
                self.domain_head_bindings[field.name] = {"origin_policy": config["origin_policy"],
                                                        "frame_binding": frame_binding}
            elif field.representation in ("vector", "magnitude"):
                if field.level == "atom":
                    self.field_heads[key] = EquivariantDenoisingHead(
                        dim, radius=vector_radius, rbf_count=vector_rbf_count, hidden_dim=hidden_dim,
                        normalization="none", message_layers=0, pair_chunk_size=pair_chunk_size)
                else:
                    self.field_heads[key] = _DipoleHead(dim, hidden_dim, field.representation == "magnitude")
            elif field.level == "pair":
                self.field_heads[key] = _PairHead(dim, field.prediction_width, hidden_dim)
            elif field.level == "atom":
                self.field_heads[key] = _mlp(dim, field.prediction_width, hidden_dim)
            else:
                form = self.forms[field.name]
                if form == "H1":
                    head = Linear(dim, field.prediction_width)
                elif form == "H2":
                    if field.group not in self.group_projectors:
                        self.group_projectors[field.group] = nn.Sequential(Linear(dim, hidden_dim), nn.SiLU())
                    head = Linear(hidden_dim, field.prediction_width)
                else:
                    head = _mlp(dim, field.prediction_width, hidden_dim)
                self.field_heads[key] = head
                if self.pooling_overrides.get(field.name)=='learned' or field.pooling == "learned":
                    self.pooling_mixers[key] = _PoolingMixer()

    def get_extra_state(self):
        result={"schema": "model_v3_head_bank_v1", "registry_sha256": self.registry.content_sha256,
                "dim": self.dim, "hidden_dim": self.hidden_dim, "forms": dict(self.forms)}
        if self.pooling_overrides:result['pooling_overrides']=dict(self.pooling_overrides)
        if self.domain_head_bindings:result["domain_head_bindings"] = deepcopy(self.domain_head_bindings)
        return result

    def set_extra_state(self, state):
        compared = json_metadata(state) if self.domain_head_bindings else state
        require(compared == self.get_extra_state(), "Head registry/forms differ from checkpoint")

    def forward(self, h0: Tensor, batch: Tensor, pos: Tensor, *, enabled_groups,
                enabled_fields=None, pair_indices=None, prediction_offsets=None,
                domain_inputs=None, geometry_context=None):
        require(h0.ndim == 2 and h0.size(1) == self.dim and h0.is_floating_point()
                and len(h0) > 0 and bool(torch.isfinite(h0).all()), "Finite packed H0 required")
        require(batch.dtype == torch.long and batch.shape == (len(h0),) and bool((batch >= 0).all())
                and pos.shape == (len(h0), 3) and pos.dtype == torch.float32
                and batch.device == pos.device == h0.device and bool(torch.isfinite(pos).all()),
                "Explicit packed molecule IDs/fp32 coordinates required")
        graphs = int(batch.max()) + 1
        require(bool((torch.bincount(batch, minlength=graphs) > 0).all()), "Packed molecule IDs must be contiguous")
        pairs = dict(pair_indices or {})
        offsets = dict(prediction_offsets or {})
        require(domain_inputs is None or isinstance(domain_inputs, Mapping), "Typed domain-input mapping required")
        domains = dict(domain_inputs or {})
        require(set(pairs) <= set(self.registry.by_name()) and set(offsets) <= set(self.registry.by_name()),
                "Unknown pair-index/offset field")
        require(set(domains) <= set(self.domain_head_bindings), "Unknown or non-typed domain-input field")
        require(not (set(pairs) & set(self.domain_head_bindings)),
                "Typed ordered/tensor domains cannot use ordinary pair indices")
        require(not (set(offsets) & set(self.domain_head_bindings)),
                "Typed ordered/tensor domains cannot use graph-scalar prediction offsets")
        active = self.registry.enabled(enabled_groups, enabled_fields)
        actual_geometry_ids = actual_geometry_bindings = None
        if any(field.name in self.domain_head_bindings for field in active):
            actual_geometry_ids, actual_geometry_bindings = validate_geometry_context(batch, graphs, geometry_context)
        outputs = {}
        for field in active:
            key, head = self.keys[field.name], self.field_heads[self.keys[field.name]]
            if field.level == "ordered_entry":
                require(field.name in domains and isinstance(domains[field.name], OrderedEntryInputs),
                        f"{field.name}: explicit ordered-entry domain inputs required")
                prediction = head(h0, pos, batch, domains[field.name], actual_geometry_ids=actual_geometry_ids,
                                  actual_geometry_bindings=actual_geometry_bindings)
            elif field.representation == "symmetric_tensor6":
                require(field.name in domains and isinstance(domains[field.name], Tensor6Inputs),
                        f"{field.name}: explicit tensor6 geometry/origin inputs required")
                inputs = domains[field.name]
                inputs.__post_init__()
                require(inputs.geometry_ids == actual_geometry_ids
                        and inputs.frame_binding == self.domain_head_bindings[field.name]["frame_binding"],
                        f"{field.name}: tensor origin/frame differs from actual source geometry or head policy")
                prediction = head(h0, pos, batch, graphs, inputs.origin)
            elif field.representation in ("vector", "magnitude"):
                with torch.autocast(device_type=h0.device.type, enabled=False):
                    prediction = head(h0.float(), pos.float(), batch) if field.level == "atom" else (
                        head(h0.float(), pos.float(), batch, graphs))
            elif field.level == "pair":
                require(field.name in pairs, f"{field.name}: explicit source pair indices required")
                index = pairs[field.name]
                require(isinstance(index, Tensor) and index.dtype == torch.long and index.ndim == 2
                        and index.size(0) == 2 and index.device == h0.device
                        and bool(((index >= 0) & (index < len(h0))).all()), "Native pair index shape/domain differs")
                require(bool((batch[index[0]] == batch[index[1]]).all())
                        and bool((index[0] != index[1]).all()), "Pairs must be distinct atoms in one molecule")
                prediction = head(h0, pos, index)
            elif field.level == "atom":
                prediction = head(h0)
            else:
                feature = self.pooling_mixers[key](h0, batch, graphs) if (self.pooling_overrides.get(field.name)=='learned'
                    or field.pooling == "learned") else (
                    _pool(h0, batch, graphs, field.pooling))
                if self.forms[field.name] == "H2":
                    feature = self.group_projectors[field.group](feature)
                prediction = head(feature)
            if field.name in offsets:
                offset = offsets[field.name]
                require(field.kind == "regression" and field.level == "graph" and field.representation == "scalar"
                        and isinstance(offset, Tensor) and offset.shape == prediction.shape
                        and offset.device == prediction.device and offset.dtype == torch.float32
                        and not offset.requires_grad and bool(torch.isfinite(offset).all()),
                        "Only explicit detached D-4 graph-scalar prediction offsets are supported")
                prediction = prediction.float() + offset
            outputs[field.name] = prediction
        return outputs


class V3PretrainingModel(nn.Module):
    """Opt-in composition; it does not modify the existing encoder or factory."""
    def __init__(self, encoder, heads: V3HeadBank):
        super().__init__()
        require(getattr(encoder, "latent_dim", None) == heads.dim == 512,
                "V3 canonical H0 must remain 512-dimensional")
        self.encoder, self.heads = encoder, heads
        self.latent_dim = 512

    def encode_atoms(self, batch) -> Tensor:
        return self.encoder.encode_atoms(batch)

    def encode_graph(self, batch, pooling: str = "mean") -> Tensor:
        return self.encoder.encode_graph(batch, pooling=pooling)

    def forward_pretrain(self, batch, *, enabled_groups, enabled_fields=None,
                         pair_indices=None, prediction_offsets=None, domain_inputs=None, geometry_context=None):
        domain_kwargs = {} if not domain_inputs else {"domain_inputs": domain_inputs,
                                                     "geometry_context": geometry_context}
        return self.heads(self.encode_atoms(batch), ensure_batch_attr(batch), batch.pos,
                          enabled_groups=enabled_groups, enabled_fields=enabled_fields,
                          pair_indices=pair_indices, prediction_offsets=prediction_offsets, **domain_kwargs)
