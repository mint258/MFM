"""Pinned DataB synthetic projection -> typed index -> real sampler/dataset.

No final D5/release authority, physical corpus, or label generation is used.
"""
from copy import deepcopy
from dataclasses import FrozenInstanceError, dataclass, replace
import hashlib
from itertools import islice
import os
from pathlib import Path
import random
import types

import numpy as np
import pytest
import torch

from phychem_mfm.phase1.v3_contract import FieldSpec, FieldTarget, LabelRegistry
from phychem_mfm.phase1.v3_data import DecodedSample, ManifestSampleDataset, collate_v3_samples
from phychem_mfm.phase1.v3_sampling import ConformationSelection
from phychem_mfm.phase1 import v3_sampling, v3_sampling_bridge
from phychem_mfm.phase1.v3_sampling_bridge import (CandidateProjectionInput, PROJECTION_SOURCE_SHA256,
                                                 build_candidate_sampling_index)

DATA_SOURCE = Path(os.environ.get("MODEL_V3_D5_PROJECTION_SOURCE",
    "/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository/"
    "workflows/data_v1_final/export/wire_v1/sampling_projection_v1.py"))


@pytest.fixture(scope="module")
def projector():
    raw = DATA_SOURCE.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == PROJECTION_SOURCE_SHA256, "DataB actual source pin differs"
    module = types.ModuleType("model_v3_pinned_data_projection_fixture")
    # Execute the actual verified source bytes, avoiding an unrelated .pyc or
    # a local mirror of the data line's implementation.
    exec(compile(raw, str(DATA_SOURCE), "exec"), module.__dict__)
    yield module.project_training_sources
    assert hashlib.sha256(DATA_SOURCE.read_bytes()).hexdigest() == PROJECTION_SOURCE_SHA256


def arguments(mid, number, counts):
    geometries, orders, atoms = [], [], {}
    for source, count in zip(("pm7", "uff_sprime"), counts):
        ids = [f"{mid}:{source}:g{100 - 3 * i}" for i in range(count)]
        for i, gid in enumerate(ids):
            geometries.append({"geometry_id": gid, "molecule_id": mid, "geometry_source": source,
                # UFF may retain the original PM7 record as provenance. It must
                # not become UFF's conformer identity or cross-source join key.
                "native_record_id": f"native-{mid}-p{i}" if source == "pm7" else f"native-{mid}-p0",
                "sprime_conf_idx": None if source == "pm7" else 17 + 3 * i,
                "parent_geometry_id": None, "view_id": None})
            atoms[gid] = 4 + number
        source_orders = {"fixed_random": ids, "energy": list(reversed(ids)),
                         "diversity": ids[1:] + ids[:1]}
        for kind, ordered in source_orders.items():
            for rank, gid in enumerate(ordered):
                orders.append({"molecule_id": mid, "geometry_source": source, "geometry_id": gid,
                    "order_type": kind, "rank": rank if kind == "fixed_random" else rank + 1,
                    "training_rank": rank})
        view = deepcopy(geometries[-count])
        view.update(geometry_id=f"{mid}:{source}:allowed-offeq", parent_geometry_id=ids[0], view_id="offeq")
        geometries.append(view)
    return {"effective_role": "TRAIN", "training_geometries": geometries, "training_orders": orders,
        "diagnostic_targets": [
            {"molecule_id": mid, "geometry_source": "pm7", "geometry_id": f"{mid}:held-p-energy0"},
            {"molecule_id": mid, "geometry_source": "pm7", "geometry_id": f"{mid}:held-p-child"},
            {"molecule_id": mid, "geometry_source": "uff_sprime", "geometry_id": f"{mid}:held-u-energy0"}],
        "native_atom_counts": atoms, "group_mask": {"S": True, "D": True, "P": number != 1},
        "family_mask": {"physics": number != 2}}


def inputs(projector):
    result = []
    for i, counts in enumerate(((1, 5), (4, 2), (9, 3))):
        mid = f"m{i}"
        args = arguments(mid, i, counts)
        actual_projection = projector(mid, **args)
        result.append(CandidateProjectionInput(mid, actual_projection, args, PROJECTION_SOURCE_SHA256))
    return result


