"""Engineering protocol tests; no D authority, proxy acceptance or Slurm claims."""
from copy import deepcopy
from dataclasses import replace
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
import torch
from torch_geometric.data import Data

from test_model_v3_trainer import UnitTracker,make_trainer
from test_model_v3_training import assert_tree_equal
from test_model_v3_sample_budget import plan as tiny_plan,fake_result_and_evidence
from phychem_mfm.phase1 import v3_proxy_run as proxy
from phychem_mfm.phase1.v3_proxy_segments import BoundedLineageController,ProxySegmentExperiment,allocate_launch
from phychem_mfm.phase1.v3_proxy_engineering import synthetic_proxy_inputs
from phychem_mfm.phase1.v3_sample_budget_events import binding,read_bound,write_once,verify_checkpoint_record
from phychem_mfm.phase1.v3_training import capture_rng_state
from phychem_mfm.phase1.v3_encoder_bridge import load_encoder_pair
from phychem_mfm.phase1.v3_decision_evidence import reject_engineering_configuration

BASE = 'e47d066e53f000d71c05bf1c772597f2a5c42c30'


@pytest.fixture(autouse=True)
def cpu_environment():
    threads,precision = torch.get_num_threads(),torch.get_float32_matmul_precision()
    matmul,cudnn = torch.backends.cuda.matmul.allow_tf32,torch.backends.cudnn.allow_tf32
    torch.set_num_threads(1); torch.set_float32_matmul_precision('highest')
    torch.backends.cuda.matmul.allow_tf32 = False; torch.backends.cudnn.allow_tf32 = False
    try: yield
    finally:
        torch.set_num_threads(threads); torch.set_float32_matmul_precision(precision)
        torch.backends.cuda.matmul.allow_tf32 = matmul; torch.backends.cudnn.allow_tf32 = cudnn


def metadata(tmp_path,**kwargs):
    ref = proxy.engineering_request(tmp_path/'metadata',code_sha=BASE,**kwargs)
    request = read_bound(ref)
    configuration,plan,_ = proxy.validate_request(request,input_kind='synthetic',engineering_only=True)
    return ref,request,configuration,plan


def constructed(tmp_path,request,configuration,plan,*,name='job1',tracker=None):
    inputs = proxy.bind_inputs(request,configuration)
    exp = proxy.build_experiment(request,configuration,plan,inputs,tracker or UnitTracker(name),
        output_root=tmp_path/name/'training',lineage_root=tmp_path/'ledger',lineage='unit-engineering',
        device='cpu',allow_unit_tracker=True)
    return exp


@pytest.mark.parametrize('input_kind,flag',[('authoritative_proxy',False),('synthetic',False),('authoritative_proxy',True)])
def test_synthetic_requires_both_explicit_cli_gates(tmp_path,input_kind,flag):
    _,request,_,_ = metadata(tmp_path)
    with pytest.raises(ValueError): proxy.validate_request(request,input_kind=input_kind,engineering_only=flag)


@pytest.mark.parametrize('part',['source','projection','configuration'])
def test_actual_source_configuration_and_input_bytes_are_bound(tmp_path,part):
    _,request,_,_ = metadata(tmp_path)
    if part == 'source': request['sources']['runtime_files'][next(iter(request['sources']['runtime_files']))] = '0'*64
    elif part == 'projection': request['input_projection']['adapter_sha256'] = '0'*64
    else: Path(request['configuration']['path']).write_text('{}')
    with pytest.raises(ValueError): proxy.validate_request(request,input_kind='synthetic',engineering_only=True)


def test_registry_normalization_and_validation_membership_drift_rejected(tmp_path):
    _,request,config,_ = metadata(tmp_path)
    request['input_projection']['normalization_sha256'] = '0'*64
    with pytest.raises(ValueError,match='projection'): proxy.bind_inputs(request,config)
    _,good,config,_ = metadata(tmp_path/'other')
    config['proxy_contract']['validation']['population_bindings']['VAL'] = '0'*64
    with pytest.raises(ValueError,match='memberships'): proxy.bind_inputs(good,config)


