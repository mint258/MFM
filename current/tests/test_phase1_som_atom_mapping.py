"""Synthetic structural lineage only; no real source files or SoM targets."""
from __future__ import annotations

from dataclasses import FrozenInstanceError
import builtins
import json
import random

import numpy as np
import pytest
from rdkit import Chem, rdBase
import torch

from phychem_mfm.phase1.identity import canonical_hash
from phychem_mfm.phase1.som_atom_mapping import (
    AUTHOR_RDKIT_PIN, MAPPING_SCHEMA, SomAtomMappingError, build_cyp_author_atom_mapping,
)


SOURCE = {"source_file": "fixture.sdf", "source_file_sha256": "a" * 64,
          "source_record_1based": 1, "source_block_sha256": "b" * 64}


def binary(mol):
    return mol.ToBinary(Chem.PropertyPickleOptions.AllProps)


def pair(smiles="CO", *, interleave=False, coordinates=True):
    source = Chem.AddHs(Chem.MolFromSmiles(smiles))
    if interleave:
        assert source.GetNumAtoms() == 6
        source = Chem.RenumberAtoms(source, [2, 0, 3, 1, 4, 5])
    if coordinates:
        conformer = Chem.Conformer(source.GetNumAtoms())
        conformer.Set3D(False)
        for index in range(source.GetNumAtoms()):
            conformer.SetAtomPosition(index, (float(index), float((index * index) % 3), 0.))
        source.AddConformer(conformer)
    block = Chem.MolToMolBlock(source)
    native = Chem.MolFromMolBlock(block, sanitize=True, removeHs=False, strictParsing=True)
    # The actual default supplier parser, fed only synthetic structure text.
    supplier = Chem.SDMolSupplier()
    supplier.SetData(block + "\n$$$$\n")
    author = supplier[0]
    assert native is not None and author is not None
    return native, author


def mapping(native, author, **source):
    return build_cyp_author_atom_mapping(native, author, **{**SOURCE, **source})


def test_interleaved_h_has_retained_subset_bijection_and_deleted_nulls():
    native, author = pair(interleave=True)
    result = mapping(native, author)
    assert result.author_to_native == result.retained_native_ids == (1, 3)
    assert result.native_to_author == (None, 0, None, 1, None, None)
    assert result.deleted_native_ids == (0, 2, 4, 5)
    assert result.provenance["native_atoms"] == 6 and result.provenance["author_atoms"] == 2
    assert result.provenance["bijection_scope"] == "author_atoms_to_retained_native_subset_only"
    for index, native_index in enumerate(result.author_to_native):
        assert result.native_to_author[native_index] == index
    with pytest.raises(FrozenInstanceError):
        result.author_to_native = (0, 1)


def test_no_explicit_h_is_identity_map_without_canonical_roundtrip():
    native = Chem.MolFromSmiles("OCC")
    author = Chem.Mol(native)
    result = mapping(native, author)
    assert result.author_to_native == result.native_to_author == (0, 1, 2)
    assert result.deleted_native_ids == ()
    assert native.GetAtomWithIdx(0).GetAtomicNum() == 8


def test_default_removehs_keeps_isotope_h_and_does_not_simply_filter_atomic_number():
    native, author = pair("[2H]OC", coordinates=False)
    result = mapping(native, author)
    isotope_index = next(atom.GetIdx() for atom in native.GetAtoms()
                         if atom.GetAtomicNum() == 1 and atom.GetIsotope() == 2)
    assert isotope_index in result.retained_native_ids
    assert result.native_to_author[isotope_index] is not None
    assert author.GetAtomWithIdx(result.native_to_author[isotope_index]).GetIsotope() == 2
    assert result.deleted_native_ids


def test_original_objects_all_properties_coordinates_and_rng_are_unchanged():
    native, author = pair(interleave=True)
    native.SetProp("PRIMARY_SOM", "OPAQUE_SYNTHETIC_ANNOTATION_NOT_DECODED")
    native.GetAtomWithIdx(1).SetProp("arbitrary", "preserve atom property")
    native.GetAtomWithIdx(1).SetIntProp("_phase1_som_mapping_native_id_v1", 987)
    author.SetProp("unrelated_property", "keep")
    before_native, before_author = binary(native), binary(author)
    python_rng, numpy_rng, torch_rng = random.getstate(), np.random.get_state(), torch.get_rng_state().clone()
    result = mapping(native, author)
    assert binary(native) == before_native and binary(author) == before_author
    assert random.getstate() == python_rng
    current = np.random.get_state()
    assert current[0] == numpy_rng[0] and np.array_equal(current[1], numpy_rng[1])
    assert current[2:] == numpy_rng[2:]
    assert torch.equal(torch.get_rng_state(), torch_rng)
    assert "OPAQUE_SYNTHETIC" not in json.dumps(result.provenance)


