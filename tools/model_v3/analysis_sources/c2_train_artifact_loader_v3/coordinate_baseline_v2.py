#!/usr/bin/env python3
"""Conditional C2 v2 analysis tool; no real execution without new adoption.

The old request/source/selection is immutable. Original design_matrix and
evaluation are reused, but this independent fitter never manufactures a v1
500-iteration receipt from augmented-operator statistics.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import hashlib
import inspect
import json
import math
import os
import re
from pathlib import Path
import resource
import subprocess
import sys
import time
import traceback

sys.dont_write_bytecode = True
import numpy as np
import scipy
import threadpoolctl
from scipy import sparse

import diagnose_coordinate_lookup as support_runtime
import solver_math as solver_runtime
from core_capture import controlled_blas, source_sha
from solver_math import augmented_active_jacobi, csr_fingerprint, numerical_state, solve_augmented, require


STOP_CODES = (0, 1, 2, 4, 5)
DIAGNOSTIC_PREREGISTRATION = "cd0c434bb39824cd75c24d7c6de0531946da1de5"
DIAGNOSTIC_PROTOCOL_RAW_SHA256 = "415f1fa96d0a510fa5c7eeeca381b27603edecba6d27ac1b01bc43712e847961"
EXECUTED_FILES = ("coordinate_baseline_v2.py", "solver_math.py", "core_capture.py", "diagnose_coordinate_lookup.py")
REUSED_SOURCE_SHA256 = {
    "solver_math.py": "e0cf8ef6859d026e8dc6c260718f0c5ddc368779097fa48405572f1f26f79472",
    "core_capture.py": "9ac5b4be9a029a093419d0d6cb92673b3f89ca41a4a02e21b8c07f9a8fe33cd3",
    "diagnose_coordinate_lookup.py": "7c78234b333dddd87ff5efd0927cf9f25642f455e6c31ca73c9abb936ed1e781"}
SOLVER = {"kind": "active_Jacobi_explicit_augmented_LSQR_v2", "damp": 0., "maximum_iterations": 2000,
          "atol": 1e-8, "btol": 1e-8, "condition_limit": 1e8, "ridge": 1e-4,
          "BLAS_threads": 1, "warm_start_used": False, "KKT_acceptance_threshold": None}
CAPS = support_runtime.CAPS


def executed_sources():
    root = Path(__file__).absolute().parent
    return {name: support_runtime.binding(root/name)["sha256"] for name in EXECUTED_FILES}


def save_v2(path, value):
    support_runtime.save(path, {**value, "method": SOLVER, "original_v1_job_4520482_remains_FAILED": True})


@dataclass
class TrainSystem:
    matrix: object
    rhs_normalized: np.ndarray
    support: np.ndarray
    atoms: int
    directed_edges: int
    receipts: list
    capacity: dict


def build_train_system(core, records, config, *, expected_records, check=lambda: None):
    """Exact original design/stack/RHS order; no old solver or old receipt."""
    require(type(expected_records) is int and 0 < expected_records <= config.max_train_records,
            "Exact bounded TRAIN record count required")
    matrices, targets, receipts, seen = [], [], [], set()
    support = np.zeros(config.columns, dtype=np.int64)
    atoms = edges = 0
    capacity = core.matrix_capacity_estimate(atoms=0, directed_edges=0, columns=config.columns)
    for record in records:
        check()
        require(len(receipts) < expected_records, "TRAIN stream exceeded its fixed population")
        require(isinstance(record, core.LookupRecord) and record.role == "TRAIN", "Only TRAIN may enter v2 fit")
        record.validate(config)
        require(record.record_id not in seen, "Duplicate TRAIN record")
        matrix, codes = core.design_matrix(record.elements, record.noisy, config)
        atoms += len(record.elements); edges += len(codes)
        capacity = core.matrix_capacity_estimate(atoms=atoms, directed_edges=edges, columns=config.columns)
        require(atoms <= config.max_train_atoms and edges <= config.max_directed_edges
                and 3*edges <= config.max_coo_entries and capacity["numeric_upper_bytes"] <= config.matrix_budget_bytes,
                "Original sparse TRAIN budget exceeded; no truncation or changed features")
        matrices.append(matrix)
        targets.append((record.noisy.astype(np.float64)-record.clean.astype(np.float64)).reshape(-1))
        np.add.at(support, codes, 1)
        receipts.append(core._record_receipt(record)); seen.add(record.record_id)
    require(len(receipts) == expected_records, "TRAIN stream ended before its exact fixed budget")
    check()
    matrix = sparse.vstack(matrices, format="csr")
    target = np.concatenate(targets)
    del matrices, targets
    return TrainSystem(matrix, target/math.sqrt(atoms), support, atoms, edges, receipts, capacity)


@dataclass(frozen=True)
class V2Lookup:
    core: object
    config: object
    coefficients: np.ndarray
    train_edge_counts: np.ndarray
    fit_receipt: dict

    def predict_noise(self, elements, noisy):
        return self.core.CoordinateLookup.predict_noise(self, elements, noisy)

    def document(self):
        require(self.fit_receipt["v2_executed_source_sha256"] == executed_sources(), "V2 source drift after fitting")
        observed = np.flatnonzero(self.train_edge_counts)
        require(np.isfinite(self.coefficients).all() and np.equal(self.coefficients[self.train_edge_counts == 0], 0).all(),
                "Finite v2 coefficients and exact unknown-bin zero required")
        return {"schema": "model_v3_C2_coordinate_lookup_v2", "status": "ANALYSIS_ONLY_NOT_MODEL_SELECTION_V2",
            "method": SOLVER,
            "source_feature_resource_configuration_v1": asdict(self.config),
            "configuration_note": "Original adapter defaults include max_iterations=500; actual v2 solver is separately declared below.",
            "actual_solver_configuration_v2": SOLVER, "source_core": self.core.source_binding(),
            "v2_implementation_sha256": source_sha(__file__), "fit_receipt_v2": self.fit_receipt,
            "v2_executed_source_sha256": self.fit_receipt["v2_executed_source_sha256"],
            "codes": observed.tolist(), "coefficients": self.coefficients[observed].tolist(),
            "train_directed_edge_counts": self.train_edge_counts[observed].tolist(),
            "original_v1_job_4520482_remains_FAILED": True}


def fit_v2(core, records, *, config, expected_records, source_request_sha256, source_plan_sha256,
           check=lambda: None, sink=lambda *_: None):
    """TRAIN fit only. Calling this never opens or evaluates validation data."""
    require(config.ridge == 1e-4 and config.atol == config.btol == 1e-8 and config.condition_limit == 1e8,
            "Unchanged original ridge/tolerances required")
    before_sources = executed_sources()
    require(all(before_sources[name] == sha for name, sha in REUSED_SOURCE_SHA256.items()), "Reused tested diagnostic source changed")
    if hasattr(check, "stage"): check.stage = "BASELINE_v2_TRAIN_BUILD"
    build_start = time.perf_counter()
    train = build_train_system(core, records, config, expected_records=expected_records, check=check)
    build_wall = time.perf_counter()-build_start
    original = csr_fingerprint(train.matrix, check=check)
    def emit(name, value):
        sink(name, {**value, "method": SOLVER, "original_v1_job_4520482_remains_FAILED": True})
    with controlled_blas(emit, "BASELINE_v2_thread_control") as threads:
        if hasattr(check, "stage"): check.stage = "BASELINE_v2_AUGMENTED_PREPROCESS"
        preprocess_start = time.perf_counter()
        augmented = augmented_active_jacobi(train.matrix, train.rhs_normalized, train.support,
            n_atoms=train.atoms, ridge=config.ridge, numeric_budget_bytes=CAPS["maximum_numeric_bytes"], check=check)
        preprocessing_wall = time.perf_counter()-preprocess_start
        if hasattr(check, "stage"): check.stage = "BASELINE_v2_AUGMENTED_LSQR"
        solve_start = time.perf_counter()
        coefficient, stats = solve_augmented(augmented, atol=config.atol, btol=config.btol,
            condition_limit=config.condition_limit, maximum_iterations=2000, check=check)
        solver_wall = time.perf_counter()-solve_start
        # These values belong to the augmented operator, never to old A/500.
        observed = {"schema": "model_v3_C2_v2_augmented_solver_return_v1", "actual_solver_configuration": SOLVER,
            "augmented_operator_statistics": stats, "preprocessing": augmented.metadata,
            "TRAIN_build_wall_seconds": build_wall, "preprocessing_wall_seconds": preprocessing_wall,
            "solver_wall_seconds": solver_wall, "full_original_coefficient_shape": list(coefficient.shape)}
        emit("BASELINE_v2_solver_return", observed)
        require(stats["stop_code"] in STOP_CODES and np.isfinite(coefficient).all(),
                "V2 augmented LSQR did not satisfy unchanged stop/finite rule; do not evaluate VAL")
        require(np.equal(coefficient[train.support == 0], 0).all(), "Unknown bins must keep exact zero correction")
        if hasattr(check, "stage"): check.stage = "BASELINE_v2_ORIGINAL_COORDINATE_KKT"
        kkt = numerical_state(train.matrix, train.rhs_normalized, coefficient,
            n_atoms=train.atoms, ridge=config.ridge, check=check)
    require(csr_fingerprint(train.matrix, check=check) == original, "Original TRAIN CSR was changed")
    require(before_sources == executed_sources(), "V2 source changed during fit")
    receipt = {"schema": "model_v3_C2_coordinate_baseline_v2_fit_receipt_v1", "fit_role": "TRAIN", "method": SOLVER,
        "TRAIN_records": len(train.receipts), "TRAIN_atoms": train.atoms, "TRAIN_directed_edges": train.directed_edges,
        "TRAIN_record_ids": sorted(r["record_id"] for r in train.receipts),
        "TRAIN_molecule_ids": sorted({r["molecule_id"] for r in train.receipts}),
        "TRAIN_membership_sha256": support_runtime.canonical(train.receipts),
        "source_request_raw_sha256": source_request_sha256, "source_plan_raw_sha256": source_plan_sha256,
        "source_feature_resource_configuration_v1_sha256": support_runtime.canonical(asdict(config)),
        "actual_solver_configuration_v2": SOLVER, "augmented_operator_statistics": stats,
        "v2_executed_source_sha256": before_sources,
        "original_coordinate_KKT_and_objective": kkt, "KKT_acceptance_threshold_applied": False,
        "preprocessing": augmented.metadata, "thread_control": threads,
        "original_matrix": original, "original_sparse_capacity": train.capacity,
        "target_units": "epsilon=y-x, Angstrom displacement", "normalization": "sum_squared_vector_error/TRAIN_atoms",
        "damp_squared_of_equivalent_unscaled_original_ridge": config.ridge*train.atoms,
        "dense_Gram_constructed": False, "validation_used_for_fit_or_tuning": False,
        "solver_wall_seconds": solver_wall, "TRAIN_build_wall_seconds": build_wall,
        "preprocessing_wall_seconds": preprocessing_wall, "original_v1_job_4520482_remains_FAILED": True}
    return V2Lookup(core, config, coefficient.copy(), train.support.copy(), receipt)


def restore_v2(core, document):
    require(document.get("schema") == "model_v3_C2_coordinate_lookup_v2"
            and document.get("status") == "ANALYSIS_ONLY_NOT_MODEL_SELECTION_V2"
            and document["actual_solver_configuration_v2"] == SOLVER
            and document["source_core"] == core.source_binding()
            and document["v2_implementation_sha256"] == source_sha(__file__)
            and document["v2_executed_source_sha256"] == executed_sources(), "Bound honest v2 model schema/source required")
    config = core.CoordinateLookupConfig(**document["source_feature_resource_configuration_v1"])
    codes = np.asarray(document["codes"], dtype=np.int64)
    values = np.asarray(document["coefficients"], dtype=np.float64)
    counts = np.asarray(document["train_directed_edge_counts"], dtype=np.int64)
    require(codes.ndim == values.ndim == counts.ndim == 1 and len(codes) == len(values) == len(counts)
            and len(set(codes.tolist())) == len(codes) and ((codes >= 0) & (codes < config.columns)).all()
            and (counts > 0).all() and np.isfinite(values).all(), "Finite unique supported v2 coefficient table required")
    receipt = document["fit_receipt_v2"]
    require(receipt.get("schema") == "model_v3_C2_coordinate_baseline_v2_fit_receipt_v1"
            and receipt["actual_solver_configuration_v2"] == SOLVER
            and receipt["augmented_operator_statistics"]["stop_code"] in STOP_CODES
            and receipt["augmented_operator_statistics"]["coefficients_finite"] is True
            and receipt["v2_executed_source_sha256"] == document["v2_executed_source_sha256"]
            and receipt["source_feature_resource_configuration_v1_sha256"] == support_runtime.canonical(asdict(config)),
            "Accepted source-bound v2 fit receipt required")
    coefficients, support = np.zeros(config.columns), np.zeros(config.columns, dtype=np.int64)
    coefficients[codes], support[codes] = values, counts
    return V2Lookup(core, config, coefficients, support, receipt)


def fit_then_evaluate(core, source, plan, *, config, train_records, validation_records,
                      request_sha256, plan_sha256, check=lambda: None, sink=lambda *_: None,
                      on_fit=lambda _: None):
    """Synthetic-testable stop boundary; production activation is checked earlier."""
    require(source.native_reads == 0, "Fresh source handles required for a new v2 fit")
    model = fit_v2(core, source.records("TRAIN", plan), config=config, expected_records=train_records,
        source_request_sha256=request_sha256, source_plan_sha256=plan_sha256, check=check, sink=sink)
    require(source.native_reads == train_records, "Exact TRAIN-only fit boundary required before VAL")
    on_fit(model)
    if hasattr(check, "stage"): check.stage = "BASELINE_v2_PRETRAIN_VAL_ANALYSIS"
    metrics = core.evaluate_coordinate_lookup(model, source.records("PRETRAIN_VAL", plan),
        expected_records=validation_records, check=check)
    require(source.native_reads == train_records+validation_records, "Full unchanged validation budget required")
    return model, metrics


def validate_diagnostic_registration(original_inputs, input_binding):
    """Keep the executed local ref distinct from its public same-tree identity.

    The caller first verifies the immutable original input/binding byte chains.
    Public commit identity is pinned; the recorded public tree is checked against
    the real executed local Git object. No arbitrary local/public ID fallback.
    """
    public = original_inputs.get("public_registration")
    local = original_inputs.get("protocol_registration")
    require(type(public) is dict and set(public) == {"commit", "tree"}
            and public["commit"] == DIAGNOSTIC_PREREGISTRATION
            and type(public["tree"]) is str and re.fullmatch(r"[0-9a-f]{40}", public["tree"]),
            "Actual pinned public diagnostic registration required")
    require(type(local) is dict and set(local) == {"repository", "commit", "path", "sha256"}
            and input_binding.get("protocol_registration") == local
            and type(local["commit"]) is str and re.fullmatch(r"[0-9a-f]{40}", local["commit"])
            and local["commit"] != public["commit"]
            and local["sha256"] == DIAGNOSTIC_PROTOCOL_RAW_SHA256,
            "Complete executed local diagnostic ref/blob identity differs")
    # The already tested loader verifies raw Git blob SHA, exact method/caps,
    # normalized ridge rules and the three executed diagnostic-source hashes.
    support_runtime.registered_protocol(local)
    actual_tree = subprocess.run(["git", "-C", local["repository"], "rev-parse", local["commit"]+"^{tree}"],
        check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.decode().strip()
    require(actual_tree == public["tree"], "Executed local diagnostic tree differs from recorded public tree")
    return {"schema": "model_v3_C2_diagnostic_local_public_mapping_v1",
        "executed_local_protocol_registration": dict(local), "public_registration": dict(public),
        "verified_local_tree": actual_tree, "verified_protocol_blob_raw_sha256": local["sha256"],
        "method_and_source_inventory_verified": True}


def adopted_protocol(registration, request_ref, plan_ref, diagnostic_ref, diagnostic_done_ref, diagnostic_input_ref):
    """No real fit/VAL merely because the conditional tool has been published."""
    import re
    require(re.fullmatch(r"[0-9a-f]{40}", registration["commit"]), "Actual public v2 protocol commit required")
    relative = registration["path"]
    require(relative and not relative.startswith(("/", "-")) and "\\" not in relative
            and all(p not in ("", ".", "..") for p in relative.split("/")), "Safe registered protocol path required")
    raw = subprocess.run(["git", "-C", registration["repository"], "show", registration["commit"]+":"+relative], check=True,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout
    require(len(raw) <= 128*1024 and hashlib.sha256(raw).hexdigest() == registration["sha256"], "Committed v2 protocol SHA differs")
    value = support_runtime.decode_json(raw)
    require(value.get("schema") == "model_v3_C2_coordinate_baseline_v2_protocol_v1"
            and value.get("adoption_status") == "ADOPTED_AFTER_TRAIN_ONLY_DIAGNOSTIC",
            "V2 is only prepared; explicit new public adoption protocol required")
    require(value["solver"] == SOLVER and value["caps"] == CAPS
            and value["source_inventory_sha256"] == support_runtime.canonical(executed_sources())
            and value["source_request_raw_sha256"] == request_ref["sha256"]
            and value["selection_plan_raw_sha256"] == plan_ref["sha256"]
            and value["TRAIN_diagnostic_result_raw_sha256"] == diagnostic_ref["sha256"]
            and value["TRAIN_diagnostic_done_raw_sha256"] == diagnostic_done_ref["sha256"]
            and value["TRAIN_diagnostic_input_binding_raw_sha256"] == diagnostic_input_ref["sha256"],
            "Actual v2 source/selection/diagnostic binding differs")
    diagnostic = support_runtime.bound_json(diagnostic_ref)
    done = support_runtime.bound_json(diagnostic_done_ref)
    diagnostic_inputs = support_runtime.bound_json(diagnostic_input_ref)
    original_diagnostic_inputs = support_runtime.bound_json(diagnostic_inputs["inputs"])
    require(done["result"]["sha256"] == diagnostic_ref["sha256"]
            and done["status"] == diagnostic["status"]
            and done["inputs"]["sha256"] == diagnostic_inputs["inputs"]["sha256"]
            and diagnostic_inputs["source_request"]["sha256"] == request_ref["sha256"]
            and diagnostic_inputs["selection_plan"]["sha256"] == plan_ref["sha256"]
            and original_diagnostic_inputs["source_request"]["sha256"] == request_ref["sha256"]
            and original_diagnostic_inputs["selection_plan"]["sha256"] == plan_ref["sha256"]
            and diagnostic_inputs["native_PRETRAIN_VAL_records_decoded"] == done["native_PRETRAIN_VAL_records_decoded"] == 0,
            "Completed TRAIN diagnostic does not bind the same original inputs")
    validate_diagnostic_registration(original_diagnostic_inputs, diagnostic_inputs)
    source_return = diagnostic["source"]["baseline"]
    require(type(source_return["stop_code"]) is int and type(source_return["coefficients_finite"]) is bool
            and type(diagnostic["candidate"]["solver"]["stop_code"]) is int,
            "Actual returned diagnostic stop/finite fields required")
    original_passed = (source_return["stop_code"] in STOP_CODES and source_return["coefficients_finite"] is True)
    require(diagnostic["status"] == "DIAGNOSTIC_ONLY_COMPLETED_NO_BASELINE_ACCEPTANCE"
            and diagnostic["native_PRETRAIN_VAL_records_decoded"] == 0
            and not original_passed
            and diagnostic["candidate"]["solver"]["stop_code"] in STOP_CODES
            and diagnostic["candidate"]["solver"]["coefficients_finite"] is True,
            "Conditional v2 route not established; a successful original 500 uses the original-v1 retry route")
    return value


class V2Guard:
    """Owned CPU bounds with honest validation counters (no copied zero log)."""
    def __init__(self, output, census):
        self.output, self.census, self.started = output, census, time.monotonic()
        self.stage, self.finalizing, self.source = "SOURCE_BINDING", False, None
        self.checked = self.logged = -1e9
        self.peak_RSS_bytes = self.output_bytes = 0
        self.output_cap = min(CAPS["maximum_output_bytes"], int(os.environ.get("MODEL_V3_CHILD_OUTPUT_BUDGET_BYTES", CAPS["maximum_output_bytes"])))
    def __call__(self):
        elapsed = time.monotonic()-self.started
        require(elapsed <= (CAPS["finalization_deadline_seconds"] if self.finalizing else CAPS["work_deadline_seconds"]),
                "V2 reached reserved work/finalization boundary")
        self.peak_RSS_bytes = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)*1024
        require(self.peak_RSS_bytes <= CAPS["maximum_process_RSS_bytes"], "V2 exceeded unchanged RSS cap")
        if elapsed-self.checked >= 2:
            self.output_bytes = self.census(self.output); self.checked = elapsed
            require(self.output_bytes <= self.output_cap, "V2 exceeded unchanged output cap")
        if elapsed-self.logged >= 30:
            reads = 0 if self.source is None else self.source.native_reads
            print(json.dumps({"stage": self.stage, "elapsed_seconds": elapsed, "native_geometry_records_decoded": reads,
                "native_TRAIN_records_decoded": min(reads, 8192), "native_PRETRAIN_VAL_records_decoded": max(0, reads-8192),
                "process_peak_RSS_bytes": self.peak_RSS_bytes, "output_bytes": self.output_bytes}), flush=True)
            self.logged = elapsed


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", required=True); parser.add_argument("--inputs-sha256", required=True)
    parser.add_argument("--expected-node", required=True); parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args(argv)
    support_runtime.cpu_admission(args.expected_node)
    inputs_ref = {"path": args.inputs, "sha256": args.inputs_sha256}
    inputs = support_runtime.bound_json(inputs_ref)
    require(inputs.get("schema") == "model_v3_C2_coordinate_baseline_v2_inputs_v1", "Bound v2 inputs required")
    protocol = adopted_protocol(inputs["protocol_registration"], inputs["source_request"],
        inputs["selection_plan"], inputs["TRAIN_diagnostic_result"], inputs["TRAIN_diagnostic_done"], inputs["TRAIN_diagnostic_input_binding"])
    require(protocol.get("fit_origin") == "NEW_TRAIN_FIT", "Use the dedicated prior-TRAIN-artifact entrypoint; do not silently refit")
    request = support_runtime.bound_json(inputs["source_request"])
    plan = support_runtime.bound_json(inputs["selection_plan"])
    require(request["schema"] == "model_v3_C2_existing_S_request_v1"
            and request["preregistration_sha"] == support_runtime.ORIGINAL_PREREGISTRATION
            and plan["source_request_sha256"] == support_runtime.canonical(request)
            and plan["selection"] == request["selection"] and plan["selection_uses_targets"] is False
            and plan["native_geometry_records_decoded"] == 0, "Exact old closed label-free plan required")
    root = Path(inputs["source_repository"]).absolute(); output = args.output_root.absolute()
    require(not output.exists() and not output.resolve().is_relative_to(root.resolve())
            and not output.resolve().is_relative_to(Path(__file__).resolve().parent), "Fresh external v2 output required")
    census = support_runtime.fixed_monitor(inputs["runtime_monitor"])
    output.mkdir(parents=True); guard = V2Guard(output, census)
    source = run = None; before = executed_sources(); native_reads = 0
    try:
        sys.path.insert(0, str(root/"current"))
        from phychem_mfm.phase1 import v3_coordinate_lookup as core
        from phychem_mfm.phase1.v3_coordinate_lookup_source import ExistingSLookupSource
        require(Path(core.__file__).resolve() == (root/"current/phychem_mfm/phase1/v3_coordinate_lookup.py").resolve()
                and asdict(core.CoordinateLookupConfig()) == request["method"]
                and request["selection"]["train_records"] == 8192 and request["selection"]["validation_records"] == 1024,
                "Unchanged original C2 source/method/population required")
        source = ExistingSLookupSource(request, check=guard); guard.source = source
        require(plan["role_evidence"] == source.evidence, "Original pretraining-role metadata proof differs")
        layout = support_runtime.configure_wandb_layout(output)
        import wandb
        run = wandb.init(project="phychem-model-v3", mode="offline", dir=str(output),
            name="C2_conditional_baseline_v2_"+os.environ["SLURM_JOB_ID"], config={"method": SOLVER,
                "source_request_sha256": inputs["source_request"]["sha256"], "selection_plan_sha256": inputs["selection_plan"]["sha256"],
                "public_v2_protocol_commit": inputs["protocol_registration"]["commit"], "tracking_layout": layout,
                "original_v1_job_4520482_remains_FAILED": True, "analysis_only": True})
        require(run is not None and not run.disabled, "Persistent offline SDK required")
        save_v2(output/"BASELINE_v2_INPUT_BINDING.json", {"inputs": support_runtime.binding(args.inputs),
            "source_request": inputs["source_request"], "selection_plan": inputs["selection_plan"],
            "protocol_registration": inputs["protocol_registration"], "executed_sources": before,
            "actual_solver_configuration_v2": SOLVER, "source_feature_resource_configuration_v1": request["method"],
            "runtime": {"numpy_version": np.__version__, "scipy_version": scipy.__version__,
                "threadpoolctl_version": threadpoolctl.__version__, "python": sys.version,
                "lsqr_source": support_runtime.binding(inspect.getsourcefile(solver_runtime.lsqr)),
                "threadpoolctl_source": support_runtime.binding(threadpoolctl.__file__)}})
        guard.stage = "BASELINE_v2_TRAIN_FIT"
        def on_fit(model):
            save_v2(output/"BASELINE_v2_FIT_RECEIPT.json", model.fit_receipt)
            run.log({"fit/TRAIN_records": 8192, "fit/TRAIN_atoms": model.fit_receipt["TRAIN_atoms"],
                "fit/augmented_solver_iterations": model.fit_receipt["augmented_operator_statistics"]["iterations"]}, step=0, commit=True)
        # Production activation was checked before opening source handles.
        model, metrics = fit_then_evaluate(core, source, plan, config=core.CoordinateLookupConfig(**request["method"]),
            train_records=8192, validation_records=1024, request_sha256=inputs["source_request"]["sha256"],
            plan_sha256=inputs["selection_plan"]["sha256"], check=guard, on_fit=on_fit,
            sink=lambda name, value: save_v2(output/(name+".json"), value))
        guard.finalizing = True; source.verify(); source.close()
        native_reads = source.native_reads; source = None
        require(native_reads == 9216 and before == executed_sources(), "Source/count bindings changed during v2")
        for key in ("source_request", "selection_plan", "TRAIN_diagnostic_result", "TRAIN_diagnostic_done", "TRAIN_diagnostic_input_binding"):
            support_runtime.bound_json(inputs[key])
        save_v2(output/"BASELINE_v2_LOOKUP.json", model.document())
        run.log({"validation/"+key: value for key, value in metrics.items() if type(value) in (int, float)}, step=1, commit=True)
        result = {"schema": "model_v3_C2_coordinate_baseline_v2_result_v1", "status": "ANALYSIS_COMPLETE_NOT_MODEL_SELECTION_V2",
            "method": SOLVER, "fit_receipt_v2": model.fit_receipt, "metrics": metrics,
            "native_geometry_records_decoded": native_reads, "source_request": inputs["source_request"],
            "selection_plan": inputs["selection_plan"], "public_v2_protocol_commit": inputs["protocol_registration"]["commit"],
            "original_v1_job_4520482_remains_FAILED": True, "wandb_run_id": run.id,
            "tracking_mode": "persistent_offline", "online_sync_claimed": False,
            "resource_observation": {"wall_seconds": time.monotonic()-guard.started, "process_peak_RSS_bytes": guard.peak_RSS_bytes}}
        run.finish(); run = None; guard()
        save_v2(output/"BASELINE_v2_RESULT.json", result)
        save_v2(output/"BASELINE_v2_COMPLETE.json", {"schema": "model_v3_C2_coordinate_baseline_v2_complete_v1",
            "status": result["status"], "method": SOLVER, "result": support_runtime.binding(output/"BASELINE_v2_RESULT.json"),
            "lookup": support_runtime.binding(output/"BASELINE_v2_LOOKUP.json"), "inputs": support_runtime.binding(args.inputs),
            "source_request": inputs["source_request"], "selection_plan": inputs["selection_plan"],
            "original_v1_job_4520482_remains_FAILED": True, "model_selection_gate": False})
    except BaseException as exc:
        if run is not None: run.finish(exit_code=1)
        save_v2(output/"BASELINE_v2_FAILED.json", {"schema": "model_v3_C2_coordinate_baseline_v2_failure_v1",
            "exception_type": type(exc).__name__, "exception_chain": traceback.format_exc(), "stage": guard.stage,
            "native_geometry_records_decoded": native_reads if source is None else source.native_reads,
            "original_v1_job_4520482_remains_FAILED": True, "model_selection_gate": False})
        raise
    finally:
        if source is not None: source.close()


if __name__ == "__main__": main()