def bridge(items, **overrides):
    options = {"data_version": "candidate-integration-fixture-v1", "geometry_source": "PM7",
               "selected_molecule_ids": [item.molecule_id for item in items], "allow_candidate": True}
    options.update(overrides)
    return build_candidate_sampling_index(items, **options)


class ProjectionProvider:
    def __init__(self, sampling_index):
        self.index = sampling_index
        self.closed = False

    def read(self, draw):
        assert not self.closed and draw.index_sha256 == self.index.content_sha256
        native = self.index.native_identity_for(draw.locator)
        assert native.geometry_id == draw.conformer_id and native.molecule_id == draw.molecule_id
        assert native.model_geometry_source == draw.geometry_source
        n = draw.native_atoms
        offset = 0. if draw.geometry_source == "PM7" else 10.
        value = float(sum(draw.locator.encode("utf-8")))
        return DecodedSample(draw.molecule_id, draw.conformer_id, draw.geometry_source,
            torch.full((n, 1), 5, dtype=torch.long),
            torch.arange(n * 3, dtype=torch.float32).reshape(n, 3) / 10 + offset,
            torch.arange(n, dtype=torch.long),
            {"p": FieldTarget(torch.tensor([[value]], dtype=torch.float32), torch.ones(1, dtype=torch.bool))})

    def close(self):
        self.closed = True


@dataclass(frozen=True)
class ProjectionFactory:
    sampling_index: object
    read_only = node_local = True

    @property
    def data_version(self):
        return self.sampling_index.version

    def __call__(self):
        return ProjectionProvider(self.sampling_index)


@pytest.mark.parametrize("source", ["PM7", "Sprime_UFF", "mixed"])
def test_actual_data_projection_to_sampler_and_bound_dataset_preserves_sources_and_masks(projector, source):
    raw = inputs(projector)
    mixed = {"m0": "Sprime_UFF", "m1": "PM7", "m2": "Sprime_UFF"} if source == "mixed" else None
    idx = bridge(raw, geometry_source=source, mixed_sources=mixed, data_version="caller-chosen-fixture-version")
    assert idx.version == "caller-chosen-fixture-version" and idx.authority == "synthetic_fixture"
    assert not idx.contract_finalized and not idx.real_data_export_accepted
    assert len(idx) == 3 and len({idx.molecule_at(i).molecule_id for i in range(3)}) == 3
    assert idx.projections[0].entry_for("PM7").conformers[0].conformer_id != idx.projections[0].entry_for("Sprime_UFF").conformers[0].conformer_id
    assert [len(p.entry_for("PM7").conformers) for p in idx.projections] == [1, 4, 9]
    assert [len(p.entry_for("Sprime_UFF").conformers) for p in idx.projections] == [5, 2, 3]
    sampler = idx.make_sampler(seed=20261025, sample_budget=90)
    dataset = ManifestSampleDataset(idx, ProjectionFactory(idx))
    reg = LabelRegistry((FieldSpec("p", "P", "physics", "graph"),), "synthetic-registry", "a" * 64)
    try:
        draws = list(sampler)
        assert {draw.molecule_id for draw in draws} == {"m0", "m1", "m2"}
        batch = collate_v3_samples([dataset[draw] for draw in draws], reg)
        for draw, sample_value in zip(draws, batch.targets["p"].values[:, 0]):
            expected_source = mixed[draw.molecule_id] if source == "mixed" else source
            assert draw.geometry_source == expected_source
            native = idx.native_identity_for(draw.conformer_id)
            assert native.model_geometry_source == expected_source and draw.locator == native.geometry_id
            assert sample_value.item() == sum(draw.locator.encode("utf-8"))
            assert "offeq" not in draw.locator and "held" not in draw.locator
        assert batch.targets["p"].valid.tolist() == [draw.molecule_id == "m0" for draw in draws]
        assert sampler.samples_consumed == 0
        owner = dataset._provider
    finally:
        dataset.close()
    assert owner.closed


