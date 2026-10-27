"""CPU mechanisms only; no CUDA/A20+500/D3/performance acceptance."""
from copy import deepcopy
from dataclasses import asdict

import pytest
import torch
from torch import nn
from torch_geometric.data import Batch, Data

from phychem_mfm.model.v3_architecture import ArchitectureOptions, build_architecture_model
from phychem_mfm.model.v3_performance import PerformanceOptions
from phychem_mfm.phase1.v3_training_execution import (TrainingExecutionSpec, build_training_encoder,
    make_training_optimizer, finalize_training_execution, training_execution_context,
    validate_training_execution_contract, validate_training_execution_state,
    validate_h0_export_contract, build_h0_export_encoder)
from phychem_mfm.phase1.v3_trainer import _execution_state

PADDING = {"atom_bucket_width": 2, "max_graphs_per_chunk": 1, "max_padded_cost_per_chunk": 16}


@pytest.fixture(autouse=True)
def cpu_runtime():
    before = (torch.get_num_threads(), torch.backends.cuda.matmul.allow_tf32, torch.backends.cudnn.allow_tf32,
              torch.get_float32_matmul_precision())
    torch.set_num_threads(1)
    torch.set_float32_matmul_precision("highest")
    torch.backends.cudnn.allow_tf32 = False
    try:yield
    finally:
        torch.set_num_threads(before[0]); torch.set_float32_matmul_precision(before[3])
        torch.backends.cudnn.allow_tf32 = before[2]


def configuration(architecture="C1-0"):
    cfg = {"architecture": {"preset": "shared_light"},
        "backbone": {"dim": 16, "layers": 2, "heads": 4, "ff_mult": 2, "activation_checkpointing": True},
        "head": {"profile": "phase1", "geometry_head": "equivariant_noise", "geometry_hidden_dim": 8,
                 "geometry_rbf_count": 4, "geometry_message_layers": 0, "geometry_pair_chunk_size": 64}}
    if architecture != "C1-0":
        cfg["backbone"]["v3_architecture"] = asdict(ArchitectureOptions(
            distance_bias=architecture, pair_dim=4, pair_hidden_dim=8))
    return cfg


def policy(architecture="C1-0", *, packing=False, checkpoint=True):
    return {"geometry_scope": "c1_scalar_distance_v1" if architecture == "C1-0" else "c1_shared_pair_v1",
        "options": {"backbone_checkpointing": checkpoint, "distance_checkpointing": checkpoint,
                    "head_checkpointing": checkpoint, "distance_pair_rows": 4,
                    "distance_implementation": "tiled" if architecture == "C1-0" else "dense"},
        "padding": PADDING if packing else None}


def workload(cfg, optimizer=None):
    return {"schema": "model_v3_training_workload_v1", "scope": "engineering_synthetic_fixture", "seed": 31,
        "model_configuration": deepcopy(cfg), "data": {"registry_sha256": "1" * 64,
            "normalization_sha256": "2" * 64, "authority_sha256": "3" * 64,
            "data_version": "explicit_unit_fixture", "selection": {"mode": "all_fixture"},
            "validation_population_bindings": {"VAL": {"fixture": "seen"},
                "TRAIN_UNSEEN_CONFORMATION": {"fixture": "unseen"}}},
        "groups": ["S", "P"], "fields": ["fixture_pd"], "heads": {"fixture": "linear"}, "views": "three",
        "view_policy": {"fixture": True}, "loss": {"fixture": "whole_logical_mean"},
        "optimizer": {"lr": .001} if optimizer is None else deepcopy(optimizer),
        "validation": {"roles": ["VAL", "TRAIN_UNSEEN_CONFORMATION"]}}


def packed():
    generator = torch.Generator().manual_seed(341)
    return Batch.from_data_list([Data(x=torch.full((n, 1), 5, dtype=torch.long),
        pos=torch.randn(n, 3, generator=generator) * .2) for n in (1, 3, 7)])


