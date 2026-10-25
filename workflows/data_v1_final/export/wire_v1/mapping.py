"""Explicit physical targets and source components; never one head per audit row."""
from __future__ import annotations
import math
import numpy as np

TENSOR6 = ("xx", "xy", "yy", "xz", "yz", "zz")
TENSOR_POS = ((0, 0), (0, 1), (1, 1), (0, 2), (1, 2), (2, 2))


def preflight_registry(registry, mapping, *, require_final=True):
    fields = {row["field_key"]: row for row in registry["fields"] if row["status"] == "enabled"}
    if len(fields) != sum(row["status"] == "enabled" for row in registry["fields"]):
        raise ValueError("DUPLICATE_SOURCE_FIELD")
    if require_final and (not str(registry.get("status", "")).startswith("FROZEN")
                          or mapping.get("status") != "FROZEN"):
        raise ValueError("SCIENTIFIC_MAPPING_NOT_FROZEN")
    targets, used = {}, set()
    for target in mapping["physical_targets"]:
        target_id = target["target_id"]
        if target_id in targets:
            raise ValueError("DUPLICATE_PHYSICAL_TARGET")
        if target["group"] not in {"S", "D", "P"}:
            raise ValueError("PPRIME_IS_P_CONDITION_NOT_FOURTH_GROUP")
        if target["level"] not in {"molecule", "atom", "pair"}:
            raise ValueError("INVALID_TARGET_LEVEL")
        if target["kind"] not in {"scalar", "vector", "symmetric_tensor"}:
            raise ValueError("INVALID_TARGET_KIND")
        if target["geometry_source"] not in {"pm7", "uff_sprime"}:
            raise ValueError("INVALID_GEOMETRY_SOURCE")
        if target["condition"] == "Pprime" and (target["group"] != "P"
                                               or target["geometry_source"] != "uff_sprime"):
            raise ValueError("INVALID_PPRIME_CONTEXT")
        members = target["members"]
        if not members:
            raise ValueError("EMPTY_PHYSICAL_TARGET")
        for member in members:
            key = member["field_key"]
            if key not in fields or key in used:
                raise ValueError("MISSING_DISABLED_OR_DUPLICATED_SOURCE_COMPONENT")
            source = fields[key]
            for name in ("source_path", "registry_id", "component"):
                if source.get(name) != member.get(name):
                    raise ValueError("SOURCE_COMPONENT_MAPPING_MISMATCH")
            expected_semantic = {"molecule": ("molecule", "scalar"), "atom": ("atom", "scalar"),
                "sparse_atom_pair": ("pair", "scalar"), "molecule_vector": ("molecule", "vector"),
                "atom_vector": ("atom", "vector"), "molecule_tensor": ("molecule", "symmetric_tensor")}.get(source["level"])
            if expected_semantic != (target["level"], target["kind"]):
                raise ValueError("SOURCE_LEVEL_KIND_MAPPING_MISMATCH")
            if source["group"] != target["group"]:
                raise ValueError("SOURCE_GROUP_MISMATCH")
            if source["unit"] != target["unit"]:
                raise ValueError("UNIT_CONVERSION_NOT_DECLARED_BY_CONTRACT")
            if not target["unit"] or not target["family"]:
                raise ValueError("UNIT_AND_FAMILY_REQUIRED_NOT_GUESSED")
            if require_final:
                if target.get("unit_status") != "VERIFIED":
                    raise ValueError("UNIT_AUTHORITY_PENDING")
                if source.get("family_v1_final") != target["family"]:
                    raise ValueError("FINAL_FAMILY_NOT_BOUND")
                frame = source.get("reference_frame")
                if frame and frame.get("verification") != "VERIFIED":
                    raise ValueError("REFERENCE_FRAME_PENDING")
            used.add(key)
        if target["kind"] in {"vector", "symmetric_tensor"} and len(members) > 1:
            parents = {(fields[m["field_key"]].get("task"), fields[m["field_key"]].get("registry_id"),
                        fields[m["field_key"]].get("source_path")) for m in members}
            if len(parents) != 1:
                raise ValueError("VECTOR_OR_TENSOR_MIXES_PHYSICAL_SOURCE_TARGETS")
        if require_final and target["condition"] == "Pprime" and not registry.get("pprime", {}).get("computed_labels_available"):
            raise ValueError("PPRIME_LABELS_NOT_AVAILABLE")
        if target["kind"] == "scalar" and len(members) != 1:
            raise ValueError("SCALAR_REQUIRES_ONE_EXPLICIT_COMPONENT")
        if target["kind"] == "vector":
            if len(members) not in (1, 3) or target["mask_reduction"] != "all_components":
                raise ValueError("VECTOR_GROUPING_OR_MASK_POLICY")
            if len(members) == 3 and (target["component_order"] != ["x", "y", "z"]
                    or [m["component"] for m in members] != target["component_order"]):
                raise ValueError("VECTOR_COMPONENT_ORDER_REQUIRED")
        if target["kind"] == "symmetric_tensor":
            if (len(members) != 6 or tuple(target["component_order"]) != TENSOR6
                    or [m["component"] for m in members] != target["component_order"]):
                raise ValueError("TENSOR_SIX_COMPONENT_ORDER_REQUIRED")
            if target["storage"] not in {"symmetric6", "matrix3x3"}:
                raise ValueError("TENSOR_STORAGE_REQUIRED")
            if target["mask_reduction"] != "all_components":
                raise ValueError("TENSOR_MASK_POLICY_REQUIRED")
        if target["level"] == "pair":
            policy = target["pair_index_policy"]
            if type(policy["directed"]) is not bool or type(policy["allow_self"]) is not bool:
                raise ValueError("PAIR_INDEX_POLICY_REQUIRED")
        targets[target_id] = dict(target)
    if used != set(fields):
        raise ValueError("ENABLED_COMPONENTS_NOT_FULLY_MAPPED")
    return {"status": "FROZEN" if require_final else "CANDIDATE_NOT_TRAINING_ELIGIBLE",
            "physical_targets": targets, "source_component_count": len(fields),
            "physical_target_count": len(targets)}