@pytest.mark.parametrize("source", ["PM7", "Sprime_UFF"])
def test_energy_minimum_uses_retained_training_rank_zero_after_original_minimum_exclusion(projector, source):
    raw = inputs(projector)
    idx = bridge(raw, geometry_source=source, selection=ConformationSelection("minimum_energy"))
    data_source = "pm7" if source == "PM7" else "uff_sprime"
    expected = {}
    for item in raw:
        energy = [row for row in item.training_arguments["training_orders"]
                  if row["geometry_source"] == data_source and row["order_type"] == "energy"]
        first = min(energy, key=lambda row: row["training_rank"])
        assert first["training_rank"] == 0 and first["rank"] == 1
        expected[item.molecule_id] = first["geometry_id"]
    draws = list(idx.make_sampler(seed=8, sample_budget=100))
    assert all(draw.conformer_id == expected[draw.molecule_id] for draw in draws)
    assert all("held" not in draw.locator for draw in draws)


@pytest.mark.parametrize("source", ["PM7", "Sprime_UFF"])
@pytest.mark.parametrize("mode,k", [("all", None), ("first_k", 2), ("minimum_energy", None), ("diversity_first_k", 2)])
def test_each_selection_uses_its_source_specific_training_order(projector, source, mode, k):
    raw = inputs(projector)
    idx = bridge(raw, selected_molecule_ids=["m1"], geometry_source=source, selection=ConformationSelection(mode, k))
    rows = raw[1].training_arguments["training_orders"]
    src = "pm7" if source == "PM7" else "uff_sprime"
    kind = {"all": "fixed_random", "first_k": "fixed_random", "minimum_energy": "energy", "diversity_first_k": "diversity"}[mode]
    ordered = sorted([r for r in rows if r["geometry_source"] == src and r["order_type"] == kind], key=lambda r: r["training_rank"])
    expected = [row["geometry_id"] for row in ordered]
    expected = expected[:1] if mode == "minimum_energy" else expected[:k] if k else expected
    assert {draw.conformer_id for draw in idx.make_sampler(seed=37, sample_budget=200)} == set(expected)


def test_uniform_molecule_sampling_despite_different_retained_conformer_counts(projector):
    from scipy.stats import chisquare
    idx = bridge(inputs(projector))
    molecules = np.zeros(3, dtype=np.int64)
    last_conformers = np.zeros(9, dtype=np.int64)
    positions = {ref.conformer_id: i for i, ref in enumerate(idx.molecule_at(2).conformers)}
    for draw in idx.make_sampler(seed=20261025, sample_budget=30000):
        molecules[draw.molecule_index] += 1
        if draw.molecule_index == 2:
            last_conformers[positions[draw.conformer_id]] += 1
    # Fixed seed and fixed 1% threshold, with no retries or seed selection.
    assert chisquare(molecules).pvalue >= .01
    assert chisquare(last_conformers).pvalue >= .01


