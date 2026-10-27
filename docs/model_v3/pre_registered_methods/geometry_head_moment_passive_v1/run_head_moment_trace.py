#!/usr/bin/env python3
"""One original complete48/192-forward passive trace; no numerical candidate."""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import traceback

HERE=Path(__file__).absolute().parent
B=Path('/share/home/zixiao/descriptor_analysis')
OLD=B/'runs/model_v3_20261026/geometry_fp32_e2e_v1_source'
META_CAP=2<<20
INPUT_CAP=128<<20  # GPU inputs only original terminal/control; CPU trace consumer will use512MiB.

def require(ok,message):
    if not ok: raise ValueError(message)

def ref(path,maximum=META_CAP):
    path=Path(path).absolute()
    require(path.is_file() and not path.is_symlink() and path.stat().st_size<=maximum,'Bounded ordinary input required: '+str(path))
    raw=path.read_bytes()
    return dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())

def bound(leaf):
    require(set(leaf)=={'path','bytes','sha256'} and ref(leaf['path'])==leaf,'Exact metadata rawref differs')
    return json.loads(Path(leaf['path']).read_bytes())

def load_file(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    return module

def metadata_selfcheck():
    # Reuse only the original metadata checks, never its model/pytest entry.
    return load_file(OLD/'run_geometry_matrix.py','_passive_old_metadata').metadata_selfcheck()

def verify_publication(request):
    require(request['status']=='FINAL_BOUND_PUBLIC_GEOMETRY_HEAD_MOMENT_TRACE_REQUEST','Draft cannot admit a GPU')
    sys.path.insert(0,str(OLD))
    try:
        original=bound(request['geometry_request'])
        old=load_file(OLD/'run_geometry_matrix.py','_passive_old_publication')
        rows=old.verify_publication(original)
    finally:
        sys.path.remove(str(OLD))
    negative=bound(request['baseline4579_Root_closure'])
    require(negative['job_id']=='4524579'
            and negative['status']=='ACTUAL_COMPLETE48_GEOMETRY_FP32_SCIENTIFIC_CRITERION_FAIL_15_PASS_33_FAIL_SOURCE_RESOURCE_CLOSED'
            and negative['result']==request['baseline4579_result']
            and negative['request']==request['geometry_request']
            and negative['supervisor']==request['baseline4579_supervisor']
            and negative['all_sources_before_after_current_equal'] is True
            and negative['private_cleanup_and_recorded_processes_closed'] is True
            and negative['formal_FP32_gate_satisfied'] is False,
            'Original complete negative geometry/source/resource authority differs')
    proof=bound(request['trace_method_publication'])
    require(proof['schema']=='model_v3_exact_tree_publication_actual_v1'
            and proof['branch']=='model-v3' and proof['repository_full_name']=='mint258/MFM'
            and proof['public_branch_readback_verified'] is True
            and proof['public_Git_API_tree_readback_verified'] is True,'Actual Root method publication/readback required')
    published={v['path']:v for v in proof['files']}
    expected=request['trace_method_files']
    names={'head_ports.py','passive_capture.py','run_head_moment_trace.py','prepare_metadata.py',
           'launch_passive_trace_GPU_v1.py','run_passive_trace_GPU_v1.sbatch',
           'PROTOCOL_README.md','inputs_DRAFT.json','dependencies.json','PLAN.md'}
    require(len(expected)==len({v['runtime_path'] for v in expected})==10
            and {Path(v['runtime_path']).name for v in expected}==names
            and len(published)==len(proof['files']), 'Complete exact ten-leaf method source map required')
    for leaf in expected:
        name=Path(leaf['runtime_path']).name
        require(leaf['runtime_path']==str(HERE/name) and leaf['repository_relative_path']==
                'docs/model_v3/pre_registered_methods/geometry_head_moment_passive_v1/'+name,
                'Only this exact new passive-method runtime/published path may execute')
        current=ref(leaf['runtime_path'])
        require(current==dict(path=leaf['runtime_path'],bytes=leaf['bytes'],sha256=leaf['sha256']),
                'Published method raw source differs')
        raw=Path(current['path']).read_bytes()
        blob=hashlib.sha1(b'blob '+str(len(raw)).encode()+bytes([0])+raw).hexdigest()
        item=published[leaf['repository_relative_path']]
        require(item['type']=='blob' and item['sha']==leaf['git_blob_sha']==blob,'Trace method Git blob differs')
    return dict(original_candidate_and_method=rows,passive_method=request['trace_method_publication'],
                passive_method_files=expected,scientific_adoption=False)

def source_snapshot(request,pins_sha):
    pins=bound({**ref(HERE/'source_pins_v1.json'),'sha256':pins_sha})
    require(pins['schema']=='model_v3_geometry_head_moment_passive_GPU_launch_source_pins_v1','Dedicated final launch pins required')
    values=request['source_refs']+pins['files']+pins['protected_dependencies']
    sources={}
    for leaf in values:
        require(leaf['path'] not in sources or sources[leaf['path']]==leaf,'Conflicting source refs')
        sources[leaf['path']]=leaf
    sources[str(HERE/'source_pins_v1.json')]=ref(HERE/'source_pins_v1.json')
    sources[str(HERE/'execution_request_v1.json')]=ref(HERE/'execution_request_v1.json')
    controls=list(sources.values())+[v['case_json'] for v in request['baseline_cases']]+[
        {k:v['actual_terminal_output_artifact'][k] for k in ('path','bytes','sha256')} for v in request['baseline_cases']]
    physical={}
    for leaf in controls:
        path=Path(leaf['path']);st=path.stat()
        require(path.is_file() and not path.is_symlink() and st.st_size==leaf['bytes'],'Selected source/terminal input stat differs')
        key=(st.st_dev,st.st_ino)
        require(key not in physical or physical[key]==st.st_size,'Conflicting selected physical input')
        physical[key]=st.st_size
    require(sum(physical.values())<=INPUT_CAP,'Selected source/metadata/terminal input exceeds128MiB')
    for leaf in sources.values():
        require(ref(leaf['path'],maximum=16<<20)==leaf,'Source changed before capture')
    verify_publication(request)
    return sources

def terminal_control(saved,measured):
    import numpy as np
    require(saved['case_id']==measured['case_id'] and saved['case']==measured['case']
            and saved['encoder_configuration']==measured['encoder_configuration'],'4579 case/config identity differs')
    keys=('registry_sha256','fixture_geometry_sha256','original_physical_geometry_sha256',
          'original_view_identity_sha256','encoder_forward_shapes','complete_terminal_count','weight_summary','fixture_native_atoms')
    for key in keys: require(saved[key]==measured[key],'4579 fixture/state/row identity differs: '+key)
    require(measured['complete_terminal_count']==13,'Original13 fields required')
    a,b=saved['actual_terminal_output_artifact'],measured['actual_terminal_output_artifact']
    require(len(a['arrays'])==len(b['arrays'])==52 and a['arrays']==b['arrays']
            and a['contains_parameter_weights'] is False and b['contains_parameter_weights'] is False,
            'All52 terminal headers and their unchanged no-weights provenance required')
    require(ref(a['path'],maximum=512<<10)=={k:a[k] for k in ('path','bytes','sha256')},'4579 terminal input raw bytes changed')
    controls=[]
    with np.load(a['path'],allow_pickle=False) as old,np.load(b['path'],allow_pickle=False) as fresh:
        require(set(old.files)==set(fresh.files)==set(a['arrays']),'All52 terminal key coverage differs')
        for key in sorted(old.files):
            left,right=old[key],fresh[key]
            require(left.dtype==right.dtype==np.float32 and left.shape==right.shape and np.isfinite(left).all()
                    and np.isfinite(right).all(),'Terminal type/shape/finiteness differs')
            controls.append(dict(array=key,bitwise_equal=left.tobytes()==right.tobytes()))
    require(ref(a['path'],maximum=512<<10)=={k:a[k] for k in ('path','bytes','sha256')},'4579 terminal changed while comparing')
    return dict(arrays=controls,baseline_passed=saved['passed'],fresh_passed=measured['passed'],
                passed=all(v['bitwise_equal'] for v in controls) and measured['passed']==saved['passed'],
                scope='52_SAME_FORWARD_TERMINALS_EXTERNAL_4579_NOT_OLD_HIDDEN_H0')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request',type=Path,required=True)
    parser.add_argument('--request-sha256',required=True)
    parser.add_argument('--output-root',type=Path,required=True)
    parser.add_argument('--admit-only',action='store_true')
    args=parser.parse_args()
    request=bound({**ref(args.request),'sha256':args.request_sha256})
    require(request['schema']=='model_v3_geometry_head_moment_passive_GPU_request_v1'
            and request['expected_case_count']==48 and request['trace_cap_bytes']==512<<20
            and request['trace_role_cap_bytes']==4<<20 and request['full_FP64_encoder_forwards']==0
            and request['geometry_mode']=='residual_expansion_fp32_v1', 'Fixed passive complete48 trace required')
    require(os.environ.get('MODEL_V3_NUMERIC_GPU_REQUEST_SHA')==args.request_sha256
            and os.environ.get('MODEL_V3_EXPECTED_NODE')==request['node']==socket.gethostname().split('.')[0]
            and os.environ.get('CUDA_VISIBLE_DEVICES')==request['gpu_uuid']
            and os.environ.get('SLURM_JOB_ID','').isdigit(),'Actual assigned GPU job required')
    sources=source_snapshot(request,os.environ['MODEL_V3_NUMERIC_GPU_LAUNCH_PINS_SHA'])
    if args.admit_only:
        leaf=request['UUID_admission_source']
        require(ref(leaf['path'])==leaf,'Original CUDA UUID admission differs')
        module=load_file(leaf['path'],'_passive_actual_CUuuid')
        value=module.admit_runtime(dict(device='cuda:0',expected_node=request['node'],gpu_uuid=request['gpu_uuid']))
        old=load_file(OLD/'run_geometry_matrix.py','_passive_old_admission_writer')
        old.save(args.output_root/'CUDA_UUID_ADMISSION.json',value)
        return 0
    out=args.output_root.absolute()
    require(not out.exists(),'Fresh passive trace output required');out.mkdir()
    sys.path.insert(0,str(OLD))
    from passive_capture import TraceBudget,passive_composition
    budget=TraceBudget(out)
    budget.json(out/'sources_before.json',sources)
    budget.json(out/'PUBLIC_METHOD_IDENTITY.json',verify_publication(request))
    rows,failures,after=[],[],None
    try:
        subprocess.run([sys.executable,'-B',str(Path(__file__).absolute()),'--request',str(args.request),
            '--request-sha256',args.request_sha256,'--output-root',str(out),'--admit-only'],check=True)
        budget.adopt(out/'CUDA_UUID_ADMISSION.json')
        require(os.environ.get('PYTHONPATH','').split(':')[0]==str(Path(request['repository'])/'current'),'Single immutable candidate namespace required')
        adapter=load_file(OLD/'geometry_adapter.py','_passive_published_projection_adapter')
        equation=adapter.load_equation()
        reference=load_file(request['encoder_reference_source']['path'],'_passive_frozen_stage_references')
        local=load_file(request['local_observer_source']['path'],'_passive_frozen_local_refs')
        require([c.identity for c in equation.CASE_SPECS]==request['expected_case_ids'],'Original full48 order differs')
        for ordinal,case in enumerate(equation.CASE_SPECS):
            budget.reserve_case()
            directory=out/('case_%02d'%ordinal);directory.mkdir()
            holder,measured,control,construction=None,None,None,None
            error=None
            try:
                with adapter.geometry_composition(equation,request['original1492_parameter_sha256'][case.identity]) as construction:
                    with passive_composition(equation,reference,local,directory,budget) as holder:
                        measured=equation.measure_case(case,device='cuda:0',threads=1,terminal_output_directory=directory)
                saved=bound(request['baseline_cases'][ordinal]['case_json'])['measured']
                control=terminal_control(saved,measured)
                require(construction[0]['original_parameter_sha256']==construction[0]['actual_parameter_sha256']
                        ==request['original1492_parameter_sha256'][case.identity],'1492 original full seeded parameter identity differs')
                require(len(construction)==1 and len(construction[0]['projection_ports'])==48
                        and all(p['all_observed_projection_floating_ports_CUDA_FP32'] for p in construction[0]['projection_ports']),
                        'Original twelve projection sites/four frames coverage differs')
                geometry_ports=construction[0]['geometry_ports']
                expected_geometry=([('dense_layer',i,True) for _ in range(4) for i in range(6)]
                    if case.distance_bias=='C1-0' else [('shared_pair_encoder',None,False)]*4)
                require([(p['caller'],p['layer'],p['squared']) for p in geometry_ports]==expected_geometry
                        and all(p['all_observed_geometry_floating_ports_CUDA_FP32'] for p in geometry_ports),
                        'Actual residual geometry complete caller coverage differs')
                require(len(holder['calls'])==4 and [v['role'] for v in holder['calls']]==list(range(4))
                        and all(v['artifact']['contains_parameter_weights'] is (v['role']==0)
                                and v['population']['head_ports']['contains_parameter_weights'] is (v['role']==0)
                                for v in holder['calls']), 'Typed parameter subset provenance differs')
                for call in holder['calls']:
                    require(len(call['population']['head_ports']['fields'])==2,
                            'Both independent heads must be captured on every frame')
                require(holder['forward_calls']==holder['full_forward_returns']==holder['observed_encoder_returns']==4 and len(holder['calls'])==4 and not holder['errors']
                        and holder['state_unchanged'],'Complete passive capture/state control failed')
                require(control['passed'],'4579 all52 terminal transparency control failed')
            except Exception as exc:
                error=dict(type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc())
                failures.append(dict(case_id=case.identity,error=error))
            for generated in directory.iterdir(): budget.adopt(generated)
            record=dict(schema='model_v3_geometry_head_moment_passive_case_v1',case_id=case.identity,
                original_measurement=measured,construction=construction[0] if construction else None,
                passive_capture=holder,terminal_control=control,error=error,
                no_local_module_replays=True,no_F64_model_or_local_reference_calls=True,scientific_adoption=False)
            leaf=budget.json(directory/'TRACE_CASE.json',record)
            rows.append(dict(case_id=case.identity,case_json=leaf,transparency_passed=error is None,
                             physical_criterion_passed=measured['passed'] if measured else None,
                             captured_roles=len(holder['calls']) if holder else 0,
                             forward_calls=holder['full_forward_returns'] if holder else 0,
                             observed_encoder_returns=holder['observed_encoder_returns'] if holder else 0,
                             node_stage_observations=sum(len(v['population']['stages']) for v in holder['calls']) if holder else 0,
                             geometry_observations=sum(len(v['population']['geometry']) for v in holder['calls']) if holder else 0,
                             projection_helper_calls=len(construction[0]['projection_ports']) if construction else 0,
                             geometry_helper_calls=len(construction[0]['geometry_ports']) if construction else 0,
                             head_observations=sum(len(v['population']['head_ports']['fields']) for v in holder['calls']) if holder else 0,
                             magnitude_norm_observations=sum(sum(h['original_norm_calls'] for h in v['population']['head_ports']['fields']) for v in holder['calls']) if holder else 0,
                             parameter_artifact_present=(directory/'role_0.npz').is_file(),
                             parameter_subset_bytes=sum(sum(a['nbytes'] for k,a in v['artifact']['arrays'].items()
                                                        if '__parameter__' in k) for v in holder['calls']) if holder else 0))
            # No failfast: retain all48 original cases even when a replay/transparency gate fails.
    except Exception as exc:
        failures.append(dict(scope='driver',type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc()))
    finally:
        try:
            after={path:ref(path,maximum=16<<20) for path in sources}
            budget.json(out/'sources_after.json',after)
            require(after==sources,'Source changed during capture')
        except Exception as exc:
            failures.append(dict(scope='source_after',type=type(exc).__name__,message=str(exc)))
        stage_count=sum(v['node_stage_observations'] for v in rows)
        geometry_count=sum(v['geometry_observations'] for v in rows)
        if len(rows)==48 and (stage_count!=1728 or geometry_count!=512):
            failures.append(dict(scope='coverage',node_stages=stage_count,geometry=geometry_count))
        if len(rows)==48 and (sum(v['head_observations'] for v in rows)!=384
                or sum(v['magnitude_norm_observations'] for v in rows)!=192
                or sum(v['parameter_subset_bytes'] for v in rows)!=48*263176
                or sum(v['projection_helper_calls'] for v in rows)!=2304
                or sum(v['geometry_helper_calls'] for v in rows)!=512):
            failures.append(dict(scope='head_parameter_projection_geometry_coverage'))
        complete=len(rows)==48 and not failures and all(v['transparency_passed'] for v in rows)
        result=dict(schema='model_v3_geometry_head_moment_passive_result_v1',
            status='PASSIVE_TRACE_COMPLETE_PENDING_ACTUAL_OUTER_C0' if complete else 'HOLD_RETAIN_ALL_AVAILABLE',
            job_id=os.environ.get('SLURM_JOB_ID'),cases=rows,failures=failures,
            ordinary_original_FP32_encoder_forwards=sum(v['observed_encoder_returns'] for v in rows),
            original_full_model_returns=sum(v['forward_calls'] for v in rows),
            expected_encoder_forwards=192,node_stage_observations=stage_count,geometry_observations=geometry_count,
            expected_node_stages=1728,expected_geometry_observations=512,
            head_observations=sum(v['head_observations'] for v in rows),
            magnitude_norm_observations=sum(v['magnitude_norm_observations'] for v in rows),
            actual_projection_helper_calls=sum(v['projection_helper_calls'] for v in rows),
            actual_geometry_helper_calls=sum(v['geometry_helper_calls'] for v in rows),
            contains_parameter_weights=any(v['parameter_artifact_present'] for v in rows),parameter_scope='Seeded synthetic two-charges-MLP subset only, once per case role0',
            parameter_subset_bytes=sum(v['parameter_subset_bytes'] for v in rows),
            parameter_bytes_scope='Completed typed artifacts only; every written role0 is flagged even after later metadata failure',
            local_module_replays=0,full_FP64_encoder_forwards=0,
            original1492_seeded_parameters=True,baseline_terminal_job='4524579',
            source_before_after_equal=after==sources,trace_bytes_before_final_result=budget.bytes,
            trace_cap_bytes=512<<20,trace_numeric_bytes=budget.numeric_bytes,
            physical_passed=sum(v['physical_criterion_passed'] is True for v in rows),
            physical_failed=sum(v['physical_criterion_passed'] is False for v in rows),
            measurement_scope='FRESH_PASSIVE_TRACE_NOT_A_NEW_CANDIDATE_OR_CAUSAL_RANKING',
            scientific_adoption=False)
        budget.json(out/'RESULT.json',result)
        if complete: budget.json(out/'COMPLETE.json',dict(result=ref(out/'RESULT.json')))
    return 0 if complete else 1

if __name__=='__main__':
    raise SystemExit(main())
