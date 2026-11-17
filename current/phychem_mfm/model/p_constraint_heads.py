"""Taskbook T2 constrained atom heads, enabled only for the frozen-panel pass list."""
import torch
from torch import nn
from torch.nn import functional as F

K=14.3996
A=1.0

def charge_equilibrium(chi,u,pos,batch,total_charge):
    pieces=[]
    with torch.autocast(device_type=pos.device.type,enabled=False):
        for molecule in range(int(batch.max())+1):
            rows=batch==molecule
            p=pos[rows].double();n=len(p)
            distance2=(p[:,None,:]-p[None,:,:]).square().sum(-1)
            hardness=K/A+F.softplus(u[rows].double().reshape(-1))
            interaction=K/torch.sqrt(distance2+A*A)
            matrix=interaction+torch.diag(hardness-K/A)
            ones=matrix.new_ones((n,1))
            system=torch.cat((torch.cat((matrix,ones),1),torch.cat((ones.T,matrix.new_zeros((1,1))),1)),0)
            rhs=torch.cat((-chi[rows].double().reshape(-1),matrix.new_tensor([total_charge])))
            pieces.append(torch.linalg.solve(system,rhs)[:n,None])
    return torch.cat(pieces,0).to(chi.dtype)

def fukui_projection(s,batch):
    values=[]
    for molecule in range(int(batch.max())+1):
        original=s[batch==molecule]
        x=original.double()
        value=x+(1-x.sum(0,keepdim=True))/len(x)
        values.append(value.to(s.dtype))
    return torch.cat(values,0)

class ChargeHead(nn.Module):
    p_heads_constraint=True
    def __init__(self,dimension,total_charge):
        super().__init__();self.total_charge=total_charge
        self.predict=nn.Sequential(nn.Linear(dimension,64),nn.SiLU(),nn.Linear(64,2))
    def forward(self,h,pos,batch):
        value=self.predict(h)
        return charge_equilibrium(value[:,:1],value[:,1:],pos,batch,self.total_charge)

class FukuiHead(nn.Module):
    p_heads_constraint=True
    def __init__(self,original_mlp):
        super().__init__();self.predict=original_mlp
    def forward(self,h,pos,batch):return fukui_projection(self.predict(h),batch)

def install_physical_heads(bank,configuration):
    bank.physical_constraints=dict(configuration)
    for name,spec in configuration.items():
        field=bank.registry.by_name()[name]
        if field.level!='atom' or field.representation!='scalar':raise ValueError('Only approved atom scalar fields')
        key=bank.keys[name]
        original=bank.field_heads[key]
        bank.field_heads[key]=(ChargeHead(bank.dim,spec['Q']) if spec['kind']=='charge' else FukuiHead(original))
