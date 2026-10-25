"""Bounded, canonical JSON plus little-endian numeric arrays; no pickle."""
from __future__ import annotations
from dataclasses import dataclass
import json
import hashlib
import math
import re
import struct
import numpy as np

MAGIC = b"MFM3"
DTYPES = {"<f4", "<i2", "<i4", "<i8", "<u2", "|u1"}
NAME = re.compile(r"[A-Za-z][A-Za-z0-9_.:/-]{0,255}\Z")


@dataclass(frozen=True)
class Limits:
    header_bytes: int = 1024 * 1024
    payload_bytes: int = 256 * 1024 * 1024
    arrays: int = 512
    rank: int = 4
    elements: int = 16 * 1024 * 1024


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError("DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def _shape(value, limits):
    if not isinstance(value, list) or len(value) > limits.rank:
        raise ValueError("INVALID_ARRAY_RANK")
    if any(type(x) is not int or x < 0 or x > limits.elements for x in value):
        raise ValueError("INVALID_ARRAY_DIMENSION")
    count = math.prod(value)
    if count > limits.elements:
        raise ValueError("ARRAY_ELEMENT_LIMIT")
    return tuple(value), count


def _training_array(value):
    original = np.asarray(value)
    if original.dtype.kind == "f":
        if original.dtype.itemsize not in (4, 8):
            raise ValueError("UNSUPPORTED_FLOAT_SOURCE_DTYPE")
        with np.errstate(over="ignore", invalid="ignore"):
            result = np.asarray(original, dtype="<f4", order="C")
        if np.any(np.isfinite(original) & ~np.isfinite(result)):
            raise ValueError("FLOAT32_OVERFLOW")
    elif original.dtype.kind == "b":
        result = np.asarray(original, dtype="|u1", order="C")
    else:
        dtype = "<i2" if original.dtype.kind == "i" and original.dtype.itemsize == 1 else original.dtype.newbyteorder("<").str
        if dtype not in DTYPES or original.dtype.kind not in "iu":
            raise ValueError("UNSUPPORTED_INTEGER_SOURCE_DTYPE")
        result = np.asarray(original, dtype=dtype, order="C")
    if result.dtype.str not in DTYPES:
        raise ValueError("UNSUPPORTED_WIRE_DTYPE")
    return np.ascontiguousarray(result).reshape(original.shape)


def encode_record(metadata, arrays, limits=Limits()):
    if not isinstance(metadata, dict) or not isinstance(arrays, dict):
        raise ValueError("RECORD_MAPS_REQUIRED")
    if len(arrays) > limits.arrays:
        raise ValueError("ARRAY_COUNT_LIMIT")
    descriptors, chunks, offset = [], [], 0
    for name, value in sorted(arrays.items()):
        if not isinstance(name, str) or NAME.fullmatch(name) is None:
            raise ValueError("INVALID_ARRAY_NAME")
        array = _training_array(value)
        shape, count = _shape(list(array.shape), limits)
        raw = array.tobytes(order="C")
        assert len(raw) == count * array.dtype.itemsize
        descriptors.append({"name": name, "dtype": array.dtype.str, "shape": list(shape),
                            "offset": offset, "nbytes": len(raw)})
        chunks.append(raw)
        offset += len(raw)
        if offset > limits.payload_bytes:
            raise ValueError("PAYLOAD_LIMIT")
    body = b"".join(chunks)
    header = canonical_json({"format": "MFM3", "version": 1,
                             "payload_sha256": hashlib.sha256(body).hexdigest(),
                             "metadata": metadata, "arrays": descriptors})
    if len(header) > limits.header_bytes:
        raise ValueError("HEADER_LIMIT")
    return MAGIC + struct.pack("<I", len(header)) + header + body


def decode_record(raw, limits=Limits()):
    if not isinstance(raw, (bytes, bytearray, memoryview)):
        raise ValueError("BYTE_PAYLOAD_REQUIRED")
    raw = memoryview(raw)
    if len(raw) < 8 or bytes(raw[:4]) != MAGIC:
        raise ValueError("INVALID_MAGIC_OR_TRUNCATION")
    length = struct.unpack("<I", raw[4:8])[0]
    if length > limits.header_bytes or 8 + length > len(raw):
        raise ValueError("INVALID_HEADER_LENGTH")
    header_raw = bytes(raw[8:8 + length])
    try:
        header = json.loads(header_raw.decode("utf-8"), object_pairs_hook=_pairs,
                            parse_constant=lambda value: (_ for _ in ()).throw(
                                ValueError("NONFINITE_JSON")))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("INVALID_HEADER_JSON") from exc
    if canonical_json(header) != header_raw:
        raise ValueError("NONCANONICAL_HEADER")
    if not isinstance(header, dict) or set(header) != {"format", "version", "metadata", "arrays", "payload_sha256"}:
        raise ValueError("INVALID_HEADER_FIELDS")
    if header["format"] != "MFM3" or type(header["version"]) is not int or header["version"] != 1:
        raise ValueError("UNSUPPORTED_VERSION")
    if not isinstance(header["metadata"], dict) or not isinstance(header["arrays"], list):
        raise ValueError("INVALID_RECORD_MAPS")
    if len(header["arrays"]) > limits.arrays:
        raise ValueError("ARRAY_COUNT_LIMIT")
    body = raw[8 + length:]
    if len(body) > limits.payload_bytes:
        raise ValueError("PAYLOAD_LIMIT")
    arrays, cursor = {}, 0
    for descriptor in header["arrays"]:
        if not isinstance(descriptor, dict) or set(descriptor) != {
                "name", "dtype", "shape", "offset", "nbytes"}:
            raise ValueError("INVALID_ARRAY_DESCRIPTOR")
        name, dtype = descriptor["name"], descriptor["dtype"]
        if not isinstance(name, str) or NAME.fullmatch(name) is None or name in arrays:
            raise ValueError("INVALID_OR_DUPLICATE_ARRAY_NAME")
        if not isinstance(dtype, str) or dtype not in DTYPES:
            raise ValueError("UNSUPPORTED_WIRE_DTYPE")
        shape, count = _shape(descriptor["shape"], limits)
        offset, size = descriptor["offset"], descriptor["nbytes"]
        if type(offset) is not int or type(size) is not int or offset != cursor or size < 0:
            raise ValueError("OFFSET_OVERLAP_OR_GAP")
        if size != count * np.dtype(dtype).itemsize or offset + size > len(body):
            raise ValueError("ARRAY_LENGTH_MISMATCH")
        array = np.frombuffer(body[offset:offset + size], dtype=dtype, count=count).reshape(shape)
        array.setflags(write=False)
        arrays[name] = array
        cursor += size
    if cursor != len(body):
        raise ValueError("TRAILING_OR_UNDECLARED_BYTES")
    if hashlib.sha256(body).hexdigest() != header["payload_sha256"]:
        raise ValueError("PAYLOAD_CHECKSUM_MISMATCH")
    return header["metadata"], arrays
