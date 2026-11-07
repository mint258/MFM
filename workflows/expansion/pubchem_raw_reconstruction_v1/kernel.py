"""Original four-function kernel, with isolated byte-identical science imports."""
import json
import os
import time
import traceback
from types import SimpleNamespace
from .support import need, CooperativeStop

shared = SimpleNamespace(need=need)
files = SimpleNamespace(CooperativeStop=CooperativeStop)
policy = SimpleNamespace(CONTAINER_CAP=1024 ** 3, PENDING=32)
STOP = None
INITIALIZATION = {}

FLOAT_FEATURES = ("molecular_weight_Da", "tpsa_A2", "logp")
INT_FEATURES = ("heavy_atoms", "isotopic_atoms", "rings", "aromatic_rings", "rotatable_bonds", "hbd", "hba", "stereocenters")
TEXT_FEATURES = ("isomeric_smiles", "full_key", "wp5_key", "non_h_composition", "element_combination", "generic_murcko", "ecfp4_2048_hex")
FEATURE_KEYS = {"cid", "ordinal", "reasons", "source_smiles", "elements", "generic_ring_systems",
                *FLOAT_FEATURES, *INT_FEATURES, *TEXT_FEATURES}


def funnel(result, audit_flags, audit_parse, errors, original):
    """Preserve legacy reasons; undefined parse X bits never become false flags."""
    codes = list(errors)
    if not isinstance(result, dict) or type(result.get("reasons")) is not list:
        return "technicalUnresolved", [*codes, "DISPATCHER_RESULT_OR_REASONS_UNAVAILABLE"]
    if result.get("cid") != int(original["cid_source_ascii"]) or result.get("ordinal") != original["ordinal"]:
        codes.append("DISPATCHER_SOURCE_IDENTITY_MISMATCH")
    reasons = result["reasons"]
    full_boolean_audit = set(audit_flags) == {"X01", "X02", "X03", "X04", "X05"} and all(
        type(value) is bool for value in audit_flags.values())
    if reasons and all(reason in ("X01", "X02", "X03", "X04", "X05") for reason in reasons):
        expected = [name for name in ("X01", "X02", "X03", "X04", "X05") if audit_flags.get(name) is True]
        if audit_parse is not True or not full_boolean_audit or reasons != expected:
            codes.append("AUDIT_DISPATCHER_X_REASONS_CONFLICT")
        return ("technicalUnresolved", codes) if codes else ("chemReject", [])
    if reasons:
        return "technicalUnresolved", [*codes, "LEGACY_NON_X_REASON_PRESERVED:" + ",".join(map(str, reasons))]
    if audit_parse is not True or not full_boolean_audit or any(audit_flags.values()):
        codes.append("AUDIT_DISPATCHER_PARSE_OR_X_CONFLICT")
    if set(result) != FEATURE_KEYS or result.get("source_smiles") != original["source_smiles"]:
        codes.append("FULL_FEATURE_OR_SOURCE_FIELDS_DIFFER")
    try:
        json.dumps(result, allow_nan=False)
    except (ValueError, TypeError):
        codes.append("NONFINITE_OR_NONJSON_FEATURE_RESULT")
    return ("technicalUnresolved", codes) if codes else ("accepted", [])


