"""Metadata-only finite accounting tests; no native GPU or quota is invented."""
from copy import deepcopy
import json
import os
from pathlib import Path
from types import SimpleNamespace
import time

import pytest
import native_s_storage as native


@pytest.fixture(scope='module')
def runtime():
    return native.load_runtime(metadata_only=True)


def put(storage,path,value):
    return storage.write_once(path,value)


def prepare(root,runtime,*,purpose=native.PROFILE):
    storage,pins=runtime
    root.mkdir(parents=True,exist_ok=True)
    authority='ENGINEERING_METADATA_FIXTURE'
    zeros={key:0 for key in storage.COUNTS}
    counts=dict(launch_attempts=4,successful_segments=2,failed_attempts=2,checkpoint_attempts=8,
        complete_checkpoints=8,successful_panels=0,failed_panels=0,wsd_children=0,events=0,ack_attempts=0)
    policy=dict(schema='model_v3_long_run_policy_v1',segment_bytes=2<<30,segment_seconds=7200,
        durable_bytes=8<<30,metadata_bytes=32<<20,metadata_records=2000,managed_roots=16,inode_limit=10000,
        quota_max_age_seconds=90,checkpoint_bytes=384<<20,counts=counts)
    science=dict(scope=native.SCOPE,source=deepcopy(native.SOURCE),plan=deepcopy(native.PLAN),
        members=[[0,'fp32'],[0,'bf16'],[1,'fp32'],[1,'bf16']],
        model=dict(dim=512,layers=6,heads=8,ff_mult=2),
        sampling='original_TRAIN_record_natural_counts_not_molecule_uniform',native_repo=str(root/'not_an_output_git_tree'))
    config=dict(schema='existing_native_S_storage_configuration_v2',engineering_only=True,purpose=purpose,
        profile_updates=20,Root_storage_commit=native.ROOT_COMMIT,Root_runtime_pin=native.runtime_pin(pins),
        science=science,long_run_policy=policy,capacity=dict(child_seconds=6900,GPU_fraction=.85,
            max_checkpoints_per_segment=2,checkpoint_reserve_seconds=300,
            checkpoint_reserve_bytes=64<<20,non_checkpoint_bytes=128<<20))
    configuration=put(storage,root/'configuration.json',config)
    record=put(storage,root/'Root_reservation_record.json',dict(reservation_id='fixture-only',
        uid=os.getuid(),durable_root=str(root/'durable'),reserved_additional_bytes=8<<30,
        initial_counts=zeros,authority=authority,phase_ledger_id='fixture-only-no-reservation'))
    principal=put(storage,root/'principal.json',dict(schema='model_v3_Root_durable_reservation_v1',
        reservation_id='fixture-only',uid=os.getuid(),status='ROOT_COORDINATOR_RESERVED_FINITE',
        policy_sha256=storage.canonical_hash(policy),max_bytes=8<<30,counts=counts,
        science_identity_sha256=storage.canonical_hash(config),initial_existing_bytes=0,
        reserved_additional_bytes=8<<30,initial_counts=zeros,authority=authority,
        Root_reservation_record=record,durable_root=str(root/'durable'),filesystem='/dev/fixture'))
    producer=root/'producer.py'
    producer.write_text('# engineering metadata only; not an actual quota publisher\n')
    feed=root/'quota.json'
    put(storage,feed,dict(schema='model_v3_Root_live_quota_v1',uid=os.getuid(),host='sonmi',
        filesystem='/dev/fixture',returncode=0,captured_unix=time.time(),authority=authority,
        stdout='/dev/fixture 1000 1000000000 1000000000 0 0 0\n',
        inodes=dict(filesystem='/dev/fixture',uid=os.getuid(),captured_unix=time.time(),available=1000000),
        producer_source_sha256=storage.binding(producer)['sha256'],
        phase_ledger_id='fixture-only-no-reservation',headroom_bytes=1<<20,
        reservations={'fixture-only':dict(durable_root=str(root/'durable'),
            principal_sha256=principal['sha256'],remaining_bytes=8<<30)}))
    descriptor=put(storage,root/'descriptor.json',dict(schema='model_v3_Root_quota_feed_descriptor_v1',
        uid=os.getuid(),filesystem='/dev/fixture',authority=authority,
        producer_source=storage.binding(producer),feed_path=str(feed)))
    lease=put(storage,root/'lease.json',dict(reservation_id='fixture-only',authority=authority,
        created_unix=time.time()-1,expires_unix=time.time()+12000))
    member=dict(scope=native.SCOPE,plan=deepcopy(native.PLAN),seed=0,precision='fp32',code_sha='a'*40,
        prereg_sha='b'*40,sources={'explicit_metadata_fixture':'c'*64},
        runtime=dict(device='cuda',gpu_uuid='GPU-engineering-declaration-not-used',
            deterministic_execution_sha256='d'*64))
    initial=put(storage,root/'initial.json',dict(schema='model_v3_long_run_initial_roots_v1',roots=[]))
    request=dict(schema='existing_native_S_storage_request_v1',configuration=configuration,native_member=member,
        long_run=dict(reservation_principal=principal,initial_roots=initial,quota_feed_descriptor=descriptor,lease=lease))
    admission=put(storage,root/'admission.json',dict(schema='model_v3_Root_long_run_segment_admission_v1',
        stable_request_identity_sha256=native.stable_native_request(request,storage),
        reservation_principal=principal,authority=authority,lease=lease,quota_feed_descriptor=descriptor,
        workload='native_S_profile_only' if purpose==native.PROFILE else 'native_S_B_member',
        resource_envelope=dict(outer_output_budget_bytes=2<<30,child_output_budget_bytes=(2<<30)-(96<<20),
            supervisor_output_reserve_bytes=96<<20,private_storage_budget_bytes=1<<30,additional_durable_private_growth_hold_bytes=0),
        segment_id='fixture-one',job_root=str(root/'job'),lineage_root=str(root/'lineage'),external_roots=[]))
    request['long_run']['Root_segment_admission']=admission
    ref=put(storage,root/'request.json',request)
    return ref,request,config


