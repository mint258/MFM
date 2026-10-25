"""Real frozen CYP decoder regression for the source sample attribute seam."""
from copy import deepcopy
from dataclasses import replace
import math
from types import SimpleNamespace

import pytest
from rdkit import Chem, rdBase

from test_model_v3_selected_training_store import source_modules
from test_phase1_downstream_source_records import block, store_fixture, candidate, ledger
from phychem_mfm.phase1 import downstream_source_records as records
from phychem_mfm.phase1.som_atom_mapping import build_cyp_author_atom_mapping
from phychem_mfm.phase1.som_annotation import decode_cyp_primary_annotation
from phychem_mfm.phase1.az_atom_mapping import build_az_author_atom_mapping
from phychem_mfm.phase1.az_annotation import parse_az_exact_groups
from phychem_mfm.phase1.v3_source_sample_compat import CompatibleSourceRecords, checked_existing_binding
from phychem_mfm.phase1.v3_selected_training_store import FrozenSelectedDecoder, SelectedTrainingStoreError


TASKS = ['1A2', '2A6', '2B6', '2C19', '2C8', '2C9', '2D6', '2E1', '3A4']


def fixture(tmp_path, kind):
    blocks = [block(three_d=True), block(smiles='CC')] if kind == 'source3D' else [block()]
    _, files, sources, members = store_fixture(tmp_path, blocks=blocks)
    # The old generic reader fixture omits this original-membership field;
    # the frozen full-source join correctly requires it. Declare it explicitly
    # before ingestion so all native member-row/record hashes bind that field.
    members = [{**member, 'sample_id': 'synthetic_sample_'+str(i+1)} for i, member in enumerate(members)]
    store = records.SourceRecordStore(tmp_path, source_files=files, source_rows=sources, member_rows=members)
    record = store.get(store.record_ids[0])
    if kind == 'source3D':
        other = store.get(store.record_ids[1])
        artifact, _, _ = ledger(tmp_path, [candidate(other, ready=False)])
    else:
        artifact, _, _ = ledger(tmp_path, [candidate(record, ready=kind != 'failed')])
    sample = records.materialize_geometry(record, candidates=artifact, source_units='angstrom')
    p = record.provenance; geometry = sample.geometry
    member = {'dataset': 'cyp_isoform', 'member_index': 0, 'member_uid': record.member['sample_uid'],
        'sample_id': record.member['sample_id'], 'fold': record.member['fold'], 'inchikey': record.structure.identity.inchikey,
        'source_frame': {'source_file': store.source_bindings[p['source_file']], 'record_id': record.record_id,
            'source_record_1based': p['source_record_1based'], 'structure_sha256': p['structural_sha256']},
        'geometry_artifact_ref': {'record_id': record.record_id, 'native_n_atoms': record.structure.n_atoms,
            'status': sample.status, 'kind': ('original_source_3d' if kind == 'source3D' else
                'not_ready' if kind == 'failed' else 'cached_generated')}}
    if geometry is not None:
        member['geometry_artifact_ref'].update(geometry_provenance_sha256=geometry.provenance['geometry_provenance_sha256'],
            encoder_tensor_hashes=geometry.provenance['encoder_tensor_hashes'])
    return store, record, artifact, sample, member


def modules(source_module):
    return (source_module, Chem, rdBase, build_cyp_author_atom_mapping, decode_cyp_primary_annotation,
            build_az_author_atom_mapping, parse_az_exact_groups)


