"""Engineering metadata/ordinary CPU tensor checks; not actual D3 or physical acceptance."""
from copy import deepcopy
from dataclasses import asdict, replace
import hashlib
import json

import pytest
import torch
from torch import nn
from torch_geometric.data import Batch, Data

from phychem_mfm.phase1.v3_contract import FieldSpec, LabelRegistry, FieldTarget, TrainNormalization, canonical_hash
from phychem_mfm.phase1.v3_physical_policy import (
    PhysicalLossPolicy, physical_policy_for_release, LOSS_DISABLED_PHYSICAL,
    TENSOR_SELECTOR, CHARGE_SELECTOR, POLICY_SCHEMA, POLICY_STATUS)
from phychem_mfm.phase1.v3_losses import compute_v3_loss
from phychem_mfm.phase1.v3_training import ValidationAccumulator, SampleClock
from phychem_mfm.phase1.v3_structural import StructuralFieldBinding, build_structural_views, combine_structural_loss
from phychem_mfm.phase1.v3_label_domains import Tensor6Inputs, tensor6_from_f64
from phychem_mfm.phase1.v3_trainer import V3StepTrainer, SampleLRScheduler, PreparedV3Batch
from phychem_mfm.phase1.v3_sampling import InMemorySamplingIndex, MoleculeEntry, ConformerRef, UniformMoleculeSampler
from phychem_mfm.model.v3_multiview import V3MultiViewModel
from phychem_mfm.model.v3_heads import V3HeadBank
from test_model_v3_typed_heads_integration import TinyRoutingEncoder, QFRAME, REF
from test_model_v3_trainer import UnitTracker
from test_model_v3_loss_readiness import loss_case, disabled
from phychem_mfm.training.losses import LossWeights


@pytest.fixture(autouse=True)
def isolated_cpu():
    old = torch.get_num_threads()
    with torch.random.fork_rng(devices=[]):
        torch.set_num_threads(1)
        try: yield
        finally: torch.set_num_threads(old)


def policy_document():
    return {"UNIT_FIXTURE_ONLY_NOT_REAL_AUTHORITY": True, "schema": POLICY_SCHEMA, "status": POLICY_STATUS,
        "contract_version": "v3.0", "reviewer": "root", "global_physical_PASS": False,
        "Model_same_version_ACK": False, "original_numerical_accuracy_and_thresholds_unchanged": True,
        "user_choices_1_to_4_unchanged": True, "xtb_singlepoint_rules": [
            {"selector": CHARGE_SELECTOR, "training_exposure": "DISABLED_PER_USER_5A_FALLBACK",
             "original_values_component_masks_reasons_preserved": True, "new_numeric_mask": False},
            {"selector": TENSOR_SELECTOR, "loss_status": LOSS_DISABLED_PHYSICAL,
             "reason": "UNIT_SAME_POLICY_NOT_ACTUAL_QM_EVIDENCE", "sampling_molecules_changed": False,
             "diagnostic_PASS_samples_not_selected_for_training": True,
             "components_values_masks_reasons_and_F64_retained": True,
             "scale_unbound_status_remains_separate": "LOSS_DISABLED_SCALE_UNBOUND_OR_DEGENERATE",
             "other_ready_targets_continue": True}]}


def make_policy(tmp_path, *, change=None, target="unit-q"):
    body = policy_document()
    if change: change(body)
    path = tmp_path / ("physical_" + hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()[:12] + ".json")
    raw = (json.dumps(body, sort_keys=True, allow_nan=False) + "\n").encode()
    if path.exists(): assert path.read_bytes() == raw
    else: path.write_bytes(raw)
    return PhysicalLossPolicy({"path": str(path), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()},
        {"q": {"registry_id": 674, "target_id": target, "task": "xtb_singlepoint", "condition": "unit-condition"}},
        engineering_only=True)


