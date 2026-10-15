"""Synthetic ordered-structure proofs; no source files, annotations or targets.

Fixtures use RDKit's public direction generator/decoder as an independent
oracle. No production constraint helpers construct their expected answers.
"""
from __future__ import annotations

import builtins
import json
import random

import numpy as np
import pytest
from rdkit import Chem, rdBase
import torch

from phychem_mfm.phase1.identity import canonical_hash
from phychem_mfm.phase1.som_direction_equivalence import (
    SomDirectionEquivalenceError,
    verify_cyp_direction_equivalence,
)


SIGNED = (Chem.BondDir.ENDUPRIGHT, Chem.BondDir.ENDDOWNRIGHT)
EZ = (Chem.BondStereo.STEREOE, Chem.BondStereo.STEREOZ)


@pytest.fixture(autouse=True)
def legacy_perception():
    previous = Chem.GetUseLegacyStereoPerception()
    Chem.SetUseLegacyStereoPerception(True)
    try:
        yield
    finally:
        Chem.SetUseLegacyStereoPerception(previous)


def binary(mol):
    return mol.ToBinary(Chem.PropertyPickleOptions.AllProps)


def signed_ids(mol):
    return tuple(b.GetIdx() for b in mol.GetBonds() if b.GetBondDir() in SIGNED)


def double_bonds(mol):
    return tuple(b for b in mol.GetBonds() if b.GetBondType() == Chem.BondType.DOUBLE)


def stereo_signature(mol):
    return (
        tuple(str(a.GetChiralTag()) for a in mol.GetAtoms()),
        tuple((b.GetIdx(), str(b.GetStereo()), tuple(b.GetStereoAtoms()))
              for b in double_bonds(mol)),
    )


def decoded_signature(mol):
    copied = Chem.Mol(mol)
    copied.RemoveAllConformers()
    Chem.AssignStereochemistry(copied, cleanIt=True, force=True)
    return stereo_signature(copied)


def molecule(smiles="F/C=C/F", *, coordinates=False):
    mol = Chem.MolFromSmiles(smiles)
    assert mol is not None
    # Also sign secondary substituents, so branch coverage is not diff-only.
    Chem.SetDoubleBondNeighborDirections(mol)
    Chem.AssignStereochemistry(mol, cleanIt=True, force=True)
    assert signed_ids(mol), "Fixture must actually contain directional support"
    if coordinates:
        conf = Chem.Conformer(mol.GetNumAtoms())
        conf.Set3D(True)
        for index in range(mol.GetNumAtoms()):
            conf.SetAtomPosition(index, (float(index), float(index % 3), .25))
        mol.AddConformer(conf)
    return mol


def inverted(mol, ids=None):
    result = Chem.Mol(mol)
    selected = signed_ids(mol) if ids is None else tuple(ids)
    for index in selected:
        bond = result.GetBondWithIdx(index)
        assert bond.GetBondDir() in SIGNED
        bond.SetBondDir(SIGNED[1] if bond.GetBondDir() == SIGNED[0] else SIGNED[0])
    return result


def accept(candidate, author, *, redecoded=True):
    before = binary(candidate), binary(author)
    receipt = verify_cyp_direction_equivalence(candidate, author)
    assert (binary(candidate), binary(author)) == before
    assert receipt["schema_version"] == "phase1_cyp_direction_equivalence_v1"
    assert json.loads(json.dumps(receipt, allow_nan=False)) == receipt
    content = dict(receipt)
    digest = content.pop("receipt_sha256")
    assert digest == canonical_hash(content)
    assert receipt["state"] == "NOT_FROZEN" and receipt["formal_eligible"] is False
    assert receipt["author_version_reproduced"] is False
    assert receipt["annotation_semantics_verified"] is receipt["labels_read_or_inferred"] is False
    assert receipt["original_molecules_preserved"] is True
    assert receipt["atom_or_bond_reordering"] is receipt["direction_flags_rewritten"] is False
    if redecoded:
        # Equal cached enums alone cannot establish the result.
        assert decoded_signature(candidate) == stereo_signature(candidate)
        assert decoded_signature(author) == stereo_signature(author)
        assert stereo_signature(candidate) == stereo_signature(author)
    return receipt


def reject(candidate, author):
    before = binary(candidate), binary(author)
    with pytest.raises(SomDirectionEquivalenceError):
        verify_cyp_direction_equivalence(candidate, author)
    assert (binary(candidate), binary(author)) == before


