from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable


GRAPH_DESCRIPTOR_NAMES = (
    "MolLogP",
    "MolMR",
    "TPSA",
    "LabuteASA",
    "ExactMolWt",
    "NumValenceElectrons",
    "HeavyAtomCount",
    "NumHeteroatoms",
    "NumHAcceptors",
    "NumHDonors",
    "NumRotatableBonds",
    "FractionCSP3",
    "RingCount",
    "NumAromaticRings",
    "NumAliphaticRings",
    "NumSaturatedRings",
    "NumHeterocycles",
    "NumBridgeheadAtoms",
    "NumSpiroAtoms",
    "NumAmideBonds",
    "BertzCT",
    "HallKierAlpha",
    "Kappa1",
    "Kappa2",
    "Kappa3",
    "RadiusOfGyration",
    "NPR1",
    "NPR2",
    "Asphericity",
    "Eccentricity",
    "PBF",
)

GRAPH_GEOMETRY_DESCRIPTOR_NAMES = (
    "RadiusOfGyration",
    "NPR1",
    "NPR2",
    "Asphericity",
    "Eccentricity",
    "PBF",
)

GRAPH_EXTENSIVE_DESCRIPTOR_NAMES = (
    "ExactMolWt",
    "NumValenceElectrons",
    "HeavyAtomCount",
    "NumHeteroatoms",
    "NumHAcceptors",
    "NumHDonors",
    "NumRotatableBonds",
    "RingCount",
    "NumAromaticRings",
    "NumAliphaticRings",
    "NumSaturatedRings",
    "NumHeterocycles",
    "NumBridgeheadAtoms",
    "NumSpiroAtoms",
    "NumAmideBonds",
)

_GRAPH_DESCRIPTOR_INDEX = {name: idx for idx, name in enumerate(GRAPH_DESCRIPTOR_NAMES)}
GRAPH_GEOMETRY_DESCRIPTOR_INDICES = tuple(_GRAPH_DESCRIPTOR_INDEX[name] for name in GRAPH_GEOMETRY_DESCRIPTOR_NAMES)
GRAPH_EXTENSIVE_DESCRIPTOR_INDICES = tuple(_GRAPH_DESCRIPTOR_INDEX[name] for name in GRAPH_EXTENSIVE_DESCRIPTOR_NAMES)
GRAPH_CHEM_DESCRIPTOR_NAMES = tuple(
    name
    for name in GRAPH_DESCRIPTOR_NAMES
    if name not in set(GRAPH_GEOMETRY_DESCRIPTOR_NAMES) and name not in set(GRAPH_EXTENSIVE_DESCRIPTOR_NAMES)
)
GRAPH_CHEM_DESCRIPTOR_INDICES = tuple(_GRAPH_DESCRIPTOR_INDEX[name] for name in GRAPH_CHEM_DESCRIPTOR_NAMES)

RDKIT_GRAPH_DESC_DIM = len(GRAPH_DESCRIPTOR_NAMES)
ESTATE_TYPE_NUM_CLASSES = 80

BOND_INDEX_FIELD = "rdkit_bond_index"
BOND_ORDER_FIELD = "rdkit_bond_order"
BOND_STATUS_FIELD = "rdkit_bond_status"
BOND_FAIL_REASON_FIELD = "rdkit_bond_fail_reason"
BOND_NEGATIVE_UPPER_IDS_FIELD = "rdkit_bond_negative_upper_ids"
BOND_NEGATIVE_COUNT_FIELD = "rdkit_bond_negative_count"

TARGET_X_FIELD = "target_x"
TARGET_POS_FIELD = "target_pos"
SAMPLE_TYPE_ID_FIELD = "sample_type_id"
ELEMENT_CORRUPT_MASK_FIELD = "element_corrupt_mask"
PRETRAIN_RECIPE_NAME_FIELD = "pretrain_recipe_name"
PRETRAIN_RECIPE_LEVEL_FIELD = "pretrain_recipe_level"
PRETRAIN_RECIPE_SEED_FIELD = "pretrain_recipe_seed"
PRETRAIN_BASE_KEY_FIELD = "pretrain_base_key"

