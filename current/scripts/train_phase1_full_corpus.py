#!/usr/bin/env python3
"""New frozen compact-corpus pretraining entry; no historical formal bridge.

This is a draft implementation pending actual QA, full-train fit, initialization,
model/bucket capacity profile and independent CPU/resume tests. It accepts only
the new frozen schema. An owned Slurm launcher selects a live GPU UUID and runs
the external resource/foreign-process/quota supervisor; this CLI cannot make a
shared GPU isolated. Every offline segment obtains a new W&B run and lineage.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import tempfile
import time

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import torch
import wandb

from phychem_mfm.factory import build_model
from phychem_mfm.phase1.downstream_training import checkpoint_content_sha256
from phychem_mfm.phase1.formal_gate import canonical_sha256 as canonical_hash
from phychem_mfm.phase1.formal_runtime import backbone_state_hash, single_gpu_environment
from phychem_mfm.phase1.full_corpus_loader import (
    CompactNativeIndex, FullCorpusViewsDataset, BlockAtomBatchSampler, make_prefetch_loader)
from phychem_mfm.phase1.full_corpus_training import FullCorpusTrainer
from phychem_mfm.phase1.full_corpus_controls import load_full_corpus_controls
from phychem_mfm.phase1.positive_strategy import JOINT, STRATEGIES, strategy_from_protocol
from phychem_mfm.phase1.seed_runtime import select_runtime_binding
from phychem_mfm.training.checkpoint import source_provenance
from phychem_mfm.training.full_corpus_normalization import (
    validate_full_train_regression_normalization, validate_full_train_moment_artifact)

SCHEMA = "phase1_full_corpus_pretraining_v1"
SHA = re.compile(r"^[0-9a-f]{64}$")


def require(value, message):
    if not value:
        raise RuntimeError(message)


def file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path, maximum=4 << 20):
    require(Path(path).is_file() and Path(path).stat().st_size <= maximum, "Metadata missing or too large: " + str(path))
    raw = Path(path).read_bytes()
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "Duplicate JSON key")
            result[key] = value
        return result
    return json.loads(raw.decode("utf-8"), object_pairs_hook=unique,
                      parse_constant=lambda x: (_ for _ in ()).throw(ValueError("Nonfinite JSON: " + x)))


def exclusive_json(path, value):
    raw = json.dumps(value, sort_keys=True, indent=2, allow_nan=False).encode() + b"\n"
    with Path(path).open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def tree_bytes(root):
    total = 0
    for path in Path(root).rglob("*"):
        if path.is_symlink():
            require(path.resolve().is_relative_to(Path(root).resolve()), "Output symlink leaves owned run directory")
        elif path.is_file():
            total += path.stat().st_size
    return total


def save_checkpoint(path, payload, output, cap):
    """At most best/latest and one owned pending archive coexist; no embeddings."""
    pending = Path(path).with_suffix(".pending.pt")
    require(not pending.exists(), "Owned checkpoint pending archive already exists")
    free = cap - tree_bytes(output)
    class BoundedWriter:
        def __init__(self, stream):
            self.stream, self.bytes = stream, 0
        def write(self, raw):
            require(self.bytes + len(raw) <= free, "Checkpoint atomic output peak exceeds run budget")
            self.bytes += len(raw)
            return self.stream.write(raw)
        def flush(self):
            self.stream.flush()
    try:
        with pending.open("xb") as stream:
            torch.save(payload, BoundedWriter(stream))
            stream.flush()
            os.fsync(stream.fileno())
        # Weights-only load plus typed tensor seal verifies the actual archive.
        checked = torch.load(pending, weights_only=True, map_location="cpu")
        require(checked["checkpoint_content_sha256"] == checkpoint_content_sha256(checked)
                == payload["checkpoint_content_sha256"], "Saved checkpoint roundtrip content differs")
        os.replace(pending, path)
    except BaseException:
        # Only this exclusive owned pending path, never any previous checkpoint.
        if pending.exists():
            pending.unlink()
        raise


def closed_history(run_file, journal_path):
    """Stream actual W&B protobuf history against every acknowledged row seal.

    Avoid the historical export helper's corpus-sized history list. This reads
    installed W&B data-store/protobuf APIs; it does not invent metric numbers.
    """
    from wandb.proto import wandb_internal_pb2
    from wandb.sdk.internal.datastore import DataStore
    store = DataStore()
    store.open_for_scan(str(run_file))
    rows = 0
    try:
        with Path(journal_path).open("r", encoding="utf-8") as journal:
            for line in journal:
                expected = json.loads(line)
                row = None
                while row is None:
                    data = store.scan_data()
                    require(data is not None, "W&B closed history ended before acknowledged rows")
                    record = wandb_internal_pb2.Record()
                    record.ParseFromString(data)
                    if record.HasField("history"):
                        row = {item.key or "/".join(item.nested_key): json.loads(item.value_json)
                               for item in record.history.item if item.key or item.nested_key}
                        if not row:
                            row = None
                require(row.get("_step") == expected["step"] == rows, "Closed W&B local cursor differs")
                scientific = {key: value for key, value in row.items() if not key.startswith("_")}
                observed_seal = scientific.pop("tracking/payload_sha256", None)
                require(observed_seal == expected["payload_sha256"] == canonical_hash(scientific),
                        "Closed W&B scientific payload differs from the acknowledged actual forward/update")
                rows += 1
            while (data := store.scan_data()) is not None:
                record = wandb_internal_pb2.Record()
                record.ParseFromString(data)
                require(not record.HasField("history") or not record.history.item, "Unexpected extra closed W&B history row")
    finally:
        closer = getattr(store, "close", None)
        if callable(closer):
            closer()
        elif getattr(store, "_fp", None) is not None:
            store._fp.close()
    return {"rows": rows, "run_file_sha256": file_hash(run_file), "journal_sha256": file_hash(journal_path),
            "all_acknowledged_payloads_exact": True, "online_sync_claimed": False}


def runtime(protocol, *, seed):
    """Actual Slurm host allocation and selected-device identity, not isolation."""
    compute = protocol["compute"]
    selection = select_runtime_binding(compute, seed=seed)
    profile = selection["profile"]
    require(compute["gpu_isolation_policy"] == "user_accepted_shared_gpu", "Only explicitly accepted project shared policy is supported")
    require(os.getuid() == 1278 and os.environ.get("USER") == "zixiao", "Live worker owner differs")
    job = os.environ.get("SLURM_JOB_ID")
    require(job and job.isdigit() and socket.gethostname() in profile["allowed_nodes"], "Actual owned Slurm node/job required")
    text = subprocess.check_output(["scontrol", "show", "job", "-o", job], text=True, timeout=15)
    fields = dict(token.split("=", 1) for token in text.split() if "=" in token)
    require(fields.get("JobId") == job and fields.get("UserId") == "zixiao(1278)"
            and fields.get("JobState") == "RUNNING" and fields.get("NumCPUs") == "16"
            and fields.get("NodeList") == socket.gethostname(), "Live Slurm allocation owner/node/CPU differs")
    tres = dict(item.split("=", 1) for item in fields.get("AllocTRES", fields.get("TRES", "")).split(",") if "=" in item)
    declared_memories = [value for value in (tres.get("mem"), fields.get("MinMemoryNode")) if value is not None]
    require(declared_memories and all(value in {"64G", "65536M", "68719476736"} for value in declared_memories),
            "Live allocation does not consistently declare the required 64GiB host memory")
    require(int(os.environ.get("SLURM_CPUS_PER_TASK", "0")) == 16, "CPU task declaration differs")
    single_gpu_environment(protocol)
    uuid = os.environ["CUDA_VISIBLE_DEVICES"]
    require(uuid.startswith("GPU-") and "," not in uuid, "Selected GPU must be the full physical UUID")
    gpu_text = subprocess.check_output(["nvidia-smi", "-i", uuid,
        "--query-gpu=uuid,name,memory.total,memory.free", "--format=csv,noheader,nounits"], text=True, timeout=15)
    observed = [value.strip() for value in gpu_text.strip().split(",")]
    require(len(observed) == 4 and observed[0] == uuid and observed[1] == profile["gpu_model"], "Selected NVML UUID/model differs")
    require(torch.cuda.device_count() == 1 and torch.cuda.get_device_name(0) == profile["gpu_model"], "Actual CUDA model/visibility differs")
    props = torch.cuda.get_device_properties(0)
    actual_uuid = str(props.uuid)
    require(actual_uuid == uuid or actual_uuid == uuid.removeprefix("GPU-"), "CUDA and NVML full UUID differ")
    actual = {"python_executable": str(Path(sys.executable).absolute()), "torch": str(torch.__version__),
              "cuda_runtime": torch.version.cuda, "default_dtype": str(torch.get_default_dtype())}
    require(actual == profile["runtime_environment"], "Selected paired-seed runtime environment differs")
    require(int(observed[2]) * (1 << 20) > compute["gpu_memory_safety_margin_bytes"]
            and int(observed[3]) * (1 << 20) >= compute["minimum_start_free_gpu_bytes"], "Selected GPU lacks the declared startup headroom")
    return {"job_id": job, "node": socket.gethostname(), "uid": os.getuid(), "cpus": 16,
            "requested_host_memory_bytes": 64 << 30, "gpu_uuid": uuid,
            "nvml_total_bytes": int(observed[2]) * (1 << 20), "nvml_start_free_bytes": int(observed[3]) * (1 << 20),
            "gpu_cap_bytes": int(observed[2]) * (1 << 20) - compute["gpu_memory_safety_margin_bytes"],
            "runtime_environment": actual, "runtime_selection": selection,
            "protection": "USER_ACCEPTED_SHARED_GPU_RISK",
            "external_supervisor_required": True, "device_isolation_verified": False}


def main():
    segment_started = time.monotonic()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--artifacts", required=True)
    parser.add_argument("--variant", choices=("none", "S", "D", "P", "SD", "SP", "DP", "SDP"), required=True)
    parser.add_argument("--seed", type=int, choices=(0, 1, 2), required=True)
    parser.add_argument("--strategy", choices=STRATEGIES, default=JOINT)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--resume")
    args = parser.parse_args()
    protocol, artifacts = read_json(args.protocol), read_json(args.artifacts)
    require(protocol.get("schema_version") == SCHEMA and protocol.get("state") == "frozen"
            and protocol.get("content_sha256") == canonical_hash({k: v for k, v in protocol.items() if k != "content_sha256"}),
            "Only an actually frozen new full-corpus scientific protocol is executable")
    require(args.variant in protocol["variants"] and args.seed in protocol["seeds"]
            and type(protocol["training"]["epochs"]) is int and protocol["training"]["epochs"] == 3,
            "Condition/seed/three-epoch coverage differs from the new protocol")
    require("strategy" not in protocol["training"], "Strategy has one frozen authority: protocol.strategies")
    strategy = strategy_from_protocol(protocol, args.strategy, args.variant, args.seed)
    require(protocol["tracking"]["mode"] == "offline", "This segmented entry closes actual offline W&B history only")
    require(protocol["loader_start_method"] == "spawn", "CUDA prefetch must use the declared spawn worker recipe")
    torch.multiprocessing.set_start_method("spawn", force=False)
    source_before = source_provenance(ROOT)
    require(not any(name.startswith("PHYCHEM_SOURCE_") for name in os.environ), "Do not override actual source provenance")
    require(source_before["git_commit"] == protocol["source"]["git_commit"]
            and source_before["source_sha256"] == protocol["source"]["source_sha256"], "Actual full-corpus source differs")
    expected = protocol["artifacts"]
    require("validation_controls" in expected, "Formal execution requires physically bound train-only original-unit controls")
    require(type(artifacts) is dict and set(artifacts) == set(expected), "Artifact map keys differ from the frozen new protocol")
    before = {}
    for key, declaration in expected.items():
        require(type(artifacts[key]) is str and SHA.fullmatch(declaration["sha256"]), "Invalid physical artifact declaration")
        before[key] = file_hash(artifacts[key])
        require(before[key] == declaration["sha256"], "Physical artifact bytes differ: " + key)
    require(before["source_snapshot"] == source_before["source_sha256"], "Source snapshot raw hash differs from live source aggregate")
    live = runtime(protocol, seed=args.seed)
    output = Path(args.output_dir).resolve()
    output.mkdir(parents=True, exist_ok=False)
    os.environ.update(WANDB_CACHE_DIR=str(output / "cache"), XDG_CACHE_HOME=str(output / "cache"))
    torch.set_num_threads(16)
    torch.manual_seed(args.seed)
    torch.cuda.manual_seed_all(args.seed)
    torch.set_default_dtype(torch.float32)
    norm = read_json(artifacts["normalization"])
    validate_full_train_regression_normalization(norm)
    moments = read_json(artifacts["training_moments"])
    validate_full_train_moment_artifact(norm, moments)
    require(norm["training_provenance"]["moments_file_sha256"] == before["training_moments"],
            "Full-train affine moment file differs from actual fit bytes")
    controls = read_json(artifacts["validation_controls"])
    load_full_corpus_controls(controls, norm)
    factory = deepcopy(protocol["model"])
    require(factory["backbone"]["n_atom_types"] == 119 and factory["backbone"]["activation_checkpointing"] is True,
            "Full-native 118-element taxonomy and genuine shared checkpoint required")
    factory["head"]["regression_output_normalization"] = norm
    model = build_model(factory)
    init = read_json(artifacts["initialization.seed_" + str(args.seed)])
    require(init == {"schema_version": "phase1_full_corpus_paired_initialization_v1", "seed": args.seed,
                     "model_config_sha256": canonical_hash(model.config_dict()),
                     "backbone_state_sha256": backbone_state_hash(model)}, "Fresh paired initialization differs from new model/fit recipe")
    run = wandb.init(project=protocol["tracking"]["project"], entity=protocol["tracking"]["entity"],
        mode=protocol["tracking"]["mode"], dir=str(output),
        name="full-corpus-" + args.variant + "-" + args.strategy + "-seed" + str(args.seed) + "-job" + live["job_id"],
        config={"protocol_sha256": protocol["content_sha256"], "variant": args.variant, "seed": args.seed,
                "source": source_before, "runtime": live, "new_full_corpus_science": True,
                "strategy": strategy.config_dict()})
    journal_path = output / "tracking_journal.jsonl"
    with journal_path.open("x", encoding="utf-8") as journal:
        def record(step, row):
            journal.write(json.dumps({"step": step, "payload_sha256": row["tracking/payload_sha256"]}, sort_keys=True) + "\n")
            journal.flush()
            os.fsync(journal.fileno())
        if args.variant == "none":
            require(not args.resume, "None is a zero-update initialization export")
            payload = {"schema_version": "phase1_full_corpus_none_endpoint_v1", "seed": args.seed,
                "strategy": strategy.config_dict(),
                "optimizer_updates": 0, "consumed_base_exposures": 0, "consumed_view_exposures": 0,
                "protocol_sha256": protocol["content_sha256"], "source": source_before,
                "model_config": model.config_dict(), "backbone_state_sha256": backbone_state_hash(model),
                "backbone_state": {name: value.detach().cpu().clone() for name, value in model.backbone.state_dict().items()}}
            payload["checkpoint_content_sha256"] = checkpoint_content_sha256(payload)
            row = {"train/optimizer_updates": 0, "train/base_exposures": 0, "train/view_exposures": 0,
                   "strategy/name": args.strategy, "strategy/recipe_sha256": strategy.config_dict()["recipe_sha256"],
                   "endpoint/paired_initial_encoder_sha256": payload["backbone_state_sha256"]}
            row["tracking/payload_sha256"] = canonical_hash(row)
            run.log(row, step=0, commit=True)
            record(0, row)
            save_checkpoint(output / "latest.pt", payload, output, protocol["storage"]["per_run_cap_bytes"])
            result = {"status": "complete", "none_no_corpus_iteration": True,
                      "strategy": strategy.config_dict(),
                      "optimizer_updates": 0, "consumed_base_exposures": 0, "consumed_view_exposures": 0}
        else:
            transport_path = Path(artifacts["native_transport"]).resolve()
            module_name = transport_path.stem
            require(re.fullmatch(r"[A-Za-z_]\w*", module_name) is not None, "Native transport must have an importable module name")
            sys.path.insert(0, str(transport_path.parent))
            spec = importlib.util.spec_from_file_location(module_name, transport_path)
            module = importlib.util.module_from_spec(spec)
            require(module_name not in sys.modules, "Native transport module name already loaded")
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            native_binding = {"policy": module.MASK_POLICY, "source_sha256": before["native_transport"]}
            indices = {}
            for key in ("train_manifest", "routine_validation_manifest", "full_validation_manifest"):
                indices[key] = CompactNativeIndex(read_json(artifacts[key]), expected_manifest_sha256=expected[key]["manifest_sha256"])
            cfg = deepcopy(protocol["training"])
            cfg.update(schema_version="phase1_full_corpus_training_v1", variant=args.variant, seed=args.seed, device="cuda:0")
            strategy = strategy_from_protocol(protocol, args.strategy, args.variant, args.seed,
                           total_base_exposures=cfg["epochs"] * len(indices["train_manifest"]))
            cfg["strategy"] = strategy.config_dict()
            cfg["original_unit_controls"] = deepcopy(controls)
            cfg["bindings"] = {"protocol_sha256": protocol["content_sha256"], "source_sha256": source_before["source_sha256"],
                "train_manifest_sha256": indices["train_manifest"].content_sha256,
                "routine_validation_manifest_sha256": indices["routine_validation_manifest"].content_sha256,
                "full_validation_manifest_sha256": indices["full_validation_manifest"].content_sha256,
                "normalization_contract_sha256": norm["contract_sha256"],
                "initial_encoder_sha256": init["backbone_state_sha256"], "environment": live["runtime_environment"],
                "runtime_selection": live["runtime_selection"]}
            sampler = BlockAtomBatchSampler(indices["train_manifest"], seed=args.seed, **protocol["sampler"])
            def loader(index, sample, seed):
                dataset = FullCorpusViewsDataset(index, native_transport=module.transport_native_record,
                    native_transport_binding=native_binding, seed=seed, **protocol["views"])
                return make_prefetch_loader(dataset, sample, **protocol["loader"])
            train_loader = loader(indices["train_manifest"], sampler, args.seed)
            def validation_sampler(scope):
                index = indices[("routine" if scope == "routine" else "full") + "_validation_manifest"]
                return BlockAtomBatchSampler(index, seed=protocol["validation_seed"], **protocol["sampler"])
            trainer = FullCorpusTrainer(model, sampler, cfg, tracker=run, journal=record)
            if args.resume:
                require(Path(args.resume).stat().st_size <= protocol["storage"]["per_run_cap_bytes"], "Resume archive exceeds declared bound")
                trainer.load_checkpoint(torch.load(args.resume, map_location="cpu", weights_only=True),
                    checkpoint_file_sha256=file_hash(args.resume), validation_sampler_factory=validation_sampler)
                run.config.update({"parent_run_id": trainer.tracking["parent_run_id"],
                                   "parent_checkpoint_sha256": trainer.tracking["parent_checkpoint_sha256"]})
            # A historical best score belongs to its historical checkpoint, not
            # the newer weights in a resumed segment's first latest snapshot.
            last_best = deepcopy(trainer.best_validation)
            def checkpoint(trained, kind):
                nonlocal last_best
                data = trained.checkpoint()
                save_checkpoint(output / "latest.pt", data, output, protocol["storage"]["per_run_cap_bytes"])
                if trained.best_validation is not None and trained.best_validation != last_best:
                    save_checkpoint(output / "best.pt", data, output, protocol["storage"]["per_run_cap_bytes"])
                    last_best = deepcopy(trained.best_validation)
            def validation_factory(scope):
                index = indices[("routine" if scope == "routine" else "full") + "_validation_manifest"]
                sample = validation_sampler(scope)
                return sample, loader(index, sample, protocol["validation_seed"])
            result = trainer.fit(train_loader, validation_factory=validation_factory,
                    checkpoint_callback=checkpoint, checkpoint_every_batches=protocol["checkpoint_every_consumed_batches"],
                    segment_started_at=segment_started)
            checkpoint(trainer, "latest")
            for index in indices.values():
                index.verify_unchanged()
    run_dir = Path(run.dir).resolve().parent
    run.finish()
    candidates = list(run_dir.glob("run-*.wandb"))
    require(len(candidates) == 1, "Actual closed W&B segment file is not unique")
    tracking = closed_history(candidates[0], journal_path)
    after = {key: file_hash(path) for key, path in artifacts.items()}
    source_after = source_provenance(ROOT)
    require(after == before and source_after["source_sha256"] == source_before["source_sha256"]
            and source_after["git_commit"] == source_before["git_commit"], "Source or input artifacts changed during the segment")
    require(tree_bytes(output) <= protocol["storage"]["per_run_cap_bytes"], "Final run output exceeds budget")
    summary = {"schema_version": "phase1_full_corpus_segment_execution_v1", "result": result,
        "strategy": strategy.config_dict(),
        "tracking": tracking, "source_before": source_before, "source_after": source_after,
        "input_sha256_before": before, "input_sha256_after": after, "runtime": live,
        "latest_checkpoint_sha256": file_hash(output / "latest.pt"), "output_bytes_before_summary": tree_bytes(output),
        "old_58k_protocol_or_source_bridge_used": False, "final_test_targets_read": False,
        "completion_requires_actual_child_and_Slurm_exit_zero": True}
    exclusive_json(output / "summary.json", summary)
    require(tree_bytes(output) <= protocol["storage"]["per_run_cap_bytes"], "Closed summary exceeds the run output budget")
    print(json.dumps({"status": result["status"], "summary_sha256": file_hash(output / "summary.json"),
                      "history_rows": tracking["rows"], "output_dir": str(output)}, sort_keys=True))


if __name__ == "__main__":
    main()
