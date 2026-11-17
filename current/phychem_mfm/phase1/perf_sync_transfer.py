"""Shared reader tensors and a one-batch pinned, event-ordered CUDA prefetch."""
from collections import deque
from copy import copy

import torch
from torch_geometric.data.data import BaseData


def map_tensors(value, function):
    if isinstance(value, torch.Tensor):
        return function(value)
    if isinstance(value, BaseData):
        return copy(value).apply(function)
    if isinstance(value, dict):
        return {name: map_tensors(item, function) for name, item in value.items()}
    if isinstance(value, tuple):
        return tuple(map_tensors(item, function) for item in value)
    if isinstance(value, list):
        return [map_tensors(item, function) for item in value]
    return value


def share_tensors(value):
    return map_tensors(value, lambda tensor: tensor.share_memory_())


def async_batches(batches, device='cuda'):
    from .p_recipe_input import PreparedSamples
    stream = torch.cuda.Stream(device=device)
    inflight = deque()
    source = iter(batches)

    def fetch():
        try:
            samples, rng = next(source)
        except StopIteration:
            return None
        pinned = map_tensors(samples.prepared, lambda tensor: tensor.pin_memory())
        with torch.cuda.stream(stream):
            copied = map_tensors(pinned, lambda tensor: tensor.to(device, non_blocking=True))
            ready = torch.cuda.Event()
            ready.record(stream)
        inflight.append((ready, pinned))
        return PreparedSamples(samples, copied), rng, ready

    pending = fetch()
    try:
        while pending is not None:
            samples, rng, ready = pending
            compute = torch.cuda.current_stream(device)
            compute.wait_event(ready)
            map_tensors(samples.prepared, lambda tensor: tensor.record_stream(compute) or tensor)
            pending = fetch()
            while inflight and inflight[0][0].query():
                inflight.popleft()
            yield samples, rng
    finally:
        # Keep pinned sources alive until DMA finishes, including early exits.
        stream.synchronize()
        inflight.clear()
        if hasattr(source, 'close'):
            source.close()
