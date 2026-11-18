"""Registered F1 physical heads with one PM7/xTB method embedding."""
import torch
from torch import nn
from ..model.common import Linear
from ..model.v3_heads import _DipoleHead,_pool


class PhysicalFidelityHeads(nn.Module):
    """One core per registered physical pair; targets and D4 stay unchanged."""
    def __init__(self,pairs,selections,head_by_name,*,atom_dim,scalar_dim,hidden_dim=64,method_dim=8):
        super().__init__()
        if method_dim!=8:raise ValueError('Registered F1 method dimension is8')
        self.method_embedding=nn.Embedding(2,method_dim)
        self.heads=nn.ModuleDict();self.bindings={};self.vector_heads=set()
        for pair in pairs:
            key=pair['quantity'];members=[]
            for method,side in enumerate(('PM7_fields','xTB_fields')):
                names=pair[side]
                physical={selections[name][0] for name in names}
                if len(physical)!=1:raise ValueError('A fidelity member must identify one physical head')
                name=physical.pop();spec=head_by_name[name]
                if spec.level!='graph' or spec.representation not in ('scalar','vector'):
                    raise ValueError('Registered pairs require molecular scalar or vector heads')
                members.append((name,spec,method))
            a,b=members
            if (a[1].level,a[1].representation,a[1].prediction_width)!=(b[1].level,b[1].representation,b[1].prediction_width):
                raise ValueError('Fidelity physical head dimensions differ')
            if a[1].representation=='vector':
                self.heads[key]=_DipoleHead(atom_dim+method_dim,hidden_dim,False)
                self.vector_heads.add(key)
            else:self.heads[key]=Linear(scalar_dim+method_dim,a[1].prediction_width)
            for name,spec,method in members:
                if name in self.bindings:raise ValueError('A physical head has more than one fidelity pairing')
                self.bindings[name]=(key,method)

    def forward(self,h,batch,pos,*,selected,graph_latent=None):
        graphs=int(batch.max())+1
        scalars=graph_latent if graph_latent is not None else _pool(h,batch,graphs,'mean')
        result={}
        for name in selected:
            if name not in self.bindings:continue
            key,method=self.bindings[name];core=self.heads[key]
            features=h if key in self.vector_heads else scalars
            embedding=self.method_embedding.weight[method].to(features.dtype).expand(len(features),-1)
            features=torch.cat((features,embedding),-1)
            result[name]=(core(features.float(),pos.float(),batch,graphs) if key in self.vector_heads else core(features))
        return result
