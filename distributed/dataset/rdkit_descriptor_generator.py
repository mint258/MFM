"""
RDKit descriptor generation for LMDB building.

The mapping contract is intentionally strict:

- The final RDKit molecule is built from the stored SMILES graph.
- 3D coordinates are attached as a conformer only after we verify that the
  explicit-H atom sequence from RDKit exactly matches `data.x`.
- Therefore `data.pos[i]` and `data.x[i]` correspond to RDKit atom `i`.
- If the sequence check fails, the generator does not attempt risky atom
  remapping. It marks all RDKit-derived labels as unavailable instead.

This design prefers false negatives over silent wrong labels.
"""

from __future__ import annotations

import pickle
import time
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List, Sequence

import torch

from rdkit import Chem, RDConfig
from rdkit.Chem import (
    ChemicalFeatures,
    Crippen,
    Descriptors,
    Descriptors3D,
    GraphDescriptors,
    Lipinski,
    MolSurf,
    RegistrationHash,
    rdDetermineBonds,
)
from rdkit.Chem.EState import AtomTypes, EState

from .descriptor_schema import (
    BOND_FAIL_REASON_FIELD,
    BOND_INDEX_FIELD,
    BOND_NEGATIVE_COUNT_FIELD,
    BOND_NEGATIVE_UPPER_IDS_FIELD,
    BOND_ORDER_FIELD,
    BOND_ORDER_TO_ID,
    BOND_STATUS_FIELD,
    ELEMENT_CORRUPT_MASK_FIELD,
    PRETRAIN_BASE_KEY_FIELD,
    PRETRAIN_RECIPE_LEVEL_FIELD,
    PRETRAIN_RECIPE_NAME_FIELD,
    PRETRAIN_RECIPE_SEED_FIELD,
    SAMPLE_TYPE_ID_FIELD,
    TARGET_POS_FIELD,
    TARGET_X_FIELD,
)

RDKIT_SCHEMA_VERSION = "rdkit_descriptor_pack_v2"
RDKitData = object


GRAPH_DESCRIPTOR_SPECS: list[tuple[str, Callable[[Chem.Mol], float], str]] = [
    ("MolLogP", Crippen.MolLogP, "2d"),
    ("MolMR", Crippen.MolMR, "2d"),
    ("TPSA", MolSurf.TPSA, "2d"),
    ("LabuteASA", MolSurf.LabuteASA, "2d"),
    ("ExactMolWt", Descriptors.ExactMolWt, "2d"),
    ("NumValenceElectrons", Descriptors.NumValenceElectrons, "2d"),
    ("HeavyAtomCount", Lipinski.HeavyAtomCount, "2d"),
    ("NumHeteroatoms", Lipinski.NumHeteroatoms, "2d"),
    ("NumHAcceptors", Lipinski.NumHAcceptors, "2d"),
    ("NumHDonors", Lipinski.NumHDonors, "2d"),
    ("NumRotatableBonds", Lipinski.NumRotatableBonds, "2d"),
    ("FractionCSP3", Lipinski.FractionCSP3, "2d"),
    ("RingCount", Lipinski.RingCount, "2d"),
    ("NumAromaticRings", Lipinski.NumAromaticRings, "2d"),
    ("NumAliphaticRings", Lipinski.NumAliphaticRings, "2d"),
    ("NumSaturatedRings", Lipinski.NumSaturatedRings, "2d"),
    ("NumHeterocycles", Lipinski.NumHeterocycles, "2d"),
    ("NumBridgeheadAtoms", Lipinski.NumBridgeheadAtoms, "2d"),
    ("NumSpiroAtoms", Lipinski.NumSpiroAtoms, "2d"),
    ("NumAmideBonds", Lipinski.NumAmideBonds, "2d"),
    ("BertzCT", GraphDescriptors.BertzCT, "2d"),
    ("HallKierAlpha", GraphDescriptors.HallKierAlpha, "2d"),
    ("Kappa1", GraphDescriptors.Kappa1, "2d"),
    ("Kappa2", GraphDescriptors.Kappa2, "2d"),
    ("Kappa3", GraphDescriptors.Kappa3, "2d"),
    ("RadiusOfGyration", Descriptors3D.RadiusOfGyration, "3d"),
    ("NPR1", Descriptors3D.NPR1, "3d"),
    ("NPR2", Descriptors3D.NPR2, "3d"),
    ("Asphericity", Descriptors3D.Asphericity, "3d"),
    ("Eccentricity", Descriptors3D.Eccentricity, "3d"),
    ("PBF", Descriptors3D.PBF, "3d"),
]

