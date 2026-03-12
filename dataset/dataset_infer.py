#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dataset_infer.py
--------------------------------
Inference-only dataloader aligned with the training sample format.

Returned fields are consistent with the new training dataset as much as possible:
- `x`, `pos`, `y`, `charge_mask`
- `energy`, `energy_unit`
- `smiles`, `sample_key`
- `filename`
"""

from __future__ import annotations

import glob
import logging
import math
import os
import re
from typing import List, Optional, Tuple

import torch
from torch_geometric.data import Data, Dataset


try:
    import periodictable as _pt

    _ELEMENT_TO_IDX = {
        element.symbol: idx
        for idx, element in enumerate(_pt.elements)
        if getattr(element, "symbol", None)
    }
except ModuleNotFoundError:
    _EL_LIST = (
        "H He Li Be B C N O F Ne "
        "Na Mg Al Si P S Cl Ar K Ca "
        "Sc Ti V Cr Mn Fe Co Ni Cu Zn "
        "Ga Ge As Se Br Kr"
    ).split()
    _ELEMENT_TO_IDX = {symbol: i for i, symbol in enumerate(_EL_LIST)}


_FLOAT_PAT = re.compile(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?")


def _to_float(text: str) -> float:
    return float(text.replace("*^", "e").replace("D", "e"))


def _read_nonempty_lines(path: str) -> List[str]:
    with open(path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def _standardize_filename(filename: str) -> str:
    return filename.replace("_new", "")


def _sample_key_from_path(path: str) -> str:
    stem = os.path.splitext(os.path.basename(path))[0]
    return _standardize_filename(stem)


def _is_atom_row(parts: List[str]) -> bool:
    if len(parts) < 4:
        return False
    if parts[0] not in _ELEMENT_TO_IDX:
        return False
    try:
        _to_float(parts[1])
        _to_float(parts[2])
        _to_float(parts[3])
    except ValueError:
        return False
    return True


def _parse_energy(comment: str) -> Tuple[float, str]:
    if "SCF Energy:" in comment:
        payload = comment.split("SCF Energy:", 1)[1].strip()
    elif comment.lower().startswith("energy:"):
        payload = comment.split(":", 1)[1].strip()
    else:
        return math.nan, "unknown"

    match = _FLOAT_PAT.search(payload)
    if match is None:
        return math.nan, "unknown"

    energy = _to_float(match.group(0))
    if "Hartree" in comment:
        unit = "Hartree"
    elif "kcal/mol" in comment:
        unit = "kcal/mol"
    else:
        unit = "unknown"
    return energy, unit


def _parse_xyz(path: str, allow_unknown: bool = False) -> Data:
    lines = _read_nonempty_lines(path)
    if len(lines) < 3:
        raise ValueError(f"{path}: file is too short")

    n_atom = int(lines[0].strip())
    comment = lines[1].strip()
    atom_lines = lines[2 : 2 + n_atom]
    if len(atom_lines) != n_atom:
        raise ValueError(f"{path}: atom line count mismatch")

    energy, energy_unit = _parse_energy(comment)

    atoms: List[str] = []
    coords: List[List[float]] = []
    charges: List[float] = []
    saw_charge = False

    for ln in atom_lines:
        parts = ln.split()
        if len(parts) < 4:
            raise ValueError(f"{path}: malformed atom row")
        sym = parts[0]
        if sym not in _ELEMENT_TO_IDX:
            if allow_unknown:
                continue
            raise KeyError(f"Unknown element: {sym} @ {path}")
        atoms.append(sym)
        coords.append([_to_float(x) for x in parts[1:4]])
        if len(parts) >= 5:
            charges.append(_to_float(parts[4]))
            saw_charge = True

    z = torch.tensor([_ELEMENT_TO_IDX[a] for a in atoms], dtype=torch.long).view(-1, 1)
    pos = torch.tensor(coords, dtype=torch.float)
    n_kept = int(pos.size(0))

    tail_smiles = ""
    if len(lines) > 2 + n_atom:
        tail_parts = lines[-1].split()
        if not _is_atom_row(tail_parts):
            tail_smiles = lines[-1]

    data = Data(x=z, pos=pos, filename=os.path.basename(path))
    data.sample_key = _sample_key_from_path(path)
    data.smiles = tail_smiles
    data.energy = float(energy)
    data.energy_unit = energy_unit

    if saw_charge and len(charges) == n_kept:
        data.y = torch.tensor(charges, dtype=torch.float).view(-1, 1)
        data.charge_mask = torch.ones((n_kept, 1), dtype=torch.float)
    else:
        data.y = torch.zeros((n_kept, 1), dtype=torch.float)
        data.charge_mask = torch.zeros((n_kept, 1), dtype=torch.float)

    return data


class MoleculeDataset(Dataset):
    """
    Inference dataset aligned with the training sample format.

    Parameters
    ----------
    root : str
        Root directory; all `.xyz` files are found recursively.
    start_idx / end_idx : int, optional
        Slice the discovered file list.
    allow_unknown : bool
        If True, unknown elements are skipped. If False, parsing raises.
    """

    def __init__(
        self,
        root: str,
        transform=None,
        pre_transform=None,
        *,
        start_idx: int = 0,
        end_idx: Optional[int] = None,
        allow_unknown: bool = False,
    ):
        super().__init__(root, transform, pre_transform)
        self.file_paths: List[str] = sorted(
            glob.glob(os.path.join(root, "**", "*.xyz"), recursive=True)
        )
        if not self.file_paths:
            raise FileNotFoundError(f"No .xyz files found under {root}")
        self.file_paths = self.file_paths[start_idx:end_idx]
        self.allow_unknown = allow_unknown
        logging.info("InferenceDataset | loaded %d xyz files", len(self.file_paths))

    def len(self) -> int:  # type: ignore[override]
        return len(self.file_paths)

    def get(self, idx: int) -> Data:  # type: ignore[override]
        path = self.file_paths[idx]
        return _parse_xyz(path, self.allow_unknown)

    def raw_file_names(self):
        return []

    def processed_file_names(self):
        return []
