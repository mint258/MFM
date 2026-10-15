"""Read-only, fail-closed review of a frozen Phase 1 formal protocol.

Exported scheduler text and arbitrary JSON assertions never authorize training.
A live pass additionally checks standard node configuration files and a local
observation inside the matching Slurm allocation. Hashes record provenance and
integrity; they are not a new authorization or approval procedure.
This module never creates a protocol, contacts a scheduler, or changes jobs.
"""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
import errno
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
from typing import Any, Mapping

from .strategy_contract import contrast_hash_fields, contrast_run_count, validated_contrasts
from .paired_statistics import validate_analysis_plan
from .pretraining_scientific_authority import (
    AUTHORITY_FIELD, ANALYSIS_FIELD, pretraining_only,
    validate_scope_declaration, verify_pretraining_scientific_authority,
)
from .trial_source_bridge import BRIDGE_FIELD, verify_trial_producer_consumer_bridge


PROTOCOL_SCHEMA = "phase1_formal_protocol_v1"
CONFIG_SOURCE_NAMES = ("gres", "cgroup", "sshd", "pam")
VARIANTS = ("none", "S", "D", "P", "SD", "SP", "DP", "SDP")
HASH_PATTERN = re.compile(r"[0-9a-f]{64}\Z")
SHARED_GPU_POLICY = "user_accepted_shared_gpu"
SHARED_GPU_STATUS = "PASS_LIVE_SHARED_GPU_USER_ACCEPTED"


def shared_gpu_policy(protocol) -> bool:
    """Explicit execution policy; it never claims GPU allocation or isolation."""
    return _get(protocol, "compute.gpu_isolation_policy") == SHARED_GPU_POLICY

# SHA fields identify actual read-only artifacts, not just JSON booleans.
REQUIRED_HASH_FIELDS = (
    "data.source_manifest_sha256", "data.split_manifest_sha256",
    "data.decontamination_sha256", "data.normalization_sha256",
    "data.normalization_train_ids_sha256", "source.source_sha256",
    "encoder.architecture_sha256", "tasks.target_manifest_sha256",
    "tasks.label_contract_sha256", "strategy.loss_policy_sha256",
    "strategy.schedule_sha256", "downstream.split_manifest_sha256",
    "downstream.readout_config_sha256", "downstream.final_evaluation_config_sha256",
    "downstream.statistics.analysis_plan_sha256",
    "trial_evidence.summary_sha256", "trial_evidence.training_log_sha256",
    "trial_evidence.gradient_checks_sha256", "trial_evidence.tracking_sha256",
)
REQUIRED_TEXT_FIELDS = (
    "data.train_source", "source.commit", "encoder.name", "strategy.name",
    "pretraining.budget.equivalence_rule", "pretraining.checkpoint_rule.selection_metric",
    "downstream.statistics.method", "downstream.statistics.primary_metric",
    "downstream.statistics.multiple_comparison_rule", "compute.site",
    "compute.partition", "compute.gpu_model",
    "storage.checkpoint_retention", "storage.tracker_retention", "tracking.provider",
)
REQUIRED_POSITIVE_FIELDS = (
    "pretraining.budget.optimizer_steps_per_condition",
    "pretraining.budget.structures_per_condition", "pretraining.budget.gpu_hours_per_condition",
    "pretraining.checkpoint_rule.save_every_steps", "pretraining.checkpoint_rule.keep_checkpoints",
    "downstream.budget.max_gpu_hours_total", "downstream.budget.max_trials",
    "compute.nodes_per_job", "compute.gpus_per_job", "compute.cpus_per_task",
    "compute.max_concurrent_jobs", "compute.max_gpu_hours_total", "compute.max_walltime_hours",
    "compute.min_gpu_memory_gib", "compute.min_free_gpu_memory_gib",
    "storage.quota_bytes", "storage.available_bytes", "storage.reserve_bytes",
    "storage.max_run_bytes", "storage.max_total_artifact_bytes",
)


def _required_hash_fields(protocol):
    if pretraining_only(protocol):
        return tuple(field for field in REQUIRED_HASH_FIELDS if field != ANALYSIS_FIELD) + (AUTHORITY_FIELD,)
    return REQUIRED_HASH_FIELDS


@dataclass(frozen=True)
class GateIssue:
    code: str
    message: str


@dataclass
class GateReport:
    status: str
    issues: list[GateIssue] = field(default_factory=list)
    protocol_sha256: str = ""
    reviewed_artifacts: dict[str, str] = field(default_factory=dict)
    runtime_observation: dict[str, Any] | None = None
    scope: str = "preflight only; no submission or job modification"

    @property
    def may_start_formal_training(self) -> bool:
        if self.issues:
            return False
        if self.status == "PASS_LIVE_ALLOCATION":
            return True
        observation = self.runtime_observation or {}
        return (self.status == SHARED_GPU_STATUS
                and observation.get("gpu_isolation_policy") == SHARED_GPU_POLICY
                and observation.get("gpu_protection_verified") is False)

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "may_start_formal_training": self.may_start_formal_training}


def canonical_sha256(document: Mapping[str, Any], *, omit_content_hash: bool = False) -> str:
    """Hash an already supplied document. Does not create or freeze a protocol."""
    body = {key: value for key, value in document.items() if not (omit_content_hash and key == "content_sha256")}
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                                     allow_nan=False).encode("utf-8")).hexdigest()


def _get(document: Mapping[str, Any], path: str, default=None):
    value: Any = document
    for key in path.split("."):
        if not isinstance(value, Mapping) or key not in value:
            return default
        value = value[key]
    return value


def _account_contract(protocol):
    """Keep legacy named accounts; explicitly bind inherited effective account."""
    compute = _get(protocol, "compute")
    if not isinstance(compute, Mapping):
        raise ValueError("Missing compute account contract")
    if "account_policy" not in compute:
        account = compute.get("account")
        if not isinstance(account, str) or not account.strip() or account == "(null)":
            raise ValueError("Legacy explicit account must be a nonempty string")
        return account, False
    policy = compute["account_policy"]
    if (not isinstance(policy, Mapping) or set(policy) != {"mode", "resolved_account"}
            or policy["mode"] != "inherit_site_default"
            or "account" not in compute or compute["account"] is not None):
        raise ValueError("Account inheritance requires its exact policy and null requested account")
    account = policy["resolved_account"]
    if account is not None and (not isinstance(account, str) or not account.strip()
                                or account == "(null)"):
        raise ValueError("Resolved default account must be a real name or explicit JSON null")
    return account, True


