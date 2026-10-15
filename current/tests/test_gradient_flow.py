from __future__ import annotations

from copy import deepcopy

import pytest
import torch

from conftest import small_config
from phychem_mfm.factory import build_model
from phychem_mfm.supervision import SupervisionConfig
from phychem_mfm.training.losses import LossWeights, StageSchedule, compute_pretrain_loss
from phychem_mfm.training.optim import build_adamw


VARIANTS = ("S", "P", "D", "SP", "SD", "SPD")


def _has_grad(module) -> bool:
    return any(parameter.grad is not None and torch.isfinite(parameter.grad).all() and parameter.grad.abs().sum() > 0 for parameter in module.parameters())


def _all_none(module) -> bool:
    return all(parameter.grad is None for parameter in module.parameters())


@pytest.mark.parametrize("route", ("light", "expert"))
@pytest.mark.parametrize("variant", VARIANTS)
def test_gradient_flow(route, variant, mixed_real_batch, real_data_bundle):
    torch.manual_seed(17)
    model = build_model(small_config(route), preset=route)
    supervision = SupervisionConfig.from_variant(variant)
    schedule = StageSchedule(0, 1, 0, 1.0)
    active = supervision.objectives_at_descriptor_scale(1.0)
    outputs = model.forward_pretrain(mixed_real_batch, active)
    result = compute_pretrain_loss(
        outputs,
        mixed_real_batch,
        real_data_bundle.standardizers,
        supervision,
        LossWeights(),
        schedule,
        1,
        graph_descriptor_indices=model.graph_descriptor_target_indices,
    )
    result.total.backward()
    assert _has_grad(model.backbone)

    task_to_group = {"energy": "P", "charge": "P", "element": "S", "geometry": "S", "bond": "S"}
    for task, group in task_to_group.items():
        active_task = group in variant
        if route == "expert":
            assert _has_grad(model.task_adapters[task]) if active_task else _all_none(model.task_adapters[task])
        head = getattr(model, f"{task}_head")
        assert _has_grad(head) if active_task else _all_none(head)
    descriptor_active = "D" in variant
    descriptor_modules = (
        model.graph_descriptor_heads,
        model.charge_descriptor_heads,
        model.element_descriptor_heads,
    )
    assert all(_has_grad(module) for module in descriptor_modules) if descriptor_active else all(
        _all_none(module) for module in descriptor_modules
    )


@pytest.mark.parametrize("route", ("light", "expert"))
def test_inactive_parameters_do_not_drift(route, mixed_real_batch, real_data_bundle):
    torch.manual_seed(23)
    model = build_model(small_config(route), preset=route)
    optimizer = build_adamw(model, lr=1e-3, weight_decay=0.1)
    supervision = SupervisionConfig.from_variant("P")
    schedule = StageSchedule(0, 1, 0, 1.0)
    tracked_names = [
        name for name, _ in model.named_parameters()
        if any(token in name for token in ("task_adapters.element", "task_adapters.geometry", "task_adapters.bond", "element_head", "geometry_head", "bond_head", "descriptor_heads"))
    ]
    before = {name: parameter.detach().clone() for name, parameter in model.named_parameters() if name in tracked_names}
    optimizer.zero_grad(set_to_none=True)
    outputs = model.forward_pretrain(mixed_real_batch, supervision.objectives)
    result = compute_pretrain_loss(
        outputs, mixed_real_batch, real_data_bundle.standardizers, supervision, LossWeights(), schedule, 1,
        graph_descriptor_indices=model.graph_descriptor_target_indices,
    )
    result.total.backward()
    optimizer.step()
    current = dict(model.named_parameters())
    for name, old_value in before.items():
        assert current[name].grad is None, name
        torch.testing.assert_close(current[name], old_value, rtol=0.0, atol=0.0, msg=name)


def test_light_expert_common_initialization_is_identical():
    torch.manual_seed(101)
    light = build_model(small_config("light"), preset="light")
    torch.manual_seed(101)
    expert = build_model(small_config("expert"), preset="expert")
    expert_state = expert.state_dict()
    for name, value in light.state_dict().items():
        if name.startswith("task_adapters."):
            continue
        torch.testing.assert_close(expert_state[name], value, rtol=0.0, atol=0.0, msg=name)


def test_expert_activation_checkpointing_preserves_forward_and_gradients(mixed_real_batch):
    eager_config = small_config("expert")
    checkpoint_config = deepcopy(eager_config)
    checkpoint_config["expert"]["activation_checkpointing"] = True
    torch.manual_seed(29)
    eager = build_model(eager_config, preset="expert")
    torch.manual_seed(29)
    recompute = build_model(checkpoint_config, preset="expert")
    eager.train()
    recompute.train()
    eager_h0 = eager.encode_atoms(mixed_real_batch)
    recompute_h0 = recompute.encode_atoms(mixed_real_batch)
    eager_output = eager.task_adapter("energy", eager_h0, mixed_real_batch)
    recompute_output = recompute.task_adapter("energy", recompute_h0, mixed_real_batch)
    torch.testing.assert_close(recompute_output, eager_output, rtol=0.0, atol=0.0)

    eager_output.square().mean().backward()
    recompute_output.square().mean().backward()
    eager_parameters = dict(eager.named_parameters())
    for name, parameter in recompute.named_parameters():
        if parameter.grad is not None:
            torch.testing.assert_close(parameter.grad, eager_parameters[name].grad, rtol=1e-5, atol=1e-6, msg=name)
