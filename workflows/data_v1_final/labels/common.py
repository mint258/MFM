"""Small, explicit readers shared by the v1 label metadata and CPU pilot tools.

These readers do not import or modify the historical WP5 implementation.  The
CELL semantics follow wp5_parquet_v2.py; source bytes and kinds remain visible.
"""
from __future__ import annotations

import hashlib
import json
import math
import time
from pathlib import Path

D20_NAMES = [
    "MolLogP", "MolMR", "TPSA", "LabuteASA", "ExactMolWt",
    "NumValenceElectrons", "HeavyAtomCount", "NumHeteroatoms", "NumHAcceptors",
    "NumHDonors", "FractionCSP3", "RingCount", "NumAromaticRings",
    "NumAliphaticRings", "NumSaturatedRings", "NumHeterocycles",
    "NumBridgeheadAtoms", "NumSpiroAtoms", "BertzCT", "HallKierAlpha",
]
OWNER_KEYS = ("record_id", "molecule_id", "attempt_id", "job_id", "task_id")
ALLOWED_STATUSES = {"SUCCESS", "PROPERTY_FAILED"}
MISSING = object()


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def reference(path):
    p = Path(path).absolute()
    return {"path": str(p), "bytes": p.stat().st_size, "sha256": sha256(p)}


def verify_reference(ref, *, content=True):
    p = Path(ref["path"])
    st = p.stat()
    if not p.is_file() or st.st_size != int(ref["bytes"]):
        raise ValueError("SOURCE_SIZE_OR_TYPE_DIFFERS:" + str(p))
    if content and sha256(p) != ref["sha256"]:
        raise ValueError("SOURCE_SHA256_DIFFERS:" + str(p))
    return p


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_json_new(path, value):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def storage_preflight(plan):
    """Require Root's fresh, actual account-quota receipt, never whole-disk df."""
    budget = plan["storage_budget"]
    receipt = read_json(verify_reference(budget["quota_receipt"]))
    if receipt.get("status") != "QUOTA_METADATA_VERIFIED":
        raise ValueError("ACTUAL_ACCOUNT_QUOTA_NOT_VERIFIED")
    age = time.time() - float(receipt["observed_at_epoch"])
    if not 0 <= age <= 3600:
        raise ValueError("QUOTA_RECEIPT_NOT_FRESH")
    floor = int(budget["minimum_remaining_bytes"])
    total = int(budget["total_declared_new_bytes"])
    if floor < 200_000_000_000 or total <= 0 or int(receipt["available_bytes"]) - total < floor:
        raise ValueError("STOP_ACCOUNT_QUOTA_WOULD_FALL_BELOW_200GB")
    return receipt


def _reshape(values, shape):
    if not shape:
        if len(values) != 1:
            raise ValueError("CELL_SCALAR_SHAPE_INVALID")
        return values[0]
    if len(shape) == 1:
        return values[:]
    stride = math.prod(shape[1:])
    return [_reshape(values[i * stride:(i + 1) * stride], shape[1:])
            for i in range(shape[0])]


def decode_cell(cell):
    """Retain ABSENT, NULL, JSON, bool and nonfinite semantics separately."""
    if cell is None or cell["kind"] == 9:
        return MISSING
    kind = cell["kind"]
    if kind == 0:
        return None
    if kind in (1, 2, 3, 4):
        return cell[{1: "f64", 2: "i64", 3: "boolean", 4: "text"}[kind]]
    if kind in (8, 10):
        return json.loads(cell["text"])
    if kind in (5, 6, 7):
        values = cell[{5: "array_f64", 6: "array_i64", 7: "array_bool"}[kind]]
        shape = cell["shape"]
        if (not isinstance(shape, list) or any(type(x) is not int or x < 0 for x in shape)
                or values is None or math.prod(shape) != len(values)):
            raise ValueError("CELL_SHAPE_INVALID")
        return _reshape(values, shape)
    raise ValueError("UNKNOWN_CELL_KIND:" + str(kind))


def numeric(value):
    return type(value) in (int, float) and math.isfinite(value)


