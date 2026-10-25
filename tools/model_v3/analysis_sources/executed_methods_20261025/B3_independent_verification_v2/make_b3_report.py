"""Whitelist-only aggregate report for a historical B3 panel; no predictions/IDs."""
from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path

from verify_native_history import (PREREGISTRATION, TASKS, READOUTS, binding,
    bound_json, encoded, require)

MAX_REPORT_BYTES = 128 << 10
DATASETS = frozenset(("cyp_isoform", "expansionrx", "qm9"))


def validate_panel(result, guard, request, panel):
    require(result["status"] == guard["status"] == "COMPLETED" and guard["child_returncode"] == 0,
        "A complete real result and successful guard are required")
    require(result["reference_kind"] == request["reference_kind"] == "historical_sanity_only"
        and result["encoder_pair"]["reference_kind"] == "historical_sanity_only"
        and result["encoder_pair"]["H0_dimension"] == 384, "Report is restricted to historical B3 384")
    require(result["preregistration_sha"] == request["preregistration_sha"] == guard["preregistration_sha"] == PREREGISTRATION,
        "Actual published preregistration differs")
    require({task["task_id"] for task in panel["tasks"]} == TASKS and len(panel["tasks"]) == 9,
        "Frozen nine-task panel differs")
    require(panel["uncertainty"]["bootstrap_samples"] == 1000 and panel["uncertainty"]["confidence"] == .95
        and panel["uncertainty"]["paired"] is True
        and panel["uncertainty"]["same_draw_across_tasks_and_readouts_within_dataset"] is True,
        "Frozen paired bootstrap specification differs")
    require(panel["readouts"]["linear64_relu"]["batch_graphs"] == 32
        and panel["readouts"]["linear64_relu"]["epochs"] == 20, "Fixed readout recipe differs")
    pair = result["encoder_pair"]
    require(pair["architecture_sha256"] == request["architecture_sha256"] == result["architecture_sha256"]
        and pair["checkpoint"] == request["checkpoint"]
        and pair["original_configuration"] == request["model_configuration"], "Actual candidate architecture/checkpoint/configuration differs")
    require(pair["random_reference_seed"] == result["random_reference_initialization_seed"] == 20261025
        and pair["pretraining_seed"] == result["pretraining_seed"] == request["pretraining_seed"]
        and result["readout_seed"] == panel["readouts"]["linear64_relu"]["seed"], "Matched seeds differ")
    require(pair["historical_memory_implementation"]["candidate_and_random_use_identical_builder"] is True,
        "Candidate/random historical builders are not matched")
    caches = result["h0_caches"]
    require(set(caches) == {label+"/"+dataset for label in ("candidate", "reference") for dataset in DATASETS},
        "Expected six H0 caches")
    for dataset in DATASETS:
        candidate, reference = (caches[label+"/"+dataset] for label in ("candidate", "reference"))
        left, right = candidate["binding"], reference["binding"]
        for key in ("architecture_sha256", "membership_sha256", "geometry_sha256", "dimension",
                    "packing_budget_sha256", "packing_plan_sha256", "effective_runtime_sha256"):
            require(left[key] == right[key], "Candidate/random H0 binding mismatch: "+key)
        require(left["dimension"] == 384 and left["architecture_sha256"] == result["architecture_sha256"]
            and left["membership_sha256"] == result["membership_sha256"][dataset]
            and left["packing_plan_sha256"] == result["h0_packing_plan_sha256"][dataset]
            and left["packing_budget_sha256"] == result["h0_packing_budget_sha256"], "H0/result binding mismatch")
        require(left["encoder_sha256"] == pair["checkpoint_encoder_state_sha256"]
            and right["encoder_sha256"] == pair["random_encoder_state_sha256"]
            and left["encoder_sha256"] != right["encoder_sha256"], "Candidate/random states are not distinct and correctly bound")
        for label, item in (("candidate", candidate), ("reference", reference)):
            require(item["targets_cached"] is False and item["binding"]["effective_runtime_sha256"] == result["h0_effective_runtime_sha256"],
                "H0 cache contains targets or runtime drift")
            require(item["molecules"] > 0 and item["atoms"] >= item["molecules"], "Invalid H0 inventory counts")
        require(candidate["molecules"] == reference["molecules"] and candidate["atoms"] == reference["atoms"],
            "Candidate/random native H0 inventories differ")
    summaries = result["summaries"]
    require(set(summaries) == {"primary_18_cells", *READOUTS}, "Mandatory separate readout summaries are missing")
    all_cells = {task+"@"+readout for task in TASKS for readout in READOUTS}
    rows = []
    definitions = {task["task_id"]: task for task in panel["tasks"]}
    for name, summary in summaries.items():
        expected = all_cells if name == "primary_18_cells" else {task+"@"+name for task in TASKS}
        require(summary["complete"] is True and set(summary["tasks"]) == expected,
            "Incomplete task/readout cells")
        require(summary["architecture_sha256"] == result["architecture_sha256"]
            and summary["bootstrap_samples"] == summary["bootstrap_defined"] == 1000
            and summary["bootstrap_unit"] == "molecule"
            and summary["bootstrap_seed"] == panel["uncertainty"]["seed"], "Bootstrap summary contract differs")
        require(len(summary["bootstrap_ci"]) == 2 and all(math.isfinite(v) for v in summary["bootstrap_ci"])
            and summary["bootstrap_ci"][0] <= summary["bootstrap_ci"][1], "Invalid aggregate bootstrap interval")
        scores = []
        for cell, item in sorted(summary["tasks"].items()):
            require(all(type(item[key]) in (int, float) and math.isfinite(item[key])
                for key in ("error", "reference_error", "normalized_improvement")), "Invalid task errors")
            require(item["error"] >= 0 and item["reference_error"] > 0
                and item["bootstrap_defined"] == 1000, "Undefined task/reference/bootstrap result")
            score = (item["reference_error"]-item["error"])/item["reference_error"]
            require(math.isclose(score, item["normalized_improvement"], rel_tol=1e-12, abs_tol=1e-12), "Normalized improvement differs")
            scores.append(score)
            task, readout = cell.split("@")
            require(summaries[readout]["tasks"][cell] == item, "Separate readout and primary cells differ")
            if name == "primary_18_cells":
                require(len(item["bootstrap_ci"]) == 2 and all(math.isfinite(v) for v in item["bootstrap_ci"])
                    and item["bootstrap_ci"][0] <= item["bootstrap_ci"][1], "Invalid task bootstrap interval")
                for key in ("observed_labels", "observed_molecules"):
                    require(type(item[key]) is int and item[key] > 0, "Missing observed population counts")
                rows.append({"task_id": task, "readout": readout,
                    "error_metric": definitions[task]["error_metric"], "unit": definitions[task]["unit"],
                    "candidate_error": item["error"], "random_reference_error": item["reference_error"],
                    "normalized_improvement": score, "ci95_low": item["bootstrap_ci"][0],
                    "ci95_high": item["bootstrap_ci"][1], "bootstrap_samples": 1000,
                    "observed_labels": item["observed_labels"], "observed_molecules": item["observed_molecules"]})
        require(math.isclose(sum(scores)/len(scores), summary["mean_normalized_improvement"], abs_tol=1e-12),
            "Equal-weight summary mean differs")
    return rows


