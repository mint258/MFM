"""Synthetic source files only; no real benchmark annotations are consumed."""
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path

import pytest
from rdkit import Chem
from rdkit.Chem import rdDepictor
import torch

from conftest import small_config
from phychem_mfm.factory import build_model
from phychem_mfm.phase1.downstream_structures import read_cyp_mol_block, read_az_raw_smiles
from phychem_mfm.phase1.generated_geometry import prepare_native_generated_geometry
from phychem_mfm.phase1.identity import canonical_hash
from phychem_mfm.phase1.source_geometry import geometry_tensor_sha256
from phychem_mfm.phase1 import downstream_source_records as records
from phychem_mfm.phase1.downstream_source_records import (
    ClosedCandidateLedger, SourceRecordError, SourceRecordStore,
    materialize_geometry, source_ordered_graph_sha256,
)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def block(*, smiles="CO", three_d=False, native_h=False, interleave=False):
    mol = Chem.MolFromSmiles(smiles)
    if native_h:
        mol = Chem.AddHs(mol)
    if interleave:
        assert mol.GetNumAtoms() == 6
        mol = Chem.RenumberAtoms(mol, [2, 0, 3, 1, 4, 5])
    conf = Chem.Conformer(mol.GetNumAtoms())
    conf.Set3D(three_d)
    for i in range(mol.GetNumAtoms()):
        conf.SetAtomPosition(i, (float(i), float(i % 3), (i + 1) * .1234 if three_d else 0.))
    mol.AddConformer(conf)
    return Chem.MolToMolBlock(mol)


def frame(text, *, primary="1", other=b"opaque\xff\x00bytes", duplicate=False):
    raw = text.encode("utf8") + b"\n"
    if primary is not None:
        raw += b">  <PRIMARY_SOM>\n" + primary.encode("utf8") + b"\n\n"
        if duplicate:
            raw += b">  <PRIMARY_SOM>\n2\n\n"
    return raw + b">  <UNSELECTED_COMMENT>\n" + other + b"\n\n$$$$\n"


def parent(structure, *, ordinal, name=None, compound=None, uid=None, fold=3):
    source = {"dataset": "cyp_isoform" if name else "az_exactsom", "n_atoms": structure.n_atoms,
              "atomic_numbers": list(structure.atomic_numbers), "source_atom_map": list(structure.source_atom_map),
              "inchikey": structure.identity.inchikey, "ordered_graph_hash": source_ordered_graph_sha256(structure),
              "provenance": deepcopy(structure.provenance), "source_record_1based": ordinal}
    if name:
        source["source_file"] = name
    else:
        source["compound_id"] = compound
    member = {**deepcopy(source), "sample_uid": uid or f"synthetic::{name or compound}::{ordinal}", "fold": fold}
    if not name:
        member.pop("source_record_1based")  # Real AZ fold rows join through Compound ID.
    return source, member


def store_fixture(tmp_path, *, blocks=None, primaries=None, other=b"opaque\xff\x00bytes", az=False):
    blocks = blocks or [block()]
    primaries = primaries or ["1"] * len(blocks)
    name = "1A2.sdf"
    raw = b"".join(frame(text, primary=primary, other=other) for text, primary in zip(blocks, primaries))
    path = tmp_path / "cyp_isoform" / "raw" / name
    path.parent.mkdir(parents=True)
    path.write_bytes(raw)
    sources, members = [], []
    for ordinal, text in enumerate(blocks, 1):
        s, m = parent(read_cyp_mol_block(text), ordinal=ordinal, name=name)
        sources.append(s)
        members.append(m)
    files = {name: {"bytes": len(raw), "sha256": sha(raw)}}
    if az:
        # Quoted opaque targets contain comma, newline, doubled quote and invalid UTF8.
        csv = b'Compound ID,SMILES,final_target\r\n"Cmpd 1",CO,"opaque,\xff\n""text"""\r\nCmpd 2,CC,"\xff"\r\n'
        azpath = tmp_path / "az_exactsom" / "raw" / "az_120_compounds.csv"
        azpath.parent.mkdir(parents=True)
        azpath.write_bytes(csv)
        for ordinal, (compound, smiles) in enumerate((("Cmpd 1", "CO"), ("Cmpd 2", "CC")), 1):
            s, m = parent(read_az_raw_smiles(smiles), ordinal=ordinal, compound=compound)
            sources.append(s)
            if ordinal == 1:
                members.append(m)  # The second raw-only member must stay outside the loader.
        files[azpath.name] = {"bytes": len(csv), "sha256": sha(csv)}
    store = SourceRecordStore(tmp_path, source_files=files, source_rows=sources, member_rows=members)
    return store, files, sources, members


