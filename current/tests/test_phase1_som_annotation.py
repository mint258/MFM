"""Synthetic CYP PRIMARY capability, never real/final annotation evidence.

Positive fixtures use the actual molecular lineage helper and a default SDF
supplier on tiny in-memory structures. Corrupted fixtures are explicit negative
tests, not manually asserted proofs of molecular correspondence.
"""
from __future__ import annotations

import builtins
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import hashlib
import json
import random

import numpy as np
import pytest
from rdkit import Chem
import torch

from phychem_mfm.phase1.identity import canonical_hash
from phychem_mfm.phase1.som_atom_mapping import build_cyp_author_atom_mapping
from phychem_mfm.phase1.som_annotation import (
    CYP_ISOFORMS,
    MAX_ANNOTATION_BYTES,
    MAX_MAPPING_PROVENANCE_BYTES,
    SomAnnotationError,
    decode_cyp_primary_annotation,
)


EXPECTED_ISOFORMS = ("1A2", "2A6", "2B6", "2C8", "2C9", "2C19", "2D6", "2E1", "3A4")


def binary(mol):
    return mol.ToBinary(Chem.PropertyPickleOptions.AllProps)


def fixture(*, primary="1", smiles="CO", interleave=True, isoform="1A2"):
    source = Chem.AddHs(Chem.MolFromSmiles(smiles))
    if interleave:
        assert source.GetNumAtoms() == 6
        source = Chem.RenumberAtoms(source, [2, 0, 3, 1, 4, 5])
    conformer = Chem.Conformer(source.GetNumAtoms())
    conformer.Set3D(False)
    for index in range(source.GetNumAtoms()):
        conformer.SetAtomPosition(index, (float(index), float((index * index) % 3), 0.))
    source.AddConformer(conformer)
    block = Chem.MolToMolBlock(source)
    raw = block + "\n>  <PRIMARY_SOM>\n" + primary + "\n\n$$$$\n"
    native = Chem.MolFromMolBlock(block, sanitize=True, removeHs=False, strictParsing=True)
    supplier = Chem.SDMolSupplier()
    supplier.SetData(raw)
    author = supplier[0]
    assert native is not None and author is not None
    mapping = build_cyp_author_atom_mapping(native, author,
        source_file=isoform + ".sdf", source_file_sha256=hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        source_record_1based=1, source_block_sha256=hashlib.sha256(block.encode("utf-8")).hexdigest())
    return native, author, mapping


def decode(primary, mapping, *, isoform="1A2", empty_policy="reject"):
    return decode_cyp_primary_annotation(primary, mapping, isoform=isoform, empty_policy=empty_policy)


def with_provenance(mapping, **updates):
    provenance = deepcopy(mapping.provenance)
    provenance.update(updates)
    return replace(mapping, provenance=provenance)


def reseal_mapping(mapping):
    """Repair only the checksum of a deliberately corrupted negative fixture."""
    provenance = deepcopy(mapping.provenance)
    provenance["mapping_provenance_sha256"] = canonical_hash(
        {key: value for key, value in provenance.items() if key != "mapping_provenance_sha256"})
    return replace(mapping, provenance=provenance)


def test_source_reader_oracle_subtracts_once_then_maps_to_interleaved_native_ids():
    native, author, mapping = fixture(primary="1")
    # Independent fixed-author algorithm, using the actual supplier property.
    author_positions = [int(token) - 1 for token in author.GetProp("PRIMARY_SOM").strip().split()
                        if token.isdigit()]
    author_labels = [int(index in author_positions) for index in range(author.GetNumAtoms())]
    output = decode(author.GetProp("PRIMARY_SOM"), mapping)
    assert mapping.author_to_native == (1, 3)
    assert native.GetNumAtoms() == 6 and author.GetNumAtoms() == 2
    assert author_labels == [1, 0]
    assert output.positive_author_ids == (0,)
    assert output.positive_native_ids == (1,)
    assert output.labels == (None, 1, None, 0, None, None)
    assert output.candidate_mask == output.supervision_mask == (False, True, False, True, False, False)
    assert [output.labels[index] for index in mapping.author_to_native] == author_labels


