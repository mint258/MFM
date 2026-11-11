"""Taskbook-v3 PMA/Lite molecular latents and the latent-only reconstruction decoder."""
from __future__ import annotations

from dataclasses import asdict,dataclass,replace
import math

import torch
from torch import nn


@dataclass(frozen=True)
class LatentSpec:
    kind: str = 'lite_rec'
    n_ref: float | None = None
    d: int = 512
    heads: int = 8
    k: int = 8
    latent_dim: int = 256
    projected_dim: int = 64
    sum_dim: int = 64
    decoder_dim: int = 256
    reconstruction_weight: float = .1
    insert_layers: tuple = (5,6)
    write_back: bool | None = None
    reconstruction: bool | None = None
    radial_count: int = 32
    radial_max_A: float = 8.
    dense_hidden_dim: int | None = None

    def __post_init__(self):
        if self.kind not in ('none','pma','lite','lite_rec','dense_addon'):
            raise ValueError('Unknown taskbook-v3 latent option')
        if self.kind!='none' and (not isinstance(self.n_ref,(int,float)) or
                                  not math.isfinite(self.n_ref) or self.n_ref<=0):
            raise ValueError('Supply the fixed240k optimization-population mean atom count')
        if (self.d,self.heads,self.latent_dim,self.projected_dim,self.sum_dim,self.decoder_dim,
                self.radial_count,self.radial_max_A)!=(512,8,256,64,64,256,32,8.):
            raise ValueError('Use the fixed taskbook-v3 dimensions and existing8A radial range')
        if (self.k,self.reconstruction_weight) not in ((8,.1),(8,.3),(16,.1)):
            raise ValueError('Only the default and two expressly registered lambda/k settings exist')
        if tuple(self.insert_layers)!=(5,6):
            raise ValueError('Insert only after layers5 and6')
        if self.dense_hidden_dim is not None and (self.kind != 'dense_addon' or
                type(self.dense_hidden_dim) is not int or self.dense_hidden_dim < 8 or
                self.dense_hidden_dim % 8):
            raise ValueError('Dense width is the producer-derived positive multiple8')
        object.__setattr__(self,'insert_layers',tuple(self.insert_layers))
        if self.write_back is None:
            object.__setattr__(self,'write_back',self.kind in ('lite','lite_rec'))
        if self.reconstruction is None:
            object.__setattr__(self,'reconstruction',self.kind=='lite_rec')


class MaskedAttention(nn.Module):
    def __init__(self,q_dim,kv_dim,out_dim,*,width=256,heads=8):
        super().__init__()
        self.width,self.heads = width,heads
        self.q = nn.Linear(q_dim,width,bias=False)
        self.k = nn.Linear(kv_dim,width,bias=False)
        self.v = nn.Linear(kv_dim,width,bias=False)
        self.out = nn.Linear(width,out_dim,bias=False)

    def forward(self,query,key,value,key_mask=None):
        b,n,_ = query.shape
        m = key.shape[1]
        head_dim = self.width//self.heads
        def split(x):
            return x.reshape(b,-1,self.heads,head_dim).transpose(1,2)
        q,k,v = split(self.q(query)),split(self.k(key)),split(self.v(value))
        logits = (q@k.transpose(-1,-2))/math.sqrt(head_dim)
        if key_mask is not None:
            logits = logits.masked_fill(~key_mask[:,None,None,:],-torch.inf)
        attention = torch.softmax(logits,dim=-1)
        result = (attention@v).transpose(1,2).reshape(b,n,self.width)
        return self.out(result)


class LatentLayer(nn.Module):
    def __init__(self,*,write_back):
        super().__init__()
        self.read_z_norm,self.read_x_norm = nn.LayerNorm(256),nn.LayerNorm(512)
        self.read = MaskedAttention(256,512,256)
        self.ffn_norm = nn.LayerNorm(256)
        self.ffn = nn.Sequential(nn.Linear(256,512),nn.GELU(),nn.Linear(512,256))
        self.self_norm = nn.LayerNorm(256)
        self.self_attention = MaskedAttention(256,256,256)
        self.write_back = write_back
        if write_back:
            self.write_x_norm,self.write_z_norm = nn.LayerNorm(512),nn.LayerNorm(256)
            self.write = MaskedAttention(512,256,512)
            self.gamma = nn.Parameter(torch.zeros(512))

    def forward(self,x,z,mask):
        x = torch.where(mask.unsqueeze(-1),x,x.new_zeros(()))
        xn,zn = self.read_x_norm(x),self.read_z_norm(z)
        z = z+self.read(zn,xn,xn,mask)
        z = z+self.ffn(self.ffn_norm(z))
        zn = self.self_norm(z)
        z = z+self.self_attention(zn,zn,zn)
        if self.write_back:
            zn = self.write_z_norm(z)
            x = x+self.gamma*self.write(self.write_x_norm(x),zn,zn)
        return torch.where(mask.unsqueeze(-1),x,x.new_zeros(())),z


