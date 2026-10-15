"""Conservative CYP direction-component proof on ordered source-mol copies.

Changed representations support ordinary SINGLE UP/DOWN signs around fully
defined E/Z bonds only. CIS/TRANS remains supported by the exact-signature
path. The changed path requires whole-molecule legacy redecoding to preserve
all graph fields, so even unchanged CIS/TRANS elsewhere may conservatively
reject that path. Neither source directions nor atoms are rewritten. No
files or annotations are read.
"""
from __future__ import annotations

from rdkit import Chem, rdBase

from .identity import canonical_hash


DIRECTION_EQUIVALENCE_SCHEMA = "phase1_cyp_direction_equivalence_v1"
_SIGNS = {"ENDUPRIGHT": 1, "ENDDOWNRIGHT": -1}
_PARITY = {"STEREOZ": 1, "STEREOE": -1}
_VERIFIED_RING_RUNTIME = "2025.09.5"
_LEGACY_MIN_RING_SIZE = 8


class SomDirectionEquivalenceError(ValueError):
    """An ordered source pair lacks the conservative component proof."""


def _require(condition, message):
    if not condition:
        raise SomDirectionEquivalenceError(message)


def _hashes(signature):
    return {"ordered_signature_sha256": canonical_hash(signature),
            "ordered_graph_sha256": canonical_hash({key: signature[key]
                for key in ("atoms", "bonds", "stereo_groups")})}


def _decoded_copy(mol, raw, ordered_structure):
    """Regenerate stereo/CIP caches from directions, never from source coords."""
    decoded = Chem.Mol(mol)
    decoded.RemoveAllConformers()
    # Read only newly generated CIP ranks below. Caller-supplied/stale computed
    # properties cannot establish control-atom priority; no target is decoded.
    for atom in decoded.GetAtoms():
        for name in ("_CIPRank", "_CIPCode", "_ChiralityPossible"):
            if atom.HasProp(name):
                atom.ClearProp(name)
    with rdBase.BlockLogs():
        Chem.AssignStereochemistry(decoded, cleanIt=True, force=True,
                                   flagPossibleStereoCenters=True)
    signature = ordered_structure(decoded)
    for field in ("atoms", "bonds", "stereo_groups"):
        _require(signature[field] == raw[field],
                 "Clean legacy direction decoder changed ordered " + field)
    ranks = []
    for atom in decoded.GetAtoms():
        _require(atom.HasProp("_CIPRank"), "Clean legacy decoder did not generate CIP ranks")
        rank = atom.GetUnsignedProp("_CIPRank")
        _require(isinstance(rank, int) and not isinstance(rank, bool)
                 and 0 <= rank < decoded.GetNumAtoms(), "Invalid freshly decoded CIP rank")
        ranks.append(rank)
    return decoded, ranks, {**_hashes(signature), "stereo_signature_sha256": canonical_hash({
        "atom_chiral_tags": [row[6] for row in signature["atoms"]],
        "bond_stereo_and_controls": [[row[5], row[6]] for row in signature["bonds"]],
        "stereo_groups": signature["stereo_groups"]}),
        "fresh_cip_ranks": ranks, "raw_graph_fields_preserved": True,
        "conformers_removed_on_decoder_copy_only": True,
        "method": "legacy clean/force AssignStereochemistry; freshly generated CIP caches"}


def _neighbors(mol, bond, endpoint):
    return [other for other in mol.GetAtomWithIdx(endpoint).GetBonds()
            if other.GetIdx() != bond.GetIdx()]


