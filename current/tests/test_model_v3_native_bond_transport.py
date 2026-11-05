"""Existing S bond facts survive the optional decoded-loader transport.

Synthetic native model facts only: no D-1 wire/codebook or real-data acceptance.
"""
from dataclasses import dataclass, replace
import json
from multiprocessing.util import Finalize
import os
from pathlib import Path

import pytest
import torch
from torch_geometric.data import Batch, Data

from phychem_mfm.data.descriptor_schema import (BOND_FAIL_REASON_FIELD, BOND_INDEX_FIELD,
                                               BOND_ORDER_FIELD, BOND_STATUS_FIELD)
from phychem_mfm.factory import build_model
from phychem_mfm.model.v3_heads import V3HeadBank
from phychem_mfm.model.v3_multiview import V3MultiViewModel
from phychem_mfm.phase1.v3_contract import FieldSpec, FieldTarget, LabelRegistry, TrainNormalization
from phychem_mfm.phase1.v3_data import (DecodedSample, ExposureBatchSampler, ManifestSampleDataset,
                                       NativeBondTransport, collate_v3_samples, make_v3_loader)
from phychem_mfm.phase1.v3_sampling import (ConformerRef, InMemorySamplingIndex, MoleculeEntry,
                                           SampleChoice, UniformMoleculeSampler)
from phychem_mfm.phase1.v3_structural import StructuralFieldBinding, build_structural_views
from phychem_mfm.training.losses import LossWeights

VERSION = "synthetic-native-bond-v1"


def registry():
    return LabelRegistry((
        FieldSpec("s_element", "S", "structure", "atom", kind="classification", classes=119),
        FieldSpec("s_noise", "S", "structure", "atom", kind="denoise_eps_mse", representation="vector"),
        FieldSpec("s_bond", "S", "structure", "pair", kind="classification", classes=5),
        FieldSpec("p", "P", "physics", "graph"),
        FieldSpec("d", "D", "descriptor", "atom")), VERSION, "a" * 64)


def index():
    entries = tuple(MoleculeEntry(f"m{i}", (ConformerRef(f"c{i}", 0, n, (("PM7", f"native:{i}"),)),),
        (("S", True), ("D", True), ("P", True)),
        (("structure", True), ("physics", True), ("descriptor", True)))
        for i, n in enumerate((6, 8, 4, 3)))
    return InMemorySamplingIndex(entries, VERSION)


def choice(molecule_index, ordinal=None):
    manifest = index()
    entry = manifest.molecule_at(molecule_index)
    ref = entry.conformers[0]
    return SampleChoice(molecule_index if ordinal is None else ordinal, molecule_index,
        entry.molecule_id, ref.conformer_id, "PM7", ref.locator("PM7"), ref.native_atoms,
        entry.group_mask, entry.family_mask, manifest.content_sha256, "c" * 64)


def native_bonds(n, status="oK"):
    if n >= 6:
        # Deliberately unsorted/repeated edges and unknown/zero/negative original
        # order values. Transport must not sort, deduplicate or remap them.
        pairs = torch.tensor([[2, 0, 1, 3, 0, 4, 1], [3, 1, 2, 4, 2, 5, 2]])
        orders = torch.tensor([5, 1, 3, 0, 8, -2, 2])
    else:
        pairs = torch.stack((torch.arange(n - 1), torch.arange(1, n)))
        orders = torch.arange(n - 1) % 5 + 1
    return NativeBondTransport(pairs.long(), orders.long(), status, "literal source reason")


def sample(draw, *, bonds=True):
    n = draw.native_atoms
    generator = torch.Generator().manual_seed(713 + draw.molecule_index)
    return DecodedSample(draw.molecule_id, draw.conformer_id, draw.geometry_source,
        (torch.arange(n) % 3 + 5).long()[:, None], torch.randn(n, 3, generator=generator) * .3,
        torch.arange(n, dtype=torch.long) * 7 + 11,
        {"p": FieldTarget(torch.tensor([[float(draw.molecule_index + 1)]]), torch.ones(1, dtype=torch.bool)),
         "d": FieldTarget(torch.arange(n, dtype=torch.float32)[:, None] / n, torch.ones(n, dtype=torch.bool))},
        native_bonds(n) if bonds else None)


