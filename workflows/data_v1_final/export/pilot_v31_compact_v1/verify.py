"""One caller-supplied 1000-PM7-sample comparison, with no hashes or F64 IO.

Each sample has role, molecule_index, conformer_index, identity and qa_sources.
qa_sources is [{path, gid, kind, geometry_role, target_ids}], containing the actual old
label contributors (including M.d20) and this P record's base/perturbed
geometry. Do not include a different conformer's molecule-topology anchor as
the P base geometry. identity may declare atom_permutation_new_to_old or
per-source atom_permutations=[{path,gid,source_to_M}], as emitted by assembly.

This file deliberately does not import assembly transformations. Expected
values come from the old store's own compiled targets, original values/valid
arrays and member/axis declarations. Source metadata and mask JSON are read
only by legacy_reader; neither old nor new payload hashes are computed.
"""

from __future__ import annotations

from collections import OrderedDict
from pathlib import Path

import numpy as np

from .codec import decode, encode_key
from .legacy_reader import OldStore


_TENSOR_POS = {"xx": (0, 0), "xy": (0, 1), "yy": (1, 1),
               "xz": (0, 2), "yz": (1, 2), "zz": (2, 2)}
_AXIS = {"x": 0, "y": 1, "z": 2}


class VerificationError(ValueError):
    """The one requested compact/legacy comparison found a mismatch."""


def _need(condition, message):
    if not condition:
        raise VerificationError(message)


def _same_bits(left, right):
    left, right = np.asarray(left, dtype="<f4"), np.asarray(right, dtype="<f4")
    return left.shape == right.shape and np.array_equal(left.view("<u4"), right.view("<u4"))


def _compare(actual, expected, label, totals):
    actual, expected = np.asarray(actual), np.asarray(expected, dtype="<f4")
    _need(actual.dtype.kind == "f" and actual.dtype.itemsize == 4,
          label + ": compact value must be f4")
    _need(actual.shape == expected.shape, label + ": shape mismatch")
    invalid = np.isnan(expected)
    _need(np.array_equal(np.isnan(actual), invalid), label + ": NaN/validmask mismatch")
    valid = ~invalid
    _need(np.isfinite(expected[valid]).all() and np.isfinite(actual[valid]).all(),
          label + ": nonfinite valid value")
    delta = np.abs(actual[valid].astype(np.float64) - expected[valid].astype(np.float64))
    tolerance = 1e-6 + 1e-6 * np.abs(expected[valid].astype(np.float64))
    _need(np.all(delta <= tolerance), label + ": numeric tolerance exceeded")
    totals["field_or_geometry_comparisons"] += 1
    totals["valid_values_compared"] += int(valid.sum())
    totals["invalid_nan_values_compared"] += int(invalid.sum())
    if delta.size:
        totals["max_absolute_delta"] = max(totals["max_absolute_delta"], float(delta.max()))


def _merge(expected, incoming, valid, label, previous):
    incoming, valid = np.asarray(incoming, dtype="<f4"), np.asarray(valid)
    _need(incoming.shape == expected.shape and valid.shape == expected.shape,
          label + ": old value/valid shape mismatch")
    _need(np.isin(valid, (0, 1)).all(), label + ": old validmask is not binary")
    valid = valid.astype(bool)
    _need(np.isfinite(incoming[valid]).all(), label + ": old valid value is nonfinite")
    if previous is not None:
        _need(_same_bits(previous[0], incoming) and np.array_equal(previous[1], valid),
              label + ": duplicate legacy raw values/valid differ; no validity union")
    expected[valid] = incoming[valid]
    return incoming.copy(), valid.copy()


def _permutation(identity, source, n):
    """Independently derive new-index -> this old source's atom index."""
    identity = identity or {}
    declared = []
    for item in identity.get("atom_permutations", []):
        if str(item.get("path")) == str(source["path"]) and item.get("gid") == source["gid"]:
            old_to_new = np.asarray(item["source_to_M"])
            _need(old_to_new.shape == (n,) and old_to_new.dtype.kind in "iu",
                  "invalid per-source atom permutation")
            _need(np.array_equal(np.sort(old_to_new), np.arange(n)),
                  "per-source atom permutation is not bijective")
            new_to_old = np.empty(n, dtype=np.intp)
            new_to_old[old_to_new.astype(np.intp)] = np.arange(n)
            declared.append(new_to_old)
    if "atom_permutation_new_to_old" in identity:
        new_to_old = np.asarray(identity["atom_permutation_new_to_old"])
        _need(new_to_old.shape == (n,) and new_to_old.dtype.kind in "iu"
              and np.array_equal(np.sort(new_to_old), np.arange(n)),
              "invalid new-to-old atom permutation")
        declared.append(new_to_old.astype(np.intp))
    if not declared:
        return np.arange(n, dtype=np.intp)
    _need(all(np.array_equal(declared[0], other) for other in declared[1:]),
          "inconsistent atom-permutation declarations for one source")
    return declared[0]


