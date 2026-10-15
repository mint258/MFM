from __future__ import annotations

import json
import os
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .identity import canonical_sha256


REGISTRY_VERSION = 1
REUSE_STATES = {"first_pass", "transfer_ready"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ExperimentRegistry:
    """Portable JSON registry with immutable pass-specific checkpoint records."""

    def __init__(self, path: str | Path):
        self.path = Path(path).resolve()
        self.payload = self._load()

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {
                "format_version": REGISTRY_VERSION,
                "experiments": {},
                "checkpoints": {},
                "historical_artifacts": {},
                "updated_at": _utc_now(),
            }
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if int(payload.get("format_version", -1)) != REGISTRY_VERSION:
            raise RuntimeError(f"Unsupported registry version: {payload.get('format_version')}")
        return payload

    @contextmanager
    def _lock(self):
        lock_path = self.path.with_suffix(self.path.suffix + ".lock")
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with lock_path.open("a+b") as handle:
            if os.name == "nt":
                import msvcrt

                handle.seek(0)
                if handle.tell() == 0:
                    handle.write(b"0")
                    handle.flush()
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
                try:
                    yield
                finally:
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def _save_unlocked(self) -> None:
        self.payload["updated_at"] = _utc_now()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle, temp_name = tempfile.mkstemp(prefix=self.path.name, suffix=".tmp", dir=self.path.parent)
        os.close(handle)
        try:
            Path(temp_name).write_text(json.dumps(self.payload, indent=2, sort_keys=True), encoding="utf-8")
            os.replace(temp_name, self.path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)

    def save(self) -> None:
        with self._lock():
            self._save_unlocked()

    def register_experiment(self, manifest: Mapping[str, Any]) -> dict[str, Any]:
        with self._lock():
            self.payload = self._load()
            record = dict(manifest)
            recipe = str(record["recipe_hash"])
            experiment_id = str(record.get("experiment_id") or f"discovery-{recipe[:12]}")
            record["experiment_id"] = experiment_id
            record.setdefault("created_at", _utc_now())
            record["updated_at"] = _utc_now()
            existing = self.payload["experiments"].get(experiment_id)
            if existing and existing.get("recipe_hash") != recipe:
                raise RuntimeError(f"Experiment id collision: {experiment_id}")
            if existing:
                immutable = ("recipe_hash", "train_pool_hash", "validation_pool_hash")
                mismatched = [key for key in immutable if existing.get(key) != record.get(key)]
                if mismatched:
                    raise RuntimeError(f"Cannot mutate experiment identity fields: {mismatched}")
                new_record = record
                record = {**existing, **new_record}
                for nested_key in ("downstream_results", "result_paths"):
                    if nested_key in new_record:
                        record[nested_key] = {
                            **dict(existing.get(nested_key, {})),
                            **dict(new_record[nested_key]),
                        }
                record["created_at"] = existing.get("created_at", record["created_at"])
            initial_commit = str(existing.get("source_commit")) if existing and existing.get("source_commit") else str(
                record.get("source_commit", "unknown")
            )
            current_commit = str(manifest.get("source_commit", initial_commit))
            source_commits = list(existing.get("source_commits", [])) if existing else []
            for commit in (initial_commit, current_commit):
                if commit not in source_commits:
                    source_commits.append(commit)
            record["source_commit"] = initial_commit
            record["current_source_commit"] = current_commit
            record["source_commits"] = source_commits
            self.payload["experiments"][experiment_id] = record
            self._save_unlocked()
        return record

    def register_checkpoint(self, record: Mapping[str, Any]) -> dict[str, Any]:
        with self._lock():
            self.payload = self._load()
            item = dict(record)
            sha256 = str(item["checkpoint_sha256"])
            if item.get("checkpoint_state") not in REUSE_STATES | {"pass_end", "partial"}:
                raise ValueError(f"Unknown checkpoint state: {item.get('checkpoint_state')}")
            existing = self.payload["checkpoints"].get(sha256)
            item.setdefault("registered_at", existing.get("registered_at") if existing else _utc_now())
            if existing:
                evaluation_fields = {
                    "evaluations", "domain_protocol_version", "data_quality_protocol_version",
                    "data_quality_policy_hash", "validation_manifest_hash",
                    "target_adequacy_version", "energy_original_unit_metrics",
                    "charge_original_unit_metrics", "geometry_original_unit_metrics",
                    "bond_metrics", "descriptor_metrics", "per_task_fidelity",
                    "optimization_status", "target_adequacy_status",
                    "budget_status", "downstream_protocol_version", "v3_validity",
                }
                existing_identity = {key: value for key, value in existing.items() if key not in evaluation_fields}
                item_identity = {key: value for key, value in item.items() if key not in evaluation_fields}
                # transfer_ready_status is an evaluated status in v3 but was part
                # of the original immutable record in v2. Ignore only that field.
                existing_identity.pop("transfer_ready_status", None)
                item_identity.pop("transfer_ready_status", None)
                if canonical_sha256(existing_identity) != canonical_sha256(item_identity):
                    raise RuntimeError(f"Checkpoint hash collision or mutable identity record: {sha256}")
                item = {**item, **{key: existing[key] for key in evaluation_fields if key in existing}}
                if "transfer_ready_status" in existing and "target_adequacy_version" in existing:
                    item["transfer_ready_status"] = existing["transfer_ready_status"]
            self.payload["checkpoints"][sha256] = item
            self._save_unlocked()
        return item

    def update_experiment(self, experiment_id: str, updates: Mapping[str, Any]) -> dict[str, Any]:
        """Merge result metadata without permitting recipe identity mutation."""

        with self._lock():
            self.payload = self._load()
            if experiment_id not in self.payload["experiments"]:
                raise KeyError(f"Unknown experiment_id: {experiment_id}")
            existing = dict(self.payload["experiments"][experiment_id])
            immutable = {
                key: existing.get(key)
                for key in ("recipe_hash", "train_pool_hash", "validation_pool_hash", "source_commit")
            }
            merged = {**existing, **dict(updates)}
            for nested_key in ("downstream_results", "result_paths"):
                if nested_key in updates:
                    merged[nested_key] = {**dict(existing.get(nested_key, {})), **dict(updates[nested_key])}
            changed = [key for key, value in immutable.items() if merged.get(key) != value]
            if changed:
                raise RuntimeError(f"Cannot mutate experiment identity fields: {changed}")
            merged["updated_at"] = _utc_now()
            self.payload["experiments"][experiment_id] = merged
            self._save_unlocked()
            return merged

    def update_checkpoint_evaluation(self, checkpoint_sha256: str, updates: Mapping[str, Any]) -> dict[str, Any]:
        """Attach versioned evaluation metadata without mutating checkpoint identity.

        Checkpoint bytes and training provenance remain immutable. Re-evaluation
        is intentionally replaceable only under its protocol version so a v2
        result can coexist with a v3 result without pretending they are equal.
        """

        with self._lock():
            self.payload = self._load()
            sha256 = str(checkpoint_sha256)
            if sha256 not in self.payload["checkpoints"]:
                raise KeyError(f"Unknown checkpoint_sha256: {sha256}")
            record = dict(self.payload["checkpoints"][sha256])
            version = str(updates.get("target_adequacy_version", "unknown"))
            evaluations = dict(record.get("evaluations", {}))
            evaluations[version] = dict(updates)
            record["evaluations"] = evaluations
            for key in (
                "domain_protocol_version", "data_quality_protocol_version", "data_quality_policy_hash",
                "validation_manifest_hash", "target_adequacy_version",
                "energy_original_unit_metrics", "charge_original_unit_metrics",
                "geometry_original_unit_metrics", "bond_metrics", "descriptor_metrics",
                "per_task_fidelity", "optimization_status", "target_adequacy_status",
                "budget_status", "transfer_ready_status", "downstream_protocol_version",
                "v3_validity",
            ):
                if key in updates:
                    record[key] = updates[key]
            self.payload["checkpoints"][sha256] = record
            self._save_unlocked()
            return record

    def register_historical(self, record: Mapping[str, Any]) -> dict[str, Any]:
        with self._lock():
            self.payload = self._load()
            item = dict(record)
            artifact_id = str(item["artifact_id"])
            existing = self.payload["historical_artifacts"].get(artifact_id)
            item.setdefault("registered_at", existing.get("registered_at") if existing else _utc_now())
            self.payload["historical_artifacts"][artifact_id] = item
            self._save_unlocked()
        return item

    def query_reusable(self, recipe: str, checkpoint_state: str) -> list[dict[str, Any]]:
        if checkpoint_state not in REUSE_STATES:
            raise ValueError(f"checkpoint_state must be one of {sorted(REUSE_STATES)}")
        with self._lock():
            self.payload = self._load()
            experiment_ids = {
                key
                for key, value in self.payload["experiments"].items()
                if value.get("recipe_hash") == recipe
            }
            return [
                value
                for value in self.payload["checkpoints"].values()
                if value.get("experiment_id") in experiment_ids
                and (
                    value.get("checkpoint_state") == checkpoint_state
                    or checkpoint_state in value.get("aliases", [])
                )
            ]

    def assert_submit_allowed(self, recipe: str, checkpoint_state: str) -> None:
        matches = self.query_reusable(recipe, checkpoint_state)
        if matches:
            paths = [str(item.get("path")) for item in matches]
            raise RuntimeError(f"EXACT_REUSABLE checkpoint already exists for {checkpoint_state}: {paths}")
