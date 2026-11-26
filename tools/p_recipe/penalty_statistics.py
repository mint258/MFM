"""A3 native B32 penalty terms and F64 fixed-VAL summaries; no fitting."""
import math
import numpy as np
import torch


def b4_terms(h,gamma):
    # Same operations/order as phase1.p_recipe.collapse_penalty.
    std=h.std(dim=0,unbiased=False)
    centered=h-h.mean(dim=0)
    covariance=centered.T@centered/len(h)
    correlation=covariance/(std[:,None]*std[None,:]).clamp_min(torch.finfo(h.dtype).eps)
    diagonal=torch.eye(h.shape[1],device=h.device,dtype=torch.bool)
    off_diagonal=correlation[~diagonal]
    return torch.relu(h.new_tensor(gamma)-std).mean(),off_diagonal.square().mean()


def p_objective(loss):
    # T2's original grouped-field branch: equal active fields, before B4.
    active=[name for name in loss.fields if loss.counts[name]>0]
    if not active:
        raise ValueError("No observed P field in this native validation batch")
    return torch.stack([loss.fields[name] for name in active]).mean()


def validate_prefix(rows,fixed,batch_size):
    batches=(len(fixed)+batch_size-1)//batch_size
    if len(rows)>batches:
        raise ValueError("Analysis cursor exceeds the fixed validation population")
    for i,row in enumerate(rows):
        expected=fixed[i*batch_size:(i+1)*batch_size]
        if (row["batch_index"]!=i or row["molecule_indices"]!=expected
                or row["molecules"]!=len(expected)):
            raise ValueError("Closed native batch prefix/population changed")
    return len(rows)


def summarize_batches(rows,fixed,batch_size):
    if validate_prefix(rows,fixed,batch_size)!=(len(fixed)+batch_size-1)//batch_size:
        raise ValueError("Do not summarize an unfinished source")
    weights=np.asarray([r["molecules"] for r in rows],dtype=np.float64)
    names=("hinge","decorrelation","B4","weighted_B4","P_loss")
    values={name:np.asarray([r[name] for r in rows],dtype=np.float64) for name in names}
    if not all(np.isfinite(a).all() for a in values.values()):
        raise ValueError("Nonfinite native penalty/P loss")
    means={name:float(np.dot(weights,a)/weights.sum()) for name,a in values.items()}
    b4=means["B4"]
    ratio=means["weighted_B4"]/means["P_loss"] if means["P_loss"]>0 else None
    return dict(molecules=int(weights.sum()),native_batches=len(rows),batch_size=batch_size,
        last_batch_molecules=int(weights[-1]),hinge=means["hinge"],
        decorrelation=means["decorrelation"],B4=b4,weighted_B4=means["weighted_B4"],
        P_loss=means["P_loss"],weighted_B4_over_P=ratio,
        aggregation="molecule_count_weighted_native_B32_batches_then_ratio_of_means",
        term_precision="original_FP32_operators",statistics_precision="F64",
        gamma_refitted=False,CI_computed=False)


def intervention_condition(rows):
    values={int(r["checkpoint_samples"]):r["weighted_B4_over_P"] for r in rows}
    if set(values)!={1000000,3000000,6000000,9000000}:
        raise ValueError("All four preregistered T2 sources required")
    first,last=values[1000000],values[9000000]
    growth=(last/first if first is not None and first>0 and last is not None else None)
    return dict(ratio_9M_over_1M=growth,
        I2_triggered=(growth>=2 if growth is not None else None),
        interpretation="Trigger only; no intervention or recipe adoption performed",
        I2_initial150k_policy_resolved=False)