GRAPH_DESCRIPTOR_NAMES = tuple(name for name, _, _ in GRAPH_DESCRIPTOR_SPECS)

CIP_CODE_TO_INT = {
    "": 0,
    "R": 1,
    "S": 2,
    "other": 3,
}

AtomTypes.BuildPatts()
ESTATE_TYPE_NAMES = tuple(name for name, _ in AtomTypes.esPatterns)
ESTATE_TYPE_TO_INT = {name: idx + 1 for idx, name in enumerate(ESTATE_TYPE_NAMES)}

FEATURE_FACTORY = ChemicalFeatures.BuildFeatureFactory(
    RDConfig.RDDataDir + "/BaseFeatures.fdef"
)

RDKIT_DESCRIPTOR_PACK_FIELDS = (
    "rdkit_schema_version",
    "rdkit_build_mode",
    "rdkit_status",
    "rdkit_fail_reason",
    "rdkit_graph_desc",
    "rdkit_graph_desc_mask",
    "canonical_smiles",
    "isomeric_smiles",
    "canonical_smiles_from_rdkit",
    "registration_hash",
    "match_is_unique",
    "total_charge",
    "rdkit_node_formal_charge",
    "rdkit_node_hybridization",
    "rdkit_node_is_aromatic",
    "rdkit_node_is_in_ring",
    "rdkit_node_min_ring_size",
    "rdkit_node_total_degree",
    "rdkit_node_total_num_Hs",
    "rdkit_node_total_valence",
    "rdkit_node_donor",
    "rdkit_node_acceptor",
    "rdkit_node_estate_type",
    "rdkit_node_estate_index",
    "rdkit_node_chiral_tag",
    "rdkit_node_cip_code",
    "rdkit_node_mask",
)
RDKIT_BOND_PACK_FIELDS = (
    BOND_INDEX_FIELD,
    BOND_ORDER_FIELD,
    BOND_STATUS_FIELD,
    BOND_FAIL_REASON_FIELD,
)
BOND_NEGATIVE_POOL_PACK_FIELDS = (
    BOND_NEGATIVE_UPPER_IDS_FIELD,
    BOND_NEGATIVE_COUNT_FIELD,
)
PRETRAIN_RECIPE_PACK_FIELDS = (
    TARGET_X_FIELD,
    TARGET_POS_FIELD,
    SAMPLE_TYPE_ID_FIELD,
    ELEMENT_CORRUPT_MASK_FIELD,
    PRETRAIN_RECIPE_NAME_FIELD,
    PRETRAIN_RECIPE_LEVEL_FIELD,
    PRETRAIN_RECIPE_SEED_FIELD,
    PRETRAIN_BASE_KEY_FIELD,
)
PROPERTY_PACK_FIELDS = {
    "rdkit_descriptors": RDKIT_DESCRIPTOR_PACK_FIELDS,
    "rdkit_bonds": RDKIT_BOND_PACK_FIELDS,
    "bond_negative_pool": BOND_NEGATIVE_POOL_PACK_FIELDS,
    "pretrain_recipe": PRETRAIN_RECIPE_PACK_FIELDS,
}


@dataclass
class RDKitGenerationStats:
    total_samples: int = 0
    ok_samples: int = 0
    partial_samples: int = 0
    failed_samples: int = 0
    total_seconds: float = 0.0

    def record(self, status: str, elapsed_s: float) -> None:
        self.total_samples += 1
        self.total_seconds += elapsed_s
        if status == "ok":
            self.ok_samples += 1
        elif status == "partial":
            self.partial_samples += 1
        else:
            self.failed_samples += 1

    @property
    def avg_ms_per_sample(self) -> float:
        if self.total_samples == 0:
            return 0.0
        return 1000.0 * self.total_seconds / self.total_samples


