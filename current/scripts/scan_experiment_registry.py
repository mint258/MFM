#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import torch

from phychem_mfm.discovery.registry import ExperimentRegistry


REQUIRED_DISCOVERY_FIELDS = {
    "recipe_hash",
    "train_pool_hash",
    "validation_pool_hash",
    "unique_structure_count",
    "unique_molecule_count",
    "pass_count",
    "cumulative_structure_exposure",
    "atom_exposure",
}
CHECKPOINT_SUFFIXES = {".pt", ".pth", ".ckpt", ".model"}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def classify_checkpoint(payload: dict) -> tuple[str, list[str]]:
    discovery = payload.get("discovery")
    if isinstance(discovery, dict) and REQUIRED_DISCOVERY_FIELDS.issubset(discovery):
        state = str(payload.get("checkpoint_type", ""))
        if state in {"transfer_ready", "pass_end", "partial"}:
            return "EXACT_REUSABLE", []
    architecture = str(payload.get("architecture_type", ""))
    model_state = payload.get("model_state", payload)
    keys = list(model_state) if isinstance(model_state, dict) else []
    if architecture == "shared_multitask" or any(key.startswith("backbone.") for key in keys):
        missing = sorted(REQUIRED_DISCOVERY_FIELDS.difference(discovery or {}))
        return "HISTORICAL_COMPARABLE", [f"missing_discovery_field:{field}" for field in missing]
    return "INCOMPATIBLE", ["unrecognized_architecture_or_state_schema"]


def discover_paths(roots: list[str]) -> list[Path]:
    result: set[Path] = set()
    for raw in roots:
        path = Path(raw).resolve()
        if path.is_file() and path.suffix in CHECKPOINT_SUFFIXES:
            result.add(path)
        elif path.is_dir():
            result.update(item for item in path.rglob("*") if item.is_file() and item.suffix in CHECKPOINT_SUFFIXES)
    return sorted(result)


def main():
    parser = argparse.ArgumentParser("Scan current and historical checkpoints into the discovery registry")
    parser.add_argument("--registry", default="registry/discovery_registry.json")
    parser.add_argument("roots", nargs="+")
    args = parser.parse_args()
    registry = ExperimentRegistry(args.registry)
    records = []
    for path in discover_paths(args.roots):
        record = {
            "artifact_id": file_sha256(path),
            "path": str(path),
            "size_bytes": path.stat().st_size,
        }
        try:
            payload = torch.load(path, map_location="cpu", weights_only=False)
            if not isinstance(payload, dict):
                raise TypeError(f"checkpoint root is {type(payload).__name__}, expected dict")
            classification, reasons = classify_checkpoint(payload)
            record.update(
                {
                    "classification": classification,
                    "classification_reasons": reasons,
                    "architecture_type": payload.get("architecture_type"),
                    "task_route": payload.get("task_route"),
                    "checkpoint_type": payload.get("checkpoint_type"),
                    "global_exposure_step": payload.get("global_exposure_step", payload.get("global_step")),
                    "optimizer_update_step": payload.get("optimizer_update_step"),
                    "source": payload.get("source"),
                    "discovery": payload.get("discovery"),
                }
            )
        except Exception as exc:
            record.update(
                {
                    "classification": "INCOMPATIBLE",
                    "classification_reasons": [f"load_failed:{type(exc).__name__}:{exc}"],
                }
            )
        registry.register_historical(record)
        records.append(record)
        print(f"{record['classification']:23s} {path}")
    counts = {
        label: sum(item["classification"] == label for item in records)
        for label in ("EXACT_REUSABLE", "HISTORICAL_COMPARABLE", "INCOMPATIBLE")
    }
    report = {"scanned": len(records), "classification_counts": counts, "records": records}
    report_path = Path(args.registry).resolve().with_name("historical_scan_report.json")
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"report": str(report_path), **counts}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
