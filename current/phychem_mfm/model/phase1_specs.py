"""Phase 1 prediction targets without changing the archived LMDB schema."""

from __future__ import annotations

from ..data.descriptor_schema import (
    BOND_ORDER_CLASS_NAMES,
    CHARGE_DESCRIPTOR_SPECS,
    ELEMENT_DESCRIPTOR_SPECS,
)


PHASE1_GRAPH_DESCRIPTOR_NAMES = (
    "MolLogP", "MolMR", "TPSA", "LabuteASA", "ExactMolWt",
    "NumValenceElectrons", "HeavyAtomCount", "NumHeteroatoms",
    "NumHAcceptors", "NumHDonors", "FractionCSP3", "RingCount",
    "NumAromaticRings", "NumAliphaticRings", "NumSaturatedRings",
    "NumHeterocycles", "NumBridgeheadAtoms", "NumSpiroAtoms",
    "BertzCT", "HallKierAlpha", "Kappa1", "Kappa2", "Kappa3",
)
PHASE1_CHARGE_DESCRIPTOR_SPECS = tuple(
    spec for spec in CHARGE_DESCRIPTOR_SPECS
    if spec.name in {"donor", "acceptor", "estate_index"}
)
PHASE1_ELEMENT_DESCRIPTOR_SPECS = tuple(
    spec for spec in ELEMENT_DESCRIPTOR_SPECS
    if spec.name in {"is_aromatic", "is_in_ring", "min_ring_size"}
)
PHASE1_BOND_ORDER_CLASS_NAMES = BOND_ORDER_CLASS_NAMES[1:]
PHASE1_BOND_ORDER_NUM_CLASSES = len(PHASE1_BOND_ORDER_CLASS_NAMES)


def descriptor_specs_for_profile(profile: str):
    """Return model/loss node specifications, keeping the legacy default intact."""
    normalized = str(profile).strip().lower()
    if normalized == "legacy":
        return CHARGE_DESCRIPTOR_SPECS, ELEMENT_DESCRIPTOR_SPECS
    if normalized == "phase1":
        return PHASE1_CHARGE_DESCRIPTOR_SPECS, PHASE1_ELEMENT_DESCRIPTOR_SPECS
    raise ValueError(f"Unsupported head profile: {profile}")
