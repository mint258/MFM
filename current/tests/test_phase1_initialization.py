"""Fresh synthetic CPU models only; no formal artifacts or data are produced."""
from copy import deepcopy
import json
import random

import numpy as np
import pytest
import torch

from conftest import small_config
from test_phase1_normalization import provenance, statistics
import phychem_mfm.phase1.initialization as initialization
from phychem_mfm.factory import build_model
from phychem_mfm.model.normalization import train_regression_normalization
from phychem_mfm.phase1.formal_runtime import (
    INIT_RECIPE, backbone_state_hash, module_manifest, verify_architecture, verify_paired_initialization,
)
from phychem_mfm.phase1.identity import canonical_hash
from phychem_mfm.phase1.objectives import PHASE1_VARIANTS


def fixture_config(route="light", *, statistic_offset=0.):
    config = small_config(route)
    config["architecture"]["type"] = "shared_multitask"
    config["head"].update(profile="phase1", geometry_head="legacy")
    config["phase1"] = {"status": "synthetic_test_fixture", "atom_encoding": "zero_based",
                        "regression_output_mode": "train_affine"}
    stats = statistics(offset=statistic_offset)
    source = provenance(stats)
    source["diagnostic_only"] = False
    source["provenance_hash"] = canonical_hash({key: value for key, value in source.items() if key != "provenance_hash"})
    config["head"]["regression_output_normalization"] = train_regression_normalization(stats, source)
    return config


def prepare(config, seed=17):
    return initialization.prepare_initialization(config, seed, scope="synthetic_test_fixture")


def formal_cpu_model(config, seed):
    # Exactly the formal entry's CPU initialization order; isolate this test's
    # reference build as well so it cannot perturb another assertion's RNG.
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(seed)
        return build_model(config)


@pytest.mark.parametrize("route", ["light", "expert"])
def test_strict_consumers_accept_json_roundtrip_and_actual_cpu_model(route):
    config = fixture_config(route)
    result = json.loads(json.dumps(prepare(config), allow_nan=False))
    paired, architecture, proof = (result[name] for name in ("paired_initialization", "architecture", "proof"))
    model = formal_cpu_model(config, 17)
    assert set(paired) == {"schema_version", "seed", "backbone_state_sha256", "hash_recipe"}
    assert paired["schema_version"] == "phase1_paired_init_v1" and paired["hash_recipe"] == INIT_RECIPE
    assert set(architecture) == {"schema_version", "config", "module_manifest"}
    assert set(architecture["config"]) == {"architecture", "backbone", "expert", "head"}
    assert verify_paired_initialization(model, paired, 17) == backbone_state_hash(model)
    verify_architecture(model, config, architecture)
    assert architecture["module_manifest"] == module_manifest(model)
    assert all(value.device.type == "cpu" and value.dtype == torch.float32 for value in model.parameters())
    assert proof["state"] == "NOT_FROZEN" and proof["formal_eligible"] is False
    assert proof["scope"] == "synthetic_test_fixture" and proof["strict_formal_consumer_selfcheck_passed"]
    assert proof["affine_contract_sha256"] == config["head"]["regression_output_normalization"]["contract_sha256"]
    assert proof["historical_weights_or_data_read"] is False


def test_each_seed_pairs_all_eight_conditions_without_training_and_other_seed_differs():
    config = fixture_config()
    expected = None
    for variant in PHASE1_VARIANTS:
        condition = deepcopy(config)
        condition["supervision"]["variant"] = variant
        result = prepare(condition, 23)
        digest = result["paired_initialization"]["backbone_state_sha256"]
        expected = digest if expected is None else expected
        assert digest == expected
        assert result["proof"]["construction_seed"] == 23
    assert prepare(config, 24)["paired_initialization"]["backbone_state_sha256"] != expected


def test_light_expert_and_existing_geometry_heads_preserve_common_backbone_but_architecture_is_bound():
    light, expert = fixture_config("light"), fixture_config("expert")
    first, second = prepare(light), prepare(expert)
    assert first["paired_initialization"] == second["paired_initialization"]
    assert first["architecture"]["module_manifest"]["total_parameters"] < second["architecture"]["module_manifest"]["total_parameters"]
    residual = deepcopy(light)
    residual["head"].update(geometry_head="residual", geometry_residual_hidden_dim=8, geometry_residual_scale=.1)
    assert prepare(residual)["paired_initialization"] == first["paired_initialization"]
    for changed in (expert, residual, fixture_config(statistic_offset=2.)):
        with pytest.raises(ValueError, match="architecture/module manifest"):
            verify_architecture(formal_cpu_model(changed, 17), changed, first["architecture"])


def test_consumer_refuses_extra_paired_fields_wrong_seed_or_changed_actual_weights():
    config = fixture_config()
    result, model = prepare(config), formal_cpu_model(config, 17)
    paired = result["paired_initialization"]
    for changed in ({**paired, "proof": {}}, {**paired, "seed": 18}, {**paired, "hash_recipe": "shape_only"}):
        with pytest.raises(ValueError, match="Fresh random H0"):
            verify_paired_initialization(model, changed, 17)
    with torch.no_grad():
        next(model.backbone.parameters()).add_(1.)
    with pytest.raises(ValueError, match="Fresh random H0"):
        verify_paired_initialization(model, paired, 17)


