from copy import deepcopy

import pytest
import torch

from conftest import small_config
from phychem_mfm.factory import build_model
from phychem_mfm.supervision import SupervisionConfig
from phychem_mfm.training.checkpoint import load_training_checkpoint, save_training_checkpoint, source_provenance
from phychem_mfm.training.optim import build_adamw, build_warmup_cosine_scheduler


def test_resume_rejects_same_shape_changed_science_before_mutation(tmp_path):
    config = small_config("light")
    config["head"]["profile"] = "phase1"
    config["supervision"]["variant"] = "SDP"
    model = build_model(config)
    optimizer = build_adamw(model, lr=3e-5, weight_decay=.01)
    scheduler = build_warmup_cosine_scheduler(optimizer, total_steps=20, warmup_steps=2)
    manifest = {"split": "molecule-independent", "normalizer": "train-only-a", "protocol": "diagnostic-v1"}
    path = tmp_path / "checkpoint.pt"
    save_training_checkpoint(path, model=model, optimizer=optimizer, scheduler=scheduler, config=config,
                             supervision=SupervisionConfig.from_variant("SDP").to_dict(), dataset_manifest=manifest,
                             exposure_step=1, optimizer_update_step=1, checkpoint_type="latest", project_root=tmp_path)
    restored = build_model(config)
    initial = {key: value.clone() for key, value in restored.state_dict().items()}
    changed = deepcopy(config)
    changed["loss"]["energy"] = 123.
    with pytest.raises(RuntimeError, match="config mismatch"):
        load_training_checkpoint(path, model=restored, expected_config=changed, expected_dataset_manifest=manifest)
    with pytest.raises(RuntimeError, match="manifest mismatch"):
        load_training_checkpoint(path, model=restored, expected_config=config,
                                 expected_dataset_manifest={**manifest, "normalizer": "validation-statistics"})
    for key, value in restored.state_dict().items():
        torch.testing.assert_close(value, initial[key], rtol=0, atol=0)
    load_training_checkpoint(path, model=restored, expected_config=config, expected_dataset_manifest=manifest)
    for key, value in restored.state_dict().items():
        torch.testing.assert_close(value, model.state_dict()[key], rtol=0, atol=0)


def test_source_hash_covers_json_rules_and_excludes_runtime(tmp_path):
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    rules = config_dir / "rules.json"
    rules.write_text('{"charge": "NET ATOMIC CHARGES"}')
    first = source_provenance(tmp_path)["source_sha256"]
    runtime = tmp_path / "runs"
    runtime.mkdir()
    (runtime / "summary.json").write_text('{"step": 1}')
    assert source_provenance(tmp_path)["source_sha256"] == first
    rules.write_text('{"charge": "changed-target"}')
    assert source_provenance(tmp_path)["source_sha256"] != first