def _verify_allocation_account(protocol, job):
    expected, inherit = _account_contract(protocol)
    if "Account" not in job or not isinstance(job["Account"], str):
        raise ValueError("Actual Slurm Account field is missing/invalid")
    actual = job["Account"]
    if inherit and actual == "(null)":
        actual = None
    if actual != expected:
        raise ValueError("Allocation effective account differs from the frozen account policy")
    return {"selection": "inherit_site_default" if inherit else "explicit",
            "requested_account": None if inherit else expected,
            "effective_account": actual, "slurm_account_raw": job["Account"]}


def _timestamp(value) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.astimezone(timezone.utc) if parsed.tzinfo is not None else None
    except ValueError:
        return None


def _positive(value) -> bool:
    return isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value) and value > 0


def _hash(value) -> bool:
    return isinstance(value, str) and HASH_PATTERN.fullmatch(value) is not None


def _string_list(value) -> bool:
    return isinstance(value, list) and bool(value) and all(isinstance(item, str) and bool(item.strip()) for item in value)


def _seeds(value) -> bool:
    return (isinstance(value, list) and bool(value) and all(isinstance(seed, int) and not isinstance(seed, bool)
            and seed >= 0 for seed in value) and len(set(value)) == len(value))


def _key_values(text: str) -> dict[str, str]:
    return {key: value for key, value in re.findall(r"([A-Za-z][A-Za-z0-9_:/]*)[ \t]*=[ \t]*([^\s]+)", text or "")}


def _gpu_count(value: str | None) -> int:
    if not value or value.lower() in {"(null)", "null", "none", "n/a"}:
        return 0
    total = 0
    for part in value.split(","):
        match = re.fullmatch(r"gpu(?::[^:()]+)?:(\d+)(?:\([^)]*\))?", part)
        if match:
            total += int(match.group(1))
    return total


def _tres_gpu_count(value: str | None) -> int:
    match = re.search(r"(?:^|,)gres/gpu=(\d+)(?:,|$)", value or "")
    return int(match.group(1)) if match else 0


def _node_names(expression: str) -> set[str]:
    # Only support an explicit list or one numeric bracket range; unknown syntax
    # is not guessed, including complex heterogeneous/multi-bracket allocations.
    if "[" not in expression:
        return {name for name in expression.split(",") if name and name != "(null)"}
    match = re.fullmatch(r"([^\[\],]+)\[([0-9,-]+)\]", expression)
    if not match:
        return set()
    names = set()
    prefix, ranges = match.groups()
    for item in ranges.split(","):
        if "-" in item:
            start, stop = item.split("-", 1)
            if int(stop) < int(start) or int(stop) - int(start) > 1024:
                return set()
            width = len(start) if start.startswith("0") else 0
            names.update(prefix + str(index).zfill(width) for index in range(int(start), int(stop) + 1))
        else:
            names.add(prefix + item)
    return names


