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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--run', action='append', required=True, help='directory,SlurmID,GPUmodel')
    args = parser.parse_args()
    runs = [value.split(',') for value in args.run]
    query = subprocess.run(['sacct', '-j', ','.join(row[1] for row in runs),
        '--format=JobIDRaw,State', '-n', '-P'], capture_output=True, text=True, check=True)
    states = dict(line.split('|')[:2] for line in query.stdout.splitlines() if line.strip())
    rows = []
    for name, job, gpu in runs:
        root = Path(args.root) / name
        config = json.loads((root / 'configuration.json').read_text()) if (root / 'configuration.json').exists() else {}
        summary = json.loads((root / 'summary.json').read_text()) if (root / 'summary.json').exists() else {}
        dev = json.loads((root/'dev_eval/summary.json').read_text()) if (root/'dev_eval/summary.json').exists() else {}
        progress = last_training_row(root / 'losses.csv')
        samples = summary.get('actual_samples', summary.get('samples', progress.get('samples', 0)))
        seconds = summary.get('seconds', progress.get('seconds', ''))
        state = states.get(job, 'UNKNOWN')
        phase = summary.get('status')
        rows.append(dict(run_id=name, stage=config.get('stage', 2 if 'mode' in config else 5),
            condition=config.get('condition', 'SDP' if config.get('mode') == 'sdp' else 'PD' if config.get('mode') == 'overfit' else 'S'),
            candidate=config.get('candidate', config.get('distance_bias', '')),
            views=config.get('views', ''), seed=config.get('seed', ''),
            molecules=config.get('TRAIN_molecules', config.get('overfit_molecules', config.get('expected_molecules', ''))),
            samples=samples, updates=summary.get('actual_updates', summary.get('updates', progress.get('updates', 0))),
            gpu_model=gpu if progress else '', elapsed_seconds=seconds,
            throughput_molecules_s=samples / seconds if seconds else '',
            peak_memory_bytes=summary.get('gpu_peak_bytes', ''),
            dev_score=dev.get('mean_normalized_improvement', '') if dev.get('complete') and dev.get('consumed_samples') == samples else '',
            status=state if phase is None else state + ':' + phase, slurm_job_id=job))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == '__main__':
    main()
