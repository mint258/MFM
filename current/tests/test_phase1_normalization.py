"""Output conditioning is invariant to label units, not a source of H0 inputs."""
from copy import deepcopy

import pytest
import torch

from conftest import small_config
from test_phase1_training import _batch
from phychem_mfm.data.descriptor_schema import GRAPH_DESCRIPTOR_NAMES
from phychem_mfm.factory import build_model
from phychem_mfm.model.normalization import (
    REGRESSION_TARGETS, train_regression_normalization, validate_regression_normalization,
)
from phychem_mfm.model.phase1_specs import PHASE1_GRAPH_DESCRIPTOR_NAMES
from phychem_mfm.phase1.identity import canonical_hash
from phychem_mfm.phase1.objectives import Phase1JointSchedule
from phychem_mfm.supervision import SupervisionConfig
from phychem_mfm.training.checkpoint import save_training_checkpoint, load_training_checkpoint
from phychem_mfm.training.losses import LossWeights, compute_pretrain_loss
from phychem_mfm.training.optim import build_adamw, build_warmup_cosine_scheduler


def statistics(*, factor=1., offset=0.):
    result = {
        "muE": 12.0 * factor + offset, "stdE": 2.5 * factor,
        "muQ": .15 * factor + offset, "stdQ": .4 * factor,
        "estate_index_mu": .8 * factor + offset, "estate_index_std": 1.7 * factor,
        "formal_charge_mu": 0., "formal_charge_std": 1.,
        "graph_desc_mu": torch.linspace(0., 2., len(GRAPH_DESCRIPTOR_NAMES)) * factor + offset,
        "graph_desc_std": torch.linspace(.5, 1.5, len(GRAPH_DESCRIPTOR_NAMES)) * factor,
    }
    return result


def provenance(stats):
    serial = {key: value.tolist() if isinstance(value, torch.Tensor) else value for key, value in stats.items()}
    value = {
        "train_only": True, "train_pool_hash": "a" * 64, "train_view_hash": "b" * 64,
        "sampled_record_keys_hash": "c" * 64, "statistics_hash": canonical_hash(serial),
        "estimator_version": "phase1_masked_population_std_v1", "seed": 7, "cap": 2,
        "sampled_structure_count": 2, "sampled_logical_indices": [0, 1],
        "valid_label_counts": {"energy": 2, "charge": 7, "estate_index": 7,
                               "graph_descriptor": [2] * len(GRAPH_DESCRIPTOR_NAMES)},
        "statistics_usage": "train-only; explicit head contract declares the transform",
    }
    value["provenance_hash"] = canonical_hash(value)
    return value


def configuration(route="light", *, stats=None):
    config = small_config(route)
    config["head"]["profile"] = "phase1"
    config["supervision"]["variant"] = "SDP"
    if stats is not None:
        config["head"]["regression_output_normalization"] = train_regression_normalization(stats, provenance(stats))
    return config


def paired_model(config):
    torch.manual_seed(817)
    model = build_model(config)
    return model


def result(model, batch, stats, variant="DP"):
    supervision = SupervisionConfig.from_variant(variant)
    outputs = model.forward_pretrain(batch, supervision.objectives)
    loss = compute_pretrain_loss(outputs, batch, stats, supervision, LossWeights(), Phase1JointSchedule(), 0,
                                 graph_descriptor_indices=model.graph_descriptor_target_indices, phase1_mode=True)
    return outputs, loss


@pytest.mark.parametrize("route", ("light", "expert"))
def test_affine_units_leave_standardized_loss_and_all_parameter_gradients_unchanged(route):
    stats = statistics()
    changed_stats = statistics(factor=4., offset=10.)
    batch, transformed = _batch(), _batch()
    transformed.energy = transformed.energy * 4. + 10.
    transformed.y = transformed.y * 4. + 10.
    transformed.rdkit_graph_desc = transformed.rdkit_graph_desc * 4. + 10.
    transformed.rdkit_node_estate_index = transformed.rdkit_node_estate_index * 4. + 10.
    model = paired_model(configuration(route, stats=stats))
    changed_model = paired_model(configuration(route, stats=changed_stats))
    outputs, loss = result(model, batch, stats)
    changed_outputs, changed_loss = result(changed_model, transformed, changed_stats)
    torch.testing.assert_close(changed_outputs.energy_pred, outputs.energy_pred * 4. + 10., rtol=2e-6, atol=2e-6)
    torch.testing.assert_close(changed_loss.total, loss.total, rtol=2e-5, atol=2e-6)
    loss.total.backward()
    changed_loss.total.backward()
    gradients = dict(changed_model.named_parameters())
    for name, parameter in model.named_parameters():
        other = gradients[name]
        assert (parameter.grad is None) == (other.grad is None), name
        if parameter.grad is not None:
            torch.testing.assert_close(parameter.grad, other.grad, rtol=3e-5, atol=3e-6, msg=name)
    assert any(parameter.grad is not None and parameter.grad.abs().sum() > 0 for parameter in model.backbone.parameters())


