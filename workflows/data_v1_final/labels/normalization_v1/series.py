"""Auditable scalar/component/element and physical-invariant statistical views."""
from __future__ import annotations

import collections
import math


def inventory(item):
    fields = item["fields"]; basis = item["plan"]["element_basis"]
    rows = []
    def add(key, field, view, element=None, axis=None, physical_group=None):
        rows.append({"key": key, "source_field_key": field["field_key"], "source_field_id": field["field_id"],
            "view": view, "element_atomic_number": element, "axis": axis,
            "unit": field.get("unit"), "physical_group": physical_group,
            "normalization_policy": "DRAFT_STATISTICS_ONLY_MODEL_HEAD_AND_EQUIVARIANT_CONVENTION_UNDECIDED"})
    for f in fields:
        fid = str(f["field_id"])
        add(fid + "/raw", f, "raw")
        if f["element_reference_eligible"]:
            add(fid + "/residual", f, "TRAIN_element_reference_residual")
        if f["level"] in {"atom", "atom_vector"}:
            for z in basis:
                add(fid + "/raw/Z" + str(z), f, "raw_element", z)
        if f["level"] == "atom_vector":
            for axis in ("x", "y", "z", "norm"):
                add(fid + "/" + axis, f, "atom_vector_" + axis, axis=axis, physical_group=f["field_key"])
                for z in basis:
                    add(fid + "/" + axis + "/Z" + str(z), f, "atom_vector_" + axis + "_element", z, axis, f["field_key"])
    grouped = collections.defaultdict(list)
    for f in fields:
        if f["level"] in {"molecule_vector", "molecule_tensor"}:
            grouped[(f["task"], f["registry_id"], f["source_path"], f["level"])].append(f)
    physical = []
    for key, group in sorted(grouped.items()):
        mapping = {f["component"]: f["field_id"] for f in group}
        expected = ["x", "y", "z"] if key[3] == "molecule_vector" else ["xx", "xy", "yy", "xz", "yz", "zz"]
        if set(mapping) != set(expected):
            raise ValueError("INCOMPLETE_PHYSICAL_VECTOR_OR_TENSOR_GROUP")
        gkey = "physical/" + str(key[1]) + "/" + key[0]
        for kind in (["norm"] if len(expected) == 3 else ["frobenius_norm", "trace"]):
            add(gkey + "/" + kind, group[0], kind, physical_group=gkey)
        physical.append({"key": gkey, "kind": key[3], "components": expected,
                         "field_ids": [mapping[c] for c in expected], "label_frame": "stored source Cartesian frame",
                         "frame_equivalence_proven": False,
                         "head_normalization_convention": "DRAFT_REQUIRES_MODEL_LINE_AGREEMENT"})
    rows.sort(key=lambda r: r["key"])
    for i, row in enumerate(rows):
        row["field_id"] = i  # radix series id, not a registry field id or a model head
    return rows, physical


def energy_residual(value, numbers, model):
    if not model or "coefficients" not in model:
        return None
    counts = collections.Counter(numbers)
    if set(counts) - set(model["basis"]):
        raise ValueError("ENERGY_REFERENCE_ELEMENT_BASIS_DIFFERS")
    return value - (model["intercept"] + math.fsum(counts[z] * b for z, b in zip(model["basis"], model["coefficients"])))


def views(entries, numbers, physical, models):
    """Produce temporary values; never mutate the reader's source leaf arrays."""
    out = {}; by_id = {e["field_id"]: e for e in entries}; joint = {}
    for e in entries:
        f = e["field"]; fid = str(f["field_id"]); vals = e["values_float64"]; mask = e["value_mask"]
        valid = [v for v, keep in zip(vals, mask) if keep]
        if not all(math.isfinite(v) for v in valid):
            raise ValueError("NONFINITE_UNMASKED_FINAL_TRAIN_VALUE")
        out[fid + "/raw"] = valid
        if f["element_reference_eligible"]:
            if len(valid) > 1:
                raise ValueError("ENERGY_REFERENCE_REQUIRES_MOLECULE_SCALAR")
            value = energy_residual(valid[0], numbers, models.get(fid)) if valid else None
            out[fid + "/residual"] = [] if value is None else [value]
        if f["level"] in {"atom", "atom_vector"}:
            for v, keep, atom in zip(vals, mask, e["atom_indices"]):
                if type(atom) is not int or not 0 <= atom < len(numbers):
                    raise ValueError("FINAL_ATOM_INDEX_NOT_IN_VALIDATED_COORDINATE_ORDER")
                if keep:
                    out.setdefault(fid + "/raw/Z" + str(numbers[atom]), []).append(v)
        if f["level"] == "atom_vector":
            if vals and (len(vals) != 3 * len(numbers) or e["atom_indices"] != [i for i in range(len(numbers)) for _ in range(3)]):
                raise ValueError("ATOM_VECTOR_COMPONENT_ORDER_NOT_XYZ_PER_ATOM")
            for i in range(len(vals) // 3):
                triple = vals[3*i:3*i+3]; keep = mask[3*i:3*i+3]; z = numbers[i]
                for a, v, ok in zip(("x", "y", "z"), triple, keep):
                    if ok:
                        out.setdefault(fid + "/" + a, []).append(v)
                        out.setdefault(fid + "/" + a + "/Z" + str(z), []).append(v)
                if all(keep):
                    norm = math.hypot(*triple)
                    out.setdefault(fid + "/norm", []).append(norm)
                    out.setdefault(fid + "/norm/Z" + str(z), []).append(norm)
                    joint.setdefault(f["field_key"], []).append(triple)
    for group in physical:
        if not set(group["field_ids"]) <= set(by_id):
            continue
        entries_g = [by_id[fid] for fid in group["field_ids"]]
        if not all(len(e["values_float64"]) == 1 and e["value_mask"] == [True] for e in entries_g):
            continue
        a = [e["values_float64"][0] for e in entries_g]
        key = group["key"]; joint[key] = [a]
        if group["kind"] == "molecule_vector":
            out[key + "/norm"] = [math.hypot(*a)]
        else:
            xx, xy, yy, xz, yz, zz = a
            out[key + "/frobenius_norm"] = [math.hypot(xx, yy, zz, math.sqrt(2)*xy, math.sqrt(2)*xz, math.sqrt(2)*yz)]
            out[key + "/trace"] = [math.fsum((xx, yy, zz))]
    return out, joint
