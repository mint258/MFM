"""Synthetic metadata + real tiny offline SDK; never actual C2 VAL/lookup inputs."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time

import pytest

import c2_artifact_schema as s
import c2_native_sdk as n
import c2_artifact_report as report


def metrics():
    return {'status': 'ANALYSIS_ONLY_NOT_MODEL_SELECTION', 'role': 'PRETRAIN_VAL', 'records': 1024,
        'atoms': 4096, 'local_pairs': 3, 'directed_edges': 10, 'known_directed_edges': 8, 'unknown_directed_edges': 2,
        'displacement_vector_MSE_A2': .0075, 'coordinate_vector_RMSE_A': (.0075)**.5,
        'coordinate_component_RMSE_A': .05, 'explicit_sigma_normalized_component_MSE': .25,
        'noisy_identity_vector_MSE_A2': .03, 'local_pair_RMSE_A': .04, 'noisy_identity_local_pair_RMSE_A': .14,
        'local_cutoff_A': 2., 'sigma_A_for_normalized_metric_only': .1, 'evaluation_membership_sha256': 'e'*64,
        'all_atoms_in_coordinate_denominator': True, 'unknown_bins_use_zero_correction_without_exclusion': True,
        'downstream_records_or_scores_read': False}


@pytest.fixture
def metadata(tmp_path):
    """Full-sized identity metadata only; lookup and NPZ references NEVER exist."""
    def save(name, value):
        path = tmp_path/name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(s.encoded(value)); return s.file_ref(path)
    train = [{'record_id': 'TRAIN_SECRET_ID_'+str(i), 'molecule_id': 'TM'+str(i),
        'native_n_atoms': 54 if i < 1944 else 53, 'payload_sha256': 'a'*64} for i in range(8192)]
    validation = [{'record_id': 'VAL_SECRET_ID_'+str(i), 'molecule_id': 'VM'+str(i),
        'native_n_atoms': 4, 'payload_sha256': 'b'*64} for i in range(1024)]
    def receipts(rows, role):
        return [{'record_id': r['record_id'], 'molecule_id': r['molecule_id'], 'role': role,
            'payload_sha256': r['payload_sha256'], 'atoms': r['native_n_atoms']} for r in rows]
    request = {'selection': {'train_records': 8192, 'validation_records': 1024},
        'input_manifest': {'sha256': '1'*64}, 'source_noise': {'seed': 0}}
    request_ref = save('original_request.json', request)
    plan = {'selection': request['selection'], 'source_request_sha256': s.canonical(request),
        'selection_uses_targets': False, 'native_geometry_records_decoded': 0, 'records': {'TRAIN': train, 'PRETRAIN_VAL': validation}}
    plan_ref = save('original_plan.json', plan)
    inventory = dict(s.RUNTIME_SOURCES)
    base_inventory = {key: value for key, value in inventory.items() if key != s.PRODUCER.name}
    local = {'repository': '/synthetic/local_diagnostic_repository', 'commit': '4'*40,
        'path': 'configs/model_v3/c2_train_solver_diagnostic.json', 'sha256': s.DIAGNOSTIC_BLOB_SHA}
    public = {'commit': s.DIAGNOSTIC_PUBLIC_COMMIT, 'tree': '5'*40}
    original_inputs_ref = save('prior_diagnostic_inputs.json', {'protocol_registration': local, 'public_registration': public,
        'source_request': request_ref, 'selection_plan': plan_ref})
    diagnostic_binding_ref = save('prior_diagnostic_input_binding.json', {'inputs': original_inputs_ref,
        'protocol_registration': local, 'source_request': request_ref, 'selection_plan': plan_ref,
        'executed_sources': {key: inventory[key] for key in ('core_capture.py', 'solver_math.py', 'diagnose_coordinate_lookup.py')}})
    artifact = {'path': str(tmp_path/'MUST_NOT_OPEN_TRAIN_ARRAYS.npz'), 'sha256': '2'*64, 'bytes': 100361}
    protocol = {'schema': 'model_v3_C2_coordinate_baseline_v2_protocol_v1', 'adoption_status': 'ADOPTED_AFTER_TRAIN_ONLY_DIAGNOSTIC',
        'fit_origin': s.ORIGIN, 'current_job_TRAIN_geometry_reads': 0, 'original_v1_job_4520482_remains_FAILED': True,
        'TRAIN_fit_job_id': '4520559', 'solver': s.SOLVER, 'model_selection_gate': False,
        'TRAIN_supervisor_sources_sha256': s.SUPERVISOR_SOURCES, 'artifact_runtime_sources': inventory,
        'base_runtime_sources': base_inventory, 'source_inventory_sha256': s.canonical(base_inventory),
        'artifact_runtime_source_inventory_sha256': s.canonical(inventory), 'source_request_raw_sha256': request_ref['sha256'],
        'selection_plan_raw_sha256': plan_ref['sha256'], 'TRAIN_artifact_raw_sha256': artifact['sha256'], 'TRAIN_artifact_bytes': artifact['bytes'],
        'TRAIN_diagnostic_input_binding_raw_sha256': diagnostic_binding_ref['sha256'],
        'validation_revision': 'TRAIN_artifact_loader_v3_local_public_mapping', 'diagnostic_registration_policy': s.DIAGNOSTIC_POLICY,
        'caps': {'maximum_process_RSS_bytes': 24 << 30, 'wall_seconds': 3300}}
    protocol_ref = save('adopted.json', protocol)
    registration = {'repository': '/synthetic/public/repository', 'commit': '3'*40,
        'path': 'configs/model_v3/c2_prior_TRAIN_artifact_v3_adopted.json', 'sha256': protocol_ref['sha256']}
    inputs = {'schema': 'model_v3_C2_prior_TRAIN_artifact_v2_inputs_v1', 'source_request': request_ref, 'selection_plan': plan_ref,
        'protocol_registration': registration, 'TRAIN_artifact': artifact, 'TRAIN_diagnostic_input_binding': diagnostic_binding_ref}
    inputs_ref = save('artifact_inputs.json', inputs)
    fit = {'schema': 'model_v3_C2_coordinate_baseline_v2_fit_receipt_v1', 'fit_origin': s.ORIGIN, 'fit_role': 'TRAIN',
        'method': s.SOLVER, 'actual_solver_configuration_v2': s.SOLVER, 'parameter_estimation_job_id': '4520559',
        'current_job_TRAIN_geometry_reads': 0, 'current_job_parameter_estimation_performed': False,
        'TRAIN_records': 8192, 'TRAIN_atoms': 436120, 'TRAIN_record_ids': sorted(r['record_id'] for r in train),
        'TRAIN_molecule_ids': sorted(r['molecule_id'] for r in train), 'TRAIN_membership_sha256': s.canonical(receipts(train, 'TRAIN')),
        'source_request_raw_sha256': request_ref['sha256'], 'source_plan_raw_sha256': plan_ref['sha256'],
        'validation_used_for_fit_or_tuning': False, 'KKT_acceptance_threshold_applied': False,
        'artifact_runtime_source_sha256': inventory, 'prior_TRAIN_artifact': artifact,
        'v2_executed_source_sha256': base_inventory,
        'diagnostic_registration_mapping': {'schema': 'model_v3_C2_diagnostic_local_public_mapping_v1',
            'executed_local_protocol_registration': local, 'public_registration': public, 'verified_local_tree': public['tree'],
            'verified_protocol_blob_raw_sha256': s.DIAGNOSTIC_BLOB_SHA, 'method_and_source_inventory_verified': True},
        'normalization': 'sum_squared_vector_error/TRAIN_atoms', 'target_units': 'epsilon=y-x, Angstrom displacement',
        'dense_Gram_constructed': False, 'augmented_operator_statistics': {'solver_called': True, 'stop_code': 2, 'iterations': 74},
        'original_coordinate_KKT_and_objective': {'original_objective': .01, 'acceptance_threshold_applied': False},
        'prior_TRAIN_job_elapsed_seconds': 1440, 'original_v1_job_4520482_remains_FAILED': True}
    fit_ref = save('eval/BASELINE_v2_ARTIFACT_FIT_RECEIPT.json', fit)
    m = metrics(); m['evaluation_membership_sha256'] = s.canonical(receipts(validation, 'PRETRAIN_VAL'))
    result = {'schema': 'model_v3_C2_prior_TRAIN_artifact_v2_result_v1', 'status': s.STATUS, 'fit_origin': s.ORIGIN,
        'parameter_estimation_job_id': '4520559', 'current_job_TRAIN_geometry_reads': 0,
        'current_job_PRETRAIN_VAL_geometry_reads': 1024, 'fit_receipt_v2': fit, 'metrics': m,
        'wandb_run_id': 'synthetic', 'tracking_mode': 'persistent_offline', 'online_sync_claimed': False,
        'resource_observation': {'wall_seconds': 55., 'process_peak_RSS_bytes': 10000000}, 'method': s.SOLVER,
        'original_v1_job_4520482_remains_FAILED': True}
    result_ref = save('eval/BASELINE_v2_ARTIFACT_RESULT.json', result)
    done = {'schema': 'model_v3_C2_prior_TRAIN_artifact_v2_complete_v1', 'status': s.STATUS, 'fit_origin': s.ORIGIN,
        'parameter_estimation_job_id': '4520559', 'current_job_TRAIN_geometry_reads': 0, 'current_job_PRETRAIN_VAL_geometry_reads': 1024,
        'model_selection_gate': False, 'result': result_ref, 'inputs': inputs_ref, 'method': s.SOLVER,
        'lookup': {'path': str(tmp_path/'MUST_NOT_OPEN_LOOKUP.json'), 'sha256': '4'*64, 'bytes': 5000000},
        'original_v1_job_4520482_remains_FAILED': True}
    done_ref = save('eval/BASELINE_v2_ARTIFACT_COMPLETE.json', done)
    bound = {'inputs': inputs_ref, 'protocol_registration': registration, 'executed_sources': inventory,
        'TRAIN_artifact': artifact, 'source_request': request_ref, 'selection_plan': plan_ref}
    bound_ref = save('eval/BASELINE_v2_ARTIFACT_INPUT_BINDING.json', bound)
    supervisor = {'job_id': '123', 'status': 'COMPLETED', 'exit_code': 0, 'first_failure': None, 'remaining': [],
        'gpu_initialization_permitted': False, 'private_storage': {'first_sampling_failure': None},
        'sources_sha256': {'/frozen/'+key: value for key, value in s.SUPERVISOR_SOURCES.items()},
        'command': ['python', str(s.PRODUCER), '--inputs', inputs_ref['path'], '--inputs-sha256', inputs_ref['sha256']]}
    supervisor_ref = save('supervisor.json', supervisor)
    stdout = '123|COMPLETED|0:0|60|16\n123.batch|COMPLETED|0:0|60|16\n'
    closure = {'schema': 'model_v3_C2_artifact_v3_root_closure_v1', 'source_job': {'job_id': '123', 'state': 'COMPLETED', 'exit_code': '0:0', 'elapsed_seconds': 60},
        'raw_sacct': {'argv': ['sacct', '--format=JobIDRaw,State,ExitCode,ElapsedRaw,AllocCPUS'], 'stdout': stdout,
            'stdout_sha256': hashlib.sha256(stdout.encode()).hexdigest()}, 'supervisor': supervisor_ref}
    closure_ref = save('root_closure.json', closure)
    sdk_path = tmp_path/'eval/wandb/offline-synthetic/run-synthetic.wandb'; sdk_path.parent.mkdir(parents=True); sdk_path.write_bytes(b'synthetic SDK placeholder')
    manifest = {'schema': 'model_v3_C2_artifact_v3_report_inputs_v1', 'expected_job_id': '123',
        'root_closure': closure_ref, 'source_request': request_ref, 'selection_plan': plan_ref,
        'artifact_inputs': inputs_ref, 'input_binding': bound_ref, 'fit_receipt': fit_ref, 'completion': done_ref,
        'result': result_ref, 'protocol': protocol_ref, 'protocol_registration': registration, 'SDK_file': s.file_ref(sdk_path, 128 << 20)}
    return manifest, save


def test_prepare_exports_only_aggregate_and_preserves_origin(metadata):
    manifest, _ = metadata; context = s.prepare(manifest)
    raw = s.encoded(context['report'])
    assert b'TRAIN_SECRET_ID_' not in raw and b'VAL_SECRET_ID_' not in raw
    assert context['report']['lookup_or_NPZ_opened'] is False
    assert context['report']['current_job_TRAIN_geometry_reads'] == 0
    assert context['expected_rows'][0]['row']['prior_TRAIN_fit/parameter_estimation_job_id'] == '4520559'
    assert set(context['expected_rows'][1]['row']) == {'validation/'+k for k in s.DEFINITIONS}
    assert set(context['report']['metrics']) == set(s.DEFINITIONS)
    assert context['report']['producer_sources_sha256'] == s.RUNTIME_SOURCES
    mapping = context['report']['diagnostic_registration_mapping']
    assert mapping['executed_local_protocol_registration']['commit'] != mapping['public_registration']['commit']
    assert mapping['public_registration']['commit'] == s.DIAGNOSTIC_PUBLIC_COMMIT
    assert mapping['verified_local_tree'] == mapping['public_registration']['tree']


@pytest.mark.parametrize('field,value', [('role', 'TRAIN'), ('all_atoms_in_coordinate_denominator', False),
    ('unknown_directed_edges', 3), ('coordinate_component_RMSE_A', .1), ('sigma_A_for_normalized_metric_only', 1.),
    ('records', True), ('local_pairs', 0), ('coordinate_vector_RMSE_A', float('nan'))])
def test_metric_drift_rejected(field, value):
    m = metrics(); m[field] = value
    with pytest.raises(ValueError): s.metrics_checked(m)


def test_zero_pair_denominator_is_explicit():
    m = metrics(); m.update(local_pairs=0, local_pair_RMSE_A=None, noisy_identity_local_pair_RMSE_A=None)
    assert s.metrics_checked(m)['local_pair_RMSE_A'] is None


@pytest.mark.parametrize('change', ['failed', 'guard', 'raw_sha', 'prior_origin', 'membership'])
def test_closed_metadata_drift_rejected(metadata, change):
    manifest, save = metadata
    if change == 'raw_sha': manifest['result']['sha256'] = '0'*64
    elif change == 'guard':
        closure = s.read(manifest['root_closure']); supervisor = s.read(closure['supervisor'])
        supervisor['remaining'] = [12]; closure['supervisor'] = save('supervisor.json', supervisor)
        manifest['root_closure'] = save('root_closure.json', closure)
    elif change == 'failed':
        closure = s.read(manifest['root_closure']); closure['source_job']['state'] = 'FAILED'
        manifest['root_closure'] = save('root_closure.json', closure)
    else:
        value = s.read(manifest['result'])
        if change == 'prior_origin': value['current_job_TRAIN_geometry_reads'] = 8192
        else: value['metrics']['evaluation_membership_sha256'] = '0'*64
        manifest['result'] = save('eval/BASELINE_v2_ARTIFACT_RESULT.json', value)
        done = s.read(manifest['completion']); done['result'] = manifest['result']
        manifest['completion'] = save('eval/BASELINE_v2_ARTIFACT_COMPLETE.json', done)
    with pytest.raises(ValueError): s.prepare(manifest)


@pytest.mark.parametrize('filename,old_sha', [
    ('accepted_train_artifact_v2.py', '37db0904fb7d0af6254f42f281b0a11aaccce9674397c53c8d09862d101a6ebf'),
    ('coordinate_baseline_v2.py', '7af1678e8358c20b48470429ddefaff301918a69e7a948fba63daa12b9a696b1'),
    ('solver_math.py', '0'*64)])
def test_v3_rejects_old_or_foreign_sha_even_with_matching_declared_inventory(metadata, filename, old_sha):
    manifest, _ = metadata; bound, protocol = s.read(manifest['input_binding']), s.read(manifest['protocol'])
    bound['executed_sources'][filename] = old_sha
    protocol['artifact_runtime_sources'][filename] = old_sha
    protocol['artifact_runtime_source_inventory_sha256'] = s.canonical(protocol['artifact_runtime_sources'])
    if filename in protocol['base_runtime_sources']:
        protocol['base_runtime_sources'][filename] = old_sha
        protocol['source_inventory_sha256'] = s.canonical(protocol['base_runtime_sources'])
    with pytest.raises(ValueError, match='frozen v3'): s.runtime_checked(bound, protocol)


def test_v3_requires_exact_new_producer_directory(metadata):
    manifest, save = metadata; closure = s.read(manifest['root_closure']); supervisor = s.read(closure['supervisor'])
    supervisor['command'][1] = str(s.PRODUCER).replace('_v3_source/', '_v2_source/')
    closure['supervisor'] = save('supervisor.json', supervisor); manifest['root_closure'] = save('root_closure.json', closure)
    with pytest.raises(ValueError, match='Exact v3'): s.prepare(manifest)


def test_v3_refuses_old_adoption_registration_path(metadata):
    manifest, _ = metadata
    manifest['protocol_registration']['path'] = 'configs/model_v3/c2_prior_TRAIN_artifact_v2_adopted.json'
    with pytest.raises(ValueError, match='public artifact adoption'): s.prepare(manifest)


@pytest.mark.parametrize('change', ['public_commit', 'tree', 'blob', 'local_ref', 'method_verified'])
def test_v3_diagnostic_mapping_drift_rejected(metadata, change):
    manifest, save = metadata; fit = s.read(manifest['fit_receipt']); mapping = fit['diagnostic_registration_mapping']
    if change == 'public_commit': mapping['public_registration']['commit'] = '0'*40
    elif change == 'tree': mapping['verified_local_tree'] = '0'*40
    elif change == 'blob': mapping['verified_protocol_blob_raw_sha256'] = '0'*64
    elif change == 'local_ref': mapping['executed_local_protocol_registration']['path'] = 'foreign.json'
    else: mapping['method_and_source_inventory_verified'] = False
    manifest['fit_receipt'] = save('eval/BASELINE_v2_ARTIFACT_FIT_RECEIPT.json', fit)
    result = s.read(manifest['result']); result['fit_receipt_v2'] = fit
    manifest['result'] = save('eval/BASELINE_v2_ARTIFACT_RESULT.json', result)
    done = s.read(manifest['completion']); done['result'] = manifest['result']
    manifest['completion'] = save('eval/BASELINE_v2_ARTIFACT_COMPLETE.json', done)
    with pytest.raises(ValueError, match='local/public/tree/blob'): s.prepare(manifest)


def test_v3_requires_explicit_new_report_manifest(metadata):
    manifest, _ = metadata; manifest['schema'] = 'model_v3_C2_artifact_v2_report_inputs_v1'
    with pytest.raises(ValueError, match='report manifest'): s.prepare(manifest)


def packets(context):
    from wandb.proto import wandb_internal_pb2 as pb
    result = []
    run = pb.Record(); run.run.run_id = context['run_id']; run.run.display_name = context['run_name']
    for key, value in context['expected_config'].items(): run.run.config.update.add(key=key, value_json=json.dumps(value))
    result.append(run)
    for row in context['expected_rows']:
        record = pb.Record(); record.history.item.add(key='_step', value_json=str(row['step']))
        for key, value in row['row'].items(): record.history.item.add(key=key, value_json=json.dumps(value))
        result.append(record)
    summary = pb.Record()
    for row in context['expected_rows']:
        for key, value in row['row'].items(): summary.summary.update.add(key=key, value_json=json.dumps(value))
    summary.summary.update.add(key='_step', value_json='1'); result.append(summary)
    exit_record = pb.Record(); exit_record.exit.exit_code = 0; result.append(exit_record)
    return result


def compare_packets(records, context, **kwargs):
    from wandb.proto import wandb_internal_pb2 as pb
    class Data:
        def __init__(self): self.rows = iter(r.SerializeToString() for r in records)
        def scan_data(self): return next(self.rows, None)
    return n.compare(Data(), pb.Record, context, **kwargs)


def test_native_two_rows_all_fields_config_and_summary(metadata):
    context = s.prepare(metadata[0]); verdict = compare_packets(packets(context), context)
    assert verdict['native_closed'] and verdict['history_rows'] == 2 and verdict['native_packets'] == 5


@pytest.mark.parametrize('change', ['missing_metric', 'extra_metric', 'step', 'config', 'run_name', 'run_id', 'summary', 'exit', 'missing_exit'])
def test_native_semantic_drift_rejected(metadata, change):
    context = s.prepare(metadata[0]); records = packets(context)
    if change == 'missing_metric': del records[2].history.item[-1]
    elif change == 'extra_metric': records[2].history.item.add(key='validation/NEW', value_json='0')
    elif change == 'step': records[2].history.item[0].value_json = '2'
    elif change == 'config': records[0].run.config.update[0].value_json = '{}'
    elif change == 'run_name': records[0].run.display_name = 'other'
    elif change == 'run_id': records[0].run.run_id = 'other'
    elif change == 'summary': records[3].summary.update[0].value_json = '2'
    elif change == 'exit': records[-1].exit.exit_code = 1
    else: records.pop()
    with pytest.raises(ValueError): compare_packets(records, context)


def test_native_ancillary_packets_do_not_consume_history_budget(metadata):
    from wandb.proto import wandb_internal_pb2 as pb
    context = s.prepare(metadata[0]); records = packets(context)
    records[1:1] = [pb.Record() for _ in range(20)]
    assert compare_packets(records, context, max_history_rows=2)['native_packets'] == 25
    with pytest.raises(ValueError, match='packet budget'): compare_packets(records, context, max_native_records=24)


def test_uncommitted_native_request_rejected(metadata):
    from wandb.proto import wandb_internal_pb2 as pb
    context = s.prepare(metadata[0]); records = packets(context)
    partial = pb.Record(); partial.request.partial_history.SetInParent(); records.insert(2, partial)
    with pytest.raises(ValueError, match='partial_history'): compare_packets(records, context)


@pytest.mark.parametrize('change', ['record_bytes', 'deadline', 'history_cap', 'config_change_after_history'])
def test_scan_budgets_and_post_history_config_rejected(metadata, change):
    from wandb.proto import wandb_internal_pb2 as pb
    context = s.prepare(metadata[0]); records = packets(context); kwargs = {}
    if change == 'record_bytes': kwargs['max_record_bytes'] = 1
    elif change == 'deadline': kwargs['deadline'] = time.monotonic()-1
    elif change == 'history_cap': kwargs['max_history_rows'] = 1
    else:
        update = pb.Record(); update.config.update.add(key='method', value_json='{}'); records.insert(2, update)
    with pytest.raises(ValueError): compare_packets(records, context, **kwargs)


def test_real_small_offline_sdk_end_to_end(metadata, monkeypatch, tmp_path):
    import wandb
    context = s.prepare(metadata[0]); output = tmp_path/'real_sdk'
    for key, value in {'WANDB_DIR': str(output), 'WANDB_CACHE_DIR': str(output/'cache'),
            'WANDB_DATA_DIR': str(output/'wandb_data'), 'WANDB_CONFIG_DIR': str(output/'wandb_config'), 'WANDB_MODE': 'offline'}.items():
        monkeypatch.setenv(key, value)
    output.mkdir()
    context['expected_config']['tracking_layout'] = {key: str(value) for key, value in {
        'WANDB_DIR': output, 'WANDB_CACHE_DIR': output/'cache', 'WANDB_DATA_DIR': output/'wandb_data',
        'WANDB_CONFIG_DIR': output/'wandb_config', 'WANDB_MODE': 'offline'}.items()}
    run = wandb.init(project='C2-synthetic-report-unit', mode='offline', dir=str(output), name=context['run_name'], config=context['expected_config'])
    context['run_id'] = run.id
    for row in context['expected_rows']: run.log(row['row'], step=row['step'], commit=True)
    run.finish()
    sdk = list((output/'wandb').glob('offline-*/run-*.wandb')); assert len(sdk) == 1
    context['SDK_file'] = s.file_ref(sdk[0], 128 << 20)
    # Only the containment reference changes for this real synthetic SDK fixture.
    original = Path(metadata[0]['result']['path']).read_bytes()
    (output/'BASELINE_v2_ARTIFACT_RESULT.json').write_bytes(original)
    context['sources']['result'] = s.file_ref(output/'BASELINE_v2_ARTIFACT_RESULT.json')
    certificate = n.verify(context)
    assert certificate['status'] == 'VERIFIED' and certificate['native']['history_rows'] == 2
    assert certificate['native']['native_packets'] > 2 and certificate['online_sync_performed'] is False


def test_complete_render_png_pdf_typed_csv_and_no_identities(metadata, tmp_path):
    context = s.prepare(metadata[0])
    certificate = {'status': 'VERIFIED', 'job_id': context['job_id'], 'run_id': context['run_id'],
        'metadata_bindings': context['sources'], 'all_public_metrics_config_summary_exact': True,
        'native': {'native_closed': True, 'native_packets': 5}, 'expectation_origin': 'SYNTHETIC UNIT FIXTURE ONLY',
        'SDK_file': context['SDK_file'], 'reader_source': s.file_ref(s.READER)}
    output = tmp_path/'report'; rendered = report.render(context, certificate, output)
    assert rendered['status'] == report.SUCCESS
    assert (output/'metrics.png').read_bytes().startswith(b'\x89PNG')
    assert (output/'metrics.pdf').read_bytes().startswith(b'%PDF')
    for path in (output/'report.json', output/'report.md', output/'native_verification.json', output/'summary.csv', output/'REPORT_COMPLETE.json'):
        assert b'TRAIN_SECRET_ID_' not in path.read_bytes() and b'VAL_SECRET_ID_' not in path.read_bytes()
    checker_path = Path('/share/home/zixiao/descriptor_analysis/MFM_model_v3/tools/check_repository.py')
    spec = importlib.util.spec_from_file_location('c2_readonly_repo_checker', checker_path)
    checker = importlib.util.module_from_spec(spec); sys.modules[spec.name] = checker; spec.loader.exec_module(checker)
    assert checker.model_summary_csv('docs/model_v3/results/c2_artifact_summary.csv', (output/'summary.csv').read_bytes()) is True
    with pytest.raises(ValueError, match='Fresh absolute'): report.render(context, certificate, output)
