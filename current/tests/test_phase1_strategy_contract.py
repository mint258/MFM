"""Explicit comparison scope; no real data, scheduler or GPU access."""
from copy import deepcopy

import pytest

from phychem_mfm.phase1.strategy_contract import (
    contrast_hash_fields, contrast_run_count, validated_contrasts,
)


def declared():
    return {"pretraining": {"seeds": [0, 3, 5]}, "strategy": {"contrasts": {
        "s-first": {"variant": "SDP", "seeds": [0, 5], "recipe_sha256": "a" * 64},
        "p-first": {"variant": "SP", "seeds": [3], "recipe_sha256": "b" * 64},
    }}}


def test_explicit_subset_scope_and_detached_result():
    protocol = declared()
    original = deepcopy(protocol)
    result = validated_contrasts(protocol)
    assert contrast_run_count(protocol) == 3
    assert contrast_hash_fields(protocol) == (
        "strategy.contrasts.s-first.recipe_sha256", "strategy.contrasts.p-first.recipe_sha256")
    result["s-first"]["seeds"].append(3)
    result["p-first"]["variant"] = "SDP"
    assert protocol == original
    assert validated_contrasts(protocol) == original["strategy"]["contrasts"]


@pytest.mark.parametrize("protocol", ({}, {"strategy": {}}, {"strategy": {"contrasts": {}}}))
def test_absent_comparisons_do_not_infer_a_new_matrix(protocol):
    assert validated_contrasts(protocol) == {}
    assert contrast_run_count(protocol) == 0
    assert contrast_hash_fields(protocol) == ()


@pytest.mark.parametrize("bad_id", ("direct_joint", "SDP", "a.b", "../recipe", "", "a" * 65, 1, True))
def test_recipe_names_cannot_alias_direct_or_dotted_artifact_paths(bad_id):
    protocol = declared()
    entry = protocol["strategy"]["contrasts"].pop("s-first")
    protocol["strategy"]["contrasts"][bad_id] = entry
    with pytest.raises(ValueError, match="Contrast id"):
        validated_contrasts(protocol)


@pytest.mark.parametrize("defect", (
    "no_map", "null_map", "missing_field", "extra_field", "single_group", "none",
    "alias", "seed_not_paired", "bool_seed", "duplicate_seed", "no_seed",
    "bad_main_seeds", "unhashed_recipe", "duplicate_run",
))
def test_invalid_scope_does_not_drop_or_repair_a_comparison(defect):
    protocol = declared()
    contrasts = protocol["strategy"]["contrasts"]
    entry = contrasts["s-first"]
    if defect == "no_map":
        protocol["strategy"]["contrasts"] = [entry]
    elif defect == "null_map":
        protocol["strategy"]["contrasts"] = None
    elif defect == "missing_field":
        entry.pop("recipe_sha256")
    elif defect == "extra_field":
        entry["max_updates"] = 20
    elif defect == "single_group":
        entry["variant"] = "D"
    elif defect == "none":
        entry["variant"] = "none"
    elif defect == "alias":
        entry["variant"] = "SPD"
    elif defect == "seed_not_paired":
        entry["seeds"] = [7]
    elif defect == "bool_seed":
        entry["seeds"] = [True]
    elif defect == "duplicate_seed":
        entry["seeds"] = [0, 0]
    elif defect == "no_seed":
        entry["seeds"] = []
    elif defect == "bad_main_seeds":
        protocol["pretraining"]["seeds"] = [0, 0]
    elif defect == "unhashed_recipe":
        entry["recipe_sha256"] = "recipe-v1"
    else:
        contrasts["same-run-new-name"] = deepcopy(entry)
    before = deepcopy(protocol)
    with pytest.raises(ValueError):
        validated_contrasts(protocol)
    assert protocol == before


def test_same_recipe_can_use_disjoint_paired_seeds_without_duplicate_runs():
    protocol = declared()
    entry = deepcopy(protocol["strategy"]["contrasts"]["s-first"])
    entry["seeds"] = [3]
    protocol["strategy"]["contrasts"]["same-recipe-other-seed"] = entry
    assert contrast_run_count(protocol) == 4
