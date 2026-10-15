"""Consumers of frozen artifacts for the single-GPU Phase 1 runner.

This module never prepares/freezes a protocol, fits controls, submits jobs or
changes CUDA visibility. An artifact hash proves integrity, not authorization:
the executable additionally requires the existing live formal allocation gate.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import re
import socket
import subprocess
import time

import numpy as np
import torch

from ..data.descriptor_schema import GRAPH_DESCRIPTOR_NAMES
from ..model.normalization import train_regression_normalization
from ..model.phase1_specs import PHASE1_CHARGE_DESCRIPTOR_SPECS, PHASE1_ELEMENT_DESCRIPTOR_SPECS, PHASE1_GRAPH_DESCRIPTOR_NAMES
from ..training.checkpoint import contract_hash, semantic_config
from ..training.losses import LossWeights
from .baselines import TrainingBaselines
from .formal_gate import check_formal_gate, shared_gpu_policy
from .identity import IDENTITY_POLICY, canonical_hash, frozen_test_identities
from .objectives import GROUP_TASKS, PHASE1_VARIANTS, Phase1LossPolicy
from .strategy import INDEX_UNIT, PositivePiecewiseJoint, PositiveWeightStage
from .strategy_contract import DIRECT_RECIPE, validated_contrasts


FORMAL_RUN_SCHEMA = "phase1_formal_single_gpu_v1"
VIEWS = ["clean", "geom", "topo"]
ORDER = {"name": "fixed_seed_permutation_cycle_v1", "permutation_seed_rule": "condition_seed",
         "view_seed_rule": "condition_seed_plus_logical_index", "views": VIEWS}
INIT_RECIPE = "sorted_name_dtype_shape_and_raw_tensor_bytes_v1"
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_INCHI = re.compile(r"[A-Z]{14}-[A-Z]{10}-[A-Z]\Z")


def get_path(document, path):
    value = document
    for part in path.split("."):
        if not isinstance(value, Mapping) or part not in value:
            raise ValueError(f"Missing frozen field: {path}")
        value = value[part]
    return value


def integer(value, name, *, minimum=1):
    if type(value) is not int or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return value


def finite(value, name, *, positive=False):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or (positive and value <= 0):
        raise ValueError(f"{name} must be finite{' and positive' if positive else ''}")
    return float(value)


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path):
    result = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(result, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return result


def write_json(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False), encoding="utf-8")
    temporary.replace(path)


def artifact_paths(map_path):
    path = Path(map_path).resolve()
    result = {}
    for field, name in read_json(path).items():
        if not isinstance(name, str) or not name:
            raise ValueError(f"Artifact map requires actual file paths: {field}")
        item = Path(name)
        result[field] = (item if item.is_absolute() else path.parent / item).resolve()
    return result


def read_artifact(protocol, artifacts, field):
    path = artifacts.get(field)
    expected = get_path(protocol, field)
    if path is None or not isinstance(expected, str) or not _SHA.fullmatch(expected) or file_sha256(path) != expected:
        raise ValueError(f"Frozen artifact missing/changed: {field}")
    return read_json(path)


def single_gpu_environment(protocol, env=None):
    """Do not infer DDP, accept multiple devices, or mutate actual visibility.

    The explicit shared-GPU policy uses a launcher-selected physical UUID;
    it does not describe that device as scheduler-reserved or isolated.
    """
    env = os.environ if env is None else env
    if not env.get("SLURM_JOB_ID"):
        raise RuntimeError("Formal training requires a matching live Slurm allocation")
    if get_path(protocol, "compute.nodes_per_job") != 1 or get_path(protocol, "compute.gpus_per_job") != 1:
        raise RuntimeError("This runner supports exactly one node and one GPU")
    for name in ("WORLD_SIZE", "LOCAL_WORLD_SIZE", "SLURM_NTASKS", "SLURM_NPROCS", "SLURM_JOB_NUM_NODES"):
        if name in env and env[name] != "1":
            raise RuntimeError(f"Single-GPU runner rejects {name}={env[name]}")
    for name in ("RANK", "LOCAL_RANK", "SLURM_PROCID"):
        if name in env and env[name] != "0":
            raise RuntimeError(f"Single-GPU runner rejects {name}={env[name]}")
    visible = env.get("CUDA_VISIBLE_DEVICES", "")
    if not visible or len(visible.split(",")) != 1 or not visible.strip() or visible != visible.strip() or visible == "-1":
        raise RuntimeError("A single scheduler-provided CUDA_VISIBLE_DEVICES entry is required")
    if shared_gpu_policy(protocol) and re.fullmatch(
            r"GPU-[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", visible) is None:
        raise RuntimeError("Shared-GPU execution requires one complete launcher-selected physical GPU UUID")
    return visible


def live_gate(protocol, artifacts):
    """Read scheduler and standard system files locally; no exports/overrides."""
    single_gpu_environment(protocol)
    def command(*args):
        return subprocess.check_output(args, text=True, stderr=subprocess.STDOUT, timeout=20)
    configuration = command("scontrol", "show", "config")
    hostname = socket.gethostname().split(".")[0]
    node = command("scontrol", "show", "node", hostname)
    job = command("scontrol", "show", "job", os.environ["SLURM_JOB_ID"])
    match = re.search(r"(?:SlurmConf|SLURM_CONF)\s*=\s*(\S+)", configuration)
    slurm_conf = Path(match.group(1) if match else "/etc/slurm/slurm.conf")
    report = check_formal_gate(protocol, slurm_config_text=configuration, slurm_node_text=node,
        slurm_job_text=job, configuration_files={"gres": slurm_conf.parent / "gres.conf",
            "cgroup": slurm_conf.parent / "cgroup.conf", "sshd": Path("/etc/ssh/sshd_config"), "pam": Path("/etc/pam.d/sshd")},
        configuration_node=hostname, artifacts=artifacts, live_allocation=True)
    return report


def target_contract():
    return {"schema_version": "phase1_targets_v1", "head_profile": "phase1",
            "groups": {group: list(tasks) for group, tasks in GROUP_TASKS.items()}}


def label_contract():
    return {"schema_version": "phase1_label_contract_v1", "atom_encoding": "zero_based", "views": VIEWS,
        "energy": {"field": "energy", "unit": "kcal/mol", "mask": "energy_mask", "view": "clean"},
        "charge": {"field": "y", "definition": "MOPAC NET ATOMIC CHARGES", "unit": "e", "mask": "charge_mask", "view": "clean"},
        "geometry": {"field": "target_pos", "unit": "angstrom", "objective": "all_pair_morse_log1p_per_atom_mean",
                     "view": "geom", "mask": "real_atoms_and_finite_target_positions", "metric_pair_count": "unique_upper_triangle"},
        "element": {"field": "target_x", "view": "topo", "mask": "element_corrupt_mask", "classes": "Z_minus_1_excluding_reserved_padding"},
        "bond_order": {"field": "rdkit_bond_order", "classes": 5, "positive_edges_only": True, "view": "clean"},
        "descriptors": {"graph_field": "rdkit_graph_desc", "graph_mask": "rdkit_graph_desc_mask", "node_mask": "rdkit_node_mask",
                        "per_target_finite_required": True, "view": "clean"}}


def frozen_execution(protocol, execution, *, variant, seed):
    if execution.get("schema_version") != "phase1_execution_v1" or execution.get("world_size") != 1 or execution.get("strategy") != "direct_joint":
        raise ValueError("Only frozen phase1_execution_v1 direct_joint/world_size=1 is supported; no staged/DDP fallback")
    if variant not in PHASE1_VARIANTS or variant not in get_path(protocol, "pretraining.variants"):
        raise ValueError("Variant is not in the frozen matrix")
    integer(seed, "seed", minimum=0)
    if seed not in get_path(protocol, "pretraining.seeds"):
        raise ValueError("Seed is not in the frozen matrix")
    if execution.get("order") != ORDER or execution.get("none_policy") != "zero_updates_export_paired_H0":
        raise ValueError("Frozen identical order/views and none policy are required")
    evaluation = execution.get("evaluation", {})
    integer(evaluation.get("every_updates"), "evaluation.every_updates")
    if set(evaluation) != {"every_updates", "endpoint"} or evaluation.get("endpoint") != "full_pretrain_validation":
        raise ValueError("Full fixed-interval/endpoint pretrain validation is required")
    config = deepcopy(execution.get("config"))
    if not isinstance(config, dict) or any(not isinstance(config.get(key), dict) for key in semantic_config({})):
        raise ValueError("Execution must contain the complete expanded semantic configuration")
    if config["architecture"].get("type") != "shared_multitask" or config["head"].get("profile") != "phase1":
        raise ValueError("Formal execution requires the Phase 1 shared-H0 architecture")
    p = config["phase1"]
    if p.get("status") != "formal" or p.get("atom_encoding") != "zero_based" or p.get("views") != VIEWS:
        raise ValueError("Diagnostic/subset/changed-view configuration cannot start a formal run")
    if any(name in p for name in ("train_limit", "validation_limit", "diagnostic_limit", "train_manifest", "validation_manifest", "max_wall_seconds")):
        raise ValueError("Formal data/budgets come only from frozen artifacts/protocol, never diagnostic overrides")
    if p.get("charge_definition") != "MOPAC NET ATOMIC CHARGES":
        raise ValueError("Phase 1 charge definition changed")
    for name in ("max_atoms_per_molecule", "max_atoms_per_batch"):
        integer(p.get(name), f"phase1.{name}")
    for name in ("geometry_level", "topology_level"):
        level = finite(p.get(name), name)
        if not 0 <= level <= 1:
            raise ValueError(f"Unsupported corruption level: {name}")
    n = integer(get_path(protocol, "pretraining.budget.optimizer_steps_per_condition"), "optimizer_steps")
    b = integer(config["training"].get("base_molecules_per_batch"), "global base batch")
    if get_path(protocol, "pretraining.budget.structures_per_condition") != n * b:
        raise ValueError("Frozen structures budget must equal optimizer_steps * global base batch (three views are not three structures)")
    if config["schedule"].get("strategy") != "direct_joint_from_step_zero" or config["schedule"].get("max_steps") != n:
        raise ValueError("Only the exact frozen direct-joint update schedule is supported")
    if "joint_weighting" in config["schedule"]:
        raise ValueError("Selected recipe bindings must come from the frozen contrast artifact, not the base execution")
    warmup = integer(config["schedule"].get("warmup_steps"), "warmup_steps", minimum=0)
    if warmup > n or not 0 <= finite(config["schedule"].get("min_lr_ratio"), "min_lr_ratio") <= 1:
        raise ValueError("Frozen LR schedule outside supported range")
    if config["training"].get("world_size", 1) != 1 or config["training"].get("precision", "float32") != "float32":
        raise ValueError("DDP and AMP are not implemented in this formal runner")
    forbidden = ("gradient_accumulation_steps", "accumulate_grad_batches")
    if any(config["training"].get(name, 1) != 1 for name in forbidden):
        raise ValueError("Gradient accumulation is not implemented; global batch must be explicit")
    if set(config["loss"]) != set(LossWeights.__dataclass_fields__):
        raise ValueError("Every legacy loss parameter must be explicitly frozen, including zero angle/torsion")
    weights = LossWeights.from_mapping(config["loss"])
    if weights.angle != 0 or weights.torsion != 0:
        raise ValueError("Phase 1 cannot enable angle/torsion objectives")
    policy = Phase1LossPolicy.from_mapping(p)
    if p.get("group_weights") != dict(policy.group_weights) or p.get("task_weights") != dict(policy.task_weights):
        raise ValueError("Every fixed group/task weight must be explicit in execution")
    if p.get("group_normalization") != "fixed_weighted_mean_of_enabled_groups":
        raise ValueError("Unsupported group normalization")
    if variant != "none":
        # Validate actual FP32 coefficients for direct joint too; a positive
        # Python weight is insufficient if the existing loss casts it to zero.
        PositivePiecewiseJoint(variant, n, (PositiveWeightStage(n, {group: 1. for group in GROUP_TASKS}),)).policy_at_update(policy, 0)
    checkpoint = get_path(protocol, "pretraining.checkpoint_rule")
    if checkpoint.get("selection_split") != "fixed_budget" or checkpoint.get("selection_metric") != "fixed_budget_endpoint":
        raise ValueError("Formal runner cannot choose checkpoints by validation performance")
    integer(checkpoint.get("save_every_steps"), "save_every_steps")
    integer(checkpoint.get("keep_checkpoints"), "keep_checkpoints")
    for key in ("lr", "grad_clip_norm"):
        finite(config["optimizer"].get(key), f"optimizer.{key}", positive=True)
    if finite(config["optimizer"].get("weight_decay"), "weight_decay") < 0:
        raise ValueError("Negative weight decay")
    betas = config["optimizer"].get("betas")
    if not isinstance(betas, list) or len(betas) != 2 or any(not 0 <= finite(beta, "beta") < 1 for beta in betas):
        raise ValueError("Frozen AdamW betas invalid")
    config["supervision"]["variant"], config["training"]["seed"] = variant, seed
    return config, policy


def select_formal_recipe(protocol, artifacts, *, variant, seed, recipe_id, config, base_policy):
    """Select one explicit comparison, preserving the original default config.

    Recipe byte SHA and recipe semantic SHA are distinct. No stage/seed is
    inferred; all stages are checked in the actual FP32 loss arithmetic before
    any model or optimizer is constructed. Shared LR/data/budget fields stay
    unchanged. ``direct_joint`` has no additional binding or mutable cursor.
    """
    contrasts = validated_contrasts(protocol)
    if recipe_id == DIRECT_RECIPE:
        return config, None, None
    entry = contrasts.get(recipe_id) if isinstance(recipe_id, str) else None
    if entry is None or entry["variant"] != variant or seed not in entry["seeds"]:
        raise ValueError("Requested recipe/variant/seed is not an explicit frozen contrast")
    if config["supervision"]["variant"] != variant or config["training"]["seed"] != seed:
        raise ValueError("Contrast selection differs from the actual condition/seed configuration")
    field = f"strategy.contrasts.{recipe_id}.recipe_sha256"
    recipe = PositivePiecewiseJoint.from_dict(read_artifact(protocol, artifacts, field))
    if recipe.variant != variant or recipe.max_updates != config["schedule"]["max_steps"]:
        raise ValueError("Contrast recipe condition/update endpoint differs from the paired main matrix")
    stages, integrated, begin = [], {}, 0
    for stage in recipe.stages:
        snapshot = recipe.policy_at_update(base_policy, begin)
        stages.append(snapshot.to_dict())
        for group, coefficient in snapshot.effective_group_coefficients.items():
            integrated[group] = integrated.get(group, 0.) + (stage.end_update_exclusive-begin) * coefficient
        begin = stage.end_update_exclusive
    binding = {"schema_version": "phase1_formal_joint_weighting_v1", "recipe_id": recipe_id,
               "artifact_field": field, "artifact_sha256": entry["recipe_sha256"],
               "recipe": recipe.to_dict(), "recipe_semantic_sha256": recipe.sha256,
               "base_loss_policy_sha256": contract_hash(base_policy.to_dict()), "index_unit": INDEX_UNIT,
               "stage_begin_policies": stages, "integrated_group_coefficients": integrated}
    selected = deepcopy(config)
    selected["schedule"]["strategy"] = "positive_piecewise_joint_from_step_zero"
    selected["schedule"]["joint_weighting"] = {
        name: binding[name] for name in ("recipe_id", "artifact_sha256", "recipe_semantic_sha256", "base_loss_policy_sha256")}
    return selected, recipe, binding


def formal_policy_at_update(binding, base_policy, u, *, recipe=None):
    """Derive the policy from the same frozen base, never from a prior stage."""
    if binding.get("schema_version") != "phase1_formal_joint_weighting_v1" or binding.get("index_unit") != INDEX_UNIT:
        raise ValueError("Unknown formal joint-weighting binding")
    if contract_hash(base_policy.to_dict()) != binding.get("base_loss_policy_sha256"):
        raise ValueError("The frozen base loss policy changed")
    recipe = PositivePiecewiseJoint.from_dict(binding["recipe"]) if recipe is None else recipe
    if recipe.to_dict() != binding["recipe"] or recipe.sha256 != binding.get("recipe_semantic_sha256"):
        raise ValueError("The frozen recipe semantics changed")
    return recipe.policy_at_update(base_policy, u)


def formal_weighting_state(binding, base_policy, updates):
    """Checkpoint/journal state describes the *next* update at a shared cursor."""
    if binding is None:
        return None
    n = binding["recipe"]["max_updates"]
    integer(updates, "joint-weighting next update", minimum=0)
    if updates > n:
        raise ValueError("Joint-weighting cursor passed the fixed update endpoint")
    # Validate even an endpoint's base/recipe binding without calling policy(N).
    checked = formal_policy_at_update(binding, base_policy, 0)
    next_policy = (checked if updates == 0 else formal_policy_at_update(binding, base_policy, updates)) if updates < n else None
    return {"schema_version": "phase1_formal_joint_weighting_state_v1", "binding_sha256": contract_hash(binding),
            "next_optimizer_update_step": updates, "status": "ready" if updates < n else "endpoint",
            "next_policy": next_policy.to_dict() if next_policy is not None else None}


def formal_weighting_metrics(snapshot, binding):
    """Log the zero-based loss index, independently of the post-update cursor."""
    if snapshot is None:
        return {}
    return {"strategy/recipe_id": binding["recipe_id"], "strategy/optimizer_update_step_used": snapshot.optimizer_update_step,
            "strategy/stage_id": snapshot.stage_id, "strategy/begin_update_inclusive": snapshot.begin_update_inclusive,
            "strategy/end_update_exclusive": snapshot.end_update_exclusive,
            "strategy/recipe_semantic_sha256": snapshot.schedule_sha256,
            "strategy/base_loss_policy_sha256": binding["base_loss_policy_sha256"],
            "strategy/loss_policy_sha256": snapshot.policy_sha256,
            **{f"strategy/group_multiplier/{group}": value for group, value in snapshot.group_weight_multipliers.items()},
            **{f"strategy/effective_group_coefficient/{group}": value for group, value in snapshot.effective_group_coefficients.items()}}


def verify_source(protocol, artifacts, source):
    if file_sha256(artifacts["source.source_sha256"]) != source["source_sha256"] or source["source_sha256"] != get_path(protocol, "source.source_sha256"):
        raise ValueError("Live source fingerprint differs from the exact frozen source byte snapshot")
    if source.get("git_commit") != get_path(protocol, "source.commit"):
        raise ValueError("Live source commit differs from frozen source commit")


def module_manifest(model):
    return {"state": {name: {"shape": list(value.shape), "dtype": str(value.dtype)} for name, value in model.state_dict().items()},
            "parameters": {name: {"shape": list(value.shape), "dtype": str(value.dtype), "requires_grad": value.requires_grad}
                           for name, value in model.named_parameters()},
            "total_parameters": sum(value.numel() for value in model.parameters())}


def verify_architecture(model, config, artifact):
    expected = {key: config[key] for key in ("architecture", "backbone", "expert", "head")}
    if artifact.get("schema_version") != "phase1_architecture_v1" or artifact.get("config") != expected or artifact.get("module_manifest") != module_manifest(model):
        raise ValueError("Frozen full architecture/module manifest differs from constructed model")


def backbone_state_hash(model):
    digest = hashlib.sha256()
    for name, value in sorted(model.backbone.state_dict().items()):
        tensor = value.detach().cpu().contiguous()
        digest.update(f"{name}:{tensor.dtype}:{tuple(tensor.shape)}\n".encode())
        digest.update(tensor.numpy().tobytes())
    return digest.hexdigest()


def verify_paired_initialization(model, artifact, seed):
    actual = backbone_state_hash(model)
    if artifact != {"schema_version": "phase1_paired_init_v1", "seed": seed, "backbone_state_sha256": actual, "hash_recipe": INIT_RECIPE}:
        raise ValueError("Fresh random H0 does not match the frozen same-seed paired initialization artifact")
    return actual


def _fit_record_keys(train, entry, name):
    if not isinstance(entry, dict) or set(entry) != {"logical_indices", "record_keys"}:
        raise ValueError(f"Missing complete frozen {name} fit IDs")
    indices = entry["logical_indices"]
    if not isinstance(indices, list) or not indices or len(set(indices)) != len(indices):
        raise ValueError(f"Empty/duplicate {name} fit indices")
    for index in indices:
        integer(index, f"{name} fit index", minimum=0)
        if index >= len(train):
            raise ValueError(f"{name} fit index outside full training view")
    expected = [f"{shard}:{real}" for shard, real in (train.record_ref(index) for index in indices)]
    if entry["record_keys"] != expected:
        raise ValueError(f"{name} record IDs do not exactly match the frozen training view")
    return indices, expected


def load_fitted_controls(controls, fit_ids, train, config):
    """Validate/load train-only snapshots; intentionally contains no fit call."""
    if train.kind != "train" or train.diagnostic_only or controls.get("schema_version") != "phase1_fitted_controls_v1":
        raise ValueError("Controls require the full frozen training view")
    if fit_ids.get("schema_version") != "phase1_fit_ids_v1" or fit_ids.get("train_pool_hash") != train.pool_hash or fit_ids.get("train_view_hash") != train.view_hash:
        raise ValueError("Frozen control fit IDs reference another training pool/view")
    statistics, provenance = controls.get("statistics"), controls.get("statistics_provenance", {})
    if provenance.get("diagnostic_only") is not False or provenance.get("train_pool_hash") != train.pool_hash or provenance.get("train_view_hash") != train.view_hash:
        raise ValueError("Normalizer is diagnostic-only or references another training pool/view")
    for field, expected in {"estimator_version": "phase1_masked_population_std_v1", "atom_encoding": "zero_based",
            "energy_unit": "kcal/mol", "charge_definition": "MOPAC NET ATOMIC CHARGES", "charge_unit": "e"}.items():
        if provenance.get(field) != expected:
            raise ValueError(f"Frozen normalizer {field} differs from the actual Phase 1 estimator/label units")
    integer(provenance.get("seed"), "statistics fit seed", minimum=0)
    cap = integer(provenance.get("cap"), "statistics fit cap")
    contract = train_regression_normalization(statistics, provenance)
    indices, keys = _fit_record_keys(train, fit_ids.get("statistics"), "statistics")
    if (indices != provenance.get("sampled_logical_indices") or len(indices) != provenance.get("sampled_structure_count")
            or len(indices) > cap or canonical_hash(keys) != provenance.get("sampled_record_keys_hash")):
        raise ValueError("Normalizer actual fitted record IDs differ from the frozen fit-ID artifact")
    mode = config["phase1"].get("regression_output_mode")
    frozen_contract = config["head"].get("regression_output_normalization")
    if mode == "train_affine":
        if frozen_contract != contract:
            raise ValueError("Frozen affine head does not exactly match train-fitted controls")
    elif mode != "raw" or frozen_contract is not None:
        raise ValueError("Frozen regression output mode/contract is invalid")
    state = controls.get("baselines", {})
    ntypes = integer(state.get("n_atom_types"), "baseline.n_atom_types", minimum=2)
    if ntypes != config["backbone"].get("n_atom_types"):
        raise ValueError("Baseline vocabulary differs from model vocabulary")
    bprov = state.get("provenance", {})
    declared = bprov.get("train_manifest", {})
    if (declared.get("role") != "train" or declared.get("diagnostic_only") is not False
            or declared.get("pool_hash") != train.pool_hash or declared.get("view_hash") != train.view_hash
            or bprov.get("element_majority_source") != "train_topology_actual_corrupted_target_x"):
        raise ValueError("Baselines lack full train-only/task-specific provenance")
    bindices, _ = _fit_record_keys(train, fit_ids.get("baselines"), "baselines")
    if len(bindices) != bprov.get("fit_records") or bprov.get("element_fit_view_records") != len(bindices):
        raise ValueError("Baseline actual fitted record count differs from frozen fit IDs")
    view = state.get("element_view", {})
    if (set(view) != {"mode", "level", "seed", "seed_rule"} or view.get("mode") != "topo"
            or view.get("level") != config["phase1"]["topology_level"] or view.get("seed_rule") != "seed_plus_logical_index"):
        raise ValueError("Element baseline must use the frozen training actual-corruption topology view")
    integer(view.get("seed"), "element_view.seed", minimum=0)
    def vector(name, length, *, counts=False):
        values = np.asarray(state.get(name), dtype=np.float64)
        if values.shape != (length,) or not np.isfinite(values).all() or (counts and (np.any(values < 0) or np.any(values != np.floor(values)))):
            raise ValueError(f"Malformed frozen baseline vector: {name}")
        return values.astype(np.int64) if counts else values
    energy = vector("energy_coefficients", ntypes + 1)
    charges, charge_counts = vector("charge_means", ntypes), vector("charge_counts", ntypes, counts=True)
    element = integer(state.get("element_majority"), "element_majority", minimum=0)
    bond = integer(state.get("bond_majority"), "bond_majority")
    if element >= ntypes - 1 or bond > 5 or bprov.get("element_fit_labels", 0) <= 0 or bprov.get("energy_fit_labels", 0) <= 0 or charge_counts.sum() <= 0:
        raise ValueError("Frozen baseline labels/classes are unavailable or outside legal vocabulary")
    if integer(bprov.get("charge_fit_labels"), "baseline charge fit labels") != int(charge_counts.sum()):
        raise ValueError("Frozen charge baseline counts differ from its actual fit-label provenance")
    class_counts = bprov.get("element_class_counts")
    if not isinstance(class_counts, dict) or not class_counts:
        raise ValueError("Element baseline requires frozen actual-corruption class counts")
    for label, count in class_counts.items():
        if not isinstance(label, str) or not label.isdecimal() or str(int(label)) != label or not 0 <= int(label) < ntypes - 1:
            raise ValueError("Frozen element class-count key outside actual target vocabulary")
        integer(count, "element class-count")
    expected_majority = int(min(class_counts, key=lambda label: (-class_counts[label], int(label))))
    if sum(class_counts.values()) != bprov["element_fit_labels"] or element != expected_majority:
        raise ValueError("Frozen element majority/class counts differ from actual fit-label provenance")
    graph, nodes = state.get("graph_means"), state.get("node_predictions")
    specs = {spec.name: spec for spec in PHASE1_CHARGE_DESCRIPTOR_SPECS + PHASE1_ELEMENT_DESCRIPTOR_SPECS}
    if (not isinstance(graph, dict) or not set(graph).issubset(GRAPH_DESCRIPTOR_NAMES)
            or not set(PHASE1_GRAPH_DESCRIPTOR_NAMES).issubset(graph) or not isinstance(nodes, dict) or set(nodes) != set(specs)):
        raise ValueError("Formal baseline snapshot must include all 23 graph and 6 node targets; omitted values cannot masquerade as unavailable labels")
    for name, value in {**graph, **nodes}.items():
        finite(value, f"baseline.{name}")
        if name in specs and specs[name].task_type != "regression":
            classes = 2 if specs[name].task_type == "binary" else specs[name].num_classes
            if value != math.floor(value) or not 0 <= value < classes:
                raise ValueError(f"Invalid node majority class: {name}")
    baseline = TrainingBaselines(ntypes, energy_coefficients=energy, charge_means=charges, charge_counts=charge_counts,
        element_majority=element, bond_majority=bond, graph_means=graph, node_predictions=nodes, provenance=bprov)
    stats = deepcopy(statistics)
    for key in ("graph_desc_mu", "graph_desc_std"):
        stats[key] = torch.tensor(stats[key], dtype=torch.float32)
    return stats, baseline, {"statistics": provenance, "baseline": bprov, "element_view": view,
                             "continuous_output_contract_sha256": contract["contract_sha256"] if mode == "train_affine" else None}


def verify_identity_ledger(dataset, declaration, *, artifact_directory):
    if dataset.diagnostic_only or declaration.get("rows") != len(dataset):
        raise ValueError("Identity ledger must cover every record in the actual full view")
    path = Path(str(declaration.get("path", "")))
    path = path if path.is_absolute() else Path(artifact_directory) / path
    if file_sha256(path) != declaration.get("sha256"):
        raise ValueError("Full identity ledger byte hash changed")
    identities, count = set(), 0
    with path.open(encoding="utf-8") as stream:
        for count, line in enumerate(stream, 1):
            if count > len(dataset):
                raise ValueError("Identity ledger contains extra records")
            row = json.loads(line)
            shard, real = dataset.record_ref(count - 1)
            if (row.get("manifest_pool_hash") != dataset.pool_hash or row.get("shard") != shard
                    or row.get("real_index") != real or row.get("status") != "identity_ok"
                    or row.get("identity_policy") != IDENTITY_POLICY or row.get("source_field") not in {"smiles", "isomeric_smiles", "canonical_smiles"}
                    or not isinstance(row.get("inchikey"), str) or not _INCHI.fullmatch(row["inchikey"])):
                raise ValueError(f"Identity ledger does not cover exact active {dataset.kind} record {count - 1}")
            if "logical_index" in row and row["logical_index"] != count - 1:
                raise ValueError("Identity ledger logical order changed")
            identities.add(row["inchikey"])
    if count != len(dataset):
        raise ValueError("Partial identity ledger cannot prove complete decontamination")
    return identities


def verify_decontamination(protocol, evidence, train, validation, downstream, *, artifact_directory, downstream_directory):
    if evidence.get("schema_version") == "phase1_common_identity_and_composition_embargo_plan_v2":
        from .decontamination_v2 import verify_common_embargo
        return verify_common_embargo(protocol, evidence, train, validation, downstream,
            artifact_directory=artifact_directory, downstream_directory=downstream_directory)
    if evidence.get("schema_version") != "phase1_decontamination_v1" or evidence.get("identity_policy") != IDENTITY_POLICY:
        raise ValueError("Complete frozen decontamination evidence is required")
    for name, field in (("source_manifest_sha256", "data.source_manifest_sha256"), ("split_manifest_sha256", "data.split_manifest_sha256"),
                        ("downstream_split_manifest_sha256", "downstream.split_manifest_sha256")):
        if evidence.get(name) != get_path(protocol, field):
            raise ValueError(f"Decontamination evidence references another artifact: {name}")
    ledgers = evidence.get("ledgers", {})
    if set(ledgers) != {"train", "validation"}:
        raise ValueError("Both full active-pool identity ledgers are required")
    train_keys = verify_identity_ledger(train, ledgers["train"], artifact_directory=artifact_directory)
    val_keys = verify_identity_ledger(validation, ledgers["validation"], artifact_directory=artifact_directory)
    specification = deepcopy(downstream.get("test_identity_specification", {}))
    for entry in specification.get("test_files", []):
        path = Path(entry["path"])
        if not path.is_absolute():
            entry["path"] = str(Path(downstream_directory) / path)
    test_keys, test_proof = frozen_test_identities(specification)
    intersections = {"train_validation": train_keys & val_keys, "train_test": train_keys & test_keys, "validation_test": val_keys & test_keys}
    if any(intersections.values()):
        raise ValueError("Active full manifests contain molecular identity overlap: " + ", ".join(f"{name}={len(keys)}" for name, keys in intersections.items()))
    return {"scope": "complete_active_manifests_and_frozen_final_test_structures_only", "identity_policy": IDENTITY_POLICY,
            "train_unique": len(train_keys), "validation_unique": len(val_keys), "overlaps": {name: 0 for name in intersections},
            "train_identity_hash": canonical_hash(sorted(train_keys)), "validation_identity_hash": canonical_hash(sorted(val_keys)), "test": test_proof}


def cyclic_batch_indices(permutation, update, batch_size):
    integer(update, "update cursor", minimum=0)
    integer(batch_size, "base batch")
    if len(permutation) == 0:
        raise ValueError("Empty full training view")
    return [int(permutation[(update * batch_size + offset) % len(permutation)]) for offset in range(batch_size)]


def check_atom_caps(atom_counts, *, per_molecule, per_batch):
    integer(per_molecule, "max_atoms_per_molecule")
    integer(per_batch, "max_atoms_per_batch")
    for count in atom_counts:
        integer(count, "actual atoms")
    if max(atom_counts, default=0) > per_molecule or sum(atom_counts) > per_batch:
        raise RuntimeError("Frozen atom cap exceeded; filtering, replacing molecules or lowering batch/views is forbidden")


@dataclass
class BudgetClock:
    wall_cap_seconds: float
    gpu_cap_hours: float
    carried_wall_seconds: float = 0.
    began: float = 0.

    @classmethod
    def from_protocol(cls, protocol, *, carried_wall_seconds=0., began=None):
        return cls(3600 * finite(get_path(protocol, "compute.max_walltime_hours"), "wall cap", positive=True),
                   finite(get_path(protocol, "pretraining.budget.gpu_hours_per_condition"), "GPU hours cap", positive=True),
                   finite(carried_wall_seconds, "carried wall"), time.perf_counter() if began is None else began)

    def usage(self, now=None):
        seconds = self.carried_wall_seconds + max(0., (time.perf_counter() if now is None else now) - self.began)
        if self.carried_wall_seconds < 0:
            raise ValueError("Negative carried budget usage")
        return {"wall_seconds": seconds, "gpu_hours": seconds / 3600., "gpu_count": 1}

    def exhausted(self, now=None):
        usage = self.usage(now)
        return usage["wall_seconds"] >= self.wall_cap_seconds or usage["gpu_hours"] >= self.gpu_cap_hours


def finalize_endpoint(*, candidate_complete, finish_tracker, save_endpoint, publish_endpoint, revoke_endpoint, clock):
    """An endpoint becomes usable only after every tracked finalization step.

    Callbacks operate only on the current run. Any tracker, checkpoint/storage,
    publication or budget failure revokes the endpoint. No new budget is added.
    """
    try:
        # All large/failure-prone checkpoint and storage preparation occurs
        # while the tracker can still record failure. Publication afterwards
        # must be an atomic rename of an already prepared file, not a copy.
        if candidate_complete and not clock.exhausted():
            save_endpoint()
        finish_tracker()
        if not candidate_complete or clock.exhausted():
            revoke_endpoint()
            return "budget_stop"
        publish_endpoint()
        if clock.exhausted():
            revoke_endpoint()
            return "budget_stop"
        return "complete"
    except BaseException:
        revoke_endpoint()
        raise


def verify_tracker_lineage(run, *, run_id, mode, resume=False, expected_next_step=None, expected_run_path=None):
    """Validate actual W&B SDK lineage, never infer appendability from run ID.

    Offline fresh runs are supported. Offline segments cannot establish resume
    until their merging/append behavior has been validated for this deployment.
    W&B's internal history cursor differs from the scientific optimizer axis.
    """
    if resume and mode != "online":
        raise RuntimeError("Offline W&B resume is unsupported until segment append/sync behavior is verified; no fresh segment fallback")
    if run is None or run.id != run_id or getattr(run, "disabled", False) or str(run.settings.mode) != mode:
        raise RuntimeError("A real persistent W&B run with matching ID/mode is required before training")
    path = getattr(run, "path", None)
    if not isinstance(path, str) or not path:
        raise RuntimeError("W&B run has no entity/project/run identity")
    next_step = integer(run.step, "W&B internal next step", minimum=0)
    if resume:
        if not getattr(run, "resumed", False) or path != expected_run_path or next_step != expected_next_step:
            raise RuntimeError("W&B did not resume the exact saved path/history cursor; no lost or replayed history is allowed")
    elif getattr(run, "resumed", False) or next_step != 0:
        raise RuntimeError("Fresh formal tracking unexpectedly reuses existing W&B history")
    return next_step, path


def validate_formal_resume(payload, *, expected_manifest, expected_config, expected_run_id, expected_init_hash, journal, checkpoint_sha256):
    """Reject historical/diagnostic checkpoints before mutating a live model."""
    extra = payload.get("extra", {})
    if extra.get("formal_run_schema") != FORMAL_RUN_SCHEMA or payload.get("dataset_manifest") != expected_manifest:
        raise RuntimeError("Only this formal run's exact frozen protocol checkpoint may resume")
    if payload.get("semantic_config") != semantic_config(expected_config) or payload.get("semantic_config_sha256") != contract_hash(semantic_config(expected_config)):
        raise RuntimeError("Formal resume scientific configuration changed")
    if extra.get("wandb_run_id") != expected_run_id or journal.get("wandb_run_id") != expected_run_id:
        raise RuntimeError("Formal resume W&B lineage mismatch")
    if extra.get("paired_initial_H0_sha256") != expected_init_hash or journal.get("paired_initial_H0_sha256") != expected_init_hash:
        raise RuntimeError("Formal resume paired initialization mismatch")
    if journal.get("schema_version") != FORMAL_RUN_SCHEMA or journal.get("manifest_sha256") != contract_hash(expected_manifest):
        raise RuntimeError("Formal resume budget journal references another protocol/run")
    if not isinstance(expected_run_id, str) or not expected_run_id.strip():
        raise RuntimeError("Formal resume has no real tracker lineage")
    if journal.get("status") in {"complete", "budget_stop"}:
        raise RuntimeError("Completed/exhausted formal runs cannot acquire a new budget via resume")
    if journal.get("status") != "failed" or payload.get("checkpoint_type") not in {"initial_random_state", "periodic", "pending_fixed_budget_endpoint", "fixed_budget_endpoint"}:
        raise RuntimeError("Formal resume requires a closed failed attempt and a resumable formal state, never an active/unknown/budget-stop run")
    n = expected_config["schedule"]["max_steps"]
    batch_size = expected_config["training"]["base_molecules_per_batch"]
    updates = integer(payload.get("optimizer_update_step"), "resume updates", minimum=0)
    exposure = integer(extra.get("base_molecule_exposure"), "resume base exposure", minimum=0)
    if updates > n or payload.get("global_exposure_step") != updates or exposure != updates * batch_size:
        raise RuntimeError("Formal resume counters violate the fixed base-exposure/update budget")
    if expected_config["supervision"]["variant"] == "none" and (updates or exposure):
        raise RuntimeError("None control cannot resume optimizer updates")
    binding = expected_manifest.get("joint_weighting")
    if binding is not None:
        try:
            base_policy = Phase1LossPolicy.from_mapping(expected_manifest["loss_policy"])
            expected_weighting = formal_weighting_state(binding, base_policy, updates)
        except (KeyError, TypeError, ValueError) as error:
            raise RuntimeError("Formal resume expected joint-weighting contract is invalid") from error
        if extra.get("joint_weighting_state") != expected_weighting or journal.get("joint_weighting_state") != expected_weighting:
            raise RuntimeError("Formal resume next policy/stage/hash differs from the exact frozen update cursor")
    elif extra.get("joint_weighting_state") is not None or journal.get("joint_weighting_state") is not None:
        raise RuntimeError("Direct-joint resume cannot import a contrast weighting state")
    if payload.get("checkpoint_type") in {"pending_fixed_budget_endpoint", "fixed_budget_endpoint"} and (extra.get("evaluation_completion") != "complete" or
            (expected_config["supervision"]["variant"] != "none" and updates != n)):
        raise RuntimeError("A pending endpoint requires full completed validation and the exact frozen update endpoint")
    if (journal.get("optimizer_update_step") != updates or journal.get("base_molecule_exposure") != exposure
            or journal.get("latest_checkpoint_sha256") != checkpoint_sha256):
        raise RuntimeError("Resume must use latest committed state; replaying uncheckpointed effective updates would exceed the matched exposure budget")
    saved_usage = extra.get("budget_usage", {})
    wall = finite(journal.get("budget_usage", {}).get("wall_seconds"), "journal wall usage")
    gpu_hours = finite(journal.get("budget_usage", {}).get("gpu_hours"), "journal GPU usage")
    if wall < 0 or gpu_hours != wall / 3600 or wall < finite(saved_usage.get("wall_seconds"), "checkpoint wall usage"):
        raise RuntimeError("Formal resume budget usage regressed or is inconsistent")
    if payload.get("scheduler_state", {}).get("last_epoch") != updates:
        raise RuntimeError("Formal resume scheduler cursor differs from actual optimizer updates")
    tracker_step = integer(journal.get("tracker_next_step"), "saved W&B history cursor", minimum=0)
    checkpoint_tracker_step = integer(extra.get("tracker_next_step"), "checkpoint W&B history cursor", minimum=0)
    if (checkpoint_tracker_step > tracker_step or not isinstance(journal.get("tracker_run_path"), str)
            or not journal["tracker_run_path"] or extra.get("tracker_run_path") != journal["tracker_run_path"]):
        raise RuntimeError("Formal resume lacks a consistent saved W&B path/history cursor")
    return wall
