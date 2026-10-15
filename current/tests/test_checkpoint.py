from copy import deepcopy

import torch

from conftest import small_config
from phychem_mfm.factory import build_model
from phychem_mfm.supervision import SupervisionConfig
from phychem_mfm.training.checkpoint import load_training_checkpoint, save_training_checkpoint
from phychem_mfm.training.optim import build_adamw, build_warmup_cosine_scheduler


def test_scheduler_advances_on_exposure_without_optimizer_update():
    parameter = torch.nn.Parameter(torch.tensor(1.0))
    optimizer = torch.optim.AdamW([parameter], lr=3e-5)
    scheduler = build_warmup_cosine_scheduler(optimizer, total_steps=20, warmup_steps=10)
    before_parameter = parameter.detach().clone()
    before_lr = optimizer.param_groups[0]["lr"]

    scheduler.step()

    torch.testing.assert_close(parameter, before_parameter, rtol=0.0, atol=0.0)
    assert scheduler.last_epoch == 1
    assert optimizer.param_groups[0]["lr"] > before_lr


def test_checkpoint_roundtrip_and_resume_schedule(tmp_path):
    config = small_config("light")
    model = build_model(config, preset="light")
    optimizer = build_adamw(model, lr=3e-5, weight_decay=0.01)
    scheduler = build_warmup_cosine_scheduler(optimizer, total_steps=20, warmup_steps=2)
    optimizer.zero_grad(set_to_none=True)
    sum(parameter.sum() for parameter in model.parameters()).backward()
    optimizer.step()
    scheduler.step()
    path = tmp_path / "roundtrip.pt"
    save_training_checkpoint(
        path,
        model=model,
        optimizer=optimizer,
        scheduler=scheduler,
        config=config,
        supervision=SupervisionConfig.from_variant("SPD").to_dict(),
        dataset_manifest={"manifest_sha256": "test"},
        exposure_step=7,
        optimizer_update_step=6,
        checkpoint_type="latest",
        project_root=tmp_path,
    )

    restored = build_model(config, preset="light")
    restored_optimizer = build_adamw(restored, lr=3e-5, weight_decay=0.01)
    restored_scheduler = build_warmup_cosine_scheduler(restored_optimizer, total_steps=20, warmup_steps=2)
    payload = load_training_checkpoint(
        path,
        model=restored,
        optimizer=restored_optimizer,
        scheduler=restored_scheduler,
        expected_config=config,
    )
    assert payload["global_exposure_step"] == 7
    assert payload["optimizer_update_step"] == 6
    assert restored_scheduler.state_dict() == scheduler.state_dict()
    for (name_a, value_a), (name_b, value_b) in zip(model.state_dict().items(), restored.state_dict().items()):
        assert name_a == name_b
        torch.testing.assert_close(value_b, value_a, rtol=0.0, atol=0.0)
