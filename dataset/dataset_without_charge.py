import logging
import os
import re
from typing import Dict, List, Optional

import periodictable
import torch
from torch_geometric.data import Data, Dataset


LOGGER = logging.getLogger(__name__)

ELEMENT_TO_Z = {
    element.symbol: idx
    for idx, element in enumerate(periodictable.elements)
    if getattr(element, "symbol", None)
}

STABLE_PAT = re.compile(r"(.*_\d{8}_\d{2})(?:\.xyz)$")
TRANSITION_PAT = re.compile(r"(.*_\d{8}_\d{2})_(\d+)\.xyz$")
IDX_PAT = re.compile(r"_(\d{8})_\d{2}$")
FLOAT_PAT = re.compile(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?")


def standardize_filename(filename: str) -> str:
    return filename.replace("_new", "")


def extract_sample_key(filename: str) -> Optional[str]:
    base = standardize_filename(os.path.basename(filename))
    match = STABLE_PAT.fullmatch(base)
    return match.group(1) if match else None


def extract_transition_key(filename: str) -> tuple[Optional[str], Optional[int]]:
    base = standardize_filename(os.path.basename(filename))
    match = TRANSITION_PAT.fullmatch(base)
    if not match:
        return None, None
    return match.group(1), int(match.group(2))


def extract_dataset_idx(sample_key: str) -> int:
    match = IDX_PAT.search(sample_key)
    if not match:
        raise ValueError(f"Cannot parse 8-digit dataset index from key: {sample_key}")
    return int(match.group(1))


def read_nonempty_lines(file_path: str) -> List[str]:
    with open(file_path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def parse_energy_line(line: str) -> tuple[float, str]:
    if "SCF Energy:" not in line:
        raise ValueError(f"Unrecognized energy line: {line}")
    payload = line.split("SCF Energy:", 1)[1].strip()
    match = FLOAT_PAT.search(payload)
    if match is None:
        raise ValueError(f"Failed to parse energy from line: {line}")
    energy = float(match.group(0).replace("*^", "e").replace("D", "e"))
    if "Hartree" in line:
        unit = "Hartree"
    elif "kcal/mol" in line:
        unit = "kcal/mol"
    else:
        unit = "unknown"
    return energy, unit


def _to_float(text: str) -> float:
    return float(text.replace("*^", "e").replace("D", "e"))


def parse_xyz_stable(file_path: str) -> Data:
    lines = read_nonempty_lines(file_path)
    if len(lines) < 2:
        raise ValueError(f"File is too short: {file_path}")

    atom_num = int(lines[0])
    energy, energy_unit = parse_energy_line(lines[1])
    atom_lines = lines[2 : 2 + atom_num]
    if len(atom_lines) != atom_num:
        raise ValueError(f"Atom line count mismatch in stable xyz: {file_path}")

    atom_types: List[str] = []
    positions: List[List[float]] = []
    charges: List[float] = []
    saw_charge = False
    saw_no_charge = False

    for line in atom_lines:
        parts = line.split()
        if len(parts) < 4:
            raise ValueError(f"Incomplete stable xyz row: {file_path}")
        atom = parts[0]
        if atom not in ELEMENT_TO_Z:
            raise KeyError(f"Unknown element {atom} in {file_path}")
        atom_types.append(atom)
        positions.append([_to_float(x) for x in parts[1:4]])
        if len(parts) >= 5:
            charges.append(_to_float(parts[4]))
            saw_charge = True
        else:
            saw_no_charge = True

    if saw_charge and saw_no_charge:
        raise ValueError(f"Mixed charged/uncharged atom rows in stable xyz: {file_path}")

    z = torch.tensor([ELEMENT_TO_Z[atom] for atom in atom_types], dtype=torch.long).view(-1, 1)
    pos = torch.tensor(positions, dtype=torch.float)
    data = Data(x=z, pos=pos, energy=energy)
    data.energy_unit = energy_unit

    if saw_charge:
        data.y = torch.tensor(charges, dtype=torch.float).view(-1, 1)
        data.charge_mask = torch.ones((atom_num, 1), dtype=torch.float)
    else:
        data.y = torch.zeros((atom_num, 1), dtype=torch.float)
        data.charge_mask = torch.zeros((atom_num, 1), dtype=torch.float)

    return data


def parse_xyz_transition(file_path: str) -> Data:
    lines = read_nonempty_lines(file_path)
    if len(lines) < 2:
        raise ValueError(f"File is too short: {file_path}")

    atom_num = int(lines[0])
    energy, energy_unit = parse_energy_line(lines[1])
    atom_lines = lines[2 : 2 + atom_num]
    if len(atom_lines) != atom_num:
        raise ValueError(f"Atom line count mismatch in transition xyz: {file_path}")

    atom_types: List[str] = []
    positions: List[List[float]] = []
    for line in atom_lines:
        parts = line.split()
        if len(parts) < 4:
            raise ValueError(f"Incomplete transition xyz row: {file_path}")
        atom = parts[0]
        if atom not in ELEMENT_TO_Z:
            raise KeyError(f"Unknown element {atom} in {file_path}")
        atom_types.append(atom)
        positions.append([_to_float(x) for x in parts[1:4]])

    z = torch.tensor([ELEMENT_TO_Z[atom] for atom in atom_types], dtype=torch.long).view(-1, 1)
    pos = torch.tensor(positions, dtype=torch.float)
    data = Data(x=z, pos=pos, energy=energy)
    data.energy_unit = energy_unit
    data.charge_mask = torch.zeros((atom_num, 1), dtype=torch.float)
    return data


def read_smiles_from_input_xyz(file_path: str) -> Optional[str]:
    lines = read_nonempty_lines(file_path)
    if len(lines) < 2:
        raise ValueError(f"File is too short: {file_path}")

    atom_num = int(lines[0])
    coord_end = 2 + atom_num
    if len(lines) < coord_end:
        raise ValueError(f"Coordinate line count mismatch in raw xyz: {file_path}")

    if len(lines) <= coord_end:
        return None
    return lines[-1]


class MoleculeDataset(Dataset):
    """
    Build samples from optimized xyz files and optionally attach SMILES from raw xyz files.

    Default behavior:
    - `include_trajectory=False`: skip `geom_frames` to reduce startup and LMDB size.
    - `include_smiles=True`: read SMILES from the last line of the matched raw xyz file.
    """

    def __init__(
        self,
        root=None,
        stable_folder="train_result_geometric_optimization",
        raw_folder="train_data",
        transition_folder="geom_frames",
        stable_root=None,
        raw_root=None,
        transition_root=None,
        start_idx=None,
        end_idx=None,
        include_smiles=True,
        require_smiles=True,
        include_trajectory=False,
        transform=None,
        pre_transform=None,
    ):
        dataset_root = root or stable_root or raw_root
        super().__init__(dataset_root, transform, pre_transform)
        self.root = dataset_root
        self.start_idx = start_idx
        self.end_idx = end_idx
        self.include_smiles = include_smiles
        self.require_smiles = require_smiles
        self.include_trajectory = include_trajectory

        stable_dir = self._resolve_dir(root, stable_root, stable_folder, required=True, label="stable")
        raw_dir = self._resolve_dir(root, raw_root, raw_folder, required=include_smiles, label="raw")
        transition_dir = self._resolve_dir(
            root,
            transition_root,
            transition_folder,
            required=False,
            label="transition",
        )

        stable_groups = self._scan_stable_files(stable_dir)
        raw_lookup = self._scan_raw_files(raw_dir) if include_smiles else {}
        transition_lookup = self._scan_transition_files(transition_dir) if include_trajectory else {}

        missing_smiles: List[str] = []
        samples = []
        for key in sorted(stable_groups):
            idx = extract_dataset_idx(key)
            if self.start_idx is not None and idx < self.start_idx:
                continue
            if self.end_idx is not None and idx > self.end_idx:
                continue

            raw_path = raw_lookup.get(key)
            if include_smiles and require_smiles and raw_path is None:
                missing_smiles.append(key)
                continue

            samples.append(
                {
                    "key": key,
                    "stable_path": sorted(stable_groups[key])[-1],
                    "raw_path": raw_path,
                    "transition_paths": transition_lookup.get(key, []),
                }
            )

        if missing_smiles:
            preview = ", ".join(missing_smiles[:5])
            raise FileNotFoundError(
                f"{len(missing_smiles)} optimized samples are missing matching raw xyz files. "
                f"Examples: {preview}"
            )

        self.samples = samples
        LOGGER.info(
            "MoleculeDataset(%s) loaded %d samples [stable=%s raw=%s smiles=%s trajectory=%s filter %s-%s]",
            self.root,
            len(self.samples),
            stable_dir,
            raw_dir,
            include_smiles,
            include_trajectory,
            str(self.start_idx),
            str(self.end_idx),
        )

    @staticmethod
    def _resolve_dir(
        root: Optional[str],
        explicit_root: Optional[str],
        folder_name: str,
        required: bool,
        label: str,
    ) -> Optional[str]:
        if explicit_root is not None:
            return os.path.abspath(explicit_root)
        if root is not None:
            return os.path.join(root, folder_name)
        if required:
            raise FileNotFoundError(
                f"Missing {label} directory. Provide either `root` or `{label}_root`."
            )
        return None

    def _scan_stable_files(self, stable_dir: str) -> Dict[str, List[str]]:
        if not os.path.isdir(stable_dir):
            raise FileNotFoundError(f"Stable xyz directory does not exist: {stable_dir}")

        groups: Dict[str, List[str]] = {}
        with os.scandir(stable_dir) as it:
            for entry in it:
                if not entry.is_file() or not entry.name.endswith(".xyz"):
                    continue
                key = extract_sample_key(entry.name)
                if key is None:
                    continue
                groups.setdefault(key, []).append(entry.path)

        if not groups:
            raise FileNotFoundError(f"No usable stable xyz files found in: {stable_dir}")
        return groups

    def _scan_raw_files(self, raw_dir: str) -> Dict[str, str]:
        if not os.path.isdir(raw_dir):
            raise FileNotFoundError(f"Raw xyz directory does not exist: {raw_dir}")

        mapping: Dict[str, str] = {}
        with os.scandir(raw_dir) as it:
            for entry in it:
                if not entry.is_file() or not entry.name.endswith(".xyz"):
                    continue
                key = extract_sample_key(entry.name)
                if key is None:
                    continue
                old = mapping.get(key)
                if old is None or entry.name > os.path.basename(old):
                    mapping[key] = entry.path
        return mapping

    def _scan_transition_files(self, transition_dir: Optional[str]) -> Dict[str, List[str]]:
        if transition_dir is None:
            return {}
        if not os.path.isdir(transition_dir):
            LOGGER.warning("Transition directory does not exist, skipping: %s", transition_dir)
            return {}

        mapping: Dict[str, List[tuple[int, str]]] = {}
        with os.scandir(transition_dir) as it:
            for entry in it:
                if not entry.is_file() or not entry.name.endswith(".xyz"):
                    continue
                key, frame = extract_transition_key(entry.name)
                if key is None or frame is None:
                    continue
                mapping.setdefault(key, []).append((frame, entry.path))

        return {key: [path for _, path in sorted(items)] for key, items in mapping.items()}

    def len(self):
        return len(self.samples)

    def get(self, idx):
        sample = self.samples[idx]
        stable = parse_xyz_stable(sample["stable_path"])
        stable.sample_key = sample["key"]

        raw_path = sample["raw_path"]
        if self.include_smiles and raw_path is not None:
            smiles = read_smiles_from_input_xyz(raw_path)
            if self.require_smiles and not smiles:
                raise ValueError(f"Raw xyz is missing SMILES: {raw_path}")
            stable.smiles = smiles

        if self.include_trajectory:
            traj = []
            for path in sample["transition_paths"]:
                try:
                    traj.append(parse_xyz_transition(path))
                except Exception as exc:
                    LOGGER.error("Transition parse fail (%s): %s", path, exc)
            stable.trajectory = traj

        return stable
