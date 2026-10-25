"""Run the reviewed P-prime pilot only; this CLI never submits Slurm or starts full scale."""
from __future__ import annotations

import argparse
import atexit
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import sys
import time
import traceback

from common import (TASKS, digest, load_config, load_engine, new_output, output_guard,
                    read_staging, reference, require_pin, require_preflight, runtime,
                    staging_bytes, write_json)


def run_lane(lane, tasks, config_path, prepared, output, scratch_parent, reproduction_sha, deadline):
    """One submitted process owns one serial QM lane and closes it in finally."""
    c = load_config(config_path)
    root = Path(output)
    lane_root = root / f'lane-{lane:02d}'
    lane_root.mkdir(mode=0o700, exist_ok=False)
    scratch = Path(scratch_parent) / f'lane-{lane:02d}'
    scratch.mkdir(mode=0o700, exist_ok=False)
    os.environ.update(TMPDIR=str(scratch), TMP=str(scratch), CUDA_VISIBLE_DEVICES='',
                      OMP_NUM_THREADS='1', MKL_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1',
                      NUMEXPR_NUM_THREADS='1')
    e = sink = None
    records = 0
    staged = 0
    result = {'lane': lane, 'pid': os.getpid(), 'status': 'FAILED', 'records': 0}
    try:
        from engine_adapter import compute_pair
        from raw_archive import RawSink
        e, contract, _ = load_engine(c)
        e.initialize_worker(c['source_plan']['path'], protocol=contract['protocol']['path'],
                            node_scratch_root=str(scratch), deadline=deadline,
                            audit_membership=str(Path(prepared) / 'audit_membership.json'),
                            reproduction_package=contract['reproduction_package']['path'])
        sink = RawSink(lane_root / 'raw_outputs.sqlite', e.OUTPUT_ARCHIVE,
                       c['max_retained_raw_bytes_per_worker'])
        import wp5_parquet_v2 as wire
        with (lane_root / 'parsed_records.jsonl').open('xb') as stream:
            for task in tasks:
                for pair in task:
                    if time.time() >= deadline - 60:
                        raise RuntimeError('PPRIME_PILOT_WALL_BUDGET_ADMISSION_CLOSED')
                    record = compute_pair(e, pair, sink, {
                        'job_id': int(os.environ['SLURM_JOB_ID']), 'lane': lane,
                        'pprime_reproduction_manifest_sha256': reproduction_sha})
                    record['lane'] = lane
                    payload = staging_bytes(wire.native(record)) + b'\n'
                    if staged + len(payload) > c['max_staging_bytes_per_worker']:
                        raise RuntimeError('PPRIME_PER_WORKER_PARSED_OUTPUT_CAP')
                    stream.write(payload)
                    stream.flush()
                    os.fsync(stream.fileno())
                    staged += len(payload)
                    records += 1
                print(json.dumps({'lane': lane, 'completed_records': records}), flush=True)
        result.update(status='COMPLETE', records=records,
                      staged=reference(lane_root / 'parsed_records.jsonl'))
    except Exception as exc:
        result.update(error_type=type(exc).__name__, error=str(exc),
                      traceback=traceback.format_exc(), records=records)
        if e is not None:
            e.PRESERVE_ARCHIVE_FAILURE = True
    finally:
        if sink is not None:
            sink.close()
        staging_path = lane_root / 'parsed_records.jsonl'
        if staging_path.is_file():
            result['staged'] = reference(staging_path)
        result['engine_close'] = e.close_worker() if e is not None else {'initialized': False}
        result['raw_container'] = reference(lane_root / 'raw_outputs.sqlite') if (lane_root / 'raw_outputs.sqlite').is_file() else None
        result['scratch_path'] = str(scratch)
        result['scratch_preserved'] = any(scratch.iterdir())
        # Only empty, exact self-created lane roots are removed; failed scratch stays.
        if not result['scratch_preserved']:
            scratch.rmdir()
        write_json(lane_root / 'worker_closed.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True, type=Path)
    parser.add_argument('--prepared', required=True, type=Path)
    parser.add_argument('--prepared-sha256', required=True)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--root-preflight', required=True, type=Path)
    args = parser.parse_args()
    c = load_config(args.config)
    observed = runtime(c['workers'])
    preflight = require_preflight(args.root_preflight, args.config, c)
    prepared_path = args.prepared / 'prepared.json'
    if digest(prepared_path) != args.prepared_sha256:
        raise ValueError('EXACT_PREPARED_MANIFEST_SHA_REQUIRED')
    prepared = json.loads(prepared_path.read_text())
    if prepared['status'] != 'PPRIME_PAIRS_READY_NOT_QM_EXECUTED' or prepared['config'] != reference(args.config):
        raise ValueError('EXACT_CONFIG_AND_PREPARED_PAIR_LINEAGE_REQUIRED')
    for pin in prepared['outputs']:
        require_pin(pin)
    pairs = [json.loads(line) for line in (args.prepared / 'pairs.jsonl').read_text().splitlines()]
    grouped = {}
    for pair in pairs:
        if pair['geometry_source'] != 'uff_sprime':
            raise ValueError('PPRIME_ONLY_ACCEPTS_UFF_GEOMETRY')
        if hashlib.sha256(__import__('common').canonical(pair['conformer'])).hexdigest() != pair['conformer_row_sha256']:
            raise ValueError('PREPARED_UFF_ROW_CHANGED')
        grouped.setdefault(pair['molecule_id'], []).append(pair)
    if len(pairs) != 2000 or len(grouped) != 1000 or any(len(v) != 2 for v in grouped.values()):
        raise ValueError('EXACT_1000_BY_TWO_PILOT_REQUIRED')
    out = new_output(args.output, c)
    e, contract, protocol = load_engine(c)
    e.CONFIG = protocol
    source_refs = [reference(p) for p in sorted(Path(__file__).parent.glob('*.py'))]
    reproduction = {'schema': 'PPRIME_PILOT_REPRODUCTION_REFERENCES_V1',
                    'status': 'INPUT_AND_SCIENCE_REFERENCES_FROZEN_BEFORE_QM',
                    'config': reference(args.config), 'prepared': reference(prepared_path),
                    'sources': source_refs, 'legacy_contract': c['legacy_contract'],
                    'legacy_reproduction_package': contract['reproduction_package'],
                    'audit_membership': reference(args.prepared / 'audit_membership.json'),
                    'geometry_source': 'uff_sprime', 'Q02_applicable': False,
                    'legacy_package_audit_membership_is_lineage_only': True,
                    'new_audit_membership_is_used_for_new_records': True,
                    'task_recipe_and_software_changed': False}
    reproduction_ref = write_json(out / 'reproduction_manifest.json', reproduction)
    short_tmp = Path('/tmp') / f'pp_{observed["job_id"]}_{os.getpid()}'
    short_tmp.mkdir(mode=0o700, exist_ok=False)
    os.environ['TMPDIR'] = str(short_tmp)
    deadline = time.time() + c['worker_wall_seconds']
    molecules = [sorted(grouped[mid], key=lambda p: p['random_order_rank']) for mid in sorted(grouped)]
    started = time.monotonic()
    closed = []
    pool = ProcessPoolExecutor(max_workers=16, mp_context=multiprocessing.get_context('spawn'))
    futures = [pool.submit(run_lane, lane, molecules[lane::16], str(args.config),
                           str(args.prepared), str(out), str(short_tmp),
                           reproduction_ref['sha256'], deadline) for lane in range(16)]
    processes = list(pool._processes.values())
    try:
        for future in as_completed(futures):
            try:
                closed.append(future.result())
            except Exception as exc:
                closed.append({'status': 'WORKER_FAILED_BEFORE_CLOSURE', 'error': str(exc),
                               'error_type': type(exc).__name__})
    finally:
        # Wait for already-running calculations; no terminate()/scancel()/pool kill.
        pool.shutdown(wait=True, cancel_futures=False)
    process_closure = [{'pid': p.pid, 'exitcode': p.exitcode, 'alive': p.is_alive()} for p in processes]
    all_joined = len(process_closure) == 16 and all(not p['alive'] and p['exitcode'] == 0 for p in process_closure)
    failures = [r for r in closed if r['status'] != 'COMPLETE']
    if not all_joined or len({r.get('pid') for r in closed}) != 16:
        failures.append({'status': 'SIXTEEN_DISTINCT_JOINED_WORKERS_NOT_PROVEN'})
    records = []
    for item in closed:
        if item.get('staged'):
            require_pin(item['staged'])
            with Path(item['staged']['path']).open('rb') as stream:
                records.extend(read_staging(line) for line in stream)
    records.sort(key=lambda row: row['record_id'])
    refs, qc = [], []
    if len(records) == 2000 and not failures:
        from export_families import export
        refs, qc = export(records, out / 'parquet', e, reproduction_ref['sha256'], c)
    task_statuses = Counter(d['scope_status'] for r in records for d in r['tasks'])
    failure_reasons = Counter((d['task'], d.get('failure_code') or 'UNSPECIFIED')
                             for r in records for d in r['tasks'] if d['scope_status'] != 'SUCCESS')
    success_records = (sum(row['all_twelve_tasks_success'] for row in qc) if qc else
                       sum(len(r['tasks']) == 12 and all(d['scope_status'] == 'SUCCESS'
                                                        for d in r['tasks']) for r in records))
    by_task = {task: {'requested_records': 2000,
                     'completed_record_task_slots': sum(d['task'] == task for r in records for d in r['tasks']),
                     'success_slots': sum(d['task'] == task and d['scope_status'] == 'SUCCESS'
                                          for r in records for d in r['tasks'])} for task in TASKS}
    report = {'status': 'PPRIME_PILOT_COMPUTE_CLOSED_AWAITING_PARENT_ACCOUNTING' if not failures and refs else 'PPRIME_PILOT_FAILED_NO_FULL_AUTHORITY',
              'runtime': observed, 'config': reference(args.config), 'root_preflight': preflight,
              'prepared': reference(prepared_path), 'reproduction_manifest': reproduction_ref,
              'completed_records': len(records), 'requested_records': 2000,
              'all_twelve_tasks_success_records': success_records,
              'record_success_rate': success_records / 2000,
              'task_statuses': dict(task_statuses),
              'task_statistics': by_task,
              'task_count_scope': 'completed parsed records; failed partial execution evidence remains in worker reports/raw containers and is not invented as zero calls',
              'failure_reasons': [{'task': k[0], 'code': k[1], 'count': v} for k, v in sorted(failure_reasons.items())],
              'workers': closed, 'process_closure': process_closure, 'all_workers_joined': all_joined,
              'failures': failures, 'family_parquets': refs,
              'wall_seconds_within_cli': time.monotonic() - started,
              'allocated_core_seconds_per_conformer': None,
              'accounting_reason': 'Root must close actual sacct parent ElapsedRaw*AllocCPUS, including setup/export and failures',
              'Pprime_outlier_scan_completed': False, 'P_vs_Pprime_comparison_completed': False,
              'full_run_started_or_authorized_by_this_script': False,
              'original_lmdb_or_wp5_modified': False,
              'scratch_parent': str(short_tmp), 'output_bytes_before_report': output_guard(out, c, reserve=2 << 20)}
    write_json(out / 'result.json', report)
    if short_tmp.is_dir() and not any(short_tmp.iterdir()):
        short_tmp.rmdir()
    print(json.dumps({'status': report['status'], 'records': len(records), 'output': str(out)}))
    return 0 if report['status'] == 'PPRIME_PILOT_COMPUTE_CLOSED_AWAITING_PARENT_ACCOUNTING' else 1


if __name__ == '__main__':
    sys.exit(main())