def test_scientific_execution_rejects_dirty_source_and_candidate_adapter(tmp_path,monkeypatch):
    _,request,config,_ = metadata(tmp_path)
    scientific = deepcopy(request); scientific['mode'] = 'authoritative_proxy'
    scientific['sources'].update(state='clean_committed',tree_sha='a'*40)
    monkeypatch.setattr(proxy,'_git',lambda root,*args: BASE if args == ('rev-parse','HEAD') else 'a'*40 if args == ('rev-parse','HEAD^{tree}') else '?? dirty.py')
    with pytest.raises(ValueError,match='clean committed'): proxy.validate_sources(scientific)
    adapter = tmp_path/'candidate.py'
    adapter.write_text('from phychem_mfm.phase1.v3_proxy_engineering import synthetic_proxy_inputs\ndef verify_and_bind_model_v3_proxy_inputs(request):\n    return synthetic_proxy_inputs()\n')
    scientific['adapter'] = binding(adapter)
    with pytest.raises(ValueError,match='Final-D authority'): proxy.bind_inputs(scientific,config)


def test_engineering_configuration_cannot_enter_scientific_selection():
    reject_engineering_configuration({'seed':0})
    for marker in ({'engineering_only':True},{'experiment_scope':proxy.ENGINEERING}):
        with pytest.raises(ValueError,match='ineligible'): reject_engineering_configuration(marker)


def test_calibration_requires_own_registration_without_platform_circularity(tmp_path,monkeypatch):
    _,request,config,_ = metadata(tmp_path,layers=6)
    config['engineering_only'] = False; config['experiment_scope'] = 'CALIBRATION_ONLY'
    request['configuration'] = write_once(tmp_path/'scientific_config.json',config)
    request.update(mode='authoritative_proxy',scope='calibration',registrations={key:{} for key in ('budget','validation','calibration')})
    monkeypatch.setattr(proxy,'validate_sources',lambda r: config['runtime_source_inventory_sha256'])
    called = []
    def registered(ref,*,purpose,configuration):
        called.append(purpose); return {'verified_local_commit_epoch':1}
    monkeypatch.setattr(proxy,'_registration',registered)
    # Reaching Root admission proves no already-confirmed platform prerequisite
    # was inserted. This mocked boundary is not scientific registration proof.
    with pytest.raises(KeyError,match='Root_admission'): proxy.validate_request(request)
    assert set(called) == {'budget','validation','calibration'}
    request['scope'] = 'comparison'
    with pytest.raises(ValueError,match='Missing explicit preregistered'): proxy.validate_request(request)


def test_validation_uses_actual_sse_fixed_context_and_preserves_training_rng(tmp_path):
    _,request,config,plan = metadata(tmp_path)
    exp = constructed(tmp_path,request,config,plan)
    trainer = exp.trainer
    before = (capture_rng_state(),deepcopy(trainer.provider.state_dict()),trainer.view_config)
    first = trainer.validate('VAL')
    for field in first['fields'].values():
        if field.get('RMSE') is not None:
            assert field['RMSE']**2 == pytest.approx(field['squared_error_sum']/field['component_denominator'])
    assert first['validation_seed'] == 0 and first['validation_epoch'] == 0
    assert_tree_equal(before[0],capture_rng_state()); assert_tree_equal(before[1],trainer.provider.state_dict())
    assert before[2] == trainer.view_config
    trainer.provider.generator.manual_seed(999); trainer.provider.calls += 19
    second = trainer.validate('VAL')
    assert first['input_population_sha256'] == second['input_population_sha256']
    assert first['fields'] == second['fields']
    trainer.provider.close()


