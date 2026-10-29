"""Synthetic typed-domain routing through banks and clean S/PD wrappers."""
from copy import deepcopy
from dataclasses import replace
import json
from types import SimpleNamespace

import pytest
import torch
from torch import nn
from torch_geometric.data import Batch, Data

from model_v3_typed_fixture import FRAME, REF, ordered_target
from phychem_mfm.model.v3_heads import V3HeadBank, V3PretrainingModel
from phychem_mfm.model.v3_multiview import V3MultiViewModel
from phychem_mfm.phase1.v3_architecture_views import V3TwoViewModel
from phychem_mfm.phase1.v3_contract import FieldSpec, LabelRegistry, TrainNormalization
from phychem_mfm.phase1.v3_label_domains import Tensor6Inputs, tensor6_from_f64
from phychem_mfm.phase1.v3_losses import compute_v3_loss
from phychem_mfm.phase1.v3_structural import StructuralFieldBinding, combine_structural_loss


QFRAME = {**FRAME, "target_id": "fixture-r674"}
CONTEXT = {"geometry_ids": ("g0",), "geometry_bindings": (REF,), "native_atom_counts": (2,)}


def setup_bank(dim=4):
    fields = (FieldSpec("q", "P", "r674", "graph", representation="symmetric_tensor6"),
              FieldSpec("r", "D", "r73", "ordered_entry"), FieldSpec("p", "P", "scalar", "graph"))
    registry = LabelRegistry(fields, "synthetic-typed-heads", "a" * 64)
    ordered = ordered_target()
    configs = {"q": {"origin_policy": "explicit_comoving", "frame_binding": QFRAME},
               "r": {"codebook": ordered.inputs.codebook, "frame_binding": FRAME, "channel_dim": 2}}
    bank = V3HeadBank(registry, dim=dim, hidden_dim=8, domain_head_configs=configs)
    inputs = {"q": Tensor6Inputs(torch.tensor([[9., -3., 2.]]), ("g0",), (REF,), QFRAME),
              "r": ordered.inputs}
    return bank, registry, configs, inputs


def bank_forward(bank, inputs, **kwargs):
    return bank(torch.ones((2, bank.dim)), torch.zeros(2, dtype=torch.long), torch.tensor([[1., 2., 3.], [4., 5., 6.]]),
        enabled_groups=("D", "P"), domain_inputs=inputs, geometry_context=CONTEXT, **kwargs)


def test_bank_uses_dedicated_heads_and_requires_explicit_source_bindings():
    bank, registry, configs, inputs = setup_bank()
    outputs = bank_forward(bank, inputs)
    assert {key: tuple(value.shape) for key, value in outputs.items()} == {"q": (1, 6), "r": (4, 1), "p": (1, 1)}
    assert bank.field_heads[bank.keys["q"]].__class__.__name__ == "SymmetricTensor6Head"
    assert bank.field_heads[bank.keys["r"]].__class__.__name__ == "OrderedEntryHead"
    assert bank.get_extra_state()["domain_head_bindings"]["r"]["schema"] == "model_v3_source_frame_ordered_head_v2"
    with pytest.raises(ValueError, match="Every typed domain"):
        V3HeadBank(registry, dim=4)
    with pytest.raises(ValueError, match="domain inputs"):
        bank_forward(bank, {"q": inputs["q"]})
    with pytest.raises(ValueError, match="comoving"):
        V3HeadBank(registry, dim=4, domain_head_configs={**configs, "q": {**configs["q"], "origin_policy": "centroid"}})
    with pytest.raises(ValueError, match="numeric source-frame"):
        bank_forward(bank, {**inputs, "r": replace(inputs["r"], frame_origin=None, frame_basis=None)})


def test_tensor_requires_declared_origin_frame_and_actual_geometry_identity():
    bank, registry, configs, inputs = setup_bank()
    with pytest.raises(ValueError, match="tensor origin/frame"):
        bank_forward(bank, {**inputs, "q": replace(inputs["q"], geometry_ids=("wrong-g",))})
    with pytest.raises(ValueError, match="tensor origin/frame"):
        bank_forward(bank, {**inputs, "q": replace(inputs["q"], frame_binding={**QFRAME, "sign": "wrong-sign"})})
    with pytest.raises(ValueError, match="actual-geometry"):
        bank(torch.ones(2, 4), torch.zeros(2, dtype=torch.long), torch.zeros(2, 3), enabled_groups=("P",),
             enabled_fields=("q",), domain_inputs={"q": inputs["q"]})


@pytest.mark.parametrize("name", ["q", "r"])
def test_typed_domains_reject_ordinary_pair_indices_and_prediction_offsets(name):
    bank, registry, configs, inputs = setup_bank()
    with pytest.raises(ValueError, match="ordinary pair"):
        bank_forward(bank, inputs, pair_indices={name: torch.tensor([[0], [1]])})
    with pytest.raises(ValueError, match="prediction offsets"):
        bank_forward(bank, inputs, prediction_offsets={name: torch.zeros(1, 1)})


