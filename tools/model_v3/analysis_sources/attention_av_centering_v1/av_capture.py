"""Scoped actual-attention capture. Hooks/mode retain refs and return originals."""
from contextlib import contextmanager
import hashlib
import torch
from torch import nn
from torch.overrides import TorchFunctionMode

def require(value, message):
    if not value:
        raise ValueError(message)

def header(value):
    raw = value.detach().cpu().contiguous()
    return {'shape': list(value.shape), 'stride': list(value.stride()),
            'storage_offset': value.storage_offset(), 'dtype': str(value.dtype),
            'device': str(value.device), 'bytes': raw.numel()*raw.element_size(),
            'sha256': hashlib.sha256(raw.numpy().tobytes()).hexdigest()}

class _ActualCalls(TorchFunctionMode):
    def __init__(self, owner):
        self.owner = owner

    def __torch_function__(self, func, types, args=(), kwargs=None):
        kwargs = {} if kwargs is None else kwargs
        result = func(*args, **kwargs)  # Exactly one original call; never replace output.
        frame = self.owner.active
        if frame is not None and func is torch.softmax:
            require(frame['softmax'] is None and frame['matmuls'] == 1, 'Unexpected actual softmax sequence')
            dim = kwargs.get('dim', args[1] if len(args) > 1 else None)
            require(dim == -1 and isinstance(result, torch.Tensor), 'Actual last-axis softmax required')
            frame['softmax'] = (args[0], result)
        elif frame is not None and func is torch.matmul:
            frame['matmuls'] += 1
            if frame['softmax'] is None:
                require(frame['matmuls'] == 1, 'Unexpected pre-softmax matmul')
            else:
                require(frame['matmuls'] == 2 and len(args) == 2 and not kwargs
                        and args[0] is frame['softmax'][1], 'Original AV operands/order differ')
                frame['av'] = (args[0], args[1], result)
        return result

