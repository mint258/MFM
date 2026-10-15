"""Hash-bound selections and real tiny CPU updates; no live/formal execution."""
from copy import deepcopy
import json

import numpy as np
import pytest
import torch

from conftest import small_config
from test_phase1_formal_runner import execution, load_runner, protocol
from test_phase1_training import _graph, _std
from phychem_mfm.factory import build_model
from phychem_mfm.phase1.formal_runtime import (
    FORMAL_RUN_SCHEMA, backbone_state_hash, cyclic_batch_indices, file_sha256,
    formal_policy_at_update, formal_weighting_metrics, formal_weighting_state,
    frozen_execution, select_formal_recipe, validate_formal_resume,
)
from phychem_mfm.phase1.objectives import GROUP_TASKS, Phase1JointSchedule
from phychem_mfm.phase1.strategy import RECIPE_NAME
from phychem_mfm.supervision import SupervisionConfig
from phychem_mfm.training.checkpoint import contract_hash, load_training_checkpoint, save_training_checkpoint, semantic_config
from phychem_mfm.training.data import fast_collate
from phychem_mfm.training.losses import LossWeights, compute_pretrain_loss
from phychem_mfm.training.optim import build_adamw, build_warmup_cosine_scheduler


def recipe_values():
    return {"name": RECIPE_NAME, "index_unit": "optimizer_update_step", "variant": "SDP", "max_updates": 4,
            "stages": [{"end_update_exclusive": 2, "group_weight_multipliers": {"S": 3., "D": 1., "P": 1.}},
                       {"end_update_exclusive": 4, "group_weight_multipliers": {"S": 1., "D": 3., "P": 1.}}]}


def fixture(tmp_path, values=None, *, seed=3, variant="SDP", recipe_id="emphasis_v1"):
    tmp_path.mkdir(parents=True, exist_ok=True)
    path = tmp_path / "recipe.json"
    path.write_text(json.dumps(recipe_values() if values is None else values), encoding="utf-8")
    frozen, document = protocol(), execution()
    tiny = small_config("light")
    document["config"].update({name: deepcopy(tiny[name]) for name in ("backbone", "expert")})
    document["config"]["head"].update(tiny["head"])
    frozen["strategy"] = {"name": "joint", "contrasts": {"emphasis_v1": {
        "variant": "SDP", "seeds": [3], "recipe_sha256": file_sha256(path)}}}
    artifacts = {"strategy.contrasts.emphasis_v1.recipe_sha256": path}
    config, policy = frozen_execution(frozen, document, variant=variant, seed=seed)
    selected, recipe, binding = select_formal_recipe(frozen, artifacts, variant=variant, seed=seed,
        recipe_id=recipe_id, config=config, base_policy=policy)
    return frozen, document, artifacts, config, selected, policy, recipe, binding


def test_default_config_policy_and_manifest_inputs_remain_unchanged(tmp_path):
    frozen, document, artifacts, base_config, _, policy, _, _ = fixture(tmp_path)
    original = deepcopy(base_config)
    selected, recipe, binding = select_formal_recipe(frozen, artifacts, variant="SDP", seed=3,
        recipe_id="direct_joint", config=base_config, base_policy=policy)
    assert selected is base_config and selected == original and recipe is binding is None
    assert "joint_weighting" not in selected["schedule"]
    assert formal_weighting_state(None, policy, 0) is None
    assert formal_weighting_metrics(None, None) == {}
    assert frozen_execution(frozen, document, variant="SDP", seed=3)[0] == original
    args = load_runner().parse_args(["--protocol", "p", "--artifacts", "a", "--variant", "SDP", "--seed", "3", "--output-dir", "o"])
    assert args.recipe == "direct_joint"


def test_selection_binds_recipe_bytes_and_semantics_without_changing_shared_budget(tmp_path):
    frozen, document, artifacts, base, selected, policy, recipe, binding = fixture(tmp_path)
    assert selected != base and selected["schedule"]["strategy"] == "positive_piecewise_joint_from_step_zero"
    for name in ("architecture", "backbone", "expert", "head", "supervision", "loss", "optimizer", "training", "phase1"):
        assert selected[name] == base[name]
    for name in ("max_steps", "warmup_steps", "min_lr_ratio"):
        assert selected["schedule"][name] == base["schedule"][name]
    assert binding["artifact_sha256"] == file_sha256(artifacts[binding["artifact_field"]])
    assert binding["recipe_semantic_sha256"] == recipe.sha256
    assert binding["base_loss_policy_sha256"] == contract_hash(policy.to_dict())
    assert [row["optimizer_update_step"] for row in binding["stage_begin_policies"]] == [0, 2]
    assert sum(binding["integrated_group_coefficients"].values()) == pytest.approx(4.)
    assert frozen["pretraining"]["budget"]["structures_per_condition"] == 8
    assert document["config"]["schedule"]["strategy"] == "direct_joint_from_step_zero"


