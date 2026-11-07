"""Explicit Arrow/WP5-CELL selectors; masks, shape and owner keys are authority."""
from __future__ import annotations
import json
import math
import struct
import numpy as np
from wire_v1.codec import canonical_json
from wire_v1.mapping import assemble_target
from .masks import restore


def decode_cell(cell):
    # WP5 CELL v2 wire types. ABSENT/NULL never become a valid numeric zero.
    if cell is None or cell["kind"] in {0, 9}:
        return None
    kind = cell["kind"]
    if kind in {1, 2, 3, 4}:
        return cell[{1: "f64", 2: "i64", 3: "boolean", 4: "text"}[kind]]
    if kind in {8, 10}:
        return json.loads(cell["text"])
    if kind in {5, 6, 7}:
        values = cell[{5: "array_f64", 6: "array_i64", 7: "array_bool"}[kind]]
        shape = cell["shape"]
        if not isinstance(shape, list) or any(type(v) is not int or v < 0 for v in shape) or values is None or math.prod(shape) != len(values):
            raise ValueError("WP5_CELL_SHAPE_INVALID")
        return np.asarray(values).reshape(shape).tolist()
    raise ValueError("WP5_CELL_KIND_NOT_SUPPORTED")


def descend(value, path):
    for key in path:
        if type(key) not in {str, int} or type(key) is bool:
            raise ValueError("EXPLICIT_STRING_OR_INTEGER_SELECTOR_REQUIRED")
        value = value[key]
    return value


def extract(row, spec):
    value = row[spec["column"]]
    if "cell_registry_id" in spec:
        matching = [c for c in value if c["registry_id"] == spec["cell_registry_id"]]
        if len(matching) != 1:
            raise ValueError("EXACTLY_ONE_DECLARED_REGISTRY_CELL_REQUIRED")
        value = decode_cell(matching[0])
    elif spec.get("decode") == "json":
        value = json.loads(value)
    elif spec.get("decode", "plain") != "plain":
        raise ValueError("UNDECLARED_SOURCE_DECODER")
    value = descend(value, spec.get("path", []))
    if "project" in spec:
        value = [descend(item, spec["project"]) for item in value]
    if "select_index" in spec:
        value = np.asarray(value)[..., spec["select_index"]]
    return value


def shape(spec, n):
    result = tuple(n if v == "n_atoms" else v for v in spec)
    if len(result) > 4 or any(type(v) is not int or v < 0 for v in result) or math.prod(result) > 16_000_000:
        raise ValueError("SOURCE_COMPONENT_SHAPE_OUTSIDE_CAP")
    return result


def numeric_array(value, dtype, expected_shape, *, reshape=False):
    raw = np.asarray(value)
    if raw.dtype.kind not in "biuf" or raw.dtype.hasobject:
        raise ValueError("SOURCE_NUMERIC_ARRAY_REQUIRED")
    if raw.shape != expected_shape:
        if not reshape or raw.size != math.prod(expected_shape):
            raise ValueError("SOURCE_DECLARED_SHAPE_DIFFERS")
        raw = raw.reshape(expected_shape)
    if dtype in {"|u1", "<u2", "<i2", "<i4"}:
        limits = np.iinfo(np.dtype(dtype))
        if np.any(~np.isfinite(raw)) or np.any(raw != np.floor(raw)) or np.any(raw < limits.min) or np.any(raw > limits.max):
            raise ValueError("INTEGER_MASK_OR_INDEX_CAST_WOULD_LOSE_INFORMATION")
    return np.ascontiguousarray(raw, dtype=dtype).reshape(expected_shape)


def geometry_arrays(row, spec, n):
    result = {}
    expected = {"atomic_numbers": ("<i2", (n,)), "positions_A": ("<f8", (n, 3))}
    for name, (dtype, dimensions) in expected.items():
        selector = spec["arrays"][name]
        result[name] = numeric_array(extract(row, selector), dtype, dimensions, reshape=selector.get("reshape", False))
    if "bond_pairs" in spec["arrays"]:
        pairs = np.asarray(extract(row, spec["arrays"]["bond_pairs"]))
        if pairs.ndim != 2 or pairs.shape[1] != 2:
            raise ValueError("BOND_PAIR_LAYOUT_INVALID")
        result["bond_pairs"] = numeric_array(pairs, "<i4", pairs.shape)
        result["bond_order_codes"] = numeric_array(extract(row, spec["arrays"]["bond_order_codes"]), "|u1", (len(pairs),))
    if set(result) != set(spec["arrays"]):
        raise ValueError("UNDECLARED_GEOMETRY_ARRAY_TRANSFORM")
    return result


