import hashlib
import importlib.util
from pathlib import Path

import pytest


def helper():
    path = Path(__file__).absolute().parents[2] / "tools/model_v3/native_runtime_bindings.py"
    spec = importlib.util.spec_from_file_location("v3_native_binding_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_original_snapshot_raw_pin_is_bound_without_rewriting_device_fields(tmp_path):
    module = helper()
    raw = b'{"shards":{"0":{"identity":[1,2,3,4],"path":"/native/read-only"}}}\n'
    path = tmp_path / "shard_snapshot_v1.json"
    path.write_bytes(raw)
    value, ref = module.bind_original_snapshot(path, hashlib.sha256(raw).hexdigest())
    assert value["shards"]["0"]["identity"] == [1, 2, 3, 4]
    assert path.read_bytes() == raw and ref["original_bytes_modified"] is False
    assert ref["bytes"] == len(raw)


def test_wrong_pin_and_symlink_snapshot_are_rejected(tmp_path):
    module = helper()
    path = tmp_path / "snapshot.json"
    raw = b'{"shards":{}}'
    path.write_bytes(raw)
    with pytest.raises(ValueError, match="pre-job pin"):
        module.bind_original_snapshot(path, "0" * 64)
    alias = tmp_path / "alias.json"
    alias.symlink_to(path)
    with pytest.raises(ValueError, match="ordinary"):
        module.bind_original_snapshot(alias, hashlib.sha256(raw).hexdigest())


def test_duplicate_or_nonfinite_original_json_does_not_get_normalized_away(tmp_path):
    module = helper()
    path = tmp_path / "snapshot.json"
    for raw in (b'{"shards":{},"shards":{}}', b'{"shards":{},"value":NaN}'):
        path.write_bytes(raw)
        with pytest.raises(ValueError):
            module.bind_original_snapshot(path, hashlib.sha256(raw).hexdigest())