@pytest.mark.parametrize("variant,seed,recipe_id", [("SDP", 5, "emphasis_v1"), ("SD", 3, "emphasis_v1"),
    ("none", 3, "emphasis_v1"), ("S", 3, "emphasis_v1"), ("SDP", 3, "missing")])
def test_condition_seed_and_recipe_selection_must_be_whitelisted(tmp_path, variant, seed, recipe_id):
    with pytest.raises(ValueError, match="explicit frozen contrast"):
        fixture(tmp_path, variant=variant, seed=seed, recipe_id=recipe_id)


@pytest.mark.parametrize("change", ["bytes", "condition", "budget", "zero_later_stage", "underflow_later_stage"])
def test_changed_or_invalid_later_stage_artifact_is_rejected_before_training(tmp_path, change):
    frozen, _, artifacts, config, _, policy, _, _ = fixture(tmp_path)
    path = artifacts["strategy.contrasts.emphasis_v1.recipe_sha256"]
    values = recipe_values()
    if change == "bytes":
        path.write_text(path.read_text() + "\n")  # Semantic equality does not replace byte binding.
    else:
        if change == "condition": values["variant"] = "SD"
        elif change == "budget": values["max_updates"] = values["stages"][-1]["end_update_exclusive"] = 5
        else: values["stages"][1]["group_weight_multipliers"]["D"] = 0. if change == "zero_later_stage" else 1e-100
        path.write_text(json.dumps(values), encoding="utf-8")
        frozen["strategy"]["contrasts"]["emphasis_v1"]["recipe_sha256"] = file_sha256(path)
    with pytest.raises(ValueError):
        select_formal_recipe(frozen, artifacts, variant="SDP", seed=3, recipe_id="emphasis_v1", config=config, base_policy=policy)


def test_caller_cannot_change_the_frozen_base_policy_between_updates(tmp_path):
    _, _, _, _, _, policy, recipe, binding = fixture(tmp_path)
    policy.group_weights["S"] = 2.
    with pytest.raises(ValueError, match="base loss policy changed"):
        formal_policy_at_update(binding, policy, 2, recipe=recipe)


def tiny_model_optimizer(config):
    torch.manual_seed(config["training"]["seed"])
    model = build_model(config)
    optimizer = build_adamw(model, **{name: config["optimizer"][name] for name in ("lr", "weight_decay", "betas")})
    scheduler = build_warmup_cosine_scheduler(optimizer, total_steps=4, warmup_steps=1, min_lr_ratio=.05)
    return model, optimizer, scheduler


def cpu_updates(runner, model, optimizer, scheduler, config, policy, recipe, binding, *, begin, end, log_path):
    """Use the runner's actual forward/loss and logging helpers in a CPU loop."""
    records = []
    order = np.random.default_rng(config["training"]["seed"]).permutation(5)
    supervision = SupervisionConfig.from_variant("SDP")
    for step in range(begin, end):
        indices = cyclic_batch_indices(order, step, 2)
        batch_rows = []
        for index in indices:
            for view in ("clean", "geom", "topo"):
                row = _graph(view)
                row.energy += int(index)
                batch_rows.append(row)
        batch = fast_collate(batch_rows)
        optimizer.zero_grad(set_to_none=True)
        lr_used = optimizer.param_groups[0]["lr"]
        with torch.random.fork_rng(devices=[]):
            torch.manual_seed(config["training"]["seed"] + step)
            outputs, loss, snapshot = runner.formal_weighted_forward(model, batch, _std(), supervision,
                LossWeights(), Phase1JointSchedule(), step, policy, recipe=recipe, recipe_binding=binding)
            assert loss.total.requires_grad and torch.isfinite(loss.total)
            assert loss.descriptor_scale == loss.stage1_scale == 1.
            assert all(loss.counts[name] > 0 and loss.task_weights[name] > 0. for name in loss.raw)
            loss.total.backward()
        assert any(parameter.grad is not None and parameter.grad.abs().sum() > 0 for parameter in model.backbone.parameters())
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.)
        optimizer.step()
        scheduler.step()
        row = {"optimizer_update_step_after": step + 1, "base_molecule_exposure": 2*(step + 1),
               "base_indices": indices, "lr_used": lr_used, "lr_next": optimizer.param_groups[0]["lr"],
               **loss.scalar_metrics("train/"), **formal_weighting_metrics(snapshot, binding)}
        with log_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row, allow_nan=False) + "\n")
        records.append(row)
    return records