@pytest.mark.parametrize("route", ("light", "expert"))
def test_public_predictions_use_original_units_and_padding_and_other_heads_are_preserved(route):
    stats = statistics()
    raw = paired_model(configuration(route))
    rng_after_raw = torch.random.get_rng_state().clone()
    conditioned = paired_model(configuration(route, stats=stats))
    assert torch.equal(torch.random.get_rng_state(), rng_after_raw)
    for name, parameter in raw.named_parameters():
        torch.testing.assert_close(parameter, dict(conditioned.named_parameters())[name], rtol=0, atol=0)
    batch = _batch()
    objectives = SupervisionConfig.from_variant("SDP").objectives
    old, new = raw.forward_pretrain(batch, objectives), conditioned.forward_pretrain(batch, objectives)
    torch.testing.assert_close(new.energy_pred, stats["muE"] + stats["stdE"] * old.energy_pred)
    real = old.node_mask.squeeze(-1)
    for before, after, mean, std in (
        (old.charge_pred, new.charge_pred, stats["muQ"], stats["stdQ"]),
        (old.charge_descriptor_pred["estate_index"], new.charge_descriptor_pred["estate_index"],
         stats["estate_index_mu"], stats["estate_index_std"]),
    ):
        torch.testing.assert_close(after[real], mean + std * before[real])
        assert after[~real].eq(0).all()
    for column, name in enumerate(PHASE1_GRAPH_DESCRIPTOR_NAMES):
        index = GRAPH_DESCRIPTOR_NAMES.index(name)
        expected = stats["graph_desc_mu"][index] + stats["graph_desc_std"][index] * old.graph_descriptor_by_name[name]
        torch.testing.assert_close(new.graph_descriptor_by_name[name], expected)
        torch.testing.assert_close(new.graph_descriptor_pred[:, column:column + 1], expected)
    for name in ("donor", "acceptor"):
        torch.testing.assert_close(new.charge_descriptor_pred[name], old.charge_descriptor_pred[name], rtol=0, atol=0)
    for name in new.element_descriptor_pred:
        torch.testing.assert_close(new.element_descriptor_pred[name], old.element_descriptor_pred[name], rtol=0, atol=0)
    torch.testing.assert_close(new.element_logits, old.element_logits, rtol=0, atol=0)
    torch.testing.assert_close(new.coordinate_pred, old.coordinate_pred, rtol=0, atol=0)
    torch.testing.assert_close(new.bond.order, old.bond.order, rtol=0, atol=0)


def test_h0_does_not_depend_on_statistics_and_model_contract_is_not_aliased():
    first_config = configuration(stats=statistics())
    first = paired_model(first_config)
    changed = paired_model(configuration(stats=statistics(factor=4., offset=10.)))
    batch = _batch()
    torch.testing.assert_close(first.encode_atoms(batch), changed.encode_atoms(batch), rtol=0, atol=0)
    torch.testing.assert_close(first.encode_graph(batch), changed.encode_graph(batch), rtol=0, atol=0)
    saved = deepcopy(first.config_dict())
    first_config["head"]["regression_output_normalization"]["targets"]["energy"]["mean"] = 999.
    exported = first.config_dict()
    exported["head_config"]["regression_output_normalization"]["targets"]["energy"]["mean"] = -999.
    assert first.config_dict() == saved
    assert not tuple(first.regression_output_normalizer.parameters())
    assert set(saved["head_config"]["regression_output_normalization"]["targets"]) == set(REGRESSION_TARGETS)
    assert len(REGRESSION_TARGETS) == 26


