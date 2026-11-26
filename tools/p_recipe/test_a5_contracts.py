"""Only the two repaired A5 calling contracts; no scientific replay."""
import pytest
from a5_contracts import require_runtime_configuration, open_native_store

def test_work_unit_is_supplied_and_validated_before_reads():
    with pytest.raises(ValueError, match="work_unit_seconds"):
        require_runtime_configuration({"cleanup_seconds": 180})
    c = {"work_unit_seconds": 60, "cleanup_seconds": 180}
    assert require_runtime_configuration(c) is c

def test_native_reader_receives_original_expected_sha256():
    ref = {"path": "/original/training_store.json", "sha256": "a"*64}
    seen = {}
    def reader(path, *, expected_sha256):
        seen.update(path=path, sha256=expected_sha256)
        return seen
    assert open_native_store(ref, reader) == ref