def test_unconsumed_prefetch_resume_uses_bound_inputs_and_keeps_global_rng(projector):
    raw = inputs(projector)
    mixed = {"m0": "Sprime_UFF", "m1": "PM7", "m2": "Sprime_UFF"}
    idx = bridge(raw, geometry_source="mixed", mixed_sources=mixed)
    before = random.getstate(), np.random.get_state(), torch.get_rng_state().clone()
    sampler = idx.make_sampler(seed=71, sample_budget=60)
    iterator = iter(sampler)
    consumed, speculative = list(islice(iterator, 5)), list(islice(iterator, 9))
    assert sampler.samples_consumed == 0
    prefetched_dataset = ManifestSampleDataset(idx, ProjectionFactory(idx))
    try:
        prefetched_rows = [prefetched_dataset[draw][1] for draw in speculative]
    finally:
        prefetched_dataset.close()
    sampler.commit_batch(consumed)
    rebuilt = bridge(deepcopy(raw), geometry_source="mixed", mixed_sources=dict(mixed))
    assert rebuilt.content_sha256 == idx.content_sha256
    resumed = rebuilt.make_sampler(seed=71, sample_budget=60)
    resumed.load_state_dict(sampler.state_dict())
    repeated_draws = list(islice(resumed, 9))
    assert repeated_draws == speculative and resumed.samples_consumed == 5
    restored_dataset = ManifestSampleDataset(rebuilt, ProjectionFactory(rebuilt))
    try:
        for old, draw in zip(prefetched_rows, repeated_draws):
            current = restored_dataset[draw][1]
            assert torch.equal(current.x, old.x) and torch.equal(current.pos, old.pos)
            assert torch.equal(current.source_atom_ids, old.source_atom_ids)
            assert torch.equal(current.fields["p"].values, old.fields["p"].values)
            assert torch.equal(current.fields["p"].valid, old.fields["p"].valid)
    finally:
        restored_dataset.close()
    assert random.getstate() == before[0] and torch.equal(torch.get_rng_state(), before[2])
    np_after = np.random.get_state()
    assert np_after[0] == before[1][0] and np.array_equal(np_after[1], before[1][1]) and np_after[2:] == before[1][2:]


def test_actual_bridge_and_sampler_bytes_are_bound_besides_upstream_source_pin(projector):
    idx = bridge(inputs(projector))
    sources = idx.bindings["source_sha256"]
    assert sources["data_projection"] == hashlib.sha256(DATA_SOURCE.read_bytes()).hexdigest()
    assert sources["model_bridge"] == hashlib.sha256(Path(v3_sampling_bridge.__file__).read_bytes()).hexdigest()
    assert sources["model_sampler"] == hashlib.sha256(Path(v3_sampling.__file__).read_bytes()).hexdigest()
    bound = idx.bindings["input_projections"][0]
    assert set(bound) >= {"projection_sha256", "training_geometry_sha256", "training_orders_sha256",
                         "diagnostic_sha256", "native_atom_counts_sha256", "native_identity_sha256", "source_entry_sha256"}


def test_uff_null_native_provenance_is_preserved_without_borrowing_pm7_identity(projector):
    raw = inputs(projector)
    item = raw[0]
    row = next(r for r in item.training_arguments["training_geometries"] if r["geometry_source"] == "uff_sprime" and r["view_id"] is None)
    row["native_record_id"] = None
    raw[0] = replace(item, projection=projector(item.molecule_id, **item.training_arguments))
    idx = bridge(raw, geometry_source="Sprime_UFF")
    native = idx.native_identity_for(row["geometry_id"])
    assert native.native_record_id is None and native.sprime_conf_idx == 17
    assert native.model_geometry_source == "Sprime_UFF"


def test_identity_sidecars_and_bindings_are_snapshots_not_mutable_aliases(projector):
    raw = inputs(projector)
    idx = bridge(raw)
    before = idx.content_sha256
    gid = idx.projections[0].entry_for("Sprime_UFF").conformers[0].conformer_id
    identity = idx.native_identity_for(gid)
    assert identity.geometry_source == "uff_sprime" and identity.model_geometry_source == "Sprime_UFF"
    assert identity.native_record_id == "native-m0-p0" and identity.sprime_conf_idx == 17
    with pytest.raises(FrozenInstanceError):
        identity.native_record_id = "changed"
    with pytest.raises(FrozenInstanceError):
        idx.authority = "data_line"
    returned = idx.bindings
    returned["source_sha256"]["data_projection"] = "0" * 64
    raw[0].projection["native_conformer_identity"][gid]["sprime_conf_idx"] = 999
    raw[0].training_arguments["native_atom_counts"][gid] = 999
    assert idx.content_sha256 == before and idx.native_identity_for(gid).sprime_conf_idx == 17
    assert idx.bindings["source_sha256"]["data_projection"] == PROJECTION_SOURCE_SHA256
    with pytest.raises(KeyError):
        idx.native_identity_for("unselected-or-heldout-geometry")


