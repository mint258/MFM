"""MFM4 array-only record codec; no field semantics or scientific conversions.

All offsets below are relative to the first magic byte. The record header is
``b'MFM4' + <uint16 version + <uint16 array_count`` (8 bytes). Each array is
``<uint16 id + uint8 dtype_code + uint8 ndim + ndim * <uint32 dimension``
followed immediately by its little-endian, C-contiguous raw bytes. Both headers
are already multiples of four bytes; there is no padding inside a header or
between a descriptor and its raw bytes. After EACH raw payload, including the
last, zero bytes pad the record offset to a multiple of four. Empty payloads
need no padding. No other bytes, trailer, JSON, strings, or objects are allowed.

IDs are unique uint16 values encoded in strictly increasing order. Dimensions
may be zero; ndim=0 denotes a scalar. Values are not normalized, rounded, or
filtered. Only the six declared dtypes are accepted; f4 NaNs are retained.

Keys use network byte order independently of the little-endian record format:
M + >I (5 bytes), or P/U + >IH (7 bytes). Every index is zero based. The full
uint32/uint16 ranges are available; no value is reserved as a sentinel. A
single-key codec cannot prove a store's continuous 0..N-1 enumeration; that
store-level obligation remains with the writer/manifest.
"""

from __future__ import annotations

from collections.abc import Mapping
from numbers import Integral
import struct
import sys

import numpy as np


MAGIC = b"MFM4"
FORMAT_VERSION = 1
_RECORD = struct.Struct("<4sHH")
_ARRAY = struct.Struct("<HBB")
_DIMENSION = struct.Struct("<I")
_DTYPES = {
    1: np.dtype("u1"),
    2: np.dtype("<i2"),
    3: np.dtype("<u2"),
    4: np.dtype("<u4"),
    5: np.dtype("<i4"),
    6: np.dtype("<f4"),
}
_CODES = {(dtype.kind, dtype.itemsize): code for code, dtype in _DTYPES.items()}
_NAMES = {1: "u1", 2: "i2", 3: "u2", 4: "u4", 5: "i4", 6: "f4"}


class CodecError(ValueError):
    """A value or byte sequence is outside the declared MFM4 structure."""


def _uint(value, bits, name):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral):
        raise CodecError(f"{name} must be an integer")
    value = int(value)
    if not 0 <= value < (1 << bits):
        raise CodecError(f"{name} is outside uint{bits}")
    return value


def _payload_size(shape, itemsize):
    # Check Python/NumPy addressability before frombuffer/reshape. A zero axis
    # means zero elements, regardless of the product of the other dimensions.
    for dimension in shape:
        if dimension > np.iinfo(np.intp).max:
            raise CodecError("dimension is not addressable on this platform")
    elements = 0 if 0 in shape else 1
    if elements:
        for dimension in shape:
            elements *= dimension
            if elements > sys.maxsize // itemsize:
                raise CodecError("payload is not addressable on this platform")
    return elements * itemsize


def encode(arrays: Mapping[int, np.ndarray]) -> bytes:
    """Encode an ID-to-ndarray mapping, preserving the supplied numeric dtype.

    Big-endian or strided arrays are stored as little-endian C-order values.
    Unsupported dtypes are rejected rather than cast to a supported dtype.
    The input arrays are never modified. This function does not hash payloads.
    """
    if not isinstance(arrays, Mapping):
        raise CodecError("arrays must be an ID-to-ndarray mapping")
    if len(arrays) > 65535:
        raise CodecError("array count exceeds uint16")
    entries = []
    seen = set()
    for supplied_id, array in arrays.items():
        array_id = _uint(supplied_id, 16, "array ID")
        if array_id in seen:
            raise CodecError("duplicate array ID")
        seen.add(array_id)
        if not isinstance(array, np.ndarray) or np.ma.isMaskedArray(array):
            raise CodecError("each value must be an unmasked NumPy ndarray")
        dtype = array.dtype
        code = _CODES.get((dtype.kind, dtype.itemsize))
        if code is None or dtype.fields is not None or dtype.subdtype is not None:
            raise CodecError(f"unsupported dtype: {dtype}")
        if dtype.metadata is not None:
            raise CodecError("dtype metadata is not part of MFM4")
        if array.ndim > 255:
            raise CodecError("ndim exceeds uint8")
        shape = tuple(_uint(n, 32, "dimension") for n in array.shape)
        _payload_size(shape, dtype.itemsize)
        entries.append((array_id, code, shape, array))

    result = bytearray(_RECORD.pack(MAGIC, FORMAT_VERSION, len(entries)))
    for array_id, code, shape, array in sorted(entries, key=lambda entry: entry[0]):
        result.extend(_ARRAY.pack(array_id, code, len(shape)))
        for dimension in shape:
            result.extend(_DIMENSION.pack(dimension))
        # Same kind and width only: this is byte-order/layout conversion, not
        # a precision change. tobytes also handles zero-dimensional scalars.
        raw = array.astype(_DTYPES[code], order="C", casting="equiv", copy=False)
        result.extend(raw.tobytes(order="C"))
        result.extend(b"\0" * ((-len(result)) % 4))
    return bytes(result)


