#!/usr/bin/env python3
"""Bounded read-only CPU audit; never scans or copies a complete LMDB pool."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import torch
from rdkit import Chem, rdBase

from phychem_mfm.data.dataset_lmdb import LmdbMoleculeDataset
from phychem_mfm.phase1.data import (
    Phase1ViewDataset, StrictManifestDataset, audit_manifest_identities,
    fit_train_statistics, validate_atom_encoding,
)
from phychem_mfm.phase1.identity import identity_from_record
from phychem_mfm.training.degrade_molecules import DegradeConfig, degrade_once


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", default="/share/home/zixiao/dataset/lmdb_new")
    parser.add_argument("--samples-per-shard", type=int, default=3)
    parser.add_argument("--max-seconds", type=float, default=120.0)
    parser.add_argument("--atom-encoding", choices=("zero_based", "atomic_number"), default="zero_based")
    parser.add_argument("--train-manifest")
    parser.add_argument("--validation-manifest")
    parser.add_argument("--diagnostic-limit", type=int, default=32)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def inspect_record(raw, *, encoding: str, seed: int) -> dict:
    fields = set(raw.keys())
    summary = {
        "field_names": sorted(fields),
        "atoms": int(raw.x.shape[0]),
        "x_min": int(raw.x.min()), "x_max": int(raw.x.max()),
        "energy_present": "energy" in fields, "energy_unit": str(getattr(raw, "energy_unit", "")),
        "charge_present": "y" in fields, "charge_mask_present": "charge_mask" in fields,
        "charge_shape": list(raw.y.shape) if isinstance(getattr(raw, "y", None), torch.Tensor) else None,
        "pos_shape": list(raw.pos.shape), "coordinates_finite": bool(torch.isfinite(raw.pos).all()),
        "rdkit_status": str(getattr(raw, "rdkit_status", "missing")),
    }
    identity = identity_from_record(raw)
    summary["inchikey_resolved"] = True
    summary["identity_source_field"] = identity.source_field
    with rdBase.BlockLogs():
        mol = Chem.AddHs(Chem.MolFromSmiles(getattr(raw, identity.source_field)))
    z = torch.tensor([atom.GetAtomicNum() for atom in mol.GetAtoms()])
    summary["matches_atomic_number"] = tuple(z.shape) == tuple(raw.x[:, 0].shape) and bool(torch.equal(z, raw.x[:, 0]))
    summary["matches_zero_based"] = tuple(z.shape) == tuple(raw.x[:, 0].shape) and bool(torch.equal(z - 1, raw.x[:, 0]))
    validate_atom_encoding(raw, encoding)
    if isinstance(getattr(raw, "y", None), torch.Tensor):
        mask = getattr(raw, "charge_mask", torch.zeros_like(raw.y)).bool()
        summary["charge_valid_count"] = int(mask.sum())
        summary["masked_charges_finite"] = bool(torch.isfinite(raw.y[mask]).all())
    if isinstance(getattr(raw, "rdkit_graph_desc_mask", None), torch.Tensor):
        summary["valid_graph_descriptor_count"] = int(raw.rdkit_graph_desc_mask.sum())
    if isinstance(getattr(raw, "rdkit_node_mask", None), torch.Tensor):
        summary["valid_descriptor_atom_count"] = int(raw.rdkit_node_mask.sum())
    views = {}
    for mode in ("clean", "geom", "topo", "both"):
        cfg = DegradeConfig(
            mode=mode, level=0.8, atom_encoding=encoding,
            topo_delete_frac=0.0, geom_angle_std_deg=0.0, geom_bond_scale_std=0.0,
        )
        result = degrade_once(raw, cfg, torch.Generator().manual_seed(seed))
        changes = result.x.ne(raw.x).any(dim=1)
        mask = result.element_corrupt_mask.view(-1)
        views[mode] = {
            "same_atom_count": result.x.shape == raw.x.shape,
            "changed_element_count": int(changes.sum()),
            "corrupt_mask_count": int(mask.sum()),
            "mask_exactly_matches_changes": bool(torch.equal(changes, mask)),
            "unchanged_positions_preserved": bool(torch.equal(result.x[~mask], raw.x[~mask])),
            "charge_target_preserved": (
                bool(torch.equal(result.y, raw.y)) if isinstance(getattr(raw, "y", None), torch.Tensor) else True
            ),
        }
        if not all(views[mode][name] for name in (
            "same_atom_count", "mask_exactly_matches_changes", "unchanged_positions_preserved", "charge_target_preserved"
        )):
            raise ValueError(f"{mode} view violates clean/noisy atom or mask invariants")
    views["both"]["preserves_topology_corrupt_mask"] = views["both"]["corrupt_mask_count"] == views["topo"]["corrupt_mask_count"]
    if not views["both"]["preserves_topology_corrupt_mask"]:
        raise ValueError("Both view lost the topology corruption mask")
    summary["views"] = views
    return summary


def main():
    args = parse_args()
    if not 1 <= args.samples_per_shard <= 16:
        raise ValueError("Bounded inspection requires 1..16 records per shard")
    if not 0 < args.max_seconds <= 300:
        raise ValueError("Bounded inspection wall-clock limit must be <= 300 seconds")
    if not 1 <= args.diagnostic_limit <= 256:
        raise ValueError("Diagnostic manifest limit must be 1..256")
    if bool(args.train_manifest) != bool(args.validation_manifest):
        raise ValueError("Supply both existing train and validation manifests together")
    started = time.monotonic()
    deadline = started + args.max_seconds
    report = {
        "schema_version": "phase1_bounded_record_audit_v1",
        "scope": "bounded samples only; not complete pool coverage or atomic mapping provenance proof",
        "atom_encoding": args.atom_encoding,
        "no_training": True, "no_lmdb_mutation": True,
        "records": [], "failures": [], "completed_all_requested_samples": True,
    }
    shards = sorted(Path(args.data_root).glob("principal_*.lmdb")) + sorted(Path(args.data_root).glob("unimol_*.lmdb"))
    report["clean_shard_count"] = len(shards)
    for shard in shards:
        reader = LmdbMoleculeDataset(
            shard, start_idx=0, end_idx=0, normalize_samples=False,
            strict_index=True, filter_missing_on_init=False,
        )
        indices = np.linspace(0, reader._len - 1, min(args.samples_per_shard, reader._len), dtype=np.int64)
        for index in indices.tolist():
            if time.monotonic() >= deadline:
                report["completed_all_requested_samples"] = False
                break
            reference = {"shard": shard.name, "real_index": int(index)}
            try:
                raw = reader.get_by_real_index(index)
                record = inspect_record(raw, encoding=args.atom_encoding, seed=1000 + len(report["records"]))
                report["records"].append({**reference, **record})
            except Exception as exc:
                report["failures"].append({**reference, "error_type": type(exc).__name__, "reason": str(exc)})
        if not report["completed_all_requested_samples"]:
            break
    if args.train_manifest and time.monotonic() < deadline:
        try:
            train = StrictManifestDataset(args.train_manifest, atom_encoding=args.atom_encoding, diagnostic_limit=args.diagnostic_limit)
            validation = StrictManifestDataset(args.validation_manifest, atom_encoding=args.atom_encoding, diagnostic_limit=args.diagnostic_limit)
            report["diagnostic_train_view"] = train.summary()
            report["diagnostic_validation_view"] = validation.summary()
            report["diagnostic_identity_audit"] = audit_manifest_identities(train, validation)
            _, provenance = fit_train_statistics(train, cap=min(len(train), 64), seed=0, validation=validation)
            report["diagnostic_statistics_provenance"] = provenance
            # Inspect all views on a selected manifest record, without training.
            for mode in ("clean", "geom", "topo", "both"):
                view = Phase1ViewDataset(train, mode=mode, level=0.8, seed=0)
                view[0]
        except Exception as exc:
            report["failures"].append({"scope": "diagnostic_manifest_views", "error_type": type(exc).__name__, "reason": str(exc)})
    elif args.train_manifest:
        report["completed_all_requested_samples"] = False
    report["elapsed_seconds"] = round(time.monotonic() - started, 3)
    report["inspected_record_count"] = len(report["records"])
    report["rdkit_status_counts"] = dict(Counter(row["rdkit_status"] for row in report["records"]))
    report["status"] = "PASS_BOUNDED" if not report["failures"] and report["completed_all_requested_samples"] and shards else "FAIL_OR_INCOMPLETE"
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({key: report[key] for key in (
        "status", "clean_shard_count", "inspected_record_count", "elapsed_seconds", "completed_all_requested_samples"
    )}))
    print(f"summary_path={destination}")
    return 0 if report["status"] == "PASS_BOUNDED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
