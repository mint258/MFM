#!/usr/bin/env python3
"""Audit existing LMDB supervision without running new QM calculations."""

from __future__ import annotations

import argparse
import collections
import csv
import heapq
import json
import math
from pathlib import Path

import numpy as np
import torch

from phychem_mfm.data.dataset_lmdb import LmdbMoleculeDataset
from phychem_mfm.data.descriptor_schema import GRAPH_DESCRIPTOR_NAMES
from phychem_mfm.discovery.manifests import load_manifest


BOUNDED_DESCRIPTORS = {
    "FractionCSP3": (0.0, 1.0), "NPR1": (0.0, 1.0), "NPR2": (0.0, 1.0),
    "Eccentricity": (0.0, 1.0),
}
NONNEGATIVE_DESCRIPTORS = {
    "TPSA", "LabuteASA", "ExactMolWt", "NumValenceElectrons", "HeavyAtomCount",
    "NumHeteroatoms", "NumHAcceptors", "NumHDonors", "NumRotatableBonds", "RingCount",
    "NumAromaticRings", "NumAliphaticRings", "NumSaturatedRings", "NumHeterocycles",
    "NumBridgeheadAtoms", "NumSpiroAtoms", "NumAmideBonds", "BertzCT",
    "RadiusOfGyration", "Asphericity",
}


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--top-k", type=int, default=100)
    return parser.parse_args()


def _domain(shard: str) -> str:
    return "principal" if Path(shard).name.startswith("principal_") else "molecule"


def _stats(values: np.ndarray) -> dict[str, object]:
    values = np.asarray(values, dtype=np.float64)
    finite = values[np.isfinite(values)]
    if not finite.size:
        return {"count": int(values.size), "finite_count": 0}
    quantiles = np.quantile(finite, [0, 0.001, 0.01, 0.5, 0.99, 0.999, 1])
    mad = float(np.median(np.abs(finite - quantiles[3])))
    return {
        "count": int(values.size), "finite_count": int(finite.size),
        "mean": float(finite.mean()), "std": float(finite.std()),
        "min": float(quantiles[0]), "p001": float(quantiles[1]), "p01": float(quantiles[2]),
        "median": float(quantiles[3]), "p99": float(quantiles[4]),
        "p999": float(quantiles[5]), "max": float(quantiles[6]),
        "median_absolute_deviation": mad, "robust_sigma": 1.4826 * mad,
    }


def _push_top(heap, value: float, record: dict[str, object], top_k: int) -> None:
    entry = (abs(float(value)), json.dumps(record, sort_keys=True), float(value), record)
    if len(heap) < top_k:
        heapq.heappush(heap, entry)
    elif entry[:2] > heap[0][:2]:
        heapq.heapreplace(heap, entry)


def _top_records(heap) -> list[dict[str, object]]:
    return [{"value": value, **record} for _, _, value, record in sorted(heap, reverse=True)]


