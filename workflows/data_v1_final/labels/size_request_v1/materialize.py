"""Root-only stdlib materializer for the frozen 512-molecule size pilot request.

Only code and small JSON/text metadata are read. No scientific modules, Parquet,
SQLite, scheduler command, QM, fitting, ranking, or submission is executed.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat

PROJECT = Path("/share/home/zixiao/descriptor_analysis")
RUN = PROJECT / "runs/data_v1_20261025"
REPOSITORY = RUN / "repository"
LABELS = REPOSITORY / "workflows/data_v1_final/labels"
PYTHON = "/share/home/zixiao/.conda/envs/chemprop/bin/python"
DEPS = PROJECT / "docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
MAX_PIN_BYTES = 2 * 1024**2
MAX_METADATA_TOTAL_BYTES = 32 * 1024**2
CAP = 8 * 1024**3
META = {}
DATA = {}
SOURCE_RAW = {}


def identity(path):
    s = path.stat()
    return (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)


def small_ref(path, expected=None):
    path = Path(path).absolute()
    if path in META:
        pin = META[path]
    else:
        if not path.is_absolute() or any(p.is_symlink() for p in (path, *path.parents)):
            raise ValueError("SMALL_PIN_PATH_NOT_LITERAL_REGULAR_PATH:" + str(path))
        s = path.stat()
        if not stat.S_ISREG(s.st_mode) or s.st_uid != 1278 or not 0 <= s.st_size <= MAX_PIN_BYTES:
            raise ValueError("SMALL_PIN_OWNER_TYPE_OR_2MIB_LIMIT:" + str(path))
        before = identity(path)
        raw = path.read_bytes()
        if identity(path) != before or len(raw) != s.st_size:
            raise ValueError("SMALL_PIN_CHANGED_WHILE_READ:" + str(path))
        if sum(len(v) for v in SOURCE_RAW.values()) + len(raw) > MAX_METADATA_TOTAL_BYTES:
            raise ValueError("SMALL_METADATA_TOTAL_32MIB_LIMIT")
        pin = {"path": str(path), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
        META[path] = pin
        SOURCE_RAW[path] = raw
    if expected is not None and any(expected[k] != pin[k] for k in ("path", "bytes", "sha256")):
        raise ValueError("ACTUAL_PATH_BYTES_HASH_DIFFERS_FROM_REFERENCE:" + str(path))
    return pin


def read_json(path, expected=None):
    pin = small_ref(path, expected)
    return json.loads(SOURCE_RAW[Path(pin["path"])].decode("utf-8-sig"))


def pinned_json(pin):
    return read_json(pin["path"], pin)


def inherit(value):
    """Record inherited data/authority refs without opening or hashing bodies."""
    if isinstance(value, dict):
        if {"path", "bytes", "sha256"} <= set(value):
            pin = {k: value[k] for k in ("path", "bytes", "sha256")}
            if not Path(pin["path"]).is_absolute() or not re.fullmatch(r"[a-f0-9]{64}", pin["sha256"]):
                raise ValueError("MALFORMED_INHERITED_REFERENCE")
            previous = DATA.setdefault(pin["path"], pin)
            if previous != pin:
                raise ValueError("CONFLICTING_INHERITED_REFERENCE:" + pin["path"])
        for item in value.values():
            inherit(item)
    elif isinstance(value, list):
        for item in value:
            inherit(item)


def write_new(path, raw):
    if any(p.is_symlink() for p in (path.parent, *path.parent.parents)):
        raise ValueError("OUTPUT_PARENT_SYMLINK")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode()


def collect_inputs():
    template = REPOSITORY / "configs/data_v1/labels/size_rho_pilot_v1.json"
    cfg = read_json(template)
    if (cfg["schema"] != "PHYSICAL_TARGET_SIZE_RHO_CONFIG_V1" or cfg["scope"] != "PROVISIONAL_SOURCE_TRAIN_PILOT"
            or cfg["workers"] != 16 or cfg["memory_gib"] != 64 or cfg["wall_seconds"] != 7200
            or cfg["output_cap_bytes"] != CAP or cfg["final_authority"] is not None
            or cfg["final_dataset_manifest"] is not None):
        raise ValueError("FROZEN_SIZE_PILOT_RESOURCE_OR_SCOPE_DIFFERS")
    expected_root = {
        "proposal_config": REPOSITORY / "configs/data_v1/labels/size_semantics_proposal_v1.json",
        "scan_adapter": LABELS / "streaming_v1/scan_v2.py"}
    for key, path in expected_root.items():
        if cfg[key]["path"] != str(path):
            raise ValueError("ROOT_RUNTIME_REFERENCE_POINTS_TO_OTHER_TREE:" + key)
        small_ref(path, cfg[key])
    production = ["aggregate.py", "build_proposal.py", "rank_sql.py", "run_size.py",
                  "size_reader.py", "size_shared.py", "size_worker.py"]
    code = [LABELS / "size_semantics_v1" / n for n in production]
    code += [LABELS / "streaming_v1" / n for n in ("scan_v2.py", "support.py", "compact.py", "calibration.py")]
    code += [LABELS / "normalization_v1" / n for n in ("runtime.py", "reader.py")]
    code += [REPOSITORY / "workflows/data_v1_final/execution/submit_reviewed.py", Path(__file__).absolute()]
    for path in code:
        if REPOSITORY not in path.parents:
            raise ValueError("RUNTIME_CODE_NOT_IN_ROOT_REPOSITORY")
        small_ref(path)
    proposal = pinned_json(cfg["proposal_config"])
    for pin in [proposal["registry"], *proposal["lineage_sources"]]:
        small_ref(pin["path"], pin)
    plan, scan, reduction = (pinned_json(cfg[k]) for k in ("plan", "mask_scan", "mask_reduction"))
    expected = cfg["expected_pilot"]
    actual = {"records": plan["records"], "molecules": plan["molecules"], "groups": len(plan["groups"]),
              "coverage_fingerprint": plan["coverage_fingerprint"]}
    if (actual != expected or actual["records"] != 4251 or actual["molecules"] != 512 or actual["groups"] != 16
            or plan["mode"] != "pilot" or scan["plan"] != cfg["plan"] or reduction["plan"] != cfg["plan"]
            or reduction["scan_manifest"] != cfg["mask_scan"] or reduction["records"] != actual["records"]
            or scan["coverage_fingerprint"] != actual["coverage_fingerprint"]
            or reduction["coverage_fingerprint"] != actual["coverage_fingerprint"] or reduction["stop_fields"]
            or any(r["new_mask_fraction"] > .01 for r in reduction["field_counts"].values())):
        raise ValueError("CLOSED_MASK_PILOT_SCOPE_OR_STOP_GATE_DIFFERS")
    source_cfg = pinned_json(plan["config"])
    small_ref(plan["field_map"]["path"], plan["field_map"])
    for pin in source_cfg["adapter_source_pins"]:
        if REPOSITORY not in Path(pin["path"]).parents:
            raise ValueError("LEGACY_IMPORT_WOULD_LOAD_CHILD_TREE")
        small_ref(pin["path"], pin)
    for key in ("registry", "mask_rules"):
        pin = source_cfg["sources"][key]
        small_ref(pin["path"], pin)
    groups = {g["group_index"]: g for g in plan["groups"]}
    seen = set()
    for pin in scan["group_receipts"]:
        row = pinned_json(pin)
        index = row["group_index"]
        if index in seen or index not in groups or row["status"] != "SOURCE_GROUP_SCANNED":
            raise ValueError("MASK_RECEIPT_GROUP_SET_NOT_COMPLETE")
        seen.add(index)
        if row["owner_index"] != groups[index]["owner_index"] or row["records"] != groups[index]["expected_records"]:
            raise ValueError("MASK_RECEIPT_OWNER_OR_RECORD_COUNT_DIFFERS")
        inherit(row)
    if seen != set(groups) or sum(g["expected_records"] for g in groups.values()) != 4251:
        raise ValueError("CANONICAL_PILOT_MASS_NOT_CONSERVED")
    for value in (cfg, proposal, plan, scan, reduction, source_cfg):
        inherit(value)
    fixtures_path = RUN / "control/size_rho_incremental_fixtures_v1.json"
    fixtures = read_json(fixtures_path)
    if (fixtures["status"] != "PASS" or fixtures["semantic_tests"] != 13
            or len(set(fixtures["actual_worker_pids"])) != 16
            or fixtures["real_scientific_label_bodies_read"] is not False):
        raise ValueError("ACTUAL_INCREMENTAL_FIXTURE_EVIDENCE_NOT_CLOSED")
    for name in ("sb3_size_rho_static_v1.json", "root_size_rho_integration_v1.json"):
        proof = read_json(RUN / "control" / name)
        if proof["status"] != "PASS" or proof["errors"]:
            raise ValueError("SIZE_SOURCE_STATIC_OR_ROOT_INTEGRATION_NOT_PASS")
    # These original metadata-generation refs may correctly name the child tree;
    # they are provenance evidence, never substituted for actual Root code pins.
    small_ref(RUN / "control/size_semantics_metadata_proposal_v1/metadata_receipt.json")
    small_ref(LABELS / "size_semantics_v1/size_rho.sbatch.in")
    return template, cfg, actual


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--job-name", default="dv1_size_rho_pilot_v1")
    p.add_argument("--output", help="New child of the frozen size external_output_root")
    args = p.parse_args()
    expected_entry = LABELS / "size_request_v1/materialize.py"
    if os.getuid() != 1278 or Path(__file__).absolute() != expected_entry:
        raise ValueError("RUN_THIS_MATERIALIZER_FROM_THE_ACTUAL_ROOT_REPOSITORY_ENTRY")
    if not re.fullmatch(r"dv1_[A-Za-z0-9_]+", args.job_name):
        raise ValueError("UNSAFE_OR_UNREVIEWABLE_JOB_NAME")
    template, cfg, actual = collect_inputs()
    name = args.job_name
    output = Path(args.output).absolute() if args.output else Path(cfg["external_output_root"]) / name
    allowed = Path(cfg["external_output_root"])
    if output == allowed or allowed not in output.parents or output.exists() or any(p.is_symlink() for p in (output, *output.parents)):
        raise ValueError("SIZE_OUTPUT_MUST_BE_A_NEW_LITERAL_EXTERNAL_CHILD")
    config = RUN / f"control/requests/{name}.run_actual.json"
    script = RUN / f"control/scripts/{name}.sbatch"
    request_path = RUN / f"control/requests/{name}.json"
    receipt_path = RUN / f"control/{name}.materialization.json"
    intent = RUN / f"control/submissions/{name}.intent.json"
    submission = RUN / f"control/submissions/{name}.json"
    if any(path.exists() for path in (config, script, request_path, receipt_path, intent, submission)):
        raise FileExistsError("NO_OVERWRITE_OR_AUTOMATIC_RETRY_OF_REGISTERED_SIZE_REQUEST")
    # Preserve the scientific configuration exactly; only the new physical
    # run_actual path differs. root_guard requires that exact path in the request.
    write_new(config, SOURCE_RAW[template])
    small_ref(config)
    template_script = LABELS / "size_semantics_v1/size_rho.sbatch.in"
    text = SOURCE_RAW[template_script].decode("utf-8")
    replacements = {
        "#SBATCH --job-name=dv1_size_rho_pilot_v1": "#SBATCH --job-name=" + name,
        "__LOG_PATH__": str(RUN / f"control/{name}_%j.out"),
        "__BOUND_NEW_SIZE_CONFIG_JSON__": str(config),
        "__FRESH_ROOT_INTENT_JSON__": str(intent),
        "__NEW_EXTERNAL_SIZE_DIRECTORY__": str(output),
        "export PYTHONPATH=" + str(DEPS): "export PYTHONPATH=" + str(REPOSITORY) + ":" + str(DEPS)}
    for old, new in replacements.items():
        if text.count(old) != 1:
            raise ValueError("FROZEN_SBATCH_TEMPLATE_BINDING_NOT_UNIQUE:" + old)
        text = text.replace(old, new)
    if "__" in text or "\r" in text or not text.startswith("#!/bin/bash\n"):
        raise ValueError("UNRESOLVED_SBATCH_BINDING_OR_NON_LF_SCRIPT")
    write_new(script, text.encode())
    script_pin = small_ref(script)
    sources = sorted((pin for pin in META.values() if pin["path"] != str(script)), key=lambda pin: pin["path"])
    sources_by_path = {p["path"] for p in sources}
    inherited = sorted((p for path, p in DATA.items() if path not in sources_by_path), key=lambda pin: pin["path"])
    now = datetime.now(timezone.utc).isoformat()
    request = {
        "kind": "analysis", "node": "compute-0-20", "cpus": 16, "memory_gib": 64,
        "wall_seconds": 7200, "estimated_peak_output_bytes": CAP, "pilot": True,
        "estimated_total_core_hours": 32, "script_reference": script_pin,
        "source_references": sources, "data_references": inherited,
        "root_review": {"status": "APPROVED", "reviewer": "root", "observed_at": now,
            "scope": "Exactly the existing canonical 512 molecules/4251 records/16 owner groups; two new source passes for physical-target size rho, provisional source TRAIN only",
            "checks": "Actual13 incremental fixtures PASS/16 distinct PIDs (4520430); actual child static and Root integration PASS. Root paths are freshly read and pinned; no child same-SHA substitution.",
            "resources": "Ordinary node20 CPU allocation64GiB/16CPU/2h/8GiB unique-inode output; worker2.5GiB RSS stops. Fresh submit_reviewed quota, all-user85% declared-memory guard and200GB reserve required; no336 live-memory exception.",
            "science": "69 signed scalars with5 matched-TRAIN HOF residuals; dipole L2, tensor Frobenius, atomvector norm RMS, approved atom/pair complete-value aggregations, one-record primary/one-molecule median sensitivity; no newmask or automatic family freeze.",
            "limits": "New size pass RSS/scientific outcomes not yet measured. Common/diagnostic final authority absent; no finalD2/D4/registry/Pprime claim. Old source/config bytes and thresholds unchanged.",
            "dependency_binding": "Runtime Root code+consumed small metadata individually<=2MiB hashed here; scientific Parquet/SQLite and oversized historical authority references inherited from already SHA-pinned metadata, not opened here."}}
    write_new(request_path, json_bytes(request))
    receipt = {"schema": "ROOT_SIZE_PILOT_REQUEST_MATERIALIZATION_V1", "status": "MATERIALIZED_NOT_SUBMITTED_NOT_EXECUTED",
               "request": small_ref(request_path), "run_actual_config": META[config], "script": script_pin,
               "template": META[template], "scientific_config_bytes_unchanged": True, "scope": actual,
               "source_references_count": len(sources), "inherited_data_references_count": len(inherited),
               "metadata_bytes_read_total": sum(len(v) for v in SOURCE_RAW.values()), "maximum_pin_bytes": MAX_PIN_BYTES,
               "runtime": {"python_logical_entry": PYTHON, "PYTHONPATH": str(REPOSITORY) + ":" + str(DEPS)},
               "submission_command_prepared_only": [PYTHON, "-B", str(REPOSITORY / "workflows/data_v1_final/execution/submit_reviewed.py"), "--request", str(request_path)],
               "scheduler_commands_run": [], "scientific_data_bodies_opened": False, "new_QM_calls": 0}
    write_new(receipt_path, json_bytes(receipt))
    print(json.dumps({"request": str(request_path), "script": str(script), "run_actual": str(config),
                      "receipt": str(receipt_path), "source_refs": len(sources), "status": receipt["status"]}))


if __name__ == "__main__":
    main()