def test_same_element_permutation_and_equal_fullkey_do_not_license_atom_matching():
    native, author = pair("CCO")
    swapped = Chem.RenumberAtoms(author, [1, 0, 2])
    assert [atom.GetAtomicNum() for atom in swapped.GetAtoms()] == [atom.GetAtomicNum() for atom in author.GetAtoms()]
    assert Chem.MolToInchiKey(Chem.Mol(swapped)) == Chem.MolToInchiKey(Chem.Mol(author))
    before = binary(native), binary(swapped)
    with pytest.raises(SomAtomMappingError, match="ordered"):
        mapping(native, swapped)
    assert (binary(native), binary(swapped)) == before


def test_equal_atom_features_still_require_ordered_bond_correspondence():
    native = Chem.MolFromSmiles("CC.CC")
    author = Chem.RenumberAtoms(native, [0, 2, 1, 3])
    assert all(atom.GetAtomicNum() == 6 and atom.GetNumImplicitHs() == 3
               for mol in (native, author) for atom in mol.GetAtoms())
    assert Chem.MolToInchiKey(Chem.Mol(native)) == Chem.MolToInchiKey(Chem.Mol(author))
    with pytest.raises(SomAtomMappingError, match="ordered bonds"):
        mapping(native, author)


@pytest.mark.parametrize("change", ["coordinates", "dimension", "missing_conformer", "conformer_id"])
def test_author_coordinate_origin_and_dimension_must_match_exactly(change):
    native, author = pair()
    changed = Chem.Mol(author)
    if change == "coordinates":
        changed.GetConformer().SetAtomPosition(0, (99., 0., 0.))
    elif change == "dimension":
        changed.GetConformer().Set3D(not changed.GetConformer().Is3D())
    elif change == "missing_conformer":
        changed.RemoveAllConformers()
    else:
        changed.GetConformer().SetId(7)
    with pytest.raises(SomAtomMappingError, match="conformers"):
        mapping(native, changed)


@pytest.mark.parametrize("field", ["isotope", "formal_charge", "atom_stereo", "bond_stereo"])
def test_same_size_author_structure_drift_is_rejected(field):
    smiles = "F[C@H](Cl)Br" if field == "atom_stereo" else "F/C=C/F" if field == "bond_stereo" else "CO"
    native = Chem.MolFromSmiles(smiles)
    author = Chem.RemoveHs(Chem.Mol(native))
    if field == "isotope":
        author.GetAtomWithIdx(0).SetIsotope(13)
    elif field == "formal_charge":
        author.GetAtomWithIdx(0).SetFormalCharge(1)
    elif field == "atom_stereo":
        atom = author.GetAtomWithIdx(1)
        other = Chem.ChiralType.CHI_TETRAHEDRAL_CCW if atom.GetChiralTag() == Chem.ChiralType.CHI_TETRAHEDRAL_CW else Chem.ChiralType.CHI_TETRAHEDRAL_CW
        atom.SetChiralTag(other)
    else:
        double = next(bond for bond in author.GetBonds() if bond.GetBondType() == Chem.BondType.DOUBLE)
        double.SetStereo(Chem.BondStereo.STEREOZ)
    with pytest.raises(SomAtomMappingError, match="ordered"):
        mapping(native, author)


def test_nonfinite_source_coordinate_is_rejected_without_original_mutation():
    native, author = pair()
    native.GetConformer().SetAtomPosition(0, (float("nan"), 0., 0.))
    before = binary(native), binary(author)
    with pytest.raises(SomAtomMappingError, match="finite"):
        mapping(native, author)
    assert (binary(native), binary(author)) == before


@pytest.mark.parametrize("damage", ["missing", "duplicate", "out_of_range", "reordered", "non_h_deleted"])
def test_removehs_lineage_failure_rejects_instead_of_guessing(monkeypatch, damage):
    native, author = pair()
    original = Chem.RemoveHs
    def damaged(mol):
        copied = original(mol)
        tag = "_phase1_som_mapping_native_id_v1"
        if damage == "missing":
            copied.GetAtomWithIdx(0).ClearProp(tag)
        elif damage == "duplicate":
            copied.GetAtomWithIdx(1).SetIntProp(tag, copied.GetAtomWithIdx(0).GetIntProp(tag))
        elif damage == "out_of_range":
            copied.GetAtomWithIdx(0).SetIntProp(tag, 999)
        elif damage == "reordered":
            copied = Chem.RenumberAtoms(copied, [1, 0])
        else:
            copied.GetAtomWithIdx(1).SetIntProp(tag, 2)  # Native oxygen (ID1) would be missing.
        return copied
    monkeypatch.setattr(Chem, "RemoveHs", damaged)
    with pytest.raises(SomAtomMappingError):
        mapping(native, author)


@pytest.mark.parametrize("binding", [
    {"source_file": "../fixture.sdf"}, {"source_file": "C:\\fixture.sdf"},
    {"source_file_sha256": "not_a_hash"}, {"source_block_sha256": "A" * 64},
    {"source_record_1based": 0}, {"source_record_1based": True}, {"source_record_1based": 1.},
])
def test_source_references_require_explicit_structure_only_contract(binding):
    native, author = pair()
    with pytest.raises(SomAtomMappingError):
        mapping(native, author, **binding)


