"""Synthetic bound files/real Git objects; no scientific results or D schema."""
from copy import deepcopy
from dataclasses import asdict
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import subprocess

import pytest
import torch

from phychem_mfm.phase1.v3_decision_evidence import (
    METRIC, bound_json, build_global_seed_sd, canonical, inspect_run,
    scientific_identity, verify_global_seed_sd)
from phychem_mfm.phase1.v3_structural import StructuralViewConfig


ROOT = Path(__file__).absolute().parents[2]


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(value, sort_keys=True, allow_nan=False)+"\n").encode()
    path.write_bytes(raw)
    return {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest()}


def rebind(run):
    """Rebind deliberate fixture changes, so failures test semantics not stale SHA."""
    root = run["root"]
    entry, request, result = run["entry"], run["request"], run["result"]
    request["model_configuration"] = write(root/"config.json", run["configuration"])
    payload = run["payload"]
    payload["bindings"]["configuration_sha256"] = request["model_configuration"]["sha256"]
    payload["bindings"]["trainer_configuration_sha256"] = canonical(payload["extra_state"]["contract"])
    entry["sampler_contract"] = write(root/"sampler.json", run["sampler"])
    payload["sampler"]["contract_sha256"] = canonical(run["sampler"], ascii=True)
    cpdir = root/"checkpoint"; cpdir.mkdir(exist_ok=True)
    cp = cpdir/"payload.pt"; torch.save(payload, cp)
    request["checkpoint"] = {"path": str(cp), "sha256": hashlib.sha256(cp.read_bytes()).hexdigest(), "state_key": "auto"}
    marker = {"schema": payload["schema"], "payload_bytes": cp.stat().st_size,
        "payload_sha256": request["checkpoint"]["sha256"], "bindings": payload["bindings"],
        "samples_consumed": payload["clock"]["samples_consumed"], "optimizer_updates": payload["clock"]["optimizer_updates"]}
    request["training_completion"] = write(cpdir/"COMPLETE.json", marker)
    run["execution"]["checkpoint_sha256"] = request["checkpoint"]["sha256"]
    run["execution"]["configuration_sha256"] = request["model_configuration"]["sha256"]
    entry["execution"] = write(root/"execution.json", run["execution"])
    pair = result["encoder_pair"]
    pair["checkpoint"] = request["checkpoint"]
    pair["original_configuration"] = request["model_configuration"]
    for key in ("code_sha", "preregistration_sha", "architecture_sha256", "data_version", "pretraining_seed",
                "h0_packing_budget_sha256", "h0_packing_plan_sha256"):
        result[key] = request[key]
    entry["request"] = write(root/"request.json", request)
    result["request_sha256"] = entry["request"]["sha256"]
    entry["result"] = write(root/"result.json", result)


