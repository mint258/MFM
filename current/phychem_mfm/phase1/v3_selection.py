"""User2026-11-10 paired single-seed decisions; original v2 rules stay historical."""
from __future__ import annotations

import math
import numpy as np


def paired_difference(a, b, *, expected_task_count=9):
    """Condition-keyed complete primary panels from the existing common-draw bootstrap.

    Indexed draws, not separately estimated confidence-interval endpoints, are
    differenced. The same molecule groups/seed/order are required in every
    condition and candidate, so a draw remains paired across the whole decision.
    """
    if set(a)!=set(b) or not a:
        raise ValueError('The same complete compared conditions are required')
    conditions = sorted(a)
    exemplar = a[conditions[0]]['paired_bootstrap']
    if exemplar['samples']!=1000 or exemplar['seed']!=20261025 or exemplar['confidence']!=.95:
        raise ValueError('Taskbook-v3 fixed molecule bootstrap is required')
    for panels in (a,b):
        for condition in conditions:
            value = panels[condition]
            boot = value['paired_bootstrap']
            if (not value['complete'] or len(value['tasks'])!=expected_task_count or len(boot['values'])!=1000 or
                    boot['groups']!=exemplar['groups'] or
                    any(boot[k]!=exemplar[k] for k in ('samples','seed','confidence'))):
                raise ValueError('Primary panels must share the exact molecule-group draws')
    score_a = float(np.mean([a[c]['mean_normalized_improvement'] for c in conditions]))
    score_b = float(np.mean([b[c]['mean_normalized_improvement'] for c in conditions]))
    if not math.isfinite(score_a) or not math.isfinite(score_b):
        raise ValueError('Finite complete primary scores required')
    delta = score_a-score_b
    draws = []
    for i in range(1000):
        av = [a[c]['paired_bootstrap']['values'][i] for c in conditions]
        bv = [b[c]['paired_bootstrap']['values'][i] for c in conditions]
        if all(v is not None for v in av+bv):
            draws.append(float(np.mean(av)-np.mean(bv)))
    if not draws:
        raise ValueError('No defined paired bootstrap difference')
    low,high = map(float,np.quantile(draws,[.025,.975]))
    threshold = max(.01,.05*max(score_a,score_b))
    a_wins = low>0 and delta>=threshold
    b_wins = high<0 and -delta>=threshold
    return dict(score_A=score_a,score_B=score_b,delta=delta,ci95=[low,high],
        effect_threshold=threshold,A_wins=a_wins,B_wins=b_wins,tied=not(a_wins or b_wins),
        bootstrap_samples=1000,bootstrap_defined=len(draws),bootstrap_seed=20261025,
        conditions=conditions,aggregation='equal_task_means_then_equal_condition_means')


def select_candidate(panels, simplicity_order):
    if len(panels)<2 or not set(panels)<=set(simplicity_order):
        raise ValueError('At least two declared candidates required')
    rank = {name:i for i,name in enumerate(simplicity_order)}
    conditions = set(next(iter(panels.values())))
    if not conditions or any(set(v)!=conditions or
            any(not p['complete'] or len(p['tasks'])!=9 for p in v.values())
            for v in panels.values()):
        raise ValueError('Rank only complete nine-task results in every compared condition')
    scores = {name:float(np.mean([v['mean_normalized_improvement'] for v in conditions.values()]))
              for name,conditions in panels.items()}
    ordered = sorted(scores,key=lambda name:(-scores[name],rank[name]))
    first,second = ordered[:2]
    comparison = paired_difference(panels[first],panels[second])
    selected = first if comparison['A_wins'] else min((first,second),key=rank.get)
    return dict(selected=selected,ranked=ordered,scores=scores,compared_top_two=[first,second],
                top_two_comparison=comparison,rule='taskbook_v3_single_seed_paired_bootstrap')


def convergence_budget(curve, *, ceiling=64000000):
    for n in sorted(curve):
        if 2*n not in curve:
            continue
        comparison = paired_difference({'condition':curve[2*n]},{'condition':curve[n]})
        low,high = comparison['ci95']
        if comparison['delta']<comparison['effect_threshold'] or low<=0<=high:
            return dict(status='OBSERVED_PLATEAU',budget=n,later_samples=2*n,
                        comparison=comparison,endpoint='before_doubling')
    return dict(status='CEILING_REACHED_WITHOUT_OBSERVED_PLATEAU' if ceiling in curve
                else 'MORE_CHECKPOINTS_REQUIRED',budget=None,tested_limit=max(curve,default=0))