def target_arrays(row, spec, target, n, *, compact_loader=None, annotations=None):
    values, valid, reason, pairs = {}, {}, {}, None
    compact_arrays, compact_members = {}, {}
    for member in target["members"]:
        key = member["field_key"]
        selector = spec["components"][key]
        dimensions = shape(selector["shape"], n)
        original = extract(row, selector["value"])
        indices = None
        if "atom_indices" in selector:
            if target["level"] != "atom" or target["kind"] != "scalar" or dimensions != (n,):
                raise ValueError("EXPLICIT_ATOM_SCATTER_ONLY_FOR_ATOM_SCALAR")
            raw_indices = np.asarray(extract(row, selector["atom_indices"]))
            indices = numeric_array(raw_indices, "<i4", (len(raw_indices),))
            if np.any(indices < 0) or np.any(indices >= n) or len(np.unique(indices)) != len(indices):
                raise ValueError("SOURCE_ATOM_SCATTER_INDICES_INVALID")
            dimensions = (len(indices),)
        if "compact" in selector:
            cs = selector["compact"]
            compact = compact_loader(cs) if compact_loader else extract(row, cs)
            restored = restore(compact, cs["field_id"], math.prod(dimensions))
            valid[key] = restored["valid"].reshape(dimensions)
            for scope, source_name in (("source", "source_reason_groups"), ("new", "new_reason_groups"), ("review", "review_groups")):
                compact_arrays["reason_fields_" + scope + "/" + key] = np.asarray(restored[source_name], dtype="<u2")
            partial = restored["partial_leaf_reason_codes"]
            compact_arrays["reason_leaf_index/" + key] = np.asarray([p["leaf_index"] for p in partial], dtype="<i4")
            compact_arrays["reason_leaf_code/" + key] = np.asarray([p["code"] for p in partial], dtype="<u2")
            compact_members[key] = {"field_id": cs["field_id"], "leaf_shape": list(dimensions)}
        else:
            valid[key] = numeric_array(extract(row, selector["valid"]), "|u1", dimensions, reshape=selector.get("reshape", False))
            reason[key] = numeric_array(extract(row, selector["reason"]), "<u2", dimensions, reshape=selector.get("reshape", False))
        if original is None:
            if selector.get("null_value_policy") != "masked_nan" or np.any(valid[key]):
                raise ValueError("NULL_SOURCE_REQUIRES_EXPLICIT_MASKED_NAN_POLICY_AND_ALL_FALSE_MASK")
            values[key] = np.full(dimensions, np.nan, dtype="<f8")
            if annotations is None:
                raise ValueError("NULL_PLACEHOLDER_SOURCE_ANNOTATION_REQUIRED")
            annotations.setdefault("_source_null_fields", []).append(key)
        else:
            values[key] = numeric_array(original, "<f8", dimensions, reshape=selector.get("reshape", False))
        if indices is not None:
            missing = np.setdiff1d(np.arange(n, dtype="<i4"), indices)
            code = selector.get("missing_atom_reason_code")
            if len(missing) and (type(code) is not int or not 0 < code < 65535):
                raise ValueError("MISSING_ATOM_REASON_REQUIRES_EXPLICIT_FROZEN_CODEBOOK_DECISION")
            dense_values = np.full(n, np.nan, dtype="<f8"); dense_values[indices] = values[key]
            dense_valid = np.zeros(n, dtype="|u1"); dense_valid[indices] = valid[key]
            values[key], valid[key] = dense_values, dense_valid
            if key in compact_members:
                index_key, code_key = "reason_leaf_index/" + key, "reason_leaf_code/" + key
                old = compact_arrays[index_key]
                compact_arrays[index_key] = np.concatenate((indices[old], missing)).astype("<i4")
                compact_arrays[code_key] = np.concatenate((compact_arrays[code_key], np.full(len(missing), code or 0, dtype="<u2")))
                compact_members[key]["leaf_shape"] = [n]
            else:
                dense_reasons = np.full(n, code or 0, dtype="<u2"); dense_reasons[indices] = reason[key]
                reason[key] = dense_reasons
        if np.any(valid[key] > 1):
            raise ValueError("SOURCE_MASK_NOT_BINARY")
        if target["level"] == "pair":
            pair = np.asarray(extract(row, selector["pairs"]))
            pair = numeric_array(pair, "<i4", (len(values[key]), 2))
            if pairs is not None and not np.array_equal(pair, pairs):
                raise ValueError("COMPONENTS_USE_DIFFERENT_PAIR_INDICES")
            pairs = pair
    tid = target["target_id"]
    if compact_members and len(compact_members) != len(target["members"]):
        raise ValueError("MIXED_REASON_GRANULARITY_WITHIN_PHYSICAL_TARGET")
    result = {"values/" + tid: assemble_target(target, values), "valid/" + tid: assemble_target(target, valid)}
    if compact_members:
        result.update(compact_arrays)
        if annotations is None:
            raise ValueError("COMPACT_REASON_GRANULARITY_HEADER_REQUIRED")
        annotations[tid] = {"mode": "field_set_and_sparse_generic_leaf_v1", "members": compact_members}
    else:
        result["reason/" + tid] = assemble_target(target, reason)
    if pairs is not None:
        result["pairs/" + tid] = pairs
    return result


