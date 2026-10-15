#!/usr/bin/env python3
"""Fit full retained-train statistics/baselines in a bounded CPU Slurm job.

Preparation emits NOT_FROZEN artifacts. It never repairs a split, selects a
training scope, reads validation/final-test data, freezes a protocol or trains
a model. Actual retained manifests/configuration must be decided beforehand.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import signal
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import torch

from phychem_mfm.config import load_experiment_config
from phychem_mfm.phase1.data import StrictManifestDataset
from phychem_mfm.phase1.fitted_controls import (
    PREPARATION_SCHEMA, PreparationBudget, PreparationBudgetExceeded,
    cpu_slurm_environment, fit_full_train_controls, validate_output_directory,
    validate_preparation_config, verify_cpu_slurm_job,
)
from phychem_mfm.phase1.formal_runtime import file_sha256
from phychem_mfm.training.checkpoint import source_provenance


FAILURE_EVIDENCE_RESERVE = 2048


@contextmanager
def wall_alarm(seconds):
    if sys.platform != "linux":
        raise RuntimeError("Real preparation wall alarm requires Linux")
    previous_handler = signal.getsignal(signal.SIGALRM)
    previous_timer = signal.getitimer(signal.ITIMER_REAL)
    if previous_timer != (0., 0.):
        raise RuntimeError("Refusing to replace an existing process wall timer")
    def exceeded(signum, frame):
        raise PreparationBudgetExceeded("CPU preparation internal wall alarm expired")
    signal.signal(signal.SIGALRM, exceeded)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)


def _encode(value):
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def _owned_files(directory):
    result = {}
    for path in Path(directory).rglob("*"):
        if path.is_symlink():
            raise ValueError("Preparation output contains an unexpected symbolic link")
        if path.is_file():
            result[path.relative_to(directory).as_posix()] = path.stat().st_size
    return result


def _encoded_with_total(value, other_bytes, *, compact=False):
    value["output_bytes"] = other_bytes
    for _ in range(4):
        encoded = ((json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n").encode("utf-8")
                   if compact else _encode(value))
        total = other_bytes + len(encoded)
        if value["output_bytes"] == total:
            return encoded
        value["output_bytes"] = total
    raise RuntimeError("Output byte accounting did not stabilize")


def _summary_write(path, value, *, max_output_bytes):
    files = _owned_files(path.parent)
    before = sum(files.values())
    # Atomic replacement briefly retains both old summary and pending summary.
    encoded = _encoded_with_total(value, before - files.get(path.name, 0))
    if len(encoded) > 1024 * 1024 or before + len(encoded) + FAILURE_EVIDENCE_RESERVE > max_output_bytes:
        raise PreparationBudgetExceeded("Preparation summary/atomic replacement exceeds total output allowance")
    pending = path.with_suffix(".json.pending")
    with pending.open("xb") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
    pending.replace(path)


def _failure_summary_write(output, summary, *, max_output_bytes):
    # Never discard a pending payload or an earlier summary's unique bindings.
    # Renaming preserves all bytes while making the canonical status truthful.
    path = output / "summary.json"
    if path.exists():
        previous = output / "summary.before_failure.json"
        if previous.exists():
            raise FileExistsError("Refusing to overwrite previous failure evidence")
        path.replace(previous)
    files = _owned_files(output)
    resources = summary.get("resources", {})
    inputs = summary.get("inputs", {})
    original_error = str(summary.get("error", ""))
    compact = {"schema_version": PREPARATION_SCHEMA, "state": "NOT_FROZEN", "status": summary["status"],
               "complete": False, "formal_eligible": False, "error_type": summary.get("error_type"),
               "error": original_error[:80], "error_truncated": len(original_error) > 80,
               "error_sha256": hashlib.sha256(original_error.encode("utf-8")).hexdigest(),
               "resources": {key: resources.get(key) for key in ("elapsed_seconds", "peak_rss_mib", "last_stage", "last_logical_index",
                                                                "max_wall_seconds", "max_memory_mib", "max_output_bytes")},
               "input_bindings": {"source_sha256": inputs.get("source", {}).get("source_sha256"),
                                  "train_manifest_sha256": inputs.get("train_manifest", {}).get("sha256"),
                                  "train_pool_hash": inputs.get("train_manifest", {}).get("pool_hash"),
                                  "train_view_hash": inputs.get("train_manifest", {}).get("view_hash"),
                                  "config_sha256": inputs.get("config", {}).get("sha256")},
               "retained_files": files}
    encoded = _encoded_with_total(compact, sum(files.values()), compact=True)
    if len(encoded) > FAILURE_EVIDENCE_RESERVE or sum(files.values()) + len(encoded) > max_output_bytes:
        raise PreparationBudgetExceeded("Essential failure evidence cannot fit; original error remains in process output")
    with path.open("xb") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
    summary["output_bytes"] = compact["output_bytes"]


def _sources(train):
    result = {}
    for segment in train.manifest["segments"]:
        path = (train.root / segment["shard"]).resolve()
        if str(path) in result:
            continue
        # Directory LMDB payload lives in data.mdb. Observations are explicitly
        # size/mtime bindings, not a new claim of a whole-LMDB content digest.
        payload = path / "data.mdb" if path.is_dir() else path
        stat = payload.stat()
        result[str(path)] = {"payload": str(payload), "size": stat.st_size, "mtime_ns": stat.st_mtime_ns}
    return result


def _allocated_memory_mib(env, allocation):
    per_node = str(env.get("SLURM_MEM_PER_NODE", ""))
    per_cpu = str(env.get("SLURM_MEM_PER_CPU", ""))
    if per_node.isdigit() and int(per_node) > 0:
        return int(per_node)
    if per_cpu.isdigit() and int(per_cpu) > 0:
        return int(per_cpu) * allocation["cpus_per_task"]
    raise RuntimeError("CPU preparation requires an explicit finite Slurm memory allocation")


def run_preparation(args):
    """Run the guarded CLI path; return summary and a truthful exit code."""
    output, budget, published = None, None, []
    summary = {"schema_version": PREPARATION_SCHEMA, "state": "NOT_FROZEN", "status": "FAILED",
               "complete": False, "formal_eligible": False,
               "purpose": "fit statistics and baselines on all explicitly retained train records",
               "split_or_lmdb_mutation": False, "validation_or_downstream_labels_read": False,
               "paired_init_or_architecture_artifacts_prepared": False}
    try:
        allocation = cpu_slurm_environment()
        budget = PreparationBudget(max_wall_seconds=args.max_wall_seconds, max_memory_mib=args.max_memory_mib,
                                   max_output_bytes=args.max_output_bytes)
        allocated_memory = _allocated_memory_mib(os.environ, allocation)
        live_allocation = verify_cpu_slurm_job(allocation)
        if args.max_memory_mib > min(allocated_memory, live_allocation["memory_mib"]):
            raise ValueError("Observed RSS bound cannot exceed the requested Slurm memory allocation")
        manifest_path, config_path = Path(args.train_manifest).resolve(), Path(args.config).resolve()
        if not manifest_path.is_file() or not config_path.is_file():
            raise FileNotFoundError("Explicit existing retained-train manifest and config files are required")
        manifest_sha, config_sha = file_sha256(manifest_path), file_sha256(config_path)
        config = load_experiment_config(config_path).to_dict()
        validate_preparation_config(config)
        train = StrictManifestDataset(manifest_path, atom_encoding="zero_based")
        candidate_output = validate_output_directory(args.output_dir, project_root=PROJECT_ROOT,
                                                     input_paths=[manifest_path, config_path, train.root])
        source = source_provenance(PROJECT_ROOT)
        if not isinstance(source.get("source_sha256"), str) or len(source["source_sha256"]) != 64:
            raise ValueError("Preparation requires the actual source byte fingerprint")
        inputs = {"train_manifest": {"path": str(manifest_path), "sha256": manifest_sha,
                                     "pool_hash": train.pool_hash, "view_hash": train.view_hash},
                  "config": {"path": str(config_path), "sha256": config_sha}, "source": source,
                  "lmdb_sources": _sources(train),
                  "lmdb_binding_kind": "hash-bound exact manifest plus observed payload size/mtime; no newly computed LMDB content hash"}
        summary.update(inputs=inputs, allocation={**allocation, "memory_mib": allocated_memory, "live_observation": live_allocation},
                       fit_seed=args.fit_seed, topology_seed=args.topology_seed,
                       topology_level=config["phase1"]["topology_level"], status="RUNNING")
        budget.check("before_fit")
        candidate_output.mkdir(parents=True, exist_ok=False)
        output = candidate_output
        _summary_write(output / "summary.json", summary, max_output_bytes=args.max_output_bytes)
        torch.set_num_threads(allocation["cpus_per_task"])
        # No CUDA APIs are called; preserve the scheduler's visibility verbatim.
        with wall_alarm(max(0.001, args.max_wall_seconds - budget.evidence()["elapsed_seconds"])):
            prepared = fit_full_train_controls(train, config, fit_seed=args.fit_seed, topology_seed=args.topology_seed,
                                               deadline_check=budget.check)
            budget.check("input_revalidation")
            if (file_sha256(manifest_path) != manifest_sha or file_sha256(config_path) != config_sha
                    or source_provenance(PROJECT_ROOT) != source or _sources(train) != inputs["lmdb_sources"]):
                raise ValueError("Source, manifest, config or LMDB payload changed during full-train fitting")
            encoded = {"controls.json": _encode(prepared["controls"]), "fit_ids.json": _encode(prepared["fit_ids"])}
            # Count the actual entire directory, retaining room for truthful
            # compact failure evidence even if a later write/rename fails.
            if sum(_owned_files(output).values()) + sum(len(value) for value in encoded.values()) + FAILURE_EVIDENCE_RESERVE > args.max_output_bytes:
                raise PreparationBudgetExceeded("Controls plus fit IDs exceed the declared output allowance")
            evidence = {}
            for name, content in encoded.items():
                budget.check("artifact_save")
                path = output / name
                pending = output / f"{name}.pending"
                with pending.open("xb") as handle:
                    handle.write(content)
                    handle.flush()
                    os.fsync(handle.fileno())
                evidence[name] = {"path": str(path), "sha256": file_sha256(pending), "bytes": len(content)}
            budget.check("artifact_publish")
            for name in encoded:
                (output / f"{name}.pending").replace(output / name)
                published.append(output / name)
            budget.check("finalization")
            proof = prepared["proof"]
            summary.update(status="COMPLETE_NOT_FROZEN", complete=True, artifacts=evidence,
                           full_training_view=proof["train"], all_retained_train_ids_fitted=True,
                           statistics_fit_records=proof["statistics_fit_records"], baseline_fit_records=proof["baseline_fit_records"],
                           element_fit_view_records=proof["element_fit_view_records"], strict_formal_consumer_roundtrip_passed=True,
                           continuous_output_contract_sha256=proof["consumer_proof"]["continuous_output_contract_sha256"],
                           affine_contract_derived_for_selfcheck_only=proof["affine_contract_derived_for_selfcheck_only"],
                           resources=budget.evidence(), artifact_payload_bytes=sum(len(value) for value in encoded.values()))
            _summary_write(output / "summary.json", summary, max_output_bytes=args.max_output_bytes)
        return summary, 0
    except (Exception, KeyboardInterrupt) as exc:
        summary.update(status="TIMEOUT_OR_RESOURCE_LIMIT" if isinstance(exc, PreparationBudgetExceeded) else "FAILED",
                       complete=False, strict_formal_consumer_roundtrip_passed=False,
                       error_type=type(exc).__name__, error=str(exc))
        if budget is not None:
            summary["resources"] = budget.evidence()
        if output is not None:
            # This directory belongs exclusively to this attempt. Retain failed
            # payloads for evidence, but never publish them as complete artifacts.
            secondary = []
            for path in published:
                try:
                    if path.exists():
                        path.replace(output / f"{path.name}.incomplete")
                except Exception as failed_revoke:
                    secondary.append(f"{type(failed_revoke).__name__}: {failed_revoke}")
            try:
                _failure_summary_write(output, summary, max_output_bytes=args.max_output_bytes)
            except Exception as failed_evidence:
                secondary.append(f"{type(failed_evidence).__name__}: {failed_evidence}")
            if secondary:
                summary["failure_evidence_write_error"] = "; ".join(secondary)
        return summary, 3 if isinstance(exc, PreparationBudgetExceeded) else 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train-manifest", required=True, help="Explicit complete retained-train manifest; no subset option")
    parser.add_argument("--config", required=True, help="Explicit preparation configuration; never overwritten")
    parser.add_argument("--output-dir", required=True, help="New directory outside repository and all input trees")
    parser.add_argument("--fit-seed", type=int, required=True)
    parser.add_argument("--topology-seed", type=int, required=True)
    parser.add_argument("--max-wall-seconds", type=float, required=True)
    parser.add_argument("--max-memory-mib", type=int, required=True)
    parser.add_argument("--max-output-bytes", type=int, required=True)
    args = parser.parse_args()
    summary, code = run_preparation(args)
    print(json.dumps({name: summary.get(name) for name in ("status", "complete", "formal_eligible", "error_type", "error")}, ensure_ascii=False))
    if summary.get("failure_evidence_write_error"):
        print("Failure evidence finalization also failed: " + summary["failure_evidence_write_error"], file=sys.stderr)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
