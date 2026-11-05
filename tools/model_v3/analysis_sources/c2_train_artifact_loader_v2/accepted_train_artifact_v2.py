#!/usr/bin/env python3
"""Conditional v2: restore completed TRAIN parameters, then first native VAL.

No TRAIN geometry/design matrix, new solve or new KKT is computed here.
The stored candidate_coefficient is already original-coordinate c, not z=D*c.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import traceback
import zipfile

sys.dont_write_bytecode = True
import numpy as np

import coordinate_baseline_v2 as base
from core_capture import source_sha
from solver_math import require


FIT_ORIGIN = "prior_TRAIN_diagnostic_artifact"
TRAIN_SUPERVISOR_SOURCES = {
    "run_cpu_supervised_128m_v1.py": "23fe5a473918dc420621d98bef49e7e08c7bcd7b43e6f001ae8821bce96b976e",
    "runtime_monitor.py": "dbe875ab7ceec7e5002c5b70bff0608e3506f7451bdacd38e5f5bfc0700663fe",
    "run_supervised.py": "a1b16ea1af0400dd695a6b1e651b9f88a5ed88bcabe4ed718d5e19ad11abd7bd",
    "private_runtime_storage.py": "791e2742b2131e5001ebc4fe549d8fcb43f7d28f399368a5aa5f82d7d592a041"}
ARRAY_TYPES = {"active_columns": np.dtype("int64"), "observed_support": np.dtype("int64"),
    "candidate_coefficient": np.dtype("float64"), "controlled_source_coefficient": np.dtype("float64"),
    "jacobi_scale": np.dtype("float64")}


def executed_sources():
    return {**base.executed_sources(), "accepted_train_artifact_v2.py": source_sha(__file__)}


def _raw_sacct(raw, expected_job):
    argv, stdout = raw["argv"], raw["stdout"]
    require(type(argv) is list and all(type(a) is str for a in argv)
            and any(Path(a).name == "sacct" for a in argv) and type(stdout) is str,
            "Original machine sacct argv/stdout required")
    require(hashlib.sha256(stdout.encode()).hexdigest() == raw["stdout_sha256"], "Raw sacct stdout SHA differs")
    columns = None
    for index, argument in enumerate(argv):
        if argument in ("--format", "-o") and index+1 < len(argv): columns = argv[index+1].split(",")
        if argument.startswith("--format="): columns = argument.split("=", 1)[1].split(",")
    require(columns is not None, "Explicit sacct column order required")
    columns = [re.sub(r"%.*$", "", value) for value in columns]
    require({"JobIDRaw", "State", "ExitCode", "ElapsedRaw"} <= set(columns), "Original parent-job closure columns required")
    matches = []
    for line in stdout.splitlines():
        values = [value.strip() for value in line.split("|")]
        if len(values) == len(columns)+1 and values[-1] == "": values.pop()
        if len(values) != len(columns): continue
        row = dict(zip(columns, values))
        if row["JobIDRaw"] == expected_job: matches.append(row)
    require(len(matches) == 1, "Exactly one actual parent-job accounting row required")
    row = matches[0]
    require(row["State"] == "COMPLETED" and row["ExitCode"] == "0:0"
            and row["ElapsedRaw"].isascii() and row["ElapsedRaw"].isdigit(), "Prior TRAIN job did not actually complete C0")
    return row


def closure(inputs, protocol, diagnostic_binding):
    root = base.support_runtime.bound_json(inputs["TRAIN_closure"])
    require(root.get("schema") == "model_v3_C2_TRAIN_artifact_closure_v1", "Fixed model-owned TRAIN QA closure required")
    source = root["source_job"]
    job = protocol["TRAIN_fit_job_id"]
    require(str(source["job_id"]) == job and source["state"] == "COMPLETED" and source["exit_code"] == "0:0",
            "Closed source TRAIN job identity/status differs")
    row = _raw_sacct(root["raw_sacct"], job)
    require(type(source["elapsed_seconds"]) is int and source["elapsed_seconds"] == int(row["ElapsedRaw"]),
            "Projected and actual TRAIN accounting elapsed differ")
    supervisor = base.support_runtime.bound_json(root["supervisor"])
    require(str(supervisor["job_id"]) == job and supervisor["status"] == "COMPLETED"
            and type(supervisor["exit_code"]) is int and supervisor["exit_code"] == 0
            and supervisor["first_failure"] is None and type(supervisor["remaining"]) is list and not supervisor["remaining"]
            and supervisor["gpu_initialization_permitted"] is False
            and supervisor["private_storage"]["first_sampling_failure"] is None, "Actual CPU supervisor did not close cleanly")
    source_items = list(supervisor["sources_sha256"].items())
    pins = {Path(path).name: sha for path, sha in source_items}
    require(len(source_items) == len(pins) == 4 and pins == TRAIN_SUPERVISOR_SOURCES
            and protocol["TRAIN_supervisor_sources_sha256"] == TRAIN_SUPERVISOR_SOURCES,
            "Actual fixed 128-MiB supervisor/four-source inventory differs")
    command = supervisor["command"]
    require(type(command) is list and all(type(a) is str for a in command)
            and any(Path(a).name == "diagnose_coordinate_lookup.py" for a in command), "Actual supervised TRAIN diagnostic command required")
    for flag, expected in (("--inputs", diagnostic_binding["inputs"]["path"]),
                           ("--inputs-sha256", diagnostic_binding["inputs"]["sha256"])):
        require(command.count(flag) == 1 and command.index(flag)+1 < len(command)
                and command[command.index(flag)+1] == expected, "Actual supervisor binds a different diagnostic input bundle")
    return root


def checked_npz(reference, contents, *, active_count, full_columns):
    require(type(active_count) is int and 0 < active_count <= full_columns, "Explicit expected active-column count required")
    path = Path(reference["path"])
    require(path.is_file() and not path.is_symlink() and path.stat().st_size <= base.CAPS["maximum_array_bytes"],
            "Bounded ordinary private TRAIN NPZ required")
    raw = path.read_bytes()
    require(len(raw) == reference["bytes"] and hashlib.sha256(raw).hexdigest() == reference["sha256"], "TRAIN NPZ raw bytes/SHA differ")
    require(set(contents) == set(ARRAY_TYPES), "Exact completed diagnostic array-content declaration required")
    for name, dtype in ARRAY_TYPES.items():
        require(contents[name] == {"shape": [active_count], "dtype": str(dtype)}, "Declared TRAIN array dtype/shape differs")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        members = archive.infolist(); names = [item.filename for item in members]
        require(len(names) == len(set(names)) == len(ARRAY_TYPES)
                and set(names) == {name+".npy" for name in ARRAY_TYPES}, "Exact unique numeric NPZ keys required")
        require(sum(item.file_size for item in members) <= base.CAPS["maximum_array_bytes"]
                and all(item.file_size <= active_count*8+4096 and not item.is_dir()
                        and not (item.flag_bits & 1) for item in members), "NPZ expanded-array budget/header exceeded")
    with np.load(io.BytesIO(raw), allow_pickle=False, max_header_size=4096) as loaded:
        require(set(loaded.files) == set(ARRAY_TYPES), "Unexpected NPZ array key")
        arrays = {name: loaded[name].copy() for name in ARRAY_TYPES}
    for name, value in arrays.items():
        require(value.dtype == ARRAY_TYPES[name] and value.shape == (active_count,)
                and np.isfinite(value).all(), "Exact finite TRAIN array dtype/shape required")
    codes, support, scale = arrays["active_columns"], arrays["observed_support"], arrays["jacobi_scale"]
    require((codes >= 0).all() and (codes < full_columns).all() and (np.diff(codes) > 0).all()
            and (support > 0).all() and (scale > 0).all(), "Sorted unique in-range supported columns/positive D required")
    return arrays


def adopted_artifact_protocol(inputs):
    value = base.adopted_protocol(inputs["protocol_registration"], inputs["source_request"], inputs["selection_plan"],
        inputs["TRAIN_diagnostic_result"], inputs["TRAIN_diagnostic_done"], inputs["TRAIN_diagnostic_input_binding"])
    require(value.get("fit_origin") == FIT_ORIGIN
            and value["artifact_runtime_source_inventory_sha256"] == base.support_runtime.canonical(executed_sources())
            and value["TRAIN_closure_raw_sha256"] == inputs["TRAIN_closure"]["sha256"]
            and value["TRAIN_artifact_raw_sha256"] == inputs["TRAIN_artifact"]["sha256"]
            and value["TRAIN_artifact_bytes"] == inputs["TRAIN_artifact"]["bytes"],
            "New public artifact-origin source/closure/NPZ adoption binding required")
    return value


@dataclass(frozen=True)
class AcceptedTrainArtifactLookup(base.V2Lookup):
    def document(self):
        value = super().document()
        require(self.fit_receipt["artifact_runtime_source_sha256"] == executed_sources(), "Artifact-loader source drift")
        return {**value, "schema": "model_v3_C2_coordinate_lookup_v2_prior_TRAIN_artifact",
            "fit_origin": FIT_ORIGIN, "artifact_runtime_source_sha256": executed_sources(),
            "current_job_TRAIN_geometry_reads": 0}


def load_accepted_TRAIN_artifact(core, inputs, protocol):
    """Only closed numeric/identity metadata is loaded; no native geometry."""
    request = base.support_runtime.bound_json(inputs["source_request"])
    plan = base.support_runtime.bound_json(inputs["selection_plan"])
    diagnostic = base.support_runtime.bound_json(inputs["TRAIN_diagnostic_result"])
    diagnostic_binding = base.support_runtime.bound_json(inputs["TRAIN_diagnostic_input_binding"])
    done = base.support_runtime.bound_json(inputs["TRAIN_diagnostic_done"])
    prior_inputs = base.support_runtime.bound_json(diagnostic_binding["inputs"])
    require(done["result"]["sha256"] == inputs["TRAIN_diagnostic_result"]["sha256"]
            and done["status"] == diagnostic["status"] and done["native_PRETRAIN_VAL_records_decoded"] == 0
            and done["inputs"]["sha256"] == diagnostic_binding["inputs"]["sha256"]
            and diagnostic_binding["source_request"]["sha256"] == prior_inputs["source_request"]["sha256"] == inputs["source_request"]["sha256"]
            and diagnostic_binding["selection_plan"]["sha256"] == prior_inputs["selection_plan"]["sha256"] == inputs["selection_plan"]["sha256"]
            and prior_inputs["protocol_registration"]["commit"] == base.DIAGNOSTIC_PREREGISTRATION,
            "Full prior diagnostic DONE/input/source/selection/publication chain differs")
    verified_closure = closure(inputs, protocol, diagnostic_binding)
    require(diagnostic_binding["executed_sources"] == base.REUSED_SOURCE_SHA256, "Prior diagnostic executed source pins differ")
    require(request["schema"] == "model_v3_C2_existing_S_request_v1"
            and request["preregistration_sha"] == base.support_runtime.ORIGINAL_PREREGISTRATION
            and request["source_files"]["current/phychem_mfm/phase1/v3_coordinate_lookup.py"] == source_sha(core.__file__)
            and plan["source_request_sha256"] == base.support_runtime.canonical(request)
            and plan["selection"] == request["selection"] and plan["selection_uses_targets"] is False
            and plan["native_geometry_records_decoded"] == 0, "Exact original request/closed plan required")
    config = core.CoordinateLookupConfig(**request["method"])
    require(config.ridge == 1e-4 and config.atol == config.btol == 1e-8 and config.condition_limit == 1e8
            and config.maximum_iterations == 500, "Unchanged prior TRAIN objective/original controlled limits required")
    train = plan["records"]["TRAIN"]
    require(len(train) == request["selection"]["train_records"] == protocol["TRAIN_records"]
            and all(type(r["native_n_atoms"]) is int and 0 < r["native_n_atoms"] <= config.max_record_atoms for r in train),
            "Full original TRAIN record/atom budget required")
    atoms = sum(r["native_n_atoms"] for r in train)
    original = diagnostic["source"]["baseline"]; candidate = diagnostic["candidate"]
    require(diagnostic["status"] == "DIAGNOSTIC_ONLY_COMPLETED_NO_BASELINE_ACCEPTANCE"
            and diagnostic["native_PRETRAIN_VAL_records_decoded"] == 0
            and original["original_configuration"] == request["method"]
            and original["configured_iteration_limit"] == 500 and original["stop_code"] not in base.STOP_CODES
            and original["coefficients_finite"] is True
            and candidate["solver"]["stop_code"] in base.STOP_CODES and candidate["solver"]["coefficients_finite"] is True,
            "Completed finite old-source-failed/augmented-accepted TRAIN evidence required")
    require(diagnostic["source"]["native_TRAIN_records_decoded"] == len(train)
            and original["TRAIN_atoms"] == atoms and atoms <= config.max_train_atoms
            and diagnostic["original_TRAIN_CSR"]["shape"] == [3*atoms, config.columns]
            and protocol["full_columns"] == config.columns
            and original["observed_support_columns"] == candidate["preprocessing"]["observed_support_columns"] == protocol["active_columns"],
            "Actual TRAIN CSR/population/support dimensions differ")
    preconditioning = candidate["preprocessing"]
    require(preconditioning["damp"] == 0 and preconditioning["warm_start_used"] is False
            and preconditioning["dense_gram_constructed"] is False and preconditioning["original_CSR_unchanged"] is True
            and preconditioning["scale"] == "sqrt(column_squared_norm/n_atoms + ridge)"
            and preconditioning["operator"] == "[A_active/(sqrt(n_atoms)*D); sqrt(ridge)/D]",
            "Prior accepted candidate was not the exact same-objective active/Jacobi method")
    for thread in (original, candidate):
        before, after = thread["threadpools_before"], thread["threadpools_restored"]
        require({r["filepath"]: r["num_threads"] for r in before} == {r["filepath"]: r["num_threads"] for r in after},
                "Prior solver thread restoration evidence differs")
        for key in ("threadpools_inside_before", "threadpools_inside_after"):
            blas = [r for r in thread[key] if r.get("user_api") == "blas"]
            require(blas and all(r["num_threads"] == 1 for r in blas), "Prior actual BLAS1 evidence missing")
    artifact = diagnostic["array_artifact"]
    require(artifact["saved"] is True and artifact["CSR_saved"] is False
            and artifact["binding"]["sha256"] == inputs["TRAIN_artifact"]["sha256"]
            and artifact["binding"]["bytes"] == inputs["TRAIN_artifact"]["bytes"], "Closed diagnostic binds a different TRAIN NPZ")
    arrays = checked_npz(inputs["TRAIN_artifact"], artifact["contents"], active_count=protocol["active_columns"], full_columns=config.columns)
    require(original["TRAIN_directed_edges"] <= config.max_directed_edges
            and (arrays["observed_support"] <= config.max_directed_edges).all()
            and sum(int(value) for value in arrays["observed_support"]) == original["TRAIN_directed_edges"],
            "Saved support count differs from actual TRAIN edges")
    coefficients, support = np.zeros(config.columns), np.zeros(config.columns, dtype=np.int64)
    active = arrays["active_columns"]
    coefficients[active] = arrays["candidate_coefficient"]  # ALREADY c. Never divide by jacobi_scale again.
    support[active] = arrays["observed_support"]
    receipts = [{"record_id": r["record_id"], "molecule_id": r["molecule_id"], "role": "TRAIN",
        "payload_sha256": r["payload_sha256"], "atoms": r["native_n_atoms"]} for r in train]
    require(len({r["record_id"] for r in receipts}) == len(train), "Duplicate closed TRAIN identity")
    receipt = {"schema": "model_v3_C2_coordinate_baseline_v2_fit_receipt_v1", "method": base.SOLVER,
        "fit_origin": FIT_ORIGIN, "fit_role": "TRAIN", "parameter_estimation_job_id": protocol["TRAIN_fit_job_id"],
        "current_job_TRAIN_geometry_reads": 0, "current_job_parameter_estimation_performed": False,
        "TRAIN_records": len(train), "TRAIN_atoms": atoms, "TRAIN_directed_edges": original["TRAIN_directed_edges"],
        "TRAIN_record_ids": sorted(r["record_id"] for r in receipts), "TRAIN_molecule_ids": sorted({r["molecule_id"] for r in receipts}),
        "TRAIN_membership_sha256": base.support_runtime.canonical(receipts),
        "source_request_raw_sha256": inputs["source_request"]["sha256"], "source_plan_raw_sha256": inputs["selection_plan"]["sha256"],
        "source_feature_resource_configuration_v1_sha256": base.support_runtime.canonical(asdict(config)),
        "actual_solver_configuration_v2": base.SOLVER, "augmented_operator_statistics": candidate["solver"],
        "original_coordinate_KKT_and_objective": candidate["original_coordinate_diagnostics"],
        "KKT_origin": "copied from bound prior TRAIN diagnostic; not recomputed", "KKT_acceptance_threshold_applied": False,
        "preprocessing": candidate["preprocessing"], "original_matrix": diagnostic["original_TRAIN_CSR"],
        "prior_TRAIN_artifact": inputs["TRAIN_artifact"], "prior_TRAIN_closure": inputs["TRAIN_closure"],
        "prior_TRAIN_diagnostic_result": inputs["TRAIN_diagnostic_result"],
        "v2_executed_source_sha256": base.executed_sources(), "artifact_runtime_source_sha256": executed_sources(),
        "target_units": "epsilon=y-x, Angstrom displacement", "normalization": "sum_squared_vector_error/TRAIN_atoms",
        "validation_used_for_fit_or_tuning": False, "dense_Gram_constructed": False,
        "original_v1_job_4520482_remains_FAILED": True, "prior_TRAIN_job_elapsed_seconds": verified_closure["source_job"]["elapsed_seconds"]}
    return AcceptedTrainArtifactLookup(core, config, coefficients, support, receipt)


def evaluate_only(core, model, source, plan, *, expected_records, check=lambda: None):
    require(source.native_reads == 0, "Fresh metadata-only source required; current job must not reread TRAIN geometry")
    metrics = core.evaluate_coordinate_lookup(model, source.records("PRETRAIN_VAL", plan), expected_records=expected_records, check=check)
    require(source.native_reads == expected_records, "Exactly the fixed VAL population, with zero TRAIN reads, required")
    return metrics


def restore_accepted_TRAIN_model(core, document):
    require(document.get("schema") == "model_v3_C2_coordinate_lookup_v2_prior_TRAIN_artifact"
            and document.get("fit_origin") == FIT_ORIGIN and document["current_job_TRAIN_geometry_reads"] == 0
            and document["artifact_runtime_source_sha256"] == executed_sources(), "Bound prior-TRAIN v2 model required")
    validated_base = base.restore_v2(core, {**document, "schema": "model_v3_C2_coordinate_lookup_v2"})
    require(validated_base.fit_receipt["fit_origin"] == FIT_ORIGIN
            and validated_base.fit_receipt["artifact_runtime_source_sha256"] == executed_sources(), "Artifact-origin receipt differs")
    return AcceptedTrainArtifactLookup(core, validated_base.config, validated_base.coefficients,
                                      validated_base.train_edge_counts, validated_base.fit_receipt)


class VALOnlyGuard(base.V2Guard):
    def __call__(self):
        # Reuse identical cap enforcement, suppressing its full-refit telemetry.
        previous = self.logged; self.logged = time.monotonic()-self.started
        try: super().__call__()
        finally: self.logged = previous
        elapsed = time.monotonic()-self.started
        if elapsed-self.logged >= 30:
            reads = 0 if self.source is None else self.source.native_reads
            print(json.dumps({"stage": self.stage, "elapsed_seconds": elapsed, "fit_origin": FIT_ORIGIN,
                "current_job_TRAIN_geometry_reads": 0, "current_job_PRETRAIN_VAL_geometry_reads": reads,
                "process_peak_RSS_bytes": self.peak_RSS_bytes, "output_bytes": self.output_bytes}), flush=True)
            self.logged = elapsed


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", required=True); parser.add_argument("--inputs-sha256", required=True)
    parser.add_argument("--expected-node", required=True); parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args(argv)
    base.support_runtime.cpu_admission(args.expected_node)
    inputs_ref = {"path": args.inputs, "sha256": args.inputs_sha256}
    inputs = base.support_runtime.bound_json(inputs_ref)
    require(inputs.get("schema") == "model_v3_C2_prior_TRAIN_artifact_v2_inputs_v1", "Bound artifact-origin v2 inputs required")
    protocol = adopted_artifact_protocol(inputs)
    require(protocol["TRAIN_fit_job_id"] == "4520559" and protocol["TRAIN_records"] == 8192
            and protocol["active_columns"] == 4116 and protocol["full_columns"] == 708050, "Explicit actual 559 adoption dimensions required")
    request = base.support_runtime.bound_json(inputs["source_request"]); plan = base.support_runtime.bound_json(inputs["selection_plan"])
    root = Path(inputs["source_repository"]).absolute(); output = args.output_root.absolute()
    require(not output.exists() and not output.resolve().is_relative_to(root.resolve())
            and not output.resolve().is_relative_to(Path(__file__).resolve().parent), "Fresh external VAL-only output required")
    census = base.support_runtime.fixed_monitor(inputs["runtime_monitor"])
    output.mkdir(parents=True); guard = VALOnlyGuard(output, census)
    source = run = None; before = executed_sources(); native_reads = 0
    try:
        sys.path.insert(0, str(root/"current"))
        from phychem_mfm.phase1 import v3_coordinate_lookup as core
        from phychem_mfm.phase1.v3_coordinate_lookup_source import ExistingSLookupSource
        require(Path(core.__file__).resolve() == (root/"current/phychem_mfm/phase1/v3_coordinate_lookup.py").resolve()
                and asdict(core.CoordinateLookupConfig()) == request["method"]
                and request["selection"]["train_records"] == 8192 and request["selection"]["validation_records"] == 1024,
                "Original source/features/record budget required")
        model = load_accepted_TRAIN_artifact(core, inputs, protocol)
        source = ExistingSLookupSource(request, check=guard); guard.source = source
        require(source.native_reads == 0 and source.evidence == plan["role_evidence"], "Metadata-only fresh source/role proof required")
        layout = base.support_runtime.configure_wandb_layout(output)
        import wandb
        run = wandb.init(project="phychem-model-v3", mode="offline", dir=str(output),
            name="C2_v2_prior_TRAIN_then_first_VAL_"+os.environ["SLURM_JOB_ID"], config={"method": base.SOLVER,
                "fit_origin": FIT_ORIGIN, "parameter_estimation_job_id": "4520559", "current_job_TRAIN_geometry_reads": 0,
                "source_request_sha256": inputs["source_request"]["sha256"], "selection_plan_sha256": inputs["selection_plan"]["sha256"],
                "public_artifact_protocol_commit": inputs["protocol_registration"]["commit"], "tracking_layout": layout})
        require(run is not None and not run.disabled, "Persistent offline SDK required")
        base.save_v2(output/"BASELINE_v2_ARTIFACT_INPUT_BINDING.json", {"inputs": base.support_runtime.binding(args.inputs),
            "fit_origin": FIT_ORIGIN, "protocol_registration": inputs["protocol_registration"], "executed_sources": before,
            "TRAIN_artifact": inputs["TRAIN_artifact"], "source_request": inputs["source_request"], "selection_plan": inputs["selection_plan"]})
        base.save_v2(output/"BASELINE_v2_ARTIFACT_FIT_RECEIPT.json", model.fit_receipt)
        run.log({"prior_TRAIN_fit/records": 8192, "prior_TRAIN_fit/atoms": model.fit_receipt["TRAIN_atoms"],
            "prior_TRAIN_fit/parameter_estimation_job_id": "4520559", "current_job/TRAIN_geometry_reads": 0}, step=0, commit=True)
        guard.stage = "BASELINE_v2_FIRST_NATIVE_PRETRAIN_VAL"
        metrics = evaluate_only(core, model, source, plan, expected_records=1024, check=guard)
        native_reads = source.native_reads
        require(native_reads == 1024, "Exactly the original 1024 VAL records required; no TRAIN geometry may be decoded")
        guard.finalizing = True; source.verify(); source.close(); source = None
        require(before == executed_sources(), "Artifact-v2 source drift during VAL")
        for key in ("source_request", "selection_plan", "TRAIN_diagnostic_result", "TRAIN_diagnostic_done",
                    "TRAIN_diagnostic_input_binding", "TRAIN_closure"): base.support_runtime.bound_json(inputs[key])
        base.save_v2(output/"BASELINE_v2_ARTIFACT_LOOKUP.json", model.document())
        run.log({"validation/"+key: value for key, value in metrics.items() if type(value) in (int, float)}, step=1, commit=True)
        result = {"schema": "model_v3_C2_prior_TRAIN_artifact_v2_result_v1", "status": "ANALYSIS_COMPLETE_NOT_MODEL_SELECTION_V2",
            "fit_origin": FIT_ORIGIN, "parameter_estimation_job_id": "4520559", "current_job_TRAIN_geometry_reads": 0,
            "current_job_PRETRAIN_VAL_geometry_reads": native_reads, "fit_receipt_v2": model.fit_receipt, "metrics": metrics,
            "wandb_run_id": run.id, "tracking_mode": "persistent_offline", "online_sync_claimed": False,
            "resource_observation": {"wall_seconds": time.monotonic()-guard.started, "process_peak_RSS_bytes": guard.peak_RSS_bytes}}
        run.finish(); run = None; guard()
        base.save_v2(output/"BASELINE_v2_ARTIFACT_RESULT.json", result)
        base.save_v2(output/"BASELINE_v2_ARTIFACT_COMPLETE.json", {"schema": "model_v3_C2_prior_TRAIN_artifact_v2_complete_v1",
            "status": result["status"], "fit_origin": FIT_ORIGIN, "result": base.support_runtime.binding(output/"BASELINE_v2_ARTIFACT_RESULT.json"),
            "lookup": base.support_runtime.binding(output/"BASELINE_v2_ARTIFACT_LOOKUP.json"), "inputs": base.support_runtime.binding(args.inputs),
            "parameter_estimation_job_id": "4520559", "current_job_TRAIN_geometry_reads": 0,
            "current_job_PRETRAIN_VAL_geometry_reads": native_reads, "model_selection_gate": False})
    except BaseException as exc:
        if run is not None: run.finish(exit_code=1)
        base.save_v2(output/"BASELINE_v2_ARTIFACT_FAILED.json", {"schema": "model_v3_C2_prior_TRAIN_artifact_v2_failure_v1",
            "exception_type": type(exc).__name__, "exception_chain": traceback.format_exc(), "stage": guard.stage,
            "fit_origin": FIT_ORIGIN, "current_job_TRAIN_geometry_reads": 0,
            "current_job_PRETRAIN_VAL_geometry_reads": native_reads if source is None else source.native_reads})
        raise
    finally:
        if source is not None: source.close()


if __name__ == "__main__": main()
