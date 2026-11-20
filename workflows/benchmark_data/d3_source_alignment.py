"""Map accepted source atoms into the unchanged legacy D3 wire and back."""
from rdkit import Chem
import numpy as np
from .downstream_science import geometry_descriptors as legacy_geometry_descriptors

ALIGNMENT_ERRORS = (
    "Stored SMILES/element atom-order alignment unavailable for requested 3D",
    "Source bondgraph differs from ordered SMILES graph for 3D",
)


def targeted_failure(conformer):
    return (conformer.get("D3") is None and
            any(message.startswith("D3_SOURCE_MAPPING_OR_PROPERTY_FAILED:")
                and any(reason in message for reason in ALIGNMENT_ERRORS)
                for message in conformer.get("D3_issues", [])))


def atom_permutation(smiles, source_mol):
    """Return legacy-index -> actual source-index via full graph isomorphism."""
    template = Chem.MolFromSmiles(smiles)
    if template is None:
        raise ValueError("Legacy SMILES graph cannot be reconstructed")
    legacy = Chem.AddHs(template)
    if (legacy.GetNumAtoms() != source_mol.GetNumAtoms()
            or legacy.GetNumBonds() != source_mol.GetNumBonds()):
        raise ValueError("Source and legacy full atom graphs differ in size")
    mapping = tuple(source_mol.GetSubstructMatch(legacy, useChirality=True))
    n = source_mol.GetNumAtoms()
    if len(mapping) != n or len(set(mapping)) != n:
        raise ValueError("No chirality-preserving full atom graph bijection")
    for new, old in enumerate(mapping):
        a, b = legacy.GetAtomWithIdx(new), source_mol.GetAtomWithIdx(old)
        signature = lambda atom: (atom.GetAtomicNum(), atom.GetIsotope(),
                                  atom.GetFormalCharge(), atom.GetIsAromatic(),
                                  atom.GetNumRadicalElectrons())
        if signature(a) != signature(b):
            raise ValueError("Atom identity differs across D3 permutation")
    inverse = {old: new for new, old in enumerate(mapping)}
    def bonds(mol, remap):
        return {(min(remap[b.GetBeginAtomIdx()], remap[b.GetEndAtomIdx()]),
                 max(remap[b.GetBeginAtomIdx()], remap[b.GetEndAtomIdx()]),
                 str(b.GetBondType()), b.GetIsAromatic()) for b in mol.GetBonds()}
    if bonds(source_mol, inverse) != bonds(legacy, dict(enumerate(range(n)))):
        raise ValueError("Full bond graph differs across D3 permutation")
    return legacy, mapping


def aligned_descriptors(smiles, source_mol, source_z, source_xyz, d20):
    """Evaluate ONLY D3 once; return atomic SASA in the original source order."""
    xyz = np.asarray(source_xyz, dtype=np.float64)
    z = np.asarray(source_z, dtype=np.int64)
    n = source_mol.GetNumAtoms()
    if xyz.shape != (n, 3) or z.shape != (n,):
        raise ValueError("Source D3 geometry/element axes differ")
    if z.tolist() != [atom.GetAtomicNum() for atom in source_mol.GetAtoms()]:
        raise ValueError("Source D3 elements do not match the actual source graph")
    legacy, mapping = atom_permutation(smiles, source_mol)
    indices = np.asarray(mapping, dtype=np.int64)
    d3, issues = legacy_geometry_descriptors(smiles, legacy, z[indices],
                                            xyz[indices], d20)
    result = dict(d3)
    if result.get("SASA_atom_A2") is not None:
        original = np.asarray(result["SASA_atom_A2"], dtype=np.float64)
        if original.shape != (n,):
            raise ValueError("Legacy atomic SASA axis differs from full source graph")
        restored = np.empty(n, dtype=np.float64)
        restored[indices] = original
        result["SASA_atom_A2"] = restored.tolist()
    return result, issues, list(mapping)