def test_second_author_position_is_not_second_native_row_or_canonical_order():
    _, author, mapping = fixture(primary="2")
    output = decode(author.GetProp("PRIMARY_SOM"), mapping)
    assert output.positive_author_ids == (1,)
    assert output.positive_native_ids == (3,)
    assert output.labels == (None, 0, None, 1, None, None)


def test_duplicate_and_leading_zero_tokens_preserve_binary_source_semantics_and_raw_provenance():
    primary = "2 1 2 01"
    _, author, mapping = fixture(primary=primary)
    output = decode(author.GetProp("PRIMARY_SOM"), mapping)
    assert output.positive_author_ids == (1, 0)
    assert output.positive_native_ids == (3, 1)
    assert output.labels == (None, 1, None, 1, None, None)
    assert output.provenance["raw_tokens"] == ("2", "1", "2", "01")
    assert output.provenance["raw_token_count"] == 4
    assert output.provenance["unique_positive_count"] == 2
    assert output.provenance["duplicate_count"] == 2
    assert output.provenance["decoded_property_utf8_sha256"] == hashlib.sha256(primary.encode("utf-8")).hexdigest()


@pytest.mark.parametrize("whitespace", [" ", "\t", "\n", "\r", "\v", "\f", " \t\n\r\v\f "])
def test_declared_ascii_whitespace_is_accepted_without_changing_atom_order(whitespace):
    _, _, mapping = fixture()
    output = decode(whitespace + "01" + whitespace + "002" + whitespace, mapping)
    assert output.positive_author_ids == (0, 1)
    assert output.positive_native_ids == (1, 3)
    assert output.labels == (None, 1, None, 1, None, None)


def test_deleted_hydrogens_stay_unknown_and_candidate_mask_is_the_actual_retained_universe():
    native, author, mapping = fixture(primary="1 2")
    output = decode("1 2", mapping)
    assert mapping.deleted_native_ids == (0, 2, 4, 5)
    for index in mapping.deleted_native_ids:
        assert native.GetAtomWithIdx(index).GetAtomicNum() == 1
        assert output.labels[index] is None
        assert output.candidate_mask[index] is output.supervision_mask[index] is False
    assert sum(output.candidate_mask) == author.GetNumAtoms()
    assert all(type(value) is bool for value in output.candidate_mask + output.supervision_mask)
    assert all(value is None or type(value) is int for value in output.labels)


def test_retained_isotope_h_is_a_candidate_and_can_receive_source_label():
    native, author, mapping = fixture(primary="1", smiles="[2H]OC", interleave=False)
    isotope_id = next(atom.GetIdx() for atom in native.GetAtoms()
                      if atom.GetAtomicNum() == 1 and atom.GetIsotope() == 2)
    assert isotope_id == 0 and author.GetAtomWithIdx(0).GetIsotope() == 2
    output = decode("1", mapping)
    assert output.positive_native_ids == (isotope_id,)
    assert output.candidate_mask[isotope_id] is output.supervision_mask[isotope_id] is True
    assert output.labels[isotope_id] == 1
    assert mapping.deleted_native_ids


@pytest.mark.parametrize("isoform", EXPECTED_ISOFORMS)
def test_exact_nine_isoform_tasks_are_source_basename_bound(isoform):
    assert CYP_ISOFORMS == EXPECTED_ISOFORMS
    _, _, mapping = fixture(isoform=isoform)
    output = decode("1", mapping, isoform=isoform)
    assert output.provenance["isoform"] == isoform
    assert output.provenance["source_file"] == isoform + ".sdf"
    assert output.provenance["property_name"] == "PRIMARY_SOM"


@pytest.mark.parametrize("isoform", ["2A6", "AZ", "3a4", "1A2.sdf", "all", "", None, True])
def test_wrong_or_undeclared_isoform_is_not_inferred_from_molecular_identity(isoform):
    _, _, mapping = fixture(isoform="1A2")
    with pytest.raises(SomAnnotationError):
        decode("1", mapping, isoform=isoform)


@pytest.mark.parametrize("primary", [None, True, False, 1, [1], (1,), {"PRIMARY_SOM": "1"}, b"1"])
@pytest.mark.parametrize("policy", ["reject", "preserve_unknown", "author_zero"])
def test_missing_or_nonstring_property_never_becomes_a_valid_negative(primary, policy):
    _, _, mapping = fixture()
    with pytest.raises(SomAnnotationError):
        decode(primary, mapping, empty_policy=policy)