def assemble_target(target, source_values):
    values = [np.asarray(source_values[m["field_key"]]) for m in target["members"]]
    if target["kind"] == "scalar" or (target["kind"] == "vector" and len(values) == 1):
        if len(values) != 1:
            raise ValueError("SCALAR_REQUIRES_SINGLE_EXPLICIT_COMPONENT")
        return values[0]
    if any(v.shape != values[0].shape for v in values):
        raise ValueError("SOURCE_COMPONENT_SHAPE_MISMATCH")
    packed = np.stack(values, axis=-1)
    if target["kind"] == "vector" or target["storage"] == "symmetric6":
        return packed
    result = np.empty(values[0].shape + (3, 3), dtype=packed.dtype)
    for component, (i, j) in zip(values, TENSOR_POS):
        result[..., i, j] = component
        result[..., j, i] = component
    return result


def validate_pairs(pairs, n_atoms, policy):
    if pairs.dtype.str != "<i4" or pairs.ndim != 2 or pairs.shape[1] != 2:
        raise ValueError("PAIR_DTYPE_OR_SHAPE")
    if np.any(pairs < 0) or np.any(pairs >= n_atoms):
        raise ValueError("PAIR_INDEX_OUT_OF_RANGE")
    if not policy["allow_self"] and np.any(pairs[:, 0] == pairs[:, 1]):
        raise ValueError("PAIR_SELF_INDEX")
    if not policy["directed"] and np.any(pairs[:, 0] > pairs[:, 1]):
        raise ValueError("UNDIRECTED_PAIR_ORDER")
    if len(pairs) != len(np.unique(pairs, axis=0)):
        raise ValueError("DUPLICATED_PAIR_INDEX")


def validate_geometry(metadata, arrays):
    if set(arrays) - {"atomic_numbers", "positions_A", "bond_pairs", "bond_order_codes"}:
        raise ValueError("UNDECLARED_GEOMETRY_ARRAY")
    if ("bond_pairs" in arrays) != ("bond_order_codes" in arrays):
        raise ValueError("BOND_ARRAYS_MUST_BE_PAIRED")
    z, pos = arrays["atomic_numbers"], arrays["positions_A"]
    n = metadata["n_atoms"]
    if type(n) is not int or n <= 0 or z.shape != (n,) or z.dtype.str != "<i2":
        raise ValueError("ATOMIC_NUMBERS_DTYPE_OR_SHAPE")
    if np.any(z < 1) or np.any(z > 118) or pos.shape != (n, 3) or pos.dtype.str != "<f4":
        raise ValueError("GEOMETRY_DTYPE_OR_SHAPE")
    if not np.isfinite(pos).all():
        raise ValueError("NONFINITE_GEOMETRY")
    if "bond_pairs" in arrays:
        validate_pairs(arrays["bond_pairs"], n, {"directed": False, "allow_self": False})
        if (arrays["bond_order_codes"].shape != (len(arrays["bond_pairs"]),)
                or arrays["bond_order_codes"].dtype.str not in {"|u1", "<i2", "<i4"}
                or np.any(arrays["bond_order_codes"] > 5) or np.any(arrays["bond_order_codes"] < 0)):
            raise ValueError("BOND_ORDER_SHAPE")