class Composite(nn.Module):
    """Real encoder plus a real extra head, never a mocked training model."""
    def __init__(self, encoder):
        super().__init__(); self.encoder = encoder; self.pd = nn.Linear(16, 1)

    def forward(self, batch):
        output = self.encoder.forward_pretrain(batch, ("element", "geometry"))
        return output, self.pd(output.atom_repr)


def assembled(architecture="C1-0", *, packing=False, checkpoint=True, optimizer=None):
    cfg = configuration(architecture); binding = workload(cfg, optimizer)
    built = build_training_encoder(cfg, execution=policy(architecture, packing=packing, checkpoint=checkpoint),
                                   workload_binding=binding)
    model = Composite(built.encoder)
    opt = make_training_optimizer(model, binding["optimizer"], built)
    with training_execution_context(built):
        contract = finalize_training_execution(model, opt, built)
    return model, opt, built, contract


@pytest.mark.parametrize("architecture", ["C1-a", "C1-b"])
def test_partial_C1_declaration_is_still_rejected_before_constructor_rng(architecture):
    cfg = configuration(architecture)
    cfg["backbone"]["v3_architecture"] = {
        "distance_bias": architecture, "pair_dim": 4, "pair_hidden_dim": 8}
    before = deepcopy(cfg)
    rng = torch.get_rng_state().clone()
    for construct in (
            lambda: build_architecture_model(cfg),
            lambda: build_training_encoder(cfg, execution=policy(architecture), workload_binding=workload(cfg))):
        with pytest.raises(ValueError, match="Declared C1 configuration/options differ"):
            construct()
        assert cfg == before and torch.equal(rng, torch.get_rng_state())

@pytest.mark.parametrize("architecture", ["C1-0", "C1-a", "C1-b"])
def test_absent_optin_retains_original_constructor_rng_values_and_keys(architecture):
    cfg = configuration(architecture)
    torch.manual_seed(31); original = build_architecture_model(cfg); expected_rng = torch.get_rng_state().clone()
    torch.manual_seed(31); built = build_training_encoder(cfg)
    assert torch.equal(expected_rng, torch.get_rng_state())
    assert built.resolved_options is None and built.observer is None and built.contract is None
    assert not hasattr(built.encoder, "v3_performance_options")
    assert tuple(original.state_dict()) == tuple(built.encoder.state_dict())
    for key, value in original.state_dict().items():
        if isinstance(value, torch.Tensor):assert torch.equal(value, built.encoder.state_dict()[key])
        else:assert value == built.encoder.state_dict()[key]


@pytest.mark.parametrize("architecture", ["C1-0", "C1-a", "C1-b"])
@pytest.mark.parametrize("checkpoint", [False, True])
def test_actual_whole_batch_chunks_restore_values_position_and_all_parameter_gradients(architecture, checkpoint):
    torch.manual_seed(31); left, _, _, _ = assembled(architecture, checkpoint=checkpoint)
    left_rng = torch.get_rng_state().clone()
    torch.manual_seed(31); right, _, built, _ = assembled(architecture, checkpoint=checkpoint, packing=True)
    assert torch.equal(left_rng, torch.get_rng_state())
    assert tuple(left.state_dict()) == tuple(right.state_dict())
    batch = packed(); batch.pos.requires_grad_(True)
    source_x, source_pos, source_batch = batch.x.clone(), batch.pos.detach().clone(), batch.batch.clone()
    rng = torch.get_rng_state().clone(); outputs = []; position_grads = []
    for model in (left, right):
        batch.pos.grad = None
        output, pd = model(batch)
        loss = output.atom_repr.square().mean() + output.element_logits.square().mean() + output.noise_pred.square().mean() + pd.square().mean()
        loss.backward(); outputs.append((output, pd)); position_grads.append(batch.pos.grad.detach().clone())
        assert torch.equal(rng, torch.get_rng_state())
    for name in ("atom_repr", "graph_repr", "element_logits", "noise_pred"):
        torch.testing.assert_close(getattr(outputs[0][0], name), getattr(outputs[1][0], name), atol=5e-6, rtol=3e-5)
    torch.testing.assert_close(outputs[0][1], outputs[1][1], atol=5e-6, rtol=3e-5)
    torch.testing.assert_close(position_grads[0], position_grads[1], atol=8e-6, rtol=5e-4)
    for (name, a), (other_name, b) in zip(left.named_parameters(), right.named_parameters()):
        assert name == other_name and (a.grad is None) == (b.grad is None)
        if a.grad is not None:torch.testing.assert_close(a.grad, b.grad, atol=8e-6, rtol=5e-4)
    assert torch.equal(source_x, batch.x) and torch.equal(source_pos, batch.pos) and torch.equal(source_batch, batch.batch)
    receipt = built.encoder.backbone.last_logical_batch_execution
    assert receipt["graph_atom_counts"] == [1, 3, 7]
    assert receipt["chunked_dense_padded_cost"] < receipt["legacy_dense_padded_cost"]
    assert receipt["original_atom_and_graph_order_restored"] and not receipt["loss_or_group_reduction_per_chunk"]


