"""Synthetic contract tests; not the D-3 1,000-molecule overfit acceptance."""
from dataclasses import replace
import inspect
from itertools import islice
import random

import numpy as np
import pytest
import torch
from torch_geometric.data import Batch, Data

from phychem_mfm.model.v3_heads import V3HeadBank, V3PretrainingModel
from phychem_mfm.phase1.v3_contract import FieldSpec, FieldTarget, LabelRegistry, TrainNormalization
from phychem_mfm.phase1.v3_losses import compute_v3_loss
from phychem_mfm.phase1.v3_sampling import (ConformationSelection, ConformerRef, InMemorySamplingIndex,
                                          MoleculeEntry, UniformMoleculeSampler)
from phychem_mfm.phase1.v3_data import (DecodedSample, ExposureBatchSampler, ManifestSampleDataset,
                                       collate_v3_samples, make_v3_loader)


def registry(*fields):
    return LabelRegistry(tuple(fields), "synthetic-v1", "a" * 64)


def norm(width=1):
    return TrainNormalization((0.,) * width, (1.,) * width, "b" * 64, "synthetic-v1")


def target(values, mask=None):
    value = torch.tensor(values, dtype=torch.float32).reshape(-1, 1)
    return FieldTarget(value, torch.ones(len(value), dtype=torch.bool) if mask is None else torch.tensor(mask))


def sampling_index(counts=(1, 4, 9)):
    molecules = []
    for i, count in enumerate(counts):
        conformers = tuple(ConformerRef(f"m{i}-c{j}", j, j % 3 + 2,
                            (("PM7", f"pm7:{i}:{j}"), ("Sprime_UFF", f"uff:{i}:{j}")), count - j - 1)
                           for j in range(count))
        molecules.append(MoleculeEntry(f"m{i}", conformers, (("S", True), ("D", True), ("P", i != 1)),
                                       (("a", i != 2), ("b", True)),
                                       "PM7" if i % 2 == 0 else "Sprime_UFF", f"m{i}-c{count - 1}"))
    return InMemorySamplingIndex(tuple(molecules), "synthetic-v1")


def test_observed_field_mean_then_enabled_group_mean():
    reg = registry(FieldSpec("a", "P", "a", "graph"), FieldSpec("missing", "P", "a", "graph"),
                   FieldSpec("d", "D", "b", "graph"))
    a = torch.tensor([[2.], [1000.]], requires_grad=True)
    missing = torch.tensor([[7.], [9.]], requires_grad=True)
    d = torch.tensor([[1.]], requires_grad=True)
    result = compute_v3_loss({"a": a, "missing": missing, "d": d},
                             {"a": target([0., float("nan")], [True, False]),
                              "missing": target([float("nan"), float("nan")], [False, False]), "d": target([0.])},
                             reg, {name: norm() for name in ("a", "missing", "d")}, enabled_groups=("P", "D"))
    assert result.total.item() == pytest.approx(1.)  # P=1.5, D=.5; missing excluded from P fields.
    assert result.counts == {"a": 1, "missing": 0, "d": 1}
    assert result.observed_fields == {"D": 1, "P": 1}
    result.total.backward()
    assert missing.grad is None
    assert a.grad[1].item() == 0.
    assert torch.isfinite(a.grad).all()


def test_enabled_empty_group_stays_in_group_denominator_and_disabled_field_untouched():
    reg = registry(FieldSpec("p", "P", "a", "graph"), FieldSpec("s", "S", "a", "graph"))
    p = torch.tensor([[2.]], requires_grad=True)
    s = torch.tensor([[float("nan")]], requires_grad=True)
    result = compute_v3_loss({"p": p, "s": s}, {"p": target([0.])}, reg, {"p": norm()}, enabled_groups=("P", "D"))
    assert result.total.item() == pytest.approx(.75)
    result.total.backward()
    assert s.grad is None
    assert "s" not in result.counts


