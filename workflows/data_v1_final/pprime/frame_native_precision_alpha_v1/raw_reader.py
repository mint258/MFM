"""Bounded read-only adapter; keep the frozen archive unbundle and SHA checks."""
from __future__ import annotations
import gzip,hashlib,io,json,pathlib,sqlite3
from urllib.parse import quote
from precision import need


def bounded_gzip(frame,max_raw_bytes):
    """Read at most max_raw+1 output bytes, and require a validated gzip EOF/CRC.

    A too-large stream is rejected before unbundle. For an allowed stream the
    read reaches EOF, including all concatenated members, so GzipFile validates
    each member's trailer/CRC as the frozen gzip.decompress path did.
    """
    need(type(max_raw_bytes) is int and max_raw_bytes>0,'POSITIVE_RAW_LIMIT_REQUIRED')
    with gzip.GzipFile(fileobj=io.BytesIO(frame),mode='rb') as stream:
        body=stream.read(max_raw_bytes+1)
        need(len(body)<=max_raw_bytes,'RAW_DECOMPRESSED_BYTES_EXCEED_FROZEN_CASE_CAP')
        need(stream.read(1)==b'','VALIDATED_GZIP_EOF_REQUIRED')
    return body


class BoundedRawReader:
    """Same keyed SQLite -> gzip -> body SHA -> frozen unbundle readback chain."""
    def __init__(self,path,archive_module,max_raw_bytes,max_metadata_bytes):
        self.path=pathlib.Path(path).absolute();self.archive=archive_module
        need(type(max_raw_bytes) is int and max_raw_bytes>0,'POSITIVE_RAW_LIMIT_REQUIRED')
        need(type(max_metadata_bytes) is int and max_metadata_bytes>0,'POSITIVE_METADATA_LIMIT_REQUIRED')
        self.max_raw_bytes=max_raw_bytes;self.max_metadata_bytes=max_metadata_bytes
        # Generous gzip storage allowance, checked by SQLite before BLOB loading.
        # It is a finite read-adapter bound, not a new scientific size allowance.
        self.max_frame_bytes=max_raw_bytes+(1<<20)
        need(not self.path.is_symlink() and self.path.is_file(),'REGULAR_RAW_CONTAINER_REQUIRED')
        self.db=sqlite3.connect('file:'+quote(str(self.path),safe='/')+'?mode=ro',uri=True)
        # The metadata length check and subsequent BLOB fetch share one read
        # snapshot; a concurrent change cannot bypass the pre-fetch bound.
        self.db.execute('BEGIN')

    def get(self,record_id,calc_type,execution_id,expected_raw_sha256,expected_raw_bytes):
        need(type(expected_raw_bytes) is int and 0<expected_raw_bytes<=self.max_raw_bytes,
             'PINNED_RAW_BYTES_EXCEED_FROZEN_CASE_CAP')
        key=(record_id,calc_type,execution_id)
        # Avoid fetching a malicious compressed BLOB or metadata body first.
        limits=self.db.execute('SELECT raw_sha256,raw_bytes,length(frame),length(CAST(metadata_json AS BLOB)) '
            'FROM raw WHERE record_id=? AND calc_type=? AND execution_id=?',key).fetchone()
        need(limits is not None,'RETAINED_RAW_KEY_NOT_FOUND')
        sha,size,frame_size,metadata_size=limits
        need(sha==expected_raw_sha256 and type(size) is int and size==expected_raw_bytes,
             'ORIGINAL_RESULT_RAW_REFERENCE_DIFFERS')
        need(type(frame_size) is int and 0<frame_size<=self.max_frame_bytes,'BOUNDED_COMPRESSED_RAW_FRAME_REQUIRED')
        need(type(metadata_size) is int and 0<metadata_size<=self.max_metadata_bytes,'BOUNDED_RAW_METADATA_REQUIRED')
        row=self.db.execute('SELECT metadata_json,raw_sha256,raw_bytes,frame FROM raw '
            'WHERE record_id=? AND calc_type=? AND execution_id=?',key).fetchone()
        need(row is not None and row[1:3]==(sha,size) and len(row[3])==frame_size,
             'RAW_ROW_CHANGED_BETWEEN_METADATA_AND_BODY_READ')
        need(len(row[0].encode('utf-8'))==metadata_size,'RAW_METADATA_BYTES_CHANGED')
        body=bounded_gzip(row[3],self.max_raw_bytes)
        need(len(body)==row[2] and hashlib.sha256(body).hexdigest()==row[1],
             'RAW_CONTAINER_CONTENT_SHA_OR_SIZE_CHANGED')
        # The pinned original archive validates the original member offsets,
        # sizes and per-member SHA. No alternative archive/parser is introduced.
        files,manifest=self.archive.unbundle(body)
        metadata=json.loads(row[0])
        need(manifest==metadata['output_file_manifest'] and
             not any(item['name'] in self.archive.FORBIDDEN_INPUT_NAMES for item in files),
             'RAW_OUTPUT_MANIFEST_OR_INPUT_OMISSION_CHANGED')
        return {'metadata':metadata,'output_files':files,'input_bodies_saved':False}

    def close(self):
        self.db.close()