def test_original_numerical_resume_across_fresh_jobs_and_canonical_outbox(tmp_path):
    ref,request,config,plan = metadata(tmp_path,budget=3)
    exp = constructed(tmp_path,request,config,plan)
    first = exp.run_segment(segment_id='one',until_samples=2,request_ref=ref,preflight=lambda *a: None)
    exp.trainer.next_step(1)
    for role in proxy.ROLES: exp.trainer.validate(role)
    expected = (deepcopy(exp.trainer.model.state_dict()),deepcopy(exp.trainer.optimizer.state_dict()),
        deepcopy(exp.trainer.provider.state_dict()),deepcopy(exp.trainer.scheduler.state_dict()),capture_rng_state())
    restored = constructed(tmp_path,request,config,plan,name='job2')
    last = restored.run_segment(segment_id='two',until_samples=3,request_ref=ref,parent=first['last_checkpoint'],preflight=lambda *a: None)
    actual = (restored.trainer.model.state_dict(),restored.trainer.optimizer.state_dict(),restored.trainer.provider.state_dict(),
        restored.trainer.scheduler.state_dict(),capture_rng_state())
    for a,b in zip(expected,actual): assert_tree_equal(a,b)
    assert last['status'] == 'BUDGET_REACHED_PENDING_EVALUATION'
    assert restored.trainer.clock.samples_consumed == restored.trainer.sampler.samples_consumed == 3
    assert sorted(body['samples_consumed'] for _,body in restored.controller.pending()) == [2,3]
    assert restored.trainer.resume_parent['id'] == exp.trainer.tracker.id
    roots = restored.lineage_output_roots()
    assert set(roots) == {tmp_path/'job1',tmp_path/'job2',tmp_path/'ledger'}
    assert len(restored._all_checkpoint_directories()) == 2
    exp.trainer.provider.close(); restored.trainer.provider.close()


def test_global_attempt_cap_partial_retention_and_foreign_resume_rejection(tmp_path):
    contract = {'synthetic_fixture':True}
    ledger = BoundedLineageController(tmp_path/'ledger',contract=contract,max_records=1,maximum_bytes=8 << 20)
    ref = write_once(tmp_path/'request.json',{'schema':'NOT_A_CHECKPOINT','fixture':True})
    ledger.register_segment(segment_id='one',experiment_root=tmp_path/'job1'/'training',request_ref=ref,parent=None)
    partial = tmp_path/'job1/training/segments/one/checkpoint_partial'
    partial.mkdir(parents=True); (partial/'payload.partial').write_bytes(b'unpublished')
    with pytest.raises(ValueError,match='attempt cap'):
        ledger.register_segment(segment_id='two',experiment_root=tmp_path/'job2'/'training',request_ref=ref,parent=None)
    assert (partial/'payload.partial').read_bytes() == b'unpublished'
    with pytest.raises(ValueError): ledger.publish(binding(ref['path']))


def test_true_small_original_trainer_recovery_rejects_changed_parent_contract(tmp_path):
    trainer = make_trainer(budget=3,milestones=(2,),groups=('P',))
    plan = tiny_plan(3,(2,3),max_total_checkpoints=2,max_checkpoints_per_segment=1)
    exp = ProxySegmentExperiment(trainer,plan,output_root=tmp_path/'job1/training',lineage='tiny',
        input_scope='synthetic_fixture',lineage_root=tmp_path/'ledger',ledger_bytes=8 << 20)
    req = write_once(tmp_path/'request.json',{'fixture':True})
    first = exp.run_segment(segment_id='first',until_samples=3,request_ref=req,preflight=lambda *a: None)
    assert first['status'] == 'SEGMENT_PAUSED' and first['samples_consumed'] == 2
    altered = ProxySegmentExperiment(make_trainer(budget=3,milestones=(2,),groups=('P',)),plan,
        output_root=tmp_path/'job2/training',lineage='tiny',input_scope='synthetic_fixture',
        lineage_root=tmp_path/'ledger',ledger_bytes=8 << 20)
    altered.trainer.bindings['configuration_sha256'] = 'f'*64
    with pytest.raises(ValueError,match='binding'): altered.resume_from(first['last_checkpoint'])
    assert len(altered.controller.pending()) == 1


@pytest.fixture(scope='module')
def ready512(tmp_path_factory):
    root = tmp_path_factory.mktemp('proxy-ready512')
    # Keep one real6x512 payload in this test module; other fixtures use1layer.
    threads,precision = torch.get_num_threads(),torch.get_float32_matmul_precision()
    matmul,cudnn = torch.backends.cuda.matmul.allow_tf32,torch.backends.cudnn.allow_tf32
    torch.set_num_threads(1); torch.set_float32_matmul_precision('highest')
    torch.backends.cuda.matmul.allow_tf32 = False; torch.backends.cudnn.allow_tf32 = False
    try:
        ref,request,config,plan = metadata(root,layers=6,budget=1)
        exp = constructed(root,request,config,plan)
        outcome = exp.run_segment(segment_id='one',until_samples=1,request_ref=ref,preflight=lambda *a: None)
        yield root,exp,outcome
        exp.trainer.provider.close()
    finally:
        torch.set_num_threads(threads); torch.set_float32_matmul_precision(precision)
        torch.backends.cuda.matmul.allow_tf32 = matmul; torch.backends.cudnn.allow_tf32 = cudnn