@pytest.mark.parametrize("architecture", ["C1-a", "C1-b"])
@pytest.mark.parametrize("checkpoint", [False, True])
def test_shared_pair_wrapper_preserves_optional_interface_objects_gradients_and_later_default(architecture, checkpoint):
    from phychem_mfm.model.v3_architecture import SharedGaussianPairEncoder
    from phychem_mfm.model.v3_performance import CheckpointedSharedPairEncoder
    options = ArchitectureOptions(distance_bias=architecture, pair_dim=4, pair_hidden_dim=8)
    original = SharedGaussianPairEncoder(options, n_atom_types=8)
    parameters = dict(original.named_parameters())
    buffers = dict(original.named_buffers())
    state_keys = tuple(original.state_dict())
    rng = torch.get_rng_state().clone()
    wrapped = CheckpointedSharedPairEncoder(original, activation_checkpointing=checkpoint)
    assert torch.equal(rng, torch.get_rng_state())
    assert wrapped.options is original.options and wrapped.n_atom_types == original.n_atom_types
    assert wrapped.project is original.project and wrapped.training == original.training
    assert wrapped.pair_scale is original.pair_scale and wrapped.pair_shift is original.pair_shift
    if architecture == "C1-a":
        assert wrapped.pair_scale is None and wrapped.pair_shift is None
    else:
        assert type(wrapped.pair_scale) is nn.Embedding and type(wrapped.pair_shift) is nn.Embedding
    assert tuple(wrapped.state_dict()) == state_keys
    assert set(dict(wrapped.named_parameters())) == set(parameters)
    assert all(dict(wrapped.named_parameters())[name] is value for name, value in parameters.items())
    assert set(dict(wrapped.named_buffers())) == set(buffers)
    assert all(dict(wrapped.named_buffers())[name] is value for name, value in buffers.items())
    positions = torch.tensor([[[0., 0., 0.], [.4, .1, .2], [0., 0., 0.]],
                              [[.2, .1, .3], [.7, .4, .2], [.1, .8, .5]]])
    elements = torch.tensor([[5, 0, 0], [6, 5, 0]])
    mask = torch.tensor([[True, True, False], [True, True, True]])
    results, gradients = [], []
    for encoder in (original, wrapped):
        pos = positions.clone().requires_grad_(True)
        features, distances = encoder(pos, elements, mask)
        grads = torch.autograd.grad(features.square().sum() + distances.square().sum(),
                                    (pos, *parameters.values()))
        assert all(torch.isfinite(value).all() for value in grads)
        results.append((features.detach(), distances.detach()))
        gradients.append(grads)
    for expected, actual in zip(results[0], results[1]):
        torch.testing.assert_close(actual, expected, rtol=0, atol=0)
    for expected, actual in zip(gradients[0], gradients[1]):
        torch.testing.assert_close(actual, expected, rtol=0, atol=0)
    assert torch.equal(rng, torch.get_rng_state())
    # A later no-opt-in forward/backward in the same process still follows the
    # original path; no global hooks or delegation into this pair encoder.
    cfg = configuration()
    with torch.random.fork_rng(devices=[]):
        torch.random.default_generator.manual_seed(812)
        control = build_architecture_model(cfg)
        after_control = torch.get_rng_state().clone()
        torch.random.default_generator.manual_seed(812)
        default = build_training_encoder(cfg)
        assert torch.equal(after_control, torch.get_rng_state())
        assert default.resolved_options is None and default.observer is None
        control_result = control.encode_atoms(packed())
        default_result = default.encoder.encode_atoms(packed())
        torch.testing.assert_close(default_result, control_result, rtol=0, atol=0)
        control_grads = torch.autograd.grad(control_result.square().sum(), tuple(control.backbone.parameters()))
        default_grads = torch.autograd.grad(default_result.square().sum(), tuple(default.encoder.backbone.parameters()))
        for expected, actual in zip(control_grads, default_grads):
            torch.testing.assert_close(actual, expected, rtol=0, atol=0)
    assert torch.equal(rng, torch.get_rng_state())