@pytest.mark.parametrize("smiles", ["F/C=C/F", "F/C=C\\F", "C/C=C/C=C/C"])
def test_complete_component_inversion_is_accepted_and_redecodes_exact_stereo(smiles):
    candidate = molecule(smiles)
    author = inverted(candidate)
    assert all(b.GetStereo() in EZ for b in double_bonds(candidate))
    assert decoded_signature(candidate) == decoded_signature(author)
    receipt = accept(candidate, author)
    assert receipt["ordered_direction_flags_exact_match"] is False
    assert receipt["all_other_ordered_fields_exact_match"] is True
    assert sorted(receipt["changed_bond_ids"]) == list(signed_ids(candidate))
    assert sorted(receipt["all_signed_bond_ids"]) == list(signed_ids(candidate))
    assert receipt["status"] == "VERIFIED_DIRECTION_COMPONENT_INVERSION"
    assert receipt["decoded_copies"]["performed"] is True
    assert len(receipt["components"]) == 1
    component = receipt["components"][0]
    assert component["signed_bond_ids"] == list(signed_ids(candidate))
    assert component["support_complete"] is True
    assert component["author_to_candidate_sign_ratios"] == [-1] * len(signed_ids(candidate))
    assert component["candidate_raw_direction_flags"] == [
        str(candidate.GetBondWithIdx(i).GetBondDir()) for i in signed_ids(candidate)]
    assert component["author_raw_direction_flags"] == [
        str(author.GetBondWithIdx(i).GetBondDir()) for i in signed_ids(author)]
    assert [proof["double_bond_id"] for proof in component["stereo_constraints"]] == [
        bond.GetIdx() for bond in double_bonds(candidate)]


def test_four_signed_branches_are_all_in_the_constraint_component():
    candidate = molecule("F/C(Cl)=C(/Br)I")
    assert len(signed_ids(candidate)) == 4
    accept(candidate, inverted(candidate))
    # The controlling pair is inverted but an extra support branch is not.
    double = double_bonds(candidate)[0]
    controls = tuple(candidate.GetBondBetweenAtoms(endpoint, ref).GetIdx()
                     for endpoint, ref in zip(
                         (double.GetBeginAtomIdx(), double.GetEndAtomIdx()),
                         double.GetStereoAtoms()))
    assert len(set(controls)) == 2
    reject(candidate, inverted(candidate, controls))
    reject(candidate, inverted(candidate, signed_ids(candidate)[:-1]))


@pytest.mark.parametrize("selection", [(0,), (1,), (0, 1)])
def test_proper_subsets_of_one_conjugated_component_are_rejected(selection):
    candidate = molecule("C/C=C/C=C/C")
    ids = signed_ids(candidate)
    assert len(ids) == 3
    reject(candidate, inverted(candidate, (ids[i] for i in selection)))


def test_isolated_changed_sign_is_not_a_stereo_proof():
    candidate = Chem.MolFromSmiles("CC")
    candidate.GetBondWithIdx(0).SetBondDir(Chem.BondDir.ENDUPRIGHT)
    reject(candidate, inverted(candidate))


def test_independent_components_can_have_different_constant_ratios():
    candidate = molecule("F/C=C/F.Cl/C=C/Br")
    fragments = Chem.GetMolFrags(candidate)
    first = set(fragments[0])
    ids = tuple(b.GetIdx() for b in candidate.GetBonds()
                if b.GetBondDir() in SIGNED and b.GetBeginAtomIdx() in first)
    assert len(ids) == 2 and len(signed_ids(candidate)) == 4
    receipt = accept(candidate, inverted(candidate, ids))
    assert sorted(receipt["changed_bond_ids"]) == list(ids)
    assert sorted(receipt["all_signed_bond_ids"]) == list(signed_ids(candidate))
    assert len(receipt["components"]) == 1
    assert receipt["components"][0]["signed_bond_ids"] == list(ids)


def test_unchanged_valid_component_does_not_cover_a_changed_orphan():
    candidate = molecule("F/C=C/F.CC")
    orphan = next(b for b in candidate.GetBonds()
                  if b.GetBeginAtomIdx() >= 4 and b.GetBondType() == Chem.BondType.SINGLE)
    orphan.SetBondDir(Chem.BondDir.ENDUPRIGHT)
    reject(candidate, inverted(candidate, (orphan.GetIdx(),)))


