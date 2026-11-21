"""Select the user's four-arm 3M calibration and export the new study base.

This consumes existing scores only; it never schedules extra readout evaluations.
"""
import argparse
from copy import deepcopy
import json
import math
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def choose(groups, observations=None):
    if len(groups) != 4:
        raise ValueError('All four registered calibration groups are required')
    for group in groups:
        if group['samples'] != 3000000 or group['state'] != 'COMPLETED':
            raise ValueError('Each calibration must complete 3M and both registered readouts')
        if not all(math.isfinite(group[key]) for key in ('R1', 'R3')):
            raise ValueError('Calibration readouts must be finite')
    # Exact ties keep the registered order; throughput does not enter selection.
    winner = max(groups, key=lambda group: group['R3'])
    seen = observations if observations is not None else winner['observations']
    by_sample = {}
    for row in seen:
        if row['run'] != winner['run']:
            raise ValueError('Budget observations must belong to the winning run')
        sample, score = row['samples'], row['R3']
        if not isinstance(sample, int) or not 0 < sample <= 3000000 or not math.isfinite(score):
            raise ValueError('Invalid budget observation')
        if sample in by_sample and by_sample[sample] != score:
            raise ValueError('Conflicting scores at one sample checkpoint')
        by_sample[sample] = score
    if by_sample.get(3000000) != winner['R3']:
        raise ValueError('Budget observations must include the winning 3M score')
    reached = [sample for sample, score in by_sample.items() if score >= .30]
    first = min(reached) if reached else None
    budget = ((first + 499999) // 500000) * 500000 if first else 3000000
    return dict(winner_run=winner['run'], winner_group=winner['arm'],
                batch_size=winner['batch_size'], lr=winner['lr'],
                activation_checkpointing=winner['activation_checkpointing'],
                R3_at_3M=winner['R3'], first_observed_R3_ge_030_samples=first,
                screening_samples=budget,
                budget_observations=[dict(run=winner['run'], samples=sample, R3=by_sample[sample])
                                     for sample in sorted(by_sample)],
                groups=[{key: group[key] for key in ('run', 'arm', 'batch_size', 'lr', 'R1', 'R3')}
                        for group in groups])


def selected_base(base, selection, protocol):
    result = deepcopy(base)
    result.update({key: selection[key] for key in ('batch_size', 'lr', 'activation_checkpointing', 'screening_samples')})
    result.update(protocol['rescreening'])
    result['microbatch_size'] = result['batch_size']
    result['samples'] = result['screening_samples']
    result['run'] = result['run_prefix'] + 'base'
    result['output'] = str(Path(base['output']).parent / result['study_revision'] / result['run'])
    result['clip_calibration'] = dict(fraction=.05, initial_clip=281.7, quantile=.99)
    result['clip_reference'] = str(REPO / 'configs/p_recipe/calibration_20261114/initial_clip.json')
    result['calibration_selection_run'] = selection['winner_run']
    for key in ('base_configuration', 'study_directory', 'gpu_hours_source'):
        result.pop(key, None)
    return result


def read(path):
    return json.loads(Path(path).read_text())


def completed_groups(plan, ledger):
    groups = []
    for path in plan['configurations']:
        config = read(path)
        record = ledger['runs'][config['run']]
        output = Path(config['output'])
        summary = read(output / 'summary.json')
        if record['state'] != 'COMPLETED' or summary.get('status') != 'COMPLETE':
            raise ValueError('All four calibration processes must finish successfully')
        observations = []
        for samples in (1500000, 3000000):
            scores = read(output / ('readout' if samples == 3000000 else 'readout_1500000') / 'scores.json')
            observations.append(dict(run=config['run'], samples=samples,
                                     R3=scores['R3']['mean_normalized_improvement']))
        groups.append(dict(config, state=record['state'],
                           R1=scores['R1']['mean_normalized_improvement'],
                           R3=scores['R3']['mean_normalized_improvement'], observations=observations))
    return groups


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', required=True)
    parser.add_argument('--ledger', required=True)
    parser.add_argument('--protocol', required=True)
    parser.add_argument('--base', required=True)
    parser.add_argument('--budget-observations', help='Existing winner-only observations; no evaluations are launched')
    parser.add_argument('--base-output', required=True)
    parser.add_argument('--selection-output', required=True)
    args = parser.parse_args()
    groups = completed_groups(read(args.plan), read(args.ledger))
    selection = choose(groups, read(args.budget_observations) if args.budget_observations else None)
    selection['observation_source'] = args.budget_observations or 'registered_1.5M_and_3M_only'
    base = selected_base(read(args.base), selection, read(args.protocol))
    for destination, value in ((args.base_output, base), (args.selection_output, selection)):
        path = Path(destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=2) + '\n')
    print(json.dumps(selection), flush=True)


if __name__ == '__main__':
    main()