def validate_labels(metadata, arrays, compiled):
    n = metadata["n_atoms"]
    if type(n) is not int or n <= 0:
        raise ValueError("N_ATOMS_REQUIRED")
    if not isinstance(metadata.get("group_exposure_mask"), dict) or not isinstance(
            metadata.get("family_exposure_mask"), dict):
        raise ValueError("EXPOSURE_MASKS_REQUIRED")
    expected = set()
    for name, target in compiled["physical_targets"].items():
        value_key, valid_key, reason_key = ("values/" + name, "valid/" + name, "reason/" + name)
        expected.update((value_key, valid_key, reason_key))
        values, valid, reasons = arrays[value_key], arrays[valid_key], arrays[reason_key]
        leading = () if target["level"] == "molecule" else (n,)
        if target["level"] == "pair":
            pair_key = "pairs/" + name
            expected.add(pair_key)
            pairs = arrays[pair_key]
            validate_pairs(pairs, n, target["pair_index_policy"])
            leading = (len(pairs),)
        tail = () if target["kind"] == "scalar" else (
            (3,) if target["kind"] == "vector" else (
                (6,) if target["storage"] == "symmetric6" else (3, 3)))
        if values.shape != leading + tail or values.dtype.str != "<f4":
            raise ValueError("TARGET_VALUE_SHAPE_OR_DTYPE")
        if valid.shape != values.shape or valid.dtype.str != "|u1" or np.any(valid > 1):
            raise ValueError("TARGET_VALID_MASK")
        if reasons.shape != values.shape or reasons.dtype.str != "<u2":
            raise ValueError("TARGET_REASON_MASK")
        keep = valid.astype(bool)
        if np.any(~np.isfinite(values[keep])) or np.any(reasons[keep] != 0) or np.any(reasons[~keep] == 0):
            raise ValueError("VALIDITY_REASON_OR_NONFINITE_VALUE")
        if type(metadata["group_exposure_mask"].get(target["group"])) is not bool or type(
                metadata["family_exposure_mask"].get(target["family"])) is not bool:
            raise ValueError("EXPOSURE_MASK_KEY_OR_TYPE")
        if metadata["geometry_source"] != target["geometry_source"]:
            raise ValueError("TARGET_GEOMETRY_CONTEXT_MISMATCH")
        if target["kind"] == "symmetric_tensor" and target["storage"] == "matrix3x3":
            if not np.array_equal(valid, valid.swapaxes(-1, -2)):
                raise ValueError("TENSOR_MASK_NOT_SYMMETRIC")
            complete = np.all(keep, axis=(-1, -2))
            if not np.allclose(values[complete], values[complete].swapaxes(-1, -2), rtol=0, atol=0):
                raise ValueError("TENSOR_NOT_SYMMETRIC")
    if set(arrays) != expected:
        raise ValueError("UNDECLARED_OR_MISSING_TARGET_ARRAY")


def family_schema(compiled, family, geometry_source):
    selected = {key: value for key, value in compiled["physical_targets"].items()
                if value["family"] == family and value["geometry_source"] == geometry_source}
    if not selected:
        raise ValueError("EMPTY_FAMILY_GEOMETRY_TARGET_PARTITION")
    return {"kind": "labels", "family": family,
            "compiled": {**compiled, "physical_targets": selected,
                         "physical_target_count": len(selected),
                         "source_component_count": sum(len(v["members"]) for v in selected.values())}}


def main():
    import argparse
    import json
    from pathlib import Path
    from .codec import canonical_json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--candidate-only", action="store_true")
    args = parser.parse_args()
    registry = json.loads(args.registry.read_text(encoding="utf-8"))
    mapping = json.loads(args.mapping.read_text(encoding="utf-8"))
    result = preflight_registry(registry, mapping, require_final=not args.candidate_only)
    print(canonical_json(result).decode())


if __name__ == "__main__":
    main()
