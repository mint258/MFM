"""Bounded exact inventory-derived byte reads, no molecule/target decoding."""
from __future__ import annotations

import codecs
import hashlib
import heapq
import json
import os
from pathlib import Path
import random
import re
import threading

from .. import full_queue_v1 as execution
from .policy import CONTAINER_CAP, COUNT, INDEX_CAP, LONGEST


STOP = None


def check():
    if STOP is not None and STOP.is_set():
        raise execution.CooperativeStop("STOP_BEFORE_NEXT_SOURCE_SEGMENT")


def sample_ordinals(n, k=COUNT, seed=20261026):
    execution.require(type(n) is int and type(k) is int and 0 < k <= n, "Positive finite without-replacement sample required")
    values = sorted(random.Random(seed).sample(range(1, n + 1), k))
    execution.require(len(values) == len(set(values)) == k and 1 <= values[0] <= values[-1] <= n, "Uniform ordinal conservation")
    return values


def index_rows(path):
    with Path(path).open("rb") as stream:
        while True:
            check()
            raw = stream.readline(INDEX_CAP + 1)
            if not raw:
                return
            execution.require(len(raw) <= INDEX_CAP and raw.endswith(b"\n"), "Index entry exceeds4KiB or is truncated")
            yield json.loads(raw)


def validate_entry(row, *, root, index, first_ordinal):
    execution.require(set(row) == {"index", "first_ordinal", "last_ordinal", "records", "bytes", "first_cid", "last_cid", "reference"},
                      "Exact inventory-v2 part schema required")
    for key in ("index", "first_ordinal", "last_ordinal", "records", "bytes"):
        execution.require(type(row[key]) is int and row[key] >= (0 if key == "index" else 1), "Integer part metadata required")
    ref = row["reference"]
    expected = Path(root) / f"source_{index:06d}.tsv"
    execution.require(row["index"] == index and row["first_ordinal"] == first_ordinal and
        row["last_ordinal"] == first_ordinal + row["records"] - 1 and ref["bytes"] == row["bytes"] and
        set(ref) == {"path", "bytes", "sha256"} and ref["path"] == str(expected) and
        re.fullmatch(r"[a-f0-9]{64}", ref["sha256"]), "Canonical index/path/ordinal/row/byte/SHA authority differs")
    execution.require(expected.is_absolute() and ".." not in expected.parts and not Path(root).is_symlink() and
        expected.resolve() == expected, "Literal owned paths without any symlink required")
    return row


def push_longest(heap, value, count=LONGEST):
    item = (value["smiles_bytes"], -value["ordinal"], value)
    if len(heap) < count:
        heapq.heappush(heap, item)
    elif item[:2] > heap[0][:2]:
        heapq.heapreplace(heap, item)


def sorted_longest(heap):
    return [item[2] for item in sorted(heap, key=lambda item: (-item[0], -item[1]))]


def frame_equal(opened, frame):
    return (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns, opened.st_uid) == \
        tuple(frame[key] for key in ("device", "inode", "size", "mtime_ns", "uid"))


