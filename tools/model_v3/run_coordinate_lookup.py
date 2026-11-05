#!/usr/bin/env python3
"""Bind/prepare/run the independent C2 analysis; never submit a job.

Root owns Slurm admission/supervision. Binding and metadata preparation must
finish and be reviewed before an explicit run command opens native geometry.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import resource
import sys
import time
import traceback

ROOT = Path(__file__).absolute().parents[2]
sys.path.insert(0, str(ROOT / "current"))


def save(path, value):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n"); stream.flush(); os.fsync(stream.fileno())


def configure_wandb_layout(output):
    """Bind canonical owned SDK paths before importing or initializing W&B."""
    output = Path(output).absolute()
    if not output.is_dir() or output.is_symlink():
        raise ValueError("An owned ordinary C2 output directory is required")
    paths = {"WANDB_DIR": output, "WANDB_CACHE_DIR": output / "cache",
             "WANDB_DATA_DIR": output / "wandb_data", "WANDB_CONFIG_DIR": output / "wandb_config"}
    for path in paths.values():
        if path.is_symlink() or (path.exists() and not path.is_dir()):
            raise ValueError("Canonical W&B paths must be ordinary directories")
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.environ.update({key: str(path) for key, path in paths.items()})
    os.environ["WANDB_MODE"] = "offline"
    return {**{key: str(path) for key, path in paths.items()}, "WANDB_MODE": "offline"}


def request_document(code_sha, preregistration_sha):
    from phychem_mfm.phase1.v3_coordinate_lookup import CoordinateLookupConfig
    from phychem_mfm.phase1.v3_coordinate_lookup_source import (OLD, PROJECT, LookupSelection,
        ORIGINAL_SNAPSHOT_SHA, bind_source_snapshot, binding, implementation_sources)
    configuration = ROOT / "workflows/sprime_s/formal_s/B1_seed0_v2.json"
    original = json.loads(configuration.read_text())
    _, snapshot = bind_source_snapshot(OLD / "training_inputs_v1/shard_snapshot_v1.json", ORIGINAL_SNAPSHOT_SHA)
    return {"schema": "model_v3_C2_existing_S_request_v1", "code_sha": code_sha,
        "preregistration_sha": preregistration_sha, "method": asdict(CoordinateLookupConfig()),
        "selection": asdict(LookupSelection()), "source_files": implementation_sources(),
        "configuration": binding(configuration),
        "input_manifest": binding(OLD / "training_inputs_v1/manifest.json"),
        "population_manifest": binding(PROJECT / "runs/phase1_wp5_20261011/population/manifest.json"),
        "protocol": binding(original["frozen_protocol_reference"]["path"]),
        "shard_snapshot": {key: snapshot[key] for key in ("path", "bytes", "sha256")},
        "interpretation": "ANALYSIS_ONLY_NOT_MODEL_SELECTION",
        "source_noise": {"seed": 0, "epoch": 0, "noise_seed_includes_epoch": True, "sigma_A": .1},
        "execution_caps": {"wall_seconds": 3300, "finalization_reserve_seconds": 30,
            "maximum_process_RSS_bytes": 24 * 1024**3, "maximum_output_bytes": 128 * 1024**2}}


class Guard:
    def __init__(self, output):
        self.output, self.started = output, time.monotonic()
        self.checked, self.logged = -1e9, -1e9
        self.output_bytes, self.peak_RSS_bytes = 0, 0
        self.stage = "SOURCE_BINDING"

    def __call__(self):
        elapsed = time.monotonic() - self.started
        if elapsed > 3270:
            raise TimeoutError("C2 reached its reserved finalization boundary")
        self.peak_RSS_bytes = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) * 1024
        if self.peak_RSS_bytes > 24 * 1024**3:
            raise MemoryError("C2 process RSS exceeded its declared bound")
        if elapsed - self.checked >= 2:
            self.output_bytes = sum(path.stat().st_size for path in self.output.rglob("*") if path.is_file())
            self.checked = elapsed
            if self.output_bytes > 128 * 1024**2:
                raise OSError("C2 output exceeded its declared bound")
        if elapsed - self.logged >= 30:
            print(json.dumps({"stage": self.stage, "elapsed_seconds": elapsed,
                "peak_RSS_bytes": self.peak_RSS_bytes, "output_bytes": self.output_bytes}), flush=True)
            self.logged = elapsed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("bind", "prepare", "run"), required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--request", type=Path)
    parser.add_argument("--request-sha256")
    parser.add_argument("--selection-plan", type=Path)
    parser.add_argument("--selection-plan-sha256")
    parser.add_argument("--code-sha")
    parser.add_argument("--preregistration-sha")
    args = parser.parse_args()
    if not os.environ.get("SLURM_JOB_ID") or int(os.environ.get("SLURM_CPUS_PER_TASK", "0")) < 16:
        raise RuntimeError("C2 commands require the root coordinator's owned 16-CPU Slurm allocation")
    if os.environ.get("CUDA_VISIBLE_DEVICES") != "":
        raise RuntimeError("This analysis is CPU-only; explicitly hide CUDA devices")
    output = args.output_root.absolute()
    if output.exists() or output.resolve().is_relative_to(ROOT.resolve()):
        raise ValueError("Fresh external output directory required; preserve all previous evidence")
    output.mkdir(parents=True)
    guard = Guard(output)
    source = run = None
    try:
        from phychem_mfm.phase1.v3_dev_store import bound_json
        from phychem_mfm.phase1.v3_coordinate_lookup_source import ExistingSLookupSource, binding
        if args.mode == "bind":
            import re
            if not all(re.fullmatch(r"[0-9a-f]{40}", value or "") for value in (args.code_sha, args.preregistration_sha)):
                raise ValueError("Full actual code and published preregistration commits required")
            request = request_document(args.code_sha, args.preregistration_sha)
            save(output / "source_request.json", request)
            save(output / "binding_result.json", {"status": "BOUND_METADATA_ONLY", "native_geometry_records_decoded": 0,
                "request": binding(output / "source_request.json")})
            return
        if args.request is None or args.request_sha256 is None:
            raise ValueError("An immutable source request and raw SHA are required")
        request = bound_json(args.request, args.request_sha256)
        source = ExistingSLookupSource(request, check=guard)
        guard.stage = "METADATA_SELECTION"
        selected = source.plan()
        if args.mode == "prepare":
            source.verify(); source.close()
            save(output / "selection_plan.json", selected)
            save(output / "preparation_result.json", {"status": "FROZEN_METADATA_ONLY_SELECTION",
                "selection_plan": binding(output / "selection_plan.json"), "native_geometry_records_decoded": 0,
                "source_request": binding(args.request),
                "original_snapshot_receipt": getattr(source, "snapshot_receipt", None),
                "node_local_device_projections": getattr(source, "node_local_device_projections", None)})
            return
        if args.selection_plan is None or args.selection_plan_sha256 is None:
            raise ValueError("Freeze metadata selection before an explicit C2 run")
        original = bound_json(args.selection_plan, args.selection_plan_sha256)
        if original != selected:
            raise ValueError("Frozen metadata selection differs; do not reselect after fitting")
        save(output / "input_binding.json", {"source_request": binding(args.request),
            "selection_plan": binding(args.selection_plan), "actual_code_sha": request["code_sha"],
            "public_preregistration_sha": request["preregistration_sha"], "role_evidence": selected["role_evidence"],
            "original_snapshot_receipt": getattr(source, "snapshot_receipt", None),
            "node_local_device_projections": getattr(source, "node_local_device_projections", None)})
        tracking_layout = configure_wandb_layout(output)
        import wandb
        run = wandb.init(project="phychem-model-v3", mode="offline", dir=str(output),
            name="model_v3_C2_radial_coordinate_lookup_seed0_"+os.environ["SLURM_JOB_ID"],
            config={"code_sha": request["code_sha"], "preregistration_sha": request["preregistration_sha"],
                "request_sha256": args.request_sha256, "selection_plan_sha256": args.selection_plan_sha256,
                "method": request["method"], "analysis_only": True, "seed": 0,
                "tracking_layout": tracking_layout})
        if run is None or run.disabled:
            raise RuntimeError("Persistent offline W&B is required")
        from phychem_mfm.phase1.v3_coordinate_lookup import (CoordinateLookupConfig, fit_coordinate_lookup,
                                                            evaluate_coordinate_lookup)
        guard.stage = "TRAIN_SPARSE_FIT"
        model = fit_coordinate_lookup(source.records("TRAIN", selected),
            config=CoordinateLookupConfig(**request["method"]), expected_records=request["selection"]["train_records"],
            source_plan_sha256=args.selection_plan_sha256, check=guard)
        run.log({"fit/records": model.fit_receipt["TRAIN_records"], "fit/atoms": model.fit_receipt["TRAIN_atoms"],
            "fit/solver_iterations": model.fit_receipt["solver"]["iterations"],
            "fit/observed_codes": model.fit_receipt["observed_codes"]}, step=0, commit=True)
        guard.stage = "PRETRAIN_VALIDATION_ANALYSIS"
        metrics = evaluate_coordinate_lookup(model, source.records("PRETRAIN_VAL", selected),
            expected_records=request["selection"]["validation_records"], check=guard)
        source.verify(); source.close(); guard()
        save(output / "coordinate_lookup.json", model.document())
        result = {"status": "ANALYSIS_COMPLETE_NOT_MODEL_SELECTION", "fit_receipt": model.fit_receipt,
            "metrics": metrics, "native_geometry_records_decoded": source.native_reads,
            "resource_observation": {"wall_seconds": time.monotonic()-guard.started,
                "process_peak_RSS_bytes": guard.peak_RSS_bytes, "output_bytes_before_finalization": guard.output_bytes},
            "wandb_run_id": run.id, "tracking_mode": "persistent_offline", "online_sync_claimed": False}
        result["tracking_layout"] = tracking_layout
        run.log({"validation/"+key: value for key, value in metrics.items()
            if type(value) in (int, float)}, step=1, commit=True)
        run.finish(); run = None
        save(output / "result.json", result)
        save(output / "COMPLETE.json", {"status": "ANALYSIS_COMPLETE_NOT_MODEL_SELECTION",
            "lookup": binding(output / "coordinate_lookup.json"), "result": binding(output / "result.json"),
            "source_request": binding(args.request), "selection_plan": binding(args.selection_plan)})
    except BaseException as exc:
        if run is not None:
            run.finish(exit_code=1)
        save(output / "FAILED.json", {"exception_type": type(exc).__name__, "exception_chain": traceback.format_exc(),
            "stage": guard.stage, "elapsed_seconds": time.monotonic()-guard.started,
            "native_geometry_records_decoded": 0 if source is None else source.native_reads})
        raise
    finally:
        if source is not None:
            source.close()


if __name__ == "__main__":
    main()
