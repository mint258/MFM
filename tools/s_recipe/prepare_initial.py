"""Prepare the six authorized seed0 configs, without training or dispatch."""
import json
from pathlib import Path

from checkpoint_binding import validate_resume
from configuration import make
from runtime import REPO, capacity, write

ARMS = ('S-B0', 'S-N1', 'S-N2', 'S-R1', 'S-R2', 'S-G1')


def prepare(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    paths = []
    for arm in ARMS:
        c = make(arm, seed=0, samples=3000000)
        path = directory/(arm+'.json')
        if path.is_file():
            # Re-entry preserves any existing execution/handoff metadata.
            validate_resume(c, json.loads(path.read_text()))
        else:
            write(path, c)
        paths.append(str(path))
    plan = dict(schema='S_RECIPE_INITIAL_SCREENING_V1', configurations=paths,
        arms=list(ARMS), seed=0, samples_per_run=3000000, total_samples=18000000,
        status='PREPARED_WAITING_FOR_PREREGISTRATION_FREEZE_AND_P_GATE',
        training_executed=False, jobs_submitted=False,
        priority=list(ARMS))
    write(directory/'plan.json', plan)
    return plan


if __name__ == '__main__':
    capacity()
    print(json.dumps(prepare(REPO/'configs/s_recipe/screening')), flush=True)