def test_masked_nan_is_allowed_but_observed_nan_or_illegal_class_is_rejected():
    reg = registry(FieldSpec("p", "P", "a", "graph"))
    with pytest.raises(ValueError, match="observed label"):
        compute_v3_loss({"p": torch.zeros(1, 1)}, {"p": target([float("nan")])}, reg,
                        {"p": norm()}, enabled_groups=("P",))
    categorical = registry(FieldSpec("c", "S", "a", "atom", kind="classification", classes=3))
    with pytest.raises(ValueError, match="observed label"):
        compute_v3_loss({"c": torch.zeros(1, 3)}, {"c": FieldTarget(torch.tensor([[3]]), torch.tensor([True]))},
                        categorical, {}, enabled_groups=("S",))


def test_train_normalization_and_vector_symmetry_contracts():
    with pytest.raises(ValueError, match="TRAIN"):
        TrainNormalization((0.,), (1.,), "a" * 64, "v1", fit_role="VAL")
    field = FieldSpec("v", "P", "a", "atom", representation="vector")
    with pytest.raises(ValueError, match="isotropic"):
        TrainNormalization((0., 0., 0.), (1., 2., 3.), "a" * 64, "v1").validate_for(field)
    reg = registry(FieldSpec("a", "P", "a", "graph"))
    normalizer = TrainNormalization((100.,), (2.,), "a" * 64, "v1")
    loss = compute_v3_loss({"a": torch.tensor([[104.]])}, {"a": target([100.])}, reg,
                           {"a": normalizer}, enabled_groups=("P",))
    assert loss.total.item() == pytest.approx(1.5)


def test_denoising_mse_has_a4_vector_normalization():
    field = FieldSpec("noise", "S", "a", "atom", kind="denoise_eps_mse", representation="vector")
    reg = registry(field)
    prediction = torch.tensor([[.1, .1, .1], [9., 9., 9.]])
    labels = FieldTarget(torch.tensor([[0., 0., 0.], [float("nan")] * 3]), torch.tensor([True, False]))
    loss = compute_v3_loss({"noise": prediction}, {"noise": labels}, reg, {}, enabled_groups=("S",))
    assert loss.total.item() == pytest.approx(1., rel=1e-6)
    assert loss.counts["noise"] == 1


def test_molecule_frequency_uniform_despite_unequal_conformer_counts():
    from scipy.stats import chisquare
    index = sampling_index()
    sampler = UniformMoleculeSampler(index, seed=20261025, sample_budget=30000)
    counts = np.zeros(3, dtype=np.int64)
    by_conformer = np.zeros(9, dtype=np.int64)
    for choice in sampler:
        counts[choice.molecule_index] += 1
        if choice.molecule_index == 2:
            by_conformer[int(choice.conformer_id.split("-c")[1])] += 1
    assert chisquare(counts).pvalue >= .01  # fixed seed, fixed alpha, no retry.
    assert chisquare(by_conformer).pvalue >= .01
    assert sampler.samples_consumed == 0


@pytest.mark.parametrize("mode,k,expected", [("all", None, {"m2-c0", "m2-c1", "m2-c2", "m2-c3", "m2-c4", "m2-c5", "m2-c6", "m2-c7", "m2-c8"}),
                                             ("first_k", 2, {"m2-c0", "m2-c1"}),
                                             ("minimum_energy", None, {"m2-c8"}),
                                             ("diversity_first_k", 2, {"m2-c8", "m2-c7"})])
def test_conformer_selection_uses_declared_orders(mode, k, expected):
    molecule = sampling_index().molecule_at(2)
    assert {c.conformer_id for c in ConformationSelection(mode, k).allowed(molecule)} == expected


def test_sampling_resume_drops_speculative_prefetch_and_preserves_global_rng():
    index = sampling_index()
    sampler = UniformMoleculeSampler(index, seed=123, sample_budget=50, geometry_source="mixed")
    torch.manual_seed(100); random.seed(100)
    torch_before, python_before = torch.get_rng_state(), random.getstate()
    iterator = iter(sampler)
    consumed = list(islice(iterator, 4))
    prefetched = list(islice(iterator, 7))
    assert sampler.samples_consumed == 0
    sampler.commit_batch(consumed)
    restored = UniformMoleculeSampler(index, seed=123, sample_budget=50, geometry_source="mixed")
    restored.load_state_dict(sampler.state_dict())
    assert list(islice(restored, 7)) == prefetched
    assert torch.equal(torch_before, torch.get_rng_state()) and python_before == random.getstate()
    for draw in consumed + prefetched:
        assert draw.geometry_source == index.molecule_at(draw.molecule_index).mixed_geometry_source
    with pytest.raises(ValueError, match="Committed"):
        sampler.commit_batch(consumed)
    with pytest.raises(ValueError, match="contract"):
        UniformMoleculeSampler(index, seed=124, sample_budget=50, geometry_source="mixed").load_state_dict(sampler.state_dict())


