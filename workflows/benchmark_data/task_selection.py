"""Active benchmark endpoint selector; historical B0 source records remain unchanged.

Use this at the task-enumeration boundary before B1 fitting and every later
evaluation stage. This policy is independent of source acquisition and B0 QA.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath

DEFAULT_POLICY = Path(__file__).resolve().parents[2] / "configs" / "benchmark_data" / "B1.deferred_tasks.json"


def canonical_task_key(dataset: str, source_task: str) -> str:
    group = str(dataset).strip().casefold()
    original = str(source_task).strip().replace("\\", "/")
    if not group or not original:
        raise ValueError("Missing benchmark group or source task")
    parts = PurePosixPath(original).parts
    if group == "tdc_admet":
        if len(parts) == 3 and parts[0].casefold() == "admet_group" and parts[-1].casefold() in {"train_val.csv", "test.csv"}:
            task = parts[1]
        elif len(parts) == 1 and not parts[0].endswith(".csv"):
            task = parts[0]
        else:
            raise ValueError("Unexpected official group member path")
    else:
        task = parts[-1]
    return group + "::" + task.casefold()


def task_fingerprint(dataset: str, source_task: str) -> str:
    return hashlib.sha256(canonical_task_key(dataset, source_task).encode("utf-8")).hexdigest()


def load_deferred_policy(path: str | Path = DEFAULT_POLICY) -> set[str]:
    policy = json.loads(Path(path).read_text(encoding="utf-8"))
    values = policy.get("fingerprint_values", [])
    if policy.get("schema") != "MFM_DEFERRED_BENCHMARK_TASKS_V1":
        raise ValueError("Unrecognized deferred evaluation policy")
    if policy.get("status") != "EXCLUDE_FROM_CURRENT_EVALUATION":
        raise ValueError("Deferred endpoint policy is not active")
    if policy.get("deferred_task_count") != 5 or len(values) != 5 or len(set(values)) != 5:
        raise ValueError("Deferred endpoint registry is incomplete or duplicated")
    if any(len(value) != 64 or any(c not in "0123456789abcdef" for c in value) for value in values):
        raise ValueError("Malformed endpoint fingerprint")
    return set(values)


def is_active_task(dataset: str, source_task: str, *, fingerprints: set[str] | None = None) -> bool:
    pending = load_deferred_policy() if fingerprints is None else fingerprints
    return task_fingerprint(dataset, source_task) not in pending


def select_active_tasks(
    tasks: list[tuple[str, str]],
    *,
    fingerprints: set[str] | None = None,
    verify_full_inventory: bool = False,
) -> list[tuple[str, str]]:
    """Return eligible task identifiers without changing source rows.

    Set verify_full_inventory=True only when the entire known candidate
    inventory has been enumerated, before any B1 model fitting. Fail closed
    rather than silently missing a deferred task due to a renamed source.
    """
    pending = load_deferred_policy() if fingerprints is None else fingerprints
    included: list[tuple[str, str]] = []
    observed: set[str] = set()
    for dataset, source_task in tasks:
        marker = task_fingerprint(dataset, source_task)
        if marker in pending:
            observed.add(marker)
        else:
            included.append((dataset, source_task))
    if verify_full_inventory and observed != pending:
        raise ValueError(f"Deferred policy coverage mismatch: {len(observed)} / {len(pending)}")
    return included
