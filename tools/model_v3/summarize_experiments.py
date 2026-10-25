#!/usr/bin/env python3
"""Publish small typed experiment summaries; never copy sample-level targets."""
from __future__ import annotations

import argparse
import csv
import importlib.util
import io
import json
from pathlib import Path

ROOT = Path(__file__).absolute().parents[2]


def evaluation_row(request, result, *, request_sha256):
    if result["request_sha256"] != request_sha256:
        raise ValueError("Result does not match the root-bound evaluation request")
    if any(result[key] != request[key] for key in ('code_sha', 'preregistration_sha', 'data_version')):
        raise ValueError("Result scientific provenance differs from the evaluation request")
    row = {"run_id": result["wandb_run_id"], "stage": "4",
           "config_sha256": result["request_sha256"], "code_sha": result["code_sha"],
           "data_version": result["data_version"], "seed": request["pretraining_seed"],
           "gpu_model": result["gpu_model"], "gpu_uuid": result["gpu_uuid"],
           "elapsed_seconds": result["elapsed_seconds"], "status": result["status"],
           "preregistration_sha": result["preregistration_sha"],
           "dev_score": result["summaries"]["primary_18_cells"]["mean_normalized_improvement"],
           "peak_memory_bytes": result["gpu_peak_allocated_bytes"]}
    for method in ("ridge", "linear64_relu"):
        summary = result["summaries"][method]
        row["metric__"+method+"_mean"] = summary["mean_normalized_improvement"]
        for task, value in summary["tasks"].items():
            name = task.replace(".", "_").replace("@", "_")
            for metric in ("error", "reference_error", "normalized_improvement"):
                row["metric__"+name+"_"+metric] = value[metric]
    return row


def summary_bytes(rows, *, repository_root=ROOT):
    spec = importlib.util.spec_from_file_location("model_v3_summary_checker", Path(repository_root) / "tools/check_repository.py")
    checker = importlib.util.module_from_spec(spec); spec.loader.exec_module(checker)
    rows = tuple(rows)
    if not rows:
        raise ValueError("No actual run summaries supplied")
    fields = list(checker.MODEL_RESULT_REQUIRED)
    fields += sorted({key for row in rows for key in row} - set(fields))
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for row in sorted(rows, key=lambda row: row["run_id"]):
        writer.writerow({key: "" if value is None else value for key, value in row.items()})
    raw = output.getvalue().encode("utf-8")
    if not checker.model_summary_csv("docs/model_v3/results/runs.csv", raw):
        raise ValueError("Only the repository's typed one-row-per-run summary schema is accepted")
    return raw


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=Path, required=True,
                        help="JSON list of already aggregated run dictionaries, never raw sample rows")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    relative = args.output.absolute().relative_to(ROOT)
    if relative.parent.as_posix() != "docs/model_v3/results" or relative.suffix != ".csv":
        raise ValueError("Publish only the explicitly allowed model-summary directory")
    raw = summary_bytes(json.loads(args.rows.read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("xb") as stream:
        stream.write(raw)
    print(json.dumps({"status": "TYPED_SUMMARY_WRITTEN", "output": str(args.output), "bytes": len(raw)}))


if __name__ == "__main__":
    main()
