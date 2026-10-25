"""Bound model-owned C2 metadata -> allowlisted aggregates, never lookup arrays."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import stat
import sys

READER = Path('/share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/archive_closed_v7_source/bounded_history_v7.py')
READER_SHA = '6aee76e16c182be97b7f88e635b43948510d0fc335e0ccfbf9ba107a1c29ab95'
ORIGIN = 'prior_TRAIN_diagnostic_artifact'
STATUS = 'ANALYSIS_COMPLETE_NOT_MODEL_SELECTION_V2'
PRODUCER = Path('/share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/c2_train_artifact_loader_v3_source/accepted_train_artifact_v2.py')
# SA4 frozen request acb401d0d8aa6393680ff718fd0fde0898b7425fadc389dfeb7c68e2bfcab7d2.
RUNTIME_SOURCES = {
    'accepted_train_artifact_v2.py': '704f2683fcb9751102712d639b1ffc1a4b8f218d1b9f3257b0fe2b3e4dede12b',
    'coordinate_baseline_v2.py': 'ffaba07c79e5acb74f90d4f732df10d7e81d89ad7468f04ee35800928e5c05b7',
    'core_capture.py': '9ac5b4be9a029a093419d0d6cb92673b3f89ca41a4a02e21b8c07f9a8fe33cd3',
    'diagnose_coordinate_lookup.py': '7c78234b333dddd87ff5efd0927cf9f25642f455e6c31ca73c9abb936ed1e781',
    'solver_math.py': 'e0cf8ef6859d026e8dc6c260718f0c5ddc368779097fa48405572f1f26f79472'}
DIAGNOSTIC_PUBLIC_COMMIT = 'cd0c434bb39824cd75c24d7c6de0531946da1de5'
DIAGNOSTIC_BLOB_SHA = '415f1fa96d0a510fa5c7eeeca381b27603edecba6d27ac1b01bc43712e847961'
DIAGNOSTIC_POLICY = {'schema': 'model_v3_C2_diagnostic_local_public_mapping_v1',
    'public_commit': DIAGNOSTIC_PUBLIC_COMMIT, 'executed_local_protocol_blob_raw_sha256': DIAGNOSTIC_BLOB_SHA,
    'complete_local_ref_matches_closed_input_binding': True, 'actual_local_git_tree_equals_recorded_public_tree': True,
    'exact_method_and_diagnostic_source_inventory_checked': True, 'local_and_public_commits_distinct': True,
    'arbitrary_commit_alias_fallback': False}
SUPERVISOR_SOURCES = {
    'run_cpu_supervised_128m_v1.py': '23fe5a473918dc420621d98bef49e7e08c7bcd7b43e6f001ae8821bce96b976e',
    'runtime_monitor.py': 'dbe875ab7ceec7e5002c5b70bff0608e3506f7451bdacd38e5f5bfc0700663fe',
    'run_supervised.py': 'a1b16ea1af0400dd695a6b1e651b9f88a5ed88bcabe4ed718d5e19ad11abd7bd',
    'private_runtime_storage.py': '791e2742b2131e5001ebc4fe549d8fcb43f7d28f399368a5aa5f82d7d592a041'}
SOLVER = {'kind': 'active_Jacobi_explicit_augmented_LSQR_v2', 'damp': 0., 'maximum_iterations': 2000,
    'atol': 1e-8, 'btol': 1e-8, 'condition_limit': 1e8, 'ridge': 1e-4,
    'BLAS_threads': 1, 'warm_start_used': False, 'KKT_acceptance_threshold': None}
# Every numerical key returned by the unchanged evaluator; bool is not numeric.
DEFINITIONS = {
    'records': ('records', 'all fixed PRETRAIN_VAL records'), 'atoms': ('atoms', 'all atoms N'),
    'local_pairs': ('pairs', 'all unique clean-distance<2 Angstrom pairs P'),
    'directed_edges': ('edges', 'all noisy-distance<5 Angstrom directed feature edges'),
    'known_directed_edges': ('edges', 'observed TRAIN bins'), 'unknown_directed_edges': ('edges', 'zero correction; never excluded'),
    'displacement_vector_MSE_A2': ('Angstrom^2', 'SSE/N'),
    'coordinate_vector_RMSE_A': ('Angstrom', 'sqrt(SSE/N)'),
    'coordinate_component_RMSE_A': ('Angstrom', 'sqrt(SSE/(3N))'),
    'explicit_sigma_normalized_component_MSE': ('dimensionless', 'SSE/(3N*sigma^2)'),
    'noisy_identity_vector_MSE_A2': ('Angstrom^2', 'zero-correction SSE/N'),
    'local_pair_RMSE_A': ('Angstrom', 'sqrt(pair SSE/P); same predicted clean coordinates'),
    'noisy_identity_local_pair_RMSE_A': ('Angstrom', 'sqrt(zero-correction pair SSE/P)'),
    'local_cutoff_A': ('Angstrom', 'fixed clean-distance analysis cutoff'),
    'sigma_A_for_normalized_metric_only': ('Angstrom', 'fixed normalization sigma')}
METRIC_META = {'status', 'role', 'evaluation_membership_sha256', 'all_atoms_in_coordinate_denominator',
    'unknown_bins_use_zero_correction_without_exclusion', 'downstream_records_or_scores_read'}
STATS = ('solver_called', 'stop_code', 'iterations', 'rnorm', 'damped_rnorm', 'anorm', 'acond', 'arnorm', 'xnorm', 'coefficients_finite')
KKT = ('TRAIN_mean_atom_squared_vector_error_A2', 'TRAIN_component_MSE_A2', 'ridge_penalty', 'original_objective',
    'original_normal_residual_norm', 'original_rhs_gradient_norm', 'relative_original_normal_residual',
    'relative_normal_residual_defined', 'normal_equation', 'acceptance_threshold_applied')


def require(value, message):
    if not value: raise ValueError(message)


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n').encode()


def canonical(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def file_ref(path, maximum=32 << 20):
    require(Path(path).is_absolute(), 'Absolute source path required')
    path = Path(path).absolute()
    require('..' not in path.parts, 'Absolute physical source required')
    for parent in (path, *path.parents): require(not parent.is_symlink(), 'Symlink source ancestry forbidden')
    before = path.stat()
    require(stat.S_ISREG(before.st_mode) and before.st_uid == os.getuid() and before.st_nlink == 1
        and before.st_size <= maximum, 'Owned bounded ordinary single-link source required')
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''): digest.update(block)
    after = path.stat()
    require((before.st_ino, before.st_size, before.st_mtime_ns) == (after.st_ino, after.st_size, after.st_mtime_ns), 'Source changed during hash')
    return {'path': str(path), 'bytes': before.st_size, 'sha256': digest.hexdigest()}


def reader():
    require(file_ref(READER)['sha256'] == READER_SHA, 'Frozen bounded archive_v7 reader drifted')
    name = 'c2_readonly_archive_v7_'+READER_SHA
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, READER)
        module = importlib.util.module_from_spec(spec); sys.modules[name] = module; spec.loader.exec_module(module)
    return sys.modules[name]


def read(ref):
    require(set(ref) == {'path', 'bytes', 'sha256'} and type(ref['bytes']) is int and 0 <= ref['bytes'] <= 32 << 20,
        'Bounded32MiB JSON reference required')
    require(file_ref(ref['path']) == ref, 'Raw source bytes/SHA differ')
    raw = Path(ref['path']).read_bytes()
    require(hashlib.sha256(raw).hexdigest() == ref['sha256'], 'Source changed before parse')
    return reader().strict_json(raw)


def same(a, b):
    require(a['path'] == b['path'] and a['sha256'] == b['sha256']
        and ('bytes' not in a or 'bytes' not in b or a['bytes'] == b['bytes']), 'Raw source reference differs')


def slurm_row(raw, job):
    require(hashlib.sha256(raw['stdout'].encode()).hexdigest() == raw['stdout_sha256'], 'Raw sacct hash differs')
    argv = raw['argv']; require(any(Path(a).name == 'sacct' for a in argv), 'Actual sacct argv required')
    columns = None
    for i, item in enumerate(argv):
        if item.startswith('--format='): columns = item.split('=', 1)[1].split(',')
        if item in ('--format', '-o') and i+1 < len(argv): columns = argv[i+1].split(',')
    require(columns is not None, 'Explicit sacct column order required')
    columns = [re.sub(r'%.*$', '', item) for item in columns]
    require({'JobIDRaw', 'State', 'ExitCode', 'ElapsedRaw'} <= set(columns), 'Parent closure columns required')
    rows = []
    for line in raw['stdout'].splitlines():
        values = line.rstrip('|').split('|')
        if len(values) == len(columns):
            value = dict(zip(columns, values))
            if value['JobIDRaw'] == job: rows.append(value)
    require(len(rows) == 1 and rows[0]['State'] == 'COMPLETED' and rows[0]['ExitCode'] == '0:0', 'Actual parent C0 required')
    require(rows[0]['ElapsedRaw'].isascii() and rows[0]['ElapsedRaw'].isdigit(), 'Actual integer ElapsedRaw required')
    return rows[0]


def metrics_checked(metrics):
    require(set(metrics) == set(DEFINITIONS) | METRIC_META, 'Fixed original core metric keys required')
    require(metrics['status'] == 'ANALYSIS_ONLY_NOT_MODEL_SELECTION' and metrics['role'] == 'PRETRAIN_VAL'
        and metrics['records'] == 1024 and metrics['all_atoms_in_coordinate_denominator'] is True
        and metrics['unknown_bins_use_zero_correction_without_exclusion'] is True
        and metrics['downstream_records_or_scores_read'] is False, 'Original populations/denominators required')
    for key in ('records', 'atoms', 'local_pairs', 'directed_edges', 'known_directed_edges', 'unknown_directed_edges'):
        require(type(metrics[key]) is int and metrics[key] >= 0, 'Integer population/coverage count required')
    require(metrics['atoms'] > 0 and metrics['known_directed_edges']+metrics['unknown_directed_edges'] == metrics['directed_edges'], 'All directed edges must remain counted')
    for key in DEFINITIONS:
        value = metrics[key]
        if value is None:
            require(key in ('local_pair_RMSE_A', 'noisy_identity_local_pair_RMSE_A') and metrics['local_pairs'] == 0, 'Unexpected unavailable metric')
        else:
            require(type(value) in (int, float) and math.isfinite(value) and value >= 0, 'Finite nonnegative core metric required')
    require(all((metrics[k] is None) == (metrics['local_pairs'] == 0) for k in ('local_pair_RMSE_A', 'noisy_identity_local_pair_RMSE_A')), 'Local-pair denominator differs')
    v = metrics['displacement_vector_MSE_A2']
    require(metrics['local_cutoff_A'] == 2. and metrics['sigma_A_for_normalized_metric_only'] == .1
        and math.isclose(metrics['coordinate_vector_RMSE_A']**2, v, rel_tol=1e-12, abs_tol=1e-15)
        and math.isclose(3*metrics['coordinate_component_RMSE_A']**2, v, rel_tol=1e-12, abs_tol=1e-15)
        and math.isclose(metrics['explicit_sigma_normalized_component_MSE'], v/(3*.1**2), rel_tol=1e-12, abs_tol=1e-15),
        'Original vector/component/sigma algebra differs; no metric quality threshold is added')
    return {key: metrics[key] for key in DEFINITIONS}


def runtime_checked(bound, protocol):
    require(bound['executed_sources'] == protocol['artifact_runtime_sources'] == RUNTIME_SOURCES
        and canonical(bound['executed_sources']) == protocol['artifact_runtime_source_inventory_sha256']
        and protocol['base_runtime_sources'] == {key: value for key, value in RUNTIME_SOURCES.items() if key != PRODUCER.name}
        and canonical(protocol['base_runtime_sources']) == protocol['source_inventory_sha256']
        and protocol['validation_revision'] == 'TRAIN_artifact_loader_v3_local_public_mapping'
        and protocol['diagnostic_registration_policy'] == DIAGNOSTIC_POLICY,
        'Exact frozen v3 logger, five runtime sources and local/public validation policy required')
    reader().typed_like(protocol['diagnostic_registration_policy'], DIAGNOSTIC_POLICY)


def prepare(manifest):
    require(manifest['schema'] == 'model_v3_C2_artifact_v3_report_inputs_v1', 'Artifact-v3 report manifest required')
    for name, suffix in (('result', 'RESULT'), ('completion', 'COMPLETE'), ('input_binding', 'INPUT_BINDING'), ('fit_receipt', 'FIT_RECEIPT')):
        require(Path(manifest[name]['path']).name == 'BASELINE_v2_ARTIFACT_'+suffix+'.json', 'Only named model-owned metadata is opened')
    names = ('root_closure', 'source_request', 'selection_plan', 'artifact_inputs', 'input_binding', 'fit_receipt', 'completion', 'result', 'protocol')
    values = {name: read(manifest[name]) for name in names}
    closure, request, plan, inputs, bound, fit, done, result, protocol = (values[name] for name in names)
    job = str(manifest['expected_job_id']); accounting = slurm_row(closure['raw_sacct'], job)
    require(closure['schema'] == 'model_v3_C2_artifact_v3_root_closure_v1' and str(closure['source_job']['job_id']) == job
        and closure['source_job']['state'] == 'COMPLETED' and closure['source_job']['exit_code'] == '0:0'
        and closure['source_job']['elapsed_seconds'] == int(accounting['ElapsedRaw']), 'Projected/actual current-job C0 differs')
    supervisor = read(closure['supervisor'])
    require(str(supervisor['job_id']) == job and supervisor['status'] == 'COMPLETED' and supervisor['exit_code'] == 0
        and supervisor['first_failure'] is None and supervisor['remaining'] == []
        and supervisor['gpu_initialization_permitted'] is False and supervisor['private_storage']['first_sampling_failure'] is None,
        'Fixed CPU supervisor/process/private-storage closure required')
    pins = {Path(path).name: sha for path, sha in supervisor['sources_sha256'].items()}
    require(len(supervisor['sources_sha256']) == 4 and pins == SUPERVISOR_SOURCES
        and protocol['TRAIN_supervisor_sources_sha256'] == SUPERVISOR_SOURCES, 'Actual four-source128MiB guard differs')
    command = supervisor['command']; require(command.count(str(PRODUCER)) == 1, 'Exact v3 artifact-origin producer path required')
    for flag, expected in (('--inputs', manifest['artifact_inputs']['path']), ('--inputs-sha256', manifest['artifact_inputs']['sha256'])):
        require(command.count(flag) == 1 and command[command.index(flag)+1] == expected, 'Supervised producer input binding differs')
    require(result['schema'] == 'model_v3_C2_prior_TRAIN_artifact_v2_result_v1' and done['schema'] == 'model_v3_C2_prior_TRAIN_artifact_v2_complete_v1'
        and result['status'] == done['status'] == STATUS and done['model_selection_gate'] is False, 'Successful analysis-only artifact completion required')
    for value in (result, done, fit, protocol):
        require(value['fit_origin'] == ORIGIN and value['current_job_TRAIN_geometry_reads'] == 0
            and value['original_v1_job_4520482_remains_FAILED'] is True, 'Prior TRAIN origin/zero current TRAIN/failed v1 must remain explicit')
    require(result['parameter_estimation_job_id'] == done['parameter_estimation_job_id'] == fit['parameter_estimation_job_id'] == protocol['TRAIN_fit_job_id'] == '4520559'
        and result['current_job_PRETRAIN_VAL_geometry_reads'] == done['current_job_PRETRAIN_VAL_geometry_reads'] == 1024,
        'Parameter source559/current VAL-only1024 counters differ')
    same(done['result'], manifest['result']); same(done['inputs'], manifest['artifact_inputs']); same(bound['inputs'], manifest['artifact_inputs'])
    same(bound['source_request'], manifest['source_request']); same(bound['selection_plan'], manifest['selection_plan'])
    same(inputs['source_request'], manifest['source_request']); same(inputs['selection_plan'], manifest['selection_plan'])
    registration = inputs['protocol_registration']
    require(registration == bound['protocol_registration'] == manifest['protocol_registration']
        and re.fullmatch('[a-f0-9]{40}', registration['commit']) and registration['sha256'] == manifest['protocol']['sha256']
        and registration['path'] == 'configs/model_v3/c2_prior_TRAIN_artifact_v3_adopted.json', 'Actual public artifact adoption binding differs')
    require(protocol['schema'] == 'model_v3_C2_coordinate_baseline_v2_protocol_v1'
        and protocol['adoption_status'] == 'ADOPTED_AFTER_TRAIN_ONLY_DIAGNOSTIC'
        and protocol['solver'] == SOLVER and fit['actual_solver_configuration_v2'] == SOLVER
        and result['method'] == done['method'] == SOLVER and protocol['model_selection_gate'] is False,
        'Unchanged adopted solver/protocol required')
    runtime_checked(bound, protocol)
    require(protocol['source_request_raw_sha256'] == manifest['source_request']['sha256']
        and protocol['selection_plan_raw_sha256'] == manifest['selection_plan']['sha256']
        and plan['source_request_sha256'] == canonical(request) and plan['selection'] == request['selection']
        and plan['selection_uses_targets'] is False and plan['native_geometry_records_decoded'] == 0,
        'Original frozen metadata-only selection differs')
    require(result['fit_receipt_v2'] == fit and fit['TRAIN_records'] == 8192 and fit['TRAIN_atoms'] == 436120
        and fit['fit_role'] == 'TRAIN' and fit['current_job_parameter_estimation_performed'] is False
        and fit['validation_used_for_fit_or_tuning'] is False and fit['KKT_acceptance_threshold_applied'] is False
        and request['selection']['train_records'] == 8192 and request['selection']['validation_records'] == 1024,
        'Original fit/counts/untuned analysis origin differs')
    require(fit['schema'] == 'model_v3_C2_coordinate_baseline_v2_fit_receipt_v1'
        and inputs['schema'] == 'model_v3_C2_prior_TRAIN_artifact_v2_inputs_v1'
        and fit['artifact_runtime_source_sha256'] == bound['executed_sources']
        and fit['source_request_raw_sha256'] == manifest['source_request']['sha256']
        and fit['source_plan_raw_sha256'] == manifest['selection_plan']['sha256']
        and fit['normalization'] == 'sum_squared_vector_error/TRAIN_atoms'
        and fit['target_units'] == 'epsilon=y-x, Angstrom displacement'
        and fit['dense_Gram_constructed'] is False and fit['method'] == SOLVER
        and result['tracking_mode'] == 'persistent_offline' and result['online_sync_claimed'] is False,
        'Exact artifact/source/normalization/recorded tracking origin required')
    require(fit['v2_executed_source_sha256'] == protocol['base_runtime_sources'], 'v3 base runtime receipt inventory differs')
    diagnostic_binding_ref = inputs['TRAIN_diagnostic_input_binding']
    require(diagnostic_binding_ref['sha256'] == protocol['TRAIN_diagnostic_input_binding_raw_sha256'], 'Original diagnostic binding raw SHA differs')
    diagnostic_binding = read(diagnostic_binding_ref)
    original_inputs_ref = diagnostic_binding['inputs']; original_inputs = read(original_inputs_ref)
    mapping = fit['diagnostic_registration_mapping']
    local, public = original_inputs['protocol_registration'], original_inputs['public_registration']
    require(set(local) == {'repository', 'commit', 'path', 'sha256'}
        and set(public) == {'commit', 'tree'} and diagnostic_binding['protocol_registration'] == local
        and re.fullmatch('[a-f0-9]{40}', local['commit']) and local['commit'] != public['commit']
        and public['commit'] == DIAGNOSTIC_PUBLIC_COMMIT and re.fullmatch('[a-f0-9]{40}', public['tree'])
        and local['sha256'] == DIAGNOSTIC_BLOB_SHA
        and mapping['method_and_source_inventory_verified'] is True
        and mapping == {'schema': 'model_v3_C2_diagnostic_local_public_mapping_v1',
            'executed_local_protocol_registration': local, 'public_registration': public,
            'verified_local_tree': public['tree'], 'verified_protocol_blob_raw_sha256': DIAGNOSTIC_BLOB_SHA,
            'method_and_source_inventory_verified': True}, 'Bound diagnostic local/public/tree/blob mapping differs')
    require(diagnostic_binding['executed_sources'] == {key: RUNTIME_SOURCES[key] for key in
        ('core_capture.py', 'solver_math.py', 'diagnose_coordinate_lookup.py')}, 'Prior diagnostic three-source binding differs')
    for value in (diagnostic_binding, original_inputs):
        same(value['source_request'], manifest['source_request']); same(value['selection_plan'], manifest['selection_plan'])
    artifact = inputs['TRAIN_artifact']
    same(artifact, bound['TRAIN_artifact']); same(artifact, fit['prior_TRAIN_artifact'])
    require(artifact['sha256'] == protocol['TRAIN_artifact_raw_sha256'] and artifact['bytes'] == protocol['TRAIN_artifact_bytes'],
        'Declared prior TRAIN artifact differs (reporter never opens it)')
    receipts = {}
    for role, count in (('TRAIN', 8192), ('PRETRAIN_VAL', 1024)):
        selected = plan['records'][role]
        require(len(selected) == count and all(type(row['native_n_atoms']) is int and row['native_n_atoms'] > 0 for row in selected),
            'Closed original record/atom counts differ')
        receipts[role] = [{'record_id': row['record_id'], 'molecule_id': row['molecule_id'], 'role': role,
            'payload_sha256': row['payload_sha256'], 'atoms': row['native_n_atoms']} for row in selected]
        require(len({row['record_id'] for row in selected}) == count, 'Duplicate closed record identity')
    train, validation = receipts['TRAIN'], receipts['PRETRAIN_VAL']
    for key in ('record_id', 'molecule_id'):
        require(not ({row[key] for row in train} & {row[key] for row in validation}), 'TRAIN/VAL closed identity overlap')
    require(fit['TRAIN_record_ids'] == sorted(row['record_id'] for row in train)
        and fit['TRAIN_molecule_ids'] == sorted({row['molecule_id'] for row in train})
        and fit['TRAIN_membership_sha256'] == canonical(train)
        and sum(row['atoms'] for row in train) == 436120, 'Bound prior TRAIN metadata population differs')
    metrics = metrics_checked(result['metrics'])
    require(result['metrics']['evaluation_membership_sha256'] == canonical(validation)
        and metrics['atoms'] == sum(row['atoms'] for row in validation), 'Original validation membership/atom denominator differs')
    require(type(result['resource_observation']['process_peak_RSS_bytes']) is int
        and 0 <= result['resource_observation']['process_peak_RSS_bytes'] <= protocol['caps']['maximum_process_RSS_bytes']
        and type(result['resource_observation']['wall_seconds']) in (int, float)
        and 0 <= result['resource_observation']['wall_seconds'] <= protocol['caps']['wall_seconds'], 'Finite bounded resource observation required')
    for container, fields in ((fit['augmented_operator_statistics'], STATS), (fit['original_coordinate_KKT_and_objective'], KKT)):
        for key in fields:
            if key in container:
                value = container[key]
                require(type(value) in (int, float, bool, str, type(None))
                    and (type(value) is not str or len(value) <= 256), 'Only fixed scalar diagnostics may be exported')
    require(type(fit['prior_TRAIN_job_elapsed_seconds']) is int and fit['prior_TRAIN_job_elapsed_seconds'] >= 0,
        'Observed prior TRAIN allocation seconds must be an integer')
    output_root = str(Path(manifest['result']['path']).parent)
    layout = {'WANDB_DIR': output_root, 'WANDB_CACHE_DIR': output_root+'/cache', 'WANDB_DATA_DIR': output_root+'/wandb_data',
        'WANDB_CONFIG_DIR': output_root+'/wandb_config', 'WANDB_MODE': 'offline'}
    config = {'method': SOLVER, 'fit_origin': ORIGIN, 'parameter_estimation_job_id': '4520559', 'current_job_TRAIN_geometry_reads': 0,
        'source_request_sha256': manifest['source_request']['sha256'], 'selection_plan_sha256': manifest['selection_plan']['sha256'],
        'public_artifact_protocol_commit': registration['commit'], 'tracking_layout': layout}
    expected = [{'step': 0, 'row': {'prior_TRAIN_fit/records': 8192, 'prior_TRAIN_fit/atoms': 436120,
        'prior_TRAIN_fit/parameter_estimation_job_id': '4520559', 'current_job/TRAIN_geometry_reads': 0}},
        {'step': 1, 'row': {'validation/'+key: value for key, value in result['metrics'].items() if type(value) in (int, float)}}]
    report = {'schema': 'model_v3_C2_artifact_v3_aggregate_report_v1', 'status': 'PENDING_INDEPENDENT_SDK_VERIFICATION',
        'model_selection_gate': False, 'fit_origin': ORIGIN, 'actual_job_id': job, 'parameter_estimation_job_id': '4520559',
        'current_job_TRAIN_geometry_reads': 0, 'current_job_PRETRAIN_VAL_geometry_reads': 1024,
        'current_job_parameter_estimation_performed': False,
        'prior_TRAIN_records': 8192, 'prior_TRAIN_atoms': 436120, 'metrics': metrics,
        'core_metric_metadata': {key: result['metrics'][key] for key in sorted(METRIC_META)},
        'metric_units_and_denominators': {key: {'unit': unit, 'denominator': denominator} for key, (unit, denominator) in DEFINITIONS.items()},
        'derived_zero_baseline': {'coordinate_vector_RMSE_A': math.sqrt(metrics['noisy_identity_vector_MSE_A2']),
            'coordinate_component_RMSE_A': math.sqrt(metrics['noisy_identity_vector_MSE_A2']/3),
            'explicit_sigma_normalized_component_MSE': metrics['noisy_identity_vector_MSE_A2']/(3*.1**2)},
        'solver': SOLVER, 'prior_solver_statistics': {key: fit['augmented_operator_statistics'][key] for key in STATS if key in fit['augmented_operator_statistics']},
        'prior_original_coordinate_diagnostics': {key: fit['original_coordinate_KKT_and_objective'][key] for key in KKT if key in fit['original_coordinate_KKT_and_objective']},
        'KKT_origin': 'copied from bound prior TRAIN559; not recomputed', 'prior_TRAIN_job_elapsed_seconds': fit['prior_TRAIN_job_elapsed_seconds'],
        'current_job_elapsed_seconds': int(accounting['ElapsedRaw']), 'current_job_resources': {key: result['resource_observation'][key]
            for key in ('wall_seconds', 'process_peak_RSS_bytes')}, 'run_id': result['wandb_run_id'], 'online_sync_claimed': False,
        'original_v1_job_4520482_remains_FAILED': True, 'original_v1_stop_inferred': False,
        'diagnostic_registration_mapping': mapping,
        'diagnostic_mapping_observation': 'independent metadata-chain comparison; real git/tree/blob validation performed by the bound v3 producer',
        'producer_path': str(PRODUCER), 'producer_sources_sha256': RUNTIME_SOURCES,
        'model_owned_identity_metadata_read': True, 'identities_weights_native_geometries_predictions_exported': False,
        'lookup_or_NPZ_opened': False, 'source_bindings': {name: manifest[name] for name in names}, 'protocol_registration': registration}
    allocated = int(accounting['AllocCPUS'])*int(accounting['ElapsedRaw']) if 'AllocCPUS' in accounting else ''
    row = {'run_id': 'C2_artifact_'+job, 'stage': '5', 'config_sha256': manifest['source_request']['sha256'],
        'code_sha': registration['commit'], 'data_version': 'existing_S_manifest_'+request['input_manifest']['sha256'],
        'seed': request['source_noise']['seed'], 'gpu_model': 'CPU', 'elapsed_seconds': int(accounting['ElapsedRaw']),
        'status': 'COMPLETED', 'preregistration_sha': registration['commit'], 'denoise_rmse': metrics['coordinate_component_RMSE_A'],
        'peak_memory_bytes': result['resource_observation']['process_peak_RSS_bytes'], 'allocated_cpu_seconds': allocated,
        'allocated_gpu_seconds': 0, 'metric__current_TRAIN_geometry_reads': 0, 'metric__current_VAL_records': 1024,
        **{'metric__'+key: value for key, value in metrics.items() if value is not None}}
    refs = {name: manifest[name] for name in names}; refs['supervisor'] = closure['supervisor']
    refs['prior_diagnostic_input_binding'] = diagnostic_binding_ref; refs['prior_diagnostic_inputs'] = original_inputs_ref
    return {'report': report, 'csv': row, 'expected_rows': expected, 'expected_config': config,
        'job_id': job, 'run_id': result['wandb_run_id'], 'run_name': 'C2_v2_prior_TRAIN_then_first_VAL_'+job,
        'SDK_file': manifest['SDK_file'], 'sources': refs}