BOND_ORDER_CLASS_NAMES = (
    "none",
    "single",
    "double",
    "triple",
    "aromatic",
    "other",
)
BOND_ORDER_TO_ID = {name: idx for idx, name in enumerate(BOND_ORDER_CLASS_NAMES)}
BOND_ORDER_NUM_CLASSES = len(BOND_ORDER_CLASS_NAMES)


@dataclass(frozen=True)
class DescriptorTargetSpec:
    name: str
    field_name: str
    task_type: str
    num_outputs: int
    num_classes: int | None = None


@dataclass(frozen=True)
class BondTargetSpec:
    name: str
    index_field: str
    task_type: str
    value_field: str | None = None
    num_classes: int | None = None


CHARGE_DESCRIPTOR_SPECS = (
    DescriptorTargetSpec(
        name="formal_charge",
        field_name="rdkit_node_formal_charge",
        task_type="regression",
        num_outputs=1,
    ),
    DescriptorTargetSpec(
        name="donor",
        field_name="rdkit_node_donor",
        task_type="binary",
        num_outputs=1,
    ),
    DescriptorTargetSpec(
        name="acceptor",
        field_name="rdkit_node_acceptor",
        task_type="binary",
        num_outputs=1,
    ),
    DescriptorTargetSpec(
        name="estate_index",
        field_name="rdkit_node_estate_index",
        task_type="regression",
        num_outputs=1,
    ),
)

ELEMENT_DESCRIPTOR_SPECS = (
    DescriptorTargetSpec(
        name="hybridization",
        field_name="rdkit_node_hybridization",
        task_type="multiclass",
        num_outputs=9,
        num_classes=9,
    ),
    DescriptorTargetSpec(
        name="is_aromatic",
        field_name="rdkit_node_is_aromatic",
        task_type="binary",
        num_outputs=1,
    ),
    DescriptorTargetSpec(
        name="is_in_ring",
        field_name="rdkit_node_is_in_ring",
        task_type="binary",
        num_outputs=1,
    ),
    DescriptorTargetSpec(
        name="min_ring_size",
        field_name="rdkit_node_min_ring_size",
        task_type="multiclass",
        num_outputs=8,
        num_classes=8,
    ),
    DescriptorTargetSpec(
        name="total_degree",
        field_name="rdkit_node_total_degree",
        task_type="multiclass",
        num_outputs=8,
        num_classes=8,
    ),
    DescriptorTargetSpec(
        name="total_num_Hs",
        field_name="rdkit_node_total_num_Hs",
        task_type="multiclass",
        num_outputs=6,
        num_classes=6,
    ),
    DescriptorTargetSpec(
        name="total_valence",
        field_name="rdkit_node_total_valence",
        task_type="multiclass",
        num_outputs=8,
        num_classes=8,
    ),
    DescriptorTargetSpec(
        name="estate_type",
        field_name="rdkit_node_estate_type",
        task_type="multiclass",
        num_outputs=ESTATE_TYPE_NUM_CLASSES,
        num_classes=ESTATE_TYPE_NUM_CLASSES,
    ),
    DescriptorTargetSpec(
        name="chiral_tag",
        field_name="rdkit_node_chiral_tag",
        task_type="multiclass",
        num_outputs=9,
        num_classes=9,
    ),
    DescriptorTargetSpec(
        name="cip_code",
        field_name="rdkit_node_cip_code",
        task_type="multiclass",
        num_outputs=4,
        num_classes=4,
    ),
)

BOND_TARGET_SPECS = (
    BondTargetSpec(
        name="bond_existence",
        index_field=BOND_INDEX_FIELD,
        task_type="pair_binary",
    ),
    BondTargetSpec(
        name="bond_order",
        index_field=BOND_INDEX_FIELD,
        value_field=BOND_ORDER_FIELD,
        task_type="pair_multiclass",
        num_classes=BOND_ORDER_NUM_CLASSES,
    ),
)

