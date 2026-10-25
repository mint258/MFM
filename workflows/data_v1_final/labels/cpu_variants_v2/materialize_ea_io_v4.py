"""Stdlib-only proof/preparation for the same EA cases with one Parquet handle.

Root source proof:
  python -B <Root>/workflows/data_v1_final/labels/cpu_variants_v2/materialize_ea_io_v4.py \
    --proof-only --proof-output <run>/control/root_ea_io_v4_source_proof.json
Root fresh preparation, never submission:
  python -B <Root>/workflows/data_v1_final/labels/cpu_variants_v2/materialize_ea_io_v4.py \
    --node compute-0-17 --job-name dv1_ea_known_seven_io_v4

Keep the actual 1280MiB config bytes, 32GiB allocation, 75% monitor and v3 memory
evidence. Only source I/O lifetime changes; all columns and scientific selection
remain. Actual complete 14-context diagnosis is pending, not asserted here.
"""
from __future__ import annotations

import argparse
import ast
import copy
import importlib
import json
import os
from pathlib import Path
import re
import socket
import sys

RUN = Path("/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025")
REPO = RUN / "repository"
LABELS = REPO / "workflows/data_v1_final/labels"
HERE = LABELS / "cpu_variants_v2"
ENTRY = LABELS / "ea_cpu_v2/bounded_probe_v4.py"
LEDGER = LABELS / "ea_cpu_v2/io_v4_source_edits.json"
FAILED = "dv1_ea_known_seven_rss1280_v1"


def span(text, start, end):
    if text.count(start) != 1 or text.count(end) != 1:
        raise ValueError("SCIENTIFIC_SOURCE_ANCHOR_NOT_UNIQUE")
    return text[text.index(start):text.index(end)]


def prove(h):
    ledger = h.load(LEDGER)
    if ledger["schema"] != "EA_SINGLE_PARQUET_HANDLE_SOURCE_EDITS_V4" or len(ledger["edits"]) != 5:
        raise ValueError("EXACT_IO_ONLY_SOURCE_LEDGER_REQUIRED")
    baseline = LABELS / "ea_cpu_v2/bounded_probe_v3.py"
    if (ledger["baseline_actual_root_reference"]["path"] != str(baseline)
            or ledger["intended_root_variant_path"] != str(ENTRY)):
        raise ValueError("ROOT_ACTUAL_V3_TO_V4_SOURCE_PATHS_REQUIRED")
    old_pin = h.small(baseline, ledger["baseline_actual_root_reference"])
    new_pin = h.small(ENTRY, ledger["prepared_child_variant_reference"] | {"path": str(ENTRY)})
    old, new = h.RAW[baseline].decode(), h.RAW[ENTRY].decode()
    expected = old
    for edit in ledger["edits"]:
        if edit["kind"] != "IO_lifecycle_only" or expected.count(edit["old"]) != 1:
            raise ValueError("IO_EDIT_NOT_DECLARED_OR_UNIQUE")
        expected = expected.replace(edit["old"], edit["new"])
    restored = new
    for edit in reversed(ledger["edits"]):
        if restored.count(edit["new"]) != 1:
            raise ValueError("IO_EDIT_INVERSE_NOT_UNIQUE")
        restored = restored.replace(edit["new"], edit["old"])
    if expected.encode() != h.RAW[ENTRY] or restored.encode() != h.RAW[baseline]:
        raise ValueError("IO_EDITS_NOT_INVERSE_COMPLETE_ORIGINAL_BYTES")
    if old.count(ledger["original_guard_literal"]) != 1 or new.count(ledger["original_guard_literal"]) != 1:
        raise ValueError("ORIGINAL_RU_MAXRSS_GUARD_BYTES_CHANGED")
    for start, end in (
            ("        # Select actual physical scalar/charge leaves", "        count = matches = 0"),
            ("            count += len(batch)", '            _memory_note("latest_post_batch"')):
        if span(old, start, end) != span(new, start, end):
            raise ValueError("PROJECTION_OR_SCIENTIFIC_BATCH_BODY_BYTES_CHANGED")
    before, after = ast.parse(old), ast.parse(new)
    if ast.dump(before, include_attributes=False) != ast.dump(ast.parse(restored), include_attributes=False):
        raise ValueError("INVERSE_IO_MODULE_AST_DIFFERS")
    first = {n.name: n for n in before.body if isinstance(n, ast.FunctionDef)}
    last = {n.name: n for n in after.body if isinstance(n, ast.FunctionDef)}
    if set(last) - set(first) != {"_close_parquet_source", "_reuse_parquet_source"}:
        raise ValueError("UNDECLARED_EXTRA_SOURCE_FUNCTION")
    functions = []
    for key, node in first.items():
        equal = key in last and ast.get_source_segment(old, node) == ast.get_source_segment(new, last[key])
        if key not in {"project", "_project", "main"} and not equal:
            raise ValueError("NON_IO_FUNCTION_BYTES_CHANGED:" + key)
        functions.append({"function": key, "actual_source_bytes_identical": equal})
    return {"schema": "EA_SINGLE_PARQUET_HANDLE_IO_SOURCE_PROOF_V4", "status": "PASS",
        "baseline_actual_root_reference": old_pin, "variant_actual_root_reference": new_pin,
        "source_ledger_actual_root_reference": h.small(LEDGER),
        "full_file_inverse_bytes_and_module_ast_identical": True,
        "original_ru_maxrss_guard_literal_identical": True,
        "typed_leaf_projection_and_scientific_batch_body_raw_bytes_identical": True,
        "functions": functions, "only_existing_IO_edited_functions": ["project", "_project", "main"],
        "source_mutation_rejected_between_reused_rowgroups": True,
        "worker_actual_open_close_reuse_counts_added_to_receipts": True,
        "scientific_modules_imported": [], "scientific_data_bodies_read": False,
        "science_executed": False, "resource_budget_increase": False}


