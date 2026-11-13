"""Only taskbook-required tests of new label/loss logic."""
import torch
from phychem_mfm.phase1.p_recipe import (
    element_residual,state_difference,heavy_tail,normalized_field_weights,
    UncertaintyWeights,collapse_penalty)

def test_reversible_fp64_label_transforms():
    y=torch.tensor([-3e4,-.01,0.,.2,7e4],dtype=torch.float64)
    counts=torch.tensor([[1.,2.],[2.,3.],[0.,4.],[1.,5.],[3.,2.]],dtype=torch.float64)
    coefficients=torch.tensor([12.3,-45.6],dtype=torch.float64)
    for transformed,inverse in (
        (element_residual(y,counts,coefficients,2.1),lambda x:element_residual(x,counts,coefficients,2.1,inverse=True)),
        (state_difference(y,y*.37),lambda x:state_difference(x,y*.37,inverse=True)),
        (heavy_tail(y,.125),lambda x:heavy_tail(x,.125,inverse=True))):
        restored=inverse(transformed)
        assert torch.all((restored-y).abs()<=torch.maximum(torch.full_like(y,1e-9),y.abs()*1e-9))

def test_a4_weights_sum_to_one_and_equal_family_mass():
    families={'a':'energy','b':'energy','c':'charge'}
    weights=normalized_field_weights(families,family_equal=True,dtype=torch.float64)
    assert abs(float(sum(weights.values()))-1)<1e-12
    assert float(weights['a']+weights['b'])==float(weights['c'])

def test_c4_normalized_weights_and_exact_kendall_loss():
    layer=UncertaintyWeights(['a','b']).double()
    with torch.no_grad():layer.log_variance.copy_(torch.tensor([-.4,.7]))
    assert torch.allclose(layer.weights().sum(),torch.tensor(1.,dtype=torch.float64),atol=1e-12,rtol=1e-12)
    values={'a':torch.tensor(2.,dtype=torch.float64),'b':torch.tensor(.3,dtype=torch.float64)}
    expected=(.5*torch.exp(-layer.log_variance)*torch.stack(list(values.values()))+.5*layer.log_variance).mean()
    assert torch.allclose(layer(values),expected,atol=1e-12,rtol=1e-12)
    layer(values).backward()
    assert torch.isfinite(layer.log_variance.grad).all()

def test_b4_zero_for_uncorrelated_sufficient_variance_and_finite_gradient():
    h=torch.tensor([[-1.,-1.],[-1.,1.],[1.,-1.],[1.,1.]],dtype=torch.float64,requires_grad=True)
    penalty=collapse_penalty(h,1.)
    assert torch.allclose(penalty,torch.zeros_like(penalty),atol=1e-12,rtol=1e-12)
    penalty.backward();assert torch.isfinite(h.grad).all()
    collapsed=torch.zeros((4,2),dtype=torch.float64,requires_grad=True)
    collapse_penalty(collapsed,1.).backward()
    assert torch.isfinite(collapsed.grad).all()

def test_inverse_composed_labels_uses_predicted_neutral_in_fp64():
    import numpy as np
    from phychem_mfm.phase1.p_recipe_data import original_predictions
    class NativeHeads:
        def original_predictions(self,predictions,samples):return dict(predictions)
    y=torch.tensor([[12.],[-.4]],dtype=torch.float64)
    neutral=torch.tensor([[3.],[1.]],dtype=torch.float64)
    counts=torch.tensor([[2.],[1.]],dtype=torch.float64)
    reference=counts*1.25+.1
    encoded=heavy_tail(y-neutral-reference,.75)
    samples=[{'Z':np.array([6,6]),'targets':{'neutral':'unused target'}},
             {'Z':np.array([6]),'targets':{'neutral':'unused target'}}]
    parameters={'state_difference':{'charged':'neutral'},'heavy_tail':{'charged':{'m':.75,
        'offset_reference':{'basis':[6],'coefficients':[1.25],'intercept':.1}}}}
    prediction={'charged':encoded,'neutral':neutral}
    restored=original_predictions(NativeHeads(),prediction,samples,parameters)['charged']
    assert torch.allclose(restored,y,atol=1e-9,rtol=1e-9)
    shifted=original_predictions(NativeHeads(),{**prediction,'neutral':neutral+2.},samples,parameters)['charged']
    assert torch.allclose(shifted,y+2.,atol=1e-9,rtol=1e-9)
def test_state_groups_follow_dipole_definition_inside_multipole_family():
    from types import SimpleNamespace
    from phychem_mfm.phase1.p_recipe_data import physical_state_groups
    fields=[];metadata=[]
    for state,unit,path in [('pm7_B','Debye','values.dipole_Debye'),('pm7_anion','Debye','values.dipole_Debye'),('pm7_water','unknown_unit','values.dipole_Debye'),('pm7_cation','Debye','values.quadrupole')]:
        name=f'P.{state}.r1.x'
        fields.append(dict(name=name,group='P',family='multipole',level='molecule_vector',unit=unit))
        metadata.append(dict(field_key=name,source_path=path,component='x',unit=unit))
    view=SimpleNamespace(fields=fields,schema={'columns':{'mol_labels':metadata}})
    groups=physical_state_groups(view,{f['name'] for f in fields})
    assert len(groups)==1
    assert next(iter(groups.values()))=={'neutral':'P.pm7_B.r1.x','anion':'P.pm7_anion.r1.x'}