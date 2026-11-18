"""Opt-in step execution helpers; no parameters or checkpoint state are added."""
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps

import torch


_layout = ContextVar('perf_sync_layout', default=None)
_finite = ContextVar('perf_sync_finite', default=None)


def layout_forward(function):
    @wraps(function)
    def wrapped(self, *args, **kwargs):
        data = args[0] if args else kwargs.get('batch', kwargs.get('data'))
        if not hasattr(data, 'perf_sync_layout'):
            return function(self, *args, **kwargs)
        with batch_layout(data):
            return function(self, *args, **kwargs)
    return wrapped


def prepare_layout(data):
    """Called only in a CPU reader, before any device transfer."""
    if data.batch.device.type != 'cpu':
        raise ValueError('Prepare graph metadata on CPU')
    ids = data.batch
    graphs = int(ids.max()) + 1 if ids.numel() else 0
    counts = torch.bincount(ids, minlength=graphs)
    if graphs == 0 or not bool((counts > 0).all()) or not bool((ids >= 0).all()):
        raise ValueError('Packed nonempty contiguous molecule IDs required')
    if data.pos.dtype != torch.float32 or not bool(torch.isfinite(data.pos).all()):
        raise ValueError('Finite fp32 source coordinates required')
    maximum = int(counts.max())
    offsets = counts.cumsum(0) - counts
    packed = torch.arange(len(ids)) - offsets[ids] + ids * maximum
    data.perf_sync_layout = dict(graphs=graphs, maximum=maximum, counts=counts,
                                 packed=packed, finite=[])
    return data


@contextmanager
def batch_layout(data):
    token = _layout.set(getattr(data, 'perf_sync_layout', None))
    try:
        yield
    finally:
        _layout.reset(token)


def graph_count(batch):
    layout = _layout.get()
    return layout['graphs'] if layout is not None else int(batch.max()) + 1


def has_layout():
    return _layout.get() is not None


def dense_batch(value, batch, fill_value=0.):
    from torch_geometric.utils import to_dense_batch
    layout = _layout.get()
    if layout is None:
        return to_dense_batch(value, batch, fill_value=fill_value)
    # This mode skips PyG's GPU max/filter guard: the reader validated the layout.
    from torch_geometric.experimental import experimental_mode
    with experimental_mode('disable_dynamic_shapes'):
        return to_dense_batch(value, batch, fill_value=fill_value,
                              batch_size=layout['graphs'], max_num_nodes=layout['maximum'])


def unpack_dense(value, mask):
    layout = _layout.get()
    return value[mask] if layout is None else value.flatten(0, 1)[layout['packed']]


@contextmanager
def finite_checks():
    checks = []
    token = _finite.set(checks)
    try:
        yield checks
    finally:
        _finite.reset(token)


def check_finite(value):
    """Internal activations cannot be checked in readers; defer the GPU flag."""
    check = torch.isfinite(value).all()
    checks = _finite.get()
    if checks is None:
        return bool(check)
    checks.append(check)
    return True


def configure(model, options):
    """Assign execution attributes only; retain original state_dict key names."""
    if not any(options.get(name, False) for name in ('sync_free', 'sdpa', 'async_transfer')) and options.get('compile', 'none') == 'none' and not getattr(model, 'perf_sync_configured', False):
        return
    model.perf_sync_configured = True
    from .attention import DenseGeoSelfAttention
    from .v3_latent import MaskedAttention
    mode = options.get('compile', 'none')
    if mode not in ('none', 'encoder', 'encoder_heads'):
        raise ValueError('compile must be none, encoder, or encoder_heads')
    for module in model.modules():
        if isinstance(module, (DenseGeoSelfAttention, MaskedAttention)):
            module.perf_sync_sdpa = bool(options.get('sdpa', False))
    backbone = model.encoder.backbone
    backbone.perf_sync_free = bool(options.get('sync_free', False))
    backbone.perf_sync_mark_dynamic = bool(options.get('compile_mark_dynamic', False))
    model.heads.perf_sync_free = bool(options.get('sync_free', False))
    for layer in backbone.layers:
        if mode != 'none':
            layer.compile(dynamic=True)
        else:
            layer._compiled_call_impl = None
    if mode == 'encoder_heads':
        model.heads.compile(dynamic=True)
    else:
        model.heads._compiled_call_impl = None
