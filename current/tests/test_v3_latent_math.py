"""Only the three specified new-module properties; frozen C1 precision is untouched.

The real checkpoint supplies layer5/6 hidden scalars. New latent maps are tested
in FP64; the pre-existing coordinate-to-H0 implementation is not a new precision
experiment. Full checkpoint zero-gate composition is also compared directly.
"""
from copy import deepcopy
from dataclasses import replace
import json
import os
from pathlib import Path

import pytest
import torch
from torch_geometric.data import Batch,Data
from torch_geometric.utils import to_dense_batch

from phychem_mfm.phase1.v2_s_training import s_model
from phychem_mfm.model.v3_latent import LatentSpec,MolecularLatent


@pytest.fixture(scope='module')
def checkpoint_features():
    path = Path(os.environ.get('MODEL_V3_C1_MATH_CHECKPOINT',
        '/share/home/zixiao/descriptor_analysis/runs/model_v31_20261105/S_C1_0_seed0_v2/samples_6000000.pt'))
    if not path.exists():
        pytest.skip('The specified actual owning-server C1 checkpoint is required')
    checkpoint = torch.load(path,map_location='cpu',weights_only=True)
    config = checkpoint['configuration']
    torch.manual_seed(20261025)
    model,_ = s_model(config['distance_bias'],config['views'])
    model.load_state_dict(checkpoint['model'])
    model.eval()
    graphs = [Data(x=torch.arange(1,n+1).long().reshape(-1,1),pos=torch.randn(n,3))
              for n in (3,5)]
    batch = Batch.from_data_list(graphs)
    hidden = {}
    handles = [model.encoder.backbone.layers[layer-1].register_forward_hook(
        lambda module,args,out,layer=layer:hidden.update({layer:out.detach().clone()}))
        for layer in (5,6)]
    with torch.no_grad():
        baseline = model.encoder.encode_atoms(batch)
    for handle in handles:
        handle.remove()
    pos,mask = to_dense_batch(batch.pos,batch.batch)
    elements,_ = to_dense_batch(batch.x[:,0],batch.batch)
    specification = json.loads((Path(__file__).parents[2]/'configs/model_v3/latent_lite_v1.json').read_text())['default']
    return model,checkpoint,config,batch,baseline,hidden,pos,mask,elements,LatentSpec(**specification)


def _run_maps(module,features,mask,norm):
    module.begin()
    x5 = module.step(0,features[5],mask)
    x6 = module.step(1,features[6],mask)
    x6 = torch.where(mask.unsqueeze(-1),norm(x6),x6.new_zeros(()))
    return x5,x6,module.finish(x6,mask)


def _close(actual,reference):
    tolerance = torch.maximum(torch.full_like(reference,1e-7),1e-6*reference.abs())
    assert bool(((actual-reference).abs()<=tolerance).all())


def test_real_checkpoint_zero_gamma_preserves_X(checkpoint_features):
    model,checkpoint,config,batch,baseline,hidden,pos,mask,elements,spec = checkpoint_features
    torch.manual_seed(0)
    augmented,_ = s_model(config['distance_bias'],config['views'],latent='lite_rec',
                          latent_config=spec.__dict__)
    augmented.load_state_dict(checkpoint['model'],strict=False)
    augmented.eval()
    with torch.no_grad():
        actual = augmented.encoder.encode_atoms(batch)
    _close(actual.double(),baseline.double())
    # Exact new insertion operators in FP64 on actual checkpoint layer states.
    module = deepcopy(augmented.encoder.latent_module).double()
    module.begin()
    with torch.no_grad():
        for index,layer in enumerate((5,6)):
            expected = hidden[layer].double()
            observed = module.step(index,expected,mask)
            _close(observed[mask],expected[mask])


def test_fp64_new_latent_permutation_SE3_invariance(checkpoint_features):
    model,checkpoint,config,batch,baseline,hidden,pos,mask,elements,spec = checkpoint_features
    torch.manual_seed(0)
    module = MolecularLatent(spec).double().eval()
    for layer in module.layers:
        layer.gamma.data.fill_(.1)
    features = {k:v.double() for k,v in hidden.items()}
    norm = deepcopy(model.encoder.backbone.out_norm).double()
    permutation = torch.tensor([4,1,3,0,2])
    rotation,_ = torch.linalg.qr(torch.randn(3,3,dtype=torch.float64))
    rotation[:,0] *= torch.det(rotation)
    shifted = pos.double()@rotation+torch.tensor([.7,-1.2,2.3],dtype=torch.float64)
    with torch.no_grad():
        _,_,reference = _run_maps(module,features,mask,norm)
        projected = module.last_projected_latent
        # Positions enter only the element/radius decoder, never an X shortcut.
        module.decoder(projected,elements,pos.double(),mask)
        _,_,actual = _run_maps(module,{k:v[:,permutation] for k,v in features.items()},
                               mask[:,permutation],norm)
        module.decoder(module.last_projected_latent,elements[:,permutation],
                       shifted[:,permutation],mask[:,permutation])
    relative = torch.linalg.vector_norm(actual-reference)/torch.linalg.vector_norm(reference)
    assert float(relative)<=1e-9
    # The explicitly requested FP32 observation has no acceptance threshold.
    fp32 = deepcopy(module).float()
    with torch.no_grad():
        _,_,a = _run_maps(fp32,{k:v.float() for k,v in features.items()},mask,norm.float())
        _,_,b = _run_maps(fp32,{k:v.float()[:,permutation] for k,v in features.items()},
                          mask[:,permutation],norm.float())
    print(json.dumps(dict(FP64_relative_error=float(relative),
        FP32_relative_error_report_only=float(torch.linalg.vector_norm(a-b)/torch.linalg.vector_norm(a)))))


def test_fp64_padding_preserves_z_and_valid_X(checkpoint_features):
    model,checkpoint,config,batch,baseline,hidden,pos,mask,elements,spec = checkpoint_features
    torch.manual_seed(0)
    module = MolecularLatent(spec).double().eval()
    for layer in module.layers:
        layer.gamma.data.fill_(.1)
    norm = deepcopy(model.encoder.backbone.out_norm).double()
    features = {k:v.double() for k,v in hidden.items()}
    padded = {k:torch.cat((v,torch.full((2,4,512),float('nan'),dtype=torch.float64)),1)
              for k,v in features.items()}
    padded_mask = torch.cat((mask,torch.zeros(2,4,dtype=torch.bool)),1)
    with torch.no_grad():
        ref5,ref6,refz = _run_maps(module,features,mask,norm)
        out5,out6,z = _run_maps(module,padded,padded_mask,norm)
    _close(out5[padded_mask],ref5[mask])
    _close(out6[padded_mask],ref6[mask])
    _close(z,refz)
