"""Root stdlib EA request materializer; preparation only, no source-data I/O.

After Root integration/review:
  python -B <repository>/workflows/data_v1_final/labels/ea_request_v1/materialize.py

Reads and hashes only actual Root code and small metadata pins (<=2MiB each).
The 30MB latest index, six Parquet files, three SQLite archives and compression
dictionary bodies are inherited data refs: not opened, hashed, or even stat'ed.
Creates a byte-identical run_actual config, node20/16CPU/32GiB/1h/64MiB sbatch,
reviewed request and materialization receipt. Never imports scientific/project
modules, queries a scheduler, submits a job, runs tests/QM, or changes old files.
Root subsequently invokes submit_reviewed.py; its fresh ordinary quota/85%
declared-memory guard remains mandatory. There is no node21 option or exception.
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
REPO = RUN / "repository"
LABELS = REPO / "workflows/data_v1_final/labels"
WP5 = PROJECT / "runs/phase1_wp5_20261011"
PYTHON = "/share/home/zixiao/.conda/envs/chemprop/bin/python"
DEPS = PROJECT / "docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
CAP = 64 * 1024**2
PIN_CAP = 2 * 1024**2
METADATA_CAP = 16 * 1024**2
FROZEN_CONFIG = {"bytes": 19259, "sha256": "17a8147478ab532612518ebf1958fc9c4b8d2fa75d527168da6023ee893f7b04"}
SOURCE = {}
RAW = {}
DATA = {}


def state(path):
    s = path.stat()
    return s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns


def pin_shape(value):
    pin = {k: value[k] for k in ("path", "bytes", "sha256")}
    if (not Path(pin["path"]).is_absolute() or type(pin["bytes"]) is not int or pin["bytes"] < 0
            or not re.fullmatch(r"[a-f0-9]{64}", pin["sha256"])):
        raise ValueError("MALFORMED_LITERAL_REFERENCE")
    return pin


def small(path, expected=None):
    """Only code/metadata inputs; reject scientific/decoder bodies before stat."""
    path = Path(path).absolute()
    if path.suffix.lower() in {".parquet", ".sqlite", ".lmdb", ".db", ".dict"}:
        raise ValueError("DATA_BODY_MUST_NOT_BE_OPENED_OR_STATED:" + str(path))
    if expected is not None and pin_shape(expected)["bytes"] > PIN_CAP:
        raise ValueError("DECLARED_SMALL_PIN_OVER_2MIB_NO_STAT:" + str(path))
    if path not in SOURCE:
        if any(p.is_symlink() for p in (path, *path.parents)):
            raise ValueError("SMALL_PIN_SYMLINK_PATH")
        s = path.stat()
        if not stat.S_ISREG(s.st_mode) or s.st_uid != 1278 or s.st_size > PIN_CAP:
            raise ValueError("SMALL_PIN_TYPE_OWNER_OR_SIZE_DIFFERS:" + str(path))
        before = state(path)
        raw = path.read_bytes()
        if len(raw) != s.st_size or state(path) != before:
            raise ValueError("SMALL_PIN_CHANGED_DURING_READ:" + str(path))
        if sum(len(v) for v in RAW.values()) + len(raw) > METADATA_CAP:
            raise ValueError("TOTAL_SMALL_METADATA_OVER_16MIB")
        SOURCE[path] = {"path": str(path), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
        RAW[path] = raw
    result = SOURCE[path]
    if expected is not None and pin_shape(expected) != result:
        raise ValueError("ACTUAL_PATH_BYTES_SHA_NOT_THE_PINNED_REFERENCE:" + str(path))
    return result


def read_json(path, expected=None):
    return json.loads(RAW[Path(small(path, expected)["path"])].decode("utf-8-sig"))


def pinned_json(pin):
    return read_json(pin["path"], pin)


def data_ref(value, role):
    """No Path.stat/exists/read on any inherited source or dictionary asset."""
    pin = pin_shape(value)
    previous = DATA.get(pin["path"])
    if previous is not None and pin != {k: previous[k] for k in pin}:
        raise ValueError("CONFLICTING_INHERITED_DATA_REFERENCE")
    DATA[pin["path"]] = {**pin, "binding_basis": "INHERITED_FROM_FRESHLY_SHA_CHECKED_SMALL_METADATA_NO_BODY_OR_STAT",
                         "data_role": role}


def new_file(path, raw):
    if any(p.is_symlink() for p in (path.parent, *path.parent.parents)):
        raise ValueError("NEW_CONTROL_FILE_PARENT_SYMLINK")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def encode(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode()


def inputs():
    template = REPO / "configs/data_v1/labels/ea_diagnostic_v1.json"
    expected = {"path": str(template), **FROZEN_CONFIG}
    cfg = read_json(template, expected)
    if (cfg["schema"] != "EA_CANONICAL_BOUNDED_DIAGNOSTIC_V1" or cfg["workers"] != 16
            or cfg["memory_gib"] != 32 or cfg["wall_seconds"] != 3600
            or cfg["output_cap_bytes"] != CAP or len(cfg["cases"]) != 7
            or len(cfg["sources"]) != 6 or len(cfg["archives"]) != 3):
        raise ValueError("EXACT_EA_DIAGNOSTIC_SCOPE_OR_RESOURCE_DIFFERS")
    probe = LABELS / "ea_diagnostic_v1/bounded_probe.py"
    sbatch = LABELS / "ea_diagnostic_v1/diagnostic.sbatch.in"
    for path in (probe, sbatch, LABELS / "ea_diagnostic_v1/PROPOSAL.md", Path(__file__).absolute(),
                 REPO / "workflows/data_v1_final/execution/submit_reviewed.py"):
        if REPO not in path.parents:
            raise ValueError("ACTUAL_RUNTIME_SOURCE_NOT_IN_ROOT_REPOSITORY")
        small(path)
    if cfg["support_source"]["path"] != str(LABELS / "streaming_v1/support.py"):
        raise ValueError("SUPPORT_SOURCE_IS_NOT_THE_ACTUAL_ROOT_PATH")
    for key in ("support_source", "archive_reader_v4", "archive_reader_v5", "scf_metadata"):
        pin = cfg[key]
        small(pin["path"], pin)
    dictionary = pinned_json(cfg["dictionary_manifest"])
    registry = pinned_json(cfg["physical_registry"])
    protocol = pinned_json(cfg["protocol"])
    if {r["registry_id"] for r in registry if r["task"] == "xtb_vipea"} != {751, 752}:
        raise ValueError("VIPEA_WIRE_REGISTRY_CHANGED")
    tasks = {t["name"]: t for t in protocol["tasks"]}
    if any(tasks[task]["args"] != args for task, args in cfg["expected_task_args"].items()):
        raise ValueError("FROZEN_SP_VIPEA_METHODS_CHANGED")
    metadata = {}
    for pin in cfg["metadata_sources"]:
        small(pin["path"], pin)
        if pin["path"].endswith(".json"):
            metadata[pin["path"]] = pinned_json(pin)
    def one(suffix):
        found = [value for path, value in metadata.items() if path.endswith(suffix)]
        if len(found) != 1:
            raise ValueError("SMALL_OWNER_AUTHORITY_NOT_UNIQUE:" + suffix)
        return found[0]
    projection = one("/sb3_catalog_projection_v1/source_files.json")
    verified = one("/D20_failure_aware_v2_4515602/verification_report.json")
    excerpt = one("/xtb_EA_actual_probe_closed_excerpt_v1.json")
    if verified["status"] != "PASS":
        raise ValueError("CLOSED_SOURCE_FULL_VERIFICATION_NOT_PASS")
    expected_cases = {(r["record_id"], r["molecule_id"], str(r["attempt_id"]), str(r["job_id"]), str(r["task_id"]),
                       r["EA_eV"], r["IP_eV"]) for r in excerpt["all7_extreme_sample_records"]}
    actual_cases = {(r["record_id"], r["molecule_id"], str(r["attempt_id"]), str(r["job_id"]), str(r["task_id"]),
                     r["EA_eV"], r["IP_eV"]) for r in cfg["cases"]}
    if expected_cases != actual_cases or len(actual_cases) != 7:
        raise ValueError("SEVEN_EXISTING_CASE_IDENTITIES_OR_VALUES_CHANGED")
    source_lookup = {r["path"]: r for r in projection}
    verified_lookup = {r["path"]: r for r in verified["files_verified"]}
    if sum(r["bytes"] for r in cfg["sources"]) != 737661761:
        raise ValueError("SIX_FILE_CONTAINER_BOUND_CHANGED")
    for pin in cfg["sources"]:
        if (pin_shape(source_lookup.get(pin["path"], {})) != pin_shape(pin)
                or pin_shape(verified_lookup.get(pin["path"], {})) != pin_shape(pin)
                or pin["family"] not in {"xtb_singlepoint", "xtb_vipea"}):
            raise ValueError("SIX_SOURCES_NOT_CANONICAL_PROJECTION_AND_FULL_READBACK_BOUND")
        data_ref(pin, "EXACT_OWNER_FAMILY_PARQUET")
    for pin in cfg["archives"]:
        if pin_shape(verified_lookup.get(pin["path"], {})) != pin_shape(pin):
            raise ValueError("ARCHIVE_NOT_CLOSED_FULL_READBACK_BOUND")
        data_ref(pin, "CLOSED_OWNER_ARCHIVE_PK_ONLY_DURING_ACTUAL_PROBE")
    if cfg["latest_molecules"]["path"] != str(WP5 / "acceptance/final_20261016_v1/catalog_closed_v2/latest_molecules.parquet"):
        raise ValueError("LATEST_OWNER_INDEX_NOT_THE_FROZEN_CANONICAL_PATH")
    data_ref(cfg["latest_molecules"], "CANONICAL_COMPLETE_RECEIPT_CONSISTENT_EXPORTED_OWNER_INDEX")
    dictionaries = dictionary["dictionaries"]
    if len(dictionaries) != 12 or len({r["calc_type"] for r in dictionaries}) != 12:
        raise ValueError("FROZEN_ARCHIVE_DECODER_REQUIRES_EXACTLY_TWELVE_DICTIONARIES")
    for pin in dictionaries:
        if pin["bytes"] > PIN_CAP:
            raise ValueError("UNEXPECTED_DECODER_DICTIONARY_SIZE")
        data_ref(pin, "FROZEN_DECODER_DICTIONARY_BODY_CHECKED_BY_ACTUAL_ARCHIVE_READER")
    # Bind the existing source-owner authority pointer without opening its large
    # catalog. The diagnostic itself will freshly check latest-index content.
    authority_cfg_path = REPO / "configs/data_v1/labels/streaming_v1.json"
    authority_cfg = read_json(authority_cfg_path)
    catalog = authority_cfg["sources"]["catalog"]
    data_ref(catalog, "INHERITED_ACCEPTED_OWNER_CATALOG_AUTHORITY_NOT_OPENED_HERE")
    for name in ("sb3_ea_diagnostic_static_v1.json", "root_ea_diagnostic_integration_v1.json"):
        proof = read_json(RUN / "control" / name)
        if proof["status"] != "PASS" or proof["errors"]:
            raise ValueError("EA_CHILD_STATIC_OR_ROOT_INTEGRATION_NOT_PASS")
    # Prove every original job metadata owner uses the pinned decoder/parser.
    # This is source lineage, not a statement that any SCC failure occurred.
    owner_jobs = {int(r["job_id"]) for r in cfg["cases"]}
    observed = set()
    for path, value in metadata.items():
        if path.endswith("/run.json"):
            options = value["options"]
            job = int(options["job_id"])
            if job not in owner_jobs or options["policy"] != "FAILURES_PLUS_STRATIFIED_RECORD_AUDIT_NO_INPUT":
                raise ValueError("ORIGINAL_OWNER_RUN_OR_RAW_POLICY_NOT_EXPECTED")
            observed.add(job)
            expected_bindings = {cfg["archive_reader_v4"]["path"]: cfg["archive_reader_v4"]["sha256"],
                                 cfg["archive_reader_v5"]["path"]: cfg["archive_reader_v5"]["sha256"],
                                 cfg["scf_metadata"]["path"]: cfg["scf_metadata"]["sha256"]}
            actual_bindings = {r["path"]: r["sha256"] for r in options["source_bindings"]}
            if any(actual_bindings.get(k) != v for k, v in expected_bindings.items()):
                raise ValueError("ORIGINAL_OWNER_SOURCE_LINEAGE_DIFFERS")
    if observed != owner_jobs:
        raise ValueError("ORIGINAL_OWNER_RUN_METADATA_COVERAGE_INCOMPLETE")
    return template, cfg, probe, sbatch, catalog


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--job-name", default="dv1_ea_diagnostic_v1")
    p.add_argument("--output", help="New child of the frozen EA external_output_root")
    a = p.parse_args()
    if os.getuid() != 1278 or Path(__file__).absolute() != LABELS / "ea_request_v1/materialize.py":
        raise ValueError("ROOT_MUST_RUN_THE_ACTUAL_ROOT_REPOSITORY_MATERIALIZER_ENTRY")
    if not re.fullmatch(r"dv1_[A-Za-z0-9_]+", a.job_name):
        raise ValueError("INVALID_REVIEWED_JOB_NAME")
    template, cfg, probe, sbatch, catalog = inputs()
    name = a.job_name
    allowed = Path(cfg["external_output_root"])
    output = Path(a.output).absolute() if a.output else allowed / name
    if output == allowed or allowed not in output.parents or output.exists() or any(p.is_symlink() for p in (output, *output.parents)):
        raise ValueError("EA_OUTPUT_MUST_BE_A_NEW_LITERAL_EXTERNAL_CHILD")
    config = RUN / f"control/requests/{name}.run_actual.json"
    script = RUN / f"control/scripts/{name}.sbatch"
    request_path = RUN / f"control/requests/{name}.json"
    receipt_path = RUN / f"control/{name}.materialization.json"
    intent = RUN / f"control/submissions/{name}.intent.json"
    submission = RUN / f"control/submissions/{name}.json"
    if any(path.exists() for path in (config, script, request_path, receipt_path, intent, submission)):
        raise FileExistsError("EA_REQUEST_ALREADY_EXISTS_NO_OVERWRITE_OR_AUTOMATIC_RETRY")
    new_file(config, RAW[template])
    small(config)
    text = RAW[sbatch].decode("utf-8")
    replacements = {
        "#SBATCH --job-name=dv1_ea_diagnostic_v1": "#SBATCH --job-name=" + name,
        "__LOG_PATH__": str(RUN / f"control/{name}_%j.out"),
        "__ROOT_BOUND_PROBE_PY__": str(probe), "__NEW_CONFIG_JSON__": str(config),
        "__FRESH_INTENT_JSON__": str(intent), "__NEW_EXTERNAL_OUTPUT__": str(output)}
    for old, new in replacements.items():
        if text.count(old) != 1:
            raise ValueError("EA_SBATCH_TEMPLATE_BINDING_NOT_UNIQUE:" + old)
        text = text.replace(old, new)
    expected_env = "export PYTHONPATH=" + str(REPO) + ":" + str(DEPS)
    if (expected_env not in text or "__" in text or "\r" in text or not text.startswith("#!/bin/bash\n")
            or "#SBATCH --nodelist=compute-0-20\n" not in text
            or "#SBATCH --mem=32G\n" not in text or "#SBATCH --time=01:00:00\n" not in text):
        raise ValueError("EA_ROOT_PATH_ENV_OR_ANALYSIS20_RESOURCE_BINDING_DIFFERS")
    new_file(script, text.encode())
    script_ref = small(script)
    refs = sorted((r for r in SOURCE.values() if r["path"] != str(script)), key=lambda r: r["path"])
    request = {
        "kind": "analysis", "node": "compute-0-20", "cpus": 16, "memory_gib": 32,
        "wall_seconds": 3600, "estimated_peak_output_bytes": CAP, "estimated_total_core_hours": 16,
        "pilot": True, "script_reference": script_ref, "source_references": refs,
        "data_references": sorted(DATA.values(), key=lambda r: r["path"]),
        "root_review": {"status": "APPROVED", "reviewer": "root", "observed_at": datetime.now(timezone.utc).isoformat(),
            "scope": "Seven already identified EA cases/six exact owner-family Parquet files/three original archives. Fresh canonical latest-owner join;14same-record SP/VIPEA contexts; retained canonical raw only if present; no all-population scan/QM/newmask.",
            "checks": "Actual EA childstatic and Root integration PASS;aef7b35. Original config remains byte-identical. Small metadata/actual Root runtime sources checked against literal path+bytes+SHA; old run policy/decoder lineage and closed full source verification checked.",
            "resources": "Ordinary node20 analysis16CPU32GiB1h/64MiB unique-inode output;16nonempty actual rowgroup partitions required by probe. Worker RSS stop1GiB;raw4MiB/call16MiBtotal. Fresh quota/200GBreserve/all-user85% declared-memory checks by submit_reviewed; no live-memory exception or node21 authority assumed.",
            "scientific_limits": "No inference of nonconvergence from NULL or missing raw. SP GFN2 and VIPEA GFN1 are non-equivalent; last printed TOTAL ENERGY has no assumed neutral stage. Magnitude/energy-closeness/gap-sign only diagnostic;390population count not reestablished. Cause remains unknown; no new masks or changed labels/status.",
            "data_binding": "Latest30MB, six Parquet, three SQLite,12dictionary bodies and large old owner catalog only inherited data refs: not stat'ed/opened/hashed here. Actual probe validates latest content and owner context, inherited source identities and raw SHA/input bundle when retained outputs are actually read."}}
    new_file(request_path, encode(request))
    receipt = {"schema": "ROOT_EA_DIAGNOSTIC_REQUEST_MATERIALIZATION_V1", "status": "MATERIALIZED_NOT_SUBMITTED_NOT_EXECUTED",
               "request": small(request_path), "script": script_ref, "run_actual_config": SOURCE[config],
               "frozen_template": SOURCE[template], "scientific_config_bytes_unchanged": True,
               "source_references_count": len(refs), "inherited_data_references_count": len(DATA),
               "small_metadata_bytes_read_total": sum(len(v) for v in RAW.values()), "small_pin_cap_bytes": PIN_CAP,
               "latest_owner_reference": cfg["latest_molecules"], "owner_catalog_authority_inherited": catalog,
               "runtime": {"logical_python": PYTHON, "PYTHONPATH": str(REPO) + ":" + str(DEPS)},
               "submission_argv_prepared_only": [PYTHON, "-B", str(REPO / "workflows/data_v1_final/execution/submit_reviewed.py"), "--request", str(request_path)],
               "scheduler_commands_run": [], "scientific_modules_imported": [], "scientific_data_body_reads_or_stats": [],
               "tests_run": [], "new_QM_calls": 0, "new_masks": 0}
    new_file(receipt_path, encode(receipt))
    print(json.dumps({"status": receipt["status"], "request": str(request_path), "script": str(script),
                      "run_actual": str(config), "receipt": str(receipt_path), "source_refs": len(refs), "data_refs": len(DATA)}))


if __name__ == "__main__":
    main()