NODE_MASK_FIELD = "rdkit_node_mask"
GRAPH_MASK_FIELD = "rdkit_graph_desc_mask"
GRAPH_FIELD = "rdkit_graph_desc"


def normalize_recipe_mode(mode: str) -> str:
    normalized = str(mode).strip().lower()
    if normalized not in {"clean", "geom", "topo", "both"}:
        raise ValueError(f"Unsupported recipe mode: {mode}")
    return normalized


def _format_recipe_level_token(level: float) -> str:
    raw = f"{float(level):.6f}".rstrip("0").rstrip(".")
    if not raw:
        raw = "0"
    return raw.replace("-", "m").replace(".", "p")


def canonical_recipe_name(mode: str, level: float) -> str:
    normalized_mode = normalize_recipe_mode(mode)
    return f"{normalized_mode}:{float(level):g}"


def recipe_cache_suffix(mode: str, level: float) -> str:
    normalized_mode = normalize_recipe_mode(mode)
    return f"recipe_{normalized_mode}_{_format_recipe_level_token(level)}"


def parse_graph_descriptor_name_list(values: str | Iterable[str] | None) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, str):
        raw_values = (values,)
    else:
        raw_values = tuple(values)

    names: list[str] = []
    for raw_value in raw_values:
        if raw_value is None:
            continue
        for token in re.split(r"[\s,;]+", str(raw_value).strip()):
            name = token.strip()
            if name:
                names.append(name)
    return tuple(names)


def normalize_graph_descriptor_names(selected_names: str | Iterable[str] | None) -> tuple[str, ...]:
    if selected_names is None:
        return GRAPH_DESCRIPTOR_NAMES

    requested = parse_graph_descriptor_name_list(selected_names)
    unknown = sorted(set(requested) - set(GRAPH_DESCRIPTOR_NAMES))
    if unknown:
        raise ValueError(
            "Unknown graph descriptor names: "
            + ", ".join(unknown)
            + ". Valid names are: "
            + ", ".join(GRAPH_DESCRIPTOR_NAMES)
        )

    requested_set = set(requested)
    return tuple(name for name in GRAPH_DESCRIPTOR_NAMES if name in requested_set)


def graph_descriptor_indices(names: str | Iterable[str] | None) -> tuple[int, ...]:
    normalized = normalize_graph_descriptor_names(names)
    return tuple(_GRAPH_DESCRIPTOR_INDEX[name] for name in normalized)


def resolve_graph_descriptor_selection(
    include: str | Iterable[str] | None = None,
    exclude: str | Iterable[str] | None = None,
) -> tuple[tuple[str, ...], tuple[int, ...]]:
    selected = GRAPH_DESCRIPTOR_NAMES if include is None else normalize_graph_descriptor_names(include)
    excluded = normalize_graph_descriptor_names(exclude or ())
    excluded_set = set(excluded)
    resolved = tuple(name for name in selected if name not in excluded_set)
    return resolved, graph_descriptor_indices(resolved)


def build_energy_output_layout(graph_descriptor_names: str | Iterable[str] | None = None) -> tuple[dict[str, slice], int]:
    selected_graph_descriptor_names = normalize_graph_descriptor_names(graph_descriptor_names)
    layout = {
        "energy": slice(0, 1),
        "graph_desc": slice(1, 1 + len(selected_graph_descriptor_names)),
    }
    return layout, 1 + len(selected_graph_descriptor_names)


def build_charge_output_layout() -> tuple[dict[str, slice], int]:
    layout = {"charge": slice(0, 1)}
    offset = 1
    for spec in CHARGE_DESCRIPTOR_SPECS:
        layout[spec.name] = slice(offset, offset + spec.num_outputs)
        offset += spec.num_outputs
    return layout, offset


def build_element_output_layout(n_atom_types: int) -> tuple[dict[str, slice], int]:
    layout = {"element": slice(0, n_atom_types)}
    offset = n_atom_types
    for spec in ELEMENT_DESCRIPTOR_SPECS:
        layout[spec.name] = slice(offset, offset + spec.num_outputs)
        offset += spec.num_outputs
    return layout, offset
