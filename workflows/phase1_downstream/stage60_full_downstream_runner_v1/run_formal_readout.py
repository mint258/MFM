#!/usr/bin/env python3
"""External five-dataset formal readout worker; root-owned execution only.

--help is stdlib-only. Actual cache/fit work imports the physically bound real
project, provider and decoder. A resource supervisor must account the shared
H0 cache as well as fit outputs and enforce the accepted shared-GPU policy.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time

sys.dont_write_bytecode = True

from formal_plan import compile_plan, select_fit, digest, require, canonical


def raw_sha(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def load_module(name, ref):
    require(Path(ref["path"]).is_absolute() and not Path(ref["path"]).is_symlink()
            and Path(ref["path"]).stat().st_size == ref["bytes"] and raw_sha(ref["path"]) == ref["sha256"], "Actual bound module bytes differ")
    require(name not in sys.modules, "External module name is already occupied")
    spec = importlib.util.spec_from_file_location(name, ref["path"])
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", required=True)
    parser.add_argument("--request-sha256", required=True)
    args = parser.parse_args()
    started = time.monotonic()
    require(raw_sha(args.request) == args.request_sha256, "Actual worker request changed")
    def pairs(items):
        value = {}
        for key, item in items:
            require(key not in value, "Duplicate execution request field")
            value[key] = item
        return value
    request = json.loads(Path(args.request).read_bytes(), object_pairs_hook=pairs,
        parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
    fields = {"schema_version", "mode", "protocol", "runtime_source", "provider", "endpoint", "fit_id",
              "cache", "output_dir", "limits", "expected_slurm_job_id", "resume_checkpoint"}
    require(type(request) is dict and set(request) == fields
            and request["schema_version"] == "phase1_full_downstream_execution_request_v1"
            and request["mode"] in ("cache", "fit"), "Exact external formal readout request required")
    require(os.getuid() == 1278 and os.environ.get("USER") == "zixiao"
            and os.environ.get("SLURM_JOB_ID") == request["expected_slurm_job_id"], "Actual owned Slurm allocation differs")
    require(not any(key.startswith("PHYCHEM_SOURCE_") for key in os.environ), "Actual source provenance must not be overridden")
    project = Path(request["runtime_source"]["project_root"])
    require(project.is_absolute() and project.is_dir(), "Actual project path required")
    sys.path.insert(0, str(project))
    from formal_readout import (read_bound_json, write_json, file_sha, load_encoder, prepare_h0_cache,
        NativeH0Cache, validate_store_group, validate_store_readout_bridge, frozen_metric_cells,
        train_fixed_readout, evaluate_outer, TypedOfflineJournal)
    import torch
    import wandb
    from phychem_mfm.training.checkpoint import source_provenance
    source_before = source_provenance(project)
    require(all(source_before.get(key) == request["runtime_source"][key] for key in ("git_commit", "source_sha256")), "Actual runtime source differs from the raw-bound consumer")
    for name, module in tuple(sys.modules.items()):
        if name.startswith("phychem_mfm") and getattr(module, "__file__", None):
            require(Path(module.__file__).resolve().is_relative_to(project.resolve()), "Imported project module origin escapes actual source")
    protocol = read_bound_json(request["protocol"], 2 << 20)
    plan = compile_plan(protocol, protocol_file_sha256=request["protocol"]["sha256"])
    fit = select_fit(plan, request["fit_id"])
    endpoint = request["endpoint"]
    require(all(endpoint[name] == fit[name] for name in ("strategy", "variant", "pretraining_seed")), "Fit/encoder artifact pairing differs")
    limits = request["limits"]
    require(set(limits) == {"wall_seconds", "max_atoms_per_forward", "cache_cap_bytes", "fit_cap_bytes", "maximum_journal_bytes"}
            and all(type(value) is int and value > 0 for value in limits.values()), "Explicit positive execution budgets required")
    require(limits["fit_cap_bytes"] <= protocol["storage"]["per_run_cap_bytes"], "Single fit storage cannot exceed frozen per-run cap")
    def wall_check():
        require(time.monotonic() - started < limits["wall_seconds"], "Whole external worker wall budget exhausted")
    # Reuse actual allocation/environment observations without invoking the
    # pretraining main(), optimizers, data views or statistics computation.
    runtime_path = project / "scripts" / "train_phase1_full_corpus.py"
    runtime_module = load_module("phase60_actual_runtime_entry", {
        "path": str(runtime_path), "bytes": runtime_path.stat().st_size, "sha256": file_sha(runtime_path)})
    torch.set_num_threads(16)
    torch.set_default_dtype(torch.float32)
    runtime = runtime_module.runtime(protocol, seed=fit["pretraining_seed"])
    provider = load_module("phase60_actual_data_provider", request["provider"]["module"])
    manifest = request["provider"]["manifest"]
    require(Path(manifest["path"]).stat().st_size == manifest["bytes"] and file_sha(manifest["path"]) == manifest["sha256"], "Physical downstream manifest differs")
    store = provider.FrozenDownstreamStore(manifest["path"], expected_sha256=manifest["sha256"])
    store.verify_unchanged()
    contract, roles = validate_store_group(store, fit)
    manifest_document = read_bound_json(manifest)
    readout_bridge = validate_store_readout_bridge(manifest_document, protocol, contract, fit)
    metric_cells = frozen_metric_cells(manifest_document, protocol, contract, fit)
    store_binding = {"manifest_file_sha256": manifest["sha256"], "provider_module_file_sha256": request["provider"]["module"]["sha256"]}
    model, encoder_binding = load_encoder(protocol, endpoint, device="cuda:0")
    output = Path(request["output_dir"])
    output.mkdir(parents=True, exist_ok=False)
    cache, journal, successful, result = None, None, False, None
    try:
        if request["mode"] == "cache":
            require(request["resume_checkpoint"] is None, "Feature cache has no optimizer resume")
            cache_ref = prepare_h0_cache(model, store, fit, encoder_binding=encoder_binding,
                store_binding=store_binding, directory=request["cache"]["directory"],
                cache_cap_bytes=limits["cache_cap_bytes"], max_atoms_per_forward=limits["max_atoms_per_forward"], wall_check=wall_check)
            result = {"status": "COMPLETE_NATIVE_H0_INPUT_CACHE", "cache": cache_ref,
                "cache_is_whole_phase_accounted_input": True, "actual_optimizer_updates": 0}
        else:
            cache = NativeH0Cache(request["cache"]["directory"],
                expected_catalog_sha256=request["cache"]["catalog_sha256"], encoder_binding=encoder_binding,
                store_binding=store_binding, dataset_id=fit["dataset_id"])
            os.environ.update(WANDB_CACHE_DIR=str(output / "cache"), XDG_CACHE_HOME=str(output / "cache"))
            require(str(wandb.__version__) == "0.28.1", "Actual closed-history SDK version differs")
            run = wandb.init(project=protocol["tracking"]["project"], entity=protocol["tracking"]["entity"],
                mode="offline", dir=str(output), name=fit["fit_id"],
                config={"protocol_content_sha256": protocol["content_sha256"], "fit": fit,
                        "encoder_binding": encoder_binding, "source": source_before, "runtime": runtime,
                        "source_contract_sha256": digest(contract)})
            journal = TypedOfflineJournal(run, output, maximum_rows=20 * ((len(roles["train"]) + 31) // 32),
                maximum_journal_bytes=limits["maximum_journal_bytes"])
            readout, training = train_fixed_readout(store, cache, fit, contract, protocol=protocol,
                encoder_binding=encoder_binding, tracker=journal, directory=output, device="cuda:0",
                wall_check=wall_check, resume_ref=request["resume_checkpoint"])
            metric = evaluate_outer(readout, store, cache, fit, contract, device="cuda:0",
                encoder_binding=encoder_binding, wall_check=wall_check, metric_cell_bindings=metric_cells)
            decoder_path = project / "tools" / "export_wandb_history.py"
            decoder = load_module("phase60_actual_closed_wandb_decoder", {
                "path": str(decoder_path), "bytes": decoder_path.stat().st_size, "sha256": file_sha(decoder_path)})
            tracking = journal.finish(success=True, decode_history=decoder.decode_history)
            write_json(output / "metrics.json", metric)
            result = {"status": "COMPLETE_FIXED_FINAL_READOUT_AND_OUTER_METRICS", "training": training,
                "tracking": tracking, "metric_file_sha256": file_sha(output / "metrics.json"),
                "unavailable_metrics_are_null": True, "heldout_selection_performed": False,
                "formal_statistics_envelope_issued": False}
        wall_check()
        store.verify_unchanged()
        require(source_provenance(project) == source_before and raw_sha(args.request) == args.request_sha256
                and file_sha(request["protocol"]["path"]) == request["protocol"]["sha256"]
                and file_sha(endpoint["checkpoint"]["path"]) == endpoint["checkpoint"]["sha256"]
                and file_sha(request["provider"]["module"]["path"]) == request["provider"]["module"]["sha256"], "Actual source/input bytes changed during computation")
        successful = True
    finally:
        if cache is not None:
            cache.close()
        if journal is not None and not journal.finished:
            journal.finish(success=False, decode_history=None)
    summary = {"schema_version": "phase1_full_downstream_worker_execution_v1", "complete": successful,
        "result": result, "fit": fit, "encoder_binding": encoder_binding, "runtime": runtime,
        "source_before": source_before, "source_after": source_provenance(project),
        "external_driver_source_file_sha256": file_sha(__file__), "provider_binding": store_binding,
        "actual_384_readout_bridge": readout_bridge,
        "request_file_sha256": args.request_sha256, "protocol_file_sha256": request["protocol"]["sha256"],
        "wall_seconds": time.monotonic() - started, "pretraining_recipe_modified": False,
        "device_isolation_verified": False, "protection": "USER_ACCEPTED_SHARED_GPU_RISK_EXTERNAL_SUPERVISOR_REQUIRED"}
    summary["execution_receipt_sha256"] = digest(summary)
    write_json(output / "summary.json", summary)
    print(json.dumps({"complete": successful, "status": result["status"], "fit_id": fit["fit_id"]}, sort_keys=True))


if __name__ == "__main__":
    main()
