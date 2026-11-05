"""Opt-in shared pair backbones: unchanged control and geometric semantics."""
from dataclasses import replace

import pytest
import torch
from torch_geometric.data import Batch, Data

from phychem_mfm.factory import build_model
from phychem_mfm.model.v3_architecture import (ArchitectureOptions, SharedGaussianPairEncoder,
    build_architecture_model, configuration_with_architecture, build_source_s_architecture_model,
    source_s_architecture_configuration)


def configuration(**backbone):
    return {"architecture": {"preset": "shared_light"},
        "backbone": {"n_atom_types": 119, "dim": 32, "layers": 2, "heads": 4, "ff_mult": 2,
                     "use_radius_mask": False, "radius": 8., **backbone},
        "head": {"profile": "phase1", "geometry_head": "equivariant_noise",
                 "geometry_hidden_dim": 16, "geometry_rbf_count": 8}}


def molecules():
    return Batch.from_data_list([
        Data(x=torch.tensor([[5], [7], [0], [6]]),
             pos=torch.tensor([[0., 0., 0.], [1.1, 0., 0.], [.1, .8, .2], [.2, .2, 1.4]])),
        Data(x=torch.tensor([[5], [8]]), pos=torch.tensor([[0., 0., 0.], [1.8, .3, 0.]]))])


def create(candidate, **backbone):
    torch.manual_seed(619)
    return build_architecture_model(configuration(**backbone), ArchitectureOptions(distance_bias=candidate))


def test_c1_zero_is_exact_legacy_factory_and_preserves_state_keys_and_rng():
    torch.manual_seed(619)
    original = build_model(configuration())
    rng = torch.get_rng_state().clone()
    candidate = create("C1-0")
    assert torch.equal(torch.get_rng_state(), rng)
    assert set(original.state_dict()) == set(candidate.state_dict())
    for key, value in original.state_dict().items():
        assert torch.equal(value, candidate.state_dict()[key])
    assert torch.equal(original.encode_atoms(molecules()), candidate.encode_atoms(molecules()))


@pytest.mark.parametrize("kind", ("C1-a", "C1-b"))
def test_new_distance_path_retains_common_parameter_initialization_and_rng(kind):
    control = create("C1-0")
    rng = torch.get_rng_state().clone()
    candidate = create(kind)
    assert torch.equal(torch.get_rng_state(), rng)
    common = {key: value for key, value in control.state_dict().items() if ".dist_mlp." not in key}
    for key, value in common.items():
        assert torch.equal(value, candidate.state_dict()[key]), key
    assert not any("dist_mlp" in key for key in candidate.state_dict())
    assert candidate.encode_atoms(molecules()).shape == (6, 32)
    assert candidate.encode_graph(molecules()).shape == (2, 32)


def test_a_b_share_initial_common_pair_weights_and_outputs_before_pair_affines_learn():
    a, b = create("C1-a"), create("C1-b")
    for key, value in a.state_dict().items():
        if key.endswith("_extra_state"):
            continue
        assert torch.equal(value, b.state_dict()[key]), key
    assert torch.equal(a.encode_atoms(molecules()), b.encode_atoms(molecules()))


def test_config_export_and_reconstruction_bind_same_shape_c1_options():
    options = ArchitectureOptions(distance_bias="C1-a")
    sealed = configuration_with_architecture(configuration(), options)
    torch.manual_seed(619); model = build_architecture_model(sealed)
    assert model.config_dict()["backbone_config"] == sealed["backbone"]
    assert model.config_dict()["backbone_config"]["v3_architecture"]["cutoff"] is None
    with pytest.raises(ValueError, match="configuration/options differ"):
        build_architecture_model(sealed, replace(options, rbf_max_distance=9.))
    rebuilt = build_architecture_model(sealed)
    rebuilt.load_state_dict(model.state_dict())
    assert torch.equal(rebuilt.encode_atoms(molecules()), model.encode_atoms(molecules()))


