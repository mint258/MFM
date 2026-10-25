"""Per-task field bitsets and sparse exceptions; normal label values are absent."""
from __future__ import annotations

import collections
import math

WIDTH=19  # 146 enabled field IDs occupy 19 bytes; schema rejects larger registries.
REASONS=["SOURCE_TASK_STATUS", "SOURCE_CELL_ABSENT", "SOURCE_CELL_NULL", "SOURCE_CELL_EMPTY",
    "SOURCE_NONFINITE_OR_NONNUMERIC", "SOURCE_NUMERIC_ISSUE", "SOURCE_VALID_MASK_FALSE",
    "CELL_DECODE_INVALID", "ARRAY_TYPE_INVALID", "MOLECULE_VECTOR_SHAPE_INVALID",
    "SHELL_SHAPE_INVALID", "FUKUI_SHAPE_INVALID", "COMPOUND_SHAPE_INVALID",
    "ONE_CENTER_ATOM_COUNT_INVALID", "COMPOUND_ATOM_INDEX_INVALID", "PAIR_VALUE_LAYOUT_INVALID",
    "PAIR_INDEX_INVALID", "ATOM_VECTOR_SHAPE_INVALID", "ATOM_VALUE_SHAPE_INVALID",
    "UNSUPPORTED_PHYSICAL_LAYOUT", "D20_SHAPE_OR_NAMES_INVALID", "SOURCE_D3_FAILURE_ISSUE",
    "EXPLICIT_ELECTRONIC_NONCONVERGENCE", "PHYSICAL_DEFINITION_RANGE",
    "SUCCESS_WITH_CONVERGENCE_EVIDENCE_UNKNOWN", "PROPERTY_FAILED_WITH_CONVERGENCE_EVIDENCE_UNKNOWN",
    "SOURCE_AND_SCOPE_STATUS_DIFFER", "CHARGE_SUM_TOLERANCE_UNRESOLVED_SOURCE_PRECISION_UNKNOWN",
    "NEUTRAL_ATOMIC_CHARGE_SUM_OUTSIDE_SOURCE_ROUNDING_TOLERANCE",
    "IP_EA_ORBITAL_GAP_SIGN_INCONSISTENT_SAME_PM7_CONTEXT", "ROBUST_Z_GT20_REVIEW_ONLY",
    "ZERO_MAD_UNEQUAL_VALUE_REVIEW_ONLY", "WITHIN_MOLECULE_JUMP_REVIEW_ONLY",
    "OTHER_TASK_STATUS_WITH_CONVERGENCE_EVIDENCE_UNKNOWN", "TRAIN_SCALE_UNDEFINED_REVIEW_ONLY"]
CODE={name:i+1 for i,name in enumerate(REASONS)}


def reason_code(text):
    key="SOURCE_TASK_STATUS" if text.startswith("SOURCE_TASK_STATUS_") else text.split(":",1)[0]
    if key.endswith("_WITH_CONVERGENCE_EVIDENCE_UNKNOWN") and key not in CODE:
        key="OTHER_TASK_STATUS_WITH_CONVERGENCE_EVIDENCE_UNKNOWN"
    if key not in CODE:
        raise ValueError("UNKNOWN_REASON_REQUIRES_SCHEMA_REVISION:"+text)
    return CODE[key]


def bits(ids):
    value=0
    for i in ids:
        if type(i) is not int or not 0<=i<146:
            raise ValueError("FIELD_ID_OUTSIDE_146_COMPONENT_SCHEMA")
        value|=1<<i
    return value.to_bytes(WIDTH,"little")


def unpack(raw):
    if len(raw)!=WIDTH:
        raise ValueError("FIELD_BITSET_WIDTH_INVALID")
    value=int.from_bytes(raw,"little")
    if value>>146:
        raise ValueError("UNASSIGNED_FIELD_BITS_SET")
    return [i for i in range(146) if value>>i&1]


def grouped(items,key):
    groups=collections.defaultdict(list)
    for row in items:
        for reason in set(row[key]):
            groups[reason_code(reason)].append(row["field_id"])
    return [{"code":code,"fields":bits(ids)} for code,ids in sorted(groups.items())]


def encode(ordinal,task_code,items):
    ids=[row["field_id"] for row in items]
    if len(ids)!=len(set(ids)):
        raise ValueError("DUPLICATE_FIELD_IN_CANONICAL_TASK")
    source,valid,complete,newly,exceptions=[],[],[],[],[]
    for row in items:
        fid=row["field_id"];a,b=row["source_value_mask"],row["value_mask"]
        if len(a)!=len(b) or len(b)!=len(row["values_float64"]):
            raise ValueError("LEAF_VALUE_MASK_LENGTH_DIFFERS")
        if any(a):source.append(fid)
        if any(b):valid.append(fid)
        if b and all(b):complete.append(fid)
        if any(x and not y for x,y in zip(a,b)):newly.append(fid)
        # An all-false field is represented by the field bit. Only a partially
        # valid field needs per-leaf exception indices to reconstruct its mask.
        if any(b) and not all(b):
            for i,keep in enumerate(b):
                if not keep:
                    exceptions.append({"field_id":fid,"leaf_index":i,
                        "code":CODE["PHYSICAL_DEFINITION_RANGE"] if a[i] else CODE["SOURCE_NONFINITE_OR_NONNUMERIC"]})
    return {"record_ordinal":ordinal,"task_code":task_code,"in_scope_fields":bits(ids),
        "source_valid_fields":bits(source),"valid_fields":bits(valid),"all_leaves_valid_fields":bits(complete),
        "newly_masked_fields":bits(newly),"source_reason_groups":grouped(items,"source_reasons"),
        "new_reason_groups":grouped(items,"new_reasons"),"review_groups":grouped(items,"review_reasons"),
        "leaf_exceptions":exceptions}


def restore_mask(compact,fid,n):
    if fid not in unpack(compact["in_scope_fields"]):
        raise ValueError("FIELD_NOT_IN_TASK_SCOPE")
    if fid not in unpack(compact["valid_fields"]):
        return [False]*n
    mask=[True]*n
    for item in compact["leaf_exceptions"]:
        if item["field_id"]==fid:
            if not 0<=item["leaf_index"]<n:
                raise ValueError("LEAF_EXCEPTION_OUTSIDE_ORIGINAL_LABEL")
            mask[item["leaf_index"]]=False
    return mask


def arrow_schema():
    import pyarrow as pa
    reason=pa.struct([("code",pa.uint16()),("fields",pa.binary(WIDTH))])
    leaf=pa.struct([("field_id",pa.uint16()),("leaf_index",pa.uint32()),("code",pa.uint16())])
    return pa.schema([("record_ordinal",pa.uint64()),("task_code",pa.uint8()),
        *[(name,pa.binary(WIDTH)) for name in ("in_scope_fields","source_valid_fields","valid_fields","all_leaves_valid_fields","newly_masked_fields")],
        *[(name,pa.list_(reason)) for name in ("source_reason_groups","new_reason_groups","review_groups")],
        ("leaf_exceptions",pa.list_(leaf))])
