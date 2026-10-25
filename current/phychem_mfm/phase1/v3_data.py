"""Node-local, read-only provider injection and decoded v3 batch assembly.

No storage format or field conversion is guessed here. The provider factory
must be implemented against the data line's agreed D-1 version. The current
tests use only synthetic providers with identical typed model-side outputs.
"""
from __future__ import annotations

from copy import copy
from dataclasses import dataclass
import os
from typing import Mapping

import torch
from torch import Tensor
from torch.utils.data import DataLoader, Dataset
from torch_geometric.data import Batch, Data

from ..data.descriptor_schema import (BOND_FAIL_REASON_FIELD, BOND_INDEX_FIELD,
                                      BOND_ORDER_FIELD, BOND_STATUS_FIELD)
from .v3_contract import FieldTarget, LabelRegistry, require
from .v3_sampling import SampleChoice, SamplingIndex, UniformMoleculeSampler
from .v3_wire_audit import SampleSourceAudit


@dataclass(frozen=True)
class NativeBondTransport:
    """Optional existing rdkit_bond_* facts, not a new wire/codebook adapter.

    Status and order values are copied literally. The original S head remains
    responsible for its existing clean/status/order validity filtering.
    """
    pair_index: Tensor
    order: Tensor
    status: str
    fail_reason: str = ""

    def __post_init__(self):
        require(isinstance(self.pair_index, Tensor) and self.pair_index.dtype == torch.long
                and self.pair_index.ndim == 2 and self.pair_index.size(0) == 2
                and self.pair_index.device.type == "cpu", "Native bond index must be CPU long[2,p]")
        require(isinstance(self.order, Tensor) and self.order.dtype == torch.long
                and self.order.shape == (self.pair_index.size(1),)
                and self.order.device.type == "cpu", "Native bond orders must be CPU long[p]")
        require(type(self.status) is str and type(self.fail_reason) is str,
                "Native bond status/failure reason must be literal strings")

    def validate_atoms(self, native_atoms):
        # Recheck mutable tensor contents before crossing the loader boundary.
        self.__post_init__()
        require(bool(((self.pair_index >= 0) & (self.pair_index < native_atoms)).all()),
                "Native bond indices must reference this molecule's atom rows")


@dataclass(frozen=True)
class DecodedSample:
    molecule_id: str
    conformer_id: str
    geometry_source: str
    x: Tensor
    pos: Tensor
    source_atom_ids: Tensor
    fields: Mapping[str, FieldTarget]
    native_bonds: NativeBondTransport | None = None
    audit: SampleSourceAudit | None = None


def _validate_native_bonds(sample):
    if sample.native_bonds is not None:
        require(isinstance(sample.native_bonds, NativeBondTransport), "Typed native bond transport required")
        sample.native_bonds.validate_atoms(len(sample.x))


def _encoder_graph(sample, *, with_bond_transport):
    _validate_native_bonds(sample)
    graph = Data(x=sample.x, pos=sample.pos)
    if with_bond_transport:
        bonds = sample.native_bonds
        # Mixed batches need identical PyG keys. Missing transport uses the
        # original head's exact default status "", never fabricated "ok".
        setattr(graph, BOND_INDEX_FIELD, bonds.pair_index if bonds is not None else torch.empty((2, 0), dtype=torch.long))
        setattr(graph, BOND_ORDER_FIELD, bonds.order if bonds is not None else torch.empty(0, dtype=torch.long))
        setattr(graph, BOND_STATUS_FIELD, bonds.status if bonds is not None else "")
        setattr(graph, BOND_FAIL_REASON_FIELD, bonds.fail_reason if bonds is not None else "")
    return graph


