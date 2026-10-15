"""Strict Phase 1 views of immutable LMDB manifests; no implicit resampling."""
from __future__ import annotations

from bisect import bisect_right
import copy
from pathlib import Path
from typing import Mapping

import numpy as np
import torch
from torch.utils.data import Dataset
from rdkit import Chem

from ..data.dataset_lmdb import LmdbMoleculeDataset
from ..data.descriptor_schema import RDKIT_GRAPH_DESC_DIM
from ..discovery.manifests import load_manifest
from ..training.degrade_molecules import DegradeConfig, degrade_once
from .identity import IDENTITY_POLICY, assert_disjoint_identities, canonical_hash, identity_from_record


ATOM_ENCODINGS = {"zero_based", "atomic_number"}


def _manifest_hash(manifest: Mapping) -> str:
    payload = dict(manifest)
    expected = str(payload.pop("pool_hash"))
    actual = canonical_hash(payload)
    if actual != expected:
        raise ValueError(f"Manifest content hash mismatch: expected {expected}, computed {actual}")
    return expected


def validate_atom_encoding(record, encoding: str) -> None:
    if encoding not in ATOM_ENCODINGS:
        raise ValueError("Phase 1 requires explicit zero_based or atomic_number encoding")
    x, pos = getattr(record, "x", None), getattr(record, "pos", None)
    if not isinstance(x, torch.Tensor) or x.ndim != 2 or x.shape[1] != 1 or x.shape[0] == 0:
        raise ValueError("Invalid element tensor shape; expected nonempty [N, 1]")
    if x.dtype not in (torch.int8, torch.int16, torch.int32, torch.int64):
        raise ValueError("Element indices must use an integer dtype")
    if not isinstance(pos, torch.Tensor) or tuple(pos.shape) != (len(x), 3) or not torch.isfinite(pos).all():
        raise ValueError("Invalid atom-aligned coordinate tensor")
    identity = identity_from_record(record)
    source = getattr(record, identity.source_field)
    mol = Chem.AddHs(Chem.MolFromSmiles(source))
    z = torch.tensor([atom.GetAtomicNum() for atom in mol.GetAtoms()], dtype=torch.long)
    expected = z - 1 if encoding == "zero_based" else z
    if expected.shape != x[:, 0].shape or not torch.equal(expected, x[:, 0].detach().cpu().long()):
        raise ValueError("Element sequence does not match the declared encoding and explicit-H SMILES atom order")