def _nonstereogenic_proof(mol, bond, ranks):
    """Two narrow graph proofs; NONE alone never proves non-stereogenicity."""
    if str(bond.GetStereo()) != "STEREONONE" or tuple(bond.GetStereoAtoms()) or str(bond.GetBondDir()) != "NONE":
        return None
    for endpoint in (bond.GetBeginAtomIdx(), bond.GetEndAtomIdx()):
        neighbors = _neighbors(mol, bond, endpoint)
        if not neighbors:
            return {"reason": "endpoint_degree_one", "endpoint_atom_id": endpoint,
                    "other_substituent_atom_ids": []}
        if len(neighbors) == 2:
            ids = [other.GetOtherAtomIdx(endpoint) for other in neighbors]
            if ranks[ids[0]] == ranks[ids[1]]:
                return {"reason": "two_explicit_substituents_have_equal_fresh_legacy_cip_ranks",
                        "endpoint_atom_id": endpoint, "other_substituent_atom_ids": ids,
                        "fresh_legacy_cip_ranks": [ranks[index] for index in ids]}
    return None


def _legacy_ring_exclusion(mol, bond):
    """Current-version detection exclusion, not physical non-stereogenicity."""
    if (rdBase.rdkitVersion != _VERIFIED_RING_RUNTIME
            or Chem.GetUseLegacyStereoPerception() is not True
            or str(bond.GetBondType()) != "DOUBLE" or bond.GetIsAromatic()
            or str(bond.GetStereo()) != "STEREONONE" or tuple(bond.GetStereoAtoms())
            or str(bond.GetBondDir()) != "NONE"):
        return None
    # Presence-only structural uncertainty guard. Do not read any property
    # values, including SD properties or annotation fields. A zero-valued
    # marker also rejects conservatively instead of guessing its meaning.
    endpoints = (bond.GetBeginAtom(), bond.GetEndAtom())
    if (mol.HasProp("_UnknownStereo") or any(atom.HasProp("_UnknownStereo") for atom in endpoints)
            or any(other.HasProp("_UnknownStereo") for atom in endpoints for other in atom.GetBonds())):
        return None
    ring_copy = Chem.Mol(mol)
    # Chem.Mol inherits RingInfo: explicitly discard copied computed caches
    # before public graph ring perception. Fresh CIP ranks live elsewhere.
    ring_copy.ClearComputedProps(includeRings=True)
    Chem.GetSymmSSSR(ring_copy)
    ring_info = ring_copy.GetRingInfo()
    index = bond.GetIdx()
    count, minimum = ring_info.NumBondRings(index), ring_info.MinBondRingSize(index)
    if not (count > 0 and 3 <= minimum < _LEGACY_MIN_RING_SIZE):
        return None
    cycles = [list(cycle) for cycle in ring_info.BondRings() if index in cycle]
    _require(len(cycles) == count and min(map(len, cycles)) == minimum,
             "Fresh ring membership and minimum ring-size evidence disagree")
    proof = {"reason": "current_legacy_detection_exclusion",
             "scope": "current legacy ring detection only; no physical non-stereogenicity claim",
             "rdkit_version": rdBase.rdkitVersion, "use_legacy_stereo_perception": True,
             "method": "independent copy; ClearComputedProps(includeRings=True); Chem.GetSymmSSSR defaults",
             "source_ring_cache_used": False, "num_bond_rings": count,
             "minimum_bond_ring_size": minimum, "containing_ring_bond_cycles": cycles,
             "stereo_detection_minimum_ring_size": _LEGACY_MIN_RING_SIZE,
             "threshold_source": "RDKit Release_2025_09_5 Chirality.h: minRingSizeForDoubleBondStereo",
             "predicate_source": "RDKit Release_2025_09_5 Chirality.cpp: shouldDetectDoubleBondStereo"}
    proof["ring_evidence_sha256"] = canonical_hash(proof)
    return proof


