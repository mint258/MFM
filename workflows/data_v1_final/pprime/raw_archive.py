"""New output-only containers; retain exactly WP5 failure/record-audit scope."""
from __future__ import annotations

import gzip
import hashlib
import json
import os
from pathlib import Path
import sqlite3
from urllib.parse import quote

from common import canonical


class RawSink:
    def __init__(self, path, archive_module, max_bytes):
        self.path, self.archive, self.max_bytes = Path(path), archive_module, int(max_bytes)
        if self.path.exists():
            raise FileExistsError(self.path)
        self.db = sqlite3.connect(self.path, isolation_level=None)
        self.db.execute('PRAGMA journal_mode=DELETE')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('CREATE TABLE raw(record_id TEXT,calc_type TEXT,execution_id TEXT,metadata_json TEXT,raw_sha256 TEXT,raw_bytes INTEGER,frame BLOB,PRIMARY KEY(record_id,calc_type,execution_id)) WITHOUT ROWID')

    def __call__(self, record):
        keep, reason = self.archive.retention(record)
        ref = {'container_path': str(self.path) if keep else None,
               'record_id': record['record_id'], 'calc_type': record['calc_type'],
               'execution_id': record['execution_id'], 'output_retained': keep,
               'retention_reason': reason, 'input_bodies_saved': False}
        if not keep:
            return ref
        for item in record['files']:
            if item.get('role') != 'output' or item['name'] in self.archive.FORBIDDEN_INPUT_NAMES:
                raise ValueError('INPUT_BODY_FORBIDDEN_IN_PPRIME_RAW')
            if hashlib.sha256(item['data']).hexdigest() != item['sha256']:
                raise ValueError('RAW_OUTPUT_MEMBER_SHA_CHANGED')
        body, manifest = self.archive.bundle(record['files'])
        metadata = {k: v for k, v in record.items() if k != 'files'}
        metadata.update(output_file_manifest=manifest, input_bodies_saved=False,
                        compression='gzip; WP5 output-bundle member format')
        encoded = canonical(metadata).decode('utf-8')
        frame = gzip.compress(body, compresslevel=3, mtime=0)
        # Include SQLite journal overlap and space for indexes before writing.
        if self.path.stat().st_size + 2 * (len(frame) + len(encoded)) + (1 << 20) > self.max_bytes:
            raise RuntimeError('PPRIME_PER_WORKER_RAW_OUTPUT_CAP')
        key = hashlib.sha256(body).hexdigest()
        self.db.execute('BEGIN IMMEDIATE')
        try:
            self.db.execute('INSERT INTO raw VALUES(?,?,?,?,?,?,?)',
                            (record['record_id'], record['calc_type'], record['execution_id'],
                             encoded, key, len(body), frame))
            self.db.execute('COMMIT')
        except Exception:
            self.db.execute('ROLLBACK')
            raise
        # Actual readback after FULL-synchronous commit; not just a log ACK.
        saved = self.db.execute('SELECT raw_sha256,frame FROM raw WHERE record_id=? AND calc_type=? AND execution_id=?',
                                (record['record_id'], record['calc_type'], record['execution_id'])).fetchone()
        if saved[0] != key or hashlib.sha256(gzip.decompress(saved[1])).hexdigest() != key:
            raise RuntimeError('RETAINED_PPRIME_RAW_READBACK_FAILED')
        return dict(ref, raw_call_durable=True, raw_sha256=key, raw_bytes=len(body),
                    compressed_bytes=len(frame))

    def close(self):
        self.db.close()


class RawReader:
    """Read a pinned new container; partial executions remain explicitly keyed."""
    def __init__(self, path, archive_module):
        self.path, self.archive = Path(path).absolute(), archive_module
        if self.path.is_symlink() or not self.path.is_file():
            raise ValueError('REGULAR_RAW_CONTAINER_REQUIRED')
        self.db = sqlite3.connect('file:' + quote(str(self.path), safe='/') + '?mode=ro', uri=True)

    def get(self, record_id, calc_type, execution_id):
        row = self.db.execute('SELECT metadata_json,raw_sha256,raw_bytes,frame FROM raw WHERE record_id=? AND calc_type=? AND execution_id=?',
                              (record_id, calc_type, execution_id)).fetchone()
        if row is None:
            raise KeyError((record_id, calc_type, execution_id))
        body = gzip.decompress(row[3])
        if len(body) != row[2] or hashlib.sha256(body).hexdigest() != row[1]:
            raise ValueError('RAW_CONTAINER_CONTENT_SHA_OR_SIZE_CHANGED')
        files, manifest = self.archive.unbundle(body)
        metadata = json.loads(row[0])
        if manifest != metadata['output_file_manifest'] or any(f['name'] in self.archive.FORBIDDEN_INPUT_NAMES for f in files):
            raise ValueError('RAW_OUTPUT_MANIFEST_OR_INPUT_OMISSION_CHANGED')
        return {'metadata': metadata, 'output_files': files, 'input_bodies_saved': False}

    def close(self):
        self.db.close()
