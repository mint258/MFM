"""Metadata role evidence and bounded label-free selection, without native reads."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from phychem_mfm.phase1.v3_coordinate_lookup_source import (INPUT_SHA, LookupSelection,
    OLD, ORIGINAL_SNAPSHOT_SHA, SNAPSHOT_BINDER, bind_source_snapshot, choose_metadata, role_evidence)


def declarations():
    config = {"variant": "S", "input_manifest_sha256": INPUT_SHA}
    inputs = {"status": "INPUT_METADATA_CLOSED_NATIVE_SAMPLE_PASS",
              "roles": {"train": {"records": 11104772}, "full": {"records": 127082}}}
    population = {"status": "WP5_FORMAL_POPULATION_CLOSED", "configuration": {
        "FULL_anchor_promotes_entire_TRAIN_component": True, "routine_is_FULL_monitor_subset": True},
        "roles": [{"split": "train", "records": 11104772}, {"split": "full", "records": 127082}]}
    protocol = {"validation_population_policy": {"terminal": "full_declared_validation_at_three_epoch_FINAL"},
                "artifacts": {"full_validation_manifest": {"sha256": "a"*64}}}
    return config, inputs, population, protocol


def test_pretraining_full_role_requires_original_protocol_and_population_evidence():
    evidence = role_evidence(*declarations())
    assert evidence["role_map"] == {"TRAIN": "train", "PRETRAIN_VAL": "full"}
    assert evidence["downstream_final_role_or_scores_used"] is False
    assert evidence["D5_new_split_claimed"] is False
    values = declarations(); values[3]["validation_population_policy"]["terminal"] = "test"
    with pytest.raises(ValueError, match="explicitly define"):
        role_evidence(*values)
    values = declarations(); values[2]["roles"][1]["records"] = 127081
    with pytest.raises(ValueError, match="counts differ"):
        role_evidence(*values)
    values = declarations(); values[0]["variant"] = "downstream"
    with pytest.raises(ValueError, match="existing frozen S"):
        role_evidence(*values)


class MetadataIndex:
    def __init__(self, atom_counts):
        self.atoms = atom_counts
        self.ref_calls = []
    def __len__(self):
        return len(self.atoms)
    def ref(self, index):
        self.ref_calls.append(index)
        return SimpleNamespace(native_n_atoms=self.atoms[index], record_id="r"+str(index),
            molecule_id="m"+str(index), payload_sha256="a"*64)
    def get(self, *args, **kwargs):
        raise AssertionError("A semantic record decoder was called during metadata selection")


def test_selection_uses_counts_and_identities_only_and_is_fixed_before_any_geometry():
    selection = LookupSelection(train_records=3, validation_records=2, max_candidates_per_role=12)
    index = MetadataIndex([4, 600, 5, 0, 512, 513, 8, 9, 10, 600, 3, 4])
    counts = MetadataIndex(index.atoms)
    first = choose_metadata(index, counts, wanted=3, seed=17, selection=selection)
    second = choose_metadata(index, counts, wanted=3, seed=17, selection=selection)
    assert first == second and len(first) == 3
    assert all(0 < row["native_n_atoms"] <= 512 for row in first)
    assert len({row["record_id"] for row in first}) == 3
    assert len(counts.ref_calls) >= len(index.ref_calls)


def test_insufficient_predeclared_candidates_fail_without_selection_budget_increase():
    selection = LookupSelection(train_records=3, validation_records=2, max_candidates_per_role=3)
    index = MetadataIndex([513, 600, 700])
    with pytest.raises(ValueError, match="insufficient eligible"):
        choose_metadata(index, index, wanted=3, seed=17, selection=selection)


def test_selection_bounds_require_an_explicit_sufficient_candidate_budget():
    with pytest.raises(ValueError, match="candidate bound"):
        LookupSelection(max_candidates_per_role=1024)
    with pytest.raises(ValueError, match="Positive integer"):
        LookupSelection(max_record_atoms=0)


def test_snapshot_source_rejects_an_unregistered_pin_or_path_before_source_access(tmp_path):
    with pytest.raises(ValueError, match="preregistered original S snapshot pin"):
        bind_source_snapshot(OLD / "training_inputs_v1/shard_snapshot_v1.json", "0"*64)
    with pytest.raises(ValueError, match="preregistered original S snapshot pin"):
        bind_source_snapshot(tmp_path / "different.json", ORIGINAL_SNAPSHOT_SHA)


@pytest.mark.skipif(not SNAPSHOT_BINDER.is_file() or not (OLD / "training_inputs_v1/shard_snapshot_v1.json").is_file(),
                    reason="Actual site's immutable S snapshot and fixed tested binder are unavailable")
def test_actual_original_snapshot_fixed_binder_preserves_raw_bytes_and_independent_parsed_copy():
    path = OLD / "training_inputs_v1/shard_snapshot_v1.json"
    before = path.read_bytes()
    value, receipt = bind_source_snapshot(path, ORIGINAL_SNAPSHOT_SHA)
    first = next(iter(value["shards"]))
    original_device = value["shards"][first]["identity"][0]
    value["shards"][first]["identity"][0] = original_device + 1
    repeated, receipt2 = bind_source_snapshot(path, ORIGINAL_SNAPSHOT_SHA)
    assert receipt == receipt2 and path.read_bytes() == before
    assert repeated["shards"][first]["identity"][0] == original_device
    assert receipt["sha256"] == ORIGINAL_SNAPSHOT_SHA
    assert receipt["original_bytes_modified"] is False
    assert receipt["node_local_device_projection"] == "separate_existing_v2_adapter_copy_only"
