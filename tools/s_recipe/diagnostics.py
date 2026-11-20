"""Consume existing S forward outputs for zero-displacement diagnostics."""
import torch
from torch_geometric.utils import to_dense_batch


def noise_statistics(outputs, views, *, group_labels=None):
    noisy, _ = to_dense_batch(views.batch.pos, views.batch.batch)
    reference, _ = to_dense_batch(views.batch.target_pos, views.batch.batch)
    target = noisy.float() - reference.float()
    mask = outputs.node_mask.squeeze(-1).bool()
    mask = mask & views.batch.sample_type_id.reshape(-1).eq(1)[:, None]
    mask = mask & torch.isfinite(reference).all(-1) & torch.isfinite(noisy).all(-1)
    residual = outputs.noise_pred.float() - target
    predicted_error = residual.square().sum(-1)
    zero_error = target.square().sum(-1)
    # Sum before division so graph/atom counts retain their original weighting.
    result = dict(predicted_squared_error=float(predicted_error[mask].sum()),
                  zero_squared_error=float(zero_error[mask].sum()), atoms=int(mask.sum()))
    if group_labels is not None:
        groups = {}
        for graph in mask.any(dim=1).nonzero().reshape(-1).tolist():
            label = group_labels[int(views.base_graph_index[graph])]
            group = groups.setdefault(label, dict(predicted_squared_error=0., zero_squared_error=0., atoms=0))
            group['predicted_squared_error'] += float(predicted_error[graph][mask[graph]].sum())
            group['zero_squared_error'] += float(zero_error[graph][mask[graph]].sum())
            group['atoms'] += int(mask[graph].sum())
        result['groups'] = groups
    return result


def relative_error(statistics):
    denominator = statistics['zero_squared_error']
    return statistics['predicted_squared_error']/denominator if denominator > 0 else None