@pytest.mark.parametrize("architecture", ["C1-a", "C1-b"])
def test_shared_pair_checkpoint_scope_uses_real_parameters_and_one_shared_encoder(architecture):
    model, _, _, contract = assembled(architecture, checkpoint=True)
    scope = contract["checkpoint_scope_map"]["distance_checkpointing"]
    assert scope["meaning"] == "shared_pair_encoder_complete"
    assert scope["modules"] == ["encoder.backbone.pair_encoder"]
    assert contract["resolved_options"]["distance_checkpointing"] is True
    assert model.encoder.backbone.pair_encoder.activation_checkpointing is True
    assert not any("dist_mlp" in name for name, _ in model.encoder.named_parameters())
    assert all(layer.attn.pair_projection.weight.requires_grad for layer in model.encoder.backbone.layers)


@pytest.mark.parametrize("architecture,bad", [("C1-a", "scope"), ("C1-b", "bf16"), ("C1-0", "dropout"),
                                              ("C1-0", "global_sparse"), ("C1-a", "tiled")])
def test_unsupported_combinations_reject_before_parameter_initialization_rng(architecture, bad):
    cfg = configuration(architecture); request = policy(architecture, packing=True)
    if bad == "scope":request["geometry_scope"] = "c1_scalar_distance_v1"
    elif bad == "bf16":request["options"]["precision"] = "bf16"
    elif bad == "dropout":cfg["backbone"]["dropout"] = .2
    elif bad == "global_sparse":request["options"]["attention_backend"] = "sparse_radius"
    else:request["options"]["distance_implementation"] = "tiled"
    rng = torch.get_rng_state().clone()
    with pytest.raises(ValueError):build_training_encoder(cfg, execution=request, workload_binding=workload(cfg))
    assert torch.equal(rng, torch.get_rng_state())


@pytest.mark.parametrize("declared", [{"lr": .001}, {"lr": .001, "fused": None, "foreach": None},
                                    {"lr": .001, "fused": False, "foreach": False}])
def test_actual_optimizer_preserves_omitted_none_false_dispatch_and_full_pd_parameters(declared):
    model, optimizer, _, contract = assembled(optimizer=declared)
    assert contract["optimizer_dispatch"]["declared"] == declared
    assert optimizer.defaults["fused"] is declared.get("fused")
    assert optimizer.defaults["foreach"] is declared.get("foreach")
    assert {id(p) for group in optimizer.param_groups for p in group["params"]} == {id(p) for p in model.parameters()}