def test_disabled_typed_heads_do_not_execute_or_gain_gradients_or_require_geometry():
    bank, registry, configs, inputs = setup_bank()
    output = bank(torch.ones(2, 4), torch.zeros(2, dtype=torch.long), torch.zeros(2, 3),
                  enabled_groups=("D", "P"), enabled_fields=("p",))
    output["p"].sum().backward()
    for name in ("q", "r"):
        assert all(parameter.grad is None for parameter in bank.field_heads[bank.keys[name]].parameters())
    assert bank.field_heads[bank.keys["p"]].weight.grad is not None


def test_bank_default_checkpoint_state_preserves_legacy_shape_and_pooling_override():
    field = FieldSpec("p", "P", "scalar", "graph")
    reg = LabelRegistry((field,), "synthetic-legacy", "a" * 64)
    bank = V3HeadBank(reg, dim=4, hidden_dim=8)
    assert bank.get_extra_state() == {"schema": "model_v3_head_bank_v1", "registry_sha256": reg.content_sha256,
        "dim": 4, "hidden_dim": 8, "forms": {"p": "H1"}}
    bank.load_state_dict(deepcopy(bank.state_dict()))
    pooled = V3HeadBank(reg, dim=4, hidden_dim=8, pooling_overrides={"p": "learned"})
    assert pooled.get_extra_state()["pooling_overrides"] == {"p": "learned"}
    assert pooled.keys["p"] in pooled.pooling_mixers


class TinyRoutingEncoder(nn.Module):
    """Only a routing fixture; no scientific encoder/equivariance claim."""
    latent_dim, n_atom_types = 512, 119
    geometry_head_mode, head_profile = "equivariant_noise", "phase1"

    def __init__(self):
        super().__init__()
        self.embedding = nn.Embedding(119, 512)
        self.forward_calls = 0

    def encode_atoms(self, batch):
        return self.embedding(batch.x[:, 0])

    def forward_pretrain(self, batch, objectives):
        self.forward_calls += 1
        return SimpleNamespace(atom_repr=self.encode_atoms(batch))


def routing_views(two_views):
    pos = torch.tensor([[1., 2., 3.], [4., 5., 6.]])
    modes = (0, 3) if two_views else (0, 1, 2)
    records = [Data(x=torch.tensor([[0], [1]]), pos=pos + 10 * mode,
                    sample_type_id=torch.tensor([mode])) for mode in modes]
    return SimpleNamespace(batch=Batch.from_data_list(records), clean_atom_rows=torch.tensor([0, 1]),
        clean_graph_rows=torch.tensor([0]), includes_structural=True, ordinals=(4,))


@pytest.mark.parametrize("two_views", [False, True])
def test_both_wrappers_route_original_clean_h0_positions_and_explicit_inputs_from_one_forward(two_views):
    bank, pd_registry, configs, inputs = setup_bank(dim=512)
    sfields = (FieldSpec("element", "S", "s", "atom", kind="classification", classes=119),
        FieldSpec("noise", "S", "s", "atom", kind="denoise_eps_mse", representation="vector"),
        FieldSpec("bond", "S", "s", "pair", kind="classification", classes=5))
    registry = replace(pd_registry, fields=sfields + pd_registry.fields)
    encoder = TinyRoutingEncoder()
    model_type = V3TwoViewModel if two_views else V3MultiViewModel
    model = model_type(encoder, bank, registry, StructuralFieldBinding("element", "noise", "bond"))
    views = routing_views(two_views)
    captured = []
    handle = bank.register_forward_pre_hook(lambda module, args: captured.append(args))
    try:
        output = model.forward_pretrain(views, enabled_groups=("S", "D", "P"),
            domain_inputs=inputs, geometry_context=CONTEXT)
    finally:
        handle.remove()
    assert encoder.forward_calls == 1 and len(captured) == 1
    torch.testing.assert_close(captured[0][0], output.clean_h0)
    assert torch.equal(captured[0][1], torch.zeros(2, dtype=torch.long))
    assert torch.equal(captured[0][2], views.batch.pos[:2])
    assert output.pd_predictions["q"].shape == (1, 6) and output.pd_predictions["r"].shape == (4, 1)
    with pytest.raises(ValueError, match="atom membership"):
        model.forward_pretrain(views, enabled_groups=("S", "D", "P"), domain_inputs=inputs,
            geometry_context={**CONTEXT, "native_atom_counts": (3,)})