def reference_batch(samples):
    """Direct pre-loader native Data, retaining the existing head's defaults."""
    include = any(row.native_bonds is not None for row in samples)
    graphs = []
    for row in samples:
        graph = Data(x=row.x, pos=row.pos)
        if include:
            bond = row.native_bonds
            graph.rdkit_bond_index = bond.pair_index if bond is not None else torch.empty((2, 0), dtype=torch.long)
            graph.rdkit_bond_order = bond.order if bond is not None else torch.empty(0, dtype=torch.long)
            graph.rdkit_bond_status = bond.status if bond is not None else ""
            graph.rdkit_bond_fail_reason = bond.fail_reason if bond is not None else ""
        graphs.append(graph)
    return Batch.from_data_list(graphs)


def assert_native_batch_equal(actual, expected):
    assert set(actual.keys()) == set(expected.keys())
    for name in expected.keys():
        a, b = actual[name], expected[name]
        if isinstance(a, torch.Tensor):
            assert torch.equal(a, b), name
        else:
            assert a == b, name


def model():
    torch.manual_seed(2071)
    encoder = build_model({"architecture": {"preset": "shared_light"},
        "backbone": {"dim": 512, "layers": 1, "heads": 8, "ff_mult": 1, "n_atom_types": 119, "dropout": 0.},
        "head": {"profile": "phase1", "geometry_head": "equivariant_noise",
                 "geometry_hidden_dim": 32, "geometry_message_layers": 0, "geometry_pair_chunk_size": 8192}})
    reg = registry()
    heads = V3HeadBank(replace(reg, fields=tuple(f for f in reg.fields if f.group != "S")), forms="H2")
    return V3MultiViewModel(encoder, heads, reg, StructuralFieldBinding("s_element", "s_noise", "s_bond")).eval()


def losses(network, batch, targets, ordinals, *, groups=("S", "D", "P")):
    views = build_structural_views(batch, ordinals=ordinals, include_structural="S" in groups)
    prediction = network.forward_pretrain(views, enabled_groups=groups)
    normalizations = {name: TrainNormalization((0.,), (1.,), "b" * 64, VERSION) for name in ("p", "d")}
    result = network.compute_loss(prediction, views, {k: targets[k] for k in ("p", "d")}, normalizations,
                                  enabled_groups=groups, weights=LossWeights())
    return views, prediction, result


@pytest.fixture
def single_intraop_thread():
    # Original-source repeated backward itself was not bitwise at 8 threads
    # (4520338). Keep torch.equal and restore the caller's thread environment.
    previous = torch.get_num_threads()
    torch.set_num_threads(1)
    try:
        yield
    finally:
        torch.set_num_threads(previous)


def test_two_molecule_offsets_native_attributes_and_raw_order_values_are_exact():
    draws = (choice(0), choice(1))
    samples = tuple(sample(draw) for draw in draws)
    original = tuple((row.native_bonds.pair_index.clone(), row.native_bonds.order.clone()) for row in samples)
    batch = collate_v3_samples(tuple(zip(draws, samples)), registry())
    assert_native_batch_equal(batch.encoder_batch, reference_batch(samples))
    assert batch.encoder_batch.rdkit_bond_index[:, 7:].tolist() == (samples[1].native_bonds.pair_index + 6).tolist()
    assert batch.encoder_batch.rdkit_bond_order.tolist() == [5, 1, 3, 0, 8, -2, 2] * 2
    assert batch.encoder_batch.rdkit_bond_status == ["oK", "oK"]
    for restored, row, (pairs, orders) in zip(batch.encoder_batch.to_data_list(), samples, original):
        assert torch.equal(restored.rdkit_bond_index, pairs)
        assert torch.equal(restored.rdkit_bond_order, orders)
        assert restored.rdkit_bond_status == row.native_bonds.status
        assert restored.rdkit_bond_fail_reason == row.native_bonds.fail_reason
        assert torch.equal(row.native_bonds.pair_index, pairs) and torch.equal(row.native_bonds.order, orders)
    assert batch.source_atom_ids.tolist() == samples[0].source_atom_ids.tolist() + samples[1].source_atom_ids.tolist()


def test_all_missing_transport_keeps_old_graph_keys_and_true_default_status():
    draws = (choice(0), choice(1))
    rows = tuple(sample(draw, bonds=False) for draw in draws)
    batch = collate_v3_samples(tuple(zip(draws, rows)), registry())
    assert_native_batch_equal(batch.encoder_batch, Batch.from_data_list([Data(x=r.x, pos=r.pos) for r in rows]))
    assert not hasattr(batch.encoder_batch, BOND_INDEX_FIELD) and not hasattr(batch.encoder_batch, BOND_STATUS_FIELD)
    assert model().encoder._graph_string_attr(batch.encoder_batch, BOND_STATUS_FIELD, 2) == ["", ""]


