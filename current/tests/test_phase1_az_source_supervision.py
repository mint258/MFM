"""Synthetic AZ source frames; no real benchmark annotations are consumed."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path

import pytest
from rdkit import Chem
import torch

from conftest import small_config
from test_phase1_downstream_source_records import parent, candidate, ledger, sha, direction_copy
from phychem_mfm.factory import build_model
from phychem_mfm.phase1 import downstream_source_records as records
from phychem_mfm.phase1.az_annotation import GROUP_COLUMN, FLAG_COLUMN
from phychem_mfm.phase1.az_atom_mapping import AZAtomMappingError, build_az_author_atom_mapping
from phychem_mfm.phase1.downstream_readout import SourceAlignedH0Readout
from phychem_mfm.phase1.downstream_structures import read_az_raw_smiles
from phychem_mfm.phase1.identity import canonical_hash


def quote(value):
    return b'"' + value.replace(b'"', b'""') + b'"'


def fixture(tmp_path, *, smiles="CO", groups=b"['0']", flags=b"['1']", columns=None, raw_only=False):
    names = columns or ["Compound ID", "SMILES", GROUP_COLUMN, FLAG_COLUMN, "UNSELECTED_COMMENT"]
    values = {"Compound ID": b"Cmpd 1", "SMILES": smiles.encode("utf8"), GROUP_COLUMN: groups,
              FLAG_COLUMN: flags, "UNSELECTED_COMMENT": b'opaque,\xff\n"comment"'}
    raw = b'\xef\xbb\xbf' + b",".join(quote(x.encode("utf8")) for x in names) + b"\r\n"
    raw += b",".join(quote(values[x]) for x in names) + b"\r\n"
    sources, members = [], []
    source, member = parent(read_az_raw_smiles(smiles), ordinal=1, compound="Cmpd 1")
    sources.append(source)
    members.append(member)
    if raw_only:
        other = {**values, "Compound ID": b"Cmpd 2", GROUP_COLUMN: b"\xff", FLAG_COLUMN: b"\xff"}
        raw += b",".join(quote(other[x]) for x in names) + b"\r\n"
        source2, _ = parent(read_az_raw_smiles(smiles), ordinal=2, compound="Cmpd 2")
        sources.append(source2)
    path = tmp_path / "az_exactsom" / "raw" / "az_120_compounds.csv"
    path.parent.mkdir(parents=True)
    path.write_bytes(raw)
    store = records.SourceRecordStore(tmp_path, source_files={path.name: {"bytes": len(raw), "sha256": sha(raw)}},
                                      source_rows=sources, member_rows=members)
    record = store.get("az:Cmpd 1")
    row = candidate(record)
    artifact, _, _ = ledger(tmp_path, [row])
    sample = records.materialize_geometry(record, candidates=artifact, source_units="angstrom")
    return store, record, sample, raw, values


def build(store, record, sample, **options):
    return store.build_az_supervised_sample(record.record_id, sample=sample, role=options.pop("role", "train"),
        label_policy=options.pop("label_policy", "strict_exact_binary_set"),
        empty_policy=options.pop("empty_policy", "reject"), **options)


def reseal_record(record, *, mol=None, member=None, frame=None):
    changed = replace(record, structure=replace(record.structure, mol=mol) if mol is not None else record.structure,
                      member=deepcopy(member) if member is not None else deepcopy(record.member),
                      opaque_frame=frame if frame is not None else record.opaque_frame,
                      provenance=deepcopy(record.provenance))
    p = changed.provenance
    p["native_graph_sha256"] = canonical_hash(records._native_graph(changed.structure))
    p["raw_frame_sha256"] = sha(changed.opaque_frame)
    p["parent_member_row_sha256"] = canonical_hash(changed.member)
    p["record_binding_sha256"] = canonical_hash({k: v for k, v in p.items() if k != "record_binding_sha256"})
    return changed


def test_same_frame_complete_columns_physical_unquote_and_utf8_hashes(tmp_path):
    groups, flags = b'["0",\n "1"]', b'["1", "0"]'
    store, record, sample, raw, values = fixture(tmp_path, groups=groups, flags=flags)
    output = build(store, record, sample)
    assert output.annotation.groups == ((0,), (1,)) and output.annotation.flags == (1, 0)
    assert output.batch.targets[:, 0].tolist() == [1., 0.]
    for column in (GROUP_COLUMN, FLAG_COLUMN):
        proof = output.provenance["fields"][column]
        token = record.opaque_frame[proof["physical_token_start_in_frame"]:proof["physical_token_end_in_frame"]]
        assert token == quote(values[column])
        assert raw[proof["physical_token_start_in_file"]:proof["physical_token_end_in_file"]] == token
        assert proof["physical_csv_token_sha256"] == sha(token)
        assert proof["csv_unquoted_value_sha256"] == proof["decoded_field_utf8_sha256"] == sha(values[column])
        assert proof["physical_csv_token_sha256"] != proof["decoded_field_utf8_sha256"]
        assert proof["raw_frame_sha256"] == sha(record.opaque_frame)
    assert output.provenance["same_ingested_record_property_association_verified"] is True
    assert output.provenance["supervision_provenance_sha256"] == canonical_hash({
        k: v for k, v in output.provenance.items() if k != "supervision_provenance_sha256"})
    assert json.loads(json.dumps(output.provenance, allow_nan=False))["formal_eligible"] is False


def test_zero_is_native_zero_and_empty_group_preservation_is_explicit_not_author_replica(tmp_path):
    store, record, sample, _, _ = fixture(tmp_path, groups=b"['', '0,0', '1']", flags=b"[0, '1', 0]")
    output = build(store, record, sample)
    assert output.annotation.groups == ((), (0, 0), (1,))
    assert output.annotation.exact_author_ids == (0,) and output.batch.targets[:, 0].tolist() == [1., 0.]
    assert output.mapping.author_to_native == output.mapping.native_to_author == (0, 1)
    assert output.provenance["author_literal_loader_reproduced"] is False
    assert output.provenance["chemical_negative_truth_verified"] is False
    assert "drops empty groups" in output.provenance["author_difference"]


@pytest.mark.parametrize("groups,flags,state", [
    (b"[]", b"[]", "NO_GROUPS"), (b"['']", b"[1]", "EXACT_GROUPS_EMPTY"),
    (b"['']", b"[0]", "EMPTY_GROUPS"), (b"['0,1']", b"[0]", "EXTENDED_ONLY"),
])
def test_empty_and_extended_only_are_unknown_or_rejected_never_valid_all_negative(tmp_path, groups, flags, state):
    store, record, sample, _, _ = fixture(tmp_path, groups=groups, flags=flags)
    with pytest.raises(records.SourceRecordError):
        build(store, record, sample)
    output = build(store, record, sample, empty_policy="preserve_unknown")
    assert output.annotation.annotation_state == state
    assert output.batch.candidate_mask.all() and not output.batch.supervision_mask.any()
    assert torch.isnan(output.batch.targets).all()
    assert output.provenance["supervision_state"] == "UNKNOWN"


@pytest.mark.parametrize("options", [{"role": "final_test"}, {"role": None},
    {"label_policy": "author_binary_set"}, {"empty_policy": "author_zero"}])
def test_unsupported_or_implicit_policy_never_decodes_targets(tmp_path, monkeypatch, options):
    store, record, sample, _, _ = fixture(tmp_path)
    monkeypatch.setattr(records, "_az_annotation_fields", lambda *a: (_ for _ in ()).throw(AssertionError("target decoded")))
    with pytest.raises(records.SourceRecordError):
        build(store, record, sample, **options)
    with pytest.raises(TypeError):
        store.build_az_supervised_sample(record.record_id, sample=sample, role="train", empty_policy="reject")


def test_parser_retained_isotope_h_is_candidate_and_not_decremented_or_removed_again(tmp_path):
    store, record, sample, _, _ = fixture(tmp_path, smiles="[2H]CO")
    output = build(store, record, sample, role="train_inner_validation")
    assert record.structure.atomic_numbers == (1, 6, 8)
    assert output.mapping.author_to_native == (0, 1, 2) and output.mapping.deleted_native_ids == ()
    assert output.batch.targets[:, 0].tolist() == [1., 0., 0.]
    assert output.batch.candidate_mask.all() and output.batch.supervision_mask.all()
    assert output.mapping.provenance["additional_hydrogen_transform"] == "none"


@pytest.mark.parametrize("case", ["frame", "member", "same_element_permutation", "fp32", "fp64", "not_ready"])
def test_source_or_geometry_drift_rejects_before_annotation_extraction(tmp_path, monkeypatch, case):
    store, record, sample, _, _ = fixture(tmp_path, smiles="CCO")
    if case == "frame": sample = replace(sample, record=reseal_record(record, frame=record.opaque_frame + b" "))
    if case == "member":
        member = {**record.member, "fold": (record.member["fold"] + 1) % 10}
        sample = replace(sample, record=reseal_record(record, member=member))
    if case == "same_element_permutation":
        sample = replace(sample, record=reseal_record(record, mol=Chem.RenumberAtoms(record.structure.mol, [1, 0, 2])))
    if case == "fp32": sample.geometry.encoder_batch.pos[0, 0] += 1.
    if case == "fp64": sample.geometry.native_coordinates_float64[0, 0] += 1.
    if case == "not_ready": sample = replace(sample, status="NOT_READY", geometry=None)
    monkeypatch.setattr(records, "_az_annotation_fields", lambda *a: (_ for _ in ()).throw(AssertionError("target decoded")))
    with pytest.raises(records.SourceRecordError):
        build(store, record, sample)


def test_raw_only_record_and_nonselected_invalid_utf8_remain_opaque(tmp_path, monkeypatch):
    store, record, sample, _, _ = fixture(tmp_path, raw_only=True)
    assert store.record_ids == (record.record_id,)
    assert b"\xff" in record.opaque_frame and record.provenance["annotation_values_decoded"] is False
    output = build(store, record, sample)
    assert output.batch.targets[:, 0].tolist() == [1., 0.]
    monkeypatch.setattr(records, "_az_annotation_fields", lambda *a: (_ for _ in ()).throw(AssertionError("target decoded")))
    with pytest.raises(records.SourceRecordError):
        store.build_az_supervised_sample("az:Cmpd 2", sample=sample, role="train",
            label_policy="strict_exact_binary_set", empty_policy="reject")


@pytest.mark.parametrize("case", ["missing_column", "invalid_selected_utf8", "cardinality"])
def test_complete_selected_fields_fail_instead_of_prefix_decode_or_fallback(tmp_path, case):
    options = {}
    if case == "missing_column": options["columns"] = ["Compound ID", "SMILES", GROUP_COLUMN, "UNSELECTED_COMMENT"]
    if case == "invalid_selected_utf8": options["groups"] = b"['0']\xff"
    if case == "cardinality": options["flags"] = b"[]"
    store, record, sample, _, _ = fixture(tmp_path, **options)
    with pytest.raises(ValueError):
        build(store, record, sample)


def test_complete_direction_component_reparse_is_proved_without_touching_geometry(tmp_path, monkeypatch):
    store, record, sample, _, _ = fixture(tmp_path, smiles="F/C=C/Cl")
    changed = reseal_record(record, mol=direction_copy(record.structure.mol))
    before = sample.geometry.native_coordinates_float64.clone()
    monkeypatch.setattr(store, "get", lambda ref: changed)
    output = build(store, record, sample)
    assert output.mapping.provenance["ordered_pair_structure_verification"] == "VERIFIED_DIRECTION_COMPONENT_INVERSION"
    assert output.provenance["source_reparse_binding"]["direction_equivalence"]["status"] == "VERIFIED_DIRECTION_COMPONENT_INVERSION"
    assert output.batch.targets[:, 0].tolist() == [1., 0., 0., 0.]
    assert torch.equal(sample.geometry.native_coordinates_float64, before)


@pytest.mark.parametrize("case", ["partial_direction", "stereo"])
def test_unsupported_direction_or_stereo_change_rejects_before_target_decode(tmp_path, monkeypatch, case):
    store, record, sample, _, _ = fixture(tmp_path, smiles="F/C=C/Cl")
    altered = direction_copy(record.structure.mol, only_first=True) if case == "partial_direction" else Chem.Mol(record.structure.mol)
    if case == "stereo":
        next(b for b in altered.GetBonds() if b.GetBondType() == Chem.BondType.DOUBLE).SetStereo(Chem.BondStereo.STEREOZ)
    monkeypatch.setattr(store, "get", lambda ref: reseal_record(record, mol=altered))
    monkeypatch.setattr(records, "_az_annotation_fields", lambda *a: (_ for _ in ()).throw(AssertionError("target decoded")))
    with pytest.raises(records.SourceRecordError):
        build(store, record, sample)


def test_producer_is_owned_no_regeneration_or_file_reopen_and_inputs_rng_unchanged(tmp_path, monkeypatch):
    store, record, sample, _, _ = fixture(tmp_path)
    before = record.structure.mol.ToBinary(Chem.PropertyPickleOptions.AllProps)
    positions, coords, proof = sample.geometry.encoder_batch.pos.clone(), sample.geometry.native_coordinates_float64.clone(), deepcopy(sample.geometry.provenance)
    rng = torch.get_rng_state().clone()
    monkeypatch.setattr(Path, "open", lambda *a, **k: (_ for _ in ()).throw(AssertionError("unexpected IO")))
    monkeypatch.setattr("phychem_mfm.phase1.generated_geometry.prepare_native_generated_geometry",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not regenerate")))
    output = build(store, record, sample)
    assert output.mapping.provenance["mapping_provenance_sha256"] == canonical_hash({
        k: v for k, v in output.mapping.provenance.items() if k != "mapping_provenance_sha256"})
    assert torch.equal(rng, torch.get_rng_state()) and torch.equal(sample.geometry.encoder_batch.pos, positions)
    assert torch.equal(sample.geometry.native_coordinates_float64, coords) and sample.geometry.provenance == proof
    assert record.structure.mol.ToBinary(Chem.PropertyPickleOptions.AllProps) == before
    output.batch.encoder_batch.pos.zero_()
    output.batch.source_atom_ids.zero_()
    assert torch.equal(sample.geometry.encoder_batch.pos, positions) and sample.geometry.source_atom_ids.tolist() == [0, 1]


@pytest.mark.parametrize("case", ["smiles_hash", "cyp_filename", "permutation"])
def test_pure_az_map_binds_raw_smiles_and_rejects_cyp_profile_or_permutation(case):
    structure = read_az_raw_smiles("CCO")
    options = {"source_file": "az_120_compounds.csv", "source_file_sha256": "a" * 64,
               "source_record_1based": 1, "raw_frame_sha256": "b" * 64, "source_smiles_sha256": sha(b"CCO")}
    native = structure.mol
    if case == "smiles_hash": options["source_smiles_sha256"] = "c" * 64
    if case == "cyp_filename": options["source_file"] = "1A2.sdf"
    if case == "permutation": native = Chem.RenumberAtoms(native, [1, 0, 2])
    with pytest.raises(AZAtomMappingError):
        build_az_author_atom_mapping(native, "CCO", **options)


def test_actual_producer_batch_feeds_shared_h0_atom_readout_without_annotation_fields(tmp_path):
    store, record, sample, _, _ = fixture(tmp_path)
    output = build(store, record, sample)
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(39)
        config = small_config("light")
        config["backbone"].update(dim=8, heads=2, layers=1, dropout=0.)
        config["head"]["profile"] = "phase1"
        model = build_model(config).eval()
        readout = SourceAlignedH0Readout(8, 1, output_level="atom", hidden_dim=8).eval()
    assert set(output.batch.encoder_batch.keys()) == {"x", "pos", "batch", "ptr"}
    with torch.no_grad():
        h0 = model.encode_atoms(output.batch.encoder_batch)
        prediction = readout(h0, source_atom_ids=output.batch.source_atom_ids,
                             batch=output.batch.encoder_batch.batch, ptr=output.batch.encoder_batch.ptr)
    assert h0.shape == (2, 8) and torch.isfinite(h0).all()
    assert prediction.predictions.shape == (2, 1) and torch.isfinite(prediction.predictions).all()
    assert prediction.source_atom_ids.tolist() == [0, 1]