@pytest.mark.parametrize("primary", ["", " \t\n\r\v\f "])
def test_present_empty_reject_policy_cannot_silently_supply_negatives(primary):
    _, _, mapping = fixture()
    with pytest.raises(SomAnnotationError):
        decode(primary, mapping, empty_policy="reject")


@pytest.mark.parametrize("primary", ["", " \t\n\r\v\f "])
def test_present_empty_preserve_unknown_keeps_candidates_without_supervision(primary):
    _, _, mapping = fixture()
    output = decode(primary, mapping, empty_policy="preserve_unknown")
    assert output.labels == (None,) * 6
    assert output.candidate_mask == (False, True, False, True, False, False)
    assert output.supervision_mask == (False,) * 6
    assert output.positive_author_ids == output.positive_native_ids == ()
    assert output.provenance["annotation_state"] == "PRESENT_EMPTY_UNKNOWN"
    assert output.provenance["property_present"] is True
    assert output.provenance["annotation_truth_verified"] is False
    assert output.provenance["formal_eligible"] is False


def test_explicit_author_zero_policy_is_a_nonformal_capability_not_a_default_empty_label():
    _, _, mapping = fixture()
    output = decode("", mapping, empty_policy="author_zero")
    assert output.labels == (None, 0, None, 0, None, None)
    assert output.supervision_mask == output.candidate_mask
    assert output.provenance["annotation_state"] == "PRESENT_EMPTY_AUTHOR_ZERO"
    assert output.provenance["empty_policy"] == "author_zero"
    assert output.provenance["annotation_truth_verified"] is False
    assert output.provenance["formal_eligible"] is False


@pytest.mark.parametrize("policy", [None, True, "", "auto", "negative", "author-zero"])
@pytest.mark.parametrize("primary", ["", "1"])
def test_empty_policy_must_be_explicit_even_for_nonempty_annotation(primary, policy):
    _, _, mapping = fixture()
    with pytest.raises(SomAnnotationError):
        decode(primary, mapping, empty_policy=policy)


def test_public_api_does_not_infer_an_omitted_empty_policy():
    _, _, mapping = fixture()
    with pytest.raises(TypeError):
        decode_cyp_primary_annotation("1", mapping, isoform="1A2")


@pytest.mark.parametrize("primary", ["0", "-1", "+1", "3", "6", "1,2", "1 , 2", "[1,2]",
    "1.0", "1e0", "1 bad 2", "1\x002", "１", "²", "١", "\u00a01", "1\u00a0",
    "1\u00a02", "1\u20032", "\u200b1", "1;2"])
def test_strict_field_rejects_bad_tokens_unicode_and_author_range_instead_of_filtering(primary):
    _, _, mapping = fixture()
    # Native count 6 must not license an author index >2.
    with pytest.raises(SomAnnotationError):
        decode(primary, mapping)


def test_decoded_property_byte_budget_is_checked_before_parsing_or_integer_coercion():
    _, _, mapping = fixture()
    assert MAX_ANNOTATION_BYTES == 65536
    with pytest.raises(SomAnnotationError):
        decode("1" + " " * MAX_ANNOTATION_BYTES, mapping)


def test_long_but_bounded_leading_zero_token_has_the_same_one_based_value():
    _, _, mapping = fixture()
    output = decode("0" * 5000 + "1", mapping)
    assert output.positive_author_ids == (0,)
    assert output.positive_native_ids == (1,)
    assert output.labels == (None, 1, None, 0, None, None)


