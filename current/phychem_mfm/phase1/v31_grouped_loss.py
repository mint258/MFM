"""Column-batched physical scalar/vector regression with original field means."""
from collections import defaultdict

import numpy as np
import torch
import torch.nn.functional as F

from .v3_contract import FieldTarget, TrainNormalization, require, selected_groups
from .v3_losses import V3LossResult, compute_v3_loss


def grouped_regression_loss(predictions, targets, registry, normalizations, *, enabled_groups, enabled_fields=None,
                            prediction_affines=None):
    groups = selected_groups(enabled_groups)
    fields = registry.enabled(groups, enabled_fields)
    if any(f.kind != 'regression' or f.representation not in ('scalar', 'vector', 'magnitude')
           or not isinstance(normalizations.get(f.name), TrainNormalization) for f in fields):
        return compute_v3_loss(predictions, targets, registry, normalizations,
                               enabled_groups=groups, enabled_fields=enabled_fields)
    first = next(iter(predictions.values()), None)
    if first is None:
        return compute_v3_loss(predictions, targets, registry, normalizations,
                               enabled_groups=groups, enabled_fields=enabled_fields)
    zero = first.new_zeros((), dtype=torch.float32)
    buckets = defaultdict(list)
    for field in fields:
        buckets[(field.group, field.level, field.representation,
                 field.prediction_width, field.huber_delta, len(targets[field.name].values))].append(field)
    raw, counts = {}, {}
    for (_, _, representation, width, delta, _), columns in buckets.items():
        mask = torch.stack([targets[f.name].valid for f in columns], dim=1)
        sizes = mask.sum(0).cpu().tolist()
        active = []
        for field, size in zip(columns, sizes):
            counts[field.name] = size
            if size:
                active.append(field)
            else:
                # Keep absent-field parameters unused, as with the original loop.
                raw[field.name] = zero
        if not active:
            continue
        mask = torch.stack([targets[f.name].valid for f in active], dim=1).to(first.device)
        with torch.autocast(device_type=first.device.type, enabled=False):
            prediction = torch.stack([predictions[f.name].float() for f in active], dim=1)
            target = torch.stack([targets[f.name].values for f in active], dim=1).to(first.device)
            require(bool((~mask | torch.isfinite(target).all(-1)).all()), 'Invalid observed label')
            require(bool((~mask | torch.isfinite(prediction).all(-1)).all()), 'Nonfinite observed prediction')
            # Exclude missing NaNs before any arithmetic, including inactive branches.
            prediction = torch.where(mask[..., None], prediction, 0.)
            target = torch.where(mask[..., None], target, 0.)
            if prediction_affines is not None:
                center = prediction.new_tensor([prediction_affines[f.name]['center'] for f in active])
                scale = prediction.new_tensor([prediction_affines[f.name]['scale'] for f in active])
                prediction = (prediction-center[None])/scale[None]
            centers = prediction.new_tensor([normalizations[f.name].center if len(normalizations[f.name].center)==width
                                            else normalizations[f.name].center*width for f in active])
            scales = prediction.new_tensor([normalizations[f.name].scale if len(normalizations[f.name].scale)==width
                                           else normalizations[f.name].scale*width for f in active])
            prediction = (prediction - centers[None]) / scales[None]
            target = (target - centers[None]) / scales[None]
            if representation == 'vector':
                radius2 = (prediction - target).square().mean(-1)
                rows = torch.where(radius2 <= delta**2, .5*radius2,
                    delta*(radius2.clamp_min(delta**2).sqrt()-.5*delta))
            else:
                rows = F.huber_loss(prediction, target, reduction='none', delta=delta).mean(-1)
            denominator = prediction.new_tensor([counts[f.name] for f in active])
            values = torch.where(mask, rows, 0.).sum(0) / denominator
            require(bool(torch.isfinite(values).all()), 'Nonfinite loss')
            raw.update((f.name, values[i]) for i, f in enumerate(active))
    raw = {f.name: raw[f.name] for f in fields}
    by_group = {group: [raw[f.name] for f in fields if f.group == group and counts[f.name]] for group in groups}
    losses = {group: torch.stack(values).mean() if values else zero for group, values in by_group.items()}
    total = torch.stack(list(losses.values())).mean() if groups else zero
    return V3LossResult(total, raw, losses, counts,
                        {group: len(values) for group, values in by_group.items()}, groups)


def prepare_v31_targets(model, samples, groups, fields):
    """CPU packing, also used in the reader process without an encoder."""
    members = defaultdict(list)
    for field in model.registry.enabled(groups, fields):
        name = field.name
        spec = model.definitions[name].get('normalization', model.view.normalizations.get(name))
        if spec is None:
            raise ValueError('Missing D4 normalization for ' + name)
        values = np.concatenate([s['targets'][name].values for s in samples])
        valid = np.concatenate([s['targets'][name].valid for s in samples])
        head_name, component = model.selections[name]
        members[head_name].append((component, name, values, valid, spec))
    targets, affines, names = {}, {}, {}
    for name, columns in members.items():
        if columns[0][0] is not None:
            columns.sort(key=lambda item: item[0])
            if [item[0] for item in columns] != [0, 1, 2]:
                raise ValueError('The original physical vector loss requires all three selected components')
        if model.head_by_name[name].representation == 'vector':
            model._require_vector_normalization([item[4] for item in columns])
        names[name] = tuple(item[1] for item in columns)
        values = np.concatenate([item[2] for item in columns], -1)
        valid = np.concatenate([item[3] for item in columns], -1).all(-1)
        targets[name] = FieldTarget(torch.as_tensor(values, dtype=torch.float32), torch.as_tensor(valid))
        center, scale = [], []
        for _, _, value, _, spec in columns:
            center.extend(np.broadcast_to(spec['center'], (value.shape[-1],)).tolist())
            scale.extend(np.broadcast_to(spec['scale'], (value.shape[-1],)).tolist())
        affines[name] = dict(center=center, scale=scale)
    return targets, affines, names


def grouped_v31_loss(model, predictions, samples, groups, fields):
    """Apply prediction affines and the original physical losses by column."""
    prepared = getattr(samples, 'prepared', {})
    if 'loss_targets' in prepared:
        from .p_recipe_input import unpack_targets
        targets, affines, names = unpack_targets(prepared['loss_targets'])
    else:
        targets, affines, names = prepare_v31_targets(model, samples, groups, fields)
    physical = {name: torch.cat([predictions[n] for n in columns], -1) if len(columns)>1
                else predictions[columns[0]] for name, columns in names.items()}
    return grouped_regression_loss(physical, targets, model.head_registry, model.unit_normalizations,
        enabled_groups=groups, enabled_fields=tuple(names),
        prediction_affines=affines if model.output_parameterization=='raw' else None)
