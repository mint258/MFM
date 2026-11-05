"""Bound evidence for the single, preregistered v3 pretraining-seed SD.

This is model-owned analysis metadata, not a data-line contract or an experiment
runner. No configuration is selected here. Existing encoder/trainer defaults are
untouched. A bound execution receipt is an operator-verified accounting projection;
its authenticity and the public availability of a Git commit remain external facts.
"""
from __future__ import annotations

from dataclasses import dataclass
from copy import deepcopy
from datetime import datetime
import hashlib
import io
import json
import math
from pathlib import Path
import re
import subprocess


METRIC = "equal_mean_18_task_readout_normalized_error_improvements_v1"
READOUTS = ("ridge", "linear64_relu")
# Only these TOP-LEVEL run-location fields may be omitted. Nested seeds (readout,
# corruption, initialization policies, etc.) stay scientific until a new protocol.
CONFIG_RUN_KEYS = frozenset(("seed", "output_root", "cache_root", "run_id"))
BINDING_RUN_KEYS = frozenset(("configuration_sha256", "trainer_configuration_sha256",
                              "training_run_id", "training_start_utc", "job_id"))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical(value, *, ascii=False):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
        ensure_ascii=ascii, allow_nan=False).encode("utf-8")).hexdigest()


def digest(value, length=64):
    require(type(value) is str and re.fullmatch(r"[0-9a-f]{%d}" % length, value) is not None,
            "Full lowercase source digest required")
    return value


def _json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "Duplicate evidence key")
            result[key] = value
        return result
    return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite evidence")))


def bound_bytes(reference, *, maximum=16*1024**2):
    require(type(reference) is dict and {"path", "sha256"} <= set(reference), "Bound file reference required")
    digest(reference["sha256"])
    path = Path(reference["path"])
    require(path.is_file() and not path.is_symlink() and 0 < path.stat().st_size <= maximum,
            "Bounded ordinary evidence file required")
    raw = path.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == reference["sha256"], "Evidence bytes differ from bound SHA")
    return raw


def bound_json(reference):
    return _json(bound_bytes(reference))


def _number(value):
    require(type(value) in (int, float) and math.isfinite(value), "Finite numeric metric required")
    return float(value)


def _integer(value, *, minimum=0):
    require(type(value) is int and value >= minimum, "Explicit nonnegative integer required")
    return value


def _utc(value):
    require(type(value) is str, "Explicit UTC timestamp required")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    require(parsed.utcoffset() is not None and parsed.utcoffset().total_seconds() == 0,
            "Accounting start timestamp must be UTC")
    return parsed.timestamp()


