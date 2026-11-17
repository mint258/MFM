"""Regression for disappearing multiprocessing/compile temporary directories."""
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from regression import allocated_bytes


def test_disappearing_file_is_not_a_capacity_failure(tmp_path):
    kept=tmp_path/'kept';kept.write_bytes(b'payload')
    transient=tmp_path/'transient';transient.write_bytes(b'closed')
    expected=kept.stat().st_blocks*512
    def walker(*args,**kwargs):
        transient.unlink()
        yield str(tmp_path),[],['kept','transient']
        kwargs['onerror'](FileNotFoundError('temporary directory removed'))
    with patch.object(os,'walk',walker):
        assert allocated_bytes([tmp_path])==expected


def test_unreadable_directory_still_stops_accounting(tmp_path):
    def walker(*args,**kwargs):
        kwargs['onerror'](PermissionError('unknown allocation'))
        yield str(tmp_path),[],[]
    with patch.object(os,'walk',walker),pytest.raises(PermissionError):
        allocated_bytes([tmp_path])


def test_closed_trace_archive_preserves_bytes_and_failed_training(tmp_path):
    import gzip
    import gpu_study as study
    payload=b'closed profiler JSON fixture\n'*100
    for name in ('S0_trace.json','S1_trace.json','S8_trace.json.tmp'):
        (tmp_path/name).write_bytes(payload)
    training=tmp_path/'S8_profile_training'
    training.mkdir();(training/'losses.csv').write_text('retained failed-run log')
    with patch.object(study,'ROOT',tmp_path),patch.object(study,'capacity',lambda:None):
        study.archive_closed_profiles()
    for name in ('S0_trace.json','S1_trace.json','S8_trace.json.tmp.failed_4535744'):
        assert gzip.decompress((tmp_path/(name+'.gz')).read_bytes())==payload
        assert not (tmp_path/name).exists()
    assert (tmp_path/'S8_profile_training.failed_4535744/losses.csv').read_text()=='retained failed-run log'


def test_closed_trace_archive_rejects_external_symlink(tmp_path):
    import gpu_study as study
    root=tmp_path/'owned';root.mkdir()
    outside=tmp_path/'outside';outside.write_bytes(b'untouched')
    (root/'S0_trace.json').symlink_to(outside)
    with patch.object(study,'ROOT',root),patch.object(study,'capacity',lambda:None),pytest.raises(OSError):
        study.archive_closed_profiles()
    assert outside.read_bytes()==b'untouched'
    assert not (root/'S0_trace.json.gz').exists()
