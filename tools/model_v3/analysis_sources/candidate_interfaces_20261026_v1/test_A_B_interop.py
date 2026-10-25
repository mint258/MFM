"""Actual pinned DataB projector -> A -> B -> original v3 trainer, synthetic only.

Run only after Root merges A and B into one Python package. This test imports
their real functions; it contains no replacement projector/provider/sampler.
"""
from collections import Counter
from copy import deepcopy
from dataclasses import asdict, replace
import hashlib
import json
import math
import os
from pathlib import Path
import pickle
import shutil
import tempfile
import types

import pytest
import torch

from model_v3_wire_fixture import fixture as make_wire_fixture
from test_model_v3_trainer import UnitTracker
from phychem_mfm.factory import build_model
from phychem_mfm.model.v3_heads import V3HeadBank
from phychem_mfm.model.v3_multiview import V3MultiViewModel
from phychem_mfm.phase1 import v3_sampling_bridge, v3_wire_provider, v3_data, v3_wire_audit, v3_trainer
from phychem_mfm.phase1.v3_contract import TrainNormalization, canonical_hash
from phychem_mfm.phase1.v3_data import ExposureBatchSampler, ManifestSampleDataset, collate_v3_samples, make_v3_loader
from phychem_mfm.phase1.v3_sampling_bridge import CandidateProjectionInput, build_candidate_sampling_index
from phychem_mfm.phase1.v3_structural import StructuralViewConfig
from phychem_mfm.phase1.v3_trainer import SampleLRScheduler, V3StepTrainer
from phychem_mfm.phase1.v3_training import SampleClock
from phychem_mfm.phase1.v3_wire_provider import CandidateWireFactory, WirePreparedProvider, file_ref, local_storage_receipt
from phychem_mfm.training.losses import LossWeights

PROJECTOR=Path("/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository/workflows/data_v1_final/export/wire_v1/sampling_projection_v1.py")
PROJECTOR_SHA="50aceee73de4718b7f35dbd2a37a207a7739d57f8ed53f39a36da16bfbc0e2dd"
IMPORTED_SHA={
    "A":(v3_sampling_bridge,"2c15a8b61fa5b071d3e64cd8f769a8e43930174dbaa0555e70a1ef233809d946"),
    "B":(v3_wire_provider,"80c728c157205ca1e9870d511751efc6b87a7c59c795d28a6911c313610c2ea8"),
    "data":(v3_data,"0d34824ca39e6b9bfe9b48f56183f86405a00607a70cd9f244a722324c5760c3"),
    "audit":(v3_wire_audit,"ead6ce5e15e8c405510833f25a7050b4ef0aa61c1a9fe0eeff841a99bde1822c"),
    "trainer":(v3_trainer,"6dece41eb2f528a12297d194b016044dded5a855edca98c39c0710c208717436"),
}


def source_receipts():
    values={"external_interop_test":file_ref(Path(__file__).absolute())}
    for name,(module,sha) in IMPORTED_SHA.items():
        ref=file_ref(Path(module.__file__).absolute())
        assert ref["sha256"]==sha,(name,"Root must use the merged, unchanged admitted source")
        values[name]=ref
    ref=file_ref(PROJECTOR);assert ref["sha256"]==PROJECTOR_SHA;values["DataB_projector"]=ref
    for relative,sha in v3_wire_provider.DATA_SOURCE_SHA.items():
        ref=file_ref(v3_wire_provider.DATA_EXPORT/relative);assert ref["sha256"]==sha
        values["DataB_"+relative]=ref
    # Also bind the genuine fixture builder and explicit unit tracker utility.
    import model_v3_wire_fixture
    import test_model_v3_trainer
    values["B_fixture"]=file_ref(Path(model_v3_wire_fixture.__file__).absolute())
    assert values["B_fixture"]["sha256"]=="19f3c572d5dd39177eb3e455759e86f55f73bfb469712926112d36a2bd126293"
    values["unit_tracker"]=file_ref(Path(test_model_v3_trainer.__file__).absolute())
    assert values["unit_tracker"]["sha256"]=="4e7d3a6f3b5ee7137d2a87f5eda49bf8d42510abc71acc524d446ec8d2c0eb38"
    import phychem_mfm.factory
    import phychem_mfm.model.v3_heads
    import phychem_mfm.model.v3_multiview
    for name,module in (("model_factory",phychem_mfm.factory),("PD_heads",phychem_mfm.model.v3_heads),
                        ("original_multiview_model",phychem_mfm.model.v3_multiview)):
        values[name]=file_ref(Path(module.__file__).absolute())
    return values