def test_pretraining_wrapper_also_routes_new_geometry_inputs_without_changing_h0_api():
    bank, registry, configs, inputs = setup_bank(dim=512)
    encoder = TinyRoutingEncoder()
    model = V3PretrainingModel(encoder, bank)
    record = Batch.from_data_list([Data(x=torch.tensor([[0], [1]]), pos=torch.zeros(2, 3))])
    before = model.encode_atoms(record)
    output = model.forward_pretrain(record, enabled_groups=("D", "P"), domain_inputs=inputs, geometry_context=CONTEXT)
    torch.testing.assert_close(before, model.encode_atoms(record))
    assert output["q"].shape == (1, 6) and output["r"].shape == (4, 1)


def test_structural_combination_retains_original_component_audit_counts():
    bank, registry, configs, inputs = setup_bank()
    outputs = bank_forward(bank, inputs, enabled_fields=("q", "r"))
    q = tensor6_from_f64(values=torch.zeros((1, 6), dtype=torch.float64), component_valid=torch.ones((1, 6), dtype=torch.bool),
        geometry_ids=("g0",), component_geometry_ids=(("g0",) * 6,), reasons=({},), source_ref=REF)
    norms = {name: TrainNormalization((0.,), (1.,), "b" * 64, "synthetic") for name in ("q", "r")}
    pd = compute_v3_loss(outputs, {"q": q, "r": ordered_target()}, registry, norms,
        enabled_groups=("D", "P"), enabled_fields=("q", "r"))
    combined = combine_structural_loss(pd, {"s": torch.tensor(2.)}, {"s": 1}, enabled_groups=("S", "D", "P"))
    assert combined.audit_counts == pd.audit_counts
    assert combined.metrics()["domain_audit/q/source_valid_components"] == 6
    assert combined.observed_fields == {"D": 1, "P": 1, "S": 1}


@pytest.mark.parametrize("changed", ["origin", "basis", "missing"])
def test_collator_rejects_separate_frame_inputs_that_differ_from_source_labels(changed):
    from phychem_mfm.phase1.v3_data import DecodedSample, collate_v3_samples
    from phychem_mfm.phase1.v3_sampling import SampleChoice

    target = ordered_target()
    registry = LabelRegistry((FieldSpec("r", "D", "r73", "ordered_entry"),),
                             "synthetic-frame-identity", "a" * 64)
    choice = SampleChoice(0, 0, "m0", "g0", "PM7", "fixture:0", 2,
                          (("D", True),), (("r73", True),), "a" * 64, "b" * 64)
    sample = DecodedSample("m0", "g0", "PM7", torch.tensor([[5], [7]]),
                           torch.tensor([[0., 0., 0.], [1., 0., 0.]]),
                           torch.arange(2), {"r": target},
                           domain_inputs={"r": target.inputs}, geometry_ref=REF)
    good = collate_v3_samples(((choice, sample),), registry)
    assert torch.equal(good.domain_inputs["r"].frame_origin, target.inputs.frame_origin)
    if changed == "origin":
        mismatched = replace(target.inputs, frame_origin=target.inputs.frame_origin + 1.)
    elif changed == "basis":
        mismatched = replace(target.inputs, frame_basis=-target.inputs.frame_basis)
    else:
        mismatched = replace(target.inputs, frame_origin=None, frame_basis=None)
    with pytest.raises(ValueError, match="source labels and separate ordered-entry inputs differ"):
        collate_v3_samples(((choice, replace(sample, domain_inputs={"r": mismatched})),), registry)