def test_one_canonical_combined_namespace_and_class_origins(runtime):
    storage,pins=runtime
    assert storage.__name__=='phychem_mfm.phase1.v3_long_run_storage'
    assert len(pins['combined_commit'])==40 and len(pins['combined_tree'])==40
    assert storage.REPOSITORY==Path(pins['runtime_root'])
    import phychem_mfm
    assert not phychem_mfm.__name__.startswith('_native_s_root_storage_')


def test_profile_only_bootstrap_does_not_require_a_preexisting_science_profile(runtime,tmp_path):
    storage,_=runtime
    _,request,config=prepare(tmp_path,runtime)
    checked=native.validate_admission(request,config,storage)
    assert checked['profile'] is None
    assert checked['principal']['authority']=='ENGINEERING_METADATA_FIXTURE'
    assert not (tmp_path/'durable').exists()


@pytest.mark.parametrize('mutation', ['source','role','geometry','sampling','plan','model','members'])
def test_native_science_identity_cannot_alias_D5_or_change_population(runtime,tmp_path,mutation):
    storage,_=runtime
    _,request,config=prepare(tmp_path,runtime)
    changed=deepcopy(config)
    if mutation=='source': changed['science']['source']['D5_authority']=True
    elif mutation=='role': changed['science']['source']['roles']=['TRAIN','VAL']
    elif mutation=='geometry': changed['science']['source']['geometry']='PM7'
    elif mutation=='sampling': changed['science']['sampling']='uniform_molecule'
    elif mutation=='plan': changed['science']['plan']['updates']=6000000
    elif mutation=='model': changed['science']['model']['layers']=4
    elif mutation=='members': changed['science']['members']=[[0,'fp32'],[0,'bf16']]
    with pytest.raises(ValueError):
        native.validate_admission(request,changed,storage)
    assert not (tmp_path/'durable').exists()


@pytest.mark.parametrize('mutation',['segment_bytes','segment_seconds','GPU_fraction','checkpoint_reserve_seconds','non_checkpoint_bytes'])
def test_original_segment_resource_and_finite_reserves_cannot_relax(runtime,tmp_path,mutation):
    storage,_=runtime
    _,request,config=prepare(tmp_path,runtime)
    changed=deepcopy(config)
    if mutation in ('segment_bytes','segment_seconds'): changed['long_run_policy'][mutation]+=1
    elif mutation=='GPU_fraction': changed['capacity'][mutation]=.95
    elif mutation=='checkpoint_reserve_seconds': changed['capacity'][mutation]=0
    else: changed['capacity'][mutation]=2<<30
    with pytest.raises(ValueError):
        native.validate_admission(request,changed,storage)