def _raw_x_sequence_from_data(data: RDKitData) -> list[int]:
    x = getattr(data, "x", None)
    if not isinstance(x, torch.Tensor):
        raise TypeError("data.x must be a torch.Tensor")
    if x.dim() == 2 and x.size(-1) == 1:
        x = x.view(-1)
    elif x.dim() != 1:
        raise ValueError(f"Unsupported data.x shape: {tuple(x.shape)}")
    return [int(v) for v in x.tolist()]


def _blank_graph_pack() -> tuple[torch.Tensor, torch.Tensor]:
    n_desc = len(GRAPH_DESCRIPTOR_SPECS)
    return (
        torch.zeros((n_desc,), dtype=torch.float32),
        torch.zeros((n_desc,), dtype=torch.bool),
    )


def _blank_bond_pack() -> dict[str, torch.Tensor]:
    return {
        BOND_INDEX_FIELD: torch.zeros((2, 0), dtype=torch.long),
        BOND_ORDER_FIELD: torch.zeros((0,), dtype=torch.long),
    }


def _blank_node_pack(n_atoms: int) -> dict[str, torch.Tensor]:
    zeros_long = torch.zeros((n_atoms, 1), dtype=torch.long)
    zeros_float = torch.zeros((n_atoms, 1), dtype=torch.float32)
    zeros_bool = torch.zeros((n_atoms, 1), dtype=torch.bool)
    return {
        "rdkit_node_formal_charge": zeros_long.clone(),
        "rdkit_node_hybridization": zeros_long.clone(),
        "rdkit_node_is_aromatic": zeros_bool.clone(),
        "rdkit_node_is_in_ring": zeros_bool.clone(),
        "rdkit_node_min_ring_size": zeros_long.clone(),
        "rdkit_node_total_degree": zeros_long.clone(),
        "rdkit_node_total_num_Hs": zeros_long.clone(),
        "rdkit_node_total_valence": zeros_long.clone(),
        "rdkit_node_donor": zeros_bool.clone(),
        "rdkit_node_acceptor": zeros_bool.clone(),
        "rdkit_node_estate_type": zeros_long.clone(),
        "rdkit_node_estate_index": zeros_float.clone(),
        "rdkit_node_chiral_tag": zeros_long.clone(),
        "rdkit_node_cip_code": zeros_long.clone(),
        "rdkit_node_mask": zeros_bool,
    }


def _fill_failure_fields(data: RDKitData, reason: str) -> RDKitData:
    n_atoms = int(getattr(data, "pos").size(0))
    graph_desc, graph_mask = _blank_graph_pack()
    bond_pack = _blank_bond_pack()
    node_pack = _blank_node_pack(n_atoms)

    data.rdkit_schema_version = RDKIT_SCHEMA_VERSION
    data.rdkit_build_mode = "smiles_identity"
    data.rdkit_status = "failed"
    data.rdkit_fail_reason = reason
    data.rdkit_graph_desc = graph_desc
    data.rdkit_graph_desc_mask = graph_mask
    data.canonical_smiles = ""
    data.isomeric_smiles = ""
    data.canonical_smiles_from_rdkit = ""
    data.registration_hash = ""
    data.match_is_unique = False
    data.total_charge = 0
    data.rdkit_bond_status = "failed"
    data.rdkit_bond_fail_reason = reason

    for key, value in bond_pack.items():
        setattr(data, key, value)

    for key, value in node_pack.items():
        setattr(data, key, value)

    return data


def _attach_conformer(template_h: Chem.Mol, pos: torch.Tensor) -> Chem.Mol:
    mol = Chem.Mol(template_h)
    mol.RemoveAllConformers()
    conf = Chem.Conformer(mol.GetNumAtoms())
    conf.Set3D(True)
    coords = pos.detach().cpu().view(-1, 3).tolist()
    for atom_idx, (x, y, z) in enumerate(coords):
        conf.SetAtomPosition(atom_idx, (float(x), float(y), float(z)))
    mol.AddConformer(conf, assignId=True)
    return mol


def _adjacency_set(mol: Chem.Mol) -> set[tuple[int, int]]:
    pairs: set[tuple[int, int]] = set()
    for bond in mol.GetBonds():
        begin = bond.GetBeginAtomIdx()
        end = bond.GetEndAtomIdx()
        pairs.add((min(begin, end), max(begin, end)))
    return pairs