@pytest.mark.parametrize('kind', ['source3D', 'cached'])
def test_frozen_som_payload_uses_exact_existing_provenance_without_new_binding(tmp_path, source_modules, kind):
    native, old_decoder, graph = source_modules
    store, record, artifact, sample, member = fixture(tmp_path, kind)
    source_bytes = record.structure.mol.ToBinary(Chem.PropertyPickleOptions.AllProps)
    original_proof = deepcopy(sample.provenance)
    assert not hasattr(sample, 'native_source_graph_binding')
    # Reproduce the actual legacy seam using the unmodified frozen decoder,
    # real source reader, original atom mapping, and only synthetic annotations.
    with pytest.raises(AttributeError, match='native_source_graph_binding'):
        old_decoder.som_payload(member, store, artifact, TASKS, modules(records))
    projected = CompatibleSourceRecords(records)
    view = projected.materialize_geometry(record, candidates=artifact, source_units='angstrom')
    assert view.record is record and view.geometry.provenance == sample.geometry.provenance
    assert view.provenance == original_proof
    assert view.native_source_graph_binding == original_proof['native_source_graph_binding']
    if kind == 'source3D':
        assert view.native_source_graph_binding is None  # Existing declared not-applicable value.
    else:
        copied = view.native_source_graph_binding
        assert copied and copied['current_native_graph_sha256'] == record.provenance['native_graph_sha256']
        copied['status'] = 'caller mutation'
        assert view.native_source_graph_binding == original_proof['native_source_graph_binding']
    row = {'member_index': 0, 'member_uid': member['member_uid'], 'original_member': member,
        'original_member_row_sha256': native.canonical(member), 'native_n_atoms': record.structure.n_atoms, 'selected_role': 'train'}
    plan = {'records': {'cyp_isoform': [row]}, 'contracts': {'cyp_isoform': {'tasks': TASKS}}}
    selected = FrozenSelectedDecoder({'native': native, 'decoder': old_decoder, 'graph': graph}, plan)
    selected.som_store, selected.candidates, selected.som_modules = store, artifact, modules(projected)
    actual = selected.decode('cyp_isoform', 0, role='train')
    assert [r[0] for r in actual['targets']] == [1., 0.]
    assert all(r[0] for r in actual['candidate']) and all(r[0] for r in actual['supervision'])
    assert all(math.isnan(r[t]) for r in actual['targets'] for t in range(1, 9))
    assert all(not r[t] for r in actual['supervision'] for t in range(1, 9))
    if kind == 'source3D':
        # The original SourceEncoderGeometry retains FP32 tensors and a sealed
        # FP64 hash. Independently read exact doubles from that same conformer;
        # never use FP32-to-FP64 promotion as the expected source coordinates.
        conformer = record.structure.mol.GetConformer()
        expected64 = [[conformer.GetAtomPosition(i).x, conformer.GetAtomPosition(i).y,
            conformer.GetAtomPosition(i).z] for i in range(record.structure.n_atoms)]
    else:
        expected64 = sample.geometry.native_coordinates_float64.tolist()
    assert actual['coordinates'] == expected64
    assert actual['coordinates'] is not None  # Valid source3D must stay ready in the native writer.
    import torch
    coordinates64 = torch.tensor(actual['coordinates'], dtype=torch.float64)
    expected_hash = (sample.geometry.provenance['source_coordinates_float64_sha256'] if kind == 'source3D'
        else records.geometry_tensor_sha256(sample.geometry.native_coordinates_float64))
    assert records.geometry_tensor_sha256(coordinates64) == expected_hash
    assert records.geometry_tensor_sha256(coordinates64.to(torch.float32)) == sample.geometry.provenance['encoder_tensor_hashes']['pos']
    packed = native.record_bytes(actual['x'], actual['coordinates'], actual['targets'], actual['candidate'], actual['supervision'])
    import struct
    assert struct.unpack_from('<4I', packed)[3] == 1
    assert actual['source_proof']['native_source_graph_binding'] == original_proof['native_source_graph_binding']
    assert sample.provenance == original_proof
    assert record.structure.mol.ToBinary(Chem.PropertyPickleOptions.AllProps) == source_bytes
    with pytest.raises(SelectedTrainingStoreError, match='allowlist'):
        selected.decode('cyp_isoform', 99, role='train')


@pytest.mark.parametrize('change', ['absent', 'outer_seal', 'record_sha', 'geometry_sha', 'native_graph_sha'])
def test_compatibility_rejects_missing_or_changed_source_proof_without_fallback(tmp_path, change):
    _, record, artifact, sample, _ = fixture(tmp_path, 'cached')
    proof = deepcopy(sample.provenance)
    if change == 'absent': proof.pop('native_source_graph_binding')
    elif change == 'outer_seal': proof['source_preserved'] = False
    elif change == 'record_sha': proof['record_binding_sha256'] = '0'*64
    elif change == 'geometry_sha': proof['geometry_provenance_sha256'] = '0'*64
    else:
        value = proof['native_source_graph_binding']; value['current_native_graph_sha256'] = '0'*64
        value['native_source_graph_binding_sha256'] = records.canonical_hash(
            {k: v for k, v in value.items() if k != 'native_source_graph_binding_sha256'})
    if change != 'outer_seal':
        proof['sample_provenance_sha256'] = records.canonical_hash({k: v for k, v in proof.items() if k != 'sample_provenance_sha256'})
    altered = replace(sample, provenance=proof)
    with pytest.raises(ValueError):
        checked_existing_binding(records, altered, expected_record=record)
    assert not hasattr(sample, 'native_source_graph_binding') and sample.provenance['source_preserved'] is True