class StrictManifestDataset(Dataset):
    """Read exactly the declared records, preserving their existing split.

    A diagnostic limit samples deterministic evenly-spaced logical records from
    this existing view. It is marked diagnostic-only; it does not establish a
    qualified molecule split and must pass a separate InChIKey intersection
    audit. No adjacent-key fallback, SafeResampleDataset or mutable index list
    participates in reads.
    """

    def __init__(
        self,
        manifest_or_path: Mapping | str | Path,
        *,
        atom_encoding: str = "zero_based",
        diagnostic_limit: int | None = None,
        validate_encoding: bool = True,
    ):
        if atom_encoding not in ATOM_ENCODINGS:
            raise ValueError("Phase 1 forbids per-sample atom-encoding heuristics")
        self.manifest = (
            copy.deepcopy(dict(manifest_or_path)) if isinstance(manifest_or_path, Mapping)
            else load_manifest(manifest_or_path)
        )
        self.pool_hash = _manifest_hash(self.manifest)
        self.kind = str(self.manifest.get("kind", ""))
        if self.kind not in {"train", "validation", "test"}:
            raise ValueError("Manifest must explicitly identify train, validation or test role")
        self.root = Path(str(self.manifest["data_root"])).resolve()
        self.atom_encoding = atom_encoding
        self.validate_encoding = bool(validate_encoding)
        self._readers: dict[tuple[str, bool], LmdbMoleculeDataset] = {}
        self._segments, self._ends = [], []
        seen: dict[str, list[tuple[int, int]]] = {}
        total = 0
        for segment in self.manifest["segments"]:
            shard = str(segment["shard"])
            path = (self.root / shard).resolve()
            if not path.is_relative_to(self.root):
                raise ValueError("Manifest shard escapes the declared data root")
            start, end, count = int(segment["start"]), int(segment["end"]), int(segment["count"])
            if start < 0 or end < start or count != end - start + 1:
                raise ValueError("Invalid manifest segment range")
            if not path.is_file() and not path.is_dir():
                raise FileNotFoundError(path)
            stat = path.stat()
            for field, current in (("source_size", stat.st_size), ("source_mtime_ns", stat.st_mtime_ns)):
                if field in segment and int(segment[field]) != current:
                    raise ValueError(f"Manifest source {field} changed for {shard}")
            seen.setdefault(shard, []).append((start, end))
            self._segments.append((shard, start, count))
            total += count
            self._ends.append(total)
        for ranges in seen.values():
            ordered = sorted(ranges)
            if any(left[1] >= right[0] for left, right in zip(ordered, ordered[1:])):
                raise ValueError("Manifest selects duplicate or overlapping records")
        if total != int(self.manifest["unique_structure_count"]) or not total:
            raise ValueError("Manifest structure count does not match its segments")
        self.diagnostic_only = diagnostic_limit is not None
        if diagnostic_limit is not None:
            if int(diagnostic_limit) <= 0:
                raise ValueError("diagnostic_limit must be positive")
            size = min(int(diagnostic_limit), total)
            self._selection = np.linspace(0, total - 1, size, dtype=np.int64)
        else:
            self._selection = None
        self._length = total if self._selection is None else len(self._selection)
        self.view_hash = canonical_hash({
            "pool_hash": self.pool_hash, "atom_encoding": atom_encoding,
            "diagnostic_only": self.diagnostic_only,
            "logical_selection": None if self._selection is None else self._selection.tolist(),
            "reader_policy": "exact_key_no_fallback_v1",
        })

    def __len__(self):
        return self._length

    def record_ref(self, index: int) -> tuple[str, int]:
        index = int(index)
        if index < 0:
            index += len(self)
        if index < 0 or index >= len(self):
            raise IndexError(index)
        logical = index if self._selection is None else int(self._selection[index])
        segment_index = bisect_right(self._ends, logical)
        offset = 0 if segment_index == 0 else self._ends[segment_index - 1]
        shard, start, _ = self._segments[segment_index]
        return shard, start + logical - offset

    def _read(self, index: int, *, raw: bool):
        shard, real = self.record_ref(index)
        reader_key = (shard, raw)
        if reader_key not in self._readers:
            self._readers[reader_key] = LmdbMoleculeDataset(
                self.root / shard, start_idx=0, end_idx=0,
                strict_index=True, filter_missing_on_init=False, normalize_samples=not raw,
            )
        return self._readers[reader_key].get_by_real_index(real)

    def raw_record(self, index: int):
        return self._read(index, raw=True)

    def __getitem__(self, index: int):
        record = self._read(index, raw=False)
        if self.validate_encoding:
            validate_atom_encoding(record, self.atom_encoding)
        identity = identity_from_record(record)
        shard, real = self.record_ref(index)
        record.phase1_inchikey = identity.inchikey
        record.phase1_record_key = f"{shard}:{real}"
        record.phase1_pool_hash = self.pool_hash
        record.phase1_atom_encoding = self.atom_encoding
        if str(getattr(record, "energy_unit", "")) != "kcal/mol":
            record.energy_mask = torch.zeros(1, dtype=torch.bool)
        if tuple(record.y.shape) != (record.x.shape[0], 1) or tuple(record.charge_mask.shape) != (record.x.shape[0], 1):
            raise ValueError("Invalid charge/coordinate atom correspondence")
        charge_valid = record.charge_mask.bool()
        if not torch.isfinite(record.y[charge_valid]).all():
            raise ValueError("Non-finite masked charge labels")
        # Invalid/unavailable labels remain masked, with finite placeholders so
        # even a downstream arithmetic mask cannot propagate NaN * zero.
        record.y = torch.where(charge_valid, record.y, torch.zeros_like(record.y))
        graph_values = record.rdkit_graph_desc
        graph_valid = record.rdkit_graph_desc_mask.bool()
        if graph_values.numel() != RDKIT_GRAPH_DESC_DIM or graph_valid.shape != graph_values.shape:
            raise ValueError("Invalid graph descriptor/mask shape")
        if not torch.isfinite(graph_values[graph_valid]).all():
            raise ValueError("Non-finite valid graph descriptor labels")
        record.rdkit_graph_desc = torch.where(graph_valid, graph_values, torch.zeros_like(graph_values))
        return record

    def identity_keys(self) -> list[str]:
        return [identity_from_record(self.raw_record(index)).inchikey for index in range(len(self))]

    def summary(self) -> dict[str, object]:
        return {
            "pool_id": self.manifest.get("pool_id"), "kind": self.kind,
            "pool_hash": self.pool_hash, "view_hash": self.view_hash,
            "selected_structure_count": len(self),
            "source_structure_count": self.manifest["unique_structure_count"],
            "diagnostic_only": self.diagnostic_only, "atom_encoding": self.atom_encoding,
            "identity_policy": IDENTITY_POLICY,
            "identity_disjointness": "requires_explicit_intersection_audit",
        }


