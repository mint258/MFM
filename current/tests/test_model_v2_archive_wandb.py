"""Closed SDK archives preserve actual files, provenance and interrupted output."""
import importlib.util
import json
from pathlib import Path
import tarfile

import pytest

SOURCE = Path(__file__).resolve().parents[2] / 'tools/model_v3/v2_archive_wandb.py'
spec = importlib.util.spec_from_file_location('archive_wandb_under_test', SOURCE)
archive = importlib.util.module_from_spec(spec)
spec.loader.exec_module(archive)


def runs(tmp_path, jobs=(11, 12)):
    tracking = tmp_path / 'tracking'
    for job in jobs:
        for root, state_name in ((tracking / str(job), 'tracking.json'),
                                 (tracking / 'diagnostics' / str(job), 'status.json')):
            (root / 'wandb/offline-run').mkdir(parents=True)
            (root / state_name).write_text(json.dumps(dict(job=job, finished=True)))
            (root / 'wandb/offline-run/run.wandb').write_bytes(b'\x00SDK\xff' + str(job).encode())
        (tracking / 'diagnostics' / str(job) / 'system_metrics.jsonl').write_text('{"power":42}\n')
    return dict(tracking_root=str(tracking), runs=[dict(job=job) for job in jobs])


def test_selected_closed_runs_preserve_all_regular_files_and_payloads(tmp_path):
    manifest = runs(tmp_path)
    expected = {}
    for path in Path(manifest['tracking_root']).rglob('*'):
        if path.is_file():
            expected['WANDB_20261110/' + path.relative_to(manifest['tracking_root']).as_posix()] = path.read_bytes()
    destination = tmp_path / 'archives'
    result = archive.pack_closed_runs(manifest, [11, 12], destination, 'complete',
                                     capacity_check=lambda *_: None)
    assert result['jobs'] == [11, 12]
    assert result['native_sdk_finished'] is True
    assert result['original_files_retained'] is True
    assert result['file_count'] == len(expected)
    assert result['uncompressed_bytes'] == sum(map(len, expected.values()))
    with tarfile.open(result['archive'], 'r:gz') as stream:
        actual = {member.name: stream.extractfile(member).read() for member in stream.getmembers()}
    assert actual == expected
    assert all((Path(manifest['tracking_root']) / name.split('/', 1)[1]).is_file() for name in expected)


@pytest.mark.parametrize('finished', [False, None])
def test_unclosed_diagnostic_cannot_produce_archive(tmp_path, finished):
    manifest = runs(tmp_path)
    state = Path(manifest['tracking_root']) / 'diagnostics/11/status.json'
    state.write_text(json.dumps(dict(job=11, finished=finished)))
    destination = tmp_path / 'archives'
    with pytest.raises(ValueError, match='not closed'):
        archive.pack_closed_runs(manifest, [11], destination, 'complete',
                                 capacity_check=lambda *_: None)
    assert not destination.exists()


def test_unknown_or_duplicate_execution_is_not_silently_substituted(tmp_path):
    manifest = runs(tmp_path)
    for jobs in ([999], [11, 11]):
        with pytest.raises(ValueError):
            archive.pack_closed_runs(manifest, jobs, tmp_path / 'archives', 'complete',
                                     capacity_check=lambda *_: None)
    assert not (tmp_path / 'archives').exists()


def test_completed_archive_metadata_is_reused_without_repacking(tmp_path):
    manifest = runs(tmp_path)
    destination = tmp_path / 'archives'
    first = archive.pack_closed_runs(manifest, [11], destination, 'complete',
                                    capacity_check=lambda *_: None)
    def unexpected_write(*_):
        raise AssertionError('No new archive write is needed')
    second = archive.pack_closed_runs(manifest, [11], destination, 'complete',
                                     capacity_check=unexpected_write)
    assert first == second
    assert len(list(destination.iterdir())) == 2


def test_capacity_failure_keeps_partial_and_originals(tmp_path):
    manifest = runs(tmp_path)
    destination = tmp_path / 'archives'
    calls = []
    def unavailable(*args):
        calls.append(args)
        if len(calls) > 1:
            raise OSError('Actual capacity became unavailable')
    with pytest.raises(OSError, match='capacity'):
        archive.pack_closed_runs(manifest, [11], destination, 'complete',
                                 capacity_check=unavailable)
    assert (destination / 'complete.tar.gz.partial').is_file()
    assert not (destination / 'complete.tar.gz').exists()
    assert (Path(manifest['tracking_root']) / '11/wandb/offline-run/run.wandb').read_bytes() == b'\x00SDK\xff11'


def test_interrupted_archive_is_preserved(tmp_path):
    manifest = runs(tmp_path)
    destination = tmp_path / 'archives'
    destination.mkdir()
    partial = destination / 'complete.tar.gz.partial'
    partial.write_bytes(b'original interrupted bytes')
    with pytest.raises(FileExistsError, match='interrupted'):
        archive.pack_closed_runs(manifest, [11], destination, 'complete',
                                 capacity_check=lambda *_: None)
    assert partial.read_bytes() == b'original interrupted bytes'


def test_archive_name_cannot_select_another_output_path(tmp_path):
    manifest = runs(tmp_path)
    with pytest.raises(ValueError, match='archive name'):
        archive.pack_closed_runs(manifest, [11], tmp_path / 'archives', '../other',
                                 capacity_check=lambda *_: None)
    assert not (tmp_path / 'other.tar.gz').exists()
