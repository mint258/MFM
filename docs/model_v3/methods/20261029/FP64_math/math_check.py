#!/usr/bin/env python3
"""FP64 mathematical check only. No compensated candidate or FP32 repair is used.

The frozen original realized F32 fixture/views are promoted BEFORE each F64
rigid transform. Full original baseline parameters are losslessly promoted;
all actual forward floating operands/results must be F64. This is distinct
from job 4521561, which promoted already-F32-transformed positions.
Criterion: abs(actual-reference)<=1e-9*abs(reference), including exact zero
when reference==0. No epsilon, polar projection, seed/scale change or retry.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from copy import deepcopy
import csv
from dataclasses import asdict, is_dataclass, fields, replace
import hashlib
import importlib.util
import inspect
import itertools
import json
import multiprocessing
import os
from pathlib import Path
import socket
import sys
import textwrap
import time
import traceback
from types import MethodType

BASE=Path('/share/home/zixiao/descriptor_analysis')
ROOT=BASE/'MFM_model_v3_composed_equivariance_runtime_v3'
SHADOW=BASE/'runs/model_v3_20261026/numeric_full_encoder_fp64_v1_source/encoder_reference_v1.py'
SHADOW_SHA='1dbf90dfb0e4faa8af6b93147aaf3235b22ff39142b32b0dea97fc5ab21c385c'
FIXTURE_SHA='0c49debe901ee5db79a71fcbc8541d426231c5090eb9740b84649e867d8df0e8'
CAPTURE=BASE/'runs/model_v3_20261025/fixed_h0_capture_GPU_v2_4521492/CAPTURE_MANIFEST.json'
CAPTURE_SHA='670bf0a21b113d1b11bad4cb82e7e6a3995ac789524fb48b285e4ab33ef713a4'
CASES=[f'{c}__{v}__{h}__seed{s}' for c,v,h,s in itertools.product(
    ('C1-0','C1-a','C1-b'),('two','three'),
    ('H1_fixed','H1_learned','H2_fixed','H3_fixed'),(20261026,20261027))]
RELATIVE=1e-9
CASE_OUTPUT_CAP=32<<20
TOTAL_OUTPUT_CAP=2<<30
T=None
E=None
REF=None
AUTHORITY=None


def need(ok,message):
    if not ok:raise ValueError(message)


def rawref(path,maximum=16<<20):
    path=Path(path).absolute()
    need(path.is_file() and not path.is_symlink() and path.stat().st_size<=maximum,
         'Bounded regular metadata/source required: '+str(path))
    raw=path.read_bytes()
    return dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def read_bound(ref,maximum=2<<20):
    need(type(ref) is dict and set(ref)=={'path','bytes','sha256'}
         and rawref(ref['path'],maximum)==ref,'Actual raw metadata reference differs')
    return json.loads(Path(ref['path']).read_bytes())


def save(path,value):
    raw=(json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
    need(len(raw)<=16<<20,'Output metadata limit exceeded')
    with Path(path).open('xb') as stream:
        stream.write(raw);stream.flush();os.fsync(stream.fileno())


def module_source_refs():
    paths={Path(__file__).absolute(),SHADOW,ROOT/'workflows/sprime_s/scripts/s_model_memory_v1.py'}
    paths.update((ROOT/'current/phychem_mfm').rglob('*.py'))
    for name,module in list(sys.modules.items()):
        if name.startswith('phychem_mfm') or name.startswith('model_v3_architecture_s_memory_'):
            value=getattr(module,'__file__',None)
            if value and Path(value).suffix=='.py':paths.add(Path(value).absolute())
    need(all(p==SHADOW or p==Path(__file__).absolute() or p.is_relative_to(ROOT) for p in paths),
         'Foreign baseline package/source origin')
    return {str(p):rawref(p) for p in sorted(paths)}


def init_worker():
    global T,E,REF,AUTHORITY
    need(os.environ.get('CUDA_VISIBLE_DEVICES')=='','CPU-only worker required')
    sys.path.insert(0,str(ROOT/'current'))
    import torch
    import phychem_mfm
    from phychem_mfm.phase1 import v3_composed_equivariance as equation
    need(Path(phychem_mfm.__file__).resolve()==(ROOT/'current/phychem_mfm/__init__.py').resolve(),
         'Only original uncompensated baseline namespace allowed')
    need(rawref(equation.__file__)['sha256']==FIXTURE_SHA,'Original fixture source changed')
    need(rawref(SHADOW)['sha256']==SHADOW_SHA,'Existing FP64 shadow source changed')
    need(rawref(CAPTURE)['sha256']==CAPTURE_SHA,'Original parameter capture metadata changed')
    torch.set_num_threads(4);torch.set_num_interop_threads(1)
    torch.set_float32_matmul_precision('highest')
    torch.backends.cudnn.allow_tf32=False
    # Do not initialize CUDA, change original weights/default dtype or enable AMP.
    spec=importlib.util.spec_from_file_location('original_encoder_FP64_math_reference',SHADOW)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    T,E,REF=torch,equation,module
    AUTHORITY=json.loads(CAPTURE.read_bytes())
    need(AUTHORITY['status']=='CAPTURE_COMPLETE' and AUTHORITY['job_id']=='4521492',
         'Original completed seeded parameter authority required')
    need([s.identity for s in E.CASE_SPECS]==CASES,'Exact original ordered complete48 required')
    need(torch.get_default_dtype()==torch.float32,'Original F32 initialization dtype changed')
    need(not torch.cuda.is_initialized(),'CPU mathematical worker initialized CUDA')


def typed_header(value):
    return REF.tensor_header(value)


def install_head_reference(model):
    """Three clone-only literal dtype lifts, original real formulas unchanged."""
    from phychem_mfm.model.v3_heads import V3HeadBank,_PairHead,_DipoleHead
    lifted=[]
    for module in model.pd_heads.modules():
        cls=type(module)
        expected={V3HeadBank:(5,2),_PairHead:(3,0),_DipoleHead:(4,0)}.get(cls)
        if expected is None:continue
        original=cls.forward
        source=textwrap.dedent(inspect.getsource(original))
        need((source.count('.float()'),source.count('torch.float32'))==expected,
             'Original head cast/guard source differs: '+cls.__name__)
        changed=source.replace('.float()','.to(dtype=torch.float64)').replace('torch.float32','torch.float64')
        namespace=dict(original.__globals__)
        exec(compile(changed,'<FP64_math_'+cls.__name__+'>','exec'),namespace)
        module.forward=MethodType(namespace['forward'],module)
        lifted.append(dict(class_name=cls.__name__,float_casts_lifted=expected[0],
            dtype_guards_lifted=expected[1],
            original_forward_sha256=hashlib.sha256(source.encode()).hexdigest(),
            reference_forward_sha256=hashlib.sha256(changed.encode()).hexdigest()))
    need(sum(r['class_name']=='V3HeadBank' for r in lifted)==1
         and sum(r['class_name']=='_PairHead' for r in lifted)==1
         and sum(r['class_name']=='_DipoleHead' for r in lifted)==2,
         'All original PD pair and two independent dipole heads must be lifted')
    return lifted


def build_reference(spec):
    original,registry=E.build_composition(spec)  # Original CPU seed/order/assignments.
    summary=E.weight_summary(original)
    rows=[r for r in AUTHORITY['cases'] if r['case_id']==spec.identity]
    need(len(rows)==1,'One original parameter authority per case required')
    authority_ref=rows[0]['capture_case'];old=read_bound(authority_ref)
    weight=old['original_measurement']['weight_summary']
    need(old['original_measurement']['case_id']==spec.identity
         and old['original_measurement']['case']==asdict(spec)
         and old['original_measurement']['registry_sha256']==registry.content_sha256,
         'Original case/seed/registry authority differs')
    need(summary['all_named_parameter_sha256']==weight['all_named_parameter_sha256']
         and summary['parameters']==weight['parameters'],'Original complete named tensor parameters differ')
    clone=deepcopy(original)
    REF._same_state(original.state_dict(),clone.state_dict())
    encoder,mapping=REF.strict_fp64_encoder_copy(original.encoder)
    clone.encoder=encoder
    clone.pd_heads.double()
    clone.eval()
    old_state,new_state=original.state_dict(),clone.state_dict()
    need(set(old_state)==set(new_state),'Complete state key membership differs')
    castback_checks=0
    for key,value in old_state.items():
        other=new_state[key]
        if isinstance(value,T.Tensor):
            if value.is_floating_point():
                need(value.dtype==T.float32 and other.dtype==T.float64
                     and typed_header(value)==typed_header(other.to(T.float32)),
                     'Full parameter/buffer promotion is not lossless: '+key)
                castback_checks+=1
            else:need(typed_header(value)==typed_header(other),'Nonfloating state changed')
        else:need(value==other,'Original extra_state semantic identity changed')
    need(all(not p.is_floating_point() or p.dtype==T.float64 for p in clone.parameters())
         and all(not b.is_floating_point() or b.dtype==T.float64 for b in clone.buffers()),
         'All cloned floating parameters/buffers must be F64')
    need(not any(hasattr(m,'numeric_mode') and m.numeric_mode!='legacy' for m in clone.modules()),
         'Compensated candidate is forbidden in this mathematical check')
    head_lifts=install_head_reference(clone)
    return clone,registry,dict(original_parameter_summary=summary,original_capture_case=authority_ref,
        lossless_full_floating_state_castback_checks=castback_checks,
        state_castback_scope='Identity verification outside all mathematical forwards only',
        head_dtype_lifts=head_lifts,geometry_policy=REF.geometry_policy(clone.encoder),
        encoder_reference_mapping_keys=len(mapping))


def floating_tensors(value):
    if isinstance(value,T.Tensor):
        if value.is_floating_point() or value.is_complex():yield value
    elif isinstance(value,dict):
        for item in value.values():yield from floating_tensors(item)
    elif isinstance(value,(list,tuple)):
        for item in value:yield from floating_tensors(item)
    elif is_dataclass(value):
        for field in fields(value):yield from floating_tensors(getattr(value,field.name))
    elif hasattr(value,'to_dict'):
        yield from floating_tensors(value.to_dict())


def fp64(value,label):
    for tensor in floating_tensors(value):
        need(tensor.dtype==T.float64 and tensor.device.type=='cpu',
             'Hidden non-F64 floating port: '+label+' '+str(tensor.dtype))
        need(bool(T.isfinite(tensor).all()),'Nonfinite FP64 port: '+label)


def mathematical_forward(model,views,pairs,registry,observed):
    from torch.overrides import TorchFunctionMode
    class FullFP64Audit(TorchFunctionMode):
        def __init__(self):super().__init__();self.calls=0;self.operands=0;self.results=0
        def __torch_function__(self,func,types,args=(),kwargs=None):
            kwargs={} if kwargs is None else kwargs
            # Dtype checks inspect storage metadata; never cast/replace a tensor.
            for value in floating_tensors((args,kwargs)):
                need(value.dtype==T.float64 and value.device.type=='cpu',
                     'Non-F64 actual floating operand in '+getattr(func,'__name__',str(func)))
                self.operands+=1
            result=func(*args,**kwargs);self.calls+=1
            for value in floating_tensors(result):
                need(value.dtype==T.float64 and value.device.type=='cpu',
                     'Non-F64 actual floating result in '+getattr(func,'__name__',str(func)))
                self.results+=1
            return result
    handles=[]
    ports={}
    def after(name):
        def hook(module,args,result):
            # Only actual module floating port dtypes, no replacements or arithmetic.
            inputs=list(floating_tensors(args));outputs=list(floating_tensors(result))
            need(all(v.dtype==T.float64 for v in inputs+outputs),'Non-F64 module input/output: '+name)
            row=ports.setdefault(name,dict(class_name=type(module).__name__,calls=0,inputs=0,outputs=0))
            row['calls']+=1;row['inputs']+=len(inputs);row['outputs']+=len(outputs)
        return hook
    for name,module in model.named_modules():handles.append(module.register_forward_hook(after(name)))
    old_dtype=T.get_default_dtype();audit=FullFP64Audit();terminals_complete=False
    try:
        T.set_default_dtype(T.float64)
        fp64(views.batch,'full original physical input')
        with T.inference_mode(),T.autocast(device_type='cpu',enabled=False),audit:
            prediction=model.forward_pretrain(views,enabled_groups=('S','D','P'),pair_indices=pairs)
        fp64(prediction,'full model output')
        tables=E._terminals(prediction,registry)
        need(len(tables)==13 and all(v[0].dtype==T.float64 for v in tables.values()),
             'All13 original F64 terminal fields required')
        need(prediction.clean_h0.shape==(44,512),'Original canonical44 H0 location changed')
        need(T.equal(prediction.clean_h0,prediction.source_outputs.atom_repr[views.clean_atom_rows]),
             'PD does not consume actual same-forward clean H0')
        need(ports.get('encoder.backbone',{}).get('calls')==1,'Exactly one full encoder call required')
        need(ports.get('encoder.geometry_head',{}).get('calls')==1
             and ports.get('encoder.element_head',{}).get('calls')==1
             and ports.get('encoder.bond_head',{}).get('calls')==1,
             'Actual S geometry/element/bond head coverage required')
        terminals_complete=True
        return prediction,tables
    finally:
        observed.append(dict(function_calls=audit.calls,floating_operands=audit.operands,
            floating_results=audit.results,complete_terminal_outputs=terminals_complete,
            all_observed_floating_ports_CPU_FP64=terminals_complete,module_ports=ports,
            complete_encoder_forwards=ports.get('encoder.backbone',{}).get('calls',0)))
        for handle in handles:handle.remove()
        T.set_default_dtype(old_dtype)


def run_case(index,out_root):
    import numpy as np
    started=time.monotonic();spec=E.CASE_SPECS[index]
    out=Path(out_root)/('case_%02d'%index);out.mkdir()
    arrays={};observed=[];failure=None;model=None
    source_before={};source_after={};csv_rows=0;bad_elements=0;rows=[]
    result=dict(case_id=spec.identity,case=asdict(spec),status='ERROR',passed=False,
        reference_rule='abs(actual-reference)<=1e-9*abs(reference); zero reference requires exact delta0',
        relative_tolerance=RELATIVE,absolute_epsilon=0,full_H0_byte_replay_of_1561=False)
    try:
        model,registry,identity=build_reference(spec)
        result['identity']=identity
        source_before=module_source_refs()
        base=E.fixture_batch()
        builder=E.build_two_structural_views if spec.views=='two' else E.build_structural_views
        original=builder(base,ordinals=E.ORDINALS,config=E.VIEW_CONFIGURATION)
        data=original.batch.clone();promotions={}
        for key,value in list(data):
            if isinstance(value,T.Tensor) and value.is_floating_point():
                before=typed_header(value);converted=value.to(T.float64)
                need(typed_header(converted.to(value.dtype))==before,'Input promotion lost original fixture bytes')
                promotions[key]=dict(original=before,promoted=typed_header(converted))
                data[key]=converted
        need(data.pos.dtype==data.target_pos.dtype==T.float64,'Promote before any rigid transform')
        original=replace(original,batch=data)
        result['input_definition']=dict(
            original_realized_F32_fixture_views_preserved_then_losslessly_promoted=True,
            promotions=promotions,rigid_transforms_evaluated_entirely_FP64=True,
            transformed_positions_roundback_to_FP32=False,
            difference_from_1561='1561 promoted already-F32-transformed inputs; this run transforms promoted original views in F64',
            physical_graph_counts=(data.ptr[1:]-data.ptr[:-1]).tolist(),
            original_discrete_view_identity=E._view_identity(original))
        result['domain']=E.geometry_domain(original)
        pairs={'p_pair':base.rdkit_bond_index}
        prediction,tables=mathematical_forward(model,original,pairs,registry,observed)
        base_edges=E._edge_identity(model.encoder.geometry_head,original)
        for name,(value,law,unit,nonzero) in tables.items():
            arrays['original__'+name.replace('/','__')]=value.detach().numpy().copy()
        csv_path=out/'comparisons.csv'
        with csv_path.open('x',newline='',encoding='utf-8') as stream:
            writer=csv.writer(stream)
            writer.writerow(('case_id','transform','field','row','component','reference','actual',
                             'signed_delta','allowed_absolute_delta','reference_is_zero','passed'))
            for number,transform in enumerate(E.transforms()):
                moved=original.batch.clone()
                moved.pos=data.pos@transform.rotation+transform.translation
                moved.target_pos=data.target_pos@transform.rotation+transform.translation
                pushed=replace(original,batch=moved)
                need(E._view_identity(pushed)==E._view_identity(original),'Discrete physical views changed')
                other,actual_tables=mathematical_forward(model,pushed,pairs,registry,observed)
                need(tuple(actual_tables)==tuple(tables),'Complete field ordering changed')
                edges=E._edge_identity(model.encoder.geometry_head,pushed)
                edge_equal=(edges==base_edges)
                field_rows=[]
                for field,(reference,law,unit,required_nonzero) in tables.items():
                    actual=actual_tables[field][0].detach()
                    expected=E.transform_expected(reference,transform,law)
                    need(actual.dtype==expected.dtype==T.float64 and actual.shape==expected.shape
                         and actual.ndim==2 and actual.numel()>0,'Complete corresponding F64 terminal matrices required')
                    finite=bool(T.isfinite(actual).all() and T.isfinite(expected).all())
                    delta=actual-expected;bound=RELATIVE*expected.abs()
                    good=T.isfinite(delta)&T.isfinite(expected)&(delta.abs()<=bound)
                    nonzero=(not required_nonzero or
                        (float(reference.norm(dim=-1).max())>E.NONZERO_NORM_FLOOR
                         and float(actual.norm(dim=-1).max())>E.NONZERO_NORM_FLOOR))
                    failures=int((~good).sum());bad_elements+=failures
                    for r in range(actual.shape[0]):
                        for c in range(actual.shape[1]):
                            writer.writerow((spec.identity,transform.name,field,r,c,
                                format(float(expected[r,c]),'.17g'),format(float(actual[r,c]),'.17g'),
                                format(float(delta[r,c]),'.17g'),format(float(bound[r,c]),'.17g'),
                                bool(expected[r,c]==0),bool(good[r,c])))
                            csv_rows+=1
                    arrays['transform%d__'%number+field.replace('/','__')]=actual.numpy().copy()
                    worst=int(delta.abs().reshape(-1).argmax());r,c=divmod(worst,actual.shape[1])
                    field_rows.append(dict(field=field,law=law,unit=unit,shape=list(actual.shape),
                        elements=actual.numel(),failed_elements=failures,
                        zero_reference_elements=int((expected==0).sum()),
                        finite=finite,nonzero_control_pass=nonzero,
                        maxabs=float(delta.abs().max()) if finite else None,
                        argmax=dict(row=r,component=c,reference=float(expected[r,c]),
                                    actual=float(actual[r,c]),signed_delta=float(delta[r,c])),
                        passed=finite and nonzero and failures==0))
                rows.append(dict(transform=transform.document(),fields=field_rows,
                    native_vector_edges_unchanged=edge_equal,
                    masks_bonds_unchanged=bool(T.equal(prediction.source_outputs.node_mask,other.source_outputs.node_mask)
                        and T.equal(prediction.source_outputs.bond.pair_index,other.source_outputs.bond.pair_index)),
                    transformed_noise_push_residual_A=float(((moved.pos-moved.target_pos)
                        -(data.pos-data.target_pos)@transform.rotation).abs().max())))
                stream.flush();os.fsync(stream.fileno())
                need(stream.tell()<=CASE_OUTPUT_CAP,'Per-case CSV output limit exceeded')
        need(len(observed)==4 and all(r['complete_terminal_outputs'] for r in observed)
             and len(rows)==3 and all(len(r['fields'])==13 for r in rows),
             'All original4role/13field/3transform coverage required')
        passed=(result['domain']['domain_pass'] and all(r['native_vector_edges_unchanged']
            and r['masks_bonds_unchanged'] and all(f['passed'] for f in r['fields']) for r in rows))
        result.update(status='PASS' if passed else 'MATHEMATICAL_CRITERION_FAIL',passed=passed)
    except BaseException as error:
        failure=dict(type=type(error).__name__,message=str(error),traceback=traceback.format_exc())
    finally:
        if model is not None:REF.close_analysis_forwards(model.encoder.backbone)
        if arrays:
            need(all(a.dtype==np.float64 for a in arrays.values()),'Only actual F64 output archive allowed')
            np.savez_compressed(out/'outputs.npz',**arrays)
            with (out/'outputs.npz').open('rb') as stream:os.fsync(stream.fileno())
            result['output_archive']=rawref(out/'outputs.npz',CASE_OUTPUT_CAP)
            result['output_archive_contains_parameter_weights']=False
            result['output_arrays']={k:dict(dtype=str(a.dtype),shape=list(a.shape),bytes=a.nbytes) for k,a in arrays.items()}
        try:
            source_after=module_source_refs()
            need(source_after==source_before,'Original source graph changed during case')
        except BaseException as error:
            failure=dict(earlier=failure,source_after_error=str(error))
        result.update(failure=failure,measurements=rows,actual_forward_audits=observed,
            actual_complete_FP64_encoder_forwards=sum(r['complete_encoder_forwards'] for r in observed),FP32_encoder_forwards=0,
            failed_elements=bad_elements,comparison_CSV_rows=csv_rows,
            source_before=source_before,source_after=source_after,source_equal=(source_after==source_before),
            wall_seconds=time.monotonic()-started,scientific_adoption=False,
            scope='NEW_FP64_MATHEMATICAL_ACCEPTANCE_ONLY_NO_FP32_REPAIR_OR_DEPLOYMENT_CANDIDATE')
        if failure is not None:result.update(status='ERROR',passed=False)
        if (out/'comparisons.csv').is_file():result['comparison_CSV']=rawref(out/'comparisons.csv',CASE_OUTPUT_CAP)
        result['CUDA_initialized']=bool(T.cuda.is_initialized())
        need(sum(p.stat().st_size for p in out.iterdir() if p.is_file())<CASE_OUTPUT_CAP-(1<<20),
             'Combined per-case output exceeds fixed32MiB reserve')
        save(out/'case.json',result)
    return dict(case_id=spec.identity,status=result['status'],passed=result['passed'],
        complete_FP64_encoder_forwards=sum(r['complete_encoder_forwards'] for r in observed),failed_elements=bad_elements,
        failed_field_transform_records=sum(not f['passed'] for r in rows for f in r['fields']),
        case_json=rawref(out/'case.json'),error=failure,CUDA_initialized=result['CUDA_initialized'])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--expected-node',required=True)
    args=parser.parse_args()
    need(os.name=='posix' and os.environ.get('SLURM_JOB_ID','').isdigit(),'Actual Linux CPU Slurm job required')
    need(os.environ.get('SLURM_CPUS_PER_TASK')=='16' and os.environ.get('CUDA_VISIBLE_DEVICES')=='',
         'CPU16-only execution required')
    need(socket.gethostname().split('.')[0]==args.expected_node,'Actual CPU node differs')
    need(args.expected_node in ['compute-0-'+str(i) for i in (2,*range(8,20))],'CPU partition node required')
    need(not args.output.exists(),'Fresh output required; never overwrite old results')
    args.output.mkdir(parents=True)
    start=time.monotonic();rows={}
    # Parent has not imported Torch/BLAS. Fork-only CPU workers avoid CUDA/fork
    # and post-fork exec identity transitions; each independently imports Torch.
    with ProcessPoolExecutor(max_workers=4,mp_context=multiprocessing.get_context('fork'),
                             initializer=init_worker) as pool:
        pending={pool.submit(run_case,i,str(args.output)):i for i in range(48)}
        for future in as_completed(pending):
            i=pending[future]
            try:rows[i]=future.result()
            except BaseException as error:
                rows[i]=dict(case_id=CASES[i],status='ERROR',passed=False,
                    complete_FP64_encoder_forwards=0,failed_elements=None,failed_field_transform_records=None,
                    error=dict(type=type(error).__name__,message=str(error)))
    ordered=[rows[i] for i in range(48)]
    size=sum(p.stat().st_size for p in args.output.rglob('*') if p.is_file())
    need(size<TOTAL_OUTPUT_CAP-(2<<20),'Whole output exceeds original2GiB bound')
    counts=dict(cases=48,passed=sum(r['status']=='PASS' for r in ordered),
        mathematical_failures=sum(r['status']=='MATHEMATICAL_CRITERION_FAIL' for r in ordered),
        errors=sum(r['status']=='ERROR' for r in ordered),
        complete_FP64_encoder_forwards=sum(r['complete_FP64_encoder_forwards'] for r in ordered),
        FP32_encoder_forwards=0)
    passed=counts['passed']==48 and counts['errors']==0 and counts['complete_FP64_encoder_forwards']==192
    summary=dict(schema='model_v3_equivariance_v2_FP64_math_v1',
        status='PASS' if passed else 'FAIL',passed=passed,counts=counts,cases=ordered,
        relative_tolerance=RELATIVE,absolute_epsilon=0,
        zero_reference_requires_exact_zero_delta=True,seed_scale_fixture_or_rotation_selection=False,
        input_definition='Original realized F32 base/views/noise/masks preserved, then losslessly promoted BEFORE F64 R/t; no transformed-F32 roundback',
        distinction_from_1561='192 fresh complete original-baseline F64 forwards including all13 terminal fields; not historical H0-only evidence',
        model_path='Original uncompensated runtime_v3; clone-only dtype-preserving shadow/three PD dtype lifts',
        CPU_workers=4,torch_threads_per_worker=4,
        CUDA_initialized=False if all(r.get('CUDA_initialized') is False for r in ordered) else None,
        state_castback_checks_outside_forward_only=True,
        runtime_node=args.expected_node,job_id=os.environ['SLURM_JOB_ID'],
        memory_allocation_guarantee_claimed=False,whole_output_bytes_before_summary=size,
        wall_seconds=time.monotonic()-start,scientific_adoption=False,
        no_FP32_compensated_candidate_or_repairs=True,actual_native_data_reads=0)
    save(args.output/'summary.json',summary)
    if passed:save(args.output/'COMPLETE.json',dict(summary=rawref(args.output/'summary.json')))
    print(json.dumps(dict(summary=rawref(args.output/'summary.json'),counts=counts),sort_keys=True))
    return 0 if passed else 1


if __name__=='__main__':raise SystemExit(main())