def test_real_6x512_checkpoint_roundtrips_existing_target_free_h0_bridge(ready512):
    root,exp,outcome = ready512
    event = exp.controller.pending()[0][1]
    assert event['status'] == 'READY'
    pair = load_encoder_pair(event['checkpoint'],event['model_configuration'],architecture_sha256=event['architecture_sha256'],
        pretraining_seed=event['pretraining_seed'],training_completion=event['training_completion'],enable_architecture_candidates=True)
    graph = Data(x=torch.tensor([[5],[0],[7]]),pos=torch.tensor([[0.,0.,0.],[1.,0.,0.],[0.,1.,0.]]))
    exp.trainer.model.eval()
    with torch.no_grad():
        assert torch.equal(pair.candidate.encode_atoms(graph),exp.trainer.model.encoder.encode_atoms(graph))
        assert pair.random_reference.encode_atoms(graph).shape == (3,512)
    assert pair.provenance['downstream_target_records_read'] == 0
    capacity = proxy.checkpoint_capacity(exp.trainer)
    assert capacity['tensor_floor_bytes'] > 0 and not capacity['serialization_upper_bound_proven']
    actual = Path(event['checkpoint']['path']).stat().st_size
    assert actual > capacity['model_tensor_bytes']
    print(json.dumps({'synthetic_6x512_actual_checkpoint_bytes':actual,'capacity':capacity}))


def test_independent_ack_survives_new_controller_and_refuses_changed_evidence(ready512):
    root,exp,_ = ready512
    event_ref,event = exp.controller.pending()[0]
    original_result,original_evidence = fake_result_and_evidence(root,event)
    value = read_bound(original_result)
    for key,cache in value['h0_caches'].items():
        cache['binding']['membership_sha256'] = event['panel_binding']['membership_sha256'][key.split('/')[1]]
    result = write_once(root/'matching_result.json',value)
    proof = read_bound(original_evidence); sdk = read_bound(proof['sdk_verification'])
    sdk['inputs']['result'] = result
    proof['result'] = result; proof['sdk_verification'] = write_once(root/'matching_sdk_fixture.json',sdk)
    evidence = write_once(root/'matching_evidence_fixture.json',proof)
    exp.controller.acknowledge(event_ref,result,evidence)
    same = BoundedLineageController(exp.controller.root,contract=exp.contract,
        max_records=exp.plan.max_total_checkpoints,maximum_bytes=16 << 20)
    assert same.pending() == [] and len(same.acknowledgements()) == 1
    changed = write_once(root/'different_evidence.json',{'fixture_changed':True})
    with pytest.raises(ValueError,match='replay'): same.acknowledge(event_ref,result,changed)
    # These evidence files are synthetic unit fixtures, never Root C0 proof.


def test_existing_ledger_lock_and_byte_caps_are_not_reset(tmp_path):
    ledger = BoundedLineageController(tmp_path/'ledger',contract={'fixture':True},max_records=2,maximum_bytes=8 << 20)
    (ledger.root/'retained.partial').write_bytes(b'x'*(8 << 20))
    with pytest.raises(ValueError,match='cap exhausted'):
        BoundedLineageController(ledger.root,contract=ledger.contract,max_records=2,maximum_bytes=8 << 20)