def test_legal_scale_and_source_values_masks_are_preserved_and_ready_parameter_updates(tmp_path):
    registry, predictions, targets, norms = loss_case(tmp_path)
    norms["q"] = TrainNormalization((0.,), (2.,), "b"*64, registry.version)
    before = (targets["q"].values.clone(), targets["q"].component_valid.clone(), deepcopy(asdict(norms["q"])))
    result = compute_v3_loss(predictions, targets, registry, norms, enabled_groups=("P",), physical_policy=make_policy(tmp_path))
    assert result.counts == {"q": 2, "ready": 2} and result.loss_counts == {"q": 0, "ready": 2}
    assert result.loss_status["q"] == LOSS_DISABLED_PHYSICAL and result.scale_status["q"] == "READY"
    assert result.metrics()["loss/q"] is None and result.metrics()["loss/ready"] > 0
    optimizer = torch.optim.SGD(predictions.values(), lr=.1)
    original = predictions["ready"].detach().clone()
    result.total.backward(); optimizer.step()
    assert predictions["q"].grad is None and not torch.equal(predictions["ready"], original)
    assert torch.equal(targets["q"].values, before[0]) and torch.equal(targets["q"].component_valid, before[1])
    assert asdict(norms["q"]) == before[2] and result.audit_counts["q"]["source_valid_components"] == 12
    assert result.audit_counts["q"]["excluded_physical_policy_tensors"] == 2


def test_physical_and_scale_disabled_axes_are_distinct_even_when_both_apply(tmp_path):
    registry, predictions, targets, norms = loss_case(tmp_path)
    result = compute_v3_loss(predictions, targets, registry, norms, enabled_groups=("P",), physical_policy=make_policy(tmp_path))
    assert result.loss_status["q"] == result.physical_status["q"] == LOSS_DISABLED_PHYSICAL
    assert result.scale_status["q"] == norms["q"].status and result.scale_reasons["q"] == "ZERO"
    assert result.metrics()["scale_disabled_reason/q"] == "ZERO" and not hasattr(norms["q"], "scale")


def test_validation_keeps_raw_population_and_independent_loss_denominators(tmp_path):
    registry, predictions, targets, norms = loss_case(tmp_path)
    norms["q"] = TrainNormalization((0.,), (2.,), "b"*64, registry.version)
    result = compute_v3_loss(predictions, targets, registry, norms, enabled_groups=("P",), physical_policy=make_policy(tmp_path))
    metric = ValidationAccumulator(registry, role="VAL", enabled_groups=("P",))
    metric.add(predictions, targets, result); metric.add(predictions, targets, result)
    q = metric.result()["fields"]["q"]
    assert q["valid_labels"] == 4 and q["loss_count"] == 0 and q["loss"] is None
    assert q["loss_status"] == LOSS_DISABLED_PHYSICAL and q["scale_status"] == "READY"
    assert q["MAE"] > 0 and q["Frobenius_SSE"] > 0


def test_structural_combination_preserves_policy_and_original_group_denominator(tmp_path):
    registry, predictions, targets, norms = loss_case(tmp_path)
    loss = compute_v3_loss(predictions, targets, registry, norms, enabled_groups=("P",), physical_policy=make_policy(tmp_path))
    combined = combine_structural_loss(loss, {"s": torch.tensor(2., requires_grad=True)}, {"s": 3}, enabled_groups=("S","P"))
    assert combined.loss_counts["s"] == 3 and combined.physical_status["s"] == "NOT_TARGETED_BY_BOUND_PHYSICAL_POLICY"
    assert combined.loss_status["q"] == LOSS_DISABLED_PHYSICAL and combined.physical_policy_sha256 == loss.physical_policy_sha256
    torch.testing.assert_close(combined.total, (combined.groups["S"] + combined.groups["P"]) / 2)


def test_default_result_serialization_and_metrics_have_no_physical_keys(tmp_path):
    registry, predictions, targets, norms = loss_case(tmp_path)
    norms["q"] = TrainNormalization((0.,), (2.,), "b"*64, registry.version)
    with torch.no_grad(): result = compute_v3_loss(predictions, targets, registry, norms, enabled_groups=("P",))
    assert result.physical_policy_sha256 is None
    assert set(asdict(result)) == {"total","fields","groups","counts","observed_fields","enabled_groups","audit_counts"}
    assert not any(k.startswith(("physical_", "physical_status/", "scale_status/")) for k in result.metrics())


@pytest.mark.parametrize("change", [
    lambda d:d.update(global_physical_PASS=True),
    lambda d:d.update(Model_same_version_ACK=True),
    lambda d:d.update(schema="fabricated_release"),
    lambda d:d["xtb_singlepoint_rules"][1].update(loss_status="NO_VALID_LABELS"),
    lambda d:d["xtb_singlepoint_rules"][1].update(scale_unbound_status_remains_separate=LOSS_DISABLED_PHYSICAL),
    lambda d:d["xtb_singlepoint_rules"][0].update(new_numeric_mask=True),
])
def test_unknown_policy_or_false_pass_or_merged_state_or_new_mask_refuses(tmp_path, change):
    with pytest.raises(ValueError): make_policy(tmp_path, change=change)


