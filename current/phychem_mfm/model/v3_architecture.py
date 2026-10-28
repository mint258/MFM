"""Opt-in C1 distance encoders; legacy factory, H0 API and defaults stay intact.

C1-b uses an element-pair affine distance before normalized Gaussians, as in
Uni-Mol's GaussianLayer. This implementation has K=64, one shared small MLP
and separate projections per layer; it is not a Uni-Mol model reproduction.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from copy import deepcopy
import math
import hashlib
import importlib.util
from pathlib import Path
import sys

import torch
from torch import Tensor, nn
from torch.utils.checkpoint import checkpoint
from torch_geometric.utils import to_dense_batch

from ..factory import build_model
from ..phase1.v3_contract import require
from .common import Linear, ensure_batch_attr
from .v3_geometry_fp32 import (LEGACY_GEOMETRY, RESIDUAL_GEOMETRY,
    validate_geometry_mode, require_geometry_binding, geometry_mode as geometry_mode_of,
    residual_pairwise_distance_fp32)
from .v3_attention_numerics import (LEGACY_AGGREGATION, CENTERED_FP32, aggregation_mode,
                                    require_centered_attention_context, centered_attention_value,
                                    require_centered_backbone, require_centered_f32_context, require_centered_packed_atoms)
from .v3_ffn_projection import LEGACY_FFN, ffn_projection_mode, require_ffn_backbone
from .v3_attention_projection import (LEGACY_PROJECTION, BLOCKED_PROJECTION,
    projection_mode, require_projection_backbone, attention_projection)
from .v3_numeric_stability import (COMPENSATED, LEGACY, numeric_mode, apply_numeric_mode,
                                    compensated_pairwise_norm3, require_fp32_context)

SOURCE_S_MEMORY_SHA256 = "170a7752bad1812d15dceace1613d19f579aec5d97a4965ed0960731cc53f232"


@dataclass(frozen=True)
class ArchitectureOptions:
    distance_bias: str = "C1-0"
    rbf_count: int = 64
    pair_dim: int = 64
    pair_hidden_dim: int = 64
    rbf_max_distance: float = 8.0
    cutoff: float | None = None

    def __post_init__(self):
        require(self.distance_bias in ("C1-0", "C1-a", "C1-b"), "Unknown C1 candidate")
        require(type(self.rbf_count) is int and self.rbf_count == 64, "C1 uses exactly 64 Gaussian kernels")
        require(all(type(value) is int and value > 0 for value in (self.pair_dim, self.pair_hidden_dim)),
                "Positive pair embedding/hidden dimensions required")
        require(type(self.rbf_max_distance) in (int, float) and math.isfinite(self.rbf_max_distance)
                and self.rbf_max_distance > 0, "Finite positive Gaussian center range required")
        require(self.cutoff is None or (type(self.cutoff) in (int, float)
                and math.isfinite(self.cutoff) and self.cutoff > 0), "Cutoff must be None or finite positive")
        require(self.distance_bias != "C1-0" or self.cutoff is None,
                "C1-0 retains its existing attention policy without a new cutoff")

    def validate_attention(self, backbone):
        if self.distance_bias == "C1-0":
            return
        require(backbone.get("use_dist_bias", True) is True, "C1 candidates require distance bias enabled")
        masked = backbone.get("use_radius_mask", False)
        require(type(masked) is bool, "Explicit boolean attention radius policy required")
        if masked:
            radius = float(backbone.get("radius", 8.0))
            require(math.isfinite(radius) and radius > 0 and self.cutoff == radius,
                    "Finite Gaussian cutoff must equal the enabled attention radius")
        else:
            require(self.cutoff is None,
                    "Global attention requires cutoff=None; an unused radius is not a cutoff")


class SharedGaussianPairEncoder(nn.Module):
    """Compute Euclidean geometry/RBF once, using input elements, never labels.

    The center range does not truncate global attention. A finite cutoff is
    supported only with a matching explicit attention radius. Pair types are
    ordered (source*n_types+destination), matching Uni-Mol's edge convention.
    """
    def __init__(self, options: ArchitectureOptions, n_atom_types: int, *, geometry_mode=LEGACY_GEOMETRY):
        super().__init__()
        require(options.distance_bias in ("C1-a", "C1-b"), "Shared encoder needs a C1-a/b option")
        self.options, self.n_atom_types = options, n_atom_types
        self.geometry_mode = validate_geometry_mode(geometry_mode)
        self.centers = nn.Parameter(torch.linspace(0., float(options.rbf_max_distance), options.rbf_count))
        width = float(options.rbf_max_distance) / (options.rbf_count - 1)
        self.raw_widths = nn.Parameter(torch.full((options.rbf_count,), math.log(math.expm1(width))))
        if options.distance_bias == "C1-b":
            # Constant-initialized pair transforms must not shift the common
            # pair MLP/projection initialization relative to C1-a.
            with torch.random.fork_rng(devices=[]):
                self.pair_scale = nn.Embedding(n_atom_types * n_atom_types, 1)
                self.pair_shift = nn.Embedding(n_atom_types * n_atom_types, 1)
            nn.init.ones_(self.pair_scale.weight)
            nn.init.zeros_(self.pair_shift.weight)
        else:
            self.pair_scale = self.pair_shift = None
        self.project = nn.Sequential(Linear(options.rbf_count, options.pair_hidden_dim), nn.SiLU(),
                                     Linear(options.pair_hidden_dim, options.pair_dim))

    def forward(self, pos: Tensor, elements: Tensor, mask: Tensor):
        require(pos.ndim == 3 and pos.size(-1) == 3 and pos.dtype == torch.float32
                and elements.shape == mask.shape == pos.shape[:2] and elements.dtype == torch.long
                and mask.dtype == torch.bool, "Dense fp32 coordinates/native element indices/mask required")
        if self.geometry_mode == RESIDUAL_GEOMETRY:
            require_fp32_context(self, pos)
        with torch.autocast(device_type=pos.device.type, enabled=False):
            # Direct Euclidean path has finite derivatives at coincident atoms.
            if self.geometry_mode == RESIDUAL_GEOMETRY:
                distances = residual_pairwise_distance_fp32(pos, pos)
            else:
                distances = (compensated_pairwise_norm3(pos.float(), pos.float())
                             if numeric_mode(self) == COMPENSATED else
                             torch.cdist(pos.float(), pos.float(), compute_mode='donot_use_mm_for_euclid_dist'))
            transformed = distances.unsqueeze(-1)
            if self.pair_scale is not None:
                pair_type = elements[:, :, None] * self.n_atom_types + elements[:, None, :]
                transformed = self.pair_scale(pair_type).float() * transformed + self.pair_shift(pair_type).float()
            widths = torch.nn.functional.softplus(self.raw_widths.float()) + 1e-5
            standardized = (transformed - self.centers.float()) / widths
            rbf = torch.exp(-0.5 * standardized.square()) / (math.sqrt(2 * math.pi) * widths)
        features = self.project(rbf)
        pair_valid = mask[:, :, None] & mask[:, None, :]
        envelope = pair_valid.to(features.dtype)
        if self.options.cutoff is not None:
            with torch.autocast(device_type=pos.device.type, enabled=False):
                radius = float(self.options.cutoff)
                cutoff_envelope = torch.where(distances < radius,
                    0.5 * (1. + torch.cos(math.pi * distances / radius)), torch.zeros_like(distances))
            envelope = envelope * cutoff_envelope.to(features.dtype)
        return features * envelope.unsqueeze(-1), distances


class SharedPairAttention(nn.Module):
    """Reuse all common attention parameters; replace only distance bias."""
    def __init__(self, original, pair_dim):
        super().__init__()
        self.attention_aggregation_mode = aggregation_mode(original)
        self.attention_projection_mode = projection_mode(original)
        self.geometry_mode = geometry_mode_of(original)
        self.dim, self.nheads, self.d_head = original.dim, original.nheads, original.d_head
        self.qkv, self.proj, self.attn_drop = original.qkv, original.proj, original.attn_drop
        self.use_radius_mask, self.radius = original.use_radius_mask, original.radius
        # A constant/head bias is softmax-null; no redundant constant is added.
        self.pair_projection = Linear(pair_dim, self.nheads, bias=False)

    def forward(self, x, pair_features, distances, mask):
        if self.attention_aggregation_mode == CENTERED_FP32:
            require_centered_attention_context(self, mask, x, pair_features, distances)
        bsz, seqlen, _ = x.shape
        qkv = (attention_projection(self, self.qkv, x)
               if self.attention_projection_mode == BLOCKED_PROJECTION else self.qkv(x))
        q, k, v = qkv.view(bsz, seqlen, 3, self.nheads, self.d_head).unbind(2)
        q, k, v = (value.transpose(1, 2) for value in (q, k, v))
        logits = torch.matmul(q, k.transpose(-2, -1)) / math.sqrt(self.d_head)
        bias = self.pair_projection(pair_features).permute(0, 3, 1, 2).contiguous()
        logits = logits + bias
        logits = logits.masked_fill(~mask[:, None, None, :], -1e9)
        if self.use_radius_mask:
            logits = logits.masked_fill(distances[:, None, :, :] > self.radius, -1e9)
        weights = self.attn_drop(torch.softmax(logits, dim=-1))
        if self.attention_aggregation_mode == CENTERED_FP32:
            context = centered_attention_value(weights, v, mask, attention_dropout=self.attn_drop)
            context = context.transpose(1, 2).contiguous().view(bsz, seqlen, self.dim)
        else:
            context = torch.matmul(weights, v).transpose(1, 2).contiguous().view(bsz, seqlen, self.dim)
        output = (attention_projection(self, self.proj, context)
                  if self.attention_projection_mode == BLOCKED_PROJECTION else self.proj(context))
        return output * mask.unsqueeze(-1).to(context.dtype)


class SharedPairTransformerLayer(nn.Module):
    def __init__(self, original, pair_dim):
        super().__init__()
        self.norm1, self.norm2, self.ffn = original.norm1, original.norm2, original.ffn
        self.attn = SharedPairAttention(original.attn, pair_dim)

    def forward(self, x, pair_features, distances, mask):
        x = x + self.attn(self.norm1(x), pair_features, distances, mask)
        x = x + self.ffn(self.norm2(x))
        return x * mask.unsqueeze(-1).to(x.dtype)


class SharedPairBackbone(nn.Module):
    """Canonical packed H0, with one shared pair encoding per physical batch."""
    def __init__(self, original, options):
        super().__init__()
        self.attention_aggregation_mode = aggregation_mode(original)
        self.attention_projection_mode = projection_mode(original)
        self.geometry_mode = geometry_mode_of(original)
        self.ffn_projection_mode = ffn_projection_mode(original)
        self.n_atom_types, self.dim = original.n_atom_types, original.dim
        self.activation_checkpointing = original.activation_checkpointing
        self.atom_emb, self.out_norm = original.atom_emb, original.out_norm
        self.options = options
        self.pair_encoder = SharedGaussianPairEncoder(options, self.n_atom_types, geometry_mode=self.geometry_mode)
        self.layers = nn.ModuleList([SharedPairTransformerLayer(layer, options.pair_dim) for layer in original.layers])

    def get_extra_state(self):
        result = {"schema": "model_v3_shared_gaussian_backbone_v1", "options": asdict(self.options),
                  "n_atom_types": self.n_atom_types, "dim": self.dim}
        if numeric_mode(self) != LEGACY:
            result['numeric_mode'] = numeric_mode(self)
        if self.attention_aggregation_mode != LEGACY_AGGREGATION:
            result['attention_aggregation_mode'] = self.attention_aggregation_mode
        if self.attention_projection_mode != LEGACY_PROJECTION:
            result["attention_projection_mode"] = self.attention_projection_mode
        if self.geometry_mode != LEGACY_GEOMETRY:
            result["geometry_mode"] = self.geometry_mode
        if self.ffn_projection_mode != LEGACY_FFN:
            result["ffn_projection_mode"] = self.ffn_projection_mode
        return result

    def set_extra_state(self, state):
        require(state == self.get_extra_state(), "C1 checkpoint/options differ")

    def forward(self, data):
        require(getattr(data, "pos", None) is not None, "C1 H0 requires coordinates")
        require_ffn_backbone(self, expected_mode=self.ffn_projection_mode)
        require_geometry_binding(self, expected_mode=self.geometry_mode)
        if self.attention_projection_mode == BLOCKED_PROJECTION:
            require_projection_backbone(self, expected_mode=BLOCKED_PROJECTION)
        if self.attention_aggregation_mode == CENTERED_FP32:
            require_centered_backbone(self)
            require_centered_f32_context(self, data.pos)
            require_centered_packed_atoms(data.pos)
        batch = ensure_batch_attr(data)
        raw = data.x[:, 0] if data.x.ndim == 2 else data.x
        elements = raw.long().clamp(min=0, max=self.n_atom_types - 1)
        embedded, mask = to_dense_batch(self.atom_emb(elements), batch, fill_value=0.)
        pos, _ = to_dense_batch(data.pos.to(torch.float32), batch, fill_value=0.)
        dense_elements, _ = to_dense_batch(elements, batch, fill_value=0)
        pair_features, distances = self.pair_encoder(pos, dense_elements, mask)
        for layer in self.layers:
            if self.activation_checkpointing and self.training and torch.is_grad_enabled():
                embedded = checkpoint(layer, embedded, pair_features, distances, mask, use_reentrant=False)
            else:
                embedded = layer(embedded, pair_features, distances, mask)
        return (self.out_norm(embedded) * mask.unsqueeze(-1).to(embedded.dtype))[mask]


def configuration_with_architecture(config, options: ArchitectureOptions):
    """Return a complete model configuration with explicit C1 semantics."""
    require(isinstance(options, ArchitectureOptions), "Explicit architecture options required")
    result = deepcopy(dict(config))
    options.validate_attention(result["backbone"])
    existing = result["backbone"].get("v3_architecture")
    require(existing is None or existing == asdict(options), "Declared C1 configuration/options differ")
    if options.distance_bias == "C1-0":
        require(existing is None, "C1-0 must retain its original unextended model configuration")
    else:
        result["backbone"]["v3_architecture"] = asdict(options)
    return result


def source_s_architecture_configuration(config, options=None):
    """Seal the actual stage1 tiled65536 control builder into model identity."""
    if options is None:
        declared = config["backbone"].get("v3_architecture")
        options = ArchitectureOptions(**declared) if declared is not None else ArchitectureOptions()
    result = configuration_with_architecture(config, options)
    memory = {"kind": "source_s_tiled_distance_v1", "pair_rows": 65536,
              "source_sha256": SOURCE_S_MEMORY_SHA256}
    require(result["backbone"].get("v3_legacy_memory", memory) == memory, "Source S memory configuration differs")
    result["backbone"]["v3_legacy_memory"] = memory
    return result


def _source_memory_builder(memory):
    require(memory == {"kind": "source_s_tiled_distance_v1", "pair_rows": 65536,
                       "source_sha256": SOURCE_S_MEMORY_SHA256}, "Only the frozen measured S memory builder is supported")
    source = Path(__file__).absolute().parents[3] / "workflows/sprime_s/scripts/s_model_memory_v1.py"
    require(source.is_file() and not source.is_symlink()
            and hashlib.sha256(source.read_bytes()).hexdigest() == SOURCE_S_MEMORY_SHA256,
            "Frozen measured S memory source differs")
    name = "model_v3_architecture_s_memory_" + SOURCE_S_MEMORY_SHA256[:16]
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, source)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name].build_memory_bounded_model


def build_source_s_architecture_model(config, options=None):
    """Production S comparison entry: measured tiled control, declared C1 path."""
    return build_architecture_model(source_s_architecture_configuration(config, options))


def build_architecture_model(config, options=None, *, legacy_builder=build_model):
    """Explicit builder; C1-0 returns exactly the selected legacy builder path.

    Passing the existing S memory-bounded builder retains its tiled C1-0 path.
    New C1 initialization does not alter common heads or global RNG state.
    """
    declared = config["backbone"].get("v3_architecture")
    if options is None:
        require(declared is None or type(declared) is dict, "Explicit C1 configuration mapping required")
        options = ArchitectureOptions(**declared) if declared is not None else ArchitectureOptions()
    resolved = configuration_with_architecture(config, options)
    legacy_config = deepcopy(resolved)
    legacy_config["backbone"].pop("v3_architecture", None)
    memory = legacy_config["backbone"].pop("v3_legacy_memory", None)
    if memory is not None:
        require(legacy_builder is build_model, "Sealed S memory config chooses its own fixed builder")
        legacy_builder = _source_memory_builder(memory)
    model = legacy_builder(legacy_config)
    if memory is not None:
        model.backbone_config["v3_legacy_memory"] = deepcopy(memory)
    if options.distance_bias != "C1-0":
        require(not next(model.parameters()).is_cuda, "Build architecture on CPU before device transfer")
        with torch.random.fork_rng(devices=[]):
            model.backbone = SharedPairBackbone(model.backbone, options)
        model.backbone_config["v3_architecture"] = asdict(options)
        if hasattr(model, "s_memory_implementation"):
            model.v3_legacy_control_memory_implementation = deepcopy(model.s_memory_implementation)
            del model.s_memory_implementation
    apply_numeric_mode(model, numeric_mode(model))
    model.v3_architecture_options = asdict(options)
    return model