def test_json_sealed_configuration_builds_actual_512_encoder_two_molecules_and_strict_checkpoint(tmp_path):
    """Initial-checkpoint/config interoperability only; no real D3 or overfit claim."""
    from dataclasses import asdict
    from phychem_mfm.factory import build_model
    from phychem_mfm.phase1.v3_contract import canonical_hash
    from phychem_mfm.phase1.v3_label_domains import collate_domain_inputs
    from phychem_mfm.phase1.v3_sample_budget_events import read_bound, write_once
    from phychem_mfm.phase1.v3_sampling import ConformerRef, InMemorySamplingIndex, MoleculeEntry, UniformMoleculeSampler
    from phychem_mfm.phase1.v3_training import SampleClock, load_checkpoint, save_new_checkpoint

    previous_threads = torch.get_num_threads()
    torch.set_num_threads(1)
    try:
        _, registry, configs, _ = setup_bank(dim=512)
        book = configs["r"]["codebook"]
        # Exactly the JSON shape consumed from proxy_contract.heads; no Python
        # codebook object, ordinal, value or mask is stored in this configuration.
        configuration = {"schema": "synthetic-typed-model-config-checkpoint-v1", "engineering_only": True,
            "experiment_scope": "ENGINEERING_SYNTHETIC_ONLY", "seed": 19,
            "model": {"architecture": {"preset": "shared_light"},
                "backbone": {"dim": 512, "layers": 1, "heads": 8, "ff_mult": 1, "n_atom_types": 119},
                "head": {"profile": "phase1", "geometry_head": "equivariant_noise", "geometry_hidden_dim": 64}},
            "proxy_contract": {"heads": {"dim": 512, "hidden_dim": 8,
                "domain_head_configs": {"q": configs["q"], "r": {**configs["r"],
                    "codebook": {"tokens": list(book.tokens), "source": book.source}}}}},
            "registry": asdict(registry)}
        configuration = json.loads(json.dumps(configuration, allow_nan=False))
        configuration_hash = canonical_hash(configuration)
        sealed = write_once(tmp_path / "typed_configuration.json", configuration)
        replay = read_bound(sealed)
        assert canonical_hash(replay) == configuration_hash
        assert set(replay["proxy_contract"]["heads"]["domain_head_configs"]["r"]["codebook"]) == {"tokens", "source"}

        def construct(config):
            return V3PretrainingModel(build_model(config["model"]),
                V3HeadBank(registry, **config["proxy_contract"]["heads"])).cpu().eval()

        records = [Data(x=torch.tensor([[5], [7]]), pos=torch.tensor([[0., 0., 0.], [1., .2, -.1]])),
                   Data(x=torch.tensor([[5], [0], [6]]), pos=torch.tensor([[.1, -.3, .4], [1., 0., 0.], [0., 1., .2]]))]
        batch = Batch.from_data_list(records)
        ordered0 = ordered_target().inputs
        ordered1 = replace(ordered0, geometry_ids=("g1",))
        inputs = {"r": collate_domain_inputs((ordered0, ordered1), atom_counts=(2, 3)),
                  "q": Tensor6Inputs(torch.tensor([[9., -3., 2.], [-1., 7., 4.]]),
                                     ("g0", "g1"), (REF, REF), QFRAME)}
        context = {"geometry_ids": ("g0", "g1"), "geometry_bindings": (REF, REF), "native_atom_counts": (2, 3)}
        model = construct(replay)
        with torch.no_grad():
            original_h0 = model.encode_atoms(batch)
            original_predictions = model.forward_pretrain(batch, enabled_groups=("D", "P"),
                domain_inputs=inputs, geometry_context=context)
        assert original_h0.shape == (5, 512)
        assert {name: tuple(value.shape) for name, value in original_predictions.items()} == {
            "q": (2, 6), "r": (8, 1), "p": (2, 1)}
        head_state = model.heads.get_extra_state()
        assert json.loads(json.dumps(head_state, allow_nan=False)) == head_state

        index = InMemorySamplingIndex(tuple(MoleculeEntry(f"m{i}",
            (ConformerRef(f"g{i}", 0, count, (("PM7", f"fixture:{i}"),)),),
            (("S", True), ("D", True), ("P", True)), (("r73", True), ("r674", True), ("scalar", True)))
            for i, count in enumerate((2, 3))), "synthetic-typed-checkpoint")
        sampler = UniformMoleculeSampler(index, seed=19, sample_budget=4)
        clock = SampleClock(4)
        optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4)
        bindings = {"code_sha": "a" * 40, "configuration_sha256": sealed["sha256"],
            "registry_sha256": registry.content_sha256, "normalization_sha256": "b" * 64,
            "data_version": index.version}
        save_new_checkpoint(tmp_path / "initial", output_root=tmp_path, model=model, optimizer=optimizer,
            sampler=sampler, clock=clock, bindings=bindings,
            extra_state={"configuration": replay, "configuration_identity_sha256": configuration_hash,
                         "engineering_only": True, "checkpoint_scope": "initial_untrained_config_interop"})
        payload = torch.load(tmp_path / "initial" / "payload.pt", map_location="cpu", weights_only=True)
        assert payload["extra_state"]["configuration"] == replay
        restored = construct(read_bound(sealed))
        restored_optimizer = torch.optim.AdamW(restored.parameters(), lr=.5)
        extra = load_checkpoint(tmp_path / "initial", output_root=tmp_path, model=restored,
            optimizer=restored_optimizer, sampler=UniformMoleculeSampler(index, seed=19, sample_budget=4),
            clock=SampleClock(4), expected_bindings=bindings)
        assert extra["configuration_identity_sha256"] == configuration_hash
        with torch.no_grad():
            restored_h0 = restored.encode_atoms(batch)
            restored_predictions = restored.forward_pretrain(batch, enabled_groups=("D", "P"),
                domain_inputs=inputs, geometry_context=context)
        assert torch.equal(original_h0, restored_h0)
        for name in original_predictions:
            assert torch.equal(original_predictions[name], restored_predictions[name])
    finally:
        torch.set_num_threads(previous_threads)
