"""Actual engineering WSD restoration/SDK tests; not D/proxy acceptance."""
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
import torch
from torch_geometric.data import Data

from test_model_v3_trainer import UnitTracker
from test_model_v3_training import assert_tree_equal
from phychem_mfm.phase1 import v3_proxy_run as proxy
from phychem_mfm.phase1 import v3_wsd_fork as wsd
from phychem_mfm.phase1.v3_sample_budget_events import binding,read_bound,write_once,verify_checkpoint_record
from phychem_mfm.phase1.v3_training import capture_rng_state
from phychem_mfm.phase1.v3_encoder_bridge import load_encoder_pair

BASE = '5ac19e805a9ebab9dca516ba7201bae0666d2515'


@pytest.fixture(autouse=True)
def cpu_environment():
    old = torch.get_num_threads(),torch.get_float32_matmul_precision(),torch.backends.cuda.matmul.allow_tf32,torch.backends.cudnn.allow_tf32,torch.are_deterministic_algorithms_enabled()
    torch.set_num_threads(1); torch.set_float32_matmul_precision('highest')
    torch.backends.cuda.matmul.allow_tf32 = False; torch.backends.cudnn.allow_tf32 = False
    torch.use_deterministic_algorithms(True)
    try: yield
    finally:
        torch.set_num_threads(old[0]); torch.set_float32_matmul_precision(old[1])
        torch.backends.cuda.matmul.allow_tf32 = old[2]; torch.backends.cudnn.allow_tf32 = old[3]
        torch.use_deterministic_algorithms(old[4])


def create_parent(root,*,layers=1,seed=7,schedule=None):
    meta = proxy.engineering_request(root/'initial_metadata',code_sha=BASE,layers=layers,budget=8,seed=seed)
    request = read_bound(meta); config = read_bound(request['configuration'])
    config['proxy_contract']['schedule'] = schedule or {'mode':'wsd','warmup_samples':0,'decay_start_samples':6,'minimum_ratio':0.}
    request['configuration'] = write_once(root/'stable_configuration.json',config)
    ref = write_once(root/'stable_request.json',request)
    config,plan,_ = proxy.validate_request(request,input_kind='synthetic',engineering_only=True)
    inputs = proxy.bind_inputs(request,config)
    experiment = proxy.build_experiment(request,config,plan,inputs,UnitTracker('parent-'+str(seed)),
        output_root=root/'parent_job/training',lineage_root=root/'parent_ledger',lineage='parent',device='cpu',allow_unit_tracker=True)
    result = experiment.run_segment(segment_id='parent',until_samples=2,request_ref=ref,preflight=lambda *args:None)
    return {'root':root,'request':request,'request_ref':ref,'configuration':config,'experiment':experiment,
        'complete':result['last_checkpoint'],'ledger':root/'parent_ledger','registration':binding(root/'parent_ledger/segments/parent.json'),
        'rng':capture_rng_state()}


@pytest.fixture(scope='module')
def parent512(tmp_path_factory):
    # One actual6x512 parent checkpoint, reused read-only across tests.
    old = torch.get_num_threads(),torch.get_float32_matmul_precision(),torch.backends.cuda.matmul.allow_tf32,torch.backends.cudnn.allow_tf32,torch.are_deterministic_algorithms_enabled()
    torch.set_num_threads(1); torch.set_float32_matmul_precision('highest')
    torch.backends.cuda.matmul.allow_tf32 = False; torch.backends.cudnn.allow_tf32 = False
    torch.use_deterministic_algorithms(True)
    try:
        parent = create_parent(tmp_path_factory.mktemp('wsd-parent512'),layers=6)
        yield parent
        parent['experiment'].trainer.provider.close()
    finally:
        torch.set_num_threads(old[0]); torch.set_float32_matmul_precision(old[1])
        torch.backends.cuda.matmul.allow_tf32 = old[2]; torch.backends.cudnn.allow_tf32 = old[3]
        torch.use_deterministic_algorithms(old[4])


def child_metadata(root,parent,**kwargs):
    ref = wsd.engineering_fork_request(root/'child_metadata',parent_request_ref=parent['request_ref'],
        parent_complete_ref=parent['complete'],parent_ledger=parent['ledger'],parent_segment_registration=parent['registration'],
        family_root=root/'family',code_sha=BASE,decay_samples=2,**kwargs)
    request = read_bound(ref)
    values = wsd.validate_fork(request,input_kind='synthetic',engineering_only=True)
    return ref,request,values