def git_registration(reference, *, expected_sha256):
    """Read a document from a FIXED Git commit:path, never from result ranking.

    Caller must independently pin expected_sha256 from the preregistration review.
    Commit dates alone do not prove when a commit was publicly available.
    """
    require(type(reference) is dict and set(reference) == {"repository", "commit", "path", "sha256"},
            "Explicit Git registration reference required")
    commit = digest(reference["commit"], 40)
    require(reference["sha256"] == digest(expected_sha256), "Out-of-band anchor registration SHA differs")
    relative = reference["path"]
    require(type(relative) is str and relative and not relative.startswith(("/", "-"))
            and "\\" not in relative and all(part not in ("", ".", "..") for part in relative.split("/")),
            "Safe repository-relative registration path required")
    repo = str(Path(reference["repository"]).absolute())
    raw = subprocess.run(["git", "-C", repo, "show", commit+":"+relative], check=True,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout
    require(0 < len(raw) <= 128*1024 and hashlib.sha256(raw).hexdigest() == expected_sha256,
            "Preregistered Git blob differs")
    stamp = subprocess.run(["git", "-C", repo, "show", "-s", "--format=%ct", commit], check=True,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.decode().strip()
    require(stamp.isascii() and stamp.isdecimal(), "Git commit timestamp unavailable")
    return _json(raw), int(stamp)


def registered_anchor(reference, *, expected_sha256):
    value, stamp = git_registration(reference, expected_sha256=expected_sha256)
    require(value.get("schema") == "model_v3_global_seed_sd_registration_v1"
            and type(value.get("anchor_id")) is str and bool(value["anchor_id"]), "Explicit global anchor registration required")
    seeds = value.get("pretraining_seeds")
    require(type(seeds) is list and len(seeds) == 2 and all(type(s) is int and s >= 0 for s in seeds)
            and len(set(seeds)) == 2, "Preregister exactly two different pretraining seeds")
    for key in ("scientific_identity_sha256", "panel_identity_sha256"):
        digest(value.get(key))
    require(value.get("metric") == METRIC, "Only the complete primary panel defines seed SD")
    return value, stamp


def scientific_identity(*, configuration, sampler, trainer, scheduler, bindings,
                        checkpoint_samples, request, panel_identity, seed, execution, runtime):
    """Also usable BEFORE training with the exact planned runtime contracts.

    The evaluated output checkpoint is intentionally absent. A checkpoint inside
    the original scientific configuration may instead specify initialization, so
    that field is retained. No recursive deletion of arbitrary ``seed`` keys.
    """
    require(configuration.get("seed") == sampler.get("seed") == seed,
            "Actual configuration/sampler pretraining seed differs")
    trainer = deepcopy(trainer)
    views = trainer["view_configuration"]
    require(views.get("seed") == seed, "Actual structural-view seed differs from member pretraining seed")
    configuration = deepcopy(configuration)
    # These spellings are accepted only when the WHOLE supplied view object is
    # identical to the actual saved StructuralViewConfig, not merely its seed.
    for key in ("view_configuration", "view_config"):
        if key in configuration:
            require(configuration[key] == views, "Original/saved structural-view configurations differ")
            del configuration[key]["seed"]
    del views["seed"]
    return {"schema": "model_v3_seed_excluded_scientific_identity_v1",
        "configuration": {k: v for k, v in configuration.items() if k not in CONFIG_RUN_KEYS},
        "sampler_contract": {k: v for k, v in sampler.items() if k != "seed"},
        "trainer_contract": trainer, "scheduler_contract": scheduler,
        "execution": execution, "runtime": runtime,
        "checkpoint_samples_consumed": _integer(checkpoint_samples, minimum=1),
        "bindings": {k: v for k, v in bindings.items() if k not in BINDING_RUN_KEYS},
        "architecture_sha256": request["architecture_sha256"], "panel_identity": panel_identity,
        "evaluation_sources": request["source_files"], "h0_packing": request["h0_packing"],
        "h0_packing_budget_sha256": request["h0_packing_budget_sha256"],
        "h0_packing_plan_sha256": request["h0_packing_plan_sha256"]}


def _panel_score(panel, result):
    require(panel.get("schema") == "model_v3_dev_panel_v1" and len(panel.get("tasks", [])) == 9,
            "Existing frozen nine-task panel required")
    ids = [task["task_id"] for task in panel["tasks"]]
    require(len(set(ids)) == 9 and set(panel["readouts"]) == set(READOUTS) | {"pooling_note"},
            "Exact panel task/readout coverage required")
    expected = {task+"@"+readout for task in ids for readout in READOUTS}
    summaries = result["summaries"]
    primary = summaries["primary_18_cells"]
    require(primary.get("complete") is True and set(primary.get("tasks", {})) == expected,
            "Incomplete primary 18-cell panel")
    values = {}
    for key, row in primary["tasks"].items():
        error, reference = _number(row["error"]), _number(row["reference_error"])
        require(error >= 0 and reference > 0 and _integer(row["observed_labels"], minimum=1)
                and _integer(row["observed_molecules"], minimum=1), "Undefined/empty panel cell")
        score = _number(row["normalized_improvement"])
        require(math.isclose(score, (reference-error)/reference, rel_tol=1e-12, abs_tol=1e-12),
                "Panel cell normalized improvement differs")
        values[key] = score
    for name in ("primary_18_cells", *READOUTS):
        summary = summaries[name]
        subset = expected if name == "primary_18_cells" else {k for k in expected if k.endswith("@"+name)}
        require(summary.get("complete") is True and set(summary.get("tasks", {})) == subset,
                "Incomplete separate readout report")
        require(summary.get("architecture_sha256") == result["architecture_sha256"], "Panel architecture differs")
        require(all(summary["tasks"][k] == primary["tasks"][k] for k in subset), "Readout cell reports disagree")
        require(math.isclose(_number(summary["mean_normalized_improvement"]),
                math.fsum(values[k] for k in subset)/len(subset), rel_tol=1e-12, abs_tol=1e-12),
                "Panel/readout aggregate differs from complete cells")
    return _number(primary["mean_normalized_improvement"])


@dataclass(frozen=True)
class RunEvidence:
    score: float
    seed: int
    scientific_identity_sha256: str
    panel_identity_sha256: str
    checkpoint_sha256: str
    training_run_id: str
    training_start_epoch: float
    evidence_sha256: str
    sources: dict
    checkpoint_samples: int
    curve_identity_sha256: str


def reject_engineering_configuration(configuration):
    """Engineering fixtures never enter registered scientific selection."""
    require(configuration.get('engineering_only') is not True
        and configuration.get('experiment_scope') != 'ENGINEERING_SYNTHETIC_ONLY',
        'Engineering/synthetic configuration is ineligible for scientific selection')


def inspect_run(entry, *, panel_reference, preregistration_commit):
    """Verify source chains of an actual v3 sample-checkpoint panel evaluation.

    Safe CPU-only checkpoint loading is intentional: raw configuration hashes
    alone cannot establish the actual recipe, sampler seed or consumed budget.
    No model is constructed, no target payload is opened, and no optimizer runs.
    """
    import torch

    require(type(entry) is dict and set(entry) == {"request", "result", "sampler_contract", "memberships", "execution", "source_snapshot_root"},
            "Complete bound run evidence required")
    panel = bound_json(panel_reference)
    request, result = bound_json(entry["request"]), bound_json(entry["result"])
    require(request.get("schema") == "model_v3_dev_evaluation_request_v1"
            and result.get("schema") == "model_v3_dev_evaluation_result_v1"
            and result.get("status") == "COMPLETED", "Completed native development evaluation required")
    require(request.get("reference_kind", "primary") == result.get("reference_kind", "primary") == "primary",
            "Historical sanity reference cannot define decisions")
    require(result.get("request_sha256") == entry["request"]["sha256"]
            and request["panel"] == panel_reference and result["panel_sha256"] == panel_reference["sha256"],
            "Evaluation request/panel binding differs")
    digest(preregistration_commit, 40)
    require(request["preregistration_sha"] == preregistration_commit, "Evaluation does not bind the registered anchor commit")
    for key in ("code_sha", "preregistration_sha", "architecture_sha256", "data_version", "pretraining_seed",
                "h0_packing_budget_sha256", "h0_packing_plan_sha256"):
        require(request[key] == result[key], "Evaluation provenance differs: "+key)
    digest(request["code_sha"], 40); digest(request["architecture_sha256"])
    seed = _integer(request["pretraining_seed"])
    require(result["training_store_sha256"] == request["training_store"]["sha256"], "Training store binding differs")
    store = _json(bound_bytes(request["training_store"], maximum=512*1024**2))
    require(store.get("schema") == "model_v3_training_role_store_v1"
            and store.get("source_complete") is True and store.get("targets_in_metadata") is False
            and store.get("native_record_hashes_preserved") is True and store.get("data_version") == request["data_version"],
            "Actual complete target-free TRAIN metadata sidecar required")
    snapshot = Path(entry["source_snapshot_root"]).absolute()
    require(snapshot.is_dir() and not snapshot.is_symlink() and request.get("source_files"),
            "Actual immutable executed-source snapshot required")
    source_paths = set()
    for source in request["source_files"]:
        relative = source["path"]
        require(type(relative) is str and relative and not relative.startswith(("/", "-"))
                and "\\" not in relative and all(p not in ("", ".", "..") for p in relative.split("/"))
                and relative not in source_paths, "Unique repository-relative executed-source inventory required")
        path = snapshot/relative
        require(path.resolve().is_relative_to(snapshot.resolve()), "Executed source escapes snapshot")
        bound_bytes({"path": str(path), "sha256": source["sha256"]})
        source_paths.add(relative)
    configuration = bound_json(request["model_configuration"])
    reject_engineering_configuration(configuration)
    require(configuration.get("seed") == seed, "Actual original configuration seed differs")
    completion_ref = request.get("training_completion")
    require(completion_ref is not None, "Actual v3 checkpoint COMPLETE binding required")
    marker = bound_json(completion_ref)
    cp = request["checkpoint"]
    require(Path(cp["path"]).name == "payload.pt" and Path(completion_ref["path"]).name == "COMPLETE.json"
            and Path(cp["path"]).absolute().parent == Path(completion_ref["path"]).absolute().parent,
            "Checkpoint payload and COMPLETE must share an immutable directory")
    raw = bound_bytes(cp, maximum=4*1024**3)
    require(marker.get("schema") == "model_v3_training_checkpoint_v1"
            and marker.get("payload_sha256") == cp["sha256"] and marker.get("payload_bytes") == len(raw),
            "Checkpoint COMPLETE byte binding differs")
    payload = torch.load(io.BytesIO(raw), map_location="cpu", weights_only=True)
    del raw
    require(payload.get("schema") == marker["schema"] and payload["bindings"] == marker["bindings"],
            "Checkpoint schema/bindings differ")
    bindings, extra = payload["bindings"], payload["extra_state"]
    contract, sampler = extra["contract"], bound_json(entry["sampler_contract"])
    scheduler_state = extra["scheduler"]
    scheduler = scheduler_state["contract"]
    require(extra.get("schema") == "model_v3_trainer_resume_v1"
            and contract.get("schema") == "model_v3_step_trainer_v1"
            and sampler.get("schema") == "model_v3_uniform_molecule_sampler_v1"
            and scheduler.get("schema") == "model_v3_sample_lr_v1", "Recognized actual trainer/sampler/scheduler contracts required")
    require(bindings["configuration_sha256"] == request["model_configuration"]["sha256"]
            and bindings["trainer_configuration_sha256"] == canonical(contract)
            and bindings["code_sha"] == request["code_sha"] and bindings["data_version"] == request["data_version"],
            "Actual checkpoint scientific bindings differ")
    for key in ("registry_sha256", "normalization_sha256", "trainer_source_sha256", "adapter_sha256"):
        digest(bindings.get(key))
    require(contract["adapter_sha256"] == bindings["adapter_sha256"], "Actual provider adapter binding differs")
    saved_groups, declared_groups = payload["optimizer"]["param_groups"], contract["optimizer_options"]
    require(len(saved_groups) == len(declared_groups) == len(contract["optimizer_parameter_groups"])
            and len(saved_groups) > 0, "Actual optimizer parameter-group coverage differs")
    for saved, declared, names in zip(saved_groups, declared_groups, contract["optimizer_parameter_groups"]):
        require(len(saved["params"]) == len(names)
                and canonical({k: v for k, v in saved.items() if k not in ("params", "lr", "initial_lr")}) == canonical(declared),
                "Actual saved optimizer recipe differs from trainer contract")
    require(sampler["seed"] == seed and payload["sampler"]["schema"] == sampler["schema"]
            and canonical(sampler, ascii=True) == payload["sampler"]["contract_sha256"],
            "Actual sampler seed/contract differs")
    require(canonical(scheduler) == scheduler_state["binding_sha256"] == contract["scheduler_binding"],
            "Actual scheduler binding differs")
    count = _integer(payload["clock"]["samples_consumed"], minimum=1)
    updates = _integer(payload["clock"]["optimizer_updates"], minimum=1)
    require(marker["samples_consumed"] == payload["sampler"]["samples_consumed"]
            == scheduler_state["samples_consumed"] == count and marker["optimizer_updates"] == updates,
            "Checkpoint sample/update cursors differ")
    require(count <= _integer(sampler["sample_budget"], minimum=1) == scheduler["sample_budget"],
            "Actual sampler/scheduler sample budgets differ")
    pair = result["encoder_pair"]
    require(pair.get("schema") == "model_v3_bound_encoder_pair_v1"
            and pair["checkpoint"] == cp and pair["original_configuration"] == request["model_configuration"]
            and pair["checkpoint_schema"] == "model_v3_immutable_sample_checkpoint"
            and pair["pretraining_seed"] == seed and pair["reference_kind"] == "primary"
            and pair["architecture_sha256"] == request["architecture_sha256"]
            and pair["random_reference_seed"] == result["random_reference_initialization_seed"] == 20261025,
            "Actually evaluated encoder/checkpoint/seed/reference differs")
    require(result["readout_seed"] == panel["readouts"]["linear64_relu"]["seed"], "Fixed readout seed differs")
    datasets = {task["dataset_id"] for task in panel["tasks"]}
    require(set(entry["memberships"]) == set(result["membership_sha256"]) == datasets,
            "Complete actual panel membership sources required")
    for dataset, reference in entry["memberships"].items():
        members = bound_json(reference)
        require(members.get("schema") == "model_v3_inner_membership_v1" and members.get("dataset_id") == dataset
                and members.get("target_values_consulted") is False
                and set(members.get("roles", {})) == {"train", "train_inner_validation"}
                and all(members["roles"].values())
                and canonical(members, ascii=True) == result["membership_sha256"][dataset],
                "Actual TRAIN-inner membership binding differs")
    execution = bound_json(entry["execution"])
    require(execution.get("schema") == "model_v3_run_execution_evidence_v1"
            and execution.get("authority") == "root_verified_slurm_accounting"
            and execution.get("status") == "COMPLETED"
            and execution.get("checkpoint_sha256") == cp["sha256"]
            and execution.get("configuration_sha256") == request["model_configuration"]["sha256"]
            and execution.get("pretraining_seed") == seed, "Bound actual execution receipt required")
    require(type(execution.get("training_run_id")) is str and execution["training_run_id"]
            and type(execution.get("training_job_id")) is str and execution["training_job_id"].isdigit(),
            "Actual training run/job identity required")
    require(execution.get("source_files"), "Original accounting/source evidence required")
    for source in execution["source_files"]:
        bound_bytes(source)
    started = _utc(execution["training_start_utc"])
    for key, value in (("training_run_id", execution["training_run_id"]),
                       ("job_id", execution["training_job_id"]),
                       ("training_start_utc", execution["training_start_utc"])):
        require(key not in bindings or bindings[key] == value, "Checkpoint/execution run identity differs")
    require("run_id" not in configuration or configuration["run_id"] == execution["training_run_id"],
            "Original configuration/execution run identity differs")
    score = _panel_score(panel, result)
    panel_identity = {"metric": METRIC, "panel_sha256": panel_reference["sha256"],
        "membership_sha256": result["membership_sha256"], "training_store_sha256": result["training_store_sha256"],
        "data_version": result["data_version"], "readout_seed": result["readout_seed"],
        "random_reference_initialization_seed": result["random_reference_initialization_seed"]}
    identity = scientific_identity(configuration=configuration, sampler=sampler, trainer=contract,
        scheduler=scheduler, bindings=bindings, checkpoint_samples=count, request=request,
        panel_identity=panel_identity, seed=seed, execution=extra["execution"], runtime=payload["runtime"])
    return RunEvidence(score, seed, canonical(identity), canonical(panel_identity), cp["sha256"],
        execution["training_run_id"], started, canonical(entry), entry, count,
        canonical({k: v for k, v in identity.items() if k != "checkpoint_samples_consumed"}))


def build_global_seed_sd(manifest, *, expected_registration_sha256):
    """Exactly two actual pretraining seeds; all decisions share this artifact."""
    require(manifest.get("schema") == "model_v3_global_seed_sd_inputs_v1", "Explicit seed-SD input manifest required")
    anchor, committed = registered_anchor(manifest["registration"], expected_sha256=expected_registration_sha256)
    entries = manifest.get("runs")
    require(type(entries) is list and len(entries) == 2, "Exactly two actual pretraining runs required")
    runs = [inspect_run(entry, panel_reference=manifest["panel"],
                        preregistration_commit=manifest["registration"]["commit"]) for entry in entries]
    require({run.seed for run in runs} == set(anchor["pretraining_seeds"]), "Actual seeds differ from the preregistered pair")
    require(len({run.training_run_id for run in runs}) == len({run.checkpoint_sha256 for run in runs}) == 2,
            "Independent actual training runs/checkpoints required")
    require(all(run.scientific_identity_sha256 == anchor["scientific_identity_sha256"] for run in runs),
            "Actual seed-excluded scientific configuration differs from registered anchor")
    require(all(run.panel_identity_sha256 == anchor["panel_identity_sha256"] for run in runs),
            "Actual complete panel/membership identity differs from registered anchor")
    require(all(committed < run.training_start_epoch for run in runs), "Anchor commit must precede both actual training starts")
    scores = [run.score for run in runs]
    sd = abs(scores[0]-scores[1])/math.sqrt(2.)
    return {"schema": "model_v3_global_seed_sd_artifact_v1", "status": "COMPLETE_BOUND_EVIDENCE",
        "frozen": False, "anchor_id": anchor["anchor_id"], "metric": METRIC, "ddof": 1,
        "seed_count": 2, "pretraining_seeds": [run.seed for run in runs], "scores": scores,
        "sample_standard_deviation": sd, "scientific_identity_sha256": anchor["scientific_identity_sha256"],
        "panel_identity_sha256": anchor["panel_identity_sha256"], "inputs": manifest,
        "inputs_sha256": canonical(manifest), "registration_sha256": expected_registration_sha256,
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "proof_scope": "Byte-bound files and actual checkpoint contracts; Git timestamp ordered against root-verified accounting receipt. Public availability and receipt authenticity require external verification.",
        "bootstrap_confidence_interval_used": False, "architecture_or_recipe_selected": False}


def verify_global_seed_sd(reference):
    """Recompute from all bound originals before using a saved SD artifact."""
    value = bound_json(reference)
    require(value.get("schema") == "model_v3_global_seed_sd_artifact_v1", "Global seed-SD artifact required")
    expected = build_global_seed_sd(value["inputs"], expected_registration_sha256=value["registration_sha256"])
    require(value == expected, "Saved global seed-SD artifact differs from its sources")
    return value
