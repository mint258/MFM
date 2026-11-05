"""Real engineering CLI/metadata guards; never final-data or CUDA acceptance.

The six-layer bridge suite imports run_cli_pair, sharing a single large CP
family. This module's own CLI test uses one layer. Root executes every test in
an owned CPU Slurm allocation and supplies the independent outer closure.
"""
from copy import deepcopy
from dataclasses import asdict
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
import torch

from phychem_mfm.phase1 import v3_proxy_run as proxy
from phychem_mfm.phase1.v3_contract import canonical_hash
from phychem_mfm.phase1.v3_proxy_segments import BoundedLineageController
from phychem_mfm.phase1.v3_sample_budget_events import binding, read_bound, write_once

BASE = '81948e457c29fbc51687066a4f944ff5bcd5bad5'
MANUAL = {'options': {'backbone_checkpointing': True}, 'batch_padded_cost': 10000}


def run_cli_pair(tmp_path, *, layers=1, training_execution=None, budget=3):
    """Two actual fresh CLI processes, with immutable resume and native SDKs.

    A checkpoint reconstructed afterward is a saved-state control, not an
    observation of a live pre-save encoder. No fake Slurm/job identity is set.
    """
    assert os.environ.get('SLURM_JOB_ID'), 'Root must supply an actual owned CPU allocation'
    assert int(os.environ.get('SLURM_CPUS_PER_TASK', '0')) >= 16
    assert budget == 3, 'This bounded fixture owns exactly two small engineering segments'
    tmp_path = Path(tmp_path)
    ref = proxy.engineering_request(tmp_path/'metadata', code_sha=BASE, layers=layers,
        budget=budget, training_execution=training_execution)
    request = read_bound(ref)
    configuration = read_bound(request['configuration'])
    cli = proxy.REPOSITORY/'tools/model_v3/run_proxy_experiment.py'
    environment = {**os.environ, 'CUDA_VISIBLE_DEVICES': '', 'WANDB_MODE': 'offline', 'WANDB_SILENT': 'true',
        'MODEL_V3_CHILD_OUTPUT_BUDGET_BYTES': str((2 << 30)-(16 << 20)-(96 << 20))}
    parent = None
    receipts = []
    lineage_root = tmp_path/'ledger'
    lineage = 'training-entry-engineering'
    for name, endpoint in (('job1', 2), ('job2', 3)):
        output = tmp_path/name
        command = [sys.executable, str(cli), 'run', '--input', 'synthetic', '--engineering-only',
            '--request', ref['path'], '--request-sha256', ref['sha256'], '--output', str(output),
            '--lineage-root', str(lineage_root), '--lineage', lineage, '--segment-id', name,
            '--until-samples', str(endpoint)]
        if parent is not None:
            command += ['--resume-complete', parent['path']]
        completed = subprocess.run(command, env=environment, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=180)
        # Preserve failed subprocess diagnostics in the owning fixture output.
        (tmp_path/(name+'_cli_stdout.txt')).write_text(completed.stdout, encoding='utf-8')
        (tmp_path/(name+'_cli_stderr.txt')).write_text(completed.stderr, encoding='utf-8')
        assert completed.returncode == 0, completed.stdout+'\n'+completed.stderr
        receipt = read_bound(binding(output/'CHILD_RECEIPT.json'))
        assert receipt['status'] == 'CHILD_FINISHED_PENDING_ROOT_CLOSURE'
        assert receipt['cleanup_errors'] == [] and receipt['scientific_acceptance'] is False
        assert receipt['first_failure'] is None
        assert str(receipt['job_id']) == os.environ['SLURM_JOB_ID']
        native = list((output/'wandb').glob('offline-run-*/run-*.wandb'))
        assert len(native) == 1 and native[0].stat().st_size > 0
        rows = [json.loads(line) for line in (output/'history.jsonl').read_text().splitlines()]
        assert rows and all(row['commit'] is True for row in rows)
        assert [row['step'] for row in rows] == sorted({row['step'] for row in rows})
        assert {row['row']['role'] for row in rows if row['row'].get('event') == 'VALIDATION'} == set(proxy.ROLES)
        receipts.append(receipt)
        parent = receipt['outcome']['last_checkpoint']
    contract = read_bound(binding(lineage_root/'EXPERIMENT.json'))['contract']
    controller = BoundedLineageController(lineage_root, contract=contract,
        max_records=contract['plan']['max_total_checkpoints'],
        maximum_bytes=configuration['proxy_contract']['resources']['ledger_bytes'])
    event_ref, event = max(controller.pending(), key=lambda item: item[1]['samples_consumed'])
    assert event['samples_consumed'] == 3 and event['optimizer_updates'] == 2
    assert receipts[0]['native_sdk_run_id'] != receipts[1]['native_sdk_run_id']
    return {'request_ref': ref, 'request': request, 'configuration': configuration,
        'first_result': receipts[0], 'second_result': receipts[1], 'event': event, 'event_ref': event_ref,
        'last_checkpoint': parent, 'root': tmp_path, 'lineage_root': lineage_root, 'lineage': lineage,
        'final_training_root': tmp_path/'job2/training',
        'trainer_checkpoint_directory': Path(event['checkpoint']['path']).parent}


