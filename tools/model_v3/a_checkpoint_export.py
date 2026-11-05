"""Opt-in H0-only artifacts from completed native A numerical comparisons.

Uses the standard format-v1 envelope and atomic serializer without modifying
the original checkpoint module, enabling unsafe pickle, or providing A resume.
Only the final READY receipt admits an exported bundle to downstream review;
the outer Slurm/supervisor terminal status must still be checked separately.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import resource
import stat
import time


def require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def rng_fingerprint():
    import torch
    def fingerprint(value):
        return hashlib.sha256(value.cpu().numpy().tobytes()).hexdigest()
    return {"torch_cpu": fingerprint(torch.get_rng_state()),
            "torch_cuda": {str(device): fingerprint(torch.cuda.get_rng_state(device))
                           for device in range(torch.cuda.device_count())} if torch.cuda.is_initialized() else {}}


def file_ref(path):
    path = Path(path).absolute()
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and info.st_nlink == 1,
            "Owned ordinary single-link export file required")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024**2), b""):
            digest.update(block)
    return {"path": str(path), "sha256": digest.hexdigest(), "bytes": info.st_size}


def write_json(path, value):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def validate_export_destination(destination, *, output_root, repository_root):
    if destination is None:
        return None
    destination, output_root, repository_root = map(lambda value: Path(value).absolute(),
                                                    (destination, output_root, repository_root))
    require(".." not in destination.parts and destination.parent == output_root,
            "Export must be one fresh immediate child of this run output root")
    require(not destination.is_relative_to(repository_root) and not destination.exists() and not destination.is_symlink(),
            "Fresh outside-Git export destination required")
    if output_root.exists():
        info = output_root.lstat()
        require(stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid(), "Owned ordinary run output root required")
    return destination


def validate_numeric_admission(configuration, fixed_gate, trajectory_gate, consumed_samples, stream_state):
    require(configuration.get("input") == "native_s" and configuration.get("smoke") is False,
            "Only full native-S numerical comparisons can export")
    require(configuration.get("fixed_batches") == 20 and configuration.get("trajectory_updates") == 500,
            "Exact20batch/500update configuration required")
    require(fixed_gate.get("pass") is True and fixed_gate.get("batches") == 20
            and len(fixed_gate.get("results", ())) == 20, "Fixed20-batch gate not complete/pass")
    for number, row in enumerate(fixed_gate["results"]):
        require(row.get("batch") == number and row.get("pass") is True, "Every fixed batch must pass in order")
        for key, tolerance in (("forward", 1e-5), ("gradient", 1e-4)):
            detail = row[key]
            require(detail.get("pass") is True and detail.get("tolerance") == tolerance,
                    "Original per-tensor A thresholds must remain unchanged")
            require(isinstance(detail.get("tensors"), list) and detail["tensors"], "Complete per-tensor gate rows required")
            for tensor in detail["tensors"]:
                require(tensor.get("pass") is True, "An individual A tensor failed")
                if "relative_l2" in tensor:
                    error = tensor["relative_l2"]
                    require(type(error) in (int, float) and math.isfinite(error) and 0 <= error <= tolerance,
                            "Invalid individual A tensor error")
                else:
                    require(tensor.get("reason") == "both_disabled", "Unexpected missing-gradient admission")
    require(trajectory_gate.get("pass") is True and trajectory_gate.get("updates") == 500
            and len(trajectory_gate.get("results", ())) == 500, "Paired500-update gate not complete/pass")
    for step, row in enumerate(trajectory_gate["results"], 1):
        error = row.get("relative_difference")
        require(row.get("step") == step and row.get("pass") is True and type(error) in (int, float)
                and math.isfinite(error) and 0 <= error <= 1e-3, "Every original trajectory point must pass")
    require(type(consumed_samples) is int and consumed_samples > 0
            and stream_state.get("committed_base_samples") == consumed_samples,
            "Actual committed base-record clock differs")
    backbone = configuration["model"]["backbone"]
    require((backbone["dim"], backbone["layers"]) == (512, 6), "Primary H0 export requires512x6")
    require(configuration["candidate"]["precision"] == "fp32", "This is not a bf16 export admission protocol")


def verify_source_inventory(configuration, repository_root):
    root = Path(repository_root).absolute()
    inventory = configuration.get("source_sha256")
    require(isinstance(inventory, dict) and inventory, "Complete runtime source inventory required")
    required = {"tools/model_v3/paired_a_acceptance.py", "tools/model_v3/a_checkpoint_export.py",
                "current/phychem_mfm/training/checkpoint.py", "current/phychem_mfm/model/v3_performance.py"}
    require(required <= set(inventory), "Export/standard-format sources must have been bound before training")
    for name, expected in inventory.items():
        relative = Path(name)
        require(not relative.is_absolute() and ".." not in relative.parts and re.fullmatch(r"[0-9a-f]{64}", expected),
                "Invalid repository source binding")
        source = root / relative
        require(not source.is_symlink() and source.is_file() and source.resolve().is_relative_to(root.resolve()),
                "Bound source is no longer an ordinary repository file")
        require(hashlib.sha256(source.read_bytes()).hexdigest() == expected, "Bound source bytes changed: " + name)
    return canonical(inventory)


def h0_training_recipe(configuration):
    recipe = deepcopy(configuration["model"])
    recipe.update(supervision=deepcopy(configuration["supervision"]), loss=deepcopy(configuration["loss_weights"]),
        optimizer=deepcopy(configuration["optimizer"]), schedule=deepcopy(configuration["schedule"]),
        training={"seed": configuration["seed"], "purpose": "paired_A_diagnostic_H0_export", "resume_supported": False},
        phase1={"performance_options": deepcopy(configuration["candidate"]),
                "deterministic_controls": deepcopy(configuration.get("deterministic_controls")),
                "export_scope": "H0_only_no_A_resume"})
    return recipe


def write_standard_h0_bundle(directory, *, model, optimizer, configuration, provenance, source_metadata):
    """Serialization primitive, not admission: deliberately does not create READY.

    CPU unit roundtrips may use this primitive with explicit synthetic provenance.
    Production publication is exclusively export_candidate_checkpoint below.
    """
    import torch
    from phychem_mfm.training import checkpoint as standard
    directory = Path(directory)
    require(directory.is_dir() and not directory.is_symlink(), "Fresh owned bundle directory required")
    require(standard.CHECKPOINT_FORMAT_VERSION == 1, "Review a new standard checkpoint format before exporting")
    recipe = h0_training_recipe(configuration)
    environment = standard.environment_fingerprint()
    environment["torch"] = str(environment["torch"])
    # Keep standard save_training_checkpoint format-v1 field names/semantics.
    # It has no environment hook; only this new adapter normalizes TorchVersion.
    # No monkeypatch or safe-global allowlist is installed on the original API.
    payload = {
        "format_version": standard.CHECKPOINT_FORMAT_VERSION,
        "architecture_type": model.architecture_type,
        "task_route": recipe.get("architecture", {}).get("task_route"),
        "task_route_per_task": model.task_route_config.to_dict(),
        "model_config": model.config_dict(), "backbone_config": dict(model.backbone_config),
        "supervision": dict(recipe["supervision"]), "loss_weights": dict(recipe["loss"]),
        "schedule": dict(recipe["schedule"]), "optimizer_config": dict(recipe["optimizer"]),
        "dataset_manifest": deepcopy(configuration["data_version"]),
        "semantic_config": standard.semantic_config(recipe),
        "semantic_config_sha256": standard.contract_hash(standard.semantic_config(recipe)),
        "dataset_manifest_sha256": standard.contract_hash(configuration["data_version"]),
        "seed": int(configuration["seed"]), "global_exposure_step": int(provenance["consumed_base_records"]),
        "optimizer_update_step": int(provenance["optimizer_updates"]), "source": deepcopy(source_metadata),
        "environment": environment, "checkpoint_type": "A_diagnostic_candidate_H0_only_no_resume",
        "model_state": model.state_dict(), "optimizer_state": optimizer.state_dict(),
        "scheduler_state": {"kind": "none_fixed_lr_diagnostic", "used_during_training": False, "resume_supported": False},
        "extra": {"H0_export_provenance": deepcopy(provenance), "A_resume_supported": False}, "discovery": {},
    }
    checkpoint_path = directory / "candidate.pt"
    require(not checkpoint_path.exists(), "No checkpoint overwrite is allowed")
    write_json(directory / "model_configuration.json", recipe)
    write_json(directory / "a_run_configuration.json", configuration)
    write_json(directory / "provenance.json", provenance)
    standard._atomic_torch_save(payload, checkpoint_path)
    with checkpoint_path.open("rb") as stream:
        os.fsync(stream.fileno())
    return {"checkpoint": {**file_ref(checkpoint_path), "state_key": "model_state"},
            "model_configuration": file_ref(directory / "model_configuration.json"),
            "a_run_configuration": file_ref(directory / "a_run_configuration.json"),
            "provenance": file_ref(directory / "provenance.json")}


def verify_h0_bundle(references, *, expected_code_sha, expected_source_sha256):
    """Validate provenance and standard weights-only bytes before generic H0 load."""
    import torch
    from phychem_mfm.phase1.v3_encoder_bridge import load_encoder_pair, source_model_configuration
    from phychem_mfm.phase1.v3_dev_panel import canonical as model_sha
    def read(ref, *, as_json=False):
        require(file_ref(ref["path"]) == {key: ref[key] for key in ("path", "sha256", "bytes")},
                "Bundle source file bytes differ")
        raw = Path(ref["path"]).read_bytes()
        require(len(raw) == ref["bytes"] and hashlib.sha256(raw).hexdigest() == ref["sha256"],
                "Bundle source file bytes changed while reading")
        return json.loads(raw) if as_json else raw
    provenance = read(references["provenance"], as_json=True)
    configuration = read(references["a_run_configuration"], as_json=True)
    recipe = read(references["model_configuration"], as_json=True)
    require(provenance["code_sha"] == expected_code_sha and provenance["source_inventory_sha256"] == expected_source_sha256,
            "Export code/source provenance differs from expected binding")
    require(canonical(configuration["source_sha256"]) == expected_source_sha256,
            "Export source inventory contents differ")
    raw = read(references["checkpoint"])
    payload = torch.load(io.BytesIO(raw), map_location="cpu", weights_only=True)
    require(payload.get("format_version") == 1 and payload["source"]["git_commit"] == expected_code_sha
            and payload["source"]["source_sha256"] == expected_source_sha256,
            "Checkpoint source metadata differs from expected binding")
    require(payload["source"].get("source_files") == configuration["source_sha256"],
            "Checkpoint source file inventory differs from run configuration")
    require(payload["extra"]["H0_export_provenance"] == provenance, "Checkpoint provenance and sidecar differ")
    del payload, raw
    # Generic builder forks CPU RNG but torch.manual_seed also affects CUDA.
    # Protect every visible CUDA RNG here without changing the original bridge.
    with torch.random.fork_rng(devices=list(range(torch.cuda.device_count()))):
        pair = load_encoder_pair(references["checkpoint"], references["model_configuration"],
            architecture_sha256=model_sha(source_model_configuration(recipe)), pretraining_seed=configuration["seed"],
            reference_kind="primary", expected_state_key="model_state")
    return pair


def export_candidate_checkpoint(destination, *, output_root, repository_root=None, model=None, optimizer=None,
                                configuration=None, fixed_gate=None, trajectory_gate=None,
                                consumed_samples=None, stream_state=None, output_budget_bytes=2*1024**3):
    if destination is None:
        return None
    started = time.monotonic()
    require(repository_root is not None and model is not None and optimizer is not None, "Export context missing")
    target = validate_export_destination(destination, output_root=output_root, repository_root=repository_root)
    validate_numeric_admission(configuration, fixed_gate, trajectory_gate, consumed_samples, stream_state)
    require(configuration.get("configuration_sha256") == canonical({key: value for key, value in configuration.items()
            if key != "configuration_sha256"}), "Original A run configuration hash differs")
    source_sha = verify_source_inventory(configuration, repository_root)
    require(getattr(model, "v3_performance_options", None) == configuration["candidate"],
            "Candidate runtime options differ from the recorded configuration")
    require(re.fullmatch(r"[0-9a-f]{40}", configuration["code_sha"]) and re.fullmatch(r"[0-9a-f]{40}", configuration["prereg_sha"]),
            "Full actual/public code references required")
    root = Path(output_root).absolute()
    references = {}
    for name, expected in (("configuration", configuration), ("fixed_batch_gate", fixed_gate), ("trajectory_gate", trajectory_gate)):
        ref = file_ref(root / (name + ".json"))
        actual = json.loads(Path(ref["path"]).read_text())
        require(actual == expected, "Committed gate/configuration source changed: " + name)
        references[name] = ref
    for name in ("consumption.jsonl", "reference_history.jsonl", "candidate_history.jsonl"):
        references[name] = file_ref(root / name)
    from runtime_monitor import owned_output_bytes
    budget = min(output_budget_bytes, int(os.environ.get("MODEL_V3_CHILD_OUTPUT_BUDGET_BYTES", output_budget_bytes)))
    require(32 * 1024**2 <= budget <= 2 * 1024**3, "Original bounded output cap required")
    remaining = budget - owned_output_bytes(root) - 32 * 1024**2
    require(remaining > 0, "No export space within original output budget/reserve")
    target.mkdir(mode=0o700, exist_ok=False)
    provenance = {"schema": "model_v3_A_H0_export_provenance_v1", "full_native_A_numeric_gates_passed": True,
        "purpose": "development_H0_panel_and_encoder_performance", "formal_pretraining_complete": False,
        "A_resume_supported": False, "optimizer_updates": 500, "consumed_base_records": consumed_samples,
        "consumed_sample_unit": "existing_S_base_records_not_D5_uniform_molecules",
        "committed_stream_state": deepcopy(stream_state), "code_sha": configuration["code_sha"],
        "prereg_sha": configuration["prereg_sha"], "seed": configuration["seed"],
        "source_inventory_sha256": source_sha, "source_files": deepcopy(configuration["source_sha256"]),
        "performance_options": deepcopy(configuration["candidate"]),
        "deterministic_controls": deepcopy(configuration.get("deterministic_controls")),
        "data_version": deepcopy(configuration["data_version"]), "gate_and_raw_configuration_files": references,
        "scientific_timing_excludes_this_export": True, "outer_job_terminal_not_asserted_inside_child": True}
    source = {"git_commit": configuration["code_sha"], "git_dirty": None, "source_sha256": source_sha,
              "source_files": deepcopy(configuration["source_sha256"]), "origin": "explicit_A_runtime_source_bindings"}
    previous_limit = resource.getrlimit(resource.RLIMIT_FSIZE)
    finite_limit = min(remaining, previous_limit[0]) if previous_limit[0] != resource.RLIM_INFINITY else remaining
    import torch
    rng_before = rng_fingerprint()
    with torch.random.fork_rng(devices=list(range(torch.cuda.device_count()))):
        try:
            resource.setrlimit(resource.RLIMIT_FSIZE, (finite_limit, previous_limit[1]))
            bundle = write_standard_h0_bundle(target, model=model, optimizer=optimizer, configuration=configuration,
                                             provenance=provenance, source_metadata=source)
        finally:
            resource.setrlimit(resource.RLIMIT_FSIZE, previous_limit)
        # No unsafe pickle fallback, global allowlist mutation or training update.
        pair = verify_h0_bundle(bundle, expected_code_sha=configuration["code_sha"], expected_source_sha256=source_sha)
        h0_provenance = deepcopy(pair.provenance)
        del pair
    rng_after = rng_fingerprint()
    require(rng_before == rng_after, "H0 export changed the training Torch CPU/CUDA RNG")
    require(owned_output_bytes(root) <= budget - 16 * 1024**2, "Export consumed finalization reserve")
    ready = {"schema": "model_v3_A_H0_export_ready_v1", "status": "H0_BYTES_VERIFIED_PENDING_OUTER_JOB_TERMINAL",
        **bundle, "architecture_sha256": h0_provenance["architecture_sha256"], "pretraining_seed": configuration["seed"],
        "H0_loader_provenance": h0_provenance,
        "training_rng_before": rng_before, "training_rng_after": rng_after, "training_rng_unchanged": True,
        "source_inventory_sha256": source_sha, "code_sha": configuration["code_sha"],
        "optimizer_updates": 500, "consumed_base_records": consumed_samples, "resume_supported": False,
        "export_elapsed_seconds": time.monotonic() - started,
        "generic_checkpoint_schema": "source_training_checkpoint_v1"}
    write_json(target / "READY.json", ready)
    return {"ready": file_ref(target / "READY.json"), "export_elapsed_seconds": time.monotonic() - started,
            "bytes": owned_output_bytes(target), "resume_supported": False}
