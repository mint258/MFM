"""Selective GEMM precision; every operator boundary remains FP32.

No module or parameter is replaced. Modes are runtime attributes, so old
state dictionaries and the master weights keep their original schema.
TF32 is enabled inside eligible GEMMs, including their backward GEMMs.
BF16 autocast is local to a GEMM and its result is immediately widened.
"""
from contextlib import contextmanager
from contextvars import ContextVar

import torch
from torch.nn import functional as F

MODES = ('fp32', 'tf32_islands', 'bf16_islands')
_observer = ContextVar('precision_island_observer', default=None)


@contextmanager
def matmul_flags(tf32=False):
    previous = (torch.backends.cuda.matmul.allow_tf32, torch.backends.cudnn.allow_tf32)
    try:
        torch.backends.cuda.matmul.allow_tf32 = tf32
        torch.backends.cudnn.allow_tf32 = False
        yield
    finally:
        torch.backends.cuda.matmul.allow_tf32, torch.backends.cudnn.allow_tf32 = previous


@contextmanager
def fp32_island(value):
    with matmul_flags(False), torch.autocast(value.device.type, enabled=False):
        yield


@contextmanager
def observe_islands(callback):
    token = _observer.set(callback)
    try:
        yield
    finally:
        _observer.reset(token)


def island_tensor(name, value):
    value = value.float()
    callback = _observer.get()
    if callback is not None:
        callback(name, value)
    return value


class _Linear(torch.autograd.Function):
    @staticmethod
    def forward(ctx, value, weight, bias, tf32):
        ctx.save_for_backward(value, weight)
        ctx.has_bias, ctx.tf32 = bias is not None, tf32
        with matmul_flags(tf32), torch.autocast(value.device.type, enabled=False):
            return F.linear(value.float(), weight.float(), None if bias is None else bias.float())

    @staticmethod
    def backward(ctx, grad):
        value, weight = ctx.saved_tensors
        with matmul_flags(ctx.tf32), torch.autocast(grad.device.type, enabled=False):
            grad = grad.float()
            dx = grad.matmul(weight) if ctx.needs_input_grad[0] else None
            dw = grad.reshape(-1, grad.shape[-1]).T.matmul(value.reshape(-1, value.shape[-1])) if ctx.needs_input_grad[1] else None
            db = grad.reshape(-1, grad.shape[-1]).sum(0) if ctx.has_bias and ctx.needs_input_grad[2] else None
        return dx, dw, db, None


class _Matmul(torch.autograd.Function):
    @staticmethod
    def forward(ctx, left, right):
        ctx.save_for_backward(left, right)
        with matmul_flags(True), torch.autocast(left.device.type, enabled=False):
            return torch.matmul(left, right)

    @staticmethod
    def backward(ctx, grad):
        left, right = ctx.saved_tensors
        with matmul_flags(True), torch.autocast(grad.device.type, enabled=False):
            dl = torch.matmul(grad, right.transpose(-1, -2)).sum_to_size(left.shape) if ctx.needs_input_grad[0] else None
            dr = torch.matmul(left.transpose(-1, -2), grad).sum_to_size(right.shape) if ctx.needs_input_grad[1] else None
        return dl, dr


def linear(value, weight, bias, mode, *, island=False):
    if island:
        with fp32_island(value):
            result = _Linear.apply(value.float(), weight, bias, False)
            return island_tensor('distance_bias_first_layer', result)
    if mode == 'tf32_islands':
        return _Linear.apply(value.float(), weight, bias, True)
    with matmul_flags(False), torch.autocast(value.device.type, dtype=torch.bfloat16):
        return F.linear(value, weight, bias).float()


def matmul(left, right, mode='fp32'):
    if mode == 'fp32':
        return torch.matmul(left, right)
    if mode == 'tf32_islands':
        return _Matmul.apply(left.float(), right.float())
    with matmul_flags(False), torch.autocast(left.device.type, dtype=torch.bfloat16):
        return torch.matmul(left, right).float()


def configure_precision(model, mode='fp32'):
    if mode not in MODES:
        raise ValueError('precision must be one of '+', '.join(MODES))
    from .common import Linear
    for module in model.modules():
        module.precision = mode
        if isinstance(module, Linear):
            module._precision_mode = mode
    # Keep the actual first child of the frozen tiled Sequential, including
    # its Parameter objects, type, keys and checkpoint recomputation path.
    for module in model.modules():
        mlp = getattr(module, 'dist_mlp', None)
        if mlp is not None:
            mlp[0]._precision_island = True
    return model
