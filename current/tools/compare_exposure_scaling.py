#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser("Compare v3 target fidelity, exposure, validation, transfer, and compute")
    parser.add_argument("--registry", default="registry/discovery_registry.json")
    parser.add_argument("--adequacy-reports", nargs="*", default=[])
    parser.add_argument("--output-dir", default="artifacts/v3/exposure_scaling")
    parser.add_argument("--include-historical-invalid", action="store_true")
    parser.add_argument("--include-partial", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    registry = json.loads(Path(args.registry).read_text(encoding="utf-8"))
    reports = {}
    for path in args.adequacy_reports:
        report = json.loads(Path(path).read_text(encoding="utf-8"))
        reports[str(report.get("checkpoint_sha256"))] = report
    rows = []
    for sha, checkpoint in registry.get("checkpoints", {}).items():
        experiment = registry.get("experiments", {}).get(checkpoint.get("experiment_id"), {})
        if not args.include_partial and checkpoint.get("checkpoint_state") == "partial":
            continue
        invalid = str(checkpoint.get("v3_validity", "")).startswith("HISTORICAL_INVALID_FOR_V3") or str(experiment.get("v3_validity", "")).startswith("HISTORICAL_INVALID_FOR_V3")
        if invalid and not args.include_historical_invalid:
            continue
        report = reports.get(sha)
        if report is None:
            evaluations = checkpoint.get("evaluations", {})
            v3 = [value for key, value in evaluations.items() if str(key).startswith("pretraining-target-adequacy-v3")]
            report = v3[-1] if v3 else {}
        base = {
            "checkpoint_sha256": sha,
            "experiment_id": checkpoint.get("experiment_id"),
            "architecture": experiment.get("task_route"),
            "descriptor_schedule": experiment.get("descriptor_schedule", {}).get("name"),
            "unique_structures": checkpoint.get("unique_structure_count", experiment.get("unique_structure_count")),
            "unique_molecules": checkpoint.get("unique_molecule_count", experiment.get("unique_molecule_count")),
            "total_exposure": checkpoint.get("cumulative_structure_exposure"),
            "wall_time_seconds": experiment.get("wall_time_seconds"),
            "validation_loss": _validation_loss_at_exposure(experiment, checkpoint),
            "optimization_status": checkpoint.get("optimization_status", checkpoint.get("convergence_status")),
            "target_adequate": report.get("target_adequate", checkpoint.get("target_adequacy_status") == "ADEQUATE"),
            "transfer_ready": report.get("transfer_ready", checkpoint.get("transfer_ready_status")),
        }
        metrics = report.get("per_task_metrics", {})
        base.update({
            "energy_mae_kcal_mol": metrics.get("energy", {}).get("mae"),
            "charge_mae_e": metrics.get("charge", {}).get("mae"),
            "geometry_local_pair_mae_angstrom": metrics.get("geometry", {}).get("local_pair_mae"),
            "element_macro_f1": metrics.get("element", {}).get("macro_f1"),
            "bond_existence_f1": metrics.get("bond", {}).get("existence_f1"),
            "bond_order_macro_f1": metrics.get("bond", {}).get("order_macro_f1"),
            "graph_descriptor_mean_normalized_mae": metrics.get("graph_descriptor", {}).get("mean_normalized_mae"),
        })
        downstream = experiment.get("downstream_results", {})
        for dataset, result in downstream.items():
            if isinstance(result, dict):
                score = result.get("score", result.get("rmse", result.get("mae")))
                base[f"downstream_{dataset}"] = score
        rows.append(base)

    rows.sort(key=_row_order)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "exposure_scaling.json").write_text(json.dumps(rows, indent=2, sort_keys=True), encoding="utf-8")
    columns = sorted({key for row in rows for key in row})
    with (output_dir / "exposure_scaling.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader(); writer.writerows(rows)
    make_plots(rows, output_dir)
    print(json.dumps({"rows": len(rows), "output_dir": str(output_dir.resolve())}, indent=2))


def _validation_loss_at_exposure(experiment, checkpoint):
    history = experiment.get("validation_history", [])
    if not history:
        summary_path = experiment.get("result_paths", {}).get("summary")
        if summary_path and Path(str(summary_path)).is_file():
            history = json.loads(Path(str(summary_path)).read_text(encoding="utf-8")).get("validation_history", [])
    if not history:
        return None
    checkpoint_exposure = checkpoint.get("checkpoint_exposure", checkpoint.get("cumulative_structure_exposure"))
    if checkpoint_exposure is not None:
        eligible = [
            point for point in history
            if point.get("val/cumulative_structure_exposure") is not None
            and int(point["val/cumulative_structure_exposure"]) <= int(checkpoint_exposure)
        ]
        if eligible:
            history = eligible
    return history[-1].get("val/loss/selection", history[-1].get("val/loss/total"))


def make_plots(rows, output_dir: Path):
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        return
    specs = [
        ("unique_structures", "energy_mae_kcal_mol", "target_fidelity_vs_unique_data"),
        ("total_exposure", "energy_mae_kcal_mol", "target_fidelity_vs_total_exposure"),
        ("total_exposure", "validation_loss", "validation_loss_vs_exposure"),
    ]
    downstream_keys = sorted({key for row in rows for key in row if key.startswith("downstream_")})
    if downstream_keys:
        specs.extend([
            ("unique_structures", downstream_keys[0], "downstream_transfer_vs_unique_data"),
            ("total_exposure", downstream_keys[0], "downstream_transfer_vs_training_exposure"),
        ])
    for x_key, y_key, name in specs:
        points = [(row.get(x_key), row.get(y_key)) for row in rows]
        points = [(float(x), float(y)) for x, y in points if _finite(x) and _finite(y)]
        if not points:
            continue
        points.sort()
        figure, axis = plt.subplots(figsize=(6, 4))
        axis.plot([x for x, _ in points], [y for _, y in points], marker="o")
        axis.set_xlabel(x_key); axis.set_ylabel(y_key); axis.grid(alpha=0.25)
        figure.tight_layout(); figure.savefig(output_dir / f"{name}.png", dpi=180); plt.close(figure)


def _finite(value):
    try:
        return value is not None and math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _row_order(row):
    def sortable(value):
        return float(value) if _finite(value) else math.inf

    return (
        sortable(row.get("unique_structures")),
        sortable(row.get("total_exposure")),
        str(row.get("architecture") or ""),
        str(row.get("checkpoint_sha256") or ""),
    )


if __name__ == "__main__":
    main()
