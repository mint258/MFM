"""Specific actual-q replay and program-order reference; no model/head objects."""
import numpy as np
import torch
import torch.nn.functional as F
from pathlib import Path
import phychem_mfm
from phychem_mfm.model import v3_numeric_stability as numeric_source
from phychem_mfm.model.v3_numeric_stability import (
    compensated_pool, compensated_index_add, compensated_norm3)

FIELDS=('p_dipole','p_dipole_magnitude')
PARAMETERS=('0.weight','0.bias','2.weight','2.bias')
CLOSURE=1e-10


def need(ok,message):
    if not ok:raise ValueError(message)


def tensor(value,dtype=None):
    x=torch.from_numpy(np.ascontiguousarray(value))
    return x if dtype is None else x.to(dtype=dtype)


def exact_port(value,expected,label):
    actual=value.detach().cpu().contiguous().numpy()
    need(actual.dtype==expected.dtype and actual.shape==expected.shape,
         'CPU local replay dtype/shape differs: '+label)
    need(np.isfinite(actual).all(),'Nonfinite CPU local replay output: '+label)
    bitdiff=actual.view(np.uint32)!=expected.view(np.uint32)
    exact=not bool(bitdiff.any())
    delta=actual.astype(np.float64)-expected.astype(np.float64)
    point=tuple(int(v) for v in np.unravel_index(int(np.abs(delta).argmax()),delta.shape))
    if not exact and float(np.abs(delta[point]))==0.:
        point=tuple(int(v) for v in np.unravel_index(int(np.flatnonzero(bitdiff.reshape(-1))[0]),delta.shape))
    return dict(port=label,exact_bitwise=exact,changed_components=int(np.count_nonzero(bitdiff)),
        maxabs=float(np.max(np.abs(delta))),argmax=list(point),
        actual_at_argmax=float(actual[point]),captured_GPU_at_argmax=float(expected[point]),
        status='EXACT' if exact else 'HOLD_CPU_GPU_LOCAL_REPLAY_NOT_EXACT')


def local_replay(arrays,field):
    """Each primitive uses captured actual operands; a mismatch never cascades or drops algebra."""
    prefix='head__'+field+'__'
    p,b,q=tensor(arrays['head__pos']),tensor(arrays['head__batch']),tensor(arrays[prefix+'charges'])
    center=tensor(arrays[prefix+'center']);indexed=tensor(arrays[prefix+'indexed_center'])
    relative=tensor(arrays[prefix+'relative']);product=tensor(arrays[prefix+'product'])
    moment_value=tensor(arrays[prefix+'moment'])
    operations=[
        ('center',lambda:compensated_pool(p,b,3,'mean')),
        ('indexed_center',lambda:center[b]),
        ('relative',lambda:p-indexed),
        ('product',lambda:q*relative),
        ('moment',lambda:compensated_index_add(torch.zeros((3,3),dtype=torch.float32),b,product))]
    if field==FIELDS[1]:
        operations.append(('output',lambda:compensated_norm3(moment_value,keepdim=True)))
    else:
        operations.append(('output',lambda:moment_value))
    controls=[]
    with torch.no_grad(),torch.autocast('cpu',enabled=False):
        for name,operation in operations:
            try:controls.append(exact_port(operation(),arrays[prefix+name],field+'/'+name))
            except Exception as error:
                controls.append(dict(port=field+'/'+name,status='HOLD_UNSUPPORTED_LOCAL_REPLAY',
                                     exact_bitwise=False,type=type(error).__name__,message=str(error)))
    exact=all(v['exact_bitwise'] for v in controls)
    return dict(field=field,all_actual_CPU_local_ports_bitwise_equal=exact,controls=controls,
                status='EXACT' if exact else 'HOLD_NO_CPU_GPU_ARITHMETIC_ATTRIBUTION',
                full_model_or_head_forward_calls=0,local_primitive_replay_only=True,
                actual_captured_operands_used_independently=True,
                does_not_prove_instruction_or_backend_identity=True)

def weights(base,field):
    prefix='head__'+field+'__parameter__'
    return {key:tensor(base[prefix+key],torch.float64) for key in PARAMETERS}


