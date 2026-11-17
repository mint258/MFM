"""Preregistered5090 ABBA and two-seed gates; no model/data math."""
from decimal import Decimal
import math


def _decimal(value):
    if not math.isfinite(float(value)):
        raise ValueError('Nonfinite measurement')
    return Decimal(str(value))


def abba(rates):
    if len(rates)!=4:
        raise ValueError('ABBA requires exactly four rates')
    a0,b0,b1,a1=map(_decimal,rates)
    if min(a0,b0,b1,a1)<=0:
        raise ValueError('Rates must be positive')
    baseline=(a0+a1)/2
    candidate=(b0+b1)/2
    gap=abs(a1-a0)
    # Cross multiplication keeps the strict 2*noise boundary exact.
    effective=candidate>=Decimal('1.05')*baseline and candidate-baseline>2*gap
    return dict(baseline_mean=float(baseline),candidate_mean=float(candidate),
        speedup=float(candidate/baseline),baseline_gap_samples_per_second=float(gap),
        baseline_noise_fraction=float(gap/baseline),speed_effective=bool(effective))


def two_seed_quality(baseline,candidate,finite):
    if set(baseline)!={0,1} or set(candidate)!={0,1} or set(finite)!={0,1}:
        raise ValueError('Both seeds are mandatory')
    base={s:_decimal(baseline[s]) for s in (0,1)}
    cand={s:_decimal(candidate[s]) for s in (0,1)}
    noise=abs(base[0]-base[1]);limit=noise+Decimal('0.01')
    deltas={s:abs(cand[s]-base[s]) for s in (0,1)}
    passed=all(finite[s] and deltas[s]<=limit for s in (0,1))
    return dict(noise_N=float(noise),limit=float(limit),
        absolute_deltas={str(s):float(deltas[s]) for s in (0,1)},passed=bool(passed))


def cpu_scan_plan(available,completed=()):
    """Reuse a closed cell even if a recovered allocation has fewer CPUs."""
    return [dict(cores=n,reuse=n in completed,run=n<=available or n in completed)
            for n in (4,8,16,24)]