@pytest.mark.parametrize("change", ["data_version", "selected_order", "selection", "orders_note", "diagnostic_note", "unused_source_native_id", "atom_counts"])
def test_content_changes_reject_old_committed_sampler_state_even_when_versions_match(projector, change):
    original = inputs(projector)
    idx = bridge(original)
    sampler = idx.make_sampler(seed=11, sample_budget=20)
    sampler.commit_batch(list(islice(sampler, 3)))
    raw, options = deepcopy(original), {}
    if change == "data_version":
        options["data_version"] = "another-explicit-caller-version"
    elif change == "selected_order":
        options["selected_molecule_ids"] = ["m2", "m0", "m1"]
    elif change == "selection":
        options["selection"] = ConformationSelection("minimum_energy")
    elif change in ("orders_note", "diagnostic_note"):
        key = "training_orders" if change == "orders_note" else "diagnostic_targets"
        raw[0].training_arguments[key][0]["fixture_evidence_note"] = "changed source evidence, same sampling entries"
    elif change == "unused_source_native_id":
        row = next(r for r in raw[0].training_arguments["training_geometries"] if r["geometry_source"] == "uff_sprime" and r["view_id"] is None)
        row["native_record_id"] = "different UFF provenance, no PM7 sampling change"
        raw[0] = replace(raw[0], projection=projector(raw[0].molecule_id, **raw[0].training_arguments))
    else:
        gid = raw[0].projection["source_entries"]["pm7"]["conformers"][0]["conformer_id"]
        raw[0].training_arguments["native_atom_counts"][gid] += 1
        raw[0] = replace(raw[0], projection=projector(raw[0].molecule_id, **raw[0].training_arguments))
    changed = bridge(raw, **options)
    assert changed.content_sha256 != idx.content_sha256
    if change != "data_version":
        assert changed.version == idx.version
    with pytest.raises(ValueError, match="contract changed"):
        changed.make_sampler(seed=11, sample_budget=20).load_state_dict(sampler.state_dict())


@pytest.mark.parametrize("opt_in", [False, None, 1])
def test_candidate_opt_in_is_explicit_and_does_not_accept_truthy_integers(projector, opt_in):
    with pytest.raises(ValueError, match="allow_candidate=True"):
        bridge(inputs(projector), allow_candidate=opt_in)


@pytest.mark.parametrize("corruption", ["source_pin", "release_status", "contract_final", "schema", "minimum",
    "fixed_rank", "diversity_rank", "atom_count", "locator_alignment", "native_identity", "projected_numeric_mask",
    "original_numeric_mask", "training_rank", "diagnostic_base", "diagnostic_child", "cross_source_order"])
def test_projection_and_evidence_disagreements_are_rejected(projector, corruption):
    raw = inputs(projector)
    item, args, projected = raw[1], raw[1].training_arguments, raw[1].projection
    ref = projected["source_entries"]["pm7"]["conformers"][0]
    gid = ref["conformer_id"]
    if corruption == "source_pin":
        raw[1] = replace(item, projection_source_sha256="0" * 64)
    elif corruption == "release_status":
        projected["status"] = "FROZEN"
    elif corruption == "contract_final":
        projected["contract_finalized"] = True
    elif corruption == "schema":
        projected["schema"] = "invented-release-schema"
    elif corruption == "minimum":
        projected["source_entries"]["pm7"]["minimum_energy_conformer_id"] = gid
    elif corruption == "fixed_rank":
        ref["fixed_order"] = 2
    elif corruption == "diversity_rank":
        ref["diversity_order"] = 999
    elif corruption == "atom_count":
        ref["native_atoms"] = True
    elif corruption == "locator_alignment":
        ref["geometry_locators"].append(["Sprime_UFF", gid])
    elif corruption == "native_identity":
        projected["native_conformer_identity"][gid]["native_record_id"] = "another record"
    elif corruption == "projected_numeric_mask":
        projected["source_entries"]["pm7"]["group_mask"][0][1] = 1
    elif corruption == "original_numeric_mask":
        args["group_mask"]["P"] = 1
    elif corruption == "training_rank":
        args["training_orders"][0]["training_rank"] = 5
    elif corruption == "diagnostic_base":
        args["diagnostic_targets"].append({"molecule_id": item.molecule_id, "geometry_source": "pm7", "geometry_id": gid})
    elif corruption == "diagnostic_child":
        next(r for r in args["training_geometries"] if r["view_id"] is not None)["parent_geometry_id"] = args["diagnostic_targets"][0]["geometry_id"]
    else:
        args["training_orders"][0]["geometry_id"] = projected["source_entries"]["uff_sprime"]["conformers"][0]["conformer_id"]
    with pytest.raises(ValueError):
        bridge(raw)