def _read_artifact(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _configuration_lines(path: Path, kind: str, reviewed: dict[str, str], seen=None) -> list[str]:
    """Read standard configuration, including ordinary local Include files."""
    seen = set() if seen is None else seen
    resolved = path.resolve()
    if resolved in seen or len(seen) > 32:
        raise ValueError(f"Configuration include cycle or excessive includes: {path}")
    seen.add(resolved)
    reviewed[f"site_config/{resolved}"] = _read_artifact(resolved)
    result = []
    for raw in resolved.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        included = []
        if kind == "sshd" and parts[0].lower() == "include":
            for expression in parts[1:]:
                target = Path(expression)
                target = target if target.is_absolute() else resolved.parent / target
                matches = sorted(target.parent.glob(target.name))
                if not matches:
                    raise ValueError(f"Unresolved SSH configuration include: {expression}")
                included.extend(matches)
        elif kind == "pam" and parts[0] == "@include" and len(parts) == 2:
            included = [resolved.parent / parts[1]]
        elif kind == "pam" and len(parts) >= 3 and parts[1] in {"include", "substack"}:
            included = [resolved.parent / parts[2]]
        if included:
            for child in included:
                result.extend(_configuration_lines(child, kind, reviewed, seen))
        else:
            result.append(line)
    return result


def _site_configuration(configuration_files, config, node, configuration_node):
    """Validate existing standard node files; no custom attestation is required."""
    issues, reviewed, lines = [], {}, {}
    add = lambda code, message: issues.append(GateIssue(code, message))
    if configuration_node != node.get("NodeName"):
        add("site_config.node", "Standard configuration exports must identify the reviewed node")
    for name in CONFIG_SOURCE_NAMES:
        path = (configuration_files or {}).get(name)
        try:
            if path is None:
                raise ValueError(f"Missing standard {name} configuration file")
            lines[name] = _configuration_lines(Path(path), name, reviewed)
        except (OSError, ValueError, TypeError) as error:
            add("site_config.unverified", str(error))
            lines[name] = []
    cgroup = _key_values("\n".join(lines["cgroup"]))
    if cgroup.get("ConstrainDevices", "").lower() != "yes":
        add("site_config.devices", "Actual cgroup configuration must enable ConstrainDevices=yes")
    minors = []
    for line in lines["gres"]:
        values = _key_values(line)
        if values.get("Name") != "gpu":
            continue
        if "NodeName" in values and node.get("NodeName") not in _node_names(values["NodeName"]):
            continue
        files = _node_names(values.get("File", ""))
        if not files or "CountOnly" in values.get("Flags", "") or any(
            re.fullmatch(r"/dev/nvidia\d+", device) is None for device in files
        ):
            add("site_config.gres_mapping", "Standard gres.conf or slurmd -G output must map GPU GRES to real device files")
            continue
        minors.extend(sorted(int(device.removeprefix("/dev/nvidia")) for device in files))
    auto_nvml = not minors and _key_values("\n".join(lines["gres"])).get("AutoDetect", "").lower() == "nvml"
    if not auto_nvml and (len(minors) != _gpu_count(node.get("Gres")) or len(set(minors)) != len(minors) or not minors):
        add("site_config.gres_mapping", "Node GPU GRES count and unique configured device files must agree")
    # Slurm requires File entries in increasing numeric order. GRES indices are
    # mapped through those files, never guessed from NVML/CUDA index equality.
    if minors != sorted(minors):
        add("site_config.gres_mapping", "GPU device File entries must be in increasing numeric order")
    bindings = {"__autodetect_nvml__": _gpu_count(node.get("Gres"))} if auto_nvml else {
        str(index): minor for index, minor in enumerate(minors)
    }
    ssh = {}
    for line in lines["sshd"]:
        fields = line.split(None, 1)
        key, value = fields[0], fields[1] if len(fields) > 1 else ""
        ssh.setdefault(key.lower(), value.strip())
        if key.lower() == "match":
            add("site_config.ssh_unknown", "Conditional SSH configuration requires effective standard configuration evidence; this parser cannot infer it")
    if ssh.get("usepam", "").lower() != "yes":
        add("site_config.ssh_pam", "sshd must actually enable UsePAM for SSH job adoption")
    methods = ssh.get("authenticationmethods", "").replace(",", " ").split()
    no_interactive = ssh.get("kbdinteractiveauthentication", ssh.get("challengeresponseauthentication", "")).lower() == "no"
    if not no_interactive and not (methods and all(method in {"publickey", "password"} for method in methods)):
        add("site_config.ssh_auth", "SSH authentication must not bypass pam_slurm_adopt via unsupported keyboard-interactive methods")
    account_rows = [line for line in lines["pam"] if line.split()[0].lstrip("-") == "account"]
    adoption_rows = [line for line in account_rows if "pam_slurm_adopt.so" in line]
    if not adoption_rows or adoption_rows[-1] != account_rows[-1]:
        add("site_config.ssh_adoption", "The complete actual SSH PAM account stack must end with pam_slurm_adopt")
    else:
        parts = adoption_rows[-1].split()
        options = _key_values(adoption_rows[-1])
        if len(parts) < 3 or parts[0] != "account" or parts[1] not in {"required", "requisite"}:
            add("site_config.ssh_adoption", "SSH adoption must be enforced, without an optional/missing-module bypass")
        if options.get("action_adopt_failure") != "deny" or options.get("action_generic_failure") != "deny":
            add("site_config.ssh_failure", "SSH adoption/generic failures must deny unconfined logins")
        if options.get("action_no_jobs", "deny") != "deny" or options.get("action_unknown", "newest") not in {"newest", "deny"}:
            add("site_config.ssh_failure", "No-job or ambiguous SSH logins must not allow unconfined access")
    if any(" sufficient " in f" {line} " or "[" in line for line in account_rows[:-1]):
        add("site_config.ssh_bypass", "An earlier PAM sufficient/conditional account rule has unverified SSH adoption bypass semantics")
    if any("pam_systemd.so" in line for line in lines["pam"]):
        add("site_config.ssh_bypass", "pam_systemd conflicts with SSH Slurm adoption in this supported configuration")
    if "contain" not in config.get("PrologFlags", "").lower().split(","):
        add("site_config.extern_step", "PrologFlags=Contain is required for SSH extern-step adoption")
    return issues, reviewed, bindings


def _live_configuration_paths(configuration_files, config) -> list[GateIssue]:
    """Live checks read real system files, not a copied JSON/text assertion."""
    slurm_conf = Path(config.get("SLURM_CONF", config.get("SlurmConf", "/etc/slurm/slurm.conf")))
    expected = {"gres": slurm_conf.parent / "gres.conf", "cgroup": slurm_conf.parent / "cgroup.conf",
                "sshd": Path("/etc/ssh/sshd_config"), "pam": Path("/etc/pam.d/sshd")}
    issues = []
    for name, system_path in expected.items():
        supplied = (configuration_files or {}).get(name)
        if supplied is None or Path(supplied).resolve() != system_path.resolve():
            issues.append(GateIssue("runtime.configuration_source", f"Live verification must read actual local system configuration: {system_path}"))
    return issues


def _shared_site_configuration(configuration_files, node, configuration_node):
    """Record existing system files without calling them isolation evidence."""
    issues, reviewed = [], {}
    if configuration_node != node.get("NodeName"):
        issues.append(GateIssue("site_config.node", "Configuration source node differs from the reviewed node"))
    for name in CONFIG_SOURCE_NAMES:
        path = (configuration_files or {}).get(name)
        if path is not None and Path(path).is_file():
            try:
                reviewed[f"site_config/{Path(path).resolve()}"] = _read_artifact(Path(path))
            except (OSError, ValueError, TypeError) as error:
                issues.append(GateIssue("site_config.unreadable", str(error)))
    return issues, reviewed, {}


def validate_protocol(protocol: Mapping[str, Any], *, now: datetime | None = None) -> list[GateIssue]:
    """Validate the frozen semantic contract; data/proof files are checked later."""
    issues: list[GateIssue] = []
    add = lambda code, message: issues.append(GateIssue(code, message))
    now = now or datetime.now(timezone.utc)
    if protocol.get("schema_version") != PROTOCOL_SCHEMA:
        add("protocol.schema", f"schema_version must be {PROTOCOL_SCHEMA}")
    frozen_at = _timestamp(protocol.get("frozen_at"))
    if protocol.get("state") != "frozen" or frozen_at is None or frozen_at > now:
        add("protocol.not_frozen", "A reviewed frozen protocol with a non-future timezone-aware frozen_at is required")
    try:
        content_hash = canonical_sha256(protocol, omit_content_hash=True)
    except (TypeError, ValueError):
        content_hash = ""
    if not _hash(protocol.get("content_sha256")) or protocol.get("content_sha256") != content_hash:
        add("protocol.content_hash", "Frozen protocol content_sha256 does not match its canonical content")
    try:
        validate_scope_declaration(protocol)
    except (TypeError, ValueError) as error:
        add("protocol.execution_scope", str(error))
    isolation_policy = _get(protocol, "compute.gpu_isolation_policy")
    if isolation_policy not in (None, "protected_slurm_gpu", SHARED_GPU_POLICY):
        add("protocol.gpu_isolation_policy", "Unknown GPU isolation execution policy")
    if shared_gpu_policy(protocol) and not pretraining_only(protocol):
        add("protocol.gpu_isolation_scope", "Accepted shared-GPU execution is limited to explicit pretraining_only scope")
    for path in _required_hash_fields(protocol):
        if not _hash(_get(protocol, path)):
            add("protocol.required_hash", f"Missing or invalid SHA-256: {path}")
    for path in REQUIRED_TEXT_FIELDS:
        value = _get(protocol, path)
        if not isinstance(value, str) or not value.strip():
            add("protocol.required_text", f"Missing concrete protocol value: {path}")
    try:
        _account_contract(protocol)
    except ValueError as error:
        add("protocol.account", str(error))
    for path in REQUIRED_POSITIVE_FIELDS:
        if not _positive(_get(protocol, path)):
            add("protocol.required_budget", f"Missing finite positive budget/resource cap: {path}")
        elif any(token in path for token in ("steps", "structures", "keep_checkpoints", "max_trials", "nodes_per_job",
                                              "gpus_per_job", "cpus_per_task", "max_concurrent_jobs", "_bytes")):
            value = _get(protocol, path)
            if not isinstance(value, int) or isinstance(value, bool):
                add("protocol.integer_budget", f"A discrete resource count must be a positive integer: {path}")
    for path in ("experiment.questions", "experiment.main_comparisons", "downstream.datasets",
                 "downstream.readouts", "downstream.modes", "downstream.main_comparisons"):
        if not _string_list(_get(protocol, path)):
            add("protocol.required_list", f"Missing nonempty explicit list: {path}")
    exact = {
        "data.decontamination_complete": True, "data.normalization_fit_split": "train",
        "encoder.encode_api": "SharedBackboneMFM.encode_atoms", "encoder.representation": "H0",
        "encoder.head_profile": "phase1", "tasks.charge_target": "MOPAC NET ATOMIC CHARGES",
        "tasks.graph_target_count": 23, "tasks.node_target_count": 6, "tasks.bond_order_only": True,
        "strategy.name": "joint", "strategy.all_enabled_tasks_positive_at_step_zero": True,
        "pretraining.paired_random_initialization.enabled": True,
        "pretraining.paired_random_initialization.initialization_source": "random",
        "pretraining.paired_random_initialization.same_seed_per_condition": True,
        "pretraining.checkpoint_rule.export_representation": "H0",
        "downstream.representation": "H0", "downstream.final_test_usage": "once_after_freeze",
        "downstream.statistics.paired": True, "compute.non_preemptible": True,
        "trial_evidence.final_status": "completed",
    }
    for path, expected in exact.items():
        actual = _get(protocol, path)
        if type(actual) is not type(expected) or actual != expected:
            add("protocol.semantic", f"{path} must be {expected!r}, got {actual!r}")
    if _get(protocol, "pretraining.variants") != list(VARIANTS):
        add("protocol.variants", "Canonical eight-condition matrix must be none/S/D/P/SD/SP/DP/SDP")
    seeds = _get(protocol, "pretraining.seeds")
    if not _seeds(seeds):
        add("protocol.pretrain_seeds", "Unique explicit nonnegative pretraining seeds are required")
    try:
        validated_contrasts(protocol)
        additional_runs = contrast_run_count(protocol)
    except (TypeError, ValueError) as error:
        add("protocol.strategy_contrasts", str(error))
        additional_runs = 0
    initialization_hashes = _get(protocol, "pretraining.paired_random_initialization.encoder_sha256_by_seed")
    if not isinstance(initialization_hashes, Mapping) or not _seeds(seeds) or (
        set(initialization_hashes) != {str(seed) for seed in seeds}
        or not all(_hash(value) for value in initialization_hashes.values())
    ):
        add("protocol.paired_initialization", "A pinned shared random-encoder artifact is required for every pretraining seed")
    if _get(protocol, "pretraining.paired_random_initialization.pretrained_checkpoint") not in (None, ""):
        add("protocol.pretrained_initialization", "Historical pretrained checkpoints cannot initialize this paired matrix")
    if not _seeds(_get(protocol, "downstream.seeds")):
        add("protocol.downstream_seeds", "Explicit downstream seeds are required")
    confidence = _get(protocol, "downstream.statistics.confidence_level")
    if not _positive(confidence) or confidence >= 1:
        add("protocol.statistics", "confidence_level must lie strictly between zero and one")
    if _get(protocol, "downstream.statistics.method") != "paired_seed_contrast_sign_flip_bootstrap_v1":
        add("protocol.statistics_method", "Statistics require an implemented, versioned paired pretraining-seed contrast method")
    if _get(protocol, "downstream.statistics.multiple_comparison_rule") != "Holm":
        add("protocol.statistics_family", "The implemented analysis plan requires explicit complete Holm families")
    if _get(protocol, "downstream.statistics.primary_metric") != "per_endpoint_declared":
        add("protocol.statistics_metric", "Metric names, units and directions must be declared for every analysis endpoint")
    selection_split = _get(protocol, "pretraining.checkpoint_rule.selection_split")
    if selection_split not in {"train", "pretrain_validation", "fixed_budget"}:
        add("protocol.checkpoint_selection", "Checkpoint selection must be frozen without final-test selection")
    bridge_hash = _get(protocol, BRIDGE_FIELD)
    if bridge_hash is not None and not _hash(bridge_hash):
        add("protocol.trial_bridge_hash", "Declared trial/source bridge requires an actual SHA-256")
    if (_get(protocol, "trial_evidence.source_sha256") != _get(protocol, "source.source_sha256")
            and not _hash(bridge_hash)):
        add("protocol.trial_source", "Trial evidence must match the exact frozen source hash")
    if _get(protocol, "trial_evidence.data_sha256") != _get(protocol, "data.source_manifest_sha256"):
        add("protocol.trial_data", "Trial evidence must match the exact frozen training-source manifest")
    tracking_mode = _get(protocol, "tracking.mode")
    if tracking_mode not in {"online", "offline_persistent", "offline_with_verified_sync"}:
        add("protocol.tracking", "Formal tracking must be online or use persistent offline records")
    if tracking_mode == "offline_persistent":
        # This freezes an explicit sync/retention plan. Actual W&B initialization
        # and its persistent directory are checked by the runner, not by a prior
        # successful network connection or an artificial approval artifact.
        for path, code in (("tracking.sync_method", "protocol.tracking_sync_method"),
                           ("storage.tracker_retention", "protocol.tracking_retention")):
            value = _get(protocol, path)
            if not isinstance(value, str) or not value.strip():
                add(code, f"Persistent offline tracking requires an explicit plan: {path}")
    if _get(protocol, "tracking.mode") == "offline_with_verified_sync" and not _hash(_get(protocol, "tracking.sync_evidence_sha256")):
        add("protocol.tracking_sync", "Legacy offline_with_verified_sync declares pinned successful sync evidence")
    if _seeds(seeds) and _positive(_get(protocol, "pretraining.budget.gpu_hours_per_condition")):
        downstream_hours = _get(protocol, "downstream.budget.max_gpu_hours_total")
        needed = (len(seeds) * 7 + additional_runs) * _get(protocol, "pretraining.budget.gpu_hours_per_condition")
        needed += downstream_hours if _positive(downstream_hours) else 0
        if not _positive(_get(protocol, "compute.max_gpu_hours_total")) or needed > _get(protocol, "compute.max_gpu_hours_total"):
            add("protocol.matrix_compute_budget", "Compute cap does not cover seven pretrained conditions for every seed, explicit strategy contrasts, and downstream trials")
    available = _get(protocol, "storage.available_bytes")
    reserve = _get(protocol, "storage.reserve_bytes")
    artifact_cap = _get(protocol, "storage.max_total_artifact_bytes")
    quota = _get(protocol, "storage.quota_bytes")
    if all(_positive(value) for value in (available, reserve, artifact_cap, quota)):
        if available > quota or reserve + artifact_cap > available:
            add("protocol.storage_budget", "Artifact cap and reserve must fit the actual available quota")
    max_run = _get(protocol, "storage.max_run_bytes")
    concurrency = _get(protocol, "compute.max_concurrent_jobs")
    if all(_positive(value) for value in (max_run, concurrency, artifact_cap)) and max_run * concurrency > artifact_cap:
        add("protocol.concurrent_storage", "Artifact cap cannot fit the declared concurrent runs")
    if _get(protocol, "compute.nodes_per_job") != 1:
        add("protocol.unsupported_multinode", "This gate currently supports single-node jobs only; multinode proof is not implemented")
    return issues


def _capture_local_observation(*, include_processes=False) -> dict[str, Any]:
    """Observe only this local allocation. No SSH, network or scheduler command.

    CUDA metadata is queried through the current process's actual device view,
    preserving scheduler-provided numeric or UUID CUDA_VISIBLE_DEVICES. No model
    operation or GPU kernel is run. Device opens close immediately; unallocated
    physical GPUs must be denied by the kernel, even if NVML hides them.
    """
    if sys.platform != "linux":
        raise RuntimeError("Live allocation verification requires Linux")
    cgroup = Path("/proc/self/cgroup").read_text(encoding="utf-8")
    import torch
    cuda_devices = []
    for index in range(torch.cuda.device_count()):
        properties = torch.cuda.get_device_properties(index)
        uuid = getattr(properties, "uuid", None)
        if uuid is None:
            raise RuntimeError("This installed CUDA/PyTorch cannot report actual visible device UUIDs")
        text_uuid = str(uuid)
        cuda_devices.append({"cuda_index": index, "uuid": text_uuid if text_uuid.startswith("GPU-") else "GPU-" + text_uuid})
    if not cuda_devices:
        raise RuntimeError("CUDA observes no assigned GPU")
    kernel_devices = []
    for path in Path("/proc/driver/nvidia/gpus").glob("*/information"):
        values = {key.strip(): value.strip() for key, _, value in (
            line.partition(":") for line in path.read_text(encoding="utf-8").splitlines()
        )}
        if not values.get("GPU UUID", "").startswith("GPU-") or not values.get("Device Minor", "").isdigit():
            raise RuntimeError("Kernel NVIDIA UUID/device-minor metadata is incomplete")
        kernel_devices.append({"uuid": values["GPU UUID"], "device_minor": int(values["Device Minor"]),
                               "pci_bus_id": path.parent.name})
    if not kernel_devices:
        raise RuntimeError("Physical NVIDIA kernel device mapping is unavailable")
    device_nodes = {int(path.name.removeprefix("nvidia")) for path in Path("/dev").glob("nvidia[0-9]*")
                    if path.name.removeprefix("nvidia").isdigit()}
    if device_nodes != {device["device_minor"] for device in kernel_devices}:
        raise RuntimeError("Kernel GPU device nodes and physical UUID inventory disagree")
    inventory = []
    for device in cuda_devices:
        result = subprocess.run(
            ["nvidia-smi", f"--id={device['uuid']}", "--query-gpu=index,minor_number,uuid,name,memory.total,memory.free",
             "--format=csv,noheader,nounits"], check=True, capture_output=True, text=True, timeout=10,
        )
        rows = list(csv.reader(io.StringIO(result.stdout)))
        if len(rows) != 1 or len(rows[0]) != 6:
            raise RuntimeError("Unknown assigned-GPU NVIDIA inventory format")
        index, minor, uuid, name, total, free = [part.strip() for part in rows[0]]
        inventory.append({"index": int(index), "device_minor": int(minor), "uuid": uuid, "name": name,
                          "memory_total_mib": float(total), "memory_free_mib": float(free)})
    access = {}
    for gpu in kernel_devices:
        try:
            descriptor = os.open(f"/dev/nvidia{gpu['device_minor']}", os.O_RDONLY | os.O_NONBLOCK)
        except OSError as error:
            if error.errno not in (errno.EACCES, errno.EPERM):
                raise RuntimeError(f"GPU device access cannot be determined: {error}") from error
            access[str(gpu["device_minor"])] = False
        else:
            os.close(descriptor)
            access[str(gpu["device_minor"])] = True
    environment_keys = ("SLURM_JOB_ID", "SLURM_JOB_GPUS", "SLURM_STEP_GPUS", "SLURM_GPUS_ON_NODE",
                        "CUDA_VISIBLE_DEVICES", "CUDA_DEVICE_ORDER")
    observation = {"captured_at": datetime.now(timezone.utc).isoformat(), "hostname": socket.gethostname().split(".")[0],
            "uid": os.getuid(), "environment": {key: os.environ.get(key, "") for key in environment_keys},
            "cgroup": cgroup, "gpu_inventory": inventory, "gpu_device_access": access,
            "cuda_devices": cuda_devices, "kernel_devices": kernel_devices,
            "runtime_environment": {"python": sys.executable, "torch": str(torch.__version__),
                                    "cuda": torch.version.cuda, "default_dtype": str(torch.get_default_dtype())}}
    if include_processes:
        processes = []
        for device in cuda_devices:
            result = subprocess.run(
                ["nvidia-smi", f"--id={device['uuid']}", "--query-compute-apps=gpu_uuid,pid",
                 "--format=csv,noheader,nounits"], check=True, capture_output=True, text=True, timeout=10)
            for row in csv.reader(io.StringIO(result.stdout)):
                if len(row) != 2 or not row[1].strip().isdigit():
                    raise RuntimeError("Unknown assigned-GPU compute-process inventory format")
                uuid, pid = row[0].strip(), int(row[1].strip())
                if not uuid.startswith("GPU-") or pid <= 0:
                    raise RuntimeError("Assigned-GPU process UUID/PID is inconsistent")
                if uuid != device["uuid"]:
                    continue  # Some NVML query versions include other GPUs.
                proc = Path("/proc") / str(pid)
                uid_row = re.search(r"^Uid:\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s*$",
                                    (proc / "status").read_text(encoding="utf-8"), re.MULTILINE)
                if uid_row is None or len(set(uid_row.groups())) != 1:
                    raise RuntimeError("Assigned-GPU process ownership cannot be verified")
                processes.append({"uuid": uuid, "pid": pid, "uid": int(uid_row.group(1)),
                                  "cgroup": (proc / "cgroup").read_text(encoding="utf-8")})
        observation["gpu_processes"] = processes
    return observation


def _check_runtime(observation, protocol, node, job, bindings, configuration_node, now) -> list[GateIssue]:
    issues = []
    add = lambda code, message: issues.append(GateIssue(code, message))
    shared = shared_gpu_policy(protocol)
    environment = observation.get("environment", {})
    job_id = environment.get("SLURM_JOB_ID", "")
    if not isinstance(job_id, str) or not job_id.isdigit() or job.get("JobId") != job_id:
        add("runtime.job_id", "Live SLURM_JOB_ID must match the exported current allocation")
    cgroup = observation.get("cgroup", "")
    if not job_id or not re.search(r"(?:^|[/_])job[_-]?" + re.escape(job_id) + r"(?:/|$)", cgroup, re.MULTILINE):
        add("runtime.cgroup", "This process is not proven to be in its Slurm job cgroup")
    uid_match = re.search(r"\((\d+)\)", job.get("UserId", ""))
    if uid_match is None or int(uid_match.group(1)) != observation.get("uid"):
        add("runtime.owner", "Allocation owner must match the local process uid")
    hostname = observation.get("hostname")
    if hostname != node.get("NodeName") or hostname not in _node_names(job.get("NodeList", "")):
        add("runtime.node", "Actual hostname must match both node export and allocated job nodes")
    if hostname != configuration_node:
        add("runtime.configuration_node", "Configuration source node does not match the actual allocation node")
    if pretraining_only(protocol):
        if hostname not in _get(protocol, "compute.allowed_nodes", []):
            add("runtime.scientific_node", "Actual node is outside the frozen scientific allowed nodes")
        expected_environment = _get(protocol, "compute.runtime_environment", {})
        actual_environment = observation.get("runtime_environment", {})
        expected_python, actual_python = expected_environment.get("python"), actual_environment.get("python")
        if not isinstance(expected_python, str) or not isinstance(actual_python, str) or (
            Path(expected_python).resolve() != Path(actual_python).resolve()
            or any(actual_environment.get(key) != expected_environment.get(key) for key in ("torch", "cuda"))
            or actual_environment.get("default_dtype") != "torch.float32"
        ):
            add("runtime.scientific_environment", "Actual Python/Torch/CUDA/FP32 default differs from frozen seed-paired environment")
        allocated_cpus = re.search(r"(?:^|,)cpu=(\d+)(?:,|$)", job.get("AllocTRES", job.get("TRES", "")))
        if allocated_cpus is None or int(allocated_cpus.group(1)) != _get(protocol, "compute.cpus_per_task"):
            add("runtime.scientific_cpus", "Actual allocated CPU count differs from the frozen single-task request")
    if shared:
        memory = re.search(r"(?:^|,)mem=([^,]+)(?:,|$)", job.get("AllocTRES", job.get("TRES", "")))
        expected_memory = _get(protocol, "compute.requested_cpu_memory_gib")
        units = {"": 1024 ** 2, "K": 1024, "M": 1024 ** 2, "G": 1024 ** 3, "T": 1024 ** 4}
        def memory_bytes(value):
            match = re.fullmatch(r"(\d+)([KMGT]?)", value)
            return None if match is None else int(match.group(1)) * units[match.group(2)]
        # This site omits memory TRES. Read the actual current job's explicit
        # MinMemoryNode only in that case; this is a request, not measured RSS.
        node_memory = job.get("MinMemoryNode")
        actual_memory = memory_bytes(memory.group(1)) if memory is not None else (
            memory_bytes(node_memory) if node_memory is not None else None)
        if (not _positive(expected_memory) or actual_memory != expected_memory * 1024 ** 3
                or (memory is not None and node_memory is not None and memory_bytes(node_memory) != actual_memory)):
            add("runtime.cpu_memory", "Actual Slurm host-memory request differs from the frozen request")
        limit = re.fullmatch(r"(?:(\d+)-)?(\d+):(\d{2}):(\d{2})", job.get("TimeLimit", ""))
        expected_hours = _get(protocol, "compute.max_walltime_hours")
        if (limit is None or not _positive(expected_hours) or int(limit.group(3)) >= 60 or int(limit.group(4)) >= 60
                or ((int(limit.group(1) or 0) * 24 + int(limit.group(2))) * 3600
                    + int(limit.group(3)) * 60 + int(limit.group(4))) != expected_hours * 3600):
            add("runtime.time_limit", "Actual Slurm wall-time limit differs from the frozen execution cap")
    if job.get("JobState") != "RUNNING" or job.get("Partition") != _get(protocol, "compute.partition"):
        add("runtime.job_state", "A running allocation in the frozen partition is required")
    try:
        _verify_allocation_account(protocol, job)
    except ValueError as error:
        add("runtime.account", str(error))
    count = _get(protocol, "compute.gpus_per_job")
    if not shared and _tres_gpu_count(job.get("AllocTRES", job.get("TRES"))) != count:
        add("runtime.allocated_gres", "Actual allocated GPU GRES must match the frozen per-job count")
    visible = [value.strip() for value in environment.get("CUDA_VISIBLE_DEVICES", "").split(",") if value.strip()]
    inventory = observation.get("gpu_inventory", [])
    by_uuid = {gpu.get("uuid"): gpu for gpu in inventory}
    cuda_devices = observation.get("cuda_devices", [])
    cuda_uuids = {device.get("uuid") for device in cuda_devices}
    if len(visible) != count or len(set(visible)) != len(visible) or len(cuda_devices) != count or len(cuda_uuids) != count:
        add("runtime.cuda_devices", "Scheduler CVD and actual CUDA-visible device count must agree with the allocation")
    for token, device in zip(visible, cuda_devices):
        if shared and (re.fullmatch(r"GPU-[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", token) is None
                       or token != device.get("uuid")):
            add("runtime.cuda_devices", "Shared-GPU execution requires one complete actual physical GPU UUID")
        elif not shared and not token.isdigit() and not (token.startswith("GPU-") and str(device.get("uuid", "")).startswith(token)):
            add("runtime.cuda_devices", "A UUID CVD token does not identify the actual CUDA device")
    allocated = environment.get("SLURM_STEP_GPUS") or environment.get("SLURM_JOB_GPUS", "")
    ids = allocated.split(",") if allocated else []
    if not shared and (not ids or not all(value.isdigit() for value in ids) or len(ids) != count or len(set(ids)) != len(ids)):
        add("runtime.slurm_gpu_ids", "Exact physical Slurm GPU ids are required; unknown/remapped ids cannot pass")
    kernel_devices = observation.get("kernel_devices", [])
    kernel_by_minor = {device.get("device_minor"): device for device in kernel_devices}
    kernel_by_uuid = {device.get("uuid"): device for device in kernel_devices}
    if not kernel_devices or len(kernel_by_minor) != len(kernel_devices) or len(kernel_by_uuid) != len(kernel_devices):
        add("runtime.kernel_inventory", "The actual kernel GPU UUID/minor inventory is missing or ambiguous")
    if "__autodetect_nvml__" in bindings:
        if len(kernel_devices) != bindings["__autodetect_nvml__"] or not all(
            re.fullmatch(r"[0-9a-fA-F]{4,8}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}\.[0-7]", device.get("pci_bus_id", ""))
            for device in kernel_devices
        ):
            add("runtime.autodetect_mapping", "AutoDetect=nvml requires complete actual PCI bus/UUID/kernel-minor metadata")
            bindings = {}
        else:
            ordered = sorted(kernel_devices, key=lambda device: device["pci_bus_id"])
            bindings = {str(index): device["device_minor"] for index, device in enumerate(ordered)}
    assigned_minors = ({kernel_by_uuid.get(uuid, {}).get("device_minor") for uuid in cuda_uuids}
                       if shared else {bindings.get(index) for index in ids})
    assigned_uuids = {kernel_by_minor.get(minor, {}).get("uuid") for minor in assigned_minors}
    if None in assigned_minors or None in assigned_uuids or assigned_uuids != cuda_uuids:
        add("runtime.physical_mapping", "Actual CUDA UUIDs and configured GRES/kernel devices do not identify the same allocated GPUs")
    if set(by_uuid) != cuda_uuids:
        add("runtime.inventory", "Assigned-GPU hardware query must cover every actual CUDA device")
    for uuid in cuda_uuids:
        gpu, kernel = by_uuid.get(uuid), kernel_by_uuid.get(uuid)
        if gpu is None or kernel is None or gpu.get("device_minor") != kernel.get("device_minor"):
            add("runtime.device_binding", "Actual CUDA/NVML/kernel UUID to device-minor mapping disagrees")
    allocated_minors = {str(minor) for minor in assigned_minors}
    actual_access = observation.get("gpu_device_access", {})
    for gpu in kernel_devices:
        minor = str(gpu.get("device_minor"))
        accessible = actual_access.get(minor)
        if (type(accessible) is not bool
                or (minor in allocated_minors and not accessible)
                or (not shared and accessible != (minor in allocated_minors))):
            add("runtime.device_access", "Kernel device access must allow every allocated GPU and deny every other physical GPU")
            break
    if shared:
        processes = observation.get("gpu_processes")
        if type(processes) is not list:
            add("runtime.gpu_processes", "Actual selected-GPU compute-process inventory is required")
        else:
            seen_pids = set()
            for process in processes:
                if (type(process) is not dict or process.get("uuid") not in cuda_uuids
                        or type(process.get("pid")) is not int or process["pid"] <= 0
                        or process["pid"] in seen_pids or type(process.get("uid")) is not int):
                    add("runtime.gpu_processes", "Selected-GPU process metadata is incomplete or ambiguous")
                    break
                seen_pids.add(process["pid"])
                if (process["uid"] != observation.get("uid") or not isinstance(process.get("cgroup"), str)
                        or not re.search(r"(?:^|[/_])job[_-]?" + re.escape(job_id) + r"(?:/|$)", process["cgroup"], re.MULTILINE)):
                    add("runtime.foreign_gpu_process", "Selected GPU has a compute process outside this owned Slurm job")
                    break
    for uuid in cuda_uuids:
        gpu = by_uuid.get(uuid)
        if gpu is None:
            continue
        if gpu.get("name") != _get(protocol, "compute.gpu_model"):
            add("runtime.gpu_model", "Actual physical GPU model differs from the frozen protocol")
        if not _positive(gpu.get("memory_total_mib")) or gpu["memory_total_mib"] < _get(protocol, "compute.min_gpu_memory_gib", math.inf) * 1024:
            add("runtime.gpu_memory", "Actual GPU total memory is below the frozen requirement or unknown")
        if not _positive(gpu.get("memory_free_mib")) or gpu["memory_free_mib"] < _get(protocol, "compute.min_free_gpu_memory_gib", math.inf) * 1024:
            add("runtime.free_memory", "Actual GPU memory headroom is below the frozen requirement or unknown")
    captured = _timestamp(observation.get("captured_at"))
    if captured is None or not now - timedelta(seconds=30) <= captured <= now + timedelta(seconds=5):
        add("runtime.stale_observation", "Live hardware observation is missing or stale")
    return issues


def check_formal_gate(
    protocol: Mapping[str, Any], *, slurm_config_text: str, slurm_node_text: str,
    slurm_job_text: str = "", configuration_files: Mapping[str, str | Path] | None = None,
    configuration_node: str | None = None,
    artifacts: Mapping[str, str | Path] | None = None, live_allocation: bool = False,
    now: datetime | None = None,
) -> GateReport:
    """Review exports or additionally verify this process's actual allocation.

    Standard configuration hashes record facts, not an additional approval.
    Neither exclusive allocation, free memory, nor CUDA visibility proves
    isolation. Live mode reads actual local system files, then verifies current
    allocation/device facts; exports are not given an artificial expiry time.
    Exports alone can only yield REVIEW_ONLY, never PASS_LIVE_ALLOCATION.
    """
    supplied_now = now
    now = now or datetime.now(timezone.utc)
    issues = validate_protocol(protocol, now=now)
    add = lambda code, message: issues.append(GateIssue(code, message))
    reviewed = {}
    artifacts = artifacts or {}
    fields = list(_required_hash_fields(protocol))
    if _get(protocol, BRIDGE_FIELD) is not None:
        fields.append(BRIDGE_FIELD)
    seeds = _get(protocol, "pretraining.paired_random_initialization.encoder_sha256_by_seed")
    if isinstance(seeds, Mapping):
        fields.extend(f"pretraining.paired_random_initialization.encoder_sha256_by_seed.{seed}" for seed in seeds)
    try:
        fields.extend(contrast_hash_fields(protocol))
    except (TypeError, ValueError):
        # validate_protocol already records the malformed declaration. Do not
        # infer a subset of valid comparisons or silently repair the protocol.
        pass
    if _get(protocol, "tracking.mode") == "offline_with_verified_sync":
        fields.append("tracking.sync_evidence_sha256")
    for path in fields:
        expected = _get(protocol, path)
        artifact = artifacts.get(path)
        if not _hash(expected) or artifact is None:
            add("artifact.unverified", f"An actual local artifact with the frozen hash is required: {path}")
            continue
        try:
            actual = _read_artifact(artifact)
        except (OSError, TypeError) as error:
            add("artifact.unreadable", f"Cannot verify {path}: {error}")
            continue
        reviewed[path] = actual
        if actual != expected:
            add("artifact.hash_mismatch", f"Artifact changed after protocol freeze: {path}")
    if _get(protocol, BRIDGE_FIELD) is not None and reviewed.get(BRIDGE_FIELD) == _get(protocol, BRIDGE_FIELD):
        try:
            verify_trial_producer_consumer_bridge(protocol, artifacts)
        except (OSError, TypeError, ValueError, KeyError) as error:
            add("artifact.trial_source_bridge", f"Trial/source reuse bridge failed actual byte checks: {error}")
    if pretraining_only(protocol) and reviewed.get(AUTHORITY_FIELD) == _get(protocol, AUTHORITY_FIELD):
        try:
            verify_pretraining_scientific_authority(protocol, artifacts, now=now)
        except (OSError, TypeError, ValueError, KeyError) as error:
            add("artifact.scientific_authority", f"Frozen pretraining science projection failed: {error}")
    statistics_field = "downstream.statistics.analysis_plan_sha256"
    statistics_artifact = artifacts.get(statistics_field)
    if not pretraining_only(protocol) and statistics_artifact is not None and reviewed.get(statistics_field) == _get(protocol, statistics_field):
        try:
            with Path(statistics_artifact).open("rb") as stream:
                raw_plan = stream.read(1024 * 1024 + 1)
            if len(raw_plan) > 1024 * 1024 or hashlib.sha256(raw_plan).hexdigest() != reviewed[statistics_field]:
                raise ValueError("Analysis plan changed during review or exceeds the 1 MiB metadata bound")
            def reject_constant(value):
                raise ValueError("Analysis plan contains a non-finite JSON constant")
            def unique_keys(pairs):
                result = {}
                for key, value in pairs:
                    if key in result:
                        raise ValueError("Analysis plan contains a duplicate JSON key")
                    result[key] = value
                return result
            plan = json.loads(raw_plan.decode("utf-8-sig"), parse_constant=reject_constant,
                              object_pairs_hook=unique_keys)
            validate_analysis_plan(plan, protocol)
        except (OSError, TypeError, ValueError, KeyError) as error:
            add("artifact.statistics_plan", f"Frozen statistics artifact is not an executable complete analysis plan: {error}")
    config, node, job = map(_key_values, (slurm_config_text, slurm_node_text, slurm_job_text))
    shared = shared_gpu_policy(protocol)
    if not shared and "gpu" not in config.get("GresTypes", "").split(","):
        add("slurm.no_gpu_gres", "GresTypes must explicitly include gpu; null GRES cannot reserve training GPUs")
    if not shared and "task/cgroup" not in config.get("TaskPlugin", "").split(","):
        add("slurm.no_task_cgroup", "task/affinity alone does not enforce GPU device isolation; task/cgroup evidence is required")
    if config.get("ProctrackType") != "proctrack/cgroup":
        add("slurm.no_process_cgroup", "A matching Slurm process cgroup mechanism must be verified")
    if config.get("PreemptMode") != "OFF":
        add("slurm.preemption_unknown", "Non-preemptible scheduling is not proven by this config export")
    requested_count = _get(protocol, "compute.gpus_per_job")
    if not _positive(requested_count) or (not shared and _gpu_count(node.get("Gres")) < requested_count):
        add("slurm.node_gres", "The reviewed node has insufficient or unknown GPU GRES")
    site_issues, site_hashes, bindings = (_shared_site_configuration(configuration_files, node, configuration_node)
        if shared else _site_configuration(configuration_files, config, node, configuration_node))
    issues.extend(site_issues)
    reviewed.update(site_hashes)
    for name, snapshot in (("slurm_config", slurm_config_text), ("slurm_node", slurm_node_text), ("slurm_job", slurm_job_text)):
        if snapshot:
            reviewed[f"site_snapshot/{name}"] = hashlib.sha256(snapshot.encode("utf-8")).hexdigest()
    if live_allocation:
        issues.extend(_live_configuration_paths(configuration_files, config))
    observation = None
    # Never inspect devices when the semantic/static gate is already blocked.
    if live_allocation and not issues:
        try:
            observation = (_capture_local_observation(include_processes=True) if shared else _capture_local_observation())
            if shared:
                observation["gpu_isolation_policy"] = SHARED_GPU_POLICY
                observation["gpu_protection_verified"] = False
                observation["gpu_scheduler_reservation_verified"] = False
            runtime_now = supplied_now or datetime.now(timezone.utc)
            issues.extend(_check_runtime(observation, protocol, node, job, bindings, configuration_node, runtime_now))
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
            add("runtime.unverified", f"Live allocation observation failed: {error}")
    elif live_allocation:
        add("runtime.not_observed", "Static preconditions failed; no live hardware observation was attempted")
    status = "BLOCKED" if issues else (SHARED_GPU_STATUS if live_allocation and shared else
                                       "PASS_LIVE_ALLOCATION" if live_allocation else "REVIEW_ONLY")
    return GateReport(status, issues, protocol.get("content_sha256", ""), reviewed, observation)
