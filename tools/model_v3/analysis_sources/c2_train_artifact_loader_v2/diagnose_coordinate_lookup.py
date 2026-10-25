#!/usr/bin/env python3
"""Preregistered TRAIN-only C2 numerical diagnosis; never invoke old runner/VAL."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import importlib.util
import inspect
import json
import math
import os
from pathlib import Path
import resource
import socket
import subprocess
import sys
import time
import traceback

sys.dont_write_bytecode = True

import numpy as np
import scipy
import threadpoolctl
from threadpoolctl import threadpool_info, threadpool_limits

from core_capture import CoreCapture, controlled_blas, source_sha, verified_blas_info
from solver_math import (augmented_active_jacobi, csr_fingerprint, numerical_state,
                         solve_augmented, require)


EXECUTED_FILES = ("diagnose_coordinate_lookup.py", "core_capture.py", "solver_math.py")
ORIGINAL_PREREGISTRATION = "1a8c124571ddf37f87ae06ef9971efa85e417f95"
MONITOR_SHA256 = "dbe875ab7ceec7e5002c5b70bff0608e3506f7451bdacd38e5f5bfc0700663fe"
CAPS = {"wall_seconds": 3300, "work_deadline_seconds": 3240, "finalization_deadline_seconds": 3270,
        "maximum_process_RSS_bytes": 24*1024**3, "maximum_output_bytes": 128*1024**2,
        "maximum_array_bytes": 32*1024**2, "maximum_numeric_bytes": 8*1024**3}


def canonical(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def binding(path):
    path = Path(path).absolute()
    require(path.is_file() and not path.is_symlink(), "Ordinary bound source file required")
    sha = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024**2), b""): sha.update(block)
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": sha.hexdigest()}


def decode_json(raw):
    def pairs(items):
        value = {}
        for key, item in items:
            require(key not in value, "Duplicate metadata key")
            value[key] = item
        return value
    return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite metadata")))


def bound_json(ref):
    path = Path(ref["path"])
    require(path.is_file() and not path.is_symlink() and path.stat().st_size <= 32*1024**2,
            "Bounded ordinary metadata required")
    raw = path.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == ref["sha256"] and ("bytes" not in ref or ref["bytes"] == len(raw)),
            "Bound metadata SHA/bytes differ")
    return decode_json(raw)


def save(path, value):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n"); stream.flush(); os.fsync(stream.fileno())


def executed_sources():
    root = Path(__file__).absolute().parent
    return {name: binding(root/name)["sha256"] for name in EXECUTED_FILES}


def registered_protocol(ref):
    require(type(ref) is dict and set(ref) == {"repository", "commit", "path", "sha256"}, "Fixed Git diagnostic protocol reference required")
    import re
    require(re.fullmatch(r"[0-9a-f]{40}", ref["commit"]) and re.fullmatch(r"[0-9a-f]{64}", ref["sha256"]), "Full actual protocol commit/SHA required")
    relative = ref["path"]
    require(type(relative) is str and relative and not relative.startswith(("/", "-")) and "\\" not in relative
            and all(p not in ("", ".", "..") for p in relative.split("/")), "Safe Git protocol path required")
    raw = subprocess.run(["git", "-C", ref["repository"], "show", ref["commit"]+":"+relative], check=True,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout
    require(len(raw) <= 128*1024 and hashlib.sha256(raw).hexdigest() == ref["sha256"], "Committed diagnostic protocol blob differs")
    protocol = decode_json(raw)
    require(protocol.get("schema") == "model_v3_C2_train_solver_diagnostic_protocol_v1"
            and protocol["scope"] == "TRAIN_ONLY_DIAGNOSTIC_NOT_BASELINE_ACCEPTANCE"
            and protocol["caps"] == CAPS and protocol["blas_threads"] == 1
            and protocol["controlled_source_max_iterations"] == 500
            and protocol["candidate_max_iterations"] == 2000
            and protocol["atol"] == protocol["btol"] == 1e-8
            and protocol["condition_limit"] == 1e8 and protocol["ridge"] == 1e-4
            and protocol["warm_start_used"] is False
            and protocol["source_inventory_sha256"] == canonical(executed_sources()), "Diagnostic rules or executed source differ from the fixed Git registration")
    return protocol


def cpu_admission(expected_node):
    import re
    require(re.fullmatch(r"compute-0-(?:2|[89]|1[0-9])", expected_node), "Root must choose an available site CPU node")
    host = socket.gethostname().split(".")[0]
    node = os.environ.get("SLURMD_NODENAME", host).split(".")[0]
    require(node == host == expected_node and os.environ.get("SLURM_JOB_ID", "").isdigit()
            and int(os.environ.get("SLURM_CPUS_PER_TASK", "0")) >= 16
            and os.environ.get("CUDA_VISIBLE_DEVICES") == "", "Owned CPU-only 16-CPU Slurm allocation required")


def configure_wandb_layout(output):
    output = Path(output).absolute()
    require(output.is_dir() and not output.is_symlink(), "Ordinary owned diagnostic output required")
    paths = {"WANDB_DIR": output, "WANDB_CACHE_DIR": output/"cache",
        "WANDB_DATA_DIR": output/"wandb_data", "WANDB_CONFIG_DIR": output/"wandb_config"}
    for path in paths.values():
        require(not path.is_symlink() and (not path.exists() or path.is_dir()), "Canonical ordinary W&B directory required")
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.environ.update({key: str(path) for key, path in paths.items()})
    os.environ["WANDB_MODE"] = "offline"
    return {**{key: str(path) for key, path in paths.items()}, "WANDB_MODE": "offline"}


class WorkDeadline(TimeoutError):
    pass


class Guard:
    def __init__(self, output, census):
        self.output, self.census = output, census
        self.started = time.monotonic()
        self.checked = self.logged = -1e9
        self.stage, self.finalizing = "SOURCE_BINDING", False
        self.peak_RSS_bytes = self.output_bytes = 0
        inherited = int(os.environ.get("MODEL_V3_CHILD_OUTPUT_BUDGET_BYTES", CAPS["maximum_output_bytes"]))
        self.output_cap = min(CAPS["maximum_output_bytes"], inherited)

    def __call__(self):
        elapsed = time.monotonic()-self.started
        deadline = CAPS["finalization_deadline_seconds"] if self.finalizing else CAPS["work_deadline_seconds"]
        if elapsed > deadline: raise WorkDeadline("Predeclared diagnostic work/finalization boundary reached")
        self.peak_RSS_bytes = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)*1024
        require(self.peak_RSS_bytes <= CAPS["maximum_process_RSS_bytes"], "Diagnostic RSS exceeded unchanged 24-GiB cap")
        if elapsed-self.checked >= 2:
            self.output_bytes = self.census(self.output)
            require(self.output_bytes <= self.output_cap, "Diagnostic owned output exceeded unchanged cap")
            self.checked = elapsed
        if elapsed-self.logged >= 30:
            print(json.dumps({"stage": self.stage, "elapsed_seconds": elapsed, "peak_RSS_bytes": self.peak_RSS_bytes,
                "owned_output_bytes": self.output_bytes, "native_PRETRAIN_VAL_records_read": 0}), flush=True)
            self.logged = elapsed


def fixed_monitor(ref):
    actual = binding(ref["path"])
    require(actual["sha256"] == ref["sha256"] == MONITOR_SHA256, "Fixed four-link owned-output census source differs")
    spec = importlib.util.spec_from_file_location("c2_diagnostic_fixed_runtime_monitor", ref["path"])
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module; spec.loader.exec_module(module)
    return module.owned_output_bytes


def run_train_only(core, source, request, selected, *, sink, check, numeric_budget=8*1024**3):
    """Reusable testable execution boundary: only source.records('TRAIN', ...)."""
    config = core.CoordinateLookupConfig(**request["method"])
    expected = request["selection"]["train_records"]
    fit_started = time.perf_counter()
    with CoreCapture(core, config, expected_source_sha256=request["source_files"]["current/phychem_mfm/phase1/v3_coordinate_lookup.py"],
            sink=sink, check=check) as capture:
        try:
            model = core.fit_coordinate_lookup(source.records("TRAIN", selected), config=config,
                expected_records=expected, source_plan_sha256=request["diagnostic_selection_plan_raw_sha256"], check=check)
        except ValueError as exc:
            if (str(exc) != "Sparse LSQR did not satisfy the preregistered stopping condition" or capture.baseline is None):
                raise
            source_outcome = "ORIGINAL_CORE_REJECTED_NEW_CONTROLLED_SOLVER_RETURN"
        else:
            source_outcome = "ORIGINAL_CORE_RETURNED_TRAIN_MODEL_NO_VALIDATION_CALLED"
            del model
    require(source.native_reads == expected and capture.baseline is not None, "Only the exact original TRAIN population may be decoded")
    source_result = {"source_outcome": source_outcome, "fit_build_plus_solver_wall_seconds": time.perf_counter()-fit_started,
        "baseline": capture.baseline, "native_TRAIN_records_decoded": source.native_reads, "native_PRETRAIN_VAL_records_decoded": 0}
    sink("controlled_source_fit_outcome", source_result)
    if hasattr(check, "stage"): check.stage = "TRAIN_ACTIVE_JACOBI_PREPROCESS"
    check()
    preprocessing_started = time.perf_counter()
    with controlled_blas(sink, "active_jacobi_thread_control") as threads:
        before, inside_before = threads["threadpools_before"], threads["threadpools_inside_before"]
        system = augmented_active_jacobi(capture.matrix, capture.rhs, capture.support, n_atoms=capture.n_atoms,
            ridge=config.ridge, numeric_budget_bytes=numeric_budget, check=check)
        preprocessing_wall = time.perf_counter()-preprocessing_started
        if hasattr(check, "stage"): check.stage = "TRAIN_ACTIVE_JACOBI_LSQR"
        solver_started = time.perf_counter()
        coefficient, stats = solve_augmented(system, atol=config.atol, btol=config.btol,
            condition_limit=config.condition_limit, maximum_iterations=2000, check=check)
        solver_wall = time.perf_counter()-solver_started
        candidate = {"status": "DIAGNOSTIC_ONLY_NOT_BASELINE_ACCEPTANCE", "preprocessing": system.metadata,
            "preprocessing_wall_seconds": preprocessing_wall, "solver_wall_seconds": solver_wall,
            "solver": stats, "threadpools_before": before, "threadpools_inside_before": inside_before,
            "threadpools_inside_after": verified_blas_info(),
            "inactive_coefficients_exact_zero": bool(np.equal(coefficient[capture.support == 0], 0).all()),
            "native_PRETRAIN_VAL_records_decoded": 0, "KKT_acceptance_threshold_applied": False}
        sink("active_jacobi_candidate_return", candidate)
        if hasattr(check, "stage"): check.stage = "TRAIN_ORIGINAL_COORDINATE_NORMAL_RESIDUAL"
        candidate["original_coordinate_diagnostics"] = numerical_state(capture.matrix, capture.rhs,
            coefficient, n_atoms=capture.n_atoms, ridge=config.ridge, check=check)
    restored = threads["threadpools_restored"]
    candidate["threadpools_restored"] = restored
    require(csr_fingerprint(capture.matrix, check=check) == capture.pre_fingerprint, "Captured original TRAIN matrix was mutated")
    sink("active_jacobi_candidate_diagnostics", candidate)
    arrays = {"active_columns": system.active_columns, "observed_support": capture.support[system.active_columns],
        "jacobi_scale": system.scale, "candidate_coefficient": coefficient[system.active_columns]}
    if capture.baseline["coefficients_finite"]:
        arrays["controlled_source_coefficient"] = capture.baseline_coefficient[system.active_columns]
    return {"status": "DIAGNOSTIC_ONLY_COMPLETED_NO_BASELINE_ACCEPTANCE", "source": source_result,
        "candidate": candidate, "original_TRAIN_CSR": capture.pre_fingerprint,
        "original_v1_job_4520482_remains_FAILED": True, "original_v1_stop_or_iteration_count_inferred": False,
        "native_PRETRAIN_VAL_records_decoded": 0, "model_selection_gate": False}, arrays


def write_arrays(arrays, output, guard):
    upper = sum(value.nbytes for value in arrays.values())+64*1024
    if upper > CAPS["maximum_array_bytes"] or guard.census(output)+upper > guard.output_cap-2*1024**2:
        return {"saved": False, "reason": "predeclared optional array/output budget", "uncompressed_upper_bytes": upper}
    guard()
    path = output/"active_coefficients_and_support.npz"
    with path.open("xb") as stream: np.savez_compressed(stream, **arrays)
    guard()
    return {"saved": True, "binding": binding(path), "uncompressed_upper_bytes": upper,
        "contents": {key: {"shape": list(value.shape), "dtype": str(value.dtype)} for key, value in arrays.items()},
        "CSR_saved": False, "member_IDs_or_coordinates_saved": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", required=True)
    parser.add_argument("--inputs-sha256", required=True)
    parser.add_argument("--expected-node", required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args(argv)
    cpu_admission(args.expected_node)
    bundle_ref = {"path": args.inputs, "sha256": args.inputs_sha256}
    bundle = bound_json(bundle_ref)
    require(bundle.get("schema") == "model_v3_C2_train_solver_diagnostic_inputs_v1", "Bound TRAIN-only diagnostic inputs required")
    protocol = registered_protocol(bundle["protocol_registration"])
    request, selected, failed = (bound_json(bundle[key]) for key in ("source_request", "selection_plan", "original_failure"))
    require(request["schema"] == "model_v3_C2_existing_S_request_v1" and request["preregistration_sha"] == ORIGINAL_PREREGISTRATION
            and selected["source_request_sha256"] == canonical(request)
            and selected["selection"] == request["selection"] and selected["selection_uses_targets"] is False
            and selected["native_geometry_records_decoded"] == 0, "Use the exact old source request and closed metadata selection")
    require(failed["stage"] == "TRAIN_SPARSE_FIT" and failed["native_geometry_records_decoded"] == 8192
            and failed["exception_type"] == "ValueError"
            and "Sparse LSQR did not satisfy the preregistered stopping condition" in failed["exception_chain"],
            "Original v1 failure evidence differs; do not infer an unstored stop code")
    root = Path(bundle["source_repository"]).absolute()
    output = args.output_root.absolute()
    require(not output.exists() and not output.resolve().is_relative_to(root.resolve())
            and not output.resolve().is_relative_to(Path(__file__).resolve().parent), "New external diagnostic output directory required")
    census = fixed_monitor(bundle["runtime_monitor"])
    output.mkdir(parents=True)
    guard = Guard(output, census)
    source = run = None
    initial_sources = executed_sources()
    try:
        sys.path.insert(0, str(root/"current"))
        from phychem_mfm.phase1 import v3_coordinate_lookup as core
        from phychem_mfm.phase1.v3_coordinate_lookup_source import ExistingSLookupSource
        require(Path(core.__file__).resolve() == (root/"current/phychem_mfm/phase1/v3_coordinate_lookup.py").resolve(),
                "Wrong original core package tree imported")
        require(asdict(core.CoordinateLookupConfig()) == request["method"]
                and request["method"]["maximum_iterations"] == 500
                and request["selection"]["train_records"] == 8192 and request["selection"]["validation_records"] == 1024,
                "Original v1 method or population changed")
        source = ExistingSLookupSource(request, check=guard)
        require(selected["role_evidence"] == source.evidence and len(selected["records"]["TRAIN"]) == 8192,
                "Original frozen role/selection binding differs")
        layout = configure_wandb_layout(output)
        import wandb
        run = wandb.init(project="phychem-model-v3", mode="offline", dir=str(output),
            name="C2_TRAIN_solver_diagnostic_"+os.environ["SLURM_JOB_ID"],
            config={"diagnostic_only": True, "source_request_sha256": bundle["source_request"]["sha256"],
                "selection_plan_sha256": bundle["selection_plan"]["sha256"],
                "diagnostic_protocol_commit": bundle["protocol_registration"]["commit"],
                "diagnostic_protocol_sha256": bundle["protocol_registration"]["sha256"],
                "original_code_sha": request["code_sha"], "original_preregistration_sha": ORIGINAL_PREREGISTRATION,
                "blas_threads": 1, "tracking_layout": layout, "seed": request["source_noise"]["seed"]})
        require(run is not None and not run.disabled, "Persistent offline SDK required")
        save(output/"input_binding.json", {"inputs": binding(args.inputs), "source_request": bundle["source_request"],
            "selection_plan": bundle["selection_plan"], "original_failure": bundle["original_failure"],
            "protocol_registration": bundle["protocol_registration"], "executed_sources": initial_sources,
            "runtime": {"numpy_version": np.__version__, "scipy_version": scipy.__version__,
                "threadpoolctl_version": threadpoolctl.__version__, "python": sys.version,
                "lsqr_source": binding(inspect.getsourcefile(core.lsqr)), "threadpoolctl_source": binding(threadpoolctl.__file__)},
            "tracking_layout": layout, "native_PRETRAIN_VAL_records_decoded": 0})
        def sink(name, value):
            save(output/(name+".json"), value)
        local_request = {**request, "diagnostic_selection_plan_raw_sha256": bundle["selection_plan"]["sha256"]}
        guard.stage = "TRAIN_ORIGINAL_BUILD_AND_CONTROLLED_SOURCE_500"
        try:
            result, arrays = run_train_only(core, source, local_request, selected, sink=sink, check=guard,
                numeric_budget=CAPS["maximum_numeric_bytes"])
        except WorkDeadline as exc:
            result, arrays = {"status": "DIAGNOSTIC_ONLY_CENSORED_NO_BASELINE_ACCEPTANCE", "cause": str(exc),
                "censored_phase": guard.stage,
                "native_TRAIN_records_decoded": source.native_reads, "native_PRETRAIN_VAL_records_decoded": 0,
                "original_v1_job_4520482_remains_FAILED": True, "original_v1_stop_or_iteration_count_inferred": False,
                "candidate_stop_code": None, "candidate_iterations": None, "model_selection_gate": False}, None
            candidate_path = output/"active_jacobi_candidate_return.json"
            if candidate_path.exists():
                actual_candidate = bound_json(binding(candidate_path))
                result["candidate_stop_code"] = actual_candidate["solver"]["stop_code"]
                result["candidate_iterations"] = actual_candidate["solver"]["iterations"]
                result["candidate_solver_return"] = binding(candidate_path)
            thread_path = output/"active_jacobi_thread_control.json"
            if thread_path.exists(): result["candidate_thread_control"] = binding(thread_path)
        guard.finalizing, guard.stage = True, "FINAL_SOURCE_VERIFICATION_NO_VALIDATION"
        source.verify(); source.close(); source = None
        require(initial_sources == executed_sources(), "Diagnostic source changed during job")
        for name in ("source_request", "selection_plan", "original_failure"):
            bound_json(bundle[name])
        result["array_artifact"] = write_arrays(arrays, output, guard) if arrays is not None else {"saved": False, "reason": "work deadline"}
        result.update({"wandb_run_id": run.id, "tracking_mode": "persistent_offline", "online_sync_claimed": False,
            "elapsed_seconds": time.monotonic()-guard.started, "process_peak_RSS_bytes": guard.peak_RSS_bytes,
            "owned_output_bytes_before_finalization": census(output)})
        source_receipt = output/"controlled_source_solver_return.json"
        if source_receipt.exists():
            observed = json.loads(source_receipt.read_text())
            run.log({"source/stop_code": observed["stop_code"], "source/iterations": observed["iterations"],
                "source/solver_wall_seconds": observed["solver_wall_seconds"]}, step=0, commit=True)
        numeric = {"diagnostic/completed_requested_work": arrays is not None, "diagnostic/native_PRETRAIN_VAL_records_decoded": 0}
        if "candidate" in result:
            stats = result["candidate"]["solver"]
            numeric.update({"candidate/iterations": stats["iterations"],
                "candidate/solver_wall_seconds": result["candidate"]["solver_wall_seconds"]})
        run.log(numeric, step=1, commit=True)
        run.finish(); run = None
        guard()
        save(output/"DIAGNOSTIC_RESULT.json", result)
        save(output/"DIAGNOSTIC_DONE.json", {"status": result["status"], "result": binding(output/"DIAGNOSTIC_RESULT.json"),
            "inputs": binding(args.inputs), "native_PRETRAIN_VAL_records_decoded": 0, "baseline_accepted": False})
    except BaseException as exc:
        if run is not None: run.finish(exit_code=1)
        save(output/"DIAGNOSTIC_FAILED.json", {"exception_type": type(exc).__name__, "exception_chain": traceback.format_exc(),
            "stage": guard.stage, "native_TRAIN_records_decoded": None if source is None else source.native_reads,
            "native_PRETRAIN_VAL_records_decoded": 0, "baseline_accepted": False})
        raise
    finally:
        if source is not None: source.close()


if __name__ == "__main__":
    main()