def make_run(tmp_path, seed, score, *, noise_epoch=True):
    root = tmp_path/("synthetic_seed_"+str(seed)); root.mkdir()
    panel = json.loads((ROOT/"configs/dev_panel_v1.json").read_text(encoding="utf-8"))
    panel_ref = write(tmp_path/"panel.json", panel)
    views = asdict(StructuralViewConfig(seed=seed, noise_seed_includes_epoch=noise_epoch))
    config = {"seed": seed, "run_id": "synthetic_"+str(seed), "output_root": str(root),
        "model": {"backbone": {"latent_dim": 512, "layers": 6}}, "view_configuration": views,
        "precision": "fp32", "initialization_policy": {"seed": 9182}, "readout_policy": {"seed": 0}}
    scheduler = {"schema": "model_v3_sample_lr_v1", "sample_budget": 100,
        "warmup_samples": 2, "mode": "cosine", "decay_start_samples": None,
        "minimum_ratio": 0., "base_lrs": [.0003]}
    contract = {"schema": "model_v3_step_trainer_v1", "enabled_groups": ["S"],
        "enabled_fields": ["element", "noise", "bond"], "view_configuration": deepcopy(views),
        "original_s_loss_weights": {"element": 1., "noise": 1., "bond": 1.},
        "gradient_clip_norm": 1., "gradient_probe_interval": 500, "probe_samples": 1,
        "scheduler_binding": canonical(scheduler), "batch_limits": [8, 256, 2048],
        "schedule_clock": "consumed_samples_including_no_label_batches", "adapter_sha256": "d"*64,
        "registry_projection": "e"*64, "provider_class": "synthetic.FixtureProvider",
        "normalization_projection": "f"*64, "performance_options": {},
        "optimizer_class": "torch.optim.adamw.AdamW", "optimizer_parameter_groups": [["encoder.weight"]],
        "optimizer_options": [{"betas": [.9, .95], "weight_decay": .01, "eps": 1e-8}]}
    sampler = {"schema": "model_v3_uniform_molecule_sampler_v1", "index_sha256": "1"*64,
        "data_version": "SYNTHETIC_ONLY", "seed": seed, "sample_budget": 100,
        "selection": {"mode": "all", "fixed_k": None}, "geometry_source": "PM7",
        "sampling": "uniform_molecule_then_uniform_allowed_conformer_with_replacement"}
    payload = {"schema": "model_v3_training_checkpoint_v1", "bindings": {"code_sha": "b"*40,
        "configuration_sha256": "0"*64, "trainer_configuration_sha256": canonical(contract),
        "registry_sha256": "2"*64, "normalization_sha256": "3"*64, "data_version": "SYNTHETIC_ONLY",
        "trainer_source_sha256": "4"*64, "adapter_sha256": "d"*64},
        "clock": {"samples_consumed": 100, "optimizer_updates": 2},
        "runtime": {"torch_version": str(torch.__version__), "num_threads": 1},
        "sampler": {"schema": sampler["schema"], "samples_consumed": 100, "contract_sha256": "0"*64},
        "model": {"encoder.weight": torch.tensor([float(seed)])},
        "optimizer": {"state": {}, "param_groups": [{"params": [0], "lr": 0., **deepcopy(contract["optimizer_options"][0])}]},
        "extra_state": {"schema": "model_v3_trainer_resume_v1", "contract": contract,
            "execution": {"float32_matmul_precision": "highest", "matmul_tf32": False, "performance_options": {}},
            "scheduler": {"contract": scheduler, "binding_sha256": canonical(scheduler), "samples_consumed": 100}}}
    memberships, membership_hashes = {}, {}
    for dataset in {task["dataset_id"] for task in panel["tasks"]}:
        members = {"schema": "model_v3_inner_membership_v1", "dataset_id": dataset,
            "target_values_consulted": False, "roles": {role: [{"member_index": i, "member_uid": "synthetic_"+str(i),
                "full_inchikey": "synthetic_group_"+str(i)}] for i, role in enumerate(("train", "train_inner_validation"))}}
        memberships[dataset] = write(tmp_path/("membership_"+dataset+".json"), members)
        membership_hashes[dataset] = canonical(members, ascii=True)
    store_ref = write(tmp_path/"training_store.json", {"schema": "model_v3_training_role_store_v1",
        "source_complete": True, "targets_in_metadata": False, "native_record_hashes_preserved": True,
        "data_version": "SYNTHETIC_ONLY", "records": [], "contracts": [],
        "records_file": {"path": "/must/not/open/any/native/target/payload"}})
    snapshot = tmp_path/"source_snapshot"; (snapshot/"synthetic").mkdir(parents=True, exist_ok=True)
    source = snapshot/"synthetic/source.py"; source.write_text("# Synthetic non-executed source fixture\n")
    source_ref = {"path": "synthetic/source.py", "sha256": hashlib.sha256(source.read_bytes()).hexdigest()}
    request = {"schema": "model_v3_dev_evaluation_request_v1", "code_sha": "b"*40, "preregistration_sha": "c"*40,
        "architecture_sha256": "a"*64, "data_version": "SYNTHETIC_ONLY", "pretraining_seed": seed,
        "panel": panel_ref, "training_store": store_ref,
        "source_files": [source_ref],
        "h0_packing": {"synthetic": True}, "h0_packing_budget_sha256": "7"*64,
        "h0_packing_plan_sha256": {dataset: "8"*64 for dataset in memberships}, "reference_kind": "primary"}
    cells = {task["task_id"]+"@"+readout: {"error": 1-score, "reference_error": 1., "normalized_improvement": score,
        "observed_labels": 2, "observed_molecules": 2} for task in panel["tasks"] for readout in ("ridge", "linear64_relu")}
    summaries = {}
    for name in ("primary_18_cells", "ridge", "linear64_relu"):
        summaries[name] = {"complete": True, "tasks": {k: v for k, v in cells.items() if name == "primary_18_cells" or k.endswith("@"+name)},
            "mean_normalized_improvement": score, "architecture_sha256": "a"*64, "bootstrap_ci": [-999, 999]}
    result = {"schema": "model_v3_dev_evaluation_result_v1", "status": "COMPLETED", "panel_sha256": panel_ref["sha256"],
        "training_store_sha256": store_ref["sha256"], "membership_sha256": membership_hashes, "summaries": summaries,
        "readout_seed": panel["readouts"]["linear64_relu"]["seed"], "random_reference_initialization_seed": 20261025,
        "reference_kind": "primary", "encoder_pair": {"schema": "model_v3_bound_encoder_pair_v1",
            "checkpoint_schema": "model_v3_immutable_sample_checkpoint", "pretraining_seed": seed,
            "reference_kind": "primary", "architecture_sha256": "a"*64, "random_reference_seed": 20261025}}
    accounting = root/"accounting.txt"; accounting.write_text("SYNTHETIC ACCOUNTING FIXTURE; no actual Slurm job\n")
    execution = {"schema": "model_v3_run_execution_evidence_v1", "authority": "root_verified_slurm_accounting",
        "status": "COMPLETED", "pretraining_seed": seed, "training_run_id": config["run_id"], "training_job_id": str(seed+1),
        "training_start_utc": "2030-01-01T00:00:00Z", "source_files": [{"path": str(accounting),
            "sha256": hashlib.sha256(accounting.read_bytes()).hexdigest()}]}
    run = {"root": root, "entry": {"memberships": memberships, "source_snapshot_root": str(snapshot)}, "panel": panel_ref,
        "configuration": config, "payload": payload, "request": request, "result": result,
        "sampler": sampler, "execution": execution}
    rebind(run)
    return run