def test_unit_policy_cannot_be_promoted_by_constructor_or_replace(tmp_path):
    policy = make_policy(tmp_path)
    with pytest.raises(ValueError, match="exact actual Data"): replace(policy, engineering_only=False)
    with pytest.raises(ValueError, match="exact actual Data"):
        PhysicalLossPolicy(policy.reference, policy.targets, engineering_only=False)
    assert policy.projection["release_authority_granted"] is False


def test_policy_raw_hash_and_target_identity_are_strict(tmp_path):
    policy = make_policy(tmp_path)
    with pytest.raises(ValueError): PhysicalLossPolicy({**policy.reference, "sha256":"f"*64}, policy.targets, True)
    with pytest.raises(ValueError): replace(policy, targets={"q":{**policy.targets["q"],"registry_id":True}})
    with pytest.raises(ValueError): replace(policy, targets={"q":{**policy.targets["q"],"task":"guess_task"}})


def test_unknown_active_origin_sensitive_field_holds_but_inactive_does_not_disable_scalar(tmp_path):
    policy = make_policy(tmp_path)
    registry = LabelRegistry((FieldSpec("q","P","q","graph",representation="symmetric_tensor6"),
        FieldSpec("v","P","dipole","graph",representation="vector"), FieldSpec("ready","D","d","graph")),
        "unit","a"*64)
    policy.validate_for_registry(registry, enabled_fields=("q","ready"))
    with pytest.raises(ValueError, match="QM-charge"): policy.validate_for_registry(registry, enabled_fields=("v",))


def test_same_version_joint_must_explicitly_bind_the_physical_policy(tmp_path):
    from test_model_v3_data_adapter import metadata_case
    from phychem_mfm.phase1.v3_data_adapter import verify_release_binding
    evidence, request, projection, interpreter = metadata_case(tmp_path)
    release = verify_release_binding(request, evidence=evidence, verifier=interpreter(projection))
    registry, _, _, _ = loss_case(tmp_path)
    with pytest.raises(ValueError, match="joint contract"):
        physical_policy_for_release(release, registry, make_policy(tmp_path).reference)
    assert release.is_actual_data_release is False


VERSION = "UNIT_PHYSICAL_POLICY_NOT_D3"
class UnitProvider:
    read_only = node_local = True
    omit_q_numeric_inputs = False
    data_version, source_sha256 = VERSION, "f"*64
    def prepare(self, choices, *, role, view_config, enabled_groups, enabled_fields):
        records = [Data(x=torch.tensor([[0],[1]]), pos=torch.tensor([[0.,0.,0.],[.5,.2,.1]])) for _ in choices]
        views = build_structural_views(Batch.from_data_list(records), ordinals=tuple(c.ordinal for c in choices),
                                       config=view_config, include_structural=False)
        ids = tuple(c.conformer_id for c in choices); n = len(ids)
        q = tensor6_from_f64(values=torch.ones(n,6,dtype=torch.float64), component_valid=torch.ones(n,6,dtype=torch.bool),
            geometry_ids=ids, component_geometry_ids=tuple((g,)*6 for g in ids), reasons=tuple({} for _ in ids), source_ref=REF)
        targets = {"q":q, "ready":FieldTarget(torch.ones(n,1),torch.ones(n,dtype=torch.bool))}
        return PreparedV3Batch(tuple(choices),views,targets,self.source_sha256,VERSION,role,
            domain_inputs={} if self.omit_q_numeric_inputs else {"q":Tensor6Inputs(torch.zeros(n,3),ids,(REF,)*n,QFRAME)},
            geometry_context={"geometry_ids":ids,"geometry_bindings":(REF,)*n,"native_atom_counts":(2,)*n})
    def close(self): pass