def component_values(field, value, atoms):
    """Return physical leaves and atom indices; index/basis metadata is excluded.

    Nonfinite leaves are preserved for a later false mask.  A malformed layout
    rejects the field, rather than silently pooling whichever leaves survived.
    """
    if value is MISSING:
        return [], [], "SOURCE_CELL_ABSENT"
    if value is None:
        return [], [], "SOURCE_CELL_NULL"
    leaf = field["source_path"].split(".")[-1]
    comp = field["component"]
    level = field["level"]
    if level == "molecule":
        return [value], [None], None
    if not isinstance(value, list):
        return [], [], "ARRAY_TYPE_INVALID"
    if not value:
        return [], [], "SOURCE_CELL_EMPTY"
    if leaf in ("dipole_Debye", "molecular_quadrupole_traceless_au"):
        order = (["x", "y", "z"] if leaf == "dipole_Debye"
                 else ["xx", "xy", "yy", "xz", "yz", "zz"])
        if len(value) != len(order):
            return [], [], "MOLECULE_VECTOR_SHAPE_INVALID"
        return [value[order.index(comp)]], [None], None
    if leaf == "atomic_shell_population_e":
        if len(value) != atoms or any(not isinstance(x, dict) or comp not in x for x in value):
            return [], [], "SHELL_SHAPE_INVALID"
        return [x[comp] for x in value], list(range(atoms)), None
    if leaf == "fukui":
        order = ["f_plus", "f_minus", "f_radical"]
        if len(value) != atoms or any(not isinstance(x, list) or len(x) != 3 for x in value):
            return [], [], "FUKUI_SHAPE_INVALID"
        return [x[order.index(comp)] for x in value], list(range(atoms)), None
    layouts = {
        "enpart_one_center_eV": ("values", ["electron_electron", "electron_nuclear", "total"], "atom_index"),
        "enpart_pairs_eV": ("J_K_EE_EN_NN_C_total", ["J", "K", "EE", "EN", "NN", "C", "total"], None),
        "super_heavy_atom_rows": ("values", ["Dn", "De", "charge_density_q_minus_Z"], "atom_index"),
    }
    if leaf in layouts:
        key, order, atom_key = layouts[leaf]
        if any(not isinstance(x, dict) or not isinstance(x.get(key), list)
               or len(x[key]) != len(order) for x in value):
            return [], [], "COMPOUND_SHAPE_INVALID"
        if leaf == "enpart_one_center_eV" and len(value) != atoms:
            return [], [], "ONE_CENTER_ATOM_COUNT_INVALID"
        indices = [x.get(atom_key) if atom_key else None for x in value]
        if atom_key and any(type(i) is not int or not 0 <= i < atoms for i in indices):
            return [], [], "COMPOUND_ATOM_INDEX_INVALID"
        return [x[key][order.index(comp)] for x in value], indices, None
    pair_value = {"bond_orders": "value", "wiberg_pairs": "value",
                  "sigma_pi_entries": "value", "mulliken_overlap_population_pairs": "population_e"}
    if leaf in pair_value:
        key = pair_value[leaf]
        if any(not isinstance(x, dict) or key not in x for x in value):
            return [], [], "PAIR_VALUE_LAYOUT_INVALID"
        for pair in value:
            keys = ("atom_i", "atom_j") if leaf == "sigma_pi_entries" else ("i", "j")
            if any(type(pair.get(k)) is not int or not 0 <= pair[k] < atoms for k in keys):
                return [], [], "PAIR_INDEX_INVALID"
        return [x[key] for x in value], [None] * len(value), None
    if level == "atom_vector":
        if len(value) == atoms and all(isinstance(x, list) and len(x) == 3 for x in value):
            return [v for x in value for v in x], [i for i in range(atoms) for _ in range(3)], None
        if len(value) == 3 * atoms and all(not isinstance(x, (list, dict)) for x in value):
            return value, [i for i in range(atoms) for _ in range(3)], None
        return [], [], "ATOM_VECTOR_SHAPE_INVALID"
    if level == "atom":
        if len(value) != atoms or any(isinstance(x, (list, dict)) for x in value):
            return [], [], "ATOM_VALUE_SHAPE_INVALID"
        return value, list(range(atoms)), None
    return [], [], "UNSUPPORTED_PHYSICAL_LAYOUT"


def task_components(row, family, fields):
    atoms = int(row["total_atoms"])
    cells = {}
    if family not in ("D20", "D3"):
        for cell in row.get("values") or []:
            rid = int(cell["registry_id"])
            if rid in cells:
                raise ValueError("DUPLICATE_REGISTRY_CELL")
            cells[rid] = cell
    for field in fields:
        reason = None
        if family == "D20":
            values, masks, names = row.get("values_float64"), row.get("valid_mask"), row.get("descriptor_names")
            layout = (isinstance(values, list) and len(values) == 20 and isinstance(masks, list)
                      and len(masks) == 20 and all(type(x) is bool for x in masks))
            if not layout or not (names == D20_NAMES or (names is None and not any(masks))):
                value, reason = MISSING, "D20_SHAPE_OR_NAMES_INVALID"
            else:
                i = D20_NAMES.index(field["source_path"])
                value = values[i]
                if not masks[i]:
                    reason = "SOURCE_VALID_MASK_FALSE"
        elif family == "D3":
            value = row.get(field["source_path"], MISSING)
            issues = row.get("issues") or []
            if ("D3_MISSING_OR_NONFINITE:" + field["source_path"] in issues
                    or field["source_path"] == "SASA_atom_A2" and "D3_SASA_ATOM_MISSING_NONFINITE_OR_N_MISMATCH" in issues):
                reason = "SOURCE_D3_FAILURE_ISSUE"
        else:
            cell = cells.get(field["registry_id"])
            try:
                value = decode_cell(cell)
            except (ValueError, KeyError, TypeError) as exc:
                value, reason = MISSING, "CELL_DECODE_INVALID:" + str(exc)
            if field["registry_id"] in (row.get("numeric_issues") or []):
                reason = "SOURCE_NUMERIC_ISSUE"
        values, indices, layout_reason = component_values(field, value, atoms)
        yield field, values, indices, reason or layout_reason