def _metadata(tmp_path, **kwargs):
    ref = proxy.engineering_request(tmp_path/'metadata', code_sha=BASE, **kwargs)
    request = read_bound(ref)
    configuration, plan, _ = proxy.validate_request(request, input_kind='synthetic', engineering_only=True)
    return ref, request, configuration, plan


@pytest.fixture
def workload_case(tmp_path):
    _, request, configuration, _ = _metadata(tmp_path, training_execution=MANUAL)
    inputs = proxy.bind_inputs(request, configuration)
    try:
        yield request, configuration, proxy.training_workload_binding(request, configuration, inputs)
    finally:
        inputs.provider.close()


def test_real_cli_execution_update_safe_save_fresh_resume_and_outbox(tmp_path):
    case = run_cli_pair(tmp_path, training_execution=MANUAL)
    assert case['event']['status'] == 'BLOCKED_UNSUPPORTED_ENCODER'  # one layer never becomes primary
    assert case['event']['training_execution_contract_sha256']
    assert case['event']['H0_export_sha256']
    for receipt in (case['first_result'], case['second_result']):
        artifacts = receipt['training_execution_capacity_artifacts']
        assert set(artifacts) == {'configuration', 'summary', 'steps'}
        saved = read_bound(artifacts['configuration'])
        assert saved['workload']['scope'] == 'engineering_synthetic_fixture'
        rows = [json.loads(line) for line in Path(artifacts['steps']['path']).read_text().splitlines()]
        assert rows and {row['role'] for row in rows} == {'TRAIN', *proxy.ROLES}
        assert all(row['resources']['gpu_observation'] is None for row in rows)
        assert any(row['role'] == 'TRAIN' for row in rows)
    assert case['second_result']['outcome']['samples_consumed'] == 3
    assert case['second_result']['outcome']['optimizer_updates'] == 2


def test_workload_is_reconstructed_from_actual_metadata(workload_case):
    request, configuration, workload = workload_case
    assert proxy.validate_training_workload_request(workload, request, configuration) is None
    assert workload['view_policy']['sample_budget'] == 6
    assert workload['data']['validation_population_bindings'] == configuration['proxy_contract']['validation']['population_bindings']
    assert 'configuration_sha256' not in workload and 'configuration_sha256' not in workload['data']
    assert workload['optimizer']['foreach'] is False and workload['optimizer']['fused'] is False


@pytest.mark.parametrize('part', ('heads', 'groups', 'fields', 'views', 'view_policy', 'loss', 'optimizer',
    'validation', 'registry_projection', 'normalization_projection', 'authority_sha256', 'input_projection'))
def test_workload_qualifier_rejects_self_reported_numerical_or_data_drift(workload_case, part):
    request, configuration, good = workload_case
    value = deepcopy(good)
    if part in ('registry_projection', 'normalization_projection', 'authority_sha256', 'input_projection'):
        value['data'][part] = 'unbound'
    else:
        value[part] = 'unbound'
    with pytest.raises((ValueError, TypeError, KeyError, AttributeError)):
        proxy.validate_training_workload_request(value, request, configuration)