def test_contract_state_roundtrip_safe_weights_only_h0_and_new_admission_not_in_semantics(tmp_path):
    torch.manual_seed(31); model, optimizer, built, contract = assembled("C1-b", packing=True)
    batch = packed(); output, pd = model(batch)
    (output.atom_repr.square().mean() + pd.square().mean()).backward(); optimizer.step()
    state = _execution_state(model)
    # Exercise the exact state container SA3 writes after its conditional key.
    state["training_execution"] = deepcopy(contract)
    validate_training_execution_state(contract, state)
    path = tmp_path / "safe.pt"
    torch.save({"model": model.state_dict(), "optimizer": optimizer.state_dict(), "execution": state}, path)
    loaded = torch.load(path, weights_only=True)
    validate_training_execution_state(contract, loaded["execution"])
    torch.manual_seed(99); restored, restored_opt, restored_built, restored_contract = assembled("C1-b", packing=True)
    assert restored_contract == contract
    restored.load_state_dict(loaded["model"], strict=True); restored_opt.load_state_dict(loaded["optimizer"])
    assert "operational_admission" not in contract and "capacity_profile" not in contract["requested_execution"]
    with training_execution_context(built), torch.no_grad():
        model.eval(); before = model.encoder.encode_atoms(batch)
        h0 = build_h0_export_encoder(configuration("C1-b"), contract)
        h0.load_state_dict(model.encoder.state_dict(), strict=True)
        assert torch.equal(before, h0.encode_atoms(batch))
    assert h0.training_h0_export_contract == contract["h0_export"]
    assert validate_h0_export_contract(contract) == contract
    rng = torch.get_rng_state().clone()
    corrupted = deepcopy(state); corrupted["resolved_checkpoint_flags"]["encoder.backbone"]["activation_checkpointing"] = False
    with pytest.raises(ValueError, match="projection"):validate_training_execution_state(contract, corrupted)
    assert torch.equal(rng, torch.get_rng_state())


@pytest.mark.parametrize("part", ["scope", "padding", "optimizer", "source"])
def test_changed_contract_rejects_before_weights_or_rng(part):
    model, _, _, contract = assembled("C1-a", packing=True)
    value = deepcopy(contract)
    if part == "scope":value["checkpoint_scope_map"]["distance_checkpointing"]["meaning"] = "old_scalar_tiles"
    elif part == "padding":value["h0_export"]["padding"]["atom_bucket_width"] += 1
    elif part == "optimizer":value["optimizer_dispatch"]["effective"]["foreach"] = True
    else:value["implementation_sha256"]["current/phychem_mfm/model/v3_architecture.py"] = "0" * 64
    rng = torch.get_rng_state().clone()
    parameters = {name: p.detach().clone() for name, p in model.named_parameters()}
    with pytest.raises(ValueError):validate_training_execution_contract(value)
    assert torch.equal(rng, torch.get_rng_state())
    assert all(torch.equal(parameters[name], p) for name, p in model.named_parameters())


def test_auto_compiled_packing_and_r2_are_explicitly_refused_without_cuda_selection():
    cfg = configuration(); request = policy(packing=True)
    request["checkpoint_policy"] = "auto_closed_training_profile_v1"
    request["options"]["compile_backbone"] = True
    with pytest.raises(ValueError, match="compiled packing"):
        build_training_encoder(cfg, execution=request, workload_binding=workload(cfg))
    with pytest.raises(ValueError, match="R2"):
        TrainingExecutionSpec(resident_models=2)
    assert set(asdict(PerformanceOptions())) == {"precision", "distance_implementation", "distance_pair_rows",
        "distance_checkpointing", "backbone_checkpointing", "head_checkpointing", "attention_backend",
        "sparse_query_chunk", "fused_adamw", "tf32", "compile_backbone", "compile_dynamic"}