def chemical_task(original):
    if STOP.is_set():
        raise files.CooperativeStop("STOP_BEFORE_NEXT_CHEMICAL_RECORD")
    from .science import features_legacy_compatible_v2 as compatible
    audit_flags, audit_parse, result, errors = {}, None, None, {}
    started, cpu = time.monotonic(), time.process_time()
    try:
        # The frozen signature is chemical_flags(smiles: str), not a Mol.
        molecule, audit_flags = compatible.chemical_flags(original["source_smiles"])
        audit_parse = molecule is not None
        del molecule
    except Exception as exc:
        errors["INDEPENDENT_X_AUDIT_EXCEPTION"] = {"type": type(exc).__name__, "message": str(exc), "traceback": traceback.format_exc()}
    audit_wall, audit_cpu = time.monotonic() - started, time.process_time() - cpu
    started, cpu = time.monotonic(), time.process_time()
    try:
        # This exact597 wrapper already includes original parse/X via legacy features.
        result = compatible.features_candidate(int(original["cid_source_ascii"]), original["source_smiles"], original["ordinal"])
    except Exception as exc:
        errors["COMPATIBLE_DISPATCHER_EXCEPTION"] = {"type": type(exc).__name__, "message": str(exc), "traceback": traceback.format_exc()}
    dispatch_wall, dispatch_cpu = time.monotonic() - started, time.process_time() - cpu
    category, codes = funnel(result, audit_flags, audit_parse, errors, original)
    value = {"input": original, "category": category, "technical_codes": codes,
        "audit_parse_succeeded": audit_parse, "audit_flags": audit_flags,
        "legacy_dispatcher_result": result, "errors": errors,
        "audit_wall_seconds": audit_wall, "audit_CPU_seconds": audit_cpu,
        "dispatcher_wall_seconds_includes_legacy_X_parse": dispatch_wall,
        "dispatcher_CPU_seconds_includes_legacy_X_parse": dispatch_cpu,
        "worker_pid": os.getpid(), "worker_initialization": INITIALIZATION}
    raw = json.dumps(value, ensure_ascii=False, allow_nan=True).encode()
    shared.need(len(raw) <= policy.CONTAINER_CAP // policy.PENDING, "RESULT_CONTAINER_STOP_NO_FEATURE_TRUNCATION")
    return value


def output_schema():
    import pyarrow as pa
    fields = [(name, pa.string()) for name in ("sample_group", "cid_source_ascii", "source_smiles", "source_smiles_sha256",
        "source_part_reference_json", "category", "audit_flags_json", "full_dispatcher_result_json", "error_evidence_json")]
    fields += [("ordinal", pa.int64()), ("worker_pid", pa.int64()), ("audit_parse_succeeded", pa.bool_()),
        ("technical_codes", pa.list_(pa.string())), ("legacy_reasons", pa.list_(pa.string()))]
    fields += [("audit_" + name, pa.bool_()) for name in ("X01", "X02", "X03", "X04", "X05")]
    fields += [(name, pa.float64()) for name in (*FLOAT_FEATURES, "audit_wall_seconds", "audit_CPU_seconds",
        "dispatcher_wall_seconds_includes_legacy_X_parse", "dispatcher_CPU_seconds_includes_legacy_X_parse")]
    fields += [(name, pa.int64()) for name in INT_FEATURES] + [(name, pa.string()) for name in TEXT_FEATURES]
    fields += [("elements", pa.list_(pa.int32())), ("generic_ring_systems", pa.list_(pa.string()))]
    return pa.schema(fields)


def parquet_row(value, group):
    original, feature = value["input"], value["legacy_dispatcher_result"] or {}
    encoded = {"sample_group": group, "ordinal": original["ordinal"], "cid_source_ascii": original["cid_source_ascii"],
        "source_smiles": original["source_smiles"], "source_smiles_sha256": original["source_smiles_sha256"],
        "source_part_reference_json": json.dumps(original["source_part"], sort_keys=True), "category": value["category"],
        "audit_parse_succeeded": value["audit_parse_succeeded"], "audit_flags_json": json.dumps(value["audit_flags"], sort_keys=True),
        "technical_codes": value["technical_codes"], "legacy_reasons": feature.get("reasons"),
        "full_dispatcher_result_json": json.dumps(value["legacy_dispatcher_result"], ensure_ascii=False, allow_nan=True),
        "error_evidence_json": json.dumps(value["errors"], ensure_ascii=False), "worker_pid": value["worker_pid"]}
    for name in ("X01", "X02", "X03", "X04", "X05"):
        encoded["audit_" + name] = value["audit_flags"].get(name)
    for name in (*FLOAT_FEATURES, *INT_FEATURES, *TEXT_FEATURES, "elements", "generic_ring_systems"):
        encoded[name] = feature.get(name)
    for name in ("audit_wall_seconds", "audit_CPU_seconds", "dispatcher_wall_seconds_includes_legacy_X_parse",
                 "dispatcher_CPU_seconds_includes_legacy_X_parse"):
        encoded[name] = value[name]
    return encoded