class Phase1ViewDataset(Dataset):
    def __init__(self, base: StrictManifestDataset, *, mode: str, level: float = 0.3, seed: int = 0):
        if mode not in {"clean", "geom", "topo", "both"}:
            raise ValueError(mode)
        self.base, self.mode, self.seed = base, mode, int(seed)
        self.cfg = DegradeConfig(
            mode=mode, level=level, atom_encoding=base.atom_encoding,
            topo_delete_frac=0.0, geom_angle_std_deg=0.0, geom_bond_scale_std=0.0,
        ).finalize()

    def __len__(self):
        return len(self.base)

    def __getitem__(self, index):
        clean = self.base[index]
        clean_x, clean_pos = clean.x.clone(), clean.pos.clone()
        generator = torch.Generator(device="cpu").manual_seed(self.seed + int(index))
        result = degrade_once(clean, self.cfg, generator)
        result.target_x, result.target_pos = clean_x, clean_pos
        result.sample_type_id = torch.tensor([{"clean": 0, "geom": 1, "topo": 2, "both": 3}[self.mode]])
        result.pretrain_base_key = clean.phase1_record_key
        result.pretrain_recipe_name = f"{self.mode}:{float(self.cfg.level):g}"
        result.pretrain_recipe_level = float(self.cfg.level)
        result.pretrain_recipe_seed = self.seed + int(index)
        for field in ("trajectory", "is_feasible", "neg_type"):
            if hasattr(result, field):
                delattr(result, field)
        actual_changes = result.x.ne(clean_x).any(dim=1)
        if not torch.equal(actual_changes, result.element_corrupt_mask.view(-1)):
            raise RuntimeError("Element corruption mask does not exactly describe modified input positions")
        return result


def audit_manifest_identities(train: StrictManifestDataset, validation: StrictManifestDataset) -> dict:
    if train.kind != "train" or validation.kind != "validation":
        raise ValueError("Split audit requires declared train and validation manifests")
    result = assert_disjoint_identities(train.identity_keys(), validation.identity_keys())
    result.update({
        "train_view_hash": train.view_hash, "validation_view_hash": validation.view_hash,
        "diagnostic_only": train.diagnostic_only or validation.diagnostic_only,
        "scope": "selected_views_only" if train.diagnostic_only or validation.diagnostic_only else "complete_declared_manifests",
    })
    return result


