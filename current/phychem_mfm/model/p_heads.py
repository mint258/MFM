"""Taskbook T1: atom scalar/pair decoding without changing downstream H0."""
import torch
from torch import nn
from .v3_latent import MaskedAttention

class AtomAttentionDecoder(nn.Module):
    def __init__(self):
        super().__init__()
        self.norm1=nn.LayerNorm(512)
        self.attention=MaskedAttention(512,512,512,width=256,heads=8)
        self.norm2=nn.LayerNorm(512)
        self.ffn=nn.Sequential(nn.Linear(512,512),nn.SiLU(),nn.Linear(512,512))
        nn.init.zeros_(self.attention.out.weight)
        nn.init.zeros_(self.ffn[-1].weight);nn.init.zeros_(self.ffn[-1].bias)
    def forward(self,h,batch):
        from torch_geometric.utils import to_dense_batch
        dense,mask=to_dense_batch(h,batch)
        x=self.norm1(dense)
        decoded=dense+self.attention(x,x,x,mask)
        decoded=decoded+self.ffn(self.norm2(decoded))
        return decoded[mask]

class SimpleMolecularReadout(nn.Module):
    """T5: molecular [mean H0, sum H0/N_ref, log N], with no PMA."""
    representation_dim=1025
    def __init__(self,n_ref=53.64145):
        super().__init__();self.n_ref=float(n_ref)
        if self.n_ref<=0:raise ValueError('Positive frozen N_ref required')
        self.last_z=None
    def finish(self,x,mask):
        clean=torch.where(mask.unsqueeze(-1),x,x.new_zeros(()))
        count=mask.sum(1,keepdim=True).to(x.dtype)
        if bool((count==0).any()):raise ValueError('Molecules must contain valid atoms')
        total=clean.sum(1)
        self.last_z=torch.cat((total/count,total/self.n_ref,count.log()),dim=-1)
        return self.last_z