def _validate_identity_connectivity(rdkit_z_sequence: Sequence[int], pos: torch.Tensor, template_h: Chem.Mol) -> bool:
    coord_builder = Chem.RWMol()
    for atomic_num in rdkit_z_sequence:
        coord_builder.AddAtom(Chem.Atom(int(atomic_num)))
    coord_mol = coord_builder.GetMol()
    conf = Chem.Conformer(coord_mol.GetNumAtoms())
    conf.Set3D(True)
    for atom_idx, (x, y, z) in enumerate(pos.detach().cpu().view(-1, 3).tolist()):
        conf.SetAtomPosition(atom_idx, (float(x), float(y), float(z)))
    coord_mol.AddConformer(conf, assignId=True)
    rdDetermineBonds.DetermineConnectivity(coord_mol)
    return _adjacency_set(coord_mol) == _adjacency_set(template_h)


def _ring_size_labels(mol: Chem.Mol) -> list[int]:
    atom_ring_sizes = [[] for _ in range(mol.GetNumAtoms())]
    for ring in mol.GetRingInfo().AtomRings():
        ring_size = len(ring)
        for atom_idx in ring:
            atom_ring_sizes[atom_idx].append(ring_size)

    result: list[int] = []
    for ring_sizes in atom_ring_sizes:
        if not ring_sizes:
            result.append(0)
            continue
        result.append(min(min(ring_sizes), 7))
    return result


def _feature_membership(mol: Chem.Mol) -> tuple[list[bool], list[bool]]:
    donors = [False] * mol.GetNumAtoms()
    acceptors = [False] * mol.GetNumAtoms()
    for feature in FEATURE_FACTORY.GetFeaturesForMol(mol):
        family = feature.GetFamily()
        if family not in {"Donor", "Acceptor"}:
            continue
        atom_ids = feature.GetAtomIds()
        target = donors if family == "Donor" else acceptors
        for atom_idx in atom_ids:
            target[atom_idx] = True
    return donors, acceptors


def _estate_type_labels(mol: Chem.Mol) -> list[int]:
    labels: list[int] = []
    for typed in AtomTypes.TypeAtoms(mol):
        name = typed[0] if typed else ""
        labels.append(ESTATE_TYPE_TO_INT.get(name, 0))
    return labels


def _cip_label(atom: Chem.Atom) -> int:
    code = atom.GetProp("_CIPCode") if atom.HasProp("_CIPCode") else ""
    return CIP_CODE_TO_INT.get(code, CIP_CODE_TO_INT["other"])


