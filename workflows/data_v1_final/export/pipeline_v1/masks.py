"""Compact v1 validity is exact; field-level causes are not exact leaf causes."""
from __future__ import annotations
import numpy as np
import json

UNRESOLVED_LEAF_REASON = 65535
BIT_NAMES = ("in_scope_fields", "source_valid_fields", "valid_fields", "all_leaves_valid_fields", "newly_masked_fields")
GROUP_NAMES = ("source_reason_groups", "new_reason_groups", "review_groups")


def encode_row(row):
    result = dict(row)
    for name in BIT_NAMES:
        result[name] = row[name].hex()
    for name in GROUP_NAMES:
        result[name] = [{"code": r["code"], "fields": r["fields"].hex()} for r in row[name]]
    return json.dumps(result, sort_keys=True, separators=(",", ":"))


def decode_row(raw):
    result = json.loads(raw)
    for name in BIT_NAMES:
        result[name] = bytes.fromhex(result[name])
    for name in GROUP_NAMES:
        result[name] = [{"code": r["code"], "fields": bytes.fromhex(r["fields"])} for r in result[name]]
    return result


def field_ids(raw):
    if not isinstance(raw, bytes) or len(raw) != 19:
        raise ValueError("COMPACT_146_FIELD_BITSET_REQUIRED")
    value = int.from_bytes(raw, "little")
    if value >> 146:
        raise ValueError("UNASSIGNED_COMPACT_FIELD_BITS")
    return {i for i in range(146) if value >> i & 1}


def restore(row, field_id, leaves):
    if type(field_id) is not int or not 0 <= field_id < 146 or type(leaves) is not int or leaves < 0:
        raise ValueError("COMPACT_FIELD_OR_LEAF_COUNT_INVALID")
    if field_id not in field_ids(row["in_scope_fields"]):
        raise ValueError("FIELD_OUTSIDE_CANONICAL_TASK_SCOPE")
    keep = field_id in field_ids(row["valid_fields"])
    valid = np.full(leaves, int(keep), dtype="|u1")
    reason = np.full(leaves, 0 if keep else UNRESOLVED_LEAF_REASON, dtype="<u2")
    field_reasons = set()
    by_scope = {}
    for name in ("source_reason_groups", "new_reason_groups", "review_groups"):
        scoped = set()
        for group in row[name]:
            if field_id in field_ids(group["fields"]):
                code = group["code"]
                if type(code) is not int or not 0 < code < UNRESOLVED_LEAF_REASON:
                    raise ValueError("COMPACT_REASON_CODE_INVALID")
                scoped.add(code)
                if name != "review_groups":
                    field_reasons.add(code)
        by_scope[name] = sorted(scoped)
    exceptions, seen = [], set()
    for item in row["leaf_exceptions"]:
        if item["field_id"] != field_id:
            continue
        index, code = item["leaf_index"], item["code"]
        if type(index) is not int or not 0 <= index < leaves or index in seen or type(code) is not int or not 0 < code < UNRESOLVED_LEAF_REASON:
            raise ValueError("COMPACT_PARTIAL_LEAF_EXCEPTION_INVALID")
        seen.add(index)
        valid[index] = 0; reason[index] = code
        exceptions.append({"leaf_index": index, "code": code})
    # Review flags never alter validity. 65535 explicitly means unresolved
    # per-leaf cause; it does NOT assert every field cause applies to each leaf.
    return {"valid": valid, "reason": reason, "field_reason_codes": sorted(field_reasons),
            "partial_leaf_reason_codes": exceptions, **by_scope,
            "reason_granularity": "exact validity; field cause set; partial generic leaf causes; 65535 unresolved leaf cause"}
