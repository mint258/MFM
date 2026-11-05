"""Encoder-only padding reduction inside ONE already prepared logical batch.

No sampling, views, targets, heads or loss reductions occur here. The original
full packed rows are restored before the unchanged caller observes H0.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import torch
from torch import nn
from torch_geometric.data import Data
from .backbone import RealCoordTransformerBackbone
from .common import ensure_batch_attr


@dataclass(frozen=True)
class LogicalBatchPadding:
    mode: str = "logical_batch_chunks_v1"
    atom_bucket_width: int = 16
    max_graphs_per_chunk: int = 32
    max_padded_cost_per_chunk: int = 1000000

    def __post_init__(self):
        if self.mode != "logical_batch_chunks_v1":
            raise ValueError("Unknown logical-batch padding mode")
        for key in ("atom_bucket_width", "max_graphs_per_chunk", "max_padded_cost_per_chunk"):
            if type(getattr(self, key)) is not int or getattr(self, key) <= 0:
                raise ValueError("Positive integer logical-batch padding bounds required")
        if self.atom_bucket_width > 1024 or self.max_graphs_per_chunk > 4096:
            raise ValueError("Bounded logical-batch grouping required")


def logical_batch_counts(data):
    batch = ensure_batch_attr(data)
    if (batch.dtype != torch.long or batch.ndim != 1 or len(batch) == 0
            or data.x.shape[0] != len(batch) or data.pos.shape != (len(batch), 3)
            or batch.device != data.x.device or batch.device != data.pos.device):
        raise ValueError("Nonempty packed logical batch with aligned atoms/positions/graph IDs required")
    if bool((batch < 0).any()) or bool((batch[1:] < batch[:-1]).any()):
        raise ValueError("Original contiguous packed graph order required")
    counts = torch.bincount(batch).detach().cpu().tolist()
    if not counts or any(n <= 0 for n in counts):
        raise ValueError("Empty graph or noncontiguous graph IDs are not admitted")
    return batch, counts


def chunk_plan(counts, specification):
    if not counts or any(type(n) is not int or n <= 0 for n in counts):
        raise ValueError("Positive actual graph sizes required")
    ordered = sorted(range(len(counts)), key=lambda g: (
        (counts[g] - 1) // specification.atom_bucket_width, counts[g], g))
    chunks, current = [], []
    for graph in ordered:
        proposed = current + [graph]
        cost = len(proposed) * max(counts[g] for g in proposed) ** 2
        different_bucket = current and ((counts[current[0]] - 1) // specification.atom_bucket_width
                                        != (counts[graph] - 1) // specification.atom_bucket_width)
        if current and (different_bucket or len(proposed) > specification.max_graphs_per_chunk
                        or cost > specification.max_padded_cost_per_chunk):
            chunks.append(tuple(current));current = []
        current.append(graph)
    if current:chunks.append(tuple(current))
    if sorted(g for group in chunks for g in group) != list(range(len(counts))):
        raise RuntimeError("Logical chunk plan omitted or repeated a graph")
    return tuple(chunks)


class LogicalBatchBackbone(RealCoordTransformerBackbone):
    """Same child modules/Parameter objects/keys; optional strict capacity guard.

    A chunk contains complete physical graphs. All stochastic view generation
    precedes this call; dropout is rejected, including later runtime changes.
    The head sees the complete original logical batch after H0 row restoration.
    """
    def __init__(self, original, *, padding=None, capacity_guard=None):
        if type(original) is not RealCoordTransformerBackbone:
            raise ValueError("Logical-batch execution supports only the declared original backbone")
        nn.Module.__init__(self)
        for name, module in original.named_children():self.add_module(name, module)
        for name, parameter in original.named_parameters(recurse=False):self.register_parameter(name, parameter)
        for name, buffer in original.named_buffers(recurse=False):
            self.register_buffer(name, buffer, persistent=name not in original._non_persistent_buffers_set)
        for name in ("n_atom_types", "dim", "activation_checkpointing", "distance_bias_projection_bias"):
            setattr(self, name, getattr(original, name))
        self.padding, self.capacity_guard = padding, capacity_guard
        self.performance_execution_contract = {
            "schema": "model_v3_logical_batch_runtime_contract_v1",
            "padding": None if padding is None else asdict(padding),
            "capacity_observation": None if capacity_guard is None else capacity_guard.observation["source"],
            "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
        self.last_logical_batch_execution = None
        self.train(original.training)
        self._require_context()

    def _require_context(self):
        if self.padding is not None:
            for module in self.modules():
                if isinstance(module, nn.modules.dropout._DropoutNd) and module.p != 0:
                    raise ValueError("Logical-batch chunks require zero dropout to retain original RNG consumption")
                if isinstance(module, nn.modules.batchnorm._BatchNorm):
                    raise ValueError("Across-graph batch normalization is not a local padding operation")

    def forward(self, data):
        self._require_context()
        batch, counts = logical_batch_counts(data)
        if self.capacity_guard is not None:self.capacity_guard.check(data, counts)
        self.last_logical_batch_execution = {
            "schema": "model_v3_logical_batch_execution_v1",
            "logical_graph_count": len(counts), "logical_atom_count": len(batch), "graph_atom_counts": list(counts),
            "legacy_dense_padded_cost": len(counts) * max(counts) ** 2,
            "original_atom_and_graph_order_restored": True, "views_noise_masks_targets_regenerated": False,
            "loss_or_group_reduction_per_chunk": False}
        if self.padding is None:
            return RealCoordTransformerBackbone.forward(self, data)
        if data.pos.dtype != torch.float32 or torch.is_autocast_enabled(data.pos.device.type):
            raise ValueError("Logical-batch A candidate requires original fp32 geometry and no outer AMP")
        plan = chunk_plan(counts, self.padding)
        offsets, offset = [], 0
        for size in counts:offsets.append(offset);offset += size
        outputs, original_rows = [], []
        for group in plan:
            rows = torch.cat([torch.arange(offsets[g], offsets[g] + counts[g], device=batch.device) for g in group])
            local_ids = torch.repeat_interleave(torch.arange(len(group), device=batch.device),
                                               batch.new_tensor([counts[g] for g in group]))
            # x/pos are selected from the actual finished batch. No degrade_once,
            # RNG draws, local padding noise, mask construction or head calls.
            piece = Data(x=data.x.index_select(0, rows), pos=data.pos.index_select(0, rows), batch=local_ids)
            outputs.append(RealCoordTransformerBackbone.forward(self, piece))
            original_rows.append(rows)
        rows = torch.cat(original_rows)
        values = torch.cat(outputs)
        result = values.new_zeros((len(batch), self.dim)).index_copy(0, rows, values)
        serialized = json.dumps(plan, separators=(",", ":")).encode()
        self.last_logical_batch_execution = {
            "schema": "model_v3_logical_batch_execution_v1", "padding": asdict(self.padding),
            "logical_graph_count": len(counts), "logical_atom_count": len(batch), "graph_atom_counts": list(counts),
            "legacy_dense_padded_cost": len(counts) * max(counts) ** 2,
            "chunked_dense_padded_cost": sum(len(group) * max(counts[g] for g in group) ** 2 for group in plan),
            "chunk_graphs": [list(group) for group in plan], "chunk_plan_sha256": hashlib.sha256(serialized).hexdigest(),
            "retained_oversize_singletons": sum(len(group) == 1 and counts[group[0]] ** 2
                                                > self.padding.max_padded_cost_per_chunk for group in plan),
            "original_atom_and_graph_order_restored": True,
            "views_noise_masks_targets_regenerated": False, "loss_or_group_reduction_per_chunk": False}
        return result

class LogicalBatchSharedPairBackbone(nn.Module):
    """SharedPair's native full forward per complete-graph chunk, same keys.

    This is a separate explicit runtime type. It does not route SharedPair
    inputs through the scalar-distance/C1-0 attention signature.
    """
    def __init__(self, original, *, padding=None, capacity_guard=None):
        from .v3_architecture import SharedPairBackbone
        if type(original) is not SharedPairBackbone:
            raise ValueError("Declared SharedPairBackbone required")
        super().__init__()
        for name, module in original.named_children():self.add_module(name, module)
        for name, parameter in original.named_parameters(recurse=False):self.register_parameter(name, parameter)
        for name, buffer in original.named_buffers(recurse=False):
            self.register_buffer(name, buffer, persistent=name not in original._non_persistent_buffers_set)
        for name in ("n_atom_types", "dim", "activation_checkpointing", "options", "distance_bias_projection_bias"):
            setattr(self, name, getattr(original, name))
        self.padding, self.capacity_guard = padding, capacity_guard
        self.performance_execution_contract = {"schema": "model_v3_shared_pair_logical_runtime_v1",
            "padding": None if padding is None else asdict(padding),
            "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
        self.last_logical_batch_execution = None
        self.train(original.training)
        self._require_context()

    def get_extra_state(self):
        from .v3_architecture import SharedPairBackbone
        return SharedPairBackbone.get_extra_state(self)

    def set_extra_state(self, state):
        from .v3_architecture import SharedPairBackbone
        return SharedPairBackbone.set_extra_state(self, state)

    def _require_context(self):
        LogicalBatchBackbone._require_context(self)

    def forward(self, data):
        from .v3_architecture import SharedPairBackbone
        self._require_context()
        batch, counts = logical_batch_counts(data)
        if self.capacity_guard is not None:self.capacity_guard.check(data, counts)
        if data.pos.dtype != torch.float32 or torch.is_autocast_enabled(data.pos.device.type):
            raise ValueError("SharedPair logical execution requires fp32 geometry and no outer AMP")
        if self.padding is None:
            plan = (tuple(range(len(counts))),)
            result = SharedPairBackbone.forward(self, data)
        else:
            plan = chunk_plan(counts, self.padding)
            offsets, offset = [], 0
            for count in counts:offsets.append(offset);offset += count
            outputs, original_rows = [], []
            for group in plan:
                rows = torch.cat([torch.arange(offsets[g], offsets[g] + counts[g], device=batch.device) for g in group])
                ids = torch.repeat_interleave(torch.arange(len(group), device=batch.device),
                                             batch.new_tensor([counts[g] for g in group]))
                piece = Data(x=data.x.index_select(0, rows), pos=data.pos.index_select(0, rows), batch=ids)
                outputs.append(SharedPairBackbone.forward(self, piece))
                original_rows.append(rows)
            values = torch.cat(outputs)
            result = values.new_zeros((len(batch), self.dim)).index_copy(0, torch.cat(original_rows), values)
        shapes = [(len(group), max(counts[g] for g in group)) for group in plan]
        self.last_logical_batch_execution = {"schema": "model_v3_logical_batch_execution_v1",
            "padding": None if self.padding is None else asdict(self.padding),
            "logical_graph_count": len(counts), "logical_atom_count": len(batch), "graph_atom_counts": counts,
            "legacy_dense_padded_cost": len(counts) * max(counts) ** 2,
            "chunked_dense_padded_cost": sum(b * n * n for b, n in shapes),
            "chunk_graphs": [list(group) for group in plan], "executed_dense_shapes": [list(s) for s in shapes],
            "chunk_plan_sha256": hashlib.sha256(json.dumps(plan, separators=(",", ":")).encode()).hexdigest(),
            "retained_oversize_singletons": 0 if self.padding is None else sum(len(group) == 1
                and counts[group[0]] ** 2 > self.padding.max_padded_cost_per_chunk for group in plan),
            "original_atom_and_graph_order_restored": True, "views_noise_masks_targets_regenerated": False,
            "loss_or_group_reduction_per_chunk": False}
        return result

class TrainingLogicalBatchBackbone(LogicalBatchBackbone):
    """Training-only outer-AMP guard, including the no-packing observation path."""
    def forward(self, data):
        if data.pos.dtype != torch.float32 or torch.is_autocast_enabled(data.pos.device.type):
            raise ValueError("Training execution requires fp32 geometry and no outer AMP")
        return super().forward(data)
