"""Bound one CPU-only child using the already tested process/storage helpers."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

HELPERS = Path('/share/home/zixiao/descriptor_analysis/MFM_model_v3_sa1_a/tools/model_v3')
sys.path.insert(0, str(HELPERS))
import psutil
from private_runtime_storage import PrivateStorage, _write_exclusive
from runtime_monitor import capture_process_identity, owned_process_observation, owned_output_bytes, inherited_log_bytes
from run_supervised import stop_recorded, live_recorded, IDENTITY_KEYS


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-root', type=Path, required=True)
    parser.add_argument('--record', type=Path, required=True)
    parser.add_argument('--wall-seconds', type=int, default=3300)
    parser.add_argument('--rss-limit-bytes', type=int, default=48*1024**3)
    parser.add_argument('--output-budget-bytes', type=int, default=2*1024**3)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    if (not command or not Path(command[0]).is_absolute() or not os.environ.get('SLURM_JOB_ID')
            or os.environ.get('CUDA_VISIBLE_DEVICES') != '' or int(os.environ.get('SLURM_CPUS_PER_TASK','0')) < 16):
        raise ValueError('Explicit CPU-only command in an owned >=16CPU allocation required')
    if not 60 <= args.wall_seconds <= 3600 or not 0 < args.rss_limit_bytes <= 48*1024**3:
        raise ValueError('Bounded CPU wall/RSS required')
    if args.output_budget_bytes != 2*1024**3 or args.record.absolute().is_relative_to(args.output_root.absolute()):
        raise ValueError('Bounded output and external supervision record required')
    journal = args.record.with_suffix('.journal.jsonl')
    receipt = args.record.with_suffix('.storage.json')
    if any(path.exists() for path in (args.output_root,args.record,journal,receipt)):
        raise FileExistsError('Fresh output and supervision artifacts required')
    args.record.parent.mkdir(parents=True, exist_ok=True)
    source_files = [Path(__file__), *(HELPERS/name for name in
        ('runtime_monitor.py','run_supervised.py','private_runtime_storage.py'))]
    before = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in source_files}
    storage = PrivateStorage(Path('/tmp')/('mv3n_'+os.environ['SLURM_JOB_ID']), budget_bytes=args.output_budget_bytes)
    pin = _write_exclusive(receipt, storage.bindings)
    environment = {**os.environ, **storage.bindings['environment'],
                   'MODEL_V3_STORAGE_BINDINGS_PATH': str(receipt), 'MODEL_V3_STORAGE_BINDINGS_SHA256': pin}
    group = Path('/proc/self/cgroup').read_text()
    child = subprocess.Popen(command, stdin=subprocess.DEVNULL, start_new_session=True, env=environment)
    observed, first_failure, retirement, remaining = {}, None, None, []
    start, launch, last_bytes = time.monotonic(), None, 0
    storage.start()
    try:
        launch = capture_process_identity(child.pid, expected_cgroup=group, expected_argv=command)
        if launch['status'] == 'ACTIVE':
            observed[(child.pid,launch['start_ticks'])] = launch
        elif launch['status'] not in ('GONE','EXITING'):
            raise RuntimeError('CPU child launch identity differs')
        while child.poll() is None:
            try:
                processes = owned_process_observation(child.pid)
                for process in processes['processes']:
                    bound = capture_process_identity(process['pid'], expected_cgroup=group)
                    if bound['status'] == 'ACTIVE':
                        key = bound['pid'],bound['start_ticks']
                        if key in observed and any(observed[key][name] != bound[name] for name in IDENTITY_KEYS):
                            raise RuntimeError('Recorded CPU descendant identity changed')
                        observed[key] = bound
                    elif bound['status'] not in ('GONE','EXITING'):
                        raise RuntimeError('CPU descendant left the bound identity/cgroup')
                private = storage.check()
                logs = inherited_log_bytes(exclude_root=args.output_root)
                journal_bytes = journal.stat().st_size if journal.exists() else 0
                last_bytes = owned_output_bytes(args.output_root)+private['last']['bytes']+logs+journal_bytes+receipt.stat().st_size
                row = {'elapsed_seconds': time.monotonic()-start, 'processes': processes,
                       'total_observed_bytes': last_bytes, 'private_storage': private}
                encoded = json.dumps(row)+'\n'
                if journal_bytes+len(encoded.encode()) > 32*1024**2 or logs > 32*1024**2:
                    raise MemoryError('CPU supervision/job logs exceeded explicit bound')
                with journal.open('a') as stream:
                    stream.write(encoded); stream.flush(); os.fsync(stream.fileno())
                if processes['rss_sum_bytes'] > args.rss_limit_bytes:
                    raise MemoryError('Owned CPU child tree exceeded RSS cap')
                if last_bytes > args.output_budget_bytes-16*1024**2:
                    raise MemoryError('Owned CPU output plus private scratch reached finalization reserve')
                if time.monotonic()-start > args.wall_seconds-30:
                    raise TimeoutError('CPU child reached wall/finalization reserve')
            except psutil.NoSuchProcess:
                if child.poll() is None:
                    raise
                break
            time.sleep(1.)
    except BaseException as exc:
        first_failure = {'type': type(exc).__name__, 'message': str(exc)}
        try:
            for process in owned_process_observation(child.pid)['processes']:
                bound = capture_process_identity(process['pid'], expected_cgroup=group)
                if bound['status'] == 'ACTIVE':
                    observed[(bound['pid'],bound['start_ticks'])] = bound
        except (OSError, psutil.Error):
            pass
        retirement = stop_recorded(observed)
    finally:
        if child.poll() is None:
            retirement = stop_recorded(observed)
        try:
            code = child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            code = None
        remaining = live_recorded(observed)
        if remaining:
            retirement = stop_recorded(observed)
            remaining = live_recorded(observed)
        if code != 0 and first_failure is None:
            first_failure = {'phase': 'child_exit', 'exit_code': code}
        try:
            private_final = storage.stop()
        except BaseException as exc:
            private_final = storage.observation()
            first_failure = first_failure or {'phase': 'storage_close', 'type': type(exc).__name__, 'message': str(exc)}
        try:
            last_bytes = (owned_output_bytes(args.output_root)+private_final['last']['bytes']
                          +inherited_log_bytes(exclude_root=args.output_root)+receipt.stat().st_size
                          +(journal.stat().st_size if journal.exists() else 0))
            if last_bytes > args.output_budget_bytes-16*1024**2:
                raise MemoryError('Final CPU output plus private scratch exceeded reserve')
        except BaseException as exc:
            first_failure = first_failure or {'phase': 'final_census', 'type': type(exc).__name__, 'message': str(exc)}
        if before != {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in source_files}:
            first_failure = first_failure or {'phase': 'source_changed'}
        report = {'status': 'COMPLETED' if code == 0 and first_failure is None and not remaining else 'FAILED',
            'job_id': os.environ['SLURM_JOB_ID'], 'command': command, 'launch_identity': launch,
            'supervisor_cgroup': group, 'exit_code': code, 'first_failure': first_failure,
            'retirement': retirement, 'remaining': remaining, 'elapsed_seconds': time.monotonic()-start,
            'last_total_bytes': last_bytes, 'private_storage': private_final, 'sources_sha256': before,
            'gpu_initialization_permitted': False}
        args.record.write_text(json.dumps(report, indent=2)+'\n')
    return int(report['status'] != 'COMPLETED')


if __name__ == '__main__':
    raise SystemExit(main())