def test_explicit_production_builder_recreates_measured_tiled65536_control_and_seals_implementation():
    options = ArchitectureOptions(distance_bias="C1-0")
    config = source_s_architecture_configuration(configuration(activation_checkpointing=True), options)
    torch.manual_seed(619); control = build_source_s_architecture_model(config)
    assert all(layer.attn.dist_mlp.__class__.__name__ == "TiledDistanceMLP" for layer in control.backbone.layers)
    assert control.s_memory_implementation["pair_rows"] == 65536
    assert control.backbone.activation_checkpointing is True
    assert control.config_dict()["backbone_config"] == config["backbone"]
    altered = configuration_with_architecture(config, ArchitectureOptions(distance_bias="C1-a"))
    candidate = build_source_s_architecture_model(altered)
    assert not hasattr(candidate, "s_memory_implementation")
    assert candidate.v3_legacy_control_memory_implementation["pair_rows"] == 65536
    assert not any("dist_mlp" in name for name, module in candidate.named_modules())
    broken = {**config, "backbone": {**config["backbone"], "v3_legacy_memory": {
        **config["backbone"]["v3_legacy_memory"], "source_sha256": "0" * 64}}}
    with pytest.raises(ValueError, match="Only the frozen"):
        build_architecture_model(broken)


@pytest.mark.parametrize("kind", ("C1-a", "C1-b"))
def test_invariant_to_translation_rotation_and_equivariant_to_native_atom_permutation(kind):
    model, base = create(kind).eval(), molecules()
    expected = model.encode_atoms(base)
    rotation = torch.tensor([[0., 1., 0.], [0., 0., 1.], [1., 0., 0.]])
    moved = base.clone(); moved.pos = base.pos @ rotation + torch.tensor([3., -2., .7])
    torch.testing.assert_close(model.encode_atoms(moved), expected, atol=2e-6, rtol=2e-5)
    records, order = [], []
    offset = 0
    for record in base.to_data_list():
        permutation = torch.arange(len(record.x) - 1, -1, -1)
        records.append(Data(x=record.x[permutation], pos=record.pos[permutation]))
        order.extend((permutation + offset).tolist()); offset += len(record.x)
    torch.testing.assert_close(model.encode_atoms(Batch.from_data_list(records)), expected[order], atol=2e-6, rtol=2e-5)


@pytest.mark.parametrize("kind", ("C1-a", "C1-b"))
def test_padding_another_molecule_does_not_change_native_h0(kind):
    model, base = create(kind).eval(), molecules()
    packed = model.encode_atoms(base)
    for index, record in enumerate(base.to_data_list()):
        left, right = int(base.ptr[index]), int(base.ptr[index+1])
        torch.testing.assert_close(model.encode_atoms(record), packed[left:right], atol=2e-6, rtol=2e-5)


def test_pair_encoding_once_layer_projections_distinct_and_gradients_finite_including_coincident_atoms():
    model = create("C1-b").train()
    base = molecules(); base.pos[1] = base.pos[0]; base.pos.requires_grad_(True)
    calls = []
    hook = model.backbone.pair_encoder.register_forward_hook(lambda *args: calls.append(1))
    try:
        output = model.encode_atoms(base)
        (output * torch.arange(output.numel()).reshape_as(output)).sum().backward()
    finally:
        hook.remove()
    assert calls == [1]
    projections = [layer.attn.pair_projection.weight for layer in model.backbone.layers]
    assert len({id(value) for value in projections}) == 2
    for parameter in (model.backbone.pair_encoder.centers, model.backbone.pair_encoder.raw_widths,
                      model.backbone.pair_encoder.pair_scale.weight, model.backbone.pair_encoder.pair_shift.weight, *projections):
        assert parameter.grad is not None and torch.isfinite(parameter.grad).all() and parameter.grad.abs().sum() > 0
    assert base.pos.grad is not None and torch.isfinite(base.pos.grad).all()


