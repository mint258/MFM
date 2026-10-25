"""Evaluate a proposed feature order on three pinned traces; never apply it."""
import argparse
from pathlib import Path
import os
import socket
import time
import traceback

from . import common, features_generic_candidate_v1 as candidate, screen
from .common import ARTIFACT_ROOT, check_quota, dump_new, load, reference, require, verify
from workflows.data_v1_final.execution.cpu_analysis_v1 import runtime_v2 as cpu_runtime


def run(plan_path, intent_path):
    plan, intent = load(plan_path), load(intent_path)
    require(plan["schema"] == "pubchem_feature_candidate_evaluation_plan_v1" and plan["status"] == "READY" and
            plan["target_cids"] == [7, 52, 53] and plan["repair_applied"] is False and plan["pool_modified"] is False and
            plan["full_10k_replay_authorized"] is False and plan["peak_output_cap_bytes"] == 32 * 1024 ** 2,
            "Only isolated three-CID candidate evaluation is authorized")
    request = intent["request"]
    require(request["scope_key"] == "prefix_feature_three_cid" and
            request["estimated_peak_output_bytes"] == 64 * 1024 ** 2, "Read only the small pinned trace, never old pool/raw bodies")
    proof = cpu_runtime.root_guard(intent_path, plan_path, plan["peak_output_cap_bytes"])
    declared = {r["path"]: r for r in request["source_references"]}
    needed = [reference(plan_path), plan["diagnostic_receipt"], plan["diagnostic_traces"], plan["diagnostic_monitor_closure"],
              *plan["central_runtime_references"], *plan["code_sources"]]
    require(all(declared.get(r["path"]) == r and r["bytes"] <= 2 * 1024 ** 2 for r in needed), "Exact small evaluation inputs not bound by Root")
    for ref in needed:
        verify(ref)
    actual = {str(Path(p).absolute()) for p in (__file__, common.__file__, candidate.__file__, screen.__file__, cpu_runtime.__file__)}
    require(actual <= {r["path"] for r in plan["code_sources"]}, "Actual evaluation import chain not pinned")
    runtime_names = {Path(ref["path"]).name for ref in plan["central_runtime_references"]}
    require({"runtime.py", "launch.py", "runtime_v2.py", "launch_v2.py"} <= runtime_names,
            "Both frozen v1 and reviewed local-tmp v2 CPU runtime/launcher must be explicitly pinned")
    old = load(plan["diagnostic_receipt"]["path"])
    monitor = load(plan["diagnostic_monitor_closure"]["path"])
    require(old["schema"] == "pubchem_prefix_feature_stage_diagnostic_cpu_receipt_v1" and old["job_id"] == "4520484" and
            old["node"] == "compute-0-17" and old["status"] == "READ_ONLY_STAGE_TRACES_RECORDED_NO_REPAIR" and
            old["traces"] == plan["diagnostic_traces"] and reference(screen.__file__) == old["registered_screen_source"] and
            monitor["schema"] == "CPU_BOUNDED_TEST_MONITOR_CLOSURE_V1" and monitor["job_id"] == "4520484" and
            monitor["status"] == "COMPLETED_NO_MEMORY_DENIAL" and monitor["child_returncode"] == 0 and monitor["first_denial"] is None,
            "Exact completed diagnostic/unchanged screen evidence required")
    require(request["data_references"] in ([], [old["raw_source"]]),
            "Only an unused inherited reference to the same original raw is allowed; candidate input is pinned trace only")
    cases = load(plan["diagnostic_traces"]["path"])["cases"]
    require(len(cases) == 3 and sorted(row["cid"] for row in cases) == [7, 52, 53], "Exactly the three observed cases required")
    source_proof = candidate.source_scope_proof()
    installed = candidate.installed_murcko_source_proof()
    out = Path(plan["output_root"]).absolute()
    require(out.is_relative_to(ARTIFACT_ROOT / "diagnostics") and not out.exists(), "Use a new isolated candidate-evaluation directory")
    out.mkdir(parents=True)
    start = time.monotonic()
    try:
        feed = Path(plan["quota_feed"])
        require(feed.is_file() and feed.stat().st_uid == 1278 and not feed.is_symlink(), "Task-owned actual quota feed required")
        dump_new(out / "quota_start.json", load(feed))
        check_quota(out / "quota_start.json", request["estimated_peak_output_bytes"])
        results = []
        for case in sorted(cases, key=lambda row: row["cid"]):
            cpu_runtime.checkpoint()
            mol, flags = screen.chemical_flags(case["smiles"])
            require(flags == case["old_chemical_flags"] and not any(flags.values()), "Observed original chemical flags changed")
            row = {"cid": case["cid"], "ordinal": case["ordinal"], "source_smiles": case["smiles"],
                   "original_chemical_flags": flags, "repair_applied": False, "candidate_evaluated": True}
            try:
                row["legacy_output"] = screen.features(case["cid"], case["smiles"], case["ordinal"])
                row["legacy_status"] = "PASS"
            except Exception as exc:
                row.update(legacy_status="ERROR", legacy_error={"exception_type": type(exc).__name__, "message": str(exc),
                                                                "exact_traceback": traceback.format_exc()})
            cpu_runtime.checkpoint()
            row["fragment_order_comparisons"] = candidate.evaluate_fragment_orders(mol)
            cpu_runtime.checkpoint()
            try:
                value = candidate.features_candidate(case["cid"], case["smiles"], case["ordinal"])
                row.update(candidate_status="PASS", candidate_output=value,
                           actual_trace_field_comparison=candidate.compare_to_actual_trace(value, case))
                if row["legacy_status"] == "PASS":
                    row["legacy_pass_field_comparison"] = candidate.compare_pass_fields(row["legacy_output"], value)
            except Exception as exc:
                row.update(candidate_status="ERROR", candidate_error={"exception_type": type(exc).__name__, "message": str(exc),
                                                                       "exact_traceback": traceback.format_exc()})
            results.append(row)
        dump_new(out / "candidate_comparisons.json", {"cases": results})
        checks_pass = all(row["candidate_status"] == "PASS" and
                          row["actual_trace_field_comparison"]["all_observed_non_ring_fields_exactly_equal"] and
                          all(fragment["candidate"]["status"] == "PASS" for fragment in row["fragment_order_comparisons"]) for row in results)
        receipt = {"schema": "pubchem_feature_candidate_evaluation_receipt_v1", "status": "CANDIDATE_EVALUATED_NOT_APPLIED" if checks_pass else "CANDIDATE_HAS_UNRESOLVED_ERRORS_NOT_APPLIED",
                   "node": socket.gethostname().split(".")[0], "job_id": os.environ["SLURM_JOB_ID"], "plan": reference(plan_path),
                   "root_submission": reference(intent_path), "cpu_runtime_proof": proof,
                   "actual_trace_authority": plan["diagnostic_traces"], "comparisons": reference(out / "candidate_comparisons.json"),
                   "raw_body_opened_for_candidate_evaluation": False, "declared_unused_raw_references": request["data_references"],
                   "candidate_pass_cases": sum(row["candidate_status"] == "PASS" for row in results),
                   "observed_non_ring_field_drift_cases": sum(bool(row.get("actual_trace_field_comparison", {}).get("field_differences")) for row in results),
                   "source_scope_proof": source_proof, "installed_murcko_source_proof": installed,
                   "candidate_evaluated": True, "candidate_three_case_checks_passed": checks_pass,
                   "repair_applied": False, "feature_repair_applied": False,
                   "pool_modified": False, "full_10k_replay_performed": False, "training_or_UFF_or_pool_release_authorized": False,
                   "wall_seconds": time.monotonic() - start}
        cpu_runtime.checkpoint()
        dump_new(out / "receipt.json", receipt)
        require(sum(p.stat().st_size for p in out.rglob("*") if p.is_file()) <= plan["peak_output_cap_bytes"], "Candidate output cap exceeded")
        require(checks_pass, "Candidate remains unresolved or changed an observed non-ring field; artifacts retained, no repair applied")
    except Exception as exc:
        dump_new(out / "failure.json", {"status": "CANDIDATE_EVALUATION_FAILED_NOT_APPLIED", "type": type(exc).__name__, "error": str(exc)})
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--root-submit-intent", required=True, type=Path)
    args = parser.parse_args()
    run(args.plan, args.root_submit_intent)


if __name__ == "__main__":
    main()