class SyntheticProvider:
    def read(self, choice):
        n = choice.native_atoms
        return DecodedSample(choice.molecule_id, choice.conformer_id, choice.geometry_source,
                             torch.full((n, 1), 5, dtype=torch.long),
                             torch.arange(n * 3, dtype=torch.float32).reshape(n, 3) / 10.,
                             torch.arange(n, dtype=torch.long),
                             {"p": target([1.]), "d": target(list(range(n))),
                              "w": FieldTarget(torch.tensor([[2.]]), torch.tensor([True]), torch.tensor([[0], [1]]))})

    def close(self):
        pass


class SyntheticFactory:
    read_only, node_local, data_version = True, True, "synthetic-v1"

    def __call__(self):
        return SyntheticProvider()


def test_provider_collation_preserves_ids_and_combines_all_mask_levels():
    index = sampling_index()
    sampler = UniformMoleculeSampler(index, seed=0, sample_budget=20)
    reg = registry(FieldSpec("p", "P", "a", "graph"), FieldSpec("d", "D", "a", "atom"),
                   FieldSpec("w", "P", "b", "pair"), FieldSpec("missing", "D", "b", "graph"))
    dataset = ManifestSampleDataset(index, SyntheticFactory())
    draws = list(islice(sampler, 12))
    result = collate_v3_samples([dataset[draw] for draw in draws], reg)
    assert result.targets["p"].valid.tolist() == [d.molecule_index == 0 for d in draws]
    assert result.targets["d"].valid.tolist() == [d.molecule_index != 2 for d in draws for _ in range(d.native_atoms)]
    assert not result.targets["missing"].valid.any()
    assert torch.isnan(result.targets["missing"].values).all()
    assert result.source_atom_ids.tolist() == [i for draw in draws for i in range(draw.native_atoms)]
    assert (result.encoder_batch.batch[result.pair_indices["w"][0]]
            == result.encoder_batch.batch[result.pair_indices["w"][1]]).all()
    with pytest.raises(ValueError, match="identity"):
        dataset[replace(draws[0], molecule_id="wrong")]
    dataset.close()


def test_atom_budget_and_sample_save_boundaries_keep_oversized_samples():
    index = sampling_index()
    sampler = UniformMoleculeSampler(index, seed=8, sample_budget=19)
    batches = list(ExposureBatchSampler(sampler, max_molecules=5, max_native_atoms=8,
                                        max_padded_cost=40, milestones=(3, 8, 15)))
    assert [draw.ordinal for batch in batches for draw in batch] == list(range(19))
    ends = {batch[-1].ordinal + 1 for batch in batches}
    assert {3, 8, 15} <= ends
    assert all(len(batch) <= 5 for batch in batches)


def head_fixture():
    reg = registry(FieldSpec("extensive", "P", "a", "graph", pooling="sum"),
                   FieldSpec("intensive", "D", "b", "graph"),
                   FieldSpec("atom", "P", "a", "atom"), FieldSpec("pair", "P", "a", "pair"),
                   FieldSpec("vector", "P", "a", "atom", representation="vector"),
                   FieldSpec("dipole", "P", "a", "graph", representation="vector"),
                   FieldSpec("magnitude", "P", "a", "graph", representation="magnitude"))
    torch.manual_seed(17)
    h0 = torch.randn(7, 12)
    pos = torch.tensor([[0., 0., 0.], [1., 0., 0.], [0., 1., 0.], [0., 0., 1.],
                        [2., 1., 0.], [2., 2., 0.], [2., 1., 1.]])
    batch = torch.tensor([0, 0, 0, 0, 1, 1, 1])
    pairs = {"pair": torch.tensor([[0, 1, 4], [1, 2, 5]])}
    return reg, h0, pos, batch, pairs


