"""Dynamic sparse-pair shape adapter; original source.py stays registered.

Each physical field owns its pair index. No sorting, mirroring, deduplication,
index shift or implicit value padding is performed.
"""
from __future__ import annotations
import numpy as np
from .source import extract, numeric_array, target_arrays as _BASE_TARGET_ARRAYS
from wire_v1.mapping import validate_pairs


def target_arrays(row, spec, target, n, *, compact_loader=None, annotations=None):
    if target["level"] != "pair":
        if any("n_pairs" in spec["components"][m["field_key"]]["shape"] for m in target["members"]):
            raise ValueError("N_PAIRS_ONLY_VALID_FOR_PAIR_TARGET")
        return _BASE_TARGET_ARRAYS(row, spec, target, n, compact_loader=compact_loader, annotations=annotations)
    projected_row = dict(row)
    components = dict(spec["components"])
    for member in target["members"]:
        key = member["field_key"]
        selector = dict(components[key])
        if type(selector.get("pair_index_base")) is not int or selector["pair_index_base"] != 0:
            raise ValueError("EXPLICIT_SOURCE_ZERO_BASED_PAIR_INDEX_REQUIRED_NO_AUTO_SHIFT")
        original = np.asarray(extract(row, selector["pairs"]))
        if original.shape == (0,):
            # Arrow's empty list has no rows from which a second axis could be
            # inferred. The explicit pair contract supplies that axis, not data.
            original = original.reshape(0, 2)
        if original.ndim != 2 or original.shape[1] != 2:
            raise ValueError("SOURCE_SPARSE_PAIR_SHAPE_MUST_BE_M_BY_2")
        pairs = numeric_array(original, "<i4", original.shape)
        validate_pairs(pairs, n, target["pair_index_policy"])
        shape = [len(pairs) if value == "n_pairs" else value for value in selector["shape"]]
        if shape != [len(pairs)]:
            raise ValueError("PAIR_SCALAR_DECLARED_SHAPE_MUST_MATCH_OWN_PAIR_COUNT")
        selector["shape"] = shape
        internal = "__source_pair_v2_" + key
        if internal in projected_row:
            raise ValueError("SOURCE_PAIR_PROJECTION_COLUMN_COLLISION")
        projected_row[internal] = pairs
        selector["pairs"] = {"column": internal}
        components[key] = selector
    return _BASE_TARGET_ARRAYS(projected_row, {**spec, "components": components}, target, n,
                               compact_loader=compact_loader, annotations=annotations)