def candidate(record, *, sequence=0, ready=True):
    p, source = record.provenance, record.structure
    material = canonical_hash({"atomic_numbers": source.atomic_numbers,
                               "ordered_graph_hash": source_ordered_graph_sha256(source),
                               "recipe": "native_etkdgv3_mmff94_seed_v1"})
    seed = 1 + int(material[:8], 16) % (2**31 - 2)
    row = {"record_id": record.record_id, "sequence": sequence, "dataset": p["dataset"],
           "sample_uid": record.member["sample_uid"], "fold": record.member["fold"],
           "source_record_1based": p["source_record_1based"], "source_file": p["source_file"],
           "source_file_sha256": p["source_file_sha256"], "source_structure_sha256": p["structural_sha256"],
           "native_n_atoms": source.n_atoms, "seed": seed, "seed_material_sha256": material,
           "original_molecule_unchanged": True}
    if p["dataset"] == "az_exactsom":
        row["compound_id"] = record.record_id[3:]
    if ready:
        generated = prepare_native_generated_geometry(source, seed=seed)
        row.update(status="GENERATED_CANDIDATE_READY", geometry=deepcopy(generated.provenance),
                   native_atomic_numbers=list(source.atomic_numbers), source_atom_ids=list(range(source.n_atoms)),
                   generated_native_coordinates_float64=generated.native_coordinates_float64.tolist(),
                   encoder_native_coordinates_float32=generated.encoder_batch.pos.tolist())
    else:
        row.update(status="GENERATION_FAILED", failure_category="MMFF_NOT_CONVERGED")
    return seal(row)


def seal(row):
    row["record_provenance_sha256"] = canonical_hash({k: v for k, v in row.items() if k != "record_provenance_sha256"})
    return row


