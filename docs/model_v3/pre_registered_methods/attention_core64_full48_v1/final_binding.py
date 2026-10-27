"""Root-only stdlib source binding to fresh DRAFT outputs; never submits/admit."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
from core64_publication import bound, need, reference, verify_metadata_evidence

HERE=Path(__file__).absolute().parent
BASE=Path('/share/home/zixiao/descriptor_analysis')


def save(path,value):
    raw=(json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
    need(len(raw)<=2<<20,'Bounded DRAFT control metadata required')
    with path.open('xb') as stream:
        stream.write(raw);stream.flush();os.fsync(stream.fileno())
    fd=os.open(str(path.parent),os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)


def prepare(inputs):
    need(inputs['schema']=='model_v3_core64_GPU_metadata_binding_inputs_DRAFT_v2'
         and inputs['status']=='DRAFT_ACTUAL_QA_READY_METHOD_PUBLICATION_AND_ADMISSION_PENDING',
         'Only explicit DRAFT source binding inputs accepted')
    need(os.getuid()==1278,'Actual Root account required')
    request=bound(inputs['execution_request_DRAFT'])
    dependencies=bound(inputs['dependencies_DRAFT'])
    science=bound(inputs['science_inventory'])
    metadata=bound(inputs['metadata_inventory'])
    need(science['schema']=='model_v3_core64_GPU_science_source_inventory_v1'
         and len(science['science_files'])==6,'Exact frozen six science leaves required')
    need(metadata['schema']=='model_v3_core64_GPU_actual_metadata_source_inventory_v2'
         and len(metadata['files'])==2,'Exact actual metadata verifier/binder source required')
    related=bound(request['related_cpu_root_closure'])
    full=bound(request['full_cpu_root_closure'])
    need(full['schema']=='model_v3_candidate_single_parent_full_Root_closure_v1'
         and full['job_id']=='4524207','Actual supplied full115 certificate required')
    sources={}
    expected={}
    def add(path,sha,bytes_expected=None):
        path=Path(path).absolute()
        need(path.is_relative_to(BASE) and not path.is_symlink(),'Project source/evidence only')
        current=reference(path,maximum=16<<20)
        need(current['sha256']==sha and (bytes_expected is None or current['bytes']==bytes_expected),
             'Current source/evidence differs: '+str(path))
        if str(path) in sources:need(sources[str(path)]==current,'Conflicting duplicate source')
        sources[str(path)]=current;expected[str(path)]=sha
    def add_ref(ref):add(ref['path'],ref['sha256'],ref['bytes'])
    # The actual related Root map contains the real new W and source authorities,
    # not an old performance/candidate prefix substitution.
    need(dependencies['candidate_related_QA_recorded_source_sha256']==related['full_source_map'],
         'Recorded actual related source graph differs')
    for path,sha in related['full_source_map'].items():add(path,sha)
    for ref in dependencies['recorded_active_runtime_and_parameter_metadata_refs']:add_ref(ref)
    before=bound(full['source_before'])
    for name,sha in before['runtime']['project_source_sha256'].items():
        add(str(Path(request['repository'])/name),sha)
    for ref in before['runtime']['external_source_refs'].values():
        add(ref['path'],ref['sha256'])
    evidence=[request['publication_receipt'],request['related_cpu_root_closure'],
              request['full_cpu_root_closure'],request['candidate_source_freeze'],
              inputs['execution_request_DRAFT'],inputs['dependencies_DRAFT'],
              inputs['science_inventory'],inputs['metadata_inventory']]
    evidence.extend(full[key] for key in ('summary','source_before','source_after','supervisor'))
    evidence.extend(full['XML']);evidence.extend(full['actual_four_exec_receipts'].values())
    for ref in evidence:add_ref(ref)
    for ref in science['science_files']+metadata['files']:add_ref(ref)
    # These are only source-bound drafts. They cannot satisfy runtime admission.
    request['status']='DRAFT_SOURCE_BOUND_ACTUAL_QA_VERIFIED_METHOD_PUBLICATION_PENDING'
    request['source_refs']=[sources[path] for path in sorted(sources)]
    request['candidate_QA_evidence']=[request['related_cpu_root_closure'],request['full_cpu_root_closure']]
    qa_rows=verify_metadata_evidence(request)
    for path,sha in expected.items():
        need(reference(path,maximum=16<<20)['sha256']==sha,'Source changed during Root metadata binding')
    target=HERE/'execution_request_source_bound_DRAFT_v2.json'
    pin_target=HERE/'source_pins_source_bound_DRAFT_v2.json'
    result_target=HERE/'FINAL_BINDING_DRAFT_RESULT_v2.json'
    need(not any(path.exists() for path in (target,pin_target,result_target)),
         'Fresh DRAFT outputs only; no overwrite')
    save(target,request)
    own=science['science_files']+metadata['files']
    own_paths={r['path'] for r in own}
    pins={'schema':'model_v3_core64_attention_diagnostic_complete48_GPU_launch_source_pins_v1',
        'status':'DRAFT_SOURCE_BOUND_ALL_ACTUAL_QA_CLOSED_METHOD_PUBLICATION_PENDING_NOT_ADMITTED',
        'files':own,'protected_dependencies':[sources[p] for p in sorted(sources) if p not in own_paths],
        'execution_request':reference(target),
        'attention_aggregation_mode':'centered_core64_diagnostic_v1',
        'ordinary_numeric_mode':'compensated_fp32_v1','case_count':48,
        'scientific_encoder_forwards':192,'full_FP64_encoder_forwards':0,
        'declared_mixed_core64_encoder_forwards':192,'mixed_precision_diagnostic_only':True,
        'formal_FP32_gate_satisfied':False,'model_freeze_candidate':False,
        'whole_output_bytes':2147483648,'private_bytes':2147483648,
        'RSS_bytes':30064771072,'wall_seconds':1100}
    save(pin_target,pins)
    outcome={'schema':'model_v3_core64_GPU_actual_QA_source_binding_DRAFT_result_v2',
        'status':'DRAFT_BOUND_NO_FINAL_RUNTIME_FILES_NO_ADMISSION',
        'inputs':inputs,'execution_request_DRAFT':reference(target),
        'source_pins_DRAFT':reference(pin_target),'source_count':len(sources),
        'actual_QA_metadata_verified':qa_rows,
        'CPU_optional_skips_do_not_authorize_CUDA_or_real_D3':True,
        'source_only_no_Torch_model_NPZ_SDK_network_or_Slurm':True,
        'next':'Root source review/current hashes and exact-source method publication, then separate final runtime binding and fresh GPU admission'}
    save(result_target,outcome)
    return {'result':reference(result_target),'request_DRAFT':reference(target),'pins_DRAFT':reference(pin_target)}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs',type=Path,required=True)
    parser.add_argument('--inputs-sha256',required=True)
    args=parser.parse_args()
    actual=reference(args.inputs)
    need(actual['sha256']==args.inputs_sha256,'Explicit Root DRAFT input rawSHA required')
    print(json.dumps(prepare(bound(actual)),sort_keys=True))
    return 0


if __name__=='__main__':raise SystemExit(main())