def reverse_support_endpoints(mol, reverse_ids):
    """Same ordered graph for both sides; change fixture endpoint conventions."""
    reverse_ids = set(reverse_ids)
    rw = Chem.RWMol()
    for atom in mol.GetAtoms():
        rw.AddAtom(Chem.Atom(atom))
    for bond in mol.GetBonds():
        begin, end = bond.GetBeginAtomIdx(), bond.GetEndAtomIdx()
        if bond.GetIdx() in reverse_ids:
            begin, end = end, begin
        rw.AddBond(begin, end, bond.GetBondType())
    result = rw.GetMol()
    for old in mol.GetBonds():
        new = result.GetBondWithIdx(old.GetIdx())
        new.SetIsAromatic(old.GetIsAromatic())
        new.SetIsConjugated(old.GetIsConjugated())
        direction = old.GetBondDir()
        if old.GetIdx() in reverse_ids:
            assert direction in SIGNED
            direction = SIGNED[1] if direction == SIGNED[0] else SIGNED[0]
        new.SetBondDir(direction)
        refs = tuple(old.GetStereoAtoms())
        if refs:
            new.SetStereoAtoms(*refs)
        new.SetStereo(old.GetStereo())
    Chem.SanitizeMol(result)
    assert decoded_signature(result) == stereo_signature(mol)
    return result


@pytest.mark.parametrize("selection", [(0,), (1,), (0, 1)])
def test_local_signs_are_corrected_for_reversed_single_bond_endpoints(selection):
    original = molecule()
    ids = signed_ids(original)
    candidate = reverse_support_endpoints(original, (ids[i] for i in selection))
    accept(candidate, inverted(candidate))


def test_endpoint_orientation_difference_between_molecules_is_not_gauge():
    candidate = molecule()
    changed = reverse_support_endpoints(candidate, signed_ids(candidate))
    reject(candidate, changed)


@pytest.mark.parametrize("enum", [Chem.BondStereo.STEREONONE, Chem.BondStereo.STEREOANY])
def test_cached_undefined_or_ambiguous_double_stereo_cannot_be_repaired(enum):
    candidate = molecule()
    double_bonds(candidate)[0].SetStereo(enum)
    reject(candidate, inverted(candidate))


def test_equal_but_contradictory_cached_ez_is_rejected_on_both_sides():
    candidate = molecule()
    double = double_bonds(candidate)[0]
    original = double.GetStereo()
    double.SetStereo(Chem.BondStereo.STEREOZ if original == Chem.BondStereo.STEREOE
                     else Chem.BondStereo.STEREOE)
    assert decoded_signature(candidate) != stereo_signature(candidate)
    reject(candidate, inverted(candidate))


def test_one_sided_partial_flip_keeps_cached_ez_but_redecodes_differently():
    candidate = molecule()
    author = inverted(candidate, signed_ids(candidate)[:1])
    assert stereo_signature(candidate) == stereo_signature(author)
    assert decoded_signature(author) != stereo_signature(author)
    reject(candidate, author)


@pytest.mark.parametrize("which_end", [0, 1, 2])
def test_ez_reference_atoms_must_be_the_fresh_cip_controlling_pair(which_end):
    candidate = molecule("F/C(Cl)=C(/Br)I")
    double = double_bonds(candidate)[0]
    endpoints = (double.GetBeginAtomIdx(), double.GetEndAtomIdx())
    refs = list(double.GetStereoAtoms())
    for end in range(2):
        if which_end in (end, 2):
            alternatives = [a.GetIdx() for a in candidate.GetAtomWithIdx(endpoints[end]).GetNeighbors()
                            if a.GetIdx() not in endpoints and a.GetIdx() != refs[end]]
            assert len(alternatives) == 1
            refs[end] = alternatives[0]
    double.SetStereoAtoms(*refs)
    assert decoded_signature(candidate) != stereo_signature(candidate)
    reject(candidate, inverted(candidate))


def test_high_cip_control_requires_its_own_signed_bond_not_implicit_substitution():
    candidate = molecule("F/C(Cl)=C(/Br)I")
    double = double_bonds(candidate)[0]
    bond = candidate.GetBondBetweenAtoms(double.GetBeginAtomIdx(), double.GetStereoAtoms()[0])
    bond.SetBondDir(Chem.BondDir.NONE)
    # Public legacy decoding can infer the omitted control from the other branch.
    assert decoded_signature(candidate) == stereo_signature(candidate)
    reject(candidate, inverted(candidate))


