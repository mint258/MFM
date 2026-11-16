from types import SimpleNamespace
import numpy as np
import pytest
import torch
from phychem_mfm.phase1.v31_loader import TrainingView,V31Target
from phychem_mfm.phase1.v31_training import V31PDModel
from phychem_mfm.phase1.p_conformer_decomposition import transform_target,restore_predictions
from phychem_mfm.phase1.p_recipe_input import reader_metadata,prepare_samples


def target(raw,valid=None):
    raw=np.asarray(raw,np.float64).reshape(1,-1)
    return V31Target(raw,raw.astype(np.float32),np.isfinite(raw) if valid is None else np.asarray(valid,bool).reshape(1,-1),'P','energy','molecule','scalar',True)


def model_pair():
    class Encoder(torch.nn.Module):
        latent_dim=8
        def __init__(self):super().__init__();self.weight=torch.nn.Parameter(torch.ones(()))
    columns=[dict(field_key=n,column_index=i,family='energy',level='molecule',kind='scalar') for i,n in enumerate(['energy','other'])]
    schema=dict(columns=dict(mol_labels=columns),source_D3_reference=dict(sha256='a'*64))
    fields=[dict(name=n,group='P',family='energy',level='molecule',normalization=dict(fit_role='TRAIN',center=0.,scale=1.)) for n in ['energy','other']]
    view=TrainingView(schema,dict(fields=fields))
    torch.manual_seed(7);base=V31PDModel(Encoder(),view)
    torch.manual_seed(7);model=V31PDModel(Encoder(),view,conformer_decomposition=dict(selected_fields=['energy']))
    return base,model


def sample(valid=True):
    return dict(molecule_index=0,conformer_index=0,Z=np.array([6]),pos=np.zeros((1,3),np.float32),pos_perturbed=None,
        bonds=np.empty((0,2),np.int64),bond_order=np.empty(0,np.float32),targets=dict(energy=target([1.,2.] if valid else [1.,np.nan]),other=target([0.])))


def test_f64_roundtrip_and_single_conformer_mask():
    p=dict(c1=3.5,s1=2.7,s2=.003)
    t=target([1e9+.125]);actual=transform_target(t,mu=.1,count=3,parameters=p,offset=1e9)
    restored=restore_predictions(actual.raw,p,1e9)
    np.testing.assert_allclose(restored,t.raw,atol=1e-9,rtol=1e-9)
    single=transform_target(t,mu=.125,count=1,parameters=p,offset=1e9)
    np.testing.assert_array_equal(single.valid,[[True,False]])
    missing=transform_target(target([np.nan]),mu=.125,count=3,parameters=p,offset=1e9)
    np.testing.assert_array_equal(missing.valid,[[True,False]])


def test_h1_width_two_preserves_other_heads_and_initial_mean_row():
    base,model=model_pair();key=model.heads.keys['energy'];other=model.heads.keys['other']
    assert model.heads.field_heads[key].out_features==2
    assert model.heads.field_heads[other].out_features==1
    torch.testing.assert_close(model.heads.field_heads[key].weight[0],base.heads.field_heads[key].weight[0])
    torch.testing.assert_close(model.heads.field_heads[other].weight,base.heads.field_heads[other].weight)


@pytest.mark.parametrize('prepared',[False,True])
def test_component_mask_and_single_physical_field_weight(prepared):
    _,model=model_pair();model.grouped_fields=prepared;s=sample()
    samples=prepare_samples([s],reader_metadata(model,('energy','other'))) if prepared else [s]
    prediction=dict(energy=torch.tensor([[3.,6.]],requires_grad=True),other=torch.tensor([[2.]],requires_grad=True))
    loss=model.loss(prediction,samples,groups=('P',),fields=('energy','other'))
    assert loss.counts=={'energy':1,'other':1};assert loss.observed_fields=={'P':2}
    torch.testing.assert_close(loss.fields['energy'],torch.tensor(10.))
    torch.testing.assert_close(loss.total,torch.tensor(5.75))
    loss.total.backward();torch.testing.assert_close(prediction['energy'].grad,torch.tensor([[1.,2.]]))


def test_prepared_singleton_retains_mean_gradient_and_only_two_outputs():
    _,model=model_pair();model.grouped_fields=True;s=sample(valid=False)
    samples=prepare_samples([s],reader_metadata(model,('energy',)))
    assert samples.prepared['observed'][21]=={'energy'}
    prediction=dict(energy=torch.tensor([[3.,6.]],requires_grad=True))
    loss=model.loss(prediction,samples,groups=('P',),fields=('energy',))
    torch.testing.assert_close(loss.total,torch.tensor(2.));loss.total.backward()
    torch.testing.assert_close(prediction['energy'].grad,torch.tensor([[2.,0.]]))