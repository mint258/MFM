"""Only the P taskbook's opt-in label and loss components."""
from __future__ import annotations
import numpy as np
import torch
from torch import nn

def element_residual(value, counts, coefficients, intercept, *, inverse=False):
    reference = counts @ coefficients + intercept
    return value + reference if inverse else value - reference

def state_difference(value, neutral, *, inverse=False):
    return value + neutral if inverse else value - neutral

def heavy_tail(value, m, *, inverse=False):
    if inverse:
        return value.sign() * torch.expm1(value.abs()) * m
    return value.sign() * torch.log1p(value.abs()/m)

def fit_element_residual(counts, targets):
    """Independent FP64 least squares, supplied TRAIN molecules only."""
    x=np.c_[np.asarray(counts,dtype=np.float64),np.ones(len(counts))]
    y=np.asarray(targets,dtype=np.float64)
    observed=np.isfinite(y)
    beta=np.linalg.lstsq(x[observed],y[observed],rcond=None)[0]
    residual=y[observed]-x[observed]@beta
    return dict(coefficients=beta[:-1].tolist(),intercept=float(beta[-1]),
                center=float(residual.mean()),scale=float(residual.std()),
                fit_molecules=int(observed.sum()))

def normalized_field_weights(families, *, family_equal=False, device=None, dtype=None):
    names=list(families)
    if not family_equal:
        return {n:torch.tensor(1/len(names),device=device,dtype=dtype) for n in names}
    groups={families[n] for n in names}
    counts={g:sum(families[n]==g for n in names) for g in groups}
    return {n:torch.tensor(1/(len(groups)*counts[families[n]]),device=device,dtype=dtype) for n in names}

class UncertaintyWeights(nn.Module):
    """Kendall regression form; report normalized precisions separately.

    Retain the mean precision outside the normalized weighted sum, giving
    exactly mean(0.5*exp(-s)*L + 0.5*s), without an unbounded shift-invariant
    softmax-only objective. No additional tuning constants are introduced.
    """
    def __init__(self, names):
        super().__init__();self.names=tuple(names)
        self.log_variance=nn.Parameter(torch.zeros(len(self.names)))
    def weights(self, selected=None):
        indices=[self.names.index(n) for n in (self.names if selected is None else selected)]
        return torch.softmax(-self.log_variance[indices],dim=0)
    def forward(self, values):
        names=tuple(values)
        indices=[self.names.index(n) for n in names]
        s=self.log_variance[indices]
        loss=torch.stack([values[n] for n in names])
        return (.5*torch.exp(-s)*loss+.5*s).mean()

def collapse_penalty(h, gamma):
    """B4: one fixed variance hinge and off-diagonal correlation penalty."""
    std=h.std(dim=0,unbiased=False)
    centered=h-h.mean(dim=0)
    covariance=centered.T@centered/len(h)
    correlation=covariance/(std[:,None]*std[None,:]).clamp_min(torch.finfo(h.dtype).eps)
    diagonal=torch.eye(h.shape[1],device=h.device,dtype=torch.bool)
    off_diagonal=correlation[~diagonal]
    return torch.relu(h.new_tensor(gamma)-std).mean()+off_diagonal.square().mean()

def paired_decision(a, b, bootstrap_a, bootstrap_b):
    """The taskbook's registered comparison; no tuning or extra gates."""
    delta=float(a-b)
    lower,upper=np.quantile(np.asarray(bootstrap_a)-np.asarray(bootstrap_b),[.025,.975])
    threshold=max(.01,.05*max(a,b))
    verdict='win' if lower>0 and delta>=threshold else ('loss' if upper<0 and -delta>=threshold else 'tie')
    return dict(delta=delta,ci_lower=float(lower),ci_upper=float(upper),verdict=verdict)