@pytest.fixture
def case(tmp_path_factory,request):
    private=Path(os.environ.get("TMPDIR",""))
    assert private.is_absolute() and private.is_relative_to(Path("/tmp")) and private.resolve()==private
    code_sha=os.environ.get("MODEL_V3_INTEROP_CODE_SHA","")
    assert len(code_sha)==40 and all(c in "0123456789abcdef" for c in code_sha),"Root must bind actual merged code SHA before compute"
    before=source_receipts()
    raw=PROJECTOR.read_bytes();assert hashlib.sha256(raw).hexdigest()==PROJECTOR_SHA
    module=types.ModuleType("actual_DataB_AB_interop_projector");module.__file__=str(PROJECTOR)
    exec(compile(raw,str(PROJECTOR),"exec"),module.__dict__)
    root=Path(tempfile.mkdtemp(prefix="model_v3_AB_interop_",dir=private))
    output=tmp_path_factory.mktemp("AB_interop_closure")
    factory,_,registry,binding=make_wire_fixture(root)
    item={"root":root,"output":output,"factory":factory,"registry":registry,"binding":binding,
        "projector":module.project_training_sources,"sources":before,"code_sha":code_sha,"owned":[],"trace":{}}
    try:yield item
    finally:
        for resource in reversed(item["owned"]):resource.close()
        after=source_receipts();assert after==before
        stores=[store["data"] for store in factory.manifest["stores"]]
        assert all(file_ref(ref["path"])==ref for ref in stores)
        events=root/"handles.jsonl"
        rows=[json.loads(line) for line in events.read_text().splitlines()] if events.exists() else []
        opens=Counter(row["pid"] for row in rows if row["event"]=="READONLY_HANDLES_OPENED")
        closes=Counter(row["pid"] for row in rows if row["event"]=="READONLY_HANDLES_CLOSED")
        assert opens==closes,"Every actual reader instance must have closed its owned readonly environments"
        closure={"scope":"SYNTHETIC_A_B_INTEROP_NOT_D3","test":request.node.name,
            "pytest_outcome":"NOT_INFERRED_FROM_FIXTURE_TEARDOWN","actual_merged_code_sha":code_sha,
            "sources_before":before,"sources_after":after,"local_storage":local_storage_receipt(root,root),
            "unchanged_original_fixture_store_refs":stores,"handle_events":rows,"checks":item["trace"],
            "PM7_wire_geometry_and_labels_exported":True,"UFF_index_metadata_only":True,
            "UFF_coordinates_or_labels_exported":False,"mixed_condition_normalization_admitted":False,
            "authority_claimed":False,"original_data_modified":False,"unit_tracker_only_not_persistent_SDK":True}
        (output/"closure.json").write_text(json.dumps(closure,sort_keys=True,allow_nan=False)+"\n")
        assert root.parent==private and root.name.startswith("model_v3_AB_interop_") and root.stat().st_uid==os.getuid()
        shutil.rmtree(root)


