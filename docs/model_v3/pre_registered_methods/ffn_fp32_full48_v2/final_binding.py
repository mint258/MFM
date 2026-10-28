"""Root-only stdlib evidence/source binding, optional finalization; never submits."""
from __future__ import annotations
import argparse
import json
import os
import re
from pathlib import Path
from ffn_publication import (
    ROOT, HERE, BRANCH, METADATA_NAMES, SCIENCE_NAMES, bound, need, reference,
    verify_metadata_evidence, metadata_publication_gate, publication)

BASE=Path('/share/home/zixiao/descriptor_analysis')

def save(path,value):
    raw=(json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
    need(len(raw)<=2<<20,'Bounded control metadata required')
    with path.open('xb') as stream:
        stream.write(raw);stream.flush();os.fsync(stream.fileno())
    fd=os.open(str(path.parent),os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)

def prepare(inputs,input_ref):
    need(inputs['schema']=='model_v3_ffn_FP32_GPU_metadata_binding_inputs_v1'
         and inputs['status']=='ROOT_METADATA_BINDING_ONLY_NO_SUBMISSION'
         and inputs['stage'] in ('SOURCE_BOUND_DRAFT','FINAL'),
         'Explicit Root source binding stage required')
    need(os.getuid()==1278,'Actual Root account required')
    final=inputs['stage']=='FINAL'
    request=bound(inputs['execution_request_DRAFT'])
    dependencies=bound(inputs['dependencies_DRAFT'])
    support=bound(inputs['runtime_support_refs'])
    science=bound(inputs['science_inventory'])
    metadata=bound(inputs['metadata_inventory'])
    need(science['schema']=='model_v3_ffn_FP32_complete48_science_source_inventory_v1'
         and len(science['files'])==7
         and {Path(x['path']).name for x in science['files']}==SCIENCE_NAMES|{'METHOD.md'},
         'Frozen six science leaves and METHOD required')
    need(metadata['schema']=='model_v3_ffn_FP32_GPU_metadata_source_inventory_v1'
         and len(metadata['files'])==2
         and {Path(x['path']).name for x in metadata['files']}==METADATA_NAMES,
         'Frozen two metadata sources required')
    need(support['schema']=='model_v3_projection_FP32_recorded_runtime_support_refs_v1'
         and support['status']=='RECORDED_ORIGINAL_ACTIVE_SUPPORT_NOT_NEW_QA_AUTHORITY'
         and dependencies['historical_1492_parameter_JSON_raw_refs']==support['original_parameter_JSON_refs'],
         'Original active support and parameter JSON lineage differs')
    candidate=publication(inputs['candidate_publication'],branch=BRANCH)
    request['publication_receipt']=inputs['candidate_publication']
    request['public_commit']=candidate['public_code_sha']
    request['public_files']=candidate['files']
    method=publication(inputs['method_publication'],branch='model-v3')
    request['method_publication']=inputs['method_publication']
    request['method_public_commit']=method['public_code_sha']
    request['method_public_tree']=method['tree_sha']
    request['method_publication_exact_files']=method['method_sources']
    request['metadata_inventory']=inputs['metadata_inventory']
    request['metadata_publication']=inputs['metadata_publication']
    if final:
        need(inputs['metadata_publication']==inputs['method_publication'],
             'Final metadata and science must share the same actual nine-leaf publication')
        own_public=publication(inputs['metadata_publication'],branch='model-v3')
        request['metadata_public_commit']=own_public['public_code_sha']
        request['metadata_public_tree']=own_public['tree_sha']
    else:
        need(inputs['metadata_publication'] is None,
             'DRAFT does not pretend future metadata is public; use explicit FINAL later')
        request['metadata_public_commit']=request['metadata_public_tree']=None
    full=bound(request['full_cpu_root_closure'])
    need(full['job_id']=='4524602' and full['code_commit']==request['local_commit'],
         'Actual same-code full CPU certificate required')
    sources={}
    def add(path,sha,size=None):
        path=Path(path).absolute()
        need(path.is_relative_to(BASE) and path.suffix.lower() not in
             ('.npz','.pt','.pth','.wandb','.lmdb','.parquet','.pkl'),
             'Only project source/metadata, never scientific payload')
        current=reference(path,maximum=16<<20)
        need(current['sha256']==sha and (size is None or current['bytes']==size),
             'Current source/evidence differs: '+str(path))
        need(str(path) not in sources or sources[str(path)]==current,
             'Conflicting duplicate raw source')
        sources[str(path)]=current
    def add_ref(value):
        need(type(value) is dict and set(value)=={'path','bytes','sha256'}
             and type(value['path']) is str and type(value['bytes']) is int
             and value['bytes']>=0 and type(value['sha256']) is str
             and re.fullmatch('[0-9a-f]{64}',value['sha256']),
             'Exact typed three-field metadata rawref required')
        add(value['path'],value['sha256'],value['bytes'])
    # Bind all eight authored/public leaves, including documentation outside the runtime projection.
    for leaf in bound(request['candidate_source_freeze'])['files']:
        add_ref({key:leaf[key] for key in ('path','bytes','sha256')})
    before=bound(full['source_before'])
    # Use the actual current candidate full-CPU map, never a Core path substitution.
    for name,sha in before['runtime']['project_source_sha256'].items():
        relative=Path(name)
        need(not relative.is_absolute() and '..' not in relative.parts,
             'Full project source names must be relative')
        add(ROOT/relative,sha)
    # The original full-runtime external-source protocol saves path+SHA only.
    # Preserve that evidence; current size is measured, never invented as saved.
    for leaf in before['runtime']['external_source_refs'].values():
        need(type(leaf) is dict and set(leaf)=={'path','sha256'}
             and type(leaf['path']) is str and type(leaf['sha256']) is str
             and re.fullmatch('[0-9a-f]{64}',leaf['sha256']),
             'Exact typed two-field full-runtime external-source descriptor required')
        add(leaf['path'],leaf['sha256'])
    for leaf in support['files']:add_ref(leaf)
    for leaf in support['original_parameter_JSON_refs']:add_ref(leaf)
    evidence=[input_ref,inputs['execution_request_DRAFT'],inputs['dependencies_DRAFT'],
        inputs['runtime_support_refs'],inputs['science_inventory'],inputs['metadata_inventory'],
        request['candidate_source_freeze'],request['full_cpu_root_closure'],
        request['publication_receipt'],request['original_capture_manifest'],inputs['method_publication']]
    evidence.extend(full[key] for key in ('summary','source_before','source_after','supervisor'))
    evidence.extend(full['XML']);evidence.extend(full['actual_four_exec_receipts'].values())
    for public in (method,):
        c=bound(public['checker_closure'])
        evidence.extend((public['checker_closure'],c['source_freeze'],c['checker_log'],c['supervisor']))
    if final:
        evidence.append(inputs['metadata_publication'])
        c=bound(own_public['checker_closure'])
        evidence.extend((own_public['checker_closure'],c['source_freeze'],c['checker_log'],c['supervisor']))
    for leaf in evidence:add_ref(leaf)
    for leaf in science['files']+metadata['files']:add_ref(leaf)
    request['status']=('FINAL_BOUND_PUBLIC_FFN_FP32_REQUEST' if final else
                       'DRAFT_SOURCE_BOUND_CANDIDATE_AND_METHOD_PUBLIC_METADATA_PUBLICATION_PENDING')
    request['executable']=final
    request['source_refs']=[sources[path] for path in sorted(sources)]
    request['candidate_QA_evidence']=[request['full_cpu_root_closure']]
    request['final_source_refs_pending_Root_server_fill']=False
    request['publication_verifier_pending']=not final
    request['no_GPU_execution_or_scientific_acceptance']=True
    rows=verify_metadata_evidence(request)
    if final:rows.extend(metadata_publication_gate(request))
    for path,expected in sources.items():
        need(reference(path,maximum=16<<20)==expected,'Source changed during Root binding')
    target=HERE/('execution_request_v1.json' if final else 'execution_request_source_bound_DRAFT_v1.json')
    pin_target=HERE/('source_pins_v1.json' if final else 'source_pins_source_bound_DRAFT_v1.json')
    outcome_target=HERE/('FINAL_BINDING_RESULT_v1.json' if final else 'FINAL_BINDING_DRAFT_RESULT_v1.json')
    need(not any(p.exists() for p in (target,pin_target,outcome_target)),
         'Fresh outputs only; preserve all previous DRAFT/failures')
    # Acyclic order: source/code/input graph -> request -> pins -> result.
    # Generated request/pins/result are deliberately absent from source_refs.
    save(target,request)
    own=science['files']+metadata['files'];own_paths={r['path'] for r in own}
    pins={'schema':'model_v3_ffn_FP32_complete48_GPU_launch_source_pins_v1',
        'status':'FINAL_SOURCE_BOUND_PUBLIC_NO_GPU_ACCEPTANCE' if final else 'DRAFT_NOT_ADMITTED',
        'files':own,'protected_dependencies':[sources[p] for p in sorted(sources) if p not in own_paths],
        'execution_request':reference(target),'attention_aggregation_mode':'centered_fp32_v1',
        'attention_projection_mode':'blocked_k64_compensated_fp32_v1',
        'geometry_mode':'residual_expansion_fp32_v1','expected_geometry_helper_calls':512,
        'ffn_projection_mode':'blocked_k64_compensated_fp32_v1','expected_FFN_helper_calls':2304,
        'expected_FFN_K64_leaf_calls':69120,'expected_FFN_sites':12,
        'ordinary_numeric_mode':'compensated_fp32_v1','all_FP32_fixed_FFN_projection_candidate':True,
        'case_count':48,'scientific_encoder_forwards':192,'full_FP64_encoder_forwards':0,
        'whole_output_bytes':2147483648,'private_bytes':2147483648,
        'RSS_bytes':30064771072,'wall_seconds':1100,'scientific_adoption':False}
    save(pin_target,pins)
    outcome={'schema':'model_v3_ffn_FP32_GPU_metadata_binding_result_v1',
        'status':'FINAL_METADATA_BOUND_NO_SUBMISSION_NO_SCIENCE_PASS' if final else 'DRAFT_BOUND_NOT_ADMITTED',
        'inputs':inputs,'execution_request':reference(target),'source_pins':reference(pin_target),
        'source_count':len(sources),'verified_metadata':rows,
        'CPU_optional_skips_do_not_authorize_CUDA_or_real_D3':True,
        'no_Torch_model_NPZ_SDK_network_or_Slurm':True,
        'acyclic_outputs_not_in_source_refs':True,
        'external_source_bytes_origin':'Current raw reference; original descriptor stores only path+sha256'}
    save(outcome_target,outcome)
    return {'result':reference(outcome_target),'request':reference(target),'pins':reference(pin_target)}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs',type=Path,required=True)
    parser.add_argument('--inputs-sha256',required=True)
    args=parser.parse_args()
    actual=reference(args.inputs)
    need(actual['sha256']==args.inputs_sha256,'Exact Root input rawSHA required')
    print(json.dumps(prepare(bound(actual),actual),sort_keys=True))
    return 0

if __name__=='__main__':raise SystemExit(main())