def ledger(tmp_path, rows, *, name="candidate_records.jsonl"):
    raw = b"".join((json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf8") for row in rows)
    path = tmp_path / name
    path.write_bytes(raw)
    return ClosedCandidateLedger(path, expected_sha256=sha(raw)), path, raw


def generated_fixture(tmp_path, *, primary="1", native_h=False, interleave=False, smiles="CO", other=b"opaque\xff"):
    text = block(smiles=smiles, native_h=native_h, interleave=interleave)
    store, _, _, _ = store_fixture(tmp_path, blocks=[text], primaries=[primary], other=other)
    record = store.get(store.record_ids[0])
    row = candidate(record)
    artifact, path, raw = ledger(tmp_path, [row])
    sample = materialize_geometry(record, candidates=artifact, source_units="angstrom")
    return store, record, row, artifact, sample, path, raw


def test_default_full_ingestion_decodes_only_structure_and_keeps_raw_only_outside(tmp_path):
    store, _, _, members = store_fixture(tmp_path, az=True)
    assert store.record_ids == tuple(records.source_reference(x) for x in members)
    assert store.record_ids == ("cyp:1A2.sdf:1", "az:Cmpd 1")
    cyp, az = store.get(store.record_ids[0]), store.get(store.record_ids[1])
    assert cyp.structure.atomic_numbers == az.structure.atomic_numbers == (6, 8)
    assert cyp.provenance["annotation_values_decoded"] is False
    assert az.provenance["annotation_values_decoded"] is False
    assert b"\xff" in cyp.opaque_frame and b"\xff" in az.opaque_frame
    assert az.provenance["raw_frame_sha256"] == sha(az.opaque_frame)
    with pytest.raises(SourceRecordError):
        store.get("az:Cmpd 2")


def test_ingestion_hashes_each_actual_file_once_not_per_record(tmp_path, monkeypatch):
    store, files, sources, members = store_fixture(tmp_path, blocks=[block(), block(smiles="CC")], az=True)
    original = Path.open
    opened = []
    def counted(self, *args, **kwargs):
        opened.append(self.name)
        return original(self, *args, **kwargs)
    monkeypatch.setattr(Path, "open", counted)
    store = SourceRecordStore(tmp_path, source_files=files, source_rows=sources, member_rows=members)
    assert opened == ["1A2.sdf", "az_120_compounds.csv"]
    for _ in range(2):
        for ref in store.record_ids:
            store.get(ref)
    assert opened == ["1A2.sdf", "az_120_compounds.csv"]


@pytest.mark.parametrize("field", ["sha256", "bytes"])
def test_actual_raw_binding_rejects_hash_or_size_drift(tmp_path, field):
    _, files, sources, members = store_fixture(tmp_path)
    files["1A2.sdf"][field] = "0" * 64 if field == "sha256" else 1
    with pytest.raises(SourceRecordError):
        SourceRecordStore(tmp_path, source_files=files, source_rows=sources, member_rows=members)


@pytest.mark.parametrize("field,value", [("atomic_numbers", [8, 6]), ("source_atom_map", [1, 0]),
    ("source_atom_map", [False, True]), ("ordered_graph_hash", "0" * 64), ("inchikey", "wrong"), ("n_atoms", 3)])
def test_parent_native_order_and_graph_are_checked_against_actual_source(tmp_path, field, value):
    _, files, sources, members = store_fixture(tmp_path)
    sources[0][field] = value
    store = SourceRecordStore(tmp_path, source_files=files, source_rows=sources, member_rows=members)
    with pytest.raises(SourceRecordError):
        store.get(store.record_ids[0])


@pytest.mark.parametrize("case", ["duplicate_source", "duplicate_member", "duplicate_uid", "unknown_member", "bad_fold", "bad_basename"])
def test_invalid_members_or_source_references_fail_without_reassigning(tmp_path, case):
    _, files, sources, members = store_fixture(tmp_path, blocks=[block(), block(smiles="CC")])
    if case == "duplicate_source": sources.append(deepcopy(sources[0]))
    if case == "duplicate_member": members.append(deepcopy(members[0]))
    if case == "duplicate_uid": members[1]["sample_uid"] = members[0]["sample_uid"]
    if case == "unknown_member": members[1]["source_record_1based"] = 99
    if case == "bad_fold": members[0]["fold"] = True
    if case == "bad_basename": files["../secret.sdf"] = files.pop("1A2.sdf")
    with pytest.raises(SourceRecordError):
        SourceRecordStore(tmp_path, source_files=files, source_rows=sources, member_rows=members)


def test_literal_same_element_row_permutation_cannot_reuse_source_bytes_binding(tmp_path):
    text = block(smiles="CC", three_d=True)
    store, files, sources, members = store_fixture(tmp_path, blocks=[text])
    lines = text.splitlines(keepends=True)
    lines[4], lines[5] = lines[5], lines[4]  # Both C, so element-only comparison would miss it.
    altered = frame("".join(lines))
    path = tmp_path / "cyp_isoform" / "raw" / "1A2.sdf"
    path.write_bytes(altered)
    files["1A2.sdf"] = {"bytes": len(altered), "sha256": sha(altered)}
    changed = SourceRecordStore(tmp_path, source_files=files, source_rows=sources, member_rows=members)
    with pytest.raises(SourceRecordError):
        changed.get(store.record_ids[0])


@pytest.mark.parametrize("case", ["missing_delimiter", "no_m_end", "oversize_total", "oversize_file"])
def test_actual_framing_and_ingestion_caps_fail(tmp_path, case):
    _, files, sources, members = store_fixture(tmp_path)
    path = tmp_path / "cyp_isoform" / "raw" / "1A2.sdf"
    raw = path.read_bytes()
    kwargs = {}
    if case == "missing_delimiter": raw = raw.rsplit(b"$$$$", 1)[0]
    if case == "no_m_end": raw = raw.replace(b"M  END", b"NOTEND")
    if case == "oversize_total": kwargs["max_total_bytes"] = 1
    if case == "oversize_file": kwargs["max_file_bytes"] = 1
    path.write_bytes(raw)
    files["1A2.sdf"] = {"bytes": len(raw), "sha256": sha(raw)}
    with pytest.raises(SourceRecordError):
        SourceRecordStore(tmp_path, source_files=files, source_rows=sources, member_rows=members, **kwargs)


def test_whitespace_only_after_final_sdf_delimiter_matches_existing_source_framer(tmp_path):
    _, files, sources, members = store_fixture(tmp_path)
    path = tmp_path / "cyp_isoform" / "raw" / "1A2.sdf"
    raw = path.read_bytes() + b"\n \r\n\t"
    path.write_bytes(raw)
    files["1A2.sdf"] = {"bytes": len(raw), "sha256": sha(raw)}
    store = SourceRecordStore(tmp_path, source_files=files, source_rows=sources, member_rows=members)
    assert len(store.record_ids) == 1
    assert store.get(store.record_ids[0]).structure.atomic_numbers == (6, 8)
    assert store.source_bindings["1A2.sdf"]["bytes"] == len(raw)


def test_csv_aggregate_frame_cap_is_checked_even_when_every_field_is_small(tmp_path, monkeypatch):
    raw = b"Compound ID,SMILES,t1,t2\nCmpd 1,CO," + b"a" * 40 + b"," + b"b" * 40 + b"\n"
    path = tmp_path / "az_exactsom" / "raw" / "az_120_compounds.csv"
    path.parent.mkdir(parents=True)
    path.write_bytes(raw)
    source, member = parent(read_az_raw_smiles("CO"), ordinal=1, compound="Cmpd 1")
    monkeypatch.setattr(records, "MAX_RECORD_BYTES", 64)
    with pytest.raises(SourceRecordError, match="CSV record"):
        SourceRecordStore(tmp_path, source_files={path.name: {"bytes": len(raw), "sha256": sha(raw)}},
                          source_rows=[source], member_rows=[member])


def test_generated_candidate_is_loaded_without_embedding_and_owned_arrays(tmp_path, monkeypatch):
    store, record, row, artifact, sample, _, raw = generated_fixture(tmp_path)
    before = record.structure.mol.ToBinary(Chem.PropertyPickleOptions.AllProps)
    rng = torch.get_rng_state().clone()
    monkeypatch.setattr("phychem_mfm.phase1.generated_geometry.prepare_native_generated_geometry",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not regenerate")))
    loaded = materialize_geometry(record, candidates=artifact, source_units="angstrom")
    assert loaded.status == "GEOMETRY_READY" and loaded.record is record
    assert set(loaded.geometry.encoder_batch.keys()) == {"x", "pos", "batch", "ptr"}
    assert loaded.geometry.native_coordinates_float64.dtype == torch.float64
    assert loaded.geometry.encoder_batch.pos.dtype == torch.float32
    assert loaded.geometry.native_coordinates_float64.tolist() == row["generated_native_coordinates_float64"]
    assert loaded.geometry.encoder_batch.pos.tolist() == row["encoder_native_coordinates_float32"]
    assert loaded.provenance["candidate_artifact"]["sha256"] == sha(raw)
    loaded.geometry.encoder_batch.pos.zero_()
    again = materialize_geometry(record, candidates=artifact, source_units="angstrom")
    assert torch.equal(again.geometry.encoder_batch.pos, sample.geometry.encoder_batch.pos)
    assert torch.equal(rng, torch.get_rng_state())
    assert record.structure.mol.ToBinary(Chem.PropertyPickleOptions.AllProps) == before


def test_original_3d_coords_and_failed_member_are_both_retained(tmp_path):
    store, _, _, members = store_fixture(tmp_path, blocks=[block(three_d=True), block(smiles="CC")])
    ready = store.get(store.record_ids[0])
    failed = store.get(store.record_ids[1])
    artifact, _, _ = ledger(tmp_path, [candidate(failed, ready=False)])
    source_sample = materialize_geometry(ready, candidates=artifact, source_units="angstrom")
    assert source_sample.provenance["geometry_basis"] == "ORIGINAL_SOURCE_3D"
    assert source_sample.geometry.encoder_batch.pos.tolist() == torch.tensor([
        [float(i), float(i % 3), round((i + 1) * .1234, 4)] for i in range(2)], dtype=torch.float32).tolist()
    not_ready = materialize_geometry(failed, candidates=artifact, source_units="angstrom")
    assert not_ready.status == "NOT_READY" and not_ready.geometry is None
    assert not_ready.provenance["failure_category"] == "MMFF_NOT_CONVERGED"
    assert not_ready.record.member == members[1] and len(store.record_ids) == 2


@pytest.mark.parametrize("field", ["sample_uid", "fold", "source_record_1based", "source_file_sha256", "source_structure_sha256", "native_n_atoms", "seed"])
def test_resealed_candidate_cannot_cross_source_member_or_seed_contract(tmp_path, field):
    store, record, row, _, _, _, _ = generated_fixture(tmp_path)
    row[field] = row[field] + 1 if type(row[field]) is int else "0" * 64
    seal(row)
    # Invalid reference mutation fails at ingestion; otherwise at materialization.
    with pytest.raises(SourceRecordError):
        artifact, _, _ = ledger(tmp_path, [row], name="tampered.jsonl")
        materialize_geometry(record, candidates=artifact, source_units="angstrom")


@pytest.mark.parametrize("case", ["fp64", "fp32", "source_ids", "bool_ids", "tensor_hash", "geometry_sha", "recipe", "native_graph", "signed_zero", "false_truth"])
def test_resealed_rows_still_verify_coordinates_typed_receipts_and_maps(tmp_path, case):
    _, record, row, _, _, _, _ = generated_fixture(tmp_path)
    if case == "fp64": row["generated_native_coordinates_float64"][0][0] += .125
    if case == "fp32": row["encoder_native_coordinates_float32"][0][0] += .125
    if case == "source_ids": row["source_atom_ids"] = [1, 0]
    if case == "bool_ids": row["source_atom_ids"] = [False, True]
    if case == "tensor_hash": row["geometry"]["encoder_tensor_hashes"]["pos"] = "0" * 64
    if case == "geometry_sha": row["geometry"]["geometry_provenance_sha256"] = "0" * 64
    if case == "recipe": row["geometry"]["recipe"]["mmff_max_iterations"] = 501
    if case == "native_graph": row["geometry"]["source_native_graph_sha256"] = "0" * 64
    if case == "false_truth": row["geometry"]["chemical_geometry_independently_verified"] = True
    if case == "signed_zero":
        row["generated_native_coordinates_float64"][0][0] = -0.0
        row["encoder_native_coordinates_float32"][0][0] = 0.0
    if case not in ("geometry_sha",):
        row["geometry"]["recipe_sha256"] = canonical_hash(row["geometry"]["recipe"])
        row["geometry"]["geometry_provenance_sha256"] = canonical_hash({k: v for k, v in row["geometry"].items() if k != "geometry_provenance_sha256"})
    artifact, _, _ = ledger(tmp_path, [seal(row)], name="resealed.jsonl")
    with pytest.raises(SourceRecordError):
        materialize_geometry(record, candidates=artifact, source_units="angstrom")


@pytest.mark.parametrize("case", ["tail", "file_sha", "duplicate", "cursor", "failure_geometry", "row_sha", "max_bytes"])
def test_closed_candidate_ledger_failures_are_not_successes(tmp_path, case):
    store, _, _, _ = store_fixture(tmp_path)
    row = candidate(store.get(store.record_ids[0]), ready=False)
    if case == "cursor": row["sequence"] = 1;seal(row)
    if case == "failure_geometry": row["geometry"] = {};seal(row)
    if case == "row_sha": row["record_provenance_sha256"] = "0" * 64
    raw = (json.dumps(row) + "\n").encode("utf8")
    if case == "tail": raw = raw[:-1]
    if case == "duplicate": raw += raw
    path = tmp_path / "bad.jsonl"
    path.write_bytes(raw)
    kwargs = {"max_bytes": 1} if case == "max_bytes" else {}
    with pytest.raises(SourceRecordError):
        ClosedCandidateLedger(path, expected_sha256="0" * 64 if case == "file_sha" else sha(raw), **kwargs)


def test_same_record_primary_projection_handles_interleaved_native_h_and_opaque_other(tmp_path):
    store, record, _, _, sample, _, _ = generated_fixture(tmp_path, native_h=True, interleave=True)
    result = store.build_cyp_supervised_sample(record.record_id, sample=sample, role="train", empty_policy="reject")
    assert result.mapping.author_to_native == (1, 3)
    assert result.annotation.labels == (None, 1, None, 0, None, None)
    assert result.batch.source_atom_ids.tolist() == [0, 1, 2, 3, 4, 5]
    assert result.batch.candidate_mask[:, 0].tolist() == [False, True, False, True, False, False]
    assert result.batch.supervision_mask[:, 0].tolist() == [False, True, False, True, False, False]
    assert torch.isnan(result.batch.targets[[0, 2, 4, 5]]).all()
    assert result.batch.targets[[1, 3], 0].tolist() == [1., 0.]
    proof = result.provenance["property"]
    raw_property = record.opaque_frame[proof["property_start_in_frame"]:proof["property_end_in_frame"]]
    assert raw_property == b"1\n" and proof["raw_property_sha256"] == sha(raw_property)
    assert proof["decoded_property_utf8_sha256"] == sha(b"1")
    assert proof["raw_property_sha256"] != proof["decoded_property_utf8_sha256"]
    assert result.provenance["same_ingested_record_property_association_verified"] is True
    assert result.provenance["annotation_truth_verified"] is result.provenance["formal_eligible"] is False


def test_native_isotope_h_that_author_keeps_remains_candidate(tmp_path):
    store, record, _, _, sample, _, _ = generated_fixture(tmp_path, smiles="[2H]CO")
    result = store.build_cyp_supervised_sample(record.record_id, sample=sample, role="train_inner_validation", empty_policy="reject")
    assert record.structure.atomic_numbers == (1, 6, 8)
    assert result.mapping.author_to_native == (0, 1, 2)
    assert result.annotation.labels == (1, 0, 0)
    assert result.batch.candidate_mask.all() and result.batch.role == "train_inner_validation"


@pytest.mark.parametrize("policy,expected", [("preserve_unknown", False), ("author_zero", True)])
def test_present_empty_requires_explicit_unknown_or_author_code_zero_policy(tmp_path, policy, expected):
    store, record, _, _, sample, _, _ = generated_fixture(tmp_path, primary="")
    result = store.build_cyp_supervised_sample(record.record_id, sample=sample, role="train", empty_policy=policy)
    assert result.batch.supervision_mask.all().item() == expected
    assert torch.isnan(result.batch.targets).all().item() == (not expected)
    assert result.provenance["formal_eligible"] is False


@pytest.mark.parametrize("case", ["missing", "duplicate", "invalid_selected_utf8", "ambiguous_terminator", "bad_token"])
def test_real_property_framing_rejects_ambiguous_or_invalid_selected_field(tmp_path, case):
    text = block()
    raw = frame(text, primary=None if case == "missing" else "1,2" if case == "bad_token" else "1", duplicate=case == "duplicate")
    if case == "invalid_selected_utf8": raw = raw.replace(b"<PRIMARY_SOM>\n1", b"<PRIMARY_SOM>\n\xff")
    if case == "ambiguous_terminator": raw = raw.replace(b"1\n\n>  <UNSELECTED_COMMENT>", b"1\n>  <UNSELECTED_COMMENT>")
    _, files, sources, members = store_fixture(tmp_path, blocks=[text])
    (tmp_path / "cyp_isoform" / "raw" / "1A2.sdf").write_bytes(raw)
    files["1A2.sdf"] = {"sha256": sha(raw), "bytes": len(raw)}
    store = SourceRecordStore(tmp_path, source_files=files, source_rows=sources, member_rows=members)
    record = store.get(store.record_ids[0])
    artifact, _, _ = ledger(tmp_path, [candidate(record)])
    sample = materialize_geometry(record, candidates=artifact, source_units="angstrom")
    with pytest.raises(ValueError):
        store.build_cyp_supervised_sample(record.record_id, sample=sample, role="train", empty_policy="reject")


def test_property_header_lookalike_inside_other_value_stays_opaque(tmp_path):
    store, record, _, _, sample, _, _ = generated_fixture(tmp_path, other=b"opaque\xff\n>  <PRIMARY_SOM>\n9999")
    output = store.build_cyp_supervised_sample(record.record_id, sample=sample, role="train", empty_policy="reject")
    assert output.annotation.positive_author_ids == (0,)


@pytest.mark.parametrize("role", ["final_test", "test", "validation", None])
def test_final_or_implicit_role_never_enters_target_extraction(tmp_path, role, monkeypatch):
    store, record, _, _, sample, _, _ = generated_fixture(tmp_path)
    monkeypatch.setattr(records, "_primary_property", lambda *a: (_ for _ in ()).throw(AssertionError("must stay opaque")))
    with pytest.raises(SourceRecordError):
        store.build_cyp_supervised_sample(record.record_id, sample=sample, role=role, empty_policy="reject")


def test_geometry_from_other_record_cannot_be_used_for_primary_supervision(tmp_path):
    store, _, _, _ = store_fixture(tmp_path, blocks=[block(), block(smiles="CC")])
    first, second = (store.get(x) for x in store.record_ids)
    artifact, _, _ = ledger(tmp_path, [candidate(first), candidate(second, sequence=1)])
    sample = materialize_geometry(first, candidates=artifact, source_units="angstrom")
    with pytest.raises(SourceRecordError):
        store.build_cyp_supervised_sample(second.record_id, sample=sample, role="train", empty_policy="reject")


def test_changed_live_native_graph_and_returned_metadata_are_not_silent(tmp_path):
    store, record, _, artifact, _, _, _ = generated_fixture(tmp_path)
    record.structure.mol.GetAtomWithIdx(0).SetFormalCharge(1)
    with pytest.raises(SourceRecordError):
        materialize_geometry(record, candidates=artifact, source_units="angstrom")
    unchanged = store.get(store.record_ids[0])
    assert unchanged.structure.mol.GetAtomWithIdx(0).GetFormalCharge() == 0
    mutable = artifact.binding
    mutable["sha256"] = "0" * 64
    assert artifact.binding["sha256"] != mutable["sha256"]


def test_actual_loaded_geometry_feeds_shared_h0_with_no_property_or_label_field(tmp_path):
    store, record, _, _, sample, _, _ = generated_fixture(tmp_path)
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(35)
        config = small_config("light")
        config["backbone"].update(dim=8, heads=2, layers=1, dropout=0.)
        config["head"]["profile"] = "phase1"
        model = build_model(config).eval()
    before = {k: v.clone() if torch.is_tensor(v) else deepcopy(v) for k, v in model.state_dict().items()}
    with torch.no_grad():
        h0 = model.encode_atoms(sample.geometry.encoder_batch)
    assert h0.shape == (record.structure.n_atoms, 8) and torch.isfinite(h0).all()
    assert set(sample.geometry.encoder_batch.keys()) == {"x", "pos", "batch", "ptr"}
    assert all(torch.equal(v, before[k]) if torch.is_tensor(v) else v == before[k] for k, v in model.state_dict().items())


SIGNED = (Chem.BondDir.ENDUPRIGHT, Chem.BondDir.ENDDOWNRIGHT)


def direction_copy(mol, *, only_first=False):
    copied = Chem.Mol(mol)
    ids = [b.GetIdx() for b in copied.GetBonds() if b.GetBondDir() in SIGNED]
    assert len(ids) >= 2
    for index in ids[:1] if only_first else ids:
        bond = copied.GetBondWithIdx(index)
        bond.SetBondDir(SIGNED[1] if bond.GetBondDir() == SIGNED[0] else SIGNED[0])
    return copied


def graph_rebound(record, mol):
    structure = replace(record.structure, mol=mol)
    proof = deepcopy(record.provenance)
    proof['native_graph_sha256'] = canonical_hash(records._native_graph(structure))
    proof['record_binding_sha256'] = canonical_hash({k: v for k, v in proof.items() if k != 'record_binding_sha256'})
    return replace(record, structure=structure, provenance=proof)


def direction_fixture(tmp_path):
    mol = Chem.MolFromSmiles('F/C=C/F')
    rdDepictor.Compute2DCoords(mol)
    text = Chem.MolToMolBlock(mol)
    store, _, _, _ = store_fixture(tmp_path, blocks=[text], primaries=['1'])
    record = store.get(store.record_ids[0])
    assert len([b for b in record.structure.mol.GetBonds() if b.GetBondDir() in SIGNED]) == 2
    assert next(b for b in record.structure.mol.GetBonds() if b.GetBondType() == Chem.BondType.DOUBLE).GetStereo() == Chem.BondStereo.STEREOE
    flipped = graph_rebound(record, direction_copy(record.structure.mol))
    # A genuine candidate is generated from the other complete direction gauge;
    # only its saved receipt representation differs from the current source.
    row = candidate(flipped)
    artifact, path, raw = ledger(tmp_path, [row])
    return store, record, flipped, row, artifact, path, raw


def reseal_geometry(row):
    proof = row['geometry']
    proof['geometry_provenance_sha256'] = canonical_hash({k: v for k, v in proof.items() if k != 'geometry_provenance_sha256'})
    return seal(row)


def test_saved_whole_direction_gauge_uses_one_proof_and_preserves_saved_geometry(tmp_path, monkeypatch):
    previous = Chem.GetUseLegacyStereoPerception()
    Chem.SetUseLegacyStereoPerception(True)
    try:
        _, record, flipped, row, artifact, path, raw = direction_fixture(tmp_path)
        before = record.structure.mol.ToBinary(Chem.PropertyPickleOptions.AllProps)
        rng = torch.get_rng_state().clone()
        calls, actual = [], records.verify_cyp_direction_equivalence
        def observed(candidate_mol, counterpart):
            calls.append((candidate_mol, counterpart))
            return actual(candidate_mol, counterpart)
        monkeypatch.setattr(records, 'verify_cyp_direction_equivalence', observed)
        monkeypatch.setattr('phychem_mfm.phase1.generated_geometry.prepare_native_generated_geometry',
                            lambda *a, **k: (_ for _ in ()).throw(AssertionError('must not regenerate')))
        sample = materialize_geometry(record, candidates=artifact, source_units='angstrom')
        assert len(calls) == 1 and calls[0][0] is record.structure.mol
        binding = sample.provenance['native_source_graph_binding']
        assert binding['status'] == 'VERIFIED_SAVED_NATIVE_DIRECTION_COMPONENT_INVERSION'
        assert binding['literal_native_graph_hash_match'] is False
        assert binding['current_native_graph_sha256'] == record.provenance['native_graph_sha256']
        assert binding['saved_native_graph_sha256'] == flipped.provenance['native_graph_sha256']
        assert binding['matched_copy_native_graph_sha256'] == flipped.provenance['native_graph_sha256']
        assert binding['search']['assignments_examined'] == 4 and binding['search']['unique_digest_match'] is True
        assert binding['historical_source_molecule_recovered'] is False
        assert binding['source_original_direction_flags_modified'] is False
        assert binding['reconstruction_copy_direction_flags_modified'] is True
        assert binding['native_source_graph_binding_sha256'] == canonical_hash({k: v for k, v in binding.items() if k != 'native_source_graph_binding_sha256'})
        assert sample.provenance['schema_version'] == 'phase1_source_materialized_geometry_v2'
        assert sample.geometry.provenance == row['geometry']
        assert sample.geometry.native_coordinates_float64.tolist() == row['generated_native_coordinates_float64']
        assert sample.geometry.encoder_batch.pos.tolist() == row['encoder_native_coordinates_float32']
        assert sample.geometry.source_atom_ids.tolist() == list(range(record.structure.n_atoms))
        assert record.structure.mol.ToBinary(Chem.PropertyPickleOptions.AllProps) == before
        assert path.read_bytes() == raw and torch.equal(torch.get_rng_state(), rng)
    finally:
        Chem.SetUseLegacyStereoPerception(previous)


def test_exact_saved_hash_keeps_legacy_independent_path(tmp_path, monkeypatch):
    _, record, _, artifact, _, _, _ = generated_fixture(tmp_path)
    monkeypatch.setattr(records, 'verify_cyp_direction_equivalence',
                        lambda *a: (_ for _ in ()).throw(AssertionError('exact digest must not invoke decoder')))
    previous = Chem.GetUseLegacyStereoPerception()
    Chem.SetUseLegacyStereoPerception(False)
    try:
        sample = materialize_geometry(record, candidates=artifact, source_units='angstrom')
        binding = sample.provenance['native_source_graph_binding']
        assert binding['status'] == 'EXACT_NATIVE_GRAPH_HASH' and binding['search']['performed'] is False
        assert binding['direction_equivalence'] is None and binding['literal_native_graph_hash_match'] is True
    finally:
        Chem.SetUseLegacyStereoPerception(previous)


@pytest.mark.parametrize('case', ['partial_flip', 'isotope', 'stereo', 'fp32', 'source_proof'])
def test_gauge_path_cannot_bypass_partial_or_other_saved_guards(tmp_path, case, monkeypatch):
    previous = Chem.GetUseLegacyStereoPerception()
    Chem.SetUseLegacyStereoPerception(True)
    try:
        _, record, _, row, _, _, _ = direction_fixture(tmp_path)
        if case in ('partial_flip', 'isotope', 'stereo'):
            changed = direction_copy(record.structure.mol, only_first=case == 'partial_flip')
            if case == 'isotope': changed.GetAtomWithIdx(0).SetIsotope(19)
            if case == 'stereo':
                next(b for b in changed.GetBonds() if b.GetBondType() == Chem.BondType.DOUBLE).SetStereo(Chem.BondStereo.STEREOZ)
            row['geometry']['source_native_graph_sha256'] = canonical_hash(records._native_graph(replace(record.structure, mol=changed)))
        elif case == 'fp32': row['encoder_native_coordinates_float32'][0][0] += .125
        else:
            row['geometry']['source_sha256'] = '0' * 64
            monkeypatch.setattr(records, '_saved_native_graph_binding',
                                lambda *a: (_ for _ in ()).throw(AssertionError('source guard must precede reconstruction')))
        artifact, _, raw = ledger(tmp_path, [reseal_geometry(row)], name='bad_direction.jsonl')
        before = record.structure.mol.ToBinary(Chem.PropertyPickleOptions.AllProps)
        with pytest.raises(SourceRecordError):
            materialize_geometry(record, candidates=artifact, source_units='angstrom')
        assert record.structure.mol.ToBinary(Chem.PropertyPickleOptions.AllProps) == before
    finally:
        Chem.SetUseLegacyStereoPerception(previous)


def test_changed_direction_requires_legacy_and_cyp_scope(tmp_path):
    previous = Chem.GetUseLegacyStereoPerception()
    Chem.SetUseLegacyStereoPerception(True)
    try:
        _, record, _, _, artifact, _, _ = direction_fixture(tmp_path)
        Chem.SetUseLegacyStereoPerception(False)
        with pytest.raises(SourceRecordError):
            materialize_geometry(record, candidates=artifact, source_units='angstrom')
        Chem.SetUseLegacyStereoPerception(True)
        store, _, _, _ = store_fixture(tmp_path / 'az', az=True)
        az = store.get('az:Cmpd 1')
        row = candidate(az)
        row['geometry']['source_native_graph_sha256'] = '0' * 64
        az_artifact, _, _ = ledger(tmp_path / 'az', [reseal_geometry(row)])
        with pytest.raises(SourceRecordError, match='ready CYP mol blocks'):
            materialize_geometry(az, candidates=az_artifact, source_units='angstrom')
    finally:
        Chem.SetUseLegacyStereoPerception(previous)


def test_direction_reconstruction_bound_rejects_more_than_eight_signed_bonds(tmp_path):
    mol = Chem.MolFromSmiles('F/C=C/C=C/C=C/C=C/C=C/C=C/C=C/C=C/F')
    rdDepictor.Compute2DCoords(mol)
    source = read_cyp_mol_block(Chem.MolToMolBlock(mol))
    mol = source.mol
    Chem.SetDoubleBondNeighborDirections(mol)
    assert len([b for b in mol.GetBonds() if b.GetBondDir() in SIGNED]) > 8
    before = mol.ToBinary(Chem.PropertyPickleOptions.AllProps)
    with pytest.raises(SourceRecordError, match='signed SINGLE scope'):
        records._saved_native_graph_binding({'dataset': 'cyp_isoform', 'status': 'GENERATED_CANDIDATE_READY'}, source, '0' * 64)
    assert mol.ToBinary(Chem.PropertyPickleOptions.AllProps) == before


def test_same_raw_record_direction_reparse_preserves_supervision_and_geometry(tmp_path, monkeypatch):
    previous = Chem.GetUseLegacyStereoPerception()
    Chem.SetUseLegacyStereoPerception(True)
    try:
        store, record, flipped, _, artifact, _, _ = direction_fixture(tmp_path)
        sample = materialize_geometry(record, candidates=artifact, source_units='angstrom')
        # Both calls still use the real same-record PRIMARY extractor, supplier,
        # native-author mapper and decoder; only the fresh reader gauge differs.
        monkeypatch.setattr(store, 'get', lambda ref: record)
        baseline = store.build_cyp_supervised_sample(record.record_id, sample=sample, role='train', empty_policy='reject')
        monkeypatch.setattr(store, 'get', lambda ref: flipped)
        geometry_before = deepcopy(sample.geometry.provenance)
        positions_before = sample.geometry.encoder_batch.pos.clone()
        originals = (record.structure.mol.ToBinary(Chem.PropertyPickleOptions.AllProps), flipped.structure.mol.ToBinary(Chem.PropertyPickleOptions.AllProps))
        result = store.build_cyp_supervised_sample(record.record_id, sample=sample, role='train', empty_policy='reject')
        proof = result.provenance['source_reparse_binding']
        assert result.provenance['schema_version'] == 'phase1_source_bound_cyp_supervision_v2'
        assert proof['literal_record_binding_hash_match'] is False
        assert proof['sample_record_binding_sha256'] == record.provenance['record_binding_sha256']
        assert proof['fresh_record_binding_sha256'] == flipped.provenance['record_binding_sha256']
        assert proof['direction_equivalence']['status'] == 'VERIFIED_DIRECTION_COMPONENT_INVERSION'
        assert proof['source_reparse_binding_sha256'] == canonical_hash({k: v for k, v in proof.items() if k != 'source_reparse_binding_sha256'})
        assert result.annotation.labels == baseline.annotation.labels == (1, 0, 0, 0)
        assert result.annotation.candidate_mask == baseline.annotation.candidate_mask
        assert result.annotation.supervision_mask == baseline.annotation.supervision_mask
        for key in ('targets', 'candidate_mask', 'supervision_mask', 'source_atom_ids'):
            assert torch.equal(getattr(result.batch, key), getattr(baseline.batch, key))
        assert torch.equal(result.batch.encoder_batch.pos, baseline.batch.encoder_batch.pos)
        assert torch.equal(sample.geometry.encoder_batch.pos, positions_before)
        assert sample.geometry.provenance == geometry_before
        assert (record.structure.mol.ToBinary(Chem.PropertyPickleOptions.AllProps), flipped.structure.mol.ToBinary(Chem.PropertyPickleOptions.AllProps)) == originals
    finally:
        Chem.SetUseLegacyStereoPerception(previous)


@pytest.mark.parametrize('case', ['raw_frame', 'member', 'coordinates'])
def test_reparse_drift_rejected_before_selected_property_decode(tmp_path, case, monkeypatch):
    store, record, _, _, sample, _, _ = generated_fixture(tmp_path)
    fresh = graph_rebound(record, Chem.Mol(record.structure.mol))
    if case == 'raw_frame':
        raw = fresh.opaque_frame.replace(b'opaque', b'changed')
        proof = deepcopy(fresh.provenance)
        proof['raw_frame_sha256'] = sha(raw)
        fresh = replace(fresh, opaque_frame=raw, provenance=proof)
    elif case == 'member':
        member, proof = deepcopy(fresh.member), deepcopy(fresh.provenance)
        member['sample_uid'] += 'different'
        proof['sample_uid'] = member['sample_uid']
        proof['parent_member_row_sha256'] = canonical_hash(member)
        fresh = replace(fresh, member=member, provenance=proof)
    else:
        conformer = fresh.structure.mol.GetConformer()
        xyz = conformer.GetAtomPosition(0)
        conformer.SetAtomPosition(0, (xyz.x + .125, xyz.y, xyz.z))
    proof = deepcopy(fresh.provenance)
    proof['record_binding_sha256'] = canonical_hash({k: v for k, v in proof.items() if k != 'record_binding_sha256'})
    fresh = replace(fresh, provenance=proof)
    monkeypatch.setattr(store, 'get', lambda ref: fresh)
    monkeypatch.setattr(records, '_primary_property', lambda *a: (_ for _ in ()).throw(AssertionError('must remain opaque')))
    with pytest.raises(SourceRecordError):
        store.build_cyp_supervised_sample(record.record_id, sample=sample, role='train', empty_policy='reject')
