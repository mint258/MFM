"""Actual small MFM3/LMDB fixture -> readonly provider -> existing v3 APIs."""
from copy import deepcopy
from dataclasses import asdict, replace
import json
import os
import pickle
from pathlib import Path
import shutil
import tempfile

import numpy as np
import pytest
import torch

from model_v3_wire_fixture import fixture
from phychem_mfm.phase1.v3_contract import TrainNormalization
from phychem_mfm.phase1.v3_data import ManifestSampleDataset, ExposureBatchSampler, collate_v3_samples, make_v3_loader
from phychem_mfm.phase1.v3_sampling import UniformMoleculeSampler
from phychem_mfm.phase1.v3_structural import StructuralViewConfig
from phychem_mfm.phase1.v3_wire_provider import (CandidateWireFactory, WirePreparedProvider, data_runtime, file_ref)


@pytest.fixture
def tmp_path(tmp_path_factory,request):
    """Only source fixtures live in actual Root-bound node-local TMPDIR."""
    from phychem_mfm.phase1.v3_wire_provider import local_storage_receipt
    private=Path(os.environ.get("TMPDIR",""))
    assert private.is_absolute() and private.is_relative_to(Path("/tmp")) and private.resolve()==private
    root=Path(tempfile.mkdtemp(prefix="mfm3_wire_fixture_",dir=private))
    receipt=local_storage_receipt(root,root)
    try:yield root
    finally:
        # Retain small audit/identity closure outside the deleted data fixture.
        events=root/"handles.jsonl"
        record={"test":request.node.name,"local_storage":receipt,
            "LMDB_file_identities":[{"relative_path":str(path.relative_to(root)),"bytes":path.stat().st_size,
                "inode":path.stat().st_ino,"device":path.stat().st_dev} for path in root.rglob("data.mdb")],
            "handle_events":[json.loads(row) for row in events.read_text().splitlines()] if events.exists() else [],
            "original_data_modified":False,"source_LMDB_exported_to_shared_output":False}
        output=tmp_path_factory.mktemp("wire_closure")/"closure.json"
        output.write_text(json.dumps(record,sort_keys=True)+"\n")
        assert root.parent==private and root.name.startswith("mfm3_wire_fixture_") and root.stat().st_uid==os.getuid()
        shutil.rmtree(root)


def recreate(factory, manifest):
    return CandidateWireFactory(factory.index, factory.registry, manifest,
        node_local_root=factory.root, allow_candidate=True, handle_events=factory.handle_events)


def test_real_wire_scalar_vector_atom_pair_shapes_and_reason_query(tmp_path):
    factory, sampler, registry, binding = fixture(tmp_path)
    dataset = ManifestSampleDataset(factory.index, factory)
    try:
        choice, sample = dataset[sampler.choice(0)]
        assert sample.x.dtype==torch.long and sample.x.shape==(choice.native_atoms,1)
        assert torch.equal(sample.x,torch.full_like(sample.x,5))
        assert sample.pos.dtype==torch.float32 and sample.native_bonds.status=="ok"
        assert sample.fields["energy"].values.shape==(1,1)
        assert sample.fields["atom"].values.shape==(choice.native_atoms,1)
        assert sample.fields["pair"].pair_index.shape==(2,choice.native_atoms-1)
        vector=sample.fields["dipole"]
        assert vector.values.shape==(1,3) and torch.isnan(vector.values[0,1]) and vector.valid.tolist()==[False]
        audit=sample.audit
        assert audit.query("dipole","fixture_dipole_y",0)["leaf_exception_code"]==9
        assert audit.query("dipole","fixture_dipole_x",0)["source_valid"] is True
        assert audit.query("dipole","fixture_dipole_x",0)["source_field_reason_set"]==(7,)
        assert audit.query("dipole","fixture_dipole_x",0)["review_field_reason_set"]==(11,)
        assert all(reader.env.flags()["readonly"] for reader in dataset._provider.readers.values())
    finally:dataset.close()
    events=[json.loads(line) for line in (tmp_path/"handles.jsonl").read_text().splitlines()]
    assert [row["event"] for row in events]==["READONLY_HANDLES_OPENED","READONLY_HANDLES_CLOSED"]