def test_minimal_execution_policy_and_persisted_semantic_form_match(tmp_path):
    _, _, configuration, _ = _metadata(tmp_path, training_execution=MANUAL)
    from phychem_mfm.phase1.v3_training_execution import TrainingExecutionSpec
    assert configuration['training_execution'] == TrainingExecutionSpec(**MANUAL).semantic()
    assert configuration['proxy_contract']['precision']['mode'] == 'fp32'


@pytest.mark.parametrize('key', ('performance_execution_v1', 'training_execution'))
def test_model_nested_execution_cannot_silently_reach_plain_factory(tmp_path, key):
    _, request, configuration, _ = _metadata(tmp_path)
    configuration['model'][key] = {}
    request['configuration'] = write_once(tmp_path/'bad_configuration.json', configuration)
    with pytest.raises(ValueError):
        proxy.validate_request(request, input_kind='synthetic', engineering_only=True)


def test_auto_requires_own_exact_training_capacity_admission(tmp_path):
    execution = {'options': {}, 'batch_padded_cost': 10000, 'checkpoint_policy': 'auto_closed_training_profile_v1'}
    _, request, _, _ = _metadata_without_validation(tmp_path, training_execution=execution)
    with pytest.raises(ValueError, match='profile'):
        proxy.validate_request(request, input_kind='synthetic', engineering_only=True)


def _metadata_without_validation(tmp_path, **kwargs):
    ref = proxy.engineering_request(tmp_path/'metadata', code_sha=BASE, **kwargs)
    request = read_bound(ref)
    return ref, request, read_bound(request['configuration']), None


def test_observer_configuration_is_saved_after_forward_not_on_install(tmp_path):
    """Narrow lifecycle test, not a capacity or native SDK certificate."""
    cli = _cli_module()
    class Observer:
        def __init__(self): self.completed = False; self.calls = []
        def set_sink(self, sink): self.sink = sink
        def configuration(self, *, request_reference):
            assert self.completed
            self.calls.append('configuration'); return {'actual_forward': True}
        def summary(self): self.calls.append('summary'); return {'actual_records': 1}
    class Handle:
        observer = Observer()
    class Trainer:
        training_execution = Handle()
    class Experiment:
        trainer = Trainer()
    output = tmp_path/'output'; output.mkdir()
    cfg = {'proxy_contract': {'resources': {'tracking_bytes': 1 << 20}, 'execution': {'device': 'cpu'}},
        'engineering_only': True}
    observation = cli.install_training_observer(Experiment(), cfg, output, request_reference={'unit_only': True})
    assert observation['observer'].calls == []
    observation['observer'].completed = True
    artifacts = cli.finalize_training_observer(observation, output)
    assert set(artifacts) == {'configuration', 'summary', 'steps'}
    assert observation['observer'].calls == ['configuration', 'summary']


@pytest.fixture
def exact_cpu_policy():
    old = (torch.get_num_threads(), torch.get_float32_matmul_precision(),
        torch.backends.cuda.matmul.allow_tf32, torch.backends.cudnn.allow_tf32,
        torch.are_deterministic_algorithms_enabled())
    torch.set_num_threads(1); torch.set_float32_matmul_precision('highest')
    torch.backends.cuda.matmul.allow_tf32 = False; torch.backends.cudnn.allow_tf32 = False
    torch.use_deterministic_algorithms(True)
    try:
        yield
    finally:
        torch.set_num_threads(old[0]); torch.set_float32_matmul_precision(old[1])
        torch.backends.cuda.matmul.allow_tf32 = old[2]; torch.backends.cudnn.allow_tf32 = old[3]
        torch.use_deterministic_algorithms(old[4])


def _cli_module():
    directory = str(proxy.REPOSITORY/'tools/model_v3')
    if directory not in sys.path:
        sys.path.insert(0, directory)  # same import directory as the genuine CLI process
    spec = importlib.util.spec_from_file_location('training_entry_cli_lifecycle',
        proxy.REPOSITORY/'tools/model_v3/run_proxy_experiment.py')
    cli = importlib.util.module_from_spec(spec); spec.loader.exec_module(cli)
    return cli


