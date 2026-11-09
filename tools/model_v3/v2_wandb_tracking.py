"""Tail actual model-window CSVs into persistent W&B runs and 100k snapshots.

One run per actual Slurm execution preserves replayed work as separate history.
The JSON manifest is append-only across checkpoint continuations. No model or
optimizer code, dataset access, weights upload, or GitHub credentials live here.
The root coordinator publishes only snapshots/*.json to the model-v3 branch.
"""
from __future__ import annotations

import argparse
import csv
import fcntl
import io
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time

CADENCE = 100_000
TERMINAL = {'COMPLETED', 'CANCELLED', 'FAILED', 'TIMEOUT', 'OUT_OF_MEMORY', 'NODE_FAIL', 'PREEMPTED'}
LOSS_KEYS = {'total', 'S', 'D', 'P', 'element', 'noise', 'bond'}
ROW_KEYS = LOSS_KEYS | {'samples', 'updates', 'preclip_norm', 'lr', 'seconds'}


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_suffix(path.suffix + '.next')
    pending.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    pending.replace(path)


class CsvTail:
    """Advance only over newline-closed producer records, including on restart."""
    def __init__(self, path):
        self.path, self.offset, self.fields = Path(path), 0, None

    def rows(self):
        if not self.path.exists():
            return
        with self.path.open('rb') as stream:
            stream.seek(self.offset)
            while True:
                before = stream.tell()
                raw = stream.readline()
                if not raw.endswith(b'\n'):
                    self.offset = before
                    break
                self.offset = stream.tell()
                values = next(csv.reader(io.StringIO(raw.decode('utf-8'))))
                if self.fields is None:
                    self.fields = values
                    continue
                if len(values) != len(self.fields):
                    raise ValueError('A closed CSV record has inconsistent columns')
                row = {}
                for key, value in zip(self.fields, values):
                    if key not in ROW_KEYS or not value:
                        continue
                    number = float(value)
                    if not math.isfinite(number):
                        continue
                    row[key] = int(number) if key in {'samples', 'updates'} else number
                if 'samples' not in row or 'updates' not in row:
                    raise ValueError('Training CSV lacks its actual sample/update clock')
                yield row


