"""Isolated generic-ring order candidate; no change to frozen chemical rules.

Library evaluation only. It does not patch screen.py, screen a pool or apply a
repair to saved records. Every candidate report must retain repair_applied=false.
"""
from __future__ import annotations

import ast
import hashlib
import inspect
from pathlib import Path
import traceback

from . import screen
from .common import require

chemical_flags = screen.chemical_flags
rdkit_modules = screen.rdkit_modules
wp5_key = screen.wp5_key
Counter = screen.Counter
json = screen.json
OFFICIAL_MURCKO_BLOB = "8b456b1d3ae6fcdce6b1e0e13239ff382af9efe9"
OFFICIAL_MURCKO_URL = "https://github.com/rdkit/rdkit/blob/Release_2025_09_5/rdkit/Chem/Scaffolds/MurckoScaffold.py"
FROZEN_SCREEN_SHA = "bb31d57a4749f9ef9843dc075bc75f7c268cb781f60c7b4f0d77a121a73dcc88"


def cut_ring_fragments(mol):
    Chem, *_ = rdkit_modules()
    ring = Chem.RWMol(Chem.Mol(mol))
    remove = [b.GetIdx() for b in ring.GetBonds() if not b.IsInRing()]
    removed = []
    for idx in sorted(remove, reverse=True):
        bond = ring.GetBondWithIdx(idx)
        removed.append([bond.GetBeginAtomIdx(), bond.GetEndAtomIdx(), str(bond.GetBondType())])
        ring.RemoveBond(bond.GetBeginAtomIdx(), bond.GetEndAtomIdx())
    mappings = []
    fragments = Chem.GetMolFrags(ring.GetMol(), asMols=True, sanitizeFrags=False, fragsMolAtomMapping=mappings)
    return fragments, mappings, removed


def generic_ring_systems_candidate(mol):
    Chem, _, _, _, _, Murcko, _ = rdkit_modules()
    fragments, _, _ = cut_ring_fragments(mol)
    result = []
    for fragment in fragments:
        if fragment.GetNumBonds():
            # No sanitize of the cut, still-heteroaromatic fragment. Generic
            # atom/bond conversion happens first on an independent new molecule.
            generic = Murcko.MakeScaffoldGeneric(fragment)
            Chem.SanitizeMol(generic)
            result.append(Chem.MolToSmiles(generic, isomericSmiles=False))
    return result


def features_candidate(cid, smiles, ordinal):
    Chem, DataStructs, Descriptors, Lipinski, rdMolDescriptors, Murcko, Fingerprint = rdkit_modules()
    mol, flags = chemical_flags(smiles)
    reasons = [k for k, v in flags.items() if v]
    if reasons:
        return {"cid": cid, "ordinal": ordinal, "reasons": reasons}
    key = Chem.MolToInchiKey(mol)
    wp = wp5_key(key)
    counts = Counter(a.GetAtomicNum() for a in mol.GetAtoms() if a.GetAtomicNum() != 1)
    scaffold = Murcko.MakeScaffoldGeneric(Murcko.GetScaffoldForMol(mol))
    scaffold_key = Chem.MolToSmiles(scaffold, isomericSmiles=False)
    ring_systems = generic_ring_systems_candidate(mol)
    fp = Fingerprint.GetMorganGenerator(radius=2, fpSize=2048, includeChirality=False).GetFingerprint(mol)
    return {"cid": cid, "ordinal": ordinal, "reasons": [], "source_smiles": smiles,
            "isomeric_smiles": Chem.MolToSmiles(mol, isomericSmiles=True), "full_key": key, "wp5_key": wp,
            "heavy_atoms": sum(counts.values()), "elements": sorted(counts),
            "non_h_composition": json.dumps(sorted(counts.items()), separators=(",", ":")),
            "element_combination": ",".join(map(str, sorted(counts))),
            "isotopic_atoms": sum(a.GetIsotope() > 0 for a in mol.GetAtoms()),
            "molecular_weight_Da": Descriptors.MolWt(mol), "rings": rdMolDescriptors.CalcNumRings(mol),
            "aromatic_rings": rdMolDescriptors.CalcNumAromaticRings(mol),
            "rotatable_bonds": Lipinski.NumRotatableBonds(mol), "hbd": Lipinski.NumHDonors(mol),
            "hba": Lipinski.NumHAcceptors(mol), "tpsa_A2": rdMolDescriptors.CalcTPSA(mol),
            "logp": Descriptors.MolLogP(mol),
            "stereocenters": len(Chem.FindMolChiralCenters(mol, includeUnassigned=True)),
            "generic_murcko": scaffold_key, "generic_ring_systems": sorted(ring_systems),
            "ecfp4_2048_hex": DataStructs.BitVectToBinaryText(fp).hex()}