@pytest.fixture
def executed_parent(tmp_path, exact_cpu_policy):
    """One small saved checkpoint shared by the assertions in each test."""
    from test_model_v3_trainer import UnitTracker
    ref, request, configuration, _ = _metadata(tmp_path, training_execution=MANUAL, budget=8)
    configuration['proxy_contract']['schedule'] = {
        'mode':'wsd','warmup_samples':0,'decay_start_samples':6,'minimum_ratio':0.}
    request['configuration'] = write_once(tmp_path/'stable_configuration.json', configuration)
    ref = write_once(tmp_path/'stable_request.json', request)
    configuration, plan, _ = proxy.validate_request(request, input_kind='synthetic', engineering_only=True)
    inputs = proxy.bind_inputs(request, configuration)
    exp = proxy.build_experiment(request, configuration, plan, inputs, UnitTracker('entry-unit-parent'),
        output_root=tmp_path/'parent_job/training', lineage_root=tmp_path/'parent_ledger',
        lineage='entry-parent', device='cpu', allow_unit_tracker=True)
    cli = _cli_module()
    observation = cli.install_training_observer(exp, configuration, tmp_path/'parent_job', request_reference=ref)
    result = exp.run_segment(segment_id='parent', until_samples=2, request_ref=ref, preflight=lambda *args: None)
    assert exp.trainer.clock.optimizer_updates == 1
    try:
        yield {'experiment': exp, 'configuration': configuration, 'request': request, 'request_ref': ref,
            'complete': result['last_checkpoint'], 'ledger': tmp_path/'parent_ledger',
            'registration': binding(tmp_path/'parent_ledger/segments/parent.json'), 'root': tmp_path}
    finally:
        inputs.provider.close()


def test_restore_rejects_execution_contract_before_changing_flags(executed_parent):
    from phychem_mfm.phase1.v3_trainer import _execution_state, _restore_execution
    trainer = executed_parent['experiment'].trainer
    before = _execution_state(trainer.model)
    wrong = deepcopy(before)
    wrong['training_execution']['workload_sha256'] = 'f'*64
    with pytest.raises(ValueError):
        _restore_execution(trainer.model, wrong)
    assert _execution_state(trainer.model) == before
    assert trainer.clock.samples_consumed == 2


def _fork_case(executed_parent, *, drift=False):
    from phychem_mfm.phase1 import v3_wsd_fork as wsd
    from test_model_v3_trainer import UnitTracker
    root = executed_parent['root']/'child'
    ref = wsd.engineering_fork_request(root/'metadata', parent_request_ref=executed_parent['request_ref'],
        parent_complete_ref=executed_parent['complete'], parent_ledger=executed_parent['ledger'],
        parent_segment_registration=executed_parent['registration'], family_root=root/'family', code_sha=BASE, decay_samples=2)
    request = read_bound(ref)
    config, plan, _, parent, parent_config, state, _ = wsd.validate_fork(request, input_kind='synthetic', engineering_only=True)
    family = wsd.ForkFamily(root/'family', fork=request['fork'], policy=config['wsd_fork'],
        child_identity=proxy.identity(config), maximum_checkpoints=plan.max_total_checkpoints)
    family.register_child(lineage='entry-child', ledger=root/'ledger', request_ref=ref)
    inputs = proxy.bind_inputs(parent, parent_config)
    if drift:
        config = deepcopy(config)
        config['proxy_contract']['clip_norm'] *= 2
    try:
        child = wsd.restore_and_fork(request, config, plan, inputs, UnitTracker('entry-unit-child'),
            output_root=root/'job', lineage_root=root/'ledger', lineage='entry-child', family=family,
            parent=parent, parent_config=parent_config, parent_state=state, allow_unit_tracker=True)
    except BaseException:
        inputs.provider.close()
        raise
    return child, inputs, ref, config


