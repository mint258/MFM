"""Bind original native-input JSON bytes without modifying their contents."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat


def bind_original_snapshot(path, expected_sha256):
    """Return parsed original JSON and a stable raw-byte identity receipt.

    expected_sha256 is supplied by the root's pre-job snapshot, not learned
    from the file being validated. Node-local st_dev projection occurs only in
    the existing adapter's independent copy, after this raw binding.
    """
    if not isinstance(expected_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
        raise ValueError("A pre-job pin of the original snapshot SHA256 is required")
    path = Path(path)
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("Absolute original snapshot path required")
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode) or before.st_uid != os.getuid():
        raise ValueError("Original snapshot must be an owned ordinary file")
    if not 0 < before.st_size <= 16 * 1024**2:
        raise ValueError("Original snapshot exceeds its bounded JSON size")
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        opened = os.fstat(descriptor)
        if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
            raise ValueError("Original snapshot changed before opening")
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            raw = stream.read(16 * 1024**2 + 1)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    identity = lambda value: (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns)
    if identity(before) != identity(after) or identity(path.lstat()) != identity(after) or len(raw) != after.st_size:
        raise ValueError("Original snapshot changed during raw-byte binding")
    actual = hashlib.sha256(raw).hexdigest()
    if actual != expected_sha256:
        raise ValueError("Original shard snapshot SHA256 differs from the pre-job pin")
    def unique(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate original snapshot JSON key")
            result[key] = value
        return result
    value = json.loads(raw.decode("utf-8"), object_pairs_hook=unique,
                       parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite snapshot JSON")))
    if type(value) is not dict or type(value.get("shards")) is not dict:
        raise ValueError("Original shard snapshot object required")
    return value, {"path": str(path), "bytes": len(raw), "sha256": actual,
                   "uid": before.st_uid, "st_dev": before.st_dev, "inode": before.st_ino,
                   "mtime_ns": before.st_mtime_ns, "original_bytes_modified": False,
                   "node_local_device_projection": "separate_existing_v2_adapter_copy_only"}