def candidate_inputs(case):
    """Use the actual B metadata/native binding, plus declared index-only UFF."""
    factory=case["factory"];manifest=factory.manifest
    inspector=factory()
    result=[];proof=[]
    try:
        for record in manifest["records"]:
            meta,arrays=inspector.readers[record["geometry_store"]].get(record["export_record_id"])
            labels_meta,_=inspector.readers["physics"].get(record["export_record_id"])
            native=record["native_identity"]
            assert meta["export_record_id"]==native["geometry_id"]==record["geometry_id"]
            assert meta["molecule_id"]==native["molecule_id"] and meta["geometry_source"]==native["geometry_source"]=="pm7"
            assert meta["n_atoms"]==len(arrays["atomic_numbers"])==record["n_atoms"]
            pm7={**native,"parent_geometry_id":meta["parent_geometry_id"],"view_id":meta["view_id"]}
            # The reviewed projector requires both source entries. This row is
            # explicit fixture index metadata only: it has no wire record,
            # coordinates, labels, cross-source counterpart or real authority.
            uff={"geometry_id":"index_only_uff_not_exported:"+record["geometry_id"],"molecule_id":meta["molecule_id"],
                "geometry_source":"uff_sprime","native_record_id":None,"sprime_conf_idx":1000+len(result),
                "parent_geometry_id":None,"view_id":None}
            orders=[{"molecule_id":meta["molecule_id"],"geometry_source":row["geometry_source"],"geometry_id":row["geometry_id"],
                "order_type":order,"rank":1,"training_rank":0} for row in (pm7,uff) for order in ("fixed_random","energy","diversity")]
            args={"effective_role":meta["effective_role"],"training_geometries":[pm7,uff],"training_orders":orders,
                "diagnostic_targets":[{"molecule_id":meta["molecule_id"],"geometry_source":source,
                    "geometry_id":"declared_held_energy0:"+source+":"+record["geometry_id"]} for source in ("pm7","uff_sprime")],
                "native_atom_counts":{pm7["geometry_id"]:meta["n_atoms"],uff["geometry_id"]:meta["n_atoms"]},
                "group_mask":labels_meta["group_exposure_mask"],"family_mask":labels_meta["family_exposure_mask"]}
            projected=case["projector"](meta["molecule_id"],**args)
            result.append(CandidateProjectionInput(meta["molecule_id"],projected,args,PROJECTOR_SHA))
            proof.append({"PM7_native_identity":native,"PM7_native_identity_sha256":canonical_hash(native),
                "PM7_wire_record_identity_sha256":record["identity_sha256"],"PM7_atom_order_sha256":record["atom_order_sha256"],
                "index_only_UFF_identity":{key:uff[key] for key in native},"unexported_UFF_metadata_scope":True})
    finally:inspector.close()
    case["trace"]["projection_inputs_from_actual_PM7_metadata"]=proof
    return tuple(result)


def bound_index(case,source="PM7"):
    items=candidate_inputs(case)
    options={"data_version":case["factory"].manifest["data_version"],"geometry_source":source,
        "selected_molecule_ids":[item.molecule_id for item in items],"allow_candidate":True}
    if source=="mixed":options["mixed_sources"]={items[0].molecule_id:"PM7",items[1].molecule_id:"Sprime_UFF"}
    index=build_candidate_sampling_index(items,**options)
    assert index.version==case["factory"].manifest["data_version"] and index.authority=="synthetic_fixture"
    assert index.contract_finalized is False and index.real_data_export_accepted is False
    return index


def bound_factory(case,index):
    old=case["factory"]
    return CandidateWireFactory(index,case["registry"],old.manifest,node_local_root=case["root"],allow_candidate=True,
        handle_events=old.handle_events)


def assert_prepared_matches_collation(prepared,collated,registry):
    assert prepared.choices==collated.choices
    for field in registry.fields:
        if field.group=="S":continue
        expected,actual=collated.targets[field.name],prepared.pd_targets[field.name]
        torch.testing.assert_close(actual.values,expected.values,rtol=0,atol=0,equal_nan=True)
        assert torch.equal(actual.valid,expected.valid)
        if expected.pair_index is not None:assert torch.equal(actual.pair_index,expected.pair_index)