def make_trainer(policy, *, only_q=False, provider_policy=None, omit_q_numeric_inputs=False):
    torch.manual_seed(77)
    pd_fields = (FieldSpec("q","P","q","graph",representation="symmetric_tensor6"),
                 FieldSpec("ready","P","p","graph"))
    s_fields = (FieldSpec("s_element","S","s","atom",kind="classification",classes=119),
                FieldSpec("s_noise","S","s","atom",kind="denoise_eps_mse",representation="vector"),
                FieldSpec("s_bond","S","s","pair",kind="classification",classes=5))
    pd_registry = LabelRegistry(pd_fields,VERSION,"a"*64)
    registry = replace(pd_registry, fields=s_fields+pd_fields)
    heads = V3HeadBank(pd_registry,dim=512,hidden_dim=8,domain_head_configs={
        "q":{"origin_policy":"explicit_comoving","frame_binding":QFRAME}})
    model = V3MultiViewModel(TinyRoutingEncoder(),heads,registry,StructuralFieldBinding("s_element","s_noise","s_bond"))
    norms = {name:TrainNormalization((0.,),(2.,),"b"*64,VERSION) for name in ("q","ready")}
    index = InMemorySamplingIndex(tuple(MoleculeEntry("m"+str(i),(ConformerRef("c"+str(i),0,2,(("PM7","unit"),)),),
        (("S",True),("D",True),("P",True)),(("s",True),("q",True),("p",True))) for i in range(2)),VERSION)
    sampler = UniformMoleculeSampler(index,seed=0,sample_budget=4)
    optimizer = torch.optim.AdamW(model.parameters(),lr=.001,weight_decay=0.,foreach=False)
    scheduler = SampleLRScheduler(optimizer,sample_budget=4)
    bindings = {"code_sha":"c"*40,"configuration_sha256":"d"*64,"registry_sha256":registry.source_sha256,
                "normalization_sha256":canonical_hash({k:asdict(v) for k,v in norms.items()}),"data_version":VERSION}
    provider = UnitProvider()
    provider.omit_q_numeric_inputs = omit_q_numeric_inputs
    if provider_policy is not None: provider.physical_policy = provider_policy
    return V3StepTrainer(model,optimizer,scheduler,sampler,SampleClock(4,(2,4)),provider,norms,
        LossWeights(),UnitTracker("physical-unit"),bindings,
        enabled_groups=("P",),enabled_fields=("q",) if only_q else None,allow_unit_tracker=True,
        physical_policy=policy)


def test_real_trainer_updates_ready_head_and_checkpoint_binds_policy_before_mutation(tmp_path):
    from test_model_v3_training import assert_tree_equal
    policy = make_policy(tmp_path)
    trainer = make_trainer(policy,omit_q_numeric_inputs=True)
    qhead = trainer.model.pd_heads.field_heads[trainer.model.pd_heads.keys["q"]]
    before = deepcopy(qhead.state_dict())
    readyhead = trainer.model.pd_heads.field_heads[trainer.model.pd_heads.keys["ready"]]
    before_ready = [p.detach().clone() for p in readyhead.parameters()]
    def forbidden_head(module, args): raise AssertionError("Physically disabled head must not run")
    handle = qhead.register_forward_pre_hook(forbidden_head)
    try: row = trainer.next_step(2)
    finally: handle.remove()
    assert any(not torch.equal(p, old) for p, old in zip(readyhead.parameters(),before_ready))
    assert row["metric_status/q"] == "LOSS_DISABLED_NO_PREDICTION"
    assert row["optimizer_updated"] and row["valid_count/q"] == 2 and row["loss_count/q"] == 0
    assert row["loss_status/q"] == LOSS_DISABLED_PHYSICAL and row["scale_status/q"] == "READY"
    assert all(p.grad is None for p in qhead.parameters()); assert_tree_equal(before,qhead.state_dict())
    trainer.save(tmp_path/"cp2",output_root=tmp_path)
    restored = make_trainer(policy)
    restored.load(tmp_path/"cp2",output_root=tmp_path)
    assert_tree_equal(trainer.model.state_dict(),restored.model.state_dict())
    assert restored.contract["physical_loss_policy"] == policy.projection
    changed = make_trainer(make_policy(tmp_path,target="different-unit-target"))
    unchanged = deepcopy(changed.model.state_dict())
    with pytest.raises(ValueError,match="binding|configuration"): changed.load(tmp_path/"cp2",output_root=tmp_path)
    assert_tree_equal(unchanged,changed.model.state_dict())


