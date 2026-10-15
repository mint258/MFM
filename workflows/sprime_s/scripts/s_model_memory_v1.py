"""Explicit row tiling of the same distance MLP, preserving parameters and keys.

This is a new declared runtime implementation. The original frozen runtime is
read-only. Architecture, FP32 precision, views, batch budget and loss are retained.
Numerical/gradient/RNG/resume validation is required before any scientific use.
"""
import torch
from torch import nn
from torch.utils.checkpoint import checkpoint
from phychem_mfm.factory import build_model

class TiledDistanceMLP(nn.Sequential):
    def __init__(self,original,pair_rows=65536):
        assert isinstance(original,nn.Sequential) and len(original)==3
        assert isinstance(original[0],nn.Linear) and isinstance(original[1],nn.SiLU) and isinstance(original[2],nn.Linear)
        assert original[0].in_features==1
        assert type(pair_rows) is int and pair_rows>0
        # Reuse the same Parameter objects and original numeric module names.
        super().__init__(*list(original.children()));self.pair_rows=pair_rows

    def _row_forward(self,value):return super().forward(value)

    def forward(self,value):
        assert value.shape[-1]==1
        shape=value.shape[:-1];flat=value.reshape(-1,1)
        if len(flat)<=self.pair_rows:return super().forward(value)
        result=[]
        for offset in range(0,len(flat),self.pair_rows):
            part=flat[offset:offset+self.pair_rows]
            if torch.is_grad_enabled() and any(p.requires_grad for p in self.parameters()):
                out=checkpoint(self._row_forward,part,use_reentrant=False,preserve_rng_state=True)
            else:out=self._row_forward(part)
            result.append(out)
        return torch.cat(result,dim=0).reshape(*shape,self[-1].out_features)

def build_memory_bounded_model(config,*,pair_rows=65536):
    model=build_model(config);before={name:id(parameter) for name,parameter in model.named_parameters()}
    names=[]
    for name,module in list(model.named_modules()):
        original=getattr(module,'dist_mlp',None)
        if original is not None:
            assert isinstance(original,nn.Sequential) and not isinstance(original,TiledDistanceMLP)
            module.dist_mlp=TiledDistanceMLP(original,pair_rows);names.append(name+'.dist_mlp')
    assert names and before=={name:id(parameter) for name,parameter in model.named_parameters()}
    model.s_memory_implementation={'kind':'row_tiled_distance_mlp_with_per_tile_nonreentrant_checkpoint',
        'pair_rows':pair_rows,'replaced_modules':names,'parameter_objects_and_state_keys_preserved':True}
    return model
