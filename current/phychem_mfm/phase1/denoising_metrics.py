"""Explicit masks and original-unit metrics for the S denoising repair."""
from __future__ import annotations

import math
import torch
import torch.nn.functional as F
from torch_geometric.utils import to_dense_batch

from ..data.descriptor_schema import BOND_INDEX_FIELD, BOND_ORDER_FIELD
from ..training.data import SAMPLE_TYPE_TO_ID


class DenoisingMetrics:
    def __init__(self, *, sigma=0.1, cutoff=2.0):
        self.sigma, self.cutoff = float(sigma), float(cutoff)
        self.element_correct = self.element_count = 0
        self.element_nll = 0.0
        self.bond_correct = self.bond_count = 0
        self.class_correct = [0] * 5
        self.class_count = [0] * 5
        self.local_sq = self.bond_sq = self.noise_sq = self.noisy_local_sq = 0.0
        self.local_pairs = self.bond_pairs = self.noise_atoms = 0

    @torch.no_grad()
    def add(self, outputs, batch):
        dense = lambda value: to_dense_batch(value, batch.batch)[0]
        group = batch.sample_type_id.reshape(-1).long()
        geom = group.eq(SAMPLE_TYPE_TO_ID["geom"]) | group.eq(SAMPLE_TYPE_TO_ID["both"])
        topo = group.eq(SAMPLE_TYPE_TO_ID["topo"]) | group.eq(SAMPLE_TYPE_TO_ID["both"])
        nodes = outputs.node_mask.squeeze(-1).bool()
        targets = dense(batch.target_x)[..., 0]
        mask = nodes & topo[:, None] & dense(batch.element_corrupt_mask).squeeze(-1).bool()
        mask &= targets.ge(0) & targets.lt(outputs.element_logits.size(-1) - 1)
        if mask.any():
            selected, expected = outputs.element_logits[mask].float(), targets[mask].long()
            self.element_correct += int(selected.argmax(-1).eq(expected).sum())
            self.element_count += len(expected)
            self.element_nll += float(F.cross_entropy(selected, expected, reduction="sum"))
        bond = outputs.bond
        keep = group[bond.pair_graph_index].eq(SAMPLE_TYPE_TO_ID["clean"])
        true = bond.order_target[keep].long()
        pred = bond.order[keep].argmax(-1)
        self.bond_correct += int(pred.eq(true).sum())
        self.bond_count += len(true)
        for k in range(5):
            selected = true.eq(k)
            self.class_count[k] += int(selected.sum())
            self.class_correct[k] += int((pred.eq(true) & selected).sum())
        target, noisy = dense(batch.target_pos).float(), dense(batch.pos).float()
        predicted = outputs.coordinate_pred.float()
        valid = nodes & geom[:, None] & torch.isfinite(target).all(-1)
        eps_hat = outputs.noise_pred if outputs.noise_pred is not None else noisy - predicted
        self.noise_sq += float((eps_hat.float()[valid] - (noisy - target)[valid]).double().square().sum())
        self.noise_atoms += int(valid.sum())
        truth = torch.cdist(target, target)
        recovered = torch.cdist(predicted, predicted)
        observed = torch.cdist(noisy, noisy)
        pair = valid[:, :, None] & valid[:, None, :]
        pair &= torch.triu(torch.ones_like(truth, dtype=torch.bool), diagonal=1)
        local = pair & truth.lt(self.cutoff)
        self.local_sq += float((recovered.double() - truth.double())[local].square().sum())
        self.noisy_local_sq += float((observed.double() - truth.double())[local].square().sum())
        self.local_pairs += int(local.sum())
        edges, order = getattr(batch, BOND_INDEX_FIELD), getattr(batch, BOND_ORDER_FIELD)
        i, j = edges.long()
        keep = geom[batch.batch[i]] & i.lt(j) & order.gt(0)
        if keep.any():
            gt = (batch.target_pos[i[keep]] - batch.target_pos[j[keep]]).float().norm(dim=-1)
            # Dense-to-packed follows the exact explicit node mask.
            packed = predicted[nodes]
            pr = (packed[i[keep]] - packed[j[keep]]).norm(dim=-1)
            self.bond_sq += float((pr.double() - gt.double()).square().sum())
            self.bond_pairs += int(keep.sum())

    def result(self):
        divide = lambda value, count: value / count if count else None
        rmse = lambda value, count: math.sqrt(value / count) if count else None
        return {
            "masked_element_accuracy": divide(self.element_correct, self.element_count),
            "masked_element_nll": divide(self.element_nll, self.element_count),
            "masked_element_count": self.element_count,
            "bond_order_accuracy": divide(self.bond_correct, self.bond_count),
            "bond_order_count": self.bond_count,
            "bond_order_recall": [divide(c, n) for c, n in zip(self.class_correct, self.class_count)],
            "bond_order_class_counts": self.class_count,
            "local_rmse_A": rmse(self.local_sq, self.local_pairs), "local_pair_count": self.local_pairs,
            "noisy_local_rmse_A": rmse(self.noisy_local_sq, self.local_pairs),
            "bond_rmse_A": rmse(self.bond_sq, self.bond_pairs), "bond_pair_count": self.bond_pairs,
            "noise_mse_normalized": divide(self.noise_sq, 3.0 * self.sigma ** 2 * self.noise_atoms),
            "noise_mse_A2_per_component": divide(self.noise_sq, 3 * self.noise_atoms),
            "noise_atom_count": self.noise_atoms,
        }


def shared_gradient_diagnostics(losses, model, *, weights=None):
    """Exact autograd gradients over all shared-backbone parameters, no proxies."""
    parameters = tuple(p for p in model.backbone.parameters() if p.requires_grad)
    gradients, norms = {}, {}
    for name, loss in losses.items():
        grad = torch.autograd.grad(loss, parameters, retain_graph=True, allow_unused=True)
        if weights is not None:
            grad = tuple(None if g is None else g * float(weights[name]) for g in grad)
        gradients[name] = grad
        norms[name] = math.sqrt(sum(float(g.detach().double().square().sum()) for g in grad if g is not None))
    denominator = sum(norms.values())
    fractions = {name: value / denominator if denominator else 0.0 for name, value in norms.items()}
    cosines = {}
    names = list(losses)
    for index, a in enumerate(names):
        for b in names[index + 1:]:
            dot = sum(float((ga.detach().double() * gb.detach().double()).sum())
                      for ga, gb in zip(gradients[a], gradients[b]) if ga is not None and gb is not None)
            cosines[a + "/" + b] = dot / (norms[a] * norms[b]) if norms[a] * norms[b] else None
    return {"norms": norms, "fractions_of_sum_of_norms": fractions, "cosine_similarities": cosines}