def boundaries(previous, current):
    if current < previous:
        raise ValueError('A single execution cannot rewind its scientific clock')
    return list(range((previous // CADENCE + 1) * CADENCE, current + 1, CADENCE))


def metrics(row, initial_samples, initial_seconds, imported):
    result = {'samples/cumulative': row['samples'],
        'samples/execution': row['samples'] - initial_samples,
        'optimizer/updates': row['updates'], 'history/imported': bool(imported)}
    for key in LOSS_KEYS & row.keys():
        result['loss/' + key] = row[key]
    for source, target in [('lr', 'optimizer/lr'), ('preclip_norm', 'optimizer/preclip_norm'),
                           ('seconds', 'time/cumulative_seconds')]:
        if source in row:
            result[target] = row[source]
    elapsed = row.get('seconds', initial_seconds) - initial_seconds
    if elapsed > 0:
        result['time/execution_seconds'] = elapsed
        result['time/samples_per_second'] = (row['samples'] - initial_samples) / elapsed
    return result


def job_state(entry):
    if entry.get('terminal_state') in TERMINAL:
        return entry['terminal_state']
    result = subprocess.run(['scontrol', 'show', 'job', str(entry['job']), '-o'],
        capture_output=True, text=True)
    for word in result.stdout.split():
        if word.startswith('JobState='):
            return word.split('=', 1)[1]
    # Missing observations are not evidence of completion.
    return 'UNKNOWN'


def register(manifest_path, configuration_path, *, job, node, gpu, mode):
    """Register real future launches under one lock, never replace old entries."""
    manifest_path = Path(manifest_path)
    configuration = json.loads(Path(configuration_path).read_text())
    with manifest_path.with_suffix('.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        manifest = json.loads(manifest_path.read_text())
        if any(row['job'] == job for row in manifest['runs']):
            return
        repo = Path(__file__).absolute().parents[2]
        head = (repo / '.git/HEAD').read_text().strip()
        revision = (repo / '.git' / head[5:]).read_text().strip() if head.startswith('ref: ') else head
        candidate = configuration.get('distance_bias', '')
        condition = configuration.get('condition', 'S' if mode == 'native_s' else '')
        manifest['runs'].append(dict(job=job, output=configuration['output'],
            name=Path(configuration['output']).name,
            group='stage' + str(configuration.get('stage', 'unspecified')) + '_' + condition + '_' + candidate +
                '_seed' + str(configuration.get('seed', 0)),
            node=node, gpu=gpu, source_revision=revision))
        save(manifest_path, manifest)


def export_snapshots(manifest):
    root = Path(manifest['tracking_root'])
    records = [json.loads(path.read_text()) for path in sorted(root.glob('*/snapshots/*.json'))]
    save(manifest['publication_pending'], dict(schema='MODEL_V2_WANDB_PUBLICATION_V1',
        cadence_samples=CADENCE, status='OFFLINE_UNSYNCED' if manifest.get('mode') == 'offline'
            else 'ONLINE_UPLOAD_REQUESTED_CLOUD_VISIBILITY_REQUIRES_CONFIRMATION',
        records=records))


def worker(manifest_path, job):
    manifest = json.loads(Path(manifest_path).read_text())
    entry = next(row for row in manifest['runs'] if row['job'] == job)
    output = Path(entry['output'])
    directory = Path(manifest['tracking_root']) / str(job)
    directory.mkdir(parents=True, exist_ok=True)
    for name, sub in [('WANDB_DIR', '.'), ('WANDB_CACHE_DIR', 'cache'),
                      ('WANDB_DATA_DIR', 'data'), ('TMPDIR', 'tmp')]:
        path = directory / sub
        path.mkdir(exist_ok=True)
        os.environ[name] = str(path)
    os.environ['WANDB_CONSOLE'] = 'off'
    import wandb
    configuration = json.loads((output / 'configuration.json').read_text())
    execution_path = output / 'execution.json'
    execution = json.loads(execution_path.read_text()) if execution_path.exists() else {}
    initial = int(execution.get('initial_samples', entry.get('initial_samples', 0)))
    prior_seconds = float(execution.get('elapsed_seconds_prior', entry.get('initial_seconds', 0)))
    state_path = directory / 'tracking.json'
    saved = json.loads(state_path.read_text()) if state_path.exists() else {}
    if saved.get('finished'):
        return
    run_id = saved.get('run_id', 'm3-' + str(job))
    mode = saved.get('mode', manifest.get('mode', 'online'))
    kwargs = dict(project=manifest['project'], entity=manifest.get('entity'),
        id=run_id, name=entry['name'] + '-job' + str(job), group=entry['group'],
        job_type='actual-training-csv', dir=str(directory), mode=mode,
        config={'scientific_configuration': configuration, 'execution': execution,
                'slurm_job_id': job, 'training_node': entry['node'], 'gpu_uuid': entry['gpu'],
                'source_revision': entry['source_revision'], 'restore_checkpoint': configuration.get('resume'),
                'history_origin': 'Actual producer CSV; earlier rows imported at attachment',
                'sample_cadence': CADENCE, 'weights_uploaded': False},
        settings=wandb.Settings(init_timeout=30))
    if mode == 'online':
        kwargs['resume'] = 'allow'
    init_error = None
    try:
        run = wandb.init(**kwargs)
    except Exception as exc:
        init_error = type(exc).__name__
        mode = 'offline'
        kwargs.update(mode=mode)
        kwargs.pop('resume', None)
        run = wandb.init(**kwargs)
    if run is None or run.disabled:
        raise RuntimeError('A real persistent W&B run is required')
    last = int(saved.get('last_samples', initial))
    attached = max((r['samples'] for r in CsvTail(output / 'losses.csv').rows()), default=initial)
    status = dict(run_id=run.id, mode=mode, url=run.url if mode == 'online' else None,
        project=manifest['project'], entity=manifest.get('entity'), job=job,
        last_samples=last, initial_samples=initial, attachment_samples=attached,
        init_error_type=init_error, finished=False,
        synchronization='ONLINE_UPLOAD_REQUESTED' if mode == 'online' else 'OFFLINE_UNSYNCED')
    save(state_path, status)
    tail = CsvTail(output / 'losses.csv')
    try:
        while True:
            # Parent controller may publish the actual terminal state later.
            current_manifest = json.loads(Path(manifest_path).read_text())
            current_entry = next(r for r in current_manifest['runs'] if r['job'] == job)
            for row in tail.rows():
                samples = row['samples']
                if samples <= last:
                    continue
                payload = metrics(row, initial, prior_seconds, samples <= attached)
                run.log(payload, step=samples, commit=True)
                for boundary in boundaries(last, samples):
                    snapshot = dict(schema='MODEL_V2_WANDB_100K_V1', job=job,
                        name=entry['name'], group=entry['group'], boundary_samples=boundary,
                        actual_samples=samples, execution_samples=samples-initial,
                        updates=row['updates'], metrics=payload, wandb_run_id=run.id,
                        wandb_url=status['url'], synchronization=status['synchronization'],
                        imported_history=samples <= attached, output=str(output),
                        restore_checkpoint=configuration.get('resume'), source_revision=entry['source_revision'])
                    path = directory / 'snapshots' / (str(boundary) + '.json')
                    save(path, snapshot)
                    run.summary['last_100k_boundary'] = boundary
                    run.summary['actual_samples'] = samples
                    run.save(str(path), base_path=str(directory), policy='now')
                last = samples
                status.update(last_samples=last, observed_at=time.time())
                # Durable cursor at every 100k and every controller poll. SDK
                # owns its full persistent stream; cursor is not cloud proof.
            save(state_path, status)
            actual_state = job_state(current_entry)
            if actual_state in TERMINAL:
                run.summary['slurm_state'] = actual_state
                run.summary['actual_samples'] = last
                summary_path = output / 'summary.json'
                if summary_path.exists():
                    for key, value in json.loads(summary_path.read_text()).items():
                        if isinstance(value, (int, float)) and math.isfinite(value):
                            run.summary['final/' + key] = value
                run.summary['checkpoint_reference'] = str(output / ('samples_' + str(last) + '.pt')) if (
                    output / ('samples_' + str(last) + '.pt')).exists() else str(output / 'recovery.pt')
                run.finish(exit_code=0 if actual_state == 'COMPLETED' else 1)
                status.update(finished=True, slurm_state=actual_state, observed_at=time.time())
                save(state_path, status)
                return
            time.sleep(10)
    except BaseException:
        run.finish(exit_code=1)
        raise


def supervise(manifest_path):
    children = {}
    root = Path(json.loads(Path(manifest_path).read_text())['tracking_root'])
    root.mkdir(parents=True, exist_ok=True)
    while True:
        manifest = json.loads(Path(manifest_path).read_text())
        for entry in manifest['runs']:
            job = entry['job']
            state = root / str(job) / 'tracking.json'
            if state.exists() and json.loads(state.read_text()).get('finished'):
                continue
            child = children.get(job)
            if child is not None and child.poll() is None:
                continue
            if not (Path(entry['output']) / 'configuration.json').exists():
                continue
            log = (root / ('worker_' + str(job) + '.log')).open('a')
            children[job] = subprocess.Popen([sys.executable, '-B', __file__, '--manifest',
                str(manifest_path), '--job', str(job)], stdout=log, stderr=subprocess.STDOUT)
            log.close()
        export_snapshots(manifest)
        time.sleep(15)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--job', type=int)
    parser.add_argument('--register-configuration', type=Path)
    parser.add_argument('--training-mode', choices=('v31', 'native_s'))
    parser.add_argument('--node')
    parser.add_argument('--gpu')
    parser.add_argument('--export-only', action='store_true')
    args = parser.parse_args()
    if args.export_only:
        export_snapshots(json.loads(args.manifest.read_text()))
    elif args.register_configuration:
        if not all((args.job, args.node, args.gpu, args.training_mode)):
            parser.error('Real job, node, GPU and training mode are required for registration')
        register(args.manifest, args.register_configuration, job=args.job,
            node=args.node, gpu=args.gpu, mode=args.training_mode)
    elif args.job is None:
        supervise(args.manifest)
    else:
        worker(args.manifest, args.job)


if __name__ == '__main__':
    main()
