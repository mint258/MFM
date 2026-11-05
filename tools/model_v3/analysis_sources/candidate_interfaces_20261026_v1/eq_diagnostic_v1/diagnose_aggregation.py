#!/usr/bin/env python3
"""Fixed full-matrix numerical attribution. No intervention is adopted here."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import socket
import sys
import time
import traceback

sys.dont_write_bytecode = True
HERE = Path(__file__).absolute().parent
VARIANTS = {
    "original_formula_replay": (),
    "cdist_direct_only": ("cdist_direct",),
    "charge_center_only": ("charge_center",),
    "pool_fp64_reference_only": ("pool_fp64_reference",),
    "cdist_direct_and_charge_center": ("cdist_direct", "charge_center"),
    "cdist_direct_and_pool_fp64_reference": ("cdist_direct", "pool_fp64_reference"),
    "charge_center_and_pool_fp64_reference": ("charge_center", "pool_fp64_reference"),
}
PER_VARIANT_CAP = 32*1024**2
TOTAL_CAP = 2*1024**3


def require(condition, message):
    if not condition: raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def binding(path):
    path = Path(path).absolute()
    raw = path.read_bytes()
    return {"path": str(path), "bytes": len(raw), "sha256": sha(raw)}


def bound_json(ref):
    path = Path(ref["path"])
    require(path.is_file() and not path.is_symlink(), "Ordinary bound JSON required")
    raw = path.read_bytes()
    require(len(raw) <= 8*1024**2 and len(raw) == ref["bytes"] and sha(raw) == ref["sha256"], "Bound JSON bytes changed")
    return json.loads(raw)


def save(path, value):
    path = Path(path)
    pending = path.with_suffix(path.suffix+".pending")
    raw = (json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, indent=2)+"\n").encode()
    require(len(raw) <= 8*1024**2 and not path.exists() and not pending.exists(), "Bounded fresh output required")
    with pending.open("xb") as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    os.replace(pending, path)


def import_equation(repository):
    root = Path(repository).absolute()
    current = root/"current"
    existing = sys.modules.get("phychem_mfm")
    if existing is not None:
        require(Path(existing.__file__).absolute().parent == current/"phychem_mfm", "Another package tree is already imported")
    sys.path.insert(0, str(current))
    equation = importlib.import_module("phychem_mfm.phase1.v3_composed_equivariance")
    heads = importlib.import_module("phychem_mfm.model.v3_heads")
    require(Path(equation.__file__).absolute() == current/"phychem_mfm/phase1/v3_composed_equivariance.py",
            "Diagnostic must import the actual frozen Eq tree")
    return equation, heads


def centered_vector(q, pos, batch, graphs, pool):
    """Same exact-real dipole: subtracting mean charge removes a null term.

    Runtime wrapper supplies only original FP32 tensors and FP32 pool. This
    generic expression also permits a small float64 algebra unit oracle.
    """
    center = pool(pos, batch, graphs, "mean")
    q_center = pool(q, batch, graphs, "mean")
    return pos.new_zeros((graphs, 3)).index_add(0, batch, (q-q_center[batch])*(pos-center[batch]))


@contextmanager
def intervention(equation, heads, variant):
    """Temporary operators only; never writes a source file or a parameter."""
    import torch
    require(variant in VARIANTS, "Only a preregistered full-matrix intervention is allowed")
    operations = VARIANTS[variant]
    original_cdist, original_pool, original_dipole = torch.cdist, heads._pool, heads._DipoleHead.forward
    counters = {"cdist_p2_direct_calls": 0, "charge_center_calls": 0, "fp64_graph_feature_pool_calls": 0}
    def direct(x1, x2, p=2.0, compute_mode="use_mm_for_euclid_dist_if_necessary"):
        if p == 2.0:
            counters["cdist_p2_direct_calls"] += 1
            compute_mode = "donot_use_mm_for_euclid_dist"
        return original_cdist(x1, x2, p=p, compute_mode=compute_mode)
    def pool_reference(h, batch, graphs, mode):
        # Only scalar graph H0 feature pooling. Do not change positions (3)
        # or charge-centering (1), even in a paired intervention.
        if h.ndim == 2 and h.shape[-1] == 512:
            counters["fp64_graph_feature_pool_calls"] += 1
            return original_pool(h.double(), batch, graphs, mode).to(h.dtype)
        return original_pool(h, batch, graphs, mode)
    def dipole_centered(self, h, pos, batch, graphs):
        counters["charge_center_calls"] += 1
        with torch.autocast(device_type=h.device.type, enabled=False):
            q = self.charges(h.float())
            value = centered_vector(q, pos.float(), batch, graphs, original_pool)
            return value.norm(dim=-1, keepdim=True) if self.magnitude else value
    try:
        if "cdist_direct" in operations: torch.cdist = direct
        if "charge_center" in operations: heads._DipoleHead.forward = dipole_centered
        if "pool_fp64_reference" in operations: heads._pool = pool_reference
        yield counters
    finally:
        torch.cdist, heads._pool, heads._DipoleHead.forward = original_cdist, original_pool, original_dipole
        require(torch.cdist is original_cdist and heads._pool is original_pool
                and heads._DipoleHead.forward is original_dipole, "Failed to restore original callable identities")


def unchanged_case_identity(result, original):
    for key in ("case_id", "case", "weight_summary", "fixture_geometry_sha256", "original_physical_geometry_sha256",
                "original_view_identity_sha256", "encoder_configuration", "registry_sha256"):
        require(result[key] == original[key], "Original case weights/input/config drift: "+key)


def replay_measurements(result, original):
    # Ignore wallclock/runtime allocation and external file names. Check the
    # original actual measurements exactly; no read of the old NPZ is needed.
    keys = ("measurements", "passed", "domain", "encoder_forward_shapes", "complete_terminal_count")
    return all(result[key] == original[key] for key in keys)


def source_files(equation, repository):
    result = {str(Path(repository).absolute()/name): ref for name, ref in equation.execution_source_inventory(repository).items()}
    for name in ("diagnose_aggregation.py", "test_diagnostic.py", "README.md", "baseline_aggregate.json", "baseline_public_v1.json", "BASELINE.md"):
        ref = binding(HERE/name)
        result[ref["path"]] = {"bytes": ref["bytes"], "sha256": ref["sha256"]}
    return result


def make_request(repository, aggregate, node):
    require(re.fullmatch(r"compute-0-(?:2|[89]|1[0-9])", node), "Choose a site CPU node")
    equation, _ = import_equation(repository)
    aggregate_ref = binding(aggregate)
    value = bound_json(aggregate_ref)
    require(value["schema"] == "model_v3_composed_equivariance_baseline_aggregate_v1"
            and value["source_job_id"] == "4521006" and value["complete_cases"] == value["failed_cases"] == 48
            and value["original_NPZ_bytes_read"] is False, "Actual failed original CPU aggregate required")
    expected = {spec.identity for spec in equation.CASE_SPECS}
    require({ref["case_id"] for ref in value["source_cases"]} == expected and len(value["source_cases"]) == 48,
            "All original fixed cases must be bound once")
    for ref in value["source_cases"]:
        original = bound_json(ref)
        require(original["case_id"] == ref["case_id"] and original["runtime"]["device"] == "cpu"
                and original["runtime"]["intraop_threads"] == 1, "Original CPU/one-thread case receipt required")
    sources = source_files(equation, repository)
    return {"schema": "model_v3_eq_diagnostic_request_v1", "status": "PREPARED_FOR_ROOT_PUBLIC_REGISTRATION_DIAGNOSTIC_ONLY",
        "equation_repository": str(Path(repository).absolute()), "baseline_aggregate": aggregate_ref,
        "source_files": sources, "source_inventory_sha256": equation.canonical_hash(sources), "expected_node": node,
        "variants": {name: list(items) for name, items in VARIANTS.items()}, "cases": [spec.identity for spec in equation.CASE_SPECS],
        "equation_protocol_sha256": equation.canonical_hash(equation.protocol()),
        "physical_initialization_geometry_noise_masks_tolerance": "identical to original frozen48 cases",
        "intraop_threads": 1, "device": "cpu", "per_variant_output_cap": PER_VARIANT_CAP, "whole_job_output_cap": TOTAL_CAP,
        "FP64_pool_scope": "graph scalar H0 sum/mean only, accumulated in64 then cast32; attribution reference NOT FP32 acceptance",
        "charge_scope": "both independent graph dipole/magnitude heads; original FP32 centering; same charges MLP parameters",
        "cdist_scope": "p2 only forced direct; no cutoff, mask, features, parameters or noise change",
        "baseline_replay": "all stored field/domain/edge measurements exactly equal, plus weights/input digests",
        "old_NPZ_read": False, "scientific_adoption_or_selection": False, "Root_only_submission": True}


def bytes_used(directory):
    total = 0
    for path in directory.rglob("*"):
        require(not path.is_symlink(), "No symbolic links in diagnostic output")
        if path.is_file(): total += path.stat().st_size
    return total


def run(request, request_ref, output):
    require(socket.gethostname().split(".")[0] == request["expected_node"]
            and os.environ.get("SLURMD_NODENAME", request["expected_node"]) == request["expected_node"]
            and os.environ.get("SLURM_JOB_ID", "").isdigit() and int(os.environ.get("SLURM_CPUS_PER_TASK", "0")) >= 16
            and os.environ.get("CUDA_VISIBLE_DEVICES") in ("", "-1"), "Owned CPU Slurm allocation required")
    require(not output.exists() and output.parent.is_dir(), "Fresh external diagnostic output required")
    require(not output.absolute().is_relative_to(Path(request["equation_repository"])), "Never write diagnostic artifacts into frozen Eq source")
    require(not output.absolute().is_relative_to(HERE), "Keep source and new diagnostic outputs separate")
    equation, heads = import_equation(request["equation_repository"])
    require(source_files(equation, request["equation_repository"]) == request["source_files"], "Frozen sources changed before diagnostic")
    aggregate = bound_json(request["baseline_aggregate"])
    refs = {item["case_id"]: item for item in aggregate["source_cases"]}
    output.mkdir(mode=0o700)
    save(output/"INPUT_BINDING.json", {"request": request_ref, "job_id": os.environ["SLURM_JOB_ID"],
        "status": "DIAGNOSTIC_ONLY_NO_ADOPTION", "old_NPZ_read": False})
    variants, control_ok = [], True
    start = time.perf_counter()
    for name in VARIANTS:
        directory = output/name; directory.mkdir(mode=0o700)
        records = []
        for spec in equation.CASE_SPECS:
            original = bound_json(refs[spec.identity])
            try:
                with intervention(equation, heads, name) as counters:
                    measured = equation.measure_case(spec, device="cpu", threads=1, terminal_output_directory=directory)
                unchanged_case_identity(measured, original)
                require((counters["cdist_p2_direct_calls"] > 0) == ("cdist_direct" in VARIANTS[name])
                        and counters["charge_center_calls"] == (8 if "charge_center" in VARIANTS[name] else 0)
                        and (counters["fp64_graph_feature_pool_calls"] > 0) == ("pool_fp64_reference" in VARIANTS[name]),
                        "Declared operator intervention was not actually exercised")
                exact_replay = replay_measurements(measured, original) if name == "original_formula_replay" else None
                if exact_replay is False: control_ok = False
                record = {"schema": "model_v3_eq_diagnostic_case_v1", "variant": name, "operations": list(VARIANTS[name]),
                    "status": "DIAGNOSTIC_ONLY_NO_ADOPTION", "case_id": spec.identity, "original_case": refs[spec.identity],
                    "parameter_and_input_identity_verified": True, "original_control_measurements_reproduced": exact_replay,
                    "actual_operator_calls": dict(counters), "callable_identities_restored": True,
                    "raw_threshold_pass": measured["passed"], "is_FP32_acceptance_evidence": False,
                    "contains_FP64_accumulation_reference": "pool_fp64_reference" in VARIANTS[name], "measurement": measured}
                completed = True
            except Exception as error:
                control_ok = False if name == "original_formula_replay" else control_ok
                record = {"schema": "model_v3_eq_diagnostic_case_exception_v1", "variant": name, "case_id": spec.identity,
                    "status": "DIAGNOSTIC_ONLY_FAILED_EXCEPTION", "message": str(error), "traceback": traceback.format_exc(),
                    "is_FP32_acceptance_evidence": False, "original_case": refs[spec.identity]}
                archive = directory/(spec.identity+"__terminals.npz")
                if archive.is_file(): record["partial_raw_terminal_artifact"] = binding(archive)
                completed = False
            path = directory/(spec.identity+".json")
            save(path, record)
            records.append({"case_id": spec.identity, "completed": completed, "case_result": binding(path),
                "raw_threshold_pass": record.get("raw_threshold_pass", False)})
            require(bytes_used(directory) <= PER_VARIANT_CAP and bytes_used(output) <= TOTAL_CAP, "Declared diagnostic output budget exceeded")
            print(json.dumps({"variant": name, "case_id": spec.identity, "completed": completed,
                "raw_threshold_pass_NOT_adoption": record.get("raw_threshold_pass")}), flush=True)
        summary = {"variant": name, "operations": list(VARIANTS[name]), "cases": records,
            "complete_case_count": sum(r["completed"] for r in records),
            "raw_threshold_pass_count_NOT_adoption": sum(r["raw_threshold_pass"] for r in records),
            "status": "DIAGNOSTIC_ONLY_NO_ADOPTION", "is_FP32_acceptance_evidence": False}
        save(directory/"VARIANT_RESULT.json", summary)
        require(bytes_used(directory) <= PER_VARIANT_CAP, "Per-variant32MiB cap exceeded")
        variants.append({"variant": name, "result": binding(directory/"VARIANT_RESULT.json"),
            "complete_case_count": summary["complete_case_count"], "raw_threshold_pass_count_NOT_adoption": summary["raw_threshold_pass_count_NOT_adoption"]})
    after = source_files(equation, request["equation_repository"])
    closed = control_ok and all(v["complete_case_count"] == 48 for v in variants) and after == request["source_files"]
    result = {"schema": "model_v3_eq_diagnostic_result_v1",
        "status": "DIAGNOSTIC_COMPLETE_NO_ADOPTION" if closed else "DIAGNOSTIC_INCOMPLETE_OR_REPLAY_MISMATCH",
        "variants": variants, "baseline_control_exact_replay": control_ok, "source_before_after_identical": after == request["source_files"],
        "wall_seconds": time.perf_counter()-start, "job_id": os.environ["SLURM_JOB_ID"],
        "old_NPZ_read": False, "is_FP32_acceptance_evidence": False, "scientific_selection_or_adoption": False}
    save(output/"DIAGNOSTIC_RESULT.json", result)
    require(bytes_used(output) <= TOTAL_CAP, "Whole job2GiB cap exceeded")
    return 0 if closed else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    prepare = commands.add_parser("prepare-request")
    prepare.add_argument("--eq-repository", type=Path, required=True)
    prepare.add_argument("--aggregate", type=Path, default=HERE/"baseline_aggregate.json")
    prepare.add_argument("--expected-node", required=True)
    prepare.add_argument("--output", type=Path, required=True)
    execute = commands.add_parser("run")
    execute.add_argument("--request", type=Path, required=True)
    execute.add_argument("--request-sha256", required=True)
    execute.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    if args.action == "prepare-request":
        save(args.output, make_request(args.eq_repository, args.aggregate, args.expected_node))
        print(json.dumps(binding(args.output))); return 0
    reference = binding(args.request)
    require(reference["sha256"] == args.request_sha256, "Frozen request rawSHA differs")
    request = bound_json(reference)
    require(request == make_request(request["equation_repository"], request["baseline_aggregate"]["path"], request["expected_node"]),
            "Frozen diagnostic source/method/input binding differs")
    return run(request, reference, args.output_root)


if __name__ == "__main__":
    raise SystemExit(main())