def test_collate_rebases_each_fields_pairs_and_keeps_immutable_CPU_audit(tmp_path,monkeypatch):
    factory,sampler,registry,_=fixture(tmp_path)
    dataset=ManifestSampleDataset(factory.index,factory)
    try:
        rows=[dataset[sampler.choice(i)] for i in range(2)]
        batch=collate_v3_samples(rows,registry)
        first=rows[0][0].native_atoms; p=rows[0][1].fields["pair"].pair_index.shape[1]
        assert torch.equal(batch.targets["pair"].pair_index[:,p:],rows[1][1].fields["pair"].pair_index+first)
        audits=batch.audit; assert pickle.loads(pickle.dumps(audits))==audits
        rows[0][1].fields["dipole"].valid.fill_(True)
        assert audits[0].fields[1].model_row_validity==(False,)
        assert batch.to("meta").audit is audits
        monkeypatch.setattr(torch.Tensor,"pin_memory",lambda value,*args,**kwargs:value)
        assert batch.pin_memory().audit is audits
        assert not any(isinstance(v,torch.Tensor) for v in asdict(audits[0]).values())
    finally:dataset.close()


def test_review_and_recipe_exposure_never_overwrite_source_validity(tmp_path):
    def mutation(schemas,payloads,records):
        for family in ("physics","descriptor"):
            for meta,_ in payloads[family]:meta["group_exposure_mask"]["P"]=False
    factory,sampler,registry,_=fixture(tmp_path,mutation=mutation)
    entries=tuple(replace(row,group_mask=tuple((key,False if key=="P" else value) for key,value in row.group_mask)) for row in factory.index.molecules)
    index=replace(factory.index,molecules=entries)
    factory=CandidateWireFactory(index,registry,factory.manifest,node_local_root=tmp_path,allow_candidate=True)
    sampler=UniformMoleculeSampler(index,seed=3,sample_budget=2)
    dataset=ManifestSampleDataset(index,factory)
    try:
        row=dataset[sampler.choice(0)];batch=collate_v3_samples((row,),registry)
        assert not bool(batch.targets["energy"].valid.any())
        assert row[1].fields["energy"].valid.tolist()==[True]
        audit=batch.audit[0].query("energy","fixture_energy",0)
        assert audit["source_valid"] is True and audit["review_field_reason_set"]==(11,) and audit["group_exposed"] is False
    finally:dataset.close()


@pytest.mark.parametrize("drift",("record","source_role","atom_order","codebook","unknown_reason"))
def test_valid_MFM3_family_with_wrong_join_or_reason_authority_is_rejected(tmp_path,drift):
    def mutation(schemas,payloads,records):
        for meta,arrays in payloads["physics"]:
            if drift=="record":meta["molecule_id"]="wrong-molecule"
            elif drift=="source_role":meta["source_role"]="VAL"
            elif drift=="atom_order":meta["model_fixture_atom_order_sha256"]="0"*64
            elif drift=="codebook":meta["reason_codebook_sha256"]="0"*64
            else:arrays["reason_fields_review/fixture_energy"]=np.array([123],dtype="<u2")
    factory,sampler,_,_=fixture(tmp_path,mutation=mutation)
    reader=factory()
    try:
        with pytest.raises(ValueError):reader.read(sampler.choice(0))
    finally:reader.close()