def test_all_physically_disabled_keeps_source_clock_without_fake_optimizer_update(tmp_path):
    trainer = make_trainer(make_policy(tmp_path),only_q=True,omit_q_numeric_inputs=True)
    row = trainer.next_step(2)
    assert row["valid_count/q"] == 2 and row["loss_count/q"] == 0 and row["loss/total"] is None
    assert row["loss_status/q"] == LOSS_DISABLED_PHYSICAL and not row["optimizer_updated"]
    assert trainer.clock.samples_consumed == 2 and trainer.clock.optimizer_updates == 0
    assert not trainer.optimizer.state and all(p.grad is None for p in trainer.model.parameters())


def test_default_state_and_parameter_bytes_are_independent_of_optin_policy(tmp_path):
    from test_model_v3_training import assert_tree_equal
    original, physical = make_trainer(None), make_trainer(make_policy(tmp_path))
    assert "physical_loss_policy" not in original.contract
    assert_tree_equal(original.model.state_dict(),physical.model.state_dict())
    assert asdict(original.normalizations["q"]) == asdict(physical.normalizations["q"])
    assert original.model.encode_atoms.__func__ is physical.model.encode_atoms.__func__


@pytest.mark.parametrize("bad", ["missing", "underflow"])
def test_physical_disable_does_not_relabel_absent_or_unusable_scale_as_ready(tmp_path, bad):
    registry, predictions, targets, norms = loss_case(tmp_path)
    if bad == "missing": norms.pop("q")
    else: norms["q"] = TrainNormalization((0.,),(1e-100,),"b"*64,registry.version)
    with pytest.raises(ValueError, match="scale"):
        compute_v3_loss(predictions,targets,registry,norms,enabled_groups=("P",),physical_policy=make_policy(tmp_path))


def test_provider_bound_policy_cannot_be_omitted_or_replaced_at_trainer_constructor(tmp_path):
    policy = make_policy(tmp_path)
    with pytest.raises(ValueError,match="provider physical policy"):
        make_trainer(None,provider_policy=policy)
    with pytest.raises(ValueError,match="provider physical policy"):
        make_trainer(make_policy(tmp_path,target="different-unit-target"),provider_policy=policy)
    trainer = make_trainer(policy,provider_policy=policy)
    assert trainer.contract["physical_loss_policy"] == policy.projection


def test_source_only_collate_retains_tensor_without_origin_but_cannot_grant_loss_readiness(tmp_path):
    from phychem_mfm.phase1.v3_data import DecodedSample, collate_v3_samples
    from phychem_mfm.phase1.v3_losses import loss_prediction_fields
    from phychem_mfm.phase1.v3_precision_experiment import PrecisionValidationAccumulator
    registry, _, _, norms = loss_case(tmp_path)
    norms["q"] = TrainNormalization((0.,),(2.,),"b"*64,registry.version)
    q = tensor6_from_f64(values=torch.ones(1,6,dtype=torch.float64),
        component_valid=torch.ones(1,6,dtype=torch.bool),geometry_ids=("g0",),
        component_geometry_ids=(("g0",)*6,),reasons=({},),source_ref=REF)
    sample = DecodedSample("m0","g0","PM7",torch.tensor([[0],[1]]),torch.zeros(2,3),
        torch.tensor([0,1]),{"q":q,"ready":FieldTarget(torch.ones(1,1),torch.ones(1,dtype=torch.bool))},
        geometry_ref=REF)
    index = InMemorySamplingIndex((MoleculeEntry("m0",(ConformerRef("g0",0,2,(("PM7","unit"),)),),
        (("S",True),("D",True),("P",True)),(("physics",True),)),),registry.version)
    choice = UniformMoleculeSampler(index,seed=0,sample_budget=1).choice(0)
    with pytest.raises(ValueError,match="domain inputs"):
        collate_v3_samples(((choice,sample),),registry)
    batch = collate_v3_samples(((choice,sample),),registry,loss_disabled_fields=("q",))
    assert "q" not in batch.domain_inputs
    assert torch.equal(batch.targets["q"].values,q.values)
    assert torch.equal(batch.targets["q"].component_valid,q.component_valid)
    policy = make_policy(tmp_path)
    assert loss_prediction_fields(registry,norms,enabled_groups=("P",),physical_policy=policy) == ("ready",)
    predictions = {"ready":nn.Parameter(torch.zeros(1,1))}
    loss = compute_v3_loss(predictions,batch.targets,registry,norms,enabled_groups=("P",),physical_policy=policy)
    metric = PrecisionValidationAccumulator(registry,role="VAL",enabled_groups=("P",))
    metric.add(predictions,batch.targets,loss)
    report = metric.result()["fields"]["q"]
    assert report["valid_labels"] == 1 and report["loss_count"] == 0
    assert report["MAE"] is report["RMSE"] is report["Frobenius_SSE"] is None
    assert report["prediction_status"] == "LOSS_DISABLED_NO_PREDICTION"
    with pytest.raises(ValueError,match="real prediction"):
        compute_v3_loss(predictions,batch.targets,registry,norms,enabled_groups=("P",))