def test_same_end_signed_substituents_cannot_have_equal_local_directions():
    candidate = molecule("F/C(Cl)=C(/Br)I")
    double = double_bonds(candidate)[0]
    endpoint = double.GetBeginAtomIdx()
    singles = [b for b in candidate.GetAtomWithIdx(endpoint).GetBonds()
               if b.GetBondType() == Chem.BondType.SINGLE]
    assert len(singles) == 2
    def local(bond):
        sign = 1 if bond.GetBondDir() == SIGNED[0] else -1
        return sign if bond.GetBeginAtomIdx() == endpoint else -sign
    assert local(singles[0]) == -local(singles[1])
    singles[0].SetBondDir(SIGNED[1] if singles[0].GetBondDir() == SIGNED[0] else SIGNED[0])
    assert local(singles[0]) == local(singles[1])
    reject(candidate, inverted(candidate))


@pytest.mark.parametrize("enum", [Chem.BondStereo.STEREOCIS, Chem.BondStereo.STEREOTRANS])
def test_changed_cis_trans_is_explicitly_unsupported_but_exact_path_is_preserved(enum):
    candidate = molecule("F/C(Cl)=C(/Br)I")
    double = double_bonds(candidate)[0]
    # Select the lower-ranked substituent only on the first end. A literal
    # CIS=Z or TRANS=E shortcut therefore cannot represent this reference pair.
    refs = list(double.GetStereoAtoms())
    refs[0] = next(a.GetIdx() for a in double.GetBeginAtom().GetNeighbors()
                   if a.GetIdx() not in (double.GetEndAtomIdx(), refs[0]))
    double.SetStereoAtoms(*refs)
    double.SetStereo(enum)
    assert decoded_signature(candidate) != stereo_signature(candidate)
    accept(candidate, Chem.Mol(candidate), redecoded=False)
    reject(candidate, inverted(candidate))


@pytest.mark.parametrize("ambiguous", [False, True])
def test_a_signed_bridge_touching_another_unproved_double_is_rejected(ambiguous):
    candidate = molecule("C/C=C/C=CC")
    doubles = double_bonds(candidate)
    assert doubles[0].GetStereo() in EZ
    assert doubles[1].GetStereo() == Chem.BondStereo.STEREONONE
    if ambiguous:
        doubles[1].SetStereo(Chem.BondStereo.STEREOANY)
    reject(candidate, inverted(candidate))


@pytest.mark.parametrize("smiles,reason", [
    ("C/C=C/C=O", "endpoint_degree_one"),
    ("C/C=C/C=C(F)F", "two_explicit_substituents_have_equal_fresh_legacy_cip_ranks"),
])
def test_structurally_proven_noncandidate_double_does_not_break_defined_component(smiles, reason):
    candidate = molecule(smiles)
    assert double_bonds(candidate)[0].GetStereo() in EZ
    assert double_bonds(candidate)[1].GetStereo() == Chem.BondStereo.STEREONONE
    receipt = accept(candidate, inverted(candidate))
    excluded = receipt["components"][0]["excluded_nonstereogenic_double_bonds"]
    assert len(excluded) == 1
    assert excluded[0]["double_bond_id"] == double_bonds(candidate)[1].GetIdx()
    assert excluded[0]["structural_nonstereogenic_proof"]["reason"] == reason


def test_any_is_not_a_noncandidate_proof_even_for_terminal_carbonyl():
    candidate = molecule("C/C=C/C=O")
    double_bonds(candidate)[1].SetStereo(Chem.BondStereo.STEREOANY)
    reject(candidate, inverted(candidate))


