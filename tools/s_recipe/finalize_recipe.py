"""Prepare the single conditional merge and freeze only completed S decisions."""
import argparse
import json
from pathlib import Path

from checkpoint_binding import validate_resume
from configuration import make
from confirmed_decisions import comparison, proposal
from runtime import REPO, write
from s_statistics import cpu_only
from seed0_decisions import scores


def select(seed0, confirmed, merge=None):
    if seed0['status'] != 'COMPLETE' or confirmed['status'] != 'COMPLETE':
        return dict(status='WAITING_ALL_DECISIONS')
    plan = proposal(confirmed['arms'])
    if not plan['ready']:
        return dict(status='WAITING_ALL_DECISIONS')
    components = plan['components']
    if not components:
        return dict(status='READY', recipe='S-B0', components=[])
    if len(components) == 1:
        return dict(status='READY', recipe=components[0], components=components)
    if merge is None or merge['status'] not in ('COMPLETE', 'UNRESOLVED'):
        return dict(status='WAITING_MERGE', components=components)
    if merge['status'] == 'COMPLETE' and merge['R3']['verdict'] == 'WIN':
        return dict(status='READY', recipe='S-M1', components=components, merge=merge)
    # The taskbook's single-arm delta is the registered seed0 comparison;
    # two-seed averaging is explicitly used only for N1/N2 mutual exclusion.
    best = max(components, key=lambda arm: confirmed['arms'][arm]['seed_results']['0']['R3']['delta'])
    return dict(status='READY', recipe=best, components=[best], merge=merge,
                fallback='largest adopted single seed0 R3 delta')


def save_configuration(path, c):
    if path.is_file():
        validate_resume(c, json.loads(path.read_text()))
    else:
        write(path, c)
    return str(path)


def prepare_merge():
    confirmed = json.loads((REPO/'configs/s_recipe/confirmed_decisions.json').read_text())
    plan = proposal(confirmed['arms'])
    if not plan['ready'] or not plan['merge_required']:
        return dict(status='NO_READY_MERGE', proposal=plan)
    directory = REPO/'configs/s_recipe/merge'
    directory.mkdir(parents=True, exist_ok=True)
    c = make('S-M1', components=plan['components'])
    path = save_configuration(directory/'S-M1.json', c)
    result = dict(status='PREPARED', configurations=[path], jobs_submitted=False, **plan)
    write(directory/'plan.json', result)
    return result


def freeze():
    seed0 = json.loads((REPO/'configs/s_recipe/seed0_decisions.json').read_text())
    confirmed = json.loads((REPO/'configs/s_recipe/confirmed_decisions.json').read_text())
    initial = select(seed0, confirmed)
    merge = None
    if initial['status'] == 'WAITING_MERGE':
        candidate = make('S-M1', components=initial['components'])
        actual = scores(candidate)
        baseline = scores(make('S-B0'))
        if actual is not None and baseline is not None:
            merge = comparison(actual, baseline)
        unresolved_path = REPO/'configs/s_recipe/unresolved.json'
        unresolved = json.loads(unresolved_path.read_text()) if unresolved_path.is_file() else {}
        if merge is None and 'S-M1' in unresolved:
            merge = dict(status='UNRESOLVED', reason=unresolved['S-M1'])
    selected = select(seed0, confirmed, merge)
    if selected['status'] != 'READY':
        return selected
    c = make(selected['recipe'], **({'components': selected['components']}
             if selected['recipe'] == 'S-M1' else {}))
    actual = scores(c)
    if actual is None:
        return dict(status='WAITING_SELECTED_PRODUCER_STATISTICS')
    best = dict(selected, schema='S_RECIPE_CURRENT_BEST_V1', status='FROZEN',
                seed=0, samples=3000000, run=c['run'], source_configuration=c,
                checkpoint=str(Path(c['output'])/'samples_3000000.pt'),
                scores=str(Path(c['output'])/'readout/scores.json'),
                predictions=str(Path(c['output'])/'readout/predictions.json'),
                decision_layer=6, decision_source='configs/s_recipe/confirmed_decisions.json')
    destination = REPO/'configs/s_recipe/CURRENT_BEST.json'
    if destination.is_file() and json.loads(destination.read_text()) != best:
        raise ValueError('S recipe already frozen differently;inspect before changing scientific decisions')
    write(destination, best)
    return best


def confirmation():
    best = json.loads((REPO/'configs/s_recipe/CURRENT_BEST.json').read_text())
    if best['status'] != 'FROZEN':
        raise ValueError('9M is prepared only after final recipe freeze')
    directory = REPO/'configs/s_recipe/confirmation'
    directory.mkdir(parents=True, exist_ok=True)
    configs = [make('S-B0', samples=9000000)]
    if best['recipe'] != 'S-B0':
        configs.append(make('S-final', samples=9000000, components=best['components']))
    paths = [save_configuration(directory/(c['arm']+'.json'), c) for c in configs]
    result = dict(status='PREPARED', configurations=paths, seed=0,
                  samples_per_run=9000000, fresh_random_initialization=True,
                  jobs_submitted=False, descriptive_geometry_9M=False)
    write(directory/'plan.json', result)
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--mode', choices=('prepare-merge', 'freeze', 'prepare-9M'), required=True)
    args = p.parse_args()
    cpu_only()
    if json.loads((REPO/'configs/s_recipe/preregistration.json').read_text())['status'] != 'FROZEN':
        raise ValueError('Scientific registration is not frozen')
    action = {'prepare-merge': prepare_merge, 'freeze': freeze, 'prepare-9M': confirmation}
    print(json.dumps(action[args.mode]()), flush=True)
