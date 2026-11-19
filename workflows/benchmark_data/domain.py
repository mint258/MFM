"""Benchmark applicability, using frozen v1 elements/charge and explicit B0 size rules."""
import ast
from rdkit import Chem, rdBase
from workflows.expansion.screen import WHITELIST

def assess(smiles, *, adme=False, blind=False, multiplicity=None):
    if rdBase.rdkitVersion != "2025.09.5":
        raise RuntimeError("Use the original RDKit 2025.09.5")
    result = {"original_smiles": smiles, "model_smiles": None,
              "model_atom_to_source": [], "salt_removed": False,
              "fragment_count": None, "heavy_atoms": None, "charge": None,
              "multiplicity_basis": "closed_shell_graph" if multiplicity in (None, "") else "declared",
              "reasons": []}
    params = Chem.SmilesParserParams()
    params.removeHs = False
    mol = Chem.MolFromSmiles(smiles, params) if isinstance(smiles, str) and smiles.strip() else None
    if mol is None:
        result["reasons"].append("PARSE_FAILED")
    else:
        maps = []
        fragments = Chem.GetMolFrags(mol, asMols=True, sanitizeFrags=True, fragsMolAtomMapping=maps)
        result["fragment_count"] = len(fragments)
        if adme and len(fragments) > 1:
            # First source fragment resolves an equal-heavy-atom tie deterministically.
            index = max(range(len(fragments)), key=lambda i: fragments[i].GetNumHeavyAtoms())
            mol, original_indices = fragments[index], list(maps[index])
            result["salt_removed"] = True
        else:
            original_indices = list(range(mol.GetNumAtoms()))
            # Outside ADME keep the supplied fragments; no extra domain veto.
        result["heavy_atoms"] = mol.GetNumHeavyAtoms()
        result["charge"] = Chem.GetFormalCharge(mol)
        if any(a.GetNumRadicalElectrons() for a in mol.GetAtoms()):
            result["reasons"].append("RADICAL")
        if multiplicity not in (None, ""):
            try:
                singlet = float(multiplicity) == 1
            except (ValueError, TypeError):
                singlet = False
            if not singlet:
                result["reasons"].append("NON_SINGLET_OR_UNKNOWN")
        if result["charge"] != 0:
            result["reasons"].append("NONZERO_CHARGE")
        if any(a.GetAtomicNum() not in WHITELIST for a in mol.GetAtoms()):
            result["reasons"].append("ELEMENT_OUTSIDE_V1")
        if not 3 <= result["heavy_atoms"] <= 200:
            result["reasons"].append("HEAVY_ATOMS_OUTSIDE_3_200")
        if sum(a.GetAtomicNum() for a in Chem.AddHs(mol).GetAtoms()) % 2:
            result["reasons"].append("ODD_ELECTRON_COUNT")
        result["model_smiles"] = Chem.MolToSmiles(mol, canonical=False, isomericSmiles=True)
        order = ast.literal_eval(mol.GetProp("_smilesAtomOutputOrder"))
        result["model_atom_to_source"] = [original_indices[i] for i in order]
    result["domain_eligible"] = not result["reasons"]
    result["retained"] = bool(blind or result["domain_eligible"])
    result["blind_fallback_required"] = bool(blind and not result["domain_eligible"])
    return result
