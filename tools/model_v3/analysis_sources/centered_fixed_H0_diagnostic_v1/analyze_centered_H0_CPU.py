#!/usr/bin/env python3
"""CPU-only frozen1503 functions evaluated at a NEW centered capture's actual H0."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
import os
from pathlib import Path
import socket
import sys
import traceback
from diagnostic_common import (HERE, OLD, INPUT_CAP, bound, load_file, load_shadow,
    metadata_ref, need, read_metadata, ref, save_plain, source_snapshot)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('capture-complete', 'capture-supervisor', 'capture-accounting'):
        p.add_argument('--'+name, type=Path, required=True)
        p.add_argument('--'+name+'-sha256', required=True)
    p.add_argument('--source-pins-sha256', required=True)
    p.add_argument('--expected-node', choices=['compute-0-'+str(i) for i in (2, *range(8, 20))], required=True)
    p.add_argument('--output-root', type=Path, required=True)
    a = p.parse_args()
    need(os.environ.get('CUDA_VISIBLE_DEVICES') == ''
         and socket.gethostname().split('.')[0] == a.expected_node
         and os.environ.get('SLURM_JOB_ID', '').isdigit()
         and int(os.environ.get('SLURM_CPUS_PER_TASK', '0')) == 16,
         'Actual16CPU-only allocation required')
    complete_ref = {**metadata_ref(a.capture_complete), 'sha256': a.capture_complete_sha256}
    sup_ref = {**metadata_ref(a.capture_supervisor), 'sha256': a.capture_supervisor_sha256}
    acc_ref = {**metadata_ref(a.capture_accounting), 'sha256': a.capture_accounting_sha256}
    complete = read_metadata(complete_ref)
    need(complete['schema'] == 'model_v3_fixed_h0_capture_complete_v1', 'Typed completion required')
    capture = read_metadata(complete['manifest'])
    need(capture['schema'] == 'model_v3_fixed_h0_capture_manifest_v1'
         and capture['status'] == 'CAPTURE_COMPLETE' and capture['failure'] is None
         and capture['source_before_after_equal']
         and capture['encoder_forwards'] == capture['completed_case_encoder_forwards'] == 192
         and capture['full_FP64_encoder_forwards'] == 0 and len(capture['cases']) == 48
         and capture['input_limit_bytes'] == INPUT_CAP and capture['input_bytes_before_manifest'] <= INPUT_CAP
         and capture['centered_lineage'] == 'fresh_centered_capture_not_1776_hidden_H0'
         and capture['external1776_terminal_replay_passed']
         and all(row['external1776_terminal_control_passed'] for row in capture['cases']),
         'Complete fresh centered capture and all48 external terminal replay required')
    need(capture['job_id'] not in ('4521435', '4521492', '4521776'), 'A new capture job is required')
    request = read_metadata(capture['request'])
    pins_ref = {**metadata_ref(HERE/'source_pins_v1.json'), 'sha256': a.source_pins_sha256}
    need(capture['source_pins'] == pins_ref, 'Exact new capture producer source required')
    sources = source_snapshot(request, a.source_pins_sha256)
    need([row['case_id'] for row in capture['cases']] == request['expected_case_ids'], 'No subset accepted')
    for leaf in capture['cases']:
        case = read_metadata(leaf['capture_case'])
        need(case['centered_lineage'] == 'fresh_centered_capture_not_1776_hidden_H0'
             and case['external1776_terminal_control']['passed']
             and case['original1492_parameter_sha256'] == request['original1492_parameter_sha256'][case['case_id']],
             'New per-case lineage/parameter/replay control required')
    sup, acc = read_metadata(sup_ref), read_metadata(acc_ref)
    need(sup['job_id'] == capture['job_id'] and sup['status'] == 'COMPLETED'
         and sup['exit_code'] == 0 and sup['first_failure'] is None
         and sup['remaining_recorded_processes_before_retirement'] == []
         and sup['private_storage_cleanup_errors'] == [], 'Actual capture supervisor must close successfully')
    expected = [request['GPU_python'], '-u', '-B', str(HERE/'capture_centered_H0.py'),
        '--request', capture['request']['path'], '--request-sha256', capture['request']['sha256'],
        '--output-root', str(a.capture_complete.parent)]
    need(sup['command'] == expected and sup['supervisor_source_sha256'] == request['supervisor_source']['sha256']
         and sup['gpu_uuid'] == request['gpu_uuid'] and sup['foreign_gpu_processes_signalled'] is False,
         'Actual source-bound capture command/GPU differs')
    metadata = load_file(OLD/'cpu_metadata_v3.py', '_centered_H0_original_CPU_metadata')
    accounting = metadata.validate_capture_accounting(acc, capture['job_id'])
    entries = list(a.capture_complete.parent.rglob('*'))
    need(not any(path.is_symlink() for path in entries)
         and sum(path.stat().st_size for path in entries if path.is_file()) <= INPUT_CAP,
         'Actual complete capture input scope exceeds128MiB')
    need(not a.output_root.exists(), 'Fresh CPU analysis output required')
    a.output_root.mkdir()
    save_plain(a.output_root/'sources_before.json', sources)
    result, failure = None, None
    try:
        import phychem_mfm
        need(Path(phychem_mfm.__file__).resolve() == (Path(request['repository'])/'current/phychem_mfm/__init__.py').resolve(),
             'Only the centered candidate model namespace may rebuild the exact CPU head state')
        import torch
        import numpy as np
        torch.set_num_threads(4)
        original = load_shadow()
        controls = original.tiny_selfcheck()
        payloads = [original.decode_case(leaf) for leaf in capture['cases']]
        with ThreadPoolExecutor(max_workers=4) as executor:
            rows = list(executor.map(original.evaluate, payloads))
        need([row['case_id'] for row in rows] == request['expected_case_ids']
             and len(rows) == 48 and sum(len(row['observations']) for row in rows) == 432,
             'All48/all432 observations required')
        result = {'schema': 'model_v3_centered_fixed_H0_terminal_shadow_result_v1',
            'status': 'SHADOW_COMPLETE_DIAGNOSTIC_ONLY', 'capture_complete': complete_ref,
            'capture_supervisor': sup_ref, 'capture_accounting': acc_ref,
            'capture_accounting_validation': accounting, 'capture_manifest': complete['manifest'],
            'lineage': 'new_centered_capture_H0_not_1776_internal_H0', 'cases': rows,
            'case_count': 48, 'field_transform_observations': 432,
            'frozen_1503_implementation': metadata_ref(OLD/'shadow_terminals_v1.py'),
            'selfcheck': controls, 'encoder_forwards_in_CPU_analysis': 0, 'full_FP64_encoder_forwards': 0,
            'CPU_environment': {'python': sys.executable, 'python_resolved': str(Path(sys.executable).resolve()),
                'python_version': sys.version, 'torch_version': str(torch.__version__), 'numpy_version': str(np.__version__),
                'torch_threads': torch.get_num_threads(), 'torch_interop_threads': torch.get_num_interop_threads(),
                'thread_environment': {key:os.environ.get(key) for key in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS')},
                'old1503_environment_equivalence_asserted': False},
            'absolute_tolerance': 1e-5, 'relative_tolerance': 0,
            'threshold_changed': False, 'FP64_production': False, 'scientific_adoption': False,
            'interpretation': 'Use same-component signed H/G/I/head_arithmetic_delta; residual alone does not identify encoder'}
        save_plain(a.output_root/'SHADOW_RESULT.json', result)
        with (a.output_root/'shadow_summary.csv').open('x', newline='') as stream:
            writer = csv.writer(stream)
            keys = ('GPU_FP32_D', 'CPU_FP32_D', 'D', 'H', 'G', 'I', 'head_arithmetic_delta')
            writer.writerow(['case_id', 'field', 'transform', *('maxabs_'+key for key in keys)])
            for row in rows:
                for obs in row['observations']:
                    writer.writerow([row['case_id'], obs['field'], obs['transform'], *(obs['maxabs'][key] for key in keys)])
            stream.flush(); os.fsync(stream.fileno())
    except BaseException as error:
        failure = {'type': type(error).__name__, 'message': str(error), 'traceback': traceback.format_exc()}
    finally:
        after = {path: ref(path) for path in sources}
        save_plain(a.output_root/'sources_after.json', after)
        if after != sources:
            failure = {'earlier': failure, 'source_after': 'Analysis source changed'}
        if failure is not None:
            save_plain(a.output_root/'FAILED.json', failure)
        elif result is not None:
            save_plain(a.output_root/'COMPLETE.json', {'schema': 'model_v3_centered_fixed_H0_shadow_complete_v1',
                'result': ref(a.output_root/'SHADOW_RESULT.json'), 'sources_unchanged': True})
    return 1 if failure else 0

if __name__ == '__main__':
    raise SystemExit(main())