def pack(arrays, annotations=None):
    # Internal staging retains float64. This envelope is NOT the final wire.
    descriptors, blocks, offset = [], [], 0
    for name, array in sorted(arrays.items()):
        array = np.asarray(array)
        if not array.flags.c_contiguous:
            array = array.copy(order="C")
        if array.dtype.str not in {"<f8", "<f4", "<i2", "<i4", "<i8", "<u2", "|u1"}:
            raise ValueError("STAGING_DTYPE_NOT_NUMERIC_WHITELIST")
        raw = array.tobytes()
        descriptors.append([name, array.dtype.str, list(array.shape), offset, len(raw)])
        blocks.append(raw); offset += len(raw)
    header = canonical_json({"arrays": descriptors, "reason_granularity": annotations or {}})
    raw = struct.pack("<I", len(header)) + header + b"".join(blocks)
    if len(raw) > 128 * 1024 ** 2:
        raise ValueError("STAGING_RECORD_EXCEEDS_128MIB")
    return raw


def unpack(raw):
    size = struct.unpack("<I", raw[:4])[0]
    descriptors = json.loads(raw[4:4 + size])["arrays"]
    body = memoryview(raw)[4 + size:]
    result, offset = {}, 0
    for name, dtype, dimensions, start, length in descriptors:
        if start != offset or length != math.prod(dimensions) * np.dtype(dtype).itemsize or start + length > len(body):
            raise ValueError("STAGING_OFFSET_OR_SHAPE")
        if name in result or np.dtype(dtype).str not in {"<f8", "<f4", "<i2", "<i4", "<i8", "<u2", "|u1"}:
            raise ValueError("STAGING_DESCRIPTOR_INVALID")
        result[name] = np.frombuffer(body[start:start + length], dtype=dtype).reshape(dimensions)
        offset += length
    if offset != len(body):
        raise ValueError("STAGING_TRAILING_BYTES")
    return result


def reason_annotations(raw):
    size = struct.unpack("<I", raw[:4])[0]
    return json.loads(raw[4:4 + size])["reason_granularity"]


def source_columns(spec):
    columns = {spec["keys"]["molecule_id"]}
    if spec.get("n_atoms_column"):
        columns.add(spec["n_atoms_column"])
    if spec.get("n_atoms_from_array"):
        columns.add(spec["n_atoms_from_array"])
    columns.update(v for k, v in spec["keys"].items() if v is not None and k != "geometry_source")
    columns.update(spec.get("owner_keys", {}).values())
    columns.update(spec.get("row_filters", {}))
    selectors = list(spec.get("arrays", {}).values())
    for component in spec.get("components", {}).values():
        selectors += [component[name] for name in ("value", "valid", "reason", "pairs", "atom_indices") if name in component]
        if "compact" in component and "column" in component["compact"]:
            selectors.append(component["compact"])
        if "compact" in component and "task_code_column" in component["compact"]:
            columns.add(component["compact"]["task_code_column"])
    columns.update(s["column"] for s in selectors)
    return sorted(columns)
