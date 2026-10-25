"""Root-only stdlib preparation of bounded EA/size CPU v2 requests; no submission.

Run after Root integration, static review and the two source-equivalence proofs:
  python -B <Root>/workflows/data_v1_final/labels/cpu_variants_v2/materialize_requests_v2.py \
    --scope EA_known_seven --node compute-0-17 --job-name dv1_ea_known_seven_cpu_v2
  python -B <Root>/workflows/data_v1_final/labels/cpu_variants_v2/materialize_requests_v2.py \
    --scope size_rho_canonical_512 --node compute-0-17 --job-name dv1_size_rho_cpu_v2

Only small code/metadata files (<=2MiB each, <=32MiB total) are read or hashed.
No scientific modules, Parquet, SQLite, dictionaries, scheduler or tests run.
The original central <job>.json is preserved. Root later submits <job>.bound.json.
"""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import socket
import stat
import sys

RUN = Path("/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025")
REPO = RUN / "repository"
LABELS = REPO / "workflows/data_v1_final/labels"
CENTRAL = REPO / "workflows/data_v1_final/execution/cpu_analysis_v1"
POLICY = REPO / "configs/data_v1/cpu_analysis_small_scopes_v1.json"
PYTHON = "/share/home/zixiao/.conda/envs/chemprop/bin/python"
DEPS = "/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
SMALL_CAP = 2 * 1024**2
TOTAL_CAP = 32 * 1024**2
BODY_SUFFIXES = {".parquet", ".arrow", ".ipc", ".sqlite", ".db", ".lmdb", ".dict", ".npz", ".npy"}
SOURCES = {}
RAW = {}
SPECS = {
    "EA_known_seven": {"name": "ea", "memory_gib": 32, "wall_seconds": 3600,
        "output_cap_bytes": 64 * 1024**2, "entry": "ea_cpu_v2/bounded_probe.py",
        "parameters": {"known_cases": 7, "contexts": 14, "source_files": 6, "new_QM_calls": 0, "new_masks": 0}},
    "size_rho_canonical_512": {"name": "size", "memory_gib": 64, "wall_seconds": 7200,
        "output_cap_bytes": 8 * 1024**3, "entry": "size_cpu_v2/run_size.py",
        "parameters": {"records": 4251, "molecules": 512, "groups": 16, "final_registry_or_D4": False}},
}


def pin_shape(value):
    pin = {key: value[key] for key in ("path", "bytes", "sha256")}
    path = Path(pin["path"])
    if (not path.is_absolute() or ".." in path.parts or type(pin["bytes"]) is not int
            or pin["bytes"] < 0 or not re.fullmatch(r"[a-f0-9]{64}", pin["sha256"])):
        raise ValueError("MALFORMED_LITERAL_SOURCE_OR_INHERITED_REFERENCE")
    return pin


def identity(value):
    return value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns


def small(path, expected=None):
    path = Path(path)
    if (not path.is_absolute() or ".." in path.parts or path.suffix.lower() in BODY_SUFFIXES
            or expected is not None and pin_shape(expected)["bytes"] > SMALL_CAP):
        raise ValueError("SMALL_SOURCE_ONLY_NO_BODY_OR_LARGE_STAT:" + str(path))
    if path not in SOURCES:
        if any(p.is_symlink() for p in (path, *path.parents)):
            raise ValueError("LITERAL_SOURCE_PATH_REQUIRED")
        with path.open("rb") as stream:
            before = os.fstat(stream.fileno())
            if not stat.S_ISREG(before.st_mode) or before.st_uid != 1278 or before.st_size > SMALL_CAP:
                raise ValueError("SMALL_SOURCE_OWNER_TYPE_OR_CAP_DIFFERS:" + str(path))
            raw = stream.read(SMALL_CAP + 1)
            after = os.fstat(stream.fileno())
        if len(raw) != before.st_size or identity(before) != identity(after):
            raise ValueError("SMALL_SOURCE_CHANGED_DURING_READ")
        if sum(map(len, RAW.values())) + len(raw) > TOTAL_CAP:
            raise ValueError("TOTAL_SMALL_SOURCE_METADATA_OVER_32MIB")
        SOURCES[path] = {"path": str(path), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
        RAW[path] = raw
    pin = SOURCES[path]
    if expected is not None and pin != pin_shape(expected):
        raise ValueError("ACTUAL_ROOT_PHYSICAL_PIN_DIFFERS_NO_SILENT_REBIND:" + str(path))
    return pin


def load(path, expected=None):
    pin = small(path, expected)
    return json.loads(RAW[Path(pin["path"])].decode("utf-8-sig"))


def new_file(path, raw):
    if any(p.is_symlink() for p in (path.parent, *path.parent.parents)):
        raise ValueError("NEW_CONTROL_PATH_PARENT_SYMLINK")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode()


def refs_in(value):
    if isinstance(value, dict):
        if {"path", "bytes", "sha256"} <= set(value):
            yield pin_shape(value)
        for child in value.values():
            yield from refs_in(child)
    elif isinstance(value, list):
        for child in value:
            yield from refs_in(child)


def by_path(pins):
    result = {}
    for original in pins:
        pin = pin_shape(original)
        if pin["path"] in result and result[pin["path"]] != pin:
            raise ValueError("CONFLICTING_INHERITED_OR_SOURCE_PIN")
        result[pin["path"]] = pin
    return result


def source_closure(spec, template):
    proof_path = RUN / "control/root_sb3_size_ea_cpu_bindings_v2.json"
    proof = load(proof_path)
    if (proof["schema"] != "CPU_V2_SIZE_EA_DIRECTORY_BINDING_PROOF_V1" or proof["status"] != "PASS"
            or proof["root_baselines_observed_now"] is not True
            or proof["size_guard_original_function_bytes_unchanged_hard64"] is not True):
        raise ValueError("ACTUAL_ROOT_V2_SIZE_EA_SOURCE_PROOF_REQUIRED")
    proved_files = by_path(row["actual_root_variant_reference"] for row in proof["files"])
    template_rows = [row for row in proof["config_templates"]
                     if row["actual_root_template_reference"]["path"] == str(template)]
    if len(template_rows) != 1:
        raise ValueError("EXACT_ROOT_V2_TEMPLATE_NOT_IN_PROOF")
    small(template, template_rows[0]["actual_root_template_reference"])
    code = [LABELS / spec["entry"]]
    if spec["name"] == "size":
        code = [LABELS / "size_cpu_v2" / name for name in (
            "aggregate.py", "build_proposal.py", "rank_sql.py", "run_size.py",
            "size_reader.py", "size_shared.py", "size_worker.py")]
        code += [LABELS / "normalization_cpu_v2" / name for name in ("runtime.py", "reader.py")]
    for path in code:
        if str(path) not in proved_files:
            raise ValueError("RUNTIME_ROOT_FILE_NOT_IN_DIRECTORY_BINDING_PROOF")
        small(path, proved_files[str(path)])
    stream_proof = load(RUN / "control/root_sb3_stream_cpu_equivalence_v2.json")
    if stream_proof["schema"] != "STREAMING_CPU_V2_SOURCE_EQUIVALENCE_PROOF_V1" or stream_proof["status"] != "PASS":
        raise ValueError("ACTUAL_ROOT_STREAMING_V2_SOURCE_PROOF_REQUIRED")
    stream_files = by_path(row["actual_variant_reference"] for row in stream_proof["files"])
    for name in ("scan_v2.py", "reduce.py", "support.py", "compact.py", "calibration.py"):
        path = LABELS / "streaming_cpu_v2" / name
        if str(path) not in stream_files:
            raise ValueError("ACTUAL_ROOT_CPU_V2_STREAM_DEPENDENCY_NOT_PROVED")
        small(path, stream_files[str(path)])
    support = RAW[LABELS / "streaming_cpu_v2/support.py"]
    if b"from workflows.data_v1_final.execution.cpu_analysis_v1.runtime_v2 import" not in support:
        raise ValueError("NODE_LOCAL_RUNTIME_V2_NOT_THE_ACTUAL_SUPPORT_IMPORT")
    for name in ("source_mapping_v2.json", "verify_bindings_v2.py", "README.md", "materialize_requests_v2.py"):
        small(LABELS / "cpu_variants_v2" / name)
    small(LABELS / "cpu_variants_v2/source_mapping_v2.json", proof["mapping_actual_root_reference"])
    # Central preparation imports metadata-only policy. Pin every actual central
    # module exactly as the central builder itself does, including runtime_v2.
    small(CENTRAL / "submit_cpu_pilot_v3.py")
    for path in CENTRAL.glob("*.py"):
        small(path)
    return small(proof_path), template_rows[0]


def collect(scope_key, node):
    spec = SPECS[scope_key]
    policy = load(POLICY)
    if node not in policy["cpu_nodes"] or node == "compute-0-21":
        raise ValueError("REGISTERED_CPU_NODE_REQUIRED")
    scope = policy["scopes"][scope_key]
    for key in ("memory_gib", "wall_seconds", "output_cap_bytes", "parameters"):
        if scope[key] != spec[key]:
            raise ValueError("EXACT_BOUNDED_SCOPE_RESOURCE_OR_PARAMETER_DIFFERS:" + key)
    load(policy["decision_reference"]["path"], policy["decision_reference"])
    base = load(scope["base_request_reference"]["path"], scope["base_request_reference"])
    small(base["script_reference"]["path"], base["script_reference"])
    original_sources = by_path(base["source_references"])
    inherited_data = by_path(base.get("data_references", []))
    for pin in original_sources.values():
        small(pin["path"], pin)
    for pin in scope.get("authority_references", []):
        if original_sources.get(pin["path"]) != pin_shape(pin):
            raise ValueError("REGISTERED_ORIGINAL_SOURCE_AUTHORITY_NOT_IN_BASE_REQUEST")
    template = REPO / f"configs/data_v1/labels/{spec['name']}_cpu_v2.template.json"
    proof_ref, template_proof = source_closure(spec, template)
    cfg = load(template)
    if any(cfg[key] != spec[key] for key in ("memory_gib", "wall_seconds", "output_cap_bytes")) or cfg["workers"] != 16:
        raise ValueError("CONFIG_AND_REGISTERED_16CPU_RESOURCE_BUDGET_DIFFERS")
    binding = "support_source" if spec["name"] == "ea" else "scan_adapter"
    target = "support.py" if spec["name"] == "ea" else "scan_v2.py"
    expected_path = LABELS / "streaming_cpu_v2" / target
    if (cfg[binding]["path"] != str(expected_path)
            or cfg[binding] != template_proof["actual_root_binding_target_reference"]):
        raise ValueError("CONFIG_RUNTIME_BINDING_NOT_ACTUAL_ROOT_PROVED_TARGET")
    small(expected_path, cfg[binding])
    for pin in refs_in(cfg):
        if pin["path"] in original_sources:
            small(pin["path"], pin)
        elif Path(pin["path"]) in SOURCES and SOURCES[Path(pin["path"])] == pin:
            continue
        elif inherited_data.get(pin["path"]) != pin:
            raise ValueError("CONFIG_REFERENCE_NOT_ROOT_SOURCE_OR_INHERITED_DATA_AUTHORITY:" + pin["path"])
    if spec["name"] == "ea":
        if (cfg["schema"] != "EA_CANONICAL_BOUNDED_DIAGNOSTIC_V1" or len(cfg["cases"]) != 7
                or len(cfg["sources"]) != 6 or len(cfg["archives"]) != 3):
            raise ValueError("EA_SEVEN_CASE_FINITE_SCOPE_DIFFERS")
    elif (cfg["scope"] != "PROVISIONAL_SOURCE_TRAIN_PILOT" or cfg["final_authority"] is not None
            or cfg["final_dataset_manifest"] is not None
            or {k: cfg["expected_pilot"][k] for k in ("records", "molecules", "groups")}
               != {"records": 4251, "molecules": 512, "groups": 16}):
        raise ValueError("SIZE_BOUNDED_PILOT_NOT_FINAL_COMMON_SCOPE_REQUIRED")
    return spec, scope, base, template, cfg, proof_ref


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", choices=sorted(SPECS), required=True)
    parser.add_argument("--node", required=True)
    parser.add_argument("--job-name", required=True)
    parser.add_argument("--output", help="Optional new literal child of the frozen external_output_root")
    args = parser.parse_args()
    if (os.getuid() != 1278 or socket.gethostname().split(".")[0] != "sonmi"
            or Path(__file__).absolute() != LABELS / "cpu_variants_v2/materialize_requests_v2.py"):
        raise ValueError("ROOT_ACTUAL_METADATA_ENTRY_ON_SONMI_REQUIRED")
    if not re.fullmatch(r"dv1_[A-Za-z0-9_]+", args.job_name):
        raise ValueError("SAFE_NEW_DV1_JOB_NAME_REQUIRED")
    spec, scope, base, template, cfg, proof_ref = collect(args.scope, args.node)
    name = args.job_name
    allowed = Path(cfg["external_output_root"])
    output = Path(args.output) if args.output else allowed / name
    if (not output.is_absolute() or ".." in output.parts or output == allowed or allowed not in output.parents
            or any(p.is_symlink() for p in (output, *output.parents))):
        raise ValueError("NEW_LITERAL_EXTERNAL_OUTPUT_CHILD_REQUIRED")
    config = RUN / f"control/requests/{name}.run_actual.json"
    command_file = RUN / f"control/{name}.command.json"
    binding_file = RUN / f"control/{name}.cpu_v2_bindings.json"
    request = RUN / f"control/requests/{name}.json"
    bound = RUN / f"control/requests/{name}.bound.json"
    script = RUN / f"control/scripts/{name}.sbatch"
    receipt_file = RUN / f"control/{name}.materialization.json"
    intent = RUN / f"control/submissions/{name}.intent.json"
    destinations = (output, config, command_file, binding_file, request, bound, script, receipt_file,
                    intent, RUN / f"control/submissions/{name}.json", RUN / "artifacts/cpu_analysis_guards" / name)
    if any(path.exists() or path.is_symlink() for path in destinations):
        raise FileExistsError("FRESH_NAME_AND_OUTPUT_REQUIRED_NO_OVERWRITE_OR_AUTOMATIC_RETRY")
    new_file(config, RAW[template])
    config_ref = small(config)
    command = [PYTHON, "-B", str(LABELS / spec["entry"]), "--config", str(config),
               "--root-preflight", str(intent), "--output", str(output)]
    new_file(command_file, encoded(command))
    command_ref = small(command_file)
    inherited = copy.deepcopy(base.get("data_references", []))
    bindings = {"schema": "ROOT_SB3_CPU_V2_REQUEST_BINDINGS_V1", "status": "METADATA_ONLY_NOT_SUBMITTED",
        "scope_key": args.scope, "scope_parameters": scope["parameters"], "node": args.node,
        "cpus": 16, "memory_gib": spec["memory_gib"], "wall_seconds": spec["wall_seconds"],
        "scientific_output_cap_bytes": spec["output_cap_bytes"], "output_directory": str(output),
        "source_template": small(template), "run_actual_config": config_ref,
        "run_actual_config_bytes_identical_to_actual_root_template": True,
        "source_equivalence_proof": proof_ref, "command": command_ref,
        "base_request_reference": scope["base_request_reference"],
        "inherited_data_references": inherited,
        "inherited_data_body_or_stat_performed": False,
        "actual_root_source_references": sorted(SOURCES.values(), key=lambda r: r["path"]),
        "PYTHONPATH": str(REPO) + ":" + DEPS,
        "scientific_modules_imported": [], "scheduler_commands_run": [],
        "final_registry_or_normalization_claimed": False}
    new_file(binding_file, encoded(bindings))
    binding_ref = small(binding_file)
    expected_sources = dict(SOURCES)
    # Call the existing central metadata builder once. It neither submits nor
    # probes. Its original output is never edited, including after a failure.
    sys.path.insert(0, str(REPO))
    module = importlib.import_module("workflows.data_v1_final.execution.cpu_analysis_v1.prepare_request_v2")
    if Path(module.__file__).absolute() != CENTRAL / "prepare_request_v2.py":
        raise ValueError("CENTRAL_BUILDER_IMPORTED_FROM_OTHER_TREE")
    central_args = [str(CENTRAL / "prepare_request_v2.py"), "--scope", args.scope, "--node", args.node,
                    "--job-name", name, "--command-file", str(command_file)]
    for path in sorted(expected_sources, key=str):
        central_args += ["--source", str(path)]
    previous = sys.argv
    try:
        sys.argv = central_args
        module.main()
    finally:
        sys.argv = previous
    small(request)
    original_raw = RAW[request]
    prepared = json.loads(original_raw)
    prepared_sources = by_path(prepared["source_references"])
    if (prepared["execution_argv"] != command or prepared["data_references"] != inherited
            or prepared["memory_gib"] != spec["memory_gib"] or prepared["cpus"] != 16
            or any(prepared_sources.get(pin["path"]) != pin for pin in expected_sources.values())):
        raise ValueError("CENTRAL_REQUEST_NOT_THE_EXACT_PREPARED_SOURCE_OR_COMMAND_CLOSURE")
    small(script)
    partitions = re.findall(rb"(?m)^#SBATCH --partition=(\S+)$", RAW[script])
    if partitions != [b"cpu"] or prepared.get("partition", "cpu") != "cpu":
        raise ValueError("BOUND_CPU_PARTITION_REQUIRES_EXACT_REAL_SCRIPT_CPU_DIRECTIVE")
    # Add only new keys to a separate bound copy; central script/intent job names
    # and all original central request values remain exactly unchanged.
    additive = {"sb3_cpu_v2_binding_manifest_reference": binding_ref,
                "sb3_cpu_v2_data_locators": {"output_directory": str(output),
                    "run_actual_config_reference": config_ref, "command_reference": command_ref,
                    "inherited_body_or_stat_performed": False}}
    if "partition" not in prepared:
        additive["partition"] = "cpu"
    if set(additive) & set(prepared):
        raise ValueError("ADDITIVE_BOUND_FIELDS_ALREADY_EXIST")
    bound_value = {**copy.deepcopy(prepared), **additive}
    new_file(bound, encoded(bound_value))
    if request.read_bytes() != original_raw or any(bound_value[key] != value for key, value in prepared.items()):
        raise ValueError("ORIGINAL_CENTRAL_REQUEST_OR_VALUES_WERE_CHANGED")
    receipt = {"schema": "ROOT_SB3_CPU_V2_REQUEST_MATERIALIZATION_V1", "status": "PREPARED_NOT_SUBMITTED_NOT_EXECUTED",
        "created_at": datetime.now(timezone.utc).isoformat(), "scope": args.scope,
        "original_central_request": small(request), "bound_request_to_submit": small(bound),
        "original_central_request_bytes_preserved": True, "bound_only_additive_keys": sorted(additive),
        "script": small(script), "intent_path_not_created": str(intent), "binding_manifest": binding_ref,
        "source_references_count": len(prepared_sources), "inherited_data_references_count": len(inherited),
        "metadata_bytes_read_total": sum(map(len, RAW.values())), "individual_source_cap_bytes": SMALL_CAP,
        "prepared_submitter_argv_only": [PYTHON, "-B", "-m", "workflows.data_v1_final.execution.cpu_analysis_v1.submit_cpu_pilot_v3",
                                          "--request", str(bound)],
        "scheduler_commands_run": [], "scientific_data_bodies_opened": False, "science_executed": False}
    new_file(receipt_file, encoded(receipt))
    print(json.dumps({"status": receipt["status"], "central_request": str(request), "bound_request": str(bound),
                      "script": str(script), "receipt": str(receipt_file), "output": str(output)}))


if __name__ == "__main__":
    main()