def test_scale_disabled_r73_missing_numeric_frame_skips_head_without_inventing_prediction(tmp_path):
    from model_v3_typed_fixture import ordered_target
    from phychem_mfm.phase1.v3_losses import loss_prediction_fields
    target = ordered_target()
    target = replace(target,inputs=replace(target.inputs,frame_origin=None,frame_basis=None))
    registry = LabelRegistry((FieldSpec("r","D","r73","ordered_entry"),
        FieldSpec("p","P","p","graph")),"UNIT_R73_DISABLED","a"*64)
    bank = V3HeadBank(registry,dim=4,hidden_dim=8,domain_head_configs={"r":{
        "codebook":target.inputs.codebook,"frame_binding":target.inputs.frame_binding,"channel_dim":2}})
    norms = {"r":disabled(tmp_path,name="r",version=registry.version),
        "p":TrainNormalization((0.,),(1.,),"b"*64,registry.version)}
    names = loss_prediction_fields(registry,norms,enabled_groups=("D","P"))
    assert names == ("p",) and target.inputs.frame_origin is None and target.inputs.frame_basis is None
    def forbidden_head(module, args): raise AssertionError("Scale-disabled r73 head must not run")
    handle = bank.field_heads[bank.keys["r"]].register_forward_pre_hook(forbidden_head)
    optimizer = torch.optim.SGD(bank.parameters(),lr=.1)
    before = [p.detach().clone() for p in bank.field_heads[bank.keys["p"]].parameters()]
    try:
        predictions = bank(torch.ones(2,4),torch.zeros(2,dtype=torch.long),torch.zeros(2,3),
            enabled_groups=("D","P"),enabled_fields=names)
    finally: handle.remove()
    targets = {"r":target,"p":FieldTarget(torch.ones(1,1),torch.ones(1,dtype=torch.bool))}
    loss = compute_v3_loss(predictions,targets,registry,norms,enabled_groups=("D","P"))
    assert set(predictions) == {"p"} and loss.counts["r"] == int(target.valid.sum()) and loss.loss_counts["r"] == 0
    loss.total.backward();optimizer.step()
    assert all(p.grad is None for p in bank.field_heads[bank.keys["r"]].parameters())
    assert any(not torch.equal(p, old) for p,old in zip(bank.field_heads[bank.keys["p"]].parameters(),before))


def test_checked_reader_source_only_branch_keeps_unknown_origin_without_authorizing_ready_head(tmp_path):
    from types import SimpleNamespace
    from phychem_mfm.phase1.v3_data import DecodedSample
    from phychem_mfm.phase1.v3_data_adapter import _CheckedReader
    q = tensor6_from_f64(values=torch.ones(1,6,dtype=torch.float64),
        component_valid=torch.ones(1,6,dtype=torch.bool),geometry_ids=("g0",),
        component_geometry_ids=(("g0",)*6,),reasons=({},),source_ref=REF)
    sample = DecodedSample("m0","g0","PM7",torch.tensor([[0],[1]]),torch.zeros(2,3),
        torch.tensor([0,1]),{"q":q},geometry_ref=REF)
    class Reader:
        def read(self, choice): return sample
        def close(self): pass
    binding = {k:QFRAME[k] for k in ("target_id","condition","unit","sign","frame","origin_policy")}
    release = SimpleNamespace(projection={"targets":{"q":binding},"D4_bindings":{"q":{}}},
        evidence={"joint_contract":QFRAME["joint_policy"]})
    choice = SimpleNamespace(conformer_id="g0")
    with pytest.raises(ValueError,match="source-origin"):
        _CheckedReader(Reader(),release).read(choice)
    assert _CheckedReader(Reader(),release,("q",)).read(choice) is sample
    assert not sample.domain_inputs and sample.fields["q"] is q
