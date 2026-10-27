"""Root small-metadata candidate helper: always nonexecutable, never DATA IO."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from .contract import candidate, need

FILES = ('__init__.py','contract.py','ordering.py','bindings.py','index.py','reader.py',
         'metadata.py','test_boundaries.py','README.md')


def frame(st):
    return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns, st.st_uid)


def read_small(path):
    path = Path(path)
    need(path.is_file() and not path.is_symlink(), 'REGULAR_SMALL_ROOT_REQUEST_REQUIRED')
    before = path.stat(); need(before.st_uid == 1278, 'MAIN_ROOT_METADATA_UID_REQUIRED')
    need(0 < before.st_size <= 2 << 20, 'REQUEST_SMALL_METADATA_BOUND')
    raw = path.read_bytes(); after = path.stat()
    need(frame(before) == frame(after) and len(raw) == before.st_size, 'ROOT_REQUEST_FRAME_CHANGED')
    return json.loads(raw), {'path': str(path.absolute()), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request', required=True); parser.add_argument('--output', required=True)
    args = parser.parse_args()
    need(hasattr(os, 'getuid') and os.getuid() == 1278, 'MAIN_METADATA_ONLY_NO_LOCAL_INTERPRETER')
    request, request_ref = read_small(args.request)
    result = candidate(request); result['request_reference'] = request_ref
    # These are this namespace's SOURCE files, not scientific cache bodies.
    here = Path(__file__).resolve().parent; sources = []
    for name in FILES:
        path = here / name; need(path.is_file() and not path.is_symlink(), 'ALL_INTERFACE_SOURCES_REQUIRED')
        before = path.stat(); need(before.st_uid == 1278, 'MAIN_SOURCE_UID_REQUIRED')
        raw = path.read_bytes(); after = path.stat()
        need(frame(before) == frame(after) and len(raw) == before.st_size, 'INTERFACE_SOURCE_FRAME_CHANGED')
        sources.append({'path': str(path), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()})
    result['new_source_files'] = sources
    output = Path(args.output); output.mkdir(parents=True, exist_ok=False)
    raw = (json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode()
    fd = os.open(output / 'candidate.json', os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    print(result['status'])


if __name__ == '__main__':
    main()