def construct_child(root,parent,request,values,*,name='job1',tracker=None):
    config,plan,_,old,oldconfig,state,_ = values
    family = wsd.ForkFamily(request['fork']['family_root'],fork=request['fork'],policy=config['wsd_fork'],
        child_identity=proxy.identity(config),maximum_checkpoints=plan.max_total_checkpoints)
    family.register_child(lineage='child',ledger=root/'child_ledger',request_ref=binding(root/'child_metadata/request.json'))
    inputs = proxy.bind_inputs(old,oldconfig)
    return wsd.restore_and_fork(request,config,plan,inputs,tracker or UnitTracker(name),output_root=root/name,
        lineage_root=root/'child_ledger',lineage='child',family=family,parent=old,parent_config=oldconfig,
        parent_state=state,allow_unit_tracker=True)


def test_only_pinned_new_fork_sources_can_extend_historical_runtime():
    actual = wsd.fork_sources(); parent = {'mode':'synthetic_engineering','sources':{'code_sha':BASE,
        'state':'engineering_raw_inventory_not_claimed_in_base_commit',
        'runtime_files':{p:sha for p,sha in actual.items() if p not in wsd.ALLOWED_ADDITIONS}}}
    config = {'wsd_fork':{'source_additions':{p:sha for p,sha in actual.items() if p in wsd.ALLOWED_ADDITIONS}}}
    assert set(wsd.verify_parent_sources(parent,config)['new_fork_additions']) == wsd.ALLOWED_ADDITIONS
    corrupt = deepcopy(parent); corrupt['sources']['runtime_files'][next(iter(corrupt['sources']['runtime_files']))] = '0'*64
    with pytest.raises(ValueError,match='implementation changed'): wsd.verify_parent_sources(corrupt,config)
    config['wsd_fork']['source_additions'][wsd.TOOL] = '0'*64
    with pytest.raises(ValueError,match='pinned new fork'): wsd.verify_parent_sources(parent,config)


@pytest.mark.parametrize('input_kind,flag',[('authoritative_proxy',False),('synthetic',False),('authoritative_proxy',True)])
def test_fork_engineering_still_requires_both_gates(parent512,tmp_path,input_kind,flag):
    _,request,_ = child_metadata(tmp_path,parent512)
    with pytest.raises(ValueError): wsd.validate_fork(request,input_kind=input_kind,engineering_only=flag)


@pytest.mark.parametrize('change',['optimizer','seed','validation','budget','decay_start','extra_parent_hash','parent_complete'])
def test_unregistered_or_non_decay_differences_are_rejected(parent512,tmp_path,change):
    _,request,values = child_metadata(tmp_path,parent512)
    config = deepcopy(values[0]); contract = config['proxy_contract']
    if change == 'optimizer': contract['optimizer']['weight_decay'] = .2
    elif change == 'seed': config['seed'] += 1
    elif change == 'validation': contract['validation']['seed'] += 1
    elif change == 'budget': contract['sample_budget'] += 1
    elif change == 'decay_start': contract['schedule']['decay_start_samples'] += 1
    elif change == 'extra_parent_hash': config['wsd_fork']['parent_checkpoint_sha256'] = '0'*64
    else: request['fork']['parent_complete'] = {**request['fork']['parent_complete'],'sha256':'0'*64}
    request['configuration'] = write_once(tmp_path/'changed.json',config)
    with pytest.raises(ValueError): wsd.validate_fork(request,input_kind='synthetic',engineering_only=True)


def test_actual_parent_state_and_first_LR_survive_explicit_child_rebind(parent512,tmp_path):
    _,request,values = child_metadata(tmp_path,parent512)
    child = construct_child(tmp_path,parent512,request,values)
    original = parent512['experiment'].trainer; trainer = child.trainer
    assert_tree_equal(original.model.state_dict(),trainer.model.state_dict())
    assert_tree_equal(original.optimizer.state_dict(),trainer.optimizer.state_dict())
    assert_tree_equal(original.provider.state_dict(),trainer.provider.state_dict())
    assert_tree_equal(parent512['rng'],capture_rng_state())
    assert trainer.clock.samples_consumed == trainer.sampler.samples_consumed == trainer.scheduler.samples_consumed == 2
    assert trainer.clock.optimizer_updates == original.clock.optimizer_updates
    assert trainer.log_cursor == original.log_cursor and trainer.validation_state == original.validation_state
    assert trainer.resume_parent['id'] == original.tracker.id
    for ordinal in (2,3):
        left,right = original.sampler.choice(ordinal),trainer.sampler.choice(ordinal)
        assert {k:v for k,v in left.__dict__.items() if k != 'sampler_sha256'} == {k:v for k,v in right.__dict__.items() if k != 'sampler_sha256'}
        assert left.sampler_sha256 != right.sampler_sha256
    lr = original.optimizer.param_groups[0]['lr']
    assert trainer.optimizer.param_groups[0]['lr'] == lr
    trainer.scheduler.set_consumed(3); assert trainer.optimizer.param_groups[0]['lr'] == pytest.approx(lr*.5)
    trainer.scheduler.set_consumed(4); assert trainer.optimizer.param_groups[0]['lr'] == 0.
    assert not any('parent_checkpoint' in key or 'parent_complete' in key for key in trainer.bindings)
    trainer.provider.close()