def readout(h,w):
    """Independent affine/SiLU/affine real-formula CPU64; no nn.Module."""
    h=tensor(h,torch.float64)
    with torch.no_grad():
        out=F.linear(F.silu(F.linear(h,w['0.weight'],w['0.bias'])),w['2.weight'],w['2.bias'])
    need(out.dtype==torch.float64 and out.shape==(44,1) and bool(torch.isfinite(out).all()),
         'Finite independent same-input charges reference required')
    return out


def sum_graph(value,batch):
    # Native physical atom order, three nonempty groups. FP64 reference, not production replay.
    return torch.stack([value[batch==i].sum(dim=0) for i in range(3)])


def norm(value):
    return torch.linalg.vector_norm(value,dim=-1,keepdim=True)


def moment(q,p,batch):
    count=torch.tensor([[3.],[9.],[32.]],dtype=torch.float64)
    center=sum_graph(p,batch)/count
    return sum_graph(q*(p-center[batch]),batch)


def phi(q,p,batch,magnitude):
    value=moment(q,p,batch)
    return norm(value) if magnitude else value


def lifted(value,R,magnitude):
    return value if magnitude else value@R


def steps(a,field):
    prefix='head__'+field+'__';magnitude=field==FIELDS[1]
    p=tensor(a['head__pos'],torch.float64);b=tensor(a['head__batch'])
    q=tensor(a[prefix+'charges'],torch.float64)
    raw=[moment(q,p,b),
         sum_graph(q*(p-tensor(a[prefix+'center'],torch.float64)[b]),b),
         sum_graph(q*tensor(a[prefix+'relative'],torch.float64),b),
         sum_graph(tensor(a[prefix+'product'],torch.float64),b),
         tensor(a[prefix+'moment'],torch.float64)]
    values=[norm(x) for x in raw] if magnitude else raw
    errors={name:values[i+1]-values[i] for i,name in enumerate(('E_center','E_relative','E_product','E_reduce'))}
    errors['E_norm']=(tensor(a[prefix+'output'],torch.float64)-values[-1]
                      if magnitude else torch.zeros_like(values[-1]))
    return p,b,q,values[0],errors


def checked_closure(left,right,label):
    error=float((left-right).abs().max())
    need(error<=CLOSURE,'Fixed same-component diagnostic closure failed: '+label+' maxabs='+repr(error))
    return error


def terminal_terms(base,moved,field,R,reference_charges):
    magnitude=field==FIELDS[1];prefix='head__'+field+'__'
    p0,b,q0,f0,e0=steps(base,field);pt,bt,qt,ft,et=steps(moved,field)
    need(torch.equal(b,bt),'Graph/native row mapping differs')
    qstar0,qstart=reference_charges
    F00=phi(qstar0,p0,b,magnitude);Ft0=phi(qstart,p0,b,magnitude)
    F0t=phi(qstar0,pt,b,magnitude);Ftt=phi(qstart,pt,b,magnitude)
    L=lambda x:lifted(x,R,magnitude)
    actual0=tensor(base[prefix+'output'],torch.float64)
    actualt=tensor(moved[prefix+'output'],torch.float64)
    terms={'D':actualt-L(actual0),'H':L(Ft0-F00),'G':F0t-L(F00)}
    terms['I']=Ftt-F0t-terms['H']
    terms['Q']=(ft-Ftt)-L(f0-F00)
    for name in e0:terms[name]=et[name]-L(e0[name])
    terms['E']=sum((terms[k] for k in e0),torch.zeros_like(terms['D']))
    closed=checked_closure(terms['D'],sum((terms[k] for k in ('H','G','I','Q','E')),torch.zeros_like(terms['D'])),field+'/D')
    for label,a,reference,errors in (('base',actual0,f0,e0),('moved',actualt,ft,et)):
        checked_closure(a-reference,sum(errors.values(),torch.zeros_like(a)),field+'/'+label+'/program_chain')
    qterms={'D':qt-q0,'H0_linked_readout':qstart-qstar0}
    qterms['readout_arithmetic']=(qt-qstart)-(q0-qstar0)
    checked_closure(qterms['D'],qterms['H0_linked_readout']+qterms['readout_arithmetic'],field+'/charges')
    return ({k:v.numpy() for k,v in terms.items()},
            {k:v.numpy() for k,v in qterms.items()},closed)