def scan_part(part, selected=(), *, extract=False, expected_frame=None):
    """Validate bounded UTF8 framing; retain full SMILES only for selected rows."""
    path = Path(part["reference"]["path"])
    before = execution.frame(path)
    execution.require(expected_frame is None or before == expected_frame, "Selected source frame changed since preflight")
    execution.require(before["size"] == part["bytes"], "Part byte metadata differs before read")
    selected = set(selected)
    digest = hashlib.sha256()
    longest, selected_facts, extracted = [], [], []
    read_bytes = rows = maximum_line = maximum_smiles = retained_bytes = 0
    first_cid = last_cid = None
    line_bytes = cid_bytes = tabs = canonical_digits = 0
    canonical_seen = False
    prefix, tail, collected = bytearray(), b"", bytearray()
    cid_hash = hashlib.sha256()
    decoder = codecs.getincrementaldecoder("utf-8")("strict")
    offset = 0

    def endpoint():
        return rows == 0 or rows == part["records"] - 1

    def finish():
        nonlocal rows, maximum_line, maximum_smiles, line_bytes, cid_bytes, tabs, canonical_digits
        nonlocal canonical_seen, prefix, tail, collected, cid_hash, decoder, offset, first_cid, last_cid
        decoder.decode(b"", final=True)
        execution.require(tabs == 1 and canonical_seen, "Malformed original CID/SMILES framing; no rows may be dropped")
        terminator = 2 if tail.endswith(b"\r\n") else (1 if tail.endswith(b"\n") else 0)
        smiles_bytes = line_bytes - cid_bytes - 1 - terminator
        execution.require(smiles_bytes >= 0, "Negative source field length")
        ordinal = part["first_ordinal"] + rows
        fact = {"ordinal": ordinal, "part_index": part["index"], "offset_bytes": offset,
                "source_row_bytes": line_bytes, "smiles_bytes": smiles_bytes}
        push_longest(longest, fact)
        if ordinal in selected:
            selected_facts.append(fact)
            if extract:
                raw = bytes(collected)
                cid, payload = raw.split(b"\t", 1)
                smiles_raw = payload[:-terminator] if terminator else payload
                execution.require(len(smiles_raw) == smiles_bytes, "Exact selected SMILES field bytes differ")
                extracted.append({**fact, "cid_source_ascii": cid.decode("ascii"), "source_smiles": smiles_raw.decode("utf-8"),
                    "source_row_sha256": hashlib.sha256(raw).hexdigest(), "source_smiles_sha256": hashlib.sha256(smiles_raw).hexdigest(),
                    "source_terminator_hex": raw[-terminator:].hex() if terminator else "", "source_part": part["reference"]})
        if endpoint():
            value = {"decimal_digits": canonical_digits, "decimal_prefix": prefix.decode("ascii"),
                "complete_decimal": prefix.decode("ascii") if canonical_digits <= 32 else None, "decimal_sha256": cid_hash.hexdigest()}
            first_cid = value if first_cid is None else first_cid
            last_cid = value
        maximum_line, maximum_smiles = max(maximum_line, line_bytes), max(maximum_smiles, smiles_bytes)
        offset += line_bytes
        rows += 1
        line_bytes = cid_bytes = tabs = canonical_digits = 0
        canonical_seen = False
        prefix, tail, collected = bytearray(), b"", bytearray()
        cid_hash = hashlib.sha256()
        decoder = codecs.getincrementaldecoder("utf-8")("strict")

    with path.open("rb") as stream:
        execution.require(frame_equal(os.fstat(stream.fileno()), before), "Opened source inode/frame differs")
        while True:
            check()
            piece = stream.readline(1 << 20)
            if not piece:
                if line_bytes:
                    finish()
                break
            digest.update(piece)
            decoder.decode(piece, final=False)
            if tabs == 0:
                head = piece.partition(b"\t")[0]
                execution.require(head.isascii() and (not head or head.isdigit()), "Original CID token is not decimal")
                cid_bytes += len(head)
                canonical = head if canonical_seen else head.lstrip(b"0")
                canonical_seen = canonical_seen or bool(canonical)
                canonical_digits += len(canonical)
                if endpoint():
                    cid_hash.update(canonical)
                    prefix.extend(canonical[:max(0, 32 - len(prefix))])
            tabs += piece.count(b"\t")
            line_bytes += len(piece)
            read_bytes += len(piece)
            tail = (tail + piece[-2:])[-2:]
            if extract and part["first_ordinal"] + rows in selected:
                retained_bytes += len(piece)
                execution.require(retained_bytes <= CONTAINER_CAP, "Selected source container budget STOP; no truncation")
                collected.extend(piece)
            if piece.endswith(b"\n"):
                finish()
        execution.require(frame_equal(os.fstat(stream.fileno()), before), "Source changed while open")
    execution.require(execution.frame(path) == before and digest.hexdigest() == part["reference"]["sha256"] and
        read_bytes == offset == part["bytes"] and rows == part["records"] and
        first_cid == part["first_cid"] and last_cid == part["last_cid"], "Complete part SHA/frame/row/CID/bytes conservation differs")
    return {"index": part["index"], "reference": part["reference"], "frame": before, "rows": rows, "bytes": read_bytes,
        "maximum_source_line_bytes": maximum_line, "maximum_source_smiles_bytes": maximum_smiles,
        "longest": sorted_longest(longest), "selected_facts": selected_facts, "extracted": extracted,
        "worker_pid": os.getpid(), "native_thread_id": threading.get_native_id()}