@pytest.mark.parametrize("drift",("tensor","basis","perturbed","authority","version"))
def test_candidate_does_not_admit_unknown_physical_fields_or_real_authority(tmp_path,drift):
    factory,_,registry,_=fixture(tmp_path);manifest=factory.manifest
    if drift=="tensor":manifest["targets"][0]["model_field"]="s_bond"
    elif drift=="basis":manifest["targets"][0]["basis_indexed"]=True
    elif drift=="perturbed":manifest["targets"][0]["geometry_context"]="seeded_sigma0.1A_perturbed_PM7"
    elif drift=="authority":manifest["scope"]="data_line"
    else:manifest["data_version"]="other"
    with pytest.raises(ValueError):recreate(factory,manifest)
    with pytest.raises(ValueError):CandidateWireFactory(factory.index,registry,factory.manifest,node_local_root=tmp_path)


@pytest.mark.parametrize("mutation",("WRITING","corrupt","mask_identity","pairs"))
def test_actual_reader_rejects_WRITING_corrupt_payload_mask_or_pairs(tmp_path,mutation):
    import lmdb
    factory,sampler,_,_=fixture(tmp_path);manifest=factory.manifest
    runtime=data_runtime();codec=runtime["wire_v1.codec"]
    store=next(item for item in manifest["stores"] if item["name"]==("geometry" if mutation in {"WRITING","corrupt"} else "physics"))
    env=lmdb.open(store["path"],create=False,max_dbs=4)
    try:
        db=env.open_db(b"masks" if mutation=="mask_identity" else b"records")
        with env.begin(write=True) as tx:
            if mutation=="WRITING":tx.put(b"__state__",b"WRITING")
            else:
                for gid in (b"geom0",b"geom1"):
                    raw=tx.get(gid,db=db)
                    if mutation=="corrupt":raw=raw[:-1]+bytes([raw[-1]^1])
                    else:
                        meta,arrays=codec.decode_record(raw);arrays={key:value.copy() for key,value in arrays.items()}
                        if mutation=="mask_identity":meta["molecule_id"]="wrong-mask-identity"
                        else:arrays["pairs/pair"][0,1]=arrays["pairs/pair"][0,0]
                        raw=codec.encode_record(meta,arrays)
                    tx.put(gid,raw,db=db)
        env.sync(True)
    finally:env.close()
    # A synthetic malformed-file fixture gets its own explicit new byte pin;
    # this cannot alter any source LMDB or bypass the real reader validators.
    store["data"]=file_ref(Path(store["path"])/"data.mdb")
    candidate=recreate(factory,manifest)
    if mutation=="WRITING":
        with pytest.raises(ValueError,match="INCOMPLETE_STORE"):candidate()
    else:
        reader=candidate()
        try:
            with pytest.raises(ValueError):reader.read(sampler.choice(0))
        finally:reader.close()


def test_changed_shard_after_open_is_detected_without_rehash_per_sample(tmp_path,monkeypatch):
    factory,sampler,_,_=fixture(tmp_path);reader=factory()
    try:
        reader.read(sampler.choice(0))
        import phychem_mfm.phase1.v3_wire_provider as module
        monkeypatch.setattr(module,"file_ref",lambda *args,**kwargs:(_ for _ in ()).throw(AssertionError("per-record whole-file rehash")))
        reader.read(sampler.choice(1))
        path=Path(factory.manifest["stores"][0]["path"])/"data.mdb"
        info=path.stat();os.utime(path,ns=(info.st_atime_ns,info.st_mtime_ns+1000000000))
        with pytest.raises(ValueError,match="changed after readonly open"):reader.read(sampler.choice(2))
    finally:reader.close()


def test_prepared_refuses_S_without_mapping_and_preserves_queryable_audit(tmp_path):
    factory,sampler,_,binding=fixture(tmp_path,with_bond_mapping=False)
    provider=WirePreparedProvider(factory,binding)
    try:
        choices=(sampler.choice(0),)
        with pytest.raises(ValueError,match="never drop S silently"):
            provider.prepare(choices,role="TRAIN",view_config=StructuralViewConfig(),enabled_groups=("S","D","P"),enabled_fields=None)
        prepared=provider.prepare(choices,role="TRAIN",view_config=StructuralViewConfig(),enabled_groups=("D","P"),enabled_fields=None)
        assert prepared.views.includes_structural is False and provider.audit_for(choices)[0].fields
        with pytest.raises(ValueError,match="no admitted real validation"):
            provider.prepare(choices,role="VAL",view_config=StructuralViewConfig(),enabled_groups=("D","P"),enabled_fields=None)
    finally:provider.close()