def test_wsd_rebind_preserves_draw_adam_rng_clock_and_new_child_contract(executed_parent):
    from phychem_mfm.phase1.v3_training import capture_rng_state
    from test_model_v3_training import assert_tree_equal
    parent = executed_parent['experiment'].trainer
    expected_rng = capture_rng_state()
    child, inputs, ref, cfg = _fork_case(executed_parent)
    try:
        trainer = child.trainer
        assert_tree_equal(trainer.model.state_dict(), parent.model.state_dict())
        assert_tree_equal(trainer.optimizer.state_dict(), parent.optimizer.state_dict())
        assert_tree_equal(expected_rng, capture_rng_state())
        assert trainer.log_cursor == parent.log_cursor
        assert trainer.clock.samples_consumed == trainer.sampler.samples_consumed == 2
        assert trainer.clock.optimizer_updates == parent.clock.optimizer_updates
        assert trainer.training_execution.contract == trainer.contract['training_execution']
        assert trainer.training_execution.workload_binding['view_policy']['sample_budget'] == 4
        assert parent.training_execution.workload_binding['view_policy']['sample_budget'] == 8
        assert trainer.training_execution.contract != parent.training_execution.contract
        observation = _cli_module().install_training_observer(child, cfg, child.root.parent, request_reference=ref)
        result = child.run_segment(segment_id='decay', until_samples=3, request_ref=ref, preflight=lambda *args: None)
        assert result['samples_consumed'] == 3 and result['optimizer_updates'] == 2
        rows = [json.loads(line) for line in observation['steps_path'].read_text().splitlines()]
        assert rows and rows[0]['samples_consumed'] == 3
    finally:
        inputs.provider.close()


def test_wsd_rebind_rejects_non_schedule_scientific_drift(executed_parent):
    with pytest.raises(ValueError):
        _fork_case(executed_parent, drift=True)


def _execution_ack_case(tmp_path):
    """Synthetic comparator fixture only; no real panel/Root/SDK certificate."""
    from test_model_v3_sample_budget import fake_result_and_evidence
    from phychem_mfm.phase1.v3_execution_checkpoint_bridge import training_execution_cache_projection
    from phychem_mfm.phase1.v3_sample_budget_events import _execution_digest
    event = {'status':'READY','checkpoint':{'sha256':'1'*64}, 'model_configuration':{'sha256':'2'*64},
        'training_completion':{'sha256':'3'*64}, 'pretraining_seed':7,'architecture_sha256':'4'*64,
        'panel_binding': {'panel_sha256':'5'*64,'training_store_sha256':'6'*64,
            'membership_sha256':{name:'c'*64 for name in ('cyp_isoform','expansionrx','qm9')},
            'preregistration_sha':'7'*40,'code_sha':'8'*40}}
    mapping = {'schema':'model_v3_training_h0_export_v1','precision':'fp32'}
    contract = {'schema':'model_v3_training_execution_contract_v1','h0_export':mapping,'execution_state':{}}
    execution = {'training_contract':contract,'training_execution_contract_sha256':canonical_hash(contract),
        'H0_export':mapping,'H0_export_sha256':canonical_hash(mapping),'bridge_implementation':{'path':'synthetic','sha256':'9'*64},
        'H0_export_precision':'fp32_no_internal_AMP','BF16_training_forward_bitwise_replay_claimed':False,
        'training_capacity_reused_for_downstream_H0':False,
        'saved_runtime_execution_sha256':canonical_hash({'training_execution':contract}),
        'committed_samples_consumed':6,'committed_optimizer_updates':2,'committed_log_cursor':3,'scientific_acceptance':False}
    for name in ('training_execution_contract_sha256','H0_export_sha256'):
        event[name] = execution[name]
    original, evidence_ref = fake_result_and_evidence(tmp_path, event)
    result = read_bound(original)
    result['encoder_pair']['training_execution'] = execution
    for cache in result['h0_caches'].values():
        source = {'training_execution':training_execution_cache_projection(execution),
            'training_completion':event['training_completion']}
        cache['binding']['execution_source'] = source
        cache['binding']['execution_source_sha256'] = _execution_digest(source, ascii_json=True)
    result_ref = write_once(tmp_path/'execution_result.json', result)
    evidence = read_bound(evidence_ref)
    sdk = read_bound(evidence['sdk_verification']); sdk['inputs']['result'] = result_ref
    evidence['sdk_verification'] = write_once(tmp_path/'execution_sdk_fixture.json', sdk)
    evidence['result'] = result_ref
    return event, result_ref, result, evidence


def test_execution_ack_uses_same_compact_projection_and_original_completion(tmp_path):
    from phychem_mfm.phase1.v3_sample_budget_events import validate_panel_evidence
    event, result_ref, result, evidence = _execution_ack_case(tmp_path)
    assert validate_panel_evidence(event, result_ref, result, evidence) is None
    assert 'training_contract' not in result['h0_caches']['candidate/qm9']['binding']['execution_source']['training_execution']


