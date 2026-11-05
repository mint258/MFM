"""Read closed v3.0 family LMDBs without hashes or scientific validation.

Only LMDB's default metadata DB and named records/molecule_index/masks DBs
are opened. MFM3's embedded JSON header is parsed as encoding structure; its
payload_sha256 is deliberately not recomputed or compared. No old codec,
validate_record, schema canonicalizer, or F64 sidecar reader is invoked.
"""

from __future__ import annotations

import json
from pathlib import Path
import struct
import sys

import numpy as np


_HEADER = struct.Struct("<4sI")
_DTYPES = {name: np.dtype(name) for name in
           ("<f4", "<i2", "<i4", "<i8", "<u2", "|u1")}


class LegacyFormatError(ValueError):
    """A legacy LMDB value cannot be decoded as its declared wire structure."""


def _decode_record(raw):
    """Return record metadata and read-only arrays; do not compute any hash."""
    try:
        view = memoryview(raw).cast("B")
    except (TypeError, ValueError) as error:
        raise LegacyFormatError("MFM3 value must be contiguous bytes") from error
    if len(view) < _HEADER.size:
        raise LegacyFormatError("truncated MFM3 header")
    magic, header_bytes = _HEADER.unpack_from(view)
    if magic != b"MFM3" or header_bytes > len(view) - _HEADER.size:
        raise LegacyFormatError("invalid MFM3 magic or header length")
    try:
        header = json.loads(bytes(view[8:8 + header_bytes]).decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise LegacyFormatError("invalid MFM3 header JSON") from error
    if (not isinstance(header, dict) or header.get("format") != "MFM3"
            or type(header.get("version")) is not int or header["version"] != 1
            or not isinstance(header.get("metadata"), dict)
            or not isinstance(header.get("arrays"), list)):
        raise LegacyFormatError("invalid MFM3 header structure")
    body = view[8 + header_bytes:]
    cursor = 0
    arrays = {}
    for descriptor in header["arrays"]:
        if not isinstance(descriptor, dict):
            raise LegacyFormatError("invalid MFM3 array descriptor")
        name = descriptor.get("name")
        dtype_name = descriptor.get("dtype")
        shape = descriptor.get("shape")
        offset, size = descriptor.get("offset"), descriptor.get("nbytes")
        if not isinstance(name, str) or not name or name in arrays:
            raise LegacyFormatError("invalid or duplicate MFM3 array name")
        if not isinstance(dtype_name, str) or dtype_name not in _DTYPES:
            raise LegacyFormatError("unsupported MFM3 numeric dtype")
        if (not isinstance(shape, list)
                or any(type(d) is not int or d < 0 or d > np.iinfo(np.intp).max
                       for d in shape)):
            raise LegacyFormatError("invalid MFM3 shape")
        if (type(offset) is not int or type(size) is not int
                or offset != cursor or size < 0 or size > len(body) - cursor):
            raise LegacyFormatError("MFM3 offset overlap, gap, or length overflow")
        dtype = _DTYPES[dtype_name]
        elements = 0 if 0 in shape else 1
        if elements:
            for dimension in shape:
                elements *= dimension
                if elements > sys.maxsize // dtype.itemsize:
                    raise LegacyFormatError("MFM3 array is not addressable")
        if elements * dtype.itemsize != size:
            raise LegacyFormatError("MFM3 shape/dtype/payload length mismatch")
        try:
            array = np.frombuffer(body, dtype=dtype, count=elements,
                                  offset=offset).reshape(tuple(shape))
        except (ValueError, OverflowError) as error:
            raise LegacyFormatError("unaddressable MFM3 array shape") from error
        array.setflags(write=False)
        arrays[name] = array
        cursor += size
    if cursor != len(body):
        raise LegacyFormatError("undeclared bytes after MFM3 arrays")
    return header["metadata"], arrays


def _key(value):
    if not isinstance(value, str) or not value or value.startswith("__"):
        raise LegacyFormatError("record/molecule ID must be a nonreserved string")
    raw = value.encode("utf-8")
    if len(raw) > 255 or b"\0" in raw:
        raise LegacyFormatError("invalid record/molecule key length or NUL")
    return raw


def _closed_count(raw, name):
    if raw is None:
        raise LegacyFormatError(f"missing closed-store {name}")
    try:
        text = raw.decode("ascii")
        if not text or not text.isdecimal():
            raise ValueError
        return int(text)
    except (UnicodeError, ValueError) as error:
        raise LegacyFormatError(f"invalid closed-store {name}") from error


class OldStore:
    """Readonly v3.0 family-store handle, opened on a store directory.

    ``records_for_molecule(mid)`` returns its duplicate-sorted gid strings.
    ``iter_index()`` yields every (mid, gid) pair in the LMDB index order.
    ``get(gid)`` returns records metadata plus records/masks merged arrays.
    Returned arrays are read-only views backed by owned bytes, so they survive
    the transaction and store closing. No F64 metadata is reconstructed.
    """

    def __init__(self, path):
        import lmdb

        self.path = Path(path)
        self.env = lmdb.open(str(self.path), readonly=True, create=False,
                             lock=False, readahead=False, max_dbs=4, subdir=True)
        try:
            with self.env.begin(buffers=False) as transaction:
                if transaction.get(b"__state__") != b"COMPLETE":
                    raise LegacyFormatError("legacy store is not closed COMPLETE")
                raw_schema = transaction.get(b"__schema__")
                if raw_schema is None:
                    raise LegacyFormatError("missing legacy store schema")
                try:
                    self.schema = json.loads(raw_schema.decode("utf-8"))
                except (UnicodeError, json.JSONDecodeError) as error:
                    raise LegacyFormatError("invalid legacy schema JSON") from error
                if not isinstance(self.schema, dict):
                    raise LegacyFormatError("legacy schema must be a JSON object")
                kind = self.schema.get("kind")
                if kind not in ("geometry", "labels"):
                    raise LegacyFormatError("unknown legacy family-store kind")
                self.count = _closed_count(transaction.get(b"__len__"), "length")
                self.molecule_count = _closed_count(
                    transaction.get(b"__molecules__"), "molecule count")
            self.records = self.env.open_db(b"records", create=False)
            self.molecules = self.env.open_db(b"molecule_index", create=False,
                                              dupsort=True)
            self.masks = (self.env.open_db(b"masks", create=False)
                          if kind == "labels" else None)
        except BaseException:
            self.env.close()
            self.env = None
            raise

    def _open(self):
        if self.env is None:
            raise ValueError("legacy store is closed")
        return self.env

    def get(self, gid):
        key = _key(gid)
        with self._open().begin(buffers=False) as transaction:
            raw = transaction.get(key, db=self.records)
            mask_raw = (transaction.get(key, db=self.masks)
                        if self.masks is not None else None)
        if raw is None:
            raise KeyError(gid)
        metadata, arrays = _decode_record(raw)
        if self.masks is not None:
            if mask_raw is None:
                raise LegacyFormatError("missing legacy masks record")
            # Mask metadata is encoding JSON only; records metadata is the
            # returned metadata. Do not repeat a full metadata comparison.
            _, mask_arrays = _decode_record(mask_raw)
            if arrays.keys() & mask_arrays.keys():
                raise LegacyFormatError("records and masks repeat an array name")
            arrays.update(mask_arrays)
        return metadata, arrays

    def records_for_molecule(self, mid):
        with self._open().begin(buffers=False) as transaction:
            with transaction.cursor(db=self.molecules) as cursor:
                if not cursor.set_key(_key(mid)):
                    return []
                return [value.decode("utf-8") for value in
                        cursor.iternext_dup(keys=False, values=True)]

    def iter_index(self):
        """Yield (mid, gid) strings; close/exhaust the iterator before close()."""
        with self._open().begin(buffers=False) as transaction:
            with transaction.cursor(db=self.molecules) as cursor:
                for molecule_key, record_key in cursor:
                    yield molecule_key.decode("utf-8"), record_key.decode("utf-8")

    def close(self):
        if self.env is not None:
            self.env.close()
            self.env = None

    def __enter__(self):
        self._open()
        return self

    def __exit__(self, kind, value, traceback):
        self.close()