def test_explicit_synthetic_mapping_never_guesses_an_unmapped_wire_bond_code(tmp_path):
    def mutation(schemas,payloads,records):
        for _,arrays in payloads["geometry"]:arrays["bond_order_codes"][:]=5
    factory,sampler,_,_=fixture(tmp_path,mutation=mutation);reader=factory()
    try:
        with pytest.raises(ValueError,match="Unknown synthetic wire bond code"):reader.read(sampler.choice(0))
    finally:reader.close()


def test_raw_record_role_is_checked_even_with_its_own_valid_identity_digest(tmp_path):
    from phychem_mfm.phase1.v3_wire_audit import identity_sha256
    def mutation(schemas,payloads,records):
        for meta,_ in payloads["geometry"]:meta["effective_role"]="VAL"
        for row,(meta,_) in zip(records,payloads["geometry"]):row["identity_sha256"]=identity_sha256(meta)
    factory,sampler,_,_=fixture(tmp_path,mutation=mutation);reader=factory()
    try:
        with pytest.raises(ValueError,match="source/role/base identity"):reader.read(sampler.choice(0))
    finally:reader.close()


def test_codebook_hash_and_physical_shard_ancestry_are_not_boolean_claims(tmp_path,tmp_path_factory):
    factory,_,_,_=fixture(tmp_path)
    path=Path(factory.manifest["reason_codebook"]["path"]);path.write_text(path.read_text()+" ")
    with pytest.raises(ValueError,match="codebook raw SHA"):factory()
    # A rejected path is negative test data; valid LMDBs remain in local TMPDIR.
    # Keep test links in the supervisor-declared pytest fixture subtree.
    alias=tmp_path_factory.mktemp("wire_ancestry_negative")/"alias"
    alias.symlink_to(tmp_path/"geometry",target_is_directory=True)
    manifest=factory.manifest;manifest["stores"][0]["path"]=str(alias)
    with pytest.raises(ValueError,match="physical node-local fixture root"):recreate(factory,manifest)()


def test_unresolved_leaf_cause_does_not_densify_field_cause_sets():
    from phychem_mfm.phase1.v3_wire_audit import MemberReasonAudit
    audit=MemberReasonAudit("fixture_partial",(2,),(True,False),(7,),(),(11,),(),())
    assert audit.leaf(0)["source_valid"] is True and audit.leaf(0)["leaf_exception_code"]==0
    assert audit.leaf(1)["leaf_exception_code"]==65535 and audit.leaf(1)["unresolved_leaf_cause"] is True
    assert audit.leaf(1)["source_field_reason_set"]==(7,) and audit.leaf(1)["field_sets_are_not_dense_leaf_causes"] is True


def test_decoded_default_path_has_no_audit_side_effect(tmp_path):
    factory,sampler,registry,_=fixture(tmp_path);dataset=ManifestSampleDataset(factory.index,factory)
    try:
        choice,sample=dataset[sampler.choice(0)];original=sample.audit
        plain=replace(sample,audit=None)
        left=collate_v3_samples(((choice,sample),),registry);right=collate_v3_samples(((choice,plain),),registry)
        assert right.audit is None and left.audit==(original,)
        assert torch.equal(left.encoder_batch.x,right.encoder_batch.x) and torch.equal(left.encoder_batch.pos,right.encoder_batch.pos)
        assert all(torch.equal(left.targets[name].valid,right.targets[name].valid) for name in left.targets)
    finally:dataset.close()