@pytest.mark.parametrize('mutation',['stale','producer','lease','quota','inode','outstanding','slot'])
def test_actual_fresh_quota_and_root_operational_authority_remain_mandatory(runtime,tmp_path,mutation):
    storage,_=runtime
    _,request,config=prepare(tmp_path,runtime)
    if mutation=='lease':
        lease=storage.read_bound(request['long_run']['lease'])
        lease['expires_unix']=1
        request['long_run']['lease']=put(storage,tmp_path/'changed_lease.json',lease)
    elif mutation=='producer':
        descriptor=storage.read_bound(request['long_run']['quota_feed_descriptor'])
        Path(descriptor['producer_source']['path']).write_text('# changed\n')
    else:
        descriptor=storage.read_bound(request['long_run']['quota_feed_descriptor'])
        path=Path(descriptor['feed_path']); value=json.loads(path.read_text())
        if mutation=='stale': value['captured_unix']=1
        elif mutation=='quota': value['stdout']='/dev/fixture 1000 0 0\n'
        elif mutation=='inode': value['inodes']['available']=0
        elif mutation=='outstanding': value['reservations']['other']=dict(remaining_bytes=10**30)
        elif mutation=='slot': value['reservations']['fixture-only']['principal_sha256']='e'*64
        path.write_bytes(storage.encoded(value))  # Mutable engineering feed only.
    with pytest.raises(ValueError):
        native.validate_admission(request,config,storage)
    assert not (tmp_path/'durable').exists()


def test_native_long_members_still_reject_missing_real_profile(runtime,tmp_path):
    storage,_=runtime
    _,request,config=prepare(tmp_path,runtime,purpose=native.SCIENCE)
    with pytest.raises((ValueError,KeyError)):
        native.validate_admission(request,config,storage)


def test_engineering_fixture_cannot_bind_actual_model_callback(runtime,tmp_path):
    storage,pins=runtime
    ref,request,_=prepare(tmp_path,runtime)
    callback={**request['native_member'],'output_root':str(tmp_path/'job'),'max_segment_bytes':2<<30,'wall_seconds':6900}
    with pytest.raises(ValueError,match='Engineering'):
        native.NativeStorageAdapter(callback,request_ref=ref,storage=storage,pins=pins)


def test_two_GiB_hold_only_released_by_Root_closure_failed_bytes_and_counters_remain(runtime,tmp_path):
    storage,_=runtime
    ref,request,config=prepare(tmp_path,runtime)
    ledger=native.ledger_class(storage)(request,config)
    ledger.allocate_segment(request_ref=ref,segment_id='fixture-one',job_root=tmp_path/'job',lineage_root=tmp_path/'lineage')
    before=ledger.remaining()
    (tmp_path/'job').mkdir(); original=tmp_path/'job'/'failed.log'; original.write_text('original failure remains\n')
    original_sha=native.sha(original)
    closure=put(storage,tmp_path/'closure.json',dict(schema='model_v3_Root_storage_segment_closure_v1',
        authority='ENGINEERING_METADATA_FIXTURE',job_root=str(tmp_path/'job'),status='FAILED'))
    ledger.seal_segment(job_root=tmp_path/'job',Root_closure_ref=closure)
    after=ledger.remaining()
    assert after>before and native.sha(original)==original_sha
    rows=ledger.records()
    assert sum(row['kind']=='launch_attempts' for row in rows)==1
    assert sum(row['kind']=='failed_attempts' for row in rows)==1
    assert sum(row['kind']=='segment_terminal' for row in rows)==1


def test_shared_append_chain_tamper_does_not_reset_lifetime_attempts(runtime,tmp_path):
    storage,_=runtime
    _,request,config=prepare(tmp_path,runtime)
    ledger=native.ledger_class(storage)(request,config)
    ledger.append('launch_attempts','explicit-fixture',dict(held_bytes=2<<30))
    indices=sorted((ledger.root/'index').glob('*.json'))
    indices[-1].write_text('{}')
    with pytest.raises((ValueError,KeyError)):
        ledger.records()


def test_native_worktree_is_never_an_output_root(runtime,tmp_path):
    storage,_=runtime
    _,request,config=prepare(tmp_path,runtime)
    ledger=native.ledger_class(storage)(request,config)
    with pytest.raises(ValueError,match='Git'):
        ledger.register_root(Path(config['science']['native_repo'])/'bad_output',kind='training')


def test_opaque_metadata_does_not_claim_model_training_or_SDK_acceptance(runtime,tmp_path):
    storage,_=runtime
    _,request,config=prepare(tmp_path,runtime)
    checked=native.validate_admission(request,config,storage)
    assert checked['profile'] is None and config['engineering_only'] is True
    assert config['purpose']==native.PROFILE and config['science']['source']['D5_authority'] is False


