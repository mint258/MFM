"""CPU mechanism/algebra tests, NOT native20/500 or CUDA capacity acceptance."""
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
import json
import random
import numpy as np
import pytest
import torch
from torch_geometric.data import Batch, Data
from phychem_mfm.model.v3_performance import PerformanceOptions, build_performance_model, performance_forward_pretrain
from phychem_mfm.model.v3_logical_batch import LogicalBatchBackbone, LogicalBatchPadding, chunk_plan
from phychem_mfm.phase1.v3_structural import StructuralViewConfig, build_structural_views

ROOT=Path(__file__).resolve().parents[2]
PADDING={"atom_bucket_width":2,"max_graphs_per_chunk":1,"max_padded_cost_per_chunk":16}


@pytest.fixture(autouse=True)
def one_cpu_thread():
    before=torch.get_num_threads();torch.set_num_threads(1)
    try:yield
    finally:torch.set_num_threads(before)


def config():
    return {"architecture":{"preset":"shared_light"},
            "backbone":{"dim":16,"layers":2,"heads":4,"ff_mult":2,"activation_checkpointing":True},
            "head":{"profile":"phase1","geometry_head":"equivariant_noise","geometry_hidden_dim":8,
                    "geometry_rbf_count":4,"geometry_message_layers":0,"geometry_pair_chunk_size":64}}


def packed():
    generator=torch.Generator().manual_seed(341)
    return Batch.from_data_list([Data(x=torch.full((n,1),5,dtype=torch.long),
        pos=torch.randn(n,3,generator=generator)*.5) for n in (1,3,7)])


def test_default_config_state_keys_and_constructor_rng_stay_unchanged():
    options=PerformanceOptions(distance_pair_rows=64)
    original_fields={"precision","distance_implementation","distance_pair_rows","distance_checkpointing",
        "backbone_checkpointing","head_checkpointing","attention_backend","sparse_query_chunk",
        "fused_adamw","tf32","compile_backbone","compile_dynamic"}
    assert set(asdict(options))==original_fields
    torch.manual_seed(17);legacy=build_performance_model(config(),options);rng=torch.get_rng_state().clone()
    torch.manual_seed(17);candidate=build_performance_model(config(),options,execution={"padding":PADDING})
    assert torch.equal(rng,torch.get_rng_state())
    assert legacy.v3_performance_options==asdict(options)==candidate.v3_performance_options
    assert not hasattr(legacy,"v3_performance_execution")
    assert type(legacy.backbone).__name__=="RealCoordTransformerBackbone"
    assert isinstance(candidate.backbone,LogicalBatchBackbone)
    assert tuple(legacy.state_dict())==tuple(candidate.state_dict())
    for key in legacy.state_dict():assert torch.equal(legacy.state_dict()[key],candidate.state_dict()[key])


def test_real_constructor_and_forward_restore_rows_padding_values_and_every_gradient():
    torch.manual_seed(12);left=build_performance_model(config(),PerformanceOptions(distance_pair_rows=64))
    torch.manual_seed(12);right=build_performance_model(config(),PerformanceOptions(distance_pair_rows=64),execution={"padding":PADDING})
    batch=packed();before={key:value.clone() for key,value in batch.to_dict().items() if isinstance(value,torch.Tensor)}
    rng=torch.get_rng_state().clone()
    batch.pos.requires_grad_(True);outputs=[];position_gradients=[]
    for model in (left,right):
        batch.pos.grad=None
        output=performance_forward_pretrain(model,batch,("element","geometry"))
        loss=output.atom_repr.square().mean()+output.element_logits.square().mean()+output.noise_pred.square().mean()
        loss.backward();outputs.append(output);position_gradients.append(batch.pos.grad.detach().clone())
        assert torch.equal(rng,torch.get_rng_state())
    torch.testing.assert_close(position_gradients[0],position_gradients[1],atol=3e-6,rtol=2e-4)
    for key in ("atom_repr","graph_repr","element_logits","noise_pred","coordinate_pred","node_mask"):
        a,b=getattr(outputs[0],key),getattr(outputs[1],key)
        if a.dtype==torch.bool:assert torch.equal(a,b)
        else:torch.testing.assert_close(a,b,atol=3e-6,rtol=3e-5)
    for (an,a),(bn,b) in zip(left.named_parameters(),right.named_parameters()):
        assert an==bn and (a.grad is None)==(b.grad is None)
        if a.grad is not None:torch.testing.assert_close(a.grad,b.grad,atol=3e-6,rtol=2e-4)
    assert all(torch.equal(value,batch[key]) for key,value in before.items())
    receipt=right.backbone.last_logical_batch_execution
    assert receipt["graph_atom_counts"]==[1,3,7] and receipt["logical_atom_count"]==11
    assert receipt["chunked_dense_padded_cost"]<receipt["legacy_dense_padded_cost"]
    assert receipt["retained_oversize_singletons"]==1
    assert receipt["original_atom_and_graph_order_restored"] and not receipt["views_noise_masks_targets_regenerated"]
    assert not receipt["loss_or_group_reduction_per_chunk"]