def test_spawn_workers_open_close_real_readonly_handles_and_resume_does_not_consume_prefetch(tmp_path):
    factory,sampler,registry,_=fixture(tmp_path)
    dataset=ManifestSampleDataset(factory.index,factory)
    loader=make_v3_loader(dataset,ExposureBatchSampler(sampler,max_molecules=1),registry,
                          num_workers=2,pin_memory=False,prefetch_factor=2,worker_timeout_seconds=60)
    iterator=iter(loader)
    try:
        first=next(iterator);second=next(iterator)
        assert sampler.samples_consumed==0
        sampler.commit_batch(first.choices);state=deepcopy(sampler.state_dict())
        restored=UniformMoleculeSampler(factory.index,seed=3,sample_budget=8);restored.load_state_dict(state)
        assert restored.choice(restored.samples_consumed)==second.choices[0]
        assert pickle.loads(pickle.dumps(first.audit))==first.audit
    finally:
        iterator._shutdown_workers();dataset.close()
    rows=[json.loads(line) for line in (tmp_path/"handles.jsonl").read_text().splitlines()]
    opened={row["pid"] for row in rows if row["event"]=="READONLY_HANDLES_OPENED"}
    closed={row["pid"] for row in rows if row["event"]=="READONLY_HANDLES_CLOSED"}
    assert len(opened)==2 and os.getpid() not in opened and opened==closed


def test_original_model_S_D_P_single_update_from_real_synthetic_MFM3(tmp_path):
    from dataclasses import replace
    from phychem_mfm.factory import build_model
    from phychem_mfm.model.v3_heads import V3HeadBank
    from phychem_mfm.model.v3_multiview import V3MultiViewModel
    from phychem_mfm.training.losses import LossWeights
    previous=torch.get_num_threads();torch.set_num_threads(1)
    factory,sampler,registry,binding=fixture(tmp_path);provider=WirePreparedProvider(factory,binding)
    try:
        torch.manual_seed(14)
        encoder=build_model({"architecture":{"preset":"shared_light"},"backbone":{"dim":512,"layers":6,"heads":8,"ff_mult":2,"n_atom_types":119},
            "head":{"profile":"phase1","geometry_head":"equivariant_noise","geometry_hidden_dim":64,"geometry_message_layers":0,"geometry_pair_chunk_size":8192}})
        pd=replace(registry,fields=tuple(field for field in registry.fields if field.group!="S"))
        model=V3MultiViewModel(encoder,V3HeadBank(pd,forms="H2"),registry,binding)
        assert model.latent_dim==512 and len(model.encoder.backbone.layers)==6
        norms={field.name:TrainNormalization((0.,)*field.target_width,(1.,)*field.target_width,"b"*64,factory.data_version) for field in pd.fields}
        choices=tuple(sampler.choice(i) for i in range(2))
        batch=provider.prepare(choices,role="TRAIN",view_config=StructuralViewConfig(seed=4),enabled_groups=("S","D","P"),enabled_fields=None)
        output=model.forward_pretrain(batch.views,enabled_groups=("S","D","P"),pair_indices=batch.pair_indices)
        loss=model.compute_loss(output,batch.views,batch.pd_targets,norms,enabled_groups=("S","D","P"),weights=LossWeights())
        assert torch.isfinite(loss.total) and float(loss.total.detach())>0
        assert all(loss.observed_fields[group]>0 and float(loss.groups[group].detach())>0 for group in ("S","D","P"))
        assert all(loss.counts[name]>0 for name in ("s_element","s_noise","s_bond","energy","atom","pair"))
        optimizer=torch.optim.AdamW(model.parameters(),lr=1e-4);optimizer.zero_grad(set_to_none=True);loss.total.backward()
        assert all(torch.isfinite(parameter.grad).all() for parameter in model.parameters() if parameter.grad is not None)
        optimizer.step();sampler.commit_batch(choices)
        assert sampler.samples_consumed==2 and provider.audit_for(choices)[0].query("dipole","fixture_dipole_y",0)["source_valid"] is False
    finally:provider.close();torch.set_num_threads(previous)
