"""Opt-in execution candidates; no candidate is accepted by construction.

FP32 parameters and original state keys are retained. Selective bf16 affects
backbone QKV/QK/AV/projection and FFN matrix operations only. Coordinates,
distance bias, normalizations, final H0 and the equivariant head remain fp32.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass
import math
import re
from typing import Mapping

import torch
from torch import nn
from torch.utils.checkpoint import checkpoint

from .attention import DenseGeoSelfAttention, DenseFFN
from .heads import EquivariantDenoisingHead
from .v3_attention_numerics import reject_centered_runtime


@dataclass(frozen=True)
class PerformanceOptions:
    precision: str = "fp32"
    distance_implementation: str = "tiled"
    distance_pair_rows: int = 65536
    distance_checkpointing: bool = True
    backbone_checkpointing: bool | None = None
    head_checkpointing: bool = True
    attention_backend: str = "dense"
    sparse_query_chunk: int = 32
    fused_adamw: bool = False
    tf32: bool = False
    compile_backbone: bool = False
    compile_dynamic: bool = True

    def __post_init__(self):
        if self.precision not in {"fp32", "bf16"} or self.distance_implementation not in {"dense", "tiled"}:
            raise ValueError("Explicit supported precision and distance implementation required")
        if self.attention_backend not in {"dense", "sparse_radius"}:
            raise ValueError("Unknown attention backend")
        if type(self.distance_pair_rows) is not int or self.distance_pair_rows < 1 or (
                type(self.sparse_query_chunk) is not int or self.sparse_query_chunk < 1):
            raise ValueError("Positive bounded chunk dimensions required")
        for name in ("distance_checkpointing", "head_checkpointing", "fused_adamw", "tf32",
                     "compile_backbone", "compile_dynamic"):
            if type(getattr(self, name)) is not bool:
                raise ValueError(f"{name} must be a boolean")
        if self.backbone_checkpointing is not None and type(self.backbone_checkpointing) is not bool:
            raise ValueError("backbone_checkpointing must be a boolean or None")


def _matmul_context(tensor, precision):
    return torch.autocast(device_type=tensor.device.type, dtype=torch.bfloat16, enabled=precision == "bf16")


def _fp32_context(tensor):
    return torch.autocast(device_type=tensor.device.type, enabled=False)


def _reuse_modules(target, original):
    nn.Module.__init__(target)
    for name, module in original.named_children():
        target.add_module(name, module)
    for name, buffer in original.named_buffers(recurse=False):
        target.register_buffer(name, buffer, persistent=name not in original._non_persistent_buffers_set)
    for name, parameter in original.named_parameters(recurse=False):
        target.register_parameter(name, parameter)


class ConfigurableTiledDistanceMLP(nn.Sequential):
    def __init__(self, original, *, pair_rows=65536, activation_checkpointing=True):
        if not isinstance(original, nn.Sequential) or len(original) != 3 or original[0].in_features != 1:
            raise ValueError("Original scalar-distance MLP required")
        super().__init__(*list(original.children()))
        self.pair_rows = int(pair_rows)
        self.activation_checkpointing = bool(activation_checkpointing)

    def _rows(self, value):
        return super().forward(value)

    def forward(self, value):
        with _fp32_context(value):
            value = value.float()
            shape = value.shape[:-1]
            flat = value.reshape(-1, 1)
            if len(flat) <= self.pair_rows:
                return self._rows(value)
            parts = []
            for start in range(0, len(flat), self.pair_rows):
                part = flat[start:start + self.pair_rows]
                if self.activation_checkpointing and torch.is_grad_enabled() and any(p.requires_grad for p in self.parameters()):
                    parts.append(checkpoint(self._rows, part, use_reentrant=False, preserve_rng_state=True))
                else:
                    parts.append(self._rows(part))
            return torch.cat(parts, dim=0).reshape(*shape, self[-1].out_features)


class RuntimeDenseAttention(DenseGeoSelfAttention):
    def __init__(self, original, *, precision="fp32"):
        reject_centered_runtime(original)
        _reuse_modules(self, original)
        for name in ("dim", "nheads", "d_head", "use_dist_bias", "use_radius_mask", "radius"):
            setattr(self, name, getattr(original, name))
        self.precision = precision

    def forward(self, x, pos, mask):
        bsz, seqlen, _ = x.shape
        with _matmul_context(x, self.precision):
            qkv = self.qkv(x.float()).view(bsz, seqlen, 3, self.nheads, self.d_head)
            q, k, v = qkv.unbind(dim=2)
            q, k, v = q.transpose(1, 2), k.transpose(1, 2), v.transpose(1, 2)
            logits = torch.matmul(q, k.transpose(-2, -1))
        with _fp32_context(x):
            logits = logits.float() / math.sqrt(self.d_head)
            coordinates = pos.float()
            diff = coordinates[:, :, None, :] - coordinates[:, None, :, :]
            dist2 = (diff * diff).sum(dim=-1)
            if self.use_dist_bias and self.dist_mlp is not None:
                bias = self.dist_mlp(dist2.unsqueeze(-1))
                logits = logits + bias.permute(0, 3, 1, 2).contiguous().float()
            logits = logits.masked_fill((~mask)[:, None, None, :], -1e9)
            if self.use_radius_mask:
                logits = logits.masked_fill(dist2[:, None, :, :] > self.radius * self.radius, -1e9)
            attention = self.attn_drop(torch.softmax(logits, dim=-1))
        with _matmul_context(x, self.precision):
            context = torch.matmul(attention, v)
            context = context.transpose(1, 2).contiguous().view(bsz, seqlen, self.dim)
            output = self.proj(context)
        return output.float() * mask.unsqueeze(-1).float(), attention


class SparseRadiusAttention(RuntimeDenseAttention):
    """Query-chunk neighbor attention; only existing radius masks may use it.

    Unlike the dense private attention API, weights are not materialized. The
    enclosing Transformer discards that tuple member. No radius is introduced
    for a model whose original attention was global. Dropout must be zero,
    because sparse draws would change its RNG/order recipe.
    """
    def __init__(self, original, *, precision="fp32", query_chunk=32):
        super().__init__(original, precision=precision)
        if not self.use_radius_mask:
            raise ValueError("Sparse radius attention cannot truncate an originally global model")
        if isinstance(self.attn_drop, nn.Dropout) and self.attn_drop.p != 0:
            raise ValueError("Sparse dropout requires an independently declared RNG protocol")
        self.query_chunk = int(query_chunk)

    def forward(self, x, pos, mask):
        bsz, seqlen, _ = x.shape
        with _matmul_context(x, self.precision):
            qkv = self.qkv(x.float()).view(bsz, seqlen, 3, self.nheads, self.d_head)
            q, k, v = (part.transpose(1, 2) for part in qkv.unbind(dim=2))
        graphs = []
        for graph in range(bsz):
            valid = torch.where(mask[graph])[0]
            if not len(valid):
                graphs.append(x.new_zeros((seqlen, self.dim), dtype=torch.float32))
                continue
            qg, kg, vg = (item[graph].index_select(1, valid).float() for item in (q, k, v))
            coordinates = pos[graph].index_select(0, valid).float()
            chunks = []
            for start in range(0, len(valid), self.query_chunk):
                end = min(start + self.query_chunk, len(valid))
                with _fp32_context(x):
                    difference = coordinates[start:end, None] - coordinates[None]
                    distances2 = difference.square().sum(-1)
                    src, dst = torch.where(distances2 <= self.radius * self.radius)
                    # Every valid query contains itself, so denominators cannot be zero.
                    score = (qg[:, start + src] * kg[:, dst]).sum(-1) / math.sqrt(self.d_head)
                    if self.use_dist_bias and self.dist_mlp is not None:
                        score = score + self.dist_mlp(distances2[src, dst, None]).transpose(0, 1).float()
                    scatter = src[None].expand(self.nheads, -1)
                    maxima = score.new_full((self.nheads, end - start), -torch.inf)
                    maxima = maxima.scatter_reduce(1, scatter, score, reduce="amax", include_self=True)
                    numerators = (score - maxima.gather(1, scatter)).exp()
                    denominator = score.new_zeros((self.nheads, end - start)).scatter_add(1, scatter, numerators)
                    weights = numerators / denominator.gather(1, scatter)
                    weighted = weights[..., None] * vg[:, dst]
                    context = weighted.new_zeros((self.nheads, end - start, self.d_head)).scatter_add(
                        1, scatter[..., None].expand(-1, -1, self.d_head), weighted)
                    chunks.append(context)
            packed = torch.cat(chunks, dim=1).transpose(0, 1).contiguous().view(len(valid), self.dim)
            graphs.append(packed.new_zeros((seqlen, self.dim)).index_copy(0, valid, packed))
        with _matmul_context(x, self.precision):
            output = self.proj(torch.stack(graphs))
        return output.float() * mask.unsqueeze(-1).float(), None


class RuntimeFFN(DenseFFN):
    def __init__(self, original, *, precision="fp32"):
        _reuse_modules(self, original)
        self.precision = precision

    def forward(self, value):
        with _matmul_context(value, self.precision):
            result = self.net(value.float())
        return result.float()


class ConfigurableDenoisingHead(EquivariantDenoisingHead):
    def __init__(self, original, *, activation_checkpointing=True):
        _reuse_modules(self, original)
        for name in ("radius", "normalization", "message_layers", "pair_chunk_size", "rbf_gamma"):
            setattr(self, name, getattr(original, name))
        self.activation_checkpointing = bool(activation_checkpointing)

    def forward(self, atom_repr, pos, batch):
        with _fp32_context(pos):
            h, pos = atom_repr.float(), pos.float()
            if pos.ndim != 2 or pos.size(-1) != 3 or len(h) != len(pos) or len(batch) != len(pos):
                raise ValueError("Head expects packed atoms, coordinates and molecule IDs")
            if not len(pos):
                return pos.clone()
            src, dst = self._edges(pos, batch)
            degree = torch.bincount(src, minlength=len(pos)).clamp_min(1).float().sqrt()[:, None]
            recompute = self.activation_checkpointing and torch.is_grad_enabled()
            for layer in self.messages:
                def message_chunk(features, coordinates, i, j, module=layer):
                    return module(self._features(features, coordinates, i, j)[0])
                aggregated = torch.zeros_like(h)
                for start in range(0, len(src), self.pair_chunk_size):
                    i, j = src[start:start + self.pair_chunk_size], dst[start:start + self.pair_chunk_size]
                    value = checkpoint(message_chunk, h, pos, i, j, use_reentrant=False) if recompute else message_chunk(h, pos, i, j)
                    aggregated = aggregated.index_add(0, i, value)
                h = h + aggregated / degree
            noise = torch.zeros_like(pos)
            for start in range(0, len(src), self.pair_chunk_size):
                i, j = src[start:start + self.pair_chunk_size], dst[start:start + self.pair_chunk_size]
                value = checkpoint(self._predict_chunk, h, pos, i, j, use_reentrant=False) if recompute else self._predict_chunk(h, pos, i, j)
                noise = noise.index_add(0, i, value.float())
            return noise / degree if self.normalization == "sqrt_neighbors" else noise


def build_performance_model(configuration: Mapping, options=PerformanceOptions()):
    """Build a fresh candidate with unchanged H0 methods and original keys."""
    from ..factory import build_model
    reject_centered_runtime(dict(configuration))
    model = build_model(configuration)
    if options.backbone_checkpointing is not None:
        model.backbone.activation_checkpointing = options.backbone_checkpointing
    for layer in model.backbone.layers:
        attention = layer.attn
        if options.distance_implementation == "tiled" and attention.dist_mlp is not None:
            attention.dist_mlp = ConfigurableTiledDistanceMLP(attention.dist_mlp,
                pair_rows=options.distance_pair_rows, activation_checkpointing=options.distance_checkpointing)
        attention_type = SparseRadiusAttention if options.attention_backend == "sparse_radius" else RuntimeDenseAttention
        kwargs = {"query_chunk": options.sparse_query_chunk} if options.attention_backend == "sparse_radius" else {}
        layer.attn = attention_type(attention, precision=options.precision, **kwargs)
        layer.ffn = RuntimeFFN(layer.ffn, precision=options.precision)
    if isinstance(model.geometry_head, EquivariantDenoisingHead):
        model.geometry_head = ConfigurableDenoisingHead(model.geometry_head,
                                                       activation_checkpointing=options.head_checkpointing)
    if options.compile_backbone:
        # Compiling only the bound forward retains state-dict key names and H0 APIs.
        model.backbone.forward = torch.compile(model.backbone.forward, dynamic=options.compile_dynamic, fullgraph=False)
    model.v3_performance_options = asdict(options)
    return model


def performance_forward_pretrain(model, batch, objectives):
    """Keep all heads/loss inputs fp32 outside selective backbone matmuls."""
    with _fp32_context(batch.pos):
        return model.forward_pretrain(batch, objectives)


@contextmanager
def execution_context(options):
    previous = (torch.backends.cuda.matmul.allow_tf32, torch.backends.cudnn.allow_tf32)
    torch.backends.cuda.matmul.allow_tf32 = options.tf32
    torch.backends.cudnn.allow_tf32 = options.tf32
    try:
        yield
    finally:
        torch.backends.cuda.matmul.allow_tf32, torch.backends.cudnn.allow_tf32 = previous


def make_adamw(model, configuration, options):
    if "fused" in configuration:
        raise ValueError("Fused execution belongs to the explicit performance options")
    if options.fused_adamw and any(parameter.device.type != "cuda" for parameter in model.parameters()):
        raise ValueError("Fused AdamW candidate requires the measured CUDA environment")
    if options.fused_adamw:
        return torch.optim.AdamW(model.parameters(), **dict(configuration), fused=True)
    # Preserve the original automatic foreach/single-tensor dispatch. In Torch
    # 2.10 explicit fused=False differs from leaving both execution flags None.
    return torch.optim.AdamW(model.parameters(), **dict(configuration))


def choose_checkpointing(*, gpu_name, total_memory_bytes, free_memory_bytes,
                         padded_cost, model_configuration_sha256, measured_capacity=None):
    """Only disable recomputation within an actual all-off capacity measurement.

    Unknown GPU types/capacities/batch costs default to checkpoints on. Capacity
    evidence must be pinned by the calling run configuration, not guessed from
    a GPU marketing name or from an all-on measurement.
    """
    enabled = {"backbone_checkpointing": True, "head_checkpointing": True,
               "distance_checkpointing": True, "reason": "UNVERIFIED_CAPACITY_KEEP_CHECKPOINTS"}
    if measured_capacity is None:
        return enabled
    required = {"gpu_name", "total_memory_bytes", "padded_cost", "peak_allocated_bytes",
                "model_configuration_sha256", "measurement_sha256", "checkpoint_mode"}
    row = dict(measured_capacity)
    if not required <= set(row) or row["checkpoint_mode"] != "all_off" or not (
            re.fullmatch(r"[0-9a-f]{64}", row.get("measurement_sha256", ""))):
        raise ValueError("Pinned all-off measurement required for automatic checkpoint selection")
    compatible = (row["gpu_name"] == gpu_name and row["total_memory_bytes"] == total_memory_bytes
                  and row["model_configuration_sha256"] == model_configuration_sha256
                  and padded_cost <= row["padded_cost"]
                  and 0 < row["peak_allocated_bytes"] <= .85 * total_memory_bytes
                  and free_memory_bytes >= row["peak_allocated_bytes"] + .1 * total_memory_bytes)
    if not compatible:
        return enabled
    return {"backbone_checkpointing": False, "head_checkpointing": False,
            "distance_checkpointing": False, "reason": "WITHIN_PINNED_ALL_OFF_CAPACITY",
            "measurement_sha256": row["measurement_sha256"]}