def git_document(tmp_path, value):
    repo = tmp_path/"git_preregistration"; repo.mkdir()
    ref = write(repo/"anchor.json", value)
    def git(*args, **kwargs):
        return subprocess.run(["git", "-C", str(repo), *args], check=True, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, **kwargs).stdout.decode().strip()
    git("init")
    git("add", "anchor.json")
    env = {**os.environ, "GIT_AUTHOR_DATE": "2020-01-01T00:00:00+00:00", "GIT_COMMITTER_DATE": "2020-01-01T00:00:00+00:00"}
    git("-c", "user.name=Synthetic Test", "-c", "user.email=fixture@example.invalid", "commit", "-m", "synthetic preregistration", env=env)
    return {"repository": str(repo), "commit": git("rev-parse", "HEAD"), "path": "anchor.json", "sha256": ref["sha256"]}


def manifest(tmp_path, runs):
    inspected = inspect_run(runs[0]["entry"], panel_reference=runs[0]["panel"], preregistration_commit="c"*40)
    anchor = {"schema": "model_v3_global_seed_sd_registration_v1", "anchor_id": "SYNTHETIC_NOT_A_REAL_ANCHOR",
        "pretraining_seeds": [0, 1], "scientific_identity_sha256": inspected.scientific_identity_sha256,
        "panel_identity_sha256": inspected.panel_identity_sha256, "metric": METRIC}
    reference = git_document(tmp_path, anchor)
    for run in runs:
        run["request"]["preregistration_sha"] = reference["commit"]; rebind(run)
    return {"schema": "model_v3_global_seed_sd_inputs_v1", "registration": reference,
        "panel": runs[0]["panel"], "runs": [run["entry"] for run in runs]}