def _endpoint_proof(mol, bond, endpoint, control, ranks):
    neighbors = _neighbors(mol, bond, endpoint)
    _require(1 <= len(neighbors) <= 2, "Unsupported E/Z endpoint substituent count")
    ids = [other.GetOtherAtomIdx(endpoint) for other in neighbors]
    _require(control in ids, "StereoAtoms are not the ordered opposite-end substituents")
    highest = max(ranks[index] for index in ids)
    _require(ranks[control] == highest and sum(ranks[index] == highest for index in ids) == 1,
             "E/Z StereoAtoms are not unique freshly decoded CIP controls")
    support, oriented = [], []
    control_bond = None
    for other in neighbors:
        direction = str(other.GetBondDir())
        _require(direction == "NONE" or direction in _SIGNS,
                 "Unsupported wedge or unknown direction at E/Z endpoint")
        if direction not in _SIGNS:
            continue
        _require(str(other.GetBondType()) == "SINGLE" and not other.GetIsAromatic(),
                 "E/Z signed support is not ordinary SINGLE")
        sign = _SIGNS[direction] * (1 if other.GetBeginAtomIdx() == endpoint else -1)
        support.append(other.GetIdx())
        oriented.append(sign)
        if other.GetOtherAtomIdx(endpoint) == control:
            control_bond = other.GetIdx(), sign
    _require(control_bond is not None, "E/Z CIP control lacks an explicit signed SINGLE bond")
    if len(oriented) == 2:
        _require(oriented[0] == -oriented[1], "Inconsistent signed branches at E/Z endpoint")
    return {"endpoint_atom_id": endpoint, "control_atom_id": control,
            "control_bond_id": control_bond[0], "control_oriented_sign": control_bond[1],
            "all_signed_support_bond_ids": support, "all_oriented_signs": oriented,
            "substituent_atom_ids": ids, "fresh_legacy_cip_ranks": [ranks[index] for index in ids]}


def _stereo_proof(mol, bond_id, ranks):
    bond = mol.GetBondWithIdx(bond_id)
    stereo = str(bond.GetStereo())
    _require(stereo in _PARITY and str(bond.GetBondType()) == "DOUBLE"
             and not bond.GetIsAromatic() and str(bond.GetBondDir()) == "NONE",
             "Changed components support fully defined ordinary E/Z only; CIS/TRANS is unsupported")
    controls = tuple(bond.GetStereoAtoms())
    _require(len(controls) == 2, "E/Z bond requires two explicit StereoAtoms")
    ends = bond.GetBeginAtomIdx(), bond.GetEndAtomIdx()
    proofs = [_endpoint_proof(mol, bond, end, control, ranks) for end, control in zip(ends, controls)]
    parity = proofs[0]["control_oriented_sign"] * proofs[1]["control_oriented_sign"]
    _require(parity == _PARITY[stereo], "Direction parity contradicts specified CIP-controlled E/Z")
    return {"double_bond_id": bond_id, "ordered_endpoint_atom_ids": list(ends),
            "stereo": stereo, "stereo_atom_ids": list(controls), "endpoint_proofs": proofs,
            "direction_parity": parity, "specified_stereo_parity": _PARITY[stereo]}


