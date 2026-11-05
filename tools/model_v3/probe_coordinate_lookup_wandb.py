#!/usr/bin/env python3
"""Actual CPU offline-SDK probe of C2's canonical owned output layout.

This creates only two synthetic tracking records, no native data or fit. It
uses the fixed already-validated supervisor census without modifying it.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys

from run_coordinate_lookup import configure_wandb_layout, save

ROOT = Path(__file__).absolute().parents[2]
MONITOR = Path("/share/home/zixiao/descriptor_analysis/MFM_model_v3_profiler_v2/tools/model_v3/runtime_monitor.py")
MONITOR_SHA256 = "dbe875ab7ceec7e5002c5b70bff0608e3506f7451bdacd38e5f5bfc0700663fe"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    if (not os.environ.get("SLURM_JOB_ID") or int(os.environ.get("SLURM_CPUS_PER_TASK", "0")) < 16
            or os.environ.get("CUDA_VISIBLE_DEVICES") != ""):
        raise RuntimeError("Use the root coordinator's CPU-only allocation with at least16 CPUs")
    if "wandb" in sys.modules:
        raise RuntimeError("The real SDK probe needs a fresh process before any W&B import")
    output = args.output_root.absolute()
    if output.exists() or output.resolve().is_relative_to(ROOT.resolve()):
        raise ValueError("Fresh external owned probe output required")
    if MONITOR.is_symlink() or not MONITOR.is_file() or sha(MONITOR) != MONITOR_SHA256:
        raise ValueError("The fixed profiler-v2 census source differs")
    output.mkdir(parents=True)
    source_paths = {"probe": Path(__file__), "runner": Path(__file__).with_name("run_coordinate_lookup.py"),
                    "fixed_monitor": MONITOR}
    sources_before = {key: sha(path) for key, path in source_paths.items()}
    layout = configure_wandb_layout(output)
    spec = importlib.util.spec_from_file_location("C2_exact_fixed_runtime_monitor", MONITOR)
    monitor = importlib.util.module_from_spec(spec); spec.loader.exec_module(monitor)
    import wandb
    from wandb.sdk.internal.datastore import DataStore
    from wandb.proto import wandb_internal_pb2
    run = None
    censuses, failure = [], None
    try:
        run = wandb.init(project="phychem-model-v3", mode="offline", dir=str(output),
            name="model_v3_C2_sdk_layout_probe_"+os.environ["SLURM_JOB_ID"],
            config={"synthetic_logging_probe_only": True, "native_records_decoded": 0,
                    "source_sha256": sources_before, "layout": layout})
        if run is None or run.disabled:
            raise RuntimeError("A real enabled offline SDK run is required")
        censuses.append({"stage": "initialized", "owned_output_bytes": monitor.owned_output_bytes(output)})
        for step in range(2):
            run.log({"C2_sdk_probe/update": step, "C2_sdk_probe/value": float(step+1)}, step=step, commit=True)
            censuses.append({"stage": "committed_"+str(step), "owned_output_bytes": monitor.owned_output_bytes(output)})
        run_id = run.id
        run.finish(exit_code=0); run = None
        censuses.append({"stage": "SDK_finished", "owned_output_bytes": monitor.owned_output_bytes(output)})
        streams = list((output / "wandb").glob("offline-run-*/run-*.wandb"))
        if len(streams) != 1:
            raise RuntimeError("Exactly one native offline SDK stream required")
        history, datastore = [], DataStore()
        datastore.open_for_scan(str(streams[0]))
        try:
            while (raw := datastore.scan_data()) is not None:
                record = wandb_internal_pb2.Record(); record.ParseFromString(raw)
                if record.WhichOneof("record_type") != "history":
                    continue
                row = {item.key or "/".join(item.nested_key): json.loads(item.value_json) for item in record.history.item}
                if "C2_sdk_probe/update" in row:
                    history.append(row)
        finally:
            datastore.close()
        if [(row["C2_sdk_probe/update"], row["C2_sdk_probe/value"]) for row in history] != [(0, 1.), (1, 2.)]:
            raise RuntimeError("The actual durable native history differs from the two committed records")
        links = [{"path": path.relative_to(output).as_posix(), "target": os.readlink(path)}
                 for path in output.rglob("*") if path.is_symlink()]
        top = {"wandb/latest-run", "wandb/debug.log", "wandb/debug-internal.log"}
        actual = {row["path"] for row in links}
        core = actual - top
        if not top <= actual or len(core) != 1 or not re.fullmatch(
                r"wandb/offline-run-[0-9]{8}_[0-9]{6}-[a-z0-9]{8}/logs/debug-core.log", next(iter(core))):
            raise RuntimeError("The actual SDK must exhibit all four validated link forms")
        sources_after = {key: sha(path) for key, path in source_paths.items()}
        if sources_after != sources_before:
            raise RuntimeError("Logging probe/source/census changed while the probe ran")
        report = {"status": "REAL_SDK_LAYOUT_PASS", "job_id": os.environ["SLURM_JOB_ID"],
            "wandb_version": str(wandb.__version__), "wandb_run_id": run_id, "tracking_mode": "offline",
            "layout_configured_before_sdk_import": True, "layout": layout, "censuses": censuses,
            "links": links, "four_real_sdk_link_forms_checked": True, "native_history_rows": len(history),
            "native_sdk_stream": {"path": str(streams[0]), "sha256": sha(streams[0]), "bytes": streams[0].stat().st_size},
            "source_sha256_before": sources_before, "source_sha256_after": sources_after,
            "native_records_decoded": 0, "optimizer_updates": 0, "online_sync_performed": False}
        save(output / "verification.json", report)
        monitor.owned_output_bytes(output)
        print(json.dumps(report), flush=True)
    except BaseException as exc:
        failure = exc
        if run is not None:
            run.finish(exit_code=1); run = None
        save(output / "FAILED.json", {"status": "REAL_SDK_LAYOUT_FAILED", "exception_type": type(exc).__name__,
            "message": str(exc), "observations": censuses, "native_records_decoded": 0})
        raise
    finally:
        if run is not None:
            run.finish(exit_code=int(failure is not None))


if __name__ == "__main__":
    main()