def _atom_snapshot(atom):
    value = {"atomic_number": atom.GetAtomicNum(), "degree": atom.GetDegree(), "aromatic": atom.GetIsAromatic(),
             "formal_charge": atom.GetFormalCharge(), "isotope": atom.GetIsotope(),
             "explicit_h_count": atom.GetNumExplicitHs(), "no_implicit": atom.GetNoImplicit()}
    try:
        value["cached_implicit_h_count"] = atom.GetNumImplicitHs()
    except Exception as exc:
        value["cached_implicit_h_read_error"] = type(exc).__name__ + ": " + str(exc)
    return value


def evaluate_fragment_orders(mol):
    Chem, _, _, _, _, Murcko, _ = rdkit_modules()
    fragments, mappings, removed = cut_ring_fragments(mol)
    rows = []
    for i, (fragment, original_ids) in enumerate(zip(fragments, mappings)):
        if not fragment.GetNumBonds():
            continue
        row = {"fragment_index": i, "original_atom_indices": list(original_ids),
               "before_cut_original_atoms": [_atom_snapshot(mol.GetAtomWithIdx(j)) for j in original_ids],
               "cut_fragment_atoms_before_any_sanitize": [_atom_snapshot(a) for a in fragment.GetAtoms()],
               "removed_non_ring_bonds": [b for b in removed if b[0] in original_ids or b[1] in original_ids]}
        # Failing SanitizeMol can mutate its input. Never recycle that molecule
        # into the candidate route or a subsequent fragment-order comparison.
        legacy, fresh = Chem.Mol(fragment), Chem.Mol(fragment)
        try:
            Chem.SanitizeMol(legacy)
            row["legacy"] = {"status": "PASS", "generic_smiles": Chem.MolToSmiles(Murcko.MakeScaffoldGeneric(legacy), isomericSmiles=False)}
        except Exception as exc:
            row["legacy"] = {"status": "ERROR", "exception_type": type(exc).__name__, "message": str(exc),
                             "exact_traceback": traceback.format_exc()}
        try:
            generic = Murcko.MakeScaffoldGeneric(fresh)
            Chem.SanitizeMol(generic)
            heavy = [a.GetIdx() for a in fresh.GetAtoms() if a.GetAtomicNum() != 1]
            position = {index: j for j, index in enumerate(heavy)}
            edges = sorted(sorted([position[b.GetBeginAtomIdx()], position[b.GetEndAtomIdx()]]) for b in fresh.GetBonds()
                           if b.GetBeginAtomIdx() in position and b.GetEndAtomIdx() in position)
            actual_edges = sorted(sorted([b.GetBeginAtomIdx(), b.GetEndAtomIdx()]) for b in generic.GetBonds())
            topology_ok = (generic.GetNumAtoms() == len(heavy) and edges == actual_edges and
                           all(a.GetAtomicNum() == 6 and not a.GetIsAromatic() for a in generic.GetAtoms()) and
                           all(b.GetBondType() == Chem.BondType.SINGLE and not b.GetIsAromatic() for b in generic.GetBonds()))
            require(topology_ok, "Candidate generic conversion changed the retained heavy-atom adjacency")
            row["candidate"] = {"status": "PASS", "generic_smiles": Chem.MolToSmiles(generic, isomericSmiles=False),
                                 "retained_heavy_atom_adjacency_equal": True}
        except Exception as exc:
            row["candidate"] = {"status": "ERROR", "exception_type": type(exc).__name__, "message": str(exc),
                                "exact_traceback": traceback.format_exc()}
        rows.append(row)
    return rows


def compare_pass_fields(old, candidate):
    keys = sorted(set(old) | set(candidate))
    differences = {name: {"old": old.get(name), "candidate": candidate.get(name)}
                   for name in keys if name not in old or name not in candidate or old[name] != candidate[name]}
    return {"schema_fields_equal": set(old) == set(candidate), "all_fields_exactly_equal": not differences,
            "non_ring_fields_exactly_equal": not any(k != "generic_ring_systems" for k in differences),
            "field_differences": differences}


