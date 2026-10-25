#!/usr/bin/env python3
"""Root CPU preparation of the existing frozen primary512 nine-task request.

No submission, target decoding, model execution or old score reading. A closed
selected-TRAIN source is mandatory. Reuse the tested request/planning APIs.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
from export_admission import read_validated_export, require_same_reference, EVALUATION_CODE_SHA


PREREGISTRATION = '39cf4929299cd227a3c361183a4b26c8b1405900'
FIXED_RUNTIME_MONITOR = Path('/share/home/zixiao/descriptor_analysis/MFM_model_v3_profiler_v2/tools/model_v3/runtime_monitor.py')
BRIDGE_PINS = {
    'current/phychem_mfm/phase1/v3_encoder_bridge.py': 'aa52b971b64c346575f6a83f26e771fbb9cff31f2f7c1f326da3c9dca63fa144',
    'current/phychem_mfm/phase1/v3_h0_runtime.py': '87642cca5d5c16d70ed8b04c96982526a576791b668e8014239cde31c6ffcb44',
    'current/phychem_mfm/phase1/v3_dev_panel.py': '81786f6351e20a34285cfd44caef528e4c16ecb69c3355d69d679e1b53a5ed0f',
    'tools/model_v3/prepare_dev_evaluation.py': 'e66564d33a2430fec646528caee3d82e57d31bb5fc3fae00e24c7d04de9762ea',
    'tools/model_v3/evaluate_dev_panel.py': 'cb4e54b41eec63f7680d164ef4077a72ab96d544b3b66af1d348cb5c138404a2',
    'configs/dev_panel_v1.json': '110658491fbb77b0e647c5636d9cd894a389dd7e8c0f401847273c4f7c127132'}


def require(value, reason):
    if not value: raise ValueError(reason)


def binding(path):
    path = Path(path).absolute(); require(path.is_file() and not path.is_symlink(), 'Ordinary physical source required')
    before = path.stat(); digest = hashlib.sha256(); size = 0
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024**2), b''):
            digest.update(block); size += len(block)
    after = path.stat()
    require((before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns), 'Source changed during hashing')
    return {'path': str(path), 'sha256': digest.hexdigest(), 'bytes': size}


def write(path, value):
    raw = (json.dumps(value, sort_keys=True, indent=2, allow_nan=False)+'\n').encode()
    with Path(path).open('xb') as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    return binding(path)


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec); spec.loader.exec_module(result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository-root', type=Path, default=Path('/share/home/zixiao/descriptor_analysis/MFM_model_v3_sa3'))
    parser.add_argument('--materialization-result', type=Path, required=True)
    parser.add_argument('--materialization-result-sha256', required=True)
    parser.add_argument('--ready', type=Path, required=True)
    parser.add_argument('--ready-sha256', required=True)
    parser.add_argument('--export-admission', type=Path, required=True)
    parser.add_argument('--export-admission-sha256', required=True)
    parser.add_argument('--code-sha', required=True)
    parser.add_argument('--evaluator-sha256', required=True,
        help='Machine-derived evaluator file SHA from Root verified new committed source; v1 old pin is not reused')
    parser.add_argument('--run-id', default='A00_short500_primary512_dev9_v1')
    parser.add_argument('--output-root', type=Path, required=True)
    parser.add_argument('--evaluation-output', type=Path, required=True)
    parser.add_argument('--cache-root', type=Path,
        help='Defaults to evaluation-output/h0_cache; v2 keeps all H0 inside the outer supervised evaluation root')
    parser.add_argument('--python-entry', type=Path, required=True)
    args = parser.parse_args()
    if args.cache_root is None:
        args.cache_root = args.evaluation_output / 'h0_cache'
    require(os.getuid() == 1278 and os.environ.get('SLURM_JOB_ID')
        and int(os.environ.get('SLURM_CPUS_PER_TASK', '0')) >= 16, 'Root-owned >=16 CPU Slurm allocation required')
    require(os.environ.get('CUDA_VISIBLE_DEVICES', '') == '', 'This preparation phase is CPU-only')
    require(args.code_sha == EVALUATION_CODE_SHA, 'Use the unchanged fully tested9638 evaluator tree')
    require(args.evaluator_sha256 == BRIDGE_PINS['tools/model_v3/evaluate_dev_panel.py'], 'Root committed evaluator file SHA differs')
    require(args.cache_root.absolute() == (args.evaluation_output / 'h0_cache').absolute(),
        'v2 H0 cache must remain in the outer supervised evaluation root')
    root = args.repository_root.absolute()
    for path in (args.output_root, args.evaluation_output, args.cache_root):
        require(not path.resolve().is_relative_to(root.resolve()) and not path.exists(), 'Fresh outputs/cache outside source tree required')
    args.output_root.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(root / 'current'))
    from phychem_mfm.phase1.v3_dev_store import bound_json
    from phychem_mfm.phase1.v3_h0_packing import packing_plans_for_views
    expected_pins = {**BRIDGE_PINS, 'tools/model_v3/evaluate_dev_panel.py': args.evaluator_sha256}
    pins = {relative: binding(root / relative) for relative in expected_pins}
    require(all(pins[path]['sha256'] == digest for path, digest in expected_pins.items()), 'Committed primary bridge/panel/logging implementation drifted')
    monitor_ref = binding(FIXED_RUNTIME_MONITOR)  # Compute actual bytes on this machine; never transcribe a PTY digest.
    result = bound_json(args.materialization_result, args.materialization_result_sha256)
    require(result.get('status') == 'COMPLETE_FOR_SELECTED_TRAIN' and result.get('cohort_replay_exact') is True
        and result.get('outer_target_records_decoded') == 0, 'A successfully closed selected-TRAIN materialization is mandatory')
    store_ref = result['training_store']; store = bound_json(store_ref['path'], store_ref['sha256'])
    require(store.get('closure_scope') == 'complete_for_selected_TRAIN' and store.get('historical_full_store_claimed') is False,
        'Historical failed partials and unclosed sidecars are not accepted')
    manifest_ref = store['selected_store_manifest']; manifest = bound_json(manifest_ref['path'], manifest_ref['sha256'])
    require(manifest.get('complete') is True and manifest.get('closure_scope') == 'complete_for_selected_TRAIN'
        and manifest['selection_request']['sha256'] == result['selection_request_sha256'], 'Selected source closure differs')
    require(binding(manifest['records_file']['path']) == manifest['records_file'],
        'The new closed selected-TRAIN payload bytes differ; opaque checksum only, no target decoding')
    selection_ref = manifest['selection_request']; selection = bound_json(selection_ref['path'], selection_ref['sha256'])
    require(selection.get('status') == 'FROZEN_LABEL_FREE_SELECTION' and selection['selection']['target_values_decoded'] is False,
        'Original label-free membership selection must remain byte-bound')
    ready_ref, admission_ref = binding(args.ready), binding(args.export_admission)
    require(ready_ref['sha256'] == args.ready_sha256 and admission_ref['sha256'] == args.export_admission_sha256,
        'Root-supplied READY/admission raw bytes differ')
    exported = read_validated_export(ready_ref, admission_ref)
    require(exported['export_job_id'] == '4520486' and args.run_id == 'A00_short500_primary512_dev9_v1',
        'This reviewed launcher uses only the successful A00 export486 diagnostic')
    checkpoint, configuration = exported['checkpoint'], exported['model_configuration']
    prepare = module(root / 'tools/model_v3/prepare_dev_evaluation.py', 'external_primary512_prepare')
    runner = module(root / 'tools/model_v3/evaluate_dev_panel.py', 'external_primary512_evaluator')
    arguments = dict(panel=root / 'configs/dev_panel_v1.json', training_store=store_ref['path'],
        model_configuration=configuration['path'], checkpoint=checkpoint['path'], code_sha=args.code_sha,
        preregistration_sha=PREREGISTRATION, data_version=store['data_version'], pretraining_seed=exported['pretraining_seed'],
        output_root=args.evaluation_output, cache_root=args.cache_root, run_id=args.run_id,
        reference_kind='primary', state_key='model_state',
        maximum_wall_seconds=3400, repository_root=root)
    initial = prepare.make_request(**arguments)
    require(initial['architecture_sha256'] == exported['architecture_sha256'], 'Original full exported model semantics differ from READY')
    require_same_reference(initial['checkpoint'], checkpoint, state_key='model_state')
    require_same_reference(initial['model_configuration'], configuration)
    initial_ref = write(args.output_root / 'request.metadata_planning_only.json', initial)
    _, _, native_store, views, tasks, model_config = runner.load_plan(initial_ref['path'], initial_ref['sha256'], allow_unbound_packing=True)
    require((model_config['backbone']['dim'], model_config['backbone']['layers']) == (512, 6), 'Primary512x6 model required')
    require(len(tasks) == 9, 'The full frozen nine-task panel is required')
    counts = {d: sum(len(view.view(r)) for r in ('train', 'train_inner_validation')) for d, view in views.items()}
    require(counts == {'cyp_isoform': 1803, 'expansionrx': 5326, 'qm9': 10473},
        'Reuse the exact17602-member selectedTRAIN421 panel; a new cohort requires separate review')
    for dataset, view in views.items():
        for role in ('train', 'train_inner_validation'):
            require(list(view.view(role)) == [row['member_index'] for row in selection['selection']['cohorts'][dataset]['roles'][role]],
                'Evaluation membership changed from the sealed label-free selection')
    plans = packing_plans_for_views(native_store, views, initial['h0_packing'])
    require(all(not plan['oversized_singleton_ordinals'] for plan in plans.values()),
        'The pinned packing preset rejects a native singleton; root must review a new bound budget')
    plan_ref = write(args.output_root / 'packing_plans.json', plans)
    request = prepare.make_request(**arguments, h0_packing_plan_sha256={d: p['plan_sha256'] for d, p in plans.items()})
    request_ref = write(args.output_root / 'request.bound.json', request)
    runner.load_plan(request_ref['path'], request_ref['sha256'])
    require(all(binding(root / path) == ref for path, ref in pins.items()), 'Bridge/source changed during CPU preparation')
    read_validated_export(ready_ref, admission_ref, check_freshness=False)
    guard = Path(__file__).with_name('run_panel_guard.py').absolute()
    specification = {'schema': 'model_v3_primary512_dev9_external_launch_v2', 'status': 'PREPARED_NOT_SUBMITTED',
        'repository_root': str(root), 'python_entry': str(args.python_entry.absolute()), 'request': request_ref,
        'request_argv': [str(args.python_entry.absolute()), '-u', '-B', str(root / 'tools/model_v3/evaluate_dev_panel.py'),
            '--request', request_ref['path'], '--request-sha256', request_ref['sha256']],
        'code_sha': args.code_sha, 'preregistration_sha': PREREGISTRATION, 'bridge_pins': pins,
        'external_preparer': binding(__file__), 'external_guard': binding(guard), 'packing_plans': plan_ref,
        'export_admission_implementation': binding(Path(__file__).with_name('export_admission.py')),
        'export_ready': ready_ref, 'export_terminal_admission': admission_ref,
        'export_code_sha': exported['export_code_sha'], 'export_job_id': exported['export_job_id'],
        'checkpoint_scope': 'short500_update_A_diagnostic_H0_tool_and_timing_validation_only',
        'architecture_selection_claimed': False, 'formal_pretraining_complete': False,
        'runtime_monitor': monitor_ref, 'validated_monitor_tree': 'fixed profiler_v2 dc22d3f; read-only',
        'materialization_result': binding(args.materialization_result), 'selected_store': store_ref,
        'selected_store_manifest': manifest_ref, 'selection_request': selection_ref,
        'data_version': store['data_version'], 'source_checkpoint': checkpoint, 'original_configuration': configuration,
        'expected_tasks': 9, 'expected_comparison_cells': 18, 'readouts': ['ridge', 'linear64_relu'],
        'reference_kind': 'primary', 'H0_dimension': 512,
        'fresh_cache_required': True, 'native_fields_units_masks_atom_ids_changed': False,
        'precision_policy': 'FP32 parameters/output; H0 locally disables autocast; preserve and record effective TF32/matmul policy',
        'root_must_admit_actual_GPU_UUID_and_node': True, 'core_holds_existing_UUID_lock': True,
        'maximum_child_wall_seconds': 3500, 'termination_grace_seconds': 20,
        'total_allocation_target_seconds': 3600, 'maximum_process_group_rss_bytes': 28*1024**3,
        'maximum_output_and_cache_bytes': 2*1024**3, 'maximum_global_gpu_memory_fraction': .85,
        'requested_memory_bytes': 32*1024**3,
        'CPU_mem_allocation_minimum': {'cpus': 16, 'memory_MiB': 32768},
        'output_accounting': 'validated owned_output_bytes over maximal disjoint eval/cache/guard roots; SDK symlink rules unchanged',
        'estimated_raw_H0_FP32_bytes_for_both_encoders': sum(p['native_atoms_retained'] for p in plans.values())*512*4*2,
        'metadata_prepare_379': {'actual_state': 'COMPLETED', 'target_records_decoded': 0, 'target_access_audit': 'PASSED'},
        'counts': counts,
        'no_downstream_final_targets_or_old_evaluation_scores': True,
        'performance_target_measured': False}
    spec_ref = write(args.output_root / 'launch_spec.json', specification)
    print(json.dumps({'status': 'PREPARED_NOT_SUBMITTED', 'launch_spec': spec_ref, 'request': request_ref,
        'physical_target_records_decoded': 0, 'counts': specification['counts']}))


if __name__ == '__main__':
    main()
