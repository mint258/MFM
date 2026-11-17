"""D-prime's user-fixed seed escalation and decision rules."""
import math


def decision(comparisons, baseline_r3):
    if len(comparisons) not in (1, 2) or len(comparisons) != len(baseline_r3):
        raise ValueError('Dprime uses one seed, or the two paired seeds')
    deltas = [float(row['delta']) for row in comparisons]
    intervals = [tuple(map(float, row['ci95'])) for row in comparisons]
    if any(not math.isfinite(x) for x in deltas + list(baseline_r3)
           + [x for pair in intervals for x in pair]):
        raise ValueError('Finite paired comparisons required')
    if any(len(pair) != 2 or pair[0] > pair[1] for pair in intervals):
        raise ValueError('Ordered paired CI required')
    low, high = intervals[0]
    immediate = abs(deltas[0]) >= .06 and (low > 0 or high < 0)
    if immediate:
        if len(comparisons) != 1:
            raise ValueError('Seed1 was not triggered by the registered rule')
        return dict(status='COMPLETE', verdict='win' if deltas[0] > 0 else 'loss',
                    seed1_required=False, seeds=[0], absolute_effect_threshold=.06)
    if len(comparisons) == 1:
        return dict(status='SEED1_REQUIRED', verdict=None, seed1_required=True, seeds=[0],
                    absolute_effect_threshold=.06)
    threshold = max(.03, sum(baseline_r3) / 2 * .08)
    mean_delta = sum(deltas) / 2
    verdict = ('win' if all(lo > 0 for lo, hi in intervals) and mean_delta >= threshold else
               'loss' if all(hi < 0 for lo, hi in intervals) else 'tie')
    return dict(status='COMPLETE', verdict=verdict, seed1_required=True, seeds=[0, 1],
                mean_delta=mean_delta, positive_effect_threshold=threshold)
