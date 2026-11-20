"""Registered S deletions retain the original baseline denominator."""
import torch


def structural_total(raw, counts, *, disabled=()):
    """Compute all role counts before deletion; never reweight surviving roles."""
    disabled = set(disabled)
    if set(raw) != set(counts) or not disabled <= set(raw):
        raise ValueError('Explicit original S fields and deletion subset required')
    valid = [name for name in raw if counts[name] > 0]
    terms = [raw[name] for name in valid if name not in disabled]
    zero = next(iter(raw.values())).new_zeros(())
    if not terms:
        return zero
    if not disabled:
        return torch.stack(terms).mean()  # exact original baseline reduction
    return torch.stack(terms).sum() / len(valid)
