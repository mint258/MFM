"""Future Root-only Slurm control run. ALL output raw is retained; no production labels."""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import sys
import tempfile
import time
import traceback

sys.path.insert(0, str(Path(__file__).absolute().parent.parent))
from common import (digest, load_config, load_engine, new_output, output_guard,
                    reference, require_pin, require_preflight, runtime, staging_bytes, write_json)
from raw_archive import RawSink
from prepare_v1 import load_audit
from read_outputs_v1 import parse_outputs


def execute_case(case, audit_config, pilot_config, prepared_dir, output, deadline):
    """Call the unchanged invocation once, then retain raw BEFORE offline analysis."""
    import numpy as np
    c, pilot = load_audit(audit_config), load_config(pilot_config)
    folder = Path(output) / case['case_id']
    folder.mkdir(mode=0o700, exist_ok=False)
    scratch = Path('/tmp') / f'pva_{os.environ["SLURM_JOB_ID"]}_{os.getpid()}_{case["case_id"]}'
    scratch.mkdir(mode=0o700, exist_ok=False)
    os.environ.update(TMPDIR=str(scratch), CUDA_VISIBLE_DEVICES='', OMP_NUM_THREADS='1',
                      MKL_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', NUMEXPR_NUM_THREADS='1')
    e = sink = None
    record = {'case_id': case['case_id'], 'pid': os.getpid(), 'status': 'FAILED',
              'production_membership': False, 'QM_call_attempted': False,
              'case': case}
    try:
        e, contract, _ = load_engine(pilot)
        e.initialize_worker(pilot['source_plan']['path'], protocol=contract['protocol']['path'],
                            node_scratch_root=str(scratch), deadline=deadline,
                            audit_membership=str(Path(prepared_dir)/'audit_membership.json'),
                            reproduction_package=contract['reproduction_package']['path'])
        original = e.NATIVE.read_native(case['source_record'])
        if original['z'].tolist() != case['atomic_numbers'] or original['symbols'] != case['symbols']:
            raise ValueError('AUDIT_SOURCE_ATOM_ORDER_CHANGED')
        native = dict(original, coords=np.asarray(case['native_coordinates_A'], dtype='<f8'),
                      energy=None, pairs=[tuple(p) for p in case['pairs']])
        native['native_coordinates_sha256'] = hashlib.sha256(native['coords'].tobytes()).hexdigest()
        task = next(t for t in e.CONFIG['tasks'] if t['name'] == case['calc_type'])
        rendered = e.render_inputs(task, native, case['row'])
        for ref in case['input_files']:
            require_pin(ref)
            name = Path(ref['path']).name
            if hashlib.sha256(rendered[name]).hexdigest() != ref['sha256']:
                raise ValueError('FUTURE_INVOCATION_INPUT_DIFFERS_FROM_PREPARED_CONTROL')
        e.CAPTURED = e.CALL_SCRATCH = e.CAPTURE_ERROR = None
        hashes, combined = e.rendered_input_hashes(task, native, case['row'])
        record['QM_call_attempted'] = True
        result = e.NATIVE.invoke(task, native, case['row'], e.WORK)
        if e.CAPTURE_ERROR is not None:
            raise RuntimeError('AUDIT_RAW_CAPTURE_FAILED') from e.CAPTURE_ERROR
        files = e.CAPTURED or []
        source_status = result['status']
        result['source_status'] = source_status
        invalid = e.validate_atomic_arrays(result, native['z'])
        if invalid and source_status == 'SUCCESS':
            result.update(status='PROPERTY_FAILED', failure_code='REQUESTED_SCOPE_ATOMIC_ARRAY_QC_FAILED',
                          failure_reason=' | '.join(invalid))
        result['scope_status'] = e.canonical_status(result['status'])
        result['status'] = result['scope_status']
        scf = e.extract_scf(task['name'], files, result.get('values'), result['status'], source_status)
        result['provenance'] = {'status': result['status'],
            'software_version_id': e.PACKAGE['software_versions'][task['family']]['software_version_id'],
            'elapsed_seconds': result.get('elapsed_seconds'), 'scf_iterations': scf['scf_iterations'],
            'converged': scf['converged'], 'input_file_sha256': hashes,
            'input_bundle_sha256': combined}
        result['raw_audit_selected'] = True
        context = {'execution_id': case['case_id'], 'job_id': int(os.environ['SLURM_JOB_ID']),
                   'audit_only': True, 'arm': case['arm'], 'condition': case['condition']}
        raw = e.raw_record(task, case['row'], result, files, context)
        raw.update(audit_scope='VECTOR_FRAME_CONTROL_ALL_CALLS', production_membership=False,
                   expected_actual_coordinates_A=case['expected_actual_coordinates_A'])
        sink = RawSink(folder/'all_output_raw.sqlite', e.OUTPUT_ARCHIVE, c['max_raw_bytes_per_case'])
        raw_ref = sink(raw)
        if not raw_ref.get('raw_call_durable'):
            raise RuntimeError('EVERY_FRAME_AUDIT_CALL_MUST_RETAIN_RAW')
        record['raw_reference'] = raw_ref
        # Inputs are separately retained audit artifacts; the output-only raw
        # format and formal P-prime no-input retention policy stay unchanged.
        input_refs = []
        (folder/'actual_postcall_inputs').mkdir()
        for name in rendered:
            if (e.CALL_SCRATCH/name).stat().st_size > c['max_input_bytes_per_case']:
                raise RuntimeError('POSTCALL_INPUT_SIZE_LIMIT_PRESERVE_NODE_SCRATCH')
            observed = (e.CALL_SCRATCH/name).read_bytes()
            path = folder/'actual_postcall_inputs'/name
            with path.open('xb') as stream:
                stream.write(observed); stream.flush(); os.fsync(stream.fileno())
            input_refs.append(dict(reference(path), matches_prepared_bytes=observed == rendered[name]))
        record['actual_postcall_input_references'] = input_refs
        record['parsed_wp5_result'] = result
        try:
            record['independent_raw_readback'] = parse_outputs(files, task['name'], case['symbols'])
            record['status'] = 'CONTROL_CALL_RETAINED_AND_PARSED'
        except Exception as exc:
            record.update(status='CONTROL_RAW_RETAINED_INDEPENDENT_READER_FAILED',
                          independent_reader_error=f'{type(exc).__name__}: {exc}')
        if e.CALL_SCRATCH is not None:
            record['scratch_bytes_removed'] = e.ORIGINAL_CLEANUP(e.CALL_SCRATCH)
            e.CALL_SCRATCH = None
    except Exception as exc:
        record.update(error_type=type(exc).__name__, error=str(exc), traceback=traceback.format_exc())
        if e is not None:
            e.PRESERVE_ARCHIVE_FAILURE = True
    finally:
        if sink is not None:
            sink.close()
        record['engine_close'] = e.close_worker() if e is not None else {'initialized': False}
        record['node_scratch_preserved'] = str(scratch) if any(scratch.iterdir()) else None
        if not any(scratch.iterdir()):
            scratch.rmdir()
        try:
            from wp5_parquet_v2 import native as plain
        except ImportError:
            # A pin/import failure before QM has only primitive case/error data.
            plain = lambda value: value
        payload = staging_bytes(plain(record)) + b'\n'
        if len(payload) > c['max_result_bytes_per_case']:
            payload = staging_bytes({'case_id': case['case_id'], 'status': 'PARSED_RESULT_SIZE_LIMIT',
                'production_membership': False, 'raw_reference': record.get('raw_reference'),
                'node_scratch_preserved': record.get('node_scratch_preserved'),
                'original_result_bytes': len(payload)}) + b'\n'
        with (folder/'result.json').open('xb') as stream:
            stream.write(payload); stream.flush(); os.fsync(stream.fileno())
    return reference(folder/'result.json')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--execute', action='store_true', help='Root-reviewed audit only; never implicit QM')
    p.add_argument('--config', type=Path, required=True)
    p.add_argument('--pilot-config', type=Path, required=True)
    p.add_argument('--prepared', type=Path, required=True)
    p.add_argument('--prepared-sha256', required=True)
    p.add_argument('--root-preflight', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    if not args.execute:
        p.error('QM requires the explicit --execute flag AND exact Root Slurm preflight')
    c = load_audit(args.config)
    if reference(args.pilot_config) != c['pilot_config']:
        raise ValueError('REGISTERED_PILOT_CONFIG_REQUIRED')
    observed = runtime(16)
    preflight = require_preflight(args.root_preflight, args.config, c)
    if digest(args.prepared/'prepared.json') != args.prepared_sha256:
        raise ValueError('FRAME_AUDIT_PREPARED_MANIFEST_SHA_CHANGED')
    prepared = json.loads((args.prepared/'prepared.json').read_text())
    if prepared['status'] != 'VECTOR_AUDIT_INPUTS_PREPARED_QM_NOT_STARTED' or prepared['production_membership']:
        raise ValueError('ISOLATED_CONTROL_PREPARATION_REQUIRED')
    if prepared['config'] != reference(args.config) or prepared['pilot_config'] != reference(args.pilot_config):
        raise ValueError('PREPARED_AUDIT_CONFIGURATION_CHANGED')
    require_pin(prepared['cases']); require_pin(prepared['audit_membership'])
    cases = json.loads(Path(prepared['cases']['path']).read_text())
    if not 36 <= len(cases) <= 72:
        raise ValueError('TWO_TO_FOUR_MOLECULE_36_TO_72_CALL_SCOPE_REQUIRED')
    out = new_output(args.output, c)
    write_json(out/'reproduction_manifest.json', {'status': 'AUDIT_REFERENCES_FROZEN_BEFORE_QM',
               'config': reference(args.config), 'pilot_config': reference(args.pilot_config),
               'prepared': reference(args.prepared/'prepared.json'),
               'new_sources': [reference(path) for path in sorted(Path(__file__).parent.glob('*.py'))],
               'official_source_references': c['official_source_references'], 'production_membership': False})
    deadline = time.time()+c['worker_wall_seconds']
    short_tmp = Path('/tmp')/f'va_{observed["job_id"]}_{os.getpid()}'
    short_tmp.mkdir(mode=0o700, exist_ok=False)
    os.environ['TMPDIR'] = str(short_tmp)
    tempfile.tempdir = str(short_tmp)
    pool = ProcessPoolExecutor(max_workers=16, mp_context=multiprocessing.get_context('spawn'))
    futures = [pool.submit(execute_case, case, str(args.config), str(args.pilot_config),
                           str(args.prepared), str(out), deadline) for case in cases]
    processes = list(pool._processes.values())
    refs, errors = [], []
    try:
        for future in as_completed(futures):
            try:
                refs.append(future.result())
            except Exception as exc:
                errors.append({'type': type(exc).__name__, 'message': str(exc)})
    finally:
        pool.shutdown(wait=True, cancel_futures=False)
    closure = [{'pid': p.pid, 'exitcode': p.exitcode, 'alive': p.is_alive()} for p in processes]
    write_json(out/'run_closed.json', {'status': 'FRAME_CONTROL_EXECUTION_CLOSED_NOT_FRAME_ACCEPTANCE',
               'runtime': observed, 'root_preflight': preflight, 'prepared': reference(args.prepared/'prepared.json'),
               'results': refs, 'execution_errors': errors, 'process_closure': closure,
               'all_workers_joined': len(closure) == 16 and all(not p['alive'] and p['exitcode'] == 0 for p in closure),
               'parent_short_tmp': str(short_tmp),
               'production_membership': False, 'output_bytes_before_manifest': output_guard(out, c, reserve=1 << 20)})
    if not any(short_tmp.iterdir()):
        short_tmp.rmdir()


if __name__ == '__main__':
    main()