def test_output_provenance_binds_exact_decoded_property_text_and_detaches_from_the_mapping():
    _, _, mapping = fixture()
    before = deepcopy(mapping.provenance)
    primary = " 01\t"
    output = decode(primary, mapping)
    provenance = output.provenance
    assert provenance["decoded_property_utf8_bytes"] == len(primary.encode("utf-8"))
    assert provenance["decoded_property_utf8_sha256"] == hashlib.sha256(primary.encode("utf-8")).hexdigest()
    assert provenance["mapping_provenance_sha256"] == before["mapping_provenance_sha256"]
    assert provenance["direction_equivalence_receipt_sha256"] == before["direction_equivalence_receipt_sha256"]
    assert provenance["source_index_base"] == 1 and provenance["output_index_base"] == 0
    assert provenance["index_decrement_count"] == 1
    assert provenance["source_or_annotation_truth_independently_verified"] is False
    assert provenance["property_source_record_association_independently_verified"] is False
    assert provenance["structure_block_hash_covers_property"] is False
    assert provenance["annotation_provenance_sha256"] == canonical_hash(
        {key: value for key, value in provenance.items() if key != "annotation_provenance_sha256"})
    decoded = json.loads(json.dumps(provenance))
    assert canonical_hash(decoded) == canonical_hash(provenance)
    provenance["isoform"] = "caller changed returned proof"
    assert mapping.provenance == before
    assert decode(primary, mapping).provenance["isoform"] == "1A2"
    with pytest.raises(FrozenInstanceError):
        output.labels = ()


def test_decode_success_and_failure_do_not_read_files_mutate_molecules_or_rng(monkeypatch):
    native, author, mapping = fixture()
    native.SetProp("unrelated_synthetic_property", "not supervision")
    native.GetAtomWithIdx(1).SetIntProp("synthetic_int", 7)
    author.SetProp("synthetic_author_note", "preserve")
    before_native, before_author, before_mapping = binary(native), binary(author), deepcopy(mapping)
    python_rng, numpy_rng, torch_rng = random.getstate(), np.random.get_state(), torch.get_rng_state().clone()
    def no_open(*args, **kwargs):
        pytest.fail("Pure annotation capability must not read data or checkpoint files")
    monkeypatch.setattr(builtins, "open", no_open)
    assert decode("1", mapping).positive_native_ids == (1,)
    with pytest.raises(SomAnnotationError):
        decode("1 bad", mapping)
    assert binary(native) == before_native and binary(author) == before_author
    assert mapping == before_mapping
    assert random.getstate() == python_rng
    current = np.random.get_state()
    assert current[0] == numpy_rng[0] and np.array_equal(current[1], numpy_rng[1])
    assert current[2:] == numpy_rng[2:]
    assert torch.equal(torch.get_rng_state(), torch_rng)


@pytest.mark.parametrize("field,value", [("source_file_sha256", "a" * 64),
    ("source_block_sha256", "b" * 64), ("source_record_1based", 2),
    ("author_atoms", 3), ("native_atoms", 7), ("author_commit", "c" * 40),
    ("annotation_semantics_verified", True)])
def test_stale_mapping_provenance_is_rejected_before_decoding(field, value):
    _, _, mapping = fixture()
    damaged = with_provenance(mapping, **{field: value})
    with pytest.raises(SomAnnotationError):
        decode("1", damaged)


@pytest.mark.parametrize("damage", ["counts", "inverse", "duplicate", "out_of_range", "retained_order",
                                   "deleted_overlap", "bool_index", "wrong_source_task", "wrong_commit",
                                   "wrong_contract", "false_structure_proof", "annotation_truth_claim"])
def test_rehashed_mapping_contradictions_cannot_become_structural_or_annotation_proof(damage):
    _, _, mapping = fixture()
    if damage == "counts":
        damaged = with_provenance(mapping, author_atoms=3)
    elif damage == "inverse":
        damaged = replace(mapping, native_to_author=(None, 1, None, 0, None, None))
    elif damage == "duplicate":
        damaged = replace(mapping, author_to_native=(1, 1))
    elif damage == "out_of_range":
        damaged = replace(mapping, author_to_native=(1, 6))
    elif damage == "retained_order":
        damaged = replace(mapping, retained_native_ids=(3, 1))
    elif damage == "deleted_overlap":
        damaged = replace(mapping, deleted_native_ids=(0, 1, 2, 4, 5))
    elif damage == "bool_index":
        damaged = replace(mapping, author_to_native=(True, 3))
    elif damage == "wrong_source_task":
        damaged = with_provenance(mapping, source_file="2A6.sdf")
    elif damage == "wrong_commit":
        damaged = with_provenance(mapping, author_commit="c" * 40)
    elif damage == "wrong_contract":
        damaged = with_provenance(mapping, source_contract="unverified_alternative")
    elif damage == "false_structure_proof":
        damaged = with_provenance(mapping, ordered_pair_structure_verified=False)
    else:
        damaged = with_provenance(mapping, annotation_semantics_verified=True)
    with pytest.raises(SomAnnotationError):
        decode("1", reseal_mapping(damaged))