@pytest.mark.parametrize("architecture", ["C1-a", "C1-b"])
@pytest.mark.parametrize("masked", [False, True])
def test_real_three_view_SDP_counts_masks_and_source_are_whole_batch(architecture, masked):
    from test_model_v3_structural import setup_model
    from phychem_mfm.phase1.v3_structural import build_structural_views, StructuralViewConfig
    from phychem_mfm.training.losses import LossWeights
    template, base, registry, structural, norms, targets = setup_model()
    cfg = configuration(architecture)
    cfg["backbone"].update(dim=512, layers=1, heads=8, ff_mult=1, n_atom_types=119)
    cfg["head"].update(geometry_hidden_dim=64, geometry_rbf_count=32)
    torch.manual_seed(31)
    left = build_training_encoder(cfg, execution=policy(architecture), workload_binding=workload(cfg))
    torch.manual_seed(31)
    right = build_training_encoder(cfg, execution=policy(architecture, packing=True), workload_binding=workload(cfg))
    template.encoder = left.encoder
    other = deepcopy(template); other.encoder = right.encoder
    views = build_structural_views(base, ordinals=(10, 11), config=StructuralViewConfig(seed=99))
    saved = {key: value.clone() for key, value in views.batch.to_dict().items() if isinstance(value, torch.Tensor)}
    rng = torch.get_rng_state().clone()
    eligibility = None if not masked else {"element": torch.arange(24) % 2 == 0,
        "noise": torch.arange(24) < 12, "bond": torch.zeros(24, dtype=torch.bool)}
    results = []
    for model in (template, other):
        prediction = model.forward_pretrain(views, enabled_groups=("S", "D", "P"))
        result = model.compute_loss(prediction, views, targets, norms, enabled_groups=("S", "D", "P"),
            weights=LossWeights(), atom_eligibility=eligibility, exposure_step=0)
        result.total.backward(); results.append(result)
        assert torch.equal(rng, torch.get_rng_state())
    assert results[0].counts == results[1].counts
    assert results[0].observed_fields == results[1].observed_fields
    if masked:assert results[0].counts["s_bond"] == 0
    else:assert all(value > 0 for value in results[0].counts.values())
    torch.testing.assert_close(results[0].total, results[1].total, atol=5e-6, rtol=5e-5)
    for (name, a), (other_name, b) in zip(template.named_parameters(), other.named_parameters()):
        assert name == other_name and (a.grad is None) == (b.grad is None)
        if a.grad is not None:torch.testing.assert_close(a.grad, b.grad, atol=1e-5, rtol=7e-4)
    assert all(torch.equal(value, views.batch[key]) for key, value in saved.items())
    assert views.batch.sample_type_id.tolist() == [0, 1, 2, 0, 1, 2]

@pytest.mark.parametrize("architecture", ["C1-a", "C1-b"])
@pytest.mark.parametrize("bad", ["empty", "hole", "unordered"])
def test_shared_empty_or_invalid_graphs_reject_without_rng_or_input_changes(architecture, bad):
    model, _, built, _ = assembled(architecture, packing=True)
    batch = packed()
    if bad == "empty":
        batch = Data(x=torch.empty(0, 1, dtype=torch.long), pos=torch.empty(0, 3), batch=torch.empty(0, dtype=torch.long))
    elif bad == "hole":batch.batch[batch.batch == 1] = 2
    else:batch.batch = torch.flip(batch.batch, (0,))
    x, pos, ids = batch.x.clone(), batch.pos.clone(), batch.batch.clone()
    rng = torch.get_rng_state().clone()
    with pytest.raises(ValueError):
        with built.observer.forward_context(model, role="TRAIN"):
            model.encoder.encode_atoms(batch)
    assert torch.equal(rng, torch.get_rng_state())
    assert torch.equal(x, batch.x) and torch.equal(pos, batch.pos) and torch.equal(ids, batch.batch)


@pytest.mark.parametrize("architecture", ["C1-a", "C1-b"])
@pytest.mark.parametrize("change", ["checkpoint_flag", "real_dropout"])
def test_shared_runtime_flag_or_real_dropout_changes_cannot_qualify_profile(architecture, change):
    model, _, built, _ = assembled(architecture, packing=True)
    if change == "checkpoint_flag":model.encoder.backbone.activation_checkpointing = False
    else:
        net = model.encoder.backbone.layers[0].ffn.net
        assert isinstance(net[2], nn.Identity)
        net[2] = nn.Dropout(.2)
        assert net[2].training and any(module is net[2] for module in model.modules())
        with torch.random.fork_rng(devices=[]):
            torch.set_rng_state(torch.Generator().manual_seed(1742).get_state())
            probe = torch.ones(256); before = torch.get_rng_state().clone()
            assert not torch.equal(net[2](probe), probe) and not torch.equal(before, torch.get_rng_state())
    rng = torch.get_rng_state().clone()
    with pytest.raises(ValueError, match="checkpoint|RNG"):
        with built.observer.forward_context(model, role="TRAIN"):
            model(packed())
    assert torch.equal(rng, torch.get_rng_state())

