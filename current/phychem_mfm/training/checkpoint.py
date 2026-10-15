from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping

import torch

from ..supervision import SupervisionVariant


CHECKPOINT_FORMAT_VERSION = 1


def source_provenance(project_root: str | Path) -> dict[str, object]:
    root = Path(project_root).resolve()
    commit = os.environ.get("PHYCHEM_SOURCE_COMMIT", "unavailable")
    dirty_env = os.environ.get("PHYCHEM_SOURCE_DIRTY")
    dirty = None if dirty_env is None else dirty_env.strip().lower() not in {"0", "false", "no"}
    try:
        commit = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
        dirty = bool(subprocess.check_output(["git", "-C", str(root), "status", "--porcelain"], text=True).strip())
    except (OSError, subprocess.CalledProcessError):
        head = root / ".git" / "HEAD"
        if commit == "unavailable" and head.is_file():
            head_value = head.read_text(encoding="utf-8").strip()
            if head_value.startswith("ref: "):
                ref_name = head_value[5:]
                ref_path = root / ".git" / ref_name
                if ref_path.is_file():
                    commit = ref_path.read_text(encoding="utf-8").strip()
                else:
                    packed_refs = root / ".git" / "packed-refs"
                    if packed_refs.is_file():
                        for line in packed_refs.read_text(encoding="utf-8").splitlines():
                            if line and not line.startswith(("#", "^")):
                                value, name = line.split(" ", 1)
                                if name == ref_name:
                                    commit = value
                                    break
            elif head_value:
                commit = head_value
    digest = hashlib.sha256()
    suffixes = {".py", ".yaml", ".yml", ".json", ".toml", ".sh", ".sbatch"}
    source_paths = [path for path in root.iterdir() if path.is_file() and path.suffix in suffixes]
    for directory in ("phychem_mfm", "configs", "scripts", "tools", "tests"):
        source_directory = root / directory
        if source_directory.exists():
            source_paths.extend(path for path in source_directory.rglob("*")
                                if path.is_file() and path.suffix in suffixes)
    for path in sorted(source_paths):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return {"git_commit": commit, "git_dirty": dirty, "source_sha256": digest.hexdigest()}


def semantic_config(config: Mapping[str, Any]) -> dict[str, Any]:
    """Scientific and optimization choices; excludes output/logging locations."""
    return {key: dict(config.get(key, {})) for key in
            ("architecture", "backbone", "expert", "head", "supervision", "loss",
             "schedule", "optimizer", "training", "phase1")}


def contract_hash(value: Mapping[str, Any]) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def environment_fingerprint() -> dict[str, object]:
    payload = {
        "python": sys.version,
        "platform": platform.platform(),
        "torch": torch.__version__,
        "cuda_runtime": torch.version.cuda,
        "cuda_available": torch.cuda.is_available(),
    }
    if torch.cuda.is_available():
        payload["gpu_names"] = [torch.cuda.get_device_name(index) for index in range(torch.cuda.device_count())]
    return payload


