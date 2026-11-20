"""Consume closed per-seed scores; do not adopt deletions or freeze a recipe."""
import json

from conditional_seed import CANDIDATES
from configuration import make
from runtime import REPO, write
from s_statistics import cpu_only, paired
from seed0_decisions import scores


def confirm(first, second=None):
    if first['status'] == 'UNRESOLVED':
        return dict(status='UNRESOLVED', confirmed_WIN=False, reason=first['reason'])
    if first['status'] != 'COMPLETE':
        return dict(status='WAITING_SEED0', confirmed_WIN=False)
    if first['R3']['verdict'] != 'WIN':
        return dict(status='COMPLETE', confirmed_WIN=False, seed_results={'0': first})
    if second is None:
        return dict(status='WAITING_SEED1', confirmed_WIN=False, seed_results={'0': first})
    if second['status'] == 'UNRESOLVED':
        return dict(status='UNRESOLVED', confirmed_WIN=False, reason=second['reason'],
                    seed_results={'0': first, '1': second})
    if second['status'] != 'COMPLETE':
        return dict(status='WAITING_SEED1', confirmed_WIN=False, seed_results={'0': first})
    confirmed = second['R3']['verdict'] == 'WIN'
    result = dict(status='COMPLETE', confirmed_WIN=confirmed,
                  seed_results={'0': first, '1': second})
    if confirmed:
        result.update(mean_delta=(first['R3']['delta']+second['R3']['delta'])/2,
                      mean_R3=(first['candidate_R3']+second['candidate_R3'])/2)
    return result


def choose_noise(confirmed):
    arms = ('S-N1', 'S-N2')
    if any(confirmed.get(arm, {}).get('status') not in ('COMPLETE', 'UNRESOLVED')
           for arm in arms):
        return dict(status='WAITING_NOISE_CONFIRMATIONS', selected=None)
    winners = [arm for arm in arms if confirmed[arm]['confirmed_WIN']]
    if len(winners) < 2:
        return dict(status='COMPLETE', selected=winners[0] if winners else None)
    a, b = (confirmed[arm] for arm in arms)
    tau = max(.01, .05*max(a['mean_R3'], b['mean_R3']))
    difference = abs(a['mean_delta']-b['mean_delta'])
    selected = ('S-N1' if difference < tau else
                max(arms, key=lambda arm: confirmed[arm]['mean_delta']))
    return dict(status='COMPLETE', selected=selected, tau=tau,
                mean_delta_difference=difference,
                rule='difference<tau prefers N1;otherwise larger two-seed mean delta')


def comparison(candidate, baseline):
    return dict(status='COMPLETE', candidate_R3=candidate['R3']['mean_normalized_improvement'],
                **{readout: paired(candidate[readout], baseline[readout])
                   for readout in ('R3', 'R1')})


def collect():
    cpu_only()
    registration = json.loads((REPO/'configs/s_recipe/preregistration.json').read_text())
    if registration['status'] != 'FROZEN':
        raise ValueError('Confirmations require frozen scientific rules')
    seed0 = json.loads((REPO/'configs/s_recipe/seed0_decisions.json').read_text())
    first_baseline = scores(make('S-B0'))
    if first_baseline is None:
        return dict(status='WAITING_BASELINE_STATISTICS')
    baseline1 = None
    confirmations = {}
    for arm in CANDIDATES:
        first = seed0['arms'].get(arm, dict(status='WAITING_SEED0'))
        second = None
        if first['status'] == 'COMPLETE' and first['R3']['verdict'] == 'WIN':
            candidate0 = scores(make(arm))
            if candidate0 is None:
                raise ValueError('Closed seed0 decision lost its producer statistics')
            first = comparison(candidate0, first_baseline)
            if baseline1 is None:
                baseline1 = scores(make('S-B0', seed=1))
            candidate1 = scores(make(arm, seed=1))
            if baseline1 is not None and candidate1 is not None:
                second = comparison(candidate1, baseline1)
        confirmations[arm] = confirm(first, second)
    pending = [arm for arm, entry in confirmations.items()
               if entry['status'].startswith('WAITING')]
    result = dict(schema='S_RECIPE_TWO_SEED_CONFIRMATIONS_V1',
                  status='PENDING' if pending else 'COMPLETE', pending=pending,
                  arms=confirmations, noise_choice=choose_noise(confirmations),
                  deletion_adoption='Separate decision under the frozen deletion rule',
                  recipe_frozen=False, R1='report_only', CYP='report_only',
                  seed0_decisions=str(REPO/'configs/s_recipe/seed0_decisions.json'))
    write(REPO/'configs/s_recipe/confirmed_decisions.json', result)
    return result


if __name__ == '__main__':
    print(json.dumps(collect()), flush=True)
