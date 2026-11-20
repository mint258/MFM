"""Prepare only seed0-WIN confirmations and their one shared S-B0 seed1."""
import argparse
import json
from pathlib import Path

from checkpoint_binding import validate_resume
from configuration import make
from runtime import CONTROL, REPO, capacity, write

CANDIDATES = ('S-N1', 'S-N2', 'S-R1', 'S-R2')


def candidates(decisions):
    return [arm for arm in CANDIDATES if decisions.get(arm, {}).get('status') == 'COMPLETE'
            and decisions[arm]['R3']['verdict'] == 'WIN']


def prepare(decisions, directory):
    selected = candidates(decisions)
    paths = []
    for arm in (['S-B0']+selected if selected else []):
        c = make(arm, seed=1, samples=3000000)
        path = Path(directory)/(arm+'.json')
        if path.is_file():
            validate_resume(c, json.loads(path.read_text()))
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            write(path, c)
        paths.append(str(path))
    return dict(schema='S_RECIPE_CONDITIONAL_SEED1_PLAN_V1', configurations=paths,
                candidates=selected, shared_baseline='S-B0' if selected else None,
                samples_per_run=3000000, seed=1, jobs_submitted=False)


def reference(configuration):
    c = configuration
    if (c['arm'], c['seed'], c['samples']) != ('S-B0', 1, 3000000):
        raise ValueError('Only the shared3M S-B0 seed1 can be a reference')
    output = Path(c['output'])
    summary = json.loads((output/'summary.json').read_text())
    if (summary['status'] != 'COMPLETE' or summary['samples'] != 3000000
            or summary['updates'] != 93750):
        raise ValueError('Shared reference training and original readouts are not complete')
    checkpoint = output/'samples_3000000.pt'
    if not checkpoint.is_file():
        raise ValueError('Shared reference complete checkpoint is missing')
    return dict(schema='S_RECIPE_B0_SEED1_REFERENCE_V1', status='COMPLETE', run=c['run'],
        seed=1, samples=3000000, checkpoint=str(checkpoint),
        scores=str(output/'readout/scores.json'), predictions=str(output/'readout/predictions.json'),
        initialization=c['initialization'], population=c['population'],
        reuse='All seed1 candidates reuse this single S-B0 model;no third seed')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument('--prepare', action='store_true')
    mode.add_argument('--publish-reference-configuration', type=Path)
    p.add_argument('--make-initialization', action='store_true')
    args = p.parse_args()
    from s_statistics import cpu_only
    cpu_only()
    registration = json.loads((REPO/'configs/s_recipe/preregistration.json').read_text())
    if registration['status'] != 'FROZEN':
        raise ValueError('Conditional confirmations require frozen scientific rules')
    if args.prepare:
        decisions = json.loads((REPO/'configs/s_recipe/seed0_decisions.json').read_text())['arms']
        plan = prepare(decisions, REPO/'configs/s_recipe/seed1')
        if args.make_initialization and plan['candidates']:
            initialization = CONTROL/'initialization_seed1.pt'
            if not initialization.is_file():
                from make_initialization import make_initialization
                capacity()
                make_initialization(1, initialization)
        write(REPO/'configs/s_recipe/seed1_plan.json', plan)
        result = plan
    else:
        c = json.loads(args.publish_reference_configuration.read_text())
        result = reference(c)
        destination = REPO/'configs/s_recipe/S_B0_SEED1_REFERENCE.json'
        if destination.is_file() and json.loads(destination.read_text()) != result:
            raise ValueError('Shared seed1 reference already identifies a different producer')
        write(destination, result)
    print(json.dumps(result), flush=True)