def decode(data, *, copy: bool = True) -> dict[int, np.ndarray]:
    """Decode one complete record, rejecting malformed or noncanonical layout.

    By default returned arrays own their data. With copy=False they are
    read-only views into the supplied buffer; the caller must keep that buffer
    unchanged for the views' lifetime. No numeric casts or hashes are done.
    """
    try:
        view = memoryview(data).cast("B")
    except (TypeError, ValueError) as error:
        raise CodecError("record must be a contiguous bytes-like buffer") from error
    if len(view) < _RECORD.size:
        raise CodecError("truncated record header")
    magic, version, count = _RECORD.unpack_from(view)
    if magic != MAGIC or version != FORMAT_VERSION:
        raise CodecError("unsupported MFM4 magic or version")
    arrays = {}
    offset = _RECORD.size
    previous_id = -1
    for _ in range(count):
        if offset + _ARRAY.size > len(view):
            raise CodecError("truncated array descriptor")
        array_id, code, ndim = _ARRAY.unpack_from(view, offset)
        offset += _ARRAY.size
        if array_id <= previous_id:
            raise CodecError("array IDs must be unique and strictly increasing")
        previous_id = array_id
        dtype = _DTYPES.get(code)
        if dtype is None:
            raise CodecError("unknown dtype code")
        end_header = offset + 4 * ndim
        if end_header > len(view):
            raise CodecError("truncated dimensions")
        shape = tuple(_DIMENSION.unpack_from(view, offset + 4 * i)[0]
                      for i in range(ndim))
        offset = end_header
        size = _payload_size(shape, dtype.itemsize)
        end_raw = offset + size
        end_padded = end_raw + ((-end_raw) % 4)
        if end_padded > len(view):
            raise CodecError("truncated array payload or padding")
        if any(view[end_raw:end_padded]):
            raise CodecError("padding must contain zero bytes")
        try:
            array = np.frombuffer(view, dtype=dtype, count=size // dtype.itemsize,
                                  offset=offset).reshape(shape)
        except (ValueError, OverflowError) as error:
            raise CodecError("invalid or unaddressable array shape") from error
        if copy:
            array = array.copy(order="C")
        else:
            array.setflags(write=False)
        arrays[array_id] = array
        offset = end_padded
    if offset != len(view):
        raise CodecError("trailing bytes after the last array")
    return arrays


def encode_key(kind: str, index: int, subindex: int | None = None) -> bytes:
    """Encode M/index or P,U/index/subindex with exact unsigned boundaries."""
    index = _uint(index, 32, "index")
    if kind == "M":
        if subindex is not None:
            raise CodecError("M keys have no subindex")
        return b"M" + struct.pack(">I", index)
    if kind in ("P", "U"):
        subindex = _uint(subindex, 16, "subindex")
        return kind.encode("ascii") + struct.pack(">IH", index, subindex)
    raise CodecError("key kind must be M, P, or U")


def decode_key(key) -> tuple[str, int, int | None]:
    """Return (kind, index, subindex); M has subindex=None."""
    if not isinstance(key, (bytes, bytearray, memoryview)):
        raise CodecError("key must be bytes-like")
    key = bytes(key)
    if len(key) == 5 and key[:1] == b"M":
        return "M", struct.unpack(">I", key[1:])[0], None
    if len(key) == 7 and key[:1] in (b"P", b"U"):
        index, subindex = struct.unpack(">IH", key[1:])
        return chr(key[0]), index, subindex
    raise CodecError("invalid key prefix or length")


def codec_schema() -> dict:
    """Return the array/key wire rules for a single external schema.json."""
    return {
        "format": "MFM4", "version": FORMAT_VERSION,
        "record_header": ["magic:4=MFM4", "version:little-endian-u2",
                          "array_count:little-endian-u2"],
        "array_header": ["id:little-endian-u2", "dtype_code:u1", "ndim:u1",
                         "shape:ndim*little-endian-u4"],
        "dtype_codes": {str(code): name for code, name in _NAMES.items()},
        "array_ids": "unique uint16, strictly increasing; 0 is permitted",
        "array_count_range": [0, 65535], "ndim_range": [0, 255],
        "dimension_range": [0, 4294967295],
        "scalar": "ndim=0, empty shape, exactly one element",
        "empty_array": "any zero dimension gives zero payload bytes",
        "payload": "little-endian C-order raw; declared dtype only; f4 NaNs retained",
        "padding": {"alignment_bytes": 4, "byte": 0,
                    "header_padding": "none; all headers have length divisible by 4",
                    "raw_start": "immediately after its array header",
                    "raw_end": "pad each payload, including last, to 4-byte record offset"},
        "trailing_bytes": "forbidden", "embedded_objects_strings_json": "forbidden",
        "keys": {"M": {"layout": "ASCII M + >I", "bytes": 5},
                 "P": {"layout": "ASCII P + >IH", "bytes": 7},
                 "U": {"layout": "ASCII U + >IH", "bytes": 7},
                 "index_range": [0, 4294967295], "subindex_range": [0, 65535],
                 "zero_based": True, "reserved_sentinels": None,
                 "continuity": "writer must enumerate each declared index domain as 0..N-1; single-key codec checks structure/range only"},
        "array_id_field_semantics": "defined by external schema; not chosen by codec",
        "hashing": "none",
    }
