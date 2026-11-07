"""Source-only MFM4 codec candidate; no scientific field assignments."""

from .codec import (
    MAGIC, FORMAT_VERSION, CodecError, codec_schema, decode, decode_key,
    encode, encode_key,
)

__all__ = [
    "MAGIC", "FORMAT_VERSION", "CodecError", "codec_schema", "decode",
    "decode_key", "encode", "encode_key",
]