def test_model_configuration_opt_in_uses_same_actual_constructor():
    payload=config();payload["performance_execution_v1"]={"padding":PADDING}
    model=build_performance_model(payload)
    assert isinstance(model.backbone,LogicalBatchBackbone)
    assert model.encode_atoms(packed()).shape==(11,16)
    assert "performance_execution_v1" in payload
    with pytest.raises(ValueError,match="exactly once"):
        build_performance_model(payload,execution={"padding":PADDING})


@pytest.mark.parametrize("sizes",[(1,),(7,1,4,4,2),(19,2,1,7)])
def test_chunk_plan_preserves_all_graphs_singletons_and_stable_ties(sizes):
    specification=LogicalBatchPadding(**PADDING)
    plan=chunk_plan(list(sizes),specification)
    assert sorted(g for group in plan for g in group)==list(range(len(sizes)))
    assert plan==chunk_plan(list(sizes),specification)
    assert sum(len(group)*max(sizes[g] for g in group)**2 for group in plan)<=len(sizes)*max(sizes)**2


@pytest.mark.parametrize("bad",["empty","hole","unordered"])
def test_empty_and_invalid_packed_orders_reject_without_rng_or_input_mutation(bad):
    model=build_performance_model(config(),execution={"padding":PADDING})
    batch=packed()
    if bad=="empty":batch=Data(x=torch.empty(0,1,dtype=torch.long),pos=torch.empty(0,3),batch=torch.empty(0,dtype=torch.long))
    elif bad=="hole":batch.batch[batch.batch==1]=2
    else:batch.batch=torch.flip(batch.batch,(0,))
    rng=torch.get_rng_state().clone();source=batch.x.clone()
    with pytest.raises(ValueError,match="logical batch|contiguous|packed graph"):
        model.encode_atoms(batch)
    assert torch.equal(rng,torch.get_rng_state()) and torch.equal(source,batch.x)


def test_dropout_rejected_before_construction_rng_and_later_runtime_changes():
    bad=config();bad["backbone"]["dropout"]=.2
    rng=torch.get_rng_state().clone()
    with pytest.raises(ValueError,match="dropout"):
        build_performance_model(bad,execution={"padding":PADDING})
    assert torch.equal(rng,torch.get_rng_state())
    model=build_performance_model(config(),execution={"padding":PADDING})
    net=model.backbone.layers[0].ffn.net
    # The original zero-dropout DenseFFN uses Identity; setting Identity.p
    # merely creates an unused attribute and does not test stochastic behavior.
    assert isinstance(net[2],torch.nn.Identity)
    net[2]=torch.nn.Dropout(.2)
    dropout=net[2]
    assert isinstance(dropout,torch.nn.modules.dropout._DropoutNd) and dropout.p==.2
    assert model.training and dropout.training
    assert any(module is dropout for module in model.backbone.modules())
    rng=torch.get_rng_state().clone()
    # Prove the fixture is active dropout, preserving the caller's CPU RNG.
    # Use an explicit CPU Generator state, without touching CUDA RNG streams.
    with torch.random.fork_rng(devices=[]):
        torch.set_rng_state(torch.Generator(device="cpu").manual_seed(1742).get_state())
        probe=torch.ones(256,dtype=torch.float32,device="cpu")
        probe_rng=torch.get_rng_state().clone()
        sampled=dropout(probe)
        assert not torch.equal(probe_rng,torch.get_rng_state())
        assert not torch.equal(sampled,probe)
    assert torch.equal(rng,torch.get_rng_state())
    batch=packed()
    with pytest.raises(ValueError,match="RNG"):
        model.encode_atoms(batch)
    assert torch.equal(rng,torch.get_rng_state())


@pytest.mark.parametrize("masked", [False, True])
def test_finished_three_views_original_noise_masks_and_global_field_counts(monkeypatch, masked):
    from test_model_v3_structural import setup_model
    from phychem_mfm.training.losses import LossWeights
    monkeypatch.syspath_prepend(str(ROOT/"tools/model_v3"))
    from a_execution_runtime import corpus_receipt
    left,base,registry,binding,norms,targets=setup_model();right=deepcopy(left)
    right.encoder.backbone=LogicalBatchBackbone(right.encoder.backbone,padding=LogicalBatchPadding(**PADDING))
    views=build_structural_views(base,ordinals=(10,11),config=StructuralViewConfig(seed=99))
    corpus=SimpleNamespace(native_atom_counts=(12,12),record_keys=("synthetic0","synthetic1"),
                           logical_indices=(0,1),encoder_batch=views.batch)
    source=corpus_receipt(corpus);rng=torch.get_rng_state().clone();results=[]
    masks=None
    if masked:
        masks={"element":torch.arange(24)%2==0,"noise":torch.arange(24)<12,
               "bond":torch.zeros(24,dtype=torch.bool)}
    for model in (left,right):
        prediction=model.forward_pretrain(views,enabled_groups=("S","D","P"))
        total=model.compute_loss(prediction,views,targets,norms,enabled_groups=("S","D","P"),
                                 weights=LossWeights(),atom_eligibility=masks,exposure_step=0)
        total.total.backward();results.append(total)
        assert torch.equal(rng,torch.get_rng_state())
    assert results[0].counts==results[1].counts
    if masked:assert results[0].counts["s_bond"]==0
    else:assert all(value>0 for value in results[0].counts.values())
    for (an,a),(bn,b) in zip(left.named_parameters(),right.named_parameters()):
        assert an==bn and (a.grad is None)==(b.grad is None)
        if a.grad is not None:torch.testing.assert_close(a.grad,b.grad,atol=5e-6,rtol=3e-4)
    assert results[0].observed_fields==results[1].observed_fields
    torch.testing.assert_close(results[0].total,results[1].total,atol=3e-6,rtol=3e-5)
    assert corpus_receipt(corpus)==source
    assert views.batch.sample_type_id.tolist()==[0,1,2,0,1,2]