class ManifestSampleDataset(Dataset):
    """Construct provider/readonly handles separately in each spawned worker."""
    def __init__(self, index: SamplingIndex, provider_factory):
        require(getattr(provider_factory, "read_only", None) is True
                and getattr(provider_factory, "node_local", None) is True
                and getattr(provider_factory, "data_version", None) == index.version,
                "An explicitly readonly node-local version-bound provider factory is required")
        self.index, self.provider_factory = index, provider_factory
        self.index_sha256 = index.content_sha256
        self._provider = self._pid = None

    def __len__(self):
        return len(self.index)

    def __getstate__(self):
        state = self.__dict__.copy()
        state["_provider"] = state["_pid"] = None
        return state

    def __getitem__(self, choice: SampleChoice):
        require(isinstance(choice, SampleChoice) and choice.index_sha256 == self.index_sha256
                and 0 <= choice.molecule_index < len(self.index), "Bound sampling choice required")
        molecule = self.index.molecule_at(choice.molecule_index)
        values = [ref for ref in molecule.conformers if ref.conformer_id == choice.conformer_id]
        require(molecule.molecule_id == choice.molecule_id and len(values) == 1
                and values[0].locator(choice.geometry_source) == choice.locator
                and values[0].native_atoms == choice.native_atoms
                and molecule.group_mask == choice.group_mask and molecule.family_mask == choice.family_mask,
                "Draw/manifest identity, geometry, counts or exposure masks differ")
        if self._pid != os.getpid():
            self.close()
            self._provider, self._pid = self.provider_factory(), os.getpid()
            require(callable(getattr(self._provider, "read", None)), "Provider must implement read(choice)")
        sample = self._provider.read(choice)
        require(isinstance(sample, DecodedSample) and sample.molecule_id == choice.molecule_id
                and sample.conformer_id == choice.conformer_id and sample.geometry_source == choice.geometry_source,
                "Provider returned another molecule/conformer/geometry")
        n = choice.native_atoms
        require(sample.x.dtype == torch.long and sample.x.shape == (n, 1)
                and bool(((sample.x >= 0) & (sample.x < 118)).all())
                and sample.pos.dtype == torch.float32 and sample.pos.shape == (n, 3)
                and bool(torch.isfinite(sample.pos).all()), "Native Z-1 atoms/fp32 geometry differ")
        ids = sample.source_atom_ids
        require(ids.dtype == torch.long and ids.shape == (n,) and len(ids.unique()) == n
                and bool((ids >= 0).all()), "Explicit unique source atom IDs required")
        require(sample.x.device.type == sample.pos.device.type == ids.device.type == "cpu",
                "Data workers must return CPU tensors")
        _validate_native_bonds(sample)
        return choice, sample

    def close(self):
        if self._provider is not None:
            close = getattr(self._provider, "close", None)
            if close is not None:
                close()
        self._provider = self._pid = None


@dataclass(frozen=True)
class V3Batch:
    encoder_batch: Batch
    targets: dict[str, FieldTarget]
    choices: tuple[SampleChoice, ...]
    source_atom_ids: Tensor
    audit: tuple[SampleSourceAudit | None, ...] | None = None

    def to(self, device, *, non_blocking=False):
        # Copy graph stores, not CPU tensors: cloning pinned input tensors can
        # add a host copy before the asynchronous transfer. PyG's shallow copy
        # owns its stores, so moving this graph does not mutate the source graph.
        graph = copy(self.encoder_batch).to(device, non_blocking=non_blocking)
        return V3Batch(graph,
                       {name: FieldTarget(value.values.to(device, non_blocking=non_blocking),
                                          value.valid.to(device, non_blocking=non_blocking),
                                          None if value.pair_index is None else value.pair_index.to(device, non_blocking=non_blocking))
                        for name, value in self.targets.items()}, self.choices,
                       self.source_atom_ids.to(device, non_blocking=non_blocking), self.audit)

    def pin_memory(self):
        # DataLoader invokes this protocol for a custom batch container.
        return V3Batch(copy(self.encoder_batch).pin_memory(),
                       {name: FieldTarget(value.values.pin_memory(), value.valid.pin_memory(),
                                          None if value.pair_index is None else value.pair_index.pin_memory())
                        for name, value in self.targets.items()}, self.choices, self.source_atom_ids.pin_memory(), self.audit)

    @property
    def pair_indices(self):
        return {name: value.pair_index for name, value in self.targets.items() if value.pair_index is not None}