@pytest.mark.parametrize('change', ['FP64_drift_same_FP32', 'foreign_record', 'two_conformers'])
def test_source64_transport_refuses_coordinate_or_foreign_sample_drift(tmp_path, change):
    store, record, artifact, sample, _ = fixture(tmp_path, 'source3D')
    from phychem_mfm.phase1.v3_source_sample_compat import checked_source_coordinates64
    import torch
    if change == 'foreign_record':
        foreign = store.get(record.record_id)
        assert foreign is not record
        with pytest.raises(ValueError, match='original source record'):
            checked_existing_binding(records, sample, expected_record=foreign)
    elif change == 'two_conformers':
        record.structure.mol.AddConformer(Chem.Conformer(record.structure.mol.GetConformer()), assignId=True)
        with pytest.raises(ValueError, match='one original 3D conformer'):
            checked_source_coordinates64(records, sample)
    else:
        conformer = record.structure.mol.GetConformer(); point = conformer.GetAtomPosition(1)
        prior32 = torch.tensor(point.x, dtype=torch.float32)
        conformer.SetAtomPosition(1, (point.x+1e-12, point.y, point.z))
        assert torch.equal(torch.tensor(conformer.GetAtomPosition(1).x, dtype=torch.float32), prior32)
        with pytest.raises(ValueError, match='FP64 coordinate bytes differ'):
            checked_source_coordinates64(records, sample)


@pytest.mark.parametrize('change', ['drop_ready_coordinates', 'invent_unready_coordinates'])
def test_cyp_native_status_rejects_coordinate_population_drift_after_real_decoder(tmp_path, source_modules, change):
    native, old_decoder, graph = source_modules
    kind = 'source3D' if change == 'drop_ready_coordinates' else 'failed'
    store, record, artifact, sample, member = fixture(tmp_path, kind)
    seen = []
    def altered(*args):
        # First execute the actual old decoder/source/atom-map checks. Corrupt
        # only its returned coordinate transport to reproduce population drift.
        result = list(old_decoder.som_payload(*args)); seen.append(result[1])
        assert (result[1] is not None) == (member['geometry_artifact_ref']['status'] == 'GEOMETRY_READY')
        result[1] = None if change == 'drop_ready_coordinates' else [[0., 0., 0.], [1., 0., 0.]]
        return tuple(result)
    row = {'member_index': 0, 'member_uid': member['member_uid'], 'original_member': member,
        'original_member_row_sha256': native.canonical(member), 'native_n_atoms': record.structure.n_atoms, 'selected_role': 'train'}
    plan = {'records': {'cyp_isoform': [row]}, 'contracts': {'cyp_isoform': {'tasks': TASKS}}}
    selected = FrozenSelectedDecoder({'native': native, 'decoder': SimpleNamespace(som_payload=altered), 'graph': graph}, plan)
    selected.som_store, selected.candidates = store, artifact
    selected.som_modules = modules(CompatibleSourceRecords(records))
    with pytest.raises(SelectedTrainingStoreError, match='coordinate availability differs'):
        selected.decode('cyp_isoform', 0, role='train')
    assert len(seen) == 1 and sample.provenance['annotation_values_decoded'] is False


def test_cyp_original_not_ready_keeps_none_and_the_original_target_masks(tmp_path, source_modules):
    native, old_decoder, graph = source_modules
    store, record, artifact, sample, member = fixture(tmp_path, 'failed')
    row = {'member_index': 0, 'member_uid': member['member_uid'], 'original_member': member,
        'original_member_row_sha256': native.canonical(member), 'native_n_atoms': record.structure.n_atoms, 'selected_role': 'train'}
    plan = {'records': {'cyp_isoform': [row]}, 'contracts': {'cyp_isoform': {'tasks': TASKS}}}
    selected = FrozenSelectedDecoder({'native': native, 'decoder': old_decoder, 'graph': graph}, plan)
    selected.som_store, selected.candidates = store, artifact
    selected.som_modules = modules(CompatibleSourceRecords(records))
    actual = selected.decode('cyp_isoform', 0, role='train')
    assert sample.status == member['geometry_artifact_ref']['status'] == 'NOT_READY'
    assert actual['coordinates'] is None and [row[0] for row in actual['targets']] == [1., 0.]
    assert all(row[0] for row in actual['candidate']) and all(row[0] for row in actual['supervision'])