def assert_nested_equal(left, right):
    if isinstance(left, torch.Tensor):
        torch.testing.assert_close(left, right, rtol=0, atol=0)
    elif isinstance(left, dict):
        assert set(left) == set(right)
        for key in left: assert_nested_equal(left[key], right[key])
    elif isinstance(left, (tuple, list)):
        assert len(left) == len(right)
        for first, second in zip(left, right): assert_nested_equal(first, second)
    else:
        assert left == right


def test_real_cpu_updates_log_boundary_policy_and_restore_exact_optimizer_trajectory(tmp_path):
    _, _, _, _, config, policy, recipe, binding = fixture(tmp_path)
    runner = load_runner()
    complete_model, complete_optimizer, complete_scheduler = tiny_model_optimizer(config)
    init_hash = backbone_state_hash(complete_model)
    full_rows = cpu_updates(runner, complete_model, complete_optimizer, complete_scheduler, config, policy, recipe, binding,
        begin=0, end=4, log_path=tmp_path / "complete_steps.jsonl")
    split_model, split_optimizer, split_scheduler = tiny_model_optimizer(config)
    assert backbone_state_hash(split_model) == init_hash
    first_rows = cpu_updates(runner, split_model, split_optimizer, split_scheduler, config, policy, recipe, binding,
        begin=0, end=2, log_path=tmp_path / "resumed_steps.jsonl")
    state = formal_weighting_state(binding, policy, 2)
    assert state["next_policy"]["stage_id"] == 1 and state["next_policy"]["optimizer_update_step"] == 2
    manifest = {"purpose": FORMAL_RUN_SCHEMA, "protocol_sha256": "a"*64, "loss_policy": policy.to_dict(),
                "joint_weighting": binding, "synthetic_fixture_only": True}
    checkpoint = tmp_path / "latest.pt"
    extra = {"formal_run_schema": FORMAL_RUN_SCHEMA, "wandb_run_id": "synthetic123", "paired_initial_H0_sha256": init_hash,
             "base_molecule_exposure": 4, "budget_usage": {"wall_seconds": 10.}, "joint_weighting_state": state,
             "tracker_next_step": 3, "tracker_run_path": "synthetic/project/synthetic123"}
    save_training_checkpoint(checkpoint, model=split_model, optimizer=split_optimizer, scheduler=split_scheduler,
        config=config, supervision=SupervisionConfig.from_variant("SDP").to_dict(), dataset_manifest=manifest,
        exposure_step=2, optimizer_update_step=2, checkpoint_type="periodic", project_root=tmp_path,
        source_metadata={"source_sha256": "f"*64, "git_commit": "synthetic_only"}, extra=extra)
    payload = torch.load(checkpoint, map_location="cpu", weights_only=False)
    journal = {"schema_version": FORMAL_RUN_SCHEMA, "status": "failed", "wandb_run_id": "synthetic123",
        "paired_initial_H0_sha256": init_hash, "manifest_sha256": contract_hash(manifest), "optimizer_update_step": 2,
        "base_molecule_exposure": 4, "latest_checkpoint_sha256": file_sha256(checkpoint),
        "budget_usage": {"wall_seconds": 30., "gpu_hours": 30./3600}, "joint_weighting_state": state,
        "tracker_next_step": 3, "tracker_run_path": "synthetic/project/synthetic123"}
    assert validate_formal_resume(payload, expected_manifest=manifest, expected_config=config, expected_run_id="synthetic123",
        expected_init_hash=init_hash, journal=journal, checkpoint_sha256=file_sha256(checkpoint)) == 30.
    restored_model, restored_optimizer, restored_scheduler = tiny_model_optimizer(config)
    load_training_checkpoint(checkpoint, model=restored_model, optimizer=restored_optimizer, scheduler=restored_scheduler,
        expected_config=config, expected_dataset_manifest=manifest, expected_source_sha256="f"*64, strict_semantics=True)
    _, _, _, _, rebuilt_config, rebuilt_policy, rebuilt_recipe, rebuilt_binding = fixture(tmp_path / "rebuilt")
    assert rebuilt_config == config and rebuilt_binding == binding
    tail_rows = cpu_updates(runner, restored_model, restored_optimizer, restored_scheduler, config, rebuilt_policy, rebuilt_recipe, rebuilt_binding,
        begin=2, end=4, log_path=tmp_path / "resumed_steps.jsonl")
    assert first_rows + tail_rows == full_rows
    assert [row["strategy/optimizer_update_step_used"] for row in full_rows] == [0, 1, 2, 3]
    assert [row["strategy/stage_id"] for row in full_rows] == [0, 0, 1, 1]
    assert [row["optimizer_update_step_after"] for row in full_rows] == [1, 2, 3, 4]
    assert [row["base_molecule_exposure"] for row in full_rows] == [2, 4, 6, 8]
    for row in full_rows:
        for group in GROUP_TASKS:
            assert sum(row["train/weight/task/" + name] for name in GROUP_TASKS[group]) == pytest.approx(row["strategy/effective_group_coefficient/" + group])
    assert_nested_equal(complete_model.state_dict(), restored_model.state_dict())
    assert_nested_equal(complete_optimizer.state_dict(), restored_optimizer.state_dict())
    assert_nested_equal(complete_scheduler.state_dict(), restored_scheduler.state_dict())
    assert [json.loads(line) for line in (tmp_path / "resumed_steps.jsonl").read_text().splitlines()] == full_rows
    endpoint = formal_weighting_state(binding, policy, 4)
    assert endpoint["status"] == "endpoint" and endpoint["next_policy"] is None


