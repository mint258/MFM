"""Optional C-based mean/conformer targets; no source values or fitted D4 changes."""
from dataclasses import replace
import json
from pathlib import Path
import numpy as np
import torch
from .v31_training import element_offset


def definition(path):
    if path is None:return {}
    if isinstance(path,dict):return path
    return json.loads(Path(path).read_text())


def transform_target(target,mu,count,parameters,offset):
    valid=target.valid.copy() & np.isfinite(target.raw)
    y=target.raw.astype(np.float64)-offset
    first=np.full_like(y,(mu-parameters['c1'])/parameters['s1'])
    second=(y-mu)/parameters['s2']
    values=np.concatenate([first,second],axis=-1)
    mask=np.concatenate([np.isfinite(first)&(count>0),np.isfinite(second)&(count>=2)&valid],axis=-1)
    raw=np.where(mask,values,np.nan)
    return replace(target,raw=raw,values=raw.astype(np.float32),valid=mask)


def restore_predictions(value,parameters,offset):
    return offset+parameters['c1']+parameters['s1']*value[...,0:1]+parameters['s2']*value[...,1:2]


class ConformerDecomposition:
    def __init__(self,path,split,directory,view):
        self.parameters=definition(path);self.selected=tuple(self.parameters['selected_fields'])
        self.reference=self.parameters['splits'][split]
        if Path(self.reference['directory']).resolve()!=Path(directory).resolve():raise ValueError('D means/D6 directory differs')
        self._means=self._counts=None
        self.perturbed={f['name'] for f in view.fields if f.get('registry_id') in (623,624,625)}
        self.columns={n:i for i,n in enumerate(self.parameters['candidate_fields'])}
    def __getstate__(self):
        result=dict(self.__dict__);result['_means']=result['_counts']=None;return result
    def apply(self,sample):
        if self._means is None:
            self._means=np.load(self.reference['means'],mmap_mode='r')
            self._counts=np.load(self.reference.get('counts',self.reference.get('valid_counts')),mmap_mode='r')
        mi=sample['molecule_index'];targets=dict(sample['targets'])
        for name in self.selected:
            if name not in targets:continue
            column=self.columns[name];offset=element_offset(sample['Z'],self.parameters['normalizations'][name])
            targets[name]=transform_target(targets[name],float(self._means[mi,column]),int(self._counts[mi,column]),self.parameters['fields'][name],offset)
            if name in self.perturbed and (sample['pos_perturbed'] is None or not np.isfinite(sample['pos_perturbed']).all()):
                targets[name].valid[:]=False;targets[name].raw[:]=np.nan;targets[name].values[:]=np.nan
        sample['targets']=targets;return sample


def install_heads(model,parameters,forms):
    """Keep unchanged head initialization; replace only eligible graph H1 outputs."""
    selected=parameters.get('selected_fields',[])
    with torch.random.fork_rng(devices=[]):
        for name in selected:
            if model.heads.forms[name]!='H1' or model.head_by_name[name].level!='graph' or model.head_by_name[name].representation!='scalar':raise ValueError('D requires original graph H1 scalar heads')
            key=model.heads.keys[name];old=model.heads.field_heads[key]
            if not isinstance(old,torch.nn.Linear):raise ValueError('D requires linear H1')
            head=type(old)(old.in_features,2,bias=old.bias is not None)
            with torch.no_grad():
                head.weight[0].copy_(old.weight[0])
                if old.bias is not None:head.bias[0].copy_(old.bias[0])
            model.heads.field_heads[key]=head


def decomposition_loss(model,predictions,samples,groups,fields,fixed_full_condition=False):
    from .v3_losses import V3LossResult
    active=model.registry.enabled(groups,fields);names=[f.name for f in active]
    ordinary=[n for n in names if n not in model.decomposition_fields]
    if ordinary:
        base=model.loss(predictions,samples,groups=groups,fields=ordinary,fixed_full_condition=False)
        values=dict(base.fields);counts=dict(base.counts)
    else:values={};counts={}
    prepared=getattr(samples,'prepared',{}).get('decomposition_targets',{})
    for name in names:
        if name not in model.decomposition_fields:continue
        prediction=predictions[name]
        if prediction.ndim!=2 or prediction.shape[1]!=2:raise ValueError('D requires two actual outputs')
        if name in prepared:target,valid=prepared[name]
        else:
            target=torch.as_tensor(np.concatenate([s['targets'][name].values for s in samples]))
            valid=torch.as_tensor(np.concatenate([s['targets'][name].valid for s in samples]))
        target=target.to(prediction.device);valid=valid.to(prediction.device)
        counts[name]=int(valid.any(-1).sum())
        losses=[]
        for component in range(2):
            mask=valid[:,component]
            losses.append((prediction[mask,component].float()-target[mask,component]).square().mean() if mask.any() else prediction.new_zeros(()))
        values[name]=.5*(losses[0]+losses[1])
    zero=next(iter(predictions.values())).new_zeros(())
    group_values={};observed={}
    for group in groups:
        heads=[n for n in values if model.head_by_name[n].group==group and counts[n]>0]
        observed[group]=len(heads)
        denominator=sum(f.group==group for f in model.head_registry.fields) if fixed_full_condition else len(heads)
        group_values[group]=sum((values[n] for n in heads),zero)/denominator if denominator else zero
    total=sum(group_values.values(),zero)/len(groups)
    return V3LossResult(total,values,group_values,counts,observed,tuple(groups))