def test_element_pair_transforms_only_change_their_input_pair_types():
    options = ArchitectureOptions(distance_bias="C1-b")
    encoder = SharedGaussianPairEncoder(options, 119)
    pos = torch.tensor([[[0., 0., 0.], [1., 0., 0.], [0., 1., 0.]]])
    elements, mask = torch.tensor([[5, 7, 5]]), torch.ones(1, 3, dtype=torch.bool)
    before, _ = encoder(pos, elements, mask)
    with torch.no_grad():
        encoder.pair_shift.weight[5 * 119 + 7] = .2
    after, _ = encoder(pos, elements, mask)
    selected = elements[:, :, None].eq(5) & elements[:, None, :].eq(7)
    assert torch.equal(before[~selected], after[~selected])
    assert not torch.equal(before[selected], after[selected])


def test_no_hidden_cutoff_for_global_attention_and_finite_policy_must_match_actual_radius():
    with pytest.raises(ValueError, match="Global attention"):
        build_architecture_model(configuration(), ArchitectureOptions(distance_bias="C1-a", cutoff=8.))
    with pytest.raises(ValueError, match="equal the enabled"):
        build_architecture_model(configuration(use_radius_mask=True), ArchitectureOptions(distance_bias="C1-a"))
    with pytest.raises(ValueError, match="equal the enabled"):
        build_architecture_model(configuration(use_radius_mask=True), ArchitectureOptions(distance_bias="C1-a", cutoff=5.))
    options = ArchitectureOptions(distance_bias="C1-a", cutoff=8.)
    finite = build_architecture_model(configuration(use_radius_mask=True), options)
    encoder = finite.backbone.pair_encoder
    features, _ = encoder(torch.tensor([[[0., 0., 0.], [9., 0., 0.]]]), torch.tensor([[5, 5]]),
                          torch.ones(1, 2, dtype=torch.bool))
    assert torch.equal(features[:, 0, 1], torch.zeros_like(features[:, 0, 1]))
    global_model = create("C1-a")
    long = Data(x=torch.tensor([[5], [7]]), pos=torch.tensor([[0., 0., 0.], [9., 0., 0.]]))
    output = global_model.encode_atoms(long)
    altered = long.clone(); altered.x[1] = 6
    assert not torch.equal(output[0], global_model.encode_atoms(altered)[0])


@pytest.mark.parametrize("kind", ("C1-a", "C1-b"))
def test_checkpoint_retains_shared_feature_single_forward_and_matching_gradients(kind):
    plain, checked = create(kind), create(kind, activation_checkpointing=True)
    checked.load_state_dict(plain.state_dict())
    calls = []
    hook = checked.backbone.pair_encoder.register_forward_hook(lambda *args: calls.append(1))
    coefficients = torch.linspace(-1., 1., 6 * 32).view(6, 32)
    left, right = plain.encode_atoms(molecules()), checked.encode_atoms(molecules())
    (left * coefficients).sum().backward(); (right * coefficients).sum().backward()
    hook.remove()
    assert calls == [1] and torch.equal(left, right)
    for (name, p), (other_name, q) in zip(plain.named_parameters(), checked.named_parameters()):
        assert name == other_name
        assert (p.grad is None and q.grad is None) or torch.equal(p.grad, q.grad), name


def test_rbf_and_geometry_stay_fp32_under_cpu_autocast_and_options_bind_checkpoints():
    model = create("C1-b")
    inputs = []
    hook = model.backbone.pair_encoder.project.register_forward_pre_hook(lambda module, args: inputs.append(args[0].dtype))
    with torch.autocast(device_type="cpu", dtype=torch.bfloat16):
        output = model.encode_atoms(molecules())
    hook.remove()
    assert inputs == [torch.float32] and torch.isfinite(output).all()
    wrong = create("C1-a")
    with pytest.raises(ValueError, match="checkpoint/options differ"):
        wrong.load_state_dict(model.state_dict())


@pytest.mark.parametrize("value", ({"distance_bias": "typo"}, {"rbf_count": 32},
    {"pair_dim": 0}, {"pair_hidden_dim": True}, {"cutoff": float("inf")}, {"rbf_max_distance": 0.}))
def test_bad_architecture_options_fail_before_model_build(value):
    with pytest.raises(ValueError):
        ArchitectureOptions(**value)
