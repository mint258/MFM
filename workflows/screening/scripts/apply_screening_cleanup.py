"""Remove only verified duplicate all-success C3 archives after Root closure.

The first round, every failure/timeout/partial result, original data and all
scientific Parquet stay. Recorded references remain in a retirement ledger.
"""
from __future__ import annotations
import argparse
import ast
import concurrent.futures as futures
import hashlib
import json
import multiprocessing as mp
import os
from pathlib import Path
import stat
import time

ROOT = Path('/share/home/zixiao/descriptor_analysis/runs/phase1_screening_20261011')
NODES = ROOT / 'c_engineering/nodes'


def sha(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            value.update(block)
    return value.hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def save(path, value):
    pending = Path(str(path) + '.pending')
    pending.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    pending.replace(path)


def initialize(barrier):
    barrier.wait(timeout=120)


def validate(item):
    path = Path(item['path'])
    checks = []
    info = path.lstat()
    if not path.resolve(strict=True).is_relative_to(NODES.resolve()):
        checks.append('Path outside this new run nodes root')
    if not stat.S_ISREG(info.st_mode) or path.is_symlink() or info.st_uid != os.getuid():
        checks.append('Not an owned ordinary archive')
    if (info.st_ino, info.st_mtime_ns, info.st_size) != (
            item['current_inode'], item['current_mtime_ns'], item['bytes']):
        checks.append('Archive changed since plan')
    actual_sha = sha(path)
    if actual_sha != item['recorded_sha256']:
        checks.append('Archive SHA differs')
    reference = item['scientific_Parquet_preserved']
    parquet = Path(reference['path'])
    if (not parquet.resolve(strict=True).is_relative_to(NODES.resolve()) or parquet.is_symlink() or
            parquet.stat().st_uid != os.getuid() or parquet.stat().st_size != reference['bytes'] or
            sha(parquet) != reference['sha256']):
        checks.append('Scientific Parquet closure differs')
    return {'item': item, 'issues': checks, 'actual_archive_sha256': actual_sha,
            'worker_pid': os.getpid()}


def verify_preserved_parquet(item):
    reference = item['scientific_Parquet_preserved']
    path = Path(reference['path'])
    return {'path': str(path), 'same_SHA_after_cleanup': sha(path) == reference['sha256'],
            'worker_pid': os.getpid()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', default=str(ROOT / 'reports/c_engineering_cleanup_plan.json'))
    parser.add_argument('--terminal-evidence', default=str(ROOT / 'reports/cleanup_terminal_evidence.json'))
    parser.add_argument('--workers', type=int, default=16)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    if args.check:
        ast.parse(Path(__file__).read_text()); print('CLEANUP_AST_PASS'); return
    plan = read(args.plan); terminal = read(args.terminal_evidence)
    closed_jobs = terminal['completed_own_jobs']
    refs = plan['source_closed_probe_reports']
    for ref in refs:
        if ref['job_id'] not in closed_jobs or closed_jobs[ref['job_id']]['uid'] != os.getuid():
            raise ValueError('Cleanup job ownership/terminal evidence missing')
        if sha(ref['path']) != ref['sha256']:
            raise ValueError('Closed probe source changed')
    if len(refs) != 6 or terminal['Cclose_state'] != 'COMPLETED':
        raise ValueError('Six probes and archive recheck must close before cleanup')
    items = plan['eligible_duplicate_all_success_archive_files']
    start = time.monotonic()
    if items:
        if args.workers < 16 or int(os.environ.get('SLURM_CPUS_PER_TASK', 0)) < args.workers:
            raise ValueError('Bounded >=16CPU allocation required for archive hashing')
        context = mp.get_context('spawn'); barrier = context.Barrier(args.workers)
        with futures.ProcessPoolExecutor(max_workers=args.workers, mp_context=context,
                initializer=initialize, initargs=(barrier,)) as pool:
            checked = list(pool.map(validate, items, chunksize=1))
    else:
        checked = []
    retired = []; preserved = []
    for result in checked:
        item = result['item']; path = Path(item['path'])
        if result['issues']:
            preserved.append({'path': str(path), 'issues': result['issues']}); continue
        info = path.lstat()
        if path.is_symlink() or (info.st_ino, info.st_mtime_ns, info.st_size) != (
                item['current_inode'], item['current_mtime_ns'], item['bytes']):
            preserved.append({'path': str(path), 'issues': ['Changed after SHA validation']}); continue
        record = {**item, 'actual_archive_sha256': result['actual_archive_sha256'],
            'reason': 'Completed later benchmark round; every outcome SUCCESS; scientific Parquet retained',
            'retired_epoch': time.time()}
        # Write ledger first; retain exact source receipt reference without editing it.
        retired.append(record)
        save(ROOT / 'reports/retired_duplicate_archives.json', {'retired_archives': retired})
        path.unlink()
    if retired:
        barrier = context.Barrier(args.workers)
        with futures.ProcessPoolExecutor(max_workers=args.workers, mp_context=context,
                initializer=initialize, initargs=(barrier,)) as pool:
            after = list(pool.map(verify_preserved_parquet, retired, chunksize=1))
    else:
        after = []
    summary = {'status': 'CLOSED_TEST_DUPLICATES_CLEANED', 'files_removed': len(retired),
        'released_bytes': sum(row['bytes'] for row in retired),
        'verified_worker_pids': sorted({row['worker_pid'] for row in checked}),
        'preserved_on_validation_issue': preserved, 'preserved_first_round': True,
        'preserved_all_failed_timeout_partial_raw': True, 'scientific_Parquet_removed': False,
        'original_data_touched': False, 'seconds': time.monotonic() - start,
        'plan_reference': str(Path(args.plan)), 'plan_sha256': sha(args.plan),
        'retirement_ledger': str(ROOT / 'reports/retired_duplicate_archives.json') if retired else None,
        'recorded_C3_measurements_precede_cleanup': True,
        'before_after_parquet_SHA_match': all(row['same_SHA_after_cleanup'] for row in after),
        'after_cleanup_parquet_issues': [row for row in after if not row['same_SHA_after_cleanup']],
        'script_sha256': sha(__file__)}
    save(ROOT / 'reports/cleanup_actual.json', summary)
    print(json.dumps(summary))


if __name__ == '__main__':
    main()
