"""Existing R1/R3 bootstrap and S paired decisions on CPU nodes only."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import socket
import resource
import time

import numpy as np
from runtime import REPO, capacity, write


def cpu_only():
    if socket.gethostname().split('.')[0] not in {'compute-0-'+str(i) for i in range(8, 20)}:
        raise RuntimeError('S statistics must execute on CPU8..19')
    if os.environ.get('CUDA_VISIBLE_DEVICES'):
        raise RuntimeError('CUDA must be hidden for CPU statistics')
    memory = {line.split(':', 1)[0]: int(line.split()[1])*1024
              for line in Path('/proc/meminfo').read_text().splitlines()
              if line.startswith(('MemTotal:', 'MemAvailable:'))}
    capacity()
    return memory


def finalize(c, *, execution=None):
    memory = cpu_only()
    output = Path(c['output'])
    summary = json.loads((output/'summary.json').read_text())
    if summary['status'] == 'COMPLETE':
        return summary
    if summary['status'] != 'GPU_READOUT_COMPLETE_WAITING_CPU_STATISTICS' or summary['samples'] != c['samples']:
        raise ValueError('GPU readouts have not completed the registered budget')
    spec = importlib.util.spec_from_file_location('existing_p_evaluate', REPO/'tools/p_recipe/evaluate.py')
    evaluate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(evaluate)
    started = time.monotonic()
    for samples in c['evaluation_samples']:
        directory = output/('readout' if samples == c['samples'] else 'readout_'+str(samples))
        destination = directory/'scores.json'
        if destination.is_file():
            statistics = json.loads(destination.read_text())
        else:
            capacity()
            from readouts import finish_cpu_ridge
            finish_cpu_ridge(c, samples)
            manifest = json.loads((directory/'predictions.json').read_text())
            if manifest['run'] != c['run'] or manifest['samples'] != samples:
                raise ValueError('Readout producer run/sample mismatch')
            statistics = evaluate.score(directory/'predictions.json', c['reference_manifest'], REPO/'results/s_recipe/scores.csv')
        if not all(statistics[key]['complete'] and
                   statistics[key]['bootstrap_samples'] == statistics[key]['bootstrap_defined'] == 1000
                   for key in ('R1', 'R3')):
            raise ValueError('Original R1/R3 bootstrap is incomplete; preserve its producer artifacts')
        if set(statistics['R3']['tasks']) != set(evaluate.PRIMARY_TASK_IDS):
            raise ValueError('S primary score requires the frozen seven-task R3 panel')
    from readouts import release_closed_feature_cache
    released = release_closed_feature_cache(c)
    summary.update(status='COMPLETE', statistics_complete=True, feature_cache=released,
                   statistics_job=os.environ['SLURM_JOB_ID'] if execution is None else execution['job_id'],
                   statistics_node=socket.gethostname().split('.')[0],
                   statistics_memory_at_start=memory,
                   statistics_peak_RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
                   statistics_seconds=time.monotonic()-started)
    if execution is not None:
        summary['statistics_execution'] = execution
    write(output/'summary.json', summary)
    return summary


def paired(candidate, baseline):
    """Use the producer's common molecule draws without another bootstrap."""
    a, b = candidate, baseline
    if not all(v['complete'] and v['bootstrap_defined'] == v['bootstrap_samples'] == 1000
               for v in (a, b)):
        raise ValueError('Complete1000-draw producer statistics required')
    for key in ('groups', 'seed', 'samples', 'confidence'):
        if a['paired_bootstrap'][key] != b['paired_bootstrap'][key]:
            raise ValueError('Bootstrap samples are not paired by molecule')
    if set(a['tasks']) != set(b['tasks']):
        raise ValueError('Primary task sets differ')
    delta = a['mean_normalized_improvement']-b['mean_normalized_improvement']
    draws = np.asarray(a['paired_bootstrap']['values'])-np.asarray(b['paired_bootstrap']['values'])
    lower, upper = map(float, np.quantile(draws, [.025, .975]))
    tau = max(.01, .05*max(a['mean_normalized_improvement'], b['mean_normalized_improvement']))
    verdict = 'WIN' if lower > 0 and delta >= tau else 'LOSS' if upper < 0 else 'TIE'
    return dict(delta=delta, ci_lower=lower, ci_upper=upper, tau=tau, verdict=verdict)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--configuration', type=Path, required=True)
    print(json.dumps(finalize(json.loads(p.parse_args().configuration.read_text()))), flush=True)
