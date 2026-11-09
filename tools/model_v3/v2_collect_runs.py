"""Refresh one-row-per-training summaries from actual producer logs and Slurm."""
import argparse
import csv
import json
from pathlib import Path
import subprocess

FIELDS = ('run_id', 'stage', 'condition', 'candidate', 'views', 'seed', 'molecules',
          'samples', 'updates', 'gpu_model', 'elapsed_seconds', 'throughput_molecules_s',
          'peak_memory_bytes', 'dev_score', 'status', 'slurm_job_id')


def last_training_row(path):
    if not path.exists():
        return {}
    with path.open('rb') as stream:
        header = next(csv.reader([stream.readline().decode().strip()]))
        stream.seek(0, 2)
        length = stream.tell()
        stream.seek(max(0, length - 8192))
        data = stream.read().decode()
        lines = data.splitlines()
        if data and not data.endswith('\n'):
            lines = lines[:-1]
    if not lines or lines[-1].startswith(('samples,', 'updates,')):
        return {}
    values = lines[-1].split(',')
    if len(values) != len(header):
        return {}
    values = dict(zip(header, values))
    return dict(samples=int(values['samples']), updates=int(values['updates']), seconds=float(values['seconds']))


def collect_run(root, *, name, job, gpu, state, stage=None):
    root = Path(root)
    def read(suffix):
        path = root/suffix
        return json.loads(path.read_text()) if path.exists() else {}
    config, summary, dev, execution = (read(suffix) for suffix in
        ('configuration.json', 'summary.json', 'dev_eval/summary.json', 'execution.json'))
    if stage is not None and config.get('stage', stage) != stage:
        raise ValueError('Explicit stage conflicts with the original experiment configuration')
    actual_stage = stage if stage is not None else config.get('stage', 2 if 'mode' in config else 5)
    progress = last_training_row(root/'losses.csv')
    initial_samples, initial_updates = execution.get('initial_samples', 0), execution.get('initial_updates', 0)
    prior_seconds = execution.get('elapsed_seconds_prior', 0.)
    logical_samples = summary.get('samples', progress.get('samples', summary.get('actual_samples', initial_samples)))
    logical_updates = summary.get('updates', progress.get('updates', summary.get('actual_updates', initial_updates)))
    samples = summary.get('actual_samples', logical_samples-initial_samples)
    updates = summary.get('actual_updates', logical_updates-initial_updates)
    total_seconds = summary.get('seconds', progress.get('seconds', ''))
    seconds = summary.get('actual_seconds', total_seconds-prior_seconds if total_seconds != '' else '')
    if min(samples, updates) < 0 or (seconds != '' and seconds < 0):
        raise ValueError('Observed progress predates this execution segment')
    phase = summary.get('status')
    return dict(run_id=name, stage=actual_stage,
        condition=config.get('condition', 'SDP' if config.get('mode') == 'sdp' else 'PD' if config.get('mode') == 'overfit' else 'S'),
        candidate=config.get('candidate', config.get('distance_bias', '')),
        views=config.get('views', ''), seed=config.get('seed', ''),
        molecules=config.get('TRAIN_molecules', config.get('overfit_molecules', config.get('expected_molecules', ''))),
        samples=samples, updates=updates, gpu_model=gpu if progress else '', elapsed_seconds=seconds,
        throughput_molecules_s=samples/seconds if seconds else '',
        peak_memory_bytes=summary.get('gpu_peak_bytes', ''),
        dev_score=dev.get('mean_normalized_improvement', '')
            if dev.get('complete') and dev.get('consumed_samples') == logical_samples else '',
        status=state if phase is None else state+':'+phase, slurm_job_id=job)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--stage', type=int, help='Actual queue stage when the producer config omits it')
    parser.add_argument('--run', action='append', required=True, help='directory,SlurmID,GPUmodel')
    args = parser.parse_args()
    runs = [value.split(',') for value in args.run]
    query = subprocess.run(['sacct', '-j', ','.join(row[1] for row in runs),
        '--format=JobIDRaw,State', '-n', '-P'], capture_output=True, text=True, check=True)
    states = dict(line.split('|')[:2] for line in query.stdout.splitlines() if line.strip())
    rows = []
    for name, job, gpu in runs:
        rows.append(collect_run(Path(args.root)/name, name=name,job=job,gpu=gpu,
                                state=states.get(job,'UNKNOWN'),stage=args.stage))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == '__main__':
    main()
