"""The selective adapter must never open excluded native target frames."""
import hashlib
import json
from pathlib import Path
import struct

import pytest

from phychem_mfm.phase1.v3_dev_store import TrainOnlyPackedStore


def native_frame(value):
    return (struct.pack('<4I', 1, 1, 1, 1) + struct.pack('<H', 5)
            + struct.pack('<3d', 0., 0., 0.) + struct.pack('<3f', 0., 0., 0.)
            + struct.pack('<f', value) + bytes([1, 1]))


def fixture_store(tmp_path):
    frames = [native_frame(1.), native_frame(2.)]
    excluded = b'EXCLUDED_SYNTHETIC_TARGET_BYTES_MUST_NOT_BE_OPENED'
    payload = tmp_path / 'native.bin'
    payload.write_bytes(b'P1DS1\x00\x00\x00'+b''.join(frames)+excluded)
    records = []; offset = 8
    for i, frame in enumerate(frames):
        records.append(dict(dataset_id='qm9', member_index=i, member_uid=f'source:{i}', native_n_atoms=1,
            target_rows=1, tasks=['U0'], geometry_ready=True, offset=offset, bytes=len(frame),
            sha256=hashlib.sha256(frame).hexdigest()))
        offset += len(frame)
    document = dict(schema='model_v3_training_role_store_v1', source_complete=True,
        targets_in_metadata=False, native_record_hashes_preserved=True,
        source_store_manifest_sha256='a'*64, data_version='synthetic-store-v1',
        records=records, records_file=dict(path=str(payload), bytes=payload.stat().st_size),
        contracts=[dict(dataset_id='qm9', fold_id='0', source_contract_sha256='b'*64,
            tasks=['U0'], output_level='graph', member_indices={'train': [0], 'train_inner_validation': [1]},
            ordered_members={'train': ['source:0'], 'train_inner_validation': ['source:1']})],
        molecule_groups=[dict(dataset_id='qm9', member_index=i, member_uid=f'source:{i}',
            full_inchikey=chr(65+i)*14+'-ABCDEFGHIJ-A') for i in range(2)])
    path = tmp_path / 'metadata.json'; raw = json.dumps(document).encode(); path.write_bytes(raw)
    return path, hashlib.sha256(raw).hexdigest(), payload, records


def test_only_selected_frame_bytes_are_read_and_unknown_member_is_denied(tmp_path, monkeypatch):
    path, digest, payload, records = fixture_store(tmp_path)
    original = Path.open; reads = []

    class Spy:
        def __init__(self, stream):
            self.stream = stream
        def __enter__(self):
            return self
        def __exit__(self, *args):
            self.stream.close()
        def read(self, size=-1):
            reads.append((self.stream.tell(), size))
            assert size >= 0
            return self.stream.read(size)
        def seek(self, *args):
            return self.stream.seek(*args)

    def tracked_open(self, *args, **kwargs):
        stream = original(self, *args, **kwargs)
        return Spy(stream) if self == payload else stream

    monkeypatch.setattr(Path, 'open', tracked_open)
    store = TrainOnlyPackedStore(path, digest)
    assert reads == []
    assert store.native_geometry_metadata('qm9', 0)['native_n_atoms'] == 1
    assert reads == []
    with pytest.raises(ValueError):
        store.get('qm9', 2)
    assert reads == []
    sample = store.get('qm9', 0)
    assert sample.targets.tolist() == [[1.]]
    assert reads == [(0, 8), (records[0]['offset'], records[0]['bytes'])]
    assert store.integrity_scope.startswith('TRAIN metadata')


def test_selected_native_record_corruption_cannot_be_accepted(tmp_path):
    path, digest, payload, records = fixture_store(tmp_path)
    store = TrainOnlyPackedStore(path, digest)
    with payload.open('r+b') as stream:
        stream.seek(records[0]['offset']+records[0]['bytes']-1)
        stream.write(b'\x00')
    with pytest.raises(ValueError, match='record changed'):
        store.get('qm9', 0)


def test_metadata_cannot_smuggle_unassigned_record_or_targets(tmp_path):
    path, digest, payload, records = fixture_store(tmp_path)
    document = json.loads(path.read_text())
    document['records'][0]['targets'] = [1.]
    raw = json.dumps(document).encode(); second = tmp_path / 'bad_metadata.json'; second.write_bytes(raw)
    with pytest.raises(ValueError, match='metadata schema'):
        TrainOnlyPackedStore(second, hashlib.sha256(raw).hexdigest())