class AVCapture:
    def __init__(self, attentions):
        from phychem_mfm.model.attention import DenseGeoSelfAttention
        from phychem_mfm.model.v3_architecture import SharedPairAttention
        self.active, self.pending, self.enabled = None, [], False
        self.handles = []
        self.count = len(attentions)
        try:
            for index, module in enumerate(attentions):
                require(type(module) in (DenseGeoSelfAttention, SharedPairAttention),
                        'Only the two original coupled attention classes are supported')
                def before(actual, inputs, index=index):
                    require(self.enabled and self.active is None and len(self.pending) == index,
                            'Unexpected/nested attention call or layer order')
                    require(not actual.training and actual.use_radius_mask is False,
                            'Only original eval/global attention is supported')
                    drop = actual.attn_drop
                    require(type(drop) is nn.Identity or (type(drop) is nn.Dropout
                            and (drop.p == 0 or not drop.training)), 'Effective attention dropout must be disabled')
                    require(len(inputs) in (3,4) and inputs[0].dtype == torch.float32
                            and inputs[-1].dtype == torch.bool and inputs[0].device.type == 'cuda',
                            'Actual FP32 CUDA input/native bool mask required')
                    self.active = {'layer': index, 'class': type(actual).__name__, 'mask': inputs[-1],
                        'heads': actual.nheads, 'head_dim': actual.d_head,
                        'input_shape': list(inputs[0].shape), 'softmax': None, 'av': None, 'matmuls': 0,
                        'dropout': {'class': type(drop).__name__, 'training': drop.training,
                                    'p': drop.p if type(drop) is nn.Dropout else 0.0},
                        'arithmetic_flags': {'autocast':torch.is_autocast_enabled('cuda'),
                            'tf32':torch.backends.cuda.matmul.allow_tf32,
                            'matmul_precision':torch.get_float32_matmul_precision(),
                            'deterministic':torch.are_deterministic_algorithms_enabled()},
                        'radius_mask_enabled': actual.use_radius_mask, 'declared_radius': actual.radius}
                def after(actual, inputs, output, index=index):
                    frame = self.active
                    require(frame is not None and frame['layer'] == index and frame['av'] is not None
                            and frame['softmax'] is not None and frame['matmuls'] == 2,
                            'Actual one-QK/one-softmax/one-AV coverage missing')
                    p, v, av = frame['av']
                    require(p.dtype == v.dtype == av.dtype == frame['softmax'][0].dtype == torch.float32,
                            'Hidden mixed precision is unsupported')
                    self.pending.append(frame)
                    self.active = None
                    # Returning None preserves the original attention output object.
                self.handles.append(module.register_forward_pre_hook(before))
                self.handles.append(module.register_forward_hook(after))
        except BaseException:
            self.close()
            raise

    @contextmanager
    def scope(self):
        require(not self.enabled and self.active is None and not self.pending, 'Unconsumed capture')
        self.enabled = True
        try:
            with _ActualCalls(self):
                yield
        finally:
            self.enabled = False

    def take_cpu(self):
        # Called only after the ENTIRE original model forward has returned.
        require(not self.enabled and self.active is None and len(self.pending) == self.count,
                'Incomplete actual forward AV coverage')
        rows = []
        for frame in self.pending:
            logits, p = frame['softmax']; _, v, output = frame['av']; mask = frame['mask']
            require(p.ndim == v.ndim == output.ndim == logits.ndim == 4
                    and p.shape == logits.shape and p.shape[-1] == p.shape[-2]
                    and p.shape[:2] == v.shape[:2] and p.shape[-1] == v.shape[-2]
                    and output.shape == v.shape and mask.shape == (p.shape[0],p.shape[-1]),
                    'Actual attention operand shapes differ')
            mask_cpu = mask.detach().cpu().contiguous().clone()
            require(bool(mask_cpu.any(-1).all()), 'UNSUPPORTED_ALL_MASKED_OR_EMPTY_GRAPH')
            payloads, headers = {}, {}
            for name, value in (('p',p),('v',v),('logits',logits),('output',output)):
                require(value.device.type == 'cuda' and value.isfinite().all(), 'Nonfinite actual operand')
                headers[name] = header(value)
                payloads[name] = value.detach().cpu().contiguous().clone()
            require(bool((payloads['p'] >= 0).all()), 'Negative softmax weight')
            invalid = (~mask_cpu)[:,None,None,:].expand_as(payloads['p'])
            require(bool((payloads['logits'][invalid] == -1e9).all())
                    and bool((payloads['p'][invalid] == 0).all()), 'Actual masked-key semantics differ')
            meta = {key: value for key,value in frame.items() if key not in ('mask','softmax','av')}
            meta.update(headers=headers, valid_queries=int(mask_cpu.sum()),
                        padded_queries=int((~mask_cpu).sum()), all_masked_valid_queries=0,
                        original_mask_header=header(mask), native_graph_atom_counts=mask_cpu.sum(-1).tolist(),
                        key_mask_policy='original finite -1e9; padded query removed only by original output mask')
            rows.append({'meta': meta, 'mask': mask_cpu, 'values': payloads})
        self.pending.clear()
        return rows

    def close(self):
        for handle in self.handles:
            handle.remove()
        self.handles.clear(); self.pending.clear(); self.active = None; self.enabled = False

def restore_operand(value, description):
    """Relocate saved exact values while recreating the original view layout."""
    shape, strides, offset = description['shape'], description['stride'], description['storage_offset']
    require(value.dtype == torch.float32 and list(value.shape) == shape
            and all(x >= 0 for x in strides) and offset >= 0, 'Unsupported original view layout')
    length = offset+1+sum((n-1)*s for n,s in zip(shape,strides))
    require(0 < length <= 8*1024**2, 'Bounded original view storage required')
    storage = torch.empty(length, dtype=torch.float32, device=description['device'])
    result = storage.as_strided(shape,strides,offset)
    result.copy_(value)
    require(header(result) == description, 'Restored original dtype/stride/offset/value differs')
    return result