def _targets(schema, ordered=False):
    value = (schema.get("ordered_record_targets", {}) if ordered
             else schema.get("compiled", {}).get("physical_targets", {}))
    if isinstance(value, dict):
        return value.items()
    return ((entry["target_id"], entry) for entry in value)


def _old_field(record, column):
    """Locate by real field_key/member in the old schema, not the new tid."""
    key = column["field_key"]
    found = []
    for tid, target in _targets(record["schema"]):
        if "target_ids" in record and tid not in record["target_ids"]:
            continue
        members = target["members"]
        matches = [i for i, member in enumerate(members) if member["field_key"] == key]
        for member_index in matches:
            values = np.asarray(record["arrays"]["values/" + tid])
            valid = np.asarray(record["arrays"]["valid/" + tid])
            _need(values.shape == valid.shape, key + ": legacy values/mask shapes differ")
            kind = target["kind"]
            if kind == "vector":
                axis = (_AXIS[column["component"]] if len(members) == 1
                        else member_index)
                _need(values.shape[-1:] == (3,), key + ": legacy vector shape")
                values, valid = values[..., axis], valid[..., axis]
            elif kind == "symmetric_tensor":
                component = members[member_index]["component"]
                if target.get("storage") == "symmetric6":
                    _need(values.shape[-1:] == (6,), key + ": legacy tensor6 shape")
                    values, valid = values[..., member_index], valid[..., member_index]
                else:
                    _need(values.shape[-2:] == (3, 3), key + ": legacy tensor matrix shape")
                    i, j = _TENSOR_POS[component]
                    values, valid = values[..., i, j], valid[..., i, j]
            else:
                _need(kind == "scalar", key + ": unsupported old target kind")
            pairs = (record["arrays"]["pairs/" + tid]
                     if target["level"] in ("pair", "sparse_atom_pair") else None)
            found.append((values, valid, pairs))
    return found


def _pair_map(pair_index, n):
    pairs = np.asarray(pair_index)
    _need(pairs.ndim == 2 and pairs.shape[1] == 2
          and pairs.dtype.kind == "i" and pairs.dtype.itemsize == 2,
          "compact pair_index shape/dtype")
    _need(((pairs >= 0) & (pairs < n)).all(), "compact pair_index atom bounds")
    lookup = {tuple(map(int, pair)): row for row, pair in enumerate(pairs)}
    _need(len(lookup) == len(pairs), "duplicate compact pair_index row")
    return lookup


def _column_expected(records, column, category, shape, identity, n, pair_lookup):
    expected = np.full(shape, np.nan, dtype="<f4")
    key = column["field_key"]
    previous = None
    previous_pair_source = None
    for record in records:
        if record["kind"] != "labels":
            continue
        for values, valid, pairs in _old_field(record, column):
            if category in ("atom_labels", "atom_vectors"):
                permutation = _permutation(identity, record, n)
                _need(values.shape == (n,), key + ": old atom column shape")
                values, valid = values[permutation], valid[permutation]
            elif category == "pair_labels":
                pairs = np.asarray(pairs)
                _need(pairs.shape == (len(values), 2) and values.ndim == 1
                      and pairs.dtype.kind in "iu" and ((pairs >= 0) & (pairs < n)).all(),
                      key + ": old pair column shape/bounds")
                new_to_old = _permutation(identity, record, n)
                old_to_new = np.empty(n, dtype=np.intp)
                old_to_new[new_to_old] = np.arange(n)
                mapped = old_to_new[pairs]
                pair_source = (np.asarray(values, dtype="<f4"), np.asarray(valid), mapped)
                if previous_pair_source is not None:
                    _need(_same_bits(previous_pair_source[0], pair_source[0])
                          and np.array_equal(previous_pair_source[1], pair_source[1])
                          and np.array_equal(previous_pair_source[2], pair_source[2]),
                          key + ": duplicate original pair rows/values/valid differ")
                previous_pair_source = tuple(item.copy() for item in pair_source)
                aligned = np.zeros(shape, dtype="<f4")
                aligned_valid = np.zeros(shape, dtype="u1")
                seen = set()
                for old_row, endpoints in enumerate(mapped):
                    pair = tuple(map(int, endpoints))
                    _need(pair in pair_lookup and pair not in seen,
                          key + ": source pair missing from union or duplicated")
                    seen.add(pair)
                    row = pair_lookup[pair]
                    aligned[row], aligned_valid[row] = values[old_row], valid[old_row]
                values, valid = aligned, aligned_valid
            previous = _merge(expected, values, valid, key, previous)
    return expected