def test_mixed_missing_failed_and_zero_bond_records_keep_source_facts():
    draws = tuple(choice(i) for i in range(4))
    rows = [sample(draw) for draw in draws]
    rows[1] = replace(rows[1], native_bonds=None)
    rows[2] = replace(rows[2], native_bonds=replace(rows[2].native_bonds, status="FAILED: native topology"))
    rows[3] = replace(rows[3], native_bonds=NativeBondTransport(torch.empty((2, 0), dtype=torch.long),
                                                             torch.empty(0, dtype=torch.long), "ok"))
    batch = collate_v3_samples(tuple(zip(draws, rows)), registry())
    assert_native_batch_equal(batch.encoder_batch, reference_batch(rows))
    assert batch.encoder_batch.rdkit_bond_status == ["oK", "", "FAILED: native topology", "ok"]
    assert batch.encoder_batch.to_data_list()[1].rdkit_bond_index.shape == (2, 0)
    network = model()
    _, _, result = losses(network, batch.encoder_batch, batch.targets, tuple(d.ordinal for d in draws))
    assert result.counts["s_bond"] == 4  # Only original head's valid positive orders from the first record.
    assert result.fields["s_bond"].item() > 0


def test_direct_and_loader_bridge_raw_counts_and_all_parameter_gradients_are_bitwise(single_intraop_thread, tmp_path):
    draws = (choice(0, 31), choice(1, 32))
    rows = tuple(sample(draw) for draw in draws)
    batch = collate_v3_samples(tuple(zip(draws, rows)), registry())
    direct = reference_batch(rows)
    network = model()
    ordinals = tuple(draw.ordinal for draw in draws)
    direct_views, direct_prediction, expected = losses(network, direct, batch.targets, ordinals)
    loaded_views, loaded_prediction, actual = losses(network, batch.encoder_batch, batch.targets, ordinals)
    assert_native_batch_equal(loaded_views.batch, direct_views.batch)
    assert torch.equal(loaded_prediction.clean_h0, direct_prediction.clean_h0)
    for name in ("p", "d"):
        assert torch.equal(loaded_prediction.pd_predictions[name], direct_prediction.pd_predictions[name])
    assert actual.counts == expected.counts and actual.counts["s_bond"] == 8
    assert actual.fields["s_bond"].item() > 0 and actual.observed_fields == expected.observed_fields
    parameters = tuple(network.named_parameters())
    assert parameters
    gradient_structure = {}
    for field_name in ("s_element", "s_noise", "s_bond", "p", "d", "total"):
        if field_name == "total":
            a_loss, b_loss = actual.total, expected.total
        else:
            a_loss, b_loss = actual.fields[field_name], expected.fields[field_name]
            assert actual.counts[field_name] > 0
        assert torch.equal(a_loss, b_loss)
        a = torch.autograd.grad(a_loss, tuple(p for _, p in parameters), retain_graph=True, allow_unused=True)
        b = torch.autograd.grad(b_loss, tuple(p for _, p in parameters), retain_graph=True, allow_unused=True)
        gradient_structure[field_name] = {parameter_name: {
            "loader_none": x is None, "direct_none": y is None,
            "shape": None if x is None else list(x.shape),
            "torch_equal": None if x is None or y is None else bool(torch.equal(x, y))}
            for (parameter_name, _), x, y in zip(parameters, a, b)}
        # Retain all parameter None/non-None structures in the owned pytest
        # artifact directory before checking; no gradient tensors are written.
        (tmp_path / "native_bond_gradient_structure.json").write_text(json.dumps(gradient_structure, indent=2) + "\n")
        assert any(value is not None and bool(value.ne(0).any()) for value in a)
        for (parameter_name, _), x, y in zip(parameters, a, b):
            assert (x is None) == (y is None), (field_name, parameter_name, "gradient presence")
            if x is not None:
                assert torch.equal(x, y), (field_name, parameter_name, "gradient value")
    assert torch.equal(actual.total, expected.total)


