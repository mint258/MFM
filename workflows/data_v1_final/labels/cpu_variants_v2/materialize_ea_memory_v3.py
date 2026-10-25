"""Small stdlib source proof and fresh EA memory-diagnostic request preparation.

The original 1GiB ru_maxrss guard and science remain unchanged. v3 only writes
bounded worker initial/failure process metadata; it does not assert a false alarm.
Linux getrusage documents usage preservation over execve, but that is only a
possible mechanism: https://man7.org/linux/man-pages/man2/getrusage.2.html
The actual failed job's 14 ALLOW samples reached 17,691,910,144B tree RSS, so a
real per-worker >1GiB peak remains possible. Per-worker evidence must decide.

Root source proof only:
  python -B <Root>/workflows/data_v1_final/labels/cpu_variants_v2/materialize_ea_memory_v3.py \
    --proof-only --proof-output <run>/control/root_ea_worker_memory_v3_source_proof.json
Root metadata preparation, not submission:
  python -B <Root>/workflows/data_v1_final/labels/cpu_variants_v2/materialize_ea_memory_v3.py \
    --node compute-0-17 --job-name dv1_ea_known_seven_memory_v3
"""
from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import importlib.util
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
HERE = LABELS / "cpu_variants_v2"
LEDGER = LABELS / "ea_cpu_v2/memory_v3_source_edits.json"
ENTRY = LABELS / "ea_cpu_v2/bounded_probe_v3.py"


def bootstrap_small(path):
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("ROOT_BOOTSTRAP_SMALL_LITERAL_PATH_REQUIRED")
    with path.open("rb") as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_uid != 1278 or before.st_size > 2 * 1024**2:
            raise ValueError("ROOT_BOOTSTRAP_SMALL_CODE_METADATA_CAP_OR_OWNER")
        raw = stream.read(2 * 1024**2 + 1)
        after = os.fstat(stream.fileno())
    if (len(raw) != before.st_size or (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
            != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)):
        raise ValueError("ROOT_BOOTSTRAP_SMALL_FILE_CHANGED")
    return raw