def collate_v3_samples(rows, registry: LabelRegistry) -> V3Batch:
    require(bool(rows), "Nonempty decoded batch required")
    choices, samples = zip(*rows)
    require(all(isinstance(value, SampleChoice) for value in choices)
            and len({value.ordinal for value in choices}) == len(choices), "Unique sample draws required")
    require(all(set(sample.fields) <= set(registry.by_name()) for sample in samples),
            "Provider returned an undeclared field")
    with_bond_transport = any(sample.native_bonds is not None for sample in samples)
    graphs = [_encoder_graph(sample, with_bond_transport=with_bond_transport) for sample in samples]
    encoder_batch = Batch.from_data_list(graphs)
    result = {}
    for field in registry.fields:
        values, masks, pairs, offset = [], [], [], 0
        for choice, sample in zip(choices, samples):
            n = len(sample.x)
            group_flags, family_flags = dict(choice.group_mask), dict(choice.family_mask)
            require(field.family in family_flags, f"{field.name}: explicit family exposure mask required")
            active = group_flags[field.group] and family_flags[field.family]
            target = sample.fields.get(field.name)
            count = 1 if field.level == "graph" else n
            index = None
            if field.level == "pair":
                if target is not None:
                    index = target.pair_index
                    require(isinstance(index, Tensor) and index.dtype == torch.long
                            and index.ndim == 2 and index.size(0) == 2
                            and index.device.type == "cpu" and bool(((index >= 0) & (index < n)).all())
                            and bool((index[0] != index[1]).all()), "Native local pair indices required")
                else:
                    index = torch.empty((2, 0), dtype=torch.long)
                count = index.size(1)
                pairs.append(index + offset)
            if target is None:
                fill = -1 if field.kind == "classification" else float("nan")
                dtype = torch.long if field.kind == "classification" else torch.float32
                values.append(torch.full((count, field.target_width), fill, dtype=dtype))
                masks.append(torch.zeros(count, dtype=torch.bool))
            else:
                dtype = torch.long if field.kind == "classification" else torch.float32
                require(target.values.dtype == dtype and target.values.shape == (count, field.target_width)
                        and target.valid.dtype == torch.bool and target.valid.shape == (count,)
                        and target.values.device.type == target.valid.device.type == "cpu",
                        f"{field.name}: provider field shape/dtype differs")
                values.append(target.values)
                masks.append(target.valid & active)
            offset += n
        result[field.name] = FieldTarget(torch.cat(values), torch.cat(masks),
                                         torch.cat(pairs, dim=1) if pairs else None)
    audits = tuple(sample.audit for sample in samples) if any(sample.audit is not None for sample in samples) else None
    require(audits is None or all(value is None or isinstance(value, SampleSourceAudit) for value in audits),
            "Optional CPU source audit must retain its typed source evidence")
    require(audits is None or all(value is None or value.geometry_id == choice.conformer_id
                                  for choice, value in zip(choices, audits)), "CPU audit belongs to another geometry draw")
    return V3Batch(encoder_batch, result, tuple(choices), torch.cat([sample.source_atom_ids for sample in samples]), audits)


class ExposureBatchSampler:
    """Atom-aware batches in deterministic draw order, split at save milestones."""
    def __init__(self, sampler: UniformMoleculeSampler, *, max_molecules=512,
                 max_native_atoms=65536, max_padded_cost=8000000, views_per_sample=1,
                 milestones=(1000000, 2000000, 4000000, 8000000, 16000000, 32000000, 64000000)):
        self.sampler = sampler
        self.limits = (max_molecules, max_native_atoms, max_padded_cost, views_per_sample)
        require(all(type(value) is int and value > 0 for value in self.limits), "Positive integer batch budgets required")
        self.milestones = tuple(milestones)
        require(self.milestones == tuple(sorted(set(self.milestones)))
                and all(type(value) is int and value > 0 for value in self.milestones), "Sorted positive milestones required")

    def __iter__(self):
        max_molecules, max_atoms, max_cost, views = self.limits
        batch, atoms, largest = [], 0, 0
        for draw in self.sampler:
            largest_next = max(largest, draw.native_atoms)
            cost = views * (len(batch) + 1) * largest_next ** 2
            if batch and (len(batch) >= max_molecules or atoms + draw.native_atoms > max_atoms or cost > max_cost):
                yield batch
                batch, atoms, largest = [], 0, 0
            batch.append(draw)
            atoms += draw.native_atoms
            largest = max(largest, draw.native_atoms)
            if draw.ordinal + 1 in self.milestones:
                yield batch
                batch, atoms, largest = [], 0, 0
        if batch:
            yield batch


@dataclass(frozen=True)
class _Collator:
    registry: LabelRegistry

    def __call__(self, rows):
        return collate_v3_samples(rows, self.registry)


def make_v3_loader(dataset, batch_sampler, registry, *, num_workers=8,
                   prefetch_factor=2, worker_timeout_seconds=600., pin_memory=True):
    require(type(num_workers) is int and num_workers >= 0, "Invalid worker count")
    require(type(prefetch_factor) is int and prefetch_factor > 0 and worker_timeout_seconds > 0,
            "Bounded prefetch and worker wait required")
    kwargs = {"dataset": dataset, "batch_sampler": batch_sampler, "collate_fn": _Collator(registry),
              "num_workers": num_workers, "pin_memory": pin_memory, "persistent_workers": False}
    if num_workers:
        kwargs.update(multiprocessing_context="spawn", prefetch_factor=prefetch_factor,
                      timeout=float(worker_timeout_seconds))
    return DataLoader(**kwargs)
