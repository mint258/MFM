"""Analysis-only local copies and transparent, short-lived module-boundary hooks."""
from __future__ import annotations
from copy import deepcopy
import hashlib
import json
from types import MethodType
import torch
from torch_geometric.utils import to_dense_batch

def need(ok,message):
    if not ok:raise ValueError(message)

def leaves(value):
    if isinstance(value,torch.Tensor):return [value]
    need(isinstance(value,(tuple,list)), 'Only declared tensor/tuple module outputs supported')
    return [leaf for item in value for leaf in leaves(item)]

def promote(value):
    if isinstance(value,torch.Tensor):
        need(not value.is_floating_point() or value.dtype==torch.float32,'Only actual F32 floating inputs supported')
        return value.double() if value.is_floating_point() else value
    if isinstance(value,tuple):return tuple(promote(item) for item in value)
    if isinstance(value,list):return [promote(item) for item in value]
    if isinstance(value,dict):return {key:promote(item) for key,item in value.items()}
    need(value is None or isinstance(value,(int,float,bool,str)), 'Unknown actual module context')
    return value

def state_digest(module,reference):
    rows={}
    for key,value in module.state_dict().items():
        rows[key]=reference.tensor_header(value) if isinstance(value,torch.Tensor) else value
    return hashlib.sha256(json.dumps(rows,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def strict_local_reference(module,reference):
    """No initializer or original mutation. Explicitly algorithm+dtype, not dtype-only."""
    need(type(module).__name__ in ('LayerNorm','DenseFFN','DenseGeoSelfAttention','SharedPairAttention',
                                  'TiledDistanceMLP','SharedGaussianPairEncoder'),'Unsupported local reference class')
    need(not module.training,'Only actual eval module supported')
    original=module.state_dict();clone=deepcopy(module)
    result=clone.load_state_dict(original,strict=True)
    need(not result.missing_keys and not result.unexpected_keys,'Strict local state load failed')
    reference._same_state(original,clone.state_dict())
    before=state_digest(module,reference)
    mode_maps=[]
    for name,item in clone.named_modules():
        for field in ('numeric_mode','attention_aggregation_mode'):
            if hasattr(item,field):
                old=getattr(item,field)
                need(old in ('compensated_fp32_v1','centered_fp32_v1','legacy'),'Unknown numeric option')
                setattr(item,field,'legacy');mode_maps.append({'module':name,'field':field,'original':old,'analysis':'legacy'})
    clone.double().eval()
    for key,value in original.items():
        other=clone.state_dict()[key]
        if isinstance(value,torch.Tensor):
            need(reference.tensor_header(value)==reference.tensor_header(other.float() if value.is_floating_point() else other),
                 'Local lossless state promotion/castback failed: '+key)
            need(not value.is_floating_point() or value.dtype==torch.float32 and other.dtype==torch.float64,
                 'Reference state dtype differs')
    if type(clone).__name__=='SharedGaussianPairEncoder':
        need(clone.options.cutoff is None,'Fixed48 global/no-cutoff scope only')
        clone.forward=MethodType(reference.gaussian_reference_forward,clone)
    if type(clone).__name__ in ('DenseGeoSelfAttention','SharedPairAttention'):
        need(clone.use_radius_mask is False,'Fixed48 global attention only')
    need(state_digest(module,reference)==before,'Reference creation mutated the original module')
    return clone,{'original_class':type(module).__name__,'strict_state_sha256':before,
        'lossless_promoted_state_sha256':state_digest(clone,reference),'metadata_maps':mode_maps,
        'scope':'INDEPENDENT_REAL_FORMULA_ALGORITHM_AND_FP64_NOT_DTYPE_ONLY',
        'gaussian_forward_source_reused':type(clone).__name__=='SharedGaussianPairEncoder'}

def population(value,kind,port,mask):
    """Return physical rows only; original/replay bit gates still cover raw padding."""
    need(value.is_floating_point() and value.isfinite().all(),'Nonfinite/unknown local output')
    value=value.detach().cpu()
    nodes=int(mask.sum());pair_mask=mask[:,:,None]&mask[:,None,:];pairs=int(pair_mask.sum())
    if kind=='attention' and port==1:
        need(value.ndim==4 and value.shape[0]==mask.shape[0] and value.shape[2:]==(mask.shape[1],mask.shape[1]),
             'Dense attention-weight output shape differs')
        selected=value.permute(0,2,3,1)[pair_mask]
        return selected,{'population':'VALID_QUERY_KEY_PAIRS_BY_HEAD','rows':pairs,'channels':value.shape[1],
                         'native_nodes':nodes,'native_nodes_by_graph':mask.sum(1).tolist(),'includes_diagonal':True}
    if kind in ('distance_mlp','pair_encoder'):
        need(value.shape[:3]==(mask.shape[0],mask.shape[1],mask.shape[1]),'Pair module shape differs')
        selected=value[pair_mask]
        if selected.ndim==1:selected=selected[:,None]
        return selected,{'population':'VALID_NATIVE_ORDERED_PAIRS','rows':pairs,'channels':selected.shape[-1],
                         'native_nodes':nodes,'native_nodes_by_graph':mask.sum(1).tolist(),'includes_diagonal':True}
    need(value.ndim==3 and value.shape[:2]==mask.shape,'Node module shape differs')
    return value[mask],{'population':'VALID_NATIVE_PHYSICAL_VIEW_NODES','rows':nodes,'channels':value.shape[-1],
                        'native_nodes':nodes,'native_nodes_by_graph':mask.sum(1).tolist(),'clean44_only':False}

class LocalModules:
    """Retain refs in hooks; remove ALL own handles before any local module replay."""
    def __init__(self,backbone,reference,cache):
        self.backbone,self.reference,self.cache=backbone,reference,cache
        self.modules={};self.records={};self.masks={};self.handles=[];self.armed=False
        need(len(backbone.layers)==6,'All six layers required')
        for index,layer in enumerate(backbone.layers):
            prefix='layer%d.'%index
            for name,kind in (('norm1','node'),('norm2','node'),('attn','attention'),('ffn','node')):
                self.modules[prefix+name]=(getattr(layer,name),kind,index)
            if type(layer.attn).__name__=='DenseGeoSelfAttention':
                need(type(layer.attn.dist_mlp).__name__=='TiledDistanceMLP','Original C1-0 memory path required')
                self.modules[prefix+'distance_mlp']=(layer.attn.dist_mlp,'distance_mlp',index)
            else:need(type(layer.attn).__name__=='SharedPairAttention','Unsupported attention class')
        self.modules['out_norm']=(backbone.out_norm,'node',None)
        if hasattr(backbone,'pair_encoder'):
            self.modules['shared_pair_encoder']=(backbone.pair_encoder,'pair_encoder',None)
        need(len(self.modules)==(26 if hasattr(backbone,'pair_encoder') else 31),'Complete local module set required')
    def arm(self):
        need(not self.armed and not self.handles,'Observer already armed')
        self.armed=True
        for index,layer in enumerate(self.backbone.layers):
            def before_layer(module,args,index=index):
                need(self.armed and index not in self.masks,'Layer mask coverage differs')
                self.masks[index]=args[-1]
            self.handles.append(layer.register_forward_pre_hook(before_layer))
        for name,(module,kind,index) in self.modules.items():
            def before(module,args,kwargs,name=name):
                need(self.armed and name not in self.records and not kwargs,'Unexpected module call multiplicity/kwargs')
                # Actual GPU tensor objects, including original stride/storage_offset. No copy here.
                self.records[name]={'args':args,'kwargs':kwargs}
            def after(module,args,kwargs,output,name=name):
                need(self.armed and name in self.records,'Missing prehook')
                self.records[name]['output']=output
                # No replacement output.
            self.handles.append(module.register_forward_pre_hook(before,with_kwargs=True))
            self.handles.append(module.register_forward_hook(after,with_kwargs=True))
    def disarm(self):
        for handle in self.handles:handle.remove()
        self.handles.clear();self.armed=False
    def process(self,stages):
        need(not self.armed and not self.handles and set(self.records)==set(self.modules),'Disarmed full coverage required')
        need(set(self.masks)==set(range(6)),'All six actual layer masks required')
        data=stages['input'];_,mask=to_dense_batch(data.batch,data.batch,fill_value=0)
        need(all(self.reference.tensor_header(value)==self.reference.tensor_header(mask)
                 for value in self.masks.values()),'Actual layer mask differs from original physical layout')
        rows={}
        for name,(module,kind,index) in self.modules.items():
            record=self.records[name];args=record['args']
            need(not module.training and not torch.is_grad_enabled() and torch.is_inference_mode_enabled()
                 and not torch.is_autocast_enabled('cuda'),'Actual eval/inference/F32 noAMP context required')
            need(all(not isinstance(item,torch.nn.Dropout) or not item.training or item.p==0 for item in module.modules()),
                 'Active dropout is unsupported')
            state_before=state_digest(module,self.reference)
            original=leaves(record['output'])
            # Original object inputs are reused; no reconstruction/contiguous/copy before this call.
            replay=leaves(module(*args,**record['kwargs']))
            need(len(original)==len(replay),'Replay output tree differs')
            controls=[{'original':self.reference.tensor_header(a),'replayed':self.reference.tensor_header(b),
                       'bitwise_equal':self.reference.tensor_header(a)==self.reference.tensor_header(b)}
                      for a,b in zip(original,replay)]
            if name not in self.cache:self.cache[name]=strict_local_reference(module,self.reference)
            clone,mapping=self.cache[name]
            reference_args=promote(args);reference_kwargs=promote(record['kwargs'])
            reference_values=leaves(clone(*reference_args,**reference_kwargs))
            need(len(reference_values)==len(original) and all(v.dtype==torch.float64 for v in reference_values),
                 'Reference output tree/dtype differs')
            ports=[]
            for port,(actual,ref) in enumerate(zip(original,reference_values)):
                actual_values,denominator=population(actual,kind,port,mask)
                ref_values,ref_denominator=population(ref,kind,port,mask)
                need(denominator==ref_denominator and actual_values.shape==ref_values.shape,'Physical population differs')
                ports.append({'actual':actual_values,'reference':ref_values,'denominator':denominator,
                              'raw_actual':self.reference.tensor_header(actual),'raw_reference':self.reference.tensor_header(ref)})
            # Input drift uses the same physical rows. Positions retain their vector law separately.
            inputs=[]
            if kind=='attention':
                input_kinds=['node','position'] if type(module).__name__=='DenseGeoSelfAttention' else ['node','pair','pair']
            elif kind=='pair_encoder':input_kinds=['position']
            elif kind=='distance_mlp':input_kinds=['pair']
            else:input_kinds=['node']
            for value,input_kind in zip(args,input_kinds):
                value=value.detach().cpu()
                if input_kind=='pair':
                    selected=value[mask[:,:,None]&mask[:,None,:]]
                    if selected.ndim==1:selected=selected[:,None]
                else:selected=value[mask]
                inputs.append({'kind':input_kind,'values':selected,'raw':self.reference.tensor_header(value)})
            need(state_digest(module,self.reference)==state_before,'Local replay/reference mutated original state')
            need(state_digest(clone,self.reference)==mapping['lossless_promoted_state_sha256'],'Reference module state changed')
            rows[name]={'kind':kind,'layer':index,'ports':ports,'inputs':inputs,'replay':controls,
                'state_mapping':mapping,'context':{'training':module.training,'grad_enabled':torch.is_grad_enabled(),
                    'inference_mode':torch.is_inference_mode_enabled(),'autocast_cuda':torch.is_autocast_enabled('cuda'),
                    'input_headers':[{'dtype':str(value.dtype),'shape':list(value.shape),'stride':list(value.stride()),
                        'storage_offset':value.storage_offset(),'device':str(value.device),
                        'value_header':self.reference.tensor_header(value)} for value in args if isinstance(value,torch.Tensor)],
                    'reference_input_headers':[{'dtype':str(value.dtype),'shape':list(value.shape),'stride':list(value.stride()),
                        'storage_offset':value.storage_offset(),'device':str(value.device)} for value in reference_args if isinstance(value,torch.Tensor)],
                    'matmul_precision':torch.get_float32_matmul_precision(),'allow_tf32_matmul':torch.backends.cuda.matmul.allow_tf32,
                    'allow_tf32_cudnn':torch.backends.cudnn.allow_tf32,
                    'replay_uses_original_input_objects':True,'hooks_removed_before_replay':True,
                    'numeric_mode':getattr(module,'numeric_mode',None),
                    'attention_aggregation_mode':getattr(module,'attention_aggregation_mode',None),
                    'module_flags':{key:getattr(module,key,None) for key in ('dim','nheads','d_head','use_dist_bias','use_radius_mask','radius','eps','normalized_shape','pair_rows')}}}
        self.records.clear();self.masks.clear()
        return rows
    def close(self):
        self.disarm();self.records.clear();self.masks.clear()