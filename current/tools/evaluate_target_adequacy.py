#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch

from phychem_mfm.discovery.convergence import ConvergenceGate
from phychem_mfm.discovery.identity import canonical_sha256
from phychem_mfm.discovery.manifests import build_discovery_data, load_manifest
from phychem_mfm.discovery.schedule import DataProgressSchedule
from phychem_mfm.evaluation.fidelity import TargetFidelityRegistry
from phychem_mfm.evaluation.target_adequacy import (
    ADEQUACY_VERSION,
    PretrainingTargetAdequacyEvaluator,
    load_standardizers,
    model_from_checkpoint_payload,
    write_adequacy_report,
)
from phychem_mfm.supervision import Objective, SupervisionConfig


def parse_args():
    parser = argparse.ArgumentParser("Evaluate protocol-v3 pretraining target fidelity in original target units")
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--validation-manifest", required=True)
    parser.add_argument("--active-objectives", required=True, help="S/P/D/SP/SD/SPD or comma-separated objective names")
    parser.add_argument("--threshold-registry", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--registry", default=None, help="Optional experiment registry updated with v3 evaluation fields")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--batch-size", type=int, default=96)
    parser.add_argument("--atom-budget-per-batch", type=int, default=12288)
    parser.add_argument("--num-workers", type=int, default=4)
    parser.add_argument("--max-batches", type=int, default=None)
    return parser.parse_args()


def parse_objectives(value: str):
    token = value.strip().upper()
    if token in {"S", "P", "D", "SP", "SD", "SPD"}:
        return SupervisionConfig.from_variant(token).objectives
    return frozenset(Objective(item.strip().lower()) for item in value.split(",") if item.strip())


def reassess_convergence(payload: dict, *, target_adequate: bool):
    """Apply the current Gate A implementation to immutable checkpoint history.

    Checkpoints retain the decision made by the source revision.  Re-evaluation
    must not silently inherit an obsolete gate after a protocol bug fix, so the
    original decision is retained separately and the recorded validation curve
    is assessed with the current implementation.
    """
    discovery = dict(payload.get("discovery", {}))
    original = dict(discovery.get("convergence", {}))
    history = list(discovery.get("validation_history", []))
    pass_count = int(discovery.get("pass_count", 0))
    exposure = int(discovery.get("cumulative_structure_exposure", payload.get("global_exposure_step", 0)))
    structures_per_pass = int(discovery.get("unique_structure_count", 0))
    schedule_values = dict(payload.get("schedule", {}))
    if structures_per_pass > 0 and schedule_values:
        schedule = DataProgressSchedule.from_mapping(schedule_values, structures_per_pass=structures_per_pass)
        schedule_mature = schedule.is_mature(exposure)
    else:
        schedule_mature = "descriptor_schedule_not_mature" not in original.get("reasons", [])
    warmup_complete = "warmup_not_complete" not in original.get("reasons", [])
    decision = ConvergenceGate().evaluate(
        history,
        pass_count=pass_count,
        schedule_mature=schedule_mature,
        warmup_complete=warmup_complete,
        target_adequate=target_adequate,
    )
    return original, decision