@pytest.mark.parametrize("native,author", [(None, None), ("CO", "CO"), (Chem.Mol(), Chem.Mol())])
def test_invalid_molecules_are_rejected(native, author):
    with pytest.raises(SomAtomMappingError):
        mapping(native, author)


def test_provenance_binds_source_and_maps_without_claiming_author_version_or_annotations(monkeypatch):
    native, author = pair(interleave=True)
    def forbidden_open(*args, **kwargs):
        pytest.fail("Mapping helper must not open files")
    monkeypatch.setattr(builtins, "open", forbidden_open)
    result = mapping(native, author)
    metadata = dict(result.provenance)
    digest = metadata.pop("mapping_provenance_sha256")
    assert digest == canonical_hash(metadata)
    assert metadata["schema_version"] == MAPPING_SCHEMA
    assert metadata["state"] == "NOT_FROZEN" and metadata["formal_eligible"] is False
    assert metadata["ordered_pair_structure_verified"] is True
    receipt = metadata["direction_equivalence"]
    assert receipt["status"] == "EXACT_ORDERED_SIGNATURE"
    assert metadata["ordered_pair_structure_verification"] == receipt["status"]
    assert metadata["ordered_signature_exact_match"] is True
    assert metadata["ordered_direction_flags_exact_match"] is True
    assert receipt["decoded_copies"]["performed"] is False
    receipt_content = dict(receipt)
    receipt_digest = receipt_content.pop("receipt_sha256")
    assert receipt_digest == canonical_hash(receipt_content)
    assert metadata["direction_equivalence_receipt_sha256"] == receipt_digest
    assert metadata["annotation_semantics_verified"] is metadata["labels_read_or_inferred"] is False
    assert metadata["author_environment_rdkit_pin"] == AUTHOR_RDKIT_PIN == "2025.3.6"
    assert metadata["rdkit_version"] == rdBase.rdkitVersion
    assert metadata["author_runtime_version_matches_pin"] == (rdBase.rdkitVersion == "2025.03.6")
    assert metadata["author_version_reproduced"] is metadata["geometry_ready_for_encoder"] is False
    changed = mapping(native, author, source_record_1based=2)
    assert changed.author_to_native == result.author_to_native
    assert changed.provenance["mapping_provenance_sha256"] != digest
    assert json.loads(json.dumps(result.provenance))["native_to_author"] == [None, 0, None, 1, None, None]
    with pytest.raises(TypeError):
        build_cyp_author_atom_mapping(native, author, targets=[0], **SOURCE)


def test_complete_gauge_maps_retained_atoms_and_binds_receipt_without_erasing_raw_signatures():
    previous = Chem.GetUseLegacyStereoPerception()
    Chem.SetUseLegacyStereoPerception(True)
    try:
        # Synthetic graph-only integration; this does not claim an actual author
        # SDF parse or any real source coverage. No explicit H atoms are present.
        native = Chem.MolFromSmiles("F/C(Cl)=C(/Br)I")
        Chem.SetDoubleBondNeighborDirections(native)
        Chem.AssignStereochemistry(native, cleanIt=True, force=True)
        author = Chem.Mol(native)
        signs = (Chem.BondDir.ENDUPRIGHT, Chem.BondDir.ENDDOWNRIGHT)
        signed = [bond for bond in author.GetBonds() if bond.GetBondDir() in signs]
        assert len(signed) == 4
        for bond in signed:
            bond.SetBondDir(signs[1] if bond.GetBondDir() == signs[0] else signs[0])
        before = binary(native), binary(author)
        result = mapping(native, author)
        assert (binary(native), binary(author)) == before
        assert result.author_to_native == tuple(range(native.GetNumAtoms()))
        assert result.deleted_native_ids == ()
        metadata = result.provenance
        receipt = metadata["direction_equivalence"]
        assert metadata["ordered_pair_structure_verification"] == receipt["status"]
        assert metadata["candidate_ordered_graph_sha256"] == receipt["candidate_raw"]["ordered_graph_sha256"]
        assert metadata["author_ordered_graph_sha256"] == receipt["author_raw"]["ordered_graph_sha256"]
        assert metadata["candidate_ordered_signature_sha256"] == receipt["candidate_raw"]["ordered_signature_sha256"]
        assert metadata["author_ordered_signature_sha256"] == receipt["author_raw"]["ordered_signature_sha256"]
        content = dict(receipt)
        assert metadata["direction_equivalence_receipt_sha256"] == content.pop("receipt_sha256") == canonical_hash(content)
        # RemoveHs may regenerate an equivalent complete sign component in the
        # current runtime. Both outcomes must retain their actual raw signatures.
        assert receipt["status"] in {"EXACT_ORDERED_SIGNATURE", "VERIFIED_DIRECTION_COMPONENT_INVERSION"}
        assert metadata["formal_eligible"] is metadata["annotation_semantics_verified"] is False
        assert metadata["author_version_reproduced"] is metadata["geometry_ready_for_encoder"] is False
    finally:
        Chem.SetUseLegacyStereoPerception(previous)
