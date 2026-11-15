"""One taskbook test, covering both selective GEMM modes and actual islands."""
from copy import deepcopy

import torch
from torch_geometric.data import Batch, Data

from phychem_mfm.model.backbone import RealCoordTransformerBackbone
from phychem_mfm.model.v3_heads import V3HeadBank
from phychem_mfm.model.precision import configure_precision, observe_islands, fp32_island, island_tensor
from phychem_mfm.phase1.v31_training import torch_affine
from phychem_mfm.phase1.v3_contract import FieldSpec, LabelRegistry, FieldTarget, TrainNormalization
from phychem_mfm.phase1.v3_losses import compute_v3_loss


def test_precision_islands_are_fp32_and_geometry_matches_fp32():
    torch.set_num_threads(1)
    torch.manual_seed(0)
    torch.set_float32_matmul_precision('highest')
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    registry = LabelRegistry((
        FieldSpec('scalar', 'P', 'energy', 'graph'),
        FieldSpec('pair', 'P', 'bonding', 'pair'),
        FieldSpec('dipole', 'P', 'multipole', 'graph', representation='vector'),
        FieldSpec('noise', 'P', 'force', 'atom', representation='vector'),
    ), 'precision_unit', 'a'*64)
    model = torch.nn.ModuleDict(dict(
        backbone=RealCoordTransformerBackbone(119, 16, layers=1, heads=2, ff_mult=2),
        heads=V3HeadBank(registry, dim=16, hidden_dim=8, vector_rbf_count=4),
    )).to(device)
    state = deepcopy(model.state_dict())
    batch = Batch.from_data_list([Data(x=torch.tensor([[5],[0],[0]]),
        pos=torch.tensor([[0.,0.,0.],[.75,.21,.13],[-.24,.83,.1]]))]).to(device)
    pairs = {'pair': torch.tensor([[0,1],[1,2]],device=device)}
    geometry = {}
    required = {'coordinate_subtraction','distance_squared','distance_bias_first_layer',
        'attention_bias_add','attention_softmax','layer_norm','scatter_pool',
        'pair_distance','pair_rbf','vector_relative_position','vector_index_add',
        'denoising_distance','distance','denoising_relative_position','denoising_rbf',
        'denoising_direction','standardization','inverse_standardization','loss',
        'gradient_clipping','optimizer'}
    for mode in ('fp32', 'tf32_islands', 'bf16_islands'):
        model.load_state_dict(state)
        configure_precision(model, mode)
        seen = set()
        measured = []
        def observe(name, value):
            seen.add(name)
            assert value.dtype == torch.float32, name
            assert not torch.is_autocast_enabled(device), name
            assert not torch.backends.cuda.matmul.allow_tf32, name
            if name in ('distance','distance_squared','pair_distance','denoising_distance'):
                measured.append((name,value.detach().clone()))
        optimizer = torch.optim.AdamW(model.parameters(), lr=3e-4)
        optimizer.zero_grad(set_to_none=True)
        with observe_islands(observe):
            h = model['backbone'](batch)
            predictions = model['heads'](h,batch.batch,batch.pos,enabled_groups=('P',),pair_indices=pairs)
            for name, value in predictions.items():
                predictions[name] = island_tensor('standardization',torch_affine(value,dict(center=0.,scale=2.)))
                island_tensor('inverse_standardization',torch_affine(predictions[name],dict(center=0.,scale=2.),inverse=True))
            norms = {f.name:TrainNormalization((0.,),(1.,),'a'*64,'TRAIN') for f in registry.fields}
            targets = {name:FieldTarget(torch.zeros_like(value),torch.ones(len(value),dtype=torch.bool,device=device))
                       for name,value in predictions.items()}
            with fp32_island(h):
                loss = compute_v3_loss(predictions,targets,registry,norms,enabled_groups=('P',))
                island_tensor('loss',loss.total).backward()
                island_tensor('gradient_clipping',torch.nn.utils.clip_grad_norm_(model.parameters(),281.7,error_if_nonfinite=True))
                optimizer.step()
                for parameter in model.parameters():
                    island_tensor('optimizer',parameter)
                    if parameter.grad is not None:
                        assert parameter.grad.dtype == torch.float32
        if mode != 'fp32':
            assert required <= seen, required-seen
            assert len(measured) == len(geometry['fp32'])
            for (name,value),(reference_name,reference) in zip(measured,geometry['fp32']):
                assert name == reference_name and torch.equal(value,reference), name
        geometry[mode] = measured
        assert model.state_dict().keys() == state.keys()