def main():
    args = parse_args()
    checkpoint = Path(args.checkpoint).resolve()
    payload = torch.load(checkpoint, map_location="cpu", weights_only=False)
    model = model_from_checkpoint_payload(payload)
    model.load_state_dict(payload["model_state"], strict=True)
    validation_manifest = load_manifest(args.validation_manifest)
    train_manifest = dict(payload.get("dataset_manifest", {}).get("train_pool", {}))
    if not train_manifest:
        raise RuntimeError("Checkpoint does not embed its training pool manifest; cannot reproduce training standardizers")
    standardizer_manifest = dict(
        payload.get("dataset_manifest", {}).get("standardizer_reference_pool", {})
    ) or train_manifest
    bundle = build_discovery_data(
        train_manifest,
        validation_manifest,
        batch_size=args.batch_size,
        atom_budget_per_batch=args.atom_budget_per_batch,
        num_workers=args.num_workers,
        seed=int(payload.get("seed", 0)),
        standardizer_reference_manifest=standardizer_manifest,
    )
    standardizers = load_standardizers(payload) or bundle.standardizers
    threshold_registry = TargetFidelityRegistry.load(args.threshold_registry)
    active = parse_objectives(args.active_objectives)
    evaluator = PretrainingTargetAdequacyEvaluator(
        model=model,
        active_objectives=active,
        standardizers=standardizers,
        threshold_registry=threshold_registry,
        device=torch.device(args.device),
        geometry_local_cutoff=float(payload.get("loss_weights", {}).get("cutoff", 2.0)),
    )
    adequacy = evaluator.evaluate_loaders(
        bundle.val_loader,
        element_loader=bundle.diagnostic_val_loader,
        max_batches=args.max_batches,
    )
    discovery = dict(payload.get("discovery", {}))
    original_convergence, convergence = reassess_convergence(
        payload, target_adequate=bool(adequacy["target_adequate"])
    )
    optimization_mature = bool(convergence.optimization_mature)
    report = {
        "report_type": "PretrainingTargetAdequacyReport",
        "target_adequacy_version": ADEQUACY_VERSION,
        "checkpoint": str(checkpoint),
        "checkpoint_sha256": __import__("hashlib").sha256(checkpoint.read_bytes()).hexdigest(),
        "recipe_hash": discovery.get("recipe_hash"),
        "source_commit": payload.get("source", {}).get("git_commit"),
        "validation_manifest": str(Path(args.validation_manifest).resolve()),
        "output_json": str(Path(args.output_json).resolve()),
        "output_csv": str(Path(args.output_csv).resolve()),
        "validation_manifest_hash": validation_manifest["pool_hash"],
        "data_quality_protocol_version": validation_manifest.get("data_quality_protocol_version", "unknown"),
        "data_quality_policy_hash": validation_manifest.get("data_quality_policy_hash"),
        "domain_composition": validation_manifest.get("domain_composition", {}),
        "task_definitions": sorted(item.value for item in active),
        "training_loss": payload.get("extra", {}).get("last_validation", {}),
        "optimization_status": convergence.status,
        "optimization_mature": optimization_mature,
        "optimization_reassessment": convergence.to_dict(),
        "checkpoint_original_convergence": original_convergence,
        "convergence_assessment_source": "current-gate-from-immutable-validation-history",
        **adequacy,
    }
    report["transfer_ready"] = bool(optimization_mature and report["target_adequate"])
    report["transfer_ready_status"] = "TRANSFER_READY" if report["transfer_ready"] else (
        "PLATEAU_BUT_TARGET_INADEQUATE" if optimization_mature else "NOT_OPTIMIZATION_MATURE"
    )
    report["report_hash"] = canonical_sha256(report)
    write_adequacy_report(report, args.output_json, args.output_csv)
    if args.registry:
        update_registry(Path(args.registry), report)
    print(json.dumps(report, indent=2, sort_keys=True))


def update_registry(path: Path, report: dict[str, object]) -> None:
    from phychem_mfm.discovery.registry import ExperimentRegistry

    registry = ExperimentRegistry(path)
    sha = str(report["checkpoint_sha256"])
    record = registry.payload.get("checkpoints", {}).get(sha)
    if record is None:
        raise KeyError(f"Checkpoint {sha} is not registered in {path}")
    registry.update_checkpoint_evaluation(sha, {
        "domain_protocol_version": "domain-matched-v3.1",
        "data_quality_protocol_version": report.get("data_quality_protocol_version"),
        "data_quality_policy_hash": report.get("data_quality_policy_hash"),
        "validation_manifest_hash": report["validation_manifest_hash"],
        "target_adequacy_version": report["target_adequacy_version"],
        "energy_original_unit_metrics": report.get("per_task_metrics", {}).get("energy"),
        "charge_original_unit_metrics": report.get("per_task_metrics", {}).get("charge"),
        "geometry_original_unit_metrics": report.get("per_task_metrics", {}).get("geometry"),
        "bond_metrics": report.get("per_task_metrics", {}).get("bond"),
        "descriptor_metrics": {
            key: report.get("per_task_metrics", {}).get(key)
            for key in ("graph_descriptor", "charge_descriptor", "element_descriptor")
        },
        "per_task_fidelity": report["per_task_fidelity"],
        "optimization_status": report["optimization_status"],
        "target_adequacy_status": report["target_adequacy_status"],
        "transfer_ready_status": report["transfer_ready"],
        "adequacy_report": str(Path(report.get("output_json", ""))) if report.get("output_json") else None,
    })


if __name__ == "__main__":
    main()