class ReconstructionDecoder(nn.Module):
    """The API accepts only projected latent, element, radius geometry and padding."""
    def __init__(self,spec):
        super().__init__()
        self.element = nn.Embedding(119,256)
        self.radial = nn.Linear(32,256,bias=False)
        self.up = nn.Linear(64,256,bias=False)
        self.cross = MaskedAttention(256,256,256)
        self.ffn = nn.Sequential(nn.Linear(256,512),nn.GELU(),nn.Linear(512,256))
        self.out = nn.Linear(256,512,bias=False)
        self.register_buffer('centers',torch.linspace(0.,spec.radial_max_A,32))
        self.width = spec.radial_max_A/31

    def forward(self,projected_latent,elements,pos,mask):
        clean_pos = torch.where(mask.unsqueeze(-1),pos,pos.new_zeros(()))
        count = mask.sum(1,keepdim=True).to(pos.dtype)
        centroid = clean_pos.sum(1)/count
        radius = torch.linalg.vector_norm(clean_pos-centroid[:,None,:],dim=-1)
        scaled = (radius.unsqueeze(-1)-self.centers)/self.width
        radial = torch.exp(-.5*scaled.square())/(math.sqrt(2*math.pi)*self.width)
        q = self.element(elements.long().clamp(0,118))+self.radial(radial)
        latent = self.up(projected_latent)
        predicted = self.out(self.ffn(self.cross(q,latent,latent)))
        return torch.where(mask.unsqueeze(-1),predicted,predicted.new_zeros(()))


class DenseResidual(nn.Module):
    def __init__(self,width):
        super().__init__()
        self.norm = nn.LayerNorm(512)
        self.mlp = nn.Sequential(nn.Linear(512,width),nn.GELU(),nn.Linear(width,512))
        self.gamma = nn.Parameter(torch.zeros(512))

    def forward(self,x,mask):
        x = torch.where(mask.unsqueeze(-1),x,x.new_zeros(()))
        x = x+self.gamma*self.mlp(self.norm(x))
        return torch.where(mask.unsqueeze(-1),x,x.new_zeros(()))