def _verify(candidate, author, ordered_structure):
    left, right = ordered_structure(candidate), ordered_structure(author)
    flags = {"use_legacy_stereo_perception": Chem.GetUseLegacyStereoPerception(),
             "allow_nontetrahedral_chirality": Chem.GetAllowNontetrahedralChirality()}
    receipt = {"schema_version": DIRECTION_EQUIVALENCE_SCHEMA, "state": "NOT_FROZEN",
               "formal_eligible": False, "author_version_reproduced": False,
               "annotation_semantics_verified": False, "labels_read_or_inferred": False,
               "rdkit_version": rdBase.rdkitVersion, "perception_flags": flags,
               "scope": "same ordered current-runtime graphs; changed E/Z components only",
               "candidate_raw": _hashes(left), "author_raw": _hashes(right),
               "original_molecules_preserved": True, "atom_or_bond_reordering": False,
               "direction_flags_rewritten": False, "all_other_ordered_fields_exact_match": True,
               "components_scope": "changed signed constraint components; unchanged signs remain exact and inventoried",
               "components": [], "decoded_copies": {"performed": False}}
    for field in ("atoms", "stereo_groups", "conformers"):
        _require(left[field] == right[field], "Ordered " + field + " differ")
    _require(len(left["bonds"]) == len(right["bonds"]), "Ordered bond count differs")
    changed = []
    signed = []
    for index, (a, b) in enumerate(zip(left["bonds"], right["bonds"])):
        _require(a[:-1] == b[:-1], "Non-direction ordered bond fields differ")
        if a[-1] in _SIGNS:
            signed.append(index)
        if a[-1] != b[-1]:
            _require(a[-1] in _SIGNS and b[-1] in _SIGNS and a[2] == "SINGLE" and not a[3],
                     "Direction support, wedge, or unsupported direction differs")
            changed.append(index)
    receipt.update(all_signed_bond_ids=signed, changed_bond_ids=changed,
                   candidate_raw_direction_flags=[row[-1] for row in left["bonds"]],
                   author_raw_direction_flags=[row[-1] for row in right["bonds"]],
                   all_signed_candidate_direction_flags=[left["bonds"][index][-1] for index in signed],
                   all_signed_author_direction_flags=[right["bonds"][index][-1] for index in signed],
                   all_signed_candidate_signs=[_SIGNS[left["bonds"][index][-1]] for index in signed],
                   all_signed_author_signs=[_SIGNS[right["bonds"][index][-1]] for index in signed],
                   ordered_direction_flags_exact_match=not changed,
                   ordered_signature_exact_match=left == right)
    if not changed:
        receipt["status"] = "EXACT_ORDERED_SIGNATURE"
        return receipt
    _require(flags["use_legacy_stereo_perception"] is True,
             "Changed direction-component proof requires recorded legacy perception")
    decoded_left, ranks_left, proof_left = _decoded_copy(candidate, left, ordered_structure)
    decoded_right, ranks_right, proof_right = _decoded_copy(author, right, ordered_structure)
    _require(proof_left["stereo_signature_sha256"] == proof_right["stereo_signature_sha256"],
             "Independent copy decoders disagree on ordered stereo semantics")
    receipt["decoded_copies"] = {"performed": True, "candidate": proof_left, "author": proof_right,
        "comparison_scope": "whole-molecule atoms/bonds/groups must remain literal; original conformers already matched"}
    # All signed flags are inventoried, including unchanged branches. Unsupported
    # signed bond types cannot become an unobserved boundary of a changed component.
    signed_set = set(signed)
    adjacency = {index: set() for index in signed}
    incidence = {index: set() for index in signed}
    doubles, excluded, ring_excluded = {}, {}, {}
    for bond in candidate.GetBonds():
        if str(bond.GetBondType()) != "DOUBLE":
            continue
        support = sorted({neighbor.GetIdx() for endpoint in (bond.GetBeginAtomIdx(), bond.GetEndAtomIdx())
                          for neighbor in _neighbors(candidate, bond, endpoint) if neighbor.GetIdx() in signed_set})
        if not support:
            continue
        index = bond.GetIdx()
        for single in support:
            incidence[single].add(index)
        non_left = _nonstereogenic_proof(decoded_left, decoded_left.GetBondWithIdx(index), ranks_left)
        non_right = _nonstereogenic_proof(decoded_right, decoded_right.GetBondWithIdx(index), ranks_right)
        if non_left is not None or non_right is not None:
            _require(non_left == non_right, "Both-copy non-stereogenic graph proofs disagree")
            excluded[index] = {"double_bond_id": index, "signed_neighbor_bond_ids": support,
                               "structural_nonstereogenic_proof": non_left}
            continue
        ring_left = _legacy_ring_exclusion(decoded_left, decoded_left.GetBondWithIdx(index))
        ring_right = _legacy_ring_exclusion(decoded_right, decoded_right.GetBondWithIdx(index))
        if ring_left is not None or ring_right is not None:
            _require(ring_left == ring_right, "Independent fresh ring exclusion proofs disagree")
            ring_excluded[index] = {"double_bond_id": index, "signed_neighbor_bond_ids": support,
                                    "current_legacy_detection_exclusion": ring_left}
            continue
        doubles[index] = support
        for single in support:
            adjacency[single].update(other for other in support if other != single)
    pending = set(signed)
    while pending:
        first = min(pending)
        component, stack = set(), [first]
        while stack:
            current = stack.pop()
            if current in component:
                continue
            component.add(current)
            stack.extend(adjacency[current] - component)
        pending.difference_update(component)
        if not component.intersection(changed):
            continue
        support = sorted(component)
        _require(len(support) >= 2, "Changed orphan direction has no fully defined stereo component")
        for index in support:
            row = left["bonds"][index]
            _require(row[2] == "SINGLE" and not row[3], "Unsupported signed bond in changed component")
        ratios = [_SIGNS[right["bonds"][index][-1]] * _SIGNS[left["bonds"][index][-1]] for index in support]
        _require(set(ratios) == {-1}, "Changed component is only partially or inconsistently inverted")
        incident = sorted(set().union(*(incidence[index] for index in support)))
        stereo_ids = [index for index in incident if index in doubles]
        _require(bool(stereo_ids), "Changed component has no controlling E/Z bond")
        constraints = []
        for index in stereo_ids:
            _require(set(doubles[index]).issubset(component), "Incomplete signed stereo-component support")
            a = _stereo_proof(decoded_left, index, ranks_left)
            b = _stereo_proof(decoded_right, index, ranks_right)
            _require(a["stereo_atom_ids"] == b["stereo_atom_ids"]
                     and a["direction_parity"] == b["direction_parity"], "Both E/Z parity proofs disagree")
            constraints.append({"double_bond_id": index, "candidate": a, "author": b})
        receipt["components"].append({"signed_bond_ids": support, "support_complete": True,
            "candidate_raw_direction_flags": [left["bonds"][index][-1] for index in support],
            "author_raw_direction_flags": [right["bonds"][index][-1] for index in support],
            "candidate_raw_signs": [_SIGNS[left["bonds"][index][-1]] for index in support],
            "author_raw_signs": [_SIGNS[right["bonds"][index][-1]] for index in support],
            "author_to_candidate_sign_ratios": ratios, "component_sign_ratio": -1,
            "stereo_constraints": constraints,
            "excluded_nonstereogenic_double_bonds": [excluded[index] for index in incident if index in excluded],
            "excluded_legacy_ring_double_bonds": [ring_excluded[index] for index in incident if index in ring_excluded]})
    _require(set(changed) == {index for component in receipt["components"] for index in component["signed_bond_ids"]},
             "Changed direction coverage is incomplete")
    receipt["status"] = "VERIFIED_DIRECTION_COMPONENT_INVERSION"
    return receipt


def verify_cyp_direction_equivalence(candidate, author) -> dict:
    """Return a JSON receipt or reject; never mutate either caller molecule.

    The mapping module owns the existing exact ordered structural reader. Its
    lazy import avoids a module cycle while preserving one signature contract.
    """
    _require(isinstance(candidate, Chem.Mol) and isinstance(author, Chem.Mol),
             "Both inputs must be actual ordered RDKit molecules")
    before = [mol.ToBinary(Chem.PropertyPickleOptions.AllProps) for mol in (candidate, author)]
    try:
        from .som_atom_mapping import _ordered_structure
        receipt = _verify(Chem.Mol(candidate), Chem.Mol(author), _ordered_structure)
        receipt["receipt_sha256"] = canonical_hash(receipt)
        return receipt
    except SomDirectionEquivalenceError:
        raise
    except Exception as exc:
        raise SomDirectionEquivalenceError("Ordered direction-component verification failed") from exc
    finally:
        _require(before == [mol.ToBinary(Chem.PropertyPickleOptions.AllProps) for mol in (candidate, author)],
                 "Direction proof mutated an original molecule")