def test_actual_6x512_fork_resumes_and_exports_existing_H0_with_complete_chain(parent512,tmp_path):
    ref,request,values = child_metadata(tmp_path,parent512)
    child = construct_child(tmp_path,parent512,request,values)
    first = child.run_segment(segment_id='first',until_samples=3,request_ref=ref,preflight=lambda *args:None)
    child.trainer.next_step(1)
    for role in proxy.ROLES: child.trainer.validate(role)
    expected = (deepcopy(child.trainer.model.state_dict()),deepcopy(child.trainer.optimizer.state_dict()),
        deepcopy(child.trainer.provider.state_dict()),deepcopy(child.trainer.scheduler.state_dict()),capture_rng_state())
    resumed = construct_child(tmp_path,parent512,request,values,name='job2')
    last = resumed.run_segment(segment_id='second',until_samples=4,request_ref=ref,parent=first['last_checkpoint'],preflight=lambda *args:None)
    for left,right in zip(expected,(resumed.trainer.model.state_dict(),resumed.trainer.optimizer.state_dict(),
        resumed.trainer.provider.state_dict(),resumed.trainer.scheduler.state_dict(),capture_rng_state())): assert_tree_equal(left,right)
    assert last['status'] == 'BUDGET_REACHED_PENDING_EVALUATION' and last['optimizer_updates'] == 3
    chain = wsd.verify_fork_chain(resumed,last['last_checkpoint'])
    assert chain['parent_complete'] == parent512['complete'] and not chain['scientific_acceptance']
    assert resumed.controller.acknowledgements() == {}
    roots = resumed.lineage_output_roots()
    assert parent512['root']/'parent_job' in roots and parent512['ledger'] in roots
    assert tmp_path/'job1' in roots and tmp_path/'job2' in roots and tmp_path/'family' in roots
    assert len(resumed._all_checkpoint_directories()) == 4  # parent + child start/3/4
    event = next(body for _,body in resumed.controller.pending() if body['samples_consumed'] == 4)
    pair = load_encoder_pair(event['checkpoint'],event['model_configuration'],architecture_sha256=event['architecture_sha256'],
        pretraining_seed=event['pretraining_seed'],training_completion=event['training_completion'],enable_architecture_candidates=True)
    graph = Data(x=torch.tensor([[5],[0],[7]]),pos=torch.tensor([[0.,0.,0.],[1.,0.,0.],[0.,1.,0.]]))
    resumed.trainer.model.eval()
    with torch.no_grad():
        assert torch.equal(pair.candidate.encode_atoms(graph),resumed.trainer.model.encoder.encode_atoms(graph))
        assert pair.random_reference.encode_atoms(graph).shape == (3,512)
    assert pair.provenance['downstream_target_records_read'] == 0
    child.trainer.provider.close(); resumed.trainer.provider.close()


def test_family_fork_and_segment_caps_cannot_reset_at_a_fresh_child(parent512,tmp_path):
    ref,request,values = child_metadata(tmp_path,parent512)
    cfg,plan = values[:2]
    family = wsd.ForkFamily(tmp_path/'family',fork=request['fork'],policy=cfg['wsd_fork'],
        child_identity=proxy.identity(cfg),maximum_checkpoints=plan.max_total_checkpoints)
    family.register_child(lineage='one',ledger=tmp_path/'one_ledger',request_ref=ref)
    with pytest.raises(ValueError,match='fork count'):
        family.register_child(lineage='two',ledger=tmp_path/'two_ledger',request_ref=ref)
    with pytest.raises(ValueError,match='Existing/partial'):
        family.register_child(lineage='one',ledger=tmp_path/'different_ledger',request_ref=ref)
    # Parent roots/checkpoints remain part of the same immutable family budget.
    assert parent512['root']/'parent_job' in family.roots()
    assert len(family.checkpoint_directories()) == 1
    with pytest.raises(ValueError,match='family root differs'):
        wsd.ForkFamily(tmp_path/'fresh_family',fork=request['fork'],policy=cfg['wsd_fork'],
            child_identity=proxy.identity(cfg),maximum_checkpoints=plan.max_total_checkpoints)
    # One parent segment plus15 failed initializations consumes original16
    # attempts. A new directory may not grant a seventeenth attempt.
    for number in range(1,16):
        job = tmp_path/('failed'+str(number)); job.mkdir(); (job/'retained.partial').write_bytes(b'x')
        family.reserve_launch(tmp_path/'one_ledger',request_ref=ref,lineage='one',job_root=job,segment_id='f'+str(number),
            maximum_attempts=plan.max_total_checkpoints,maximum_bytes=cfg['proxy_contract']['resources']['ledger_bytes'])
    another = tmp_path/'another'; another.mkdir()
    with pytest.raises(ValueError,match='attempt cap reached'):
        family.reserve_launch(tmp_path/'one_ledger',request_ref=ref,lineage='one',job_root=another,segment_id='too_many',
            maximum_attempts=plan.max_total_checkpoints,maximum_bytes=cfg['proxy_contract']['resources']['ledger_bytes'])
    assert len(list((tmp_path/'one_ledger/launches').glob('*.json'))) == 15
    assert (tmp_path/'failed15/retained.partial').read_bytes() == b'x'