def make_integrated_trainer(*,tracker=None,padding=None):
    from test_model_v3_trainer import make_trainer
    from phychem_mfm.phase1.v3_trainer import V3StepTrainer
    original=make_trainer(tracker=tracker,probe_interval=500)
    for module in original.model.modules():
        if isinstance(module,torch.nn.modules.dropout._DropoutNd):module.p=0.
    original.model.encoder.backbone=LogicalBatchBackbone(original.model.encoder.backbone,
        padding=LogicalBatchPadding(**(PADDING if padding is None else padding)))
    base_keys=("code_sha","configuration_sha256","registry_sha256","normalization_sha256","data_version")
    return V3StepTrainer(original.model,original.optimizer,original.scheduler,original.sampler,original.clock,
        original.provider,original.normalizations,original.weights,original.tracker,
        {key:original.bindings[key] for key in base_keys},enabled_groups=original.groups,
        gradient_probe_interval=500,probe_samples=1,allow_unit_tracker=True)


def test_actual_step_trainer_checkpoint_resume_keeps_source_cursor_rng_and_optimizer(tmp_path):
    from test_model_v3_trainer import UnitTracker
    from test_model_v3_training import assert_tree_equal
    from phychem_mfm.phase1.v3_training import capture_rng_state
    random.seed(17);np.random.seed(17);torch.manual_seed(17)
    original=make_integrated_trainer();original.next_step(2)
    checkpoint=tmp_path/"resume";original.save(checkpoint,output_root=tmp_path)
    saved_rng=capture_rng_state();trace_start=len(original.provider.trace)
    # Truly speculative sampler choices are not committed and cannot move resume.
    ahead=[original.sampler.choice(i) for i in range(original.clock.samples_consumed,6)]
    assert original.sampler.samples_consumed==original.clock.samples_consumed
    original.run(max_batch_samples=3,checkpoint_root=tmp_path)
    expected=(deepcopy(original.model.state_dict()),deepcopy(original.optimizer.state_dict()),
              original.clock.state_dict(),deepcopy(original.provider.state_dict()),capture_rng_state())
    restored=make_integrated_trainer(tracker=UnitTracker("unit-resumed"))
    restored.load(checkpoint,output_root=tmp_path);assert_tree_equal(saved_rng,capture_rng_state())
    assert [restored.sampler.choice(i) for i in range(restored.clock.samples_consumed,6)]==ahead
    fresh=tmp_path/"continued";fresh.mkdir();restored.run(max_batch_samples=3,checkpoint_root=fresh)
    assert_tree_equal(expected[0],restored.model.state_dict());assert_tree_equal(expected[1],restored.optimizer.state_dict())
    assert_tree_equal(expected[2],restored.clock.state_dict());assert_tree_equal(expected[3],restored.provider.state_dict())
    assert_tree_equal(expected[4],capture_rng_state())
    assert_tree_equal(original.provider.trace[trace_start:],restored.provider.trace)


def test_resume_refuses_changed_padding_contract_before_weights_rng_or_cursor(tmp_path):
    from test_model_v3_trainer import UnitTracker
    from test_model_v3_training import assert_tree_equal
    from phychem_mfm.phase1.v3_training import capture_rng_state
    original=make_integrated_trainer();original.next_step(2);original.save(tmp_path/"resume",output_root=tmp_path)
    restored=make_integrated_trainer(tracker=UnitTracker("unit-resumed"),padding={**PADDING,"atom_bucket_width":7})
    before=(deepcopy(restored.model.state_dict()),capture_rng_state(),restored.clock.state_dict())
    with pytest.raises(ValueError,match="binding|contract|execution|configuration"):
        restored.load(tmp_path/"resume",output_root=tmp_path)
    assert_tree_equal(before[0],restored.model.state_dict());assert_tree_equal(before[1],capture_rng_state())
    assert_tree_equal(before[2],restored.clock.state_dict())
