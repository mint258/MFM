"""Execute P head banks with the existing separately named parameters."""
from collections import defaultdict

import torch
import torch.nn.functional as F
from torch import nn
from torch.nn.utils.rnn import pad_sequence
from torch.utils.checkpoint import checkpoint

from .v3_heads import _pool
from .perf_sync import graph_count


def _linear(modules, value):
    if value.ndim == 2:
        weight = torch.cat([module.weight for module in modules])
        bias = None if modules[0].bias is None else torch.cat([module.bias for module in modules])
        return F.linear(value, weight, bias).reshape(len(value), len(modules), modules[0].out_features)
    weight = torch.stack([module.weight for module in modules])
    result = torch.bmm(value.transpose(0, 1), weight.transpose(1, 2)).transpose(0, 1)
    if modules[0].bias is not None:
        result = result + torch.stack([module.bias for module in modules])[None]
    return result


def _bank(modules, value):
    if isinstance(modules[0], nn.Linear):
        return _linear(modules, value)
    for index, layer in enumerate(modules[0]):
        if isinstance(layer, nn.Linear):
            value = _linear([module[index] for module in modules], value)
        else:
            value = F.silu(value)
    return value


def _signature(module):
    layers = [module] if isinstance(module, nn.Linear) else module
    return tuple((layer.in_features, layer.out_features, layer.bias is not None)
                 if isinstance(layer, nn.Linear) else type(layer).__name__ for layer in layers)


def _atom_vectors(heads, h, pos, batch):
    first = heads[0]
    src, dst = first._edges(pos, batch)
    degree = torch.bincount(src, minlength=len(pos)).clamp_min(1).to(pos.dtype).sqrt()[:, None, None]
    noise = pos.new_zeros((len(pos), len(heads), 3))

    def chunk(features, coordinates, i, j):
        relative = coordinates[i] - coordinates[j]
        distance = relative.norm(dim=-1).clamp_min(1e-8)
        centers = torch.stack([head.rbf_centers for head in heads])
        rbf = torch.exp(-first.rbf_gamma*(distance[:, None, None]-centers[None])**2)
        envelope = .5*(1.+torch.cos(torch.pi*distance/first.radius))
        rbf = rbf*envelope[:, None, None]
        left = features[i, None].expand(-1, len(heads), -1)
        right = features[j, None].expand(-1, len(heads), -1)
        values = _bank([head.pair_mlp for head in heads], torch.cat((left, right, rbf.to(features.dtype)), -1))
        return values*(relative/distance[:, None])[:, None]

    for start in range(0, len(src), first.pair_chunk_size):
        i, j = src[start:start+first.pair_chunk_size], dst[start:start+first.pair_chunk_size]
        value = (checkpoint(chunk, h, pos, i, j, use_reentrant=False) if first.activation_checkpointing and torch.is_grad_enabled()
                 else chunk(h, pos, i, j))
        noise = noise.index_add(0, i, value.to(pos.dtype))
    return noise/degree if first.normalization == 'sqrt_neighbors' else noise


def _pairs(heads, h, pos, indices):
    lengths = [index.shape[1] for index in indices]
    if not max(lengths):
        return [h.new_zeros((0, head.predict[-1].out_features)) for head in heads]
    packed = pad_sequence([index.T for index in indices])
    src, dst = packed[..., 0], packed[..., 1]
    features = (h[src]+h[dst], (h[src]-h[dst]).abs())
    if heads[0].use_distance:
        distance = (pos[src].float()-pos[dst].float()).norm(dim=-1)
        centers = torch.stack([head.centers for head in heads])
        rbf = torch.exp(-heads[0].gamma*(distance[..., None]-centers[None].float())**2)
        envelope = torch.where(distance < heads[0].radius,
            .5*(1+torch.cos(torch.pi*distance/heads[0].radius)), torch.zeros_like(distance))
        features += ((rbf*envelope[..., None]).to(h.dtype),)
    values = _bank([head.predict for head in heads], torch.cat(features, -1))
    return [values[:length, index] for index, length in enumerate(lengths)]


def grouped_head_predictions(bank, h, batch, pos, fields, pairs, graph_latent, observed_fields):
    graphs = graph_count(batch)
    buckets = defaultdict(list)
    for field in fields:
        if field.group != 'P' or field.level == 'ordered_entry' or field.representation == 'symmetric_tensor6':
            continue
        head = bank.field_heads[bank.keys[field.name]]
        observed = observed_fields is None or field.name in observed_fields
        if field.representation in ('vector', 'magnitude'):
            if field.level == 'atom':
                if head.message_layers:
                    continue
                kind = ('atom_vector', head.radius, head.normalization, head.pair_chunk_size,
                        head.rbf_gamma, head.activation_checkpointing, _signature(head.pair_mlp))
            else:
                kind = ('graph_vector', _signature(head.charges))
        elif field.level == 'pair':
            kind = ('pair', head.radius, head.gamma, head.use_distance, _signature(head.predict))
        elif field.level == 'atom':
            kind = ('atom', _signature(head))
        elif hasattr(bank, 'p_recipe_pma_dim'):
            kind = ('pma', _signature(head))
        elif hasattr(bank, 'latent_scalar_dim'):
            continue
        else:
            learned = bank.pooling_overrides.get(field.name) == 'learned' or field.pooling == 'learned'
            kind = ('graph', 'learned' if learned else field.pooling,
                    bank.forms[field.name], field.group, _signature(head))
        buckets[(observed, kind)].append(field)
    outputs, pooled = {}, {}

    def pool(mode):
        key = mode, torch.is_grad_enabled()
        if key not in pooled:
            pooled[key] = _pool(h, batch, graphs, mode)
        return pooled[key]

    for (observed, kind), columns in buckets.items():
        heads = [bank.field_heads[bank.keys[field.name]] for field in columns]
        with torch.set_grad_enabled(torch.is_grad_enabled() and observed):
            if kind[0] == 'pair':
                values = _pairs(heads, h, pos, [pairs[field.name] for field in columns])
            elif kind[0] == 'atom_vector':
                values = _atom_vectors(heads, h.float(), pos.float(), batch).unbind(1)
            elif kind[0] == 'graph_vector':
                center = _pool(pos.float(), batch, graphs, 'mean')
                charges = _bank([head.charges for head in heads], h.float())
                vectors = pos.new_zeros((graphs, len(heads), 3)).index_add(
                    0, batch, charges*(pos.float()-center[batch])[:, None])
                values = [vectors[:, i].norm(dim=-1, keepdim=True) if head.magnitude else vectors[:, i]
                          for i, head in enumerate(heads)]
            else:
                if kind[0] == 'atom':
                    feature = h
                elif kind[0] == 'pma':
                    feature = graph_latent
                else:
                    if kind[1] == 'learned':
                        coefficients = torch.stack([bank.pooling_mixers[bank.keys[f.name]].logits for f in columns]).softmax(-1)
                        feature = (pool('sum')[:, None]*coefficients[None, :, 0, None]
                                   + pool('mean')[:, None]*coefficients[None, :, 1, None])
                    else:
                        feature = pool(kind[1])
                    if kind[2] == 'H2':
                        feature = bank.group_projectors[kind[3]](feature)
                values = _bank(heads, feature).unbind(1)
            outputs.update((field.name, value) for field, value in zip(columns, values))
    return outputs