def _atomic_torch_save(payload: Mapping[str, Any], destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(prefix=destination.name, suffix=".tmp", dir=destination.parent)
    os.close(handle)
    try:
        torch.save(dict(payload), temp_name)
        os.replace(temp_name, destination)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def save_training_checkpoint(
    path: str | Path,
    *,
    model,
    optimizer,
    scheduler,
    config: Mapping[str, Any],
    supervision: Mapping[str, Any],
    dataset_manifest: Mapping[str, Any],
    exposure_step: int,
    optimizer_update_step: int,
    checkpoint_type: str,
    project_root: str | Path,
    source_metadata: Mapping[str, Any] | None = None,
    extra: Mapping[str, Any] | None = None,
    discovery_metadata: Mapping[str, Any] | None = None,
) -> None:
    payload = {
        "format_version": CHECKPOINT_FORMAT_VERSION,
        "architecture_type": model.architecture_type,
        "task_route": config.get("architecture", {}).get("task_route"),
        "task_route_per_task": model.task_route_config.to_dict(),
        "model_config": model.config_dict(),
        "backbone_config": dict(model.backbone_config),
        "supervision": dict(supervision),
        "loss_weights": dict(config.get("loss", {})),
        "schedule": dict(config.get("schedule", {})),
        "optimizer_config": dict(config.get("optimizer", {})),
        "dataset_manifest": dict(dataset_manifest),
        "semantic_config": semantic_config(config),
        "semantic_config_sha256": contract_hash(semantic_config(config)),
        "dataset_manifest_sha256": contract_hash(dataset_manifest),
        "seed": int(config.get("training", {}).get("seed", 0)),
        "global_exposure_step": int(exposure_step),
        "optimizer_update_step": int(optimizer_update_step),
        "source": dict(source_metadata or source_provenance(project_root)),
        "environment": environment_fingerprint(),
        "checkpoint_type": str(checkpoint_type),
        "model_state": model.state_dict(),
        "optimizer_state": optimizer.state_dict(),
        "scheduler_state": scheduler.state_dict(),
        "extra": dict(extra or {}),
        "discovery": dict(discovery_metadata or {}),
    }
    _atomic_torch_save(payload, Path(path).resolve())


def load_training_checkpoint(path, *, model, optimizer=None, scheduler=None, expected_config=None,
                             expected_dataset_manifest=None, expected_source_sha256=None,
                             strict_semantics=None, map_location="cpu"):
    payload = torch.load(path, map_location=map_location, weights_only=False)
    if payload.get("format_version") != CHECKPOINT_FORMAT_VERSION:
        raise RuntimeError(f"Unsupported checkpoint format: {payload.get('format_version')}")
    if payload.get("architecture_type") != model.architecture_type:
        raise RuntimeError("Checkpoint architecture_type mismatch")
    if payload.get("task_route_per_task") != model.task_route_config.to_dict():
        raise RuntimeError("Checkpoint task_route_per_task mismatch")
    if payload.get("backbone_config") != dict(model.backbone_config):
        raise RuntimeError("Checkpoint backbone_config mismatch")
    if expected_config is not None:
        expected_variant = expected_config.get("supervision", {}).get("variant")
        found_variant = payload.get("supervision", {}).get("variant")
        if SupervisionVariant.parse(expected_variant).canonical_value != SupervisionVariant.parse(found_variant).canonical_value:
            raise RuntimeError(f"Checkpoint supervision mismatch: expected {expected_variant}, found {found_variant}")
    if strict_semantics is None:
        strict_semantics = expected_config is not None and expected_config.get("head", {}).get("profile") == "phase1"
    if strict_semantics:
        if expected_config is None or expected_dataset_manifest is None:
            raise RuntimeError("Phase 1 resume requires the full expected config and dataset manifest")
        if payload.get("model_config") != model.config_dict():
            raise RuntimeError("Checkpoint complete model/head semantics mismatch")
        if payload.get("semantic_config") != semantic_config(expected_config):
            raise RuntimeError("Checkpoint scientific/optimization config mismatch")
        if payload.get("semantic_config_sha256") != contract_hash(semantic_config(expected_config)):
            raise RuntimeError("Checkpoint semantic config hash mismatch")
        if payload.get("dataset_manifest_sha256") != contract_hash(expected_dataset_manifest):
            raise RuntimeError("Checkpoint dataset/split/normalizer/protocol manifest mismatch")
        if payload.get("dataset_manifest") != dict(expected_dataset_manifest):
            raise RuntimeError("Checkpoint dataset manifest contents mismatch")
        if expected_source_sha256 is not None and payload.get("source", {}).get("source_sha256") != expected_source_sha256:
            raise RuntimeError("Checkpoint source hash mismatch; create a new protocol version")
    model.load_state_dict(payload["model_state"], strict=True)
    if optimizer is not None:
        optimizer.load_state_dict(payload["optimizer_state"])
    if scheduler is not None:
        scheduler.load_state_dict(payload["scheduler_state"])
    return payload


def load_backbone_only(path, *, model, legacy_prefix: str = "backbone.", map_location="cpu") -> None:
    payload = torch.load(path, map_location=map_location, weights_only=False)
    state = payload.get("model_state", payload)
    backbone_state = {key[len(legacy_prefix) :]: value for key, value in state.items() if key.startswith(legacy_prefix)}
    expected = model.backbone.state_dict()
    if set(backbone_state) != set(expected):
        missing = sorted(set(expected).difference(backbone_state))
        unexpected = sorted(set(backbone_state).difference(expected))
        raise RuntimeError(f"Backbone key mismatch: missing={missing[:5]} unexpected={unexpected[:5]}")
    model.backbone.load_state_dict(backbone_state, strict=True)
