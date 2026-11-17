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