def _strings(arrays, prefix, name, count):
    data, offsets = arrays[prefix + name + "_utf8"], arrays[prefix + name + "_offsets"]
    _need(offsets.shape == (count + 1,) and offsets.dtype.kind in "iu"
          and offsets[0] == 0 and offsets[-1] == len(data)
          and np.all(offsets[1:] >= offsets[:-1]), "old r73 UTF8 offset structure")
    raw = data.tobytes()
    return [raw[int(a):int(b)].decode("utf-8") for a, b in zip(offsets[:-1], offsets[1:])]


def _r73(records, identity, n, compact, schema, pair_lookup, totals):
    layouts = [value for value in schema["target_layout"].values()
               if value["array_name"] == "r73_ordered"]
    _need(len(layouts) <= 1, "multiple r73 targets cannot share the four-array layout")
    if not layouts:
        return
    field_key = layouts[0]["members"][0]["field_key"]
    expected_structure = None
    expected_values = None
    previous_values = None
    for record in records:
        if record["kind"] != "labels":
            continue
        for tid, target in _targets(record["schema"], ordered=True):
            if "target_ids" in record and tid not in record["target_ids"]:
                continue
            if not any(member["field_key"] == field_key for member in target["members"]):
                continue
            arrays, prefix = record["arrays"], "transport/" + tid + "/"
            values = np.asarray(arrays[prefix + "values"])
            count = len(values)
            valid = np.asarray(arrays["valid/" + prefix])
            atom_i, atom_j = arrays[prefix + "atom_i"], arrays[prefix + "atom_j"]
            _need(atom_i.shape == atom_j.shape == valid.shape == values.shape == (count,)
                  and atom_i.dtype.kind in "iu" and atom_j.dtype.kind in "iu"
                  and ((atom_i >= 0) & (atom_i < n) & (atom_j >= 0) & (atom_j < n)).all(),
                  "old r73 endpoint/value structure")
            new_to_old = _permutation(identity, record, n)
            old_to_new = np.empty(n, dtype=np.intp)
            old_to_new[new_to_old] = np.arange(n)
            endpoints = np.column_stack((old_to_new[atom_i], old_to_new[atom_j]))
            basis_i = _strings(arrays, prefix, "basis_i", count)
            basis_j = _strings(arrays, prefix, "basis_j", count)
            channel = _strings(arrays, prefix, "channel", count)
            present = arrays[prefix + "channel_present"]
            onsite_present, onsite = arrays[prefix + "onsite_present"], arrays[prefix + "onsite"]
            _need(present.shape == onsite_present.shape == onsite.shape == (count,)
                  and np.isin(present, (0, 1)).all()
                  and np.isin(onsite_present, (0, 1)).all()
                  and np.isin(onsite, (0, 1)).all(), "old r73 optional fields")
            channels = [(basis_i[i], basis_j[i], channel[i] if present[i] else None)
                        for i in range(count)]
            tri_state = np.where(onsite_present, 1 + onsite, 0).astype("u1")
            structure = (endpoints, channels, tri_state)
            if expected_structure is None:
                expected_structure = structure
                expected_values = np.full((count,), np.nan, dtype="<f4")
            else:
                _need(np.array_equal(expected_structure[0], endpoints)
                      and expected_structure[1] == channels
                      and np.array_equal(expected_structure[2], tri_state),
                      "r73 contributor layouts differ; no concatenation or deduplication")
            previous_values = _merge(expected_values, values, valid, field_key, previous_values)
    arrays_by_name = {definition["name"]: compact.get(int(array_id))
                      for array_id, definition in schema["array_definitions"].items()}
    row = arrays_by_name["r73_pair_row"]
    codes = arrays_by_name["r73_channel_codes"]
    onsite = arrays_by_name["r73_onsite"]
    values = arrays_by_name["r73_values"]
    if expected_structure is None:
        _need(all(value is None or value.size == 0 for value in (row, codes, onsite, values)),
              "unexpected r73 records without an actual legacy contributor")
        return
    endpoints, channels, tri_state = expected_structure
    count = len(expected_values)
    _need(all(value is not None for value in (row, codes, onsite, values)),
          "missing compact r73 array")
    _need(row.dtype.kind == "u" and row.dtype.itemsize == 4
          and codes.dtype.kind == "u" and codes.dtype.itemsize == 2
          and onsite.dtype.kind == "u" and onsite.dtype.itemsize == 1,
          "compact r73 integer dtype mismatch")
    _need(row.shape == onsite.shape == values.shape == (count,) and codes.shape == (count, 3),
          "compact r73 K/order shape mismatch")
    expected_rows = []
    for pair in endpoints:
        key = tuple(map(int, pair))
        _need(key in pair_lookup, "r73 endpoint missing from compact pair_index")
        expected_rows.append(pair_lookup[key])
    _need(np.array_equal(row, expected_rows), "r73 pair_row/order/duplicates mismatch")
    codebook = schema["r73_channel_codebook"]
    _need(isinstance(codebook, list) and len(codebook) > 0, "r73 codebook must be the final list")
    decoded = []
    for triple in codes:
        strings = []
        for code in triple:
            _need(0 <= int(code) < len(codebook), "r73 channel code out of schema range")
            strings.append(None if int(code) == 0 else codebook[int(code)])
        decoded.append(tuple(strings))
    _need(decoded == channels, "r73 basis/channel presence/string/order mismatch")
    _need(np.array_equal(onsite, tri_state), "r73 onsite tri-state/order mismatch")
    _compare(values, expected_values, "r73 values", totals)
    totals["r73_records_compared"] += count