def small_ring_pair_fixture(size):
    """A ring alkene shares signed support with a defined external E/Z bond."""
    candidate = molecule("C1(/C=C/F)=" + "C" * (size - 1) + "1")
    ring_double = next(b for b in double_bonds(candidate) if b.IsInRing())
    external_double = next(b for b in double_bonds(candidate) if not b.IsInRing())
    assert ring_double.GetStereo() == Chem.BondStereo.STEREONONE
    assert tuple(ring_double.GetStereoAtoms()) == ()
    assert ring_double.GetBondDir() == Chem.BondDir.NONE
    assert external_double.GetStereo() in EZ
    assert len(signed_ids(candidate)) == 2
    copied = Chem.Mol(candidate)
    Chem.GetSymmSSSR(copied)
    actual_min = min(len(ring) for ring in copied.GetRingInfo().BondRings()
                     if ring_double.GetIdx() in ring)
    assert actual_min == size
    # Check the actual incidence, not just the presence of a small ring elsewhere.
    adjacent_signed = {b.GetIdx() for endpoint in
                       (ring_double.GetBeginAtom(), ring_double.GetEndAtom())
                       for b in endpoint.GetBonds() if b.GetBondDir() in SIGNED}
    assert adjacent_signed.intersection(signed_ids(candidate))
    candidate.SetProp("synthetic_ring_marker", "preserve; not an annotation")
    ring_double.SetProp("synthetic_bond_marker", "keep")
    return candidate, ring_double


def assert_legacy_ring_receipt(receipt, ring_double, size):
    assert receipt["decoded_copies"]["performed"] is True
    assert receipt["perception_flags"]["use_legacy_stereo_perception"] is True
    component = receipt["components"][0]
    assert component["excluded_nonstereogenic_double_bonds"] == []
    excluded = component["excluded_legacy_ring_double_bonds"]
    assert len(excluded) == 1 and excluded[0]["double_bond_id"] == ring_double.GetIdx()
    proof = excluded[0]["current_legacy_detection_exclusion"]
    assert proof["reason"] == "current_legacy_detection_exclusion"
    assert proof["rdkit_version"] == "2025.09.5"
    assert proof["use_legacy_stereo_perception"] is True
    assert proof["source_ring_cache_used"] is False
    assert proof["num_bond_rings"] == 1
    assert proof["minimum_bond_ring_size"] == size
    assert proof["stereo_detection_minimum_ring_size"] == 8
    assert proof["method"] == (
        "independent copy; ClearComputedProps(includeRings=True); Chem.GetSymmSSSR defaults")
    cycles = proof["containing_ring_bond_cycles"]
    assert len(cycles) == 1 and len(cycles[0]) == size
    assert ring_double.GetIdx() in cycles[0]
    assert "no physical non-stereogenicity claim" in proof["scope"]
    content = dict(proof)
    assert content.pop("ring_evidence_sha256") == canonical_hash(content)


@pytest.mark.parametrize("size", [6, 7])
def test_legacy_small_ring_exclusion_allows_complete_external_component_inversion(size):
    candidate, ring_double = small_ring_pair_fixture(size)
    author = inverted(candidate)
    receipt = accept(candidate, author)
    assert len(receipt["components"]) == 1
    component = receipt["components"][0]
    assert component["signed_bond_ids"] == list(signed_ids(candidate))
    assert len(component["stereo_constraints"]) == 1
    assert_legacy_ring_receipt(receipt, ring_double, size)


@pytest.mark.parametrize("size", [6, 7])
def test_small_ring_exclusion_does_not_legalize_partial_external_component_inversion(size):
    candidate, _ = small_ring_pair_fixture(size)
    author = inverted(candidate, signed_ids(candidate)[:1])
    assert decoded_signature(author) != stereo_signature(author)
    reject(candidate, author)


def test_eight_membered_ring_none_is_not_a_small_ring_exclusion():
    candidate, _ = small_ring_pair_fixture(8)
    reject(candidate, inverted(candidate))


def test_small_ring_proof_reperceives_ring_info_when_caller_cache_is_absent():
    candidate, ring_double = small_ring_pair_fixture(6)
    candidate.ClearComputedProps(includeRings=True)
    author = inverted(candidate)
    # Independently initialize rings on diagnostic copies only. The originals
    # keep their absent ring/computed caches throughout the production call.
    for mol in (candidate, author):
        copied = Chem.Mol(mol)
        Chem.GetSymmSSSR(copied)
        assert decoded_signature(copied) == stereo_signature(mol)
    receipt = accept(candidate, author, redecoded=False)
    assert_legacy_ring_receipt(receipt, ring_double, 6)


@pytest.mark.parametrize("damage", ["any", "unknown_direction", "either_double",
                                    "explicit_reference_atoms"])