def failed_context(h):
    root = RUN / "artifacts/labels/ea_diagnostic_v1" / FAILED
    files = sorted(root.glob("worker_memory_v3_*.failure.json"))
    if len(files) != 16:
        raise ValueError("SIXTEEN_COMPACT_PRIOR_FAILURES_REQUIRED")
    rows = []
    for path in files:
        value = h.load(path)
        pre, post = value["metadata"]["latest_pre_batch"], value["metadata"]["latest_post_batch"]
        if (value["worker_rss_stop_bytes_unchanged"] != 1280 * 1024**2
                or value["extra"]["original_rss_guard_raised"] is not True
                or pre["context"]["batch_index"] != 0
                or pre["current_status_VmRSS_bytes"] <= 1280 * 1024**2):
            raise ValueError("PRIOR_FAILURE_NOT_ALREADY_OVER_LIMIT_BEFORE_CURRENT_BATCH")
        rows.append({"reference": h.small(path), "pid": value["pid"], "pre_batch_context": pre["context"],
                     "pre_batch_RSS_bytes": pre["current_status_VmRSS_bytes"],
                     "post_batch_RSS_bytes": post["current_status_VmRSS_bytes"]})
    if len({r["pid"] for r in rows}) != 16 or sorted(r["pre_batch_context"]["row_group"] for r in rows) != list(range(176, 192)):
        raise ValueError("OBSERVED_FAILED_ROWGROUP_CONTEXT_DIFFERS")
    closure_path = RUN / "artifacts/cpu_analysis_guards" / FAILED / "closure.json"
    closure = h.load(closure_path)
    if closure["job_id"] != "4520567" or closure["child_returncode"] != 1 or closure["first_denial"] is not None:
        raise ValueError("PRIOR_ACTUAL_FAILED_JOB_OR_NO_DENIAL_CONTEXT_DIFFERS")
    for pin in closure["evidence_exports"]:
        h.small(pin["path"], pin)
    return {"prior_job_id": "4520567", "compact_worker_failures": rows,
        "prior_monitor_closure": h.small(closure_path),
        "interpretation": "All current-batch pre-read RSS values already exceed1280MiB after earlier rowgroups; repeated Parquet construction is a source-supported IO candidate, not a proven exact allocator cause",
        "remaining": "Actual v4 constructor/footer/current RSS and exact14 canonical contexts must be checked; unchanged budget may still be insufficient"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proof-only", action="store_true")
    parser.add_argument("--proof-output")
    parser.add_argument("--node")
    parser.add_argument("--job-name")
    args = parser.parse_args()
    if (os.getuid() != 1278 or socket.gethostname().split(".")[0] != "sonmi"
            or Path(__file__).absolute() != HERE / "materialize_ea_io_v4.py"):
        raise ValueError("ACTUAL_ROOT_METADATA_ENTRY_REQUIRED")
    sys.path.insert(0, str(REPO))
    prior = importlib.import_module("workflows.data_v1_final.labels.cpu_variants_v2.materialize_ea_memory_v3")
    if Path(prior.__file__).absolute() != HERE / "materialize_ea_memory_v3.py":
        raise ValueError("PRIOR_METADATA_DEPENDENCY_NOT_ROOT_ACTUAL")
    h, _ = prior.metadata_helper()
    h.small(Path(__file__).absolute())
    proof = prove(h)
    if args.proof_only:
        path = Path(args.proof_output or "")
        if not path.is_absolute() or RUN / "control" not in path.parents:
            raise ValueError("NEW_LITERAL_RUN_CONTROL_PROOF_PATH_REQUIRED")
        h.new_file(path, h.encoded(proof))
        print(json.dumps({"status": "PASS_SOURCE_ONLY_NOT_SCIENCE", "proof": h.small(path)}))
        return
    if not args.node or not args.job_name or not re.fullmatch(r"dv1_[A-Za-z0-9_]+", args.job_name):
        raise ValueError("FRESH_DV1_NAME_AND_EXPLICIT_CPU_NODE_REQUIRED")
    _, scope, base, template, original_cfg, _ = h.collect("EA_known_seven", args.node)
    previous = h.load(RUN / f"control/{FAILED}.materialization.json")
    pin = previous["new_config"]
    cfg = h.load(pin["path"], pin)
    budget_pin = previous["worker_budget_evidence_and_single_key_proof"]
    budget = h.load(budget_pin["path"], budget_pin)
    if (set(cfg) != set(original_cfg) or cfg["worker_rss_stop_bytes"] != 1280 * 1024**2
            or {k for k in cfg if cfg[k] != original_cfg[k]} != {"worker_rss_stop_bytes"}
            or budget["config_changed_keys"] != ["worker_rss_stop_bytes"]
            or budget["new_config_reference"] != pin or budget["all_other_config_JSON_values_identical"] is not True):
        raise ValueError("EXACT_PREVIOUS_1280_SINGLE_RESOURCE_KEY_CONFIG_REQUIRED")
    context = failed_context(h)
    name = args.job_name
    output = Path(cfg["external_output_root"]) / name
    config = RUN / f"control/requests/{name}.run_actual.json"
    command_file = RUN / f"control/{name}.command.json"
    proof_file = RUN / f"control/{name}.source_equivalence.json"
    bindings_file = RUN / f"control/{name}.io_v4_bindings.json"
    request = RUN / f"control/requests/{name}.json"
    bound = RUN / f"control/requests/{name}.bound.json"
    script = RUN / f"control/scripts/{name}.sbatch"
    receipt_file = RUN / f"control/{name}.materialization.json"
    intent = RUN / f"control/submissions/{name}.intent.json"
    destinations = (output, config, command_file, proof_file, bindings_file, request, bound, script, receipt_file, intent,
                    RUN / f"control/submissions/{name}.json", RUN / "artifacts/cpu_analysis_guards" / name)
    if any(p.exists() or p.is_symlink() for p in destinations) or any(p.is_symlink() for p in output.parents):
        raise FileExistsError("FRESH_ALL_PATHS_REQUIRED_OLD_FAILURES_AND_REQUESTS_PRESERVED")
    h.new_file(config, h.RAW[Path(pin["path"])])
    config_pin = h.small(config)
    if config_pin["bytes"] != pin["bytes"] or config_pin["sha256"] != pin["sha256"]:
        raise ValueError("PREVIOUS_1280_CONFIG_BYTES_CHANGED")
    h.new_file(proof_file, h.encoded(proof))
    proof_pin = h.small(proof_file)
    command = [h.PYTHON, "-B", str(ENTRY), "--config", str(config), "--root-preflight", str(intent), "--output", str(output)]
    h.new_file(command_file, h.encoded(command))
    command_pin = h.small(command_file)
    bindings = {"schema": "EA_IO_V4_BINDINGS_V1", "status": "METADATA_PREPARED_NOT_SUBMITTED",
        "source_proof": proof_pin, "new_config": config_pin, "prior_1280_config": pin,
        "configuration_bytes_unchanged_from_actual1280": True, "original_template": h.small(template),
        "prior_single_resource_key_proof": budget_pin, "prior_actual_failed_context": context,
        "command": command_pin, "output_directory": str(output), "scope_parameters": scope["parameters"],
        "memory_gib": 32, "workers": 16, "worker_limit_bytes": 1280 * 1024**2,
        "global_monitor_75pct_and64MiB_output_cap_unchanged": True, "no_masks_QM_or_scientific_projection_change": True}
    h.new_file(bindings_file, h.encoded(bindings))
    binding_pin = h.small(bindings_file)
    expected_sources = dict(h.SOURCES)
    central = importlib.import_module("workflows.data_v1_final.execution.cpu_analysis_v1.prepare_request_v2")
    if Path(central.__file__).absolute() != h.CENTRAL / "prepare_request_v2.py":
        raise ValueError("CENTRAL_PREPARE_NOT_ROOT_ACTUAL")
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
    sources = h.by_path(prepared["source_references"])
    if (prepared["execution_argv"] != command or prepared["memory_gib"] != 32 or prepared["cpus"] != 16
            or prepared["scope_parameters"] != scope["parameters"] or prepared["data_references"] != base["data_references"]
            or any(sources.get(p["path"]) != p for p in expected_sources.values())):
        raise ValueError("CENTRAL_FINITE_SOURCE_REQUEST_DIFFERS")
    h.small(script)
    if re.findall(rb"(?m)^#SBATCH --partition=(\S+)$", h.RAW[script]) != [b"cpu"]:
        raise ValueError("EXACT_ACTUAL_CPU_SCRIPT_REQUIRED")
    additions = {"ea_io_lifecycle_v4": {"binding_reference": binding_pin, "output_directory": str(output)}}
    if "partition" not in prepared:
        additions["partition"] = "cpu"
    if prepared.get("partition", "cpu") != "cpu" or set(additions) & set(prepared):
        raise ValueError("ADDITIVE_BOUND_KEYS_CONFLICT")
    value = {**copy.deepcopy(prepared), **additions}
    h.new_file(bound, h.encoded(value))
    if request.read_bytes() != original_raw or any(value[k] != v for k, v in prepared.items()):
        raise ValueError("ORIGINAL_CENTRAL_REQUEST_CHANGED")
    receipt = {"schema": "EA_IO_V4_PREPARATION_RECEIPT_V1", "status": "PREPARED_NOT_SUBMITTED_NOT_EXECUTED",
        "central_request_original": h.small(request), "bound_request_to_submit": h.small(bound), "script": h.small(script),
        "source_equivalence": proof_pin, "bindings": binding_pin, "config": config_pin,
        "previous1280_config_bytes_unchanged": True, "source_entry": proof["variant_actual_root_reference"],
        "bound_only_additive_keys": sorted(additions), "submitter_pinned": h.small(h.CENTRAL / "submit_cpu_pilot_v3.py"),
        "prepared_submitter_argv_only": [h.PYTHON, "-B", "-m", "workflows.data_v1_final.execution.cpu_analysis_v1.submit_cpu_pilot_v3",
                                         "--request", str(bound)],
        "science_executed": False, "scientific_data_bodies_opened": False, "scheduler_commands_run": []}
    h.new_file(receipt_file, h.encoded(receipt))
    print(json.dumps({"status": receipt["status"], "bound_request": str(bound), "receipt": str(receipt_file), "output": str(output)}))


if __name__ == "__main__":
    main()
