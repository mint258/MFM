"""Check four completed standalone members and summarize an A/B/B/A series."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from a_execution_runtime import canonical_sha
from profile_s_baseline import digest, save


def summarize_abba(members, *, numeric_gate=None):
    if len(members) != 4:
        raise ValueError("Exactly four completed A/B/B/A members required")
    summaries = [item["summary"] for item in members]
    invariant = ("series_id", "code_sha", "prereg_sha", "gpu_uuid", "gpu_name", "seed", "input",
                 "smoke", "measured_updates", "warmup_updates", "candidate_options_sha256")
    config_invariant = ("model", "optimizer", "loss_policy", "loss_weights", "supervision", "schedule",
                        "reference_configuration", "a4_configuration", "original_shard_snapshot_prejob_sha256")
    def controls_signature(value):
        receipt = value.get("deterministic_controls")
        if receipt is None:
            return None
        semantic = {"requested": receipt["requested"], "actual": receipt["actual"],
            "preimport_binding_satisfied": not receipt["torch_imported_before_binding"],
            "cuda_uninitialized_before_apply": not receipt["cuda_initialized_before_apply"]}
        calculated = canonical_sha(semantic)
        if receipt.get("execution_sha256") != calculated:
            raise ValueError("Deterministic controls receipt hash differs from actual fields")
        return calculated
    def check_configuration(value, summary):
        calculated = canonical_sha({key: item for key, item in value.items() if key != "configuration_sha256"})
        if value.get("configuration_sha256") != calculated or summary.get("configuration_sha256") != calculated:
            raise ValueError("Configuration raw content does not match its run hash")
    for position, item in enumerate(members, 1):
        row = item["summary"]
        check_configuration(item["configuration"], row)
        if row["role"] != ("reference", "candidate", "candidate", "reference")[position - 1] or row["abba_position"] != position:
            raise ValueError("Actual member order must be A/B/B/A")
        if any(row[key] != summaries[0][key] for key in invariant):
            raise ValueError("A/B/B/A GPU/code/data/seed/options/window bindings differ")
        if any(item["configuration"][key] != members[0]["configuration"][key] for key in config_invariant):
            raise ValueError("A/B/B/A model/optimizer/loss/reference configuration differs")
        if item["configuration"].get("source_sha256") != members[0]["configuration"].get("source_sha256"):
            raise ValueError("Actual A/B/B/A repository source bytes differ")
        if controls_signature(item["configuration"]) != controls_signature(members[0]["configuration"]):
            raise ValueError("A/B/B/A deterministic controls differ")
        if (row["status"] != "STANDALONE_TIMING_COMPLETED" or item["run_status"]["status"] != row["status"]
                or item["run_status"].get("failure") is not None or item["run_status"].get("cleanup_errors")
                or not item["run_status"].get("stream_cleanup", {}).get("input_descriptors_closed")
                or item["supervisor"].get("status") != "COMPLETED" or item["supervisor"].get("exit_code") != 0
                or item["supervisor"].get("first_failure") is not None
                or item["supervisor"].get("gpu_uuid") != row["gpu_uuid"]
                or item["supervisor"].get("job_id") != item["configuration"].get("job_id")):
            raise ValueError("A/B/B/A child, input/SDK cleanup and supervisor must actually complete")
        if (not math.isfinite(row["elapsed_window_seconds"]) or row["elapsed_window_seconds"] <= 0
                or row["measured_base_records"] <= 0 or row["measured_native_atoms"] <= 0):
            raise ValueError("Finite positive measured windows/consumption required")
    equal_inputs = len({row["input_receipts_sha256"] for row in summaries}) == 1
    grouping = any(row["padding_exploration"] for row in summaries)
    risk = any(row["foreign_gpu_risk_observed"] for row in summaries)
    comparable = equal_inputs and not grouping and not risk
    reference, candidate = summaries[::3], summaries[1:3]
    def throughput(rows, field):
        return sum(row[field] for row in rows) / sum(row["elapsed_window_seconds"] for row in rows)
    base_a, base_b = throughput(reference, "measured_base_records"), throughput(candidate, "measured_base_records")
    atom_a, atom_b = throughput(reference, "measured_native_atoms"), throughput(candidate, "measured_native_atoms")
    numeric = False
    if numeric_gate is not None:
        summary, status = numeric_gate["summary"], numeric_gate["run_status"]
        check_configuration(numeric_gate["configuration"], summary)
        if (summary.get("full_A_numeric_acceptance") is not True or summary.get("status") != "PAIRED_GATES_PASS"
                or status.get("failure") is not None or status.get("cleanup_errors")
                or status.get("status") != "PAIRED_GATES_PASS"
                or summary.get("candidate_options_sha256") != summaries[0]["candidate_options_sha256"]
                or summary.get("code_sha") != summaries[0]["code_sha"]
                or summary.get("gpu_uuid") != summaries[0]["gpu_uuid"]):
            raise ValueError("Numeric gate does not bind this complete actual A candidate/GPU/code")
        for key, count_key, count in (("fixed_batch_gate", "batches", 20), ("trajectory_gate", "updates", 500)):
            gate = numeric_gate[key]
            if (gate.get("pass") is not True or gate.get(count_key) != count
                    or len(gate.get("results", ())) != count
                    or any(row.get("pass") is not True for row in gate["results"])):
                raise ValueError("Complete20batch/500update numerical gate evidence required")
        if numeric_gate["run_status"].get("stream_cleanup", {}).get("input_descriptors_closed") is not True:
            raise ValueError("Numeric gate input closure not verified")
        for key in config_invariant:
            if numeric_gate["configuration"][key] != members[0]["configuration"][key]:
                raise ValueError("Numeric gate model/loss/reference differs from speed series")
        if numeric_gate["configuration"]["data_version"] != members[0]["configuration"]["data_version"]:
            raise ValueError("Numeric gate and speed series do not bind the same native stream/capacity")
        if controls_signature(numeric_gate["configuration"]) != controls_signature(members[0]["configuration"]):
            raise ValueError("Numeric gate and speed series deterministic controls differ")
        numeric = True
    full_window = not summaries[0]["smoke"] and summaries[0]["input"] == "native_s" and summaries[0]["measured_updates"] == 20 and summaries[0]["warmup_updates"] == 2
    return {"schema": "model_v3_A_ABBA_speed_v1", "numeric_acceptance_granted_by_this_report": False,
        "has_matched_A_numeric_acceptance": numeric, "scientific_speed_comparison": comparable and full_window and numeric,
        "same_measured_inputs": equal_inputs, "padding_exploration": grouping, "foreign_gpu_risk_observed": risk,
        "base_records_per_second": {"reference_pooled": base_a, "candidate_pooled": base_b},
        "native_atoms_per_second": {"reference_pooled": atom_a, "candidate_pooled": atom_b},
        "speedup_candidate_over_reference": base_b / base_a if comparable else None,
        "native_atom_speedup": atom_b / atom_a if comparable else None,
        "raw_members": summaries, "window_includes_monitoring": True,
        "two_warmup_does_not_guarantee_recompilation_free_window": True}


def load_member(root, supervisor):
    paths = {"summary": root / "summary.json", "configuration": root / "configuration.json",
             "run_status": root / "run_status.json", "supervisor": supervisor}
    value = {key: json.loads(path.read_text()) for key, path in paths.items()}
    value["file_bindings"] = {key: {"path": str(path), "sha256": digest(path)} for key, path in paths.items()}
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", nargs=4, type=Path, required=True)
    parser.add_argument("--supervisors", nargs=4, type=Path, required=True)
    parser.add_argument("--numeric-gate", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Fresh compact speed report required")
    members = [load_member(root, sup) for root, sup in zip(args.runs, args.supervisors)]
    gate = None
    if args.numeric_gate is not None:
        gate = {name: json.loads((args.numeric_gate / (name + ".json")).read_text())
                for name in ("summary", "configuration", "run_status", "fixed_batch_gate", "trajectory_gate")}
    result = summarize_abba(members, numeric_gate=gate)
    result["member_file_bindings"] = [item["file_bindings"] for item in members]
    result["numeric_gate_file_bindings"] = None if gate is None else {name: {
        "path": str(args.numeric_gate / (name + ".json")), "sha256": digest(args.numeric_gate / (name + ".json"))}
        for name in gate}
    result["report_source_sha256"] = digest(Path(__file__))
    if len(json.dumps(result).encode()) > 16 * 1024**2:
        raise MemoryError("Compact ABBA report exceeds16MiB")
    save(args.output, result)


if __name__ == "__main__":
    main()