@pytest.mark.parametrize("state", ["missing", "failed", "zero_pairs"])
def test_no_eligible_native_bonds_never_create_supervision_or_bond_gradients(state, single_intraop_thread):
    draw = choice(0)
    row = sample(draw)
    bonds = {"missing": None, "failed": replace(row.native_bonds, status="FAILED"),
             "zero_pairs": NativeBondTransport(torch.empty((2, 0), dtype=torch.long),
                                                torch.empty(0, dtype=torch.long), "ok")}[state]
    row = replace(row, native_bonds=bonds)
    batch = collate_v3_samples(((draw, row),), registry())
    network = model()
    _, _, result = losses(network, batch.encoder_batch, batch.targets, (draw.ordinal,))
    assert result.counts["s_bond"] == 0 and result.fields["s_bond"].item() == 0
    assert result.counts["s_element"] > 0 and result.counts["s_noise"] > 0
    result.total.backward()
    assert all(parameter.grad is None for parameter in network.encoder.bond_head.parameters())


def test_pd_only_outputs_and_s_head_gradient_absence_are_unchanged_by_transport(single_intraop_thread):
    draws = (choice(0), choice(1))
    present = tuple(sample(draw) for draw in draws)
    absent = tuple(replace(row, native_bonds=None) for row in present)
    with_bonds = collate_v3_samples(tuple(zip(draws, present)), registry())
    without = collate_v3_samples(tuple(zip(draws, absent)), registry())
    network = model()
    _, prediction, result = losses(network, with_bonds.encoder_batch, with_bonds.targets, (0, 1), groups=("D", "P"))
    _, old_prediction, old_result = losses(network, without.encoder_batch, without.targets, (0, 1), groups=("D", "P"))
    assert torch.equal(prediction.clean_h0, old_prediction.clean_h0) and torch.equal(result.total, old_result.total)
    for name in ("p", "d"):
        assert torch.equal(prediction.pd_predictions[name], old_prediction.pd_predictions[name])
    result.total.backward()
    assert all(p.grad is None for head in (network.encoder.element_head, network.encoder.bond_head,
                                           network.encoder.geometry_head) for p in head.parameters())


@pytest.mark.parametrize("malformed", ["index_dtype", "index_shape", "order_dtype", "order_count", "status", "reason"])
def test_typed_transport_rejects_dtype_shape_and_nonliteral_status(malformed):
    values = {"pair_index": torch.tensor([[0], [1]]), "order": torch.tensor([1]), "status": "ok", "fail_reason": ""}
    values.update({"index_dtype": {"pair_index": values["pair_index"].int()},
                   "index_shape": {"pair_index": values["pair_index"].T},
                   "order_dtype": {"order": torch.tensor([1.])},
                   "order_count": {"order": torch.tensor([1, 2])},
                   "status": {"status": None}, "reason": {"fail_reason": 123}}[malformed])
    with pytest.raises(ValueError, match="Native bond"):
        NativeBondTransport(**values)


@pytest.mark.parametrize("bad_index", [-1, 6])
def test_mutated_out_of_molecule_indices_are_rejected_at_collation(bad_index):
    draw = choice(0)
    row = sample(draw)
    row.native_bonds.pair_index[0, 0] = bad_index
    with pytest.raises(ValueError, match="atom rows"):
        collate_v3_samples(((draw, row),), registry())


def test_untyped_transport_is_not_silently_coerced():
    draw = choice(0)
    row = replace(sample(draw), native_bonds={"pair_index": [[0], [1]], "order": [1], "status": "ok"})
    with pytest.raises(ValueError, match="Typed native bond"):
        collate_v3_samples(((draw, row),), registry())


def test_cpu_transfer_keeps_bond_facts_and_owns_graph_store():
    draws = (choice(0), choice(1))
    original = collate_v3_samples(tuple((draw, sample(draw)) for draw in draws), registry())
    moved = original.to("cpu", non_blocking=True)
    assert moved.encoder_batch is not original.encoder_batch
    assert_native_batch_equal(moved.encoder_batch, original.encoder_batch)
    moved.encoder_batch.rdkit_bond_status = ["changed", "changed"]
    moved.encoder_batch.rdkit_bond_index = torch.empty((2, 0), dtype=torch.long)
    assert original.encoder_batch.rdkit_bond_status == ["oK", "oK"]
    assert original.encoder_batch.rdkit_bond_index.size(1) == 14


