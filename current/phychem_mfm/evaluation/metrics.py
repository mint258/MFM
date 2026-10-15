from __future__ import annotations

import math
from typing import Iterable

import torch
from torch import Tensor


def regression_metrics(prediction: Tensor, target: Tensor) -> dict[str, float]:
    pred = prediction.detach().float().reshape(-1).cpu()
    true = target.detach().float().reshape(-1).cpu()
    valid = torch.isfinite(pred) & torch.isfinite(true)
    pred, true = pred[valid], true[valid]
    if pred.numel() == 0:
        return {key: math.nan for key in ("mae", "rmse", "median_ae", "p90_ae", "p95_ae")}
    error = (pred - true).abs()
    return {
        "mae": float(error.mean()),
        "rmse": float(torch.sqrt((pred - true).square().mean())),
        "median_ae": float(error.median()),
        "p90_ae": float(torch.quantile(error, 0.90)),
        "p95_ae": float(torch.quantile(error, 0.95)),
        "count": int(error.numel()),
    }


def confusion_matrix(prediction: Tensor, target: Tensor, num_classes: int) -> Tensor:
    pred = prediction.detach().long().reshape(-1).cpu()
    true = target.detach().long().reshape(-1).cpu()
    valid = (true >= 0) & (true < num_classes) & (pred >= 0) & (pred < num_classes)
    ids = true[valid] * num_classes + pred[valid]
    return torch.bincount(ids, minlength=num_classes * num_classes).reshape(num_classes, num_classes)


def classification_metrics(prediction: Tensor, target: Tensor, num_classes: int) -> dict[str, object]:
    matrix = confusion_matrix(prediction, target, num_classes).float()
    support = matrix.sum(1)
    tp = matrix.diag()
    precision = tp / matrix.sum(0).clamp_min(1.0)
    recall = tp / support.clamp_min(1.0)
    f1 = 2 * precision * recall / (precision + recall).clamp_min(1e-12)
    present = support > 0
    total = matrix.sum()
    return {
        "accuracy": float(tp.sum() / total.clamp_min(1.0)),
        "macro_f1": float(f1[present].mean()) if present.any() else math.nan,
        "per_class_recall": {str(index): float(recall[index]) for index in torch.where(present)[0].tolist()},
        "confusion_matrix": matrix.long().tolist(),
        "count": int(total),
    }


def binary_metrics(score: Tensor, target: Tensor) -> dict[str, float]:
    scores = score.detach().float().reshape(-1).cpu()
    true = target.detach().long().reshape(-1).cpu()
    valid = torch.isfinite(scores) & ((true == 0) | (true == 1))
    scores, true = scores[valid], true[valid]
    pred = scores >= 0.5
    tp = ((pred == 1) & (true == 1)).sum().float()
    fp = ((pred == 1) & (true == 0)).sum().float()
    fn = ((pred == 0) & (true == 1)).sum().float()
    precision = tp / (tp + fp).clamp_min(1.0)
    recall = tp / (tp + fn).clamp_min(1.0)
    f1 = 2 * precision * recall / (precision + recall).clamp_min(1e-12)
    positives = (true == 1).sum()
    if scores.numel() and positives:
        order = torch.argsort(scores, descending=True)
        sorted_true = true[order].float()
        cumulative_tp = sorted_true.cumsum(0)
        rank = torch.arange(1, len(sorted_true) + 1, dtype=torch.float32)
        auprc = float((cumulative_tp / rank * sorted_true).sum() / positives)
    else:
        auprc = math.nan
    return {
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "auprc": auprc,
        "count": int(scores.numel()),
    }


def concat(parts: Iterable[Tensor]) -> Tensor:
    materialized = [part.detach().cpu() for part in parts if part.numel()]
    return torch.cat(materialized) if materialized else torch.empty(0)