def _build_node_labels(template: Chem.Mol, n_total_atoms: int) -> dict[str, torch.Tensor]:
    heavy_atoms = template.GetNumAtoms()
    labels = _blank_node_pack(n_total_atoms)
    if heavy_atoms == 0:
        return labels

    Chem.AssignStereochemistry(template, cleanIt=True, force=True)
    ring_sizes = _ring_size_labels(template)
    donors, acceptors = _feature_membership(template)
    estate_types = _estate_type_labels(template)
    estate_indices = list(EState.EStateIndices(template))

    node_mask = torch.zeros((n_total_atoms, 1), dtype=torch.bool)
    node_mask[:heavy_atoms, 0] = True

    formal_charge = torch.zeros((n_total_atoms, 1), dtype=torch.long)
    hybridization = torch.zeros((n_total_atoms, 1), dtype=torch.long)
    is_aromatic = torch.zeros((n_total_atoms, 1), dtype=torch.bool)
    is_in_ring = torch.zeros((n_total_atoms, 1), dtype=torch.bool)
    min_ring_size = torch.zeros((n_total_atoms, 1), dtype=torch.long)
    total_degree = torch.zeros((n_total_atoms, 1), dtype=torch.long)
    total_num_hs = torch.zeros((n_total_atoms, 1), dtype=torch.long)
    total_valence = torch.zeros((n_total_atoms, 1), dtype=torch.long)
    donor = torch.zeros((n_total_atoms, 1), dtype=torch.bool)
    acceptor = torch.zeros((n_total_atoms, 1), dtype=torch.bool)
    estate_type = torch.zeros((n_total_atoms, 1), dtype=torch.long)
    estate_index = torch.zeros((n_total_atoms, 1), dtype=torch.float32)
    chiral_tag = torch.zeros((n_total_atoms, 1), dtype=torch.long)
    cip_code = torch.zeros((n_total_atoms, 1), dtype=torch.long)

    for atom_idx, atom in enumerate(template.GetAtoms()):
        formal_charge[atom_idx, 0] = int(atom.GetFormalCharge())
        hybridization[atom_idx, 0] = int(atom.GetHybridization())
        is_aromatic[atom_idx, 0] = bool(atom.GetIsAromatic())
        is_in_ring[atom_idx, 0] = bool(atom.IsInRing())
        min_ring_size[atom_idx, 0] = int(ring_sizes[atom_idx])
        total_degree[atom_idx, 0] = int(atom.GetTotalDegree())
        total_num_hs[atom_idx, 0] = int(atom.GetTotalNumHs())
        total_valence[atom_idx, 0] = int(atom.GetTotalValence())
        donor[atom_idx, 0] = bool(donors[atom_idx])
        acceptor[atom_idx, 0] = bool(acceptors[atom_idx])
        estate_type[atom_idx, 0] = int(estate_types[atom_idx])
        estate_index[atom_idx, 0] = float(estate_indices[atom_idx])
        chiral_tag[atom_idx, 0] = int(atom.GetChiralTag())
        cip_code[atom_idx, 0] = int(_cip_label(atom))

    labels["rdkit_node_formal_charge"] = formal_charge
    labels["rdkit_node_hybridization"] = hybridization
    labels["rdkit_node_is_aromatic"] = is_aromatic
    labels["rdkit_node_is_in_ring"] = is_in_ring
    labels["rdkit_node_min_ring_size"] = min_ring_size
    labels["rdkit_node_total_degree"] = total_degree
    labels["rdkit_node_total_num_Hs"] = total_num_hs
    labels["rdkit_node_total_valence"] = total_valence
    labels["rdkit_node_donor"] = donor
    labels["rdkit_node_acceptor"] = acceptor
    labels["rdkit_node_estate_type"] = estate_type
    labels["rdkit_node_estate_index"] = estate_index
    labels["rdkit_node_chiral_tag"] = chiral_tag
    labels["rdkit_node_cip_code"] = cip_code
    labels["rdkit_node_mask"] = node_mask
    return labels


def _bond_order_id(bond: Chem.Bond) -> int:
    bond_type = bond.GetBondType()
    if bond.GetIsAromatic() or bond_type == Chem.BondType.AROMATIC:
        return BOND_ORDER_TO_ID["aromatic"]
    if bond_type == Chem.BondType.SINGLE:
        return BOND_ORDER_TO_ID["single"]
    if bond_type == Chem.BondType.DOUBLE:
        return BOND_ORDER_TO_ID["double"]
    if bond_type == Chem.BondType.TRIPLE:
        return BOND_ORDER_TO_ID["triple"]
    return BOND_ORDER_TO_ID["other"]


def _build_bond_labels(template_h: Chem.Mol) -> dict[str, torch.Tensor]:
    pairs: list[tuple[int, int, int]] = []
    for bond in template_h.GetBonds():
        begin = int(bond.GetBeginAtomIdx())
        end = int(bond.GetEndAtomIdx())
        i = min(begin, end)
        j = max(begin, end)
        pairs.append((i, j, _bond_order_id(bond)))
    pairs.sort(key=lambda item: (item[0], item[1]))

    if not pairs:
        return _blank_bond_pack()

    index = torch.tensor([[i, j] for i, j, _ in pairs], dtype=torch.long).t().contiguous()
    order = torch.tensor([order_id for _, _, order_id in pairs], dtype=torch.long)
    return {
        BOND_INDEX_FIELD: index,
        BOND_ORDER_FIELD: order,
    }


def _compute_graph_descriptors(template: Chem.Mol, mol_3d: Chem.Mol) -> tuple[torch.Tensor, torch.Tensor]:
    values: list[float] = []
    mask: list[bool] = []
    for _, fn, mode in GRAPH_DESCRIPTOR_SPECS:
        source = template if mode == "2d" else mol_3d
        try:
            values.append(float(fn(source)))
            mask.append(True)
        except Exception:
            values.append(0.0)
            mask.append(False)
    return (
        torch.tensor(values, dtype=torch.float32),
        torch.tensor(mask, dtype=torch.bool),
    )