def test_source_specific_k_boundaries_are_checked_without_using_the_other_sources_count(projector):
    raw = inputs(projector)
    with pytest.raises(ValueError, match="Insufficient"):
        bridge(raw, selected_molecule_ids=["m0"], selection=ConformationSelection("first_k", 2))
    uff = bridge(raw, selected_molecule_ids=["m0"], geometry_source="Sprime_UFF", selection=ConformationSelection("first_k", 2))
    assert len({d.conformer_id for d in uff.make_sampler(seed=9, sample_budget=50)}) == 2
    with pytest.raises(ValueError):
        ConformationSelection("first_k", True)


@pytest.mark.parametrize("mapping", [{"m0": "PM7"}, {"m0": "PM7", "m1": "PM7", "m2": "UFF"},
                                    {"m0": "PM7", "m1": "PM7", "m2": "PM7", "extra": "PM7"}])
def test_mixed_requires_exactly_one_declared_model_source_per_selected_molecule(projector, mapping):
    with pytest.raises(ValueError, match="exactly one"):
        bridge(inputs(projector), geometry_source="mixed", mixed_sources=mapping)


@pytest.mark.parametrize("selection", [["m0", "m0"], ["unknown"], []])
def test_unknown_duplicate_or_empty_molecule_selection_is_rejected(projector, selection):
    with pytest.raises(ValueError):
        bridge(inputs(projector), selected_molecule_ids=selection)


def test_duplicate_molecule_input_is_not_counted_as_two_uniform_molecules(projector):
    raw = inputs(projector)
    with pytest.raises(ValueError, match="Duplicate molecule"):
        bridge([raw[0], deepcopy(raw[0])], selected_molecule_ids=["m0"])


@pytest.mark.parametrize("collision", ["training_id", "diagnostic_reflow"])
def test_global_identity_and_diagnostic_guards_reject_locally_valid_data_projections(projector, collision):
    raw = inputs(projector)
    first_id = raw[0].projection["source_entries"]["pm7"]["conformers"][0]["conformer_id"]
    args = raw[1].training_arguments
    if collision == "diagnostic_reflow":
        args["diagnostic_targets"][0]["geometry_id"] = first_id
    else:
        original = raw[1].projection["source_entries"]["uff_sprime"]["conformers"][0]["conformer_id"]
        for row in args["training_geometries"]:
            if row["geometry_id"] == original:
                row["geometry_id"] = first_id
            if row["parent_geometry_id"] == original:
                row["parent_geometry_id"] = first_id
        for row in args["training_orders"]:
            if row["geometry_id"] == original:
                row["geometry_id"] = first_id
        args["native_atom_counts"][first_id] = args["native_atom_counts"].pop(original)
    # DataB's pure function is per molecule. Both remain locally valid, while
    # the model index must additionally reject the global collision/holdout.
    raw[1] = replace(raw[1], projection=projector(raw[1].molecule_id, **args))
    with pytest.raises(ValueError, match="collision|diagnostic geometry"):
        bridge(raw)


@pytest.mark.parametrize("limit", ["max_molecules", "max_rows_per_molecule", "max_total_conformers", "max_total_geometry_rows", "max_total_diagnostic_rows"])
def test_candidate_metadata_memory_boundaries_reject_instead_of_truncating(projector, limit):
    with pytest.raises(ValueError, match="boundary|bounded"):
        bridge(inputs(projector), **{limit: 1})