def test_actual_DataB_A_B_PM7_model_step_and_committed_prefetch_restore(case):
    previous_threads=torch.get_num_threads();torch.set_num_threads(1)
    rng=torch.get_rng_state()
    index=bound_index(case);factory=bound_factory(case,index);sampler=index.make_sampler(seed=3,sample_budget=8)
    dataset=ManifestSampleDataset(index,factory);case["owned"].append(dataset)
    loader=make_v3_loader(dataset,ExposureBatchSampler(sampler,max_molecules=2),case["registry"],
        num_workers=2,pin_memory=False,prefetch_factor=2,worker_timeout_seconds=60)
    iterator=iter(loader);provider=WirePreparedProvider(factory,case["binding"]);case["owned"].append(provider)
    try:
        first=next(iterator);uncommitted=next(iterator)
        assert sampler.samples_consumed==0 and first.choices[0].ordinal==0 and uncommitted.choices[0].ordinal==2
        case["trace"]["actual_prefetched_uncommitted_ordinals"]=[value.ordinal for value in uncommitted.choices]
        assert pickle.loads(pickle.dumps(first.audit))==first.audit
        for choice,audit in zip(first.choices,first.audit):
            native=index.native_identity_for(choice.locator)
            assert native.model_geometry_source==choice.geometry_source=="PM7"
            assert native.as_dict()==next(row["native_identity"] for row in factory.manifest["records"] if row["geometry_id"]==choice.locator)
            assert audit.native_identity_sha256==native.content_sha256
            assert audit.query("dipole","fixture_dipole_y",0)["source_valid"] is False
            assert audit.query("dipole","fixture_dipole_y",0)["leaf_exception_code"]==9
            assert audit.query("energy","fixture_energy",0)["review_field_reason_set"]==(11,)
        view_config=StructuralViewConfig(seed=4)
        prepared=provider.prepare(first.choices,role="TRAIN",view_config=view_config,enabled_groups=("S","D","P"),enabled_fields=None)
        assert_prepared_matches_collation(prepared,first,case["registry"])
        torch.manual_seed(14)
        config={"architecture":{"preset":"shared_light"},"backbone":{"dim":512,"layers":6,"heads":8,"ff_mult":2,"n_atom_types":119},
            "head":{"profile":"phase1","geometry_head":"equivariant_noise","geometry_hidden_dim":64,"geometry_message_layers":0,"geometry_pair_chunk_size":8192}}
        encoder=build_model(config)
        registry=case["registry"];pd=replace(registry,fields=tuple(field for field in registry.fields if field.group!="S"))
        model=V3MultiViewModel(encoder,V3HeadBank(pd,forms="H2"),registry,case["binding"])
        assert len(model.encoder.backbone.layers)==6 and model.latent_dim==512
        norms={field.name:TrainNormalization((0.,)*field.target_width,(1.,)*field.target_width,"b"*64,index.version) for field in pd.fields}
        optimizer=torch.optim.AdamW(model.parameters(),lr=1e-4)
        scheduler=SampleLRScheduler(optimizer,sample_budget=8);clock=SampleClock(8,())
        bindings={"code_sha":case["code_sha"],"configuration_sha256":canonical_hash(config),"registry_sha256":registry.source_sha256,
            "normalization_sha256":canonical_hash({key:asdict(value) for key,value in norms.items()}),"data_version":index.version}
        tracker=UnitTracker("synthetic_actual_AB_interop")
        trainer=V3StepTrainer(model,optimizer,scheduler,sampler,clock,provider,norms,LossWeights(),tracker,bindings,
            enabled_groups=("S","D","P"),view_config=view_config,allow_unit_tracker=True,probe_samples=1)
        metrics=trainer.step(prepared)
        assert clock.optimizer_updates==1 and metrics["optimizer_updated"] is True and math.isfinite(metrics["loss/total"])
        assert all(metrics["valid_count/"+name]>0 for name in ("s_element","s_noise","s_bond","energy","atom","pair"))
        observed_by_group={group:[field.name for field in registry.fields if field.group==group
            and metrics["valid_count/"+field.name]>0 and metrics["loss/"+field.name]>0] for group in ("S","D","P")}
        assert all(observed_by_group.values())
        assert sampler.samples_consumed==clock.samples_consumed==scheduler.samples_consumed==2
        assert len(tracker.records)==1 and all(torch.isfinite(p.grad).all() for p in model.parameters() if p.grad is not None)
        cursors={"sampler":sampler.state_dict(),"clock":clock.state_dict(),"scheduler":scheduler.state_dict(),
            "index_sha256":index.content_sha256,"adapter_sha256":factory.source_sha256}
        # Small committed cursor only; no model/optimizer artifact is implied.
        path=case["output"]/"committed_cursor.json";path.write_text(json.dumps(cursors,sort_keys=True)+"\n")
        saved=json.loads(path.read_text());restored=index.make_sampler(seed=3,sample_budget=8);restored.load_state_dict(saved["sampler"])
        restored_clock=SampleClock(8,());restored_clock.load_state_dict(saved["clock"])
        scheduler.load_state_dict(saved["scheduler"])
        assert restored.samples_consumed==restored_clock.samples_consumed==scheduler.samples_consumed==2
        next_choices=tuple(restored.choice(2+i) for i in range(2))
        assert next_choices==uncommitted.choices
        provider.close()
        resumed_provider=WirePreparedProvider(factory,case["binding"]);case["owned"].append(resumed_provider)
        resumed=resumed_provider.prepare(next_choices,role="TRAIN",view_config=view_config,enabled_groups=("S","D","P"),enabled_fields=None)
        assert_prepared_matches_collation(resumed,uncommitted,registry)
        assert resumed_provider.audit_for(next_choices)==uncommitted.audit and restored.samples_consumed==2
        case["trace"].update(integration_assertions_completed=True,PM7_only_positive=True,one_real_original_trainer_update=True,
            actual_model_backbone={"layers":6,"dim":512,"heads":8,"ff_mult":2},sample_clock=clock.state_dict(),
            positive_observed_loss_fields_by_group=observed_by_group,
            committed_cursor_file_sha256=file_ref(path)["sha256"],native_identity_and_component_reasons_verified=True,
            index_binding=index.bindings,scalar_training_metrics={key:value for key,value in metrics.items() if not key.startswith("runtime/")},
            resume_scope="committed sampler/clock/scheduler cursor and provider inputs; no model/optimizer checkpoint roundtrip claimed")
    finally:
        iterator._shutdown_workers();provider.close();dataset.close()
        torch.set_rng_state(rng);torch.set_num_threads(previous_threads)