def verification_state(certificate, certificate_ref, refs, result):
    if certificate is None:
        return {"status": "PENDING", "independently_verified": False, "source_core_flag": result["wandb_history_independently_verified"]}
    require(certificate["schema"] == "model_v3_B3_native_history_verification_v2"
        and certificate["status"] == "VERIFIED" and certificate["wandb_history_independently_verified"] is True,
        "Independent verification certificate did not succeed")
    for name in ("result", "guard", "request"):
        require(certificate["inputs"][name] == refs[name], "Independent certificate is for another input: "+name)
    require(certificate["sdk_run_id"] == result["wandb_run_id"]
        and certificate["history_rows"] == result["journal_records"] and certificate["sdk_exit_code"] == 0
        and certificate["clean_eof"] is True, "Independent SDK identity/count/exit differs")
    return {"status": "VERIFIED", "independently_verified": True,
        "source_core_flag": result["wandb_history_independently_verified"],
        "certificate": certificate_ref, "native_records": certificate["native_records"],
        "history_rows": certificate["history_rows"]}


def write_csv(path, rows):
    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def run_summary(result, guard, request, request_ref, verified):
    """One row per run, in the existing repository checker's typed schema."""
    row = {"run_id": request["run_id"], "stage": "4", "config_sha256": request_ref["sha256"],
        "code_sha": result["code_sha"], "data_version": result["data_version"],
        "seed": result["pretraining_seed"], "gpu_model": result["gpu_model"],
        "elapsed_seconds": result["elapsed_seconds"], "status": result["status"],
        "preregistration_sha": result["preregistration_sha"], "gpu_uuid": result["gpu_uuid"],
        "dev_score": result["summaries"]["primary_18_cells"]["mean_normalized_improvement"],
        "metric__historical_sanity_only": 1, "metric__H0_dimension": 384,
        "metric__pretraining_seed_count": 1, "metric__bootstrap_samples": 1000,
        "metric__independent_sdk_verified": int(verified["independently_verified"]),
        "metric__torch_allocator_peak_bytes": result["gpu_peak_allocated_bytes"],
        "metric__inclusive_panel_wall_seconds": guard["inclusive_panel_wall_seconds"],
        "metric__inclusive_one_gpu_hour_target_met": int(guard["inclusive_one_GPU_hour_target_met"])}
    for name, summary in result["summaries"].items():
        for suffix, value in (("mean", summary["mean_normalized_improvement"]),
            ("ci95_low", summary["bootstrap_ci"][0]), ("ci95_high", summary["bootstrap_ci"][1]),
            ("cells", len(summary["tasks"]))):
            row["metric__"+name+"_"+suffix] = value
    return row