@pytest.mark.parametrize("mapping", [None, {}, True, [1, 3]])
def test_mapping_type_is_not_substituted_by_a_boolean_or_bare_permutation(mapping):
    with pytest.raises(SomAnnotationError):
        decode("1", mapping)


@pytest.mark.parametrize("damage", ["stale_inner_hash", "rehashed_annotation_claim",
                                   "rehashed_raw_hash_drift", "rehashed_status_drift",
                                   "consistent_exact_graph_drift", "consistent_exact_signature_drift"])
def test_nested_direction_receipt_checksums_and_semantics_must_agree_with_mapping(damage):
    _, _, mapping = fixture()
    provenance = deepcopy(mapping.provenance)
    receipt = provenance["direction_equivalence"]
    if damage in ("stale_inner_hash", "rehashed_annotation_claim"):
        receipt["labels_read_or_inferred"] = True
    elif damage == "rehashed_raw_hash_drift":
        receipt["candidate_raw"]["ordered_graph_sha256"] = "e" * 64
    elif damage in ("consistent_exact_graph_drift", "consistent_exact_signature_drift"):
        field = "ordered_graph_sha256" if damage == "consistent_exact_graph_drift" else "ordered_signature_sha256"
        receipt["candidate_raw"][field] = "e" * 64
        provenance["candidate_" + field] = "e" * 64
        # All checksum links now agree, but EXACT cannot have unequal raw
        # candidate/author signatures. This is metadata consistency, not a
        # replacement for independent molecular validation.
    else:
        receipt["status"] = "VERIFIED_DIRECTION_COMPONENT_INVERSION"
    if damage != "stale_inner_hash":
        receipt["receipt_sha256"] = canonical_hash(
            {key: value for key, value in receipt.items() if key != "receipt_sha256"})
        provenance["direction_equivalence_receipt_sha256"] = receipt["receipt_sha256"]
    damaged = reseal_mapping(replace(mapping, provenance=provenance))
    with pytest.raises(SomAnnotationError):
        decode("1", damaged)


def test_consistent_source_hash_claim_is_recorded_without_pretending_to_verify_file_bytes():
    _, _, mapping = fixture()
    changed = reseal_mapping(with_provenance(mapping, source_file_sha256="a" * 64))
    output = decode("1", changed)
    assert output.provenance["source_file_sha256"] == "a" * 64
    assert output.provenance["mapping_metadata_consistent"] is True
    assert output.provenance["source_or_annotation_truth_independently_verified"] is False
    assert output.provenance["property_source_record_association_independently_verified"] is False
    assert output.provenance["annotation_truth_verified"] is False


@pytest.mark.parametrize("damage", ["oversized_finite_json", "deep_finite_json", "cyclic_object"])
def test_mapping_metadata_bounds_and_cycles_fail_without_unbounded_serialization(damage, monkeypatch):
    _, _, mapping = fixture()
    provenance = deepcopy(mapping.provenance)
    if damage == "oversized_finite_json":
        provenance["synthetic_extra_metadata"] = "x" * (MAX_MAPPING_PROVENANCE_BYTES + 1)
    elif damage == "deep_finite_json":
        nested = {}
        for _ in range(128):
            nested = {"next": nested}
        provenance["synthetic_extra_metadata"] = nested
    else:
        provenance["synthetic_extra_metadata"] = provenance
    damaged = replace(mapping, provenance=provenance)
    if damage != "cyclic_object":
        damaged = reseal_mapping(damaged)
    def no_serialization(*args, **kwargs):
        pytest.fail("Oversized, deep or cyclic metadata must fail before entering JSON encoding")
    monkeypatch.setattr(json.JSONEncoder, "iterencode", no_serialization)
    with pytest.raises(SomAnnotationError):
        decode("1", damaged)