@pytest.mark.parametrize("form", ["H1", "H2", "H3"])
def test_all_head_levels_are_rotation_translation_equivariant(form):
    reg, h0, pos, batch, pairs = head_fixture()
    heads = V3HeadBank(reg, dim=12, forms=form, hidden_dim=16).eval()
    rotation, _ = torch.linalg.qr(torch.randn(3, 3))
    shift = torch.tensor([7., -4., 2.])
    original = heads(h0, batch, pos, enabled_groups=("P", "D"), pair_indices=pairs)
    moved = heads(h0, batch, pos @ rotation + shift, enabled_groups=("P", "D"), pair_indices=pairs)
    for field in reg.fields:
        expected = original[field.name] @ rotation if field.representation == "vector" else original[field.name]
        torch.testing.assert_close(moved[field.name], expected, atol=1e-5, rtol=0)
    assert (original["magnitude"] >= 0).all()
    flipped = heads(h0, batch, pos, enabled_groups=("P", "D"), pair_indices={"pair": pairs["pair"].flip(0)})
    torch.testing.assert_close(flipped["pair"], original["pair"], atol=0, rtol=0)


def test_disabled_head_parameters_have_no_gradient_or_loss():
    reg, h0, pos, batch, pairs = head_fixture()
    heads = V3HeadBank(reg, dim=12, forms="H2")
    outputs = heads(h0, batch, pos, enabled_groups=("P",), enabled_fields=("extensive",), pair_indices=pairs)
    assert tuple(outputs) == ("extensive",)
    outputs["extensive"].square().mean().backward()
    assert all(parameter.grad is None for name, head in heads.field_heads.items()
               if name != heads.keys["extensive"] for parameter in head.parameters())
    assert all(parameter.grad is None for parameter in heads.group_projectors["D"].parameters())


def test_head_registry_is_bound_in_state_dict_and_h0_wrapper_keeps_signatures():
    reg = registry(FieldSpec("p", "P", "a", "graph"))
    bank = V3HeadBank(reg)
    other = V3HeadBank(replace(reg, version="another-version"))
    with pytest.raises(ValueError, match="registry"):
        other.load_state_dict(bank.state_dict())
    from phychem_mfm.factory import build_model
    encoder = build_model({"architecture": {"preset": "shared_light"},
                           "backbone": {"dim": 512, "layers": 1, "heads": 8, "ff_mult": 2},
                           "head": {"profile": "phase1", "geometry_head": "equivariant_noise"}}).eval()
    model = V3PretrainingModel(encoder, bank)
    batch = Batch.from_data_list([Data(x=torch.tensor([[5], [0]]), pos=torch.randn(2, 3))])
    with torch.no_grad():
        assert torch.equal(model.encode_atoms(batch), encoder.encode_atoms(batch))
        assert torch.equal(model.encode_graph(batch), encoder.encode_graph(batch))
        assert model.encode_atoms(batch).shape == (2, 512)
        assert model.encode_graph(batch).shape == (1, 512)
    assert tuple(inspect.signature(model.encode_atoms).parameters) == ("batch",)
    assert tuple(inspect.signature(model.encode_graph).parameters) == ("batch", "pooling")


def test_node_local_spawn_prefetch_does_not_commit_unconsumed_draws():
    index = sampling_index((2, 3))
    sampler = UniformMoleculeSampler(index, seed=81, sample_budget=18)
    reg = registry(FieldSpec("p", "P", "a", "graph"), FieldSpec("d", "D", "a", "atom"),
                   FieldSpec("w", "P", "b", "pair"))
    dataset = ManifestSampleDataset(index, SyntheticFactory())
    iterator = iter(make_v3_loader(dataset, ExposureBatchSampler(sampler, max_molecules=3), reg,
                                  num_workers=2, prefetch_factor=2, worker_timeout_seconds=60., pin_memory=False))
    try:
        first = next(iterator)
        sampler.commit_batch(first.choices)
        assert sampler.samples_consumed == 3
        second = next(iterator)
        saved = sampler.state_dict()
    finally:
        from phychem_mfm.phase1.full_corpus_loader import close_prefetch_iterator
        close_prefetch_iterator(iterator)
        dataset.close()
    resumed = UniformMoleculeSampler(index, seed=81, sample_budget=18)
    resumed.load_state_dict(saved)
    assert list(islice(resumed, 3)) == list(second.choices)