def test_caller_torch_python_numpy_rng_config_and_defaults_are_unchanged_and_cuda_is_not_seeded(monkeypatch):
    config = fixture_config()
    original = deepcopy(config)
    cpu_rng, python_rng, numpy_rng = torch.get_rng_state().clone(), random.getstate(), np.random.get_state()
    def forbidden(*args, **kwargs):
        raise AssertionError("CPU producer accessed weights/data/CUDA seeding")
    monkeypatch.setattr(torch, "load", forbidden)
    monkeypatch.setattr(torch.cuda, "manual_seed_all", forbidden)
    result = prepare(config)
    assert config == original and torch.equal(torch.get_rng_state(), cpu_rng)
    assert random.getstate() == python_rng
    now = np.random.get_state()
    assert now[0] == numpy_rng[0] and np.array_equal(now[1], numpy_rng[1]) and now[2:] == numpy_rng[2:]
    assert torch.get_default_device().type == "cpu" and torch.get_default_dtype() == torch.float32
    result["architecture"]["config"]["backbone"]["dim"] = 999
    assert config == original


def test_failed_actual_construction_restores_rng_and_does_not_change_input(monkeypatch):
    config = fixture_config()
    before, original = torch.get_rng_state().clone(), deepcopy(config)
    def failed_build(payload):
        torch.rand(5)
        payload["backbone"]["dim"] = 999
        raise RuntimeError("synthetic construction failure")
    monkeypatch.setattr(initialization, "build_model", failed_build)
    with pytest.raises(RuntimeError, match="synthetic construction failure"):
        prepare(config)
    assert torch.equal(torch.get_rng_state(), before) and config == original


@pytest.mark.parametrize("seed", [-1, True, 1.0, "1", None, 2 ** 64])
def test_invalid_seed_cannot_enter_generator(seed):
    before = torch.get_rng_state().clone()
    with pytest.raises(ValueError):
        prepare(fixture_config(), seed)
    assert torch.equal(torch.get_rng_state(), before)


@pytest.mark.parametrize("change", ["missing_block", "unknown_profile", "architecture", "undeclared_route",
                                   "missing_backbone", "fractional_dim", "bool_heads", "indivisible_heads",
                                   "feature_switch", "bad_radius", "bad_dropout", "fractional_expert",
                                   "diagnostic", "subset", "raw_outputs", "missing_affine", "stale_affine",
                                   "diagnostic_statistics", "non_json"])
def test_illegal_or_diagnostic_configuration_is_rejected_without_mutation(change):
    config = fixture_config()
    if change == "missing_block":
        config.pop("expert")
    elif change == "unknown_profile":
        config["head"]["profile"] = "legacy"
    elif change == "architecture":
        config["architecture"]["type"] = "fusion"
    elif change == "undeclared_route":
        config["architecture"].pop("preset")
    elif change == "missing_backbone":
        config["backbone"].pop("radius")
    elif change in ("fractional_dim", "bool_heads", "indivisible_heads", "feature_switch", "bad_radius", "bad_dropout"):
        name, value = {"fractional_dim": ("dim", 32.5), "bool_heads": ("heads", True),
                       "indivisible_heads": ("heads", 3), "feature_switch": ("use_dist_bias", 1),
                       "bad_radius": ("radius", -1.), "bad_dropout": ("dropout", 1.)}[change]
        config["backbone"][name] = value
    elif change == "fractional_expert":
        config["expert"]["real_layers"] = .5
    elif change == "diagnostic":
        config["phase1"]["status"] = "diagnostic_only"
    elif change == "subset":
        config["phase1"]["diagnostic_limit"] = 2
    elif change == "raw_outputs":
        config["phase1"]["regression_output_mode"] = "raw"
    elif change == "missing_affine":
        config["head"].pop("regression_output_normalization")
    elif change == "stale_affine":
        config["head"]["regression_output_normalization"]["targets"]["energy"]["mean"] += 1.
    elif change == "diagnostic_statistics":
        norm = config["head"]["regression_output_normalization"]
        source = deepcopy(norm["training_provenance"])
        source["diagnostic_only"] = True
        source["provenance_hash"] = canonical_hash({key: value for key, value in source.items() if key != "provenance_hash"})
        config["head"]["regression_output_normalization"] = train_regression_normalization(norm["training_statistics"], source)
    else:
        config["expert"]["opaque_tensor"] = torch.ones(2)
    before = torch.get_rng_state().clone()
    original = deepcopy(config)
    with pytest.raises(ValueError):
        prepare(config)
    assert torch.equal(torch.get_rng_state(), before)
    if change != "non_json":
        assert config == original
    else:
        assert torch.equal(config["expert"]["opaque_tensor"], original["expert"]["opaque_tensor"])


def test_nonstandard_global_dtype_or_device_is_rejected_without_changing_caller_defaults():
    config = fixture_config()
    before = torch.get_rng_state().clone()
    original_dtype = torch.get_default_dtype()
    try:
        torch.set_default_dtype(torch.float64)
        with pytest.raises(ValueError, match="CPU float32 defaults"):
            prepare(config)
        assert torch.get_default_dtype() == torch.float64
    finally:
        torch.set_default_dtype(original_dtype)
    with torch.device("meta"):
        with pytest.raises(ValueError, match="CPU float32 defaults"):
            prepare(config)
        assert torch.get_default_device().type == "meta"
    assert torch.equal(torch.get_rng_state(), before) and torch.get_default_device().type == "cpu"


def test_preparation_scope_is_explicit_not_frozen_and_diagnostic_cannot_be_promoted():
    config = fixture_config()
    with pytest.raises(ValueError, match="Diagnostic/subset"):
        initialization.prepare_initialization(config, 17)
    config["phase1"]["status"] = "preparation"
    result = initialization.prepare_initialization(config, 17)
    assert result["proof"]["scope"] == "preparation" and not result["proof"]["formal_eligible"]
    assert result["proof"]["state"] == "NOT_FROZEN"
    assert "state" not in result["architecture"] and "proof" not in result["paired_initialization"]
    with pytest.raises(ValueError, match="never formal"):
        initialization.prepare_initialization(config, 17, scope="formal")