@pytest.mark.parametrize("initial_precision", ["highest", "medium"])
@pytest.mark.parametrize("raise_in_scope", [False, True])
def test_h0_context_applies_declared_policy_and_restores_globals_rng(initial_precision, raise_in_scope):
    from phychem_mfm.phase1.v3_training_execution import h0_export_context
    _, _, _, contract = assembled()
    def snapshot():
        return (torch.get_float32_matmul_precision(), torch.backends.cuda.matmul.allow_tf32,
            torch.backends.cudnn.allow_tf32, torch.are_deterministic_algorithms_enabled(),
            torch.is_deterministic_algorithms_warn_only_enabled(), torch.backends.cudnn.deterministic,
            torch.backends.cudnn.benchmark)
    original = snapshot()
    try:
        # Legal medium already implies CUDA TF32; a redundant legacy setter
        # would invalidate its distinct MKLDNN BF16 policy in PyTorch 2.10.
        torch.set_float32_matmul_precision(initial_precision)
        torch.backends.cudnn.allow_tf32 = True
        torch.backends.cudnn.benchmark = True
        before, rng = snapshot(), torch.get_rng_state().clone()
        assert before[0] == initial_precision
        assert before[1] == (initial_precision == "medium")
        def exercise():
            with h0_export_context(contract, device_type="cpu"):
                assert torch.get_float32_matmul_precision() == "highest"
                assert not torch.backends.cuda.matmul.allow_tf32 and not torch.backends.cudnn.allow_tf32
                assert torch.are_deterministic_algorithms_enabled() == contract["execution_state"]["deterministic_algorithms"]
                assert not torch.is_deterministic_algorithms_warn_only_enabled()
                assert not torch.backends.cudnn.benchmark
                if raise_in_scope:raise RuntimeError("scope sentinel")
        if raise_in_scope:
            with pytest.raises(RuntimeError, match="scope sentinel"):exercise()
        else:
            exercise()
        assert snapshot() == before and torch.equal(rng, torch.get_rng_state())
    finally:
        torch.set_float32_matmul_precision(original[0])
        torch.backends.cudnn.allow_tf32 = original[2]
        torch.use_deterministic_algorithms(original[3], warn_only=original[4])
        torch.backends.cudnn.deterministic = original[5]
        torch.backends.cudnn.benchmark = original[6]


def test_real_WSD_metadata_rebind_keeps_parameters_optimizer_slots_rng_and_rejects_other_changes():
    from phychem_mfm.phase1.v3_training_execution import rebind_training_execution
    cfg = configuration("C1-a"); parent_workload = workload(cfg)
    parent_workload["view_policy"].update(schedule={"mode": "wsd", "decay_start_samples": 20}, sample_budget=30)
    built = build_training_encoder(cfg, execution=policy("C1-a"), workload_binding=parent_workload)
    model = Composite(built.encoder); optimizer = make_training_optimizer(model, parent_workload["optimizer"], built)
    finalize_training_execution(model, optimizer, built)
    output, pd = model(packed()); (output.atom_repr.square().mean() + pd.square().mean()).backward(); optimizer.step()
    parameters = tuple(id(p) for p in model.parameters())
    slots = {id(p): {key: id(value) for key, value in state.items()} for p, state in optimizer.state.items()}
    rng = torch.get_rng_state().clone()
    child_workload = deepcopy(parent_workload)
    child_workload["view_policy"].update(schedule={"mode": "wsd", "decay_start_samples": 3}, sample_budget=9)
    child = rebind_training_execution(model, optimizer, built, workload_binding=child_workload)
    assert child.encoder is built.encoder and child.contract["workload_sha256"] != built.contract["workload_sha256"]
    assert child.resolved_options == built.resolved_options and child.observer is not built.observer
    assert tuple(id(p) for p in model.parameters()) == parameters
    assert {id(p): {key: id(value) for key, value in state.items()} for p, state in optimizer.state.items()} == slots
    assert torch.equal(rng, torch.get_rng_state())
    bad = deepcopy(child_workload); bad["loss"]["fixture"] = "changed"
    with pytest.raises(ValueError, match="only change"):
        rebind_training_execution(model, optimizer, child, workload_binding=bad)
    assert torch.equal(rng, torch.get_rng_state())
    assert model.training_execution_contract == child.contract
