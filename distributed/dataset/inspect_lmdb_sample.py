#!/usr/bin/env python3
"""
Inspect one LMDB sample and print all stored labels in a human-readable form.

Examples:
    python inspect_lmdb_sample.py --lmdb_path data.lmdb --index 0
    python inspect_lmdb_sample.py --lmdb_path data.lmdb --sample_key molecule_01000001_01
    python inspect_lmdb_sample.py --lmdb_path data.lmdb --index 0 --json_out sample.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import torch
from rdkit import Chem

if __package__ in (None, ""):
    import os
    import sys

    _REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if _REPO_ROOT not in sys.path:
        sys.path.insert(0, _REPO_ROOT)

from dataset.dataset_lmdb import LmdbMoleculeDataset
from dataset.descriptor_schema import BOND_ORDER_CLASS_NAMES
from dataset.rdkit_descriptor_generator import ESTATE_TYPE_NAMES, GRAPH_DESCRIPTOR_NAMES


HYBRIDIZATION_NAME = {
    0: "UNSPECIFIED",
    1: "S",
    2: "SP",
    3: "SP2",
    4: "SP3",
    5: "SP2D",
    6: "SP3D",
    7: "SP3D2",
    8: "OTHER",
}

CHIRAL_TAG_NAME = {
    0: "CHI_UNSPECIFIED",
    1: "CHI_TETRAHEDRAL_CW",
    2: "CHI_TETRAHEDRAL_CCW",
    3: "CHI_OTHER",
    4: "CHI_TETRAHEDRAL",
    5: "CHI_ALLENE",
    6: "CHI_SQUAREPLANAR",
    7: "CHI_TRIGONALBIPYRAMIDAL",
    8: "CHI_OCTAHEDRAL",
}

CIP_CODE_NAME = {
    0: "",
    1: "R",
    2: "S",
    3: "other",
}

PTABLE = Chem.GetPeriodicTable()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lmdb_path", required=True, help="Path to the LMDB file.")
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--index", type=int, help="Logical dataset index inside the LMDB.")
    target.add_argument("--sample_key", type=str, help="Sample key to search for.")
    parser.add_argument(
        "--json_out",
        type=str,
        default=None,
        help="Optional JSON output path for the fully expanded sample.",
    )
    parser.add_argument(
        "--x_encoding",
        choices=["repo_zero_based", "atomic_num"],
        default="repo_zero_based",
        help="How to decode `data.x`. This repo stores zero-based element ids by default.",
    )
    return parser.parse_args()


def decode_atomic_num(raw_value: int, x_encoding: str) -> int:
    if x_encoding == "repo_zero_based":
        return raw_value + 1
    return raw_value


def decode_symbol(raw_value: int, x_encoding: str) -> str:
    atomic_num = decode_atomic_num(raw_value, x_encoding)
    if atomic_num <= 0:
        return "?"
    try:
        return PTABLE.GetElementSymbol(int(atomic_num))
    except Exception:
        return "?"


def tensor_to_list(value: Any) -> Any:
    if isinstance(value, torch.Tensor):
        return value.detach().cpu().tolist()
    return value


def get_sample(ds: LmdbMoleculeDataset, index: int | None, sample_key: str | None):
    if index is not None:
        return index, ds[index]

    for idx in range(len(ds)):
        item = ds[idx]
        if getattr(item, "sample_key", None) == sample_key:
            return idx, item
    raise KeyError(f"sample_key not found in LMDB: {sample_key}")


def graph_descriptor_records(item) -> list[dict[str, Any]]:
    values = getattr(item, "rdkit_graph_desc")
    mask = getattr(item, "rdkit_graph_desc_mask")
    out: list[dict[str, Any]] = []
    for idx, name in enumerate(GRAPH_DESCRIPTOR_NAMES):
        enabled = bool(mask[idx].item())
        out.append(
            {
                "name": name,
                "mask": enabled,
                "value": float(values[idx].item()) if enabled else None,
            }
        )
    return out


def bond_records(item) -> list[dict[str, Any]]:
    bond_index = getattr(item, "rdkit_bond_index")
    bond_order = getattr(item, "rdkit_bond_order")
    if not isinstance(bond_index, torch.Tensor) or not isinstance(bond_order, torch.Tensor):
        return []

    if bond_index.numel() == 0 or bond_order.numel() == 0:
        return []

    index = bond_index.detach().cpu().long()
    order = bond_order.detach().cpu().long().view(-1)
    rows: list[dict[str, Any]] = []
    for edge_idx in range(index.size(1)):
        begin = int(index[0, edge_idx].item())
        end = int(index[1, edge_idx].item())
        order_id = int(order[edge_idx].item())
        order_name = (
            BOND_ORDER_CLASS_NAMES[order_id]
            if 0 <= order_id < len(BOND_ORDER_CLASS_NAMES)
            else f"unknown:{order_id}"
        )
        rows.append(
            {
                "bond_index": edge_idx,
                "begin_atom": begin,
                "end_atom": end,
                "order_id": order_id,
                "order_name": order_name,
            }
        )
    return rows


def node_records(item, x_encoding: str) -> list[dict[str, Any]]:
    x = item.x.view(-1).detach().cpu().tolist()
    pos = item.pos.detach().cpu().tolist()
    y = item.y.view(-1).detach().cpu().tolist()
    charge_mask = item.charge_mask.view(-1).detach().cpu().tolist()

    formal_charge = item.rdkit_node_formal_charge.view(-1).detach().cpu().tolist()
    hybridization = item.rdkit_node_hybridization.view(-1).detach().cpu().tolist()
    is_aromatic = item.rdkit_node_is_aromatic.view(-1).detach().cpu().tolist()
    is_in_ring = item.rdkit_node_is_in_ring.view(-1).detach().cpu().tolist()
    min_ring_size = item.rdkit_node_min_ring_size.view(-1).detach().cpu().tolist()
    total_degree = item.rdkit_node_total_degree.view(-1).detach().cpu().tolist()
    total_num_hs = item.rdkit_node_total_num_Hs.view(-1).detach().cpu().tolist()
    total_valence = item.rdkit_node_total_valence.view(-1).detach().cpu().tolist()
    donor = item.rdkit_node_donor.view(-1).detach().cpu().tolist()
    acceptor = item.rdkit_node_acceptor.view(-1).detach().cpu().tolist()
    estate_type = item.rdkit_node_estate_type.view(-1).detach().cpu().tolist()
    estate_index = item.rdkit_node_estate_index.view(-1).detach().cpu().tolist()
    chiral_tag = item.rdkit_node_chiral_tag.view(-1).detach().cpu().tolist()
    cip_code = item.rdkit_node_cip_code.view(-1).detach().cpu().tolist()
    node_mask = item.rdkit_node_mask.view(-1).detach().cpu().tolist()

    rows: list[dict[str, Any]] = []
    for idx, raw_x in enumerate(x):
        estate_id = int(estate_type[idx])
        rows.append(
            {
                "atom_index": idx,
                "x_raw": int(raw_x),
                "atomic_num": decode_atomic_num(int(raw_x), x_encoding),
                "symbol": decode_symbol(int(raw_x), x_encoding),
                "coord": [float(v) for v in pos[idx]],
                "partial_charge": float(y[idx]),
                "partial_charge_mask": bool(charge_mask[idx]),
                "rdkit_mask": bool(node_mask[idx]),
                "formal_charge": int(formal_charge[idx]),
                "hybridization": HYBRIDIZATION_NAME.get(int(hybridization[idx]), str(int(hybridization[idx]))),
                "is_aromatic": bool(is_aromatic[idx]),
                "is_in_ring": bool(is_in_ring[idx]),
                "min_ring_size": int(min_ring_size[idx]),
                "total_degree": int(total_degree[idx]),
                "total_num_Hs": int(total_num_hs[idx]),
                "total_valence": int(total_valence[idx]),
                "donor": bool(donor[idx]),
                "acceptor": bool(acceptor[idx]),
                "EState_atom_type_id": estate_id,
                "EState_atom_type": ESTATE_TYPE_NAMES[estate_id - 1] if estate_id > 0 else "",
                "EState_index": float(estate_index[idx]),
                "chiral_tag": CHIRAL_TAG_NAME.get(int(chiral_tag[idx]), str(int(chiral_tag[idx]))),
                "CIP_code": CIP_CODE_NAME.get(int(cip_code[idx]), str(int(cip_code[idx]))),
            }
        )
    return rows


def sample_to_dict(logical_index: int, item, x_encoding: str) -> dict[str, Any]:
    return {
        "logical_index": logical_index,
        "sample_key": getattr(item, "sample_key", ""),
        "smiles": getattr(item, "smiles", ""),
        "energy": float(getattr(item, "energy", 0.0)),
        "energy_unit": getattr(item, "energy_unit", ""),
        "num_atoms": int(item.pos.size(0)),
        "rdkit": {
            "schema_version": getattr(item, "rdkit_schema_version", ""),
            "build_mode": getattr(item, "rdkit_build_mode", ""),
            "status": getattr(item, "rdkit_status", ""),
            "fail_reason": getattr(item, "rdkit_fail_reason", ""),
            "bond_status": getattr(item, "rdkit_bond_status", ""),
            "bond_fail_reason": getattr(item, "rdkit_bond_fail_reason", ""),
            "canonical_smiles": getattr(item, "canonical_smiles", ""),
            "isomeric_smiles": getattr(item, "isomeric_smiles", ""),
            "canonical_smiles_from_rdkit": getattr(item, "canonical_smiles_from_rdkit", ""),
            "registration_hash": getattr(item, "registration_hash", ""),
            "match_is_unique": bool(getattr(item, "match_is_unique", False)),
            "total_charge": int(getattr(item, "total_charge", 0)),
            "graph_descriptors": graph_descriptor_records(item),
            "bonds": bond_records(item),
        },
        "nodes": node_records(item, x_encoding),
    }


def print_summary(sample: dict[str, Any]) -> None:
    print(f"logical_index: {sample['logical_index']}")
    print(f"sample_key: {sample['sample_key']}")
    print(f"smiles: {sample['smiles']}")
    print(f"energy: {sample['energy']} {sample['energy_unit']}")
    print(f"num_atoms: {sample['num_atoms']}")
    print(
        "rdkit_status: "
        f"{sample['rdkit']['status']} "
        f"(fail_reason={sample['rdkit']['fail_reason'] or 'none'})"
    )
    print(f"canonical_smiles: {sample['rdkit']['canonical_smiles']}")
    print(f"isomeric_smiles: {sample['rdkit']['isomeric_smiles']}")
    print(f"canonical_smiles_from_rdkit: {sample['rdkit']['canonical_smiles_from_rdkit']}")
    print(f"registration_hash: {sample['rdkit']['registration_hash']}")
    print(f"match_is_unique: {sample['rdkit']['match_is_unique']}")
    print(f"total_charge: {sample['rdkit']['total_charge']}")
    print(
        "bond_status: "
        f"{sample['rdkit']['bond_status']} "
        f"(fail_reason={sample['rdkit']['bond_fail_reason'] or 'none'})"
    )

    print("\n[Graph Descriptors]")
    for row in sample["rdkit"]["graph_descriptors"]:
        value = "NA" if row["value"] is None else f"{row['value']:.6f}"
        print(f"{row['name']:>20}  mask={int(row['mask'])}  value={value}")

    print("\n[Bond Labels]")
    if sample["rdkit"]["bonds"]:
        print("idx begin end order_id order_name")
        for row in sample["rdkit"]["bonds"]:
            print(
                f"{row['bond_index']:>3} "
                f"{row['begin_atom']:>5} "
                f"{row['end_atom']:>3} "
                f"{row['order_id']:>8} "
                f"{row['order_name']}"
            )
    else:
        print("none")

    print("\n[Node Labels]")
    header = (
        "idx sym rdkit_mask q qmask formal hyb aromatic ring ring_sz degree Hs "
        "valence donor acceptor estate_type estate_idx chiral cip coord"
    )
    print(header)
    for row in sample["nodes"]:
        coord = ",".join(f"{v:.4f}" for v in row["coord"])
        print(
            f"{row['atom_index']:>3} "
            f"{row['symbol']:<2} "
            f"{int(row['rdkit_mask'])!s:>10} "
            f"{row['partial_charge']:>7.4f} "
            f"{int(row['partial_charge_mask']):>5} "
            f"{row['formal_charge']:>6} "
            f"{row['hybridization']:<11} "
            f"{int(row['is_aromatic']):>8} "
            f"{int(row['is_in_ring']):>4} "
            f"{row['min_ring_size']:>7} "
            f"{row['total_degree']:>6} "
            f"{row['total_num_Hs']:>2} "
            f"{row['total_valence']:>7} "
            f"{int(row['donor']):>5} "
            f"{int(row['acceptor']):>8} "
            f"{row['EState_atom_type']:<12} "
            f"{row['EState_index']:>10.4f} "
            f"{row['chiral_tag']:<24} "
            f"{row['CIP_code']:<5} "
            f"{coord}"
        )


def main() -> None:
    args = parse_args()
    ds = LmdbMoleculeDataset(args.lmdb_path)
    logical_index, item = get_sample(ds, args.index, args.sample_key)
    sample = sample_to_dict(logical_index, item, args.x_encoding)
    print_summary(sample)

    if args.json_out:
        out_path = Path(args.json_out)
        out_path.write_text(json.dumps(sample, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\njson_written: {out_path}")


if __name__ == "__main__":
    main()