@pytest.mark.parametrize('schedule',[
    {'mode':'cosine','warmup_samples':0,'decay_start_samples':None,'minimum_ratio':0.},
    {'mode':'wsd','warmup_samples':3,'decay_start_samples':6,'minimum_ratio':0.}])
def test_actual_nonstable_original_checkpoint_cannot_be_relabelled_WSD(tmp_path,schedule):
    parent = create_parent(tmp_path/'nonstable',schedule=schedule)
    with pytest.raises(ValueError,match='parent stable interval'):
        child_metadata(tmp_path/'fork',parent)
    parent['experiment'].trainer.provider.close()


def test_two_seed_configuration_identity_keeps_parent_checkpoint_outside_recipe(parent512,tmp_path):
    _,request,values = child_metadata(tmp_path,parent512)
    left,right = deepcopy(values[0]),deepcopy(values[0]); left['seed'],right['seed'] = 0,1
    parent_left,parent_right = deepcopy(parent512['configuration']),deepcopy(parent512['configuration'])
    parent_left['seed'],parent_right['seed'] = 0,1
    assert proxy.identity(parent_left) == proxy.identity(parent_right)
    assert proxy.identity(left) == proxy.identity(right)
    assert 'parent_complete' not in left['wsd_fork'] and 'parent_request' not in left
    # Actual different seed parent refs are request provenance, never removed
    # recursively from arbitrary scientific configuration objects.
    changed = deepcopy(left); changed['proxy_contract']['validation']['seed'] += 1
    assert proxy.identity(changed) != proxy.identity(right)


def test_actual_native_sdk_child_and_fresh_process_resume(tmp_path):
    if not os.environ.get('SLURM_JOB_ID'): pytest.fail('Root must execute in the actual owned Slurm allocation')
    parent = create_parent(tmp_path/'parent_fixture',layers=1)
    ref,request,_ = child_metadata(tmp_path/'child_fixture',parent)
    tool = proxy.REPOSITORY/wsd.TOOL
    environment = {**os.environ,'CUDA_VISIBLE_DEVICES':'','WANDB_MODE':'offline','WANDB_SILENT':'true',
        'MODEL_V3_CHILD_OUTPUT_BUDGET_BYTES':str((2 << 30)-(16 << 20)-(2 << 20)-(96 << 20))}
    complete = None; run_ids = []
    root = tmp_path/'child_fixture'
    for name,endpoint in (('job1',3),('job2',4)):
        output = root/name
        command = [sys.executable,str(tool),'run','--request',ref['path'],'--request-sha256',ref['sha256'],
            '--input','synthetic','--engineering-only','--output',str(output),'--family-root',request['fork']['family_root'],
            '--lineage-root',str(root/'child_ledger'),'--lineage','sdk_child','--segment-id',name,'--until-samples',str(endpoint)]
        if complete is not None: command += ['--resume-complete',complete['path']]
        outcome = subprocess.run(command,env=environment,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=180)
        assert outcome.returncode == 0,outcome.stdout+'\n'+outcome.stderr
        receipt = read_bound(binding(output/'CHILD_RECEIPT.json'))
        assert receipt['status'] == 'CHILD_FINISHED_PENDING_ROOT_CLOSURE' and receipt['cleanup_errors'] == []
        assert not receipt['scientific_acceptance']; run_ids.append(receipt['native_sdk_run_id'])
        complete = receipt['outcome']['last_checkpoint']
        assert read_bound(binding(output/'FORK_CHAIN.json'))['parent_complete'] == parent['complete']
        assert len(list((output/'wandb').glob('offline-run-*/run-*.wandb'))) == 1
        history = [json.loads(row) for row in (output/'history.jsonl').read_text().splitlines()]
        assert history and all(v['commit'] for v in history)
    assert run_ids[0] != run_ids[1]
    assert receipt['outcome']['samples_consumed'] == 4 and receipt['outcome']['optimizer_updates'] == 3
    parent['experiment'].trainer.provider.close()
