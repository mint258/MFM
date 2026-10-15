#!/usr/bin/env python3
"""Preserve but invalidate v3 runs trained before the data-quality gate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from phychem_mfm.discovery.registry import ExperimentRegistry


INVALID_STATUS = "HISTORICAL_INVALID_FOR_V3_DATA_QUALITY"


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", default="registry/discovery_registry.json")
    parser.add_argument("--apply", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args(); registry = ExperimentRegistry(Path(args.registry))
    experiment_ids = [
        experiment_id for experiment_id, record in registry.payload["experiments"].items()
        if (
            str(record.get("domain_protocol_version", "")).startswith("domain-matched-v3")
            or "DOMAIN_MATCHED_V3" in str(record.get("train_pool_id", ""))
        )
        and not str(record.get("data_quality_protocol_version", "")).startswith("data-quality-v3")
    ]
    checkpoint_shas = [
        sha for sha, record in registry.payload["checkpoints"].items()
        if record.get("experiment_id") in experiment_ids
    ]
    reason = (
        "The authoritative generator accepted any MOPAC output containing heat-of-formation and charge "
        "sections without a numerical plausibility gate. The pre-quality 400k train pool contains finite "
        "energy labels from -46940.01781 to 545243.93981 kcal/mol and the old validation pool contains "
        "93857.56947 kcal/mol; re-evaluation cannot repair contaminated training gradients."
    )
    summary = {
        "action": "apply" if args.apply else "dry_run", "disposition": INVALID_STATUS,
        "reason": reason, "experiments": len(experiment_ids), "checkpoints": len(checkpoint_shas),
        "experiment_ids": sorted(experiment_ids),
    }
    if args.apply:
        for experiment_id in experiment_ids:
            registry.update_experiment(experiment_id, {
                "data_quality_protocol_version": "pre-quality-unfiltered-v3",
                "v3_validity": INVALID_STATUS, "scientific_conclusions_status": "SUPERSEDED_PENDING_QUALITY_V3",
            })
        for sha in checkpoint_shas:
            registry.update_checkpoint_evaluation(sha, {
                "domain_protocol_version": "domain-matched-v3.1",
                "data_quality_protocol_version": "pre-quality-unfiltered-v3",
                "target_adequacy_version": "v3-data-quality-provenance-audit",
                "optimization_status": "HISTORICAL_NOT_REASSESSED_AFTER_DATA_QUALITY_AUDIT",
                "target_adequacy_status": "NOT_EVALUATED_INVALID_TRAIN_LABEL_QUALITY",
                "transfer_ready_status": False, "v3_validity": INVALID_STATUS, "reason": reason,
            })
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