@pytest.mark.parametrize('drift', ('event_hash','export_map','saved_state','cache_contract','cache_complete','cache_source_hash','legacy_event'))
def test_execution_ack_rejects_contract_map_or_cache_reuse_drift(tmp_path, drift):
    from phychem_mfm.phase1.v3_sample_budget_events import validate_panel_evidence
    event, result_ref, result, evidence = _execution_ack_case(tmp_path)
    cache = result['h0_caches']['candidate/qm9']['binding']
    if drift == 'event_hash': event['training_execution_contract_sha256'] = 'f'*64
    elif drift == 'export_map': result['encoder_pair']['training_execution']['H0_export']['precision'] = 'bf16'
    elif drift == 'saved_state': result['encoder_pair']['training_execution']['saved_runtime_execution_sha256'] = 'f'*64
    elif drift == 'cache_contract': cache['execution_source']['training_execution']['training_execution_contract_sha256'] = 'f'*64
    elif drift == 'cache_complete': cache['execution_source']['training_completion'] = {'sha256':'f'*64}
    elif drift == 'cache_source_hash': cache['execution_source_sha256'] = 'f'*64
    else:
        del event['training_execution_contract_sha256']; del event['H0_export_sha256']
        del result['encoder_pair']['training_execution']
    with pytest.raises(ValueError):
        validate_panel_evidence(event, result_ref, result, evidence)


def test_new_recipe_routing_identity_is_explicit_and_never_changes_cp_or_capacity_scope(tmp_path):
    _, _, original, _ = _metadata(tmp_path)
    other = deepcopy(original)
    other['proxy_contract']['execution'].update(gpu_uuid='GPU-other',gpu_name='other actual model')
    assert proxy.identity(original) != proxy.identity(other)  # legacy exact behavior
    original['recipe_identity_schema'] = 'model_v3_training_recipe_identity_v2'
    other['recipe_identity_schema'] = original['recipe_identity_schema']
    assert proxy.identity(original) == proxy.identity(other)
    other['proxy_contract']['clip_norm'] *= 2
    assert proxy.identity(original) != proxy.identity(other)
    assert original['proxy_contract']['execution']['gpu_uuid'] is None
    assert other['proxy_contract']['execution']['gpu_uuid'] == 'GPU-other'


def test_unknown_recipe_identity_projection_is_not_silently_accepted(tmp_path):
    _, _, cfg, _ = _metadata(tmp_path)
    cfg['recipe_identity_schema'] = 'unknown'
    with pytest.raises(ValueError):
        proxy.identity(cfg)


@pytest.mark.parametrize('groups,views', ((('S',),'three'),(('P',),'two'),(('S','D','P'),'three')))
def test_group_scopes_use_actual_provider_and_complete_model_optimizer(tmp_path, exact_cpu_policy, groups, views):
    from test_model_v3_trainer import UnitTracker
    _, request, cfg, plan = _metadata(tmp_path, training_execution=MANUAL, groups=groups, views=views)
    inputs = proxy.bind_inputs(request, cfg)
    try:
        exp = proxy.build_experiment(request, cfg, plan, inputs, UnitTracker('entry-group-unit'),
            output_root=tmp_path/'job/training', lineage_root=tmp_path/'ledger', lineage='group-unit',
            device='cpu', allow_unit_tracker=True)
        observation = _cli_module().install_training_observer(exp, cfg, tmp_path/'job', request_reference=binding(tmp_path/'metadata/request.json'))
        row = exp.trainer.next_step(1)
        assert exp.trainer.clock.samples_consumed == 1 and exp.trainer.clock.optimizer_updates == 1
        assert exp.trainer.groups == groups
        assert exp.trainer.physical_views_per_sample == (len({'three':(0,1,2),'two':(0,3)}[views]) if 'S' in groups else 1)
        members = [p for group in exp.trainer.optimizer.param_groups for p in group['params']]
        assert len({id(p) for p in members}) == len(members)
        assert {id(p) for p in members} == {id(p) for p in exp.trainer.model.parameters()}
        records = [json.loads(line) for line in observation['steps_path'].read_text().splitlines()]
        assert len(records) == 1 and records[0]['role'] == 'TRAIN'
        assert row['training_execution_observation'] == records[0]
    finally:
        inputs.provider.close()
