"""D1 all-A tensor source order, physical covariance and actual loss behavior."""
import math
import pytest
import torch
from phychem_mfm.model.v3_rank2_targets import (
    SymmetricTensor6Head, matrix_to_six, rotate_six, six_to_matrix, tensor6_radial_huber)


def rotation(dtype=torch.float64):
    # General SO(3) rotation, not merely an axis permutation.
    axis=torch.tensor([2.,3.,5.],dtype=torch.float64)
    axis=axis/axis.norm()
    x,y,z=axis.tolist()
    skew=torch.tensor([[0.,-z,y],[z,0.,-x],[-y,x,0.]],dtype=torch.float64)
    angle=.37
    result=math.cos(angle)*torch.eye(3,dtype=torch.float64)
    result=result+(1-math.cos(angle))*axis[:,None]*axis[None,:]+math.sin(angle)*skew
    return result.to(dtype=dtype)


def test_source_six_preserves_zz_trace_and_frobenius():
    value=torch.tensor([[1., 2., 3., 4., 5., 17.]], dtype=torch.float64)
    matrix=six_to_matrix(value)
    assert torch.equal(matrix_to_six(matrix),value)
    assert matrix[0].trace() == 21
    assert torch.equal((matrix.square()).sum((-2,-1)),
                       (value.square()*torch.tensor([1.,2.,1.,2.,2.,1.])).sum(-1))
    assert torch.equal(matrix_to_six(six_to_matrix(rotate_six(value,rotation()))),rotate_six(value,rotation()))
    with pytest.raises(ValueError):rotate_six(value,2*rotation())


def test_radial_d9_is_one_complete_target_and_partial_rows_do_not_leak_nan():
    target=torch.tensor([[0.,0.,0.,0.,0.,0.],[7.,float('nan'),1.,2.,3.,4.]],dtype=torch.float64)
    pred=torch.tensor([[3.,0.,0.,0.,0.,0.],[999.,999.,999.,999.,999.,999.]],dtype=torch.float64,requires_grad=True)
    mask=torch.tensor([[1]*6,[1,0,1,1,1,1]],dtype=torch.bool)
    result=tensor6_radial_huber(pred,target,mask,torch.tensor([1,1],dtype=torch.bool),1.)
    assert result.eligible_count==1 and result.excluded_count==1 and result.loss==.5
    result.loss.backward()
    assert pred.grad[0,0]==pytest.approx(1/3) and torch.equal(pred.grad[1],torch.zeros(6,dtype=torch.float64))
    assert result.component_valid_counts.tolist()==[2,1,2,2,2,2]
    none=tensor6_radial_huber(pred,target,mask,torch.tensor([0,0],dtype=torch.bool),1.)
    assert none.loss is None and none.eligible_count==0
    with pytest.raises(ValueError):tensor6_radial_huber(pred,target,mask,torch.ones(2,dtype=torch.bool),0.)
    with pytest.raises(ValueError):tensor6_radial_huber(pred,target,mask,torch.ones(2,dtype=torch.bool),torch.ones(6))


def test_loss_rotation_invariance_and_zero_error_derivatives():
    generator=torch.Generator().manual_seed(20261029)
    target=torch.randn(5,6,generator=generator,dtype=torch.float64)
    prediction=torch.randn(5,6,generator=generator,dtype=torch.float64)
    mask=torch.ones(5,6,dtype=torch.bool);geometry=torch.ones(5,dtype=torch.bool)
    first=tensor6_radial_huber(prediction,target,mask,geometry,2.3)
    moved=tensor6_radial_huber(rotate_six(prediction,rotation()),rotate_six(target,rotation()),mask,geometry,2.3)
    assert torch.allclose(first.loss,moved.loss,atol=0,rtol=1e-12)
    exact=target.clone().requires_grad_(True)
    value=tensor6_radial_huber(exact,target,mask,geometry,2.3).loss
    grad,=torch.autograd.grad(value,exact,create_graph=True)
    second,=torch.autograd.grad(grad.sum(),exact)
    assert torch.equal(grad,torch.zeros_like(grad)) and bool(torch.isfinite(second).all())


@pytest.mark.parametrize("dtype",[torch.float32,torch.float64])
def test_head_explicit_origin_covariance_trace_and_geometry_gradients(dtype):
    torch.manual_seed(17);head=SymmetricTensor6Head(8,hidden_dim=9,origin_policy="explicit_comoving").to(dtype=dtype)
    h=torch.randn(7,8,dtype=dtype,requires_grad=True)
    pos=torch.tensor([[1.,2.,0.],[-1.,3.,2.],[0.,-2.,1.],[4.,1.,2.],[1.,5.,-1.],[-2.,1.,4.],[2.,-1.,0.]],dtype=dtype,requires_grad=True)
    batch=torch.tensor([0,0,0,1,1,1,1]);origin=torch.tensor([[.5,-.2,1.],[2.,1.,-.5]],dtype=dtype)
    r=rotation(dtype);t=torch.tensor([3.,-4.,2.],dtype=dtype)
    actual=head(h,pos,batch,2,origin)
    transformed=head(h,pos@r+t,batch,2,origin@r+t)
    expected=rotate_six(actual,r)
    atol,rtol=(1e-6,1e-4) if dtype==torch.float32 else (0.,1e-9)
    assert torch.allclose(transformed,expected,atol=atol,rtol=rtol)
    actual.square().mean().backward()
    assert bool(torch.isfinite(h.grad).all()) and bool(torch.isfinite(pos.grad).all())
    assert all(p.grad is not None and bool(torch.isfinite(p.grad).all()) for p in head.parameters())
    with torch.no_grad():
        for p in head.parameters():p.zero_()
        head.coefficients[-1].bias[0]=1.
    trace_only=head(h.detach(),pos.detach(),batch,2,origin)
    assert torch.equal(trace_only,torch.tensor([[3.,0.,3.,0.,0.,3.],[4.,0.,4.,0.,0.,4.]],dtype=dtype))
    with pytest.raises(ValueError):SymmetricTensor6Head(8,origin_policy="centroid")