class _OldStores:
    def __init__(self):
        self.handles = OrderedDict()

    def get(self, path):
        path = str(path)
        if path in self.handles:
            self.handles.move_to_end(path)
            return self.handles[path]
        if len(self.handles) >= 64:
            _, handle = self.handles.popitem(last=False)
            handle.close()
        handle = OldStore(path)
        self.handles[path] = handle
        return handle

    def close(self):
        for handle in self.handles.values():
            handle.close()
        self.handles.clear()


def verify_samples(samples, compact_roots, schema):
    """Perform exactly the supplied 1000 PM7 sample checks and return summary.

    Compact roots are LMDB directories, read only through their default DB.
    M and P are each fetched once per sample. This function does not discover
    or draw more samples, write files, read F64, hash, or benchmark anything.
    """
    import lmdb

    samples = list(samples)
    _need(len(samples) == 1000, "this final check requires exactly 1000 supplied PM7 samples")
    names = {entry["name"]: int(array_id)
             for array_id, entry in schema["array_definitions"].items()}
    totals = {"status": "COMPLETE", "pm7_samples": 0,
              "field_or_geometry_comparisons": 0, "valid_values_compared": 0,
              "invalid_nan_values_compared": 0, "r73_records_compared": 0,
              "max_absolute_delta": 0.0, "absolute_tolerance": 1e-6,
              "relative_tolerance": 1e-6, "F64_read": False,
              "hashes_computed": False, "assembler_transformations_called": False}
    old = _OldStores()
    environments = {}
    seen_samples = set()
    try:
        for sample in samples:
            role = sample["role"]
            _need(role in ("TRAIN", "VAL") and role in compact_roots, "sample role has no compact root")
            sample_key = (role, sample["molecule_index"], sample["conformer_index"])
            _need(sample_key not in seen_samples, "duplicate PM7 sample")
            seen_samples.add(sample_key)
            if role not in environments:
                environments[role] = lmdb.open(str(Path(compact_roots[role])),
                    readonly=True, create=False, lock=False, readahead=False, subdir=True)
            with environments[role].begin(buffers=False) as transaction:
                raw_m = transaction.get(encode_key("M", sample["molecule_index"]))
                raw_p = transaction.get(encode_key("P", sample["molecule_index"], sample["conformer_index"]))
            _need(raw_m is not None and raw_p is not None, "sample M/P key missing")
            molecule, conformer = decode(raw_m), decode(raw_p)
            z = molecule[names["Z"]]
            _need(z.ndim == 1 and z.dtype.kind == "u" and z.dtype.itemsize == 1,
                  "M.Z must be a u1 atom axis")
            n = len(z)
            identity = sample.get("identity", {})
            records = []
            records_by_source = {}
            for source in sample["qa_sources"]:
                key = (str(source["path"]), source["gid"])
                if key in records_by_source:
                    previous = records_by_source[key]
                    _need(previous["kind"] == source["kind"], "duplicate QA source kind differs")
                    if source["kind"] == "labels":
                        if "target_ids" in previous and "target_ids" in source:
                            previous["target_ids"] = list(dict.fromkeys(
                                [*previous["target_ids"], *source["target_ids"]]))
                        else:
                            previous.pop("target_ids", None)
                    elif previous.get("geometry_role") != source.get("geometry_role"):
                        # Reuse the one old get if the same geometry is named
                        # in both coordinate slots; do not drop either role.
                        records.append(dict(previous, geometry_role=source.get("geometry_role")))
                    continue
                handle = old.get(source["path"])
                metadata, arrays = handle.get(source["gid"])
                _need(source["kind"] == handle.schema["kind"], "QA source kind differs from old schema")
                record = dict(source, schema=handle.schema, metadata=metadata, arrays=arrays)
                records_by_source[key] = record
                records.append(record)
            for geometry_role, name in (("base", "pos"), ("perturbed", "pos_perturbed")):
                candidates = [record for record in records if record["kind"] == "geometry"
                              and record.get("geometry_role") == geometry_role]
                actual = conformer.get(names[name])
                if not candidates:
                    _need(geometry_role != "base" and actual is not None,
                          "missing actual old base or compact perturbed coordinate array")
                    _compare(actual, np.full((n, 3), np.nan, dtype="<f4"), name, totals)
                    continue
                _need(actual is not None, "compact coordinate array missing")
                expected = None
                for record in candidates:
                    permutation = _permutation(identity, record, n)
                    positions = record["arrays"]["positions_A"]
                    _need(positions.shape == (n, 3), "old geometry atom count/coordinate shape")
                    current = np.asarray(positions[permutation], dtype="<f4")
                    if expected is not None:
                        _need(_same_bits(expected, current), "conflicting old geometry contributors")
                    expected = current
                    if geometry_role == "base":
                        _need(np.array_equal(z, record["arrays"]["atomic_numbers"][permutation]),
                              "M.Z atom permutation mismatch")
                _compare(actual, expected, name, totals)
            pair_index = conformer.get(names["pair_index"], np.empty((0, 2), dtype="i2"))
            pair_lookup = _pair_map(pair_index, n)
            for category in ("d20", "mol_labels", "atom_labels", "atom_vectors", "pair_labels"):
                entries = schema["columns"][category]
                record_arrays = molecule if category == "d20" else conformer
                actual = record_arrays.get(names[category])
                if actual is None:
                    _need(not entries, "missing compact label array: " + category)
                    continue
                required_shape = ((len(entries),) if category in ("d20", "mol_labels") else
                                  (n, len(entries), 3) if category == "atom_vectors" else
                                  (len(pair_index), len(entries)) if category == "pair_labels" else
                                  (n, len(entries)))
                _need(actual.shape == required_shape, category + ": compact column layout shape")
                for column in entries:
                    index = column["column_index"]
                    components = (column["components"] if category == "atom_vectors" else [column])
                    for axis, component in enumerate(components):
                        selected = (actual[:, index, axis] if category == "atom_vectors" else
                                    actual[index] if category in ("d20", "mol_labels") else actual[:, index])
                        expected = _column_expected(records, component, category, np.shape(selected),
                                                    identity, n, pair_lookup)
                        _compare(selected, expected, component["field_key"] + "/" + str(component.get("component")), totals)
            _r73(records, identity, n, conformer, schema, pair_lookup, totals)
            totals["pm7_samples"] += 1
        return totals
    finally:
        old.close()
        for environment in environments.values():
            environment.close()
