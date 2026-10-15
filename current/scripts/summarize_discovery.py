#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser("Build a compact discovery result table from the registry")
    parser.add_argument("--registry", default="registry/discovery_registry.json")
    parser.add_argument("--output", default="registry/discovery_summary.json")
    args = parser.parse_args()
    registry = json.loads(Path(args.registry).read_text(encoding="utf-8"))
    rows = []
    for experiment_id, experiment in registry["experiments"].items():
        checkpoints = [
            item
            for item in registry["checkpoints"].values()
            if item.get("experiment_id") == experiment_id and item.get("checkpoint_state") in {"pass_end", "transfer_ready"}
        ]
        if not checkpoints:
            continue
        first = min(checkpoints, key=lambda item: int(item["checkpoint_pass"]))
        transfer = [item for item in checkpoints if item.get("transfer_ready_status")]
        selected = min(transfer, key=lambda item: int(item["checkpoint_pass"])) if transfer else max(
            checkpoints, key=lambda item: int(item["checkpoint_pass"])
        )
        summary_path = Path(str(experiment.get("result_paths", {}).get("summary", "")))
        summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.is_file() else {}
        validations = summary.get("validation_history", [])
        first_pass_points = [point for point in validations if int(point.get("val/pass_index", 0)) == 1]
        final_points = [
            point for point in validations if int(point.get("val/pass_index", 0)) == int(selected["checkpoint_pass"])
        ]
        rows.append(
            {
                "experiment_id": experiment_id,
                "recipe_hash": experiment["recipe_hash"],
                "pool_id": experiment.get("train_pool_id")
                or experiment.get("recipe", {}).get("dataset", {}).get("train_pool_id")
                or str(experiment_id).split("-", 1)[0].upper(),
                "train_pool_hash": experiment.get("train_pool_hash"),
                "validation_pool_hash": experiment.get("validation_pool_hash"),
                "unique_structure_count": experiment["unique_structure_count"],
                "unique_molecule_count": experiment["unique_molecule_count"],
                "task_route": experiment["task_route"],
                "descriptor_schedule": experiment["descriptor_schedule"]["name"],
                "first_pass_checkpoint": first["path"],
                "first_pass_val_total": first_pass_points[-1].get("val/loss/total") if first_pass_points else None,
                "selected_checkpoint": selected["path"],
                "selected_pass": selected["checkpoint_pass"],
                "selected_val_total": final_points[-1].get("val/loss/total") if final_points else None,
                "convergence_status": selected["convergence_status"],
                "transfer_ready": selected["transfer_ready_status"],
                "cumulative_structure_exposure": selected["cumulative_structure_exposure"],
                "atom_exposure": selected["atom_exposure"],
                "optimizer_update_step": selected["optimizer_update_step"],
                "wall_time_seconds": summary.get("wall_time_seconds"),
                "peak_memory_gib": summary.get("peak_memory_gib"),
                "mean_forward_seconds": summary.get("mean_forward_seconds"),
                "mean_backward_seconds": summary.get("mean_backward_seconds"),
            }
        )
    payload = {"format_version": 1, "rows": sorted(rows, key=lambda row: row["experiment_id"])}
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
