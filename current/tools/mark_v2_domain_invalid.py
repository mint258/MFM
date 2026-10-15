#!/usr/bin/env python3
"""Record the protocol-v3 disposition of principal-only v2 discovery runs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from phychem_mfm.discovery.registry import ExperimentRegistry


INVALID_STATUS = "HISTORICAL_INVALID_FOR_V3"
OLD_DOMAIN_PROTOCOL = "principal-only-train_molecule-only-validation-v2"


def parse_args():
    parser = argparse.ArgumentParser(
        "Mark discovery checkpoints whose training domain cannot be repaired by re-evaluation"
    )
    parser.add_argument("--registry", default="registry/discovery_registry.json")
    parser.add_argument("--apply", action="store_true", help="Persist changes; otherwise report a dry run")
    return parser.parse_args()


def main():
    args = parse_args()
    registry = ExperimentRegistry(Path(args.registry))
    experiment_ids = [
        experiment_id
        for experiment_id, record in registry.payload["experiments"].items()
        if not str(record.get("domain_protocol_version", "")).startswith("domain-matched-v3")
    ]
    checkpoint_shas = [
        sha
        for sha, record in registry.payload["checkpoints"].items()
        if record.get("experiment_id") in experiment_ids
    ]
    summary = {
        "action": "apply" if args.apply else "dry_run",
        "disposition": INVALID_STATUS,
        "reason": (
            "The v2 training pools contain principal structures only while validation contains "
            "molecule-domain structures only; domain-matched validation cannot repair training provenance."
        ),
        "experiments": len(experiment_ids),
        "checkpoints": len(checkpoint_shas),
        "experiment_ids": sorted(experiment_ids),
    }
    if args.apply:
        for experiment_id in experiment_ids:
            registry.update_experiment(experiment_id, {
                "domain_protocol_version": OLD_DOMAIN_PROTOCOL,
                "v3_validity": INVALID_STATUS,
                "scientific_conclusions_status": "SUPERSEDED_PENDING_V3",
                "downstream_protocol_version": "mean_pool_ridge_v2",
            })
        for sha in checkpoint_shas:
            registry.update_checkpoint_evaluation(sha, {
                "domain_protocol_version": OLD_DOMAIN_PROTOCOL,
                "target_adequacy_version": "v3-domain-provenance-audit",
                "optimization_status": "HISTORICAL_NOT_REASSESSED",
                "target_adequacy_status": "NOT_EVALUATED_INVALID_TRAIN_DOMAIN",
                "transfer_ready_status": False,
                "v3_validity": INVALID_STATUS,
                "downstream_protocol_version": "mean_pool_ridge_v2",
                "reason": summary["reason"],
            })
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