def metadata_helper():
    # Bootstrap only two small metadata/code files before reusing the frozen,
    # stdlib-only Root helper. No scientific module or main function is imported.
    raw = bootstrap_small(LEDGER)
    ledger = json.loads(raw)
    pin = ledger["metadata_helper_actual_root_reference"]
    path = HERE / "materialize_requests_v2.py"
    source = bootstrap_small(path)
    if (pin["path"] != str(path) or len(source) != pin["bytes"] or len(source) > 2 * 1024**2
            or hashlib.sha256(source).hexdigest() != pin["sha256"]):
        raise ValueError("ACTUAL_FROZEN_ROOT_METADATA_HELPER_DIFFERS")
    spec = importlib.util.spec_from_file_location("_ea_memory_v3_stdlib_metadata", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.small(path, pin)
    module.small(LEDGER, {"path": str(LEDGER), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
    module.small(Path(__file__).absolute())
    return module, ledger


def source_proof(h, ledger):
    if (ledger["schema"] != "EA_WORKER_MEMORY_DIAGNOSTIC_SOURCE_EDITS_V3"
            or ledger["original_limit_bytes"] != 1073741824
            or ledger["science_or_scope_change"] is not False):
        raise ValueError("UNKNOWN_OR_CHANGED_RESOURCE_DIAGNOSTIC_SCOPE")
    baseline = Path(ledger["baseline_actual_root_reference"]["path"])
    if baseline != LABELS / "ea_cpu_v2/bounded_probe.py" or ledger["intended_root_variant_path"] != str(ENTRY):
        raise ValueError("EXACT_ROOT_EA_V2_TO_V3_SOURCE_PATHS_REQUIRED")
    old_pin = h.small(baseline, ledger["baseline_actual_root_reference"])
    new_pin = h.small(ENTRY, ledger["prepared_child_variant_reference"] | {"path": str(ENTRY)})
    old, new = h.RAW[baseline].decode(), h.RAW[ENTRY].decode()
    expected = old
    if len(ledger["edits"]) != 7:
        raise ValueError("EXACT_SEVEN_RESOURCE_INSTRUMENTATION_EDITS_REQUIRED")
    for edit in ledger["edits"]:
        if edit["kind"] != "bounded_resource_instrumentation" or expected.count(edit["old"]) != 1:
            raise ValueError("RESOURCE_EDIT_NOT_DECLARED_OR_UNIQUE")
        expected = expected.replace(edit["old"], edit["new"])
    restored = new
    for edit in reversed(ledger["edits"]):
        if restored.count(edit["new"]) != 1:
            raise ValueError("RESOURCE_EDIT_INVERSE_NOT_UNIQUE")
        restored = restored.replace(edit["new"], edit["old"])
    if expected.encode() != h.RAW[ENTRY] or restored.encode() != h.RAW[baseline]:
        raise ValueError("RESOURCE_EDIT_FULL_FILE_INVERSE_BYTES_DIFFER")
    guard = ledger["original_guard_bytes"]
    if old.count(guard) != 1 or new.count(guard) != 1:
        raise ValueError("ORIGINAL_ONE_GIB_RU_MAXRSS_GUARD_LITERAL_CHANGED")
    before, after = ast.parse(old), ast.parse(new)
    if ast.dump(before, include_attributes=False) != ast.dump(ast.parse(restored), include_attributes=False):
        raise ValueError("MODULE_AST_AFTER_RESOURCE_INVERSE_DIFFERS")
    old_functions = {n.name: n for n in before.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    new_functions = {n.name: n for n in after.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    functions = []
    for key, fn in old_functions.items():
        unchanged = key not in {"initialize", "project", "main"}
        equal = (key in new_functions and ast.get_source_segment(old, fn)
                 == ast.get_source_segment(new, new_functions[key]))
        if unchanged and not equal:
            raise ValueError("UNDECLARED_NONRESOURCE_FUNCTION_BYTES_CHANGED:" + key)
        functions.append({"function": key, "actual_source_bytes_identical": equal,
                          "only_declared_resource_edits_inverse_to_original": True})
    if set(new_functions) - set(old_functions) != {
            "_memory_snapshot", "_memory_note", "_memory_write", "_memory_start", "_memory_batches", "_project"}:
        raise ValueError("UNDECLARED_NEW_FUNCTION_SET")
    return {"schema": "EA_WORKER_MEMORY_DIAGNOSTIC_SOURCE_PROOF_V3", "status": "PASS",
        "baseline_actual_root_reference": old_pin, "variant_actual_root_reference": new_pin,
        "source_ledger_actual_root_reference": h.small(LEDGER),
        "inverse_complete_file_bytes_identical": True, "inverse_complete_module_ast_identical": True,
        "original_ru_maxrss_guard_literal_bytes_unchanged": True, "worker_limit_bytes_unchanged": 1073741824,
        "functions": functions, "resource_only_edited_existing_functions": ["initialize", "project", "main"],
        "maximum_worker_metadata_file_bytes": 1048576, "existing_output_cap_bytes": 67108864,
        "scientific_modules_imported": [], "science_executed": False,
        "live_RSS_guard_substitution_or_limit_increase": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proof-only", action="store_true")
    parser.add_argument("--proof-output")
    parser.add_argument("--node")
    parser.add_argument("--job-name")
    args = parser.parse_args()
    if (os.getuid() != 1278 or socket.gethostname().split(".")[0] != "sonmi"
            or Path(__file__).absolute() != HERE / "materialize_ea_memory_v3.py"):
        raise ValueError("ACTUAL_ROOT_STDLIB_METADATA_ENTRY_ON_SONMI_REQUIRED")
    h, ledger = metadata_helper()
    proof = source_proof(h, ledger)
    if args.proof_only:
        path = Path(args.proof_output or "")
        if not path.is_absolute() or RUN / "control" not in path.parents:
            raise ValueError("NEW_LITERAL_RUN_CONTROL_PROOF_PATH_REQUIRED")
        h.new_file(path, h.encoded(proof))
        print(json.dumps({"status": "PASS_SOURCE_ONLY_NOT_SCIENCE", "proof": h.small(path)}))
        return
    if not args.node or not args.job_name or not re.fullmatch(r"dv1_[A-Za-z0-9_]+", args.job_name):
        raise ValueError("EXPLICIT_NODE_AND_FRESH_DV1_JOB_NAME_REQUIRED")
    spec, scope, base, template, cfg, old_proof = h.collect("EA_known_seven", args.node)
    if cfg["worker_rss_stop_bytes"] != 1073741824 or cfg["source_batch_records"] != 16:
        raise ValueError("ORIGINAL_WORKER_ONE_GIB_OR_BATCH16_CONFIG_CHANGED")
    failure_path = RUN / "artifacts/cpu_analysis_guards/dv1_ea_known_seven_cpu_v2/closure.json"
    failed = h.load(failure_path)
    if (failed["job_id"] != "4520539" or failed["child_returncode"] != 1
            or failed["first_denial"] is not None or failed["durable_evidence_exported"] is not True):
        raise ValueError("ORIGINAL_FAILED_EA_MONITOR_EVIDENCE_DIFFERS")
    for pin in failed["evidence_exports"]:
        h.small(pin["path"], pin)
    name = args.job_name
    output = Path(cfg["external_output_root"]) / name
    config = RUN / f"control/requests/{name}.run_actual.json"
    command_file = RUN / f"control/{name}.command.json"
    proof_file = RUN / f"control/{name}.source_equivalence.json"
    bindings_file = RUN / f"control/{name}.memory_v3_bindings.json"
    request = RUN / f"control/requests/{name}.json"
    bound = RUN / f"control/requests/{name}.bound.json"
    script = RUN / f"control/scripts/{name}.sbatch"
    receipt_file = RUN / f"control/{name}.materialization.json"
    intent = RUN / f"control/submissions/{name}.intent.json"
    destinations = (output, config, command_file, proof_file, bindings_file, request, bound, script, receipt_file,
                    intent, RUN / f"control/submissions/{name}.json", RUN / "artifacts/cpu_analysis_guards" / name)
    if any(p.exists() or p.is_symlink() for p in destinations) or any(p.is_symlink() for p in output.parents):
        raise FileExistsError("NEW_NAME_ALL_OUTPUTS_REQUIRED_FAILED_V2_PRESERVED")
    h.new_file(proof_file, h.encoded(proof))
    proof_pin = h.small(proof_file)
    h.new_file(config, h.RAW[template])
    config_pin = h.small(config)
    command = [h.PYTHON, "-B", str(ENTRY), "--config", str(config), "--root-preflight", str(intent), "--output", str(output)]
    h.new_file(command_file, h.encoded(command))
    command_pin = h.small(command_file)
    bindings = {"schema": "EA_MEMORY_DIAGNOSTIC_REQUEST_BINDINGS_V3", "status": "PREPARED_NOT_SUBMITTED",
        "scope_key": "EA_known_seven", "scope_parameters": scope["parameters"], "original_root_v2_proof": old_proof,
        "new_resource_source_proof": proof_pin, "run_actual_config": config_pin, "command": command_pin,
        "configuration_bytes_identical_to_root_v2_template": True, "output_directory": str(output),
        "failed_v2_monitor_preserved_reference": h.small(failure_path), "cpus": 16, "memory_gib": 32,
        "worker_rss_limit_bytes_unchanged": 1073741824, "wall_seconds": 3600,
        "worker_diagnostic_maximum_bytes_in_existing_64MiB_budget": 1048576,
        "no_new_masks_or_QM_or_scope_expansion": True}
    h.new_file(bindings_file, h.encoded(bindings))
    bindings_pin = h.small(bindings_file)
    expected_sources = dict(h.SOURCES)
    sys.path.insert(0, str(REPO))
    central = __import__("workflows.data_v1_final.execution.cpu_analysis_v1.prepare_request_v2", fromlist=["main"])
    if Path(central.__file__).absolute() != h.CENTRAL / "prepare_request_v2.py":
        raise ValueError("CENTRAL_PREPARE_V2_MUST_BE_ROOT_ACTUAL")
    argv = [str(h.CENTRAL / "prepare_request_v2.py"), "--scope", "EA_known_seven", "--node", args.node,
            "--job-name", name, "--command-file", str(command_file)]
    for path in sorted(expected_sources, key=str):
        argv += ["--source", str(path)]
    saved = sys.argv
    try:
        sys.argv = argv
        central.main()
    finally:
        sys.argv = saved
    prepared = h.load(request)
    original_raw = h.RAW[request]
    actual_sources = h.by_path(prepared["source_references"])
    if (prepared["execution_argv"] != command or prepared["memory_gib"] != 32 or prepared["cpus"] != 16
            or prepared["scope_parameters"] != scope["parameters"] or prepared["data_references"] != base["data_references"]
            or any(actual_sources.get(pin["path"]) != pin for pin in expected_sources.values())):
        raise ValueError("ACTUAL_CENTRAL_REQUEST_RESOURCE_OR_SOURCE_CLOSURE_DIFFERS")
    h.small(script)
    if re.findall(rb"(?m)^#SBATCH --partition=(\S+)$", h.RAW[script]) != [b"cpu"]:
        raise ValueError("ACTUAL_SCRIPT_NOT_EXACT_CPU_PARTITION")
    additive = {"ea_worker_memory_diagnostic_v3": {"binding_manifest_reference": bindings_pin,
                "source_equivalence_reference": proof_pin, "output_directory": str(output)}}
    if "partition" not in prepared:
        additive["partition"] = "cpu"
    if prepared.get("partition", "cpu") != "cpu" or set(additive) & set(prepared):
        raise ValueError("BOUND_ADDITIONS_CONFLICT_WITH_CENTRAL_REQUEST")
    value = {**copy.deepcopy(prepared), **additive}
    h.new_file(bound, h.encoded(value))
    if request.read_bytes() != original_raw or any(value[key] != item for key, item in prepared.items()):
        raise ValueError("CENTRAL_ORIGINAL_REQUEST_CHANGED")
    receipt = {"schema": "ROOT_EA_MEMORY_V3_PREPARATION_RECEIPT", "status": "PREPARED_NOT_SUBMITTED_NOT_EXECUTED",
        "original_central_request": h.small(request), "bound_request_to_submit": h.small(bound), "script": h.small(script),
        "source_proof": proof_pin, "bindings": bindings_pin, "config": config_pin, "entry": proof["variant_actual_root_reference"],
        "original_config_bytes_and_central_request_preserved": True, "bound_additive_keys": sorted(additive),
        "submitter_pinned": h.small(h.CENTRAL / "submit_cpu_pilot_v3.py"),
        "prepared_submitter_argv_only": [h.PYTHON, "-B", "-m", "workflows.data_v1_final.execution.cpu_analysis_v1.submit_cpu_pilot_v3",
                                         "--request", str(bound)],
        "source_references_count": len(actual_sources), "scientific_data_bodies_opened": False,
        "scheduler_commands_run": [], "science_executed": False, "output": str(output)}
    h.new_file(receipt_file, h.encoded(receipt))
    print(json.dumps({"status": receipt["status"], "bound_request": str(bound), "receipt": str(receipt_file), "output": str(output)}))


if __name__ == "__main__":
    main()
