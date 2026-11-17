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