def main() -> None:
    args = parse_args()
    manifest = load_manifest(args.manifest)
    count = int(manifest["unique_structure_count"])
    energies = np.full(count, np.nan, dtype=np.float64)
    energy_per_atom = np.full(count, np.nan, dtype=np.float64)
    charge_sum_error = np.full(count, np.nan, dtype=np.float64)
    max_abs_charge = np.full(count, np.nan, dtype=np.float64)
    descriptor_values = np.full((count, len(GRAPH_DESCRIPTOR_NAMES)), np.nan, dtype=np.float32)
    descriptor_mask = np.zeros_like(descriptor_values, dtype=bool)
    charge_chunks: list[np.ndarray] = []
    charge_buffer: list[np.ndarray] = []
    charge_buffer_size = 0
    counters = collections.Counter()
    energy_units = collections.Counter()
    rdkit_statuses = collections.Counter()
    domain_energy: dict[str, list[float]] = collections.defaultdict(list)
    top_energy: list[tuple] = []
    top_energy_per_atom: list[tuple] = []
    top_charge_sum: list[tuple] = []
    row = 0

    root = Path(str(manifest["data_root"]))
    for segment in manifest["segments"]:
        shard = str(segment["shard"])
        start, end = int(segment["start"]), int(segment["end"])
        dataset = LmdbMoleculeDataset(
            str(root / shard), start_idx=start, end_idx=end,
            filter_missing_on_init=False,
        )
        for local_index in range(len(dataset)):
            item = dataset[local_index]
            n_atoms = int(item.x.size(0)) if isinstance(getattr(item, "x", None), torch.Tensor) else 0
            record = {
                "shard": shard, "real_index": int(dataset.idx_list[local_index]),
                "sample_key": str(getattr(item, "sample_key", "")), "atom_count": n_atoms,
                "domain": _domain(shard),
            }
            counters["structures"] += 1
            if n_atoms <= 0:
                counters["invalid_empty_structure"] += 1
            pos = getattr(item, "pos", None)
            if not isinstance(pos, torch.Tensor) or pos.shape != (n_atoms, 3) or not torch.isfinite(pos).all():
                counters["invalid_coordinates"] += 1
            x = getattr(item, "x", None)
            if not isinstance(x, torch.Tensor) or x.numel() != n_atoms or not torch.isfinite(x.float()).all():
                counters["invalid_elements"] += 1

            energy = float(getattr(item, "energy", math.nan))
            energies[row] = energy
            energy_per_atom[row] = energy / n_atoms if n_atoms else math.nan
            energy_units[str(getattr(item, "energy_unit", "unknown"))] += 1
            if not math.isfinite(energy):
                counters["invalid_energy"] += 1
            else:
                domain_energy[record["domain"]].append(energy)
                _push_top(top_energy, energy, record, args.top_k)
                _push_top(top_energy_per_atom, energy_per_atom[row], record, args.top_k)

            charges = getattr(item, "y", None)
            mask = getattr(item, "charge_mask", None)
            if isinstance(charges, torch.Tensor) and isinstance(mask, torch.Tensor):
                selected = charges.reshape(-1)[mask.reshape(-1).bool()].detach().cpu().numpy().astype(np.float32)
            else:
                selected = np.empty(0, dtype=np.float32)
            if selected.size:
                charge_buffer.append(selected)
                charge_buffer_size += int(selected.size)
                if charge_buffer_size >= 1_000_000:
                    charge_chunks.append(np.concatenate(charge_buffer)); charge_buffer = []
                    charge_buffer_size = 0
                if not np.isfinite(selected).all():
                    counters["invalid_charge"] += 1
                finite_charge = selected[np.isfinite(selected)]
                if finite_charge.size:
                    total_charge = float(getattr(item, "total_charge", 0))
                    charge_sum_error[row] = float(finite_charge.sum()) - total_charge
                    max_abs_charge[row] = float(np.max(np.abs(finite_charge)))
                    _push_top(top_charge_sum, charge_sum_error[row], record, args.top_k)
            else:
                counters["missing_charge"] += 1

            desc = getattr(item, "rdkit_graph_desc", None)
            desc_mask = getattr(item, "rdkit_graph_desc_mask", None)
            if isinstance(desc, torch.Tensor) and isinstance(desc_mask, torch.Tensor):
                values = desc.reshape(-1).detach().cpu().numpy()
                valid = desc_mask.reshape(-1).bool().detach().cpu().numpy()
                if values.size == len(GRAPH_DESCRIPTOR_NAMES) and valid.size == values.size:
                    descriptor_values[row] = values
                    descriptor_mask[row] = valid
                    if not np.isfinite(values[valid]).all():
                        counters["invalid_descriptor"] += 1
                else:
                    counters["invalid_descriptor_shape"] += 1
            else:
                counters["missing_descriptor"] += 1
            rdkit_statuses[str(getattr(item, "rdkit_status", "missing"))] += 1
            row += 1

    if charge_buffer:
        charge_chunks.append(np.concatenate(charge_buffer))
    charges = np.concatenate(charge_chunks) if charge_chunks else np.empty(0, dtype=np.float32)
    descriptor_report = {}
    hard_descriptor_violations = {}
    for index, name in enumerate(GRAPH_DESCRIPTOR_NAMES):
        values = descriptor_values[:, index][descriptor_mask[:, index]]
        descriptor_report[name] = _stats(values)
        finite = values[np.isfinite(values)]
        violations = 0
        if name in BOUNDED_DESCRIPTORS:
            lower, upper = BOUNDED_DESCRIPTORS[name]
            violations = int(((finite < lower - 1e-6) | (finite > upper + 1e-6)).sum())
        elif name in NONNEGATIVE_DESCRIPTORS:
            violations = int((finite < -1e-6).sum())
        if violations:
            hard_descriptor_violations[name] = violations

    report = {
        "report_type": "PretrainingDataQualityAudit",
        "manifest": str(Path(args.manifest).resolve()), "pool_id": manifest["pool_id"],
        "pool_hash": manifest["pool_hash"], "authoritative_reference": "/share/home/zixiao/unimol_data",
        "no_new_qm_calls": True, "counts": dict(sorted(counters.items())),
        "energy_units": dict(sorted(energy_units.items())), "rdkit_statuses": dict(sorted(rdkit_statuses.items())),
        "energy": _stats(energies), "energy_per_atom": _stats(energy_per_atom),
        "energy_by_domain": {key: _stats(np.asarray(value)) for key, value in sorted(domain_energy.items())},
        "atomic_charge": _stats(charges), "charge_sum_error_vs_stored_total_charge": _stats(charge_sum_error),
        "max_abs_atomic_charge_per_structure": _stats(max_abs_charge),
        "graph_descriptors": descriptor_report,
        "hard_descriptor_invariant_violations": hard_descriptor_violations,
        "top_absolute_energy_records": _top_records(top_energy),
        "top_absolute_energy_per_atom_records": _top_records(top_energy_per_atom),
        "top_absolute_charge_sum_error_records": _top_records(top_charge_sum),
        "policy": {
            "hard_invalid": "non-finite/malformed tensors or descriptor invariant violations",
            "tail_values": "diagnostic only; robust/conditional review required before quarantine",
            "charge_sum_error": "diagnostic only because the model has no explicit conservation constraint",
        },
    }
    output_json = Path(args.output_json); output_csv = Path(args.output_csv)
    output_json.parent.mkdir(parents=True, exist_ok=True); output_csv.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    rows = [{"target": "energy", **report["energy"]}, {"target": "energy_per_atom", **report["energy_per_atom"]},
            {"target": "atomic_charge", **report["atomic_charge"]},
            {"target": "charge_sum_error_vs_stored_total_charge", **report["charge_sum_error_vs_stored_total_charge"]}]
    rows.extend({"target": f"descriptor:{name}", **stats} for name, stats in descriptor_report.items())
    columns = sorted({key for item in rows for key in item})
    with output_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns); writer.writeheader(); writer.writerows(rows)
    print(json.dumps({"pool_id": manifest["pool_id"], "structures": row, "output_json": str(output_json)}, sort_keys=True))


if __name__ == "__main__":
    main()
