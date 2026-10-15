"""Prepare full retained-train controls, without freezing or changing a split.

The CLI enforces the CPU Slurm boundary for real preparation. This library API
also supports temporary synthetic LMDB tests; it does not authorize a real fit.
Estimator, masks, standard-deviation floors and baseline algorithms are reused.
"""
from __future__ import annotations

from copy import deepcopy
import json
import math
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import time

import torch

from ..data.descriptor_schema import GRAPH_DESCRIPTOR_NAMES
from ..model.normalization import train_regression_normalization
from ..model.phase1_specs import PHASE1_CHARGE_DESCRIPTOR_SPECS, PHASE1_ELEMENT_DESCRIPTOR_SPECS
from .baselines import TrainingBaselines
from .data import Phase1ViewDataset, StrictManifestDataset, fit_train_statistics
from .formal_runtime import load_fitted_controls
from .identity import canonical_hash


PREPARATION_SCHEMA = "phase1_full_train_controls_preparation_v1"
_SHA = re.compile(r"[0-9a-f]{64}\Z")


def _integer(value, name, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return value


def validate_preparation_config(config):
    if not isinstance(config, dict) or any(not isinstance(config.get(name), dict) for name in ("backbone", "head", "phase1")):
        raise ValueError("Preparation requires explicit backbone/head/phase1 configuration")
    p = config["phase1"]
    forbidden = ("diagnostic_limit", "train_limit", "validation_limit", "train_manifest", "validation_manifest", "test_manifest", "max_wall_seconds")
    if p.get("status") == "diagnostic_only" or any(name in p for name in forbidden):
        raise ValueError("Diagnostic configuration/subset limits cannot prepare full train controls")
    if p.get("atom_encoding") != "zero_based" or p.get("charge_definition") != "MOPAC NET ATOMIC CHARGES" or config["head"].get("profile") != "phase1":
        raise ValueError("Phase 1 encoding, charge definition and head profile must be explicit")
    _integer(config["backbone"].get("n_atom_types"), "backbone.n_atom_types", 2)
    level = p.get("topology_level")
    if isinstance(level, bool) or not isinstance(level, (int, float)) or not math.isfinite(level) or not 0 <= level <= 1:
        raise ValueError("topology_level must be finite and lie in [0, 1]")
    if p.get("regression_output_mode") not in {"raw", "train_affine"}:
        raise ValueError("regression_output_mode must be explicitly raw or train_affine")


def validate_full_training_view(train):
    if not isinstance(train, StrictManifestDataset):
        raise ValueError("Preparation requires the strict exact-key training dataset")
    if (train.kind != "train" or train.diagnostic_only or getattr(train, "_selection", None) is not None
            or train.manifest.get("diagnostic_only") is True or train.atom_encoding != "zero_based"
            or len(train) != train.manifest.get("unique_structure_count")):
        raise ValueError("Preparation requires the complete retained training manifest, never a diagnostic view")
    if not len(train) or not _SHA.fullmatch(train.pool_hash) or not _SHA.fullmatch(train.view_hash):
        raise ValueError("Full training view lacks valid pool/view hashes")
    expected_view = canonical_hash({"pool_hash": train.pool_hash, "atom_encoding": "zero_based",
        "diagnostic_only": False, "logical_selection": None, "reader_policy": "exact_key_no_fallback_v1"})
    if train.view_hash != expected_view:
        raise ValueError("Full training view hash does not describe every retained exact key")


def _validate_record(record, ntypes):
    x, pos = record.x, record.pos
    if (x.device.type != "cpu" or x.ndim != 2 or x.shape[1] != 1 or not x.shape[0]
            or pos.device.type != "cpu" or tuple(pos.shape) != (len(x), 3) or not torch.isfinite(pos).all()):
        raise ValueError("Controls require aligned finite CPU coordinates and one Z-1 element column")
    atoms = x[:, 0]
    if not torch.isfinite(atoms).all() or not torch.equal(atoms, atoms.double().floor().to(atoms.dtype)) or bool(((atoms < 0) | (atoms >= ntypes - 1)).any()):
        raise ValueError("Training atom outside finite integral Z-1 vocabulary excluding reserved padding")
    if getattr(record, "energy_unit", None) != "kcal/mol":
        raise ValueError("Training energy unit must be kcal/mol; units cannot be repaired by masking")
    for field, expected in (("charge_unit", "e"), ("charge_definition", "MOPAC NET ATOMIC CHARGES")):
        observed = getattr(record, field, None)
        if observed is not None and observed != expected:
            raise ValueError(f"Training {field} differs from the Phase 1 label contract")
    for name, shape in (("y", (len(x), 1)), ("charge_mask", (len(x), 1)), ("rdkit_node_mask", (len(x), 1))):
        value = getattr(record, name, None)
        if not isinstance(value, torch.Tensor) or tuple(value.shape) != shape or value.device.type != "cpu":
            raise ValueError(f"Training label/mask shape or CPU correspondence mismatch: {name}")
    for name in ("rdkit_graph_desc", "rdkit_graph_desc_mask"):
        value = getattr(record, name, None)
        if not isinstance(value, torch.Tensor) or value.numel() != len(GRAPH_DESCRIPTOR_NAMES) or value.device.type != "cpu":
            raise ValueError(f"Training full descriptor schema mismatch: {name}")
    for spec in PHASE1_CHARGE_DESCRIPTOR_SPECS + PHASE1_ELEMENT_DESCRIPTOR_SPECS:
        value = getattr(record, spec.field_name, None)
        if not isinstance(value, torch.Tensor) or tuple(value.shape) != (len(x), 1) or value.device.type != "cpu":
            raise ValueError(f"Training node descriptor atom correspondence mismatch: {spec.name}")


class _CheckedTrainingView:
    def __init__(self, train, ntypes, check, stage):
        self.train, self.ntypes, self.check, self.stage = train, ntypes, check, stage
        self.seen = []

    def __getattr__(self, name):
        return getattr(self.train, name)

    def __len__(self):
        return len(self.train)

    def __getitem__(self, index):
        self.check(self.stage, int(index))
        record = self.train[index]
        _validate_record(record, self.ntypes)
        self.seen.append(int(index))
        self.check(self.stage, int(index))
        return record


def fit_full_train_controls(train, config, *, fit_seed, topology_seed, deadline_check=None):
    """Return JSON controls/fit IDs and proof for every retained training record.

    No validation or downstream dataset enters the API. The affine contract is
    derived solely for strict self-validation when absent from the input config;
    the input configuration is never rewritten or frozen.
    """
    validate_preparation_config(config)
    validate_full_training_view(train)
    _integer(fit_seed, "fit_seed")
    _integer(topology_seed, "topology_seed")
    check = deadline_check or (lambda stage, index=None: None)
    ntypes = config["backbone"]["n_atom_types"]
    indices = list(range(len(train)))
    keys = []
    for index in indices:
        check("fit_ids", index)
        shard, real = train.record_ref(index)
        keys.append(f"{shard}:{real}")
    if len(set(keys)) != len(train):
        raise ValueError("Retained training manifest repeats a source record")
    stats_view = _CheckedTrainingView(train, ntypes, check, "statistics")
    stats, provenance = fit_train_statistics(stats_view, cap=len(train), seed=fit_seed)
    if stats_view.seen != indices or provenance["sampled_logical_indices"] != indices:
        raise ValueError("Statistics did not fit every retained training record exactly once")
    check("statistics_complete")
    baseline_view = _CheckedTrainingView(train, ntypes, check, "baseline_clean")
    element_base = _CheckedTrainingView(train, ntypes, check, "baseline_topology")
    topology = Phase1ViewDataset(element_base, mode="topo", level=config["phase1"]["topology_level"], seed=topology_seed)
    # The existing degrader consumes an incidental global randperm before its
    # fixed generator; restore that unrelated RNG without changing the recipe.
    with torch.random.fork_rng(devices=[]):
        baseline = TrainingBaselines(ntypes).fit(
            (baseline_view[index] for index in indices), train_manifest={"role": "train", **train.summary()},
            element_records=(topology[index] for index in indices))
    if baseline_view.seen != indices or element_base.seen != indices:
        raise ValueError("Baselines did not fit every retained training record exactly once in both views")
    check("baselines_complete")
    serial_stats = {name: value.detach().cpu().tolist() if isinstance(value, torch.Tensor) else value for name, value in stats.items()}
    state = {**baseline.to_dict(), "n_atom_types": ntypes,
             "element_view": {"mode": "topo", "level": config["phase1"]["topology_level"],
                              "seed": topology_seed, "seed_rule": "seed_plus_logical_index"}}
    controls = {"schema_version": "phase1_fitted_controls_v1", "statistics": serial_stats,
                "statistics_provenance": provenance, "baselines": state}
    fit_ids = {"schema_version": "phase1_fit_ids_v1", "train_pool_hash": train.pool_hash, "train_view_hash": train.view_hash,
               "statistics": {"logical_indices": indices.copy(), "record_keys": keys.copy()},
               "baselines": {"logical_indices": indices.copy(), "record_keys": keys.copy()}}
    validation_config = deepcopy(config)
    derived = config["phase1"]["regression_output_mode"] == "train_affine" and "regression_output_normalization" not in config["head"]
    if derived:
        validation_config["head"]["regression_output_normalization"] = train_regression_normalization(serial_stats, provenance)
    # Consume the same JSON representations that the formal runner will read.
    controls = json.loads(json.dumps(controls, allow_nan=False))
    fit_ids = json.loads(json.dumps(fit_ids, allow_nan=False))
    _, _, consumer_proof = load_fitted_controls(controls, fit_ids, train, validation_config)
    check("strict_consumer_selfcheck_complete")
    proof = {"schema_version": PREPARATION_SCHEMA, "state": "NOT_FROZEN", "formal_eligible": False,
             "purpose": "full retained-train statistics and baseline preparation only", "train": train.summary(),
             "statistics_fit_records": len(indices), "baseline_fit_records": len(indices), "element_fit_view_records": len(indices),
             "all_retained_train_ids_fitted": True, "strict_formal_consumer_roundtrip_passed": True,
             "validation_or_downstream_labels_read": False, "records_reassigned_or_excluded": 0,
             "affine_contract_derived_for_selfcheck_only": derived,
             "consumer_proof": consumer_proof}
    return {"controls": controls, "fit_ids": fit_ids, "proof": proof}


def cpu_slurm_environment(env=None, *, platform=None, hostname=None):
    """Require one CPU-only Slurm task; never change CUDA visibility."""
    env = os.environ if env is None else env
    platform = sys.platform if platform is None else platform
    hostname = socket.gethostname() if hostname is None else hostname
    if platform != "linux" or not str(env.get("SLURM_JOB_ID", "")).isdigit() or int(env.get("SLURM_JOB_ID", "0")) <= 0:
        raise RuntimeError("Real controls fitting requires a Linux CPU Slurm allocation")
    if not env.get("SLURM_JOB_NODELIST") or env.get("SLURMD_NODENAME", "").split(".")[0] != hostname.split(".")[0]:
        raise RuntimeError("CPU Slurm allocation does not identify this compute node")
    for name in ("SLURM_NTASKS", "SLURM_JOB_NUM_NODES"):
        if str(env.get(name, "1")) != "1":
            raise RuntimeError("Preparation supports exactly one CPU task on one node")
    cpus = str(env.get("SLURM_CPUS_PER_TASK", ""))
    if not cpus.isdigit() or int(cpus) <= 0:
        raise RuntimeError("CPU Slurm allocation must declare cpus_per_task")
    for name in ("SLURM_JOB_GPUS", "SLURM_STEP_GPUS", "SLURM_GPUS", "SLURM_GPUS_ON_NODE"):
        if str(env.get(name, "")).strip() not in {"", "0", "(null)"}:
            raise RuntimeError("Controls preparation must use a CPU-only Slurm allocation")
    if env.get("CUDA_VISIBLE_DEVICES") not in {"", "-1"}:
        raise RuntimeError("CPU preparation requires explicit empty CUDA_VISIBLE_DEVICES; it is never rewritten")
    return {"job_id": str(env["SLURM_JOB_ID"]), "node": hostname, "cpus_per_task": int(cpus), "cuda_visible_devices": env["CUDA_VISIBLE_DEVICES"]}


def _scheduler_memory_mib(value, field):
    """Parse a finite positive Slurm memory quantity; unset is not zero."""
    memory = re.fullmatch(r"(\d+)([KMGT]?)", value)
    if memory is None or not int(memory[1]):
        raise RuntimeError(f"Live CPU Slurm job has invalid memory evidence in {field}")
    amount = int(memory[1])
    if amount > 2 ** 63 - 1:
        raise RuntimeError(f"Live CPU Slurm job has invalid memory evidence in {field}")
    return amount * {"": 1, "K": 1 / 1024, "M": 1, "G": 1024, "T": 1024 ** 2}[memory[2]]


def _cpu_job_memory_evidence(fields, *, live_cpus, task_cpus):
    """Return a budget basis, without claiming OS/cgroup enforcement.

    Slurm 22.05 may omit mem from TRES on CPU jobs while still reporting the
    same live job's MinMemoryNode/MinMemoryCPU request. Such a minimum request
    is scheduler evidence for our conservative RSS budget, not an enforced
    upper limit. Explicit invalid memory values never permit fallback.
    """
    accounted = []
    for field in ("AllocTRES", "TRES"):
        values = [token.split("=", 1)[1] for token in fields.get(field, "").split(",")
                  if token.startswith("mem=")]
        if len(values) > 1:
            raise RuntimeError(f"Live CPU Slurm job repeats memory evidence in {field}")
        if values:
            accounted.append((f"{field}.mem", _scheduler_memory_mib(values[0], f"{field}.mem")))
    if len(accounted) == 2 and accounted[0][1] != accounted[1][1]:
        raise RuntimeError("Live CPU Slurm job has contradictory allocated memory accounting")

    request_fields = [name for name in ("MinMemoryNode", "MinMemoryCPU") if name in fields]
    if len(request_fields) > 1:
        raise RuntimeError("Live CPU Slurm job declares both MinMemoryNode and MinMemoryCPU")
    request = None
    budget_cpus = min(live_cpus, task_cpus)
    if request_fields:
        field = request_fields[0]
        request = _scheduler_memory_mib(fields[field], field)
        if field == "MinMemoryCPU":
            request *= budget_cpus

    if accounted:
        field, memory_mib = accounted[0]  # Prefer AllocTRES, then legacy TRES.
        if request is not None and memory_mib < request:
            raise RuntimeError("Live CPU Slurm memory accounting is smaller than its minimum request")
        kind = "allocated_tres_accounting"
    elif request is not None:
        field, memory_mib = request_fields[0], request
        kind = "live_scheduler_job_request"
    else:
        raise RuntimeError("Live CPU Slurm job lacks finite positive memory accounting or a job request")
    evidence = {"memory_mib": memory_mib, "memory_evidence_kind": kind,
                "source_field": field, "memory_enforcement_verified": False}
    if field == "MinMemoryCPU":
        evidence["memory_budget_cpus"] = budget_cpus
    return evidence


def verify_cpu_slurm_job(allocation, *, execute=None, uid=None):
    """Read this live job; exported text/env alone cannot establish allocation."""
    execute = subprocess.run if execute is None else execute
    uid = os.getuid() if uid is None else uid
    response = execute(["scontrol", "show", "job", allocation["job_id"]], check=True, capture_output=True, text=True, timeout=10)
    if len(response.stdout) > 65536:
        raise RuntimeError("Live CPU Slurm job observation is unexpectedly large")
    fields = dict(token.split("=", 1) for token in response.stdout.split() if "=" in token)
    owner = re.search(r"\((\d+)\)\Z", fields.get("UserId", ""))
    if (fields.get("JobId") != allocation["job_id"] or fields.get("JobState") != "RUNNING" or owner is None
            or int(owner[1]) != uid or fields.get("NumNodes") != "1"
            or fields.get("NodeList", "").split(".")[0] != allocation["node"].split(".")[0]):
        raise RuntimeError("Live CPU Slurm job does not match this user, running allocation and node")
    cpus = fields.get("NumCPUs", "")
    if not cpus.isdigit() or int(cpus) < allocation["cpus_per_task"]:
        raise RuntimeError("Live CPU Slurm allocation is smaller than its environment declaration")
    if fields.get("NumTasks", "1") != "1":
        raise RuntimeError("Live CPU controls preparation requires one task")
    allocated_tres = fields.get("AllocTRES", fields.get("TRES", ""))
    for field in (allocated_tres, fields.get("ReqTRES", "")):
        tres = dict(token.split("=", 1) for token in field.split(",") if "=" in token)
        if any(key.startswith("gres/gpu") and value != "0" for key, value in tres.items()):
            raise RuntimeError("Live Slurm job requests/allocates GPUs; controls preparation is CPU-only")
    if any("gpu" in fields.get(name, "").lower() for name in ("Gres", "TresPerNode", "TresPerTask")):
        raise RuntimeError("Live Slurm job declares GPU resources")
    memory = _cpu_job_memory_evidence(fields, live_cpus=int(cpus), task_cpus=allocation["cpus_per_task"])
    return {"job_id": allocation["job_id"], "owner_uid": uid, "node": allocation["node"],
            "num_cpus": int(cpus), **memory, "job_state": "RUNNING", "gpu_resources": 0}


def validate_output_directory(output, *, project_root, input_paths):
    output = Path(output)
    if output.exists() or output.is_symlink():
        raise FileExistsError("Controls output directory must be new; refusing to overwrite")
    output = output.resolve()
    protected = [Path(project_root).resolve()]
    for value in input_paths:
        path = Path(value).resolve()
        protected.append(path if path.is_dir() else path.parent)
    if any(output == root or output.is_relative_to(root) for root in protected):
        raise ValueError("Controls output must stay outside source repository and all input trees")
    return output


class PreparationBudgetExceeded(RuntimeError):
    pass


class PreparationBudget:
    def __init__(self, *, max_wall_seconds, max_memory_mib, max_output_bytes, clock=time.monotonic):
        if isinstance(max_wall_seconds, bool) or not isinstance(max_wall_seconds, (float, int)) or not math.isfinite(max_wall_seconds) or not 0 < max_wall_seconds <= 86400:
            raise ValueError("Preparation wall bound must be positive and <=86400 seconds")
        _integer(max_memory_mib, "max_memory_mib", 1)
        _integer(max_output_bytes, "max_output_bytes", 4096)
        if max_memory_mib > 65536 or max_output_bytes > 1024 ** 3:
            raise ValueError("Preparation bounds exceed supported memory/output limits")
        self.clock, self.started = clock, clock()
        self.max_wall_seconds, self.max_memory_mib, self.max_output_bytes = float(max_wall_seconds), max_memory_mib, max_output_bytes
        self.stage, self.logical_index, self.peak_rss_mib = "startup", None, 0.

    def check(self, stage, index=None):
        self.stage, self.logical_index = stage, index
        if self.clock() - self.started >= self.max_wall_seconds:
            raise PreparationBudgetExceeded(f"Wall bound exceeded at {stage}, record {index}")
        if sys.platform == "linux":
            import resource
            self.peak_rss_mib = max(self.peak_rss_mib, resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.)
            if self.peak_rss_mib > self.max_memory_mib:
                raise PreparationBudgetExceeded(f"Observed peak RSS exceeded {self.max_memory_mib} MiB")

    def evidence(self):
        return {"elapsed_seconds": self.clock() - self.started, "peak_rss_mib": self.peak_rss_mib,
                "last_stage": self.stage, "last_logical_index": self.logical_index,
                "max_wall_seconds": self.max_wall_seconds, "max_memory_mib": self.max_memory_mib, "max_output_bytes": self.max_output_bytes,
                "bounds": "per-record wall/RSS checks plus CLI wall alarm and Slurm outer walltime; scheduler memory evidence does not verify OS/cgroup enforcement"}