def test_same_shape_different_normalization_resume_is_rejected_before_mutation(tmp_path):
    config = configuration(stats=statistics())
    model = paired_model(config)
    optimizer = build_adamw(model, lr=3e-5, weight_decay=.01)
    scheduler = build_warmup_cosine_scheduler(optimizer, total_steps=20, warmup_steps=2)
    manifest = {"protocol": "normalization-contract-test", "training_view_hash": "b" * 64}
    path = tmp_path / "checkpoint.pt"
    save_training_checkpoint(path, model=model, optimizer=optimizer, scheduler=scheduler, config=config,
                             supervision=SupervisionConfig.from_variant("SDP").to_dict(), dataset_manifest=manifest,
                             exposure_step=0, optimizer_update_step=0, checkpoint_type="paired_random", project_root=tmp_path)
    altered_config = configuration(stats=statistics(factor=4., offset=10.))
    altered = paired_model(altered_config)
    before = {key: value.clone() for key, value in altered.state_dict().items()}
    with pytest.raises(RuntimeError, match="model/head semantics mismatch"):
        load_training_checkpoint(path, model=altered, expected_config=altered_config, expected_dataset_manifest=manifest,
                                 strict_semantics=True)
    for key, value in altered.state_dict().items():
        torch.testing.assert_close(value, before[key], rtol=0, atol=0)
    restored = paired_model(config)
    load_training_checkpoint(path, model=restored, expected_config=config, expected_dataset_manifest=manifest, strict_semantics=True)
    for key, value in restored.state_dict().items():
        torch.testing.assert_close(value, model.state_dict()[key], rtol=0, atol=0)


def test_absent_label_continuous_heads_still_have_none_grad_and_no_adamw_drift():
    stats = statistics()
    model = paired_model(configuration(stats=stats))
    batch = _batch()
    batch.rdkit_graph_desc_mask[:, GRAPH_DESCRIPTOR_NAMES.index("MolLogP")] = 0
    batch.rdkit_node_estate_index[:] = float("nan")
    missing = list(model.graph_descriptor_heads["MolLogP"].parameters()) + list(model.charge_descriptor_heads["estate_index"].parameters())
    before = [parameter.detach().clone() for parameter in missing]
    optimizer = build_adamw(model, lr=1e-3, weight_decay=.1)
    optimizer.zero_grad(set_to_none=True)
    _, loss = result(model, batch, stats, "D")
    assert set(loss.missing_tasks) == {"graph_descriptor/MolLogP", "node_descriptor/estate_index"}
    loss.total.backward()
    assert all(parameter.grad is None for parameter in missing)
    optimizer.step()
    for parameter, old in zip(missing, before):
        torch.testing.assert_close(parameter, old, rtol=0, atol=0)


def test_training_contract_rejects_validation_tampering_and_missing_or_invalid_statistics():
    stats = statistics()
    source = provenance(stats)
    with pytest.raises(ValueError, match="train-only"):
        train_regression_normalization(stats, {**source, "train_only": False})
    with pytest.raises(ValueError, match="statistics_hash mismatch"):
        train_regression_normalization({**stats, "muE": 99.}, source)
    with pytest.raises(ValueError, match="provenance_hash mismatch"):
        train_regression_normalization(stats, {**source, "cap": 999})
    missing = {key: value for key, value in stats.items() if key != "muQ"}
    with pytest.raises(ValueError, match="all train-fitted means"):
        train_regression_normalization(missing, provenance(missing))
    zero_std = {**stats, "stdQ": 0.}
    with pytest.raises(ValueError, match="positive"):
        train_regression_normalization(zero_std, provenance(zero_std))
    changed = train_regression_normalization(stats, source)
    changed["targets"]["energy"]["mean"] += 1.
    changed["contract_sha256"] = canonical_hash({key: value for key, value in changed.items() if key != "contract_sha256"})
    with pytest.raises(ValueError, match="differs from its train-fitted"):
        validate_regression_normalization(changed)
    excluded = train_regression_normalization(stats, source)
    excluded["targets"]["node_descriptor/formal_charge"] = {"mean": 0., "std": 1., "count": 2}
    with pytest.raises(ValueError, match="exactly the retained"):
        validate_regression_normalization(excluded)
    legacy = configuration(stats=stats)
    legacy["head"]["profile"] = "legacy"
    with pytest.raises(ValueError, match="Phase 1-only"):
        build_model(legacy)
