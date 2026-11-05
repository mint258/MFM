"""Temporary profiler labels for the unchanged dense-attention arithmetic.

Labels do not alter module children, parameters, state keys or public H0 APIs.
Inclusive forward subregions and whole backward regions intentionally overlap;
their times must not be summed into an exclusive runtime partition.
"""
from __future__ import annotations

from contextlib import contextmanager
import functools
import math
from types import MethodType

import torch
from torch.profiler import record_function

from .attention import DenseGeoSelfAttention


def labeled_dense_attention(self, x, pos, mask):
    bsz, seqlen, _ = x.shape
    with record_function("model_v3/attention/qkv"):
        qkv = self.qkv(x).view(bsz, seqlen, 3, self.nheads, self.d_head)
        q, k, v = qkv.unbind(dim=2)
        q, k, v = q.transpose(1, 2), k.transpose(1, 2), v.transpose(1, 2)
    with record_function("model_v3/attention/qk"):
        logits = torch.matmul(q, k.transpose(-2, -1)) / math.sqrt(self.d_head)
    with record_function("model_v3/attention/distance"):
        diff = pos[:, :, None, :] - pos[:, None, :, :]
        dist2 = (diff * diff).sum(dim=-1)
    if self.use_dist_bias and self.dist_mlp is not None:
        with record_function("model_v3/attention/dist_mlp"):
            bias = self.dist_mlp(dist2.unsqueeze(-1))
            bias = bias.permute(0, 3, 1, 2).contiguous()
            logits = logits + bias
    with record_function("model_v3/attention/mask"):
        logits = logits.masked_fill((~mask)[:, None, None, :], -1e9)
        if self.use_radius_mask:
            logits = logits.masked_fill(dist2[:, None, :, :] > self.radius * self.radius, -1e9)
    with record_function("model_v3/attention/softmax"):
        attn = self.attn_drop(torch.softmax(logits, dim=-1))
    with record_function("model_v3/attention/av"):
        ctx = torch.matmul(attn, v)
        ctx = ctx.transpose(1, 2).contiguous().view(bsz, seqlen, self.dim)
    with record_function("model_v3/attention/projection"):
        out = self.proj(ctx)
        out = out * mask.unsqueeze(-1).to(out.dtype)
    return out, attn


@contextmanager
def instrument_model(model):
    """Add labels for one bounded measurement, then restore every forward."""
    originals = []

    def wrap(module, name):
        old = module.forward
        @functools.wraps(old)
        def labeled(*args, **kwargs):
            with record_function(name):
                return old(*args, **kwargs)
        originals.append((module, old))
        module.forward = labeled

    for name, module in model.named_modules():
        if isinstance(module, DenseGeoSelfAttention):
            originals.append((module, module.forward))
            module.forward = MethodType(labeled_dense_attention, module)
        elif name.endswith(".ffn"):
            wrap(module, "model_v3/ffn")
        elif name == "geometry_head":
            wrap(module, "model_v3/denoising_head")
        elif name in {"element_head", "bond_head", "energy_head", "charge_head"} or (
                name.count(".") == 1 and "descriptor_heads." in name):
            wrap(module, "model_v3/other_heads")
    try:
        yield model
    finally:
        for module, original in reversed(originals):
            module.forward = original


def padding_statistics(atom_counts, *, views=3):
    counts = tuple(int(value) for value in atom_counts)
    if not counts or min(counts) < 1 or type(views) is not int or views < 1:
        raise ValueError("Positive base molecule atom counts and view count required")
    largest = max(counts)
    native_atoms = sum(counts)
    native_pairs = sum(n * n for n in counts)
    padded_atoms = len(counts) * largest
    padded_pairs = len(counts) * largest * largest
    return {"base_molecules": len(counts), "base_atoms": native_atoms,
            "encoder_atoms": views * native_atoms, "view_graphs": views * len(counts),
            "largest_atoms": largest, "native_atom_fraction": native_atoms / padded_atoms,
            "native_pair_fraction": native_pairs / padded_pairs,
            "native_pairs_including_diagonal": views * native_pairs,
            "padded_atoms": views * padded_atoms, "padded_pairs_including_diagonal": views * padded_pairs}


def profiler_rows(profiler):
    """Export measured values with explicit units, retaining operators too."""
    rows = []
    for event in profiler.key_averages():
        rows.append({"name": event.key, "calls": int(event.count),
                     "cpu_total_us": float(event.cpu_time_total),
                     "cpu_self_us": float(event.self_cpu_time_total),
                     "device_total_us": float(getattr(event, "device_time_total", 0.)),
                     "device_self_us": float(getattr(event, "self_device_time_total", 0.)),
                     "cpu_memory_net_bytes": int(event.cpu_memory_usage),
                     "device_memory_net_bytes": int(getattr(event, "device_memory_usage", 0))})
    return sorted(rows, key=lambda row: (-row["device_total_us"], row["name"]))