def inline_controls():
    """Independent tiny arithmetic/orientation controls in each actual CPU worker; no extra parent."""
    root=Path('/share/home/zixiao/descriptor_analysis/MFM_model_v3_geometry_fp32_candidate_v1/current')
    need(Path(phychem_mfm.__file__).resolve()==root/'phychem_mfm/__init__.py'
         and Path(numeric_source.__file__).resolve()==root/'phychem_mfm/model/v3_numeric_stability.py',
         'Only exact frozen geometry candidate numerical primitive namespace may execute')
    p=np.array([[0.,0.,0.],[2.,0.,0.]],dtype=np.float32)
    q=np.array([[1.],[3.]],dtype=np.float32);b=np.array([0,0],dtype=np.int64)
    # Independent two-atom centroid1, moment2; exercise the original primitive directly.
    c=compensated_pool(tensor(p),tensor(b),1,'mean')
    need(torch.equal(c,torch.tensor([[1.,0.,0.]])),'Independent centroid oracle')
    m=compensated_index_add(torch.zeros((1,3)),tensor(b),tensor(q)*(tensor(p)-c[tensor(b)]))
    need(torch.equal(m,torch.tensor([[2.,0.,0.]])),'Independent charge moment oracle')
    need(torch.equal(compensated_norm3(torch.tensor([[3.,4.,0.]]),keepdim=True),torch.tensor([[5.]])),
         'Independent3-4-5 norm oracle')
    # Independent nonzero three-graph program-order control, including a nonlinear norm path.
    a={'head__pos':np.zeros((44,3),dtype=np.float32),
       'head__batch':np.repeat(np.arange(3,dtype=np.int64),(3,9,32))}
    a['head__pos'][:3]=[[-1.,-1.,0.],[1.,0.,0.],[0.,1.,0.]]
    for field in FIELDS:
        prefix='head__'+field+'__'
        a[prefix+'charges']=np.zeros((44,1),dtype=np.float32);a[prefix+'charges'][:3,0]=[3.,6.,7.]
        a[prefix+'center']=np.zeros((3,3),dtype=np.float32);a[prefix+'center'][0,0]=.1875
        a[prefix+'relative']=np.zeros((44,3),dtype=np.float32)
        a[prefix+'product']=np.zeros((44,3),dtype=np.float32);a[prefix+'product'][0,2]=12.
        a[prefix+'moment']=np.zeros((3,3),dtype=np.float32);a[prefix+'moment'][0]=[5.,0.,12.]
        a[prefix+'output']=(np.array([[14.],[0.],[0.]],dtype=np.float32)
                            if field==FIELDS[1] else a[prefix+'moment'].copy())
    _,_,_,first,parts=steps(a,FIELDS[1])
    need(float(first[0,0])==5. and [float(parts[k][0,0]) for k in
         ('E_center','E_relative','E_product','E_reduce','E_norm')]==[-1.,-4.,12.,1.,1.]
         and float(sum(parts.values())[0,0])==9.,'Independent nonlinear moment/norm decomposition oracle')
    # Independent fixed program-order telescoping:4=.5+.25+1.25+2, not different maxima.
    pieces=[torch.tensor([[x]],dtype=torch.float64) for x in (.5,.25,1.25,2.)]
    need(float(sum(pieces).item())==4.,'Independent nonzero telescoping oracle')
    R=torch.tensor([[0.,1.,0.],[-1.,0.,0.],[0.,0.,1.]],dtype=torch.float64)
    need(torch.equal(torch.tensor([[2.,0.,0.]],dtype=torch.float64)@R,
                     torch.tensor([[0.,2.,0.]],dtype=torch.float64)),'Row-vector orientation oracle')
    return dict(original_primitive_controls=True,nonzero_program_chain=True,row_R=True,
                diagnostic_closure_absolute_bound=CLOSURE,full_model_or_head_instances=0)