def _clone_data(data: RDKitData) -> RDKitData:
    return pickle.loads(pickle.dumps(data, protocol=pickle.HIGHEST_PROTOCOL))


def has_property_pack(data: RDKitData, pack_name: str) -> bool:
    field_names = PROPERTY_PACK_FIELDS.get(str(pack_name))
    if field_names is None:
        raise ValueError(f"Unknown property pack: {pack_name}")
    if not all(hasattr(data, field_name) for field_name in field_names):
        return False
    if pack_name == "rdkit_descriptors":
        return bool(str(getattr(data, "rdkit_status", "")).strip())
    if pack_name == "rdkit_bonds":
        return bool(str(getattr(data, BOND_STATUS_FIELD, "")).strip())
    return True


def detect_property_packs(data: RDKitData) -> tuple[str, ...]:
    return tuple(pack_name for pack_name in PROPERTY_PACK_FIELDS if has_property_pack(data, pack_name))


def missing_property_packs(data: RDKitData, requested_packs: Iterable[str]) -> tuple[str, ...]:
    ordered = []
    seen = set()
    for pack_name in requested_packs:
        normalized = str(pack_name).strip()
        if normalized in seen:
            continue
        seen.add(normalized)
        if not has_property_pack(data, normalized):
            ordered.append(normalized)
    return tuple(ordered)


def _copy_pack_fields(dst: RDKitData, src: RDKitData, pack_name: str) -> None:
    for field_name in PROPERTY_PACK_FIELDS[pack_name]:
        if hasattr(src, field_name):
            setattr(dst, field_name, getattr(src, field_name))