def test_small_ring_exclusion_requires_none_empty_controls_and_none_direction(damage):
    candidate, ring_double = small_ring_pair_fixture(6)
    if damage == "any":
        ring_double.SetStereo(Chem.BondStereo.STEREOANY)
    elif damage == "unknown_direction":
        ring_double.SetBondDir(Chem.BondDir.UNKNOWN)
    elif damage == "either_double":
        ring_double.SetBondDir(Chem.BondDir.EITHERDOUBLE)
    else:
        ends = ring_double.GetBeginAtomIdx(), ring_double.GetEndAtomIdx()
        refs = [next(atom.GetIdx() for atom in candidate.GetAtomWithIdx(endpoint).GetNeighbors()
                     if atom.GetIdx() != ends[1 - index])
                for index, endpoint in enumerate(ends)]
        ring_double.SetStereoAtoms(*refs)
        assert len(ring_double.GetStereoAtoms()) == 2
        assert ring_double.GetStereo() == Chem.BondStereo.STEREONONE
    reject(candidate, inverted(candidate))


@pytest.mark.parametrize("owner", ["mol", "ring_bond", "endpoint_atom", "incident_bond"])
@pytest.mark.parametrize("value", [0, 1])
def test_unknown_stereo_marker_presence_disallows_small_ring_exclusion(owner, value):
    candidate, ring_double = small_ring_pair_fixture(6)
    if owner == "mol":
        target = candidate
    elif owner == "ring_bond":
        target = ring_double
    elif owner == "endpoint_atom":
        target = ring_double.GetBeginAtom()
    else:
        target = next(b for b in ring_double.GetBeginAtom().GetBonds()
                      if b.GetIdx() != ring_double.GetIdx())
    target.SetIntProp("_UnknownStereo", value)
    assert target.HasProp("_UnknownStereo")
    # Even zero must fail; an annotation's value is not a proof of certainty.
    reject(candidate, inverted(candidate))


def test_small_ring_exclusion_is_not_assumed_for_an_unvalidated_rdkit_version(monkeypatch):
    candidate, _ = small_ring_pair_fixture(6)
    author = inverted(candidate)
    monkeypatch.setattr(rdBase, "rdkitVersion", "unvalidated-synthetic-runtime")
    reject(candidate, author)
    # The pre-existing exact ordered path has no runtime-dependent ring proof.
    accept(candidate, Chem.Mol(candidate), redecoded=False)


@pytest.mark.parametrize("direction", [Chem.BondDir.NONE, Chem.BondDir.BEGINWEDGE,
                                      Chem.BondDir.BEGINDASH, Chem.BondDir.UNKNOWN,
                                      Chem.BondDir.EITHERDOUBLE])
def test_changed_support_or_other_direction_classes_are_rejected(direction):
    candidate = molecule()
    author = Chem.Mol(candidate)
    author.GetBondWithIdx(signed_ids(candidate)[0]).SetBondDir(direction)
    reject(candidate, author)


@pytest.mark.parametrize("direction", [Chem.BondDir.BEGINWEDGE, Chem.BondDir.BEGINDASH,
                                      Chem.BondDir.UNKNOWN])
def test_unchanged_unsupported_branch_in_a_changed_component_is_rejected(direction):
    candidate = molecule("F/C(Cl)=C(/Br)I")
    candidate.GetBondWithIdx(signed_ids(candidate)[0]).SetBondDir(direction)
    reject(candidate, inverted(candidate))


def test_equal_canonical_graph_cannot_replace_ordered_atom_and_bond_correspondence():
    candidate = molecule()
    permuted = Chem.RenumberAtoms(candidate, [3, 2, 1, 0])
    assert Chem.MolToSmiles(Chem.Mol(candidate)) == Chem.MolToSmiles(Chem.Mol(permuted))
    reject(candidate, inverted(permuted))


def test_atom_chirality_drift_outside_the_changed_component_is_rejected():
    candidate = molecule("F/C=C/F.F[C@H](Cl)Br")
    author = inverted(candidate)
    atom = author.GetAtomWithIdx(5)
    assert atom.GetChiralTag() in (Chem.ChiralType.CHI_TETRAHEDRAL_CW,
                                  Chem.ChiralType.CHI_TETRAHEDRAL_CCW)
    atom.InvertChirality()
    reject(candidate, author)


def test_stereo_group_drift_outside_the_changed_component_is_rejected():
    candidate = molecule("F/C=C/F.F[C@H](Cl)Br |&1:5|")
    assert len(candidate.GetStereoGroups()) == 1
    author = inverted(molecule("F/C=C/F.F[C@H](Cl)Br"))
    assert len(author.GetStereoGroups()) == 0
    reject(candidate, author)