def test_real_structural_contract_seed_normalization_and_global_sd(tmp_path):
    runs = [make_run(tmp_path, seed, score) for seed, score in ((0, .125), (1, .375))]
    inputs = manifest(tmp_path, runs)
    artifact = build_global_seed_sd(inputs, expected_registration_sha256=inputs["registration"]["sha256"])
    assert artifact["sample_standard_deviation"] == pytest.approx(.25/math.sqrt(2))
    assert artifact["pretraining_seeds"] == [0, 1] and artifact["ddof"] == 1
    assert not artifact["bootstrap_confidence_interval_used"] and not artifact["frozen"]
    # Distinct actual sampler/config/checkpoint bytes but equal science identity.
    assert runs[0]["payload"]["sampler"]["contract_sha256"] != runs[1]["payload"]["sampler"]["contract_sha256"]
    assert runs[0]["request"]["model_configuration"]["sha256"] != runs[1]["request"]["model_configuration"]["sha256"]
    saved = write(tmp_path/"sd.json", artifact)
    assert verify_global_seed_sd(saved) == artifact
    artifact["sample_standard_deviation"] += .1
    with pytest.raises(ValueError, match="differs from its sources"):
        verify_global_seed_sd(write(tmp_path/"tampered_sd.json", artifact))


@pytest.mark.parametrize("change", ["noise_policy", "independent_seed", "readout_seed", "precision", "recipe", "budget", "initial_checkpoint"])
def test_seed_pair_rejects_changed_science_even_after_rebinding(tmp_path, change):
    runs = [make_run(tmp_path, seed, .25) for seed in (0, 1)]
    second = runs[1]
    if change == "noise_policy":
        second["configuration"]["view_configuration"]["noise_seed_includes_epoch"] = False
        second["payload"]["extra_state"]["contract"]["view_configuration"]["noise_seed_includes_epoch"] = False
    elif change == "independent_seed": second["configuration"]["initialization_policy"]["seed"] += 1
    elif change == "readout_seed": second["configuration"]["readout_policy"]["seed"] += 1
    elif change == "precision": second["payload"]["extra_state"]["execution"]["matmul_tf32"] = True
    elif change == "recipe": second["payload"]["extra_state"]["contract"]["gradient_clip_norm"] = 2.
    elif change == "budget":
        second["sampler"]["sample_budget"] = 200
        state = second["payload"]["extra_state"]["scheduler"]
        state["contract"]["sample_budget"] = 200
        state["binding_sha256"] = canonical(state["contract"])
        second["payload"]["extra_state"]["contract"]["scheduler_binding"] = state["binding_sha256"]
    else: second["configuration"]["checkpoint"] = {"initialization_sha256": "9"*64}
    rebind(second)
    inputs = manifest(tmp_path, runs)
    with pytest.raises(ValueError, match="scientific configuration differs"):
        build_global_seed_sd(inputs, expected_registration_sha256=inputs["registration"]["sha256"])


@pytest.mark.parametrize("change", ["missing_cell", "wrong_aggregate", "zero_reference", "historical", "final_role", "view_seed", "sampler_seed", "optimizer_recipe"])
def test_actual_run_rejects_incomplete_or_mismatched_sources(tmp_path, change):
    run = make_run(tmp_path, 0, .25)
    if change == "missing_cell": run["result"]["summaries"]["primary_18_cells"]["tasks"].pop("qm9.U0@ridge")
    elif change == "wrong_aggregate": run["result"]["summaries"]["ridge"]["mean_normalized_improvement"] = .9
    elif change == "zero_reference": run["result"]["summaries"]["primary_18_cells"]["tasks"]["qm9.U0@ridge"]["reference_error"] = 0
    elif change == "historical": run["result"]["reference_kind"] = "historical_sanity_only"
    elif change == "view_seed": run["payload"]["extra_state"]["contract"]["view_configuration"]["seed"] = 7
    elif change == "sampler_seed": run["sampler"]["seed"] = 7
    elif change == "optimizer_recipe": run["payload"]["optimizer"]["param_groups"][0]["weight_decay"] = .5
    else:
        ref = run["entry"]["memberships"]["qm9"]
        members = bound_json(ref); members["roles"]["final"] = members["roles"].pop("train_inner_validation")
        run["entry"]["memberships"]["qm9"] = write(Path(ref["path"]), members)
    rebind(run)
    with pytest.raises(ValueError): inspect_run(run["entry"], panel_reference=run["panel"], preregistration_commit="c"*40)


def test_registration_digest_and_accounting_order_are_mandatory(tmp_path):
    runs = [make_run(tmp_path, seed, .25) for seed in (0, 1)]
    inputs = manifest(tmp_path, runs)
    with pytest.raises(ValueError, match="Out-of-band"):
        build_global_seed_sd(inputs, expected_registration_sha256="f"*64)
    runs[1]["execution"]["training_start_utc"] = "2019-01-01T00:00:00Z"; rebind(runs[1])
    with pytest.raises(ValueError, match="precede both"):
        build_global_seed_sd(inputs, expected_registration_sha256=inputs["registration"]["sha256"])