class RDKitDescriptorGenerator:
    """
    Generate RDKit-derived labels for a single PyG `Data` sample.

    Stored field semantics:
    - `rdkit_graph_desc[k]` follows the order in `GRAPH_DESCRIPTOR_NAMES`.
    - `rdkit_node_*[i]` always refers to the same atom as `data.x[i]` / `data.pos[i]`.
    - `rdkit_node_mask[i] == 1` means the atom carries reliable 2D RDKit labels.
      In this first version only heavy atoms are supervised for node-level tasks.
    """

    def __init__(self) -> None:
        self.stats = RDKitGenerationStats()

    def annotate(self, data: RDKitData) -> RDKitData:
        started = time.perf_counter()
        status = "failed"
        try:
            annotated = self._annotate_impl(data)
            status = getattr(annotated, "rdkit_status", "failed")
            return annotated
        except Exception as exc:
            annotated = _fill_failure_fields(data, f"unexpected_error:{type(exc).__name__}:{exc}")
            status = "failed"
            return annotated
        finally:
            self.stats.record(status, time.perf_counter() - started)

    def _annotate_impl(self, data: RDKitData) -> RDKitData:
        smiles = getattr(data, "smiles", None)
        if not isinstance(smiles, str) or not smiles.strip():
            return _fill_failure_fields(data, "missing_smiles")
        smiles = smiles.strip()

        template = Chem.MolFromSmiles(smiles)
        if template is None:
            return _fill_failure_fields(data, "smiles_parse_failed")

        try:
            template_h = Chem.AddHs(template)
        except Exception as exc:
            return _fill_failure_fields(data, f"add_hs_failed:{type(exc).__name__}:{exc}")

        raw_x_sequence = _raw_x_sequence_from_data(data)
        rdkit_z_sequence = [atom.GetAtomicNum() for atom in template_h.GetAtoms()]
        if len(raw_x_sequence) != len(rdkit_z_sequence):
            return _fill_failure_fields(
                data,
                f"atom_count_mismatch:data={len(raw_x_sequence)} rdkit={len(rdkit_z_sequence)}",
            )
        if raw_x_sequence == rdkit_z_sequence:
            pass
        elif [value + 1 for value in raw_x_sequence] == rdkit_z_sequence:
            pass
        else:
            return _fill_failure_fields(data, "atom_sequence_mismatch")

        pos = getattr(data, "pos", None)
        if not isinstance(pos, torch.Tensor) or pos.dim() != 2 or pos.size(1) != 3:
            return _fill_failure_fields(data, "invalid_pos_tensor")

        try:
            identity_ok = _validate_identity_connectivity(rdkit_z_sequence, pos, template_h)
        except Exception as exc:
            return _fill_failure_fields(
                data,
                f"connectivity_validation_failed:{type(exc).__name__}:{exc}",
            )
        if not identity_ok:
            return _fill_failure_fields(data, "connectivity_identity_mismatch")

        try:
            mol_3d = _attach_conformer(template_h, pos)
        except Exception as exc:
            return _fill_failure_fields(data, f"attach_conformer_failed:{type(exc).__name__}:{exc}")

        try:
            bond_pack = _build_bond_labels(template_h)
        except Exception as exc:
            data = _fill_failure_fields(data, f"bond_label_failed:{type(exc).__name__}:{exc}")
            return data

        try:
            node_pack = _build_node_labels(template, n_total_atoms=mol_3d.GetNumAtoms())
        except Exception as exc:
            graph_desc, graph_mask = _compute_graph_descriptors(template, mol_3d)
            data = _fill_failure_fields(data, f"node_label_failed:{type(exc).__name__}:{exc}")
            data.rdkit_graph_desc = graph_desc
            data.rdkit_graph_desc_mask = graph_mask
            data.rdkit_status = "partial" if bool(graph_mask.any()) else "failed"
            for key, value in bond_pack.items():
                setattr(data, key, value)
            data.rdkit_bond_status = "ok"
            data.rdkit_bond_fail_reason = ""
            return data

        graph_desc, graph_mask = _compute_graph_descriptors(template, mol_3d)

        canonical_smiles = Chem.MolToSmiles(template, canonical=True, isomericSmiles=False)
        isomeric_smiles = Chem.MolToSmiles(template, canonical=True, isomericSmiles=True)
        rebuilt_smiles = Chem.MolToSmiles(
            Chem.RemoveHs(Chem.Mol(mol_3d)),
            canonical=True,
            isomericSmiles=True,
        )
        registration_hash = RegistrationHash.GetMolHash(
            RegistrationHash.GetMolLayers(template)
        )

        data.rdkit_schema_version = RDKIT_SCHEMA_VERSION
        data.rdkit_build_mode = "smiles_identity"
        data.rdkit_status = "ok" if bool(graph_mask.all()) else "partial"
        data.rdkit_fail_reason = ""
        data.rdkit_graph_desc = graph_desc
        data.rdkit_graph_desc_mask = graph_mask
        data.canonical_smiles = canonical_smiles
        data.isomeric_smiles = isomeric_smiles
        data.canonical_smiles_from_rdkit = rebuilt_smiles
        data.registration_hash = registration_hash
        data.match_is_unique = True
        data.total_charge = int(sum(atom.GetFormalCharge() for atom in template.GetAtoms()))
        data.rdkit_bond_status = "ok"
        data.rdkit_bond_fail_reason = ""

        for key, value in node_pack.items():
            setattr(data, key, value)
        for key, value in bond_pack.items():
            setattr(data, key, value)

        if data.rdkit_status == "partial":
            data.rdkit_fail_reason = "graph_descriptor_subset_failed"

        return data

    def augment_missing(
        self,
        data: RDKitData,
        required_packs: Iterable[str] = ("rdkit_descriptors", "rdkit_bonds"),
    ) -> tuple[RDKitData, tuple[str, ...]]:
        missing = missing_property_packs(data, required_packs)
        if not missing:
            return data, ()

        annotated = self.annotate(_clone_data(data))
        for pack_name in missing:
            _copy_pack_fields(data, annotated, pack_name)
        data.rdkit_schema_version = getattr(annotated, "rdkit_schema_version", RDKIT_SCHEMA_VERSION)
        return data, missing

    def summary_lines(self) -> list[str]:
        return [
            "[rdkit] schema="
            f"{RDKIT_SCHEMA_VERSION} total={self.stats.total_samples} "
            f"ok={self.stats.ok_samples} partial={self.stats.partial_samples} "
            f"failed={self.stats.failed_samples}",
            f"[rdkit] avg_descriptor_time_ms={self.stats.avg_ms_per_sample:.3f}",
        ]


def make_rdkit_descriptor_generator() -> RDKitDescriptorGenerator:
    return RDKitDescriptorGenerator()