@pytest.mark.parametrize("source",("Sprime_UFF","mixed"))
def test_unexported_UFF_source_is_explicitly_rejected_without_fake_labels_or_mixed_stats(case,source):
    index=bound_index(case,source);factory=bound_factory(case,index)
    sampler=index.make_sampler(seed=3,sample_budget=64)
    choices=[sampler.choice(i) for i in range(64)]
    draw=next(choice for choice in choices if choice.geometry_source=="Sprime_UFF")
    assert draw.locator.startswith("index_only_uff_not_exported:")
    assert draw.locator not in {row["geometry_id"] for row in factory.manifest["records"]}
    dataset=ManifestSampleDataset(index,factory);case["owned"].append(dataset)
    with pytest.raises(ValueError,match="Bound geometry locator required"):dataset[draw]
    assert sampler.samples_consumed==0
    case["trace"].update(rejection_assertions_completed=True,requested_source=source,
        unexported_locator_rejected=draw.locator,UFF_label_or_coordinate_generated=False,mixed_normalization_admitted=False)


def test_A_native_identity_SHA_is_checked_by_real_B_reader(case):
    index=bound_index(case);manifest=case["factory"].manifest
    # Keep a geometrically valid fixture while contradicting A's original
    # native identity. B must reject that discrepancy rather than trust IDs.
    for row in manifest["records"]:row["native_identity"]["native_record_id"]="wrong-native-record"
    factory=CandidateWireFactory(index,case["registry"],manifest,node_local_root=case["root"],allow_candidate=True,
        handle_events=case["factory"].handle_events)
    sampler=index.make_sampler(seed=3,sample_budget=2);reader=factory();case["owned"].append(reader)
    with pytest.raises(ValueError,match="Candidate D5/native identity differs"):reader.read(sampler.choice(0))
    assert sampler.samples_consumed==0
    case["trace"]["native_identity_mismatch_rejection_completed"]=True