@pytest.mark.parametrize("field", ["atom_isotope", "atom_charge", "atom_map", "atom_aromatic",
                                  "bond_type", "bond_aromatic", "bond_conjugated", "stereo"])
def test_a_valid_gauge_does_not_license_other_ordered_structure_drift(field):
    candidate = molecule()
    author = inverted(candidate)
    atom = author.GetAtomWithIdx(0)
    bond = author.GetBondWithIdx(signed_ids(author)[0])
    if field == "atom_isotope":
        atom.SetIsotope(19)
    elif field == "atom_charge":
        atom.SetFormalCharge(1)
    elif field == "atom_map":
        atom.SetAtomMapNum(7)
    elif field == "atom_aromatic":
        atom.SetIsAromatic(not atom.GetIsAromatic())
    elif field == "bond_type":
        bond.SetBondType(Chem.BondType.DOUBLE)
    elif field == "bond_aromatic":
        bond.SetIsAromatic(not bond.GetIsAromatic())
    elif field == "bond_conjugated":
        bond.SetIsConjugated(not bond.GetIsConjugated())
    else:
        double_bonds(author)[0].SetStereo(Chem.BondStereo.STEREOZ)
    reject(candidate, author)


@pytest.mark.parametrize("change", ["coordinate", "dimension", "missing", "conformer_id"])
def test_copy_only_diagnostic_conformer_removal_cannot_hide_original_geometry_drift(change):
    candidate = molecule(coordinates=True)
    author = inverted(candidate)
    if change == "coordinate":
        author.GetConformer().SetAtomPosition(0, (99., 0., 0.))
    elif change == "dimension":
        author.GetConformer().Set3D(False)
    elif change == "missing":
        author.RemoveAllConformers()
    else:
        author.GetConformer().SetId(4)
    reject(candidate, author)


def test_queries_are_not_accepted_as_direction_equivalence():
    candidate = Chem.MolFromSmarts("F/C=C/F")
    assert candidate is not None and any(a.HasQuery() for a in candidate.GetAtoms())
    reject(candidate, Chem.Mol(candidate))


def test_new_stereo_perception_rejects_changed_path_but_does_not_break_exact_path():
    candidate = molecule()
    author = inverted(candidate)
    Chem.SetUseLegacyStereoPerception(False)
    reject(candidate, author)
    accept(candidate, Chem.Mol(candidate), redecoded=False)


@pytest.mark.parametrize("fails", [False, True])
def test_original_allprops_and_rng_are_preserved_even_with_stale_computed_caches(fails, monkeypatch):
    candidate = molecule("F/C(Cl)=C(/Br)I", coordinates=True)
    author = inverted(candidate, signed_ids(candidate)[:1] if fails else None)
    for index, mol in enumerate((candidate, author)):
        mol.SetProp("arbitrary_private_marker", "synthetic-only")
        mol.SetIntProp("_StereochemDone", 1)
        mol.GetAtomWithIdx(0).SetIntProp("_CIPRank", 999)
        mol.GetAtomWithIdx(1).SetProp("_CIPCode", "stale-cache")
        mol.GetBondWithIdx(0).SetProp("arbitrary_bond_property", str(index))
        mol.GetConformer().SetProp("arbitrary_conformer_property", "keep")
    before = binary(candidate), binary(author)
    python_rng, numpy_rng = random.getstate(), np.random.get_state()
    torch_rng = torch.get_rng_state().clone()
    def forbidden_open(*args, **kwargs):
        pytest.fail("Direction proof must not read any files")
    monkeypatch.setattr(builtins, "open", forbidden_open)
    if fails:
        reject(candidate, author)
    else:
        accept(candidate, author)
    assert (binary(candidate), binary(author)) == before
    assert random.getstate() == python_rng
    current = np.random.get_state()
    assert current[0] == numpy_rng[0] and np.array_equal(current[1], numpy_rng[1])
    assert current[2:] == numpy_rng[2:]
    assert torch.equal(torch.get_rng_state(), torch_rng)


@pytest.mark.parametrize("candidate,author", [(None, None), ("F/C=C/F", "F/C=C/F"),
                                             (Chem.Mol(), Chem.Mol())])
def test_invalid_inputs_fail_with_the_public_error(candidate, author):
    with pytest.raises(SomDirectionEquivalenceError):
        verify_cyp_direction_equivalence(candidate, author)
