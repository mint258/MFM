"""Typed logical-bit signatures; unsupported values never imply equivalence."""
from __future__ import annotations
import hashlib,json,math,struct
MAX_DEPTH=32;MAX_NODES=100000;MAX_LEAF_BYTES=64<<20;MAX_LOGICAL_BYTES=128<<20;MAX_JSON_BYTES=1<<20

def canonical(value):return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
def sha(value):return hashlib.sha256(value).hexdigest()
def typename(value):return type(value).__module__+'.'+type(value).__qualname__

def field_signature(value):
    seen=set();unknown=[];nodes=0;logical_bytes=0
    def unsupported(path,item,reason):
        unknown.append({'path':path,'type':typename(item),'reason':reason})
        return {'kind':'UNKNOWN','type':typename(item),'reason':reason}
    def raw_node(path,item,kind,raw,**meta):
        nonlocal logical_bytes
        size=len(raw)
        if size>MAX_LEAF_BYTES or logical_bytes+size>MAX_LOGICAL_BYTES:return unsupported(path,item,'LOGICAL_BYTE_SOFTWARE_BOUND')
        logical_bytes+=size;return {'kind':kind,'type':typename(item),'bytes':size,'sha256':sha(raw),**meta}
    def visit(item,path,depth):
        nonlocal nodes
        nodes+=1
        if nodes>MAX_NODES:raise ValueError('NODE_SOFTWARE_BOUND_UNKNOWN')
        if depth>MAX_DEPTH:return unsupported(path,item,'DEPTH_SOFTWARE_BOUND')
        if item is None:return {'kind':'none','type':'builtins.NoneType'}
        if type(item) is bool:return {'kind':'bool','value':item}
        if type(item) is int:return {'kind':'int','value_decimal':str(item)}
        if type(item) is float:
            return {'kind':'float','IEEE754_binary64_big_endian_hex':struct.pack('>d',item).hex(),
              'class':'NaN' if math.isnan(item) else 'Infinity' if math.isinf(item) else 'finite'}
        if type(item) is complex:return {'kind':'complex','real':visit(item.real,path+'.real',depth+1),'imag':visit(item.imag,path+'.imag',depth+1)}
        if type(item) is str:
            raw=item.encode('utf-8');return raw_node(path,item,'str',raw,**({'value':item} if len(raw)<=4096 else {}))
        if type(item) in (bytes,bytearray):return raw_node(path,item,'bytes',bytes(item))
        import numpy as np
        import torch
        if isinstance(item,torch.Tensor):
            if type(item) is not torch.Tensor:return unsupported(path,item,'TENSOR_SUBCLASS_SEMANTICS_UNAUDITED')
            if item.layout!=torch.strided or item.is_quantized:return unsupported(path,item,'UNSUPPORTED_TENSOR_LAYOUT_OR_QUANTIZATION')
            if item.is_conj() or item.is_neg():return unsupported(path,item,'UNSUPPORTED_LOGICAL_TENSOR_VIEW_FLAGS')
            n=int(item.numel())*int(item.element_size())
            if n>MAX_LEAF_BYTES or logical_bytes+n>MAX_LOGICAL_BYTES:return unsupported(path,item,'LOGICAL_BYTE_SOFTWARE_BOUND')
            try:
                raw=item.detach().cpu().contiguous().reshape(-1).view(torch.uint8).numpy().tobytes(order='C')
                return raw_node(path,item,'torch_tensor',raw,dtype=str(item.dtype),shape=list(item.shape),layout=str(item.layout),
                    stride=list(item.stride()),requires_grad=bool(item.requires_grad),device_type=item.device.type,
                    encoding='logical_C_order_original_dtype_bits_no_numeric_cast')
            except Exception as exc:return unsupported(path,item,'TENSOR_BIT_VIEW_UNSUPPORTED:'+type(exc).__name__)
        if isinstance(item,np.ndarray):
            if type(item) is not np.ndarray or item.dtype.hasobject:return unsupported(path,item,'UNSUPPORTED_NUMPY_SUBCLASS_OR_OBJECT_DTYPE')
            if item.nbytes>MAX_LEAF_BYTES or logical_bytes+item.nbytes>MAX_LOGICAL_BYTES:return unsupported(path,item,'LOGICAL_BYTE_SOFTWARE_BOUND')
            return raw_node(path,item,'numpy_array',item.tobytes(order='C'),dtype=item.dtype.str,dtype_descr=repr(item.dtype.descr),shape=list(item.shape),
                encoding='logical_C_order_original_dtype_bits_no_numeric_cast')
        if isinstance(item,np.generic):
            if item.dtype.hasobject:return unsupported(path,item,'UNSUPPORTED_NUMPY_OBJECT_SCALAR')
            return raw_node(path,item,'numpy_scalar',item.tobytes(),dtype=item.dtype.str,dtype_descr=repr(item.dtype.descr),shape=[])
        identity=id(item)
        if identity in seen:return unsupported(path,item,'CYCLIC_CONTAINER')
        from torch_geometric.data import Data
        is_data=isinstance(item,Data)
        if is_data or type(item) in (dict,list,tuple,set,frozenset):
            seen.add(identity)
            try:
                if is_data:
                    data=item.to_dict()
                    return {'kind':'pyg_Data_to_dict','type':typename(item),'coverage':'exact_to_dict_fields_only','fields':visit(data,path+'.to_dict',depth+1)}
                if type(item) is dict:
                    return {'kind':'dict','type':typename(item),'entries':[{'key':visit(k,path+'.key['+str(i)+']',depth+1),
                        'value':visit(v,path+'.value['+str(i)+']',depth+1)} for i,(k,v) in enumerate(item.items())]}
                values=[visit(v,path+'['+str(i)+']',depth+1) for i,v in enumerate(item)]
                if type(item) in (set,frozenset):values.sort(key=canonical)
                return {'kind':type(item).__name__,'type':typename(item),'items':values}
            finally:seen.remove(identity)
        return unsupported(path,item,'UNSUPPORTED_PYTHON_TYPE_NO_REPR_OR_PICKLE_FALLBACK')
    try:tree=visit(value,'$',0);body=canonical(tree)
    except Exception as exc:
        tree=unsupported('$',value,'SIGNATURE_UNSUPPORTED_OR_BOUND:'+type(exc).__name__);body=canonical(tree)
    if len(body)>MAX_JSON_BYTES:
        unknown.append({'path':'$','type':typename(value),'reason':'SIGNATURE_JSON_SOFTWARE_BOUND'})
        tree={'kind':'UNKNOWN','type':typename(value),'reason':'SIGNATURE_JSON_SOFTWARE_BOUND','complete_tree_bytes':len(body)};body=canonical(tree)
    return {'schema':'TYPED_LOGICAL_BIT_FIELD_SIGNATURE_V1','status':'COMPLETE_TYPED_SIGNATURE' if not unknown else 'UNKNOWN_FIELDS_NOT_EQUIVALENCE',
      'tree':tree,'tree_sha256':sha(body),'unknown_fields':unknown[:256],'unknown_fields_total':len(unknown),'unknown_list_truncated':len(unknown)>256,
      'nodes_observed':nodes,'logical_bytes_hashed':logical_bytes,'numeric_cast_or_object_repickle':False}

def compare_signatures(expected,actual):
    if expected['status']!='COMPLETE_TYPED_SIGNATURE' or actual['status']!='COMPLETE_TYPED_SIGNATURE':return 'UNKNOWN_NOT_EQUIVALENT'
    return 'EXACT_TYPED_FIELD_BITS_MATCH' if expected['tree']==actual['tree'] and expected['tree_sha256']==actual['tree_sha256'] else 'FIELD_SIGNATURE_DRIFT'
