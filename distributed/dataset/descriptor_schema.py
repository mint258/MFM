from __future__ import annotations

from dataclasses import dataclass


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


@dataclass(frozen=True)
class DescriptorTargetSpec:
    name: str
    field_name: str
    task_type: str
    num_outputs: int
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

NODE_MASK_FIELD = "rdkit_node_mask"
GRAPH_MASK_FIELD = "rdkit_graph_desc_mask"
GRAPH_FIELD = "rdkit_graph_desc"


def build_energy_output_layout() -> tuple[dict[str, slice], int]:
    layout = {
        "energy": slice(0, 1),
        "graph_desc": slice(1, 1 + RDKIT_GRAPH_DESC_DIM),
    }
    return layout, 1 + RDKIT_GRAPH_DESC_DIM


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
