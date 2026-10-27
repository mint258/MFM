#!/usr/bin/env python3
"""Three CPU head routes on fixed HISTORICAL1561 H64, not a new encoder candidate."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import socket
import sys
import traceback
from counterfactual_common import (B,HERE,INPUT_CAP,REPLAY_BOUND,Budget,equal_case,helpers,
    load_H64,need,read_json,reference,validate_authorities,write_new)

def max_record(value):
    flat=int(value.abs().argmax()); width=value.shape[-1]
    return {'maxabs':float(value.abs().max()), 'argmax':[flat//width,flat%width],
            'signed_value':float(value.reshape(-1)[flat]), 'components_gt_1e_5':int((value.abs()>1e-5).sum())}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs',type=Path,required=True)
    parser.add_argument('--inputs-sha256',required=True)
    parser.add_argument('--source-pins-sha256',required=True)
    parser.add_argument('--expected-node',choices=['compute-0-'+str(i) for i in (2,*range(8,20))],required=True)
    parser.add_argument('--output-root',type=Path,required=True)
    a=parser.parse_args()
    need(os.environ.get('CUDA_VISIBLE_DEVICES')=='' and socket.gethostname().split('.')[0]==a.expected_node
         and os.environ.get('SLURM_JOB_ID','').isdigit() and int(os.environ.get('SLURM_CPUS_PER_TASK','0'))==16,
         'Actual16CPU-only allocation required')
    budget=Budget()
    input_ref={**reference(a.inputs),'sha256':a.inputs_sha256}
    pins_ref={**reference(HERE/'source_pins_v1.json'),'sha256':a.source_pins_sha256}
    inputs,pins=budget.json(input_ref),budget.json(pins_ref)
    need(inputs['schema']=='model_v3_H0_interface_quantization_CPU_inputs_v1'
         and pins['schema']=='model_v3_H0_interface_quantization_CPU_source_pins_v1'
         and pins['inputs']==input_ref and len(inputs['cases'])==48
         and inputs['combined_input_cap_bytes']==INPUT_CAP
         and inputs['diagnostic_scalar_replay_absolute_bound']==REPLAY_BOUND
         and inputs['physical_absolute_threshold']==1e-5 and inputs['physical_relative_threshold']==0,
         'Exact predeclared finite counterfactual scope required')
    sources={leaf['path']:leaf for leaf in pins['files']+pins['protected_dependencies']+inputs['source_refs']}
    sources[pins_ref['path']]=pins_ref
    for leaf in sources.values():budget.add(leaf)
    for leaf in inputs['controls']:budget.json(leaf)
    root64,root32=budget.json(inputs['Root1561']),budget.json(inputs['Root1838'])
    need(root64['status']=='ROOT_METADATA_VERIFIED_DIAGNOSTIC_ONLY' and root64['job_id']=='4521561'
         and root32['status']=='ACTUAL_GPU_C0_FULL48_EXTERNAL52_REPLAY_CLOSED_CPU_DIAGNOSTIC_ALLOWED',
         'Actual closed input authorities required')
    validate_authorities(root64,root32,budget)
    for key in ('historical_analysis','centered_manifest','original1492_manifest','historical_capture_complete','centered_request'):
        budget.json(inputs[key])
    need(not a.output_root.exists(),'Fresh diagnostic output required');a.output_root.mkdir()
    write_new(a.output_root/'sources_before.json',sources)
    facade,old=helpers()
    result,failure=None,None
    try:
        import numpy as np
        import torch
        import phychem_mfm
        need(Path(phychem_mfm.__file__).resolve()==(Path(inputs['candidate_repository'])/'current/phychem_mfm/__init__.py').resolve(),
             'Exact published centered package required for unchanged CPU bank')
        torch.set_num_threads(4)
        tiny=old.tiny_selfcheck()
        case_refs=[];baseline_failures=[];all_csv=[];call_counts={'A':0,'B':0,'C':0}
        for ordinal,entry in enumerate(inputs['cases']):
            new=budget.json(entry['centered_capture']['capture_case'])
            original=budget.json(entry['original1492_capture'])
            historical=budget.json(entry['historical1561'])
            alignment=equal_case(original,new,historical)
            need(alignment==entry['alignment'],'Prepared alignment changed')
            budget.add(new['packed']['file'],payload=True)
            case,bank,calls=old.decode_case(entry['centered_capture'])
            h64=load_H64(historical,budget)
            # Explicit actual-array check against1492 headers, not only1838 declaration.
            for role,(_,pos,batch,_) in enumerate(calls):
                for name,tensor in (('pos',pos),('batch',batch)):
                    header=original['packed']['arrays'][original['calls'][role]['keys'][name]]
                    need(hashlib.sha256(tensor.numpy().tobytes()).hexdigest()==header['sha256'],
                         'Actual1838 role geometry bytes differ from original1492')
            route={'A':[],'B':[],'C':[]};quant=[]
            with torch.inference_mode():
                for role,(h,(_,pos,batch,_)) in enumerate(zip(h64,calls)):
                    rounded=h.to(torch.float32)  # exactly ONE F64->F32 quantization, shared by B and C
                    promoted=rounded.to(torch.float64)  # lossless promotion of those exact F32 values
                    need(torch.equal(promoted.to(torch.float32).view(torch.int32),rounded.view(torch.int32)),
                         'F32-to-F64 promotion did not preserve rounded values')
                    quant.append(max_record(promoted-h))
                    route['A'].append(old.functional64(bank,h,pos,batch));call_counts['A']+=1
                    route['B'].append(old.functional64(bank,promoted,pos,batch));call_counts['B']+=1
                    route['C'].append({k:v.double() for k,v in bank(rounded,batch,pos,
                        enabled_groups=('P',),enabled_fields=facade.FIELDS).items()});call_counts['C']+=1
                observations=[]
                for index,transform in enumerate(case['transforms']):
                    rotation=torch.tensor(transform['rotation_float64'],dtype=torch.float64)
                    for field in facade.FIELDS:
                        vector=field=='p_dipole'
                        drift={name:values[index+1][field]-old.linear_transform(values[0][field],rotation,vector)
                               for name,values in route.items()}
                        saved=next(row for row in historical['terminal_observations']
                                   if row['field']==field and row['transform']==transform['name'])
                        control=saved['full_encoder_functional_head_FP64_D'];r,c=control['argmax']
                        fixed=saved['at_same_original_GPU_argmax'];fr,fc=fixed['row'],fixed['component']
                        errors={'maxabs':abs(float(drift['A'].abs().max())-control['maxabs']),
                            'saved_reference_argmax_signed':abs(float(drift['A'][r,c])-control['signed_value']),
                            'fixed_old_GPU_argmax_signed':abs(float(drift['A'][fr,fc])-fixed['FP64'])}
                        replay=max(errors.values())<=REPLAY_BOUND
                        if not replay:baseline_failures.append({'case_id':case['case_id'],'field':field,
                            'transform':transform['name'],'absolute_errors':errors})
                        effects={'B_minus_A':drift['B']-drift['A'],'C_minus_B':drift['C']-drift['B']}
                        values={**drift,**effects}
                        fixed_components={}
                        for name,value in drift.items():
                            flat=int(value.abs().argmax());width=value.shape[-1];rr,cc=flat//width,flat%width
                            fixed_components[name+'_argmax']={'row':rr,'component':cc,
                                'signed_tuple':{key:float(v[rr,cc]) for key,v in values.items()}}
                        observations.append({'field':field,'transform':transform['name'],
                            'signed_components':{k:v.tolist() for k,v in values.items()},
                            'statistics':{k:max_record(v) for k,v in values.items()},
                            'same_component_comparisons':fixed_components,
                            'A_saved1561_scalar_controls':{'absolute_errors':errors,'bound':REPLAY_BOUND,'passed':replay,
                                'scope':'SAVED_SCALAR_CONTROLS_ONLY_NOT_ALL_TERMINAL_BITWISE_REPLAY'}})
                        for name,value in drift.items():
                            all_csv.append([case['case_id'],field,transform['name'],name,float(value.abs().max()),
                                            int((value.abs()>1e-5).sum()),replay])
            arr,names,extras=facade.state_arrays(bank)
            need(facade.tensor_state_identity(arr,names,extras)==case['bank_state_identity'],'CPU bank changed')
            need(len(observations)==9,'Every case requires all3fields/all3transforms')
            case_refs.append({'case_id':case['case_id'],'result':write_new(a.output_root/('case_%02d.json'%ordinal),
                {'case_id':case['case_id'],'alignment':alignment,'historical_H64_lineage':'1561_legacy_shadow_algorithm_not_centered1838_H0',
                 'original1492_position_source':entry['original1492_capture'],'actual1838_position_source':entry['centered_capture']['capture_case'],
                 'bank_state_identity':case['bank_state_identity'],'H64_to_F32_rounding_by_role':quant,'observations':observations})})
        need([row['case_id'] for row in case_refs]==inputs['case_ids'] and call_counts=={'A':192,'B':192,'C':192},
             'All48/192head calls per arm required')
        # Every actually imported project source must belong to the verified declared package.
        loaded={}
        prefix=Path(inputs['candidate_repository'])/'current'
        for module in tuple(sys.modules.values()):
            raw=getattr(module,'__dict__',{}).get('__file__') if module is not None else None
            if isinstance(raw,str) and Path(raw).is_absolute() and raw.endswith('.py') and Path(raw).is_relative_to(prefix):
                need(str(Path(raw).absolute()) in sources,'Unexpected unbound project import: '+raw)
                loaded[raw]=sources[str(Path(raw).absolute())]
        with (a.output_root/'metrics.csv').open('x',newline='') as stream:
            writer=csv.writer(stream);writer.writerow(['case_id','field','transform','route','maxabs_D','components_gt_1e_5','A_scalar_replay_passed'])
            writer.writerows(all_csv);stream.flush();os.fsync(stream.fileno())
        result={'schema':'model_v3_H0_interface_quantization_CPU_result_v1',
            'status':'DIAGNOSTIC_COMPLETE' if not baseline_failures else 'BASELINE_REPLAY_MISMATCH_HOLD',
            'cases':case_refs,'case_count':48,'observations_per_route':432,'head_calls_by_route':call_counts,
            'encoder_forwards':0,'baseline_scalar_replay_bound':REPLAY_BOUND,'baseline_failures':baseline_failures,
            'physical_threshold':{'absolute':1e-5,'relative':0},'combined_unique_input_bytes':budget.total,
            'combined_input_cap_bytes':INPUT_CAP,'actually_loaded_project_sources':loaded,'tiny_controls':tiny,
            'CPU_environment':{'python':sys.executable,'resolved_python':str(Path(sys.executable).resolve()),
                'python_version':sys.version,'torch_version':str(torch.__version__),'numpy_version':str(np.__version__),
                'torch_threads':torch.get_num_threads(),'interop_threads':torch.get_num_interop_threads(),
                'thread_environment':{key:os.environ.get(key) for key in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS')}},
            'A_to_B_scope':'One quantization of these fixed historical H64 values; not a universal FP32 floor',
            'B_to_C_scope':'CPU head dtype plus implementation/backend; not a production CUDA equivalence claim',
            'H0_API_changed':False,'FP64_production':False,'scientific_adoption':False}
        write_new(a.output_root/'RESULT.json',result)
        if baseline_failures:failure={'type':'BaselineReplayMismatch','message':'All48 retained; attribution held'}
    except BaseException as error:
        failure={'type':type(error).__name__,'message':str(error),'traceback':traceback.format_exc()}
    finally:
        after={path:reference(path) for path in sources}
        write_new(a.output_root/'sources_after.json',after)
        if after!=sources:failure={'earlier':failure,'source_after':'Source changed'}
        if failure:write_new(a.output_root/'FAILED.json',failure)
        elif result is not None:write_new(a.output_root/'COMPLETE.json',{'result':reference(a.output_root/'RESULT.json'),'sources_unchanged':True})
    return 1 if failure else 0

if __name__=='__main__':
    raise SystemExit(main())