def fit_train_statistics(
    train: StrictManifestDataset,
    *,
    cap: int = 100000,
    seed: int = 0,
    validation: StrictManifestDataset | None = None,
) -> tuple[dict, dict]:
    """Fit valid labels from the declared training view; return stats + provenance.

    The optional validation view is used solely for an identity intersection
    check. No validation targets enter the estimator. Formal callers must also
    supply a complete split/decontamination audit to their frozen protocol.
    """
    if train.kind != "train" or int(cap) <= 0:
        raise ValueError("Statistics require a declared training view and positive cap")
    split = audit_manifest_identities(train, validation) if validation is not None else None
    indices = np.sort(np.random.default_rng(seed).choice(len(train), min(int(cap), len(train)), replace=False))
    scalar_values = {"energy": [], "charge": [], "formal_charge": [], "estate_index": []}
    graph_values = [[] for _ in range(RDKIT_GRAPH_DESC_DIM)]
    refs = []
    for index in indices.tolist():
        row = train[index]
        refs.append(row.phase1_record_key)
        if bool(row.energy_mask.all()):
            scalar_values["energy"].append(torch.tensor([float(row.energy)], dtype=torch.float64))
        valid = row.charge_mask.view(-1).bool()
        if valid.any():
            scalar_values["charge"].append(row.y.view(-1)[valid].double())
        node_valid = row.rdkit_node_mask.view(-1).bool()
        for key, field in (("formal_charge", "rdkit_node_formal_charge"), ("estate_index", "rdkit_node_estate_index")):
            value = getattr(row, field).view(-1)
            if value.numel() != node_valid.numel():
                raise ValueError(f"Node descriptor/atom correspondence mismatch for {key}")
            # Strict readers preserve missing individual fields as NaN even
            # when RDKit's shared atom-matching mask is valid. Match the loss's
            # per-target availability rather than treating absence as zero.
            value = value[node_valid & torch.isfinite(value)].double()
            if value.numel():
                scalar_values[key].append(value)
        values, mask = row.rdkit_graph_desc.view(-1).double(), row.rdkit_graph_desc_mask.view(-1).bool()
        if len(values) != RDKIT_GRAPH_DESC_DIM or len(mask) != RDKIT_GRAPH_DESC_DIM:
            raise ValueError("Descriptor pack shape mismatch")
        if not torch.isfinite(values[mask]).all():
            raise ValueError("Non-finite valid descriptor labels")
        for descriptor in mask.nonzero().view(-1).tolist():
            graph_values[descriptor].append(float(values[descriptor]))

    def estimate(parts, *, floor):
        values = torch.cat(parts) if parts else torch.empty(0, dtype=torch.float64)
        if not values.numel():
            return 0.0, 1.0, 0
        return float(values.mean()), max(float(values.std(unbiased=False)), floor), values.numel()

    stats, counts = {}, {}
    for key, mean_name, std_name, floor in (
        ("energy", "muE", "stdE", 1e-6), ("charge", "muQ", "stdQ", 1e-6),
        ("formal_charge", "formal_charge_mu", "formal_charge_std", 1e-3),
        ("estate_index", "estate_index_mu", "estate_index_std", 1e-3),
    ):
        mean, std, count = estimate(scalar_values[key], floor=floor)
        stats[mean_name], stats[std_name], counts[key] = mean, std, int(count)
    if counts["energy"] == 0:
        raise ValueError("Training view has no valid energy labels for normalization")
    graph = [estimate([torch.tensor(values, dtype=torch.float64)] if values else [], floor=1e-3) for values in graph_values]
    stats["graph_desc_mu"] = torch.tensor([row[0] for row in graph])
    stats["graph_desc_std"] = torch.tensor([row[1] for row in graph])
    counts["graph_descriptor"] = [int(row[2]) for row in graph]
    serial = {key: value.tolist() if isinstance(value, torch.Tensor) else value for key, value in stats.items()}
    provenance = {
        "estimator_version": "phase1_masked_population_std_v1", "train_only": True,
        "train_pool_hash": train.pool_hash, "train_view_hash": train.view_hash,
        "seed": int(seed), "cap": int(cap), "sampled_structure_count": len(indices),
        "sampled_logical_indices": indices.tolist(), "sampled_record_keys_hash": canonical_hash(refs),
        "valid_label_counts": counts, "atom_encoding": train.atom_encoding,
        "energy_unit": "kcal/mol", "charge_definition": "MOPAC NET ATOMIC CHARGES", "charge_unit": "e",
        "statistics_usage": "train-only means/std; output transform belongs to the model head contract",
        "statistics_hash": canonical_hash(serial),
        "split_identity_audit": split, "diagnostic_only": train.diagnostic_only,
    }
    provenance["provenance_hash"] = canonical_hash(provenance)
    return stats, provenance