@pytest.mark.skipif(not torch.cuda.is_available(), reason="Actual bond pin/transfer requires visible CUDA")
def test_pinned_bond_arrays_and_nonblocking_cuda_transfer():
    draw = choice(0)
    original = collate_v3_samples(((draw, sample(draw)),), registry())
    pinned = original.pin_memory()
    assert pinned.encoder_batch.rdkit_bond_index.is_pinned() and pinned.encoder_batch.rdkit_bond_order.is_pinned()
    moved = pinned.to("cuda", non_blocking=True)
    torch.cuda.synchronize()
    for name in (BOND_INDEX_FIELD, BOND_ORDER_FIELD):
        assert moved.encoder_batch[name].device.type == "cuda"
        assert torch.equal(moved.encoder_batch[name].cpu(), original.encoder_batch[name])
        assert pinned.encoder_batch[name].device.type == "cpu"
    assert moved.encoder_batch.rdkit_bond_status == original.encoder_batch.rdkit_bond_status


class BondProvider:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.pid = os.getpid()
        self.stream = (self.directory / "source.json").open("rb")
        self.closed = False
        self.event("open")
        # The injected provider owns this real read-only fixture handle and its
        # worker cleanup; it is never serialized from the parent process.
        self.finalizer = Finalize(self, self.close, exitpriority=10)

    def event(self, name):
        with (self.directory / f"worker-{self.pid}.jsonl").open("a") as stream:
            stream.write(json.dumps({"event": name, "pid": os.getpid(), "owner": self.pid}) + "\n")

    def read(self, draw):
        assert os.getpid() == self.pid and not self.closed and not self.stream.closed
        self.stream.seek(0)
        assert json.load(self.stream)["kind"] == "synthetic-native-bond-transport"
        self.event("read")
        return sample(draw)

    def close(self):
        if not self.closed:
            self.stream.close()
            self.closed = True
            self.event("close")


@dataclass(frozen=True)
class BondFactory:
    directory: str
    read_only = node_local = True
    data_version = VERSION

    def __call__(self):
        return BondProvider(self.directory)


def fixture_directory(tmp_path):
    (tmp_path / "source.json").write_text(json.dumps({"kind": "synthetic-native-bond-transport"}))
    return str(tmp_path)


def test_dataset_bound_read_and_explicit_close_preserve_native_transport(tmp_path):
    directory = fixture_directory(tmp_path)
    dataset = ManifestSampleDataset(index(), BondFactory(directory))
    draw = choice(0)
    try:
        returned_draw, row = dataset[draw]
        assert returned_draw == draw and row.native_bonds.status == "oK"
        assert row.native_bonds.order.tolist() == [5, 1, 3, 0, 8, -2, 2]
        owner = dataset._provider
        with pytest.raises(ValueError, match="identity"):
            dataset[replace(draw, molecule_id="another molecule")]
    finally:
        dataset.close()
    assert owner.closed and owner.stream.closed and dataset._provider is None
    events = [json.loads(line)["event"] for line in (tmp_path / f"worker-{os.getpid()}.jsonl").read_text().splitlines()]
    assert events == ["open", "read", "close"]


def test_spawn_worker_native_transport_matches_direct_and_owned_handles_close(tmp_path):
    directory = fixture_directory(tmp_path)
    manifest = index()
    sampler = UniformMoleculeSampler(manifest, seed=21, sample_budget=12)
    dataset = ManifestSampleDataset(manifest, BondFactory(directory))
    loader = make_v3_loader(dataset, ExposureBatchSampler(sampler, max_molecules=2), registry(),
                            num_workers=2, prefetch_factor=1, worker_timeout_seconds=60., pin_memory=False)
    iterator = iter(loader)
    workers = tuple(iterator._workers)
    try:
        batches = list(iterator)
        assert [d.ordinal for b in batches for d in b.choices] == list(range(12))
        for batch in batches:
            assert_native_batch_equal(batch.encoder_batch, reference_batch([sample(draw) for draw in batch.choices]))
        assert sampler.samples_consumed == 0 and dataset._provider is None
    finally:
        iterator._shutdown_workers()
        for worker in workers:
            worker.join(timeout=10.)
        dataset.close()
    assert len(workers) == 2 and all(not worker.is_alive() for worker in workers)
    logs = list(tmp_path.glob("worker-*.jsonl"))
    assert {int(p.stem.split("-")[1]) for p in logs} == {worker.pid for worker in workers}
    for path in logs:
        events = [json.loads(line) for line in path.read_text().splitlines()]
        assert events[0]["event"] == "open" and events[-1]["event"] == "close"
        assert sum(row["event"] == "open" for row in events) == sum(row["event"] == "close" for row in events) == 1
        assert any(row["event"] == "read" for row in events)
        assert all(row["pid"] == row["owner"] and row["pid"] != os.getpid() for row in events)