def test_seed_sd_rejects_duplicate_seed_and_missing_run(tmp_path):
    runs = [make_run(tmp_path, seed, .25) for seed in (0, 1)]
    inputs = manifest(tmp_path, runs)
    inputs["runs"] = inputs["runs"][:1]
    with pytest.raises(ValueError, match="Exactly two"):
        build_global_seed_sd(inputs, expected_registration_sha256=inputs["registration"]["sha256"])
    inputs["runs"] = [runs[0]["entry"], runs[0]["entry"]]
    with pytest.raises(ValueError, match="Actual seeds"):
        build_global_seed_sd(inputs, expected_registration_sha256=inputs["registration"]["sha256"])


def test_bound_files_reject_tamper_duplicate_keys_nonfinite_and_missing_complete(tmp_path):
    run = make_run(tmp_path, 0, .25)
    marker = Path(run["request"]["training_completion"]["path"])
    marker.write_bytes(b'{"schema":"tampered"}')
    with pytest.raises(ValueError, match="Evidence bytes"):
        inspect_run(run["entry"], panel_reference=run["panel"], preregistration_commit="c"*40)
    for raw in (b'{"a":1,"a":2}', b'{"a":NaN}'):
        path = tmp_path/"invalid.json"; path.write_bytes(raw)
        with pytest.raises(ValueError): bound_json({"path": str(path), "sha256": hashlib.sha256(raw).hexdigest()})


def test_cli_builds_external_artifact_once_and_rejects_bad_manifest_before_output(tmp_path):
    runs = [make_run(tmp_path, seed, score) for seed, score in ((0, .125), (1, .375))]
    inputs = manifest(tmp_path, runs)
    ref = write(tmp_path/"inputs.json", inputs)
    spec = importlib.util.spec_from_file_location("build_seed_sd", ROOT/"tools/model_v3/build_seed_sd.py")
    cli = importlib.util.module_from_spec(spec); spec.loader.exec_module(cli)
    output = tmp_path/"external"/"sd.json"
    args = ["--manifest", ref["path"], "--manifest-sha256", ref["sha256"],
            "--registration-sha256", inputs["registration"]["sha256"], "--output", str(output)]
    cli.main(args)
    assert json.loads(output.read_text())["status"] == "COMPLETE_BOUND_EVIDENCE"
    with pytest.raises(FileExistsError): cli.main(args)
    invalid = tmp_path/"never_created"/"bad.json"
    bad = list(args); bad[3] = "0"*64; bad[-1] = str(invalid)
    with pytest.raises(ValueError, match="Evidence bytes"): cli.main(bad)
    assert not invalid.parent.exists()


def test_rule_policy_comes_from_the_fixed_git_blob(tmp_path):
    from phychem_mfm.phase1.v3_decision_rules import registered_policy
    document = {"schema": "model_v3_decision_policy_v1", "rules": {"C3": {"SYNTHETIC_ONLY": True}}}
    reference = git_document(tmp_path, document)
    policy = registered_policy(reference, expected_sha256=reference["sha256"])
    assert policy.rules == document["rules"] and policy.commit == reference["commit"]
    # Working-tree replacement never changes the registered version.
    write(Path(reference["repository"])/"anchor.json", {"schema": "different"})
    assert registered_policy(reference, expected_sha256=reference["sha256"]).rules == policy.rules


@pytest.mark.parametrize("drift", ["source_snapshot", "training_store_metadata"])
def test_inherited_evaluation_sources_are_rechecked_without_native_target_reads(tmp_path, drift):
    run = make_run(tmp_path, 0, .25)
    path = (Path(run["entry"]["source_snapshot_root"])/"synthetic/source.py"
            if drift == "source_snapshot" else Path(run["request"]["training_store"]["path"]))
    path.write_bytes(b"deliberately changed bound evidence")
    with pytest.raises(ValueError, match="Evidence bytes"):
        inspect_run(run["entry"], panel_reference=run["panel"], preregistration_commit="c"*40)