def assembled_accounting_hook(runtime,tmp_path):
    """Engineering hook mechanics only; real bind rejects these fixtures above."""
    storage,_=runtime
    ref,request,config=prepare(tmp_path,runtime)
    ledger=native.ledger_class(storage)(request,config)
    ledger.allocate_segment(request_ref=ref,segment_id='fixture-one',job_root=tmp_path/'job',lineage_root=tmp_path/'lineage')
    (tmp_path/'job').mkdir()
    values=dict(scope=native.SCOPE,geometry=native.SOURCE['geometry'],node_local=False,read_only=True,
        validation_role='PRETRAIN_VAL',validation_records=1024,validation_atoms=55650,validation_seed=0,validation_epoch=0,
        TRAIN_UNSEEN_CONFORMATION='NOT_PROVIDED_D5',disjointness=dict(TRAIN_records_checked=11104772,validation_records=1024,
            record_overlap=0,molecule_overlap=0,metadata_only=True,original_split_unchanged=True),
        TRAIN=dict(manifest_sha256=native.SOURCE['manifest_sha256'],
            original_shard_snapshot=dict(sha256=native.SOURCE['snapshot_sha256'])),
        validation_selection=dict(sha256=native.SOURCE['validation_selection_sha256']),
        population_manifest_sha256=native.SOURCE['population_manifest_sha256'])
    experiment=SimpleNamespace(inputs=SimpleNamespace(bindings=values),plan=SimpleNamespace(input_scope=native.SCOPE),
        clock=SimpleNamespace(optimizer_updates=1,samples_consumed=3),log_cursor=5,
        bindings=dict(unit_accounting_fixture_only='e'*64))
    hook=object.__new__(native.NativeStorageAdapter)
    hook.storage,hook.ledger,hook.configuration=storage,ledger,config
    hook.job_root,hook.last_refresh,hook.pending,hook.experiment,hook.closed=tmp_path/'job',0.,None,None,False
    return hook,experiment


@pytest.mark.parametrize('changed',[None,'payload_hash','clock'])
def test_safe_marker_hash_and_committed_clock_accounting_reconcile_without_loading_model(runtime,tmp_path,changed):
    import torch
    hook,experiment=assembled_accounting_hook(runtime,tmp_path)
    hook.guard('checkpoint',experiment)
    path,attempt=hook.pending
    path.mkdir()
    # Actual safe torch serialization, but only a labelled metadata fixture;
    # full model/Adam/RNG roundtrips belong to the separate frozen26 tests.
    torch.save({'unit_accounting_fixture_only':True},path/'payload.pt')
    payload=hook.storage.binding(path/'payload.pt')
    marker=dict(schema='model_v3_training_checkpoint_v1',payload_bytes=payload['bytes'],payload_sha256=payload['sha256'],
        bindings=experiment.bindings,optimizer_updates=1,samples_consumed=3)
    if changed=='payload_hash': marker['payload_sha256']='f'*64
    if changed=='clock': marker['optimizer_updates']=2
    put(hook.storage,path/'COMPLETE.json',marker)
    if changed is None:
        hook.guard('step',experiment)
        assert hook.pending is None
        assert sum(row['kind']=='complete_checkpoints' for row in hook.ledger.records())==1
    else:
        with pytest.raises(ValueError): hook.guard('step',experiment)
        assert hook.pending is not None
        assert not any(row['kind']=='complete_checkpoints' for row in hook.ledger.records())
    assert sum(row['kind']=='checkpoint_attempts' for row in hook.ledger.records())==1
    assert (path/'payload.pt').exists()


def test_failed_partial_checkpoint_still_consumes_attempt_and_close_does_not_release_hold(runtime,tmp_path):
    hook,experiment=assembled_accounting_hook(runtime,tmp_path)
    hook.guard('checkpoint',experiment)
    path,_=hook.pending; path.mkdir(); (path/'payload.pt').write_bytes(b'partial-evidence')
    hook.close()
    rows=hook.ledger.records()
    assert sum(row['kind']=='checkpoint_attempts' for row in rows)==1
    assert not any(row['kind'] in ('complete_checkpoints','segment_terminal','successful_segments') for row in rows)
    assert (path/'payload.pt').read_bytes()==b'partial-evidence'


def test_profile_reservation_cannot_execute_update21_under_a20update_ceiling(runtime,tmp_path):
    hook,experiment=assembled_accounting_hook(runtime,tmp_path)
    experiment.clock.optimizer_updates=20
    with pytest.raises(ValueError,match='short update ceiling'):
        hook.guard('step',experiment)
    assert not any(row['kind']=='checkpoint_attempts' for row in hook.ledger.records())