def test_all_one_recipe_has_the_same_real_updates_as_default_direct_joint(tmp_path):
    values = recipe_values()
    for stage in values["stages"]: stage["group_weight_multipliers"] = {"S": 1., "D": 1., "P": 1.}
    _, _, _, base_config, selected, policy, recipe, binding = fixture(tmp_path, values)
    runner = load_runner()
    direct_model, direct_optimizer, direct_scheduler = tiny_model_optimizer(base_config)
    weighted_model, weighted_optimizer, weighted_scheduler = tiny_model_optimizer(selected)
    direct_rows = cpu_updates(runner, direct_model, direct_optimizer, direct_scheduler, base_config, policy, None, None,
        begin=0, end=4, log_path=tmp_path / "direct.jsonl")
    weighted_rows = cpu_updates(runner, weighted_model, weighted_optimizer, weighted_scheduler, selected, policy, recipe, binding,
        begin=0, end=4, log_path=tmp_path / "all_one.jsonl")
    assert direct_rows == [{key: value for key, value in row.items() if not key.startswith("strategy/")} for row in weighted_rows]
    assert_nested_equal(direct_model.state_dict(), weighted_model.state_dict())
    assert_nested_equal(direct_optimizer.state_dict(), weighted_optimizer.state_dict())
    assert_nested_equal(direct_scheduler.state_dict(), weighted_scheduler.state_dict())


@pytest.mark.parametrize("defect", ["missing_checkpoint_state", "missing_journal_state", "checkpoint_stage", "journal_cursor", "policy_hash", "changed_recipe"])
def test_strict_resume_rejects_missing_stale_or_changed_recipe_evidence(tmp_path, defect):
    from test_phase1_formal_runner import resume_fixture
    payload, _, _, journal = resume_fixture()
    _, _, _, _, config, policy, _, binding = fixture(tmp_path)
    manifest = {"purpose": FORMAL_RUN_SCHEMA, "protocol_sha256": "a"*64, "loss_policy": policy.to_dict(), "joint_weighting": binding}
    payload.update(dataset_manifest=deepcopy(manifest), semantic_config=semantic_config(config), semantic_config_sha256=contract_hash(semantic_config(config)))
    journal["manifest_sha256"] = contract_hash(manifest)
    payload["extra"]["joint_weighting_state"] = formal_weighting_state(binding, policy, 2)
    journal["joint_weighting_state"] = deepcopy(payload["extra"]["joint_weighting_state"])
    if defect == "missing_checkpoint_state": payload["extra"].pop("joint_weighting_state")
    elif defect == "missing_journal_state": journal.pop("joint_weighting_state")
    elif defect == "checkpoint_stage": payload["extra"]["joint_weighting_state"]["next_policy"]["stage_id"] = 0
    elif defect == "journal_cursor": journal["joint_weighting_state"]["next_optimizer_update_step"] = 1
    elif defect == "policy_hash": payload["extra"]["joint_weighting_state"]["next_policy"]["policy_sha256"] = "e"*64
    else: manifest["joint_weighting"]["recipe"]["stages"][1]["group_weight_multipliers"]["D"] = 4.
    with pytest.raises(RuntimeError):
        validate_formal_resume(payload, expected_manifest=manifest, expected_config=config, expected_run_id="run12345",
            expected_init_hash="b"*64, journal=journal, checkpoint_sha256="c"*64)
