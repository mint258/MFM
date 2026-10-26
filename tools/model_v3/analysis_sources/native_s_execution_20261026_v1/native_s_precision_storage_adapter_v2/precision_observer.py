"""Source-bound dense-attention operator interfaces, not accumulator proof."""
from contextlib import contextmanager
import re


@contextmanager
def observe(model,precision,torch,*,device_type,expected_layers):
    from torch.utils._python_dispatch import TorchDispatchMode
    stack=[]; hooks=[]; layers={}; operations=[]; coverage={
        key:0 for key in ('distance_difference','distance_squared','softmax','RBF_exp','native_layer_norm')}
    def need(value,message):
        if not value: raise ValueError(message)
    def tensors(value):
        if isinstance(value,torch.Tensor): return [value]
        if isinstance(value,(tuple,list)): return [item for value0 in value for item in tensors(value0)]
        if isinstance(value,dict): return [item for value0 in value.values() for item in tensors(value0)]
        return []
    def meta(value):
        return dict(shape=list(value.shape),dtype=str(value.dtype),device=str(value.device))
    def pre(name):
        def hook(module,args):
            stack.append(name)
            match=re.fullmatch(r'(?:encoder\.)?backbone\.layers\.(\d+)\.attn',name)
            if match:
                index=int(match.group(1))
                need(index not in layers,'One observed forward cannot contain duplicate attention calls')
                need(len(args)>=3,'Dense-attention x/pos/mask interface not observed')
                x,pos,mask=args[:3]
                batch,n,dim=x.shape; heads=int(module.nheads); width=int(module.d_head)
                need(dim==heads*width and pos.shape==(batch,n,3) and mask.shape==(batch,n),'Dense attention shape contract differs')
                need(x.dtype==pos.dtype==torch.float32 and pos.device.type==device_type,'Coordinates/features must enter as fp32')
                layers[index]=dict(module=name,attention_class=module.__class__.__module__+'.'+module.__class__.__name__,
                    batch=batch,n=n,heads=heads,width=width,inputs=[meta(x),meta(pos),meta(mask)],
                    QK=None,AV=None,softmax=None)
        return hook
    def post(name):
        def hook(module,args,output):
            need(stack and stack[-1]==name,'Operator observation module stack differs')
            stack.pop()
        return hook
    for name,module in model.named_modules():
        hooks.append(module.register_forward_pre_hook(pre(name)))
        hooks.append(module.register_forward_hook(post(name),always_call=True))
    class Mode(TorchDispatchMode):
        def __torch_dispatch__(self,func,types,args=(),kwargs=None):
            result=func(*args,**(kwargs or {})); path=stack[-1] if stack else ''
            outputs=[value for value in tensors(result) if value.is_floating_point()]
            inputs=[value for value in tensors(args) if value.is_floating_point()]
            operation=str(func)
            match=re.search(r'backbone\.layers\.(\d+)\.attn(?:\.|$)',path)
            row=layers.get(int(match.group(1))) if match else None
            def checked_fp32(kind):
                need(outputs and all(value.dtype==torch.float32 and value.device.type==device_type for value in inputs+outputs),
                    kind+' operator interface left fp32/device')
                coverage[kind]+=1
                if coverage[kind]==1 or kind=='softmax':
                    operations.append(dict(region=kind,module=path,operator=operation,
                        inputs=[meta(value) for value in inputs],outputs=[meta(value) for value in outputs]))
            if row is not None and '.dist_mlp' not in path:
                b,h,n,d=row['batch'],row['heads'],row['n'],row['width']
                if operation.startswith('aten.bmm.'):
                    need(len(inputs)==2 and len(outputs)==1,'Dense QK/AV operator arity differs')
                    stage='QK' if row['QK'] is None else 'AV'
                    need(row['AV'] is None,'Extra dense bmm cannot be assigned to QK/AV')
                    expected_dtype=torch.bfloat16 if precision=='bf16' else torch.float32
                    expected_shapes=([(b*h,n,d),(b*h,d,n)],(b*h,n,n)) if stage=='QK' else ([(b*h,n,n),(b*h,n,d)],(b*h,n,d))
                    need([tuple(value.shape) for value in inputs]==expected_shapes[0] and tuple(outputs[0].shape)==expected_shapes[1],
                        'Actual '+stage+' interface shapes differ')
                    need((row['softmax'] is None) if stage=='QK' else (row['softmax'] is not None),
                        'QK/softmax/AV source order differs')
                    need(all(value.dtype==expected_dtype and value.device.type==device_type for value in inputs+outputs),
                        'Actual '+stage+' input/output dtype/device differs')
                    row[stage]=dict(operator=operation,inputs=[meta(v) for v in inputs],outputs=[meta(v) for v in outputs])
                if operation.startswith('aten._softmax.'):
                    need(row['QK'] is not None and row['AV'] is None and row['softmax'] is None,
                        'Softmax source position differs')
                    need(inputs and tuple(inputs[0].shape)==(b,h,n,n),'Softmax shape differs')
                    checked_fp32('softmax'); row['softmax']=operations[-1]
                if operation.startswith('aten.sub.') and outputs and tuple(outputs[0].shape)==(b,n,n,3):
                    checked_fp32('distance_difference')
                if operation.startswith('aten.sum.') and inputs and tuple(inputs[0].shape)==(b,n,n,3):
                    checked_fp32('distance_squared')
            if 'geometry_head' in path and operation.startswith('aten.exp.'):
                checked_fp32('RBF_exp')
            if operation.startswith('aten.native_layer_norm.'):
                checked_fp32('native_layer_norm')
            if ('.dist_mlp' in path or 'geometry_head' in path or 'norm' in path) and outputs:
                need(all(value.dtype==torch.float32 and value.device.type==device_type for value in outputs),
                    'Geometry/distance/RBF/normalization operator output left fp32')
            return result
    result=dict(schema='native_S_selective_precision_operator_interfaces_v2',precision=precision,actual_device=device_type,
        layers=layers,coverage=coverage,coverage_operations=operations,status='NOT_OBSERVED',
        parameter_dtype='torch.float32',observation_only=True,CUDA_acceptance=False,
        semantics='Actual operator input/output interfaces for one observed forward; not kernel accumulator precision or all future TRAIN shapes',
        unsupported_attention_backend_requires_separate_observation=True)
    try:
        need(all(parameter.dtype==torch.float32 for parameter in model.parameters()),'Parameters left fp32')
        with Mode(): yield result
        complete=set(layers)==set(range(expected_layers)) and all(row['QK'] is not None and row['AV'] is not None
            and row['softmax'] is not None for row in layers.values()) and all(coverage.values())
        result['layers']={str(key):value for key,value in sorted(layers.items())}
        result['status']='OBSERVED_OPERATOR_INTERFACES' if complete else 'NOT_OBSERVED'
    finally:
        for hook in hooks: hook.remove()