def test_failed_sdk_initializations_still_consume_global_launch_and_storage(tmp_path):
    ref = write_once(tmp_path/'request.json',{'engineering_fixture':True})
    for number in (1,2):
        job = tmp_path/('failed_job'+str(number)); job.mkdir()
        (job/'unpublished_sdk.partial').write_bytes(b'x'*number)
        allocate_launch(tmp_path/'ledger',request_ref=ref,lineage='engineering-fixture',job_root=job,
            segment_id='attempt'+str(number),maximum_attempts=2,maximum_bytes=8 << 20)
    ledger = BoundedLineageController(tmp_path/'ledger',contract={'engineering_fixture':True},
        max_records=2,maximum_bytes=8 << 20)
    assert set(ledger.launch_roots()) == {tmp_path/'failed_job1',tmp_path/'failed_job2'}
    third = tmp_path/'third'; third.mkdir()
    with pytest.raises(ValueError,match='attempt cap'):
        allocate_launch(tmp_path/'ledger',request_ref=ref,lineage='engineering-fixture',job_root=third,
            segment_id='third',maximum_attempts=2,maximum_bytes=8 << 20)
    assert (tmp_path/'failed_job2/unpublished_sdk.partial').read_bytes() == b'xx'


def test_canonical_sdk_environment_and_parser_explicit_endpoint(monkeypatch,tmp_path):
    path = proxy.REPOSITORY/'tools/model_v3/run_proxy_experiment.py'
    spec = importlib.util.spec_from_file_location('proxy_cli_test',path)
    cli = importlib.util.module_from_spec(spec); spec.loader.exec_module(cli)
    for key in ('WANDB_MODE','WANDB_DIR','WANDB_CACHE_DIR','WANDB_DATA_DIR','WANDB_CONFIG_DIR'):
        monkeypatch.setenv(key,'temporary_test_environment')
    cli.sdk_environment(tmp_path)
    assert os.environ['WANDB_CACHE_DIR'] == str(tmp_path/'cache')
    assert os.environ['WANDB_DATA_DIR'] == str(tmp_path/'wandb_data')
    with pytest.raises(SystemExit): cli.parser().parse_args(['run'])


def test_actual_offline_sdk_cli_runs_and_resumes_fresh_interpreter(tmp_path):
    """Actual native SDK, not a mocked tracker. Root supplies real Slurm closure.

    This in-allocation child tests its cooperative guards and persistent SDK.
    It does not pretend this direct subprocess is an independent supervisor.
    """
    if not os.environ.get('SLURM_JOB_ID'):
        pytest.fail('Root must run this target under the owned CPU Slurm allocation')
    ref,request,config,plan = metadata(tmp_path,budget=3)
    cli = proxy.REPOSITORY/'tools/model_v3/run_proxy_experiment.py'
    environment = {**os.environ,'CUDA_VISIBLE_DEVICES':'',
        'MODEL_V3_CHILD_OUTPUT_BUDGET_BYTES':str((2 << 30)-(16 << 20)-(96 << 20)),
        'WANDB_MODE':'offline','WANDB_SILENT':'true'}
    parent = None; receipts = []
    for name,endpoint in (('job1',2),('job2',3)):
        output = tmp_path/name
        command = [sys.executable,str(cli),'run','--input','synthetic','--engineering-only',
            '--request',ref['path'],'--request-sha256',ref['sha256'],'--output',str(output),
            '--lineage-root',str(tmp_path/'ledger'),'--lineage','sdk-engineering','--segment-id',name,'--until-samples',str(endpoint)]
        if parent: command += ['--resume-complete',parent['path']]
        completed = subprocess.run(command,env=environment,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,text=True,timeout=180)
        assert completed.returncode == 0, completed.stdout+'\n'+completed.stderr
        receipt = read_bound(binding(output/'CHILD_RECEIPT.json')); receipts.append(receipt)
        assert receipt['status'] == 'CHILD_FINISHED_PENDING_ROOT_CLOSURE'
        assert not receipt['scientific_acceptance'] and receipt['cleanup_errors'] == []
        parent = receipt['outcome']['last_checkpoint']
        native = list((output/'wandb').glob('offline-run-*/run-*.wandb'))
        assert len(native) == 1 and native[0].stat().st_size > 0
        rows = [json.loads(line) for line in (output/'history.jsonl').read_text().splitlines()]
        assert rows and all(row['commit'] for row in rows)
        assert [row['step'] for row in rows] == sorted({row['step'] for row in rows})
        assert {row['row']['role'] for row in rows if row['row'].get('event') == 'VALIDATION'} == set(proxy.ROLES)
    assert receipts[0]['native_sdk_run_id'] != receipts[1]['native_sdk_run_id']
    assert receipts[1]['outcome']['samples_consumed'] == 3
    assert receipts[1]['outcome']['optimizer_updates'] == 2