def compare_to_actual_trace(candidate, case):
    stages = {row["stage"]: row for row in case["stages"]}
    mapping = {"full_key": "identity.full_inchikey", "wp5_key": "identity.wp5_key",
               "generic_murcko": "scaffold.MolToSmiles", "ecfp4_2048_hex": "independent.fingerprint.ecfp4_2048"}
    expected = {"cid": case["cid"], "ordinal": case["ordinal"], "source_smiles": case["smiles"], "reasons": []}
    for field, stage in mapping.items():
        require(stages[stage]["status"] == "PASS", "Original trace lacks an observed comparison field")
        expected[field] = stages[stage]["result"]
    counts = stages["identity.non_h_element_counts"]["result"]
    expected.update(heavy_atoms=sum(count for _, count in counts), elements=sorted(z for z, _ in counts),
                    non_h_composition=json.dumps(sorted(counts), separators=(",", ":")),
                    element_combination=",".join(str(z) for z, _ in sorted(counts)))
    prefix = "independent.original_molecule."
    for stage, row in stages.items():
        if stage.startswith(prefix):
            require(row["status"] == "PASS", "Original non-ring descriptor trace failed")
            expected[stage[len(prefix):]] = row["result"]
    differences = {name: {"actual_trace": value, "candidate": candidate.get(name)}
                   for name, value in expected.items() if candidate.get(name) != value}
    return {"observed_comparison_fields": sorted(expected), "all_observed_non_ring_fields_exactly_equal": not differences,
            "field_differences": differences, "not_directly_observed_in_original_trace": ["isotopic_atoms"],
            "isotopic_atoms_computation_covered_by_source_AST_proof": True}


def _normalized_feature_function(path, name, candidate):
    raw = Path(path).read_bytes()
    require(len(raw) <= 2 * 1024 ** 2, "Small feature source required")
    tree = ast.parse(raw)
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name)
    function.name = "_feature_body_"
    def assigned(node, target):
        return isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == target for t in node.targets)
    start = next(i for i, node in enumerate(function.body) if assigned(node, "ring_systems" if candidate else "ring"))
    end = next(i for i, node in enumerate(function.body) if assigned(node, "fp"))
    require((end - start == 1) if candidate else (end - start == 5), "Unexpected ring-block source shape")
    if candidate:
        value = function.body[start].value
        require(isinstance(value, ast.Call) and isinstance(value.func, ast.Name) and value.func.id == "generic_ring_systems_candidate",
                "Unexpected candidate replacement outside the generic-ring helper")
    marker = ast.Assign(targets=[ast.Name(id="ring_systems", ctx=ast.Store())], value=ast.Constant(value="ONLY_RING_BLOCK"))
    function.body[start:end] = [marker]
    return ast.dump(function, include_attributes=False)


def source_scope_proof():
    old = Path(screen.__file__)
    require(hashlib.sha256(old.read_bytes()).hexdigest() == FROZEN_SCREEN_SHA, "Frozen screen.py bytes changed")
    left = _normalized_feature_function(old, "features", False)
    right = _normalized_feature_function(__file__, "features_candidate", True)
    require(left == right and chemical_flags is screen.chemical_flags and rdkit_modules is screen.rdkit_modules and
            wp5_key is screen.wp5_key, "Change extends beyond the ring block or uses altered X/identity functions")
    return {"status": "ONLY_GENERIC_RING_BLOCK_DIFFERS_NON_RING_AST_IDENTICAL", "frozen_screen_sha256": FROZEN_SCREEN_SHA,
            "non_ring_normalized_ast_sha256": hashlib.sha256(left.encode()).hexdigest(),
            "chemical_function_object_identical": True, "new_chemical_function_defined": False,
            "repair_applied": False, "pool_modified": False}


def installed_murcko_source_proof():
    _, _, _, _, _, Murcko, _ = rdkit_modules()
    path = Path(inspect.getsourcefile(Murcko.MakeScaffoldGeneric))
    raw = path.read_bytes()
    require(len(raw) <= 2 * 1024 ** 2, "Installed scaffold source must be small")
    blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
    return {"installed_source": {"path": str(path), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()},
            "installed_git_blob_sha1": blob, "official_release_tag": "Release_2025_09_5",
            "official_git_blob_sha1": OFFICIAL_MURCKO_BLOB, "official_url": OFFICIAL_MURCKO_URL,
            "installed_bytes_match_official_tag": blob == OFFICIAL_MURCKO_BLOB}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-source-only", action="store_true", required=True)
    parser.parse_args()
    print(json.dumps(source_scope_proof()))