def make_markdown(result, guard, rows, verified):
    som_counts = ", ".join(task+": "+"/".join(str(n) for n in sorted({row["observed_molecules"]
        for row in rows if row["task_id"] == task})) for task in sorted(TASKS) if task.startswith("cyp."))
    lines = ["# Historical B3 TRAIN-only development panel", "",
        "This is a descriptive 384-dimensional historical sanity check. It does not select or validate the 512-dimensional model-v3 architecture.", "",
        f"Evaluation job {result['job_id']}; pretraining seed {result['pretraining_seed']}; matched random initialization seed {result['random_reference_initialization_seed']}; readout seed {result['readout_seed']}.",
        "Only the frozen TRAIN and TRAIN inner-validation panel was used. No final evaluation result is claimed. Seed SD is unavailable from this single pretraining seed.", "",
        "| Summary | Cells | Mean normalized improvement | Paired molecular bootstrap 95% CI |",
        "|---|---:|---:|---|" ]
    for name in ("primary_18_cells", "ridge", "linear64_relu"):
        summary = result["summaries"][name]
        lo, hi = summary["bootstrap_ci"]
        lines.append(f"| {name} | {len(summary['tasks'])} | {summary['mean_normalized_improvement']:.6f} | [{lo:.6f}, {hi:.6f}] |")
    lines += ["", "All means use equal task/readout weights. The 1,000 paired bootstrap resamples group native rows/atoms/isoforms by source molecule; the frozen implementation shares each dataset's draw across tasks and readouts. These intervals are read from the bound result, not recomputed from predictions by this report tool.", "",
        "| Task | Readout | Candidate error | Random error | Improvement | 95% CI | Molecules |",
        "|---|---|---:|---:|---:|---|---:|"]
    for row in rows:
        lines.append(f"| {row['task_id']} | {row['readout']} | {row['candidate_error']:.6g} | {row['random_reference_error']:.6g} | {row['normalized_improvement']:.6f} | [{row['ci95_low']:.6f}, {row['ci95_high']:.6f}] | {row['observed_molecules']} |")
    negative = [row for row in rows if row["normalized_improvement"] < 0]
    lines += ["", "Negative cells: "+(", ".join(row["task_id"]+"@"+row["readout"] for row in negative) or "none")+". Both readout means and all cells remain visible; no readout is selected after seeing results.", "",
        "Regression errors retain source units (Expansion source-label scale, QM9 energy/orbitals Ha, alpha bohr^3). SoM reports 1 minus native hit@1. Observed SoM inner-validation molecule groups: "+som_counts+". These small populations limit confidence-interval stability and generalization; atom counts are not independent bootstrap sample counts.", "",
        f"Core elapsed: {result['elapsed_seconds']:.3f}s. Guard wall through SDK finish/cleanup: {guard['inclusive_panel_wall_seconds']:.3f}s. Guard inclusive one-GPU-hour target: {guard['inclusive_one_GPU_hour_target_met']}. This is a measured B3+matching-random panel run, not a speed claim for model-v3 512 or another checkpoint.",
        f"Torch allocated-memory high-water counter: {result['gpu_peak_allocated_bytes']} bytes. Its scope is the evaluator process's PyTorch allocator since its last counter reset; it is not device-global, driver, all-process, or guaranteed H0-phase memory. The report does not infer a whole-run device-memory peak or 85% capacity validation from it.",
        f"Independent native SDK verification: {verified['status']}. The original core flag is still {result['wandb_history_independently_verified']}; originals are preserved. An independent certificate, when present, is separate evidence.", "",
        "This report exports only aggregate errors, counts, intervals and run/source identities. It reads no downstream source store, final targets, member-ID list, cached H0 tensor or predictions.", "",
        f"Actual code: `{result['code_sha']}`. Published panel/rules preregistration: `{result['preregistration_sha']}`.",
        ""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("result", "guard", "request"):
        parser.add_argument("--"+name, type=Path, required=True)
        parser.add_argument("--"+name+"-sha256", required=True)
    parser.add_argument("--verification", type=Path)
    parser.add_argument("--verification-sha256")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    refs, values = {}, {}
    for name in ("result", "guard", "request"):
        values[name], refs[name] = bound_json(getattr(args, name), getattr(args, name+"_sha256"))
    result, guard, request = (values[name] for name in ("result", "guard", "request"))
    require(guard["result"] == refs["result"] and result["request_sha256"] == guard["request_sha256"] == refs["request"]["sha256"],
        "Raw-byte result/request/guard identities differ")
    for key in ("code_sha", "job_id", "gpu_uuid"):
        require(result[key] == guard[key], "Core/guard identity mismatch")
    panel, refs["panel"] = bound_json(request["panel"]["path"], request["panel"]["sha256"])
    require(result["panel_sha256"] == refs["panel"]["sha256"], "Bound frozen panel differs")
    rows = validate_panel(result, guard, request, panel)
    require(bool(args.verification) == bool(args.verification_sha256), "Certificate path and SHA must be provided together")
    certificate = certificate_ref = None
    if args.verification:
        certificate, certificate_ref = bound_json(args.verification, args.verification_sha256)
    verified = verification_state(certificate, certificate_ref, refs, result)
    output = args.output.absolute()
    require(not output.exists() and ".." not in output.parts, "Fresh external report output required")
    require(output.is_relative_to(Path(__file__).absolute().parent), "Keep reports in this new model-owned verification directory")
    for ancestor in output.parents:
        require(not ancestor.is_symlink(), "Report output ancestors must be physical")
    require(not output.is_relative_to(Path(refs["result"]["path"]).parent), "Report must not write into evaluation originals")
    output.mkdir(parents=True, exist_ok=False)
    write_csv(output / "run_summary.csv", [run_summary(result, guard, request, refs["request"], verified)])
    separate = [{"summary": name, "cells": len(item["tasks"]),
        "mean_normalized_improvement": item["mean_normalized_improvement"],
        "ci95_low": item["bootstrap_ci"][0], "ci95_high": item["bootstrap_ci"][1],
        "bootstrap_samples": item["bootstrap_samples"]} for name, item in sorted(result["summaries"].items())]
    (output / "aggregate_details.json").write_bytes(encoded({"schema": "model_v3_B3_aggregate_details_v1",
        "summaries": separate, "task_readout_rows": rows}))
    (output / "B3_REPORT.md").write_text(make_markdown(result, guard, rows, verified), encoding="utf-8")
    report = {"schema": "model_v3_B3_aggregate_report_v1", "reference_kind": "historical_sanity_only",
        "H0_dimension": 384, "inputs": refs, "verification": verified,
        "implementation": binding(__file__, 2 << 20), "member_ids_or_predictions_exported": False,
        "seed_SD": None, "seed_SD_reason": "only one pretraining seed",
        "gpu_peak_allocated_scope": "current evaluator process torch allocator high-water since last reset; not device-global",
        "outputs": [binding(path, MAX_REPORT_BYTES) for path in sorted(output.iterdir())]}
    (output / "report_manifest.json").write_bytes(encoded(report))
    require(sum(path.stat().st_size for path in output.iterdir()) <= MAX_REPORT_BYTES, "Compact report byte budget exhausted")
    for ref in refs.values():
        require(binding(ref["path"]) == ref, "Read-only report input changed")
    if certificate_ref:
        require(binding(certificate_ref["path"]) == certificate_ref, "Read-only certificate changed")
    print("Historical B3 aggregate report written to "+str(output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
