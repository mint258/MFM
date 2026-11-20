"""Consume the original producer statistics; never reread predictions or refit."""
import argparse
import json
from pathlib import Path

from configuration import make
from runtime import REPO, write
from s_statistics import cpu_only, paired

ARMS = ('S-N1', 'S-N2', 'S-R1', 'S-R2', 'S-G1')


def scores(c):
    summary = Path(c['output'])/'summary.json'
    if not summary.is_file():
        return None
    finished = json.loads(summary.read_text())
    if finished.get('status') != 'COMPLETE':
        return None
    if finished['samples'] != c['samples'] or finished['updates']*32 != c['samples']:
        raise ValueError('Producer has not completed the registered S sample/update budget')
    path = Path(c['output'])/'readout/scores.json'
    if not path.is_file():
        return None
    return json.loads(path.read_text())


def decide():
    cpu_only()
    baseline = make('S-B0')
    reference = scores(baseline)
    if reference is None:
        return dict(status='WAITING_BASELINE_STATISTICS')
    unresolved_file = REPO/'configs/s_recipe/unresolved.json'
    unresolved = json.loads(unresolved_file.read_text()) if unresolved_file.is_file() else {}
    decisions, pending = {}, []
    for arm in ARMS:
        candidate = make(arm)
        actual = scores(candidate)
        if actual is None:
            if arm in unresolved:
                decisions[arm] = dict(status='UNRESOLVED', reason=unresolved[arm], adopted=False)
            else:
                pending.append(arm)
            continue
        decisions[arm] = dict(status='COMPLETE', configuration=candidate['run'],
            descriptive_only=arm == 'S-G1',
            **{readout: paired(actual[readout], reference[readout]) for readout in ('R3', 'R1')})
    triggers = [arm for arm, value in decisions.items() if arm != 'S-G1' and value['status'] == 'COMPLETE'
                and value['R3']['verdict'] == 'WIN']
    result = dict(schema='S_RECIPE_SEED0_DECISIONS_V1', status='PENDING' if pending else 'COMPLETE',
                  arms=decisions, pending=pending, seed1_candidates=triggers,
                  seed1_baseline_required=bool(triggers), R1='report_only', CYP='report_only')
    write(REPO/'configs/s_recipe/seed0_decisions.json', result)
    return result


if __name__ == '__main__':
    print(json.dumps(decide()), flush=True)