class MolecularLatent(nn.Module):
    def __init__(self,spec:LatentSpec):
        super().__init__()
        self.spec = spec
        self.has_z = spec.kind in ('pma','lite','lite_rec')
        self.representation_dim = spec.k*64+64+1 if self.has_z else 0
        if self.has_z:
            self.z0 = nn.Parameter(torch.empty(spec.k,256))
            nn.init.normal_(self.z0,mean=0.,std=.02)
            self.layers = nn.ModuleList([LatentLayer(write_back=spec.write_back and spec.kind!='pma')
                for _ in range(1 if spec.kind=='pma' else 2)])
            self.project = nn.Linear(256,64,bias=False)
            self.sum_norm = nn.LayerNorm(512)
            self.sum_gate = nn.Linear(512,1,bias=True)
            self.sum_project = nn.Linear(512,64,bias=False)
            self.decoder = ReconstructionDecoder(spec) if spec.reconstruction else None
        elif spec.kind=='dense_addon':
            # Fixed algebraic parameter matching, never a performance scan.
            with torch.random.fork_rng(devices=[]):
                prototype = MolecularLatent(replace(spec,kind='lite_rec',write_back=True,
                    reconstruction=True,k=8,reconstruction_weight=.1,dense_hidden_dim=None))
                target = sum(p.numel() for p in prototype.parameters())
            width = spec.dense_hidden_dim or max(8,round(((target-4096)/2050)/8)*8)
            self.layers = nn.ModuleList([DenseResidual(width),DenseResidual(width)])
            actual = sum(p.numel() for p in self.parameters())
            if spec.dense_hidden_dim is None and abs(actual-target)/target>.05:
                raise ValueError('Dense addon must match lite_rec new-module parameters within5%')
            self.parameter_match = dict(reference=target,actual=actual,relative_error=abs(actual-target)/target,
                                        hidden_dim=width)
        self.begin()

    def get_extra_state(self):
        return dict(schema='model_v3_molecular_latent_v1',spec=asdict(self.spec))

    def set_extra_state(self,value):
        # The first live T0 producers predate this serialization-only optional
        # width; absent/None is identical for every non-dense module.
        if 'dense_hidden_dim' not in value.get('spec',{}):
            value = dict(value,spec=dict(value['spec'],dense_hidden_dim=None))
        if value!=self.get_extra_state():
            raise ValueError('Latent checkpoint/specification differs')

    def begin(self):
        self._z = None
        self.last_z = None
        self.last_projected_latent = None

    def step(self,index,x,mask):
        if self.spec.kind=='dense_addon':
            return self.layers[index](x,mask)
        if self.spec.kind=='pma' or not self.has_z:
            return x
        if self._z is None:
            self._z = self.z0.unsqueeze(0).expand(x.shape[0],-1,-1)
        x,self._z = self.layers[index](x,self._z,mask)
        return x

    def finish(self,x,mask):
        if not self.has_z:
            return None
        x = torch.where(mask.unsqueeze(-1),x,x.new_zeros(()))
        if self.spec.kind=='pma':
            z = self.z0.unsqueeze(0).expand(x.shape[0],-1,-1)
            _,self._z = self.layers[0](x,z,mask)
        if self._z is None:
            raise RuntimeError('Both registered insertion layers must be visited')
        projected = self.project(self._z)
        normalized = self.sum_norm(x)
        gated = torch.sigmoid(self.sum_gate(normalized))*self.sum_project(normalized)
        total = torch.where(mask.unsqueeze(-1),gated,gated.new_zeros(())).sum(1)/self.spec.n_ref
        log_n = mask.sum(1,keepdim=True).to(x.dtype).log()
        self.last_projected_latent = projected
        self.last_z = torch.cat((projected.flatten(1),total,log_n),dim=-1)
        return self.last_z

    def reconstruction_loss(self,projected_latent,elements,pos,mask,teacher):
        if self.decoder is None:
            raise ValueError('Reconstruction is enabled only in its registered experiment')
        predicted = self.decoder(projected_latent,elements,pos,mask)
        target = teacher.detach()[mask]
        variance = target.var(0,unbiased=False).mean().clamp_min(torch.finfo(target.dtype).eps)
        # Sum feature components exactly as the specified squared vector norm;
        # average valid atoms; do not silently divide by feature dimension512.
        return (predicted[mask]-target).square().sum(-1).mean()/variance


def attach_latent(encoder,spec):
    """Install post-FFN layer5/6 hooks; none returns the original object untouched."""
    if spec.kind=='none':
        return encoder
    if hasattr(encoder,'latent_module'):
        raise ValueError('The encoder already has a registered latent module')
    if len(encoder.backbone.layers)!=6 or encoder.latent_dim!=512:
        raise ValueError('This taskbook fixes a6-layer512-dimensional backbone')
    if encoder.backbone.activation_checkpointing:
        raise ValueError('Use the already adopted backbone-checkpointing-off path')
    with torch.random.fork_rng(devices=[]):
        module = MolecularLatent(spec)
    parameter = next(encoder.parameters())
    encoder.latent_module = module.to(device=parameter.device,dtype=parameter.dtype)
    encoder.molecule_latent_dim = module.representation_dim

    def begin(backbone,args):
        module.begin()

    def layer_hook(index):
        def apply(layer,args,output):
            return module.step(index,output,args[-1])
        return apply

    def finish(backbone,args,output):
        if not module.has_z:
            return output
        from torch_geometric.utils import to_dense_batch
        from .common import ensure_batch_attr
        dense,mask = to_dense_batch(output,ensure_batch_attr(args[0]),fill_value=0.)
        module.finish(dense,mask)
        return output

    handles = [encoder.backbone.register_forward_pre_hook(begin),
               encoder.backbone.register_forward_hook(finish)]
    if spec.kind!='pma':
        handles.extend(encoder.backbone.layers[layer-1].register_forward_hook(layer_hook(i))
                       for i,layer in enumerate(spec.insert_layers))
    encoder._latent_hook_handles = handles
    return encoder
