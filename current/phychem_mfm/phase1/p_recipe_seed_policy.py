"""The Nov18B conditional second-seed rule; never fit a probe or launch a run."""
import numpy as np
from .p_recipe import paired_decision


def effect_threshold(a,b):
    return max(.01,.05*max(float(a),float(b)))


def second_seed_required(a,b):
    threshold=effect_threshold(a,b)
    return .5*threshold<=abs(float(a)-float(b))<1.5*threshold


def combined_seed_decision(pairs):
    """Mean paired deltas; equal-weight concatenation of the two bootstrap sets.

    Each seed retains its registered1000 molecule-paired draws. Their2000
    differences form the two-seed CI distribution; no resampling is repeated.
    Side-line decisions retain their own preregistered rules instead.
    """
    if set(pairs) not in ({0},{0,1}):
        raise ValueError('Registered seeds are0 and optional1; no third seed')
    a=[];b=[];draws_a=[];draws_b=[];deltas=[]
    for seed in sorted(pairs):
        sa,sb,ba,bb=pairs[seed]
        ba=np.asarray(ba,dtype=np.float64);bb=np.asarray(bb,dtype=np.float64)
        if ba.shape!=(1000,) or bb.shape!=(1000,) or not np.isfinite(ba).all() or not np.isfinite(bb).all():
            raise ValueError('Use all1000 defined original paired bootstrap draws')
        if not np.isfinite([sa,sb]).all():raise ValueError('Missing completed seed scores')
        a.append(float(sa));b.append(float(sb));draws_a.append(ba);draws_b.append(bb);deltas.append(float(sa-sb))
    mean_a=float(np.mean(a));mean_b=float(np.mean(b))
    decision=paired_decision(mean_a,mean_b,np.concatenate(draws_a),np.concatenate(draws_b))
    # Preserve the specified mean-of-paired-deltas point estimate explicitly.
    decision['delta']=float(np.mean(deltas))
    threshold=effect_threshold(mean_a,mean_b)
    decision['verdict']=('win' if decision['ci_lower']>0 and decision['delta']>=threshold else
                         'loss' if decision['ci_upper']<0 and -decision['delta']>=threshold else 'tie')
    borderline=second_seed_required(a[0],b[0])
    return dict(decision=decision,seed_count=len(pairs),seeds=sorted(pairs),
                seed0_borderline=borderline,seed1_required=len(pairs)==1 and borderline,
                per_seed_deltas=deltas,mean_score_A=mean_a,mean_score_B=mean_b,
                threshold=threshold,seed0_threshold=effect_threshold(a[0],b[0]),
                bootstrap_draws_per_seed=1000,combined_bootstrap_draws=1000*len(pairs),
                CI_method='equal-weight concatenation of original seed-wise molecular paired bootstrap differences',
                authority='docs/p_recipe/USER_DIRECTIVE_20261118B.md')
